from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

from PIL import Image

from sighttalk_api.agent.context import AgentSessionContext
from sighttalk_api.agent.lifecycle import AgentLifecycle
from sighttalk_api.agent.livekit_runtime import encode_jpeg_under_limit
from sighttalk_api.agent.vad import pcm16_stats
from sighttalk_api.providers.base import ImageFrame, ProviderEvent
from sighttalk_api.schemas.livekit import MediaPolicy


def make_context() -> AgentSessionContext:
    return AgentSessionContext(
        session_id="room-1",
        user_id="user-1",
        media_policy=MediaPolicy(
            mode="balanced",
            max_video_fps=1.0,
            max_jpeg_edge=1024,
            jpeg_quality=75,
            vad_enabled=True,
        ),
    )


def pcm16_chunk(sample: int, *, count: int = 1_600) -> bytes:
    return b"".join(sample.to_bytes(2, "little", signed=True) for _ in range(count))


async def wait_for(predicate: Callable[[], bool], *, attempts: int = 20) -> None:
    for _ in range(attempts):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition was not met")


def test_encode_jpeg_under_limit_compresses_large_frame() -> None:
    image = Image.new("RGB", (1280, 720), color=(82, 120, 180))

    data = encode_jpeg_under_limit(image, quality=90, max_bytes=20_000)

    assert len(data) <= 20_000
    assert data.startswith(b"\xff\xd8")


async def test_lifecycle_waits_for_provider_ready_before_audio() -> None:
    context = make_context()
    tooling = FakeTooling()
    lifecycle = AgentLifecycle(context=context, tooling=tooling)  # type: ignore[arg-type]
    task = asyncio.create_task(lifecycle.handle_audio_chunk(b"audio", sample_rate=16_000))

    await asyncio.sleep(0)
    assert tooling.audio_chunks == []

    lifecycle._provider_ready.set()  # noqa: SLF001
    lifecycle._input_enabled.set()  # noqa: SLF001
    await task

    assert tooling.audio_chunks == [b"audio"]
    assert lifecycle._provider_audio_started.is_set()  # noqa: SLF001


async def test_lifecycle_waits_for_first_provider_audio_before_image() -> None:
    context = make_context()
    tooling = FakeTooling(context)
    lifecycle = AgentLifecycle(context=context, tooling=tooling)  # type: ignore[arg-type]
    lifecycle._provider_ready.set()  # noqa: SLF001
    lifecycle._input_enabled.set()  # noqa: SLF001
    frame = ImageFrame(
        data=b"image",
        mime_type="image/jpeg",
        width=10,
        height=10,
    )
    task = asyncio.create_task(lifecycle.handle_image_frame(frame))

    await asyncio.sleep(0)
    assert tooling.image_frames == []

    lifecycle._provider_audio_started.set()  # noqa: SLF001
    await task

    assert tooling.image_frames == [frame]
    assert context.image_frames_sent == 1


async def test_lifecycle_publishes_single_terminal_error() -> None:
    context = make_context()
    tooling = FakeTooling()
    execution = FakeExecution()
    lifecycle = AgentLifecycle(
        context=context,
        tooling=tooling,  # type: ignore[arg-type]
        execution=execution,  # type: ignore[arg-type]
    )

    await lifecycle._handle_terminal_error("PROVIDER_UNAVAILABLE", "first")  # noqa: SLF001
    await lifecycle._handle_terminal_error("PROVIDER_UNAVAILABLE", "second")  # noqa: SLF001

    terminals = [event for event in execution.events if event["type"] == "session.terminal"]
    diagnostics = [event for event in execution.events if event["type"] == "diagnostic.error"]
    assert len(terminals) == 1
    assert terminals[0]["message"] == "first"
    assert len(diagnostics) == 1
    assert diagnostics[0]["severity"] == "terminal"


async def test_lifecycle_skips_silent_audio_and_images_until_playout_finishes() -> None:
    context = make_context()
    tooling = PlaybackTooling(
        [
            ProviderEvent(
                type="audio_delta",
                audio=b"\0\0",
                message_id="assistant-1",
            ),
            ProviderEvent(type="response_done", message_id="assistant-1"),
        ]
    )
    execution = PlaybackExecution()
    lifecycle = AgentLifecycle(
        context=context,
        tooling=tooling,  # type: ignore[arg-type]
        execution=execution,  # type: ignore[arg-type]
    )
    lifecycle._provider_ready.set()  # noqa: SLF001
    lifecycle._input_enabled.set()  # noqa: SLF001

    await lifecycle._pump_provider_events()  # noqa: SLF001
    await asyncio.sleep(0)
    await lifecycle.handle_audio_chunk(pcm16_chunk(0), sample_rate=16_000)
    await lifecycle.handle_image_frame(
        ImageFrame(data=b"dropped-image", mime_type="image/jpeg", width=10, height=10)
    )

    assert execution.played_audio == [b"\0\0"]
    assert tooling.audio_chunks == []
    assert tooling.image_frames == []
    assert [event["status"] for event in execution.events if event["type"] == "agent.status"] == [
        "speaking"
    ]

    execution.playout_done.set()
    assert lifecycle._playback_completion_task is not None  # noqa: SLF001
    await lifecycle._playback_completion_task  # noqa: SLF001
    accepted = pcm16_chunk(1_000)
    await lifecycle.handle_audio_chunk(accepted, sample_rate=16_000)

    assert tooling.audio_chunks == [accepted]
    assert execution.events[-2]["type"] == "response.done"
    assert execution.events[-2]["audio_playback_complete"] is True
    assert execution.events[-1]["status"] == "listening"


async def test_lifecycle_voice_barge_in_interrupts_assistant_playback() -> None:
    context = make_context()
    tooling = PlaybackTooling(
        [
            ProviderEvent(
                type="audio_delta",
                audio=b"\0\0",
                message_id="assistant-1",
            ),
        ]
    )
    execution = PlaybackExecution()
    lifecycle = AgentLifecycle(
        context=context,
        tooling=tooling,  # type: ignore[arg-type]
        execution=execution,  # type: ignore[arg-type]
    )
    lifecycle._provider_ready.set()  # noqa: SLF001
    lifecycle._input_enabled.set()  # noqa: SLF001
    speech = pcm16_chunk(3_000)

    await lifecycle._pump_provider_events()  # noqa: SLF001
    await lifecycle.handle_audio_chunk(speech, sample_rate=16_000)

    assert execution.interrupted
    assert tooling.control_messages == [b'{"type":"client.interrupt"}']
    assert tooling.audio_chunks == [speech]
    statuses = [event["status"] for event in execution.events if event["type"] == "agent.status"]
    assert statuses == ["speaking", "listening"]
    trace_names = [event["name"] for event in execution.events if event["type"] == "metrics.trace"]
    assert "vad.speech_started" in trace_names
    assert "interrupt" in trace_names


async def test_lifecycle_interrupt_reenables_input_during_assistant_playback() -> None:
    context = make_context()
    tooling = PlaybackTooling(
        [
            ProviderEvent(
                type="audio_delta",
                audio=b"\0\0",
                message_id="assistant-1",
            ),
        ]
    )
    execution = PlaybackExecution()
    lifecycle = AgentLifecycle(
        context=context,
        tooling=tooling,  # type: ignore[arg-type]
        execution=execution,  # type: ignore[arg-type]
    )
    lifecycle._provider_ready.set()  # noqa: SLF001
    lifecycle._input_enabled.set()  # noqa: SLF001

    await lifecycle._pump_provider_events()  # noqa: SLF001
    await lifecycle.handle_control_message(b'{"type":"client.interrupt"}')
    accepted = pcm16_chunk(1_000)
    await lifecycle.handle_audio_chunk(accepted, sample_rate=16_000)

    assert execution.interrupted
    assert tooling.control_messages == [b'{"type":"client.interrupt"}']
    assert tooling.audio_chunks == [accepted]
    assert execution.events[-1]["status"] == "listening"


async def test_lifecycle_repeated_interrupts_cancel_playback_once() -> None:
    context = make_context()
    tooling = PlaybackTooling(
        [
            ProviderEvent(
                type="audio_delta",
                audio=b"\0\0",
                message_id="assistant-1",
            ),
        ]
    )
    execution = PlaybackExecution()
    lifecycle = AgentLifecycle(
        context=context,
        tooling=tooling,  # type: ignore[arg-type]
        execution=execution,  # type: ignore[arg-type]
    )
    lifecycle._provider_ready.set()  # noqa: SLF001
    lifecycle._input_enabled.set()  # noqa: SLF001

    await lifecycle._pump_provider_events()  # noqa: SLF001
    await lifecycle.handle_control_message(b'{"type":"client.interrupt"}')
    await lifecycle.handle_control_message(b'{"type":"client.interrupt"}')

    assert execution.interrupt_count == 1
    assert tooling.control_messages == [b'{"type":"client.interrupt"}']
    statuses = [event["status"] for event in execution.events if event["type"] == "agent.status"]
    assert statuses == ["speaking", "listening", "listening"]


async def test_lifecycle_drops_stale_audio_and_completion_after_interrupt() -> None:
    context = make_context()
    tooling = QueuedPlaybackTooling()
    execution = PlaybackExecution()
    lifecycle = AgentLifecycle(
        context=context,
        tooling=tooling,  # type: ignore[arg-type]
        execution=execution,  # type: ignore[arg-type]
    )
    lifecycle._provider_ready.set()  # noqa: SLF001
    lifecycle._input_enabled.set()  # noqa: SLF001
    pump_task = asyncio.create_task(lifecycle._pump_provider_events())  # noqa: SLF001

    await tooling.emit(
        ProviderEvent(type="audio_delta", audio=b"old-audio", message_id="assistant-1")
    )
    await wait_for(lambda: execution.played_audio == [b"old-audio"])
    await lifecycle.handle_control_message(b'{"type":"client.interrupt"}')
    await tooling.emit(
        ProviderEvent(type="audio_delta", audio=b"late-audio", message_id="assistant-1")
    )
    await tooling.emit(ProviderEvent(type="response_done", message_id="assistant-1"))
    await tooling.close_stream()
    await pump_task

    assert execution.played_audio == [b"old-audio"]
    diagnostics = [event for event in execution.events if event["type"] == "diagnostic.error"]
    assert {event["code"] for event in diagnostics} >= {"STALE_PROVIDER_EVENT_DROPPED"}


async def test_lifecycle_recoverable_provider_error_is_diagnostic_only() -> None:
    context = make_context()
    tooling = PlaybackTooling(
        [
            ProviderEvent(
                type="error",
                code="PROVIDER_PROTOCOL_ERROR",
                message="cancel raced with provider",
            )
        ]
    )
    execution = PlaybackExecution()
    lifecycle = AgentLifecycle(
        context=context,
        tooling=tooling,  # type: ignore[arg-type]
        execution=execution,  # type: ignore[arg-type]
    )
    lifecycle._provider_ready.set()  # noqa: SLF001
    lifecycle._input_enabled.set()  # noqa: SLF001

    await lifecycle._pump_provider_events()  # noqa: SLF001

    assert lifecycle.state == "created"
    assert not [event for event in execution.events if event["type"] == "session.terminal"]
    diagnostics = [event for event in execution.events if event["type"] == "diagnostic.error"]
    assert len(diagnostics) == 1
    assert diagnostics[0]["severity"] == "recoverable"


async def test_lifecycle_provider_cancel_failure_is_diagnostic_only() -> None:
    context = make_context()
    tooling = FailingInterruptTooling(
        [
            ProviderEvent(
                type="audio_delta",
                audio=b"\0\0",
                message_id="assistant-1",
            ),
        ]
    )
    execution = PlaybackExecution()
    lifecycle = AgentLifecycle(
        context=context,
        tooling=tooling,  # type: ignore[arg-type]
        execution=execution,  # type: ignore[arg-type]
    )
    lifecycle._provider_ready.set()  # noqa: SLF001
    lifecycle._input_enabled.set()  # noqa: SLF001

    await lifecycle._pump_provider_events()  # noqa: SLF001
    await lifecycle.handle_control_message(b'{"type":"client.interrupt"}')

    assert lifecycle.state == "listening"
    assert not [event for event in execution.events if event["type"] == "session.terminal"]
    diagnostics = [event for event in execution.events if event["type"] == "diagnostic.error"]
    assert diagnostics[-1]["code"] == "PROVIDER_CANCEL_FAILED"


async def test_lifecycle_suppresses_noise_before_provider_audio() -> None:
    context = make_context()
    tooling = FakeTooling()
    lifecycle = AgentLifecycle(context=context, tooling=tooling)  # type: ignore[arg-type]
    lifecycle._provider_ready.set()  # noqa: SLF001
    lifecycle._input_enabled.set()  # noqa: SLF001
    noise = pcm16_chunk(160)

    await lifecycle.handle_audio_chunk(noise, sample_rate=16_000)

    assert len(tooling.audio_chunks) == 1
    assert pcm16_stats(tooling.audio_chunks[0]).rms < pcm16_stats(noise).rms


async def test_lifecycle_can_disable_noise_suppression() -> None:
    context = make_context()
    tooling = FakeTooling()
    lifecycle = AgentLifecycle(  # type: ignore[arg-type]
        context=context,
        tooling=tooling,
        noise_suppression_enabled=False,
    )
    lifecycle._provider_ready.set()  # noqa: SLF001
    lifecycle._input_enabled.set()  # noqa: SLF001
    noise = pcm16_chunk(160)

    await lifecycle.handle_audio_chunk(noise, sample_rate=16_000)

    assert tooling.audio_chunks == [noise]


async def test_lifecycle_publishes_turn_completion_metrics_before_final_status() -> None:
    context = make_context()
    tooling = PlaybackTooling(
        [
            ProviderEvent(
                type="transcript_done",
                speaker="user",
                text="hello",
                message_id="user-1",
            ),
            ProviderEvent(
                type="audio_delta",
                audio=b"\0\0",
                message_id="assistant-1",
            ),
            ProviderEvent(type="response_done", message_id="assistant-1"),
        ]
    )
    execution = PlaybackExecution()
    lifecycle = AgentLifecycle(
        context=context,
        tooling=tooling,  # type: ignore[arg-type]
        execution=execution,  # type: ignore[arg-type]
    )
    lifecycle._provider_ready.set()  # noqa: SLF001
    lifecycle._input_enabled.set()  # noqa: SLF001

    await lifecycle._pump_provider_events()  # noqa: SLF001
    execution.playout_done.set()
    assert lifecycle._playback_completion_task is not None  # noqa: SLF001
    await lifecycle._playback_completion_task  # noqa: SLF001

    trace_names = [event["name"] for event in execution.events if event["type"] == "metrics.trace"]
    assert trace_names[:2] == ["turn.start", "assistant.first_audio"]
    assert "turn.complete" in trace_names
    assert execution.events[-2]["type"] == "response.done"
    assert execution.events[-1]["status"] == "listening"


class FakeTooling:
    def __init__(self, context: AgentSessionContext | None = None) -> None:
        self.context = context
        self.audio_chunks: list[bytes] = []
        self.image_frames: list[ImageFrame] = []

    async def send_audio(self, data: bytes, *, sample_rate: int) -> None:
        self.audio_chunks.append(data)

    async def send_image(self, frame: ImageFrame) -> bool:
        self.image_frames.append(frame)
        if self.context is not None:
            self.context.add_image_frame()
        return True

    async def close(self) -> None:
        return None

    def schedule_memory_flush(self) -> None:
        return None

    def events(self) -> Any:
        raise AssertionError("events should not be called")


class FakeExecution:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def publish_event(self, payload: dict[str, Any]) -> None:
        self.events.append(payload)

    async def stop(self) -> None:
        return None


class PlaybackTooling(FakeTooling):
    def __init__(self, events: list[ProviderEvent]) -> None:
        super().__init__()
        self._events = events
        self.control_messages: list[bytes] = []

    async def handle_control_message(self, data: bytes) -> dict[str, Any] | None:
        self.control_messages.append(data)
        return self.context_event("listening")

    async def handle_provider_event(self, event: ProviderEvent) -> dict[str, Any] | None:
        if event.type == "audio_delta":
            return {
                "type": "audio.delta",
                "session_id": "room-1",
                "timestamp": "now",
                "message_id": event.message_id,
                "mime_type": event.mime_type,
                "audio": "",
            }
        if event.type == "response_done":
            return {
                "type": "response.done",
                "session_id": "room-1",
                "timestamp": "now",
                "message_id": event.message_id,
                "audio_playback_complete": False,
            }
        return None

    def context_event(self, status: str) -> dict[str, Any]:
        return {
            "type": "agent.status",
            "session_id": "room-1",
            "timestamp": "now",
            "status": status,
        }

    async def events(self) -> AsyncIterator[ProviderEvent]:
        for event in self._events:
            yield event


class QueuedPlaybackTooling(PlaybackTooling):
    def __init__(self) -> None:
        super().__init__([])
        self._queue: asyncio.Queue[ProviderEvent | None] = asyncio.Queue()

    async def emit(self, event: ProviderEvent) -> None:
        await self._queue.put(event)

    async def close_stream(self) -> None:
        await self._queue.put(None)

    async def events(self) -> AsyncIterator[ProviderEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                return
            yield event


class FailingInterruptTooling(PlaybackTooling):
    async def handle_control_message(self, data: bytes) -> dict[str, Any] | None:
        self.control_messages.append(data)
        raise RuntimeError("provider cancel failed")


class PlaybackExecution(FakeExecution):
    def __init__(self) -> None:
        super().__init__()
        self.played_audio: list[bytes] = []
        self.playout_done = asyncio.Event()
        self.interrupted = False
        self.interrupt_count = 0

    async def play_assistant_audio(self, audio: bytes) -> None:
        self.played_audio.append(audio)

    async def wait_for_assistant_playout(self) -> None:
        await self.playout_done.wait()

    async def interrupt_playback(self) -> None:
        self.interrupted = True
        self.interrupt_count += 1
