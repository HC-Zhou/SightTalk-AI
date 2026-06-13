"""Per-session realtime metrics and trace helpers."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


class RealtimeMetrics:
    """Track turn latency, provider failures, and interruption counters."""

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.monotonic
        self.turn_index = 0
        self.interrupt_count = 0
        self.provider_error_count = 0
        self._turn_started_at: float | None = None
        self._response_started_at: float | None = None

    def mark_user_turn_started(
        self,
        *,
        source: str,
        force_new: bool = False,
    ) -> dict[str, Any] | None:
        """Mark the start of a user turn and return trace fields when it is new."""
        now = self._clock()
        if not force_new and self._turn_started_at is not None:
            return None
        self.turn_index += 1
        self._turn_started_at = now
        self._response_started_at = None
        return {
            "turn_index": self.turn_index,
            "source": source,
        }

    def mark_assistant_response_started(self) -> dict[str, Any]:
        """Mark first assistant output for the current turn."""
        now = self._clock()
        if self._response_started_at is None:
            self._response_started_at = now
        return {
            "turn_index": self.turn_index,
            "first_response_latency_ms": elapsed_ms(self._turn_started_at, now),
        }

    def mark_turn_completed(self) -> dict[str, Any]:
        """Mark a provider response/playout completion for the current turn."""
        now = self._clock()
        fields = {
            "turn_index": self.turn_index,
            "turn_latency_ms": elapsed_ms(self._turn_started_at, now),
            "answer_elapsed_ms": elapsed_ms(self._response_started_at, now),
        }
        self._turn_started_at = None
        self._response_started_at = None
        return fields

    def mark_interrupt(self, *, source: str, reason: str) -> dict[str, Any]:
        """Record one interruption and return trace fields."""
        now = self._clock()
        self.interrupt_count += 1
        return {
            "turn_index": self.turn_index,
            "source": source,
            "reason": reason,
            "interrupt_count": self.interrupt_count,
            "turn_elapsed_ms": elapsed_ms(self._turn_started_at, now),
            "answer_elapsed_ms": elapsed_ms(self._response_started_at, now),
        }

    def mark_provider_error(self, *, code: str) -> dict[str, Any]:
        """Record one provider error and return trace fields."""
        self.provider_error_count += 1
        return {
            "turn_index": self.turn_index,
            "code": code,
            "provider_error_count": self.provider_error_count,
        }


def elapsed_ms(start: float | None, end: float) -> int | None:
    """Return a non-negative elapsed duration in milliseconds."""
    if start is None:
        return None
    return max(0, round((end - start) * 1000))
