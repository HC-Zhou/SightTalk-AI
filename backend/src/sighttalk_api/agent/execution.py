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
    def __call__(self, data: bytes, *, sample_rate: int) -> Awaitable[None]:
        raise NotImplementedError


ImageFrameHandler = Callable[[ImageFrame], Awaitable[None]]
ControlMessageHandler = Callable[[bytes], Awaitable[None]]
MediaPolicyGetter = Callable[[], MediaPolicy]


class LiveKitExecution:
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
    ) -> None:
        self.room_name = room_name
        self._livekit_url = livekit_url
        self._assistant_token = assistant_token
        self._media_policy = media_policy
        self._on_audio_chunk = on_audio_chunk
        self._on_image_frame = on_image_frame
        self._on_control_message = on_control_message
        self._room = rtc.Room()
        self._tasks: set[asyncio.Task[None]] = set()
        self._last_video_sent_at = 0.0
        self._connected = False
        self._assistant_audio_source: rtc.AudioSource | None = None

    async def connect(self) -> None:
        self._room.on("track_subscribed", self._handle_track_subscribed)
        self._room.on("data_received", self._handle_data_received)
        await self._room.connect(self._livekit_url, self._assistant_token)
        self._connected = True

    async def stop(self) -> None:
        for task in list(self._tasks):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if self._assistant_audio_source is not None:
            await self._assistant_audio_source.aclose()
            self._assistant_audio_source = None
        await self._room.disconnect()
        self._connected = False

    async def publish_event(self, payload: dict[str, Any]) -> None:
        if not self._connected:
            return
        await self._room.local_participant.publish_data(
            json.dumps(payload),
            reliable=True,
            topic=AGENT_TOPIC,
        )

    async def publish_assistant_audio_track(self) -> None:
        self._assistant_audio_source = rtc.AudioSource(24_000, 1)
        track = rtc.LocalAudioTrack.create_audio_track(
            "assistant-audio",
            self._assistant_audio_source,
        )
        await self._room.local_participant.publish_track(track)

    async def play_assistant_audio(self, audio: bytes) -> None:
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
        if self._assistant_audio_source is not None:
            self._assistant_audio_source.clear_queue()

    def _handle_track_subscribed(self, track: rtc.Track, *_args: Any) -> None:
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            self._track_task(asyncio.create_task(self._consume_audio(track)))
        if track.kind == rtc.TrackKind.KIND_VIDEO:
            self._track_task(asyncio.create_task(self._consume_video(track)))

    def _handle_data_received(self, packet: rtc.DataPacket) -> None:
        if packet.topic != CONTROL_TOPIC:
            return
        self._track_task(asyncio.create_task(self._handle_control_packet(packet.data)))

    def _track_task(self, task: asyncio.Task[None]) -> None:
        self._tasks.add(task)
        task.add_done_callback(lambda completed: self._tasks.discard(task))

    async def _handle_control_packet(self, data: bytes) -> None:
        await self._on_control_message(data)

    async def _consume_audio(self, track: rtc.Track) -> None:
        audio_stream = rtc.AudioStream.from_track(
            track=track,
            sample_rate=16_000,
            num_channels=1,
            frame_size_ms=100,
        )
        try:
            async for event in audio_stream:
                frame = event.frame
                await self._on_audio_chunk(
                    bytes(frame.data),
                    sample_rate=frame.sample_rate,
                )
        finally:
            await audio_stream.aclose()

    async def _consume_video(self, track: rtc.Track) -> None:
        video_stream = rtc.VideoStream.from_track(track=track, capacity=1)
        try:
            async for event in video_stream:
                now = asyncio.get_running_loop().time()
                media_policy = self._media_policy()
                min_interval = 1 / max(media_policy.max_video_fps, 0.1)
                if now - self._last_video_sent_at < min_interval:
                    continue
                frame = encode_video_frame(
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
