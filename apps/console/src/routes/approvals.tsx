// Approvals — action awaiting_approval: diff policy, guardrails, duyệt/từ chối
import { useState } from "react";

import { useActions, useDecideAction } from "../api/hooks";
import { Button, Card, Empty, QueryState } from "../components/ui";

export function ApprovalsPage() {
  const { data, isLoading, error } = useActions();
  const decide = useDecideAction();
  const [confirmed, setConfirmed] = useState<Record<string, "approve" | "reject" | undefined>>({});

  const pending = (data ?? []).filter((a) => a.state === "awaiting_approval");

  const decideOn = (id: string, decision: "approve" | "reject") => {
    // Duyệt/từ chối là thao tác hai bước: lần click đầu chỉ đổi nhãn xác nhận, lần hai mới gửi.
    if (confirmed[id] !== decision) {
      setConfirmed((c) => ({ ...c, [id]: decision }));
      return;
    }
    decide.mutate({ id, decision });
  };

  return (
    <Card title="Chờ duyệt">
      <QueryState isLoading={isLoading} error={error}>
        {decide.error && <p className="mb-2 text-red-300">{decide.error.message}</p>}
        {pending.length ? (
          <ul className="divide-y divide-slate-800/60">
            {pending.map((a) => (
              <li key={a._id} className="py-3 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                  <span className="font-mono text-slate-100">{a.type}</span>
                  <span className="glass text-xs">
                    {a.incident_id} · đề xuất bởi {a.proposed_by?.actor}
                  </span>
                  <div className="ml-auto flex items-center gap-2">
                    <Button
                      variant={confirmed[a._id] === "approve" ? "success" : "ghost"}
                      disabled={decide.isPending}
                      onClick={() => decideOn(a._id, "approve")}
                    >
                      {confirmed[a._id] === "approve" ? "Xác nhận duyệt?" : "Duyệt"}
                    </Button>
                    <Button
                      variant={confirmed[a._id] === "reject" ? "danger" : "ghost"}
                      disabled={decide.isPending}
                      onClick={() => decideOn(a._id, "reject")}
                    >
                      {confirmed[a._id] === "reject" ? "Xác nhận từ chối?" : "Từ chối"}
                    </Button>
                  </div>
                </div>
                <pre className="mt-2 overflow-x-auto rounded bg-slate-950 p-2.5 font-mono text-xs text-slate-400 ring-1 ring-inset ring-slate-800">
                  {JSON.stringify(a.params, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        ) : (
          <Empty>Không có action nào chờ duyệt.</Empty>
        )}
      </QueryState>
    </Card>
  );
}
