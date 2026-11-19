import type { RouteObject } from "react-router";

import { HelpPage } from "@/features/help/HelpPage";

import { AuthGate } from "@/features/identity/AuthGate";
import { LoginPage } from "@/features/identity/LoginPage";
import { AuditPage } from "@/features/identity/AuditPage";

import { ComponentPage } from "@/features/components/ComponentPage";
import { ComponentsPage } from "@/features/components/ComponentsPage";
import { IncidentPage } from "@/features/incidents/IncidentPage";
import { IncidentsPage } from "@/features/incidents/IncidentsPage";
import { OverviewPage } from "@/features/overview/OverviewPage";
import { RulesPage } from "@/features/rules/RulesPage";
import { ScenariosPage } from "@/features/scenarios/ScenariosPage";
import { TopologyPage } from "@/features/topology/TopologyPage";

import { AppShell } from "./AppShell";
import { NotFoundPage } from "./NotFoundPage";

export const routes: RouteObject[] = [
  { path: "help", element: <HelpPage /> },
  { path: "login", element: <LoginPage /> },
  {
    element: <AuthGate />,
    children: [
      {
        element: <AppShell />,
        children: [
          { index: true, element: <OverviewPage /> },
          { path: "topology", element: <TopologyPage /> },
          { path: "components", element: <ComponentsPage /> },
          { path: "components/:componentId", element: <ComponentPage /> },
          { path: "incidents", element: <IncidentsPage /> },
          { path: "incidents/:incidentId", element: <IncidentPage /> },
          { path: "scenarios", element: <ScenariosPage /> },
          { path: "rules", element: <RulesPage /> },
          { path: "audit", element: <AuditPage /> },
          { path: "*", element: <NotFoundPage /> },
        ],
      },
    ],
  },
];
