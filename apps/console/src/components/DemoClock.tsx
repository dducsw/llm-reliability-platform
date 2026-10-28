// Demo clock: giờ thật + "DEMO TIME ×N" khi scenario chạy --fast (giờ trong kịch bản trôi nhanh N lần)
import { useEffect, useState } from "react";

import { useDemo } from "../api/hooks";

const hhmmss = (d: Date) => d.toLocaleTimeString("vi-VN", { hour12: false });

function elapsed(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h ? `${h}h${String(m).padStart(2, "0")}m` : `${m}m${String(s % 60).padStart(2, "0")}s`;
}

export function DemoClock() {
  const { data } = useDemo();
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const scale = data?.time_scale ?? 1;
  const started = data?.run?.started_at ? new Date(data.run.started_at) : null;
  const demoElapsed = started ? (now.getTime() - started.getTime()) * scale : null;

  return (
    <div className="flex items-center gap-3 font-mono text-xs tabular-nums">
      <span className="text-slate-300">{hhmmss(now)}</span>
      {scale !== 1 && <span className="rounded bg-fuchsia-500/20 px-2 py-0.5 text-fuchsia-300">DEMO TIME ×{scale}</span>}
      {data?.run && demoElapsed != null && (
        <span className="text-slate-400">
          {data.run.scenario} · phase {data.run.phase_index} · T+{elapsed(demoElapsed)}
        </span>
      )}
    </div>
  );
}
