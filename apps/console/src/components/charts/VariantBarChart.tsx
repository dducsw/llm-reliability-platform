// Delivered quality theo variant, kèm thanh sai số CI 90% (Time Machine)
import ReactECharts from "echarts-for-react";

import type { VariantResult } from "../../api/types";

const HIGHLIGHT = "reflex_recorded";

export function VariantBarChart({ variants, objective }: { variants: [string, VariantResult][]; objective?: number }) {
  const names = variants.map(([n]) => n);
  const values = variants.map(([, v]) => v.delivered_quality);
  const lo = Math.max(0, Math.min(...values.map((v, i) => v - variants[i][1].quality_ci_90)) - 0.05);
  const option = {
    backgroundColor: "transparent",
    animation: false,
    grid: { left: 140, right: 48, top: 12, bottom: 28 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (v: number) => `${(v * 100).toFixed(1)}%`,
    },
    xAxis: {
      type: "value",
      min: Number(lo.toFixed(2)),
      max: 1,
      axisLabel: { color: "#94a3b8", formatter: (v: number) => `${Math.round(v * 100)}%` },
      splitLine: { lineStyle: { color: "#1e293b" } },
    },
    yAxis: { type: "category", data: names, inverse: true, axisLabel: { color: "#cbd5e1", fontFamily: "monospace" } },
    series: [
      {
        type: "bar",
        name: "Delivered quality",
        barMaxWidth: 22,
        data: variants.map(([n, v]) => ({
          value: v.delivered_quality,
          itemStyle: { color: n === HIGHLIGHT ? "#34d399" : "#64748b", borderRadius: [0, 3, 3, 0] },
        })),
        label: {
          show: true,
          position: "right",
          color: "#cbd5e1",
          formatter: (p: { value: number }) => `${(p.value * 100).toFixed(1)}%`,
        },
        markLine: objective
          ? {
              symbol: "none",
              label: { color: "#fbbf24", formatter: "SLO" },
              lineStyle: { color: "#fbbf24", type: "dashed" },
              data: [{ xAxis: objective }],
            }
          : undefined,
      },
    ],
  };
  return <ReactECharts option={option} style={{ height: 56 + names.length * 40 }} notMerge />;
}
