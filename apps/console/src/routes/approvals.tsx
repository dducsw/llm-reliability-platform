// Approvals — action awaiting_approval: diff policy, guardrails, duyệt/từ chối
import { useActions, useDecideAction } from "../api/hooks";
import { Card, Empty, QueryState } from "../components/ui";

export function ApprovalsPage() {
  const { data, isLoading, error } = useActions();
  const decide = useDecideAction();
  const pending = (data ?? []).filter((a) => a.state === "awaiting_approval");
  return (
    <Card title="Chờ duyệt">
      <QueryState isLoading={isLoading} error={error}>
        {decide.error && <p className="mb-2 text-red-300">{decide.error.message}</p>}
        {pending.length ? (
          <ul className="space-y-3">
            {pending.map((a) => (
              <li key={a._id} className="rounded border border-slate-800 p-3">
                <div className="flex items-center gap-3">
                  <span className="font-mono">{a.type}</span>
                  <span className="text-xs text-slate-500">
                    {a.incident_id} · đề xuất bởi {a.proposed_by?.actor}
                  </span>
                  <div className="ml-auto flex gap-2">
                    <button
                      className="rounded bg-emerald-600 px-3 py-1 hover:bg-emerald-500 disabled:opacity-50"
                      disabled={decide.isPending}
                      onClick={() => decide.mutate({ id: a._id, decision: "approve" })}
                    >
                      Duyệt
                    </button>
                    <button
                      className="rounded bg-slate-700 px-3 py-1 hover:bg-slate-600 disabled:opacity-50"
                      disabled={decide.isPending}
                      onClick={() => decide.mutate({ id: a._id, decision: "reject" })}
                    >
                      Từ chối
                    </button>
                  </div>
                </div>
                <pre className="mt-2 overflow-x-auto text-xs text-slate-400">{JSON.stringify(a.params, null, 2)}</pre>
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
