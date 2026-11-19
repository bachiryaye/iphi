import { expect, test } from "@playwright/test";

import { AUTH_STATE } from "./auth";
import { BASE_URL } from "./simulation";

const output = "../docs/design/screenshots";

test("capture bilingual help and the current dashboard", async ({ browser }) => {
  for (const view of [
    {
      name: "finalization-help-en-light-1440",
      path: "/help",
      language: "en",
      theme: "light",
      width: 1440,
      authenticated: false,
    },
    {
      name: "finalization-help-fr-dark-768",
      path: "/help",
      language: "fr",
      theme: "dark",
      width: 768,
      authenticated: false,
    },
    {
      name: "finalization-overview-fr-light-1440",
      path: "/",
      language: "fr",
      theme: "light",
      width: 1440,
      authenticated: true,
    },
    {
      name: "finalization-login-fr-light-1440",
      path: "/login",
      language: "fr",
      theme: "light",
      width: 1440,
      authenticated: false,
    },
  ] as const) {
    const context = await browser.newContext({
      baseURL: BASE_URL,
      viewport: { width: view.width, height: 900 },
      colorScheme: view.theme,
      ...(view.authenticated ? { storageState: AUTH_STATE } : {}),
    });
    await context.addInitScript((language) => {
      localStorage.setItem("iphi-language", language);
    }, view.language);
    const page = await context.newPage();
    await page.goto(view.path, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("lang", view.language);
    if (view.authenticated)
      await expect(
        page.getByRole("region", { name: "Composants", exact: true }).getByRole("table"),
      ).toBeVisible();
    await page.screenshot({ path: `${output}/${view.name}.png`, animations: "disabled" });
    await context.close();
  }
});
