# app/api/v1/visitors/preferences.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.visitor import VisitorPreferencesService
from app.schemas.visitor.visitor_preferences import (
    VisitorPreferences,
    PreferenceUpdate,
)
from . import CurrentUser, get_current_visitor

router = APIRouter(tags=["Visitor - Preferences"])


def _get_service(session: Session) -> VisitorPreferencesService:
    uow = UnitOfWork(session)
    return VisitorPreferencesService(uow)


@router.get("/", response_model=VisitorPreferences)
def get_preferences(
    current_user: CurrentUser = Depends(get_current_visitor),
    session: Session = Depends(get_session),
) -> VisitorPreferences:
    """
    Get the current visitor's preferences and notification settings.
    """
    service = _get_service(session)
    # Expected service method:
    #   get_preferences_for_user(user_id: UUID) -> VisitorPreferences
    return service.get_preferences_for_user(user_id=current_user.id)


@router.patch("", response_model=VisitorPreferences)
def update_preferences(
    payload: PreferenceUpdate,
    current_user: CurrentUser = Depends(get_current_visitor),
    session: Session = Depends(get_session),
) -> VisitorPreferences:
    """
    Partially update the current visitor's preferences.
    """
    service = _get_service(session)
    # Expected service method:
    #   update_preferences_for_user(user_id: UUID, data: PreferenceUpdate) -> VisitorPreferences
    return service.update_preferences_for_user(
        user_id=current_user.id,
        data=payload,
    )