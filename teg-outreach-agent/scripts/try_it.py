"""Interactive CLI to try the TEG outreach agent end to end (real Gemini + Tavily).

Usage (from teg-outreach-agent/):
    bash scripts/pg.sh start                    # start the local Postgres once
    .venv/bin/alembic upgrade head              # first run only, creates tables
    DATABASE_URL=postgresql+psycopg://teg@127.0.0.1:5433/teg_outreach \\
        .venv/bin/python scripts/try_it.py

You'll be asked for a name, a company, and an optional message. The pipeline
runs, the agent opens the chat, and you type replies. Commands during chat:
    /proposal  force-generate a personalized proposal PDF now
    /end       end the session (writes outcome + handoff packet)
    /quit      exit without ending

(The agent also generates a proposal on its own if you ask for one in chat —
 e.g. "can you send me a proposal / something in writing / a PDF?")
"""
import asyncio
import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://teg@127.0.0.1:5433/teg_outreach")

from app.domain.schemas import IntakePayload
from app.orchestrator import Orchestrator
from app.store.db import SessionLocal
from app.store.repositories import SessionRepo

C_AGENT = "\033[36m"
C_YOU = "\033[33m"
C_SYS = "\033[90m"
C_OFF = "\033[0m"


async def main() -> None:
    print(f"{C_SYS}--- TEG Inquiry Outreach — live test ---{C_OFF}")
    name = input("Your name: ").strip() or "Priya Sharma"
    company = input("Company name: ").strip() or "Acme Automation"
    message = input("Message (optional, Enter to skip): ").strip() or None

    orch = Orchestrator()  # real Gemini + Tavily from .env

    print(f"\n{C_SYS}Researching {name} / {company} …{C_OFF}")
    res = await orch.run_pipeline(IntakePayload(
        person_name=name, company_name=company, message=message,
    ))

    async with SessionLocal() as s:
        cs = await SessionRepo(s).get(res.session_id)
        dossier_note = f"persona={res.persona}  cta={cs.target_cta}  session={res.session_id}"
    print(f"{C_SYS}{dossier_note}{C_OFF}\n")
    print(f"{C_AGENT}TEG ▸ {res.opening_message}{C_OFF}\n")

    while True:
        try:
            msg = input(f"{C_YOU}you ▸ {C_OFF}").strip()
        except (EOFError, KeyboardInterrupt):
            msg = "/quit"
        if msg == "/quit":
            print(f"{C_SYS}(left without ending session){C_OFF}")
            return
        if msg == "/end":
            packet = await orch.end_session(res.session_id, reason="left")
            async with SessionLocal() as s:
                cs = await SessionRepo(s).get(res.session_id)
            print(f"\n{C_SYS}outcome={cs.outcome_status}  cta={cs.cta_status}  "
                  f"needs_review={cs.needs_review}{C_OFF}")
            if packet is None:
                print(f"{C_SYS}CTA completed cleanly — no handoff packet.{C_OFF}")
            else:
                print(f"{C_SYS}--- HANDOFF PACKET ---{C_OFF}")
                print(f"{C_SYS}summary: {packet.summary}{C_OFF}")
                print(f"{C_SYS}next:    {packet.recommended_next_step}{C_OFF}")
                print(f"{C_SYS}draft:   {packet.suggested_followup_message}{C_OFF}")
                print(f"{C_SYS}confidence: {packet.prospect_confidence}{C_OFF}")
            return
        if msg == "/proposal":
            print(f"{C_SYS}generating a proposal … (real Gemini + WeasyPrint){C_OFF}")
            card = await orch.generate_proposal(res.session_id)
            print(f"{C_SYS}--- PROPOSAL v{card.version} ---{C_OFF}")
            print(f"{C_SYS}file:  {card.filename}  ({card.bytes // 1024} KB){C_OFF}")
            async with SessionLocal() as s:
                from app.store.repositories import ProposalRepo
                pr = (await ProposalRepo(s).list_for_session(res.session_id))[-1]
            print(f"{C_SYS}pdf:   {pr.pdf_path}{C_OFF}")
            print(f"{C_SYS}png:   {pr.png_path}{C_OFF}")
            print(f"{C_SYS}flags: {pr.guardrail_flags or 'none'}{C_OFF}")
            print(f"{C_SYS}(open the PDF to see it — or via the server: GET {card.pdf_url}){C_OFF}\n")
            continue
        if not msg:
            continue

        turn = await orch.run_turn(res.session_id, msg)
        flags = f"  ⚠ {turn.guardrail_flags}" if turn.guardrail_flags else ""
        handoff = "  → handoff suggested" if turn.should_handoff else ""
        proposal = "  📄 wants proposal" if turn.wants_proposal else ""
        print(f"\n{C_AGENT}TEG ▸ {turn.reply_text}{C_OFF}")
        print(f"{C_SYS}   [persona={turn.persona} cta={turn.cta_status}{flags}{handoff}{proposal}]{C_OFF}")
        if turn.wants_proposal:
            print(f"{C_SYS}generating a proposal …{C_OFF}")
            card = await orch.generate_proposal(res.session_id)
            async with SessionLocal() as s:
                from app.store.repositories import ProposalRepo
                pr = (await ProposalRepo(s).list_for_session(res.session_id))[-1]
            print(f"{C_AGENT}TEG ▸ [proposal v{card.version}]  {card.filename}  "
                  f"({card.bytes // 1024} KB){C_OFF}")
            print(f"{C_SYS}   pdf: {pr.pdf_path}  |  flags: {pr.guardrail_flags or 'none'}{C_OFF}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
