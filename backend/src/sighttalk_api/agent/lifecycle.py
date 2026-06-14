"""Agent lifecycle orchestration across LiveKit execution and AI provider tooling."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from typing import Any, Literal

from sighttalk_api.agent.context import AgentSessionContext, utc_now
from sighttalk_api.agent.dialogue import DialogueStabilityCoordinator, ProviderEventStamp
from sighttalk_api.agent.execution import LiveKitExecution
from sighttalk_api.agent.frames import Frame, interrupt_frame
from sighttalk_api.agent.metrics import RealtimeMetrics
from sighttalk_api.agent.noise import (
    NoiseSuppressionConfig,
    NoiseSuppressionResult,
    NoiseSuppressor,
)
from sighttalk_api.agent.tooling import AgentTooling
from sighttalk_api.agent.vad import LocalVAD, LocalVADResult, pcm16_stats
from sighttalk_api.providers.base import ImageFrame, ProviderEvent

PCM16_BARGE_IN_RMS_THRESHOLD = 700.0
PCM16_BARGE_IN_PEAK_THRESHOLD = 1_600
CLIENT_INTERRUPT_CONTROL_MESSAGE = b'{"type":"client.interrupt"}'
TERMINAL_PROVIDER_EVENT_CODES = {
    "PROVIDER_CONFIGURATION_ERROR",
    "PROVIDER_GOAWAY",
    "PROVIDER_UNAVAILABLE",
}

logger = logging.getLogger(__name__)

LifecycleState = Literal[
    "created",
    "connecting",
    "listening",
    "speaking",
    "interrupted",
    "error",
    "ended",
]


class AgentLifecycle:
    """Coordinates one realtime assistant session from connect through shutdown.

    The lifecycle owns ordering and failure semantics: LiveKit must connect before
    provider traffic is accepted, provider errors are emitted at most once, and
    all background tasks are cancelled before session resources are released.
    """

    def __init__(
        self,
        *,
        context: AgentSessionContext,
        tooling: AgentTooling,
        execution: LiveKitExecution | None = None,
        noise_suppression_enabled: bool = True,
    ) -> None:
        self.context = context
        self.tooling = tooling
        self.execution = execution
        self.state: LifecycleState = "created"
        self._stopped = asyncio.Event()
        self._tasks: set[asyncio.Task[None]] = set()
        self._provider_ready = asyncio.Event()
        self._provider_audio_started = asyncio.Event()
        self._input_enabled = asyncio.Event()
        self._terminal_error_sent = False
        self._stopping = False
        self._assistant_playback_active = False
        self._playback_completion_task: asyncio.Task[None] | None = None
        self._vad = LocalVAD()
        self._metrics = RealtimeMetrics()
        self._dialogue = DialogueStabilityCoordinator()
        self._noise_suppressor = NoiseSuppressor(
            NoiseSuppressionConfig(enabled=noise_suppression_enabled)
        )
        self._noise_trace_sent = False

    def set_execution(self, execution: LiveKitExecution) -> None:
        """Attach the transport layer after dependency construction."""
        self.execution = execution

    @property
    def input_enabled(self) -> bool:
        """Return whether user audio/video should currently feed the provider."""
        return self._input_enabled.is_set()

    async def run(self) -> None:
        """Run the assistant session until stopped, cancelled, or terminal error."""
        if self.execution is None:
            raise RuntimeError("Agent lifecycle requires an execution harness")
        try:
            self.state = "connecting"
            await self.execution.connect()
            await self.publish_event(self.context.status_event("connecting"))
            await self.execution.publish_assistant_audio_track()
            try:
                await self.tooling.connect()
            except RuntimeError as exc:
                await self._handle_terminal_error("PROVIDER_UNAVAILABLE", str(exc))
                return
            self._provider_ready.set()
            self._input_enabled.set()
            self.state = "listening"
            await self.publish_event(self.context.status_event("listening"))
            provider_task = asyncio.create_task(self._pump_provider_events())
            self._track_task(provider_task)
            await self._stopped.wait()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._handle_terminal_error("AGENT_RUNTIME_ERROR", str(exc))
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop provider, transport, memory flush, and child tasks idempotently."""
        if self._stopping:
            return
        self._stopping = True
        self._stopped.set()
        self._input_enabled.clear()
        for task in list(self._tasks):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self.tooling.schedule_memory_flush()
        await self.tooling.close()
        if self.execution is not None:
            await self.execution.stop()
        if self.state != "error":
            self.state = "ended"

    async def handle_audio_chunk(self, data: bytes, *, sample_rate: int) -> None:
        """Forward microphone audio only after the provider is ready."""
        await self._provider_ready.wait()
        noise_result = self._noise_suppressor.process(data)
        if noise_result.applied:
            await self._publish_noise_trace(noise_result)
        audio_data = noise_result.data
        vad_result = self._vad.process(audio_data, enabled=self.context.media_policy.vad_enabled)
        if vad_result.event == "speech_started":
            await self._publish_vad_trace(vad_result)
        if not self._input_enabled.is_set():
            if not (self._assistant_playback_active and vad_result.speech_detected):
                return
            await self._handle_interrupt_frame(
                interrupt_frame(
                    source="local_vad",
                    reason="local_vad_barge_in",
                    payload={
                        "rms": round(vad_result.rms, 2),
                        "peak": vad_result.peak,
                    },
                )
            )
        try:
            await self.tooling.send_audio(audio_data, sample_rate=sample_rate)
            self._provider_audio_started.set()
        except RuntimeError as exc:
            await self._handle_terminal_error("PROVIDER_UNAVAILABLE", str(exc))

    async def handle_image_frame(self, frame: ImageFrame) -> None:
        """Forward camera frames after audio starts to avoid vision-only idle cost."""
        await self._provider_ready.wait()
        if not self._input_enabled.is_set():
            return
        await self._provider_audio_started.wait()
        if not self._input_enabled.is_set():
            return
        try:
            if await self.tooling.send_image(frame):
                await self.publish_event(self.context.cost_event())
        except RuntimeError as exc:
            await self._handle_terminal_error("PROVIDER_UNAVAILABLE", str(exc))

    async def handle_control_message(self, data: bytes) -> None:
        """Apply local control effects before forwarding control to the provider."""
        if is_interrupt_message(data):
            await self._handle_interrupt_frame(
                interrupt_frame(source="client", reason="client_request")
            )
            return
        try:
            event = await self.tooling.handle_control_message(data)
        except RuntimeError as exc:
            await self._handle_terminal_error("PROVIDER_UNAVAILABLE", str(exc))
            return
        if event is not None:
            if event.get("type") == "agent.status":
                status = str(event.get("status", "listening"))
                self.state = "listening" if status == "listening" else self.state
            await self.publish_event(event)

    async def publish_event(self, payload: dict[str, Any]) -> None:
        """Publish a normalized event if a transport layer is attached."""
        if self.execution is not None:
            await self.execution.publish_event(payload)

    async def handle_interrupt_frame(self, frame: Frame) -> None:
        """Handle one internal interruption frame from any source."""
        await self._handle_interrupt_frame(frame)

    async def _pump_provider_events(self) -> None:
        """Continuously bridge provider events to LiveKit frontend events."""
        try:
            async for event in self.tooling.events():
                stamp = self._dialogue.stamp_provider_event(event)
                if self._is_stale_assistant_event(event, stamp):
                    await self._publish_stale_event_diagnostic(event, stamp)
                    continue
                if (
                    event.type in {"transcript_delta", "transcript_done"}
                    and event.speaker == "user"
                ):
                    await self._mark_user_turn_started(source="provider_transcript")
                if self.execution is not None and event.type == "audio_delta" and event.audio:
                    if not await self._begin_assistant_playback(stamp):
                        continue
                    await self.execution.play_assistant_audio(event.audio)
                if event.type == "response_done" and self._assistant_playback_active:
                    self.tooling.schedule_memory_flush()
                    self._schedule_playback_completion(event.message_id, stamp.response_epoch)
                    continue
                if (
                    event.type == "status"
                    and event.status == "listening"
                    and self._assistant_playback_active
                ):
                    continue
                if event.type == "error":
                    await self._handle_provider_error_event(event, stamp)
                    continue
                payload = await self.tooling.handle_provider_event(event)
                if payload is not None:
                    self._stamp_payload(payload, stamp)
                    await self.publish_event(payload)
        except asyncio.CancelledError:
            raise
        except RuntimeError as exc:
            await self._handle_terminal_error("PROVIDER_UNAVAILABLE", str(exc))

    async def _handle_terminal_error(self, code: str, message: str) -> None:
        """Publish one terminal error and move the lifecycle toward shutdown."""
        self.state = "error"
        if not self._terminal_error_sent:
            self._terminal_error_sent = True
            await self._publish_metrics_trace(
                "provider.error",
                {
                    **self._metrics.mark_provider_error(code=code),
                    "severity": "terminal",
                    "response_epoch": self._dialogue.response_epoch,
                },
            )
            logger.error(
                "Terminal realtime agent error",
                extra={
                    "session_id": self.context.session_id,
                    "code": code,
                    "response_epoch": self._dialogue.response_epoch,
                },
            )
            await self.publish_event(
                self.context.diagnostic_event(
                    code,
                    message,
                    severity="terminal",
                    surface="session",
                    response_epoch=self._dialogue.response_epoch,
                )
            )
            await self.publish_event(
                self.context.terminal_event(
                    code,
                    message,
                    response_epoch=self._dialogue.response_epoch,
                )
            )
        self._stopped.set()

    async def _begin_assistant_playback(self, stamp: ProviderEventStamp) -> bool:
        """Pause user input while assistant audio is being played."""
        if not self._dialogue.begin_playback(stamp.response_epoch):
            await self._publish_stale_event_diagnostic(
                ProviderEvent(
                    type="audio_delta",
                    message_id=stamp.response_id,
                ),
                stamp,
            )
            return False
        if self._assistant_playback_active:
            return True
        self._assistant_playback_active = True
        self._input_enabled.clear()
        self._provider_audio_started.clear()
        self.state = "speaking"
        await self.publish_event(self.context.status_event("speaking"))
        await self._publish_metrics_trace(
            "assistant.first_audio",
            {
                **self._metrics.mark_assistant_response_started(),
                "response_epoch": stamp.response_epoch,
                "response_id": stamp.response_id,
            },
        )
        return True

    def _schedule_playback_completion(self, message_id: str, response_epoch: int) -> None:
        """Restore user input after LiveKit has played queued assistant audio."""
        if self._playback_completion_task is not None and not self._playback_completion_task.done():
            return
        task = asyncio.create_task(
            self._complete_playback_after_playout(message_id, response_epoch)
        )
        self._playback_completion_task = task
        self._track_task(task)
        task.add_done_callback(self._clear_playback_completion_task)

    async def _complete_playback_after_playout(
        self,
        message_id: str,
        response_epoch: int,
    ) -> None:
        if self.execution is not None:
            await self.execution.wait_for_assistant_playout()
        if not self._dialogue.complete_playback(response_epoch):
            await self._publish_stale_completion_diagnostic(message_id, response_epoch)
            return
        if not self._assistant_playback_active:
            return
        self._assistant_playback_active = False
        self._input_enabled.set()
        if self.state not in {"error", "ended"}:
            self.state = "listening"
            await self._publish_metrics_trace(
                "turn.complete",
                {
                    **self._metrics.mark_turn_completed(),
                    "response_epoch": response_epoch,
                    "response_id": message_id,
                },
            )
            await self.publish_event(self._response_done_event(message_id, response_epoch))
            await self.publish_event(self.context.status_event("listening"))

    async def _cancel_assistant_playback(self) -> None:
        """Cancel pending playback completion and immediately re-enable input."""
        self._assistant_playback_active = False
        self._input_enabled.set()
        task = self._playback_completion_task
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _interrupt_assistant_playback(self) -> None:
        """Stop assistant playback and return to listening for user speech."""
        was_active = self._assistant_playback_active
        interrupt_result = self._dialogue.interrupt(playback_active=was_active)
        await self._cancel_assistant_playback()
        if was_active and self.execution is not None:
            await self.execution.interrupt_playback()
        self._input_enabled.set()
        self.state = "interrupted"
        await self._publish_metrics_trace(
            "interrupt.epoch",
            {
                "previous_response_epoch": interrupt_result.previous_epoch,
                "response_epoch": interrupt_result.response_epoch,
                "epoch_advanced": interrupt_result.advanced,
                "stale_events_dropped": self._dialogue.stale_events_dropped,
            },
        )

    async def _handle_interrupt_frame(self, frame: Frame) -> None:
        """Apply local interruption effects and notify the provider once."""
        reason = str(frame.payload.get("reason", "runtime"))
        was_active = self._assistant_playback_active
        await self._publish_metrics_trace(
            "interrupt",
            {
                **self._metrics.mark_interrupt(source=frame.source, reason=reason),
                "response_epoch": self._dialogue.response_epoch,
                "playback_active": was_active,
            },
        )
        await self._interrupt_assistant_playback()
        if not was_active:
            self.state = "listening"
            await self.publish_event(self.context.status_event("listening"))
            return
        try:
            event = await self.tooling.handle_control_message(CLIENT_INTERRUPT_CONTROL_MESSAGE)
        except RuntimeError as exc:
            await self._publish_diagnostic_error(
                "PROVIDER_CANCEL_FAILED",
                str(exc),
                response_epoch=self._dialogue.response_epoch,
                fields={"reason": reason, "source": frame.source},
            )
            self.state = "listening"
            await self.publish_event(self.context.status_event("listening"))
            return
        if event is None:
            self.state = "listening"
            await self.publish_event(self.context.status_event("listening"))
            return
        if event.get("type") == "agent.status":
            status = str(event.get("status", "listening"))
            self.state = "listening" if status == "listening" else self.state
        await self.publish_event(event)

    async def _mark_user_turn_started(self, *, source: str, force_new: bool = False) -> None:
        fields = self._metrics.mark_user_turn_started(source=source, force_new=force_new)
        if fields is not None:
            await self._publish_metrics_trace("turn.start", fields)

    async def _publish_vad_trace(self, result: LocalVADResult) -> None:
        await self._mark_user_turn_started(
            source="local_vad",
            force_new=self._assistant_playback_active,
        )
        await self._publish_metrics_trace(
            "vad.speech_started",
            {
                "rms": round(result.rms, 2),
                "peak": result.peak,
                "noise_rms": round(result.noise_rms, 2),
                "threshold": round(result.threshold, 2),
            },
        )

    async def _publish_noise_trace(self, result: NoiseSuppressionResult) -> None:
        if self._noise_trace_sent:
            return
        self._noise_trace_sent = True
        await self._publish_metrics_trace(
            "audio.noise_suppressed",
            {
                "raw_rms": round(result.raw.rms, 2),
                "cleaned_rms": round(result.cleaned.rms, 2),
                "noise_rms": round(result.noise_rms, 2),
                "threshold": round(result.threshold, 2),
            },
        )

    async def _publish_metrics_trace(self, name: str, fields: dict[str, Any]) -> None:
        await self.publish_event(self.context.metrics_event(name, fields))

    def _clear_playback_completion_task(self, task: asyncio.Task[None]) -> None:
        if self._playback_completion_task is task:
            self._playback_completion_task = None

    async def _handle_provider_error_event(
        self,
        event: ProviderEvent,
        stamp: ProviderEventStamp,
    ) -> None:
        code = event.code or "PROVIDER_PROTOCOL_ERROR"
        if code in TERMINAL_PROVIDER_EVENT_CODES:
            await self._handle_terminal_error(code, event.message or "Provider error")
            return
        await self._publish_metrics_trace(
            "provider.error",
            {
                **self._metrics.mark_provider_error(code=code),
                "severity": "recoverable",
                "response_epoch": stamp.response_epoch,
                "response_id": stamp.response_id,
            },
        )
        await self._publish_diagnostic_error(
            code,
            event.message or "Provider error",
            response_epoch=stamp.response_epoch,
            fields={"response_id": stamp.response_id},
        )

    def _is_stale_assistant_event(
        self,
        event: ProviderEvent,
        stamp: ProviderEventStamp,
    ) -> bool:
        if not stamp.stale:
            return False
        return event.type in {"audio_delta", "response_done"} or (
            event.type in {"transcript_delta", "transcript_done"}
            and event.speaker == "assistant"
        )

    async def _publish_stale_event_diagnostic(
        self,
        event: ProviderEvent,
        stamp: ProviderEventStamp,
    ) -> None:
        dropped = self._dialogue.mark_stale_event_dropped()
        await self._publish_metrics_trace(
            "provider.stale_event_dropped",
            {
                "provider_event_type": event.type,
                "response_epoch": stamp.response_epoch,
                "active_response_epoch": self._dialogue.response_epoch,
                "response_id": stamp.response_id,
                "stale_events_dropped": dropped,
            },
        )
        await self._publish_diagnostic_error(
            "STALE_PROVIDER_EVENT_DROPPED",
            "Dropped stale provider event from an interrupted response",
            response_epoch=stamp.response_epoch,
            fields={
                "provider_event_type": event.type,
                "active_response_epoch": self._dialogue.response_epoch,
                "response_id": stamp.response_id,
                "stale_events_dropped": dropped,
            },
        )

    async def _publish_stale_completion_diagnostic(
        self,
        message_id: str,
        response_epoch: int,
    ) -> None:
        await self._publish_diagnostic_error(
            "STALE_RESPONSE_COMPLETION_DROPPED",
            "Dropped stale response completion from an interrupted response",
            response_epoch=response_epoch,
            fields={
                "active_response_epoch": self._dialogue.response_epoch,
                "response_id": message_id,
                "stale_events_dropped": self._dialogue.stale_events_dropped,
            },
        )

    async def _publish_diagnostic_error(
        self,
        code: str,
        message: str,
        *,
        response_epoch: int | None = None,
        fields: dict[str, Any] | None = None,
    ) -> None:
        logger.warning(
            "Recoverable realtime diagnostic",
            extra={
                "session_id": self.context.session_id,
                "code": code,
                "response_epoch": response_epoch,
            },
        )
        await self.publish_event(
            self.context.diagnostic_event(
                code,
                message,
                severity="recoverable",
                surface="diagnostic",
                response_epoch=response_epoch,
                fields=fields,
            )
        )

    def _stamp_payload(
        self,
        payload: dict[str, Any],
        stamp: ProviderEventStamp,
    ) -> None:
        if payload.get("type") in {
            "audio.delta",
            "transcript.delta",
            "transcript.done",
            "response.done",
        }:
            payload["response_epoch"] = stamp.response_epoch
            if stamp.response_id:
                payload["response_id"] = stamp.response_id

    def _response_done_event(self, message_id: str, response_epoch: int) -> dict[str, Any]:
        return {
            "type": "response.done",
            "session_id": self.context.session_id,
            "timestamp": utc_now(),
            "message_id": message_id,
            "response_id": message_id,
            "response_epoch": response_epoch,
            "audio_playback_complete": True,
        }

    def _track_task(self, task: asyncio.Task[None]) -> None:
        """Track lifecycle-owned background tasks for cooperative cancellation."""
        self._tasks.add(task)
        task.add_done_callback(lambda completed: self._tasks.discard(task))


def is_interrupt_message(data: bytes) -> bool:
    """Return whether a control packet is the frontend interrupt command."""
    try:
        payload = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return str(payload.get("type", "")) == "client.interrupt"


def is_probable_user_speech(data: bytes) -> bool:
    """Return whether a 16-bit PCM chunk is loud enough to barge in."""
    stats = pcm16_stats(data)
    return (
        stats.rms >= PCM16_BARGE_IN_RMS_THRESHOLD
        and stats.peak >= PCM16_BARGE_IN_PEAK_THRESHOLD
    )
