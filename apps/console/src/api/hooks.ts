// TanStack Query hooks: usePulse, useIncidents, useIncident, useActions, usePolicies, useReplay…
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { subscribe, type StreamTopic } from "../stream/sse";
import { applyEvent } from "../stream/store";
import { apiGet, apiPost } from "./client";
import type { Action, DualLedger, Incident, PipelineInfo, Policy, Pulse } from "./types";

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

/** Mở một kết nối SSE cho vòng đời của component và đẩy event vào cache. */
export function useLiveTopics(topics: StreamTopic[]): void {
  const qc = useQueryClient();
  const key = topics.join(",");
  useEffect(() => subscribe(key.split(",") as StreamTopic[], (e) => applyEvent(qc, e)), [qc, key]);
}
