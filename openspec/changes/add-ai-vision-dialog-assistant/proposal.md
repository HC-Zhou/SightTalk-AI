## Why

The project needs a PC web application where users can talk naturally with an AI assistant that can hear speech, observe camera video, and respond with useful spoken and textual answers. The repository is currently only a full-stack template, so the first change must establish the backend, frontend, realtime media architecture, and cross-team contracts clearly enough for separate backend and frontend agents to implement in parallel.

## What Changes

- Add a Python backend workspace responsible for API health checks, LiveKit session issuance, realtime agent orchestration, provider adapters, and cost-control policies.
- Add a React PC web frontend workspace responsible for camera/microphone permission handling, LiveKit room participation, local preview, transcript display, assistant state, and cost mode controls.
- Use a self-hosted LiveKit media layer for browser audio/video transport in local development.
- Use Alibaba Cloud Model Studio Bailian as the default realtime multimodal provider through a backend adapter interface that can later support other providers.
- Add backend and frontend SDD documents that define implementation contracts for two separate implementation agents.

## Capabilities

### New Capabilities

- `ai-vision-dialog-session`: Realtime AI dialog sessions that combine browser camera video, microphone audio, assistant speech output, transcript events, and cost-aware vision sampling.

### Modified Capabilities

- None.

## Impact

- Adds backend application structure under `backend/` using Python, FastAPI, LiveKit server SDK, and pytest-oriented tests.
- Adds frontend application structure under `frontend/` using React, TypeScript, Vite, LiveKit client SDK, Vitest, and Testing Library.
- Adds local development service expectations for LiveKit, backend, frontend, and the agent worker.
- Introduces public API contracts for LiveKit session creation and termination.
- Introduces environment configuration for LiveKit and Bailian credentials, region, workspace, model, and realtime endpoint.
