from sighttalk_api.ai.adapters import AsrAdapter, MultimodalAdapter, TtsAdapter
from sighttalk_api.ai.mock_adapters import MockAsrAdapter, MockMultimodalAdapter, MockTtsAdapter
from sighttalk_api.core.config import Settings


def build_adapters(settings: Settings) -> tuple[AsrAdapter, MultimodalAdapter, TtsAdapter]:
    if settings.ai_provider == "mock":
        return MockAsrAdapter(), MockMultimodalAdapter(), MockTtsAdapter()
    raise ValueError(
        "Only the mock provider is wired in this MVP. "
        "Set VISION_ASSISTANT_AI_PROVIDER=mock for local demos."
    )

