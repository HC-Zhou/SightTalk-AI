"""Conversation transcript history API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """One finalized transcript message shown in conversation history."""

    id: str = Field(min_length=1)
    speaker: Literal["user", "assistant"]
    text: str
    final: bool


class SaveConversationRequest(BaseModel):
    """Request body for saving an ended video conversation transcript."""

    session_id: str = Field(min_length=1)
    messages: list[ConversationMessage]


class ConversationArchive(BaseModel):
    """Conversation history item returned to the authenticated user."""

    id: str
    title: str
    created_at: datetime
    ended_at: datetime
    messages: list[ConversationMessage]


class ConversationListResponse(BaseModel):
    """Pageless history response for the home sidebar."""

    conversations: list[ConversationArchive]
