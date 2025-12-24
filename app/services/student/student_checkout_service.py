# app/services/student/student_checkout_service.py
"""
Student Checkout Service

Thin wrapper around the generic CheckoutWorkflowService for student-specific APIs.
"""

from __future__ import annotations

from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.services.workflows import CheckoutWorkflowService
from app.schemas.student import StudentCheckOutRequest
from app.schemas.student import StudentDetail
from app.repositories.student import StudentRepository
from app.core.exceptions import ValidationException


class StudentCheckoutService:
    """
    High-level service for student checkout, delegating orchestration to
    the CheckoutWorkflowService.
    """

    def __init__(
        self,
        checkout_workflow: CheckoutWorkflowService,
        student_repo: StudentRepository,
    ) -> None:
        self.checkout_workflow = checkout_workflow
        self.student_repo = student_repo

    async def checkout_student(
        self,
        db: Session,
        request: StudentCheckOutRequest,
        initiated_by: UUID,
    ) -> Dict[str, Any]:
        """
        Run the full checkout workflow for a student and return summary.

        Returns the workflow execution result dict.
        """
        result = await self.checkout_workflow.checkout_student(
            db=db,
            student_id=request.student_id,
            checkout_date=request.checkout_date or datetime.utcnow(),
            initiated_by=initiated_by,
            reason=request.reason,
            forwarding_address=request.forwarding_address,
            clearance_data=request.clearance_data,
        )
        return result

    async def emergency_checkout(
        self,
        db: Session,
        student_id: UUID,
        initiated_by: UUID,
        reason: str,
        emergency_contact: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform an emergency checkout.
        """
        result = await self.checkout_workflow.emergency_checkout(
            db=db,
            student_id=student_id,
            initiated_by=initiated_by,
            emergency_reason=reason,
            emergency_contact=emergency_contact,
        )
        return result

    def get_student_after_checkout(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentDetail:
        """
        Convenience method: retrieve student detail after checkout has been performed.
        """
        student = self.student_repo.get_full_student(db, student_id)
        if not student:
            raise ValidationException("Student not found")
        return StudentDetail.model_validate(student)