// Primitives dùng chung: Card, Button, Select, Badge, Meter, QueryState…
// Mọi route chỉ dùng các building block ở đây để giao diện nhất quán.
import type {
  ButtonHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

export function Card({
  title,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-header">
          <h2 className="card-title">{title}</h2>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="card-body">{children}</div>
    </section>
  );
}

const BUTTON_VARIANTS = {
  primary: "bg-sky-600 text-white hover:bg-sky-500 focus-visible:ring-sky-400",
  success:
    "bg-emerald-600 text-white hover:bg-emerald-500 focus-visible:ring-emerald-400",
  ghost:
    "border border-slate-700 bg-transparent text-slate-300 hover:bg-slate-800 hover:text-slate-100 focus-visible:ring-slate-400",
  danger:
    "border border-red-500/40 bg-transparent text-red-300 hover:bg-red-500/10 hover:text-red-200 focus-visible:ring-red-400",
} as const;

export function Button({
  variant = "ghost",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof BUTTON_VARIANTS;
}) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium
        transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950
        disabled:pointer-events-none disabled:opacity-40 ${BUTTON_VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}

export function Select({
  className = "",
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <span className="relative inline-flex">
      <select className={`field appearance-none pr-7 ${className}`} {...props} />
      <svg
        aria-hidden
        viewBox="0 0 16 16"
        className="pointer-events-none absolute right-2 top-1/2 h-3 w-3 -translate-y-1/2 text-slate-500"
      >
        <path
          d="M4 6l4 4 4-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}

const TONES = {
  critical: "bg-red-500/10 text-red-300 ring-red-500/30",
  warning: "bg-amber-500/10 text-amber-300 ring-amber-500/30",
  ok: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
  info: "bg-sky-500/10 text-sky-300 ring-sky-500/30",
  muted: "bg-slate-500/10 text-slate-400 ring-slate-500/30",
};

export function Badge({
  tone = "muted",
  dot = false,
  children,
}: {
  tone?: keyof typeof TONES;
  /** Dot trạng thái chỉ dùng khi hàng không có gì khác encode màu (status text đủ rồi). */
  dot?: boolean;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] ring-1 ring-inset ${TONES[tone]}`}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current opacity-60" />}
      {children}
    </span>
  );
}

export function statusTone(status: string): keyof typeof TONES {
  if (["resolved", "mitigated", "succeeded"].includes(status)) return "ok";
  if (["detected", "failed", "rejected"].includes(status)) return "critical";
  if (["awaiting_approval", "investigating", "mitigating", "proposed"].includes(status))
    return "warning";
  return "muted";
}

export function Spinner() {
  return (
    <span
      aria-hidden
      className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-600 border-t-sky-400"
    />
  );
}

export function QueryState({
  isLoading,
  error,
  children,
}: {
  isLoading: boolean;
  error: unknown;
  children: ReactNode;
}) {
  if (isLoading)
    return (
      <p className="flex items-center gap-2 text-slate-400">
        <Spinner /> Đang tải…
      </p>
    );
  if (error)
    return (
      <p className="rounded border border-red-500/30 bg-red-500/5 px-3 py-2 text-red-300">
        {error instanceof Error ? error.message : String(error)}
      </p>
    );
  return <>{children}</>;
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded border border-dashed border-slate-800 px-3 py-4 text-center text-slate-500">
      {children}
    </p>
  );
}

/** Thanh phần trăm (router weights, policy weights…): tile nền + phần fill. */
export function Meter({
  ratio,
  tone = "bg-sky-500",
  className = "",
}: {
  ratio: number;
  tone?: string;
  className?: string;
}) {
  return (
    <span
      className={`block h-1.5 overflow-hidden rounded-full bg-slate-700/60 ${className}`}
    >
      <span
        className={`block h-full rounded-full ${tone}`}
        style={{ width: `${Math.max(0, Math.min(1, ratio)) * 100}%` }}
      />
    </span>
  );
}
