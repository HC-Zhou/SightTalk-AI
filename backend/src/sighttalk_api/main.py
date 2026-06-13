from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sighttalk_api.ai.orchestrator import DialogueOrchestrator
from sighttalk_api.ai.provider_adapters import build_adapters
from sighttalk_api.api.v1.audio import create_audio_router
from sighttalk_api.api.v1.health import health
from sighttalk_api.api.v1.health import router as health_router
from sighttalk_api.api.v1.websocket import create_websocket_router
from sighttalk_api.core.config import Settings
from sighttalk_api.core.session import SessionStore
from sighttalk_api.storage.audio_store import InMemoryAudioStore

settings = Settings()
asr_adapter, multimodal_adapter, tts_adapter = build_adapters(settings)
session_store = SessionStore()
audio_store = InMemoryAudioStore()
orchestrator = DialogueOrchestrator(
    asr=asr_adapter,
    multimodal=multimodal_adapter,
    tts=tts_adapter,
    audio_store=audio_store,
)

app = FastAPI(title="SightTalk AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(create_audio_router(audio_store))
app.include_router(create_websocket_router(session_store, orchestrator))

# Keep a short health endpoint for local smoke checks and the original plan.
app.get("/health", tags=["health"])(health)


def run() -> None:
    import uvicorn

    uvicorn.run("sighttalk_api.main:app", host="127.0.0.1", port=8000, reload=True)
