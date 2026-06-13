from sighttalk_api.core.config import Settings


def test_bailian_defaults_are_available() -> None:
    settings = Settings()

    assert settings.bailian_api_key is None
    assert settings.bailian_compatible_base_url == (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    assert settings.bailian_asr_model == "qwen3-asr-flash"
    assert settings.bailian_vision_model == "qwen3.5-plus"
    assert settings.bailian_tts_endpoint == (
        "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer"
    )
    assert settings.bailian_tts_model == "cosyvoice-v3-flash"
    assert settings.bailian_tts_voice == "longanyang"
    assert settings.bailian_tts_format == "wav"
    assert settings.bailian_tts_sample_rate == 24000
    assert settings.bailian_timeout_seconds == 30.0


def test_bailian_settings_can_be_constructed_explicitly() -> None:
    settings = Settings(
        ai_provider="bailian",
        bailian_api_key="sk-test",
        bailian_vision_model="qwen-vl-plus",
        bailian_tts_voice="longcheng",
    )

    assert settings.ai_provider == "bailian"
    assert settings.bailian_api_key == "sk-test"
    assert settings.bailian_vision_model == "qwen-vl-plus"
    assert settings.bailian_tts_voice == "longcheng"
