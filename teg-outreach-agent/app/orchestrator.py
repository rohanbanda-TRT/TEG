from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from app.agents.analysis import AnalysisAgent
from app.agents.persuasion import PersuasionAgent
from app.agents.research import ResearchAgent
from app.domain.schemas import IntakePayload, ResearchDossier
from app.llm.base import get_llm
from app.store.db import SessionLocal
from app.store.repositories import DossierRepo, InquiryRepo, MessageRepo, SessionRepo
from config.settings import get_settings


@dataclass
class PipelineResult:
    inquiry_id: uuid.UUID
    session_id: uuid.UUID
    opening_message: str
    persona: str


class Orchestrator:
    def __init__(
        self, *,
        analysis: AnalysisAgent | None = None,
        research: ResearchAgent | None = None,
        persuasion: PersuasionAgent | None = None,
    ) -> None:
        self.analysis = analysis or AnalysisAgent(get_llm())
        self.research = research or ResearchAgent(get_llm())
        self.persuasion = persuasion or PersuasionAgent(get_llm())

    async def run_pipeline(self, payload: IntakePayload) -> PipelineResult:
        settings = get_settings()
        intake = await self.analysis.run(payload)

        try:
            dossier = await asyncio.wait_for(
                self.research.run(intake), timeout=settings.pipeline_hard_timeout_s,
            )
        except (TimeoutError, asyncio.TimeoutError):
            dossier = ResearchDossier(ask_prospect=["company_description", "role"])

        init = await self.persuasion.init(intake, dossier)

        async with SessionLocal() as s:
            inq = await InquiryRepo(s).create(payload, intake)
            await s.flush()
            drow = await DossierRepo(s).create(inq.id, dossier)
            await s.flush()
            cs = await SessionRepo(s).create(inq.id, drow.id, init)
            await s.flush()
            mr = MessageRepo(s)
            await mr.append(cs.id, "agent", init.opening_message, turn_index=0)
            await s.commit()
            return PipelineResult(
                inquiry_id=inq.id, session_id=cs.id,
                opening_message=init.opening_message, persona=init.persona,
            )
