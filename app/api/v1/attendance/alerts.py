from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.attendance import (
    AlertConfig,
    AttendanceAlert,
    AlertList,
    AlertSummary,
    AlertAcknowledgment,
)
from app.services.attendance.attendance_alert_service import AttendanceAlertService

router = APIRouter(prefix="/attendance/alerts", tags=["attendance:alerts"])


def get_alert_service(db: Session = Depends(deps.get_db)) -> AttendanceAlertService:
    return AttendanceAlertService(db=db)


@router.put(
    "/config",
    response_model=AlertConfig,
    summary="Save alert configuration for hostel",
)
def save_alert_configuration(
    payload: AlertConfig,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    """
    Configure alert thresholds (low attendance, consecutive absences, etc.) for a hostel.
    """
    return service.save_configuration(payload=payload, actor_id=_admin.id)


@router.get(
    "/config",
    response_model=AlertConfig,
    summary="Get alert configuration for hostel",
)
def get_alert_configuration(
    hostel_id: str = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    return service.get_configuration(hostel_id=hostel_id, actor_id=_admin.id)


@router.post(
    "/trigger",
    response_model=AttendanceAlert,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger manual attendance alert",
)
def trigger_alert(
    payload: AttendanceAlert,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    """
    Manually create an attendance alert for specific concerns.
    """
    return service.trigger_alert(payload=payload, actor_id=_admin.id)


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AttendanceAlert,
    summary="Acknowledge alert",
)
def acknowledge_alert(
    alert_id: str,
    payload: AlertAcknowledgment,
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    return service.acknowledge(alert_id=alert_id, payload=payload, actor_id=_admin.id)


@router.post(
    "/{alert_id}/resolve",
    response_model=AttendanceAlert,
    summary="Resolve alert",
)
def resolve_alert(
    alert_id: str,
    resolution_notes: Optional[str] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    return service.resolve_alert(
        alert_id=alert_id,
        resolution_notes=resolution_notes,
        actor_id=_admin.id,
    )


@router.get(
    "",
    response_model=AlertList,
    summary="List attendance alerts",
)
def list_alerts(
    hostel_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    status_filter: Optional[str] = Query(None, alias="status"),
    pagination=Depends(deps.get_pagination_params),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    """
    List alerts with filtering by severity/status and pagination.
    """
    return service.list_alerts(
        hostel_id=hostel_id,
        severity=severity,
        status=status_filter,
        pagination=pagination,
        actor_id=_admin.id,
    )


@router.get(
    "/summary",
    response_model=AlertSummary,
    summary="Get alert summary",
)
def get_alert_summary(
    hostel_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    _admin=Depends(deps.get_admin_user),
    service: AttendanceAlertService = Depends(get_alert_service),
) -> Any:
    """
    High-level summary of attendance alerts for dashboards.
    """
    return service.get_summary(
        hostel_id=hostel_id,
        days=days,
        actor_id=_admin.id,
    )