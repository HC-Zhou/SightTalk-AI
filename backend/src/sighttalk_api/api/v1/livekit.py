"""LiveKit session management API routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends

from sighttalk_api.agent.livekit_runtime import get_agent_manager
from sighttalk_api.api.deps import get_current_user
from sighttalk_api.core.config import Settings, get_settings
from sighttalk_api.core.errors import AppError
from sighttalk_api.schemas.livekit import (
    CreateLiveKitSessionRequest,
    CreateLiveKitSessionResponse,
    EndLiveKitSessionRequest,
    EndLiveKitSessionResponse,
)
from sighttalk_api.services.auth import StoredUser
from sighttalk_api.services.livekit_messenger import LiveKitMessenger
from sighttalk_api.services.livekit_rooms import LiveKitRoomService
from sighttalk_api.services.livekit_tokens import LiveKitTokenService
from sighttalk_api.services.session_registry import SessionRecord, get_session_registry

router = APIRouter(prefix="/livekit", tags=["livekit"])


def _make_identity(prefix: str) -> str:
    """Create a time-sortable participant or room identity."""
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}-{timestamp}"


@router.post("/session")
async def create_session(
    request: CreateLiveKitSessionRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[StoredUser, Depends(get_current_user)],
) -> CreateLiveKitSessionResponse:
    """Create a LiveKit room, issue a participant token, and register session state."""
    try:
        settings.validate_for_session()
    except ValueError as exc:
        raise AppError("CONFIGURATION_ERROR", str(exc), status_code=500) from exc

    room_name = _make_identity("sighttalk")
    participant_identity = _make_identity("user")
    assistant_identity = f"assistant-{room_name}"
    expires_at = datetime.now(tz=UTC) + timedelta(seconds=settings.livekit_room_ttl_seconds)
    media_policy = settings.media_policy_for(request.media_mode)
    room_service = LiveKitRoomService(
        url=settings.livekit_server_url or settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    )
    await room_service.ensure_room(room_name=room_name)
    token_service = LiveKitTokenService(
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
        ttl_seconds=settings.livekit_room_ttl_seconds,
    )
    token = token_service.create_room_token(
        room_name=room_name,
        participant_identity=participant_identity,
        display_name=request.display_name,
    )

    get_session_registry().put(
        SessionRecord(
            room_name=room_name,
            user_id=current_user.user_id,
            participant_identity=participant_identity,
            assistant_identity=assistant_identity,
            expires_at=expires_at,
            media_policy=media_policy,
        )
    )

    return CreateLiveKitSessionResponse(
        room_name=room_name,
        participant_identity=participant_identity,
        participant_token=token,
        livekit_url=settings.livekit_url,
        expires_at=expires_at,
        assistant_identity=assistant_identity,
        media_policy=media_policy,
    )


@router.post("/session/{room_name}/end")
async def end_session(
    room_name: str,
    request: EndLiveKitSessionRequest,
    current_user: Annotated[StoredUser, Depends(get_current_user)],
) -> EndLiveKitSessionResponse:
    """Stop an owned assistant session and release the registry record."""
    record = get_session_registry().get(room_name)
    if record is not None and record.user_id != current_user.user_id:
        raise AppError("SESSION_NOT_FOUND", "Session not found", status_code=404)
    await get_agent_manager().stop(room_name)
    get_session_registry().remove(room_name, request.participant_identity)
    return EndLiveKitSessionResponse(status="ended", room_name=room_name)


@router.post("/session/{room_name}/agent/start")
async def start_agent_session(
    room_name: str,
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[StoredUser, Depends(get_current_user)],
) -> dict[str, str]:
    """Start the assistant participant for an existing user-owned room."""
    record = get_session_registry().get(room_name)
    if record is None or record.user_id != current_user.user_id:
        raise AppError("SESSION_NOT_FOUND", "Session not found", status_code=404)

    messenger = LiveKitMessenger(
        url=settings.livekit_server_url or settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    )
    timestamp = datetime.now(tz=UTC).isoformat()
    token_service = LiveKitTokenService(
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
        ttl_seconds=settings.livekit_room_ttl_seconds,
    )
    assistant_token = token_service.create_room_token(
        room_name=room_name,
        participant_identity=record.assistant_identity,
        display_name="SightTalk AI",
    )
    get_agent_manager().start(
        room_name=room_name,
        livekit_url=settings.livekit_server_url or settings.livekit_url,
        assistant_token=assistant_token,
        settings=settings,
        media_policy=record.media_policy,
        user_id=record.user_id,
    )
    # Publish initial status and usage events so the frontend can render immediately
    # while the assistant participant is joining and provider setup completes.
    await messenger.send_json(
        room_name=room_name,
        topic="sighttalk.agent",
        payload={
            "type": "agent.status",
            "session_id": room_name,
            "timestamp": timestamp,
            "status": "listening",
        },
    )
    await messenger.send_json(
        room_name=room_name,
        topic="sighttalk.agent",
        payload={
            "type": "cost.estimate",
            "session_id": room_name,
            "timestamp": timestamp,
            "audio_seconds": 0,
            "image_frames_sent": 0,
            "mode": record.media_policy.mode,
        },
    )
    if settings.ai_provider == "mock":
        await messenger.send_json(
            room_name=room_name,
            topic="sighttalk.agent",
            payload={
                "type": "transcript.done",
                "session_id": room_name,
                "timestamp": timestamp,
                "speaker": "assistant",
                "text": "自动监听已开启。你可以直接说话，我会结合摄像头画面回答。",
                "message_id": f"mock-agent-start-{room_name}",
            },
        )
    return {"status": "started", "room_name": room_name}


@router.post("/session/{room_name}/mock-events")
async def send_mock_events(
    room_name: str,
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[StoredUser, Depends(get_current_user)],
) -> dict[str, str]:
    """Send deterministic agent events for local mock-provider demos."""
    if settings.ai_provider != "mock":
        raise AppError(
            "MOCK_PROVIDER_DISABLED",
            "Mock events are only available for AI_PROVIDER=mock",
        )
    record = get_session_registry().get(room_name)
    if record is None or record.user_id != current_user.user_id:
        raise AppError("SESSION_NOT_FOUND", "Session not found", status_code=404)

    messenger = LiveKitMessenger(
        url=settings.livekit_server_url or settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    )
    timestamp = datetime.now(tz=UTC).isoformat()
    await messenger.send_json(
        room_name=room_name,
        topic="sighttalk.agent",
        payload={
            "type": "agent.status",
            "session_id": room_name,
            "timestamp": timestamp,
            "status": "listening",
        },
    )
    await messenger.send_json(
        room_name=room_name,
        topic="sighttalk.agent",
        payload={
            "type": "transcript.done",
            "session_id": room_name,
            "timestamp": timestamp,
            "speaker": "assistant",
            "text": "Mock agent connected. I can receive your microphone and camera stream.",
            "message_id": f"mock-{room_name}",
        },
    )
    await messenger.send_json(
        room_name=room_name,
        topic="sighttalk.agent",
        payload={
            "type": "cost.estimate",
            "session_id": room_name,
            "timestamp": timestamp,
            "audio_seconds": 0,
            "image_frames_sent": 0,
            "mode": record.media_policy.mode,
        },
    )
    return {"status": "sent", "room_name": room_name}
