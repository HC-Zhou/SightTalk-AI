## ADDED Requirements

### Requirement: Session issuance
The system SHALL expose a backend API that creates a LiveKit session for a single PC web user and returns the connection information required by the frontend.

#### Scenario: Session created
- **WHEN** the frontend requests a new AI dialog session
- **THEN** the backend returns a room name, participant identity, LiveKit participant token, LiveKit URL, expiration timestamp, assistant identity, and media policy

#### Scenario: Session creation fails
- **WHEN** required LiveKit server configuration is missing or invalid
- **THEN** the backend returns a structured error and does not expose provider credentials to the frontend

### Requirement: Browser media participation
The frontend SHALL request camera and microphone permission, preview local camera video, and publish local audio and video tracks to the issued LiveKit room.

#### Scenario: User starts a session
- **WHEN** the user grants camera and microphone permissions and starts the session
- **THEN** the frontend joins the LiveKit room and publishes audio and video tracks for the backend agent

#### Scenario: Permission denied
- **WHEN** the user denies camera or microphone permission
- **THEN** the frontend displays a recoverable error state and does not attempt to join the room with missing media

### Requirement: Backend realtime agent bridge
The backend SHALL run a LiveKit agent that subscribes to the user's audio and video tracks, streams selected media to the configured AI provider adapter, and publishes assistant responses back to the room.

#### Scenario: User speaks with camera enabled
- **WHEN** the user speaks during an active session with video enabled
- **THEN** the backend agent forwards audio and policy-selected visual frames to the provider adapter and publishes assistant audio plus transcript events to the LiveKit room

#### Scenario: Provider unavailable
- **WHEN** the AI provider adapter cannot connect or returns a terminal session error
- **THEN** the backend agent publishes an error event to the room and releases provider resources for that session

### Requirement: Provider adapter
The backend SHALL define an AI provider adapter boundary so that Bailian is the default provider and future providers can be added without changing frontend session or LiveKit event contracts.

#### Scenario: Bailian provider selected
- **WHEN** `AI_PROVIDER` is unset or set to `bailian`
- **THEN** the backend uses the Bailian realtime provider configured by environment variables

#### Scenario: Unsupported provider selected
- **WHEN** `AI_PROVIDER` names a provider that is not implemented
- **THEN** the backend fails startup or session creation with a clear structured configuration error

### Requirement: Realtime UI events
The system SHALL use LiveKit data messages for assistant status, transcript, response completion, cost estimates, client mode changes, interruption requests, and errors.

#### Scenario: Assistant response streamed
- **WHEN** the AI provider emits partial and final response events
- **THEN** the backend agent publishes corresponding transcript and response events that the frontend renders in the conversation UI

#### Scenario: User changes cost mode
- **WHEN** the user selects economy, balanced, or accurate mode during an active session
- **THEN** the frontend publishes a control event and the backend agent applies the matching media policy for subsequent sampling

### Requirement: Cost-aware visual sampling
The backend agent SHALL own visual frame sampling, resizing, compression, and rate limiting before sending images to the AI provider.

#### Scenario: Balanced mode active
- **WHEN** an active session uses balanced mode
- **THEN** the backend applies VAD-enabled audio handling and limits visual context to policy-selected JPEG frames with a maximum edge of 1024 pixels

#### Scenario: Explicit visual request
- **WHEN** the user's utterance indicates a visual question such as asking what is visible or asking to read on-screen text
- **THEN** the backend may temporarily increase visual frame quality or frequency within the selected mode's limits

### Requirement: Session termination
The system SHALL allow sessions to be stopped by the user or by backend cleanup and SHALL release LiveKit and AI provider resources.

#### Scenario: User stops the session
- **WHEN** the user stops an active AI dialog session
- **THEN** the frontend disconnects from LiveKit and the backend stops the corresponding provider session and agent work

#### Scenario: Room expires
- **WHEN** a session exceeds its configured lifetime or becomes inactive
- **THEN** the backend cleanup releases provider resources and prevents continued use of expired credentials
