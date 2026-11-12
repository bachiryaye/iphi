import { Outlet } from "react-router";

import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

function SimulatedBanner() {
  return (
    <div
      role="note"
      className="sim-banner relative flex h-7 items-center justify-center gap-3 border-b border-border bg-surface-sunken px-44 text-small max-md:px-4"
    >
      <strong className="font-mono font-medium tracking-[.04em]">SIMULATED DATA</strong>
      <span className="truncate max-md:hidden">
        synthetic telemetry, not connected to any real plant
      </span>
    </div>
  );
}

export function AppShell() {
  return (
    <>
      <a
        href="#main"
        className="absolute -top-10 left-2 z-10 rounded-control border border-border-strong bg-surface px-3 py-2 focus:top-2"
      >
        Skip to content
      </a>
      <SimulatedBanner />
      <div className="grid min-h-[calc(100vh-28px)] grid-cols-[220px_minmax(0,1fr)] max-lg:grid-cols-[64px_minmax(0,1fr)]">
        <Sidebar />
        <div className="flex min-w-0 flex-col">
          <TopBar />
          <main
            id="main"
            tabIndex={-1}
            className="flex max-w-[1440px] flex-col gap-4 px-6 pt-5 pb-8 max-lg:p-4"
          >
            <Outlet />
          </main>
        </div>
      </div>
    </>
  );
}
