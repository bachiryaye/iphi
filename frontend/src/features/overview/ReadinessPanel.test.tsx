import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { readyBody, stalledBody } from "@/test/fixtures";
import { renderApp, seriousViolations, stubFetch, stubUnreachable } from "@/test/render";

const panel = () => screen.getByRole("region", { name: "Monitor readiness" });

describe("ReadinessPanel", () => {
  it("is busy with a static skeleton while loading", () => {
    stubFetch(200, readyBody);
    renderApp();

    expect(panel()).toHaveAttribute("aria-busy", "true");
  });

  it("states API ready and lists every check", async () => {
    stubFetch(200, readyBody);
    renderApp();

    expect(await within(panel()).findByText("API ready")).toBeInTheDocument();
    const rows = within(panel()).getAllByRole("row");
    expect(rows.map((row) => row.textContent)).toEqual([
      "CheckStatusDetailEvidence time",
      "DatabaseOKPostgreSQL reachable.—No evidence time",
      "Schema migrationsOKAt revision 0001.—No evidence time",
      "Worker heartbeatOKLast cycle took 3 ms.10:42:05 UTC",
      "AI diagnosis providerOffLLM provider 'none'; deterministic diagnosis only.—No evidence time",
    ]);
    expect(panel()).toHaveTextContent("Checked 10:42:07 UTC");
  });

  it("treats a 503 answer as a not-ready report, not a load error", async () => {
    stubFetch(503, stalledBody);
    renderApp();

    expect(await within(panel()).findByText("API not ready")).toBeInTheDocument();
    expect(panel()).toHaveTextContent("1 check failed.");
    expect(panel()).toHaveTextContent("Worker stalled: last cycle 80 s ago, expected every 5 s.");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("explains a problem response with its code and correlation ID", async () => {
    stubFetch(
      500,
      {
        type: "urn:iphi:problem:internal-error",
        title: "Internal Server Error",
        status: 500,
        detail: "An internal error occurred.",
        code: "INTERNAL_ERROR",
        correlation_id: "0192f1c4a7b37c3e",
        errors: [],
      },
      { "x-correlation-id": "0192f1c4a7b37c3e" },
    );
    renderApp();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The API answered 500 INTERNAL_ERROR.");
    expect(alert).toHaveTextContent("0192f1c4a7b37c3e");
    expect(within(alert).getByRole("button", { name: "Copy correlation ID" })).toBeInTheDocument();
  });

  it("explains an unreachable API and retries on demand", async () => {
    stubUnreachable();
    renderApp();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The API did not answer");

    const fetch = stubFetch(200, readyBody);
    await userEvent.click(within(alert).getByRole("button", { name: "Retry" }));

    expect(await within(panel()).findByText("API ready")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalled();
  });

  it("has no serious accessibility violation when not ready", async () => {
    stubFetch(503, stalledBody);
    const { container } = renderApp();
    await within(panel()).findByText("API not ready");

    expect(await seriousViolations(container)).toEqual([]);
  });
});
