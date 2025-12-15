# api/v1/announcements/delivery.py
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api import deps
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.announcement.announcement_delivery import (
    DeliveryConfig,
    DeliveryStatus,
    DeliveryReport,
    RetryDelivery,
    BatchDelivery,
)
from app.services.announcement import AnnouncementDeliveryService

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
    "/{announcement_id}/delivery/config",
    response_model=DeliveryConfig,
    summary="Get delivery configuration for an announcement",
)
async def get_delivery_config(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    delivery_service: Annotated[
        AnnouncementDeliveryService,
        Depends(deps.get_announcement_delivery_service),
    ] = ...,  # type: ignore[assignment]
) -> DeliveryConfig:
    """
    Return the delivery configuration (channels, batching, etc.) for an announcement.
    """
    try:
        return delivery_service.get_config(announcement_id=announcement_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.put(
    "/{announcement_id}/delivery/config",
    response_model=DeliveryConfig,
    summary="Update delivery configuration for an announcement",
)
async def update_delivery_config(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    payload: DeliveryConfig = ...,
    delivery_service: Annotated[
        AnnouncementDeliveryService,
        Depends(deps.get_announcement_delivery_service),
    ] = ...,  # type: ignore[assignment]
) -> DeliveryConfig:
    """
    Update the delivery configuration (channels, batching strategy, etc.) for an announcement.
    """
    try:
        return delivery_service.update_config(
            announcement_id=announcement_id,
            config=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{announcement_id}/delivery/status",
    response_model=DeliveryStatus,
    summary="Get delivery status for an announcement",
)
async def get_delivery_status(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    delivery_service: Annotated[
        AnnouncementDeliveryService,
        Depends(deps.get_announcement_delivery_service),
    ] = ...,  # type: ignore[assignment]
) -> DeliveryStatus:
    """
    Return high-level delivery status across channels (queued, in-progress, completed, failed).
    """
    try:
        return delivery_service.get_status(announcement_id=announcement_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{announcement_id}/delivery/report",
    response_model=DeliveryReport,
    summary="Get detailed delivery report for an announcement",
)
async def get_delivery_report(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    delivery_service: Annotated[
        AnnouncementDeliveryService,
        Depends(deps.get_announcement_delivery_service),
    ] = ...,  # type: ignore[assignment]
) -> DeliveryReport:
    """
    Return a delivery report with per-channel stats, failed deliveries, and other metadata.
    """
    try:
        return delivery_service.get_report(announcement_id=announcement_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{announcement_id}/delivery/retry",
    response_model=BatchDelivery,
    status_code=status.HTTP_200_OK,
    summary="Retry failed deliveries for an announcement",
)
async def retry_failed_deliveries(
    announcement_id: UUID = Path(..., description="Announcement ID"),
    payload: RetryDelivery = ...,
    delivery_service: Annotated[
        AnnouncementDeliveryService,
        Depends(deps.get_announcement_delivery_service),
    ] = ...,  # type: ignore[assignment]
) -> BatchDelivery:
    """
    Retry failed deliveries for an announcement, possibly limited to selected channels or
    recipient subsets.
    """
    try:
        return delivery_service.retry_failed(
            announcement_id=announcement_id,
            request=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)