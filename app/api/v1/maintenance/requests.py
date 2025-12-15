from datetime import date
from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.maintenance.maintenance_base import (
    MaintenanceCreate,
    MaintenanceUpdate,
    MaintenanceStatusUpdate,
)
from app.schemas.maintenance.maintenance_response import (
    MaintenanceDetail,
    RequestListItem,
    MaintenanceSummary,
)
from app.schemas.maintenance.maintenance_filters import (
    MaintenanceFilterParams,
    SearchRequest as MaintenanceSearchRequest,
)
from app.schemas.maintenance.maintenance_request import (
    MaintenanceRequest,
    RequestSubmission,
    EmergencyRequest,
)
from app.schemas.common.pagination import PaginatedResponse
from app.services.common.unit_of_work import UnitOfWork
from app.services.maintenance import MaintenanceService

router = APIRouter(prefix="/requests")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "",
    response_model=PaginatedResponse[RequestListItem],
    summary="List maintenance requests",
)
async def list_maintenance_requests(
    filters: MaintenanceFilterParams = Depends(),
    uow: UnitOfWork = Depends(get_uow),
) -> PaginatedResponse[RequestListItem]:
    """
    List maintenance requests using filters (hostel, status, category, priority,
    Date range, etc.) with pagination and sorting.
    """
    service = MaintenanceService(uow)
    try:
        return service.list_requests(filters=filters)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/",
    response_model=MaintenanceDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a maintenance request (low-level)",
)
async def create_maintenance_request(
    payload: MaintenanceCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> MaintenanceDetail:
    """
    Create a maintenance request with full low-level fields.

    For higher-level flows, prefer `/requests/submit` or `/requests/emergency`.
    """
    service = MaintenanceService(uow)
    try:
        return service.create_request(data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/submit",
    response_model=MaintenanceDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a maintenance request",
)
async def submit_maintenance_request(
    payload: RequestSubmission,
    uow: UnitOfWork = Depends(get_uow),
) -> MaintenanceDetail:
    """
    Higher-level submission of a maintenance request by supervisors/staff.

    Includes estimated cost, vendor, and days if known.
    """
    service = MaintenanceService(uow)
    try:
        return service.submit_request(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/emergency",
    response_model=MaintenanceDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an emergency maintenance request",
)
async def submit_emergency_request(
    payload: EmergencyRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> MaintenanceDetail:
    """
    Create an emergency maintenance request with incident details.
    """
    service = MaintenanceService(uow)
    try:
        return service.submit_emergency(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{request_id}",
    response_model=MaintenanceDetail,
    summary="Get maintenance request details",
)
async def get_maintenance_request(
    request_id: UUID = Path(..., description="Maintenance request ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> MaintenanceDetail:
    """
    Retrieve detailed information about a specific maintenance request.
    """
    service = MaintenanceService(uow)
    try:
        return service.get_request(request_id=request_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{request_id}",
    response_model=MaintenanceDetail,
    summary="Update a maintenance request",
)
async def update_maintenance_request(
    request_id: UUID = Path(..., description="Maintenance request ID"),
    payload: MaintenanceUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> MaintenanceDetail:
    """
    Partially update fields of a maintenance request (title, description,
    category, priority, location, costs, etc.).
    """
    service = MaintenanceService(uow)
    try:
        return service.update_request(
            request_id=request_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{request_id}/status",
    response_model=MaintenanceDetail,
    summary="Update maintenance request status",
)
async def update_maintenance_status(
    request_id: UUID = Path(..., description="Maintenance request ID"),
    payload: MaintenanceStatusUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> MaintenanceDetail:
    """
    Update only the status of a maintenance request
    (open, in_progress, pending_approval, completed, etc.).
    """
    service = MaintenanceService(uow)
    try:
        return service.update_status(
            request_id=request_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/search",
    response_model=PaginatedResponse[RequestListItem],
    summary="Search maintenance requests",
)
async def search_maintenance_requests(
    payload: MaintenanceSearchRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> PaginatedResponse[RequestListItem]:
    """
    Perform a richer search over maintenance requests (free-text, combined filters, etc.).
    """
    service = MaintenanceService(uow)
    try:
        return service.search_requests(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/summary",
    response_model=MaintenanceSummary,
    summary="Get maintenance summary for a hostel",
)
async def get_hostel_maintenance_summary(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> MaintenanceSummary:
    """
    Summarize maintenance requests for a hostel (counts by status/priority,
    average completion time, etc.).
    """
    service = MaintenanceService(uow)
    try:
        return service.get_hostel_summary(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)