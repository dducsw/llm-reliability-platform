// Kiểu tối thiểu cho các response của control-plane BFF. Khi chạy được server, `pnpm gen:api`
// sinh ./schema.d.ts đầy đủ từ OpenAPI; file này chỉ mô tả phần Console thực sự đọc.
export interface IncidentTimes {
  detected_at?: string;
  acknowledged_at?: string;
  mitigated_at?: string;
  resolved_at?: string;
}

export interface Signal {
  source: string;
  at: string;
  diagnosis?: string;
}

export interface Diagnosis {
  side: "provider" | "gateway" | "unknown";
  hypothesis: string;
  confidence: number;
  by: string;
}

export interface Incident {
  _id: string;
  key: string;
  is_open?: boolean;
  slo_id: string;
  sli: string;
  scope: string;
  target?: string | null;
  routes: string[];
  severity: string;
  status: string;
  signals: Signal[];
  t?: IncidentTimes;
  diagnosis?: Diagnosis | null;
  timeline?: { at: string; text?: string; kind?: string }[];
}

export interface HealthState {
  _id: string;
  status?: string;
  [key: string]: unknown;
}

export interface Candidate {
  target: string;
  weight: number;
  role: string;
}

export interface Policy {
  _id: string;
  version: number;
  candidates: Candidate[];
}

export interface Action {
  _id: string;
  incident_id?: string | null;
  type: string;
  params: Record<string, unknown>;
  state: string;
  proposed_by?: { actor: string };
  created_at?: string;
}

export interface PipelineInfo {
  id: string;
  collection: string | null;
  summary: string;
  doc: string;
  params: string[];
  source: string;
}

export interface Pulse {
  health: HealthState[];
  incidents: Incident[];
  policies: Policy[];
}

export interface LedgerPoint {
  ts: string;
  total: number;
  ok: number;
  q_eligible: number;
  q_good: number;
}

export interface DualLedger {
  route: string;
  targets: string[];
  delivered: LedgerPoint[];
  provider: LedgerPoint[];
  events: { ts: string; kind: string; label: string }[];
}

export interface ReplayVariantInfo {
  id: string;
  description: string;
}

export interface VariantResult {
  description: string;
  delivered_quality: number;
  quality_ci_90: number;
  budget_consumed: number;
  extra_cost_usd: number;
  attempts_per_request: number;
  requests_saved: number;
}

export interface Replay {
  _id: string;
  incident_id: string;
  status: "queued" | "running" | "completed" | "failed";
  requested?: { variants: string[]; k: number; seed: number };
  variants?: Record<string, VariantResult>;
  calibration_error?: number;
  seeds?: number;
  error?: string;
  created_at?: string;
  completed_at?: string;
}

export interface MemoryPoint {
  key: string;
  sli: string;
  scope?: string;
  target?: string | null;
  status?: string;
  action?: { type: string; verdict?: string | null } | null;
  x: number;
  y: number;
}

export interface SimilarIncident {
  key?: string;
  sim?: number;
  [key: string]: unknown;
}

export interface DemoState {
  profile: string;
  time_scale: number;
  run: {
    run_id: string;
    scenario: string;
    phase_index: number;
    phase_starts_at: string;
    started_at: string;
  } | null;
}
