// Provider vs Delivered — "money shot": vendor tệ đi nhưng người dùng vẫn nhận kết quả tốt
import type { LedgerPoint } from "../../api/types";
import type { OverlayEvent } from "./EventOverlay";
import { TimeSeriesChart, type Series } from "./TimeSeriesChart";

export type LedgerMetric = "availability" | "quality";

export function ratio(p: LedgerPoint, metric: LedgerMetric): number | null {
  const [good, n] = metric === "availability" ? [p.ok, p.total] : [p.q_good, p.q_eligible];
  return n > 0 ? good / n : null;
}

const toSeries = (name: string, color: string, pts: LedgerPoint[], metric: LedgerMetric): Series => ({
  name,
  color,
  data: pts.map((p) => [new Date(p.ts).getTime(), ratio(p, metric)]),
});

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
  return (
    <TimeSeriesChart
      percent
      yMax={1}
      series={[
        toSeries("Delivered (người dùng nhận)", "#34d399", delivered, metric),
        toSeries("Provider (vendor trả về)", "#f87171", provider, metric),
      ]}
      events={events}
    />
  );
}
