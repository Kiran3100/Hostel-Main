# app/api/v1/users/profile.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.users import UserProfileService
from app.schemas.user.user_profile import (
    ProfileUpdate,
    ProfileImageUpdate,
    ContactInfoUpdate,
    NotificationPreferencesUpdate,
)
from app.schemas.user.user_response import UserDetail
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Users - Profile"])


def _get_profile_service(session: Session) -> UserProfileService:
    uow = UnitOfWork(session)
    return UserProfileService(uow)


@router.patch("", response_model=UserDetail)
def update_profile(
    payload: ProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserDetail:
    """
    Update general profile fields (name, DOB, gender, etc.) for the current user.
    """
    service = _get_profile_service(session)
    # Expected service method:
    #   update_profile(user_id: UUID, data: ProfileUpdate) -> UserDetail
    return service.update_profile(user_id=current_user.id, data=payload)


@router.patch("/image", response_model=UserDetail)
def update_profile_image(
    payload: ProfileImageUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserDetail:
    """
    Update the profile image URL or upload reference for the current user.
    """
    service = _get_profile_service(session)
    # Expected service method:
    #   update_profile_image(user_id: UUID, data: ProfileImageUpdate) -> UserDetail
    return service.update_profile_image(user_id=current_user.id, data=payload)


@router.patch("/contact", response_model=UserDetail)
def update_contact_info(
    payload: ContactInfoUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserDetail:
    """
    Update contact information (email/phone/address/emergency) for the current user.
    """
    service = _get_profile_service(session)
    # Expected service method:
    #   update_contact_info(user_id: UUID, data: ContactInfoUpdate) -> UserDetail
    return service.update_contact_info(user_id=current_user.id, data=payload)


@router.patch("/notifications", response_model=UserDetail)
def update_notification_preferences(
    payload: NotificationPreferencesUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserDetail:
    """
    Update high-level notification preferences for the current user.
    """
    service = _get_profile_service(session)
    # Expected service method:
    #   update_notification_preferences(user_id: UUID, data: NotificationPreferencesUpdate) -> UserDetail
    return service.update_notification_preferences(
        user_id=current_user.id,
        data=payload,
    )