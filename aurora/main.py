"""Aplicação FastAPI do assistente do Residencial Aurora.

Uso: ``uv run uvicorn aurora.main:app --host 0.0.0.0 --port 8000``
"""

from __future__ import annotations

from fastapi import FastAPI

from .api.routes import router
from .storage import db


def create_app() -> FastAPI:
    app = FastAPI(title="Assistente Residencial Aurora")
    app.include_router(router)

    @app.on_event("startup")
    async def _startup() -> None:
        # Garante o esquema do banco do condomínio na subida.
        db.init_db()

    return app


app = create_app()
