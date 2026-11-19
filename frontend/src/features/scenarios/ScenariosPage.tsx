import { Play, Reset, SkipForward, Stop } from "@carbon/icons-react";
import { useId, useState } from "react";

import {
  useActiveRuns,
  useClock,
  useComponents,
  useReset,
  useScenarios,
  useSetClock,
  useStartScenario,
  useStopRun,
  useMutationGuard,
} from "@/shared/api/queries";
import type { Clock, ClockMode, Component, Scenario, ScenarioRun } from "@/shared/api/types";
import { formatValue } from "@/shared/format/number";
import { SimTag } from "@/shared/status/SimTag";
import { Timestamp } from "@/shared/status/Timestamp";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { LoadError, RefreshMeta, RefusedAlert, SkeletonRows } from "@/shared/ui/QueryStates";
import { staleClass } from "@/shared/ui/stale";
import { Segmented } from "@/shared/ui/Segmented";

const MODES = [
  { value: "realtime", label: "realtime" },
  { value: "accelerated", label: "accelerated" },
  { value: "manual", label: "manual" },
] as const;

function ClockControls({ clock, allowed }: { clock: Clock; allowed: boolean }) {
  const setClock = useSetClock();
  const speedId = useId();
  const [speed, setSpeed] = useState(String(clock.mode === "accelerated" ? clock.speed : 10));
  const change = (mode: ClockMode) => {
    setClock.mutate({
      action: "set_mode",
      mode,
      speed: mode === "accelerated" ? Number(speed) : null,
    });
  };
  return (
    <fieldset disabled={!allowed} className="flex flex-col gap-3 border-t border-border px-4 py-3">
      <legend className="sr-only">Clock controls</legend>
      <div className="flex flex-wrap items-center gap-3">
        <Segmented label="Clock mode" options={MODES} value={clock.mode} onChange={change} />
        <label htmlFor={speedId} className="text-small text-text-muted">
          Speed
        </label>
        <input
          id={speedId}
          name="clock-speed"
          autoComplete="off"
          type="number"
          min={1.1}
          max={60}
          step={1}
          value={speed}
          onChange={(event) => {
            setSpeed(event.target.value);
          }}
          className="h-8 w-20 rounded-control border border-border-strong bg-surface px-2 font-mono text-text"
        />
        <Button
          disabled={setClock.isPending || Number(speed) <= 1 || Number(speed) > 60}
          onClick={() => {
            change("accelerated");
          }}
        >
          Run accelerated
        </Button>
        {clock.mode === "manual" && (
          <Button
            icon={<SkipForward size={16} aria-hidden="true" />}
            disabled={setClock.isPending}
            onClick={() => {
              setClock.mutate({ action: "advance", seconds: 30 });
            }}
          >
            Advance 30 s
          </Button>
        )}
      </div>
      <RefusedAlert action="Clock change" error={setClock.error} />
    </fieldset>
  );
}

function ClockCard({ allowed }: { allowed: boolean }) {
  const clock = useClock();
  const data = clock.data;
  return (
    <Card
      title="Platform clock"
      titleId="clock-title"
      busy={clock.isPending}
      meta={<RefreshMeta updatedAt={clock.dataUpdatedAt} failed={clock.isError} />}
    >
      {clock.isPending && <SkeletonRows rows={2} />}
      {clock.isError && data === undefined && <LoadError what="the clock" query={clock} />}
      {data !== undefined && (
        <div className={staleClass(clock.isError)}>
          <dl className="grid grid-cols-4 gap-4 px-4 py-3 max-md:grid-cols-2">
            <div>
              <dt className="text-small text-text-muted">Platform time</dt>
              <dd>
                <Timestamp iso={data.platform_time} />
              </dd>
            </div>
            <div>
              <dt className="text-small text-text-muted">Mode</dt>
              <dd>
                {data.mode}
                {data.mode === "accelerated" && <span className="data"> ×{data.speed}</span>}
              </dd>
            </div>
            <div>
              <dt className="text-small text-text-muted">Sample interval</dt>
              <dd className="data">{data.sample_interval_s}&nbsp;s</dd>
            </div>
            <div>
              <dt className="text-small text-text-muted">Seed</dt>
              <dd className="data">{data.seed}</dd>
            </div>
          </dl>
          <ClockControls clock={data} allowed={allowed} />
        </div>
      )}
    </Card>
  );
}

function RunsCard({ allowed, scenarios }: { allowed: boolean; scenarios: readonly Scenario[] }) {
  const runs = useActiveRuns();
  const stop = useStopRun();
  const titles = new Map(scenarios.map((s) => [s.key, s.title]));
  const faults = (runs.data?.items ?? []).filter((r: ScenarioRun) => r.scenario_key !== "baseline");
  return (
    <Card
      title="Active scenario runs"
      titleId="runs-title"
      busy={runs.isPending}
      meta={
        <>
          <SimTag />
          <RefreshMeta updatedAt={runs.dataUpdatedAt} failed={runs.isError} />
        </>
      }
    >
      {runs.isPending && <SkeletonRows rows={2} />}
      {runs.isError && runs.data === undefined && <LoadError what="scenario runs" query={runs} />}
      {runs.data !== undefined && faults.length === 0 && (
        <p className="px-4 py-3 text-text-muted">
          Only the baseline runs: every component behaves nominally. Start a scenario below to
          inject a fault.
        </p>
      )}
      {faults.length > 0 && (
        <div className={`overflow-x-auto ${staleClass(runs.isError)}`}>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Run</th>
                <th scope="col">Target</th>
                <th scope="col">Started</th>
                <th scope="col">Ends</th>
                <th scope="col">
                  <span className="sr-only">Action</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {faults.map((run) => (
                <tr key={run.id}>
                  <th scope="row">
                    <span className="font-medium">
                      {titles.get(run.scenario_key) ?? run.scenario_key}
                    </span>{" "}
                    <span className="data text-text-muted">
                      {run.scenario_key} #{run.number}
                    </span>
                  </th>
                  <td>{run.target_component_key ?? "—"}</td>
                  <td>
                    <Timestamp iso={run.started_at} />
                  </td>
                  <td>{run.ends_at === null ? "when stopped" : <Timestamp iso={run.ends_at} />}</td>
                  <td className="num">
                    {
                      <Button
                        icon={<Stop size={16} aria-hidden="true" />}
                        disabled={!allowed || stop.isPending}
                        onClick={() => {
                          stop.mutate(run.id);
                        }}
                      >
                        Stop
                      </Button>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {stop.error !== null && (
        <div className="px-4 pb-3">
          <RefusedAlert action="Stop" error={stop.error} />
        </div>
      )}
    </Card>
  );
}

function ScenarioCard({
  scenario,
  components,
  allowed,
}: {
  scenario: Scenario;
  components: readonly Component[];
  allowed: boolean;
}) {
  const start = useStartScenario();
  const targetId = useId();
  const durationId = useId();
  const eligible = components.filter((c) => scenario.eligible_component_types.includes(c.type));
  const [chosen, setChosen] = useState<string | null>(null);
  const target = chosen ?? scenario.default_target_component_key ?? eligible[0]?.key ?? "";
  const [duration, setDuration] = useState("");
  const submit = (event: { preventDefault: () => void }) => {
    event.preventDefault();
    start.mutate({
      scenario_key: scenario.key,
      target_component_key: target === "" ? null : target,
      duration_s: duration === "" ? null : Number(duration),
    });
  };
  const titleId = `scenario-${scenario.key}`;
  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col rounded-card border border-border bg-surface"
    >
      <header className="flex items-baseline gap-2 border-b border-border px-4 py-2.5">
        <h3 id={titleId} className="font-semibold">
          {scenario.title}
        </h3>
        <span className="data ml-auto text-small text-text-muted">{scenario.key}</span>
      </header>
      <div className="flex flex-1 flex-col gap-3 px-4 py-3">
        <p>{scenario.description}</p>
        <dl className="grid grid-cols-[88px_minmax(0,1fr)] gap-x-3 gap-y-1 text-small">
          <dt className="text-text-muted">Signal</dt>
          <dd>{scenario.expected.signal}</dd>
          <dt className="text-text-muted">Expected state</dt>
          <dd>{scenario.expected.state}</dd>
          <dt className="text-text-muted">Incident</dt>
          <dd>{scenario.expected.incident}</dd>
          {scenario.parameters.length > 0 && (
            <>
              <dt className="text-text-muted">Parameters</dt>
              <dd>
                {scenario.parameters
                  .map(
                    (p) =>
                      `${p.name} ${formatValue(p.default, p.unit)} (${formatValue(p.minimum, p.unit)} to ${formatValue(p.maximum, p.unit)})`,
                  )
                  .join(", ")}
              </dd>
            </>
          )}
        </dl>
        {
          <form
            onSubmit={submit}
            className="mt-auto flex flex-wrap items-end gap-3 border-t border-border pt-3"
          >
            <span className="flex flex-col gap-1">
              <label htmlFor={targetId} className="text-small text-text-muted">
                Target
              </label>
              <select
                id={targetId}
                name="target"
                disabled={!allowed}
                value={target}
                onChange={(event) => {
                  setChosen(event.target.value);
                }}
                className="h-8 rounded-control border border-border-strong bg-surface px-2 text-text"
              >
                {eligible.map((c) => (
                  <option key={c.id} value={c.key}>
                    {c.key}
                  </option>
                ))}
              </select>
            </span>
            <span className="flex flex-col gap-1">
              <label htmlFor={durationId} className="text-small text-text-muted">
                Duration (s, optional)
              </label>
              <input
                id={durationId}
                name="duration"
                disabled={!allowed}
                autoComplete="off"
                type="number"
                min={10}
                max={604800}
                placeholder="until stopped"
                value={duration}
                onChange={(event) => {
                  setDuration(event.target.value);
                }}
                className="h-8 w-36 rounded-control border border-border-strong bg-surface px-2 font-mono text-text"
              />
            </span>
            <Button
              type="submit"
              variant="primary"
              icon={<Play size={16} aria-hidden="true" />}
              disabled={!allowed || start.isPending || target === ""}
            >
              {start.isPending ? "Starting…" : "Start scenario"}
            </Button>
          </form>
        }
        <RefusedAlert action="Start" error={start.error} />
        {start.isSuccess && (
          <p aria-live="polite" className="text-small text-text-muted">
            Run #{start.data.number} started on {start.data.target_component_key ?? "the platform"}.
          </p>
        )}
      </div>
    </section>
  );
}

function ResetCard() {
  const reset = useReset();
  const { allowed } = useMutationGuard("admin");
  const [confirming, setConfirming] = useState(false);
  return (
    <Card title="Reset the simulation" titleId="reset-title">
      <div className="flex flex-col gap-3 px-4 py-3">
        <p className="max-w-[72ch] text-text-muted">
          Stops every run, purges simulated observations and restarts the baseline with the same
          seed. Open incidents close with the resolution “reset”; their evidence is kept.
        </p>
        {!confirming ? (
          <div>
            <Button
              disabled={!allowed}
              icon={<Reset size={16} aria-hidden="true" />}
              onClick={() => {
                setConfirming(true);
              }}
            >
              Reset…
            </Button>
          </div>
        ) : (
          <div
            role="group"
            aria-label="Confirm reset"
            className="flex flex-wrap items-center gap-3"
          >
            <span className="font-medium">Reset the simulation now?</span>
            <Button
              variant="primary"
              disabled={!allowed || reset.isPending}
              onClick={() => {
                reset.mutate(undefined, {
                  onSettled: () => {
                    setConfirming(false);
                  },
                });
              }}
            >
              {reset.isPending ? "Resetting…" : "Confirm reset"}
            </Button>
            <Button
              onClick={() => {
                setConfirming(false);
              }}
            >
              Cancel
            </Button>
          </div>
        )}
        {!allowed && <p className="text-small text-text-muted">Reset requires the admin role.</p>}
        <RefusedAlert action="Reset" error={reset.error} />
        {reset.isSuccess && (
          <p aria-live="polite" className="text-small text-text-muted">
            Simulation reset: {reset.data.stopped_runs} runs stopped, baseline #
            {reset.data.baseline_run.number} started.
          </p>
        )}
      </div>
    </Card>
  );
}

export function ScenariosPage() {
  const { allowed, reason } = useMutationGuard();
  const scenarios = useScenarios();
  const components = useComponents();
  const faults = (scenarios.data?.items ?? []).filter((s) => s.kind === "fault");

  return (
    <>
      <h1 className="text-display font-semibold">Scenarios</h1>
      {reason !== undefined && !allowed && (
        <p className="border-l-[3px] border-border-strong bg-surface px-3 py-2 text-text-muted">
          Read-only: {reason}
        </p>
      )}
      <ClockCard allowed={allowed} />
      <RunsCard allowed={allowed} scenarios={scenarios.data?.items ?? []} />
      <Card
        title="Scenario catalog"
        titleId="catalog-title"
        busy={scenarios.isPending}
        meta={<span>expected outcomes come from the simulator catalog</span>}
      >
        {scenarios.isPending && <SkeletonRows rows={4} />}
        {scenarios.isError && scenarios.data === undefined && (
          <LoadError what="the scenario catalog" query={scenarios} />
        )}
        {faults.length > 0 && (
          <div className="grid grid-cols-3 gap-4 p-4 max-2xl:grid-cols-2 max-lg:grid-cols-1">
            {faults.map((scenario) => (
              <ScenarioCard
                key={scenario.key}
                scenario={scenario}
                components={components.data?.items ?? []}
                allowed={allowed}
              />
            ))}
          </div>
        )}
      </Card>
      <ResetCard />
    </>
  );
}
