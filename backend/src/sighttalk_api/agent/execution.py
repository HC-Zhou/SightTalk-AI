"""LiveKit transport execution layer for realtime audio, video, and control events."""

from __future__ import annotations

import asyncio
import io
import json
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any, Protocol

from livekit import rtc
from PIL import Image

from sighttalk_api.agent.worker import AGENT_TOPIC, CONTROL_TOPIC
from sighttalk_api.providers.base import ImageFrame
from sighttalk_api.schemas.livekit import MediaPolicy


class AudioChunkHandler(Protocol):
    """Callback contract for normalized microphone PCM chunks."""

    def __call__(self, data: bytes, *, sample_rate: int) -> Awaitable[None]:
        raise NotImplementedError


ImageFrameHandler = Callable[[ImageFrame], Awaitable[None]]
ControlMessageHandler = Callable[[bytes], Awaitable[None]]
MediaPolicyGetter = Callable[[], MediaPolicy]
InputEnabledGetter = Callable[[], bool]


class LiveKitExecution:
    """Owns LiveKit room IO while delegating business decisions to callbacks.

    This class is intentionally transport-focused: it subscribes to user tracks,
    publishes assistant audio/data, and converts camera frames to provider-ready
    JPEG images. Agent state, cost accounting, and provider policy live above it.
    """

    def __init__(
        self,
        *,
        room_name: str,
        livekit_url: str,
        assistant_token: str,
        media_policy: MediaPolicyGetter,
        on_audio_chunk: AudioChunkHandler,
        on_image_frame: ImageFrameHandler,
        on_control_message: ControlMessageHandler,
        input_enabled: InputEnabledGetter | None = None,
    ) -> None:
        self.room_name = room_name
        self._livekit_url = livekit_url
        self._assistant_token = assistant_token
        self._media_policy = media_policy
        self._input_enabled = input_enabled or (lambda: True)
        self._on_audio_chunk = on_audio_chunk
        self._on_image_frame = on_image_frame
        self._on_control_message = on_control_message
        self._room = rtc.Room()
        self._tasks: set[asyncio.Task[None]] = set()
        self._last_video_sent_at = 0.0
        self._connected = False
        self._assistant_audio_source: rtc.AudioSource | None = None
        self._assistant_audio_track: rtc.LocalAudioTrack | None = None
        self._assistant_audio_publication: rtc.LocalTrackPublication | None = None
        self._stopping = False
        self._stopped = False

    async def connect(self) -> None:
        """Join the room as the assistant participant and bind LiveKit event hooks."""
        self._room.on("track_subscribed", self._handle_track_subscribed)
        self._room.on("data_received", self._handle_data_received)
        await self._room.connect(self._livekit_url, self._assistant_token)
        self._connected = True
        self._stopped = False

    async def stop(self) -> None:
        """Cancel media consumers and release LiveKit resources."""
        if self._stopped or self._stopping:
            return
        self._stopping = True
        for task in list(self._tasks):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await self._unpublish_assistant_audio_track()
        if self._assistant_audio_source is not None:
            with suppress(Exception):
                await self._assistant_audio_source.aclose()
            self._assistant_audio_source = None
        if self._connected:
            with suppress(Exception):
                await self._room.disconnect()
        self._connected = False
        self._stopping = False
        self._stopped = True

    async def publish_event(self, payload: dict[str, Any]) -> None:
        """Publish a normalized agent data event to frontend participants."""
        if not self._connected:
            return
        await self._room.local_participant.publish_data(
            json.dumps(payload),
            reliable=True,
            topic=AGENT_TOPIC,
        )

    async def publish_assistant_audio_track(self) -> None:
        """Expose the assistant's synthesized audio stream as a LiveKit track."""
        self._assistant_audio_source = rtc.AudioSource(24_000, 1)
        track = rtc.LocalAudioTrack.create_audio_track(
            "assistant-audio",
            self._assistant_audio_source,
        )
        self._assistant_audio_track = track
        self._assistant_audio_publication = await self._room.local_participant.publish_track(track)

    async def _unpublish_assistant_audio_track(self) -> None:
        publication = self._assistant_audio_publication
        self._assistant_audio_publication = None
        self._assistant_audio_track = None
        if publication is None or not self._connected:
            return
        with suppress(Exception):
            await self._room.local_participant.unpublish_track(publication.sid)

    async def play_assistant_audio(self, audio: bytes) -> None:
        """Write provider PCM audio into the published assistant audio source."""
        if self._assistant_audio_source is None:
            return
        bytes_per_sample = 2
        samples = len(audio) // bytes_per_sample
        if samples <= 0:
            return
        frame = rtc.AudioFrame(
            audio,
            sample_rate=24_000,
            num_channels=1,
            samples_per_channel=samples,
        )
        await self._assistant_audio_source.capture_frame(frame)

    async def interrupt_playback(self) -> None:
        """Drop queued assistant audio so user interruption feels immediate."""
        if self._assistant_audio_source is not None:
            self._assistant_audio_source.clear_queue()

    async def wait_for_assistant_playout(self) -> None:
        """Wait until queued assistant audio has finished playing."""
        if self._assistant_audio_source is not None:
            await self._assistant_audio_source.wait_for_playout()

    def _handle_track_subscribed(self, track: rtc.Track, *_args: Any) -> None:
        """Start the correct media consumer when the user publishes a track."""
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            self._track_task(asyncio.create_task(self._consume_audio(track)))
        if track.kind == rtc.TrackKind.KIND_VIDEO:
            self._track_task(asyncio.create_task(self._consume_video(track)))

    def _handle_data_received(self, packet: rtc.DataPacket) -> None:
        """Forward only SightTalk control messages into the agent lifecycle."""
        if packet.topic != CONTROL_TOPIC:
            return
        self._track_task(asyncio.create_task(self._handle_control_packet(packet.data)))

    def _track_task(self, task: asyncio.Task[None]) -> None:
        """Register background tasks so stop() can cancel them deterministically."""
        self._tasks.add(task)
        task.add_done_callback(lambda completed: self._tasks.discard(task))

    async def _handle_control_packet(self, data: bytes) -> None:
        await self._on_control_message(data)

    async def _consume_audio(self, track: rtc.Track) -> None:
        """Read microphone audio as 16 kHz mono PCM chunks."""
        audio_stream = rtc.AudioStream.from_track(
            track=track,
            sample_rate=16_000,
            num_channels=1,
            frame_size_ms=100,
        )
        try:
            async for event in audio_stream:
                if not self._input_enabled():
                    continue
                frame = event.frame
                await self._on_audio_chunk(
                    bytes(frame.data),
                    sample_rate=frame.sample_rate,
                )
        finally:
            await audio_stream.aclose()

    async def _consume_video(self, track: rtc.Track) -> None:
        """Sample camera frames according to the current media policy."""
        video_stream = rtc.VideoStream.from_track(track=track, capacity=1)
        try:
            async for event in video_stream:
                if not self._input_enabled():
                    continue
                now = asyncio.get_running_loop().time()
                media_policy = self._media_policy()
                min_interval = 1 / max(media_policy.max_video_fps, 0.1)
                if now - self._last_video_sent_at < min_interval:
                    continue
                frame = await asyncio.to_thread(
                    encode_video_frame,
                    event.frame,
                    max_edge=media_policy.max_jpeg_edge,
                    quality=media_policy.jpeg_quality,
                )
                if frame is None:
                    continue
                self._last_video_sent_at = now
                await self._on_image_frame(frame)
        finally:
            await video_stream.aclose()


def encode_video_frame(frame: rtc.VideoFrame, *, max_edge: int, quality: int) -> ImageFrame | None:
    """Convert a LiveKit video frame to a bounded JPEG image frame."""
    try:
        rgb = frame.convert(rtc.VideoBufferType.RGB24)
        image = Image.frombytes("RGB", (rgb.width, rgb.height), bytes(rgb.data))
        image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        output = encode_jpeg_under_limit(image, quality=quality)
        return ImageFrame(
            data=output,
            mime_type="image/jpeg",
            width=image.width,
            height=image.height,
        )
    except Exception:
        return None


def encode_jpeg_under_limit(image: Image.Image, *, quality: int, max_bytes: int = 190_000) -> bytes:
    """Encode JPEG output under a byte budget by lowering quality and size."""
    current = image.copy()
    current_quality = quality
    while True:
        output = io.BytesIO()
        current.save(output, format="JPEG", quality=current_quality, optimize=True)
        data = output.getvalue()
        if len(data) <= max_bytes or current_quality <= 45:
            return data
        current_quality -= 10
        if current_quality <= 55 and max(current.size) > 480:
            current.thumbnail((480, 480), Image.Resampling.LANCZOS)
