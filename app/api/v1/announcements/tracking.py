# api/v1/announcements/tracking.py
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api import deps
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.announcement.announcement_tracking import (
    ReadReceipt,
    AcknowledgmentRequest,
    AcknowledgmentTracking,
    PendingAcknowledgment,
    EngagementMetrics,
    AnnouncementAnalytics,
)
from app.services.announcement import AnnouncementTrackingService

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
    "/{announcement_id}/read",
    response_model=ReadReceipt,
    status_code=status.HTTP_200_OK,
    summary="Record a read receipt for an announcement",
)
async def record_read_receipt(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    payload: ReadReceipt = ...,
    tracking_service: Annotated[
        AnnouncementTrackingService,
        Depends(deps.get_announcement_tracking_service),
    ] = ...,  # type: ignore[assignment]
) -> ReadReceipt:
    """
    Record that a recipient has read the announcement (for engagement tracking).
    """
    try:
        return tracking_service.record_read_receipt(
            announcement_id=announcement_id,
            receipt=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{announcement_id}/acknowledge",
    response_model=AcknowledgmentTracking,
    status_code=status.HTTP_200_OK,
    summary="Record an acknowledgment for an announcement",
)
async def acknowledge_announcement(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    payload: AcknowledgmentRequest = ...,
    tracking_service: Annotated[
        AnnouncementTrackingService,
        Depends(deps.get_announcement_tracking_service),
    ] = ...,  # type: ignore[assignment]
) -> AcknowledgmentTracking:
    """
    Record a formal acknowledgment from a recipient for an announcement.
    """
    try:
        return tracking_service.record_acknowledgment(
            announcement_id=announcement_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{announcement_id}/acknowledgments/pending",
    response_model=PendingAcknowledgment,
    summary="Get pending acknowledgments for an announcement",
)
async def get_pending_acknowledgments(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    tracking_service: Annotated[
        AnnouncementTrackingService,
        Depends(deps.get_announcement_tracking_service),
    ] = ...,  # type: ignore[assignment]
) -> PendingAcknowledgment:
    """
    Return information about recipients who have not yet acknowledged the announcement.
    """
    try:
        return tracking_service.get_pending_acknowledgments(
            announcement_id=announcement_id,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{announcement_id}/engagement",
    response_model=EngagementMetrics,
    summary="Get engagement metrics for an announcement",
)
async def get_engagement_metrics(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    tracking_service: Annotated[
        AnnouncementTrackingService,
        Depends(deps.get_announcement_tracking_service),
    ] = ...,  # type: ignore[assignment]
) -> EngagementMetrics:
    """
    Return engagement metrics such as open/read rates, acknowledgment rates,
    and basic reading-time statistics.
    """
    try:
        return tracking_service.get_engagement_metrics(
            announcement_id=announcement_id,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{announcement_id}/analytics",
    response_model=AnnouncementAnalytics,
    summary="Get full analytics for an announcement",
)
async def get_announcement_analytics(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    tracking_service: Annotated[
        AnnouncementTrackingService,
        Depends(deps.get_announcement_tracking_service),
    ] = ...,  # type: ignore[assignment]
) -> AnnouncementAnalytics:
    """
    Return comprehensive analytics for an announcement, combining delivery and
    engagement data.
    """
    try:
        return tracking_service.get_announcement_analytics(
            announcement_id=announcement_id,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)