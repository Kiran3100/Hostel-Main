# app/api/v1/supervisors/dashboard.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.supervisor import SupervisorDashboardService
from app.schemas.supervisor.supervisor_dashboard import SupervisorDashboard
from . import CurrentUser, get_current_supervisor

router = APIRouter(tags=["Supervisors - Dashboard"])


def _get_service(session: Session) -> SupervisorDashboardService:
    uow = UnitOfWork(session)
    return SupervisorDashboardService(uow)


@router.get("/", response_model=SupervisorDashboard)
def get_my_dashboard(
    current_user: CurrentUser = Depends(get_current_supervisor),
    session: Session = Depends(get_session),
) -> SupervisorDashboard:
    """
    Return the dashboard for the authenticated supervisor.

    Expected service method:
        get_dashboard_for_user(user_id: UUID) -> SupervisorDashboard
    """
    service = _get_service(session)
    return service.get_dashboard_for_user(user_id=current_user.id)