import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type Problem = components["schemas"]["Problem"];

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  // Resolved per call so tests and future interceptors can replace the global fetch.
  fetch: (request) => globalThis.fetch(request),
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
