import logging
import sys
import uuid
from datetime import date
from typing import Literal

import structlog
from structlog.typing import Processor


def wire_values(
    _logger: object, _method: str, event: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    """Dates as ISO 8601 (S-06) and UUIDs as text, for the JSON and console renderers alike."""
    for name, value in event.items():
        if isinstance(value, date):
            event[name] = value.isoformat()
        elif isinstance(value, uuid.UUID):
            event[name] = str(value)
    return event


def configure_logging(level: str, fmt: Literal["json", "console"]) -> None:
    """Route structlog and stdlib (uvicorn, alembic) records to stdout in one format."""
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        wire_values,
    ]
    renderer: Processor = (
        structlog.processors.JSONRenderer(default=str)
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.format_exc_info,
                renderer,
            ],
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # Request logging is emitted by CorrelationIdMiddleware with the correlation ID attached.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True
