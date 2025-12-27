from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.attendance import (
    AttendancePolicy,
    PolicyConfig,
    PolicyUpdate,
    PolicyViolation,
)
from app.services.attendance.attendance_policy_service import AttendancePolicyService

router = APIRouter(prefix="/attendance/policies", tags=["attendance:policies"])


def get_policy_service(db: Session = Depends(deps.get_db)) -> AttendancePolicyService:
    return AttendancePolicyService(db=db)


@router.get(
    "",
    response_model=AttendancePolicy,
    summary="Get current attendance policy for hostel",
)
def get_attendance_policy(
    hostel_id: str = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: AttendancePolicyService = Depends(get_policy_service),
) -> Any:
    return service.get_policy(hostel_id=hostel_id, actor_id=_admin.id)


@router.post(
    "",
    response_model=AttendancePolicy,
    status_code=status.HTTP_201_CREATED,
    summary="Create attendance policy",
)
def create_attendance_policy(
    payload: PolicyConfig,
    _super_admin=Depends(deps.get_super_admin_user),
    service: AttendancePolicyService = Depends(get_policy_service),
) -> Any:
    return service.create_policy(payload=payload, actor_id=_super_admin.id)


@router.put(
    "/{policy_id}",
    response_model=AttendancePolicy,
    summary="Update attendance policy",
)
def update_attendance_policy(
    policy_id: str,
    payload: PolicyUpdate,
    _super_admin=Depends(deps.get_super_admin_user),
    service: AttendancePolicyService = Depends(get_policy_service),
) -> Any:
    return service.update_policy(
        policy_id=policy_id,
        payload=payload,
        actor_id=_super_admin.id,
    )


@router.post(
    "/detect-violations",
    response_model=List[PolicyViolation],
    summary="Detect attendance policy violations",
)
def detect_policy_violations(
    hostel_id: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: AttendancePolicyService = Depends(get_policy_service),
) -> Any:
    """
    Detect violations (low attendance, consecutive absences, etc.) within a period.
    """
    return service.detect_violations(
        hostel_id=hostel_id,
        start_date_str=start_date,
        end_date_str=end_date,
        actor_id=_admin.id,
    )


@router.get(
    "/violations/summary",
    summary="Get policy violation summary",
)
def get_violation_summary(
    hostel_id: str = Query(...),
    days: int = Query(30, ge=1, le=365),
    _admin=Depends(deps.get_admin_user),
    service: AttendancePolicyService = Depends(get_policy_service),
) -> Any:
    """
    Return aggregate statistics of attendance policy violations for dashboards.
    """
    return service.get_violation_summary(
        hostel_id=hostel_id,
        days=days,
        actor_id=_admin.id,
    )