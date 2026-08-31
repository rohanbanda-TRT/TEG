from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.inquiries import get_orchestrator
from app.orchestrator import Orchestrator
from app.store.db import SessionLocal
from app.store.repositories import MessageRepo, SessionRepo

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
            turn = await orch.run_turn(session_id, msg.get("text", ""))
            await websocket.send_json({
                "type": "reply",
                "text": turn.reply_text,
                "cta_status": turn.cta_status,
                "should_handoff": turn.should_handoff,
            })
            if turn.should_handoff:
                await websocket.send_json({"type": "handoff"})
    except WebSocketDisconnect:
        reason = "bounced" if prospect_turns == 0 else "left"
        await orch.end_session(session_id, reason=reason)
