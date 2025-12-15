# app/api/v1/students/dashboard.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.student import StudentDashboardService
from app.schemas.student.student_dashboard import StudentDashboard
from . import CurrentUser, get_current_student

router = APIRouter(tags=["Students - Dashboard"])


def _get_service(session: Session) -> StudentDashboardService:
    uow = UnitOfWork(session)
    return StudentDashboardService(uow)


@router.get("/", response_model=StudentDashboard)
def get_my_dashboard(
    current_user: CurrentUser = Depends(get_current_student),
    session: Session = Depends(get_session),
) -> StudentDashboard:
    """
    Return the dashboard for the authenticated student.

    Expected service method:
        get_dashboard_for_user(user_id: UUID) -> StudentDashboard
    """
    service = _get_service(session)
    return service.get_dashboard_for_user(user_id=current_user.id)