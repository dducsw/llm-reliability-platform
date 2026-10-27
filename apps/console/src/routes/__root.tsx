import { Link, Outlet } from "@tanstack/react-router";

import { useLiveTopics } from "../api/hooks";

const NAV = [
  { to: "/", label: "Pulse" },
  { to: "/incidents", label: "Incidents" },
  { to: "/approvals", label: "Approvals" },
  { to: "/memory", label: "Memory" },
  { to: "/policies", label: "Policies" },
  { to: "/lab", label: "Chaos Lab" },
  { to: "/explain", label: "Query Explorer" },
] as const;

// ?present=1: chữ to hơn khi quay video
const presenting = new URLSearchParams(window.location.search).get("present") === "1";

export function RootLayout() {
  useLiveTopics(["health", "incidents", "actions", "policies", "lab", "replays"]);
  return (
    <div className={`min-h-screen bg-slate-950 text-slate-100 ${presenting ? "text-lg" : "text-sm"}`}>
      <header className="flex items-center gap-6 border-b border-slate-800 px-6 py-3">
        <span className="font-semibold tracking-wide">Reflex</span>
        <nav className="flex gap-4">
          {NAV.map((n) => (
            <Link key={n.to} to={n.to} className="text-slate-400 hover:text-white [&.active]:text-white">
              {n.label}
            </Link>
          ))}
        </nav>
        <span className="ml-auto rounded bg-amber-500/20 px-2 py-0.5 text-xs text-amber-300">DEMO PROFILE</span>
      </header>
      <main className="p-6">
        <Outlet />
      </main>
    </div>
  );
}
