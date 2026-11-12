import { QueryClient } from "@tanstack/react-query";
import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { readyBody, stalledBody } from "@/test/fixtures";
import { renderApp, seriousViolations, stubFetch, stubUnreachable } from "@/test/render";

describe("AppShell", () => {
  it("always labels the data as simulated", async () => {
    stubFetch(200, readyBody);
    renderApp();

    expect(screen.getByRole("note")).toHaveTextContent("SIMULATED DATA");
    await screen.findByText("API ready");
  });

  it("offers a skip link to the main content", async () => {
    stubFetch(200, readyBody);
    renderApp();

    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main");
    await screen.findByText("API ready");
  });

  it("reports a running monitor with its cycle and AI status", async () => {
    stubFetch(200, readyBody);
    renderApp();

    const monitor = screen.getByRole("group", { name: "Monitor status" });
    expect(await within(monitor).findByText("Monitor running")).toBeInTheDocument();
    expect(monitor).toHaveTextContent("last 10:42:05");
    expect(monitor).toHaveTextContent("AI diagnosis off");
  });

  it("raises a stalled monitor in the top bar", async () => {
    stubFetch(503, stalledBody);
    renderApp();

    const monitor = screen.getByRole("group", { name: "Monitor status" });
    expect(await within(monitor).findByText("Monitor stalled")).toBeInTheDocument();
  });

  it("shows the API as unreachable rather than healthy", async () => {
    stubUnreachable();
    renderApp();

    const monitor = screen.getByRole("group", { name: "Monitor status" });
    expect(await within(monitor).findByText("API unreachable")).toBeInTheDocument();
    expect(monitor).not.toHaveTextContent("Monitor running");
  });

  it("stops claiming the monitor runs once the API stops answering", async () => {
    stubFetch(200, readyBody);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderApp("/", client);
    const monitor = screen.getByRole("group", { name: "Monitor status" });
    await within(monitor).findByText("Monitor running");

    stubUnreachable();
    await act(() => client.refetchQueries({ queryKey: ["readiness"] }));

    expect(await within(monitor).findByText("API unreachable")).toBeInTheDocument();
    expect(monitor).not.toHaveTextContent("Monitor running");
    expect(monitor).toHaveTextContent("Last answer");
  });

  it("toggles and remembers the theme", async () => {
    stubFetch(200, readyBody);
    document.documentElement.dataset.theme = "light";
    renderApp();

    await userEvent.click(screen.getByRole("button", { name: "Switch to dark theme" }));

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("iphi-theme")).toBe("dark");
    expect(screen.getByRole("button", { name: "Switch to light theme" })).toBeInTheDocument();
  });

  it("renders a not-found page for unknown addresses", async () => {
    stubFetch(200, readyBody);
    renderApp("/nowhere");

    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
    await screen.findByText("Monitor running");
  });

  it("has no serious accessibility violation", async () => {
    stubFetch(200, readyBody);
    const { container } = renderApp();
    await screen.findByText("API ready");

    expect(await seriousViolations(container)).toEqual([]);
  });
});
