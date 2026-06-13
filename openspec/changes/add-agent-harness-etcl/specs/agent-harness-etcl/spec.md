## ADDED Requirements

### Requirement: Execution module owns LiveKit media I/O
The system SHALL provide an Execution harness module that owns LiveKit room connection, track subscription handling, frontend event publication, audio stream consumption, video stream consumption, assistant audio track publication, assistant audio playback, and cleanup. The Execution module MUST NOT call `AIProvider` directly.

#### Scenario: Track subscription delegates media frames
- **WHEN** LiveKit audio or video tracks are subscribed
- **THEN** Execution consumes frames and delegates media payloads to Lifecycle or Tooling without directly invoking provider methods

#### Scenario: Cleanup
- **WHEN** a session stops or errors
- **THEN** Execution closes media streams, assistant audio source, LiveKit room connection, and owned tasks

### Requirement: Tooling module owns provider protocol
The system SHALL provide a Tooling harness module that owns provider connection, provider calls, interrupt and media mode controls, provider event iteration, provider error handling, and provider-event-to-frontend-event normalization.

#### Scenario: Provider event normalization
- **WHEN** Tooling receives provider transcript, audio, response completion, status, or error events
- **THEN** it maps them to the existing LiveKit realtime frontend event payload shape

#### Scenario: Provider control
- **WHEN** Tooling receives an interrupt or media mode update from Lifecycle
- **THEN** it sends the corresponding provider control event and returns any frontend status or cost event needed by the existing UI contract

### Requirement: Context module owns session state and counters
The system SHALL provide a Context harness module that owns session identity, authenticated `user_id`, current media policy, transcript messages, audio-second counters, image-frame counters, cost estimate event data, and memory prompt construction.

#### Scenario: Cost estimate update
- **WHEN** audio or image media is accepted for a session
- **THEN** Context updates the corresponding counters and can produce the existing `cost.estimate` payload

#### Scenario: Transcript tracking
- **WHEN** finalized transcript events are observed
- **THEN** Context records the message text by speaker and message id for later memory persistence

### Requirement: Lifecycle module orchestrates runtime state
The system SHALL provide a Lifecycle harness module that owns state transitions across `created`, `connecting`, `listening`, `interrupted`, `error`, and `ended`; provider-ready and audio-ready gates; task startup and cancellation; terminal error convergence; and frontend event publication sequencing.

#### Scenario: Normal startup
- **WHEN** a room agent starts successfully
- **THEN** Lifecycle connects Execution, starts Tooling, opens media gates in order, publishes `agent.status` events, and enters `listening`

#### Scenario: Terminal provider error
- **WHEN** provider connection or media sending raises a terminal runtime error
- **THEN** Lifecycle publishes one terminal error event, moves to `error`, stops runtime tasks, and releases Execution and Tooling resources

### Requirement: Media readiness gates
The system MUST NOT forward user audio before the provider session is ready, and MUST NOT forward image frames before at least one audio chunk has been accepted for the provider session.

#### Scenario: Audio before provider ready
- **WHEN** an audio track is subscribed before provider startup completes
- **THEN** the system waits for provider readiness before forwarding audio chunks

#### Scenario: Image before audio
- **WHEN** video frames arrive before any audio chunk has been accepted
- **THEN** the system does not forward image frames to the provider

### Requirement: LiveKit realtime compatibility
The harness refactor MUST preserve the existing LiveKit data topic names and frontend realtime event payloads.

#### Scenario: Existing frontend receives events
- **WHEN** provider or lifecycle events are published through the harness
- **THEN** events continue to use topic `sighttalk.agent` and the existing `agent.status`, `transcript.delta`, `transcript.done`, `response.done`, `audio.delta`, `cost.estimate`, and `error` payload shapes

#### Scenario: Existing controls are received
- **WHEN** the frontend publishes interrupt or media mode controls
- **THEN** the harness continues to receive them on topic `sighttalk.control` and applies the same behavior as before the refactor
