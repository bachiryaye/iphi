import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.api.mutations import mutation
from app.api.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_CURSOR_CHARS,
    MAX_PAGE_SIZE,
    cursor_integer,
    decode_cursor,
    encode_cursor,
)
from app.core.observation import SAMPLE_INTERVAL_S
from app.core.settings import MAX_SEED
from app.identity.domain import AuditAction, AuditContext
from app.simulation.domain.catalog import ScenarioDefinition, ScenarioKey, ScenarioKind
from app.simulation.domain.clock import MAX_ACCELERATION, ClockMode
from app.simulation.domain.runs import MAX_DURATION_S, MIN_DURATION_S, RunStatus, ScenarioRun
from app.simulation.service import ClockView, SimulationService, StartCommand
from app.topology.domain import COMPONENT_KEY, ComponentType

router = APIRouter(prefix="/api/v1/simulations", tags=["simulations"])

MAX_ADVANCE_S = 24 * 3600

ComponentKey = Annotated[
    str, StringConstraints(pattern=f"^{COMPONENT_KEY.pattern}$", max_length=64)
]
ParameterName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,31}$")]
Simulation = Literal["simulation"]


class ParameterOut(BaseModel):
    name: str
    unit: str
    default: float
    minimum: float
    maximum: float
    description: str


class ExpectedOutcomeOut(BaseModel):
    signal: str
    state: str
    incident: str


class ScenarioOut(BaseModel):
    key: ScenarioKey
    title: str
    description: str
    kind: ScenarioKind
    default_target_component_key: str | None
    eligible_component_types: list[ComponentType]
    parameters: list[ParameterOut]
    expected: ExpectedOutcomeOut = Field(
        description="Outcome the default health rules should reach."
    )

    @classmethod
    def of(cls, d: ScenarioDefinition) -> ScenarioOut:
        return cls(
            key=d.key,
            title=d.title,
            description=d.description,
            kind=d.kind,
            default_target_component_key=d.default_target,
            eligible_component_types=sorted(d.eligible_types),
            parameters=[
                ParameterOut(
                    name=p.name,
                    unit=p.unit,
                    default=p.default,
                    minimum=p.minimum,
                    maximum=p.maximum,
                    description=p.description,
                )
                for p in d.parameters
            ],
            expected=ExpectedOutcomeOut(
                signal=d.expected.signal, state=d.expected.state, incident=d.expected.incident
            ),
        )


class ScenarioCatalogOut(BaseModel):
    source: Simulation = "simulation"
    sample_interval_s: int = Field(description="Platform-time period of simulated samples.")
    items: list[ScenarioOut]


class StartScenarioIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_key: ScenarioKey
    target_component_key: ComponentKey | None = Field(
        default=None, description="Defaults to the scenario's default target."
    )
    duration_s: int | None = Field(
        default=None,
        ge=MIN_DURATION_S,
        le=MAX_DURATION_S,
        description="Planned duration in platform seconds; runs until stopped when omitted.",
    )
    parameters: dict[ParameterName, float] = Field(default_factory=dict, max_length=8)


class ScenarioRunOut(BaseModel):
    id: uuid.UUID
    number: int = Field(description="Human-readable sequence number, shown as #N.")
    scenario_key: ScenarioKey
    target_component_key: str | None
    seed: int
    parameters: dict[str, float]
    started_at: datetime
    ends_at: datetime | None
    stopped_at: datetime | None
    status: RunStatus
    started_by: str
    source: Simulation = "simulation"

    @classmethod
    def of(cls, run: ScenarioRun) -> ScenarioRunOut:
        return cls(
            id=run.id,
            number=run.number,
            scenario_key=run.scenario,
            target_component_key=run.target_key,
            seed=run.seed,
            parameters=dict(run.parameters),
            started_at=run.started_at,
            ends_at=run.ends_at,
            stopped_at=run.stopped_at,
            status=run.status,
            started_by=run.started_by,
        )


class ScenarioRunPageOut(BaseModel):
    items: list[ScenarioRunOut]
    next_cursor: str | None


class ClockOut(BaseModel):
    environment: Simulation = "simulation"
    mode: ClockMode
    speed: float
    platform_time: datetime
    seed: int
    sample_interval_s: int

    @classmethod
    def of(cls, view: ClockView) -> ClockOut:
        return cls(
            mode=view.state.mode,
            speed=view.state.speed,
            platform_time=view.platform_time,
            seed=view.state.seed,
            sample_interval_s=SAMPLE_INTERVAL_S,
        )


class SetClockModeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["set_mode"]
    mode: ClockMode
    speed: float | None = Field(
        default=None, gt=1, le=MAX_ACCELERATION, description="Required in accelerated mode only."
    )

    @model_validator(mode="after")
    def speed_matches_mode(self) -> SetClockModeIn:
        if (self.mode is ClockMode.ACCELERATED) != (self.speed is not None):
            raise ValueError("speed is required for accelerated mode and forbidden otherwise")
        return self


class AdvanceClockIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["advance"]
    seconds: int = Field(ge=1, le=MAX_ADVANCE_S)


ClockCommandIn = Annotated[SetClockModeIn | AdvanceClockIn, Field(discriminator="action")]


class ResetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int | None = Field(
        default=None, ge=0, le=MAX_SEED, description="Defaults to IPHI_SIM_SEED."
    )


class ResetOut(BaseModel):
    clock: ClockOut
    baseline_run: ScenarioRunOut
    stopped_runs: int


def encode_run_cursor(number: int) -> str:
    return encode_cursor("run", str(number))


def decode_run_cursor(cursor: str) -> int:
    (value,) = decode_cursor("run", cursor, 1)
    return cursor_integer(value, minimum=1)


def simulation_service(request: Request) -> SimulationService:
    service: SimulationService = request.app.state.simulation
    return service


Service = Annotated[SimulationService, Depends(simulation_service)]


@router.get("/scenarios", summary="Scenario catalog with parameters and expected outcomes.")
def list_scenarios(service: Service) -> ScenarioCatalogOut:
    return ScenarioCatalogOut(
        sample_interval_s=SAMPLE_INTERVAL_S, items=[ScenarioOut.of(d) for d in service.catalog()]
    )


@router.post(
    "/scenarios",
    status_code=status.HTTP_201_CREATED,
    summary="Start a scenario run on a component.",
)
def start_scenario(
    body: StartScenarioIn,
    service: Service,
    context: Annotated[AuditContext, Depends(mutation(AuditAction.SCENARIO_START))],
) -> ScenarioRunOut:
    command = StartCommand(
        body.scenario_key, body.target_component_key, body.parameters, body.duration_s
    )
    return ScenarioRunOut.of(service.start(command, context))


@router.get("/runs", summary="Scenario runs, newest first.")
def list_runs(
    service: Service,
    status_filter: Annotated[RunStatus | None, Query(alias="status")] = None,
    cursor: Annotated[str | None, Query(max_length=MAX_CURSOR_CHARS)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> ScenarioRunPageOut:
    before = None if cursor is None else decode_run_cursor(cursor)
    page = service.list_runs(status_filter, before, limit)
    return ScenarioRunPageOut(
        items=[ScenarioRunOut.of(r) for r in page.items],
        next_cursor=None if page.next_before is None else encode_run_cursor(page.next_before),
    )


@router.post("/runs/{run_id}/stop", summary="Stop an active scenario run.")
def stop_run(
    run_id: uuid.UUID,
    service: Service,
    context: Annotated[AuditContext, Depends(mutation(AuditAction.SCENARIO_STOP))],
) -> ScenarioRunOut:
    return ScenarioRunOut.of(service.stop(run_id, context))


@router.post(
    "/reset",
    summary="Stop every run, restart the clock in realtime and start a fresh baseline.",
)
def reset_simulation(
    request: Request,
    service: Service,
    context: Annotated[AuditContext, Depends(mutation(AuditAction.SIMULATION_RESET))],
    body: ResetIn | None = None,
) -> ResetOut:
    seed = body.seed if body is not None and body.seed is not None else request.app.state.sim_seed
    outcome = service.reset(seed, context)
    return ResetOut(
        clock=ClockOut.of(outcome.clock),
        baseline_run=ScenarioRunOut.of(outcome.baseline),
        stopped_runs=outcome.stopped_runs,
    )


@router.get("/clock", summary="Platform clock state.")
def get_clock(service: Service) -> ClockOut:
    return ClockOut.of(service.clock())


@router.post("/clock", summary="Change the clock mode, or advance it in manual mode.")
def command_clock(
    body: ClockCommandIn,
    service: Service,
    context: Annotated[AuditContext, Depends(mutation(AuditAction.CLOCK_UPDATE))],
) -> ClockOut:
    if isinstance(body, AdvanceClockIn):
        return ClockOut.of(service.advance_clock(body.seconds, context))
    return ClockOut.of(service.set_clock_mode(body.mode, body.speed or 1.0, context))
