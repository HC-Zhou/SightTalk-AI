## ADDED Requirements

### Requirement: Local user registration
The system SHALL provide `POST /api/v1/auth/register` for creating local users with an email and password. Registration MUST persist a stable `user_id`, normalized email, and password hash metadata in `${SIGHTTALK_DATA_DIR}/users.json`.

#### Scenario: Successful registration
- **WHEN** an unauthenticated client submits a valid unused email and password
- **THEN** the API returns a successful response containing the created user profile and a Bearer token for that user

#### Scenario: Duplicate registration
- **WHEN** an unauthenticated client submits an email already present in the local user store
- **THEN** the API returns an error response and does not create a second user record

### Requirement: Passwords are stored as hashes
The system MUST hash user passwords with PBKDF2-SHA256 before persistence. The persisted user store MUST NOT contain plaintext passwords.

#### Scenario: User file after registration
- **WHEN** registration succeeds
- **THEN** `users.json` contains PBKDF2-SHA256 hash metadata and no plaintext password value

### Requirement: Local user login
The system SHALL provide `POST /api/v1/auth/login` for validating local user credentials and issuing JWT Bearer tokens.

#### Scenario: Successful login
- **WHEN** a client submits a registered email and the correct password
- **THEN** the API returns the user profile, a Bearer token, and token expiration metadata

#### Scenario: Failed login
- **WHEN** a client submits an unknown email or incorrect password
- **THEN** the API returns `401` and does not reveal whether the email or password was invalid

### Requirement: Token identity endpoint
The system SHALL provide `GET /api/v1/auth/me` for returning the authenticated user profile associated with a valid Bearer token.

#### Scenario: Valid token
- **WHEN** a client calls `/api/v1/auth/me` with `Authorization: Bearer <valid-token>`
- **THEN** the API returns the user profile associated with the token subject

#### Scenario: Invalid or expired token
- **WHEN** a client calls `/api/v1/auth/me` with a missing, malformed, expired, or unverifiable token
- **THEN** the API returns `401`

### Requirement: Authenticated LiveKit session APIs
The system MUST require `Authorization: Bearer <token>` for `POST /api/v1/livekit/session`, `POST /api/v1/livekit/session/{room_name}/agent/start`, and `POST /api/v1/livekit/session/{room_name}/end`. These endpoints MUST keep their existing request body contracts.

#### Scenario: Missing token
- **WHEN** a client calls a protected LiveKit session endpoint without a Bearer token
- **THEN** the API returns `401`

#### Scenario: Valid token
- **WHEN** a client calls a protected LiveKit session endpoint with a valid Bearer token
- **THEN** the endpoint performs the existing session behavior and associates the session with the authenticated `user_id`

### Requirement: Frontend auth lifecycle
The frontend SHALL show login/register controls when no usable token is available, persist successful auth tokens in `localStorage`, attach the token to session API requests, and clear the token on logout.

#### Scenario: Unauthenticated first load
- **WHEN** the app starts without a stored token
- **THEN** the user sees the login/register interface instead of the conversation start control

#### Scenario: Authenticated session request
- **WHEN** an authenticated user starts a SightTalk session
- **THEN** the frontend sends `Authorization: Bearer <token>` with backend LiveKit session API requests

#### Scenario: Logout
- **WHEN** the user logs out
- **THEN** the frontend clears the stored token, stops any active session, and returns to the login/register interface
