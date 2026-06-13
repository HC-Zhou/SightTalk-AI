import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApiConfig } from "../src/shared/apiConfig";
import { VisionSessionClient } from "../src/shared/wsClient";

class FakeWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  readyState = FakeWebSocket.CONNECTING;
  sent: string[] = [];
  closeCalls: Array<{ code?: number; reason?: string }> = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: ((event: { code: number; reason: string; wasClean: boolean }) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(public readonly url: string) {
    FakeWebSocket.instances.push(this);
  }

  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }

  receive(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }

  receiveRaw(data: string) {
    this.onmessage?.({ data });
  }

  send(payload: string) {
    this.sent.push(payload);
  }

  close(code = 1000, reason = "") {
    this.readyState = FakeWebSocket.CLOSED;
    this.closeCalls.push({ code, reason });
    this.onclose?.({ code, reason, wasClean: code === 1000 });
  }
}

describe("VisionSessionClient", () => {
  beforeEach(() => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    FakeWebSocket.instances = [];
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("builds the session URL, connects, sends start, and parses server events", () => {
    const events: string[] = [];
    const statuses: string[] = [];
    const client = new VisionSessionClient({
      sessionId: "demo/session",
      apiConfig: createApiConfig({ VITE_API_ORIGIN: "https://api.example.com/" }),
      onEvent: (event) => events.push(event.type),
      onStatus: (status) => statuses.push(status)
    });

    client.connect();
    const socket = FakeWebSocket.instances[0];
    expect(socket.url).toBe("wss://api.example.com/ws/session/demo%2Fsession");
    expect(statuses).toEqual(["connecting"]);

    socket.open();
    socket.receive({ type: "assistant.thinking" });

    expect(socket.sent[0]).toBe(JSON.stringify({ type: "session.start" }));
    expect(events).toEqual(["assistant.thinking"]);
    expect(statuses).toEqual(["connecting", "open"]);
  });

  it("returns whether client events were sent", () => {
    const client = new VisionSessionClient({
      sessionId: "demo",
      apiConfig: createApiConfig({}),
      onEvent: vi.fn(),
      onStatus: vi.fn()
    });

    client.connect();
    const socket = FakeWebSocket.instances[0];

    expect(client.send({ type: "playback.done" })).toBe(false);

    socket.open();
    expect(client.send({ type: "playback.done" })).toBe(true);
    expect(socket.sent[socket.sent.length - 1]).toBe(JSON.stringify({ type: "playback.done" }));

    socket.close();
    expect(client.send({ type: "playback.done" })).toBe(false);
  });

  it("reports invalid JSON as a client error without throwing", () => {
    const statuses: string[] = [];
    const errors: string[] = [];
    const client = new VisionSessionClient({
      sessionId: "demo",
      apiConfig: createApiConfig({}),
      onEvent: vi.fn(),
      onStatus: (status) => statuses.push(status),
      onClientError: (error) => errors.push(`${error.stage}:${error.message}`)
    });

    client.connect();
    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].receiveRaw("{broken json");

    expect(statuses[statuses.length - 1]).toBe("error");
    expect(errors[0]).toContain("parse:Invalid WebSocket message");
  });

  it("sends session stop before closing an open socket", () => {
    const statuses: string[] = [];
    const client = new VisionSessionClient({
      sessionId: "demo",
      apiConfig: createApiConfig({}),
      onEvent: vi.fn(),
      onStatus: (status) => statuses.push(status)
    });

    client.connect();
    const socket = FakeWebSocket.instances[0];
    socket.open();

    client.close();

    expect(socket.sent[socket.sent.length - 1]).toBe(JSON.stringify({ type: "session.stop" }));
    expect(socket.closeCalls).toEqual([{ code: 1000, reason: "" }]);
    expect(statuses[statuses.length - 1]).toBe("closed");
  });
});
