# app/api/v1/notifications/preferences.py
from typing import Union

from fastapi import APIRouter, Depends, Query, status, Response
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.notification import PreferenceService
from app.schemas.notification.notification_preferences import (
    UserPreferences,
    PreferenceUpdate,
    UnsubscribeRequest,
)
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Notifications - Preferences"])


def _get_service(session: Session) -> PreferenceService:
    uow = UnitOfWork(session)
    return PreferenceService(uow)


@router.get("/me", response_model=UserPreferences)
def get_my_preferences(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserPreferences:
    """
    Get notification preferences for the authenticated user.
    """
    service = _get_service(session)
    # Expected: get_preferences(user_id: UUID) -> UserPreferences
    return service.get_preferences(user_id=current_user.id)


@router.patch("/me", response_model=UserPreferences)
def update_my_preferences(
    payload: PreferenceUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserPreferences:
    """
    Update notification preferences for the authenticated user.
    """
    service = _get_service(session)
    # Expected: update_preferences(user_id: UUID, data: PreferenceUpdate) -> UserPreferences
    return service.update_preferences(
        user_id=current_user.id,
        data=payload,
    )


@router.post("/unsubscribe")
def unsubscribe(
    # Convert request body fields to query parameters
    token: Union[str, None] = Query(None, description="Unsubscribe token"),
    email: Union[str, None] = Query(None, description="Email to unsubscribe"),
    notification_type: Union[str, None] = Query(None, description="Notification type"),
    session: Session = Depends(get_session),
) -> Response:
    """
    Unsubscribe endpoint (can be used with signed links; may not require auth).

    Service is responsible for validating tokens / keys in the request.
    """
    service = _get_service(session)
    
    # Create UnsubscribeRequest object from query parameters
    unsubscribe_data = UnsubscribeRequest(
        token=token,
        email=email,
        notification_type=notification_type
    )
    
    # Expected: handle_unsubscribe(request: UnsubscribeRequest) -> None
    service.handle_unsubscribe(request=unsubscribe_data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)