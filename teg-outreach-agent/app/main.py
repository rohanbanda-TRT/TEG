from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import inquiries, internal, proposals


def create_app() -> FastAPI:
    app = FastAPI(title="TEG Outreach Agent")

    # Permissive CORS for local development (form + widget on any origin, incl. file://).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(inquiries.router)
    app.include_router(internal.router)
    app.include_router(proposals.router)

    from app.api import chat  # imported here to avoid circulars

    app.include_router(chat.router)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True}

    # Serve the built widget + demo page at /demo (dev convenience).
    widget_dir = Path(__file__).resolve().parent.parent / "widget"
    if widget_dir.is_dir():
        app.mount("/demo", StaticFiles(directory=str(widget_dir), html=True), name="demo")

    return app


app = create_app()
