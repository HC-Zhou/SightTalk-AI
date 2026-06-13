import { describe, expect, it } from "vitest";
import {
  buildSessionWebSocketUrl,
  createApiConfig,
  resolveApiAssetUrl
} from "../src/shared/apiConfig";

describe("apiConfig", () => {
  it("uses localhost defaults for development", () => {
    const config = createApiConfig({});

    expect(config.apiOrigin).toBe("http://127.0.0.1:8000");
    expect(config.wsOrigin).toBe("ws://127.0.0.1:8000");
  });

  it("derives secure websocket origin from https API origin", () => {
    const config = createApiConfig({ VITE_API_ORIGIN: "https://api.example.com/" });

    expect(config.apiOrigin).toBe("https://api.example.com");
    expect(config.wsOrigin).toBe("wss://api.example.com");
  });

  it("builds encoded session websocket URLs", () => {
    const config = createApiConfig({ VITE_API_ORIGIN: "https://api.example.com" });

    expect(buildSessionWebSocketUrl("demo/session", config)).toBe(
      "wss://api.example.com/ws/session/demo%2Fsession"
    );
  });

  it("resolves relative API assets against the HTTP origin", () => {
    const config = createApiConfig({ VITE_API_ORIGIN: "https://api.example.com" });

    expect(resolveApiAssetUrl("/api/v1/audio/a.wav", config)).toBe(
      "https://api.example.com/api/v1/audio/a.wav"
    );
    expect(resolveApiAssetUrl("https://cdn.example.com/a.wav", config)).toBe(
      "https://cdn.example.com/a.wav"
    );
  });
});
