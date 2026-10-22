// ECharts wrapper: một trục thời gian chung, nhiều series, overlay sự kiện
import ReactECharts from "echarts-for-react";

import { overlayMarkLine, type OverlayEvent } from "./EventOverlay";

export interface Series {
  name: string;
  color: string;
  /** [epoch ms, value]; null = không có mẫu (đứt đoạn thay vì nội suy) */
  data: [number, number | null][];
}

export function TimeSeriesChart({
  series,
  events,
  yMin,
  yMax,
  percent = false,
  height = 240,
}: {
  series: Series[];
  events?: OverlayEvent[];
  yMin?: number;
  yMax?: number;
  percent?: boolean;
  height?: number;
}) {
  const fmt = (v: number) => (percent ? `${(v * 100).toFixed(1)}%` : String(v));
  const option = {
    backgroundColor: "transparent",
    animation: false,
    grid: { left: 48, right: 16, top: 28, bottom: 28 },
    legend: { top: 0, textStyle: { color: "#94a3b8" } },
    tooltip: {
      trigger: "axis",
      valueFormatter: (v: number | null) => (v == null ? "—" : fmt(v)),
    },
    xAxis: { type: "time", axisLabel: { color: "#94a3b8" } },
    yAxis: {
      type: "value",
      min: yMin,
      max: yMax,
      axisLabel: { color: "#94a3b8", formatter: (v: number) => fmt(v) },
      splitLine: { lineStyle: { color: "#1e293b" } },
    },
    series: series.map((s, i) => ({
      name: s.name,
      type: "line",
      showSymbol: false,
      connectNulls: false,
      lineStyle: { color: s.color, width: 2 },
      itemStyle: { color: s.color },
      data: s.data,
      // overlay chỉ cần vẽ một lần
      ...(i === 0 ? { markLine: overlayMarkLine(events) } : {}),
    })),
  };
  return <ReactECharts option={option} style={{ height }} notMerge />;
}
