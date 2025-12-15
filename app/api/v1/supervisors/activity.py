# app/api/v1/supervisors/activity.py

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.supervisor import SupervisorActivityService
from app.schemas.supervisor.supervisor_activity import (
    SupervisorActivityLog,
    ActivityDetail,
    ActivitySummary,
    ActivityFilterParams,
)
from . import CurrentUser, get_current_user, get_current_supervisor

router = APIRouter(tags=["Supervisors - Activity"])


def _get_service(session: Session) -> SupervisorActivityService:
    uow = UnitOfWork(session)
    return SupervisorActivityService(uow)


@router.get("/", response_model=List[SupervisorActivityLog])
def list_my_activity(
    filters: ActivityFilterParams = Depends(),
    current_user: CurrentUser = Depends(get_current_supervisor),
    session: Session = Depends(get_session),
) -> List[SupervisorActivityLog]:
    """
    List recent activity for the authenticated supervisor.

    Expected service method:
        list_activity_for_user(user_id: UUID, filters: ActivityFilterParams) -> list[SupervisorActivityLog]
    """
    service = _get_service(session)
    return service.list_activity_for_user(
        user_id=current_user.id,
        filters=filters,
    )


@router.get("/summary", response_model=ActivitySummary)
def get_my_activity_summary(
    filters: ActivityFilterParams = Depends(),
    current_user: CurrentUser = Depends(get_current_supervisor),
    session: Session = Depends(get_session),
) -> ActivitySummary:
    """
    Get a high-level summary of activity for the authenticated supervisor.

    Expected service method:
        get_activity_summary_for_user(user_id: UUID, filters: ActivityFilterParams) -> ActivitySummary
    """
    service = _get_service(session)
    return service.get_activity_summary_for_user(
        user_id=current_user.id,
        filters=filters,
    )


@router.get("/{activity_id}", response_model=ActivityDetail)
def get_activity_detail(
    activity_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ActivityDetail:
    """
    Get detailed information about a single activity record.

    Expected service method:
        get_activity_detail(activity_id: UUID) -> ActivityDetail
    """
    service = _get_service(session)
    return service.get_activity_detail(activity_id=activity_id)