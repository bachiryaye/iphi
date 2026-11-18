import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { INCIDENT_ID, incidentDetail } from "@/test/apiFixtures";
import { renderApp, requests, stubApi } from "@/test/render";

describe("investigation notes", () => {
  it("submits one note, refreshes and keeps untrusted text inert", async () => {
    const fetch = stubApi({
      [`/api/v1/incidents/${INCIDENT_ID}/comments`]: { body: incidentDetail, status: 201 },
    });
    renderApp(`/incidents/${INCIDENT_ID}`);
    const user = userEvent.setup();
    const field = await screen.findByRole("textbox", { name: "Investigation comment" });
    await waitFor(() => {
      expect(field).toBeEnabled();
    });
    await user.type(field, "Collector checked; investigate network path.");
    await user.click(screen.getByRole("button", { name: "Add comment" }));
    expect(await screen.findByText("Comment saved in the timeline.")).toBeInTheDocument();
    expect(requests(fetch).filter((r) => r.endsWith("/comments"))).toEqual([
      `POST /api/v1/incidents/${INCIDENT_ID}/comments`,
    ]);
    expect(field).toHaveValue("");
  });

  it("loads later timeline events and renders comment text safely", async () => {
    stubApi({
      [`/api/v1/incidents/${INCIDENT_ID}`]: {
        body: { ...incidentDetail, events_next_cursor: "next", event_count: 201 },
      },
      [`/api/v1/incidents/${INCIDENT_ID}/events`]: {
        body: {
          environment: "simulation",
          items: [
            {
              ...incidentDetail.events[0],
              id: 999,
              type: "commented",
              payload: { comment: "<script>never execute</script>" },
            },
          ],
          next_cursor: null,
        },
      },
    });
    renderApp(`/incidents/${INCIDENT_ID}`);
    await userEvent.setup().click(await screen.findByRole("button", { name: "Load more events" }));
    expect(await screen.findByText("“<script>never execute</script>”")).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
  });
});
