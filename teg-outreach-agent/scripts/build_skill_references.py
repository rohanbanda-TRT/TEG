"""Extract skill reference files from the knowledge base.

Skills are prompt assets, and some of their reference material is owned by the
KB rather than hand-written. This mirrors `build_kb_facts.py`: run it after a KB
change, and `--check` in CI to catch a stale committed copy.

    python scripts/build_skill_references.py
    python scripts/build_skill_references.py --check
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import get_settings  # noqa: E402

_SKILLS = Path(__file__).resolve().parents[1] / "skills"

_HEADER = (
    "# {title}\n\n"
    "> Extracted verbatim from the TEG knowledge base (`{source}`{section}).\n"
    "> Regenerate with `python scripts/build_skill_references.py` — do not hand-edit.\n\n"
)


def _section(text: str, start: str, end: str) -> str:
    """Body between two `##` headings, exclusive."""
    m = re.search(rf"^{re.escape(start)}$(.*?)^{re.escape(end)}", text, re.M | re.S)
    if not m:
        raise SystemExit(f"section not found: {start!r} .. {end!r}")
    return m.group(1).strip()


def build() -> dict[Path, str]:
    kb = Path(get_settings().kb_path).resolve()
    goals = (kb / "event_goals_and_problem.md").read_text("utf-8")

    out: dict[Path, str] = {}

    out[_SKILLS / "teg-proposal" / "references" / "pain-library.md"] = (
        _HEADER.format(
            title="Persona Pain-Point Library",
            source="event_goals_and_problem.md",
            section=", section 5",
        )
        + _section(goals, "## 5. Persona Pain-Point Library", "## 6.")
        + "\n"
    )

    out[_SKILLS / "teg-proposal" / "references" / "teg-mechanism.md"] = (
        _HEADER.format(
            title="TEG Goals, Mechanism and Evidence",
            source="event_goals_and_problem.md",
            section=", sections 2-4 and 6",
        )
        + _section(goals, "## 2. TEG's Stated Goals", "## 5.")
        + "\n\n---\n\n## What TEG Is NOT\n\n"
        + _section(goals + "\n## END", "## 6. What TEG Is NOT", "## END")
        + "\n"
    )

    return out


def main() -> int:
    data = build()
    check = "--check" in sys.argv

    stale: list[Path] = []
    for path, body in data.items():
        if check:
            if not path.is_file() or path.read_text("utf-8") != body:
                stale.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")

    if check:
        if stale:
            print(
                "stale skill references — run: python scripts/build_skill_references.py\n"
                + "\n".join(f"  {p}" for p in stale),
                file=sys.stderr,
            )
            return 1
        return 0

    for path in data:
        print(f"wrote {path.relative_to(_SKILLS.parent)}  ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
