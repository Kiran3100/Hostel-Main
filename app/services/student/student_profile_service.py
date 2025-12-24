# app/services/student/student_profile_service.py
"""
Student Profile Service

Manages extended student profile (non-core student table).
"""

from __future__ import annotations

from uuid import UUID
from typing import Optional

from sqlalchemy.orm import Session

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
from app.core.exceptions import ValidationException


class StudentProfileService:
    """
    High-level service for extended student profiles.

    Responsibilities:
    - Create/update extended profile details
    - Fetch profile data
    """

    def __init__(
        self,
        student_repo: StudentRepository,
        profile_repo: StudentProfileRepository,
    ) -> None:
        self.student_repo = student_repo
        self.profile_repo = profile_repo

    def get_profile(
        self,
        db: Session,
        student_id: UUID,
    ) -> Optional[StudentProfile]:
        obj = self.profile_repo.get_by_student_id(db, student_id)
        if not obj:
            return None
        return StudentProfile.model_validate(obj)

    def upsert_profile(
        self,
        db: Session,
        student_id: UUID,
        data: StudentProfileCreate | StudentProfileUpdate,
    ) -> StudentProfile:
        """
        Create or update student profile.
        """
        student = self.student_repo.get_by_id(db, student_id)
        if not student:
            raise ValidationException("Student not found")

        existing = self.profile_repo.get_by_student_id(db, student_id)
        payload = data.model_dump(exclude_none=True)
        payload["student_id"] = student_id

        if existing:
            obj = self.profile_repo.update(db, existing, payload)
        else:
            obj = self.profile_repo.create(db, payload)

        return StudentProfile.model_validate(obj)

    def get_student_with_profile(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentDetail:
        """
        Fetch full student detail that includes core student + profile.
        """
        obj = self.student_repo.get_full_student(db, student_id)
        if not obj:
            raise ValidationException("Student not found")
        return StudentDetail.model_validate(obj)