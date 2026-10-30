// Policies — policy hiện tại + timeline version (diff weights so với version đang chạy)
import { useState } from "react";

import { usePolicies, usePolicyHistory } from "../api/hooks";
import type { Policy, PolicyHistoryEntry } from "../api/types";
import { Card, Empty, Meter, QueryState } from "../components/ui";

const pp = (v: number) => `${(v * 100).toFixed(0)}pp`;

/** Diff weights của một version so với version đang chạy: nào đổi thì ghi rõ. */
function diffWeights(entry: PolicyHistoryEntry, current: Policy): string {
  const nowWeights = new Map(current.candidates.map((c) => [c.target, c.weight]));
  const parts = entry.doc.candidates
    .filter((c) => {
      const w = nowWeights.get(c.target);
      return w === undefined || Math.abs(w - c.weight) > 0.001;
    })
    .map((c) => {
      const w = nowWeights.get(c.target);
      const delta = w === undefined ? c.weight : c.weight - w;
      return `${c.target} ${w === undefined ? "mới" : delta > 0 ? "+" : "−"}${pp(Math.abs(delta))}`;
    });
  return parts.join(" · ") || "—";
}

function HistoryPanel({ route, current }: { route: string; current: Policy }) {
  const { data, isLoading, error } = usePolicyHistory(route);
  return (
    <div className="mt-3 border-t border-slate-800 pt-3">
      <div className="section-label mb-2">Lịch sử version</div>
      <QueryState isLoading={isLoading} error={error}>
        {data?.length ? (
          <ol className="relative space-y-2.5 border-l border-slate-800 pl-4">
            {data.slice(0, 8).map((h) => (
              <li key={h._id} className="relative">
                <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full border border-slate-950 bg-slate-600" />
                <div className="flex flex-wrap items-baseline gap-x-3">
                  <span className="font-mono text-slate-200">v{h.version}</span>
                  <span className="glass text-xs">{h.at}</span>
                  <span className="text-xs text-slate-500">{diffWeights(h, current)}</span>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-slate-500">Chưa có lần đổi nào.</p>
        )}
      </QueryState>
    </div>
  );
}

export function PoliciesPage() {
  const { data, isLoading, error } = usePolicies();
  const [openHistory, setOpenHistory] = useState<Record<string, boolean>>({});
  return (
    <QueryState isLoading={isLoading} error={error}>
      {data?.length ? (
        <div className="grid gap-4 md:grid-cols-2">
          {data.map((p) => (
            <Card key={p._id} title={`${p._id} · v${p.version}`}>
              <table className="table">
                <tbody>
                  {p.candidates.map((c) => (
                    <tr key={c.target}>
                      <td className="w-2/5 font-mono text-slate-200">{c.target}</td>
                      <td className="text-xs text-slate-500">{c.role}</td>
                      <td className="w-28">
                        <Meter ratio={c.weight} />
                      </td>
                      <td className="w-14 text-right tabular-nums text-slate-300">{Math.round(c.weight * 100)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {openHistory[p._id] ? (
                <HistoryPanel route={p._id} current={p} />
              ) : (
                <p className="mt-2 text-xs text-slate-500">
                  <button
                    className="text-sky-400 hover:underline"
                    onClick={() => setOpenHistory((m) => ({ ...m, [p._id]: true }))}
                  >
                    Xem lịch sử version →
                  </button>
                </p>
              )}
            </Card>
          ))}
        </div>
      ) : (
        <Empty>Chưa có policy.</Empty>
      )}
    </QueryState>
  );
}
