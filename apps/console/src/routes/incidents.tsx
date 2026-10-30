// Incidents — danh sách, bộ lọc, MTTx KPIs (A17)
import { Link } from "@tanstack/react-router";
import { useState } from "react";

import { useAckIncident, useFalsePositiveIncident, useIncidents } from "../api/hooks";
import { Badge, Button, Card, Empty, QueryState, statusTone } from "../components/ui";

export function IncidentsPage() {
  const { data, isLoading, error } = useIncidents();
  const ack = useAckIncident();
  const fp = useFalsePositiveIncident();
  const [fpArm, setFpArm] = useState<Record<string, boolean>>({});
  const [onlyOpen, setOnlyOpen] = useState(false);
  const rows = (data ?? []).filter((i) => !onlyOpen || i.is_open);
  const mutating = ack.isPending || fp.isPending;

  const toggleFpArm = (key: string) => setFpArm((m) => ({ ...m, [key]: !m[key] }));

  return (
    <Card
      title="Incidents"
      actions={
        <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
          <input
            type="checkbox"
            className="checkbox"
            checked={onlyOpen}
            onChange={(e) => setOnlyOpen(e.target.checked)}
          />
          Chỉ incident đang mở
        </label>
      }
    >
      {(ack.error || fp.error) && (
        <p className="mb-2 text-red-300">{ack.error?.message ?? fp.error?.message}</p>
      )}
      <QueryState isLoading={isLoading} error={error}>
        {rows.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Key</th>
                <th>Severity</th>
                <th>Status</th>
                <th>SLI</th>
                <th>Detected</th>
                <th className="text-right">Hành động</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {rows.map((i) => {
                const open = i.is_open !== false;
                return (
                  <tr key={i.key}>
                    <td>
                      <Link to="/incidents/$key" params={{ key: i.key }} className="font-mono text-sky-400 hover:underline">
                        {i.key}
                      </Link>
                    </td>
                    <td className="font-mono text-slate-300">{i.severity}</td>
                    <td>
                      <Badge tone={statusTone(i.status)}>{i.status}</Badge>
                    </td>
                    <td className="text-slate-300">{i.sli}</td>
                    <td className="glass">{i.t?.detected_at ?? "—"}</td>
                    <td className="text-right">
                      {open ? (
                        <span className="inline-flex justify-end gap-1.5">
                          <Button
                            variant="ghost"
                            disabled={mutating}
                            onClick={() => ack.mutate(i.key)}
                            title="Ghi nhận: status → investigating, mốc acknowledged_at cho MTTA"
                          >
                            Nhận
                          </Button>
                          <Button
                            variant={fpArm[i.key] ? "danger" : "ghost"}
                            disabled={mutating}
                            onClick={() => {
                              if (fpArm[i.key]) {
                                fp.mutate(i.key);
                                setFpArm((m) => ({ ...m, [i.key]: false }));
                              } else toggleFpArm(i.key);
                            }}
                            title="Đóng incident do cảnh báo giả — không tính vào MTTX (A17)"
                          >
                            {fpArm[i.key] ? "Xác nhận?" : "False positive"}
                          </Button>
                        </span>
                      ) : (
                        <span className="glass">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <Empty>Không có incident.</Empty>
        )}
      </QueryState>
    </Card>
  );
}
