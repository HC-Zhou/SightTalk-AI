## ADDED Requirements

### Requirement: User-scoped memory files
The system SHALL persist long-term text memory per authenticated user in `${SIGHTTALK_DATA_DIR}/memory/<user_id>.jsonl`.

#### Scenario: Memory write
- **WHEN** finalized session text is persisted for a user
- **THEN** the memory store appends a JSONL record under that user's memory file with user id, session id, timestamp, speaker or source, and text

#### Scenario: User isolation
- **WHEN** memories are read for one authenticated user
- **THEN** records from other users' memory files are not returned or injected

### Requirement: Recent memory retrieval
The system SHALL retrieve only the most recent valid memory records up to `HARNESS_MEMORY_MAX_ITEMS` for a user.

#### Scenario: Retention limit
- **WHEN** a user has more than `HARNESS_MEMORY_MAX_ITEMS` memory records
- **THEN** the context layer uses only the most recent configured number of valid records

#### Scenario: Corrupt memory line
- **WHEN** a user memory file contains malformed JSONL lines
- **THEN** the memory store ignores malformed lines and still returns valid records

### Requirement: Memory prompt injection
The system SHALL inject recent user memories into the provider system prompt at session startup while preserving the existing base SightTalk assistant instructions.

#### Scenario: Session start with memories
- **WHEN** an authenticated user starts an agent session and has recent memory records
- **THEN** the provider session config includes a clearly delimited memory section in the system prompt

#### Scenario: Session start without memories
- **WHEN** an authenticated user starts an agent session and has no memory records
- **THEN** the provider session config uses the base SightTalk assistant instructions without an empty memory section

### Requirement: Memory capture from transcripts
The system SHALL persist finalized transcript text to user memory after `response.done` and when a session ends. The system MUST NOT persist raw audio bytes, image bytes, or empty text as memory.

#### Scenario: Response completion
- **WHEN** Tooling emits `response.done` for a session with finalized transcript text
- **THEN** Context flushes the finalized text messages to the authenticated user's memory file

#### Scenario: Session end
- **WHEN** a session ends before a response completion flush occurs
- **THEN** Context persists any finalized transcript text that has not already been written

#### Scenario: Empty transcript
- **WHEN** a session has no finalized transcript text
- **THEN** Context does not append a memory record
