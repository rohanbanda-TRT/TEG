from __future__ import annotations

import json
from typing import Any

from google import genai
from google.genai import types

from app.llm.base import BaseModelT, LLMClient, LLMMessage, ToolCall, ToolTurn
from config.settings import get_settings


def _to_contents(messages: list[LLMMessage]) -> list[types.Content]:
    role_map = {"user": "user", "assistant": "model"}
    return [
        types.Content(
            role=role_map[m["role"]],
            parts=[types.Part.from_text(text=m["content"])],
        )
        for m in messages
    ]


def _contents_with_tools(messages: list) -> list[types.Content]:
    """Like _to_contents but understands {"role": "tool", ...} results."""
    role_map = {"user": "user", "assistant": "model"}
    out: list[types.Content] = []
    for m in messages:
        if m.get("role") == "tool":
            # Gemini carries function results on a USER-role turn.
            out.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=m.get("name", m["tool_call_id"]),
                            response={"result": m["content"]},
                        )
                    ],
                )
            )
        else:
            out.append(
                types.Content(
                    role=role_map[m["role"]],
                    parts=[types.Part.from_text(text=m["content"])],
                )
            )
    return out


# ---------------------------------------------------------------------------
# The Gemini Developer API rejects JSON schemas containing `additionalProperties`
# (which pydantic emits for free-form `dict` fields). We sanitise the schema:
#   - drop `additionalProperties` everywhere
#   - inline `$ref`/`$defs`
#   - turn a property-less `object` (an open dict) into a `string`, and remember
#     it so we can json.loads() that field back into a dict after the call.
# ---------------------------------------------------------------------------
_STRIP_KEYS = {"additionalProperties", "$schema", "title", "default"}


def _resolve_refs(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            name = node["$ref"].split("/")[-1]
            return _resolve_refs(defs.get(name, {}), defs)
        return {k: _resolve_refs(v, defs) for k, v in node.items()}
    if isinstance(node, list):
        return [_resolve_refs(x, defs) for x in node]
    return node


def _sanitise(node: Any, path: str, coerced: set[str]) -> Any:
    if isinstance(node, list):
        return [_sanitise(x, path, coerced) for x in node]
    if not isinstance(node, dict):
        return node

    node = {k: v for k, v in node.items() if k not in _STRIP_KEYS}

    # An open object: `type: object` with no `properties` -> ask for a JSON string.
    if node.get("type") == "object" and "properties" not in node:
        coerced.add(path)
        return {"type": "string"}

    out: dict[str, Any] = {}
    for k, v in node.items():
        if k == "properties" and isinstance(v, dict):
            out[k] = {
                pk: _sanitise(pv, f"{path}.{pk}" if path else pk, coerced)
                for pk, pv in v.items()
            }
        elif k in ("items", "anyOf", "oneOf", "allOf", "prefixItems"):
            out[k] = _sanitise(v, path, coerced)
        else:
            out[k] = _sanitise(v, path, coerced)
    return out


def _prepare_schema(schema: type[BaseModelT]) -> tuple[dict[str, Any], set[str]]:
    raw = schema.model_json_schema()
    defs = raw.get("$defs", {})
    resolved = _resolve_refs(raw, defs)
    if isinstance(resolved, dict):
        resolved.pop("$defs", None)
    coerced: set[str] = set()
    sane = _sanitise(resolved, "", coerced)
    return sane, coerced


def _coerce_back(data: dict[str, Any], coerced: set[str]) -> dict[str, Any]:
    for field in coerced:
        # only top-level fields are coerced in practice
        top = field.split(".")[0]
        val = data.get(top)
        if isinstance(val, str):
            try:
                data[top] = json.loads(val) if val.strip() else {}
            except (ValueError, TypeError):
                data[top] = {}
    return data


class GeminiClient(LLMClient):
    def __init__(self) -> None:
        s = get_settings()
        self._client = genai.Client(api_key=s.gemini_api_key)
        self._model_main = s.llm_model_main

    async def generate(
        self, *, system: str, messages: list[LLMMessage],
        model: str | None = None, max_tokens: int = 2048, temperature: float = 0.3,
    ) -> str:
        # gemini-flash spends part of its budget on internal reasoning tokens; a
        # too-small ceiling can yield empty visible text. Retry once with headroom.
        for attempt, cap in enumerate((max(max_tokens, 1024), max(max_tokens * 2, 4096))):
            resp = await self._client.aio.models.generate_content(
                model=model or self._model_main,
                contents=_to_contents(messages),
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=cap,
                    temperature=temperature,
                ),
            )
            text = (resp.text or "").strip()
            if text:
                return text
            if attempt == 1:
                raise RuntimeError("gemini returned no text output after retry")
        return ""  # unreachable

    async def generate_structured(
        self, *, system: str, messages: list[LLMMessage],
        schema: type[BaseModelT], model: str | None = None,
    ) -> BaseModelT:
        sane_schema, coerced = _prepare_schema(schema)
        resp = await self._client.aio.models.generate_content(
            model=model or self._model_main,
            contents=_to_contents(messages),
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=sane_schema,
                # generous ceiling: a truncated JSON response is unparseable,
                # and gemini-flash spends part of the budget on internal tokens.
                max_output_tokens=4096,
            ),
        )
        raw = (resp.text or "").strip()
        if not raw:
            raise RuntimeError("gemini returned no structured output (possibly truncated)")
        data = json.loads(raw)
        if coerced:
            data = _coerce_back(data, coerced)
        return schema.model_validate(data)

    async def generate_with_tools(
        self, *, system: str, messages: list, tools: list[dict],
        model: str | None = None, max_tokens: int = 2048, temperature: float = 0.2,
    ) -> ToolTurn:
        decls = [
            types.FunctionDeclaration(
                name=t["name"],
                description=t.get("description", ""),
                parameters=_sanitise(t.get("parameters", {"type": "object"}), "", set()),
            )
            for t in tools
        ]
        resp = await self._client.aio.models.generate_content(
            model=model or self._model_main,
            contents=_contents_with_tools(messages),
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max(max_tokens * 2, 4096),
                tools=[types.Tool(function_declarations=decls)],
            ),
        )
        calls = [
            ToolCall(id=f"c{i}", name=fc.name, args=dict(fc.args or {}))
            for i, fc in enumerate(resp.function_calls or [])
        ]
        return ToolTurn(tool_calls=calls, text=(resp.text or "").strip())
