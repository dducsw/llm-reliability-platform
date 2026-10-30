// Query Explorer — con số → pipeline ID → JSON + explain
import { useState } from "react";

import { usePipeline, usePipelines } from "../api/hooks";
import { Card, Empty, QueryState } from "../components/ui";

export function ExplainPage() {
  const list = usePipelines();
  const [selected, setSelected] = useState<string>();
  const detail = usePipeline(selected);
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card title="Pipelines">
        <QueryState isLoading={list.isLoading} error={list.error}>
          <ul className="-mx-2">
            {list.data?.map((p) => (
              <li key={p.id}>
                <button
                  className={`flex w-full items-baseline gap-2 rounded px-2 py-1.5 text-left transition-colors hover:bg-slate-800/60 ${
                    selected === p.id ? "bg-slate-800 text-slate-50" : "text-slate-400"
                  }`}
                  onClick={() => setSelected(p.id)}
                >
                  <span className="font-mono">{p.id}</span>
                  <span className="text-xs">{p.summary}</span>
                </button>
              </li>
            ))}
          </ul>
        </QueryState>
      </Card>
      <Card title={selected ? `${selected} · ${detail.data?.collection ?? ""}` : "Chọn một pipeline"} className="lg:col-span-2">
        {detail.data ? (
          <>
            <p className="mb-3 whitespace-pre-wrap text-slate-300">{detail.data.doc}</p>
            <pre className="overflow-x-auto rounded bg-slate-950 p-3 font-mono text-xs text-slate-400 ring-1 ring-inset ring-slate-800">
              {detail.data.source}
            </pre>
          </>
        ) : (
          <Empty>Chọn một pipeline bên trái để xem explain.</Empty>
        )}
      </Card>
    </div>
  );
}
