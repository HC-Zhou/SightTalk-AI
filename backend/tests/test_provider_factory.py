from __future__ import annotations

import pytest

from sighttalk_api.core.config import Settings
from sighttalk_api.providers.bailian import BailianRealtimeProvider
from sighttalk_api.providers.factory import create_provider
from sighttalk_api.providers.mock import MockRealtimeProvider


def test_provider_factory_selects_bailian() -> None:
    settings = Settings(
        ai_provider="bailian",
        bailian_api_key="key",
        bailian_region="cn",
        bailian_workspace_id="workspace",
        bailian_model="qwen-omni",
        bailian_realtime_url="wss://example.test/realtime",
    )

    provider = create_provider(settings)

    assert isinstance(provider, BailianRealtimeProvider)


def test_provider_factory_passes_bailian_turn_silence_duration() -> None:
    settings = Settings(
        ai_provider="bailian",
        bailian_api_key="key",
        bailian_region="cn",
        bailian_workspace_id="workspace",
        bailian_model="qwen-omni",
        bailian_realtime_url="wss://example.test/realtime",
        bailian_turn_silence_duration_ms=2500,
    )

    provider = create_provider(settings)

    assert isinstance(provider, BailianRealtimeProvider)
    assert provider._turn_silence_duration_ms == 2500  # noqa: SLF001


def test_provider_factory_uses_bailian_realtime_defaults() -> None:
    settings = Settings(ai_provider="bailian", bailian_api_key="key")

    provider = create_provider(settings)

    assert isinstance(provider, BailianRealtimeProvider)
    assert provider._model == "qwen3-omni-flash-realtime"  # noqa: SLF001
    assert (  # noqa: SLF001
        provider._realtime_url == "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    )


def test_provider_factory_selects_mock() -> None:
    settings = Settings(ai_provider="mock")

    provider = create_provider(settings)

    assert isinstance(provider, MockRealtimeProvider)


def test_provider_factory_rejects_unknown_provider() -> None:
    settings = Settings(ai_provider="unknown")

    with pytest.raises(ValueError, match="Unsupported AI_PROVIDER"):
        create_provider(settings)
