"""
Payment Refund Service.

Manages refund request workflow including creation, approval,
processing through gateways, and ledger updates.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    RefundError,
    RefundValidationError,
)
from app.models.payment.payment import Payment
from app.models.payment.payment_refund import PaymentRefund, RefundStatus
from app.repositories.payment.payment_refund_repository import (
    PaymentRefundRepository,
)
from app.repositories.payment.payment_repository import PaymentRepository
from app.services.payment.payment_gateway_service import PaymentGatewayService
from app.services.payment.payment_ledger_service import PaymentLedgerService


class PaymentRefundService:
    """
    Service for payment refund operations.
    
    Handles complete refund lifecycle:
    - Request creation
    - Approval workflow
    - Gateway processing
    - Ledger posting
    - Notifications
    """

    def __init__(
        self,
        session: AsyncSession,
        refund_repo: PaymentRefundRepository,
        payment_repo: PaymentRepository,
        gateway_service: PaymentGatewayService,
        ledger_service: PaymentLedgerService,
    ):
        """Initialize refund service."""
        self.session = session
        self.refund_repo = refund_repo
        self.payment_repo = payment_repo
        self.gateway_service = gateway_service
        self.ledger_service = ledger_service

    # ==================== Refund Request ====================

    async def create_refund_request(
        self,
        payment_id: UUID,
        requested_by: UUID,
        refund_amount: Decimal,
        refund_reason: str,
        refund_category: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> PaymentRefund:
        """
        Create a refund request.
        
        Args:
            payment_id: Payment to refund
            requested_by: User requesting refund
            refund_amount: Amount to refund
            refund_reason: Detailed reason
            refund_category: Category (cancellation, overpayment, etc.)
            metadata: Additional metadata
            
        Returns:
            Created refund request
            
        Raises:
            RefundValidationError: If validation fails
            RefundError: If creation fails
        """
        try:
            async with self.session.begin_nested():
                # Get payment
                payment = await self.payment_repo.get_by_id(payment_id)
                if not payment:
                    raise RefundValidationError(f"Payment not found: {payment_id}")
                
                # Validate refund
                await self._validate_refund_request(payment, refund_amount)
                
                # Create refund request
                refund = await self.refund_repo.create_refund_request(
                    payment_id=payment_id,
                    requested_by=requested_by,
                    refund_amount=refund_amount,
                    original_amount=payment.amount,
                    refund_reason=refund_reason,
                    refund_category=refund_category,
                    metadata=metadata,
                )
                
                # Send notification to approvers
                await self._notify_refund_requested(refund)
                
                await self.session.commit()
                return refund
                
        except RefundValidationError:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise RefundError(f"Failed to create refund request: {str(e)}")

    async def _validate_refund_request(
        self,
        payment: Payment,
        refund_amount: Decimal,
    ) -> None:
        """
        Validate refund request.
        
        Raises:
            RefundValidationError: If validation fails
        """
        # Payment must be completed
        if not payment.is_completed:
            raise RefundValidationError(
                "Cannot refund payment that is not completed"
            )
        
        # Refund amount validation
        if refund_amount <= Decimal("0"):
            raise RefundValidationError("Refund amount must be greater than zero")
        
        max_refundable = payment.amount - payment.refund_amount
        if refund_amount > max_refundable:
            raise RefundValidationError(
                f"Refund amount {refund_amount} exceeds maximum refundable "
                f"amount {max_refundable}"
            )
        
        # Check for pending refund requests
        existing_refunds = await self.refund_repo.find_by_payment(
            payment_id=payment.id,
            status=RefundStatus.PENDING,
        )
        
        if existing_refunds:
            raise RefundValidationError(
                "Payment already has pending refund request"
            )

    # ==================== Approval Workflow ====================

    async def approve_refund(
        self,
        refund_id: UUID,
        approved_by: UUID,
        approval_notes: Optional[str] = None,
        auto_process: bool = True,
    ) -> PaymentRefund:
        """
        Approve a refund request.
        
        Args:
            refund_id: Refund ID
            approved_by: User approving
            approval_notes: Approval notes
            auto_process: Automatically process if True
            
        Returns:
            Updated refund
        """
        try:
            async with self.session.begin_nested():
                # Approve refund
                refund = await self.refund_repo.approve_refund(
                    refund_id=refund_id,
                    approved_by=approved_by,
                    approval_notes=approval_notes,
                )
                
                # Send approval notification
                await self._notify_refund_approved(refund)
                
                # Auto-process if enabled
                if auto_process:
                    refund = await self.process_refund(
                        refund_id=refund_id,
                        processed_by=approved_by,
                    )
                
                await self.session.commit()
                return refund
                
        except Exception as e:
            await self.session.rollback()
            raise RefundError(f"Failed to approve refund: {str(e)}")

    async def reject_refund(
        self,
        refund_id: UUID,
        approved_by: UUID,
        rejection_reason: str,
    ) -> PaymentRefund:
        """
        Reject a refund request.
        
        Args:
            refund_id: Refund ID
            approved_by: User rejecting
            rejection_reason: Reason for rejection
            
        Returns:
            Updated refund
        """
        try:
            async with self.session.begin_nested():
                # Reject refund
                refund = await self.refund_repo.reject_refund(
                    refund_id=refund_id,
                    approved_by=approved_by,
                    rejection_reason=rejection_reason,
                )
                
                # Send rejection notification
                await self._notify_refund_rejected(refund, rejection_reason)
                
                await self.session.commit()
                return refund
                
        except Exception as e:
            await self.session.rollback()
            raise RefundError(f"Failed to reject refund: {str(e)}")

    # ==================== Refund Processing ====================

    async def process_refund(
        self,
        refund_id: UUID,
        processed_by: UUID,
    ) -> PaymentRefund:
        """
        Process approved refund through payment gateway.
        
        Args:
            refund_id: Refund ID
            processed_by: User processing
            
        Returns:
            Updated refund
        """
        try:
            async with self.session.begin_nested():
                # Get refund
                refund = await self.refund_repo.get_by_id(refund_id)
                if not refund:
                    raise RefundError(f"Refund not found: {refund_id}")
                
                if refund.refund_status != RefundStatus.APPROVED:
                    raise RefundError(
                        f"Refund must be approved before processing. "
                        f"Current status: {refund.refund_status}"
                    )
                
                # Get payment
                payment = await self.payment_repo.get_by_id(refund.payment_id)
                if not payment:
                    raise RefundError(f"Payment not found: {refund.payment_id}")
                
                # Initiate processing
                refund = await self.refund_repo.initiate_refund_processing(
                    refund_id=refund_id,
                    processed_by=processed_by,
                )
                
                # Process through gateway (for online payments)
                if payment.payment_method.value == "online":
                    gateway_result = await self.gateway_service.process_refund(
                        payment_id=payment.id,
                        refund_amount=refund.refund_amount,
                        reason=refund.refund_reason,
                    )
                    
                    # Update refund with gateway info
                    await self.refund_repo.update(
                        refund_id,
                        {
                            "gateway_refund_id": gateway_result["refund_id"],
                            "transaction_id": gateway_result["refund_id"],
                        },
                    )
                
                # For offline payments or after gateway processing
                # Complete the refund immediately
                refund = await self.complete_refund(
                    refund_id=refund_id,
                    processed_amount=refund.refund_amount,
                )
                
                await self.session.commit()
                return refund
                
        except Exception as e:
            await self.session.rollback()
            # Mark refund as failed
            try:
                await self.refund_repo.mark_refund_failed(
                    refund_id=refund_id,
                    error_message=str(e),
                )
            except:
                pass
            raise RefundError(f"Failed to process refund: {str(e)}")

    async def complete_refund(
        self,
        refund_id: UUID,
        processed_amount: Decimal,
        transaction_id: Optional[str] = None,
        gateway_response: Optional[dict] = None,
        processing_fee: Optional[Decimal] = None,
    ) -> PaymentRefund:
        """
        Complete a refund and update all related records.
        
        Args:
            refund_id: Refund ID
            processed_amount: Actual amount refunded
            transaction_id: Gateway transaction ID
            gateway_response: Full gateway response
            processing_fee: Fee charged for refund
            
        Returns:
            Completed refund
        """
        try:
            async with self.session.begin_nested():
                # Complete refund
                refund = await self.refund_repo.complete_refund(
                    refund_id=refund_id,
                    processed_amount=processed_amount,
                    transaction_id=transaction_id,
                    gateway_response=gateway_response,
                    processing_fee=processing_fee,
                )
                
                # Update payment refund amount
                await self.payment_repo.handle_payment_refund(
                    payment_id=refund.payment_id,
                    refund_amount=processed_amount,
                )
                
                # Post to ledger
                payment = await self.payment_repo.get_by_id(refund.payment_id)
                if payment:
                    await self.ledger_service.post_refund(
                        payment=payment,
                        refund_amount=processed_amount,
                        posted_by=refund.processed_by or refund.requested_by,
                        refund_reference=refund.refund_reference,
                        notes=refund.refund_reason,
                    )
                
                # Send completion notification
                await self._notify_refund_completed(refund)
                
                await self.session.commit()
                return refund
                
        except Exception as e:
            await self.session.rollback()
            raise RefundError(f"Failed to complete refund: {str(e)}")

    # ==================== Refund Queries ====================

    async def get_refund_by_id(
        self,
        refund_id: UUID,
    ) -> Optional[PaymentRefund]:
        """Get refund by ID."""
        return await self.refund_repo.get_by_id(refund_id)

    async def get_refund_by_reference(
        self,
        refund_reference: str,
    ) -> Optional[PaymentRefund]:
        """Get refund by reference."""
        return await self.refund_repo.find_by_reference(refund_reference)

    async def get_payment_refunds(
        self,
        payment_id: UUID,
        status: Optional[RefundStatus] = None,
    ) -> list[PaymentRefund]:
        """Get refunds for a payment."""
        return await self.refund_repo.find_by_payment(
            payment_id=payment_id,
            status=status,
        )

    async def get_pending_refunds(
        self,
        older_than_hours: Optional[int] = None,
    ) -> list[PaymentRefund]:
        """Get pending refund requests."""
        return await self.refund_repo.find_pending_refunds(
            older_than_hours=older_than_hours,
        )

    async def get_approved_refunds(
        self,
        unprocessed_only: bool = True,
    ) -> list[PaymentRefund]:
        """Get approved refunds ready for processing."""
        return await self.refund_repo.find_approved_refunds(
            unprocessed_only=unprocessed_only,
        )

    # ==================== Refund Statistics ====================

    async def calculate_refund_statistics(
        self,
        start_date: datetime,
        end_date: datetime,
        refund_category: Optional[str] = None,
    ) -> dict[str, Any]:
        """Calculate refund statistics for a period."""
        return await self.refund_repo.calculate_refund_statistics(
            start_date=start_date,
            end_date=end_date,
            refund_category=refund_category,
        )

    async def get_refund_approval_time(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get average refund approval time."""
        return await self.refund_repo.get_refund_approval_time(
            start_date=start_date,
            end_date=end_date,
        )

    async def get_refund_categories_breakdown(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Get refund breakdown by category."""
        return await self.refund_repo.get_refund_categories_breakdown(
            start_date=start_date,
            end_date=end_date,
        )

    # ==================== Bulk Operations ====================

    async def process_approved_refunds_batch(
        self,
        processed_by: UUID,
        max_count: int = 50,
    ) -> dict[str, Any]:
        """
        Process batch of approved refunds.
        
        Should be run as scheduled job.
        
        Args:
            processed_by: User/system processing
            max_count: Maximum refunds to process
            
        Returns:
            Processing summary
        """
        approved_refunds = await self.get_approved_refunds(unprocessed_only=True)
        
        # Limit batch size
        refunds_to_process = approved_refunds[:max_count]
        
        results = {
            "total_approved": len(approved_refunds),
            "processed": 0,
            "failed": 0,
            "errors": [],
        }
        
        for refund in refunds_to_process:
            try:
                await self.process_refund(
                    refund_id=refund.id,
                    processed_by=processed_by,
                )
                results["processed"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "refund_id": str(refund.id),
                    "error": str(e),
                })
        
        return results

    # ==================== Notification Methods ====================

    async def _notify_refund_requested(self, refund: PaymentRefund) -> None:
        """Send notification when refund is requested."""
        # TODO: Implement email/SMS notification to approvers
        pass

    async def _notify_refund_approved(self, refund: PaymentRefund) -> None:
        """Send notification when refund is approved."""
        # TODO: Implement notification to requester
        pass

    async def _notify_refund_rejected(
        self,
        refund: PaymentRefund,
        reason: str,
    ) -> None:
        """Send notification when refund is rejected."""
        # TODO: Implement notification to requester
        pass

    async def _notify_refund_completed(self, refund: PaymentRefund) -> None:
        """Send notification when refund is completed."""
        # TODO: Implement notification to requester
        pass