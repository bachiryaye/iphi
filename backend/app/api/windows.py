"""Time-window query parameters shared by history endpoints (architecture §04.2)."""

from datetime import datetime, timedelta

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.ingestion.domain.series import TimeWindow

DEFAULT_WINDOW = timedelta(hours=1)


class WindowParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: AwareDatetime | None = Field(
        default=None, alias="from", description="Inclusive start; defaults to one hour before `to`."
    )
    end: AwareDatetime | None = Field(
        default=None, alias="to", description="Exclusive end; defaults to platform time."
    )


def window_of(params: WindowParams, now: datetime) -> TimeWindow:
    end = params.end or now
    return TimeWindow(params.start or end - DEFAULT_WINDOW, end)
