## ADDED Requirements

### Requirement: Typed frames carry priority and cancellation metadata
The system SHALL represent internal agent work as typed frames with stable identity, creation time, frame type, priority, source, optional target, interruptibility, and typed payload data.

#### Scenario: System frame priority
- **WHEN** a system frame and data frame are both queued
- **THEN** the worker bus dispatches the system frame first regardless of enqueue order

#### Scenario: Interruptible frame cancellation
- **WHEN** an interruption is requested for queued control or data frames
- **THEN** interruptible queued frames are cancelled and non-interruptible system frames remain available for dispatch

### Requirement: Worker bus routes frames to subscribed workers
The system SHALL provide an in-process worker bus that lets workers subscribe to frame types and receive matching frames without coupling workers to each other directly.

#### Scenario: Targeted routing
- **WHEN** a frame has a target worker id
- **THEN** only the targeted worker receives the frame if it is subscribed to that frame type

#### Scenario: Broadcast routing
- **WHEN** a frame has no target worker id
- **THEN** all active subscribed workers receive the frame according to bus ordering rules

### Requirement: Worker registry controls activation
The system SHALL provide a worker registry that tracks worker ids, subscriptions, activation state, startup, shutdown, and lookup for the runner.

#### Scenario: Inactive worker does not receive frames
- **WHEN** a worker is registered but inactive
- **THEN** the worker bus does not dispatch ordinary frames to that worker

#### Scenario: Worker startup failure is terminal
- **WHEN** a required worker fails during runner startup
- **THEN** the runner publishes one terminal error frame and begins coordinated shutdown

### Requirement: Runner owns lifecycle and interruption semantics
The system SHALL provide a worker runner that starts registered workers, drives frame dispatch, coordinates interruption, enforces terminal error convergence, and closes workers idempotently.

#### Scenario: Terminal error convergence
- **WHEN** multiple workers report terminal errors for the same session
- **THEN** the runner emits at most one terminal error event to the transport contract

#### Scenario: Interruption preserves system frames
- **WHEN** an interruption occurs while data frames are queued
- **THEN** the runner cancels interruptible queued data frames and preserves system frames needed for cleanup or status publication

### Requirement: Pipeline workers process frames sequentially
The system SHALL provide processor pipeline workers that run subscribed frames through ordered frame processors and publish any resulting frames back to the bus.

#### Scenario: Processor output is requeued
- **WHEN** a processor returns one or more output frames
- **THEN** the pipeline worker publishes those frames to the worker bus for normal routing
