import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useSession } from "@/shared/identity/session";

import { api, call } from "./client";
export { call } from "./client";
import { FALLBACK_MS, MONITOR_REFRESH_MS, usePolling } from "@/shared/live/context";
import type {
  ClockMode,
  FailureClass,
  IncidentSeverity,
  IncidentStatus,
  LogSeverity,
  ScenarioKey,
} from "./types";

/** Fallback period; live notices invalidate active views after committed changes. */
export const REFRESH_MS = FALLBACK_MS;

// The API refuses mutations without a JSON content type (ADR 0007), bodyless ones included.
const JSON_HEADERS = { "content-type": "application/json" } as const;

export function usePlatforms() {
  return useQuery({
    queryKey: ["platforms"],
    queryFn: () => call(api.GET("/api/v1/platforms")),
    ...usePolling(),
  });
}

export function useTopology(platformId: string | undefined) {
  return useQuery({
    queryKey: ["topology", platformId],
    queryFn: () =>
      call(
        api.GET("/api/v1/platforms/{platform_id}/topology", {
          params: { path: { platform_id: platformId ?? "" } },
        }),
      ),
    enabled: platformId !== undefined,
    ...usePolling(),
  });
}

export function useComponents() {
  return useQuery({
    queryKey: ["components"],
    queryFn: () => call(api.GET("/api/v1/components")),
    ...usePolling(),
  });
}

export function useStateHistory(request: { componentId: string; from: string; to: string } | null) {
  return useQuery({
    queryKey: ["state-history", request],
    queryFn: () =>
      call(
        api.GET("/api/v1/components/{component_id}/state-history", {
          params: {
            path: { component_id: request?.componentId ?? "" },
            query: { from: request?.from ?? null, to: request?.to ?? null, max_segments: 500 },
          },
        }),
      ),
    enabled: request !== null,
    placeholderData: keepPreviousData,
    ...usePolling(),
  });
}

export function useEvaluationHistory(
  request: { componentId: string; from: string; to: string; ruleKey?: string } | null,
) {
  return useQuery({
    queryKey: ["evaluation-history", request],
    queryFn: () =>
      call(
        api.GET("/api/v1/rule-evaluations", {
          params: {
            query: {
              component_id: request?.componentId ?? null,
              from: request?.from ?? null,
              to: request?.to ?? null,
              rule_key: request?.ruleKey ?? null,
              limit: 50,
            },
          },
        }),
      ),
    enabled: request !== null,
    ...usePolling(),
  });
}

export function useComment(id: string) {
  const onSuccess = useRefreshAll();
  return useMutation({
    mutationFn: (comment: string) =>
      call(
        api.POST("/api/v1/incidents/{incident_id}/comments", {
          params: { path: { incident_id: id } },
          body: { comment },
        }),
      ),
    onSuccess,
  });
}

export function useIncidentEvents(id: string, cursor: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["incident-events", id, cursor],
    queryFn: () =>
      call(
        api.GET("/api/v1/incidents/{incident_id}/events", {
          params: { path: { incident_id: id }, query: { cursor, limit: 200 } },
        }),
      ),
    enabled,
    ...usePolling(),
  });
}

export function useComponent(id: string) {
  return useQuery({
    queryKey: ["component", id],
    queryFn: () =>
      call(
        api.GET("/api/v1/components/{component_id}", { params: { path: { component_id: id } } }),
      ),
    ...usePolling(),
  });
}

export function useComponentRules(id: string) {
  return useQuery({
    queryKey: ["component-rules", id],
    queryFn: () =>
      call(
        api.GET("/api/v1/components/{component_id}/health", {
          params: { path: { component_id: id } },
        }),
      ),
    ...usePolling(),
  });
}

export function useHealthRules() {
  return useQuery({
    queryKey: ["health-rules"],
    queryFn: () => call(api.GET("/api/v1/health-rules")),
  });
}

export interface SeriesRequest {
  componentId: string;
  metricName: string;
  from: string;
  to: string;
}

export function useMetricSeries(request: SeriesRequest | null) {
  return useQuery({
    queryKey: ["metrics", request],
    queryFn: () =>
      call(
        api.GET("/api/v1/metrics", {
          params: {
            query: {
              component_id: request?.componentId ?? "",
              metric_name: request?.metricName ?? "",
              from: request?.from ?? null,
              to: request?.to ?? null,
              max_points: 720,
            },
          },
        }),
      ),
    enabled: request !== null,
    placeholderData: keepPreviousData,
    // The window moves with each refresh, so older entries are never read again.
    gcTime: REFRESH_MS,
    ...usePolling(),
  });
}

export function useLogs(componentId: string, minSeverity: LogSeverity) {
  return useQuery({
    queryKey: ["logs", componentId, minSeverity],
    queryFn: () =>
      call(
        api.GET("/api/v1/logs", {
          params: { query: { component_id: componentId, min_severity: minSeverity, limit: 100 } },
        }),
      ),
    ...usePolling(),
  });
}

export interface IncidentFilters {
  status?: IncidentStatus[];
  severity?: IncidentSeverity;
  failure_class?: FailureClass;
  component_id?: string;
  cursor?: string;
  limit?: number;
}

export function useIncidents(filters: IncidentFilters) {
  return useQuery({
    queryKey: ["incidents", filters],
    queryFn: () => call(api.GET("/api/v1/incidents", { params: { query: filters } })),
    placeholderData: keepPreviousData,
    ...usePolling(),
  });
}

export function useIncident(id: string) {
  return useQuery({
    queryKey: ["incident", id],
    queryFn: () =>
      call(api.GET("/api/v1/incidents/{incident_id}", { params: { path: { incident_id: id } } })),
    ...usePolling(),
  });
}

export function useDiagnostics(id: string) {
  return useQuery({
    queryKey: ["diagnostics", id],
    queryFn: () =>
      call(
        api.GET("/api/v1/incidents/{incident_id}/diagnostics", {
          params: { path: { incident_id: id } },
        }),
      ),
    // Poll stored results only; a refresh never calls a language model.
    ...usePolling(),
  });
}

export function useCitedEvidence(incidentId: string, evidenceId: number | null) {
  return useQuery({
    queryKey: ["cited-evidence", incidentId, evidenceId],
    enabled: evidenceId !== null,
    staleTime: Infinity,
    queryFn: () =>
      call(
        api.GET("/api/v1/incidents/{incident_id}/evidence", {
          params: {
            path: { incident_id: incidentId },
            query: { evidence_id: evidenceId },
          },
        }),
      ),
  });
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ["system-status"],
    queryFn: () => call(api.GET("/api/v1/system/status")),
    ...usePolling(),
    // The instrument checks its own liveness even when its event transport appears connected.
    refetchInterval: MONITOR_REFRESH_MS,
  });
}

/** ADR 0007 guard as the API reports it; `undefined` until the status has loaded. */
export function useMutationGuard(required: "engineer" | "admin" = "engineer") {
  const mutations = useSystemStatus().data?.mutations;
  const user = useSession().data?.user;
  const roleAllowed =
    user?.role === "admin" || (required === "engineer" && user?.role === "engineer");
  return { allowed: mutations?.enabled === true && roleAllowed, reason: mutations?.reason };
}

export function useScenarios() {
  return useQuery({
    queryKey: ["scenarios"],
    queryFn: () => call(api.GET("/api/v1/simulations/scenarios")),
  });
}

export function useActiveRuns() {
  return useQuery({
    queryKey: ["runs", "active"],
    queryFn: () =>
      call(api.GET("/api/v1/simulations/runs", { params: { query: { status: "active" } } })),
    ...usePolling(),
  });
}

export function useInvestigationRuns() {
  return useQuery({
    queryKey: ["runs", "investigation"],
    queryFn: () => call(api.GET("/api/v1/simulations/runs", { params: { query: { limit: 100 } } })),
    ...usePolling(),
  });
}

export function useClock() {
  return useQuery({
    queryKey: ["clock"],
    queryFn: () => call(api.GET("/api/v1/simulations/clock")),
    ...usePolling(),
  });
}

/** Local mutations invalidate immediately; events propagate changes from other clients. */
function useRefreshAll() {
  const client = useQueryClient();
  return () => client.invalidateQueries();
}

export function useAcknowledge(id: string) {
  const onSuccess = useRefreshAll();
  return useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/v1/incidents/{incident_id}/ack", {
          params: { path: { incident_id: id } },
          headers: JSON_HEADERS,
        }),
      ),
    onSuccess,
  });
}

export function useResolve(id: string) {
  const onSuccess = useRefreshAll();
  return useMutation({
    mutationFn: (comment: string) =>
      call(
        api.POST("/api/v1/incidents/{incident_id}/resolve", {
          params: { path: { incident_id: id } },
          body: { comment },
        }),
      ),
    onSuccess,
  });
}

export function useDiagnose(id: string, mode: "deterministic" | "llm" = "deterministic") {
  const onSuccess = useRefreshAll();
  return useMutation({
    // One key per click: a retried request returns the same diagnostic instead of a second one.
    mutationFn: (idempotencyKey: string) =>
      call(
        api.POST("/api/v1/incidents/{incident_id}/diagnose", {
          params: {
            path: { incident_id: id },
            query: { mode },
            header: { "Idempotency-Key": idempotencyKey },
          },
          headers: JSON_HEADERS,
        }),
      ),
    onSuccess,
  });
}

export interface StartScenario {
  scenario_key: ScenarioKey;
  target_component_key: string | null;
  duration_s: number | null;
}

export function useStartScenario() {
  const onSuccess = useRefreshAll();
  return useMutation({
    mutationFn: (body: StartScenario) =>
      call(api.POST("/api/v1/simulations/scenarios", { body: { ...body, parameters: {} } })),
    onSuccess,
  });
}

export function useStopRun() {
  const onSuccess = useRefreshAll();
  return useMutation({
    mutationFn: (runId: string) =>
      call(
        api.POST("/api/v1/simulations/runs/{run_id}/stop", {
          params: { path: { run_id: runId } },
          headers: JSON_HEADERS,
        }),
      ),
    onSuccess,
  });
}

export type ClockChange =
  | { action: "set_mode"; mode: ClockMode; speed: number | null }
  | { action: "advance"; seconds: number };

export function useSetClock() {
  const onSuccess = useRefreshAll();
  return useMutation({
    mutationFn: (body: ClockChange) => call(api.POST("/api/v1/simulations/clock", { body })),
    onSuccess,
  });
}

export function useReset() {
  const onSuccess = useRefreshAll();
  return useMutation({
    mutationFn: () => call(api.POST("/api/v1/simulations/reset", { body: null })),
    onSuccess,
  });
}

export const ACTIVE_INCIDENTS_LIMIT = 100;

/** Open and acknowledged incidents, most recently opened first; `more` when past the limit. */
export function useActiveIncidents() {
  return useQuery({
    queryKey: ["incidents", "active"],
    queryFn: async () => {
      const page = await call(
        api.GET("/api/v1/incidents", {
          params: { query: { status: ["open", "acknowledged"], limit: ACTIVE_INCIDENTS_LIMIT } },
        }),
      );
      return { items: page.items, more: page.next_cursor !== null };
    },
    ...usePolling(),
  });
}
