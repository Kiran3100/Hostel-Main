"""
Payment Schedule Service.

Manages recurring payment schedules with automated payment generation,
suspension/resumption workflows, and revenue forecasting.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ScheduleError, ScheduleValidationError
from app.models.payment.payment_schedule import PaymentSchedule, ScheduleStatus
from app.repositories.payment.payment_schedule_repository import (
    PaymentScheduleRepository,
)
from app.schemas.common.enums import FeeType, PaymentMethod, PaymentType
from app.services.payment.payment_service import PaymentService


class PaymentScheduleService:
    """
    Service for payment schedule operations.
    
    Features:
    - Schedule creation and management
    - Automated payment generation
    - Suspension and resumption
    - Revenue forecasting
    - Schedule expiry handling
    """

    def __init__(
        self,
        session: AsyncSession,
        schedule_repo: PaymentScheduleRepository,
        payment_service: PaymentService,
    ):
        """Initialize schedule service."""
        self.session = session
        self.schedule_repo = schedule_repo
        self.payment_service = payment_service

    # ==================== Schedule Creation ====================

    async def create_schedule(
        self,
        student_id: UUID,
        hostel_id: UUID,
        fee_type: FeeType,
        amount: Decimal,
        start_date: date,
        frequency_days: int,
        end_date: Optional[date] = None,
        day_of_month: Optional[int] = None,
        auto_generate_invoice: bool = True,
        auto_send_reminders: bool = True,
        days_before_due_reminder: int = 7,
        metadata: Optional[dict] = None,
    ) -> PaymentSchedule:
        """
        Create a new recurring payment schedule.
        
        Args:
            student_id: Student ID
            hostel_id: Hostel ID
            fee_type: Type of fee (monthly, quarterly, etc.)
            amount: Amount per period
            start_date: Schedule start date
            frequency_days: Days between payments
            end_date: Optional end date (None for indefinite)
            day_of_month: Specific day of month (1-31)
            auto_generate_invoice: Auto-generate payments
            auto_send_reminders: Auto-send reminders
            days_before_due_reminder: Days before due to remind
            metadata: Additional metadata
            
        Returns:
            Created schedule
            
        Raises:
            ScheduleValidationError: If validation fails
        """
        try:
            async with self.session.begin_nested():
                # Validate schedule
                await self._validate_schedule_creation(
                    student_id=student_id,
                    fee_type=fee_type,
                    amount=amount,
                    start_date=start_date,
                    frequency_days=frequency_days,
                    end_date=end_date,
                )
                
                # Create schedule
                schedule = await self.schedule_repo.create_schedule(
                    student_id=student_id,
                    hostel_id=hostel_id,
                    fee_type=fee_type,
                    amount=amount,
                    start_date=start_date,
                    frequency_days=frequency_days,
                    end_date=end_date,
                    day_of_month=day_of_month,
                    auto_generate_invoice=auto_generate_invoice,
                    auto_send_reminders=auto_send_reminders,
                    days_before_due_reminder=days_before_due_reminder,
                    metadata=metadata,
                )
                
                await self.session.commit()
                return schedule
                
        except ScheduleValidationError:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise ScheduleError(f"Failed to create schedule: {str(e)}")

    async def _validate_schedule_creation(
        self,
        student_id: UUID,
        fee_type: FeeType,
        amount: Decimal,
        start_date: date,
        frequency_days: int,
        end_date: Optional[date],
    ) -> None:
        """Validate schedule creation parameters."""
        # Amount validation
        if amount <= Decimal("0"):
            raise ScheduleValidationError("Amount must be greater than zero")
        
        # Date validation
        if start_date < date.today():
            raise ScheduleValidationError("Start date cannot be in the past")
        
        if end_date and end_date <= start_date:
            raise ScheduleValidationError("End date must be after start date")
        
        # Frequency validation
        if frequency_days < 1:
            raise ScheduleValidationError("Frequency must be at least 1 day")
        
        # Check for overlapping schedules
        existing_schedules = await self.schedule_repo.find_by_student(
            student_id=student_id,
            active_only=True,
        )
        
        for existing in existing_schedules:
            if existing.fee_type == fee_type:
                raise ScheduleValidationError(
                    f"Active schedule already exists for {fee_type.value}"
                )

    # ==================== Schedule Management ====================

    async def suspend_schedule(
        self,
        schedule_id: UUID,
        suspension_reason: str,
        suspension_start_date: Optional[date] = None,
        suspension_end_date: Optional[date] = None,
        skip_during_suspension: bool = True,
    ) -> PaymentSchedule:
        """
        Suspend a payment schedule.
        
        Useful for student vacation, leave of absence, etc.
        
        Args:
            schedule_id: Schedule to suspend
            suspension_reason: Reason for suspension
            suspension_start_date: Start of suspension
            suspension_end_date: End of suspension
            skip_during_suspension: Skip payment generation
            
        Returns:
            Updated schedule
        """
        try:
            async with self.session.begin_nested():
                schedule = await self.schedule_repo.suspend_schedule(
                    schedule_id=schedule_id,
                    suspension_reason=suspension_reason,
                    suspension_start_date=suspension_start_date,
                    suspension_end_date=suspension_end_date,
                    skip_during_suspension=skip_during_suspension,
                )
                
                await self.session.commit()
                return schedule
                
        except Exception as e:
            await self.session.rollback()
            raise ScheduleError(f"Failed to suspend schedule: {str(e)}")

    async def resume_schedule(
        self,
        schedule_id: UUID,
    ) -> PaymentSchedule:
        """
        Resume a suspended schedule.
        
        Args:
            schedule_id: Schedule to resume
            
        Returns:
            Updated schedule
        """
        try:
            async with self.session.begin_nested():
                schedule = await self.schedule_repo.resume_schedule(
                    schedule_id=schedule_id,
                )
                
                await self.session.commit()
                return schedule
                
        except Exception as e:
            await self.session.rollback()
            raise ScheduleError(f"Failed to resume schedule: {str(e)}")

    async def pause_schedule(
        self,
        schedule_id: UUID,
    ) -> PaymentSchedule:
        """Temporarily pause a schedule."""
        try:
            async with self.session.begin_nested():
                schedule = await self.schedule_repo.pause_schedule(
                    schedule_id=schedule_id,
                )
                
                await self.session.commit()
                return schedule
                
        except Exception as e:
            await self.session.rollback()
            raise ScheduleError(f"Failed to pause schedule: {str(e)}")

    async def complete_schedule(
        self,
        schedule_id: UUID,
        completion_reason: Optional[str] = None,
    ) -> PaymentSchedule:
        """Mark schedule as completed."""
        try:
            async with self.session.begin_nested():
                schedule = await self.schedule_repo.complete_schedule(
                    schedule_id=schedule_id,
                    completion_reason=completion_reason,
                )
                
                await self.session.commit()
                return schedule
                
        except Exception as e:
            await self.session.rollback()
            raise ScheduleError(f"Failed to complete schedule: {str(e)}")

    async def cancel_schedule(
        self,
        schedule_id: UUID,
    ) -> PaymentSchedule:
        """Cancel a schedule."""
        try:
            async with self.session.begin_nested():
                schedule = await self.schedule_repo.cancel_schedule(
                    schedule_id=schedule_id,
                )
                
                await self.session.commit()
                return schedule
                
        except Exception as e:
            await self.session.rollback()
            raise ScheduleError(f"Failed to cancel schedule: {str(e)}")

    # ==================== Payment Generation ====================

    async def generate_due_payments(
        self,
        hostel_id: Optional[UUID] = None,
        up_to_date: Optional[date] = None,
    ) -> dict[str, Any]:
        """
        Generate payments for all due schedules.
        
        This should be run as a daily scheduled job.
        
        Args:
            hostel_id: Optional hostel filter
            up_to_date: Generate payments due up to this date
            
        Returns:
            Generation summary
        """
        target_date = up_to_date or date.today()
        
        # Get due schedules
        due_schedules = await self.schedule_repo.find_due_schedules(
            hostel_id=hostel_id,
            up_to_date=target_date,
        )
        
        results = {
            "total_schedules": len(due_schedules),
            "payments_generated": 0,
            "failed": 0,
            "skipped_suspended": 0,
            "errors": [],
        }
        
        for schedule in due_schedules:
            try:
                # Skip if suspended and configured to skip
                if (
                    schedule.schedule_status == ScheduleStatus.SUSPENDED
                    and schedule.skip_during_suspension
                ):
                    results["skipped_suspended"] += 1
                    continue
                
                # Generate payment
                payment = await self.payment_service.create_payment(
                    hostel_id=schedule.hostel_id,
                    student_id=schedule.student_id,
                    payer_id=schedule.student_id,  # Student is payer
                    amount=schedule.amount,
                    payment_type=self._map_fee_type_to_payment_type(schedule.fee_type),
                    payment_method=PaymentMethod.ONLINE,  # Default
                    due_date=schedule.next_due_date,
                    payment_schedule_id=schedule.id,
                    metadata={
                        "generated_from_schedule": True,
                        "schedule_reference": schedule.schedule_reference,
                    },
                )
                
                # Calculate next due date
                next_due = schedule.next_due_date + timedelta(
                    days=schedule.frequency_days
                )
                
                # Check if schedule should end
                if schedule.end_date and next_due > schedule.end_date:
                    await self.complete_schedule(
                        schedule_id=schedule.id,
                        completion_reason="Schedule end date reached",
                    )
                else:
                    # Update next due date
                    await self.schedule_repo.update_next_due_date(
                        schedule_id=schedule.id,
                        next_due_date=next_due,
                    )
                
                results["payments_generated"] += 1
                
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "schedule_id": str(schedule.id),
                    "student_id": str(schedule.student_id),
                    "error": str(e),
                })
        
        return results

    async def generate_payment_for_schedule(
        self,
        schedule_id: UUID,
    ) -> dict[str, Any]:
        """
        Manually generate payment for a specific schedule.
        
        Args:
            schedule_id: Schedule ID
            
        Returns:
            Generation result
        """
        try:
            schedule = await self.schedule_repo.get_by_id(schedule_id)
            if not schedule:
                raise ScheduleError(f"Schedule not found: {schedule_id}")
            
            if not schedule.is_active:
                raise ScheduleError(f"Schedule is not active: {schedule.schedule_status}")
            
            payment = await self.payment_service.create_payment(
                hostel_id=schedule.hostel_id,
                student_id=schedule.student_id,
                payer_id=schedule.student_id,
                amount=schedule.amount,
                payment_type=self._map_fee_type_to_payment_type(schedule.fee_type),
                payment_method=PaymentMethod.ONLINE,
                due_date=schedule.next_due_date,
                payment_schedule_id=schedule.id,
            )
            
            # Update next due date
            next_due = schedule.next_due_date + timedelta(days=schedule.frequency_days)
            await self.schedule_repo.update_next_due_date(
                schedule_id=schedule.id,
                next_due_date=next_due,
            )
            
            return {
                "success": True,
                "payment_id": str(payment.id),
                "payment_reference": payment.payment_reference,
                "amount": float(payment.amount),
                "due_date": payment.due_date.isoformat() if payment.due_date else None,
            }
            
        except Exception as e:
            raise ScheduleError(f"Failed to generate payment: {str(e)}")

    # ==================== Schedule Queries ====================

    async def get_schedule_by_id(
        self,
        schedule_id: UUID,
    ) -> Optional[PaymentSchedule]:
        """Get schedule by ID."""
        return await self.schedule_repo.get_by_id(schedule_id)

    async def get_schedule_by_reference(
        self,
        schedule_reference: str,
    ) -> Optional[PaymentSchedule]:
        """Get schedule by reference."""
        return await self.schedule_repo.find_by_reference(schedule_reference)

    async def get_student_schedules(
        self,
        student_id: UUID,
        status: Optional[ScheduleStatus] = None,
        active_only: bool = False,
    ) -> list[PaymentSchedule]:
        """Get schedules for a student."""
        return await self.schedule_repo.find_by_student(
            student_id=student_id,
            status=status,
            active_only=active_only,
        )

    async def get_hostel_schedules(
        self,
        hostel_id: UUID,
        status: Optional[ScheduleStatus] = None,
        fee_type: Optional[FeeType] = None,
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PaymentSchedule]:
        """Get schedules for a hostel."""
        return await self.schedule_repo.find_by_hostel(
            hostel_id=hostel_id,
            status=status,
            fee_type=fee_type,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

    # ==================== Schedule Analytics ====================

    async def calculate_schedule_statistics(
        self,
        hostel_id: UUID,
    ) -> dict[str, Any]:
        """Get schedule statistics for a hostel."""
        return await self.schedule_repo.calculate_schedule_statistics(
            hostel_id=hostel_id,
        )

    async def calculate_collection_rate(
        self,
        hostel_id: UUID,
        fee_type: Optional[FeeType] = None,
    ) -> dict[str, Any]:
        """Calculate collection rate for schedules."""
        return await self.schedule_repo.calculate_collection_rate(
            hostel_id=hostel_id,
            fee_type=fee_type,
        )

    async def get_revenue_projection(
        self,
        hostel_id: UUID,
        months_ahead: int = 12,
    ) -> list[dict[str, Any]]:
        """Get revenue projection from active schedules."""
        return await self.schedule_repo.get_revenue_projection(
            hostel_id=hostel_id,
            months_ahead=months_ahead,
        )

    # ==================== Expiry Management ====================

    async def check_expiring_schedules(
        self,
        hostel_id: Optional[UUID] = None,
        days_until_expiry: int = 30,
    ) -> list[PaymentSchedule]:
        """Get schedules expiring soon."""
        return await self.schedule_repo.find_expiring_schedules(
            hostel_id=hostel_id,
            days_until_expiry=days_until_expiry,
        )

    async def auto_complete_expired_schedules(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """
        Automatically complete expired schedules.
        
        Should be run as scheduled job.
        """
        # Get schedules that have passed end date
        expiring = await self.schedule_repo.find_expiring_schedules(
            hostel_id=hostel_id,
            days_until_expiry=0,  # Already expired
        )
        
        results = {
            "total_expired": len(expiring),
            "completed": 0,
            "errors": [],
        }
        
        for schedule in expiring:
            try:
                await self.complete_schedule(
                    schedule_id=schedule.id,
                    completion_reason="Schedule end date reached",
                )
                results["completed"] += 1
            except Exception as e:
                results["errors"].append({
                    "schedule_id": str(schedule.id),
                    "error": str(e),
                })
        
        return results

    # ==================== Helper Methods ====================

    def _map_fee_type_to_payment_type(
        self,
        fee_type: FeeType,
    ) -> PaymentType:
        """Map fee type to payment type."""
        # Adjust mapping based on your actual enums
        mapping = {
            FeeType.MONTHLY: PaymentType.MONTHLY_RENT,
            FeeType.QUARTERLY: PaymentType.MONTHLY_RENT,
            # Add more mappings
        }
        
        return mapping.get(fee_type, PaymentType.MONTHLY_RENT)