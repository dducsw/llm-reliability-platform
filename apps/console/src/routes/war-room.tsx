// War Room — signals, timeline, Cortex investigation, actions, proof
import { Link, useParams } from "@tanstack/react-router";
import { useState } from "react";

import { useAckIncident, useActions, useFalsePositiveIncident, useIncident, usePostmortem } from "../api/hooks";
import { DatadogLinks } from "../components/DatadogLinks";
import { NarrationRibbon } from "../components/NarrationRibbon";
import { Badge, Button, Card, Empty, QueryState, statusTone } from "../components/ui";
import { presenting } from "../present";

export function WarRoomPage() {
  const { key } = useParams({ strict: false }) as { key: string };
  const incident = useIncident(key);
  const actions = useActions();
  const ack = useAckIncident();
  const fp = useFalsePositiveIncident();
  const postmortem = usePostmortem(key);
  const [fpArm, setFpArm] = useState(false);
  const inc = incident.data;
  const related = (actions.data ?? []).filter((a) => a.incident_id === key);
  const open = inc ? inc.is_open !== false : false;
  const mutating = ack.isPending || fp.isPending;

  return (
    <QueryState isLoading={incident.isLoading} error={incident.error}>
      {inc && (
        <div className="space-y-4">
          <NarrationRibbon incident={inc} actions={related} />
          <Card>
            <div className="flex flex-wrap items-baseline gap-3">
              <h1 className="font-mono text-lg text-slate-50">{inc.key}</h1>
              <Badge tone={statusTone(inc.status)} dot>
                {inc.status}
              </Badge>
              <span className="text-slate-400">
                {inc.severity} · {inc.sli} · {inc.target ?? "—"} → {inc.routes.join(", ")}
              </span>
              {open && (
                <span className="ml-auto flex items-center gap-1.5">
                  <Button variant="ghost" disabled={mutating} onClick={() => ack.mutate(inc.key)}>
                    Nhận
                  </Button>
                  <Button
                    variant={fpArm ? "danger" : "ghost"}
                    disabled={mutating}
                    onClick={() => {
                      if (fpArm) {
                        fp.mutate(inc.key);
                        setFpArm(false);
                      } else setFpArm(true);
                    }}
                    title="Đóng incident do cảnh báo giả — không tính vào MTTX (A17)"
                  >
                    {fpArm ? "Xác nhận đóng?" : "False positive"}
                  </Button>
                </span>
              )}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-4 text-xs">
              <DatadogLinks incidentKey={inc.key} />
              <Link to="/timemachine/$key" params={{ key: inc.key }} className="text-sky-300 hover:underline">
                Open in Time Machine
              </Link>
            </div>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Cortex diagnosis">
              {inc.diagnosis ? (
                <div className="space-y-1.5">
                  <p className="text-slate-100">{inc.diagnosis.hypothesis}</p>
                  <p className="glass text-xs">
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
                <ul className="divide-y divide-slate-800/60">
                  {related.map((a) => (
                    <li key={a._id} className="flex items-center gap-2 py-2 first:pt-0 last:pb-0">
                      <span className="font-mono text-slate-200">{a.type}</span>
                      <Badge tone={statusTone(a.state)}>{a.state}</Badge>
                      {a.verification?.verdict && (
                        <Badge tone={a.verification.verdict === "PASS" ? "ok" : "critical"}>
                          {a.verification.verdict}
                          {a.verification.p_value != null && ` · p=${a.verification.p_value.toFixed(2)}`}
                        </Badge>
                      )}
                      <span className="glass ml-auto text-xs">{a.proposed_by?.actor}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>Chưa có action.</Empty>
              )}
            </Card>
            {!presenting && postmortem.data && (
              <Card title={`Postmortem · ${postmortem.data.generated_by ?? "cortex"}`} className="lg:col-span-2">
                <p className="text-slate-100">{postmortem.data.summary}</p>
                <pre className="mt-3 max-h-96 overflow-y-auto whitespace-pre-wrap rounded bg-slate-950 p-3 font-mono text-xs leading-relaxed text-slate-300 ring-1 ring-inset ring-slate-800">
                  {postmortem.data.body_md}
                </pre>
              </Card>
            )}
            {!presenting && (
              <Card title="Signals">
                {inc.signals?.length ? (
                  <ul className="divide-y divide-slate-800/60">
                    {inc.signals.map((s, idx) => (
                      <li key={idx} className="py-2 first:pt-0 last:pb-0">
                        <div className="mb-0.5 flex items-center gap-2">
                          <Badge tone="info">{s.source}</Badge>
                          <span className="glass text-xs">{s.at}</span>
                        </div>
                        <span className="text-slate-300">{s.diagnosis}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <Empty>Không có signal.</Empty>
                )}
              </Card>
            )}
            <Card title="Timeline">
              {inc.timeline?.length ? (
                <ul className="space-y-2.5 border-l border-slate-800 pl-4">
                  {inc.timeline.map((t, idx) => (
                    <li key={idx} className="relative text-slate-300">
                      <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full border border-slate-950 bg-slate-600" />
                      <span className="glass mr-2 text-xs">{t.at}</span>
                      {t.text ?? t.kind}
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
