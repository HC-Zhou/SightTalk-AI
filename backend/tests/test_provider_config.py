import pytest

from sighttalk_api.ai.provider_adapters import build_adapters
from sighttalk_api.core.config import Settings


def test_default_settings_use_mock_provider() -> None:
    settings = Settings()

    assert settings.ai_provider == "mock"
    assert settings.asr_api_url is None
    assert settings.multimodal_api_url is None
    assert settings.tts_api_url is None
    assert settings.bailian_api_key is None


def test_build_adapters_returns_mock_adapters_by_default() -> None:
    asr, multimodal, tts = build_adapters(Settings(ai_provider="mock"))

    assert asr.__class__.__name__ == "MockAsrAdapter"
    assert multimodal.__class__.__name__ == "MockMultimodalAdapter"
    assert tts.__class__.__name__ == "MockTtsAdapter"


def test_build_adapters_returns_bailian_adapters() -> None:
    asr, multimodal, tts = build_adapters(
        Settings(ai_provider="bailian", bailian_api_key="sk-test")
    )

    assert asr.__class__.__name__ == "BailianAsrAdapter"
    assert multimodal.__class__.__name__ == "BailianMultimodalAdapter"
    assert tts.__class__.__name__ == "BailianTtsAdapter"


def test_build_bailian_adapters_requires_api_key() -> None:
    with pytest.raises(ValueError, match="VISION_ASSISTANT_BAILIAN_API_KEY"):
        build_adapters(Settings(ai_provider="bailian"))
