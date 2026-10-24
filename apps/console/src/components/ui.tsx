import type { ReactNode } from "react";

export function Card({ title, children, className = "" }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-slate-800 bg-slate-900 p-4 ${className}`}>
      {title && <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</h2>}
      {children}
    </section>
  );
}

const TONES: Record<string, string> = {
  critical: "bg-red-500/20 text-red-300",
  warning: "bg-amber-500/20 text-amber-300",
  ok: "bg-emerald-500/20 text-emerald-300",
  info: "bg-sky-500/20 text-sky-300",
  muted: "bg-slate-700/50 text-slate-300",
};

export function Badge({ tone = "muted", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return <span className={`rounded px-2 py-0.5 text-xs ${TONES[tone]}`}>{children}</span>;
}

export function statusTone(status: string): keyof typeof TONES {
  if (["resolved", "mitigated", "succeeded"].includes(status)) return "ok";
  if (["detected", "failed", "rejected"].includes(status)) return "critical";
  if (["awaiting_approval", "investigating", "mitigating", "proposed"].includes(status)) return "warning";
  return "muted";
}

export function QueryState({ isLoading, error, children }: { isLoading: boolean; error: unknown; children: ReactNode }) {
  if (isLoading) return <p className="text-slate-400">Đang tải…</p>;
  if (error) return <p className="text-red-300">Lỗi: {error instanceof Error ? error.message : String(error)}</p>;
  return <>{children}</>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-slate-500">{children}</p>;
}
