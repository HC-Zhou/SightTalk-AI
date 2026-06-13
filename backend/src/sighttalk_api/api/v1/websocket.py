from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sighttalk_api.ai.orchestrator import DialogueOrchestrator
from sighttalk_api.core.events import (
    AudioChunkEvent,
    ErrorEvent,
    SessionReadyEvent,
    SessionStartEvent,
    SessionStopEvent,
    UtteranceEndEvent,
    VideoFrameEvent,
    parse_client_event,
)
from sighttalk_api.core.session import SessionStore
from sighttalk_api.media.audio_buffer import AudioChunk
from sighttalk_api.media.frame_buffer import FrameItem


def create_websocket_router(
    session_store: SessionStore,
    orchestrator: DialogueOrchestrator,
) -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws/session/{session_id}")
    async def session_websocket(websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        session = session_store.get_or_create(session_id)

        try:
            while True:
                payload = await websocket.receive_json()
                try:
                    event = parse_client_event(payload)
                except Exception as exc:
                    await websocket.send_json(
                        ErrorEvent(
                            stage="websocket",
                            message=str(exc),
                            retryable=True,
                        ).model_dump()
                    )
                    continue

                if isinstance(event, SessionStartEvent):
                    await websocket.send_json(SessionReadyEvent(policy=session.policy).model_dump())
                elif isinstance(event, AudioChunkEvent):
                    session.audio_buffer.add(
                        AudioChunk(seq=event.seq, mime=event.mime, data=event.data)
                    )
                elif isinstance(event, VideoFrameEvent):
                    session.cost_state.record_frame_captured()
                    session.cost_state.record_frame_received()
                    session.frame_buffer.add(
                        FrameItem(
                            seq=event.seq,
                            captured_at=event.captured_at,
                            mime=event.mime,
                            data=event.data,
                        )
                    )
                elif isinstance(event, UtteranceEndEvent):
                    turn_events = await orchestrator.handle_utterance_end(
                        session=session,
                        audio_seq_end=event.audio_seq_end,
                    )
                    for turn_event in turn_events:
                        await websocket.send_json(turn_event.model_dump())
                elif isinstance(event, SessionStopEvent):
                    session_store.remove(session_id)
                    await websocket.close()
                    return
        except WebSocketDisconnect:
            session.status = "disconnected"

    return router

