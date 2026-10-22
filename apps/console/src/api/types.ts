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
  state?: string;
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
