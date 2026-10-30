// Provider vs Delivered — "money shot": vendor tệ đi nhưng người dùng vẫn nhận kết quả tốt
import type { LedgerPoint } from "../../api/types";
import type { OverlayEvent } from "./EventOverlay";
import { TimeSeriesChart, type Series } from "./TimeSeriesChart";

export type LedgerMetric = "availability" | "quality";

export function ratio(p: LedgerPoint, metric: LedgerMetric): number | null {
  const [good, n] = metric === "availability" ? [p.ok, p.total] : [p.q_good, p.q_eligible];
  return n > 0 ? good / n : null;
}

const toPoints = (pts: LedgerPoint[], metric: LedgerMetric): Series["data"] =>
  pts.map((p) => [new Date(p.ts).getTime(), ratio(p, metric)]);

export function DualLedgerChart({
  delivered,
  provider,
  events,
  metric,
}: {
  delivered: LedgerPoint[];
  provider: LedgerPoint[];
  events?: OverlayEvent[];
  metric: LedgerMetric;
}) {
  // Delivered = SLI chính (solid); Provider = tham chiếu vendor (dashed, trung tính).
  // Màu đỏ/đậm để dành cho trạng thái lỗi ở badge — không tô luôn trên đường biểu đồ.
  const series: Series[] = [
    { name: "Delivered", color: "#10b981", data: toPoints(delivered, metric) },
    { name: "Provider", color: "#64748b", dash: true, data: toPoints(provider, metric) },
  ];

  return <TimeSeriesChart percent yMax={1} series={series} events={events} />;
}

