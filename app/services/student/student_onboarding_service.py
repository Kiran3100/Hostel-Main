# app/services/student/student_onboarding_service.py
"""
Student Onboarding Service

Thin wrapper around OnboardingWorkflowService for student-specific APIs.
"""

from __future__ import annotations

from uuid import UUID
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.services.workflows import OnboardingWorkflowService
from app.schemas.student import StudentCheckInRequest, StudentDetail
from app.repositories.student import StudentRepository
from app.core.exceptions import ValidationException


class StudentOnboardingService:
    """
    High-level service for student onboarding, delegating to the
    OnboardingWorkflowService for orchestration.
    """

    def __init__(
        self,
        onboarding_workflow: OnboardingWorkflowService,
        student_repo: StudentRepository,
    ) -> None:
        self.onboarding_workflow = onboarding_workflow
        self.student_repo = student_repo

    async def onboard_from_booking(
        self,
        db: Session,
        booking_id: UUID,
        initiated_by: UUID,
        check_in_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Execute the onboarding workflow for a confirmed booking.

        Returns the workflow execution result dict.
        """
        result = await self.onboarding_workflow.onboard_student(
            db=db,
            booking_id=booking_id,
            initiated_by=initiated_by,
            check_in_date=check_in_date,
        )
        return result

    async def quick_check_in(
        self,
        db: Session,
        hostel_id: UUID,
        check_in_data: Dict[str, Any],
        initiated_by: UUID,
    ) -> Dict[str, Any]:
        """
        Execute quick check-in for a walk-in student.

        check_in_data is a dict used by the underlying workflow.
        """
        result = await self.onboarding_workflow.quick_checkin_student(
            db=db,
            hostel_id=hostel_id,
            student_data=check_in_data,
            initiated_by=initiated_by,
        )
        return result

    def get_student_after_onboarding(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentDetail:
        """
        Convenience method to fetch student detail after onboarding.
        """
        student = self.student_repo.get_full_student(db, student_id)
        if not student:
            raise ValidationException("Student not found")
        return StudentDetail.model_validate(student)