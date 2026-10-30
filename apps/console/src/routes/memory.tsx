// Incident Memory — bản đồ tương đồng (signature chiếu 2D ở backend), chọn một điểm để tìm theo hình dạng (A10)
import { Link } from "@tanstack/react-router";
import { lazy, Suspense, useState } from "react";

import { useMemoryMap, useSimilar } from "../api/hooks";
import { Badge, Card, Empty, QueryState, Select, Spinner, statusTone } from "../components/ui";

const MemoryScatter = lazy(() =>
  import("../components/charts/MemoryScatter").then((m) => ({ default: m.MemoryScatter })),
);

const SLIS = ["quality", "availability", "latency", "ttft"];

function SimilarPanel({ incidentKey }: { incidentKey: string }) {
  const { data, isLoading, error } = useSimilar(incidentKey);
  return (
    <Card title={`Tương tự ${incidentKey}`}>
      <div className="mb-3 flex gap-3 text-xs text-sky-300">
        <Link to="/incidents/$key" params={{ key: incidentKey }} className="hover:underline">
          War Room
        </Link>
        <Link to="/timemachine/$key" params={{ key: incidentKey }} className="hover:underline">
          Time Machine
        </Link>
      </div>
      <QueryState isLoading={isLoading} error={error}>
        {data?.similar.length ? (
          <ul className="divide-y divide-slate-800/60">
            {data.similar.map((s, i) => (
              <li key={String(s.key ?? i)} className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                <span className="font-mono text-slate-200">{String(s.key ?? "—")}</span>
                {typeof s.sim === "number" && (
                  <span className="glass text-xs tabular-nums">sim {s.sim.toFixed(2)}</span>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <Empty>
            {data?.reason === "no_signature" ? "Incident chưa có signature." : "Không có sự cố đủ giống (sim ≥ 0.70)."}
          </Empty>
        )}
      </QueryState>
    </Card>
  );
}

export function MemoryPage() {
  const [sli, setSli] = useState<string>();
  const [picked, setPicked] = useState<string>();
  const { data, isLoading, error } = useMemoryMap(sli);
  const point = data?.points.find((p) => p.key === picked);

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card title="Incident Memory" className="lg:col-span-2">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Select value={sli ?? ""} onChange={(e) => setSli(e.target.value || undefined)} aria-label="Lọc theo SLI">
            <option value="">Mọi SLI</option>
            {SLIS.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </Select>
          {data && (
            <span className="glass text-xs">
              {data.points.length} incident · signature 64 chiều chiếu {data.method.toUpperCase()} 2D · bấm một điểm
              để tìm sự cố cùng hình dạng
            </span>
          )}
        </div>
        <QueryState isLoading={isLoading} error={error}>
          {data?.points.length ? (
            <Suspense
              fallback={
                <p className="flex items-center gap-2 text-slate-400">
                  <Spinner /> Đang tải biểu đồ…
                </p>
              }
            >
              <MemoryScatter points={data.points} selected={picked} onSelect={setPicked} />
            </Suspense>
          ) : (
            <Empty>Chưa có incident nào có signature (chạy `task memory:bootstrap`).</Empty>
          )}
        </QueryState>
      </Card>
      <div className="space-y-4">
        {point ? (
          <>
            <Card title="Incident">
              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-slate-100">{point.key}</span>
                  {point.status && <Badge tone={statusTone(point.status)}>{point.status}</Badge>}
                </div>
                <p className="text-slate-400">
                  {point.sli} · {point.scope ?? "—"} · {point.target ?? "—"}
                </p>
                {point.action && (
                  <p className="text-slate-300">
                    Giải quyết bằng <span className="code">{point.action.type}</span>
                    {point.action.verdict && (
                      <Badge tone={point.action.verdict === "PASS" ? "ok" : "critical"}>{point.action.verdict}</Badge>
                    )}
                  </p>
                )}
              </div>
            </Card>
            <SimilarPanel incidentKey={point.key} />
          </>
        ) : (
          <Card>
            <Empty>Chọn một incident trên bản đồ.</Empty>
          </Card>
        )}
      </div>
    </div>
  );
}
