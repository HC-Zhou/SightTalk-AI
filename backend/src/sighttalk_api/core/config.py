from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from sighttalk_api.schemas.livekit import MediaMode, MediaPolicy

DEFAULT_BAILIAN_REALTIME_MODEL = "qwen3-omni-flash-realtime"
DEFAULT_BAILIAN_REALTIME_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"


class Settings(BaseSettings):
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    sighttalk_data_dir: Path = Path("data")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    auth_secret_key: str = "dev-auth-secret-change-me"
    auth_token_ttl_seconds: int = 604_800
    harness_memory_max_items: int = 20

    livekit_url: str = "ws://localhost:7880"
    livekit_server_url: str | None = None
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "secret"
    livekit_room_ttl_seconds: int = 3600

    ai_provider: str = "bailian"
    bailian_api_key: str = ""
    bailian_region: str = ""
    bailian_app_id: str = ""
    bailian_app_api_url: str = "https://dashscope.aliyuncs.com/api/v1"
    bailian_compatible_api_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    bailian_text_model: str = "qwen-plus"
    bailian_vision_model: str = "qwen-vl-plus"
    bailian_workspace_id: str = ""
    bailian_model: str = DEFAULT_BAILIAN_REALTIME_MODEL
    bailian_realtime_url: str = DEFAULT_BAILIAN_REALTIME_URL
    bailian_turn_silence_duration_ms: int = 2000

    default_media_mode: MediaMode = "balanced"
    economy_max_video_fps: float = 0.2
    balanced_max_video_fps: float = 1.0
    accurate_max_video_fps: float = 2.0
    max_jpeg_edge: int = 1024
    jpeg_quality: int = 75

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def validate_for_session(self) -> None:
        missing: list[str] = []
        if not self.livekit_url:
            missing.append("LIVEKIT_URL")
        if not self.livekit_api_key:
            missing.append("LIVEKIT_API_KEY")
        if not self.livekit_api_secret:
            missing.append("LIVEKIT_API_SECRET")
        if self.ai_provider == "bailian":
            for env_name, value in (
                ("BAILIAN_API_KEY", self.bailian_api_key),
            ):
                if not value:
                    missing.append(env_name)
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required configuration: {joined}")

    def media_policy_for(self, requested_mode: MediaMode | None = None) -> MediaPolicy:
        mode = requested_mode or self.default_media_mode
        fps_by_mode: dict[MediaMode, float] = {
            "economy": self.economy_max_video_fps,
            "balanced": self.balanced_max_video_fps,
            "accurate": self.accurate_max_video_fps,
        }
        return MediaPolicy(
            mode=mode,
            max_video_fps=fps_by_mode[mode],
            max_jpeg_edge=self.max_jpeg_edge,
            jpeg_quality=self.jpeg_quality,
            vad_enabled=True,
        )

    @property
    def bailian_application_id(self) -> str:
        return self.bailian_app_id or self.bailian_workspace_id


@lru_cache
def get_settings() -> Settings:
    return Settings()
