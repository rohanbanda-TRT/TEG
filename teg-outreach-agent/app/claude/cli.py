"""Drive the `claude` CLI as a subprocess for structured generation.

The CLI runs headless (`-p`), streams line-delimited JSON events, and validates
its final answer against a JSON Schema we pass in — the schema result arrives on
the terminal `result` event as ``structured_output``.

Security note: prospect-supplied text flows into these prompts, so `run()`
grants **no tools** by default. An injection attempt can then only produce bad
text for our own guardrails to reject, never tool execution or filesystem
access. Callers that genuinely need a capability (research needs the web) pass
an explicit, narrow `tools` list.

Auth comes from the machine's own `claude` login, with ANTHROPIC_API_KEY as an
override. Anthropic requires API-key auth for third-party products, so a
deployment serving real users must set that key.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable

from app.obs import get_logger

_log = get_logger("claude.cli")

SpawnFn = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class ClaudeProgress:
    """Streamed-token tick, for surfacing "still working" to a caller."""
    chars_streamed: int


@dataclass(frozen=True)
class ClaudeResult:
    data: Any
    cost_usd: float | None = None
    session_id: str | None = None


@dataclass(frozen=True)
class ClaudeError:
    message: str
    retryable: bool = False


ClaudeEvent = ClaudeProgress | ClaudeResult | ClaudeError


async def _default_spawn(program: str, *args: str, **kwargs: Any):
    return await asyncio.create_subprocess_exec(program, *args, **kwargs)


@dataclass
class ClaudeCli:
    spawn: SpawnFn = _default_spawn
    api_key: str = ""

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        if self.api_key:
            env["ANTHROPIC_API_KEY"] = self.api_key
        return env

    async def run(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict,
        cwd: str,
        tools: list[str] | None = None,
        allowed_tools: list[str] | None = None,
        add_dirs: list[str] | None = None,
        timeout_s: float | None = None,
        resume: str | None = None,
    ) -> AsyncIterator[ClaudeEvent]:
        """Yield progress events, then exactly one terminal result or error.

        `tools` makes a tool *available*; `allowed_tools` pre-approves it.
        Under `--permission-mode dontAsk` an available-but-unapproved tool is
        DENIED at call time, so anything in `tools` that must actually run has
        to appear in `allowed_tools` too — otherwise the model silently works
        without it.
        """
        args: list[str] = [
            "-p", user_prompt,
            "--append-system-prompt", system_prompt,
            "--model", model,
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--verbose",
            "--permission-mode", "dontAsk",
            "--json-schema", json.dumps(json_schema),
        ]
        # `--tools` with no values = no tools at all (the default, and the safe
        # choice for any prompt carrying untrusted text).
        args += ["--tools", *(tools or [""])]
        if allowed_tools:
            args += ["--allowed-tools", *allowed_tools]
        for d in add_dirs or []:
            args += ["--add-dir", str(d)]
        if resume:
            args += ["--resume", resume]

        try:
            child = await self.spawn(
                "claude", *args,
                cwd=cwd,
                env=self._env(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            yield ClaudeError("The claude CLI is not installed or not on PATH.")
            return
        except OSError as e:  # pragma: no cover - defensive
            yield ClaudeError(f"Failed to start claude: {e}")
            return

        chars = 0
        settled: ClaudeResult | ClaudeError | None = None
        try:
            async with asyncio.timeout(timeout_s) if timeout_s else _nullctx():
                while True:
                    line = await child.stdout.readline()
                    if not line:
                        break
                    try:
                        msg = json.loads(line)
                    except (ValueError, TypeError):
                        continue  # human-readable noise on stdout; ignore

                    if (
                        msg.get("type") == "stream_event"
                        and msg.get("event", {}).get("type") == "content_block_delta"
                        and msg["event"].get("delta", {}).get("type") == "text_delta"
                    ):
                        chars += len(msg["event"]["delta"]["text"])
                        yield ClaudeProgress(chars_streamed=chars)
                    elif msg.get("type") == "result" and settled is None:
                        settled = _terminal_event(msg)
        except TimeoutError:
            child.kill()
            yield ClaudeError(f"claude timed out after {timeout_s}s")
            return
        finally:
            if settled is None:
                # Nothing usable came back; make sure we don't leak the process.
                child.kill()

        if settled is not None:
            yield settled
            return

        code = await child.wait()
        stderr = (await child.stderr.read()).decode(errors="replace").strip()
        yield ClaudeError(
            "Claude exited without a result."
            if code == 0
            else f"claude exited with code {code}: {stderr}"
        )

    async def generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict,
        cwd: str,
        tools: list[str] | None = None,
        allowed_tools: list[str] | None = None,
        add_dirs: list[str] | None = None,
        timeout_s: float | None = None,
        on_progress: Callable[[int], None] | None = None,
        attempts: int = 2,
    ) -> ClaudeResult:
        """Await a single structured result, raising RuntimeError on failure.

        A run that ends without structured output is a transient model slip
        (it wrote prose, or stopped on a stop sequence) rather than a broken
        call, so it is retried once. Non-retryable failures — no CLI, a bad
        exit code, a timeout — raise on the first attempt.
        """
        last = "claude produced no result"
        for attempt in range(1, max(1, attempts) + 1):
            settled: ClaudeError | None = None
            async for ev in self.run(
                model=model, system_prompt=system_prompt, user_prompt=user_prompt,
                json_schema=json_schema, cwd=cwd, tools=tools,
                allowed_tools=allowed_tools, add_dirs=add_dirs, timeout_s=timeout_s,
            ):
                if isinstance(ev, ClaudeProgress):
                    if on_progress:
                        on_progress(ev.chars_streamed)
                elif isinstance(ev, ClaudeResult):
                    _log.info("claude ok  cost=%s  session=%s", ev.cost_usd, ev.session_id)
                    return ev
                else:
                    settled = ev

            if settled is None:
                raise RuntimeError(last)
            last = settled.message
            if not settled.retryable or attempt >= max(1, attempts):
                raise RuntimeError(last)
            _log.warning("claude retryable failure (attempt %d): %s", attempt, last)
        raise RuntimeError(last)

    async def probe(
        self, *, model: str, cwd: str, timeout_s: float = 15.0
    ) -> tuple[bool, str]:
        """Cheapest possible real call, to verify the connection actually works."""
        args = [
            "-p", "Reply with the single word: ok",
            "--model", model,
            "--output-format", "json",
            "--permission-mode", "dontAsk",
            "--tools", "",
        ]
        try:
            child = await self.spawn(
                "claude", *args, cwd=cwd, env=self._env(),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return False, "The claude CLI is not installed or not on PATH."
        except OSError as e:  # pragma: no cover - defensive
            return False, f"Failed to start claude: {e}"

        try:
            code = await asyncio.wait_for(child.wait(), timeout=timeout_s)
        except TimeoutError:
            child.kill()
            return False, "Timed out waiting for Claude to respond."

        if code == 0:
            return True, ""
        stderr = (await child.stderr.read()).decode(errors="replace").strip()
        return False, stderr or f"claude exited with code {code}"

    def start_login(self, *, cwd: str) -> None:
        """Fire-and-forget `claude auth login`.

        The CLI opens the user's real browser to Anthropic's sign-in page and
        stores the session wherever it normally keeps it — this app never sees
        or stores a token for this path. Detached so it survives a dev-server
        reload while the user is still signing in.
        """
        import subprocess  # local: only this path shells out synchronously

        subprocess.Popen(
            ["claude", "auth", "login", "--claudeai"],
            cwd=cwd,
            env=self._env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    async def auth_status(self, *, cwd: str) -> dict | None:
        """Read the CLI's stored login. None on any failure — never a hard 'no'."""
        try:
            child = await self.spawn(
                "claude", "auth", "status", "--json",
                cwd=cwd, env=self._env(),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            raw = await asyncio.wait_for(child.stdout.read(), timeout=5)
            parsed = json.loads(raw)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        return {
            "logged_in": bool(parsed.get("loggedIn")),
            "email": parsed.get("email"),
            "subscription_type": parsed.get("subscriptionType"),
        }


def _salvage_structured(text: Any) -> Any | None:
    """Last-ditch parse of a JSON object the model wrote as plain text.

    The CLI normally delivers the schema through a tool call, but the model
    sometimes ends a turn on a stop sequence having written the JSON straight
    into its answer instead. That answer is still schema-shaped, so parse it
    rather than throw away a paid-for turn. The caller validates it against the
    real model, so a wrong shape still fails loudly.
    """
    if not isinstance(text, str):
        return None
    body = text.strip()
    if body.startswith("```"):
        body = re.sub(r"^```[a-zA-Z]*\n?", "", body)
        body = re.sub(r"\n?```$", "", body).strip()
    start, end = body.find("{"), body.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(body[start : end + 1])
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _terminal_event(msg: dict) -> ClaudeResult | ClaudeError:
    """Map a CLI `result` message onto our terminal event.

    Keyed on `structured_output` being present rather than on `stop_reason`:
    a successful schema-validated run reports stop_reason "tool_use", because
    the schema is delivered through a tool call.
    """
    out = msg.get("structured_output")
    if out is None:
        out = _salvage_structured(msg.get("result"))
    if out is None:
        return ClaudeError(
            f"Claude stopped with reason {msg.get('stop_reason', 'unknown')!r} "
            "and no structured output.",
            retryable=True,
        )
    cost = msg.get("total_cost_usd")
    sid = msg.get("session_id")
    return ClaudeResult(
        data=out,
        cost_usd=cost if isinstance(cost, (int, float)) else None,
        session_id=sid if isinstance(sid, str) else None,
    )


class _nullctx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False
