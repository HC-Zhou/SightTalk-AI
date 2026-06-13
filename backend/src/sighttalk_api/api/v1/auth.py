"""Authentication API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from sighttalk_api.api.deps import get_auth_service, get_current_user
from sighttalk_api.schemas.auth import AuthCredentials, AuthResponse, UserProfile
from sighttalk_api.services.auth import AuthService, StoredUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(
    request: AuthCredentials,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthResponse:
    """Create an account and return a bearer token."""
    return auth_service.register(email=request.email, password=request.password)


@router.post("/login")
async def login(
    request: AuthCredentials,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthResponse:
    """Authenticate an existing account and return a bearer token."""
    return auth_service.login(email=request.email, password=request.password)


@router.get("/me")
async def me(current_user: Annotated[StoredUser, Depends(get_current_user)]) -> UserProfile:
    """Return the authenticated user's public profile."""
    return current_user.profile()
