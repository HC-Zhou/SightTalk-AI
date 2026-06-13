import { API_BASE_URL } from '../../shared/config';
import type {
  ApiErrorResponse,
  CreateLiveKitSessionRequest,
  CreateLiveKitSessionResponse,
  EndLiveKitSessionRequest,
  EndLiveKitSessionResponse,
} from './types';

async function parseApiError(response: Response): Promise<Error> {
  try {
    const payload = (await response.json()) as ApiErrorResponse;
    return new Error(payload.error.message);
  } catch {
    return new Error(`Request failed with status ${response.status}`);
  }
}

export async function createLiveKitSession(
  request: CreateLiveKitSessionRequest,
): Promise<CreateLiveKitSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/livekit/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return (await response.json()) as CreateLiveKitSessionResponse;
}

export async function endLiveKitSession(
  roomName: string,
  request: EndLiveKitSessionRequest,
): Promise<EndLiveKitSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/livekit/session/${roomName}/end`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return (await response.json()) as EndLiveKitSessionResponse;
}

export async function triggerMockAgentEvents(roomName: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/livekit/session/${roomName}/mock-events`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
}

export async function startLiveKitAgentSession(roomName: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/livekit/session/${roomName}/agent/start`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
}
