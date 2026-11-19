import { expect, test } from "@playwright/test";

import { AUTH_STATE, demoPassword } from "./auth";
import { BASE_URL, VIEWPORT } from "./simulation";

test("7. viewer cannot inject a fault; the refusal is visible to admin in audit", async ({
  browser,
}) => {
  const viewer = await browser.newContext({
    baseURL: BASE_URL,
    viewport: VIEWPORT,
    storageState: { cookies: [], origins: [] },
  });
  const admin = await browser.newContext({ baseURL: BASE_URL, storageState: AUTH_STATE });
  try {
    expect((await viewer.request.get("/api/v1/platforms")).status()).toBe(401);
    const page = await viewer.newPage();
    await page.goto("/scenarios");
    await page.waitForURL((url) => url.pathname === "/login");
    await expect(page.getByRole("heading", { name: "Sign in to platform health" })).toBeVisible();
    await page.getByLabel("Username", { exact: true }).fill("viewer");
    await page.getByLabel("Password", { exact: true }).fill(await demoPassword("viewer"));
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Scenarios", exact: true })).toBeVisible();
    await expect(
      page
        .getByRole("region", { name: "Collector down" })
        .getByRole("button", { name: "Start scenario" }),
    ).toBeDisabled();
    await expect(page.getByRole("button", { name: "Reset…" })).toBeDisabled();
    await expect(page.getByRole("link", { name: "Audit", exact: true })).toHaveCount(0);
    const sessionResponse = await viewer.request.get("/api/v1/auth/me");
    const session: unknown = await sessionResponse.json();
    if (
      typeof session !== "object" ||
      session === null ||
      !("csrf_token" in session) ||
      typeof session.csrf_token !== "string"
    )
      throw new Error("Invalid viewer session.");
    const attempt = await viewer.request.post("/api/v1/simulations/scenarios", {
      data: { scenario_key: "collector_down" },
      headers: { "x-csrf-token": session.csrf_token },
    });
    expect(attempt.status()).toBe(403);
    const problem: unknown = await attempt.json();
    expect(problem).toMatchObject({ code: "PERMISSION_DENIED" });
    const audit = await admin.request.get(
      "/api/v1/audit-events?action=scenario.start&outcome=denied&actor=viewer",
    );
    expect(audit.status()).toBe(200);
    const events: unknown = await audit.json();
    expect(events).toMatchObject({
      items: expect.arrayContaining([
        expect.objectContaining({ actor_label: "viewer", outcome: "denied" }),
      ]),
    });
    const auditPage = await admin.newPage();
    await auditPage.goto("/audit?action=scenario.start&outcome=denied");
    await expect(auditPage.getByRole("table")).toContainText("viewer");
    await page.getByText("viewer · viewer", { exact: true }).click();
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await page.waitForURL((url) => url.pathname === "/login");
    await expect(page.getByRole("heading", { name: "Sign in to platform health" })).toBeVisible();
    expect((await viewer.request.get("/api/v1/platforms")).status()).toBe(401);
  } finally {
    await viewer.close();
    await admin.close();
  }
});
