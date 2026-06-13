import { describe, expect, it, vi } from "vitest";
import { VisionSessionClient } from "../src/shared/wsClient";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  readyState = FakeWebSocket.OPEN;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }

  send(payload: string) {
    this.sent.push(payload);
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
  }
}

describe("VisionSessionClient", () => {
  it("connects, sends start, and parses server events", () => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    FakeWebSocket.instances = [];
    const events: string[] = [];
    const client = new VisionSessionClient({
      url: "ws://localhost:8000/ws/session/test",
      onEvent: (event) => events.push(event.type),
      onStatus: (status) => events.push(status)
    });

    client.connect();
    const socket = FakeWebSocket.instances[0];
    socket.onopen?.();
    socket.onmessage?.({ data: JSON.stringify({ type: "assistant.thinking" }) });

    expect(socket.sent[0]).toBe(JSON.stringify({ type: "session.start" }));
    expect(events).toEqual(["connecting", "open", "assistant.thinking"]);
  });
});
