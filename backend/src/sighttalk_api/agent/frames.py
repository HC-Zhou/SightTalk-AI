"""Typed internal frames for worker-bus based agent orchestration."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any, Literal

FrameKind = Literal["system", "control", "data"]
InterruptReason = Literal["client_request", "local_vad_barge_in", "runtime"]


class FramePriority(IntEnum):
    """Priority ordering for queued internal frames; lower values dispatch first."""

    SYSTEM = 0
    CONTROL = 10
    DATA = 20


@dataclass(frozen=True)
class Frame:
    """One internal unit of agent work routed by the worker bus."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    kind: FrameKind = "data"
    priority: FramePriority = FramePriority.DATA
    source: str = "runtime"
    target: str | None = None
    interruptible: bool = True
    frame_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    @classmethod
    def system(
        cls,
        type: str,
        *,
        payload: dict[str, Any] | None = None,
        source: str = "runtime",
        target: str | None = None,
    ) -> Frame:
        """Create a non-interruptible system frame."""
        return cls(
            type=type,
            payload=payload or {},
            kind="system",
            priority=FramePriority.SYSTEM,
            source=source,
            target=target,
            interruptible=False,
        )

    @classmethod
    def control(
        cls,
        type: str,
        *,
        payload: dict[str, Any] | None = None,
        source: str = "runtime",
        target: str | None = None,
        interruptible: bool = True,
    ) -> Frame:
        """Create a control frame."""
        return cls(
            type=type,
            payload=payload or {},
            kind="control",
            priority=FramePriority.CONTROL,
            source=source,
            target=target,
            interruptible=interruptible,
        )

    @classmethod
    def data(
        cls,
        type: str,
        *,
        payload: dict[str, Any] | None = None,
        source: str = "runtime",
        target: str | None = None,
        interruptible: bool = True,
    ) -> Frame:
        """Create a data frame."""
        return cls(
            type=type,
            payload=payload or {},
            kind="data",
            priority=FramePriority.DATA,
            source=source,
            target=target,
            interruptible=interruptible,
        )


def interrupt_frame(
    *,
    source: str,
    reason: InterruptReason,
    payload: dict[str, Any] | None = None,
) -> Frame:
    """Create a non-interruptible internal frame for assistant interruption."""
    return Frame.control(
        "agent.interrupt",
        payload={"reason": reason, **(payload or {})},
        source=source,
        interruptible=False,
    )
