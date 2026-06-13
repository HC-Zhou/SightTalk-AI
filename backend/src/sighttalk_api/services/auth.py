"""File-backed authentication services for local SightTalk deployments."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

import jwt

from sighttalk_api.core.config import Settings
from sighttalk_api.core.errors import AppError
from sighttalk_api.schemas.auth import AuthResponse, UserProfile

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 210_000
JWT_ALGORITHM = "HS256"


@dataclass(frozen=True)
class PasswordHash:
    """Stored password hash metadata and digest."""

    algorithm: str
    iterations: int
    salt: str
    hash: str


@dataclass(frozen=True)
class StoredUser:
    """Persisted user record used by API authorization dependencies."""

    user_id: str
    email: str
    created_at: datetime
    password_hash: PasswordHash

    def profile(self) -> UserProfile:
        """Return the public user profile without password hash material."""
        return UserProfile(
            user_id=self.user_id,
            email=self.email,
            created_at=self.created_at,
        )


class PasswordHasher:
    """PBKDF2 password hashing and verification helper."""

    def hash_password(self, password: str) -> PasswordHash:
        """Hash a plaintext password with a per-password random salt."""
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PASSWORD_ITERATIONS,
        )
        return PasswordHash(
            algorithm=PASSWORD_ALGORITHM,
            iterations=PASSWORD_ITERATIONS,
            salt=base64.b64encode(salt).decode("ascii"),
            hash=base64.b64encode(digest).decode("ascii"),
        )

    def verify_password(self, password: str, password_hash: PasswordHash) -> bool:
        """Verify a plaintext password using constant-time digest comparison."""
        if password_hash.algorithm != PASSWORD_ALGORITHM:
            return False
        try:
            salt = base64.b64decode(password_hash.salt)
            expected = base64.b64decode(password_hash.hash)
        except ValueError:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            password_hash.iterations,
        )
        return hmac.compare_digest(actual, expected)


class UserStore:
    """Thread-safe JSON user store for single-node deployments.

    The store intentionally avoids retaining users in memory between calls so tests
    and local development can observe file changes deterministically.
    """

    def __init__(self, data_dir: Path) -> None:
        self._path = data_dir / "users.json"
        self._lock = Lock()

    def create_user(self, *, email: str, password_hash: PasswordHash) -> StoredUser:
        """Create a user, enforcing normalized email uniqueness."""
        normalized_email = normalize_email(email)
        with self._lock:
            users = self._read_users()
            if any(user.email == normalized_email for user in users):
                raise AppError("USER_ALREADY_EXISTS", "User already exists", status_code=409)
            user = StoredUser(
                user_id=f"user_{uuid.uuid4().hex}",
                email=normalized_email,
                created_at=datetime.now(tz=UTC),
                password_hash=password_hash,
            )
            self._write_users([*users, user])
            return user

    def get_by_email(self, email: str) -> StoredUser | None:
        """Find a user by normalized email address."""
        normalized_email = normalize_email(email)
        with self._lock:
            return next(
                (user for user in self._read_users() if user.email == normalized_email),
                None,
            )

    def get_by_id(self, user_id: str) -> StoredUser | None:
        """Find a user by stable user id."""
        with self._lock:
            return next((user for user in self._read_users() if user.user_id == user_id), None)

    def _read_users(self) -> list[StoredUser]:
        """Read valid user records and skip malformed persisted entries."""
        if not self._path.exists():
            return []
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        raw_users = payload.get("users", []) if isinstance(payload, dict) else []
        users: list[StoredUser] = []
        for raw_user in raw_users:
            if not isinstance(raw_user, dict):
                continue
            raw_hash = raw_user.get("password_hash")
            if not isinstance(raw_hash, dict):
                continue
            try:
                users.append(
                    StoredUser(
                        user_id=str(raw_user["user_id"]),
                        email=normalize_email(str(raw_user["email"])),
                        created_at=datetime.fromisoformat(str(raw_user["created_at"])),
                        password_hash=PasswordHash(
                            algorithm=str(raw_hash["algorithm"]),
                            iterations=int(raw_hash["iterations"]),
                            salt=str(raw_hash["salt"]),
                            hash=str(raw_hash["hash"]),
                        ),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return users

    def _write_users(self, users: list[StoredUser]) -> None:
        """Atomically replace the user database file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "users": [
                {
                    **asdict(user),
                    "created_at": user.created_at.isoformat(),
                    "password_hash": asdict(user.password_hash),
                }
                for user in users
            ]
        }
        temporary_path = self._path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary_path.replace(self._path)


class AuthService:
    """Application authentication facade used by API routes."""

    def __init__(self, *, settings: Settings, user_store: UserStore) -> None:
        self._settings = settings
        self._user_store = user_store
        self._password_hasher = PasswordHasher()

    def register(self, *, email: str, password: str) -> AuthResponse:
        """Register a new account and return an access token."""
        user = self._user_store.create_user(
            email=email,
            password_hash=self._password_hasher.hash_password(password),
        )
        return self._auth_response_for(user)

    def login(self, *, email: str, password: str) -> AuthResponse:
        """Authenticate credentials and return a fresh access token."""
        user = self._user_store.get_by_email(email)
        if user is None or not self._password_hasher.verify_password(password, user.password_hash):
            raise AppError("INVALID_CREDENTIALS", "Invalid email or password", status_code=401)
        return self._auth_response_for(user)

    def authenticate_token(self, token: str) -> StoredUser:
        """Validate a bearer token and resolve the stored user."""
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._settings.auth_secret_key,
                algorithms=[JWT_ALGORITHM],
            )
        except jwt.PyJWTError as exc:
            raise AppError("UNAUTHORIZED", "Invalid or expired token", status_code=401) from exc
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AppError("UNAUTHORIZED", "Invalid or expired token", status_code=401)
        user = self._user_store.get_by_id(subject)
        if user is None:
            raise AppError("UNAUTHORIZED", "Invalid or expired token", status_code=401)
        return user

    def _auth_response_for(self, user: StoredUser) -> AuthResponse:
        """Issue a signed JWT and pair it with the public profile."""
        expires_at = datetime.now(tz=UTC) + timedelta(
            seconds=self._settings.auth_token_ttl_seconds
        )
        token = jwt.encode(
            {
                "sub": user.user_id,
                "email": user.email,
                "iat": datetime.now(tz=UTC),
                "exp": expires_at,
            },
            self._settings.auth_secret_key,
            algorithm=JWT_ALGORITHM,
        )
        return AuthResponse(
            user=user.profile(),
            access_token=token,
            expires_at=expires_at,
        )


def normalize_email(email: str) -> str:
    """Normalize email addresses for lookup and uniqueness checks."""
    return email.strip().lower()
