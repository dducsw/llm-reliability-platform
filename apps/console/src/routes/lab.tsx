// Chaos Lab — chạy scenario, phase, expectations realtime
import { useState } from "react";

import { useRunScenario, useScenarios } from "../api/hooks";
import { Card, Empty, QueryState } from "../components/ui";

export function LabPage() {
  const { data, isLoading, error } = useScenarios();
  const run = useRunScenario();
  const [fast, setFast] = useState(true);
  return (
    <Card title="Chaos Lab">
      <label className="mb-3 flex items-center gap-2 text-slate-300">
        <input type="checkbox" checked={fast} onChange={(e) => setFast(e.target.checked)} />
        --fast (x60)
      </label>
      <QueryState isLoading={isLoading} error={error}>
        {run.error && <p className="mb-2 text-red-300">{run.error.message}</p>}
        {run.data !== undefined && <p className="mb-2 text-emerald-300">Đã khởi chạy scenario.</p>}
        {data?.length ? (
          <ul className="space-y-2">
            {data.map((name) => (
              <li key={name} className="flex items-center gap-3">
                <span className="font-mono">{name}</span>
                <button
                  className="ml-auto rounded bg-sky-600 px-3 py-1 hover:bg-sky-500 disabled:opacity-50"
                  disabled={run.isPending}
                  onClick={() => run.mutate({ name, fast })}
                >
                  Chạy
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <Empty>Không tìm thấy scenario.</Empty>
        )}
      </QueryState>
    </Card>
  );
}
