import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { INCIDENT_ID, statusMutable } from "@/test/apiFixtures";
import { renderApp, seriousViolations, stubApi } from "@/test/render";

describe("Incident reports", () => {
  it("allows report downloads when mutation actions are disabled", async () => {
    stubApi({
      "/api/v1/system/status": {
        body: { ...statusMutable, mutations: { enabled: false, reason: "Read-only demo." } },
      },
    });
    const { container } = renderApp(`/incidents/${INCIDENT_ID}`);
    expect(await screen.findByRole("button", { name: "Export PDF" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Export CSV" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Diagnose" })).toBeDisabled();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("shows a download error with correlation ID and keeps the incident visible", async () => {
    stubApi({
      "/api/v1/reports/incidents/:id": {
        status: 413,
        body: {
          code: "REPORT_TOO_LARGE",
          detail: "Use the paginated evidence API.",
          correlation_id: "report-123",
        },
      },
    });
    renderApp(`/incidents/${INCIDENT_ID}`);
    await userEvent.click(await screen.findByRole("button", { name: "Export PDF" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("REPORT_TOO_LARGE");
    expect(screen.getByRole("alert")).toHaveTextContent("report-123");
    expect(screen.getByRole("alert")).not.toHaveTextContent("audit log");
    expect(screen.getByRole("region", { name: "Evidence chain" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Export CSV" })).toBeEnabled();
  });

  it("disables duplicate exports while the report is being generated", async () => {
    const fallback = stubApi();
    let resolve: ((response: Response) => void) | undefined;
    vi.stubGlobal("fetch", (request: Request | string) => {
      const url = typeof request === "string" ? request : request.url;
      if (url.includes("/reports/"))
        return new Promise<Response>((done) => {
          resolve = done;
        });
      return fallback(request);
    });
    renderApp(`/incidents/${INCIDENT_ID}`);
    await userEvent.click(await screen.findByRole("button", { name: "Export CSV" }));
    expect(screen.getByRole("button", { name: "Generating…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Export PDF" })).toBeDisabled();
    resolve?.(
      new Response(JSON.stringify({ code: "REPORT_BUSY", detail: "Retry shortly." }), {
        status: 503,
        headers: { "content-type": "application/problem+json" },
      }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("REPORT_BUSY");
  });
});
