from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.inquiries import get_orchestrator
from app.orchestrator import Orchestrator
from app.store.db import SessionLocal
from app.store.repositories import InquiryRepo, MessageRepo, SessionRepo
from config.settings import get_settings

router = APIRouter()


@router.websocket("/chat/{session_id}")
async def chat(
    websocket: WebSocket,
    session_id: uuid.UUID,
    orch: Orchestrator = Depends(get_orchestrator),
) -> None:
    await websocket.accept()

    async with SessionLocal() as s:
        cs = await SessionRepo(s).get(session_id)
        if cs is None:
            await websocket.close(code=4404)
            return
        inq = await InquiryRepo(s).get(cs.inquiry_id)
        company = (inq.company_name_canonical or inq.company_name_raw) if inq else "your company"
        history = await MessageRepo(s).history(session_id)

    opening = next((m["content"] for m in history if m["role"] == "agent"), "")
    await websocket.send_json({"type": "opening", "text": opening})

    prospect_turns = 0
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "end":
                await orch.end_session(session_id, reason="left")
                await websocket.close()
                return
            if msg.get("type") != "message":
                continue
            prospect_turns += 1
            try:
                turn = await orch.run_turn(session_id, msg.get("text", ""))
            except Exception as exc:  # noqa: BLE001 — one bad turn must not kill the chat
                from app.obs import get_logger

                get_logger("api.chat").error("turn failed: %s", exc)
                await websocket.send_json({"type": "turn_failed"})
                continue
            await websocket.send_json({
                "type": "reply",
                "text": turn.reply_text,
                "cta_status": turn.cta_status,
                "should_handoff": turn.should_handoff,
            })
            if turn.should_handoff:
                await websocket.send_json({"type": "handoff"})

            if turn.wants_proposal:
                await websocket.send_json({"type": "proposal_pending", "company": company})
                try:
                    # Use a longer timeout for proposal generation since it may include
                    # a regeneration pass after guardrail violations
                    card = await asyncio.wait_for(
                        orch.generate_proposal(session_id),
                        timeout=get_settings().proposal_hard_timeout_s,
                    )
                    await websocket.send_json({"type": "attachment", **card.model_dump()})
                except asyncio.TimeoutError:
                    from app.obs import get_logger
                    get_logger("api.chat").warning("proposal generation timed out")
                    await websocket.send_json({
                        "type": "proposal_failed",
                        "reason": "timeout"
                    })
                except Exception as exc:  # noqa: BLE001 — a failed proposal must not kill the chat
                    from app.obs import get_logger
                    get_logger("api.chat").error("proposal generation failed: %s", exc)
                    await websocket.send_json({
                        "type": "proposal_failed",
                        "reason": "error"
                    })
    except WebSocketDisconnect:
        reason = "bounced" if prospect_turns == 0 else "left"
        await orch.end_session(session_id, reason=reason)
