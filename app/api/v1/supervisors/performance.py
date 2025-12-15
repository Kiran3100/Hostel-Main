# app/api/v1/supervisors/performance.py

from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.supervisor import SupervisorPerformanceService
from app.schemas.supervisor.supervisor_performance import (
    PerformanceReport,
    PeerComparison,
)
from . import CurrentUser, get_current_user, get_current_supervisor

router = APIRouter(tags=["Supervisors - Performance"])


def _get_service(session: Session) -> SupervisorPerformanceService:
    uow = UnitOfWork(session)
    return SupervisorPerformanceService(uow)


@router.get("/me", response_model=PerformanceReport)
def get_my_performance(
    current_user: CurrentUser = Depends(get_current_supervisor),
    session: Session = Depends(get_session),
) -> PerformanceReport:
    """
    Get a detailed performance report for the authenticated supervisor.

    Expected service method:
        get_performance_for_user(user_id: UUID) -> PerformanceReport
    """
    service = _get_service(session)
    return service.get_performance_for_user(user_id=current_user.id)


@router.get("/{supervisor_id}", response_model=PerformanceReport)
def get_performance_for_supervisor(
    supervisor_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> PerformanceReport:
    """
    Get a detailed performance report for a specific supervisor.

    Expected service method:
        get_performance_for_supervisor(supervisor_id: UUID) -> PerformanceReport
    """
    service = _get_service(session)
    return service.get_performance_for_supervisor(supervisor_id=supervisor_id)


@router.get("/comparison", response_model=PeerComparison)
def compare_supervisors(
    hostel_id: Union[UUID, None] = Query(
        None,
        description="Restrict comparison to a single hostel (optional)",
    ),
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Maximum number of supervisors to include in comparison",
    ),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> PeerComparison:
    """
    Compare supervisors' performance (e.g., top/bottom performers).

    Expected service method:
        compare_supervisors(hostel_id: Union[UUID, None], limit: int) -> PeerComparison
    """
    service = _get_service(session)
    return service.compare_supervisors(
        hostel_id=hostel_id,
        limit=limit,
    )