from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.services.attendance.check_in_service import CheckInService

router = APIRouter(prefix="/attendance/check-in", tags=["attendance:check-in"])


def get_checkin_service(db: Session = Depends(deps.get_db)) -> CheckInService:
    return CheckInService(db=db)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Check in student",
)
def check_in(
    device_id: Optional[str] = Query(None, description="Device identifier"),
    _student=Depends(deps.get_student_user),
    service: CheckInService = Depends(get_checkin_service),
) -> Any:
    """
    Student check-in operation.

    Uses CheckInService.check_in().
    """
    return service.check_in(student_id=_student.id, device_id=device_id)


@router.post(
    "/out",
    status_code=status.HTTP_201_CREATED,
    summary="Check out student",
)
def check_out(
    device_id: Optional[str] = Query(None, description="Device identifier"),
    _student=Depends(deps.get_student_user),
    service: CheckInService = Depends(get_checkin_service),
) -> Any:
    """
    Student check-out operation.

    Uses CheckInService.check_out().
    """
    return service.check_out(student_id=_student.id, device_id=device_id)


@router.get(
    "/status",
    summary="Get student's current check-in status",
)
def get_check_in_status(
    _student=Depends(deps.get_student_user),
    service: CheckInService = Depends(get_checkin_service),
) -> Any:
    """
    Returns whether student is currently checked in and related metadata.

    Uses CheckInService.get_check_in_status().
    """
    return service.get_check_in_status(student_id=_student.id)