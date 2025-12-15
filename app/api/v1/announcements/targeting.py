# api/v1/announcements/targeting.py
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.announcement.announcement_targeting import (
    TargetingConfig,
    TargetingSummary,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.announcement import AnnouncementService

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
    "/{announcement_id}/targeting",
    response_model=TargetingConfig,
    summary="Get audience targeting configuration for an announcement",
)
async def get_targeting_config(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> TargetingConfig:
    """
    Fetch the current audience targeting configuration for a given announcement.
    """
    service = AnnouncementService(uow)
    try:
        return service.get_targeting_config(announcement_id=announcement_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.put(
    "/{announcement_id}/targeting",
    response_model=TargetingConfig,
    summary="Update audience targeting for an announcement",
)
async def update_targeting_config(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    payload: TargetingConfig = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> TargetingConfig:
    """
    Replace the audience targeting configuration for an announcement.

    The service is expected to recompute derived counts as needed.
    """
    service = AnnouncementService(uow)
    try:
        return service.update_targeting_config(
            announcement_id=announcement_id,
            config=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{announcement_id}/targeting/summary",
    response_model=TargetingSummary,
    summary="Get targeting summary for an announcement",
)
async def get_targeting_summary(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> TargetingSummary:
    """
    Return a summary of the targeted audience: total recipients and breakdown
    by audience segments (rooms, floors, students, etc.).
    """
    service = AnnouncementService(uow)
    try:
        return service.get_targeting_summary(announcement_id=announcement_id)
    except ServiceError as exc:
        raise _map_service_error(exc)