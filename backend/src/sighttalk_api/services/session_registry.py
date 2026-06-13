"""Process-local session registry for active LiveKit conversations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock

from sighttalk_api.schemas.livekit import MediaPolicy


@dataclass(frozen=True)
class SessionRecord:
    """Metadata required to authorize and start a LiveKit assistant session."""

    room_name: str
    user_id: str
    participant_identity: str
    assistant_identity: str
    expires_at: datetime
    media_policy: MediaPolicy


class SessionRegistry:
    """Thread-safe in-memory registry for single-process deployments.

    Production multi-instance deployments should replace this with shared storage
    because records are intentionally not replicated between API processes.
    """

    def __init__(self) -> None:
        self._records: dict[str, SessionRecord] = {}
        self._lock = Lock()

    def put(self, record: SessionRecord) -> None:
        """Store or replace one active session record by room name."""
        with self._lock:
            self._records[record.room_name] = record

    def get(self, room_name: str) -> SessionRecord | None:
        """Return the active session record for a room if present."""
        with self._lock:
            return self._records.get(room_name)

    def remove(self, room_name: str, participant_identity: str | None = None) -> None:
        """Remove a session, optionally requiring participant identity ownership."""
        with self._lock:
            record = self._records.get(room_name)
            if record is None:
                return
            if participant_identity is None or participant_identity == record.participant_identity:
                self._records.pop(room_name, None)

    def clear(self) -> None:
        """Remove all session records; intended for tests and process cleanup."""
        with self._lock:
            self._records.clear()


_registry = SessionRegistry()


def get_session_registry() -> SessionRegistry:
    """Return the process-local session registry singleton."""
    return _registry
