// SSE client cho /api/stream?topics=… (EventSource, tự reconnect với Last-Event-ID)
export type StreamTopic = "health" | "incidents" | "actions" | "policies" | "lab";

export interface StreamEvent<T = unknown> {
  topic: StreamTopic;
  op: "insert" | "update" | "replace" | "delete";
  doc: T;
}

export function subscribe(topics: StreamTopic[], onEvent: (e: StreamEvent) => void): () => void {
  void topics;
  void onEvent;
  throw new Error("not implemented");
}
