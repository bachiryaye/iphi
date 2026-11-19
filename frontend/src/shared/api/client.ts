import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type Problem = components["schemas"]["Problem"];

let csrfToken: string | null = null;

export function setCsrfToken(value: string | null) {
  csrfToken = value;
}

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: "same-origin",
  // Resolved per call so tests and future interceptors can replace the global fetch.
  fetch: (request) => globalThis.fetch(request),
});

api.use({
  onRequest({ request }) {
    if (!["GET", "HEAD"].includes(request.method) && csrfToken !== null) {
      request.headers.set("x-csrf-token", csrfToken);
    }
    return request;
  },
  onResponse({ request, response }) {
    const path = new URL(request.url).pathname;
    if (response.status === 401 && !path.startsWith("/api/v1/auth/")) {
      window.dispatchEvent(new Event("iphi:session-expired"));
    }
    return response;
  },
});

export class ApiError extends Error {
  constructor(
    readonly status: number | null,
    readonly code: string,
    message: string,
    readonly correlationId: string | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isProblem(value: unknown): value is Problem {
  return (
    typeof value === "object" &&
    value !== null &&
    "code" in value &&
    typeof value.code === "string" &&
    "detail" in value &&
    typeof value.detail === "string"
  );
}

export function toApiError(response: Response, body: unknown): ApiError {
  const correlationId = response.headers.get("x-correlation-id");
  if (isProblem(body)) {
    return new ApiError(
      response.status,
      body.code,
      body.detail,
      body.correlation_id ?? correlationId,
    );
  }
  return new ApiError(
    response.status,
    `HTTP_${String(response.status)}`,
    `The API answered ${String(response.status)} without problem details.`,
    correlationId,
  );
}

export const unreachable = (): ApiError =>
  new ApiError(null, "API_UNREACHABLE", "The API did not answer.", null);

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
