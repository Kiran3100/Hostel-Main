# app/services/payment/payment_schedule_service.py
"""
Payment Schedule Service

Manages recurring payment schedules:
- Create/update/suspend schedules
- Generate scheduled payments automatically
- Bulk schedule creation for multiple students
- Handle schedule lifecycle and exceptions
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.payment import (
    PaymentScheduleRepository,
    PaymentRepository,
)
from app.schemas.payment import (
    PaymentSchedule,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleGeneration,
    ScheduledPaymentGenerated,
    BulkScheduleCreate,
    ScheduleSuspension,
    PaymentResponse,
)
from app.core1.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)
from app.core1.logging import LoggingContext, logger


class PaymentScheduleService:
    """
    High-level service for recurring payment schedules.

    Responsibilities:
    - Create and manage payment schedules
    - Generate payments from schedules automatically
    - Handle schedule suspensions and modifications
    - Bulk schedule operations
    - Validate schedule configurations

    Delegates:
    - Schedule persistence to PaymentScheduleRepository
    - Payment creation to PaymentRepository
    """

    __slots__ = ("schedule_repo", "payment_repo")

    # Schedule frequency options
    VALID_FREQUENCIES = {
        "daily",
        "weekly",
        "biweekly",
        "monthly",
        "quarterly",
        "semi_annual",
        "annual",
    }

    # Maximum schedules per student
    MAX_SCHEDULES_PER_STUDENT = 10

    def __init__(
        self,
        schedule_repo: PaymentScheduleRepository,
        payment_repo: PaymentRepository,
    ) -> None:
        self.schedule_repo = schedule_repo
        self.payment_repo = payment_repo

    # -------------------------------------------------------------------------
    # CRUD operations
    # -------------------------------------------------------------------------

    def create_schedule(
        self,
        db: Session,
        request: ScheduleCreate,
        created_by: Optional[UUID] = None,
    ) -> PaymentSchedule:
        """
        Create a new payment schedule.

        Args:
            db: Database session
            request: Schedule creation details
            created_by: UUID of user creating the schedule

        Returns:
            PaymentSchedule with created schedule

        Raises:
            ValidationException: If schedule configuration is invalid
            BusinessLogicException: If business rules are violated
        """
        self._validate_schedule_create(db, request)

        payload = request.model_dump(exclude_none=True)
        if created_by:
            payload["created_by"] = created_by

        # Calculate next due date if not provided
        if not payload.get("next_due_date"):
            payload["next_due_date"] = self._calculate_next_due_date(
                start_date=request.start_date,
                first_due_date=request.first_due_date,
                frequency=request.frequency,
            )

        with LoggingContext(
            student_id=str(request.student_id),
            fee_type=request.fee_type,
        ):
            try:
                obj = self.schedule_repo.create_schedule(db, data=payload)

                logger.info(
                    f"Payment schedule created: {obj.id}",
                    extra={
                        "schedule_id": str(obj.id),
                        "student_id": str(request.student_id),
                        "amount": float(request.amount),
                        "frequency": request.frequency,
                    },
                )

                return PaymentSchedule.model_validate(obj)

            except Exception as e:
                logger.error(f"Failed to create payment schedule: {str(e)}")
                raise BusinessLogicException(
                    f"Failed to create payment schedule: {str(e)}"
                )

    def _validate_schedule_create(
        self,
        db: Session,
        request: ScheduleCreate,
    ) -> None:
        """Validate schedule creation request."""
        # Validate amount
        if request.amount <= 0:
            raise ValidationException("Schedule amount must be positive")

        # Validate frequency
        if request.frequency not in self.VALID_FREQUENCIES:
            raise ValidationException(
                f"Invalid frequency: {request.frequency}. "
                f"Must be one of {self.VALID_FREQUENCIES}"
            )

        # Validate dates
        if request.start_date >= request.end_date:
            raise ValidationException("Start date must be before end date")

        if request.first_due_date < request.start_date:
            raise ValidationException("First due date cannot be before start date")

        # Check max schedules per student
        existing_count = self.schedule_repo.count_active_schedules_for_student(
            db, request.student_id
        )
        if existing_count >= self.MAX_SCHEDULES_PER_STUDENT:
            raise BusinessLogicException(
                f"Student already has {existing_count} active schedules. "
                f"Maximum allowed: {self.MAX_SCHEDULES_PER_STUDENT}"
            )

        # Validate no overlapping schedules for same fee type
        if self._has_overlapping_schedule(db, request):
            raise BusinessLogicException(
                f"An active schedule already exists for {request.fee_type} "
                f"with overlapping dates"
            )

    def _has_overlapping_schedule(
        self,
        db: Session,
        request: ScheduleCreate,
    ) -> bool:
        """Check if there's an overlapping schedule for the same fee type."""
        return self.schedule_repo.has_overlapping_schedule(
            db=db,
            student_id=request.student_id,
            fee_type=request.fee_type,
            start_date=request.start_date,
            end_date=request.end_date,
        )

    def _calculate_next_due_date(
        self,
        start_date: date,
        first_due_date: date,
        frequency: str,
    ) -> date:
        """Calculate the next due date based on frequency."""
        # If first due date is in the future, use it
        today = date.today()
        if first_due_date > today:
            return first_due_date

        # Otherwise, calculate based on frequency from today
        return self._add_frequency_to_date(today, frequency)

    def _add_frequency_to_date(self, base_date: date, frequency: str) -> date:
        """Add frequency interval to a date."""
        if frequency == "daily":
            return base_date + timedelta(days=1)
        elif frequency == "weekly":
            return base_date + timedelta(weeks=1)
        elif frequency == "biweekly":
            return base_date + timedelta(weeks=2)
        elif frequency == "monthly":
            return self._add_months(base_date, 1)
        elif frequency == "quarterly":
            return self._add_months(base_date, 3)
        elif frequency == "semi_annual":
            return self._add_months(base_date, 6)
        elif frequency == "annual":
            return self._add_months(base_date, 12)
        else:
            return base_date + timedelta(days=30)  # Default to monthly

    def _add_months(self, base_date: date, months: int) -> date:
        """Add months to a date, handling month-end dates properly."""
        month = base_date.month - 1 + months
        year = base_date.year + month // 12
        month = month % 12 + 1
        day = min(base_date.day, [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
        return date(year, month, day)

    def update_schedule(
        self,
        db: Session,
        schedule_id: UUID,
        request: ScheduleUpdate,
        updated_by: Optional[UUID] = None,
    ) -> PaymentSchedule:
        """
        Update an existing payment schedule.

        Args:
            db: Database session
            schedule_id: Schedule UUID
            request: Update details
            updated_by: UUID of user updating the schedule

        Returns:
            PaymentSchedule with updated schedule

        Raises:
            NotFoundException: If schedule not found
            ValidationException: If update is invalid
        """
        schedule = self.schedule_repo.get_by_id(db, schedule_id)
        if not schedule:
            raise NotFoundException(f"Payment schedule not found: {schedule_id}")

        self._validate_schedule_update(schedule, request)

        payload = request.model_dump(exclude_none=True)
        if updated_by:
            payload["updated_by"] = updated_by

        with LoggingContext(schedule_id=str(schedule_id)):
            updated = self.schedule_repo.update_schedule(
                db,
                schedule,
                data=payload,
            )

            logger.info(
                f"Payment schedule updated: {schedule_id}",
                extra={"schedule_id": str(schedule_id)},
            )

            return PaymentSchedule.model_validate(updated)

    def _validate_schedule_update(
        self,
        schedule: Any,
        request: ScheduleUpdate,
    ) -> None:
        """Validate schedule update request."""
        if not schedule.is_active:
            raise BusinessLogicException("Cannot update inactive schedule")

        if request.amount is not None and request.amount <= 0:
            raise ValidationException("Schedule amount must be positive")

        if request.end_date is not None:
            if request.end_date <= schedule.start_date:
                raise ValidationException("End date must be after start date")

    def get_schedule(
        self,
        db: Session,
        schedule_id: UUID,
    ) -> PaymentSchedule:
        """
        Retrieve a payment schedule by ID.

        Args:
            db: Database session
            schedule_id: Schedule UUID

        Returns:
            PaymentSchedule details

        Raises:
            NotFoundException: If schedule not found
        """
        obj = self.schedule_repo.get_by_id(db, schedule_id)
        if not obj:
            raise NotFoundException(f"Payment schedule not found: {schedule_id}")

        return PaymentSchedule.model_validate(obj)

    def list_schedules_for_student(
        self,
        db: Session,
        student_id: UUID,
        active_only: bool = True,
    ) -> List[PaymentSchedule]:
        """
        List payment schedules for a student.

        Args:
            db: Database session
            student_id: Student UUID
            active_only: Return only active schedules

        Returns:
            List of PaymentSchedule objects
        """
        objs = self.schedule_repo.get_by_student_id(
            db,
            student_id,
            active_only=active_only,
        )
        return [PaymentSchedule.model_validate(o) for o in objs]

    def list_schedules_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        active_only: bool = True,
    ) -> List[PaymentSchedule]:
        """
        List payment schedules for a hostel.

        Args:
            db: Database session
            hostel_id: Hostel UUID
            active_only: Return only active schedules

        Returns:
            List of PaymentSchedule objects
        """
        objs = self.schedule_repo.get_by_hostel_id(
            db,
            hostel_id,
            active_only=active_only,
        )
        return [PaymentSchedule.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Suspension & activation
    # -------------------------------------------------------------------------

    def suspend_schedule(
        self,
        db: Session,
        request: ScheduleSuspension,
        suspended_by: Optional[UUID] = None,
    ) -> PaymentSchedule:
        """
        Suspend a payment schedule temporarily.

        Args:
            db: Database session
            request: Suspension details
            suspended_by: UUID of user suspending the schedule

        Returns:
            PaymentSchedule with suspended schedule

        Raises:
            NotFoundException: If schedule not found
            BusinessLogicException: If schedule cannot be suspended
        """
        schedule = self.schedule_repo.get_by_id(db, request.schedule_id)
        if not schedule:
            raise NotFoundException(
                f"Payment schedule not found: {request.schedule_id}"
            )

        if not schedule.is_active:
            raise BusinessLogicException("Schedule is already inactive")

        if schedule.is_suspended:
            raise BusinessLogicException("Schedule is already suspended")

        with LoggingContext(schedule_id=str(request.schedule_id)):
            updated = self.schedule_repo.suspend_schedule(
                db=db,
                schedule=schedule,
                reason=request.reason,
                suspend_from=request.suspend_from,
                suspend_to=request.suspend_to,
                skip_dues_during_suspension=request.skip_dues_during_suspension,
            )

            logger.info(
                f"Payment schedule suspended: {request.schedule_id}",
                extra={
                    "schedule_id": str(request.schedule_id),
                    "suspend_from": request.suspend_from.isoformat() if request.suspend_from else None,
                    "suspend_to": request.suspend_to.isoformat() if request.suspend_to else None,
                },
            )

            return PaymentSchedule.model_validate(updated)

    def resume_schedule(
        self,
        db: Session,
        schedule_id: UUID,
        resumed_by: Optional[UUID] = None,
    ) -> PaymentSchedule:
        """
        Resume a suspended payment schedule.

        Args:
            db: Database session
            schedule_id: Schedule UUID
            resumed_by: UUID of user resuming the schedule

        Returns:
            PaymentSchedule with resumed schedule

        Raises:
            NotFoundException: If schedule not found
            BusinessLogicException: If schedule is not suspended
        """
        schedule = self.schedule_repo.get_by_id(db, schedule_id)
        if not schedule:
            raise NotFoundException(f"Payment schedule not found: {schedule_id}")

        if not schedule.is_suspended:
            raise BusinessLogicException("Schedule is not suspended")

        with LoggingContext(schedule_id=str(schedule_id)):
            updated = self.schedule_repo.resume_schedule(
                db=db,
                schedule=schedule,
                resumed_by=resumed_by,
            )

            logger.info(
                f"Payment schedule resumed: {schedule_id}",
                extra={"schedule_id": str(schedule_id)},
            )

            return PaymentSchedule.model_validate(updated)

    def deactivate_schedule(
        self,
        db: Session,
        schedule_id: UUID,
        reason: str,
        deactivated_by: Optional[UUID] = None,
    ) -> PaymentSchedule:
        """
        Permanently deactivate a payment schedule.

        Args:
            db: Database session
            schedule_id: Schedule UUID
            reason: Deactivation reason
            deactivated_by: UUID of user deactivating the schedule

        Returns:
            PaymentSchedule with deactivated schedule

        Raises:
            NotFoundException: If schedule not found
        """
        schedule = self.schedule_repo.get_by_id(db, schedule_id)
        if not schedule:
            raise NotFoundException(f"Payment schedule not found: {schedule_id}")

        with LoggingContext(schedule_id=str(schedule_id)):
            updated = self.schedule_repo.deactivate_schedule(
                db=db,
                schedule=schedule,
                reason=reason,
                deactivated_by=deactivated_by,
            )

            logger.info(
                f"Payment schedule deactivated: {schedule_id}",
                extra={
                    "schedule_id": str(schedule_id),
                    "reason": reason,
                },
            )

            return PaymentSchedule.model_validate(updated)

    # -------------------------------------------------------------------------
    # Payment generation
    # -------------------------------------------------------------------------

    def generate_payments(
        self,
        db: Session,
        request: ScheduleGeneration,
    ) -> ScheduledPaymentGenerated:
        """
        Generate payments for a schedule within a period.

        This creates actual Payment records based on the schedule.

        Args:
            db: Database session
            request: Generation parameters

        Returns:
            ScheduledPaymentGenerated with generation results

        Raises:
            NotFoundException: If schedule not found
            BusinessLogicException: If generation fails
        """
        schedule = self.schedule_repo.get_by_id(db, request.schedule_id)
        if not schedule:
            raise NotFoundException(
                f"Payment schedule not found: {request.schedule_id}"
            )

        if not schedule.is_active:
            raise BusinessLogicException("Cannot generate payments from inactive schedule")

        with LoggingContext(schedule_id=str(request.schedule_id)):
            try:
                result = self.schedule_repo.generate_payments(
                    db=db,
                    schedule=schedule,
                    from_date=request.from_date,
                    to_date=request.to_date,
                    skip_if_already_paid=request.skip_if_already_paid,
                    send_notifications=request.send_notifications,
                )

                logger.info(
                    f"Payments generated from schedule: {request.schedule_id}",
                    extra={
                        "schedule_id": str(request.schedule_id),
                        "generated_count": result.get("generated_count", 0),
                        "skipped_count": result.get("skipped_count", 0),
                    },
                )

                return ScheduledPaymentGenerated.model_validate(result)

            except Exception as e:
                logger.error(
                    f"Failed to generate payments from schedule: {str(e)}",
                    extra={"schedule_id": str(request.schedule_id)},
                )
                raise BusinessLogicException(
                    f"Failed to generate payments: {str(e)}"
                )

    def generate_payments_for_all_due(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
        as_of_date: Optional[date] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate all due payments across schedules.

        This is typically run as a scheduled job.

        Args:
            db: Database session
            hostel_id: Optional hostel filter
            as_of_date: Date to check for due payments (default: today)
            dry_run: If True, return what would be generated without creating

        Returns:
            Dictionary with generation statistics
        """
        as_of = as_of_date or date.today()

        # Get all active schedules with due payments
        due_schedules = self.schedule_repo.get_schedules_with_due_payments(
            db=db,
            hostel_id=hostel_id,
            as_of_date=as_of,
        )

        stats = {
            "schedules_processed": 0,
            "payments_generated": 0,
            "payments_skipped": 0,
            "errors": [],
        }

        for schedule in due_schedules:
            try:
                if dry_run:
                    # Just count what would be generated
                    count = self._count_due_payments_for_schedule(
                        db, schedule, as_of
                    )
                    stats["payments_generated"] += count
                else:
                    result = self.schedule_repo.generate_payments(
                        db=db,
                        schedule=schedule,
                        from_date=schedule.next_due_date,
                        to_date=as_of,
                        skip_if_already_paid=True,
                        send_notifications=True,
                    )
                    stats["payments_generated"] += result.get("generated_count", 0)
                    stats["payments_skipped"] += result.get("skipped_count", 0)

                stats["schedules_processed"] += 1

            except Exception as e:
                logger.error(
                    f"Failed to generate payments for schedule {schedule.id}: {str(e)}"
                )
                stats["errors"].append({
                    "schedule_id": str(schedule.id),
                    "error": str(e),
                })

        logger.info(
            f"Batch payment generation completed: {stats['payments_generated']} generated, "
            f"{stats['payments_skipped']} skipped from {stats['schedules_processed']} schedules"
        )

        return stats

    def _count_due_payments_for_schedule(
        self,
        db: Session,
        schedule: Any,
        as_of_date: date,
    ) -> int:
        """Count how many payments would be generated for a schedule."""
        count = 0
        current_date = schedule.next_due_date

        while current_date <= as_of_date and current_date <= schedule.end_date:
            count += 1
            current_date = self._add_frequency_to_date(
                current_date, schedule.frequency
            )

        return count

    # -------------------------------------------------------------------------
    # Bulk operations
    # -------------------------------------------------------------------------

    def bulk_create_schedules(
        self,
        db: Session,
        request: BulkScheduleCreate,
        created_by: Optional[UUID] = None,
    ) -> List[PaymentSchedule]:
        """
        Create identical schedules for multiple students.

        Args:
            db: Database session
            request: Bulk creation parameters
            created_by: UUID of user creating schedules

        Returns:
            List of created PaymentSchedule objects

        Raises:
            ValidationException: If request is invalid
        """
        if not request.student_ids:
            raise ValidationException("No student IDs provided")

        if len(request.student_ids) > 100:
            raise ValidationException(
                "Cannot create more than 100 schedules at once"
            )

        with LoggingContext(
            hostel_id=str(request.hostel_id),
            student_count=len(request.student_ids),
        ):
            try:
                objs = self.schedule_repo.bulk_create_schedules(
                    db=db,
                    hostel_id=request.hostel_id,
                    student_ids=request.student_ids,
                    fee_type=request.fee_type,
                    amount=request.amount,
                    frequency=request.frequency,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    first_due_date=request.first_due_date,
                    created_by=created_by,
                )

                logger.info(
                    f"Bulk schedules created: {len(objs)} schedules",
                    extra={
                        "hostel_id": str(request.hostel_id),
                        "count": len(objs),
                    },
                )

                return [PaymentSchedule.model_validate(o) for o in objs]

            except Exception as e:
                logger.error(f"Failed to bulk create schedules: {str(e)}")
                raise BusinessLogicException(
                    f"Failed to bulk create schedules: {str(e)}"
                )

    def bulk_update_schedules(
        self,
        db: Session,
        schedule_ids: List[UUID],
        update_data: Dict[str, Any],
        updated_by: Optional[UUID] = None,
    ) -> List[PaymentSchedule]:
        """
        Update multiple schedules with the same data.

        Args:
            db: Database session
            schedule_ids: List of schedule UUIDs
            update_data: Data to update
            updated_by: UUID of user updating

        Returns:
            List of updated PaymentSchedule objects
        """
        if not schedule_ids:
            return []

        results = []
        for schedule_id in schedule_ids:
            try:
                schedule = self.schedule_repo.get_by_id(db, schedule_id)
                if schedule:
                    updated = self.schedule_repo.update_schedule(
                        db,
                        schedule,
                        data=update_data,
                    )
                    results.append(PaymentSchedule.model_validate(updated))
            except Exception as e:
                logger.warning(
                    f"Failed to update schedule {schedule_id}: {str(e)}",
                    extra={"schedule_id": str(schedule_id)},
                )

        logger.info(
            f"Bulk schedule update completed: {len(results)}/{len(schedule_ids)} updated"
        )

        return results

    # -------------------------------------------------------------------------
    # Utility methods
    # -------------------------------------------------------------------------

    def preview_schedule_payments(
        self,
        db: Session,
        schedule_id: UUID,
        months: int = 12,
    ) -> List[Dict[str, Any]]:
        """
        Preview upcoming payments for a schedule.

        Args:
            db: Database session
            schedule_id: Schedule UUID
            months: Number of months to preview

        Returns:
            List of upcoming payment details

        Raises:
            NotFoundException: If schedule not found
        """
        schedule = self.schedule_repo.get_by_id(db, schedule_id)
        if not schedule:
            raise NotFoundException(f"Payment schedule not found: {schedule_id}")

        preview_until = date.today() + timedelta(days=months * 30)
        current_date = schedule.next_due_date
        payments = []

        while current_date <= preview_until and current_date <= schedule.end_date:
            payments.append({
                "due_date": current_date.isoformat(),
                "amount": float(schedule.amount),
                "fee_type": schedule.fee_type,
                "description": f"{schedule.fee_type} - {current_date.strftime('%B %Y')}",
            })
            current_date = self._add_frequency_to_date(
                current_date, schedule.frequency
            )

        return payments