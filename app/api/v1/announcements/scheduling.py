# api/v1/announcements/scheduling.py

from datetime import date
from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.announcement.announcement_scheduling import (
    ScheduleRequest,
    ScheduleUpdate,
    ScheduleCancel,
    PublishNow,
    ScheduleConfig,
    ScheduledAnnouncementsList,
)
from app.schemas.announcement.announcement_response import AnnouncementDetail
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


@router.post(
    "/{announcement_id}/schedule",
    response_model=ScheduleConfig,
    status_code=status.HTTP_200_OK,
    summary="Schedule an announcement",
)
async def schedule_announcement(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    payload: ScheduleRequest = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ScheduleConfig:
    """
    Schedule a single announcement with optional expiry and recurrence.
    """
    service = AnnouncementService(uow)
    try:
        return service.schedule_announcement(
            announcement_id=announcement_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{announcement_id}/schedule",
    response_model=ScheduleConfig,
    summary="Update announcement schedule",
)
async def update_announcement_schedule(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    payload: ScheduleUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ScheduleConfig:
    """
    Update scheduling details (publish time, expiry, recurrence) for an announcement.
    """
    service = AnnouncementService(uow)
    try:
        return service.update_schedule(
            announcement_id=announcement_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{announcement_id}/schedule/cancel",
    response_model=ScheduleConfig,
    summary="Cancel announcement schedule",
)
async def cancel_announcement_schedule(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    payload: ScheduleCancel = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> ScheduleConfig:
    """
    Cancel the active schedule for an announcement (the announcement itself is
    not deleted).
    """
    service = AnnouncementService(uow)
    try:
        return service.cancel_schedule(
            announcement_id=announcement_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{announcement_id}/publish-now",
    response_model=AnnouncementDetail,
    summary="Publish an announcement immediately",
)
async def publish_now(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    payload: PublishNow = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> AnnouncementDetail:
    """
    Publish an announcement immediately, bypassing any future scheduled publish time.
    """
    service = AnnouncementService(uow)
    try:
        return service.publish_now(
            announcement_id=announcement_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/scheduled",
    response_model=ScheduledAnnouncementsList,
    summary="List scheduled announcements",
)
async def list_scheduled_announcements(
    hostel_id: Union[UUID, None] = Query(
        None,
        description="Optional hostel filter",
    ),
    start_date: Union[date, None] = Query(
        None,
        description="Optional start of date window (inclusive)",
    ),
    end_date: Union[date, None] = Query(
        None,
        description="Optional end of date window (inclusive)",
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> ScheduledAnnouncementsList:
    """
    List upcoming scheduled announcements, optionally filtered by hostel and date range.
    """
    service = AnnouncementService(uow)
    try:
        return service.list_scheduled_announcements(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)