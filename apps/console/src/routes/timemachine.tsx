// Time Machine — chọn variant → chạy Monte Carlo → bảng + biểu đồ so sánh, dòng ablation
import { Link, useParams } from "@tanstack/react-router";
import { lazy, Suspense, useState } from "react";

import { useReplay, useReplays, useReplayVariants, useRunReplay } from "../api/hooks";
import type { Replay, VariantResult } from "../api/types";
import { Badge, Button, Card, Empty, QueryState, Spinner } from "../components/ui";

const VariantBarChart = lazy(() =>
  import("../components/charts/VariantBarChart").then((m) => ({ default: m.VariantBarChart })),
);

const pct = (v: number, digits = 1) => `${(v * 100).toFixed(digits)}%`;

const REPLAY_TONE: Record<Replay["status"], "info" | "warning" | "ok" | "critical"> = {
  queued: "info",
  running: "warning",
  completed: "ok",
  failed: "critical",
};

function ResultTable({ rows }: { rows: [string, VariantResult][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="table">
        <thead>
          <tr>
            <th>Variant</th>
            <th className="text-right">Delivered quality</th>
            <th className="text-right">Budget consumed</th>
            <th className="text-right">Extra cost</th>
            <th className="text-right">Attempts/req</th>
            <th className="text-right">Requests saved</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map(([name, v]) => {
            const mine = name === "reflex_recorded";
            return (
              <tr key={name} className={mine ? "font-semibold text-emerald-300" : ""}>
                <td>
                  <div className="font-mono text-slate-200">{name}</div>
                  <div className="text-xs font-normal text-slate-500">{v.description}</div>
                </td>
                <td className="text-right">
                  {pct(v.delivered_quality)} <span className="glass">± {(v.quality_ci_90 * 100).toFixed(1)}</span>
                </td>
                <td className={`text-right ${v.budget_consumed >= 1 ? "text-red-300" : "text-slate-300"}`}>
                  {v.budget_consumed >= 1 ? "100% (breach)" : pct(v.budget_consumed)}
                </td>
                <td className="text-right text-slate-300">${v.extra_cost_usd.toFixed(2)}</td>
                <td className="text-right text-slate-300">{v.attempts_per_request.toFixed(2)}</td>
                <td className="text-right text-slate-300">{v.requests_saved.toLocaleString()}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ReplayResult({ id }: { id: string }) {
  const { data, isLoading, error } = useReplay(id);
  const rows = Object.entries(data?.variants ?? {});
  return (
    <QueryState isLoading={isLoading} error={error}>
      {data && (
        <Card title={`Kết quả ${data._id}`}>
          <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
            <Badge tone={REPLAY_TONE[data.status]}>{data.status}</Badge>
            {data.seeds != null && <span className="glass text-xs">K = {data.seeds} seed</span>}
            {data.calibration_error != null && (
              <span className="text-xs text-slate-400">
                calibration error: <span className="text-slate-200 tabular-nums">{(data.calibration_error * 100).toFixed(1)} pp</span>
              </span>
            )}
          </div>
          {data.status === "failed" && <p className="text-red-300">{data.error}</p>}
          {(data.status === "queued" || data.status === "running") && (
            <p className="flex items-center gap-2 text-slate-400">
              <Spinner /> Đang mô phỏng…
            </p>
          )}
          {data.status === "completed" && rows.length > 0 && (
            <div className="space-y-4">
              <Suspense fallback={<Empty>Đang tải biểu đồ…</Empty>}>
                <VariantBarChart variants={rows} />
              </Suspense>
              <ResultTable rows={rows} />
              <p className="glass text-xs">
                Mean ± khoảng 90% qua K seed. <span className="text-slate-300">reflex_recorded</span> replay đúng chuỗi
                policy đã áp dụng và được so với SLI thực tế để ra calibration error; các dòng còn lại là
                counterfactual/ablation.
              </p>
            </div>
          )}
        </Card>
      )}
    </QueryState>
  );
}

export function TimeMachinePage() {
  const { key } = useParams({ strict: false }) as { key: string };
  const variants = useReplayVariants();
  const history = useReplays(key);
  const run = useRunReplay();
  const [picked, setPicked] = useState<string[] | null>(null);
  const [k, setK] = useState(20);
  const [selected, setSelected] = useState<string>();

  const all = variants.data?.map((v) => v.id) ?? [];
  const chosen = picked ?? all;
  const current = selected ?? run.data?._id ?? history.data?.[0]?._id;
  const toggle = (id: string) =>
    setPicked(chosen.includes(id) ? chosen.filter((x) => x !== id) : [...chosen, id]);

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-baseline gap-3">
          <h1 className="text-lg text-slate-50">Time Machine</h1>
          <Link to="/incidents/$key" params={{ key }} className="font-mono text-sky-300 hover:underline">
            {key}
          </Link>
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Chạy replay">
          <QueryState isLoading={variants.isLoading} error={variants.error}>
            <ul className="space-y-2.5">
              {variants.data?.map((v) => (
                <li key={v.id}>
                  <label className="flex cursor-pointer items-start gap-2.5">
                    <input type="checkbox" className="checkbox mt-0.5" checked={chosen.includes(v.id)} onChange={() => toggle(v.id)} />
                    <span>
                      <span className="font-mono text-slate-200">{v.id}</span>
                      <span className="block text-xs text-slate-500">{v.description}</span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
            <label className="mt-4 flex items-center gap-3 text-xs text-slate-400">
              K seed
              <input
                type="number"
                min={1}
                max={100}
                value={k}
                onChange={(e) => setK(Math.max(1, Math.min(100, Number(e.target.value) || 1)))}
                className="field w-20 tabular-nums"
              />
            </label>
            {run.error && <p className="mt-2 text-red-300">{run.error.message}</p>}
            <div className="mt-4">
              <Button
                variant="primary"
                disabled={run.isPending || chosen.length === 0}
                onClick={() => {
                  setSelected(undefined);
                  run.mutate({ incident_id: key, variants: chosen, k });
                }}
              >
                Chạy
              </Button>
            </div>
          </QueryState>
          <h3 className="section-label mb-2 mt-6">Lần chạy trước</h3>
          <QueryState isLoading={history.isLoading} error={history.error}>
            {history.data?.length ? (
              <ul className="-mx-2 space-y-0.5">
                {history.data.map((r) => (
                  <li key={r._id}>
                    <button
                      className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left transition-colors hover:bg-slate-800/60 ${
                        r._id === current ? "bg-slate-800" : ""
                      }`}
                      onClick={() => setSelected(r._id)}
                    >
                      <span className="font-mono text-xs text-slate-300">{r._id}</span>
                      <Badge tone={REPLAY_TONE[r.status]}>{r.status}</Badge>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>Chưa có replay nào cho incident này.</Empty>
            )}
          </QueryState>
        </Card>
        <div className="lg:col-span-2">{current ? <ReplayResult id={current} /> : <Card><Empty>Chọn variant và bấm Chạy.</Empty></Card>}</div>
      </div>
    </div>
  );
}
