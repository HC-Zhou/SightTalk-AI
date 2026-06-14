"""Dialogue stability helpers for realtime response epochs and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from sighttalk_api.providers.base import ProviderEvent


@dataclass(frozen=True)
class ProviderEventStamp:
    """Correlation metadata assigned to one provider event."""

    response_epoch: int
    response_id: str
    stale: bool


@dataclass(frozen=True)
class InterruptResult:
    """State transition metadata produced by an interrupt."""

    previous_epoch: int
    response_epoch: int
    advanced: bool


class DialogueStabilityCoordinator:
    """Tracks response epochs so interrupted assistant output cannot leak through."""

    def __init__(self) -> None:
        self.response_epoch = 0
        self.stale_events_dropped = 0
        self._response_epochs: dict[str, int] = {}
        self._playback_epoch: int | None = None

    def stamp_provider_event(self, event: ProviderEvent) -> ProviderEventStamp:
        """Assign epoch metadata to a provider event using provider ids when present."""
        response_id = event.message_id
        if response_id:
            response_epoch = self._response_epochs.setdefault(response_id, self.response_epoch)
        else:
            response_epoch = self.response_epoch
        return ProviderEventStamp(
            response_epoch=response_epoch,
            response_id=response_id,
            stale=response_epoch != self.response_epoch,
        )

    def begin_playback(self, response_epoch: int) -> bool:
        """Mark playback active for the current epoch if the event is still fresh."""
        if response_epoch != self.response_epoch:
            self.mark_stale_event_dropped()
            return False
        self._playback_epoch = response_epoch
        return True

    def complete_playback(self, response_epoch: int) -> bool:
        """Return whether completion still belongs to the active response epoch."""
        if response_epoch != self.response_epoch:
            self.mark_stale_event_dropped()
            return False
        self._playback_epoch = None
        return True

    def interrupt(self, *, playback_active: bool) -> InterruptResult:
        """Invalidate the active playback epoch once for a real assistant response."""
        previous_epoch = self.response_epoch
        advanced = playback_active or self._playback_epoch is not None
        if advanced:
            self.response_epoch += 1
            self._playback_epoch = None
        return InterruptResult(
            previous_epoch=previous_epoch,
            response_epoch=self.response_epoch,
            advanced=advanced,
        )

    def is_current(self, response_epoch: int) -> bool:
        """Return whether an event epoch is still active."""
        return response_epoch == self.response_epoch

    def mark_stale_event_dropped(self) -> int:
        """Record one stale provider event drop."""
        self.stale_events_dropped += 1
        return self.stale_events_dropped
