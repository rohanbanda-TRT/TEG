"""Regenerate app/kb/pricing.json — the exact-match tier-ladder snapshot
ProposalAgent reads instead of the old hand-typed `_PRICING_BY_PERSONA` dict.

Sibling to build_kb_facts.py, same shape and same discipline: this is the
ONLY place markdown-table parsing of pricing_and_packages.md happens. It is a
build tool, not imported by the running app; its output (pricing.json) is a
committed, git-reviewed artifact, read at runtime by app/kb/pricing.py.

Kept as its OWN script rather than folded into build_kb_facts.py: facts.json
covers guardrail exact-match data (testimonials, exhibitor names, official
industries) sourced from three different topic files; pricing.json covers one
topic file's tables and feeds a structurally different consumer (per-persona
tier ladders, not flat lookup sets). Two scripts, two independently reviewable
diffs when either source file changes, rather than one script whose diff
mixes two unrelated concerns whenever only one KB file moves. `--check` is
duplicated (not shared) for the same reason build_kb_facts.py doesn't import
this module: each script is a complete, standalone build step.

    python scripts/build_kb_pricing.py           # write app/kb/pricing.json
    python scripts/build_kb_pricing.py --check   # exit 1 if the committed file is stale
"""
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import get_settings

_OUT = Path(__file__).resolve().parents[1] / "app" / "kb" / "pricing.json"

_MONTHS = {
    "January": "Jan", "February": "Feb", "March": "Mar", "April": "Apr",
    "May": "May", "June": "Jun", "July": "Jul", "August": "Aug",
    "September": "Sep", "October": "Oct", "November": "Nov", "December": "Dec",
}

# Raw KB table label -> canonical ProposalPackage.name. Only the stall/sponsor
# tiers this spec's tier ladders actually use (§3.2.1 of the design spec).
_STALL_LABELS = {
    "3m × 3m": "3m x 3m stall",
    "3m × 6m": "3m x 6m stall",
    "6m × 6m": "6m x 6m stall",
    "3m × 9m (corner stall)": "3m x 9m corner stall",
    "Catalyst Zone (startup)": "Catalyst Zone (2m x 2m startup stall)",
}
_SPONSOR_LABELS = {
    "Official Banking Partner": "Official Banking Partner",
    "Official Real Estate Partner": "Official Real Estate Partner",
    "Official AI Partner": "Official AI Partner",
}

_COMMON_STALL_INCLUDES = [
    "modular stall + fascia", "pre-scheduled 1:1 B2B meetings",
    "TEG Community Network Portal access",
]


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _price(cell: str) -> str:
    m = re.search(r"₹[\d,]+", cell)
    if not m:
        raise ValueError(f"no rupee figure found in cell {cell!r}")
    return m.group(0)


def _stall_tiers(md: str) -> dict[str, dict]:
    """Section 1 — 'Stall Packages (Exhibitor)'."""
    section = md.split("## 1. Stall Packages", 1)[1].split("\n## 2.", 1)[0]
    out: dict[str, dict] = {}
    for line in section.splitlines():
        if not line.strip().startswith("|") or "₹" not in line:
            continue
        cells = _split_row(line)
        if len(cells) < 6:
            continue
        label = cells[0].strip("*").strip()
        canon = _STALL_LABELS.get(label)
        if canon is None:
            continue
        out[canon] = {
            "price": _price(cells[5]),
            "exhibitor_passes": cells[2],
            "prepost_passes": cells[3],
            "visitor_passes": cells[4],
        }
    return out


def _sponsor_tiers(md: str) -> dict[str, dict]:
    """Section 3 — 'Authority & Positioning Sponsorship Add-Ons'."""
    section = md.split("## 3. Authority", 1)[1].split("\n## 4.", 1)[0]
    out: dict[str, dict] = {}
    for line in section.splitlines():
        if not line.strip().startswith("|") or "₹" not in line:
            continue
        cells = _split_row(line)
        if len(cells) < 5:
            continue
        label = cells[0].strip("*").strip()
        canon = _SPONSOR_LABELS.get(label)
        if canon is None:
            continue
        out[canon] = {"price": _price(cells[1]), "visitor_passes": cells[3], "vip_passes": cells[4]}
    return out


def _title_sponsor_price(md: str) -> str:
    """Section 2 — 'Title Sponsor' (a key/value table, not a tier list)."""
    section = md.split("## 2. Title Sponsor", 1)[1].split("\n## 3.", 1)[0]
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = _split_row(line)
        if len(cells) >= 2 and cells[0].strip("*").strip() == "Price":
            return _price(cells[1])
    raise ValueError("Title Sponsor price row not found")


def _payment_plan(md: str) -> str:
    """Section 7 — 'Flexible Payment Plan', rendered the same way the old
    hand-typed string was: '4 instalments of 25% (9 Apr / 30 Jun / ...)'."""
    section = md.split("## 7. Flexible Payment Plan", 1)[1].split("\n## 8.", 1)[0]
    dates: list[str] = []
    year = ""
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = _split_row(line)
        if len(cells) < 3 or not cells[0].isdigit():
            continue
        m = re.match(r"(\d+)\s+(\w+)\s+(\d{4})", cells[1])
        if not m:
            continue
        day, month, year = m.groups()
        dates.append(f"{day} {_MONTHS.get(month, month[:3])}")
    if not dates:
        raise ValueError("payment plan dates not found")
    return f"{len(dates)} instalments of 25% ({' / '.join(dates)} {year})"


def _stall_pkg(canon_name: str, tier: dict, payment_plan: str) -> dict:
    includes = [f"{tier['exhibitor_passes']} exhibitor passes"]
    if tier["prepost_passes"] not in ("—", "-", ""):
        includes.append(f"{tier['prepost_passes']} pre/post-party passes")
    if tier["visitor_passes"] not in ("—", "-", ""):
        includes.append(f"{tier['visitor_passes']} visitor passes")
    includes += _COMMON_STALL_INCLUDES
    return {
        "name": canon_name,
        "price_line": f"{tier['price']} + GST (indicative, confirmed at booking)",
        "includes": includes,
        "payment_plan": payment_plan,
    }


def build() -> dict:
    root = Path(get_settings().kb_path).resolve()
    md = (root / "pricing" / "pricing_and_packages.md").read_text("utf-8")
    stalls = _stall_tiers(md)
    sponsors = _sponsor_tiers(md)
    title_price = _title_sponsor_price(md)
    payment_plan = _payment_plan(md)

    banking = sponsors["Official Banking Partner"]
    real_estate = sponsors["Official Real Estate Partner"]
    ai_partner = sponsors["Official AI Partner"]
    sponsor_base_price_line = (
        f"{banking['price']}–{real_estate['price'].lstrip('₹')} + GST "
        "(indicative, confirmed at booking)"
    )

    tier_ladders = {
        "it_tech_service": [
            _stall_pkg("3m x 3m stall", stalls["3m x 3m stall"], payment_plan),
            _stall_pkg("3m x 9m corner stall", stalls["3m x 9m corner stall"], payment_plan),
            _stall_pkg("6m x 6m stall", stalls["6m x 6m stall"], payment_plan),
        ],
        "ai_startup": [
            _stall_pkg(
                "Catalyst Zone (2m x 2m startup stall)",
                stalls["Catalyst Zone (2m x 2m startup stall)"], payment_plan,
            ),
            _stall_pkg("3m x 3m stall", stalls["3m x 3m stall"], payment_plan),
            _stall_pkg("3m x 6m stall", stalls["3m x 6m stall"], payment_plan),
        ],
        "non_tech_sponsor": [
            {
                "name": "Official Category Partner (Banking / Real Estate)",
                "price_line": sponsor_base_price_line,
                "includes": [
                    "category exclusivity", "3m x 3m stall",
                    f"{banking['visitor_passes']} visitor passes",
                    f"{banking['vip_passes']} VIP passes",
                    "website logo", "stage mention", "on-stage trophy",
                ],
                "payment_plan": payment_plan,
            },
            {
                "name": "Official AI Partner",
                "price_line": f"{ai_partner['price']} + GST (indicative, confirmed at booking)",
                "includes": [
                    "category exclusivity", "3m x 3m stall",
                    f"{ai_partner['visitor_passes']} visitor passes",
                    f"{ai_partner['vip_passes']} VIP passes",
                    "website logo", "stage mention", "on-stage trophy", "1 digital PR",
                ],
                "payment_plan": payment_plan,
            },
            {
                "name": "Title Sponsor",
                "price_line": f"{title_price} + GST (indicative, confirmed at booking)",
                "includes": [
                    "6m x 6m stall (all benefits included)", "largest logo on all branding",
                    "entry-gate branding", "media & PR coverage", "5 VIP passes",
                    "all attendee & exhibitor data shared", "10-minute main-stage speaker slot",
                ],
                "payment_plan": payment_plan,
            },
        ],
        "visitor": [
            {
                "name": "Visitor pass",
                "price_line": "ticketed entry (no free entry); current pricing on the official ticketing portal",
                "includes": [
                    "access to 250+ exhibitors across 18 industries", "keynote sessions",
                    "the TEG networking app",
                ],
                "payment_plan": "—",
            },
        ],
    }
    return {
        "generated_from_kb_at": datetime.now(UTC).date().isoformat(),
        "tier_ladders": tier_ladders,
    }


def main() -> int:
    data = build()
    if "--check" in sys.argv:
        if not _OUT.exists():
            print("pricing.json missing; run: python scripts/build_kb_pricing.py", file=sys.stderr)
            return 1
        current = json.loads(_OUT.read_text("utf-8"))
        a = {k: v for k, v in data.items() if k != "generated_from_kb_at"}
        b = {k: v for k, v in current.items() if k != "generated_from_kb_at"}
        if a != b:
            print(
                "pricing.json is stale — run: python scripts/build_kb_pricing.py",
                file=sys.stderr,
            )
            return 1
        return 0
    _OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    n = sum(len(v) for v in data["tier_ladders"].values())
    print(f"wrote {_OUT}  ({n} tiers across {len(data['tier_ladders'])} personas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
