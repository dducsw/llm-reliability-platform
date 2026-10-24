// Incidents — danh sách, bộ lọc, MTTx KPIs (A17)
import { Link } from "@tanstack/react-router";
import { useState } from "react";

import { useIncidents } from "../api/hooks";
import { Badge, Card, Empty, QueryState, statusTone } from "../components/ui";

export function IncidentsPage() {
  const { data, isLoading, error } = useIncidents();
  const [onlyOpen, setOnlyOpen] = useState(false);
  const rows = (data ?? []).filter((i) => !onlyOpen || i.is_open);
  return (
    <Card title="Incidents">
      <label className="mb-3 flex items-center gap-2 text-slate-300">
        <input type="checkbox" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} />
        Chỉ incident đang mở
      </label>
      <QueryState isLoading={isLoading} error={error}>
        {rows.length ? (
          <table className="w-full text-left">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="py-1">Key</th>
                <th>Severity</th>
                <th>Status</th>
                <th>SLI</th>
                <th>Target</th>
                <th>Detected</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((i) => (
                <tr key={i.key} className="border-t border-slate-800">
                  <td className="py-1">
                    <Link to="/incidents/$key" params={{ key: i.key }} className="font-mono text-sky-400 hover:underline">
                      {i.key}
                    </Link>
                  </td>
                  <td>{i.severity}</td>
                  <td>
                    <Badge tone={statusTone(i.status)}>{i.status}</Badge>
                  </td>
                  <td>{i.sli}</td>
                  <td className="font-mono">{i.target ?? "—"}</td>
                  <td className="text-slate-400">{i.t?.detected_at ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty>Không có incident.</Empty>
        )}
      </QueryState>
    </Card>
  );
}
