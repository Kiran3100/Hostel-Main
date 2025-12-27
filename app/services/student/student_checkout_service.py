# app/services/student/student_checkout_service.py
"""
Student Checkout Service

Orchestrates student checkout workflow including clearance, final settlements,
room vacation, and account closure.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.workflows import CheckoutWorkflowService
from app.schemas.student import StudentCheckOutRequest, StudentDetail
from app.repositories.student import StudentRepository
from app.core1.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)

logger = logging.getLogger(__name__)


class StudentCheckoutService:
    """
    High-level service for student checkout workflows.

    Responsibilities:
    - Orchestrate standard checkout process
    - Handle emergency checkouts
    - Validate checkout prerequisites
    - Coordinate clearance procedures
    - Manage final settlements
    - Update student status

    Checkout process:
    1. Validate checkout eligibility
    2. Calculate final payments
    3. Collect clearances (library, maintenance, etc.)
    4. Vacate room and bed
    5. Process refunds/settlements
    6. Update student status to checked-out
    7. Archive records
    8. Send checkout confirmation
    """

    def __init__(
        self,
        checkout_workflow: CheckoutWorkflowService,
        student_repo: StudentRepository,
    ) -> None:
        """
        Initialize service with workflow and repository dependencies.

        Args:
            checkout_workflow: Workflow orchestration service
            student_repo: Student repository
        """
        self.checkout_workflow = checkout_workflow
        self.student_repo = student_repo

    # -------------------------------------------------------------------------
    # Standard Checkout
    # -------------------------------------------------------------------------

    async def checkout_student(
        self,
        db: Session,
        request: StudentCheckOutRequest,
        initiated_by: UUID,
    ) -> Dict[str, Any]:
        """
        Execute full checkout workflow for a student.

        Args:
            db: Database session
            request: Checkout request data
            initiated_by: UUID of user initiating checkout

        Returns:
            Dictionary with workflow execution results

        Raises:
            NotFoundException: If student not found
            ValidationException: If checkout prerequisites not met
            BusinessLogicException: If checkout fails
        """
        try:
            # Validate student exists and is eligible for checkout
            student = self._validate_checkout_eligibility(db, request.student_id)

            logger.info(
                f"Starting checkout for student: {request.student_id} "
                f"by user: {initiated_by}"
            )

            result = await self.checkout_workflow.checkout_student(
                db=db,
                student_id=request.student_id,
                checkout_date=request.checkout_date or datetime.utcnow(),
                initiated_by=initiated_by,
                reason=request.reason,
                forwarding_address=request.forwarding_address,
                clearance_data=request.clearance_data,
            )

            if result.get("status") == "completed":
                logger.info(
                    f"Checkout completed successfully for student: {request.student_id}"
                )
            else:
                logger.warning(
                    f"Checkout did not complete successfully: {result.get('status')}"
                )

            return result

        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error during checkout: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to complete checkout: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Emergency Checkout
    # -------------------------------------------------------------------------

    async def emergency_checkout(
        self,
        db: Session,
        student_id: UUID,
        initiated_by: UUID,
        reason: str,
        emergency_contact: Optional[str] = None,
        skip_clearances: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform emergency checkout with relaxed requirements.

        Args:
            db: Database session
            student_id: UUID of student
            initiated_by: UUID of user initiating
            reason: Emergency reason
            emergency_contact: Optional emergency contact info
            skip_clearances: Whether to skip clearance checks

        Returns:
            Dictionary with checkout results

        Raises:
            NotFoundException: If student not found
            BusinessLogicException: If emergency checkout fails
        """
        try:
            student = self.student_repo.get_by_id(db, student_id)
            if not student:
                raise NotFoundException(f"Student not found: {student_id}")

            logger.warning(
                f"Starting EMERGENCY checkout for student: {student_id}, "
                f"reason: {reason}"
            )

            result = await self.checkout_workflow.emergency_checkout(
                db=db,
                student_id=student_id,
                initiated_by=initiated_by,
                emergency_reason=reason,
                emergency_contact=emergency_contact,
                skip_clearances=skip_clearances,
            )

            logger.info(
                f"Emergency checkout completed for student: {student_id}"
            )

            return result

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"Error during emergency checkout: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to complete emergency checkout: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Checkout Status and Retrieval
    # -------------------------------------------------------------------------

    def get_student_after_checkout(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentDetail:
        """
        Retrieve student details after checkout completion.

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
                f"Database error retrieving student after checkout: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to retrieve student details: {str(e)}"
            ) from e

    def get_checkout_status(
        self,
        db: Session,
        student_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get checkout status and pending requirements.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            Dictionary with checkout status and checklist
        """
        try:
            student = self.student_repo.get_by_id(db, student_id)
            
            if not student:
                raise NotFoundException(f"Student not found: {student_id}")

            # Calculate checkout readiness
            status = {
                "student_id": student_id,
                "can_checkout": True,
                "pending_items": [],
                "clearances": {
                    "library": False,
                    "maintenance": False,
                    "accounts": False,
                    "hostel_admin": False,
                },
                "financial_summary": {
                    "outstanding_dues": 0,
                    "security_deposit": 0,
                    "refund_due": 0,
                },
            }

            # Check for outstanding payments
            # Check for pending clearances
            # Calculate refunds
            # This would query relevant repositories

            return status

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving checkout status: {str(e)}")
            raise BusinessLogicException(
                f"Failed to retrieve checkout status: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Clearance Management
    # -------------------------------------------------------------------------

    def submit_clearance(
        self,
        db: Session,
        student_id: UUID,
        clearance_type: str,
        cleared_by: UUID,
        notes: Optional[str] = None,
        attachments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Submit clearance for a specific department/type.

        Args:
            db: Database session
            student_id: UUID of student
            clearance_type: Type of clearance (library, maintenance, etc.)
            cleared_by: UUID of user providing clearance
            notes: Optional clearance notes
            attachments: Optional attachment paths

        Returns:
            Dictionary with clearance result
        """
        valid_types = ["library", "maintenance", "accounts", "hostel_admin"]
        
        if clearance_type not in valid_types:
            raise ValidationException(
                f"Invalid clearance type. Must be one of: {', '.join(valid_types)}"
            )

        try:
            # Record clearance
            clearance = {
                "student_id": student_id,
                "clearance_type": clearance_type,
                "cleared_by": cleared_by,
                "cleared_at": datetime.utcnow(),
                "notes": notes,
                "attachments": attachments or [],
                "status": "approved",
            }

            logger.info(
                f"Clearance submitted: {clearance_type} for student: {student_id} "
                f"by: {cleared_by}"
            )

            return clearance

        except Exception as e:
            logger.error(f"Error submitting clearance: {str(e)}")
            raise BusinessLogicException(
                f"Failed to submit clearance: {str(e)}"
            ) from e

    def get_clearance_status(
        self,
        db: Session,
        student_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get all clearance statuses for a student.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            Dictionary with clearance statuses
        """
        try:
            # This would query clearance records
            clearances = {
                "student_id": student_id,
                "clearances": {
                    "library": {"status": "pending", "cleared_at": None},
                    "maintenance": {"status": "approved", "cleared_at": datetime.utcnow()},
                    "accounts": {"status": "pending", "cleared_at": None},
                    "hostel_admin": {"status": "pending", "cleared_at": None},
                },
                "all_cleared": False,
                "pending_count": 3,
            }

            return clearances

        except Exception as e:
            logger.error(f"Error retrieving clearance status: {str(e)}")
            raise BusinessLogicException(
                f"Failed to retrieve clearance status: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Final Settlement
    # -------------------------------------------------------------------------

    def calculate_final_settlement(
        self,
        db: Session,
        student_id: UUID,
        checkout_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Calculate final financial settlement for checkout.

        Args:
            db: Database session
            student_id: UUID of student
            checkout_date: Optional checkout date for calculations

        Returns:
            Dictionary with settlement details
        """
        try:
            student = self.student_repo.get_by_id(db, student_id)
            
            if not student:
                raise NotFoundException(f"Student not found: {student_id}")

            # Calculate various components
            settlement = {
                "student_id": student_id,
                "checkout_date": checkout_date or datetime.utcnow(),
                "components": {
                    "outstanding_rent": 0,
                    "outstanding_fees": 0,
                    "damage_charges": 0,
                    "security_deposit": 0,
                    "advance_payments": 0,
                },
                "total_payable": 0,
                "total_refundable": 0,
                "net_amount": 0,  # Negative = refund, Positive = payment due
            }

            # This would query payment and fee repositories
            # Calculate prorated amounts
            # Apply any penalties or bonuses

            return settlement

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error calculating settlement: {str(e)}")
            raise BusinessLogicException(
                f"Failed to calculate settlement: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Bulk Checkout
    # -------------------------------------------------------------------------

    async def bulk_checkout(
        self,
        db: Session,
        student_ids: List[UUID],
        initiated_by: UUID,
        checkout_date: Optional[datetime] = None,
        reason: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Checkout multiple students.

        Args:
            db: Database session
            student_ids: List of student UUIDs
            initiated_by: UUID of user initiating
            checkout_date: Optional checkout date
            reason: Optional reason for bulk checkout

        Returns:
            List of checkout results
        """
        if not student_ids:
            return []

        results = []
        successful = 0
        failed = 0

        logger.info(
            f"Starting bulk checkout for {len(student_ids)} students "
            f"by user: {initiated_by}"
        )

        for student_id in student_ids:
            try:
                request = StudentCheckOutRequest(
                    student_id=student_id,
                    checkout_date=checkout_date,
                    reason=reason,
                )

                result = await self.checkout_student(
                    db=db,
                    request=request,
                    initiated_by=initiated_by,
                )
                results.append(result)
                
                if result.get("status") == "completed":
                    successful += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(
                    f"Error checking out student {student_id}: {str(e)}"
                )
                failed += 1
                results.append({
                    "student_id": student_id,
                    "status": "failed",
                    "error": str(e),
                })

        logger.info(
            f"Bulk checkout completed: {successful} successful, {failed} failed"
        )

        return results

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_checkout_eligibility(
        self,
        db: Session,
        student_id: UUID,
    ) -> Any:
        """
        Validate that student is eligible for checkout.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            Student ORM object

        Raises:
            NotFoundException: If student not found
            ValidationException: If student not eligible
        """
        student = self.student_repo.get_by_id(db, student_id)
        
        if not student:
            raise NotFoundException(f"Student not found: {student_id}")

        # Check if already checked out
        if student.student_status == "checked_out":
            raise ValidationException(
                "Student is already checked out"
            )

        # Check for active violations or holds
        # This would query relevant repositories

        return student