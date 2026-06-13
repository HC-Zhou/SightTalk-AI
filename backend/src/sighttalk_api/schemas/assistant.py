from __future__ import annotations

from pydantic import BaseModel, Field


class AssistantTurnRequest(BaseModel):
    room_name: str
    prompt: str = Field(min_length=1, max_length=4000)
    image_data_url: str | None = None
    bailian_session_id: str | None = None


class AssistantTurnResponse(BaseModel):
    room_name: str
    text: str
    bailian_session_id: str | None = None
