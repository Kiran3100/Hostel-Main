# app/api/v1/visitors/dashboard.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.visitor import VisitorDashboardService
from app.schemas.visitor.visitor_dashboard import VisitorDashboard
from . import CurrentUser, get_current_visitor

router = APIRouter(tags=["Visitor - Dashboard"])


def _get_service(session: Session) -> VisitorDashboardService:
    uow = UnitOfWork(session)
    return VisitorDashboardService(uow)


@router.get("/", response_model=VisitorDashboard)
def get_dashboard(
    current_user: CurrentUser = Depends(get_current_visitor),
    session: Session = Depends(get_session),
) -> VisitorDashboard:
    """
    Return the visitor dashboard for the authenticated visitor.
    """
    service = _get_service(session)
    # Expected service method:
    #   get_dashboard_for_user(user_id: UUID) -> VisitorDashboard
    return service.get_dashboard_for_user(user_id=current_user.id)