import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sighttalk_api.api.router import api_router
from sighttalk_api.core.config import get_settings
from sighttalk_api.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()


def run() -> None:
    uvicorn.run(
        "sighttalk_api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
