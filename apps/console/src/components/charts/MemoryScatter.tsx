// Bản đồ tương đồng: mỗi điểm là một incident, màu theo SLI, viền theo kết quả action
import ReactECharts from "echarts-for-react";

import type { MemoryPoint } from "../../api/types";

const SLI_COLORS: Record<string, string> = {
  quality: "#a78bfa",
  availability: "#38bdf8",
  latency: "#fbbf24",
  ttft: "#fb923c",
};

export function MemoryScatter({
  points,
  selected,
  onSelect,
}: {
  points: MemoryPoint[];
  selected?: string;
  onSelect: (key: string) => void;
}) {
  const bySli = new Map<string, MemoryPoint[]>();
  for (const p of points) bySli.set(p.sli, [...(bySli.get(p.sli) ?? []), p]);

  const option = {
    backgroundColor: "transparent",
    animation: false,
    grid: { left: 24, right: 24, top: 32, bottom: 24 },
    legend: { top: 0, textStyle: { color: "#94a3b8" } },
    tooltip: {
      formatter: (p: { data: { key: string; action?: MemoryPoint["action"]; target?: string | null } }) =>
        `${p.data.key}<br/>${p.data.target ?? ""}${p.data.action ? `<br/>${p.data.action.type} ${p.data.action.verdict ?? ""}` : ""}`,
    },
    xAxis: { type: "value", show: false, scale: true },
    yAxis: { type: "value", show: false, scale: true },
    series: [...bySli.entries()].map(([sli, pts]) => ({
      name: sli,
      type: "scatter",
      symbolSize: (_: unknown, p: { data: { key: string } }) => (p.data.key === selected ? 18 : 10),
      itemStyle: { color: SLI_COLORS[sli] ?? "#94a3b8" },
      data: pts.map((p) => ({
        value: [p.x, p.y],
        key: p.key,
        action: p.action,
        target: p.target,
        itemStyle:
          p.key === selected
            ? { borderColor: "#f8fafc", borderWidth: 2 }
            : p.action?.verdict === "FAIL"
              ? { borderColor: "#f87171", borderWidth: 1.5 }
              : undefined,
      })),
    })),
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: 460 }}
      notMerge
      onEvents={{ click: (e: { data?: { key?: string } }) => e.data?.key && onSelect(e.data.key) }}
    />
  );
}
