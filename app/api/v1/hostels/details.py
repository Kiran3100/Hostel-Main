# api/v1/hostels/details.py
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.hostel.hostel_admin import (
    HostelAdminView,
    HostelSettings,
    HostelVisibilityUpdate,
    HostelCapacityUpdate,
    HostelStatusUpdate,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.hostel import HostelAdminViewService

router = APIRouter(prefix="/details")


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
    "/{hostel_id}/admin-view",
    response_model=HostelAdminView,
    summary="Get admin view for a hostel",
)
async def get_hostel_admin_view(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> HostelAdminView:
    """
    Build an admin dashboard-style view for a hostel, aggregating capacity,
    students, finances, bookings, complaints, maintenance, subscription, and reviews.
    """
    service = HostelAdminViewService(uow)
    try:
        return service.get_admin_view(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{hostel_id}/settings",
    response_model=HostelSettings,
    summary="Get hostel admin settings",
)
async def get_hostel_settings(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> HostelSettings:
    """
    Get hostel-level admin settings (booking, payments, attendance, notifications, mess, etc.).
    """
    service = HostelAdminViewService(uow)
    try:
        return service.get_settings(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.put(
    "/{hostel_id}/settings",
    response_model=HostelSettings,
    summary="Update hostel admin settings",
)
async def update_hostel_settings(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    payload: HostelSettings = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> HostelSettings:
    """
    Update hostel admin settings.
    """
    service = HostelAdminViewService(uow)
    try:
        return service.update_settings(
            hostel_id=hostel_id,
            settings=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{hostel_id}/visibility",
    response_model=HostelSettings,
    summary="Update hostel visibility flags",
)
async def update_hostel_visibility(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    payload: HostelVisibilityUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> HostelSettings:
    """
    Update hostel visibility-related flags (is_public, is_featured, etc.).
    """
    service = HostelAdminViewService(uow)
    try:
        return service.update_visibility(
            hostel_id=hostel_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{hostel_id}/capacity",
    response_model=HostelSettings,
    summary="Update hostel capacity configuration",
)
async def update_hostel_capacity(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    payload: HostelCapacityUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> HostelSettings:
    """
    Update hostel capacity-related configuration.
    """
    service = HostelAdminViewService(uow)
    try:
        return service.update_capacity(
            hostel_id=hostel_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{hostel_id}/status",
    response_model=HostelSettings,
    summary="Update hostel operational status",
)
async def update_hostel_status(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    payload: HostelStatusUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> HostelSettings:
    """
    Update hostel operational status (active/inactive, status enum).
    """
    service = HostelAdminViewService(uow)
    try:
        return service.update_status(
            hostel_id=hostel_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)