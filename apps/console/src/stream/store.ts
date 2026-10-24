// Topic store: cập nhật cache TanStack Query từ SSE events
import type { QueryClient } from "@tanstack/react-query";

import type { StreamEvent, StreamTopic } from "./sse";

export const QUERY_KEYS: Record<StreamTopic, readonly string[]> = {
  health: ["pulse"],
  incidents: ["incidents"],
  actions: ["actions"],
  policies: ["policies"],
  lab: ["lab"],
};

// Change Stream chỉ báo "có gì đổi"; invalidate để refetch read-model chuẩn thay vì tự vá cache
// (read-model là nguồn sự thật, tránh lệch giữa document thô và dữ liệu đã tính).
export function applyEvent(queryClient: QueryClient, event: StreamEvent): void {
  void queryClient.invalidateQueries({ queryKey: QUERY_KEYS[event.topic] });
  if (event.topic === "incidents") {
    void queryClient.invalidateQueries({ queryKey: ["pulse"] });
  }
}
