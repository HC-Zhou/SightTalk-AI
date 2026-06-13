"""Environment-backed application settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from sighttalk_api.schemas.livekit import MediaMode, MediaPolicy

DEFAULT_BAILIAN_REALTIME_MODEL = "qwen3-omni-flash-realtime"
DEFAULT_BAILIAN_REALTIME_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
MemoryBackend = Literal["nanobot", "local_jsonl", "mem0", "disabled"]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and `.env`."""

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
    memory_backend: MemoryBackend = "nanobot"
    memory_agent_id: str = "sighttalk"
    memory_search_limit: int = 5
    memory_search_threshold: float = 0.3
    mem0_api_key: str = ""
    mem0_host: str = ""
    mem0_local_config_json: str = ""
    mem0_agent_id: str = "sighttalk"
    mem0_search_limit: int = 5
    mem0_search_threshold: float = 0.3
    short_memory_max_messages: int = 24
    short_memory_max_estimated_tokens: int = 8000

    livekit_url: str = "ws://localhost:7880"
    livekit_server_url: str | None = None
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "dev-livekit-secret-at-least-32-bytes-change-me"
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
    bailian_turn_silence_duration_ms: int = 800
    ai_manual_response_enabled: bool = False

    default_media_mode: MediaMode = "balanced"
    economy_max_video_fps: float = 0.2
    balanced_max_video_fps: float = 0.5
    accurate_max_video_fps: float = 1.0
    max_jpeg_edge: int = 640
    jpeg_quality: int = 65

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        """Support comma-separated CORS origins from environment variables."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("memory_backend", mode="before")
    @classmethod
    def normalize_memory_backend(cls, value: str) -> str:
        """Normalize memory backend names from environment variables."""
        return value.strip().lower()

    def validate_for_session(self) -> None:
        """Validate credentials required before creating a realtime session."""
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
        if self.memory_backend == "mem0" and not (
            self.mem0_api_key or self.mem0_host or self.mem0_local_config_json
        ):
            missing.append("MEM0_API_KEY or MEM0_HOST or MEM0_LOCAL_CONFIG_JSON")
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required configuration: {joined}")

    def media_policy_for(self, requested_mode: MediaMode | None = None) -> MediaPolicy:
        """Resolve the effective camera sampling policy for a requested mode."""
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
        """Return the Bailian application identifier if configured."""
        return self.bailian_app_id or self.bailian_workspace_id


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for dependency injection and service factories."""
    return Settings()
