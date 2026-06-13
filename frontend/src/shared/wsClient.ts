import type { ClientEvent, ServerEvent } from "../types/events";

export type ClientStatus = "connecting" | "open" | "closed" | "error";

export type VisionSessionClientOptions = {
  url: string;
  onEvent: (event: ServerEvent) => void;
  onStatus: (status: ClientStatus) => void;
};

export class VisionSessionClient {
  private socket: WebSocket | null = null;

  constructor(private readonly options: VisionSessionClientOptions) {}

  connect() {
    this.options.onStatus("connecting");
    this.socket = new WebSocket(this.options.url);
    this.socket.onopen = () => {
      this.options.onStatus("open");
      this.send({ type: "session.start" });
    };
    this.socket.onmessage = (message) => {
      const event = JSON.parse(message.data as string) as ServerEvent;
      this.options.onEvent(event);
    };
    this.socket.onclose = () => this.options.onStatus("closed");
    this.socket.onerror = () => this.options.onStatus("error");
  }

  send(event: ClientEvent) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(event));
    }
  }

  close() {
    this.socket?.close();
  }
}
