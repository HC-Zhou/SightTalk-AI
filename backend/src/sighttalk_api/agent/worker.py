from __future__ import annotations

import argparse
import asyncio
import base64
import json
from datetime import UTC, datetime
from typing import Any

from sighttalk_api.agent.media_policy import derive_mode_policy
from sighttalk_api.core.config import get_settings
from sighttalk_api.providers.base import (
    AIProvider,
    AudioChunk,
    ControlEvent,
    ProviderEvent,
    ProviderSessionConfig,
)
from sighttalk_api.providers.factory import create_provider
from sighttalk_api.schemas.livekit import MediaPolicy

AGENT_TOPIC = "sighttalk.agent"
CONTROL_TOPIC = "sighttalk.control"


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


class AgentSession:
    def __init__(self, *, session_id: str, provider: AIProvider, media_policy: MediaPolicy) -> None:
        self.session_id = session_id
        self.provider = provider
        self.media_policy = media_policy
        self.audio_seconds = 0.0
        self.image_frames_sent = 0

    async def start(self) -> None:
        settings = get_settings()
        await self.provider.connect(
            ProviderSessionConfig(
                session_id=self.session_id,
                model=settings.bailian_model,
                workspace_id=settings.bailian_workspace_id,
                system_prompt=(
                    "You are SightTalk AI, a concise visual voice assistant. "
                    "Use camera context when it is available and be clear when it is not."
                ),
            )
        )

    async def handle_audio(self, data: bytes, *, sample_rate: int = 16_000) -> None:
        self.audio_seconds += len(data) / max(sample_rate * 2, 1)
        await self.provider.send_audio(AudioChunk(data=data, sample_rate=sample_rate))

    async def handle_control_message(self, raw: str | bytes) -> dict[str, Any] | None:
        try:
            payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except json.JSONDecodeError:
            return self.error_event("MALFORMED_CONTROL_EVENT", "Malformed control event")

        event_type = payload.get("type")
        if event_type == "client.mode.update":
            mode = payload.get("mode")
            if mode in ("economy", "balanced", "accurate"):
                self.media_policy = derive_mode_policy(self.media_policy, mode)
                await self.provider.send_control(ControlEvent(type="mode_update", value=mode))
                return self.cost_event()
            return self.error_event("INVALID_MEDIA_MODE", "Unsupported media mode")
        if event_type == "client.interrupt":
            await self.provider.send_control(ControlEvent(type="interrupt"))
            return self.status_event("listening")
        return None

    def map_provider_event(self, event: ProviderEvent) -> dict[str, Any] | None:
        base: dict[str, Any] = {
            "session_id": self.session_id,
            "timestamp": utc_now(),
        }
        if event.type == "status":
            return {**base, "type": "agent.status", "status": event.status}
        if event.type == "transcript_delta":
            return {
                **base,
                "type": "transcript.delta",
                "speaker": event.speaker,
                "text": event.text,
                "message_id": event.message_id,
            }
        if event.type == "transcript_done":
            return {
                **base,
                "type": "transcript.done",
                "speaker": event.speaker,
                "text": event.text,
                "message_id": event.message_id,
            }
        if event.type == "response_done":
            return {
                **base,
                "type": "response.done",
                "message_id": event.message_id,
                "audio_playback_complete": False,
            }
        if event.type == "audio_delta":
            return {
                **base,
                "type": "audio.delta",
                "message_id": event.message_id,
                "mime_type": event.mime_type,
                "audio": base64.b64encode(event.audio).decode("ascii"),
            }
        if event.type == "error":
            return {**base, "type": "error", "code": event.code, "message": event.message}
        return None

    def status_event(self, status: str) -> dict[str, Any]:
        return {
            "type": "agent.status",
            "session_id": self.session_id,
            "timestamp": utc_now(),
            "status": status,
        }

    def cost_event(self) -> dict[str, Any]:
        return {
            "type": "cost.estimate",
            "session_id": self.session_id,
            "timestamp": utc_now(),
            "audio_seconds": round(self.audio_seconds, 2),
            "image_frames_sent": self.image_frames_sent,
            "mode": self.media_policy.mode,
        }

    def error_event(self, code: str, message: str) -> dict[str, Any]:
        return {
            "type": "error",
            "session_id": self.session_id,
            "timestamp": utc_now(),
            "code": code,
            "message": message,
        }


async def run_agent_worker() -> None:
    settings = get_settings()
    provider = create_provider(settings)
    session = AgentSession(
        session_id="standalone-agent",
        provider=provider,
        media_policy=settings.media_policy_for(),
    )
    await session.start()
    print("SightTalk agent worker started. LiveKit room attachment is configured by deployment.")
    while True:
        await asyncio.sleep(3600)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SightTalk realtime agent worker.")
    parser.add_argument("--once", action="store_true", help="Validate startup and exit.")
    args = parser.parse_args()
    if args.once:
        settings = get_settings()
        create_provider(settings)
        print("SightTalk agent worker configuration is valid.")
        return
    asyncio.run(run_agent_worker())


if __name__ == "__main__":
    main()
