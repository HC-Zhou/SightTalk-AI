"""Factory for selecting the configured realtime AI provider."""

from __future__ import annotations

from sighttalk_api.core.config import Settings
from sighttalk_api.providers.bailian import BailianRealtimeProvider
from sighttalk_api.providers.base import AIProvider
from sighttalk_api.providers.gemini_live import GeminiLiveProvider
from sighttalk_api.providers.mock import MockRealtimeProvider
from sighttalk_api.providers.openai_realtime import OpenAIRealtimeProvider


def create_provider(settings: Settings) -> AIProvider:
    """Instantiate the provider adapter selected by application settings."""
    if settings.ai_provider == "bailian":
        settings.validate_for_session()
        return BailianRealtimeProvider(
            api_key=settings.bailian_api_key,
            realtime_url=settings.bailian_realtime_url,
            region=settings.bailian_region,
            workspace_id=settings.bailian_workspace_id,
            model=settings.bailian_model,
            turn_silence_duration_ms=settings.bailian_turn_silence_duration_ms,
            manual_response_enabled=settings.ai_manual_response_enabled,
        )
    if settings.ai_provider == "mock":
        return MockRealtimeProvider(
            manual_response_enabled=settings.ai_manual_response_enabled,
        )
    if settings.ai_provider == "openai":
        settings.validate_for_session()
        return OpenAIRealtimeProvider(
            api_key=settings.openai_api_key,
            realtime_url=settings.openai_realtime_url,
            model=settings.openai_realtime_model,
            voice=settings.openai_realtime_voice,
        )
    if settings.ai_provider == "gemini":
        settings.validate_for_session()
        return GeminiLiveProvider(
            api_key=settings.gemini_api_key,
            live_url=settings.gemini_live_url,
            model=settings.gemini_live_model,
            voice=settings.gemini_live_voice,
        )
    raise ValueError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")
