import type { RouteObject } from "react-router";

import { OverviewPage } from "@/features/overview/OverviewPage";

import { AppShell } from "./AppShell";
import { NotFoundPage } from "./NotFoundPage";

export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
