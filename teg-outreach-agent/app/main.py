from __future__ import annotations

from fastapi import FastAPI

from app.api import inquiries, internal, proposals


def create_app() -> FastAPI:
    app = FastAPI(title="TEG Outreach Agent")
    app.include_router(inquiries.router)
    app.include_router(internal.router)
    app.include_router(proposals.router)

    from app.api import chat  # imported here to avoid circulars

    app.include_router(chat.router)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True}

    return app


app = create_app()
