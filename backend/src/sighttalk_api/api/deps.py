"""FastAPI dependency providers for settings, auth, and current user."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header

from sighttalk_api.core.config import Settings, get_settings
from sighttalk_api.core.errors import AppError
from sighttalk_api.services.auth import AuthService, StoredUser, UserStore
from sighttalk_api.services.conversation_history import ConversationHistoryStore


def get_user_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserStore:
    """Create a file-backed user store rooted in the configured data directory."""
    return UserStore(settings.sighttalk_data_dir)


def get_auth_service(
    settings: Annotated[Settings, Depends(get_settings)],
    user_store: Annotated[UserStore, Depends(get_user_store)],
) -> AuthService:
    """Create the authentication service for the current request scope."""
    return AuthService(settings=settings, user_store=user_store)


def get_conversation_history_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConversationHistoryStore:
    """Create the file-backed transcript history store."""
    return ConversationHistoryStore(settings.sighttalk_data_dir)


def get_current_user(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    authorization: Annotated[str | None, Header()] = None,
) -> StoredUser:
    """Resolve and validate the Authorization bearer token."""
    if not authorization:
        raise AppError("UNAUTHORIZED", "Authentication required", status_code=401)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError("UNAUTHORIZED", "Authentication required", status_code=401)
    return auth_service.authenticate_token(token)
