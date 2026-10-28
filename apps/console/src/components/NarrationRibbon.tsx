// Narration ribbon trên War Room: hệ thống đang ở bước nào (DETECT → INVESTIGATE → RESPOND → VERIFY)
import type { Action, Incident } from "../api/types";

const STAGES = ["DETECT", "INVESTIGATE", "RESPOND", "VERIFY"] as const;
type Stage = (typeof STAGES)[number] | "RESOLVED";

const RESPONDING = ["proposed", "awaiting_approval", "approved", "executing"];

export function stageOf(incident: Incident, actions: Action[]): Stage {
  if (incident.status === "resolved" || incident.status === "false_positive") return "RESOLVED";
  if (incident.status === "mitigated" || actions.some((a) => a.state === "verifying")) return "VERIFY";
  if (incident.status === "mitigating" || actions.some((a) => RESPONDING.includes(a.state))) return "RESPOND";
  if (incident.status === "investigating") return "INVESTIGATE";
  return "DETECT";
}

function caption(stage: Stage, incident: Incident, actions: Action[]): string {
  const target = incident.target ?? incident.routes.join(", ");
  const pending = actions.find((a) => RESPONDING.includes(a.state));
  switch (stage) {
    case "DETECT":
      return `Burn rate ${incident.sli} trên ${target} vượt ngưỡng — Sentinel và Datadog cùng phát hiện, incident được mở.`;
    case "INVESTIGATE":
      return "Cortex đang điều tra: đọc SLI, log và sự cố tương tự; mọi kết luận phải có evidence ref.";
    case "RESPOND":
      return pending?.state === "awaiting_approval"
        ? `Action ${pending.type} cần người duyệt — guardrail chưa cho tự áp.`
        : `Policy engine kiểm 10 guardrail rồi áp ${pending?.type ?? "action"} lên policy (hot-reload < 1s).`;
    case "VERIFY":
      return "Verifier so SLI trước/sau action (Wilson CI + z-test) để ra Recovery Proof.";
    case "RESOLVED":
      return "Sự cố đã đóng; postmortem được Cortex soạn từ dữ liệu thật.";
  }
}

export function NarrationRibbon({ incident, actions }: { incident: Incident; actions: Action[] }) {
  const stage = stageOf(incident, actions);
  const current = stage === "RESOLVED" ? STAGES.length : STAGES.indexOf(stage);
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/70 px-4 py-3">
      <ol className="flex flex-wrap items-center gap-2 font-semibold tracking-wider">
        {STAGES.map((s, i) => (
          <li key={s} className="flex items-center gap-2">
            <span
              className={`rounded px-2 py-0.5 text-xs ${
                i === current
                  ? "bg-sky-500 text-slate-950"
                  : i < current
                    ? "bg-emerald-500/20 text-emerald-300"
                    : "bg-slate-800 text-slate-500"
              }`}
            >
              {i < current ? "✓ " : ""}
              {s}
            </span>
            {i < STAGES.length - 1 && <span className="text-slate-600">→</span>}
          </li>
        ))}
      </ol>
      <p className="mt-2 text-slate-300">{caption(stage, incident, actions)}</p>
    </div>
  );
}
