from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock

from sighttalk_api.schemas.livekit import MediaPolicy


@dataclass(frozen=True)
class SessionRecord:
    room_name: str
    participant_identity: str
    assistant_identity: str
    expires_at: datetime
    media_policy: MediaPolicy


class SessionRegistry:
    def __init__(self) -> None:
        self._records: dict[str, SessionRecord] = {}
        self._lock = Lock()

    def put(self, record: SessionRecord) -> None:
        with self._lock:
            self._records[record.room_name] = record

    def get(self, room_name: str) -> SessionRecord | None:
        with self._lock:
            return self._records.get(room_name)

    def remove(self, room_name: str, participant_identity: str | None = None) -> None:
        with self._lock:
            record = self._records.get(room_name)
            if record is None:
                return
            if participant_identity is None or participant_identity == record.participant_identity:
                self._records.pop(room_name, None)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


_registry = SessionRegistry()


def get_session_registry() -> SessionRegistry:
    return _registry
