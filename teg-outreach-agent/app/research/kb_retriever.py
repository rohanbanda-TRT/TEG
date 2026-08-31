from __future__ import annotations

from app.kb.loader import get_kb
from app.research.tools import ResearchQuery, ResearchResult, ResearchTool


class KBRetriever(ResearchTool):
    name = "kb"

    async def lookup(self, query: ResearchQuery) -> ResearchResult:
        kb = get_kb()
        if query.track == "company":
            rec, score = kb.find_company(query.subject)
            if rec is None or score < 0.5:
                return ResearchResult(available=False, tool_name=self.name)
            fields: dict[str, str] = {}
            if rec.category:
                fields["sector"] = rec.category
            if rec.website:
                fields["website"] = rec.website
            if rec.teg_participation:
                fields["teg_history"] = rec.teg_participation
            if rec.overview:
                fields["overview"] = rec.overview
            return ResearchResult(
                available=True, fields=fields,
                confidence={k: score for k in fields},
                tool_name=self.name, notes=rec.slug,
            )
        rec_p, score_p = kb.find_person(query.subject)
        if rec_p is None or score_p < 0.6:
            return ResearchResult(available=False, tool_name=self.name)
        fields = {"teg_role": rec_p.kind}
        if rec_p.role:
            fields["role"] = rec_p.role
        if rec_p.overview:
            fields["overview"] = rec_p.overview
        if rec_p.company:
            fields["company"] = rec_p.company
        return ResearchResult(
            available=True, fields=fields,
            confidence={k: score_p for k in fields},
            tool_name=self.name, notes=rec_p.slug,
        )
