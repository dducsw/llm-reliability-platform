// Policies — policy hiện tại, timeline version, diff
import { usePolicies } from "../api/hooks";
import { Card, Empty, QueryState } from "../components/ui";

export function PoliciesPage() {
  const { data, isLoading, error } = usePolicies();
  return (
    <QueryState isLoading={isLoading} error={error}>
      <div className="grid gap-4 md:grid-cols-2">
        {data?.length ? (
          data.map((p) => (
            <Card key={p._id} title={`${p._id} · v${p.version}`}>
              <table className="w-full text-left">
                <tbody>
                  {p.candidates.map((c) => (
                    <tr key={c.target} className="border-t border-slate-800 first:border-0">
                      <td className="py-1 font-mono">{c.target}</td>
                      <td className="text-slate-400">{c.role}</td>
                      <td className="text-right">{Math.round(c.weight * 100)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          ))
        ) : (
          <Empty>Chưa có policy.</Empty>
        )}
      </div>
    </QueryState>
  );
}
