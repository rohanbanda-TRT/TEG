from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

from config.settings import get_settings

_HEADER_RE = re.compile(r"^>\s*\*\*(?P<key>[^:*]+):\*\*\s*(?P<val>.+?)\s*$", re.M)


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(
        r"\b(pvt\.?|private|ltd\.?|limited|llp|inc\.?|technologies|technolabs|solutions|software|it)\b",
        " ",
        s,
    )
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())


def _token_set_ratio(a: str, b: str) -> float:
    ta, tb = set(_norm(a).split()), set(_norm(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class CompanyRecord:
    name: str
    slug: str
    category: str | None
    website: str | None
    teg_participation: str | None
    confidence: str | None
    overview: str
    raw: str


@dataclass
class PersonRecord:
    name: str
    slug: str
    role: str | None
    kind: Literal["organizer", "speaker", "founder"]
    company: str | None
    overview: str
    raw: str


@dataclass
class PricingInfo:
    stalls: list[dict] = field(default_factory=list)
    title_sponsor_inr: int = 0
    payment_plan: str = ""
    refund_policy: str = ""
    raw: str = ""


@dataclass
class PersonaPains:
    persona_key: str
    pains: list[tuple[str, str]]


@dataclass
class GoalsAndPains:
    problem: str
    goals: str
    mechanism: str
    evidence: str
    what_teg_is_not: str
    pains_by_persona: dict[str, "PersonaPains"]


_PERSONA_HEADING_MAP = {
    "IT/Tech Service": "it_tech_service",
    "AI/Deep-Tech Startup": "ai_startup",
    "Non-Tech Sponsor": "non_tech_sponsor",
    "Visitor": "visitor",
}


def _parse_pain_table(block: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 2:
            continue
        if cells[0].lower() == "pain" or cells[1].lower().startswith("how teg"):
            continue
        if cells[0] and cells[1]:
            rows.append((cells[0], cells[1]))
    return rows


def _title_of(md: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+?)\s*$", md, re.M)
    if not m:
        return fallback
    return m.group(1).strip()


def _person_name(md: str, fallback: str) -> str:
    """First heading, trimmed to the bare name (drops a ' — Role, Company' suffix)."""
    title = _title_of(md, fallback)
    title = re.split(r"\s+[—–-]\s+", title, maxsplit=1)[0]
    title = title.split(",", 1)[0]
    return title.strip()


def _section(md: str, heading: str) -> str:
    if heading not in md:
        return ""
    seg = md.split(heading, 1)[1]
    return seg.split("\n## ", 1)[0].split("\n#", 1)[0].strip()


def _headers(md: str) -> dict[str, str]:
    return {
        m.group("key").strip().lower(): m.group("val").strip()
        for m in _HEADER_RE.finditer(md)
    }


class KnowledgeBase:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or get_settings().kb_path).resolve()
        self._companies: list[CompanyRecord] = []
        self._people: list[PersonRecord] = []
        self._load_companies()
        self._load_people()

    # ---- loading ----
    def _load_companies(self) -> None:
        cdir = self.root / "exhibitors" / "companies"
        for f in sorted(cdir.glob("*.md")):
            if f.stem == "companies_index":
                continue
            md = f.read_text(encoding="utf-8")
            h = _headers(md)
            self._companies.append(
                CompanyRecord(
                    name=_title_of(md, f.stem),
                    slug=f.stem,
                    category=h.get("category"),
                    website=h.get("website"),
                    teg_participation=h.get("teg participation"),
                    confidence=h.get("confidence"),
                    overview=_section(md, "## Overview"),
                    raw=md,
                )
            )

    def _load_people(self) -> None:
        odir = self.root / "organizers_team"
        for f in sorted(odir.glob("*.md")):
            if f.stem in {"organizers_and_team", "co_organizers"}:
                continue
            md = f.read_text(encoding="utf-8")
            self._people.append(
                PersonRecord(
                    name=_person_name(md, f.stem),
                    slug=f.stem,
                    role=_headers(md).get("role"),
                    kind="organizer",
                    company=_headers(md).get("company"),
                    overview=_section(md, "## Overview") or _section(md, "## Profile"),
                    raw=md,
                )
            )
        sdir = self.root / "speakers" / "individuals"
        if sdir.is_dir():
            for f in sorted(sdir.glob("*.md")):
                md = f.read_text(encoding="utf-8")
                self._people.append(
                    PersonRecord(
                        name=_person_name(md, f.stem),
                        slug=f.stem,
                        role=_headers(md).get("affiliation"),
                        kind="speaker",
                        company=None,
                        overview=_section(md, "## Overview") or _section(md, "## Bio"),
                        raw=md,
                    )
                )
        # founder names inside company files
        for c in self._companies:
            for m in re.finditer(
                r"-\s*\*\*Founder[^:*]*:\*\*\s*([A-Z][A-Za-z.\- ]+)", c.raw
            ):
                fname = m.group(1).strip().rstrip(".")
                if len(fname.split()) >= 2:
                    self._people.append(
                        PersonRecord(
                            name=fname,
                            slug=f"{c.slug}:{_norm(fname).replace(' ', '_')}",
                            role="Founder",
                            kind="founder",
                            company=c.name,
                            overview=c.overview,
                            raw=c.raw,
                        )
                    )

    # ---- queries ----
    def find_company(self, name: str) -> tuple[CompanyRecord | None, float]:
        n = _norm(name)
        slug_guess = n.replace(" ", "_")
        best: CompanyRecord | None = None
        best_score = 0.0
        for c in self._companies:
            if _norm(c.name) == n or c.slug == slug_guess:
                return c, 1.0
            score = _token_set_ratio(name, c.name)
            if score > best_score:
                best, best_score = c, score
        return (best, best_score) if best_score >= 0.5 else (None, best_score)

    def find_person(self, name: str) -> tuple[PersonRecord | None, float]:
        n = _norm(name)
        best: PersonRecord | None = None
        best_score = 0.0
        for p in self._people:
            if _norm(p.name) == n:
                return p, 1.0
            score = _token_set_ratio(name, p.name)
            if score > best_score:
                best, best_score = p, score
        return (best, best_score) if best_score >= 0.6 else (None, best_score)

    def peers_in_sector(self, sector: str, limit: int = 5) -> list[str]:
        f = self.root / "sector_wise_participation.md"
        md = f.read_text(encoding="utf-8")
        want = sector.strip().lower()
        blocks = re.split(r"\n### ", md)

        def _names_from(body: str) -> list[str]:
            line = ""
            for cand in body.splitlines():
                if cand.strip():
                    line = cand.strip()
                    break
            if line.startswith("|") or line.startswith("#"):
                return []
            names = [x.strip() for x in re.split(r"·|\|", line) if x.strip()]
            names = [re.sub(r"\s*\(.*?\)", "", x).strip().strip("*") for x in names]
            names = [x for x in names if x and not x.startswith("_")]
            return names

        # pass 1: exact heading match
        for block in blocks:
            head, _, body = block.partition("\n")
            if head.strip().lower() == want:
                names = _names_from(body)
                if names:
                    return names[:limit]
        # pass 2: heading contains the sector name
        for block in blocks:
            head, _, body = block.partition("\n")
            if want in head.strip().lower():
                names = _names_from(body)
                if names:
                    return names[:limit]
        return []

    def pricing(self) -> PricingInfo:
        f = self.root / "pricing" / "pricing_and_packages.md"
        md = f.read_text(encoding="utf-8")
        stalls: list[dict] = []
        # Parse the stall-package table (## 1. Stall Packages) row by row.
        # Each data row: | <size> | <area> | <exh passes> | <pre/post> | <visitor> | <price + GST> |
        stall_section = md.split("## 1. Stall Packages", 1)[-1].split("\n## ", 1)[0]
        int_re = re.compile(r"\d+")
        for line in stall_section.splitlines():
            if not line.strip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 6:
                continue
            price_m = re.search(r"₹\s*([\d,]+)", cells[-1])
            if not price_m:
                continue
            size = cells[0].strip().strip("*").strip()
            if not re.search(r"\d\s*m|sqm|zone", size, re.I) and "m ×" not in size and "m x" not in size.lower():
                continue
            exh_m = int_re.search(cells[2])
            vis_m = int_re.search(cells[4])
            stalls.append(
                {
                    "size": size,
                    "area": cells[1].strip().strip("*"),
                    "price_inr": int(price_m.group(1).replace(",", "")),
                    "exhibitor_passes": int(exh_m.group()) if exh_m else None,
                    "visitor_passes": int(vis_m.group()) if vis_m else None,
                }
            )
        ts = re.search(r"Title Sponsor.*?₹\s*([\d,]+)", md, re.S)
        title_inr = int(ts.group(1).replace(",", "")) if ts else 0
        return PricingInfo(
            stalls=stalls,
            title_sponsor_inr=title_inr,
            payment_plan=_section(md, "## 7. Flexible Payment Plan"),
            refund_policy=_section(md, "## 8. Refund"),
            raw=md,
        )

    def cleared_testimonials(self) -> list[dict]:
        f = self.root / "testimonials" / "exhibitor_testimonials.md"
        md = f.read_text(encoding="utf-8")
        block = md.split("## ✅ Attributed Testimonials", 1)[-1].split("\n## ", 1)[0]
        out: list[dict] = []
        for part in re.split(r"\n### ", block)[1:]:
            name = part.splitlines()[0].strip()
            role_m = re.search(r"\*\*Role:\*\*\s*(.+)", part)
            quote_m = re.search(r">\s*[\"“](.+?)[\"”]", part, re.S)
            if quote_m:
                out.append(
                    {
                        "name": name,
                        "role": role_m.group(1).strip() if role_m else "",
                        "quote": " ".join(quote_m.group(1).split()),
                    }
                )
        return out

    def goals_and_pains(self) -> GoalsAndPains:
        md = (self.root / "event_goals_and_problem.md").read_text(encoding="utf-8")

        def sect(n: int) -> str:
            marker = f"## {n}. "
            if marker not in md:
                return ""
            # everything after the "## N. <title>" line, up to the next "## " heading
            after_marker = md.split(marker, 1)[1]
            body = after_marker.split("\n", 1)[1] if "\n" in after_marker else ""
            return body.split("\n## ", 1)[0].strip()

        pains_section = sect(5)
        pains_by_persona: dict[str, PersonaPains] = {}
        for heading, key in _PERSONA_HEADING_MAP.items():
            token = f"### {heading}"
            if token not in pains_section:
                continue
            block = pains_section.split(token, 1)[1].split("\n### ", 1)[0]
            pains_by_persona[key] = PersonaPains(persona_key=key, pains=_parse_pain_table(block))

        return GoalsAndPains(
            problem=sect(1), goals=sect(2), mechanism=sect(3), evidence=sect(4),
            what_teg_is_not=sect(6), pains_by_persona=pains_by_persona,
        )


@lru_cache
def get_kb() -> KnowledgeBase:
    return KnowledgeBase()
