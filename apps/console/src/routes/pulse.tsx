// Pulse — health theo route/target, Delivered vs Provider, budget, incident đang mở
import { Link } from "@tanstack/react-router";
import { lazy, Suspense, useState } from "react";

import { useDualLedger, usePulse } from "../api/hooks";
import type { LedgerMetric } from "../components/charts/DualLedgerChart";
import { Badge, Card, Empty, QueryState, statusTone } from "../components/ui";

// ECharts nặng: chỉ tải khi Pulse thực sự vẽ biểu đồ
const DualLedgerChart = lazy(() =>
  import("../components/charts/DualLedgerChart").then((m) => ({ default: m.DualLedgerChart })),
);

function DualLedgerCard({ routes }: { routes: string[] }) {
  const [picked, setPicked] = useState<string>();
  const [metric, setMetric] = useState<LedgerMetric>("quality");
  const route = picked ?? routes[0];
  const { data, isLoading, error } = useDualLedger(route);
  const hasData = Boolean(data?.delivered.length || data?.provider.length);
  return (
    <Card title="Delivered vs Provider" className="lg:col-span-3">
      <div className="mb-2 flex flex-wrap gap-2 text-sm">
        <select className="rounded bg-slate-800 px-2 py-1" value={route ?? ""} onChange={(e) => setPicked(e.target.value)}>
          {routes.map((r) => (
            <option key={r}>{r}</option>
          ))}
        </select>
        <select className="rounded bg-slate-800 px-2 py-1" value={metric} onChange={(e) => setMetric(e.target.value as LedgerMetric)}>
          <option value="quality">Chất lượng (schema-valid)</option>
          <option value="availability">Khả dụng</option>
        </select>
        {data && <span className="text-slate-500">Provider = {data.targets.join(" + ") || "—"} · 60 phút gần nhất</span>}
      </div>
      <QueryState isLoading={isLoading && Boolean(route)} error={error}>
        {hasData && data ? (
          <Suspense fallback={<Empty>Đang tải biểu đồ…</Empty>}>
            <DualLedgerChart delivered={data.delivered} provider={data.provider} events={data.events} metric={metric} />
          </Suspense>
        ) : (
          <Empty>Chưa có sli_1m cho route này (cần chạy rollup A1/A2).</Empty>
        )}
      </QueryState>
    </Card>
  );
}

export function PulsePage() {
  const { data, isLoading, error } = usePulse();
  return (
    <QueryState isLoading={isLoading} error={error}>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Incident đang mở" className="lg:col-span-2">
          {data?.incidents.length ? (
            <ul className="space-y-2">
              {data.incidents.map((i) => (
                <li key={i.key} className="flex items-center gap-3">
                  <Link to="/incidents/$key" params={{ key: i.key }} className="font-mono text-sky-400 hover:underline">
                    {i.key}
                  </Link>
                  <Badge tone={statusTone(i.status)}>{i.status}</Badge>
                  <span className="text-slate-400">
                    {i.sli} · {i.target ?? "—"} → {i.routes.join(", ")}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>Không có incident nào đang mở.</Empty>
          )}
        </Card>
        <Card title="Health">
          {data?.health.length ? (
            <ul className="space-y-1">
              {data.health.map((h) => (
                <li key={h._id} className="flex justify-between">
                  <span className="font-mono">{h._id}</span>
                  <Badge tone={h.status === "healthy" ? "ok" : h.status ? "warning" : "muted"}>{h.status ?? "unknown"}</Badge>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>Chưa có health_state (Sentinel chưa chạy).</Empty>
          )}
        </Card>
        <DualLedgerCard routes={data?.policies.map((p) => p._id) ?? []} />
        <Card title="Router weights" className="lg:col-span-3">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {data?.policies.map((p) => (
              <div key={p._id}>
                <div className="mb-1 font-mono">
                  {p._id} <span className="text-slate-500">v{p.version}</span>
                </div>
                {p.candidates.map((c) => (
                  <div key={c.target} className="flex items-center gap-2">
                    <div className="h-2 rounded bg-sky-500" style={{ width: `${Math.round(c.weight * 100)}px` }} />
                    <span className="text-xs text-slate-400">
                      {c.target} {Math.round(c.weight * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </Card>
      </div>
    </QueryState>
  );
}
