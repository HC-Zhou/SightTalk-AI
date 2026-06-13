from fastapi import APIRouter, HTTPException, Response

from sighttalk_api.storage.audio_store import InMemoryAudioStore


def create_audio_router(audio_store: InMemoryAudioStore) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["audio"])

    @router.get("/audio/{filename}")
    def get_audio(filename: str) -> Response:
        audio = audio_store.get(filename)
        if audio is None:
            raise HTTPException(status_code=404, detail="Audio file not found")
        return Response(content=audio, media_type="audio/wav")

    return router

