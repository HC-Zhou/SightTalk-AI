## ADDED Requirements

### Requirement: Long-term memory protocol supports search and turn persistence
The system SHALL expose a long-term memory protocol with `search(scope, query, limit, threshold)`, `add_turn(scope, messages, metadata)`, and `close()` operations.

#### Scenario: Disabled memory is non-fatal
- **WHEN** the configured memory backend is disabled
- **THEN** memory search returns no records and turn persistence is a no-op without blocking the conversation

#### Scenario: Memory backend failure is non-fatal
- **WHEN** a memory search or add operation fails
- **THEN** the agent logs or reports the internal failure as non-terminal and continues the realtime conversation path

### Requirement: Memory scope isolates users and agents
The system SHALL scope long-term memory operations by `user_id`, `agent_id`, and `run_id`, while default search filters include `user_id` and `agent_id` but not `run_id`.

#### Scenario: Cross-session recall
- **WHEN** a user starts a new session after a previous session stored memory
- **THEN** memory search can retrieve that user's prior memories for the same agent id even though the run id differs

#### Scenario: User isolation
- **WHEN** memory exists for another user id
- **THEN** search results for the active user do not include the other user's memory

### Requirement: Mem0 backend writes finalized turns after response completion
The system SHALL write long-term memory only after `response.done` for complete finalized user/assistant turns and MUST NOT store audio bytes, image bytes, or empty text.

#### Scenario: Response completion writes metadata
- **WHEN** a response completes with finalized text turns
- **THEN** the memory backend receives messages plus metadata containing session id, turn id, media mode, visual-context flag, and source `sighttalk_realtime`

#### Scenario: Empty turn is skipped
- **WHEN** the finalized turn has no non-whitespace text
- **THEN** no long-term memory add request is sent

### Requirement: Mem0 backend uses recommended entity payloads and filters
The system SHALL call Mem0 add with messages plus `user_id`, `agent_id`, `run_id`, metadata, and default inference enabled; search SHALL use an AND filter containing `user_id` and `agent_id`, plus limit and threshold.

#### Scenario: Search filter shape
- **WHEN** the Mem0 backend searches for memories
- **THEN** it sends filters equivalent to `{"AND": [{"user_id": user_id}, {"agent_id": agent_id}]}`

#### Scenario: Add payload shape
- **WHEN** the Mem0 backend stores a completed turn
- **THEN** it sends the ordered message list with `user_id`, `agent_id`, `run_id`, metadata, and `infer=True`

### Requirement: Local JSONL fallback remains available
The system SHALL provide a local JSONL-compatible long-term memory backend for development and CI when Mem0 is not configured.

#### Scenario: Local backend search
- **WHEN** the local JSONL backend searches for memories
- **THEN** it returns recent matching user-scoped text records up to the requested limit without requiring external services

#### Scenario: Local backend add
- **WHEN** the local JSONL backend stores a finalized turn
- **THEN** it appends only non-empty text messages to the user-scoped local memory file

### Requirement: Provider responses can be gated on memory retrieval
The system SHALL support a future manual provider response flow where finalized user transcripts trigger memory search, provider context update, and explicit response creation before assistant generation.

#### Scenario: Manual response order
- **WHEN** a provider supports manual response and context update
- **THEN** the runtime can process user transcript completion as memory search, context update, and response creation in that order

#### Scenario: Automatic provider fallback
- **WHEN** a provider does not support manual response or context update
- **THEN** the runtime keeps the existing automatic provider response behavior
