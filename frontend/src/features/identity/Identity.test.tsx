import { QueryClient } from "@tanstack/react-query";
import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { safeReturnTo } from "@/shared/identity/session";
import { renderApp, seriousViolations, sessionFixture, stubApi } from "@/test/render";

const denied = {
  status: 401,
  body: { code: "AUTHENTICATION_REQUIRED", detail: "Sign in.", correlation_id: "identity-test" },
};

describe("identity", () => {
  it.each([
    "https://example.invalid",
    "//example.invalid",
    "/\\example.invalid",
    "//[",
    "/login",
    "javascript:alert(1)",
  ])("rejects unsafe return destinations: %s", (destination) => {
    expect(safeReturnTo(destination)).toBe("/");
  });

  it("preserves internal investigation links", () => {
    expect(safeReturnTo("/incidents?status=open")).toBe("/incidents?status=open");
  });

  it("signs in and returns to the protected view without browser credential storage", async () => {
    const fetch = stubApi({
      "/api/v1/auth/me": denied,
      "/api/v1/auth/login": { body: sessionFixture },
    });
    renderApp("/scenarios", undefined, false);
    await userEvent.type(await screen.findByLabelText("Username", { exact: true }), "admin");
    await userEvent.type(screen.getByLabelText("Password", { exact: true }), "local-test-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Scenarios" })).toBeVisible();
    const login = fetch.mock.calls.find(
      ([request]) =>
        request instanceof Request && new URL(request.url).pathname === "/api/v1/auth/login",
    )?.[0];
    expect(login).toBeInstanceOf(Request);
    expect(localStorage.getItem("iphi_session")).toBeNull();
    expect(sessionStorage.getItem("iphi_session")).toBeNull();
  });

  it("shows a rejected login and clears the entered password", async () => {
    stubApi({
      "/api/v1/auth/me": denied,
      "/api/v1/auth/login": {
        status: 401,
        body: {
          code: "INVALID_CREDENTIALS",
          detail: "The username or password is incorrect.",
          correlation_id: "login-test",
        },
      },
    });
    renderApp("/login", undefined, false);
    await userEvent.type(screen.getByLabelText("Username", { exact: true }), "viewer");
    await userEvent.type(screen.getByLabelText("Password", { exact: true }), "local-test-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText(/The username or password is incorrect/)).toBeVisible();
    expect(screen.getByLabelText("Password", { exact: true })).toHaveValue("");
  });

  it("keeps scenario controls visible and disabled for viewer", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(["session"], {
      ...sessionFixture,
      user: { ...sessionFixture.user, role: "viewer" },
    });
    stubApi();
    renderApp("/scenarios", client);
    const buttons = await screen.findAllByRole("button", { name: "Start scenario" });
    expect(buttons.every((button) => button.hasAttribute("disabled"))).toBe(true);
    expect(screen.getByRole("button", { name: "Reset…" })).toBeDisabled();
    expect(screen.queryByRole("link", { name: "Audit" })).not.toBeInTheDocument();
    expect(screen.getByText("Reset requires the admin role.")).toBeVisible();
  });

  it("returns to sign-in after session rejection and removes operational cache", async () => {
    stubApi();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderApp("/scenarios", client);
    await screen.findByRole("region", { name: "Collector down" });
    await act(() => window.dispatchEvent(new Event("iphi:session-expired")));
    expect(
      await screen.findByRole("heading", { name: "Sign in to platform health" }),
    ).toBeVisible();
    expect(client.getQueryData(["platforms"])).toBeUndefined();
  });

  it("shows admin audit filters, refusal details and safe text", async () => {
    stubApi({
      "/api/v1/audit-events": {
        body: {
          environment: "simulation",
          next_cursor: null,
          items: [
            {
              id: "audit-test",
              occurred_at: "2026-11-18T10:00:00Z",
              actor_label: "viewer",
              action: "scenario.start",
              target_type: "scenario",
              target_id: null,
              outcome: "denied",
              correlation_id: "audit-correlation",
              details: { reason: "<script>untrusted</script>" },
            },
          ],
        },
      },
    });
    const { container } = renderApp("/audit?outcome=denied");
    expect(await screen.findByRole("table")).toHaveTextContent("viewer");
    await userEvent.click(screen.getByText("Inspect event", { exact: true }));
    expect(screen.getByText("audit-correlation")).toBeVisible();
    expect(container.querySelector("script")).toBeNull();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("has an accessible sign-in form with password autofill", async () => {
    stubApi({ "/api/v1/auth/me": denied });
    const { container } = renderApp("/login", undefined, false);
    expect(screen.getByLabelText("Username")).toHaveAttribute("autocomplete", "username");
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "current-password");
    expect(screen.getByLabelText("Password").closest("form")).toHaveAttribute("method", "post");
    expect(await seriousViolations(container)).toEqual([]);
  });
});
