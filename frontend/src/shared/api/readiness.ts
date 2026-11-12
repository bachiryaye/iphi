import { useQuery } from "@tanstack/react-query";

import { api, toApiError, unreachable } from "./client";
import type { components } from "./schema";

export type Readiness = components["schemas"]["ReadinessOut"];
export type ReadinessCheck = components["schemas"]["ReadinessCheckOut"];
export type CheckName = components["schemas"]["CheckName"];

export const READINESS_REFRESH_MS = 10_000;

function isReadiness(value: unknown): value is Readiness {
  return typeof value === "object" && value !== null && "checks" in value && "status" in value;
}

/** Resolves for both 200 and 503: "not ready" is a valid answer, not a transport failure. */
export async function fetchReadiness(): Promise<Readiness> {
  const result = await api.GET("/ready").catch(() => {
    throw unreachable();
  });
  if (result.data) return result.data;
  if (result.response.status === 503 && isReadiness(result.error)) return result.error;
  throw toApiError(result.response, result.error);
}

export function useReadiness() {
  return useQuery({
    queryKey: ["readiness"],
    queryFn: fetchReadiness,
    refetchInterval: READINESS_REFRESH_MS,
  });
}
