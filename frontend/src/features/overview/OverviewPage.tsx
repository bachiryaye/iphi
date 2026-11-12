import { Card } from "@/shared/ui/Card";

import { ReadinessPanel } from "./ReadinessPanel";

export function OverviewPage() {
  return (
    <>
      <h1 className="text-display font-semibold">Overview</h1>
      <ReadinessPanel />
      <Card title="Platform health" titleId="platform-health-title">
        <div className="max-w-[72ch] px-4 py-4">
          <p className="font-medium">No platform health yet.</p>
          <p className="mt-1 text-text-muted">
            No platform or component is configured in this environment, so no health rule has been
            evaluated. Health states appear here once the simulated platform is running.
          </p>
        </div>
      </Card>
    </>
  );
}
