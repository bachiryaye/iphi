import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, toApiError, unreachable } from "./client";
import type {
  ClockMode,
  FailureClass,
  IncidentSeverity,
  IncidentStatus,
  LogSeverity,
  ScenarioKey,
} from "./types";

/** Polling period of every operator view until SSE arrives (US-07). */
export const REFRESH_MS = 10_000;

interface Result<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** Turns an openapi-fetch result into data or an ApiError; a network failure is "unreachable". */
export async function call<T>(request: Promise<Result<T>>): Promise<T> {
  let result: Result<T>;
  try {
    result = await request;
  } catch {
    throw unreachable();
  }
  if (result.response.ok && result.data !== undefined) return result.data;
  throw toApiError(result.response, result.error);
}

// The API refuses mutations without a JSON content type (ADR 0007), bodyless ones included.
const JSON_HEADERS = { "content-type": "application/json" } as const;

// Half a period of freshness: components mounting after the first answer reuse it.
const polled = { refetchInterval: REFRESH_MS, staleTime: REFRESH_MS / 2 } as const;

export function usePlatforms() {
  return useQuery({
    queryKey: ["platforms"],
    queryFn: () => call(api.GET("/api/v1/platforms")),
    ...polled,
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
    ...polled,
  });
}

export function useComponents() {
  return useQuery({
    queryKey: ["components"],
    queryFn: () => call(api.GET("/api/v1/components")),
    ...polled,
  });
}

export function useComponent(id: string) {
  return useQuery({
    queryKey: ["component", id],
    queryFn: () =>
      call(
        api.GET("/api/v1/components/{component_id}", { params: { path: { component_id: id } } }),
      ),
    ...polled,
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
    ...polled,
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
    ...polled,
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
    ...polled,
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
    ...polled,
  });
}

export function useIncident(id: string) {
  return useQuery({
    queryKey: ["incident", id],
    queryFn: () =>
      call(api.GET("/api/v1/incidents/{incident_id}", { params: { path: { incident_id: id } } })),
    ...polled,
    // A resolved incident only changes when reopened, which the incident list shows.
    refetchInterval: (query: { state: { data?: { status: string } | undefined } }) =>
      query.state.data?.status === "resolved" ? false : REFRESH_MS,
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
    ...polled,
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
    ...polled,
  });
}

/** ADR 0007 guard as the API reports it; `undefined` until the status has loaded. */
export function useMutationGuard() {
  const mutations = useSystemStatus().data?.mutations;
  return { allowed: mutations?.enabled === true, reason: mutations?.reason };
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
    ...polled,
  });
}

export function useClock() {
  return useQuery({
    queryKey: ["clock"],
    queryFn: () => call(api.GET("/api/v1/simulations/clock")),
    ...polled,
  });
}

/** Every view polls; after a mutation they all refetch at once instead of within 10 s. */
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
    ...polled,
  });
}
