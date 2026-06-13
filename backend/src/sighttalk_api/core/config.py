from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="VISION_ASSISTANT_")

    ai_provider: str = Field(default="mock")
    asr_api_url: str | None = Field(default=None)
    multimodal_api_url: str | None = Field(default=None)
    tts_api_url: str | None = Field(default=None)
    api_key: str | None = Field(default=None)
    bailian_api_key: str | None = Field(default=None)
    bailian_compatible_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    bailian_asr_model: str = Field(default="qwen3-asr-flash")
    bailian_vision_model: str = Field(default="qwen3.5-plus")
    bailian_tts_endpoint: str = Field(
        default="https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer"
    )
    bailian_tts_model: str = Field(default="cosyvoice-v3-flash")
    bailian_tts_voice: str = Field(default="longanyang")
    bailian_tts_format: str = Field(default="wav")
    bailian_tts_sample_rate: int = Field(default=24000)
    bailian_timeout_seconds: float = Field(default=30.0)
