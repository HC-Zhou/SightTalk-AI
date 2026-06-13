from __future__ import annotations

from sighttalk_api.core.config import Settings
from sighttalk_api.providers.bailian import BailianRealtimeProvider
from sighttalk_api.providers.base import AIProvider
from sighttalk_api.providers.mock import MockRealtimeProvider


def create_provider(settings: Settings) -> AIProvider:
    if settings.ai_provider == "bailian":
        settings.validate_for_session()
        return BailianRealtimeProvider(
            api_key=settings.bailian_api_key,
            realtime_url=settings.bailian_realtime_url,
            region=settings.bailian_region,
            workspace_id=settings.bailian_workspace_id,
            model=settings.bailian_model,
            turn_silence_duration_ms=settings.bailian_turn_silence_duration_ms,
        )
    if settings.ai_provider == "mock":
        return MockRealtimeProvider()
    raise ValueError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")
