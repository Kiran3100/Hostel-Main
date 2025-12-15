# api/v1/attendance/alerts.py

from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.attendance.attendance_alert import (
    AlertConfig,
    AlertTrigger,
    AttendanceAlert,
    AlertAcknowledgment,
    AlertList,
    AlertSummary,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.attendance import AttendanceAlertService

router = APIRouter(prefix="/alerts")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


@router.get(
    "/config/{hostel_id}",
    response_model=AlertConfig,
    summary="Get attendance alert configuration for a hostel",
)
async def get_alert_config(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> AlertConfig:
    """
    Fetch the alert configuration (thresholds, channels, patterns) for a hostel.
    """
    service = AttendanceAlertService(uow)
    try:
        return service.get_alert_config(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.put(
    "/config/{hostel_id}",
    response_model=AlertConfig,
    summary="Update attendance alert configuration for a hostel",
)
async def update_alert_config(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    payload: AlertConfig = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> AlertConfig:
    """
    Update the alert configuration for a hostel.
    """
    service = AttendanceAlertService(uow)
    try:
        return service.update_alert_config(
            hostel_id=hostel_id,
            config=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/trigger",
    response_model=AttendanceAlert,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger an attendance alert manually",
)
async def trigger_alert(
    payload: AlertTrigger,
    uow: UnitOfWork = Depends(get_uow),
) -> AttendanceAlert:
    """
    Manually trigger an attendance alert (e.g., low attendance, anomaly).
    """
    service = AttendanceAlertService(uow)
    try:
        return service.trigger_alert(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertAcknowledgment,
    status_code=status.HTTP_200_OK,
    summary="Acknowledge an attendance alert",
)
async def acknowledge_alert(
    alert_id: UUID = Path(..., description="Alert ID"),
    payload: AlertAcknowledgment = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> AlertAcknowledgment:
    """
    Acknowledge that an alert has been seen/handled.
    """
    service = AttendanceAlertService(uow)
    try:
        return service.acknowledge_alert(
            alert_id=alert_id,
            acknowledgment=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/",
    response_model=AlertList,
    summary="List attendance alerts",
)
async def list_alerts(
    hostel_id: Union[UUID, None] = Query(
        None,
        description="Optional hostel filter",
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> AlertList:
    """
    List attendance alerts, optionally filtered by hostel.
    """
    service = AttendanceAlertService(uow)
    try:
        return service.list_alerts(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/summary",
    response_model=AlertSummary,
    summary="Get attendance alert summary",
)
async def get_alert_summary(
    hostel_id: Union[UUID, None] = Query(
        None,
        description="Optional hostel filter",
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> AlertSummary:
    """
    Get summarized statistics for attendance alerts (counts, types, trends).
    """
    service = AttendanceAlertService(uow)
    try:
        return service.get_alert_summary(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)