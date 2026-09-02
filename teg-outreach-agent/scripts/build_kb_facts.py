"""Regenerate app/kb/facts.json — the exact-match snapshot the guardrail layer reads.

This is the ONLY place regex-parsing of KB markdown is allowed: a build tool, not
imported by the app, whose output is reviewed in the git diff.

    python scripts/build_kb_facts.py           # write app/kb/facts.json
    python scripts/build_kb_facts.py --check   # exit 1 if the committed file is stale
"""
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import get_settings

_OUT = Path(__file__).resolve().parents[1] / "app" / "kb" / "facts.json"


def _cleared_testimonials(root: Path) -> list[dict]:
    md = (root / "testimonials" / "exhibitor_testimonials.md").read_text("utf-8")
    # only the "✅ Attributed Testimonials" section, up to the next "## " heading
    block = md.split("## ✅ Attributed Testimonials", 1)[-1].split("\n## ", 1)[0]
    out: list[dict] = []
    for part in re.split(r"\n### ", block)[1:]:
        name = part.splitlines()[0].strip()
        role_m = re.search(r"\*\*Role:\*\*\s*(.+)", part)
        quote_m = re.search(r">\s*[\"“](.+?)[\"”]", part, re.DOTALL)
        if quote_m:
            out.append(
                {
                    "name": name,
                    "role": role_m.group(1).strip() if role_m else "",
                    "quote": " ".join(quote_m.group(1).split()),
                }
            )
    return out


def _exhibitor_names(root: Path) -> list[str]:
    names: set[str] = set()
    for f in sorted((root / "exhibitors" / "companies").glob("*.md")):
        if f.stem == "companies_index":
            continue
        m = re.search(r"^#\s+(.+?)\s*$", f.read_text("utf-8"), re.MULTILINE)
        if m:
            names.add(m.group(1).strip())
    # The per-sector company tables are shaped:
    #   | # | Company Name | Website | Booth | Notes |
    # Other tables in the file (sector summaries) are | Sector | Companies | ...,
    # so require a numeric row index in the first cell to pick out company rows.
    swp = (root / "sector_wise_participation.md").read_text("utf-8")
    for line in swp.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not cells[0].isdigit():
            continue
        cand = re.sub(r"\s*\(.*?\)", "", cells[1]).strip().strip("*")
        if not cand or set(cand) <= set("-: "):
            continue
        if cand.startswith("["):  # placeholder rows like "[Various startups]"
            continue
        names.add(cand)
    return sorted(names)


def build() -> dict:
    root = Path(get_settings().kb_path).resolve()
    return {
        "generated_from_kb_at": datetime.now(UTC).date().isoformat(),
        "cleared_testimonials": _cleared_testimonials(root),
        "exhibitor_names": _exhibitor_names(root),
    }


def main() -> int:
    data = build()
    if "--check" in sys.argv:
        if not _OUT.exists():
            print("facts.json missing; run: python scripts/build_kb_facts.py", file=sys.stderr)
            return 1
        current = json.loads(_OUT.read_text("utf-8"))
        # the date stamp is not part of the comparison
        a = {k: v for k, v in data.items() if k != "generated_from_kb_at"}
        b = {k: v for k, v in current.items() if k != "generated_from_kb_at"}
        if a != b:
            print(
                "facts.json is stale — run: python scripts/build_kb_facts.py",
                file=sys.stderr,
            )
            return 1
        return 0
    _OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"wrote {_OUT}  ({len(data['cleared_testimonials'])} testimonials, "
        f"{len(data['exhibitor_names'])} exhibitor names)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
