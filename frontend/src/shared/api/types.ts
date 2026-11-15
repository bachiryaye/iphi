import type { components } from "./schema";

type Schemas = components["schemas"];

export type HealthState = Schemas["HealthState"];
export type Health = Schemas["HealthOut"];
export type PlatformHealth = Schemas["PlatformHealthOut"];
export type Platform = Schemas["PlatformOut"];
export type Component = Schemas["ComponentOut"];
export type ComponentDetail = Schemas["ComponentDetailOut"];
export type ComponentRef = Schemas["ComponentRefOut"];
export type ComponentType = Schemas["ComponentType"];
export type Criticality = Schemas["Criticality"];
export type KeyMetric = Schemas["KeyMetricOut"];
export type Evaluation = Schemas["EvaluationOut"];
export type RuleStatus = Schemas["RuleStatusOut"];
export type ComponentRules = Schemas["ComponentRulesOut"];
export type HealthRule = Schemas["HealthRuleOut"];
export type Topology = Schemas["TopologyOut"];
export type TopologyNode = Schemas["TopologyNodeOut"];
export type TopologyEdge = Schemas["TopologyEdgeOut"];

export type Incident = Schemas["IncidentOut"];
export type IncidentDetail = Schemas["IncidentDetailOut"];
export type IncidentPage = Schemas["IncidentPageOut"];
export type IncidentStatus = Schemas["IncidentStatus"];
export type IncidentSeverity = Schemas["IncidentSeverity"];
export type IncidentEvent = Schemas["EventOut"];
export type IncidentEvidence = Schemas["app__api__incidents__EvidenceOut"];
export type FailureClass = Schemas["FailureClass"];
export type Diagnostic = Schemas["DiagnosticOut"];
export type Claim = Schemas["ClaimOut"];
export type Citation = Schemas["CitationOut"];

export type MetricSeries = Schemas["MetricSeriesOut"];
export type LogEntry = Schemas["LogOut"];
export type LogSeverity = Schemas["LogSeverity"];

export type SystemStatus = Schemas["SystemStatusOut"];
export type Scenario = Schemas["ScenarioOut"];
export type ScenarioCatalog = Schemas["ScenarioCatalogOut"];
export type ScenarioRun = Schemas["ScenarioRunOut"];
export type ScenarioKey = Schemas["ScenarioKey"];
export type ClockMode = Schemas["ClockMode"];
export type Clock = Schemas["ClockOut"];
