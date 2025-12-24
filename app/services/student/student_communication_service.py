# app/services/student/student_communication_service.py
"""
Student Communication Service

Provides convenience methods for sending notifications to students and their guardians.
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.workflows import NotificationWorkflowService
from app.repositories.student import StudentRepository
from app.schemas.student import StudentContactInfo
from app.core.exceptions import ValidationException


class StudentCommunicationService:
    """
    High-level service that wraps NotificationWorkflowService
    to send domain-specific messages to students and guardians.
    """

    def __init__(
        self,
        notification_workflow: NotificationWorkflowService,
        student_repo: StudentRepository,
    ) -> None:
        self.notification_workflow = notification_workflow
        self.student_repo = student_repo

    def get_contact_info(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentContactInfo:
        student = self.student_repo.get_student_with_contacts(db, student_id)
        if not student:
            raise ValidationException("Student not found")
        return StudentContactInfo.model_validate(student)

    def send_general_notice_to_student(
        self,
        db: Session,
        student_id: UUID,
        template_code: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send a general informational message to the student via the
        NotificationWorkflowService.
        """
        contact = self.get_contact_info(db, student_id)
        if not contact.user_id:
            raise ValidationException("Student is missing linked user account")

        self.notification_workflow._create_and_queue_notification(  # type: ignore
            db=db,
            user_id=contact.user_id,
            template_code=template_code,
            hostel_id=contact.hostel_id,
            variables=variables or {},
        )

    def send_notice_to_guardian(
        self,
        db: Session,
        student_id: UUID,
        template_code: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send a notice to the primary guardian (if email/phone exists).
        """
        contact = self.get_contact_info(db, student_id)
        if not contact.guardian_email and not contact.guardian_phone:
            return  # nothing to send

        # Here you could call channel-specific flows; as a simplification we treat
        # guardian email as a "userless" target and rely on your notification layer
        # to support external recipients (or you might resolve them to a User).
        # This stub simply demonstrates the orchestration point.
        self.notification_workflow._create_and_queue_notification(  # type: ignore
            db=db,
            user_id=contact.user_id,  # fallback to student user for now
            template_code=template_code,
            hostel_id=contact.hostel_id,
            variables=variables or {},
        )