from http import HTTPStatus

from app.core.exceptions import IphiError


class SimulationNotInitializedError(IphiError):
    status = HTTPStatus.SERVICE_UNAVAILABLE
    code = "SIMULATION_NOT_INITIALIZED"


class ClockNotManualError(IphiError):
    status = HTTPStatus.CONFLICT
    code = "CLOCK_NOT_MANUAL"


class ClockSpeedError(IphiError):
    status = HTTPStatus.UNPROCESSABLE_CONTENT
    code = "CLOCK_SPEED_INVALID"


class ScenarioNotStartableError(IphiError):
    status = HTTPStatus.CONFLICT
    code = "SCENARIO_NOT_STARTABLE"


class ScenarioTargetError(IphiError):
    status = HTTPStatus.UNPROCESSABLE_CONTENT
    code = "SCENARIO_TARGET_INVALID"


class ScenarioParameterError(IphiError):
    status = HTTPStatus.UNPROCESSABLE_CONTENT
    code = "SCENARIO_PARAMETER_INVALID"


class ScenarioTargetBusyError(IphiError):
    status = HTTPStatus.CONFLICT
    code = "SCENARIO_TARGET_BUSY"


class ScenarioRunNotFoundError(IphiError):
    status = HTTPStatus.NOT_FOUND
    code = "SCENARIO_RUN_NOT_FOUND"


class ScenarioRunNotActiveError(IphiError):
    status = HTTPStatus.CONFLICT
    code = "SCENARIO_RUN_NOT_ACTIVE"


class BaselineRunPermanentError(IphiError):
    status = HTTPStatus.CONFLICT
    code = "BASELINE_RUN_PERMANENT"
