## Context

The repository currently contains only project-level scaffolding and OpenSpec configuration. The change introduces a full-stack PC web application where a user can open their camera and microphone, speak with an AI assistant, and receive natural spoken and textual responses informed by visual context.

The implementation is split between two future agents:

- Backend agent: Python FastAPI service, LiveKit session/token APIs, LiveKit agent worker, AI provider adapter layer, Bailian realtime implementation, tests, and local service wiring.
- Frontend agent: React PC web app, browser media capture, LiveKit client connection, conversation UI, assistant state rendering, and tests.

The first implementation target is local development with a self-hosted LiveKit server and Alibaba Cloud Model Studio Bailian as the default realtime multimodal provider. Provider selection, Bailian region, Bailian workspace, model, and realtime endpoint are environment-driven so that later implementations can add additional providers without changing frontend contracts.

## Goals / Non-Goals

**Goals:**

- Build a PC web realtime AI dialog app with camera, microphone, assistant audio, transcripts, and assistant state.
- Use LiveKit as the browser media transport and Python as the server-side realtime agent runtime.
- Use Bailian through a provider adapter interface rather than directly coupling application code to one vendor.
- Define stable backend REST contracts, LiveKit data-message topics, environment variables, and test expectations for parallel implementation.
- Control cost by sampling/compressing visual frames in the backend agent and by supporting economy, balanced, and accurate media policies.

**Non-Goals:**

- Mobile UI, multi-user meeting features, authentication, billing, long-term memory, production observability, or local model inference.
- Direct browser-to-Bailian media transport.
- A provider-complete abstraction for every future model vendor; only the extension point and Bailian default implementation are required.

## Decisions

1. Use self-hosted LiveKit for local realtime media transport.
   - Rationale: LiveKit gives the browser a mature WebRTC path for camera, microphone, data messages, and assistant audio while keeping AI credentials out of the frontend.
   - Alternative considered: direct browser-to-model WebRTC. This has lower moving parts but conflicts with the chosen Bailian backend adapter and makes provider switching harder.
   - Alternative considered: FastAPI WebSocket media relay. This gives more server control but increases realtime media complexity and latency.

2. Run a Python LiveKit agent as the media bridge.
   - Rationale: The agent can subscribe to user audio/video tracks, apply VAD and frame sampling policies, send selected audio/image events to the provider adapter, and publish assistant audio/transcript/status events back into the room.
   - Alternative considered: put all realtime behavior in the REST API process. Keeping the agent as a separate worker makes runtime lifecycle and scaling clearer.

3. Default provider is Bailian, accessed through `AIProvider`.
   - Rationale: The product target is Alibaba Cloud Bailian, but an adapter interface prevents frontend and session APIs from depending on vendor-specific wire details.
   - The default implementation is `BailianRealtimeProvider`; future providers must implement the same session lifecycle, audio input, image input, control, and output event stream contracts.

4. Use REST only for session control and LiveKit data messages for realtime UI events.
   - Rationale: REST is appropriate for health, session creation, and session termination. Realtime status, transcript deltas, interruptions, cost estimates, and mode changes belong in LiveKit data messages because they are tied to the active room.

5. Perform visual sampling in the backend agent.
   - Rationale: The browser publishes camera video once to LiveKit. The backend decides when to sample frames, resize JPEGs, and send them to Bailian based on cost mode, speech activity, and visual intent.
   - Cost modes:
     - `economy`: visual frames are sent only for explicit visual requests or very low-frequency context updates.
     - `balanced`: default; VAD-enabled audio, approximately 1 FPS visual sampling during relevant interaction, JPEG max edge 1024.
     - `accurate`: higher quality and more frequent visual sampling when the user asks for visual detail.

6. Keep SDD documents as the implementation handoff.
   - Rationale: The user will run two implementation agents. `backend/sdd.md` and `frontend/sdd.md` are the stable handoff documents and must repeat the shared contracts in enough detail that agents do not need to infer cross-boundary behavior.

## Risks / Trade-offs

- [Risk] Bailian realtime API details or model capabilities vary by region/account. -> Mitigation: require `BAILIAN_REGION`, `BAILIAN_MODEL`, `BAILIAN_WORKSPACE_ID`, and `BAILIAN_REALTIME_URL` environment variables and isolate vendor details in `BailianRealtimeProvider`.
- [Risk] LiveKit plus agent worker is heavier than a direct WebSocket prototype. -> Mitigation: the architecture matches the user's chosen LiveKit pipeline and leaves room for stable media handling, later provider adapters, and separate worker scaling.
- [Risk] Vision accuracy may be poor if frames are sampled too sparsely. -> Mitigation: define mode-based sampling and allow accurate mode plus explicit visual-intent escalation.
- [Risk] Cost may grow if visual frames are sent continuously. -> Mitigation: backend-owned sampling, JPEG compression, VAD, frame-rate caps, and mode controls are required.
- [Risk] Two agents may diverge on event names or payload fields. -> Mitigation: duplicate the same REST and LiveKit data-message contracts in both SDDs.
