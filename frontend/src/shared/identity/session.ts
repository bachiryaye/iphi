import { useQuery, type QueryClient } from "@tanstack/react-query";

import { api, setCsrfToken, toApiError } from "@/shared/api/client";
import type { components } from "@/shared/api/schema";

export type Session = components["schemas"]["SessionOut"];

export function useSession() {
  return useQuery({
    queryKey: ["session"],
    queryFn: async ({ signal }): Promise<Session | null> => {
      const result = await api.GET("/api/v1/auth/me", { signal });
      if (result.response.status === 401) {
        setCsrfToken(null);
        return null;
      }
      if (!result.data) throw toApiError(result.response, result.error);
      setCsrfToken(result.data.csrf_token);
      return result.data;
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: false,
  });
}

export function safeReturnTo(value: string | null): string {
  if (!value?.startsWith("/")) return "/";
  let url: URL;
  try {
    url = new URL(value, window.location.origin);
  } catch {
    return "/";
  }
  return url.origin === window.location.origin && url.pathname !== "/login"
    ? url.pathname + url.search + url.hash
    : "/";
}

export async function clearSession(client: QueryClient) {
  await client.cancelQueries({ queryKey: ["session"] });
  setCsrfToken(null);
  client.setQueryData(["session"], null);
  client.removeQueries({ predicate: (query) => query.queryKey[0] !== "session" });
}
