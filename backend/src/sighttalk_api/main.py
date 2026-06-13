from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sighttalk_api.api.v1.assistant import router as assistant_router
from sighttalk_api.api.v1.health import router as health_router
from sighttalk_api.api.v1.livekit import router as livekit_router
from sighttalk_api.core.config import get_settings
from sighttalk_api.core.errors import AppError, app_error_handler


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="SightTalk API", version="0.1.0")
    app.add_exception_handler(AppError, app_error_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(assistant_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(livekit_router, prefix="/api/v1")
    return app


app = create_app()
