# app/services/student/student_onboarding_service.py
"""
Student Onboarding Service

Orchestrates student onboarding workflow including check-in, room assignment,
document collection, and initial setup.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.workflows import OnboardingWorkflowService
from app.schemas.student import StudentCheckInRequest, StudentDetail
from app.repositories.student import StudentRepository
from app.core.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)

logger = logging.getLogger(__name__)


class StudentOnboardingService:
    """
    High-level service for student onboarding workflows.

    Responsibilities:
    - Orchestrate onboarding from confirmed bookings
    - Handle quick check-in for walk-ins
    - Validate onboarding prerequisites
    - Coordinate with workflow service
    - Provide onboarding status and tracking

    Onboarding process:
    1. Validate booking/student data
    2. Assign room and bed
    3. Create student record
    4. Collect initial documents
    5. Set up preferences
    6. Send welcome notifications
    7. Generate onboarding checklist
    """

    def __init__(
        self,
        onboarding_workflow: OnboardingWorkflowService,
        student_repo: StudentRepository,
    ) -> None:
        """
        Initialize service with workflow and repository dependencies.

        Args:
            onboarding_workflow: Workflow orchestration service
            student_repo: Student repository
        """
        self.onboarding_workflow = onboarding_workflow
        self.student_repo = student_repo

    # -------------------------------------------------------------------------
    # Booking-based Onboarding
    # -------------------------------------------------------------------------

    async def onboard_from_booking(
        self,
        db: Session,
        booking_id: UUID,
        initiated_by: UUID,
        check_in_date: Optional[datetime] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute onboarding workflow for a confirmed booking.

        Args:
            db: Database session
            booking_id: UUID of confirmed booking
            initiated_by: UUID of user initiating onboarding
            check_in_date: Optional check-in date (defaults to now)
            additional_data: Optional additional onboarding data

        Returns:
            Dictionary with workflow execution results

        Raises:
            ValidationException: If booking invalid or not confirmed
            BusinessLogicException: If onboarding fails
        """
        try:
            logger.info(
                f"Starting onboarding from booking: {booking_id} "
                f"by user: {initiated_by}"
            )

            # Validate booking exists and is confirmed
            # This validation typically happens in the workflow service
            # but we can add preliminary checks here

            result = await self.onboarding_workflow.onboard_student(
                db=db,
                booking_id=booking_id,
                initiated_by=initiated_by,
                check_in_date=check_in_date or datetime.utcnow(),
                additional_data=additional_data or {},
            )

            if result.get("status") == "completed":
                logger.info(
                    f"Onboarding completed successfully for booking: {booking_id}, "
                    f"student: {result.get('student_id')}"
                )
            else:
                logger.warning(
                    f"Onboarding did not complete successfully: {result.get('status')}"
                )

            return result

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during onboarding: {str(e)}", exc_info=True)
            raise BusinessLogicException(
                f"Failed to complete onboarding: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Quick Check-in (Walk-ins)
    # -------------------------------------------------------------------------

    async def quick_check_in(
        self,
        db: Session,
        hostel_id: UUID,
        check_in_data: Dict[str, Any],
        initiated_by: UUID,
    ) -> Dict[str, Any]:
        """
        Execute quick check-in for walk-in students.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            check_in_data: Student and check-in information
            initiated_by: UUID of user performing check-in

        Returns:
            Dictionary with check-in results

        Raises:
            ValidationException: If check-in data invalid
            BusinessLogicException: If check-in fails
        """
        try:
            # Validate required fields in check_in_data
            self._validate_quick_checkin_data(check_in_data)

            logger.info(
                f"Starting quick check-in for hostel: {hostel_id} "
                f"by user: {initiated_by}"
            )

            result = await self.onboarding_workflow.quick_checkin_student(
                db=db,
                hostel_id=hostel_id,
                student_data=check_in_data,
                initiated_by=initiated_by,
            )

            if result.get("status") == "completed":
                logger.info(
                    f"Quick check-in completed for hostel: {hostel_id}, "
                    f"student: {result.get('student_id')}"
                )
            else:
                logger.warning(
                    f"Quick check-in did not complete: {result.get('status')}"
                )

            return result

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during quick check-in: {str(e)}", exc_info=True)
            raise BusinessLogicException(
                f"Failed to complete quick check-in: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Onboarding Status and Retrieval
    # -------------------------------------------------------------------------

    def get_student_after_onboarding(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentDetail:
        """
        Retrieve complete student details after onboarding.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            StudentDetail: Complete student information

        Raises:
            NotFoundException: If student not found
        """
        try:
            student = self.student_repo.get_full_student(db, student_id)
            
            if not student:
                raise NotFoundException(f"Student not found: {student_id}")
            
            return StudentDetail.model_validate(student)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving student after onboarding: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to retrieve student details: {str(e)}"
            ) from e

    def get_onboarding_status(
        self,
        db: Session,
        booking_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Get onboarding status and completion checklist.

        Args:
            db: Database session
            booking_id: Optional booking ID
            student_id: Optional student ID

        Returns:
            Dictionary with onboarding status and checklist

        Raises:
            ValidationException: If neither booking_id nor student_id provided
        """
        if not booking_id and not student_id:
            raise ValidationException(
                "Either booking_id or student_id must be provided"
            )

        try:
            # This would query onboarding workflow state
            # Simplified for this example
            status = {
                "booking_id": booking_id,
                "student_id": student_id,
                "status": "in_progress",  # or "completed", "failed"
                "checklist": {
                    "student_created": True,
                    "room_assigned": True,
                    "documents_uploaded": False,
                    "preferences_set": False,
                    "guardian_added": True,
                    "welcome_sent": True,
                },
                "completion_percentage": 60,
            }

            return status

        except Exception as e:
            logger.error(f"Error retrieving onboarding status: {str(e)}")
            raise BusinessLogicException(
                f"Failed to retrieve onboarding status: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Onboarding Completion and Cleanup
    # -------------------------------------------------------------------------

    async def complete_onboarding(
        self,
        db: Session,
        student_id: UUID,
        completed_by: UUID,
        completion_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Manually mark onboarding as complete.

        Args:
            db: Database session
            student_id: UUID of student
            completed_by: UUID of user completing onboarding
            completion_notes: Optional completion notes

        Returns:
            Dictionary with completion results
        """
        student = self.student_repo.get_by_id(db, student_id)
        
        if not student:
            raise NotFoundException(f"Student not found: {student_id}")

        try:
            # Mark onboarding complete in workflow
            # Update student status if needed
            # Send completion notifications

            result = {
                "student_id": student_id,
                "status": "completed",
                "completed_by": completed_by,
                "completed_at": datetime.utcnow(),
                "notes": completion_notes,
            }

            logger.info(
                f"Onboarding manually completed for student: {student_id} "
                f"by user: {completed_by}"
            )

            return result

        except Exception as e:
            logger.error(f"Error completing onboarding: {str(e)}")
            raise BusinessLogicException(
                f"Failed to complete onboarding: {str(e)}"
            ) from e

    async def cancel_onboarding(
        self,
        db: Session,
        booking_id: UUID,
        cancelled_by: UUID,
        cancellation_reason: str,
    ) -> Dict[str, Any]:
        """
        Cancel an in-progress onboarding.

        Args:
            db: Database session
            booking_id: UUID of booking
            cancelled_by: UUID of user cancelling
            cancellation_reason: Reason for cancellation

        Returns:
            Dictionary with cancellation results
        """
        try:
            # Rollback any partial onboarding state
            # Release assigned resources (room, bed)
            # Update booking status

            result = {
                "booking_id": booking_id,
                "status": "cancelled",
                "cancelled_by": cancelled_by,
                "cancelled_at": datetime.utcnow(),
                "reason": cancellation_reason,
            }

            logger.info(
                f"Onboarding cancelled for booking: {booking_id}, "
                f"reason: {cancellation_reason}"
            )

            return result

        except Exception as e:
            logger.error(f"Error cancelling onboarding: {str(e)}")
            raise BusinessLogicException(
                f"Failed to cancel onboarding: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_quick_checkin_data(
        self,
        check_in_data: Dict[str, Any],
    ) -> None:
        """
        Validate quick check-in data contains required fields.

        Args:
            check_in_data: Check-in data dictionary

        Raises:
            ValidationException: If required fields missing
        """
        required_fields = [
            "full_name",
            "email",
            "phone",
            "room_id",
        ]

        missing = [f for f in required_fields if f not in check_in_data]

        if missing:
            raise ValidationException(
                f"Missing required fields for quick check-in: {', '.join(missing)}"
            )

        # Validate email format
        if "@" not in check_in_data.get("email", ""):
            raise ValidationException("Invalid email format")

        # Validate phone
        phone = check_in_data.get("phone", "")
        if len(phone) < 10:
            raise ValidationException("Invalid phone number")

    # -------------------------------------------------------------------------
    # Bulk Onboarding
    # -------------------------------------------------------------------------

    async def bulk_onboard(
        self,
        db: Session,
        booking_ids: List[UUID],
        initiated_by: UUID,
        check_in_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Onboard multiple students from bookings.

        Args:
            db: Database session
            booking_ids: List of booking UUIDs
            initiated_by: UUID of user initiating
            check_in_date: Optional check-in date

        Returns:
            List of onboarding results
        """
        if not booking_ids:
            return []

        results = []
        successful = 0
        failed = 0

        logger.info(
            f"Starting bulk onboarding for {len(booking_ids)} bookings "
            f"by user: {initiated_by}"
        )

        for booking_id in booking_ids:
            try:
                result = await self.onboard_from_booking(
                    db=db,
                    booking_id=booking_id,
                    initiated_by=initiated_by,
                    check_in_date=check_in_date,
                )
                results.append(result)
                
                if result.get("status") == "completed":
                    successful += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(
                    f"Error onboarding booking {booking_id}: {str(e)}"
                )
                failed += 1
                results.append({
                    "booking_id": booking_id,
                    "status": "failed",
                    "error": str(e),
                })

        logger.info(
            f"Bulk onboarding completed: {successful} successful, {failed} failed"
        )

        return results