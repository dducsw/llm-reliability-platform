// markLine cho policy version / proof PASS / scenario phase trên trục thời gian chung
// Quy ước "trầm": cùng họ slate, phân biệt loại bằng tông xám sậm — nhãn small, không màu neon.
export interface OverlayEvent {
  ts: string;
  kind: string;
  label: string;
}

const KIND_COLOR: Record<string, string> = {
  policy: "#546073",
  proof: "#0e7a5f",
  phase: "#a16207",
};

export function overlayMarkLine(events: OverlayEvent[] | undefined) {
  if (!events?.length) return undefined;
  return {
    symbol: "none",
    silent: true,
    label: { formatter: "{b}", color: "#64748b", fontSize: 9 },
    data: events.map((e) => ({
      name: e.label,
      xAxis: new Date(e.ts).getTime(),
      lineStyle: {
        color: KIND_COLOR[e.kind] ?? "#475569",
        type: "dashed" as const,
        width: 1,
        dashOffset: 2,
      },
    })),
  };
}
