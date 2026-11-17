import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { diagnostic, incidentDetail, INCIDENT_ID, statusMutable } from "@/test/apiFixtures";
import { readyBody } from "@/test/fixtures";
import { renderApp, seriousViolations, stubApi } from "@/test/render";
import type { Diagnostic } from "@/shared/api/types";

const ai: Diagnostic = {
  ...diagnostic,
  id: "ai-1",
  kind: "llm",
  provider: "fake",
  model: "fake/evidence-v1",
  deterministic_id: diagnostic.id,
  validation: { checked_claims: 4, dropped_citations: 1, removed: ["Invented observation"] },
};

function setup(diagnosis: Diagnostic = ai) {
  return stubApi({
    "/api/v1/incidents/:id/diagnose": { status: 201, body: diagnosis },
    "/api/v1/incidents/:id/diagnostics": { body: { items: [diagnosis, diagnostic] } },
    "/api/v1/system/status": {
      body: { ...statusMutable, ai_provider: { status: "ok", detail: "Local test provider." } },
    },
  });
}

describe("AI diagnosis", () => {
  it("loads a cited proof beyond the first evidence page", async () => {
    const sample = incidentDetail.evidence[1];
    if (sample === undefined) throw new Error("Missing evidence fixture");
    stubApi({
      "/api/v1/incidents/:id/diagnostics": {
        body: {
          items: [
            {
              ...ai,
              observed_facts: [
                {
                  text: "An observation outside the first page.",
                  evidence: [{ evidence_id: 999, label: "E999" }],
                },
              ],
            },
          ],
        },
      },
      "/api/v1/incidents/:id/evidence": {
        body: { items: [{ ...sample, id: 999, label: "E999" }], next_cursor: null },
      },
    });
    renderApp(`/incidents/${INCIDENT_ID}`);
    await userEvent.click(await screen.findByRole("button", { name: /^Evidence E999/ }));
    const chain = screen.getByRole("region", { name: "Evidence chain" });
    expect(await within(chain).findByRole("rowheader", { name: "E999" })).toBeVisible();
  });
  it("labels model output and fake provider, shows removed claims and same-snapshot comparison", async () => {
    setup();
    const { container } = renderApp(`/incidents/${INCIDENT_ID}`);
    const panel = await screen.findByRole("region", { name: "Diagnosis: AI" });
    expect(panel).toHaveTextContent("AI-generated — verify against evidence");
    expect(panel).toHaveTextContent("Local test provider; no language model called");
    expect(panel).toHaveTextContent("Invented observation");
    await userEvent.click(screen.getByText("Compare with deterministic diagnosis"));
    expect(screen.getByRole("region", { name: "Diagnosis: deterministic" })).toBeVisible();
    const chip = within(panel).getByRole("button", { name: /^Evidence E2/ });
    await userEvent.click(chip);
    expect(
      within(screen.getByRole("region", { name: "Evidence chain" }))
        .getByRole("rowheader", { name: "E2" })
        .closest("tr"),
    ).toHaveClass("row-highlight");
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("displays the deterministic fallback immediately after provider failure", async () => {
    setup({
      ...ai,
      status: "failed",
      error_code: "LLM_TIMEOUT",
      observed_facts: [],
      hypotheses: [],
      recommended_checks: [],
    });
    renderApp(`/incidents/${INCIDENT_ID}`);
    expect(await screen.findByRole("status")).toHaveTextContent("LLM_TIMEOUT");
    expect(screen.getByRole("region", { name: "Diagnosis: deterministic" })).toBeVisible();
  });

  it("sends the explicit llm mode and an idempotency key", async () => {
    const fetch = setup();
    renderApp(`/incidents/${INCIDENT_ID}`);
    await userEvent.click(await screen.findByRole("button", { name: "AI diagnosis" }));
    const request = fetch.mock.calls
      .map(([input]) => input)
      .find((input) => typeof input !== "string" && input.method === "POST");
    expect(typeof request === "string" ? null : request?.url).toContain("mode=llm");
    expect(
      typeof request === "string" ? null : request?.headers.get("Idempotency-Key"),
    ).toBeTruthy();
  });

  it("keeps monitoring running when only the optional provider failed", async () => {
    stubApi({
      "/ready": {
        body: {
          ...readyBody,
          checks: readyBody.checks.map((check) =>
            check.name === "ai_provider" ? { ...check, status: "failed" } : check,
          ),
        },
      },
    });
    renderApp(`/incidents/${INCIDENT_ID}`);
    expect(await screen.findByText("AI unavailable · deterministic available")).toBeVisible();
    expect(screen.getByText("Monitor running")).toBeVisible();
  });
});
