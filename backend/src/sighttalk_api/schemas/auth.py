from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class AuthCredentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise ValueError("Invalid email address")
        return email


class UserProfile(BaseModel):
    user_id: str
    email: str
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserProfile
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
