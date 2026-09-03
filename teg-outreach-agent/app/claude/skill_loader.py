"""Load skills as prompt assets.

These skills are *not* `.claude/skills/` entries that Claude discovers and
invokes — the app reads them off disk and concatenates them into the system
prompt itself. That keeps the generation sessions tool-free while still letting
non-engineers edit the pitch, the pain library, and the gold-standard examples
as plain Markdown.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_FRONTMATTER = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n?", re.DOTALL)


@dataclass(frozen=True)
class SkillContent:
    name: str
    instructions: str
    references: dict[str, str] = field(default_factory=dict)


def load_skill(
    skills_root: str | Path, name: str, *, references: list[str] | None = None
) -> SkillContent:
    """Read `<skills_root>/<name>/SKILL.md` plus any named reference files."""
    root = Path(skills_root) / name
    skill_md = root / "SKILL.md"
    if not skill_md.is_file():
        raise FileNotFoundError(f"Skill file missing: {skill_md}")

    body = _FRONTMATTER.sub("", skill_md.read_text("utf-8"))

    refs: dict[str, str] = {}
    for ref in references or []:
        path = root / "references" / ref
        if not path.is_file():
            raise FileNotFoundError(f"Skill reference missing: {path}")
        refs[ref] = path.read_text("utf-8")

    return SkillContent(name=name, instructions=body, references=refs)
