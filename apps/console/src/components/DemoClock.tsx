// Đồng hồ hệ thống trên header; phần trạng thái chạy demo nằm trong War Room, không phải nav.
import { useEffect, useState } from "react";

const hhmmss = (d: Date) => d.toLocaleTimeString("vi-VN", { hour12: false });

export function DemoClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  return <span className="font-mono text-xs tabular-nums text-slate-300">{hhmmss(now)}</span>;
}
