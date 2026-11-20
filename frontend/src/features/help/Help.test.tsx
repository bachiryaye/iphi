import { QueryClient } from "@tanstack/react-query";
import { screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { pageGuidance } from "@/shared/help/pageContent";
import { sections } from "@/shared/help/content";
import { LANGUAGE_KEY } from "@/shared/i18n/LanguageProvider";
import { COLLECTOR_ID, INCIDENT_ID, noIncidents, diagnostic } from "@/test/apiFixtures";
import { renderApp, seriousViolations, sessionFixture, stubApi } from "@/test/render";

beforeEach(() => {
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: false }));
});

afterEach(() => {
  localStorage.removeItem(LANGUAGE_KEY);
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("beginner help and language", () => {
  it.each(["en", "fr"] as const)(
    "offers a public, accessible guide with valid section links in %s",
    async (language) => {
      localStorage.setItem(LANGUAGE_KEY, language);
      const fetch = stubApi();
      const { container } = renderApp("/help", undefined, false);
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        language === "fr" ? "Comprendre et utiliser IPHI" : "Understand and use IPHI",
      );
      const nav = screen.getByRole("navigation", {
        name: language === "fr" ? "Sommaire du guide" : "Guide contents",
      });
      await userEvent.click(
        within(nav).getByText(language === "fr" ? "Sommaire : 16 sujets" : "Contents: 16 topics"),
      );
      expect(within(nav).getAllByRole("link")).toHaveLength(16);
      for (const entry of sections[language]) {
        const link = within(nav).getByRole("link", { name: entry.title });
        expect(link).toHaveAttribute("href", `/help#${entry.id}`);
        expect(document.getElementById(entry.id)).toHaveTextContent(entry.title);
      }
      expect(fetch.mock.calls).toHaveLength(0);
      expect(await seriousViolations(container)).toEqual([]);
    },
  );

  const pages = [
    ["/", "states"],
    ["/topology", "tour"],
    ["/components", "metrics"],
    [`/components/${COLLECTOR_ID}`, "metrics"],
    ["/incidents", "incidents"],
    [`/incidents/${INCIDENT_ID}`, "incidents"],
    ["/scenarios", "scenarios"],
    ["/rules", "rules"],
    ["/audit", "audit"],
    ["/missing", "start"],
  ];
  it.each(pages)(
    "links contextual help on %s to the relevant beginner step",
    async (path, topic) => {
      stubApi();
      renderApp(path);
      await userEvent.click(await screen.findByText("Help for this page"));
      expect(screen.getByRole("link", { name: "Beginner guide and next step" })).toHaveAttribute(
        "href",
        `/help#${topic}`,
      );
    },
  );

  it("switches language in place, preserves filters and canonical values, then restores the preference on remount", async () => {
    stubApi();
    const view = renderApp("/incidents?severity=critical");
    await screen.findByRole("heading", { name: "Incidents", level: 1 });
    expect(screen.getByLabelText("Severity")).toHaveValue("critical");
    await userEvent.selectOptions(screen.getByLabelText("Français / English"), "fr");
    expect(screen.getByLabelText("Gravité")).toHaveValue("critical");
    expect(screen.getByRole("link", { name: "Vue d’ensemble" })).toHaveAttribute("href", "/");
    await waitFor(() => {
      expect(localStorage.getItem(LANGUAGE_KEY)).toBe("fr");
    });
    expect(document.documentElement.lang).toBe("fr");
    view.unmount();
    renderApp("/scenarios");
    expect(
      (await screen.findAllByRole("button", { name: "Démarrer le scénario" })).length,
    ).toBeGreaterThan(0);
    expect(screen.getByLabelText("Français / English")).toHaveValue("fr");
    expect(screen.getByRole("region", { name: "Arrêt du collecteur" })).toHaveTextContent(
      "collector_down",
    );
  });

  it("translates empty, failure and loading states while preserving the technical error", async () => {
    localStorage.setItem(LANGUAGE_KEY, "fr");
    stubApi({
      "/api/v1/incidents": { body: noIncidents },
      "/api/v1/components": {
        status: 500,
        body: {
          code: "INTERNAL_ERROR",
          detail: "Original server detail.",
          correlation_id: "language-test",
        },
      },
    });
    renderApp();
    expect(screen.getByRole("region", { name: "Santé de la plateforme" })).toHaveAttribute(
      "aria-busy",
      "true",
    );
    expect(await screen.findByText("Aucun incident actif.")).toBeVisible();
    expect(await screen.findByRole("button", { name: "Réessayer" })).toBeVisible();
    expect(screen.getByText("Original server detail.")).toBeVisible();
    expect(screen.getByText("INTERNAL_ERROR")).toBeVisible();
    expect(screen.getByText("language-test")).toBeVisible();
  });

  it("explains viewer restrictions in French without enabling scenario mutations", async () => {
    localStorage.setItem(LANGUAGE_KEY, "fr");
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(["session"], {
      ...sessionFixture,
      user: { ...sessionFixture.user, role: "viewer" },
    });
    stubApi();
    renderApp("/scenarios", client);
    const controls = await screen.findAllByRole("button", { name: "Démarrer le scénario" });
    expect(controls.every((button) => button.hasAttribute("disabled"))).toBe(true);
    expect(screen.getByRole("button", { name: "Réinitialiser…" })).toBeDisabled();
    expect(screen.getByText(/Votre rôle est viewer/)).toBeVisible();
    expect(screen.queryByRole("link", { name: "Audit" })).not.toBeInTheDocument();
  });

  it("translates incident controls while retaining stored facts and evidence identifiers", async () => {
    localStorage.setItem(LANGUAGE_KEY, "fr");
    stubApi();
    renderApp(`/incidents/${INCIDENT_ID}`);
    const panel = await screen.findByRole("region", { name: "Diagnostic : déterministe" });
    const fact = diagnostic.observed_facts[0];
    if (!fact) throw new Error("Missing fact fixture");
    expect(panel).toHaveTextContent(fact.text);
    expect(screen.getByRole("button", { name: "Prendre en compte" })).toBeVisible();
    expect(screen.getByRole("region", { name: "Chaîne de preuves" })).toHaveTextContent(
      "R-AVAIL-001",
    );
    expect(screen.getByText(/Preuves, journaux et diagnostics/)).toBeVisible();
  });

  it("keeps entered credentials during a language switch and offers help before login", async () => {
    stubApi({
      "/api/v1/auth/me": {
        status: 401,
        body: { code: "AUTHENTICATION_REQUIRED", detail: "Sign in." },
      },
    });
    renderApp("/login", undefined, false);
    await userEvent.type(screen.getByLabelText("Username", { exact: true }), "viewer");
    await userEvent.type(screen.getByLabelText("Password", { exact: true }), "local-test-only");
    await userEvent.selectOptions(screen.getByLabelText("Français / English"), "fr");
    expect(screen.getByLabelText("Identifiant", { exact: true })).toHaveValue("viewer");
    expect(screen.getByLabelText("Mot de passe", { exact: true })).toHaveValue("local-test-only");
    await userEvent.click(screen.getByText("Aide pour cette page"));
    expect(screen.getByRole("link", { name: "Guide débutant et prochaine étape" })).toHaveAttribute(
      "href",
      "/help#start",
    );
  });

  it("keeps language switching usable when browser persistence is blocked", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    renderApp("/help", undefined, false);
    await userEvent.selectOptions(screen.getByLabelText("Français / English"), "fr");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Comprendre et utiliser IPHI",
    );
  });

  it("maps every contextual topic to a section in both languages", () => {
    for (const language of ["en", "fr"] as const)
      for (const guidance of Object.values(pageGuidance))
        expect(sections[language].some((section) => section.id === guidance.topic)).toBe(true);
  });

  it.each(["en", "fr"] as const)(
    "lets a novice find numbered fault instructions and keyboard navigation in %s",
    async (language) => {
      localStorage.setItem(LANGUAGE_KEY, language);
      renderApp("/help", undefined, false);
      const user = userEvent.setup();
      const quickLink = screen.getByRole("link", {
        name: language === "fr" ? "Je veux essayer la démo" : "I want to try the demo",
      });
      quickLink.focus();
      await user.keyboard("{Enter}");
      await waitFor(() => expect(document.getElementById("scenarios")).toHaveFocus());
      const heading = document.getElementById("scenarios");
      const chapter = heading?.closest("section");
      if (!chapter) throw new Error("Missing scenario chapter");
      const steps = within(chapter).getByRole("list", {
        name: language === "fr" ? "Pas à pas" : "Step by step",
      });
      expect(within(steps).getAllByRole("listitem")).toHaveLength(4);
      expect(steps).toHaveTextContent("collector_down");
      expect(steps).toHaveTextContent("collector-01");
      expect(steps).toHaveTextContent(language === "fr" ? "durée vide" : "duration empty");
      expect(
        within(steps).getAllByText(language === "fr" ? "Vous devez voir :" : "You should see:"),
      ).toHaveLength(4);
      const nav = screen.getByRole("navigation", {
        name: language === "fr" ? "Sommaire du guide" : "Guide contents",
      });
      await user.click(
        within(nav).getByText(language === "fr" ? "Sommaire : 16 sujets" : "Contents: 16 topics"),
      );
      await user.click(
        within(nav).getByRole("link", {
          name:
            language === "fr"
              ? "Les références industrielles de la conception"
              : "Industrial references behind the design",
        }),
      );
      await waitFor(() => expect(document.getElementById("standards")).toHaveFocus());
      expect(document.getElementById("standards")?.closest("section")).toHaveTextContent(
        "ISA/IEC 62443",
      );
      expect(document.getElementById("standards")?.closest("section")).toHaveTextContent(
        language === "fr" ? "pas un connecteur OPC UA" : "not an OPC UA adapter",
      );
    },
  );
});
