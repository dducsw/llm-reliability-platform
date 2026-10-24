// Query Explorer — con số → pipeline ID → JSON + explain
import { useState } from "react";

import { usePipeline, usePipelines } from "../api/hooks";
import { Card, QueryState } from "../components/ui";

export function ExplainPage() {
  const list = usePipelines();
  const [selected, setSelected] = useState<string>();
  const detail = usePipeline(selected);
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card title="Pipelines">
        <QueryState isLoading={list.isLoading} error={list.error}>
          <ul className="space-y-1">
            {list.data?.map((p) => (
              <li key={p.id}>
                <button
                  className={`w-full text-left hover:text-white ${selected === p.id ? "text-white" : "text-slate-400"}`}
                  onClick={() => setSelected(p.id)}
                >
                  <span className="font-mono">{p.id}</span> {p.summary}
                </button>
              </li>
            ))}
          </ul>
        </QueryState>
      </Card>
      <Card title={selected ? `${selected} · ${detail.data?.collection ?? ""}` : "Chọn một pipeline"} className="lg:col-span-2">
        {detail.data && (
          <>
            <p className="mb-2 whitespace-pre-wrap text-slate-300">{detail.data.doc}</p>
            <pre className="overflow-x-auto rounded bg-slate-950 p-3 text-xs">{detail.data.source}</pre>
          </>
        )}
      </Card>
    </div>
  );
}
