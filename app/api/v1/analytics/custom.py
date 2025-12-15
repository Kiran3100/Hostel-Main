# api/v1/analytics/custom.py

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.analytics.custom_reports import (
    CustomReportRequest,
    CustomReportResult,
    CustomReportDefinition,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.analytics import CustomReportService

router = APIRouter(prefix="/custom")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/run",
    response_model=CustomReportResult,
    summary="Run a custom analytics report",
)
async def run_custom_report(
    payload: CustomReportRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> CustomReportResult:
    """
    Execute a schema-driven custom report over payments, bookings, complaints, attendance, etc.
    """
    service = CustomReportService(uow)
    try:
        return service.run_report(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/definitions",
    response_model=CustomReportDefinition,
    status_code=status.HTTP_201_CREATED,
    summary="Create a saved custom report definition",
)
async def create_report_definition(
    payload: CustomReportDefinition,
    uow: UnitOfWork = Depends(get_uow),
) -> CustomReportDefinition:
    """
    Create and store a custom report definition for later reuse.
    """
    service = CustomReportService(uow)
    try:
        return service.create_definition(definition=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/definitions",
    response_model=List[CustomReportDefinition],
    summary="List saved custom report definitions",
)
async def list_report_definitions(
    uow: UnitOfWork = Depends(get_uow),
) -> List[CustomReportDefinition]:
    """
    List all saved custom report definitions (optionally, you may extend with filters).
    """
    service = CustomReportService(uow)
    try:
        return service.list_definitions()
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/definitions/{report_id}",
    response_model=CustomReportDefinition,
    summary="Get a specific report definition",
)
async def get_report_definition(
    report_id: UUID = Path(..., description="Report definition ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> CustomReportDefinition:
    """
    Retrieve a specific custom report definition.
    """
    service = CustomReportService(uow)
    try:
        return service.get_definition(report_id=report_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.delete(
    "/definitions/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a report definition",
)
async def delete_report_definition(
    report_id: UUID = Path(..., description="Report definition ID"),
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Delete a saved custom report definition.
    """
    service = CustomReportService(uow)
    try:
        service.delete_definition(report_id=report_id)
    except ServiceError as exc:
        raise _map_service_error(exc)