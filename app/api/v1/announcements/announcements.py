# api/v1/announcements/announcements.py
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.announcement.announcement_base import AnnouncementCreate, AnnouncementUpdate
from app.schemas.announcement.announcement_response import (
    AnnouncementDetail,
    AnnouncementList,
)
from app.schemas.announcement.announcement_filters import (
    AnnouncementFilterParams,
    ArchiveRequest,
)
from app.schemas.common.response import BulkOperationResponse
from app.services.common.unit_of_work import UnitOfWork
from app.services.announcement import AnnouncementService

router = APIRouter(prefix="/announcements")


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
    response_model=AnnouncementList,
    summary="List announcements",
)
async def list_announcements(
    filters: AnnouncementFilterParams = Depends(),
    uow: UnitOfWork = Depends(get_uow),
) -> AnnouncementList:
    """
    List announcements using filter/search parameters.

    Typical filters include hostel, category, priority, publish state, and date range.
    """
    service = AnnouncementService(uow)
    try:
        return service.list_announcements(filters=filters)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/",
    response_model=AnnouncementDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new announcement",
)
async def create_announcement(
    payload: AnnouncementCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> AnnouncementDetail:
    """
    Create a new announcement.

    Handles targeting, scheduling fields, and initial publish flags as part
    of the create payload.
    """
    service = AnnouncementService(uow)
    try:
        return service.create_announcement(data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{announcement_id}",
    response_model=AnnouncementDetail,
    summary="Get announcement details",
)
async def get_announcement(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> AnnouncementDetail:
    """
    Retrieve full details for a single announcement.
    """
    service = AnnouncementService(uow)
    try:
        return service.get_announcement(announcement_id=announcement_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{announcement_id}",
    response_model=AnnouncementDetail,
    summary="Update an announcement",
)
async def update_announcement(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    payload: AnnouncementUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> AnnouncementDetail:
    """
    Partially update announcement fields (content, category, priority, targeting,
    scheduling, publish flags, etc.).
    """
    service = AnnouncementService(uow)
    try:
        return service.update_announcement(
            announcement_id=announcement_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/archive",
    response_model=BulkOperationResponse,
    summary="Archive announcements in bulk",
)
async def archive_announcements(
    payload: ArchiveRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> BulkOperationResponse:
    """
    Archive announcements based on the supplied criteria.

    Typically used to bulk-archive old or expired announcements.
    """
    service = AnnouncementService(uow)
    try:
        return service.archive_announcements(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)