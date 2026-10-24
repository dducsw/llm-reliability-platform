// SSE client cho /api/stream?topics=… (EventSource tự reconnect và gửi Last-Event-ID)
export type StreamTopic = "health" | "incidents" | "actions" | "policies" | "lab";

export interface StreamEvent<T = unknown> {
  topic: StreamTopic;
  op: "insert" | "update" | "replace" | "delete";
  doc: T;
}

export function subscribe(topics: StreamTopic[], onEvent: (e: StreamEvent) => void): () => void {
  const source = new EventSource(`/api/stream?topics=${topics.join(",")}`);
  source.addEventListener("change", (msg) => {
    try {
      onEvent(JSON.parse((msg as MessageEvent<string>).data) as StreamEvent);
    } catch {
      // frame hỏng: bỏ qua, frame sau vẫn xử lý được
    }
  });
  return () => source.close();
}
