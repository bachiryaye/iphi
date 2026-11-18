import type {
  Clock,
  Component,
  ComponentDetail,
  ComponentRules,
  Diagnostic,
  Evaluation,
  HealthRule,
  IncidentDetail,
  IncidentPage,
  KeyMetric,
  MetricSeries,
  Platform,
  ScenarioCatalog,
  SystemStatus,
  Topology,
  StateHistory,
} from "@/shared/api/types";

/** collector_down #12 on the simulated platform, as the API reports it at 10:42:05 UTC. */
export const PLATFORM_ID = "0b6f1e1a-0000-4000-8000-000000000001";
export const NOW = "2026-11-12T10:42:05Z";
const SINCE = "2026-11-12T10:39:47Z";

const id = (n: number) => `0b6f1e1a-0000-4000-8000-0000000001${String(n).padStart(2, "0")}`;
export const COLLECTOR_ID = id(3);
export const INCIDENT_ID = "0b6f1e1a-0000-4000-8000-000000000901";

export const recordedHistory: StateHistory = {
  environment: "simulation",
  source: "rule_evaluations",
  component: { id: COLLECTOR_ID, key: "collector-01" },
  from: "2026-11-12T10:27:05Z",
  to: NOW,
  reset_at: "2026-11-12T10:25:00Z",
  component_lane: {
    key: "component",
    versions: [],
    aggregated: false,
    segments: [
      {
        from: "2026-11-12T10:27:05Z",
        to: SINCE,
        state: "healthy",
        evaluation_ids: [11],
        contains_unknown: false,
      },
      { from: SINCE, to: NOW, state: "critical", evaluation_ids: [42], contains_unknown: false },
    ],
  },
  rules: [
    {
      key: "R-AVAIL-001",
      versions: [1],
      aggregated: false,
      segments: [
        {
          from: "2026-11-12T10:27:05Z",
          to: SINCE,
          state: "healthy",
          evaluation_ids: [11],
          contains_unknown: false,
        },
        { from: SINCE, to: NOW, state: "critical", evaluation_ids: [42], contains_unknown: false },
      ],
    },
  ],
};

const healthy = {
  state: "healthy",
  evaluated_state: "healthy",
  since: "2026-11-12T10:12:00Z",
  evaluated_at: NOW,
  stale: false,
  stale_reason: null,
} as const;

const rule = (key: string) => ({ id: `${key}-id`, key, version: 1 });

export const latencyMetric = (value: number | null): KeyMetric => ({
  name: "probe_latency_ms",
  unit: "ms",
  kind: "meter",
  aggregation: "p95",
  window_seconds: 60,
  value,
  evaluated_at: NOW,
  display_min: 0,
  display_max: 1250,
  warning_threshold: 250,
  critical_threshold: 1000,
  rule: rule("R-LAT-001"),
  state: value === null ? "unknown" : "healthy",
  since: "2026-11-12T10:12:00Z",
  evaluation_id: 8873,
});

const ageMetric = (value: number): KeyMetric => ({
  name: "data_age_s",
  unit: "s",
  kind: "meter",
  aggregation: "last",
  window_seconds: 10,
  value,
  evaluated_at: NOW,
  display_min: 0,
  display_max: 375,
  warning_threshold: 60,
  critical_threshold: 300,
  rule: rule("R-FRESH-001"),
  state: value > 60 ? "warning" : "healthy",
  since: "2026-11-12T10:40:30Z",
  evaluation_id: 8870,
});

const collectorRef = { id: COLLECTOR_ID, key: "collector-01" };

function component(
  n: number,
  key: string,
  type: Component["type"],
  overrides: Partial<Component> = {},
): Component {
  return {
    id: id(n),
    key,
    name: key,
    type,
    criticality: "high",
    platform_id: PLATFORM_ID,
    environment: "simulation",
    health: healthy,
    reason: null,
    impacted_by: [],
    key_metric: latencyMetric(42),
    ...overrides,
  };
}

const availabilityReason: Evaluation = {
  id: 8812,
  rule: rule("R-AVAIL-001"),
  component: collectorRef,
  evaluated_at: NOW,
  window_start: "2026-11-12T10:41:55Z",
  observed_value: 0,
  unit: "bool",
  sample_count: 2,
  raw_state: "critical",
  state: "critical",
  explanation: "last(up, 10 s) = 0 < 1: probe not answered.",
  evidence: { sample_ids: [501, 502], log_ids: [] },
};

export const components: Component[] = [
  component(1, "plc-sim-01", "source"),
  component(2, "edge-gateway-01", "gateway", { key_metric: latencyMetric(61) }),
  component(3, "collector-01", "collector", {
    health: { ...healthy, state: "critical", evaluated_state: "critical", since: SINCE },
    reason: availabilityReason,
    key_metric: {
      name: "up",
      unit: "bool",
      kind: "availability",
      aggregation: "last",
      window_seconds: 10,
      value: 0,
      evaluated_at: NOW,
      display_min: 0,
      display_max: 1,
      warning_threshold: null,
      critical_threshold: 1,
      rule: rule("R-AVAIL-001"),
      state: "critical",
      since: SINCE,
      evaluation_id: 8812,
    },
  }),
  component(4, "historian-01", "historian", {
    health: {
      ...healthy,
      state: "warning",
      evaluated_state: "warning",
      since: "2026-11-12T10:40:30Z",
    },
    impacted_by: [collectorRef],
    key_metric: ageMetric(148),
  }),
  component(5, "timeseries-db-01", "database"),
  component(6, "data-api-01", "api", { criticality: "medium", impacted_by: [collectorRef] }),
  component(7, "analytics-01", "analytics", {
    criticality: "low",
    health: {
      ...healthy,
      state: "unknown",
      evaluated_state: "unknown",
      since: "2026-11-12T10:41:00Z",
    },
    impacted_by: [collectorRef],
    key_metric: latencyMetric(null),
  }),
];

export const platform: Platform = {
  id: PLATFORM_ID,
  key: "demo-plant",
  name: "Demo Plant Data Platform",
  environment: "simulation",
  health: {
    state: "critical",
    evaluated_state: "critical",
    since: SINCE,
    evaluated_at: NOW,
    stale: false,
    stale_reason: null,
    counts: { healthy: 4, warning: 1, critical: 1, unknown: 1 },
    priority: 1,
    rationale: "Priority 1: a high-criticality component is Critical (collector-01).",
    decided_by: [collectorRef],
  },
};

export const healthyPlatform: Platform = {
  ...platform,
  health: {
    ...platform.health,
    state: "healthy",
    evaluated_state: "healthy",
    counts: { healthy: 7, warning: 0, critical: 0, unknown: 0 },
    priority: 4,
    rationale: "Priority 4: all 7 components are Healthy.",
    decided_by: [],
  },
};

export const incident: IncidentPage["items"][number] = {
  id: INCIDENT_ID,
  number: 7,
  reference: "INC-0007",
  title: "collector-01 unreachable",
  platform_id: PLATFORM_ID,
  component: collectorRef,
  environment: "simulation",
  failure_class: "availability",
  severity: "critical",
  peak_severity: "critical",
  status: "open",
  opened_at: SINCE,
  last_seen_at: "2026-11-12T10:42:02Z",
  acknowledged_at: null,
  acknowledged_by: null,
  resolved_at: null,
  resolved_by: null,
  resolution: null,
  occurrence_count: 24,
  reopen_count: 0,
  evidence_count: 3,
  fingerprint: "3f2a9c71d0e4b8a2",
  scenario_run_id: null,
  source: "simulation",
  impacted: [{ component: { id: id(4), key: "historian-01" }, since: "2026-11-12T10:40:12Z" }],
};

export const activeIncidents: IncidentPage = {
  environment: "simulation",
  items: [incident],
  next_cursor: null,
};

export const noIncidents: IncidentPage = {
  environment: "simulation",
  items: [],
  next_cursor: null,
};

const event = (n: number, type: IncidentDetail["events"][number]["type"], at: string) => ({
  id: n,
  type,
  occurred_at: at,
  actor_type: "system" as const,
  actor_label: "system",
  payload: { severity: "critical", rule_key: "R-AVAIL-001", evaluation_id: 8800 + n },
});

export const incidentDetail: IncidentDetail = {
  ...incident,
  resolvable: false,
  condition: [
    {
      rule: rule("R-AVAIL-001"),
      failure_class: "availability",
      state: "critical",
      raw_state: "critical",
      alerting: true,
      evaluated_at: NOW,
    },
  ],
  evidence: [
    {
      id: 1,
      label: "E1",
      kind: "evaluation",
      role: "trigger",
      added_at: SINCE,
      component: collectorRef,
      evaluation: availabilityReason,
      sample: null,
      log: null,
    },
    {
      id: 2,
      label: "E2",
      kind: "sample",
      role: "trigger",
      added_at: SINCE,
      component: collectorRef,
      evaluation: null,
      sample: {
        id: 502,
        metric_name: "up",
        value: 0,
        unit: "bool",
        observed_at: SINCE,
        quality: "good",
        source: "simulation",
        scenario_run_id: null,
      },
      log: null,
    },
    {
      id: 3,
      label: "E3",
      kind: "log",
      role: "supporting",
      added_at: SINCE,
      component: collectorRef,
      evaluation: null,
      sample: null,
      log: {
        id: 77,
        severity: "error",
        message: "connection refused by upstream gateway",
        fingerprint: "a91c4e02",
        observed_at: "2026-11-12T10:39:46Z",
        source: "simulation",
        scenario_run_id: null,
      },
    },
  ],
  evidence_next_cursor: null,
  events: [
    event(1, "opened", SINCE),
    event(2, "occurrence", "2026-11-12T10:39:52Z"),
    event(3, "occurrence", "2026-11-12T10:39:57Z"),
    event(4, "occurrence", "2026-11-12T10:40:02Z"),
  ],
  event_count: 4,
  events_next_cursor: null,
};

export const diagnostic: Diagnostic = {
  id: "diag-1",
  incident_id: INCIDENT_ID,
  environment: "simulation",
  kind: "deterministic",
  provider: "iphi",
  model: "deterministic/v1",
  status: "succeeded",
  created_at: "2026-11-12T10:41:10Z",
  created_by: "local-dev",
  evidence_set_hash: "abc",
  observed_facts: [
    {
      text: "collector-01 did not answer 24 consecutive probes.",
      evidence: [{ evidence_id: 2, label: "E2" }],
    },
  ],
  hypotheses: [
    {
      text: "collector-01 is the most upstream failing component.",
      evidence: [{ evidence_id: 1, label: "E1" }],
      uncertainty: "low",
    },
  ],
  recommended_checks: [
    { text: "Verify the collector-01 process.", evidence: [{ evidence_id: 3, label: "E3" }] },
  ],
  limitations: ["Simulated environment; no host-level metrics."],
  validation: { checked_claims: 3, dropped_citations: 0, removed: [] },
};

const status = (mutations: boolean): SystemStatus => ({
  environment: "simulation",
  checked_at: NOW,
  cycle_interval_s: 5,
  clock: { mode: "realtime", speed: 1, platform_time: NOW },
  worker: { status: "ok", detail: "Last cycle took 3 ms.", heartbeat: null },
  collection: { state: "ok", connectors: [], recent_runs: [] },
  ai_provider: { status: "disabled", detail: "LLM provider 'none'." },
  mutations: mutations
    ? { enabled: true, reason: "Local development mutations enabled (unauthenticated, ADR 0007)." }
    : {
        enabled: false,
        reason: "Mutations are disabled; set IPHI_DEV_MUTATIONS=true on a local host.",
      },
});
export const statusMutable = status(true);
export const statusReadOnly = status(false);

export const clock: Clock = {
  environment: "simulation",
  mode: "realtime",
  speed: 1,
  platform_time: NOW,
  sample_interval_s: 5,
  seed: 42,
};

export const scenarios: ScenarioCatalog = {
  source: "simulation",
  sample_interval_s: 5,
  items: [
    {
      key: "baseline",
      kind: "baseline",
      title: "Baseline",
      description: "Nominal behaviour.",
      default_target_component_key: null,
      eligible_component_types: [],
      parameters: [],
      expected: { signal: "nominal", state: "Healthy", incident: "none" },
    },
    {
      key: "collector_down",
      kind: "fault",
      title: "Collector down",
      description: "The collector stops answering its probe.",
      default_target_component_key: "collector-01",
      eligible_component_types: ["collector"],
      parameters: [],
      expected: {
        signal: "up = 0",
        state: "Critical within 10 s (R-AVAIL-001)",
        incident: "one availability incident",
      },
    },
  ],
};

const levels = (warning: number | null, critical: number | null) => ({
  warning: warning === null ? null : { threshold: warning, clear: warning * 0.8 },
  critical: critical === null ? null : { threshold: critical, clear: critical * 0.8 },
});

export const latencyRule: HealthRule = {
  id: "R-LAT-001-id",
  key: "R-LAT-001",
  version: 1,
  rule_type: "threshold",
  failure_class: "latency",
  metric_name: "probe_latency_ms",
  unit: "ms",
  aggregation: "p95",
  operator: "gt",
  ...levels(250, 1000),
  window_seconds: 60,
  raise_after: 3,
  clear_after: 3,
  min_samples: 1,
  target_types: [],
  target_components: [],
  rationale: "Sustained slowness delays data delivery.",
  recommendation: "Check resource saturation.",
  enabled: true,
  created_at: "2026-11-12T08:00:00Z",
};

export const availabilityRule: HealthRule = {
  ...latencyRule,
  id: "R-AVAIL-001-id",
  key: "R-AVAIL-001",
  failure_class: "availability",
  metric_name: "up",
  unit: "bool",
  aggregation: "last",
  operator: "lt",
  ...levels(null, 1),
  window_seconds: 10,
  raise_after: 2,
  rationale: "The active probe got no answer.",
  recommendation: "Check that the service process is running.",
};

export const rules = { items: [availabilityRule, latencyRule] };

function collector(): Component {
  const found = components.find((c) => c.id === COLLECTOR_ID);
  if (found === undefined) throw new Error("collector fixture missing");
  return found;
}

export const collectorDetail: ComponentDetail = {
  ...collector(),
  upstream: [{ component: { id: id(2), key: "edge-gateway-01" }, kind: "data_flow" }],
  downstream: [{ component: { id: id(4), key: "historian-01" }, kind: "data_flow" }],
};

export const collectorRules: ComponentRules = {
  environment: "simulation",
  component: collectorRef,
  health: collectorDetail.health,
  rules: [
    {
      rule: availabilityRule,
      health: collectorDetail.health,
      debounce: null,
      evaluated_at: NOW,
      window_start: "2026-11-12T10:41:55Z",
      raw_state: "critical",
      observed_value: 0,
      sample_count: 2,
      explanation: "last(up, 10 s) = 0 < 1: probe not answered.",
      evidence: { sample_ids: [502], log_ids: [] },
      last_evaluation_id: 8890,
      state_evaluation_id: 8812,
    },
    {
      rule: latencyRule,
      health: {
        ...healthy,
        state: "unknown",
        evaluated_state: "unknown",
        since: "2026-11-12T10:40:42Z",
      },
      debounce: null,
      evaluated_at: NOW,
      window_start: "2026-11-12T10:41:05Z",
      raw_state: "unknown",
      observed_value: null,
      sample_count: 0,
      explanation: "0 usable probe_latency_ms samples in the last 60 s, 1 required.",
      evidence: { sample_ids: [], log_ids: [] },
      last_evaluation_id: 8891,
      state_evaluation_id: 8851,
    },
  ],
};

export const upSeries: MetricSeries = {
  environment: "simulation",
  component_id: COLLECTOR_ID,
  component_key: "collector-01",
  metric_name: "up",
  unit: "bool",
  mode: "raw",
  bucket_s: null,
  window_start: "2026-11-12T10:27:05Z",
  window_end: NOW,
  points: [
    {
      sample_id: 501,
      observed_at: "2026-11-12T10:39:42Z",
      value: 1,
      quality: "good",
      source: "simulation",
      scenario_run_id: null,
    },
    {
      sample_id: 502,
      observed_at: SINCE,
      value: 0,
      quality: "good",
      source: "simulation",
      scenario_run_id: null,
    },
  ],
  buckets: [],
  gaps: [{ start: "2026-11-12T10:30:00Z", end: "2026-11-12T10:31:00Z" }],
};

export const logs = {
  environment: "simulation" as const,
  next_cursor: null,
  items: [77, 76, 75].map((n) => ({
    id: n,
    component_id: COLLECTOR_ID,
    component_key: "collector-01",
    severity: "error" as const,
    message: "connection refused by upstream gateway",
    fingerprint: "a91c4e02aa",
    observed_at: "2026-11-12T10:39:46Z",
    received_at: "2026-11-12T10:39:47Z",
    source: "simulation" as const,
    scenario_run_id: null,
    attributes: {},
  })),
};

function edge(dependent: number, dependency: number, kind: "data_flow" | "runtime") {
  return { dependent_id: id(dependent), dependency_id: id(dependency), kind };
}

export const topology: Topology = {
  environment: "simulation",
  platform_id: PLATFORM_ID,
  health: platform.health,
  nodes: components.map((c) => ({
    id: c.id,
    key: c.key,
    name: c.name,
    type: c.type,
    criticality: c.criticality,
    health: c.health,
    impacted_by: c.impacted_by.map((r) => r.id),
  })),
  edges: [
    edge(2, 1, "data_flow"),
    edge(3, 2, "data_flow"),
    edge(4, 3, "data_flow"),
    edge(4, 5, "runtime"),
    edge(6, 4, "data_flow"),
    edge(7, 6, "data_flow"),
  ],
};
