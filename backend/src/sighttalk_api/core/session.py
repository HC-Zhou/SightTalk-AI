from dataclasses import dataclass, field
from datetime import UTC, datetime

from sighttalk_api.core.cost import CostController, CostState
from sighttalk_api.core.events import CapturePolicy
from sighttalk_api.media.audio_buffer import AudioBuffer
from sighttalk_api.media.frame_buffer import FrameBuffer


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    text: str
    created_at: datetime
    frame_refs: list[str]


@dataclass
class SessionState:
    session_id: str
    policy: CapturePolicy
    audio_buffer: AudioBuffer = field(default_factory=AudioBuffer)
    frame_buffer: FrameBuffer = field(default_factory=FrameBuffer)
    conversation_history: list[ConversationTurn] = field(default_factory=list)
    cost_state: CostState = field(default_factory=CostState)
    cost_controller: CostController = field(default_factory=CostController)
    history_limit: int = 6
    status: str = "ready"

    def add_turn(self, role: str, text: str, frame_refs: list[str]) -> None:
        self.conversation_history.append(
            ConversationTurn(
                role=role,
                text=text,
                created_at=datetime.now(UTC),
                frame_refs=frame_refs,
            )
        )
        if len(self.conversation_history) > self.history_limit:
            self.conversation_history = self.conversation_history[-self.history_limit :]


class SessionStore:
    def __init__(self, history_limit: int = 6) -> None:
        self.history_limit = history_limit
        self.sessions: dict[str, SessionState] = {}

    def get_or_create(self, session_id: str) -> SessionState:
        if session_id not in self.sessions:
            policy = CapturePolicy()
            self.sessions[session_id] = SessionState(
                session_id=session_id,
                policy=policy,
                history_limit=self.history_limit,
            )
        return self.sessions[session_id]

    def remove(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
