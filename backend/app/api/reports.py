import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from app.reporting.domain import ReportFormat
from app.reporting.service import ReportingService

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def reporting_service(request: Request) -> ReportingService:
    service: ReportingService = request.app.state.reporting
    return service


@router.get(
    "/incidents/{incident_id}",
    summary="Download a simulated incident report from stored evidence.",
    response_class=Response,
    responses={
        200: {
            "content": {
                "application/pdf": {"schema": {"type": "string", "format": "binary"}},
                "text/csv": {"schema": {"type": "string", "format": "binary"}},
            },
        },
        413: {"description": "REPORT_TOO_LARGE: use the paginated incident evidence/events API."},
        503: {"description": "REPORT_BUSY or REPORT_UNAVAILABLE; retry or export CSV."},
    },
)
def incident_report(
    incident_id: uuid.UUID,
    service: Annotated[ReportingService, Depends(reporting_service)],
    format: Annotated[ReportFormat, Query()] = ReportFormat.PDF,
) -> Response:
    result = service.export(incident_id, format)
    return Response(
        result.content,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "Cache-Control": "no-store",
            "X-IPHI-Environment": "simulation",
        },
    )
