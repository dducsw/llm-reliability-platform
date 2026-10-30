// TanStack Query hooks: usePulse, useIncidents, useIncident, useActions, usePolicies, useReplay…
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { subscribe, type StreamTopic } from "../stream/sse";
import { applyEvent } from "../stream/store";
import { apiGet, apiPost } from "./client";
import type {
  Action,
  DemoState,
  DualLedger,
  Incident,
  MemoryPoint,
  PipelineInfo,
  Policy,
  PolicyHistoryEntry,
  Postmortem,
  Pulse,
  Replay,
  ReplayVariantInfo,
  SimilarIncident,
  Slo,
} from "./types";

export const usePulse = () => useQuery({ queryKey: ["pulse"], queryFn: () => apiGet<Pulse>("/api/pulse") });

export const useDualLedger = (route: string | undefined, minutes = 60) =>
  useQuery({
    queryKey: ["series", "dual", route, minutes],
    queryFn: () => apiGet<DualLedger>(`/api/series/dual?route=${encodeURIComponent(route ?? "")}&minutes=${minutes}`),
    enabled: Boolean(route),
    refetchInterval: 15_000,
  });

export const useIncidents = () =>
  useQuery({
    queryKey: ["incidents"],
    queryFn: async () => (await apiGet<{ incidents: Incident[] }>("/api/incidents")).incidents,
  });

export const useIncident = (key: string) =>
  useQuery({ queryKey: ["incidents", key], queryFn: () => apiGet<Incident>(`/api/incidents/${key}`) });

export const useActions = () =>
  useQuery({
    queryKey: ["actions"],
    queryFn: async () => (await apiGet<{ actions: Action[] }>("/api/actions")).actions,
  });

export const usePolicies = () =>
  useQuery({
    queryKey: ["policies"],
    queryFn: async () => (await apiGet<{ policies: Policy[] }>("/api/policies")).policies,
  });

export const usePolicyHistory = (route: string | undefined) =>
  useQuery({
    queryKey: ["policies", "history", route],
    queryFn: async () =>
      (
        await apiGet<{ history: PolicyHistoryEntry[] }>(
          `/api/policies/${encodeURIComponent(route ?? "")}/history`,
        )
      ).history,
    enabled: Boolean(route),
    staleTime: 30_000,
  });

export const useSlos = () =>
  useQuery({
    queryKey: ["slos"],
    queryFn: async () => (await apiGet<{ slos: Slo[] }>("/api/slos")).slos,
  });

export const usePostmortem = (key: string | undefined) =>
  useQuery({
    queryKey: ["postmortems", key],
    queryFn: () => apiGet<Postmortem>(`/api/incidents/${key}/postmortem`),
    enabled: Boolean(key),
    retry: false,
  });

export const usePipelines = () =>
  useQuery({
    queryKey: ["pipelines"],
    queryFn: async () => (await apiGet<{ pipelines: PipelineInfo[] }>("/api/pipelines")).pipelines,
  });

export const usePipeline = (id: string | undefined) =>
  useQuery({
    queryKey: ["pipelines", id],
    queryFn: () => apiGet<PipelineInfo>(`/api/pipelines/${id}`),
    enabled: Boolean(id),
  });

export const useScenarios = () =>
  useQuery({
    queryKey: ["lab", "scenarios"],
    queryFn: async () => (await apiGet<{ scenarios: string[] }>("/api/lab/scenarios")).scenarios,
  });

export const useDemo = () =>
  useQuery({
    queryKey: ["lab", "demo"], // topic `lab` (chaos_runs) invalidate khi phase đổi
    queryFn: () => apiGet<DemoState>("/api/demo"),
    refetchInterval: 30_000,
  });

export const useReplayVariants = () =>
  useQuery({
    queryKey: ["replays", "variants"],
    queryFn: async () => (await apiGet<{ variants: ReplayVariantInfo[] }>("/api/replays/variants")).variants,
    staleTime: Infinity,
  });

export const useReplays = (incidentKey: string) =>
  useQuery({
    queryKey: ["replays", "list", incidentKey],
    queryFn: async () =>
      (await apiGet<{ items: Replay[] }>(`/api/replays?incident_id=${encodeURIComponent(incidentKey)}`)).items,
  });

const isActive = (r?: Replay) => r?.status === "queued" || r?.status === "running";

export const useReplay = (id: string | undefined) =>
  useQuery({
    queryKey: ["replays", "one", id],
    queryFn: () => apiGet<Replay>(`/api/replays/${id}`),
    enabled: Boolean(id),
    // SSE topic `replays` là đường chính; poll chậm phòng khi stream rớt lúc job đang chạy
    refetchInterval: (q) => (isActive(q.state.data) ? 3_000 : false),
  });

export function useRunReplay() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { incident_id: string; variants: string[]; k: number }) =>
      apiPost<Replay>("/api/replays", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["replays", "list"] }),
  });
}

export const useMemoryMap = (sli: string | undefined) =>
  useQuery({
    queryKey: ["memory", "map", sli ?? "all"],
    queryFn: () =>
      apiGet<{ points: MemoryPoint[]; method: string }>(`/api/memory/map${sli ? `?sli=${encodeURIComponent(sli)}` : ""}`),
  });

export const useSimilar = (key: string | undefined) =>
  useQuery({
    queryKey: ["memory", "similar", key],
    queryFn: () => apiGet<{ similar: SimilarIncident[]; reason?: string }>(`/api/memory/similar?incident_id=${encodeURIComponent(key ?? "")}`),
    enabled: Boolean(key),
    retry: false,
  });

export function useDecideAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "approve" | "reject" }) =>
      apiPost(`/api/actions/${id}/${decision}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["actions"] }),
  });
}

export function useRunScenario() {
  return useMutation({
    mutationFn: ({ name, fast }: { name: string; fast: boolean }) =>
      apiPost(`/api/lab/scenarios/${name}/run?fast=${fast}`),
  });
}

/** Nhận incident (status → investigating, ghi acknowledged_at cho A17). */
export function useAckIncident() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (key: string) => apiPost(`/api/incidents/${key}/ack`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["incidents"] }),
  });
}

/** Đánh dấu false positive (đóng incident, không tính vào MTTX). */
export function useFalsePositiveIncident() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (key: string) => apiPost(`/api/incidents/${key}/false-positive`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["incidents"] }),
  });
}

/** Mở một kết nối SSE cho vòng đời của component và đẩy event vào cache. */
export function useLiveTopics(topics: StreamTopic[]): void {
  const qc = useQueryClient();
  const key = topics.join(",");
  useEffect(() => subscribe(key.split(",") as StreamTopic[], (e) => applyEvent(qc, e)), [qc, key]);
}
