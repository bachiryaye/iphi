import { expect, test } from "@playwright/test";

import { demoPassword } from "./auth";
import { SEEN, Simulation } from "./simulation";

const simulation = new Simulation();
const copy = {
  en: {
    guide: "Understand and use IPHI",
    username: "Username",
    password: "Password",
    signIn: "Sign in",
    overview: "Overview",
    scenarios: "Scenarios",
    help: "Help for this page",
    next: "Beginner guide and next step",
    scenario: "Collector down",
    start: "Start scenario",
    runs: "Active scenario runs",
    components: "Components",
    critical: "Critical",
    evidence: "Evidence chain",
    diagnose: "Diagnose",
    diagnosis: "Diagnosis: deterministic",
    csv: "Export CSV",
    stop: "Stop",
    speed: "Speed",
    accelerate: "Run accelerated",
    resolved: "Resolved",
  },
  fr: {
    guide: "Comprendre et utiliser IPHI",
    username: "Identifiant",
    password: "Mot de passe",
    signIn: "Se connecter",
    overview: "Vue d’ensemble",
    scenarios: "Scénarios",
    help: "Aide pour cette page",
    next: "Guide débutant et prochaine étape",
    scenario: "Arrêt du collecteur",
    start: "Démarrer le scénario",
    runs: "Scénarios en cours",
    components: "Composants",
    critical: "Critique",
    evidence: "Chaîne de preuves",
    diagnose: "Diagnostiquer",
    diagnosis: "Diagnostic : déterministe",
    csv: "Exporter CSV",
    stop: "Arrêter",
    speed: "Vitesse",
    accelerate: "Accélérer",
    resolved: "Résolu",
  },
};

test.afterAll(async () => {
  await simulation.reset();
});

for (const language of ["en", "fr"] as const) {
  test(`finalization: beginner journey, evidence, export and recovery in ${language}`, async ({
    page,
  }) => {
    test.setTimeout(240_000);
    const labels = copy[language];
    await simulation.reset();
    await simulation.waitAllHealthy();
    await page.context().clearCookies();
    await page.goto("/help", { waitUntil: "domcontentloaded" });
    await page.getByLabel("Français / English").selectOption(language);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(labels.guide);
    await page.reload();
    await expect(page.getByLabel("Français / English")).toHaveValue(language);
    await expect(page.locator("html")).toHaveAttribute("lang", language);

    // Long-form help must remain readable without horizontal scrolling or a login.
    for (const width of [1440, 768, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.goto("/help#scenarios", { waitUntil: "domcontentloaded" });
      await expect(page.locator("#scenarios")).toBeFocused();
      const paragraph = page.locator("#scenarios").locator("..").locator("p").first();
      const reading = await paragraph.evaluate(
        (element: {
          ownerDocument: {
            defaultView: null | {
              getComputedStyle: (element: unknown) => { fontSize: string; lineHeight: string };
            };
          };
        }) => {
          const view = element.ownerDocument.defaultView;
          if (!view) throw new Error("Missing browser window");
          const style = view.getComputedStyle(element);
          return {
            size: parseFloat(style.fontSize),
            spacing: parseFloat(style.lineHeight) / parseFloat(style.fontSize),
          };
        },
      );
      expect(reading.size).toBeGreaterThanOrEqual(16);
      expect(reading.spacing).toBeGreaterThanOrEqual(1.5);
      expect(
        await page
          .locator("html")
          .evaluate(
            (element: { scrollWidth: number; clientWidth: number }) =>
              element.scrollWidth > element.clientWidth,
          ),
      ).toBe(false);
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.locator("html").evaluate((element: { style: { fontSize: string } }) => {
      element.style.fontSize = "200%";
    });
    expect(
      await page
        .locator("html")
        .evaluate(
          (element: { scrollWidth: number; clientWidth: number }) =>
            element.scrollWidth <= element.clientWidth,
        ),
    ).toBe(true);
    await page.locator("html").evaluate((element: { style: { fontSize: string } }) => {
      element.style.fontSize = "";
    });

    await page.goto("/login", { waitUntil: "domcontentloaded" });
    await page.getByLabel(labels.username, { exact: true }).fill("engineer");
    await page.getByLabel(labels.password, { exact: true }).fill(await demoPassword("engineer"));
    await page.getByRole("button", { name: labels.signIn, exact: true }).click();
    await expect(page.getByRole("heading", { name: labels.overview, level: 1 })).toBeVisible();
    const help = page.getByText(labels.help, { exact: true });
    await help.focus();
    await page.keyboard.press("Enter");
    const guideLink = page.getByRole("link", { name: labels.next });
    await guideLink.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#states")).toBeFocused();
    // Follow the in-app instructions rather than requiring an external explanation.
    const contents = page.getByRole("navigation", {
      name: language === "fr" ? "Sommaire du guide" : "Guide contents",
    });
    const disclosure = contents.locator("details");
    if (
      !(await disclosure.evaluate((element: { hasAttribute(name: string): boolean }) =>
        element.hasAttribute("open"),
      ))
    ) {
      await contents.locator("summary").click();
    }
    await contents
      .getByRole("link", {
        name:
          language === "fr"
            ? "Exercice 1 : créer une panne du collecteur"
            : "Exercise 1: create a collector fault",
      })
      .click();
    const exercise = page.locator("#scenarios").locator("..");
    const instructions = exercise.getByRole("list", {
      name: language === "fr" ? "Pas à pas" : "Step by step",
    });
    await expect(instructions).toContainText("collector_down");
    await expect(instructions).toContainText(language === "fr" ? "durée vide" : "duration empty");
    await exercise
      .getByRole("link", {
        name: language === "fr" ? "Ouvrir Scénarios" : "Open Scenarios",
        exact: true,
      })
      .click();
    const scenario = page.getByRole("region", { name: labels.scenario, exact: true });
    await expect(scenario).toContainText("collector_down");
    await scenario.getByRole("button", { name: labels.start }).click();
    await expect(
      page.getByRole("region", { name: labels.runs }).getByRole("row", { name: /collector_down/ }),
    ).toBeVisible();
    await page.getByRole("link", { name: labels.overview, exact: true }).click();
    const collector = page
      .getByRole("region", { name: labels.components, exact: true })
      .getByRole("row")
      .filter({ has: page.getByRole("rowheader", { name: /^collector-01/ }) });
    await expect(collector).toContainText(labels.critical, { timeout: SEEN });
    await collector.getByRole("link", { name: /^collector-01/ }).click();
    await expect(
      page.getByRole("region", { name: language === "fr" ? "Règles" : "Rules", exact: true }),
    ).toContainText("R-AVAIL-001");
    await expect(
      page.getByRole("region", {
        name: language === "fr" ? "Historique des métriques" : "Metric history",
        exact: true,
      }),
    ).toBeVisible();
    await page.getByRole("link", { name: labels.overview, exact: true }).click();
    const incidentLink = page.getByRole("link", { name: /collector-01 unreachable/ });
    await expect(incidentLink).toHaveCount(1, { timeout: SEEN });
    await incidentLink.click();
    await expect(page.getByRole("region", { name: labels.evidence, exact: true })).toContainText(
      "R-AVAIL-001",
    );
    await page.getByRole("button", { name: labels.diagnose, exact: true }).click();
    await expect(page.getByRole("region", { name: labels.diagnosis, exact: true })).toContainText(
      "causation is not proven",
    );
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: labels.csv, exact: true }).click();
    expect((await download).suggestedFilename()).toMatch(/^IPHI-INC-.*-simulated\.csv$/);
    const [incident] = await simulation.activeIncidents();
    if (!incident) throw new Error("Expected one collector incident");
    await page.goto("/scenarios", { waitUntil: "domcontentloaded" });
    await page
      .getByRole("region", { name: labels.runs })
      .getByRole("row", { name: /collector_down/ })
      .getByRole("button", { name: labels.stop, exact: true })
      .click();
    await page.getByLabel(labels.speed, { exact: true }).fill("30");
    await page.getByRole("button", { name: labels.accelerate, exact: true }).click();
    await expect
      .poll(async () => (await simulation.incident(incident.id)).status, { timeout: 90_000 })
      .toBe("resolved");
    await page.goto(`/incidents/${incident.id}`, { waitUntil: "domcontentloaded" });
    await expect(page.getByText(labels.resolved, { exact: true }).first()).toBeVisible();
    expect(
      (await simulation.readiness()).checks.find((check) => check.name === "ai_provider")?.status,
    ).toBe("disabled");
  });
}
