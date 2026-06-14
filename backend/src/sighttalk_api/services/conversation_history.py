"""File-backed transcript history storage."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from pydantic import BaseModel, ValidationError

from sighttalk_api.core.errors import AppError
from sighttalk_api.schemas.conversation import (
    ConversationArchive,
    ConversationMessage,
    SaveConversationRequest,
)

CONVERSATION_HISTORY_LIMIT = 50
_STORE_LOCK = Lock()


class StoredConversation(BaseModel):
    """Persisted conversation record including the owning user id."""

    user_id: str
    archive: ConversationArchive


class ConversationHistoryStore:
    """Thread-safe JSON store for authenticated transcript history."""

    def __init__(self, data_dir: Path) -> None:
        self._path = data_dir / "conversation_history.json"
        self._lock = _STORE_LOCK

    def list_for_user(self, user_id: str) -> list[ConversationArchive]:
        """Return the newest stored conversations for one user."""
        with self._lock:
            return [
                record.archive
                for record in self._sorted_records(self._read_records())
                if record.user_id == user_id
            ][:CONVERSATION_HISTORY_LIMIT]

    def save_for_user(
        self,
        user_id: str,
        request: SaveConversationRequest,
    ) -> ConversationArchive:
        """Create or replace one completed conversation transcript for a user."""
        messages = normalized_messages(request.messages)
        if not messages:
            raise AppError("EMPTY_CONVERSATION", "Conversation has no transcript text", 422)

        now = datetime.now(tz=UTC)
        archive = ConversationArchive(
            id=request.session_id,
            title=create_conversation_title(messages),
            created_at=now,
            ended_at=now,
            messages=messages,
        )
        stored = StoredConversation(user_id=user_id, archive=archive)
        with self._lock:
            records = [
                record
                for record in self._read_records()
                if not (record.user_id == user_id and record.archive.id == request.session_id)
            ]
            records.append(stored)
            self._write_records(self._limited_records(records))
        return archive

    def _limited_records(self, records: list[StoredConversation]) -> list[StoredConversation]:
        """Keep at most the configured number of history items per user."""
        by_user: dict[str, list[StoredConversation]] = {}
        for record in self._sorted_records(records):
            by_user.setdefault(record.user_id, []).append(record)
        limited: list[StoredConversation] = []
        for user_records in by_user.values():
            limited.extend(user_records[:CONVERSATION_HISTORY_LIMIT])
        return self._sorted_records(limited)

    def _sorted_records(self, records: list[StoredConversation]) -> list[StoredConversation]:
        return sorted(records, key=lambda record: record.archive.ended_at, reverse=True)

    def _read_records(self) -> list[StoredConversation]:
        if not self._path.exists():
            return []
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        raw_records = payload.get("conversations", []) if isinstance(payload, dict) else []
        records: list[StoredConversation] = []
        for raw_record in raw_records:
            try:
                records.append(StoredConversation.model_validate(raw_record))
            except ValidationError:
                continue
        return records

    def _write_records(self, records: list[StoredConversation]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "conversations": [record.model_dump(mode="json") for record in records],
        }
        temporary_path = self._path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary_path.replace(self._path)


def normalized_messages(messages: list[ConversationMessage]) -> list[ConversationMessage]:
    """Trim empty transcript messages while preserving message metadata."""
    normalized: list[ConversationMessage] = []
    for message in messages:
        text = message.text.strip()
        if not text:
            continue
        normalized.append(message.model_copy(update={"text": text}))
    return normalized


def create_conversation_title(messages: list[ConversationMessage]) -> str:
    """Create the sidebar title from the first user message when available."""
    first_user_message = next((message for message in messages if message.speaker == "user"), None)
    source = first_user_message or messages[0]
    return truncate_text(source.text, 28)


def truncate_text(text: str, max_length: int) -> str:
    """Shorten long transcript text for compact sidebar labels."""
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."
