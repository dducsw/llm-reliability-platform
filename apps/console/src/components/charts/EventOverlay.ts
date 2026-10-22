// markLine cho policy version / proof PASS / scenario phase trên trục thời gian chung
export interface OverlayEvent {
  ts: string;
  kind: string;
  label: string;
}

const KIND_COLOR: Record<string, string> = {
  policy: "#38bdf8",
  proof: "#34d399",
  phase: "#fbbf24",
};

export function overlayMarkLine(events: OverlayEvent[] | undefined) {
  if (!events?.length) return undefined;
  return {
    symbol: "none",
    silent: true,
    label: { formatter: "{b}", color: "#cbd5e1", fontSize: 10 },
    data: events.map((e) => ({
      name: e.label,
      xAxis: new Date(e.ts).getTime(),
      lineStyle: { color: KIND_COLOR[e.kind] ?? "#94a3b8", type: "dashed" as const },
    })),
  };
}
