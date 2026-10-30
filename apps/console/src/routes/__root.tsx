import { Link, Outlet } from "@tanstack/react-router";

import { useLiveTopics } from "../api/hooks";
import { DemoClock } from "../components/DemoClock";
import { presenting } from "../present";

const NAV = [
  { to: "/", label: "Pulse" },
  { to: "/incidents", label: "Incidents" },
  { to: "/approvals", label: "Approvals" },
  { to: "/slos", label: "SLOs" },
  { to: "/memory", label: "Memory" },
  { to: "/policies", label: "Policies" },
  { to: "/lab", label: "Chaos Lab" },
  { to: "/explain", label: "Query Explorer" },
] as const;

export function RootLayout() {
  useLiveTopics(["health", "incidents", "actions", "policies", "lab", "replays"]);
  return (
    <div className={`min-h-screen bg-slate-950 text-slate-200 ${presenting ? "text-lg" : ""}`}>
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex h-12 max-w-screen-2xl items-center gap-5 px-6">
          <Link to="/" className="flex items-baseline gap-2" aria-label="Trang chủ Reflex">
            <span className="font-semibold text-slate-100">Reflex</span>
          </Link>
          <nav className="flex items-center gap-0.5">
            {NAV.map((n) => (
              <Link
                key={n.to}
                to={n.to}
                className="rounded px-2.5 py-1 text-slate-400 transition-colors hover:bg-slate-800/60 hover:text-slate-100 [&.active]:bg-slate-800 [&.active]:text-slate-50"
              >
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center">
            <DemoClock />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-screen-2xl px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
