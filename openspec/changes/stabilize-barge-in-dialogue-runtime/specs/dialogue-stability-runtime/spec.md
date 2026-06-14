## ADDED Requirements

### Requirement: Barge-in invalidates stale assistant responses
The system SHALL assign a monotonic response epoch to assistant response handling, and an interruption MUST invalidate all pending assistant events from older epochs.

#### Scenario: Late audio after interruption
- **WHEN** the user interrupts assistant speech and an audio event from the interrupted response arrives afterward
- **THEN** the system drops the stale audio event and does not play it to the user

#### Scenario: Late response completion after interruption
- **WHEN** a response completion event from an interrupted response arrives after the response epoch has advanced
- **THEN** the system ignores the stale completion event for user-visible state and records at most a diagnostic trace

#### Scenario: New response after interruption
- **WHEN** the user speaks again after interrupting the assistant
- **THEN** the system accepts provider events for the new response epoch and keeps older response events isolated from the new turn

### Requirement: Interrupt handling is idempotent
The system SHALL treat user barge-in and explicit interrupt controls as idempotent active-conversation operations.

#### Scenario: Rapid repeated interrupts
- **WHEN** the frontend sends multiple interrupt controls while the assistant is speaking
- **THEN** the backend performs one effective playback cancellation for the active epoch and keeps the session available for user input

#### Scenario: Provider cancel failure during interrupt
- **WHEN** the provider cancel command fails with a recoverable connection or protocol error during an interrupt
- **THEN** the system records a diagnostic error and keeps the active session in a recoverable listening state

#### Scenario: Interrupt while not speaking
- **WHEN** the user sends an interrupt while no assistant playback is active
- **THEN** the system leaves the session in a listening-capable state without publishing a user-visible error

### Requirement: Playback coordination prevents fragmented speech
The system SHALL coordinate assistant audio playback through a single ordered playback model that owns queue clearing, audio acceptance, playout completion, and stale audio rejection.

#### Scenario: Assistant audio starts
- **WHEN** a non-stale assistant audio event arrives for the current response epoch
- **THEN** the system starts or continues exactly one ordered playback stream for that epoch

#### Scenario: Playback is interrupted
- **WHEN** the user interrupts assistant playback
- **THEN** the system clears queued assistant audio for the interrupted epoch and prevents later audio from that epoch from reaching the playback sink

#### Scenario: Playout completion
- **WHEN** the queued audio for the current assistant response has completed playout
- **THEN** the system publishes response completion for that current epoch and returns to a listening-capable state

### Requirement: Recoverable errors are diagnostic-only during active conversation
The system SHALL classify provider cancel errors, stale provider events, malformed stale events, and recoverable provider protocol errors as diagnostic-only during an active conversation.

#### Scenario: Recoverable provider protocol error
- **WHEN** a recoverable provider protocol error occurs during an active conversation
- **THEN** the backend records the error in logs and metrics and does not publish a user-visible frontend error state

#### Scenario: Diagnostic event is emitted
- **WHEN** the system emits a diagnostic error event
- **THEN** the event includes severity and surface metadata and does not require the frontend to change visible conversation status

#### Scenario: API response includes failure details
- **WHEN** a recoverable active-conversation operation returns an API response or diagnostic payload
- **THEN** the response may include the error code and message for debugging without requiring visible in-call feedback

### Requirement: Terminal failures stop gracefully without active-call error visuals
The system SHALL distinguish terminal runtime failures from recoverable diagnostics, and terminal failures MUST stop the affected conversation gracefully without rendering a red active-call error banner.

#### Scenario: Provider becomes unavailable
- **WHEN** the provider connection becomes unavailable and the session cannot continue
- **THEN** the backend emits terminal diagnostics, stops the affected runtime resources, and prevents further provider media forwarding

#### Scenario: Frontend receives terminal failure during active call
- **WHEN** the frontend learns that an active call ended due to a terminal runtime failure
- **THEN** the frontend releases media resources and exits the active call view without rendering a visible error alert in the conversation surface

#### Scenario: Startup failure remains visible
- **WHEN** a session cannot start because of authentication, media permission, or required configuration failure
- **THEN** the frontend may present a blocking error because the active conversation has not begun

### Requirement: Frontend active conversation remains visually calm
The frontend SHALL NOT show red error banners, red interrupted status, or user-visible error text for recoverable errors that occur after an active conversation has started.

#### Scenario: Realtime diagnostic error
- **WHEN** the frontend receives a diagnostic or recoverable realtime error during an active conversation
- **THEN** the frontend stores or logs the diagnostic and keeps the visible conversation state neutral

#### Scenario: User clicks interrupt
- **WHEN** the user clicks the interrupt control during assistant speech
- **THEN** the frontend immediately stops old assistant audio locally and presents a listening-capable state without a red interrupted visual

#### Scenario: Legacy error event arrives during active call
- **WHEN** a legacy realtime `error` event arrives during an active conversation
- **THEN** the frontend treats it as a diagnostic unless it is explicitly classified as terminal

### Requirement: Diagnostics are observable and testable
The system SHALL preserve error and interruption details through structured logs, metrics traces, or diagnostic realtime payloads so operators and tests can inspect failures that are not user-visible.

#### Scenario: Interrupt diagnostic trace
- **WHEN** an interrupt is handled
- **THEN** the system records the interrupt source, reason, response epoch, and whether stale events were dropped

#### Scenario: Provider error diagnostic trace
- **WHEN** a provider error is classified as recoverable or terminal
- **THEN** the system records the provider code, normalized severity, session id, and response epoch without exposing provider secrets

#### Scenario: Test verifies hidden error
- **WHEN** automated tests simulate a recoverable provider cancel error during active conversation
- **THEN** tests can assert that diagnostics were recorded and that no user-visible frontend error feedback was rendered
