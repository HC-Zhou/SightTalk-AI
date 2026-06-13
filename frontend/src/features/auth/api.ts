import { API_BASE_URL } from '../../shared/config';
import type { ApiErrorResponse } from '../session/types';
import type { AuthCredentials, AuthResponse, AuthUser } from './types';

async function parseApiError(response: Response): Promise<Error> {
  try {
    const payload = (await response.json()) as ApiErrorResponse;
    return new Error(payload.error.message);
  } catch {
    return new Error(`Request failed with status ${response.status}`);
  }
}

export async function registerUser(credentials: AuthCredentials): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return (await response.json()) as AuthResponse;
}

export async function loginUser(credentials: AuthCredentials): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return (await response.json()) as AuthResponse;
}

export async function getCurrentUser(token: string): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
    method: 'GET',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return (await response.json()) as AuthUser;
}
