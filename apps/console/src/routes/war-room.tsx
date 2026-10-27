// War Room — signals, timeline, Cortex investigation, actions, proof
import { Link, useParams } from "@tanstack/react-router";

import { useActions, useIncident } from "../api/hooks";
import { DatadogLinks } from "../components/DatadogLinks";
import { Badge, Card, Empty, QueryState, statusTone } from "../components/ui";

export function WarRoomPage() {
  const { key } = useParams({ strict: false }) as { key: string };
  const incident = useIncident(key);
  const actions = useActions();
  const inc = incident.data;
  const related = (actions.data ?? []).filter((a) => a.incident_id === key);

  return (
    <QueryState isLoading={incident.isLoading} error={incident.error}>
      {inc && (
        <div className="space-y-4">
          <Card>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-mono text-lg">{inc.key}</h1>
              <Badge tone={statusTone(inc.status)}>{inc.status}</Badge>
              <span className="text-slate-400">
                {inc.severity} · {inc.sli} · {inc.target ?? "—"} → {inc.routes.join(", ")}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-4">
              <DatadogLinks incidentKey={inc.key} />
              <Link to="/timemachine/$key" params={{ key: inc.key }} className="text-sky-300 hover:underline">
                ▶ Open in Time Machine
              </Link>
            </div>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Cortex diagnosis">
              {inc.diagnosis ? (
                <div className="space-y-1">
                  <p>{inc.diagnosis.hypothesis}</p>
                  <p className="text-slate-400">
                    side: {inc.diagnosis.side} · confidence {Math.round(inc.diagnosis.confidence * 100)}% · by{" "}
                    {inc.diagnosis.by}
                  </p>
                </div>
              ) : (
                <Empty>Chưa có chẩn đoán.</Empty>
              )}
            </Card>
            <Card title="Actions">
              {related.length ? (
                <ul className="space-y-2">
                  {related.map((a) => (
                    <li key={a._id} className="flex items-center gap-2">
                      <span className="font-mono">{a.type}</span>
                      <Badge tone={statusTone(a.state)}>{a.state}</Badge>
                      <span className="text-xs text-slate-500">{a.proposed_by?.actor}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>Chưa có action.</Empty>
              )}
            </Card>
            <Card title="Signals">
              {inc.signals.length ? (
                <ul className="space-y-1">
                  {inc.signals.map((s, idx) => (
                    <li key={idx}>
                      <Badge tone="info">{s.source}</Badge> <span className="text-slate-400">{s.at}</span>{" "}
                      {s.diagnosis}
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>Không có signal.</Empty>
              )}
            </Card>
            <Card title="Timeline">
              {inc.timeline?.length ? (
                <ul className="space-y-1">
                  {inc.timeline.map((t, idx) => (
                    <li key={idx}>
                      <span className="text-slate-500">{t.at}</span> {t.text ?? t.kind}
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>Timeline trống.</Empty>
              )}
            </Card>
          </div>
        </div>
      )}
    </QueryState>
  );
}
