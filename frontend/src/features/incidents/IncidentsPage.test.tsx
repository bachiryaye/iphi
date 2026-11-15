import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { noIncidents } from "@/test/apiFixtures";
import { renderApp, seriousViolations, stubApi } from "@/test/render";

const urls = (fetch: ReturnType<typeof stubApi>) =>
  fetch.mock.calls.map(([input]) => (typeof input === "string" ? input : input.url));

describe("Incidents", () => {
  it("lists incidents densely with severity, status and evidence count", async () => {
    stubApi();
    renderApp("/incidents");

    const row = (await screen.findByRole("rowheader", { name: /INC-0007/ })).closest("tr");
    expect(row).toHaveTextContent("Critical");
    expect(row).toHaveTextContent("collector-01");
    expect(row).toHaveTextContent("availability");
    expect(row).toHaveTextContent("Open");
    expect(row).toHaveTextContent("10:39:47 UTC");
  });

  it("keeps filters in the URL and sends them to the API", async () => {
    const fetch = stubApi();
    renderApp("/incidents?status=resolved");

    expect(await screen.findByLabelText("Status")).toHaveValue("resolved");
    await userEvent.selectOptions(screen.getByLabelText("Severity"), "critical");

    await screen.findByRole("rowheader", { name: /INC-0007/ });
    expect(
      urls(fetch).some((u) => u.includes("status=resolved") && u.includes("severity=critical")),
    ).toBe(true);
  });

  it("explains an empty filtered list", async () => {
    stubApi({ "/api/v1/incidents": { body: noIncidents } });
    renderApp("/incidents?severity=warning");

    expect(await screen.findByText("No incident matches these filters.")).toBeInTheDocument();
  });

  it("has no serious accessibility violation", async () => {
    stubApi();
    const { container } = renderApp("/incidents");
    await screen.findByRole("rowheader", { name: /INC-0007/ });

    expect(await seriousViolations(container)).toEqual([]);
  });
});
