from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="VISION_ASSISTANT_")

    ai_provider: str = Field(default="mock")
    asr_api_url: str | None = Field(default=None)
    multimodal_api_url: str | None = Field(default=None)
    tts_api_url: str | None = Field(default=None)
    api_key: str | None = Field(default=None)

