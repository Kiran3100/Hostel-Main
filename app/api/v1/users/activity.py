# app/api/v1/users/activity.py

from typing import Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.users import UserActivityService
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Users - Activity"])


def _get_activity_service(session: Session) -> UserActivityService:
    uow = UnitOfWork(session)
    return UserActivityService(uow)


@router.get("/", response_model=List[dict])
def list_my_activity(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """
    List recent activity for the authenticated user.

    If you later add dedicated Pydantic schemas for user activity
    (e.g., UserActivityLogResponse), you can switch the response_model.
    """
    service = _get_activity_service(session)
    # Expected service method:
    #   list_activity_for_user(user_id: UUID, limit: int) -> list[BaseSchema | dict]
    activities = service.list_activity_for_user(
        user_id=current_user.id,
        limit=limit,
    )

    # Assume service returns serializable objects (either dicts or Pydantic models).
    # If they're Pydantic models, FastAPI will handle serialization.
    return activities