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


def test_provider_factory_selects_mock() -> None:
    settings = Settings(ai_provider="mock")

    provider = create_provider(settings)

    assert isinstance(provider, MockRealtimeProvider)


def test_provider_factory_rejects_unknown_provider() -> None:
    settings = Settings(ai_provider="unknown")

    with pytest.raises(ValueError, match="Unsupported AI_PROVIDER"):
        create_provider(settings)
