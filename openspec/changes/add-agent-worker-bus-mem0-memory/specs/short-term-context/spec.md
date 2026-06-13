## ADDED Requirements

### Requirement: Session state separates identity, media, counters, and transcript state
The system SHALL represent per-session agent state with separate structures for session identity, current media policy, usage counters, pending transcript deltas, finalized user and assistant turns, current summary, and recent-turn retention.

#### Scenario: Finalized user turn is retained
- **WHEN** a provider emits a finalized user transcript
- **THEN** the short-term context records the turn with speaker, text, message id, turn id, timestamp, media mode, and visual-context metadata

#### Scenario: Pending deltas are not persisted as finalized turns
- **WHEN** a provider emits only transcript deltas for a message id
- **THEN** the short-term context keeps the pending text separately and does not expose it as a finalized turn

### Requirement: Context builder preserves instruction priority
The system SHALL build provider context in a deterministic order where base system instructions outrank untrusted long-term memory, summary text, and recent conversation turns.

#### Scenario: Memory block is labeled untrusted
- **WHEN** retrieved long-term memories are included in provider context
- **THEN** the context builder labels them as untrusted user memory that is context only and not instructions

#### Scenario: Base instruction remains first
- **WHEN** provider context includes memory, summary, and conversation turns
- **THEN** the base SightTalk instruction appears before all other context blocks

### Requirement: Short-term context triggers summarization at configured limits
The system SHALL request context summarization when finalized messages exceed `SHORT_MEMORY_MAX_MESSAGES` or estimated context tokens exceed `SHORT_MEMORY_MAX_ESTIMATED_TOKENS`.

#### Scenario: Message threshold reached
- **WHEN** finalized message count exceeds the configured maximum
- **THEN** the context requests summarization before building the next provider context

#### Scenario: Token threshold reached
- **WHEN** estimated context tokens exceed the configured maximum
- **THEN** the context requests summarization before building the next provider context

### Requirement: Summarization preserves recent and incomplete turn state
The system SHALL preserve the base instruction, long-term memory block, last four finalized turns, and incomplete provider/tool sequences when summarizing older short-term context.

#### Scenario: Summary succeeds
- **WHEN** summarization succeeds
- **THEN** older finalized turns are represented by the summary while the most recent four turns remain verbatim

#### Scenario: Summary fails
- **WHEN** summarization fails or times out
- **THEN** context construction falls back to a bounded recent-window prompt and does not block the conversation

### Requirement: Short-term context keeps LiveKit payload compatibility
The system SHALL keep existing frontend payload fields for status, transcript, response completion, audio, cost, and error events while changing only internal context construction.

#### Scenario: Existing transcript payload
- **WHEN** a finalized transcript is published to LiveKit
- **THEN** the payload still uses type `transcript.done` with the existing speaker, text, message id, session id, and timestamp fields
