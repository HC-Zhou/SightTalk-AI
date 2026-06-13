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

function authHeaders(token: string, contentType = false): HeadersInit {
  return {
    ...(contentType ? { 'Content-Type': 'application/json' } : {}),
    Authorization: `Bearer ${token}`,
  };
}

export async function createLiveKitSession(
  request: CreateLiveKitSessionRequest,
  token: string,
): Promise<CreateLiveKitSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/livekit/session`, {
    method: 'POST',
    headers: authHeaders(token, true),
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
  token: string,
): Promise<EndLiveKitSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/livekit/session/${roomName}/end`, {
    method: 'POST',
    headers: authHeaders(token, true),
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return (await response.json()) as EndLiveKitSessionResponse;
}

export async function triggerMockAgentEvents(roomName: string, token: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/livekit/session/${roomName}/mock-events`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
}

export async function startLiveKitAgentSession(roomName: string, token: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/livekit/session/${roomName}/agent/start`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
}
