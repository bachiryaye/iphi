import { act, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { components } from "@/shared/api/schema";
import { renderApp, stubApi } from "@/test/render";

type Notice = components["schemas"]["StreamEventOut"];
const BASE: Notice = {
  type: "sync",
  id: "stream",
  platform_time: "2026-11-18T00:00:00Z",
  environment: "simulation",
};

class Source extends EventTarget {
  static instances: Source[] = [];
  onerror: ((event: Event) => void) | null = null;
  close = vi.fn();
  constructor(readonly url: string) {
    super();
    Source.instances.push(this);
  }
  send(notice: Notice) {
    this.dispatchEvent(new MessageEvent(notice.type, { data: JSON.stringify(notice) }));
  }
}

beforeEach(() => {
  Source.instances = [];
});

function source(): Source {
  const found = Source.instances[0];
  if (found === undefined) throw new Error("No EventSource created.");
  return found;
}

describe("Live updates", () => {
  it("coalesces committed notices into one refresh and announces a new incident", async () => {
    vi.stubGlobal("EventSource", Source);
    const fetch = stubApi();
    renderApp("/");
    await screen.findByRole("region", { name: "Components" });
    const componentRequests = () =>
      fetch.mock.calls.filter(
        ([request]) =>
          new URL(typeof request === "string" ? request : request.url).pathname ===
          "/api/v1/components",
      ).length;
    const before = componentRequests();
    act(() => {
      source().send(BASE);
      source().send({ ...BASE, type: "component.health_changed", id: "component-1" });
      source().send({ ...BASE, type: "incident.opened", id: "incident-1" });
    });
    await waitFor(() => {
      expect(componentRequests()).toBe(before + 1);
    });
    expect(screen.queryByText(/Connecting live updates/)).not.toBeInTheDocument();
    expect(screen.getByText(/New incident detected/)).toHaveAttribute("aria-live", "polite");
  });

  it("shows the 30 s fallback after disconnection and resynchronizes on the next sync", async () => {
    vi.stubGlobal("EventSource", Source);
    stubApi();
    const { unmount } = renderApp("/");
    await screen.findByRole("region", { name: "Components" });
    act(() => {
      source().send(BASE);
    });
    act(() => {
      source().onerror?.(new Event("error"));
    });
    expect(screen.getByText(/Live updates paused/)).toHaveTextContent("every 30 s");
    act(() => {
      source().send(BASE);
    });
    expect(screen.queryByText(/Live updates paused/)).not.toBeInTheDocument();
    unmount();
    expect(source().close).toHaveBeenCalledOnce();
  });

  it("ignores malformed frames and uses polling when EventSource is unavailable", async () => {
    vi.stubGlobal("EventSource", Source);
    stubApi();
    const { unmount } = renderApp("/");
    await screen.findByRole("region", { name: "Components" });
    act(() => {
      source().dispatchEvent(new MessageEvent("sync", { data: "not JSON" }));
    });
    expect(screen.getByText(/Connecting live updates/)).toBeVisible();
    unmount();
    vi.stubGlobal("EventSource", undefined);
    renderApp("/");
    expect(screen.getByText(/unavailable in this browser/)).toHaveTextContent("every 30 s");
  });

  it("closes an existing stream immediately offline and resynchronizes online", async () => {
    vi.stubGlobal("EventSource", Source);
    stubApi();
    const { unmount } = renderApp("/");
    await screen.findByRole("region", { name: "Components" });
    act(() => {
      source().send(BASE);
    });
    act(() => {
      window.dispatchEvent(new Event("offline"));
    });
    expect(source().close).toHaveBeenCalledOnce();
    expect(screen.getByText(/Live updates paused/)).toBeVisible();
    act(() => {
      window.dispatchEvent(new Event("online"));
    });
    const next = Source.instances.at(-1);
    if (next === undefined) throw new Error("No reconnected stream");
    expect(next).not.toBe(source());
    act(() => {
      next.send(BASE);
    });
    expect(screen.queryByText(/Live updates paused/)).not.toBeInTheDocument();
    unmount();
    const count = Source.instances.length;
    act(() => {
      window.dispatchEvent(new Event("online"));
    });
    expect(Source.instances).toHaveLength(count);
  });
});
