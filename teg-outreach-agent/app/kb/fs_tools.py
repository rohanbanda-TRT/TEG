"""Read-only, KB-root-locked filesystem tools for the agentic KB explorer.

Every path argument is resolved and checked against the KB root; an escape
returns an error *string* (the model sees it and adapts) — it never raises out
of the explorer loop. No regex parsing of document structure here — ``grep`` is
regex *searching* over file contents, like ripgrep.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from config.settings import get_settings

ToolSpec = dict  # {"name", "description", "parameters": <json schema>}

_LIST_MAX = 200


@lru_cache
def kb_root() -> Path:
    return Path(get_settings().kb_path).resolve()


def _safe(path: str) -> Path | None:
    """Resolve ``path`` under the KB root, or return None if it escapes."""
    root = kb_root()
    target = (root / path).resolve()
    try:
        if os.path.commonpath([str(root), str(target)]) != str(root):
            return None
    except ValueError:  # different drives / not comparable
        return None
    return target


def list_dir(path: str = ".") -> str:
    target = _safe(path)
    if target is None:
        return f"error: path {path!r} is outside the knowledge base"
    if not target.is_dir():
        return f"error: {path!r} is not a directory"
    dirs, files = [], []
    for e in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        if e.is_dir():
            dirs.append(f"{e.name}/")
        else:
            files.append(f"{e.name}  ({e.stat().st_size} B)")
    entries = dirs + files
    out = entries[:_LIST_MAX]
    if len(entries) > _LIST_MAX:
        out.append(f"… ({len(entries) - _LIST_MAX} more entries)")
    rel = target.relative_to(kb_root())
    return f"{rel}/\n" + "\n".join(out)


def read_file(path: str, offset: int = 0) -> str:
    target = _safe(path)
    if target is None:
        return f"error: path {path!r} is outside the knowledge base"
    if not target.is_file():
        return f"error: {path!r} is not a file"
    cap = get_settings().kb_read_file_max_bytes
    data = target.read_bytes()
    chunk = data[offset : offset + cap]
    text = chunk.decode("utf-8", errors="replace")
    if offset + cap < len(data):
        nxt = offset + cap
        text += f"\n… (truncated at {nxt} B; call read_file with offset={nxt} for more)"
    return text


def grep(pattern: str, path: str = ".") -> str:
    target = _safe(path)
    if target is None:
        return f"error: path {path!r} is outside the knowledge base"
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"error: invalid regex {pattern!r}: {e}"
    files = [target] if target.is_file() else sorted(target.rglob("*.md"))
    cap = get_settings().kb_grep_max_matches
    hits: list[str] = []
    root = kb_root()
    for f in files:
        try:
            for i, line in enumerate(f.read_text("utf-8", errors="replace").splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{f.relative_to(root)}:{i}: {line.strip()}")
                    if len(hits) >= cap:
                        return (
                            "\n".join(hits)
                            + "\n… (more matches not shown; narrow the pattern or pass a path)"
                        )
        except OSError:
            continue
    return "\n".join(hits) if hits else f"(no matches for {pattern!r})"


_TOOL_FNS = {"list_dir": list_dir, "read_file": read_file, "grep": grep}


def dispatch(name: str, args: dict) -> str:
    fn = _TOOL_FNS.get(name)
    if fn is None:
        return f"error: unknown tool {name!r}"
    try:
        return fn(**args)
    except TypeError as e:
        return f"error: bad arguments for {name}: {e}"
    except Exception as e:  # never break the loop  # noqa: BLE001
        return f"error: {name} failed: {e}"


TOOL_SPECS: list[ToolSpec] = [
    {
        "name": "list_dir",
        "description": (
            "List entries in a knowledge-base directory. Directories first (name/), "
            "then files with byte sizes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "directory path relative to the KB root; default '.'",
                }
            },
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read a knowledge-base file as UTF-8 text from a byte offset. Returns at most "
            "6144 bytes; a trailer tells you the next offset."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "file path relative to the KB root"},
                "offset": {"type": "integer", "description": "byte offset to start at; default 0"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "grep",
        "description": (
            "Case-insensitive regex search over *.md files. Returns 'relpath:line: text' "
            "for up to 30 matches."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "a Python regular expression"},
                "path": {
                    "type": "string",
                    "description": "file or directory to search; default '.' (whole KB)",
                },
            },
            "required": ["pattern"],
        },
    },
]
