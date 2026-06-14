import { API_BASE_URL } from '../../shared/config';
import type { ApiErrorResponse } from '../session/types';
import type {
  ConversationArchive,
  ConversationArchiveResponse,
  ConversationListResponse,
  SaveConversationRequest,
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

export async function listConversations(token: string): Promise<ConversationArchive[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/conversations`, {
    method: 'GET',
    headers: authHeaders(token),
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
  const payload = (await response.json()) as ConversationListResponse;
  return payload.conversations.map(normalizeConversation);
}

export async function saveConversation(
  request: SaveConversationRequest,
  token: string,
): Promise<ConversationArchive> {
  const response = await fetch(`${API_BASE_URL}/api/v1/conversations`, {
    method: 'POST',
    headers: authHeaders(token, true),
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return normalizeConversation((await response.json()) as ConversationArchiveResponse);
}

function normalizeConversation(response: ConversationArchiveResponse): ConversationArchive {
  return {
    id: response.id,
    title: response.title,
    createdAt: response.created_at,
    endedAt: response.ended_at,
    messages: response.messages,
  };
}
