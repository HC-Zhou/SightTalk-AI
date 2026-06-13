import type { ClientEvent, ServerEvent } from "../types/events";
import { buildSessionWebSocketUrl, type ApiConfig } from "./apiConfig";

export type ClientStatus = "connecting" | "open" | "closed" | "error";

export type ClientTransportError = {
  stage: "parse" | "socket" | "close";
  message: string;
  code?: number;
  reason?: string;
};

export type VisionSessionClientOptions = {
  sessionId: string;
  apiConfig?: ApiConfig;
  onEvent: (event: ServerEvent) => void;
  onStatus: (status: ClientStatus) => void;
  onClientError?: (error: ClientTransportError) => void;
};

export class VisionSessionClient {
  private socket: WebSocket | null = null;

  constructor(private readonly options: VisionSessionClientOptions) {}

  connect() {
    this.options.onStatus("connecting");
    const socket = new WebSocket(
      buildSessionWebSocketUrl(this.options.sessionId, this.options.apiConfig)
    );
    this.socket = socket;
    socket.onopen = () => {
      this.options.onStatus("open");
      this.send({ type: "session.start" });
    };
    socket.onmessage = (message) => {
      try {
        const event = JSON.parse(String(message.data)) as ServerEvent;
        this.options.onEvent(event);
      } catch {
        this.reportClientError({
          stage: "parse",
          message: "Invalid WebSocket message"
        });
        this.options.onStatus("error");
      }
    };
    socket.onclose = (event) => {
      if (this.socket === socket) {
        this.socket = null;
      }

      if (event.code === 1000 || event.wasClean) {
        this.options.onStatus("closed");
        return;
      }

      this.reportClientError({
        stage: "close",
        message: "WebSocket connection closed unexpectedly",
        code: event.code,
        reason: event.reason
      });
      this.options.onStatus("error");
    };
    socket.onerror = () => {
      this.reportClientError({
        stage: "socket",
        message: "WebSocket connection error"
      });
      this.options.onStatus("error");
    };
  }

  send(event: ClientEvent): boolean {
    if (this.socket?.readyState !== WebSocket.OPEN) {
      return false;
    }

    this.socket.send(JSON.stringify(event));
    return true;
  }

  close() {
    const socket = this.socket;
    if (!socket) {
      return;
    }

    if (socket.readyState === WebSocket.OPEN) {
      const stopEvent: ClientEvent = { type: "session.stop" };
      socket.send(JSON.stringify(stopEvent));
    }
    socket.close();
  }

  private reportClientError(error: ClientTransportError) {
    this.options.onClientError?.(error);
  }
}
