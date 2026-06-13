export type ApiConfig = {
  apiOrigin: string;
  wsOrigin: string;
};

export type ApiEnv = {
  VITE_API_ORIGIN?: string;
};

const DEFAULT_API_ORIGIN = "http://127.0.0.1:8000";

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function deriveWebSocketOrigin(apiOrigin: string): string {
  const url = new URL(apiOrigin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return trimTrailingSlash(url.toString());
}

export function createApiConfig(env: ApiEnv = import.meta.env): ApiConfig {
  const apiOrigin = trimTrailingSlash(env.VITE_API_ORIGIN?.trim() || DEFAULT_API_ORIGIN);
  return {
    apiOrigin,
    wsOrigin: deriveWebSocketOrigin(apiOrigin)
  };
}

export function buildSessionWebSocketUrl(sessionId: string, config = createApiConfig()): string {
  return `${config.wsOrigin}/ws/session/${encodeURIComponent(sessionId)}`;
}

export function resolveApiAssetUrl(pathOrUrl: string, config = createApiConfig()): string {
  return new URL(pathOrUrl, `${config.apiOrigin}/`).toString();
}
