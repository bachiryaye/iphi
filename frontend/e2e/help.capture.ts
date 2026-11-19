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
      storageState: view.authenticated ? AUTH_STATE : { cookies: [], origins: [] },
    });
    await context.addInitScript((language) => {
      localStorage.setItem("iphi-language", language);
    }, view.language);
    const page = await context.newPage();
    await page.goto(view.path, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      view.path === "/login"
        ? "Connexion à la supervision"
        : view.path === "/help"
          ? view.language === "fr"
            ? "Comprendre et utiliser IPHI"
            : "Understand and use IPHI"
          : "Vue d’ensemble",
    );
    await expect(page.locator("html")).toHaveAttribute("lang", view.language);
    if (view.authenticated)
      await expect(
        page.getByRole("region", { name: "Composants", exact: true }).getByRole("table"),
      ).toBeVisible();
    if (view.authenticated) {
      const items = page.getByRole("list", { name: "Composants par état" }).getByRole("listitem");
      for (const item of await items.all())
        expect(await item.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(
          true,
        );
    }
    if (view.path === "/login") {
      await expect(page.getByLabel("Mot de passe", { exact: true })).toHaveValue("");
      await expect(page.getByRole("group", { name: "État du moniteur" })).toContainText(
        "Moniteur actif",
      );
    }
    await page.screenshot({ path: `${output}/${view.name}.png`, animations: "disabled" });
    await context.close();
  }
});
