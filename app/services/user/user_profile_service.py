"""
User Profile Service

Manages user profile CRUD operations and preferences that live in profile.
"""

from __future__ import annotations

from uuid import UUID
from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.user import (
    UserRepository,
    UserProfileRepository,
)
from app.schemas.user import (
    ProfileUpdate,
    ProfileImageUpdate,
    ContactInfoUpdate,
    UserDetail,
)
from app.core.exceptions import ValidationException


class UserProfileService:
    """
    High-level service for user profile operations.

    Responsibilities:
    - Get/update profile info
    - Update profile image
    - Update contact info (and emergency contact fields on User)
    """

    def __init__(
        self,
        user_repo: UserRepository,
        profile_repo: UserProfileRepository,
    ) -> None:
        self.user_repo = user_repo
        self.profile_repo = profile_repo

    def get_profile(
        self,
        db: Session,
        user_id: UUID,
    ) -> UserDetail:
        """
        Get full profile (User + UserProfile + address/emergency info).
        """
        user = self.user_repo.get_full_user(db, user_id)
        if not user:
            raise ValidationException("User not found")

        return UserDetail.model_validate(user)

    def update_profile(
        self,
        db: Session,
        user_id: UUID,
        data: ProfileUpdate,
    ) -> UserDetail:
        """
        Update high-level profile fields (name, gender, DOB, address).
        """
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise ValidationException("User not found")

        profile = self.profile_repo.get_by_user_id(db, user_id)

        user_payload = {}
        profile_payload = {}

        d = data.model_dump(exclude_none=True)

        # Split fields between User and UserProfile as appropriate
        for field, value in d.items():
            if field in {"full_name", "gender", "date_of_birth"}:
                user_payload[field] = value
            else:
                profile_payload[field] = value

        if user_payload:
            self.user_repo.update(db, user, user_payload)

        if profile_payload:
            if profile:
                self.profile_repo.update(db, profile, profile_payload)
            else:
                profile_payload["user_id"] = user_id
                self.profile_repo.create(db, profile_payload)

        # Reload full user for response
        full = self.user_repo.get_full_user(db, user_id)
        return UserDetail.model_validate(full)

    def update_profile_image(
        self,
        db: Session,
        user_id: UUID,
        data: ProfileImageUpdate,
    ) -> UserDetail:
        """
        Update profile image URL.
        """
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise ValidationException("User not found")

        self.user_repo.update(
            db,
            user,
            {"profile_image_url": data.profile_image_url},
        )

        full = self.user_repo.get_full_user(db, user_id)
        return UserDetail.model_validate(full)

    def update_contact_info(
        self,
        db: Session,
        user_id: UUID,
        data: ContactInfoUpdate,
    ) -> UserDetail:
        """
        Update phone/email and emergency contact details on User.
        """
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise ValidationException("User not found")

        payload = data.model_dump(exclude_none=True)
        self.user_repo.update(db, user, payload)

        full = self.user_repo.get_full_user(db, user_id)
        return UserDetail.model_validate(full)