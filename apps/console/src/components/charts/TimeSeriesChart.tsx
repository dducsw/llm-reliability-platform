// ECharts wrapper: một trục thời gian chung, nhiều series, overlay sự kiện
// Style quy ước: legend mảnh kiểu Grafana, phần tử phụ trợ trung tính slate — màu sắc chỉ dành cho dữ liệu có ý nghĩa.
import ReactECharts from "echarts-for-react";

import { overlayMarkLine, type OverlayEvent } from "./EventOverlay";

export interface Series {
  name: string;
  color: string;
  /** [epoch ms, value]; null = không có mẫu (đứt đoạn thay vì nội suy) */
  data: [number, number | null][];
  /** Series tham chiếu so sánh → nét đứt mảnh (vd Provider cạnh Delivered). */
  dash?: boolean;
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
    grid: { left: 48, right: 16, top: 30, bottom: 28 },
    legend: {
      top: 0,
      left: 48,
      itemGap: 20,
      // sample mảnh "— tên", không phải chấm tròn glow
      icon: "roundRect",
      itemWidth: 14,
      itemHeight: 3,
      padding: 0,
      textStyle: { color: "#94a3b8", fontSize: 11 },
    },
    tooltip: {
      trigger: "axis",
      valueFormatter: (v: number | null) => (v == null ? "—" : fmt(v)),
      backgroundColor: "#020617",
      borderColor: "#1e293b",
      textStyle: { color: "#cbd5e1", fontSize: 11 },
      axisPointer: { lineStyle: { color: "#334155" } },
    },
    xAxis: { type: "time", axisLabel: { color: "#64748b" } },
    yAxis: {
      type: "value",
      min: yMin,
      max: yMax,
      axisLabel: { color: "#64748b", formatter: (v: number) => fmt(v) },
      splitLine: { lineStyle: { color: "#1e293b" } },
    },
    series: series.map((s, i) => ({
      name: s.name,
      type: "line",
      showSymbol: false,
      connectNulls: false,
      lineStyle: { color: s.color, width: s.dash ? 1.25 : 1.75, ...(s.dash ? { type: "dashed" as const } : {}) },
      itemStyle: { color: s.color },
      emphasis: { focus: "series" },
      z: s.dash ? 2 : 3,
      data: s.data,
      // overlay chỉ cần vẽ một lần
      ...(i === 0 ? { markLine: overlayMarkLine(events) } : {}),
    })),
  };
  return <ReactECharts option={option} style={{ height }} notMerge />;
}
