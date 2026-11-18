import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { COLLECTOR_ID, recordedHistory, upSeries } from "@/test/apiFixtures";
import { renderApp, seriousViolations, stubApi } from "@/test/render";

import { cursorValue } from "./cursorValue";

describe("recorded health history", () => {
  it("shares a keyboard cursor with the metric, exposes transitions and filters stored evaluations", async () => {
    const fetch = stubApi();
    renderApp(`/components/${COLLECTOR_ID}?window=15m&metric=up`);
    const slider = await screen.findByRole("slider", { name: "History time inspector" });
    slider.focus();
    fireEvent.keyDown(slider, { key: "ArrowRight" });
    expect(slider).toHaveValue(String(new Date(recordedHistory.from).getTime() + 15000));
    fireEvent.keyDown(slider, { key: "ArrowRight", shiftKey: true });
    expect(slider).toHaveValue(String(new Date(recordedHistory.from).getTime() + 75000));
    fireEvent.keyDown(slider, { key: "End" });
    expect(slider.getAttribute("aria-valuetext")).toContain("Critical");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "View states as table" }));
    const table = screen.getByRole("table", { name: "Recorded state transitions" });
    const ruleProof = within(table).getAllByRole("button", { name: "Inspect #42" })[1];
    if (ruleProof === undefined) throw new Error("Missing rule proof control");
    await user.click(ruleProof);
    expect(
      await screen.findByRole("table", { name: "Filtered stored evaluations" }),
    ).toHaveTextContent("R-AVAIL-001");
    expect(
      fetch.mock.calls.some(([request]) => {
        const url = new URL(typeof request === "string" ? request : request.url);
        return (
          url.pathname === "/api/v1/rule-evaluations" &&
          url.searchParams.get("rule_key") === "R-AVAIL-001"
        );
      }),
    ).toBe(true);
    fireEvent.keyDown(slider, { key: "Escape" });
    expect(slider.getAttribute("aria-valuetext")).toContain("Use Left");
  });

  it("reports missing evidence at the cursor instead of carrying a nearby metric through a gap", () => {
    expect(cursorValue(undefined, Date.now())).toBe("no data");
    expect(
      cursorValue(
        { ...upSeries, gaps: [{ start: upSeries.window_start, end: upSeries.window_end }] },
        new Date(upSeries.window_start).getTime(),
      ),
    ).toBe("no data");
  });

  it("restores the evaluation interval from a shared URL and ignores an invalid selection", async () => {
    stubApi();
    const selection = ["R-AVAIL-001", recordedHistory.from, recordedHistory.to].join("|");
    const { unmount } = renderApp(
      `/components/${COLLECTOR_ID}?metric=up&window=15m&evaluation=${encodeURIComponent(selection)}`,
    );
    expect(
      await screen.findByRole("table", { name: "Filtered stored evaluations" }),
    ).toHaveTextContent("R-AVAIL-001");
    unmount();
    renderApp(`/components/${COLLECTOR_ID}?evaluation=untrusted%7Cinvalid%7Cdate`);
    await screen.findByRole("slider", { name: "History time inspector" });
    expect(
      screen.queryByRole("table", { name: "Filtered stored evaluations" }),
    ).not.toBeInTheDocument();
  });

  it("has no serious accessibility violation", async () => {
    stubApi();
    const { container } = renderApp(`/components/${COLLECTOR_ID}`);
    await screen.findByRole("slider", { name: "History time inspector" });
    expect(await seriousViolations(container)).toEqual([]);
  });
});
