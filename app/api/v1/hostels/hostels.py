from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.hostel.hostel_filter import HostelFilterParams
from app.schemas.hostel.hostel_response import HostelResponse, HostelDetail, HostelStats
from app.services.common.unit_of_work import UnitOfWork
from app.services.hostel import HostelService

router = APIRouter()


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
    "/",
    response_model=List[HostelResponse],
    summary="List hostels (read-only, internal)",
)
async def list_hostels(
    filters: HostelFilterParams = Depends(),
    uow: UnitOfWork = Depends(get_uow),
) -> List[HostelResponse]:
    """
    List hostels for internal consumers (students, supervisors, etc.).

    This is a read-only view; admin creation/updating lives under /admin/hostels.
    """
    service = HostelService(uow)
    try:
        return service.list_hostels(filters=filters)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{hostel_id}",
    response_model=HostelDetail,
    summary="Get hostel details (internal)",
)
async def get_hostel(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> HostelDetail:
    """
    Retrieve detailed hostel information for internal use.
    """
    service = HostelService(uow)
    try:
        return service.get_hostel(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{hostel_id}/stats",
    response_model=HostelStats,
    summary="Get hostel statistics (occupancy, revenue, etc.)",
)
async def get_hostel_stats(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> HostelStats:
    """
    Summarized hostel stats: occupancy, revenue, bookings, complaints, reviews.
    """
    service = HostelService(uow)
    try:
        return service.get_hostel_stats(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)