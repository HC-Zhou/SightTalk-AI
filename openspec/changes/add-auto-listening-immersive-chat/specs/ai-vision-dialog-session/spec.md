## ADDED Requirements

### Requirement: Automatic listening conversation
The system SHALL start continuous microphone listening after the user starts a LiveKit conversation, without requiring a separate voice-question button or text turn submission.

#### Scenario: User starts conversation
- **WHEN** the user clicks `开始对话` and grants camera and microphone permissions
- **THEN** the frontend joins the LiveKit room, publishes local media, and renders the assistant as listening
- **AND** no manual `语音提问` or text-send control is required to submit speech

#### Scenario: User finishes an utterance
- **WHEN** backend/provider VAD determines that the user has finished speaking
- **THEN** the backend publishes final user transcript events and starts the assistant response

### Requirement: Backend-owned visual context
The backend SHALL own camera frame sampling for automatic conversation turns.

#### Scenario: User speaks while video is available
- **WHEN** the user speaks in an active session
- **THEN** the backend samples camera frames according to the active media policy and sends selected frames to the provider

### Requirement: Realtime captions and spoken answer
The system SHALL render realtime captions and play assistant audio for automatic turns.

#### Scenario: Assistant responds
- **WHEN** the provider emits assistant transcript and audio events
- **THEN** the backend publishes normalized caption/status events and assistant audio through the room contract

### Requirement: Minimal active controls
The frontend SHALL only expose Start, End, and Interrupt as primary active conversation controls.

#### Scenario: Conversation active
- **WHEN** a session is active
- **THEN** the UI displays `结束` and `打断`
- **AND** it does not display text input, send, voice-question, microphone toggle, camera toggle, or media mode controls in the primary surface

### Requirement: Immersive PC layout
The frontend SHALL use a fixed browser-height PC web layout with the camera preview as the primary visual surface.

#### Scenario: App rendered on desktop
- **WHEN** the app is opened in a desktop browser
- **THEN** the app shell fits the browser viewport height and presents a full-bleed video-chat interface with overlay captions and controls
