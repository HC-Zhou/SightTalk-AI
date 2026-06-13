from __future__ import annotations

import asyncio
import io
import json
from contextlib import suppress
from typing import Any

from livekit import rtc
from PIL import Image

from sighttalk_api.agent.worker import AGENT_TOPIC, AgentSession
from sighttalk_api.core.config import Settings
from sighttalk_api.providers.base import ImageFrame
from sighttalk_api.providers.factory import create_provider
from sighttalk_api.schemas.livekit import MediaPolicy


class LiveKitRoomAgent:
    def __init__(
        self,
        *,
        room_name: str,
        livekit_url: str,
        assistant_token: str,
        settings: Settings,
        media_policy: MediaPolicy,
    ) -> None:
        self._room_name = room_name
        self._livekit_url = livekit_url
        self._assistant_token = assistant_token
        self._settings = settings
        self._agent_session = AgentSession(
            session_id=room_name,
            provider=create_provider(settings),
            media_policy=media_policy,
        )
        self._room = rtc.Room()
        self._tasks: set[asyncio.Task[None]] = set()
        self._stopped = asyncio.Event()
        self._last_video_sent_at = 0.0
        self._connected = False
        self._assistant_audio_source: rtc.AudioSource | None = None
        self._terminal_error_sent = False

    async def run(self) -> None:
        self._room.on("track_subscribed", self._handle_track_subscribed)
        try:
            await self._room.connect(self._livekit_url, self._assistant_token)
            self._connected = True
            await self._publish_event(self._agent_session.status_event("connecting"))
            await self._publish_assistant_audio_track()
            await self._agent_session.start()
            await self._publish_event(self._agent_session.status_event("listening"))
            provider_task = asyncio.create_task(self._pump_provider_events())
            self._tasks.add(provider_task)
            provider_task.add_done_callback(self._tasks.discard)
            await self._stopped.wait()
        except Exception as exc:
            await self._publish_event(
                self._agent_session.error_event("AGENT_RUNTIME_ERROR", str(exc))
            )
        finally:
            await self.stop()

    async def stop(self) -> None:
        self._stopped.set()
        for task in list(self._tasks):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await self._agent_session.provider.close()
        if self._assistant_audio_source is not None:
            await self._assistant_audio_source.aclose()
        await self._room.disconnect()
        self._connected = False

    def _handle_track_subscribed(self, track: rtc.Track, *_args: Any) -> None:
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            task = asyncio.create_task(self._consume_audio(track))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        if track.kind == rtc.TrackKind.KIND_VIDEO:
            task = asyncio.create_task(self._consume_video(track))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

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
                try:
                    await self._agent_session.handle_audio(
                        bytes(frame.data),
                        sample_rate=frame.sample_rate,
                    )
                except RuntimeError as exc:
                    await self._handle_media_provider_error(exc)
                    return
        finally:
            await audio_stream.aclose()

    async def _consume_video(self, track: rtc.Track) -> None:
        video_stream = rtc.VideoStream.from_track(track=track, capacity=1)
        try:
            async for event in video_stream:
                now = asyncio.get_running_loop().time()
                min_interval = 1 / max(self._agent_session.media_policy.max_video_fps, 0.1)
                if now - self._last_video_sent_at < min_interval:
                    continue
                frame = encode_video_frame(
                    event.frame,
                    max_edge=self._agent_session.media_policy.max_jpeg_edge,
                    quality=self._agent_session.media_policy.jpeg_quality,
                )
                if frame is None:
                    continue
                self._last_video_sent_at = now
                self._agent_session.image_frames_sent += 1
                try:
                    await self._agent_session.provider.send_image(frame)
                except RuntimeError as exc:
                    await self._handle_media_provider_error(exc)
                    return
                await self._publish_event(self._agent_session.cost_event())
        finally:
            await video_stream.aclose()

    async def _pump_provider_events(self) -> None:
        async for event in self._agent_session.provider.events():
            if event.type == "audio_delta" and event.audio:
                await self._play_assistant_audio(event.audio)
            payload = self._agent_session.map_provider_event(event)
            if payload is not None:
                await self._publish_event(payload)

    async def _publish_assistant_audio_track(self) -> None:
        self._assistant_audio_source = rtc.AudioSource(24_000, 1)
        track = rtc.LocalAudioTrack.create_audio_track(
            "assistant-audio",
            self._assistant_audio_source,
        )
        await self._room.local_participant.publish_track(track)

    async def _play_assistant_audio(self, audio: bytes) -> None:
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

    async def _handle_media_provider_error(self, exc: RuntimeError) -> None:
        if not self._terminal_error_sent:
            self._terminal_error_sent = True
            await self._publish_event(
                self._agent_session.error_event("PROVIDER_UNAVAILABLE", str(exc))
            )
        self._stopped.set()

    async def _publish_event(self, payload: dict[str, Any]) -> None:
        if not self._connected:
            return
        await self._room.local_participant.publish_data(
            json.dumps(payload),
            reliable=True,
            topic=AGENT_TOPIC,
        )


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


class LiveKitAgentManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def start(
        self,
        *,
        room_name: str,
        livekit_url: str,
        assistant_token: str,
        settings: Settings,
        media_policy: MediaPolicy,
    ) -> None:
        existing = self._tasks.get(room_name)
        if existing is not None and not existing.done():
            return
        agent = LiveKitRoomAgent(
            room_name=room_name,
            livekit_url=livekit_url,
            assistant_token=assistant_token,
            settings=settings,
            media_policy=media_policy,
        )
        task = asyncio.create_task(agent.run())
        self._tasks[room_name] = task
        task.add_done_callback(lambda completed: self._tasks.pop(room_name, None))

    async def stop(self, room_name: str) -> None:
        task = self._tasks.pop(room_name, None)
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


_agent_manager = LiveKitAgentManager()


def get_agent_manager() -> LiveKitAgentManager:
    return _agent_manager
