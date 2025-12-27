from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
# Assuming calendar schemas exist or returning simple Dict/List
from app.services.leave.leave_calendar_service import LeaveCalendarService

router = APIRouter(prefix="/leaves/calendar", tags=["leaves:calendar"])


def get_calendar_service(db: Session = Depends(deps.get_db)) -> LeaveCalendarService:
    return LeaveCalendarService(db=db)


@router.get(
    "/hostel",
    summary="Get hostel leave calendar (month view)",
)
def get_hostel_calendar(
    hostel_id: str = Query(...),
    year: int = Query(...),
    month: int = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: LeaveCalendarService = Depends(get_calendar_service),
) -> Any:
    return service.hostel_month_calendar(hostel_id, year, month)


@router.get(
    "/student",
    summary="Get student leave calendar",
)
def get_student_calendar(
    student_id: str = Query(None),
    year: int = Query(...),
    month: int = Query(...),
    current_user=Depends(deps.get_current_user),
    service: LeaveCalendarService = Depends(get_calendar_service),
) -> Any:
    target_id = student_id or current_user.id
    return service.student_month_calendar(target_id, year, month)