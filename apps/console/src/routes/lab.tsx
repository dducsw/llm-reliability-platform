// Chaos Lab — chạy scenario, phase, expectations realtime
import { useState } from "react";

import { useRunScenario, useScenarios } from "../api/hooks";
import { Button, Card, Empty, QueryState } from "../components/ui";

export function LabPage() {
  const { data, isLoading, error } = useScenarios();
  const run = useRunScenario();
  const [fast, setFast] = useState(true);
  return (
    <Card
      title="Chaos Lab"
      actions={
        <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
          <input type="checkbox" className="checkbox" checked={fast} onChange={(e) => setFast(e.target.checked)} />
          --fast (x5)
        </label>
      }
    >
      <QueryState isLoading={isLoading} error={error}>
        {run.error && <p className="mb-2 text-red-300">{run.error.message}</p>}
        {run.data !== undefined && <p className="mb-2 text-emerald-300">Đã khởi chạy scenario.</p>}
        {data?.length ? (
          <ul className="divide-y divide-slate-800/60">
            {data.map((name) => (
              <li key={name} className="flex items-center py-2 first:pt-0 last:pb-0">
                <span className="font-mono text-slate-200">{name}</span>
                <Button
                  variant="primary"
                  className="ml-auto"
                  disabled={run.isPending}
                  onClick={() => run.mutate({ name, fast })}
                >
                  Chạy
                </Button>
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
