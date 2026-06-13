from sighttalk_api.ai.adapters import AsrAdapter, MultimodalAdapter, TtsAdapter
from sighttalk_api.core.events import (
    AssistantTextDeltaEvent,
    AssistantTextDoneEvent,
    AssistantThinkingEvent,
    CostSnapshotEvent,
    TranscriptFinalEvent,
    TtsReadyEvent,
)
from sighttalk_api.core.session import SessionState
from sighttalk_api.media.keyframe_selector import select_keyframes
from sighttalk_api.storage.audio_store import InMemoryAudioStore

type ServerTurnEvent = (
    TranscriptFinalEvent
    | AssistantThinkingEvent
    | AssistantTextDeltaEvent
    | AssistantTextDoneEvent
    | TtsReadyEvent
    | CostSnapshotEvent
)


class DialogueOrchestrator:
    def __init__(
        self,
        asr: AsrAdapter,
        multimodal: MultimodalAdapter,
        tts: TtsAdapter,
        audio_store: InMemoryAudioStore,
    ) -> None:
        self.asr = asr
        self.multimodal = multimodal
        self.tts = tts
        self.audio_store = audio_store

    async def handle_utterance_end(
        self,
        session: SessionState,
        audio_seq_end: int,
    ) -> list[ServerTurnEvent]:
        audio_chunks = session.audio_buffer.collect_until(audio_seq_end)
        session.cost_state.record_asr_call()
        asr_result = await self.asr.transcribe(audio_chunks)

        keyframes = select_keyframes(
            session.frame_buffer.recent(),
            limit=session.policy.max_keyframes_per_turn,
        )
        session.cost_state.record_frames_sent_to_model(len(keyframes))

        history = [(turn.role, turn.text) for turn in session.conversation_history]
        session.add_turn(
            role="user",
            text=asr_result.text,
            frame_refs=[str(frame.seq) for frame in keyframes],
        )

        session.cost_state.record_multimodal_call()
        answer = await self.multimodal.answer(asr_result.text, keyframes, history)
        session.add_turn(role="assistant", text=answer.answer, frame_refs=[])

        session.cost_state.record_tts_call()
        speech = await self.tts.synthesize(answer.answer)
        turn_id = len(session.conversation_history)
        audio_url = self.audio_store.save(session.session_id, turn_id, speech.audio_bytes)

        return [
            TranscriptFinalEvent(text=asr_result.text),
            AssistantThinkingEvent(),
            AssistantTextDeltaEvent(text=answer.answer),
            AssistantTextDoneEvent(text=answer.answer),
            TtsReadyEvent(audio_url=audio_url),
            session.cost_state.to_snapshot(policy_name=session.cost_controller.policy_name),
        ]
