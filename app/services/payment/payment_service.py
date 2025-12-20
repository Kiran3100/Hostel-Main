"""
Payment Service.

Core payment processing orchestration including validation, creation,
gateway integration, ledger posting, and notifications.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    FraudDetectedError,
    PaymentProcessingError,
    PaymentValidationError,
)
from app.models.payment.payment import Payment
from app.models.payment.payment_ledger import LedgerEntryType, TransactionType
from app.repositories.payment.payment_ledger_repository import (
    PaymentLedgerRepository,
)
from app.repositories.payment.payment_reminder_repository import (
    PaymentReminderRepository,
)
from app.repositories.payment.payment_repository import PaymentRepository
from app.repositories.payment.payment_schedule_repository import (
    PaymentScheduleRepository,
)
from app.schemas.common.enums import PaymentMethod, PaymentStatus, PaymentType
from app.services.payment.payment_fraud_service import PaymentFraudService
from app.services.payment.payment_gateway_service import PaymentGatewayService
from app.services.payment.payment_ledger_service import PaymentLedgerService
from app.services.payment.payment_reminder_service import PaymentReminderService


class PaymentService:
    """
    Service for payment business logic.
    
    Orchestrates the complete payment lifecycle including:
    - Payment creation and validation
    - Fraud detection
    - Gateway integration
    - Ledger posting
    - Receipt generation
    - Reminder scheduling
    """

    def __init__(
        self,
        session: AsyncSession,
        payment_repo: PaymentRepository,
        ledger_repo: PaymentLedgerRepository,
        schedule_repo: PaymentScheduleRepository,
        reminder_repo: PaymentReminderRepository,
        gateway_service: PaymentGatewayService,
        fraud_service: PaymentFraudService,
        ledger_service: PaymentLedgerService,
        reminder_service: PaymentReminderService,
    ):
        """Initialize payment service with dependencies."""
        self.session = session
        self.payment_repo = payment_repo
        self.ledger_repo = ledger_repo
        self.schedule_repo = schedule_repo
        self.reminder_repo = reminder_repo
        self.gateway_service = gateway_service
        self.fraud_service = fraud_service
        self.ledger_service = ledger_service
        self.reminder_service = reminder_service

    # ==================== Payment Creation ====================

    async def create_payment(
        self,
        hostel_id: UUID,
        student_id: UUID,
        payer_id: UUID,
        amount: Decimal,
        payment_type: PaymentType,
        payment_method: PaymentMethod,
        due_date: Optional[date] = None,
        booking_id: Optional[UUID] = None,
        payment_schedule_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
    ) -> Payment:
        """
        Create a new payment with full workflow.
        
        Workflow:
        1. Validate payment data
        2. Run fraud checks
        3. Create payment record
        4. Post to ledger
        5. Schedule reminders (if applicable)
        
        Args:
            hostel_id: Hostel ID
            student_id: Student ID
            payer_id: User making payment
            amount: Payment amount
            payment_type: Type of payment (rent, mess, deposit, etc.)
            payment_method: Payment method (online, cash, cheque, etc.)
            due_date: Payment due date
            booking_id: Optional booking reference
            payment_schedule_id: Optional schedule reference
            metadata: Additional metadata
            
        Returns:
            Created payment record
            
        Raises:
            PaymentValidationError: If validation fails
            FraudDetectedError: If fraud is detected
            PaymentProcessingError: If processing fails
        """
        try:
            async with self.session.begin_nested():
                # Step 1: Validation
                await self._validate_payment_creation(
                    hostel_id=hostel_id,
                    student_id=student_id,
                    amount=amount,
                    payment_type=payment_type,
                )
                
                # Step 2: Fraud detection
                fraud_assessment = await self.fraud_service.assess_payment_risk(
                    student_id=student_id,
                    hostel_id=hostel_id,
                    amount=amount,
                    payment_method=payment_method,
                    payer_id=payer_id,
                )
                
                if fraud_assessment["risk_level"] == "high":
                    raise FraudDetectedError(
                        f"High fraud risk detected: {fraud_assessment['risk_score']}/100. "
                        f"Reasons: {', '.join(fraud_assessment['risk_factors'])}"
                    )
                
                # Step 3: Create payment
                payment = await self.payment_repo.create_payment(
                    hostel_id=hostel_id,
                    student_id=student_id,
                    payer_id=payer_id,
                    payment_type=payment_type,
                    amount=amount,
                    payment_method=payment_method,
                    booking_id=booking_id,
                    payment_schedule_id=payment_schedule_id,
                    due_date=due_date,
                    metadata={
                        **(metadata or {}),
                        "fraud_score": fraud_assessment["risk_score"],
                        "fraud_level": fraud_assessment["risk_level"],
                    },
                )
                
                # Step 4: Post to ledger (debit - amount owed)
                await self.ledger_service.post_payment_created(
                    payment=payment,
                    posted_by=payer_id,
                )
                
                # Step 5: Schedule reminders (for future payments)
                if due_date and payment_method in [PaymentMethod.CASH, PaymentMethod.CHEQUE, PaymentMethod.BANK_TRANSFER]:
                    await self.reminder_service.schedule_payment_reminders(
                        payment=payment,
                    )
                
                # Step 6: Update schedule statistics
                if payment_schedule_id:
                    await self.schedule_repo.increment_payment_generated(
                        schedule_id=payment_schedule_id,
                        payment_amount=amount,
                    )
                
                await self.session.commit()
                return payment
                
        except (PaymentValidationError, FraudDetectedError) as e:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise PaymentProcessingError(f"Failed to create payment: {str(e)}")

    async def initiate_online_payment(
        self,
        payment_id: UUID,
        gateway_name: str = "razorpay",
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Initiate online payment through gateway.
        
        Args:
            payment_id: Payment ID
            gateway_name: Gateway to use (razorpay, stripe, etc.)
            return_url: URL to redirect after success
            cancel_url: URL to redirect on cancellation
            
        Returns:
            Gateway order details for client
            {
                "gateway": "razorpay",
                "order_id": "order_xxx",
                "amount": 10000,
                "currency": "INR",
                "key": "rzp_xxx",
                "checkout_url": "https://...",
            }
            
        Raises:
            PaymentValidationError: If payment not found or invalid
            PaymentProcessingError: If gateway integration fails
        """
        # Get payment
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise PaymentValidationError(f"Payment not found: {payment_id}")
        
        if payment.payment_status != PaymentStatus.PENDING:
            raise PaymentValidationError(
                f"Payment is not pending: {payment.payment_status}"
            )
        
        # Create gateway order
        gateway_order = await self.gateway_service.create_order(
            payment=payment,
            gateway_name=gateway_name,
            return_url=return_url,
            cancel_url=cancel_url,
        )
        
        return gateway_order

    async def complete_payment(
        self,
        payment_id: UUID,
        transaction_id: Optional[str] = None,
        gateway_order_id: Optional[str] = None,
        gateway_response: Optional[dict] = None,
        collected_by: Optional[UUID] = None,
    ) -> Payment:
        """
        Complete a payment and update all related records.
        
        Workflow:
        1. Validate payment can be completed
        2. Mark payment as completed
        3. Update ledger (credit - payment received)
        4. Generate receipt
        5. Send confirmation notification
        6. Update schedule statistics
        
        Args:
            payment_id: Payment ID
            transaction_id: Gateway transaction ID
            gateway_order_id: Gateway order ID
            gateway_response: Full gateway response
            collected_by: Staff who collected (for offline payments)
            
        Returns:
            Completed payment
            
        Raises:
            PaymentValidationError: If validation fails
            PaymentProcessingError: If completion fails
        """
        try:
            async with self.session.begin_nested():
                # Get payment
                payment = await self.payment_repo.get_by_id(payment_id)
                if not payment:
                    raise PaymentValidationError(f"Payment not found: {payment_id}")
                
                # Validate state transition
                if payment.payment_status == PaymentStatus.COMPLETED:
                    raise PaymentValidationError("Payment already completed")
                
                if payment.payment_status not in [
                    PaymentStatus.PENDING,
                    PaymentStatus.PROCESSING,
                ]:
                    raise PaymentValidationError(
                        f"Cannot complete payment in status: {payment.payment_status}"
                    )
                
                # Update payment to processing first
                if transaction_id:
                    await self.payment_repo.process_payment_transaction(
                        payment_id=payment_id,
                        transaction_id=transaction_id,
                        gateway_order_id=gateway_order_id,
                        gateway_response=gateway_response,
                    )
                
                # Mark as completed
                payment = await self.payment_repo.mark_payment_completed(
                    payment_id=payment_id,
                    collected_by=collected_by,
                )
                
                # Post to ledger (credit - payment received)
                await self.ledger_service.post_payment_completed(
                    payment=payment,
                    posted_by=collected_by or payment.payer_id,
                )
                
                # Generate receipt
                receipt_url = await self._generate_receipt(payment)
                
                # Update payment with receipt URL
                if receipt_url:
                    await self.payment_repo.update(
                        payment_id,
                        {"receipt_url": receipt_url},
                    )
                
                # Send confirmation
                await self._send_payment_confirmation(payment)
                
                # Update schedule statistics
                if payment.payment_schedule_id:
                    await self.schedule_repo.increment_payment_completed(
                        schedule_id=payment.payment_schedule_id,
                        payment_amount=payment.amount,
                    )
                
                await self.session.commit()
                return payment
                
        except PaymentValidationError as e:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise PaymentProcessingError(f"Failed to complete payment: {str(e)}")

    async def fail_payment(
        self,
        payment_id: UUID,
        failure_reason: str,
        error_code: Optional[str] = None,
        gateway_response: Optional[dict] = None,
    ) -> Payment:
        """
        Mark payment as failed and handle cleanup.
        
        Args:
            payment_id: Payment ID
            failure_reason: Reason for failure
            error_code: Error code from gateway
            gateway_response: Full gateway error response
            
        Returns:
            Updated payment
        """
        try:
            async with self.session.begin_nested():
                # Mark as failed
                payment = await self.payment_repo.mark_payment_failed(
                    payment_id=payment_id,
                    failure_reason=failure_reason,
                )
                
                # Optionally reverse ledger entry
                # (or keep debit to show attempted payment)
                
                # Send failure notification
                await self._send_payment_failure_notification(
                    payment=payment,
                    failure_reason=failure_reason,
                )
                
                await self.session.commit()
                return payment
                
        except Exception as e:
            await self.session.rollback()
            raise PaymentProcessingError(f"Failed to process payment failure: {str(e)}")

    # ==================== Payment Queries ====================

    async def get_payment_by_id(self, payment_id: UUID) -> Optional[Payment]:
        """Get payment by ID."""
        return await self.payment_repo.get_by_id(payment_id)

    async def get_payment_by_reference(
        self, payment_reference: str
    ) -> Optional[Payment]:
        """Get payment by reference number."""
        return await self.payment_repo.find_by_reference(payment_reference)

    async def get_student_payments(
        self,
        student_id: UUID,
        status: Optional[PaymentStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Payment]:
        """Get payments for a student."""
        return await self.payment_repo.find_by_student(
            student_id=student_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def get_hostel_payments(
        self,
        hostel_id: UUID,
        status: Optional[PaymentStatus] = None,
        payment_type: Optional[PaymentType] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Payment]:
        """Get payments for a hostel."""
        return await self.payment_repo.find_by_hostel(
            hostel_id=hostel_id,
            status=status,
            payment_type=payment_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )

    async def get_overdue_payments(
        self,
        hostel_id: Optional[UUID] = None,
        grace_period_days: int = 0,
    ) -> list[Payment]:
        """Get overdue payments."""
        return await self.payment_repo.find_overdue_payments(
            hostel_id=hostel_id,
            grace_period_days=grace_period_days,
        )

    async def get_pending_payments(
        self,
        hostel_id: Optional[UUID] = None,
        older_than_hours: Optional[int] = None,
    ) -> list[Payment]:
        """Get pending payments."""
        return await self.payment_repo.find_pending_payments(
            hostel_id=hostel_id,
            older_than_hours=older_than_hours,
        )

    # ==================== Payment Statistics ====================

    async def calculate_revenue_statistics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        payment_type: Optional[PaymentType] = None,
    ) -> dict[str, Any]:
        """Calculate revenue statistics for a period."""
        return await self.payment_repo.calculate_revenue_statistics(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
            payment_type=payment_type,
        )

    async def calculate_success_rate(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        payment_method: Optional[PaymentMethod] = None,
    ) -> dict[str, Any]:
        """Calculate payment success rate."""
        return await self.payment_repo.calculate_payment_success_rate(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
            payment_method=payment_method,
        )

    async def get_payment_method_distribution(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Get payment method distribution."""
        return await self.payment_repo.get_payment_method_distribution(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_revenue_trends(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        interval: str = "day",
    ) -> list[dict[str, Any]]:
        """Get revenue trends over time."""
        return await self.payment_repo.get_revenue_trends(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )

    # ==================== Bulk Operations ====================

    async def bulk_update_overdue_status(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> int:
        """
        Bulk update overdue status for all pending payments.
        
        This should be run as a scheduled job daily.
        
        Returns:
            Number of payments updated
        """
        return await self.payment_repo.bulk_update_overdue_status(
            hostel_id=hostel_id
        )

    async def process_scheduled_payments(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """
        Process all due scheduled payments.
        
        This should be run as a scheduled job daily.
        
        Returns:
            Processing summary
        """
        # Get due schedules
        due_schedules = await self.schedule_repo.find_due_schedules(
            hostel_id=hostel_id,
        )
        
        results = {
            "total_schedules": len(due_schedules),
            "payments_created": 0,
            "failed": 0,
            "errors": [],
        }
        
        for schedule in due_schedules:
            try:
                # Create payment from schedule
                payment = await self.create_payment(
                    hostel_id=schedule.hostel_id,
                    student_id=schedule.student_id,
                    payer_id=schedule.student_id,  # Student is payer
                    amount=schedule.amount,
                    payment_type=PaymentType.MONTHLY_RENT,  # Map from fee_type
                    payment_method=PaymentMethod.ONLINE,
                    due_date=schedule.next_due_date,
                    payment_schedule_id=schedule.id,
                )
                
                # Update schedule next due date
                next_due = schedule.next_due_date + timedelta(days=schedule.frequency_days)
                await self.schedule_repo.update_next_due_date(
                    schedule_id=schedule.id,
                    next_due_date=next_due,
                )
                
                results["payments_created"] += 1
                
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "schedule_id": str(schedule.id),
                    "error": str(e),
                })
        
        return results

    # ==================== Helper Methods ====================

    async def _validate_payment_creation(
        self,
        hostel_id: UUID,
        student_id: UUID,
        amount: Decimal,
        payment_type: PaymentType,
    ) -> None:
        """
        Validate payment creation data.
        
        Raises:
            PaymentValidationError: If validation fails
        """
        # Validate amount
        if amount <= Decimal("0"):
            raise PaymentValidationError("Payment amount must be greater than zero")
        
        if amount > Decimal("1000000"):  # 10 lakhs
            raise PaymentValidationError("Payment amount exceeds maximum limit")
        
        # Validate hostel exists (you'd check with hostel repo)
        # Validate student exists and belongs to hostel (you'd check with student repo)
        # Add more business validation as needed
        pass

    async def _generate_receipt(self, payment: Payment) -> Optional[str]:
        """
        Generate payment receipt.
        
        In production, this would:
        - Generate PDF receipt
        - Upload to S3/cloud storage
        - Return download URL
        
        Returns:
            Receipt URL or None
        """
        # TODO: Implement actual receipt generation
        # For now, return placeholder
        return f"https://receipts.example.com/{payment.receipt_number}.pdf"

    async def _send_payment_confirmation(self, payment: Payment) -> None:
        """
        Send payment confirmation notification.
        
        Would integrate with email/SMS service in production.
        """
        # TODO: Implement actual notification sending
        # This would call email service, SMS service, push notification service
        pass

    async def _send_payment_failure_notification(
        self,
        payment: Payment,
        failure_reason: str,
    ) -> None:
        """Send payment failure notification."""
        # TODO: Implement actual notification sending
        pass