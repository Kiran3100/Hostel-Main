"""
User Profile Service

Manages user profile CRUD operations and preferences that live in profile.
Enhanced with comprehensive validation, profile completeness tracking, and image handling.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

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
from app.core.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)
from app.utils.string_utils import StringHelper
from app.utils.file_utils import FileHelper

logger = logging.getLogger(__name__)


class UserProfileService:
    """
    High-level service for user profile operations.

    Responsibilities:
    - Get/update profile info
    - Update profile image
    - Update contact info
    - Calculate profile completeness
    - Validate profile data
    """

    # Profile completeness weights
    PROFILE_FIELD_WEIGHTS = {
        "full_name": 10,
        "email": 15,
        "phone": 15,
        "date_of_birth": 10,
        "gender": 5,
        "profile_image_url": 10,
        "address": 15,
        "emergency_contact_name": 10,
        "emergency_contact_phone": 10,
    }

    def __init__(
        self,
        user_repo: UserRepository,
        profile_repo: UserProfileRepository,
    ) -> None:
        self.user_repo = user_repo
        self.profile_repo = profile_repo

    # -------------------------------------------------------------------------
    # Profile Retrieval
    # -------------------------------------------------------------------------

    def get_profile(
        self,
        db: Session,
        user_id: UUID,
    ) -> UserDetail:
        """
        Get full profile (User + UserProfile + address/emergency info).

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            UserDetail schema

        Raises:
            NotFoundException: If user doesn't exist
        """
        try:
            user = self.user_repo.get_full_user(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            return UserDetail.model_validate(user)

        except SQLAlchemyError as e:
            logger.error(f"Database error getting profile for user {user_id}: {str(e)}")
            raise BusinessLogicException("Failed to retrieve user profile")

    def get_profile_completeness(
        self,
        db: Session,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Calculate profile completeness percentage and missing fields.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            Dictionary with completeness percentage and missing fields
        """
        try:
            profile = self.get_profile(db, user_id)
            profile_dict = profile.model_dump()

            total_weight = sum(self.PROFILE_FIELD_WEIGHTS.values())
            earned_weight = 0
            missing_fields = []

            for field, weight in self.PROFILE_FIELD_WEIGHTS.items():
                value = profile_dict.get(field)
                
                if value:
                    earned_weight += weight
                else:
                    missing_fields.append(field)

            completeness_percentage = int((earned_weight / total_weight) * 100)

            return {
                "completeness_percentage": completeness_percentage,
                "missing_fields": missing_fields,
                "is_complete": completeness_percentage == 100,
                "total_fields": len(self.PROFILE_FIELD_WEIGHTS),
                "completed_fields": len(self.PROFILE_FIELD_WEIGHTS) - len(missing_fields),
            }

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"Error calculating profile completeness for user {user_id}: {str(e)}"
            )
            raise BusinessLogicException("Failed to calculate profile completeness")

    # -------------------------------------------------------------------------
    # Profile Updates
    # -------------------------------------------------------------------------

    def update_profile(
        self,
        db: Session,
        user_id: UUID,
        data: ProfileUpdate,
    ) -> UserDetail:
        """
        Update high-level profile fields (name, gender, DOB, address).

        Args:
            db: Database session
            user_id: User identifier
            data: Profile update data

        Returns:
            Updated UserDetail schema

        Raises:
            NotFoundException: If user doesn't exist
            ValidationException: If validation fails
        """
        # Validate update data
        self._validate_profile_update(data)

        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            profile = self.profile_repo.get_by_user_id(db, user_id)

            user_payload: Dict[str, Any] = {}
            profile_payload: Dict[str, Any] = {}

            d = data.model_dump(exclude_none=True)

            # Split fields between User and UserProfile
            user_fields = {"full_name", "gender", "date_of_birth"}
            
            for field, value in d.items():
                if field in user_fields:
                    user_payload[field] = value
                else:
                    profile_payload[field] = value

            # Update User model
            if user_payload:
                # Normalize name
                if "full_name" in user_payload:
                    user_payload["full_name"] = self._normalize_name(
                        user_payload["full_name"]
                    )
                
                self.user_repo.update(db, user, user_payload)
                logger.info(f"Updated user fields for user {user_id}")

            # Update UserProfile model
            if profile_payload:
                if profile:
                    self.profile_repo.update(db, profile, profile_payload)
                    logger.info(f"Updated profile fields for user {user_id}")
                else:
                    profile_payload["user_id"] = user_id
                    self.profile_repo.create(db, profile_payload)
                    logger.info(f"Created profile for user {user_id}")

            # Reload full user for response
            full = self.user_repo.get_full_user(db, user_id)
            return UserDetail.model_validate(full)

        except (NotFoundException, ValidationException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error updating profile for user {user_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicException("Failed to update profile")

    def update_profile_image(
        self,
        db: Session,
        user_id: UUID,
        data: ProfileImageUpdate,
    ) -> UserDetail:
        """
        Update profile image URL.

        Args:
            db: Database session
            user_id: User identifier
            data: Profile image update data

        Returns:
            Updated UserDetail schema

        Raises:
            NotFoundException: If user doesn't exist
            ValidationException: If image URL is invalid
        """
        # Validate image URL
        self._validate_image_url(data.profile_image_url)

        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            self.user_repo.update(
                db,
                user,
                {"profile_image_url": data.profile_image_url},
            )

            logger.info(f"Updated profile image for user {user_id}")

            # Reload full user for response
            full = self.user_repo.get_full_user(db, user_id)
            return UserDetail.model_validate(full)

        except (NotFoundException, ValidationException):
            raise
        except SQLAlchemyError as e:
            logger.error(
                f"Database error updating profile image for user {user_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicException("Failed to update profile image")

    def remove_profile_image(
        self,
        db: Session,
        user_id: UUID,
    ) -> UserDetail:
        """
        Remove profile image.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            Updated UserDetail schema

        Raises:
            NotFoundException: If user doesn't exist
        """
        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            self.user_repo.update(
                db,
                user,
                {"profile_image_url": None},
            )

            logger.info(f"Removed profile image for user {user_id}")

            full = self.user_repo.get_full_user(db, user_id)
            return UserDetail.model_validate(full)

        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(
                f"Database error removing profile image for user {user_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicException("Failed to remove profile image")

    def update_contact_info(
        self,
        db: Session,
        user_id: UUID,
        data: ContactInfoUpdate,
    ) -> UserDetail:
        """
        Update phone/email and emergency contact details on User.

        Args:
            db: Database session
            user_id: User identifier
            data: Contact info update data

        Returns:
            Updated UserDetail schema

        Raises:
            NotFoundException: If user doesn't exist
            ValidationException: If validation fails
        """
        # Validate contact info
        self._validate_contact_info(data)

        try:
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                raise NotFoundException(f"User {user_id} not found")

            payload = data.model_dump(exclude_none=True)

            # Normalize phone if provided
            if "phone" in payload and payload["phone"]:
                payload["phone"] = StringHelper.normalize_phone(payload["phone"])

            # Normalize email if provided
            if "email" in payload and payload["email"]:
                payload["email"] = payload["email"].strip().lower()

            # Normalize emergency contact phone if provided
            if "emergency_contact_phone" in payload and payload["emergency_contact_phone"]:
                payload["emergency_contact_phone"] = StringHelper.normalize_phone(
                    payload["emergency_contact_phone"]
                )

            # Check for email/phone uniqueness if changed
            if "email" in payload and payload["email"] != user.email:
                existing = self.user_repo.get_by_email(db, payload["email"])
                if existing and existing.id != user_id:
                    raise ValidationException("Email already in use by another user")

            if "phone" in payload and payload["phone"] != user.phone:
                existing = self.user_repo.get_by_phone(db, payload["phone"])
                if existing and existing.id != user_id:
                    raise ValidationException("Phone number already in use by another user")

            self.user_repo.update(db, user, payload)

            logger.info(f"Updated contact info for user {user_id}")

            # Reload full user for response
            full = self.user_repo.get_full_user(db, user_id)
            return UserDetail.model_validate(full)

        except (NotFoundException, ValidationException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error updating contact info for user {user_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicException("Failed to update contact info")

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_profile_update(self, data: ProfileUpdate) -> None:
        """Validate profile update data."""
        data_dict = data.model_dump(exclude_none=True)

        # Validate full name if provided
        if "full_name" in data_dict:
            name = data_dict["full_name"]
            if not name or len(name.strip()) < 2:
                raise ValidationException("Full name must be at least 2 characters")
            if len(name) > 100:
                raise ValidationException("Full name must not exceed 100 characters")

        # Validate gender if provided
        if "gender" in data_dict:
            valid_genders = ["male", "female", "other", "prefer_not_to_say"]
            if data_dict["gender"] and data_dict["gender"].lower() not in valid_genders:
                raise ValidationException(
                    f"Invalid gender. Must be one of: {valid_genders}"
                )

        # Validate date of birth if provided
        if "date_of_birth" in data_dict and data_dict["date_of_birth"]:
            from datetime import date
            dob = data_dict["date_of_birth"]
            
            if dob >= date.today():
                raise ValidationException("Date of birth must be in the past")
            
            # Check minimum age (e.g., 13 years)
            min_age = 13
            age = (date.today() - dob).days // 365
            if age < min_age:
                raise ValidationException(f"User must be at least {min_age} years old")

    def _validate_contact_info(self, data: ContactInfoUpdate) -> None:
        """Validate contact info update data."""
        data_dict = data.model_dump(exclude_none=True)

        # Validate email if provided
        if "email" in data_dict and data_dict["email"]:
            if not StringHelper.is_valid_email(data_dict["email"]):
                raise ValidationException("Invalid email format")

        # Validate phone if provided
        if "phone" in data_dict and data_dict["phone"]:
            normalized = StringHelper.normalize_phone(data_dict["phone"])
            if len(normalized) < 10 or len(normalized) > 15:
                raise ValidationException("Phone number must be between 10 and 15 digits")

        # Validate emergency contact phone if provided
        if "emergency_contact_phone" in data_dict and data_dict["emergency_contact_phone"]:
            normalized = StringHelper.normalize_phone(data_dict["emergency_contact_phone"])
            if len(normalized) < 10 or len(normalized) > 15:
                raise ValidationException(
                    "Emergency contact phone must be between 10 and 15 digits"
                )

        # Validate emergency contact name if provided
        if "emergency_contact_name" in data_dict and data_dict["emergency_contact_name"]:
            name = data_dict["emergency_contact_name"]
            if len(name.strip()) < 2:
                raise ValidationException(
                    "Emergency contact name must be at least 2 characters"
                )
            if len(name) > 100:
                raise ValidationException(
                    "Emergency contact name must not exceed 100 characters"
                )

    def _validate_image_url(self, url: Optional[str]) -> None:
        """Validate profile image URL."""
        if not url:
            return

        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            raise ValidationException("Image URL must be a valid HTTP(S) URL")

        # Check file extension
        valid_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
        if not any(url.lower().endswith(ext) for ext in valid_extensions):
            raise ValidationException(
                f"Image URL must end with one of: {', '.join(valid_extensions)}"
            )

        # Check URL length
        if len(url) > 500:
            raise ValidationException("Image URL must not exceed 500 characters")

    def _normalize_name(self, name: str) -> str:
        """Normalize a person's name."""
        # Remove extra whitespace and title case
        parts = name.strip().split()
        normalized = " ".join(part.capitalize() for part in parts if part)
        return normalized