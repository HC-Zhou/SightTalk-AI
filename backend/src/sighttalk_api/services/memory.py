"""Append-only user memory storage for previous conversation transcripts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Literal, cast


@dataclass(frozen=True)
class MemoryRecord:
    """One transcript entry persisted as user-scoped memory."""

    user_id: str
    session_id: str
    timestamp: datetime
    speaker: Literal["user", "assistant"]
    text: str


class MemoryStore:
    """Thread-safe JSONL memory store for single-node deployments."""

    def __init__(self, data_dir: Path) -> None:
        self._memory_dir = data_dir / "memory"
        self._lock = Lock()

    def append(self, record: MemoryRecord) -> None:
        """Append a non-empty transcript memory record."""
        text = record.text.strip()
        if not text:
            return
        payload = {
            **asdict(record),
            "timestamp": record.timestamp.isoformat(),
            "text": text,
        }
        path = self._path_for(record.user_id)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, sort_keys=True))
                file.write("\n")

    def recent(self, *, user_id: str, limit: int) -> list[MemoryRecord]:
        """Return the newest valid memory records for a user."""
        if limit <= 0:
            return []
        path = self._path_for(user_id)
        if not path.exists():
            return []
        records: list[MemoryRecord] = []
        with self._lock:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                return []
        for line in lines:
            record = self._record_from_line(line)
            if record is not None and record.user_id == user_id:
                records.append(record)
        return records[-limit:]

    def _path_for(self, user_id: str) -> Path:
        """Resolve the user-scoped memory path without exposing raw user ids."""
        return self._memory_dir / f"{safe_memory_file_name(user_id)}.jsonl"

    def _record_from_line(self, line: str) -> MemoryRecord | None:
        """Decode one JSONL record and ignore corrupt or incompatible rows."""
        try:
            payload = json.loads(line)
            raw_speaker = str(payload["speaker"])
            if raw_speaker not in ("user", "assistant"):
                return None
            speaker = cast(Literal["user", "assistant"], raw_speaker)
            return MemoryRecord(
                user_id=str(payload["user_id"]),
                session_id=str(payload["session_id"]),
                timestamp=datetime.fromisoformat(str(payload["timestamp"])),
                speaker=speaker,
                text=str(payload["text"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None


def safe_memory_file_name(user_id: str) -> str:
    """Convert a user id into a safe file-name stem."""
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in user_id)
    return safe or "unknown"


def memory_record_now(
    *,
    user_id: str,
    session_id: str,
    speaker: Literal["user", "assistant"],
    text: str,
) -> MemoryRecord:
    """Create a timestamped memory record using the current UTC time."""
    return MemoryRecord(
        user_id=user_id,
        session_id=session_id,
        timestamp=datetime.now(tz=UTC),
        speaker=speaker,
        text=text,
    )
