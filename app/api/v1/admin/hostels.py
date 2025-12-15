from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.hostel.hostel_base import HostelCreate, HostelUpdate
from app.schemas.hostel.hostel_response import HostelResponse, HostelDetail
from app.schemas.hostel.hostel_filter import HostelFilterParams
from app.services.common.unit_of_work import UnitOfWork
from app.services.hostel import HostelService

router = APIRouter(prefix="/hostels")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/",
    response_model=List[HostelResponse],
    summary="List hostels (admin view)",
)
async def list_hostels(
    filters: HostelFilterParams = Depends(),
    uow: UnitOfWork = Depends(get_uow),
) -> List[HostelResponse]:
    """
    List hostels for admin users.

    Uses HostelService.list_hostels with HostelFilterParams.
    """
    service = HostelService(uow)
    try:
        return service.list_hostels(filters=filters)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/",
    response_model=HostelDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new hostel",
)
async def create_hostel(
    payload: HostelCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> HostelDetail:
    """
    Create a new hostel.

    Ensures slug uniqueness and applies default flags.
    """
    service = HostelService(uow)
    try:
        return service.create_hostel(data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{hostel_id}",
    response_model=HostelDetail,
    summary="Get hostel details (admin)",
)
async def get_hostel(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> HostelDetail:
    """
    Retrieve detailed hostel information for admin users.
    """
    service = HostelService(uow)
    try:
        return service.get_hostel(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{hostel_id}",
    response_model=HostelDetail,
    summary="Update a hostel (admin)",
)
async def update_hostel(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    payload: HostelUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> HostelDetail:
    """
    Partially update hostel fields.

    Delegates to HostelService.update_hostel.
    """
    service = HostelService(uow)
    try:
        return service.update_hostel(hostel_id=hostel_id, data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)