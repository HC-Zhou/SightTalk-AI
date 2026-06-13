# SightTalk AI

SightTalk AI is a PC web visual voice assistant. The browser captures camera and microphone media, publishes it to a self-hosted LiveKit room, and sends each user turn to a Python backend with the recognized utterance plus a camera frame. Alibaba Cloud Model Studio Bailian is the production provider target; a `mock` provider is included for local demos and automated tests without cloud credentials.

## Original Work

The application code in this repository is newly implemented for this project. Third-party dependencies are used for the framework, media transport, validation, testing, and build tooling; the original application logic is the session API, provider adapter boundary, media policy logic, realtime event contract, and PC web client experience.

## Dependencies

Backend:

- FastAPI and Uvicorn for the HTTP API.
- httpx for Bailian application and compatible-model API calls.
- Pydantic Settings for typed environment configuration.
- PyJWT for LiveKit-compatible participant token generation.
- websockets for the Bailian realtime adapter boundary.
- Pytest, Ruff, and MyPy for tests and quality checks.

Frontend:

- React, TypeScript, and Vite for the PC web app.
- livekit-client for WebRTC room connection, local camera/microphone publishing, and data messages.
- Browser Web Speech API for speech-to-text during user turns, with typed text as a fallback.
- lucide-react for control icons.
- Vitest, Testing Library, ESLint, and Prettier-compatible formatting conventions for checks.

Infrastructure:

- LiveKit Server `latest` for local realtime media transport.
- Docker Compose for local full-stack orchestration.

## Local Development

Backend:

```bash
cd backend
uv sync --dev
uv run uvicorn sighttalk_api.main:app --reload
uv run ruff check .
uv run mypy
uv run pytest
```

Frontend:

```bash
cd frontend
npm install
npm run dev
npm run lint
npm run test:run
npm run build
```

Full stack:

```bash
docker compose up --build
```

Open the frontend at `http://localhost:5173`. Click `开始对话`, grant camera and microphone permission, then use `语音提问` or the text composer. Each turn sends the recognized text and one camera frame to the backend.

The compose setup defaults to `AI_PROVIDER=mock` so the app can run without Bailian credentials. To use Bailian, create a local `.env` from `backend/.env.example` or set equivalent Compose environment variables:

- `AI_PROVIDER=bailian`
- `LIVEKIT_SERVER_URL` if the backend must call LiveKit through a different internal hostname than the browser-facing `LIVEKIT_URL`
- `BAILIAN_API_KEY`
- `BAILIAN_REGION`
- Optional `BAILIAN_APP_ID`
- `BAILIAN_COMPATIBLE_API_URL`
- `BAILIAN_TEXT_MODEL`
- `BAILIAN_VISION_MODEL`

When a configured Bailian application ID is unavailable or returns access denied, the backend automatically falls back to Bailian's OpenAI-compatible model endpoint using `BAILIAN_TEXT_MODEL` for text-only turns and `BAILIAN_VISION_MODEL` when a camera frame is provided.

## PR and Commit Guidance

Develop through small PRs. Each PR should implement one focused capability, keep `main` runnable after merge, and include:

- Title: one sentence describing the change.
- Functional description: what changed and how to use it.
- Implementation notes: main technical choices.
- Test method: commands or manual steps used to verify it.

Do not commit `.env` files or secrets. If reusing prior code, document the source in the PR description.
