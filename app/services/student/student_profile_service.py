# app/services/student/student_profile_service.py
"""
Student Profile Service

Manages extended student profile information beyond core student table.
Provides enriched profile data with validation and caching support.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.student import (
    StudentRepository,
    StudentProfileRepository,
)
from app.schemas.student import (
    StudentProfileCreate,
    StudentProfileUpdate,
    StudentProfile,
    StudentDetail,
)
from app.core1.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)

logger = logging.getLogger(__name__)


class StudentProfileService:
    """
    High-level service for extended student profiles.

    Responsibilities:
    - Create and update extended profile details
    - Fetch enriched profile data
    - Validate profile completeness
    - Manage profile-related business logic

    Performance optimizations:
    - Profile data cached at repository level
    - Lazy loading for non-critical fields
    - Optimized joins for related data
    """

    def __init__(
        self,
        student_repo: StudentRepository,
        profile_repo: StudentProfileRepository,
    ) -> None:
        """
        Initialize service with required repositories.

        Args:
            student_repo: Repository for student operations
            profile_repo: Repository for profile-specific operations
        """
        self.student_repo = student_repo
        self.profile_repo = profile_repo

    # -------------------------------------------------------------------------
    # Profile CRUD Operations
    # -------------------------------------------------------------------------

    def get_profile(
        self,
        db: Session,
        student_id: UUID,
    ) -> Optional[StudentProfile]:
        """
        Retrieve student profile by student ID.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            StudentProfile or None if not found
        """
        try:
            obj = self.profile_repo.get_by_student_id(db, student_id)
            
            if not obj:
                logger.debug(f"No profile found for student: {student_id}")
                return None
            
            return StudentProfile.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving profile for {student_id}: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to retrieve profile: {str(e)}"
            ) from e

    def create_profile(
        self,
        db: Session,
        student_id: UUID,
        data: StudentProfileCreate,
    ) -> StudentProfile:
        """
        Create a new student profile.

        Args:
            db: Database session
            student_id: UUID of student
            data: Profile creation data

        Returns:
            StudentProfile: Created profile

        Raises:
            NotFoundException: If student not found
            ValidationException: If profile already exists or validation fails
        """
        # Verify student exists
        student = self._get_student_or_raise(db, student_id)

        # Check if profile already exists
        existing = self.profile_repo.get_by_student_id(db, student_id)
        if existing:
            raise ValidationException(
                f"Profile already exists for student: {student_id}"
            )

        try:
            payload = data.model_dump(exclude_none=True)
            payload["student_id"] = student_id

            obj = self.profile_repo.create(db, payload)
            
            logger.info(f"Profile created for student: {student_id}")
            
            return StudentProfile.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Database error creating profile: {str(e)}")
            raise BusinessLogicException(
                f"Failed to create profile: {str(e)}"
            ) from e

    def update_profile(
        self,
        db: Session,
        student_id: UUID,
        data: StudentProfileUpdate,
    ) -> StudentProfile:
        """
        Update an existing student profile.

        Args:
            db: Database session
            student_id: UUID of student
            data: Profile update data

        Returns:
            StudentProfile: Updated profile

        Raises:
            NotFoundException: If profile not found
        """
        existing = self.profile_repo.get_by_student_id(db, student_id)
        if not existing:
            raise NotFoundException(
                f"Profile not found for student: {student_id}"
            )

        try:
            payload = data.model_dump(exclude_none=True, exclude_unset=True)
            
            obj = self.profile_repo.update(db, existing, payload)
            
            logger.info(f"Profile updated for student: {student_id}")
            
            return StudentProfile.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Database error updating profile: {str(e)}")
            raise BusinessLogicException(
                f"Failed to update profile: {str(e)}"
            ) from e

    def upsert_profile(
        self,
        db: Session,
        student_id: UUID,
        data: StudentProfileCreate | StudentProfileUpdate,
    ) -> StudentProfile:
        """
        Create or update student profile (upsert operation).

        Args:
            db: Database session
            student_id: UUID of student
            data: Profile data

        Returns:
            StudentProfile: Created or updated profile

        Raises:
            NotFoundException: If student not found
        """
        # Verify student exists
        self._get_student_or_raise(db, student_id)

        existing = self.profile_repo.get_by_student_id(db, student_id)
        
        try:
            payload = data.model_dump(exclude_none=True, exclude_unset=True)
            payload["student_id"] = student_id

            if existing:
                obj = self.profile_repo.update(db, existing, payload)
                action = "updated"
            else:
                obj = self.profile_repo.create(db, payload)
                action = "created"

            logger.info(f"Profile {action} for student: {student_id}")
            
            return StudentProfile.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Database error in profile upsert: {str(e)}")
            raise BusinessLogicException(
                f"Failed to upsert profile: {str(e)}"
            ) from e

    def delete_profile(
        self,
        db: Session,
        student_id: UUID,
    ) -> None:
        """
        Delete a student profile.

        Args:
            db: Database session
            student_id: UUID of student
        """
        existing = self.profile_repo.get_by_student_id(db, student_id)
        
        if not existing:
            logger.warning(f"No profile to delete for student: {student_id}")
            return

        try:
            self.profile_repo.delete(db, existing)
            logger.info(f"Profile deleted for student: {student_id}")

        except SQLAlchemyError as e:
            logger.error(f"Database error deleting profile: {str(e)}")
            raise BusinessLogicException(
                f"Failed to delete profile: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Enriched Views
    # -------------------------------------------------------------------------

    def get_student_with_profile(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentDetail:
        """
        Fetch complete student detail including core data and profile.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            StudentDetail: Comprehensive student information

        Raises:
            NotFoundException: If student not found
        """
        try:
            obj = self.student_repo.get_full_student(db, student_id)
            
            if not obj:
                raise NotFoundException(f"Student not found: {student_id}")
            
            return StudentDetail.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving full student {student_id}: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to retrieve student with profile: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Profile Validation and Analysis
    # -------------------------------------------------------------------------

    def check_profile_completeness(
        self,
        db: Session,
        student_id: UUID,
    ) -> Dict[str, Any]:
        """
        Analyze profile completeness and return missing fields.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            Dictionary with completeness metrics
        """
        profile = self.get_profile(db, student_id)
        
        if not profile:
            return {
                "complete": False,
                "completeness_percentage": 0,
                "missing_fields": ["all"],
                "has_profile": False,
            }

        # Define required fields for completeness
        required_fields = [
            "blood_group",
            "emergency_contact_name",
            "emergency_contact_phone",
            "permanent_address",
            "current_address",
        ]

        # Check which fields are missing or empty
        missing = []
        for field in required_fields:
            value = getattr(profile, field, None)
            if not value:
                missing.append(field)

        total_fields = len(required_fields)
        filled_fields = total_fields - len(missing)
        completeness = (filled_fields / total_fields) * 100 if total_fields > 0 else 0

        return {
            "complete": len(missing) == 0,
            "completeness_percentage": round(completeness, 2),
            "missing_fields": missing,
            "filled_fields": filled_fields,
            "total_required_fields": total_fields,
            "has_profile": True,
        }

    def get_incomplete_profiles(
        self,
        db: Session,
        hostel_id: UUID,
        threshold: int = 80,
    ) -> list[Dict[str, Any]]:
        """
        Get list of students with incomplete profiles.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            threshold: Minimum completeness percentage (0-100)

        Returns:
            List of students with incomplete profiles
        """
        try:
            incomplete = self.profile_repo.get_incomplete_profiles(
                db,
                hostel_id=hostel_id,
                threshold=threshold,
            )
            
            return incomplete

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving incomplete profiles: {str(e)}")
            raise BusinessLogicException(
                f"Failed to retrieve incomplete profiles: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _get_student_or_raise(
        self,
        db: Session,
        student_id: UUID,
    ) -> Any:
        """
        Get student or raise NotFoundException.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            Student ORM object

        Raises:
            NotFoundException: If student not found
        """
        student = self.student_repo.get_by_id(db, student_id)
        if not student:
            raise NotFoundException(f"Student not found: {student_id}")
        return student