"""Authenticated conversation history API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from sighttalk_api.api.deps import get_conversation_history_store, get_current_user
from sighttalk_api.schemas.conversation import (
    ConversationArchive,
    ConversationListResponse,
    SaveConversationRequest,
)
from sighttalk_api.services.auth import StoredUser
from sighttalk_api.services.conversation_history import ConversationHistoryStore

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(
    current_user: Annotated[StoredUser, Depends(get_current_user)],
    store: Annotated[ConversationHistoryStore, Depends(get_conversation_history_store)],
) -> ConversationListResponse:
    """List transcript history for the authenticated user."""
    return ConversationListResponse(conversations=store.list_for_user(current_user.user_id))


@router.post("")
async def save_conversation(
    request: SaveConversationRequest,
    current_user: Annotated[StoredUser, Depends(get_current_user)],
    store: Annotated[ConversationHistoryStore, Depends(get_conversation_history_store)],
) -> ConversationArchive:
    """Save or replace one ended video conversation transcript."""
    return store.save_for_user(current_user.user_id, request)
