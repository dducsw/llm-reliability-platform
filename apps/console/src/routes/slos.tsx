// SLOs — objective theo route×SLI, window, alert tiers, link Datadog SLO
import { useDemo, useSlos } from "../api/hooks";
import { Card, Empty, QueryState } from "../components/ui";

const ddSite = import.meta.env.VITE_DD_SITE ?? "datadoghq.com";
const pct = (v: number) => `${(v * 100).toFixed(v * 100 >= 99 ? 2 : 1)}%`;

export function SlosPage() {
  const { data, isLoading, error } = useSlos();
  const demo = useDemo();
  const isDemo = demo.data?.profile !== "standard";

  return (
    <Card title="SLO (error budget)">
      <QueryState isLoading={isLoading} error={error}>
        {data?.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Route</th>
                <th>SLI</th>
                <th className="text-right">Objective</th>
                <th className="text-right">Window</th>
                <th>Alert tiers</th>
                <th>Owner</th>
                <th>Datadog</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {data.map((s) => {
                const [scope, route, sli] = s._id.split(":");
                const window = isDemo ? s.window?.demo : s.window?.standard;
                return (
                  <tr key={s._id}>
                    <td className="font-mono text-slate-200">
                      {route}
                      <span className="glass ml-1.5 text-xs">{scope}</span>
                    </td>
                    <td className="text-slate-300">{sli}</td>
                    <td className="text-right text-slate-200">{pct(s.objective)}</td>
                    <td className="text-right text-slate-400">{window ?? "—"}</td>
                    <td>
                      <div className="flex flex-wrap gap-1">
                        {(s.alerts ?? []).map((a) => (
                          <span
                            key={a.tier}
                            className="glass rounded bg-slate-800/70 px-1.5 py-0.5 text-xs"
                            title={`${a.tier}: burn ${a.factor}× (${a.short}/${a.long})${a.hint ? ` → ${a.hint}` : ""}`}
                          >
                            {a.tier} {a.factor}×
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="text-slate-400">{s.owner ?? "—"}</td>
                    <td>
                      {s.datadog?.slo_id ? (
                        <a
                          href={`https://app.${ddSite}/slops/${s.datadog.slo_id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-sky-400 hover:underline"
                        >
                          SLO ↗
                        </a>
                      ) : (
                        <span className="glass text-xs">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <Empty>Chưa có SLO nào (seed chưa chạy?).</Empty>
        )}
      </QueryState>
    </Card>
  );
}
