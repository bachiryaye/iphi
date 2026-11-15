import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { INCIDENT_ID, incidentDetail, statusReadOnly } from "@/test/apiFixtures";
import { renderApp, requests, seriousViolations, stubApi } from "@/test/render";

const path = `/incidents/${INCIDENT_ID}`;
const region = (name: string | RegExp) => screen.getByRole("region", { name });

describe("Incident", () => {
  it("heads with severity, reference, status and failure class", async () => {
    stubApi();
    renderApp(path);

    expect(
      await screen.findByRole("heading", { level: 1, name: "INC-0007collector-01 unreachable" }),
    ).toBeInTheDocument();
    const [facts] = screen
      .getAllByText("Failure class", { selector: "dt" })
      .map((dt) => dt.closest("dl"));
    expect(facts).toHaveTextContent("availability");
    expect(facts).toHaveTextContent("Occurrences24");
  });

  it("lists immutable evidence and highlights the row an evidence chip cites", async () => {
    stubApi();
    renderApp(path);

    const chain = await screen.findByRole("region", { name: "Evidence chain" });
    expect(within(chain).getAllByRole("row")).toHaveLength(4);
    expect(chain).toHaveTextContent("up = 0");
    const diagnosis = region(/Diagnosis/);
    const chip = await within(diagnosis).findByRole("button", { name: /^Evidence E2/ });

    await userEvent.click(chip);

    expect(chip).toHaveAttribute("aria-pressed", "true");
    expect(within(chain).getByRole("rowheader", { name: "E2" }).closest("tr")).toHaveClass(
      "row-highlight",
    );
  });

  it("separates facts, hypotheses with uncertainty, checks and limitations", async () => {
    stubApi();
    renderApp(path);

    const diagnosis = await screen.findByRole("region", { name: "Diagnosis: deterministic" });
    for (const title of ["Facts", "Hypotheses", "Checks", "Limitations"]) {
      expect(within(diagnosis).getByRole("heading", { name: title })).toBeInTheDocument();
    }
    expect(diagnosis).toHaveTextContent("Uncertainty: low");
    const [toggle] = within(diagnosis).getAllByRole("button", { name: "Show cited evidence" });
    if (toggle === undefined) throw new Error("no claim toggle");
    await userEvent.click(toggle);
    expect(diagnosis).toHaveTextContent("up = 0");
  });

  it("groups repeated occurrences in the timeline instead of listing a storm", async () => {
    stubApi();
    renderApp(path);

    const timeline = await screen.findByRole("region", { name: "Timeline" });
    expect(timeline).toHaveTextContent("Opened as critical (R-AVAIL-001)");
    expect(within(timeline).getByRole("button", { name: "3 occurrences grouped" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("acknowledges with a JSON request and refuses resolve while the condition is active", async () => {
    const fetch = stubApi({
      "/api/v1/incidents/:id/ack": { body: { ...incidentDetail, status: "acknowledged" } },
    });
    renderApp(path);

    const ack = await screen.findByRole("button", { name: "Acknowledge" });
    await userEvent.click(ack);

    const call = fetch.mock.calls.find(
      ([input]) => typeof input !== "string" && input.method === "POST",
    );
    expect(call).toBeDefined();
    const request = call?.[0];
    expect(typeof request === "string" ? null : request?.headers.get("content-type")).toBe(
      "application/json",
    );
    expect(requests(fetch)).toContain(`POST /api/v1/incidents/${INCIDENT_ID}/ack`);
    expect(screen.getByRole("button", { name: "Resolve…" })).toBeDisabled();
    expect(screen.getByText(/Resolve is unavailable while the condition is active/)).toBeVisible();
  });

  it("shows actions disabled with the reason when the API refuses mutations", async () => {
    stubApi({ "/api/v1/system/status": { body: statusReadOnly } });
    renderApp(path);

    expect(await screen.findByText(/Actions are disabled: Mutations are disabled/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Acknowledge" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Diagnose" })).toBeDisabled();
  });

  it("has no serious accessibility violation", async () => {
    stubApi();
    const { container } = renderApp(path);
    await screen.findByRole("region", { name: "Diagnosis: deterministic" });

    expect(await seriousViolations(container)).toEqual([]);
  });
});
