"""Standalone agent entrypoint and backward-compatible session facade."""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from sighttalk_api.agent.context import AgentSessionContext
from sighttalk_api.agent.tooling import AgentTooling
from sighttalk_api.core.config import Settings, get_settings
from sighttalk_api.providers.base import AIProvider, ProviderEvent
from sighttalk_api.providers.factory import create_provider
from sighttalk_api.schemas.livekit import MediaPolicy
from sighttalk_api.services.long_term_memory import create_long_term_memory
from sighttalk_api.services.memory import MemoryStore

AGENT_TOPIC = "sighttalk.agent"
CONTROL_TOPIC = "sighttalk.control"


class AgentSession:
    """Compatibility facade around context and provider tooling.

    Older tests and callers exercise this class directly. New realtime execution
    uses AgentLifecycle, but this facade keeps the public session behavior stable
    while delegating all state and provider mapping to the newer components.
    """

    def __init__(
        self,
        *,
        session_id: str,
        provider: AIProvider,
        media_policy: MediaPolicy,
        user_id: str = "standalone-agent",
        memory_store: MemoryStore | None = None,
        memory_max_items: int = 20,
        settings: Settings | None = None,
    ) -> None:
        resolved_settings = settings or get_settings()
        self.context = AgentSessionContext(
            session_id=session_id,
            user_id=user_id,
            media_policy=media_policy,
            memory_store=memory_store,
            memory_max_items=memory_max_items,
            short_memory_max_messages=resolved_settings.short_memory_max_messages,
            short_memory_max_estimated_tokens=(
                resolved_settings.short_memory_max_estimated_tokens
            ),
            memory_search_limit=resolved_settings.memory_search_limit,
            memory_search_threshold=resolved_settings.memory_search_threshold,
            memory_agent_id=resolved_settings.memory_agent_id,
            long_term_memory=create_long_term_memory(resolved_settings),
        )
        self.tooling = AgentTooling(
            provider=provider,
            context=self.context,
            settings=resolved_settings,
        )

    @property
    def session_id(self) -> str:
        """Unique session identifier propagated to frontend events."""
        return self.context.session_id

    @property
    def provider(self) -> AIProvider:
        return self.tooling.provider

    @property
    def media_policy(self) -> MediaPolicy:
        return self.context.media_policy

    @media_policy.setter
    def media_policy(self, value: MediaPolicy) -> None:
        self.context.media_policy = value

    @property
    def audio_seconds(self) -> float:
        return self.context.audio_seconds

    @property
    def image_frames_sent(self) -> int:
        return self.context.image_frames_sent

    @image_frames_sent.setter
    def image_frames_sent(self, value: int) -> None:
        self.context.image_frames_sent = value

    async def start(self) -> None:
        """Connect the configured provider without attaching LiveKit transport."""
        await self.tooling.connect()

    async def handle_audio(self, data: bytes, *, sample_rate: int = 16_000) -> None:
        """Forward audio for tests or standalone worker usage."""
        await self.tooling.send_audio(data, sample_rate=sample_rate)

    async def handle_control_message(self, raw: str | bytes) -> dict[str, Any] | None:
        return await self.tooling.handle_control_message(raw)

    def map_provider_event(self, event: ProviderEvent) -> dict[str, Any] | None:
        return self.tooling.map_provider_event(event)

    async def handle_provider_event(self, event: ProviderEvent) -> dict[str, Any] | None:
        return await self.tooling.handle_provider_event(event)

    def status_event(self, status: str) -> dict[str, Any]:
        return self.context.status_event(status)

    def cost_event(self) -> dict[str, Any]:
        return self.context.cost_event()

    def error_event(self, code: str, message: str) -> dict[str, Any]:
        return self.context.error_event(code, message)


async def run_agent_worker() -> None:
    """Validate provider startup and keep a standalone worker process alive."""
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
    """CLI entrypoint for deployment startup checks and standalone worker mode."""
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
