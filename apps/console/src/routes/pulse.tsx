// Pulse — health theo route/target, Delivered vs Provider, budget, incident đang mở
import { Link } from "@tanstack/react-router";
import { lazy, Suspense, useState } from "react";

import { useDualLedger, usePulse } from "../api/hooks";
import type { PulseKpis } from "../api/types";
import type { LedgerMetric } from "../components/charts/DualLedgerChart";
import { Badge, Card, Empty, Meter, QueryState, Select, Spinner, statusTone } from "../components/ui";

// ECharts nặng: chỉ tải khi Pulse thực sự vẽ biểu đồ
const DualLedgerChart = lazy(() =>
  import("../components/charts/DualLedgerChart").then((m) => ({ default: m.DualLedgerChart })),
);

const pct = (v: number | null | undefined) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);
const dur = (s: number | null | undefined) => {
  if (s == null) return "—";
  if (s < 60) return `${Math.round(s)}s`;
  return `${Math.floor(s / 60)}m${String(Math.round(s % 60)).padStart(2, "0")}s`;
};
const money = (v: number) => `$${v.toFixed(2)}`;
const compact = (v: number) => (v >= 1000 ? `${(v / 1000).toFixed(v >= 100_000 ? 0 : 1)}k` : String(v));

function KpiTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-900 px-4 py-3">
      <div className="section-label">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums text-slate-50">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

function KpiStrip({ kpis }: { kpis?: PulseKpis | null }) {
  const kpisToday = kpis;
  const tokens = (kpisToday?.tokens_in_today ?? 0) + (kpisToday?.tokens_out_today ?? 0);
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <KpiTile label="Delivered quality" value={pct(kpis?.quality)} hint="60 phút · schema-valid" />
      <KpiTile label="Availability" value={pct(kpis?.availability)} hint="60 phút · kết quả tốt cho người dùng" />
      <KpiTile label="MTTD · MTTR" value={`${dur(kpis?.mttd_p50_s)} · ${dur(kpis?.mttr_p50_s)}`} hint="p50 · 7 ngày qua (A17)" />
      <KpiTile
        label="Chi phí hôm nay"
        value={money(kpisToday?.cost_usd_today ?? 0)}
        hint={
          kpisToday
            ? `${compact(tokens)} token · ${compact(kpisToday.requests_today)} req · VN day (A18)`
            : "chưa có dữ liệu"
        }
      />
    </div>
  );
}

function DualLedgerCard({ routes }: { routes: string[] }) {
  const [picked, setPicked] = useState<string>();
  const [metric, setMetric] = useState<LedgerMetric>("quality");
  const route = picked ?? routes[0];
  const { data, isLoading, error } = useDualLedger(route);
  const hasData = Boolean(data?.delivered.length || data?.provider.length);
  return (
    <Card
      title="Delivered vs Provider"
      className="lg:col-span-3"
      actions={
        data && <span className="glass text-xs">Provider = {data.targets.join(" + ") || "—"} · 60 phút gần nhất</span>
      }
    >
      <div className="mb-3 flex flex-wrap gap-2">
        <Select value={route ?? ""} onChange={(e) => setPicked(e.target.value)} aria-label="Route">
          {routes.map((r) => (
            <option key={r}>{r}</option>
          ))}
        </Select>
        <Select
          value={metric}
          onChange={(e) => setMetric(e.target.value as LedgerMetric)}
          aria-label="Chỉ số"
        >
          <option value="quality">Chất lượng (schema-valid)</option>
          <option value="availability">Khả dụng</option>
        </Select>
      </div>
      <QueryState isLoading={isLoading && Boolean(route)} error={error}>
        {hasData && data ? (
          <Suspense
            fallback={
              <p className="flex items-center gap-2 text-slate-400">
                <Spinner /> Đang tải biểu đồ…
              </p>
            }
          >
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
      <div className="space-y-4">
        <KpiStrip kpis={data?.kpis} />
        <div className="grid gap-4 lg:grid-cols-3">
          <Card title="Incident đang mở" className="lg:col-span-2">
            {data?.incidents.length ? (
              <ul className="divide-y divide-slate-800/60">
                {data.incidents.map((i) => (
                  <li key={i.key} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 first:pt-0 last:pb-0">
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
              <ul className="divide-y divide-slate-800/60">
                {data.health.map((h) => (
                  <li key={h._id} className="flex justify-between py-2 first:pt-0 last:pb-0">
                    <span className="font-mono">{h._id}</span>
                    <Badge tone={h.status === "healthy" ? "ok" : h.status ? "warning" : "muted"}>
                      {h.status ?? "unknown"}
                    </Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>Chưa có health_state (Sentinel chưa chạy).</Empty>
            )}
          </Card>
          <DualLedgerCard routes={data?.policies.map((p) => p._id) ?? []} />
          <Card title="Router weights" className="lg:col-span-3">
            <div className="grid gap-x-6 gap-y-4 md:grid-cols-2 lg:grid-cols-3">
              {data?.policies.map((p) => (
                <div key={p._id}>
                  <div className="mb-1.5 flex items-baseline gap-2">
                    <span className="font-mono text-slate-100">{p._id}</span>
                    <span className="glass text-xs">v{p.version}</span>
                  </div>
                  {p.candidates.map((c) => (
                    <div key={c.target} className="mb-1.5 flex items-center gap-2.5 last:mb-0">
                      <span className="w-36 shrink-0 truncate text-xs text-slate-400" title={c.target}>
                        {c.target}
                      </span>
                      <Meter ratio={c.weight} />
                      <span className="w-9 shrink-0 text-right text-xs tabular-nums text-slate-300">
                        {Math.round(c.weight * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </QueryState>
  );
}
