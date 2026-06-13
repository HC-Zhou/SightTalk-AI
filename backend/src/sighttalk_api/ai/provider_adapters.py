from sighttalk_api.ai.adapters import AsrAdapter, MultimodalAdapter, TtsAdapter
from sighttalk_api.ai.bailian_adapters import (
    BailianAsrAdapter,
    BailianMultimodalAdapter,
    BailianTtsAdapter,
)
from sighttalk_api.ai.mock_adapters import MockAsrAdapter, MockMultimodalAdapter, MockTtsAdapter
from sighttalk_api.core.config import Settings


def build_adapters(settings: Settings) -> tuple[AsrAdapter, MultimodalAdapter, TtsAdapter]:
    if settings.ai_provider == "mock":
        return MockAsrAdapter(), MockMultimodalAdapter(), MockTtsAdapter()
    if settings.ai_provider == "bailian":
        return (
            BailianAsrAdapter(settings),
            BailianMultimodalAdapter(settings),
            BailianTtsAdapter(settings),
        )
    raise ValueError(
        "Unsupported AI provider. Set VISION_ASSISTANT_AI_PROVIDER to 'mock' or 'bailian'."
    )
