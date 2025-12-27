# app/services/payment/payment_refund_service.py
"""
Payment Refund Service

Handles complete refund lifecycle:
- Request refund
- Approve/reject refund
- Coordinate with gateway refunds
- Update payment & ledger accordingly
- Handle partial and full refunds
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from decimal import Decimal
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.payment import (
    PaymentRepository,
    PaymentRefundRepository,
    GatewayTransactionRepository,
    PaymentLedgerRepository,
)
from app.schemas.payment import (
    RefundRequest,
    RefundResponse,
    RefundApproval,
    RefundList,
    RefundListItem,
)
from app.core1.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)
from app.models.base.enums import PaymentStatus, RefundStatus
from app.core1.logging import LoggingContext, logger


class PaymentRefundService:
    """
    High-level orchestration for refunds.

    Responsibilities:
    - Validate refund requests
    - Manage refund approval workflow
    - Coordinate with payment gateway for online refunds
    - Update payment and ledger records
    - Handle partial and full refunds
    - Maintain refund audit trail

    Delegates:
    - Persistence to PaymentRefundRepository
    - Payment updates to PaymentRepository
    - Ledger entries to PaymentLedgerRepository
    - Gateway calls to PaymentGatewayService (injected separately)
    """

    __slots__ = (
        "payment_repo",
        "refund_repo",
        "gateway_tx_repo",
        "ledger_repo",
    )

    def __init__(
        self,
        payment_repo: PaymentRepository,
        refund_repo: PaymentRefundRepository,
        gateway_tx_repo: GatewayTransactionRepository,
        ledger_repo: PaymentLedgerRepository,
    ) -> None:
        self.payment_repo = payment_repo
        self.refund_repo = refund_repo
        self.gateway_tx_repo = gateway_tx_repo
        self.ledger_repo = ledger_repo

    # -------------------------------------------------------------------------
    # Request
    # -------------------------------------------------------------------------

    def request_refund(
        self,
        db: Session,
        request: RefundRequest,
        requested_by: UUID,
    ) -> RefundResponse:
        """
        Create a refund request for a payment.

        Validations:
        - Payment exists and is in COMPLETED status
        - Requested amount does not exceed refundable amount
        - Payment method supports refunds
        - Refund is within allowed time window

        Args:
            db: Database session
            request: Refund request details
            requested_by: UUID of user requesting refund

        Returns:
            RefundResponse with created refund details

        Raises:
            NotFoundException: If payment not found
            ValidationException: If request is invalid
            BusinessLogicException: If refund rules are violated
        """
        payment = self.payment_repo.get_by_id(db, request.payment_id)
        if not payment:
            raise NotFoundException(f"Payment not found: {request.payment_id}")

        # Validate refund eligibility
        self._validate_refund_eligibility(db, payment, request)

        payload = request.model_dump(exclude_none=True)
        payload["requested_by"] = requested_by
        payload["requested_at"] = datetime.utcnow()
        payload["status"] = RefundStatus.PENDING.value

        with LoggingContext(
            payment_id=str(request.payment_id),
            refund_amount=float(request.refund_amount),
        ):
            try:
                obj = self.refund_repo.create_refund_request(db, payload)

                logger.info(
                    f"Refund requested: {obj.id}",
                    extra={
                        "refund_id": str(obj.id),
                        "payment_id": str(request.payment_id),
                        "amount": float(request.refund_amount),
                        "requested_by": str(requested_by),
                    },
                )

                return RefundResponse.model_validate(obj)

            except Exception as e:
                logger.error(f"Failed to create refund request: {str(e)}")
                raise BusinessLogicException(
                    f"Failed to create refund request: {str(e)}"
                )

    def _validate_refund_eligibility(
        self,
        db: Session,
        payment: Any,
        request: RefundRequest,
    ) -> None:
        """
        Validate that payment is eligible for refund.

        Args:
            db: Database session
            payment: Payment object
            request: Refund request

        Raises:
            BusinessLogicException: If payment is not refundable
            ValidationException: If request is invalid
        """
        # Check payment status
        if payment.status != PaymentStatus.COMPLETED:
            raise BusinessLogicException(
                f"Only completed payments can be refunded. Current status: {payment.status.value}"
            )

        # Check refund amount
        if request.refund_amount <= 0:
            raise ValidationException("Refund amount must be positive")

        # Calculate refundable amount
        refundable_amount = self._calculate_refundable_amount(db, payment)

        if request.refund_amount > refundable_amount:
            raise ValidationException(
                f"Refund amount ({request.refund_amount}) exceeds refundable amount ({refundable_amount})"
            )

        # Check if payment method supports refunds
        if not self._is_refundable_payment_method(payment.payment_method):
            raise BusinessLogicException(
                f"Payment method {payment.payment_method.value} does not support refunds"
            )

        # Check refund time window (e.g., within 90 days)
        if not self._is_within_refund_window(payment):
            raise BusinessLogicException(
                "Refund request is outside the allowed time window"
            )

        # Check for duplicate pending refunds
        if self._has_pending_refund(db, payment.id):
            raise BusinessLogicException(
                "A pending refund request already exists for this payment"
            )

    def _calculate_refundable_amount(
        self,
        db: Session,
        payment: Any,
    ) -> Decimal:
        """
        Calculate the amount that can still be refunded.

        Returns paid amount minus already refunded amounts.
        """
        # Get all approved/completed refunds for this payment
        existing_refunds = self.refund_repo.get_approved_refunds_for_payment(
            db, payment.id
        )

        total_refunded = sum(
            Decimal(str(r.refund_amount)) for r in existing_refunds
        )

        refundable = Decimal(str(payment.amount)) - total_refunded

        return max(refundable, Decimal("0"))

    def _is_refundable_payment_method(self, payment_method: Any) -> bool:
        """Check if payment method supports refunds."""
        # Cash payments typically don't support automated refunds
        non_refundable = {"CASH", "DEMAND_DRAFT"}
        return payment_method.value not in non_refundable

    def _is_within_refund_window(
        self,
        payment: Any,
        days: int = 90,
    ) -> bool:
        """Check if payment is within refund time window."""
        if not payment.paid_at:
            return False

        from datetime import timedelta
        window_end = payment.paid_at + timedelta(days=days)
        return datetime.utcnow() <= window_end

    def _has_pending_refund(self, db: Session, payment_id: UUID) -> bool:
        """Check if payment has pending refund requests."""
        pending = self.refund_repo.get_pending_refunds_for_payment(db, payment_id)
        return len(pending) > 0

    # -------------------------------------------------------------------------
    # Approval & processing
    # -------------------------------------------------------------------------

    def approve_refund(
        self,
        db: Session,
        refund_id: UUID,
        approved_by: UUID,
        approval_notes: Optional[str] = None,
        gateway_service: Optional[Any] = None,
    ) -> RefundResponse:
        """
        Approve a refund request and process it.

        Process:
        1. Validate refund can be approved
        2. Mark refund as approved
        3. If online payment, initiate gateway refund
        4. Create ledger entry
        5. Update payment status if fully refunded

        Args:
            db: Database session
            refund_id: Refund UUID
            approved_by: UUID of approver
            approval_notes: Optional approval notes
            gateway_service: Optional PaymentGatewayService for online refunds

        Returns:
            RefundResponse with updated refund

        Raises:
            NotFoundException: If refund not found
            BusinessLogicException: If refund cannot be approved
        """
        refund = self.refund_repo.get_by_id(db, refund_id)
        if not refund:
            raise NotFoundException(f"Refund not found: {refund_id}")

        payment = self.payment_repo.get_by_id(db, refund.payment_id)
        if not payment:
            raise NotFoundException(f"Payment not found: {refund.payment_id}")

        # Validate can be approved
        if refund.status != RefundStatus.PENDING:
            raise BusinessLogicException(
                f"Only pending refunds can be approved. Current status: {refund.status.value}"
            )

        with LoggingContext(
            refund_id=str(refund_id),
            payment_id=str(payment.id),
        ):
            try:
                # Mark as approved
                updated_refund = self.refund_repo.mark_approved(
                    db=db,
                    refund=refund,
                    approved_by=approved_by,
                    notes=approval_notes,
                )

                # Initiate gateway refund for online payments
                if payment.is_online and gateway_service:
                    self._initiate_gateway_refund(
                        db=db,
                        payment=payment,
                        refund=updated_refund,
                        gateway_service=gateway_service,
                    )

                # Create ledger entry
                self._create_refund_ledger_entry(
                    db=db,
                    payment=payment,
                    refund=updated_refund,
                )

                # Update payment status if needed
                self._update_payment_after_refund(db, payment)

                logger.info(
                    f"Refund approved: {refund_id}",
                    extra={
                        "refund_id": str(refund_id),
                        "payment_id": str(payment.id),
                        "amount": float(updated_refund.refund_amount),
                        "approved_by": str(approved_by),
                    },
                )

                return RefundResponse.model_validate(updated_refund)

            except Exception as e:
                logger.error(f"Failed to approve refund: {str(e)}")
                # Mark refund as failed
                self.refund_repo.mark_failed(
                    db=db,
                    refund=refund,
                    failure_reason=str(e),
                )
                raise BusinessLogicException(f"Failed to approve refund: {str(e)}")

    def reject_refund(
        self,
        db: Session,
        refund_id: UUID,
        rejected_by: UUID,
        rejection_reason: str,
    ) -> RefundResponse:
        """
        Reject a refund request.

        Args:
            db: Database session
            refund_id: Refund UUID
            rejected_by: UUID of user rejecting
            rejection_reason: Reason for rejection

        Returns:
            RefundResponse with rejected refund

        Raises:
            NotFoundException: If refund not found
            ValidationException: If rejection reason is missing
            BusinessLogicException: If refund cannot be rejected
        """
        if not rejection_reason or len(rejection_reason.strip()) < 10:
            raise ValidationException(
                "Rejection reason must be at least 10 characters"
            )

        refund = self.refund_repo.get_by_id(db, refund_id)
        if not refund:
            raise NotFoundException(f"Refund not found: {refund_id}")

        if refund.status != RefundStatus.PENDING:
            raise BusinessLogicException(
                f"Only pending refunds can be rejected. Current status: {refund.status.value}"
            )

        with LoggingContext(refund_id=str(refund_id)):
            updated = self.refund_repo.mark_rejected(
                db=db,
                refund=refund,
                approved_by=rejected_by,
                rejection_reason=rejection_reason,
            )

            logger.info(
                f"Refund rejected: {refund_id}",
                extra={
                    "refund_id": str(refund_id),
                    "rejected_by": str(rejected_by),
                    "reason": rejection_reason,
                },
            )

            return RefundResponse.model_validate(updated)

    def _initiate_gateway_refund(
        self,
        db: Session,
        payment: Any,
        refund: Any,
        gateway_service: Any,
    ) -> None:
        """
        Initiate refund with payment gateway.

        Args:
            db: Database session
            payment: Payment object
            refund: Refund object
            gateway_service: PaymentGatewayService instance
        """
        try:
            response = gateway_service.initiate_gateway_refund(
                db=db,
                payment_id=payment.id,
                amount=float(refund.refund_amount),
                reason=refund.refund_reason or "Customer requested refund",
                refund_id=refund.id,
            )

            # Update refund with gateway details
            self.refund_repo.update(
                db,
                refund,
                data={
                    "gateway_refund_id": response.get("refund_id"),
                    "gateway_response": response,
                },
            )

            logger.info(
                f"Gateway refund initiated for refund: {refund.id}",
                extra={
                    "refund_id": str(refund.id),
                    "gateway_refund_id": response.get("refund_id"),
                },
            )

        except Exception as e:
            logger.error(
                f"Gateway refund failed: {str(e)}",
                extra={"refund_id": str(refund.id)},
            )
            # Don't fail the entire refund, mark for manual processing
            self.refund_repo.update(
                db,
                refund,
                data={
                    "gateway_error": str(e),
                    "requires_manual_processing": True,
                },
            )

    def _create_refund_ledger_entry(
        self,
        db: Session,
        payment: Any,
        refund: Any,
    ) -> None:
        """Create ledger entry for refund."""
        self.ledger_repo.record_refund(
            db=db,
            payment_id=payment.id,
            refund_id=refund.id,
            amount=refund.refund_amount,
        )

        logger.debug(
            f"Ledger entry created for refund: {refund.id}",
            extra={"refund_id": str(refund.id)},
        )

    def _update_payment_after_refund(
        self,
        db: Session,
        payment: Any,
    ) -> None:
        """
        Update payment status after refund.

        If payment is fully refunded, mark as REFUNDED.
        If partially refunded, mark as PARTIALLY_REFUNDED.
        """
        refundable = self._calculate_refundable_amount(db, payment)

        if refundable <= Decimal("0.01"):  # Fully refunded (allowing for rounding)
            self.payment_repo.update(
                db,
                payment,
                data={"status": PaymentStatus.REFUNDED.value},
            )
            logger.info(f"Payment fully refunded: {payment.id}")
        else:
            # Partially refunded
            self.payment_repo.update(
                db,
                payment,
                data={"status": PaymentStatus.PARTIALLY_REFUNDED.value},
            )
            logger.info(f"Payment partially refunded: {payment.id}")

    # -------------------------------------------------------------------------
    # Listing & retrieval
    # -------------------------------------------------------------------------

    def get_refund(
        self,
        db: Session,
        refund_id: UUID,
    ) -> RefundResponse:
        """
        Retrieve a single refund by ID.

        Args:
            db: Database session
            refund_id: Refund UUID

        Returns:
            RefundResponse with refund details

        Raises:
            NotFoundException: If refund not found
        """
        obj = self.refund_repo.get_by_id(db, refund_id)
        if not obj:
            raise NotFoundException(f"Refund not found: {refund_id}")

        return RefundResponse.model_validate(obj)

    def list_refunds_for_payment(
        self,
        db: Session,
        payment_id: UUID,
    ) -> RefundList:
        """
        List all refunds for a payment.

        Args:
            db: Database session
            payment_id: Payment UUID

        Returns:
            RefundList with all refunds for the payment
        """
        objs = self.refund_repo.get_by_payment_id(db, payment_id)
        items = [RefundListItem.model_validate(o) for o in objs]

        total_refunded = sum(
            item.refund_amount
            for item in items
            if item.status in {RefundStatus.APPROVED, RefundStatus.COMPLETED}
        )

        return RefundList(
            payment_id=payment_id,
            refunds=items,
            total=len(items),
            total_refunded=total_refunded,
        )

    def list_refunds_for_student(
        self,
        db: Session,
        student_id: UUID,
        status: Optional[RefundStatus] = None,
    ) -> List[RefundListItem]:
        """
        List all refunds for a student.

        Args:
            db: Database session
            student_id: Student UUID
            status: Optional status filter

        Returns:
            List of RefundListItem objects
        """
        filters = {"student_id": student_id}
        if status:
            filters["status"] = status.value

        objs = self.refund_repo.list_refunds(db, filters=filters)
        return [RefundListItem.model_validate(o) for o in objs]

    def list_pending_refunds(
        self,
        db: Session,
        hostel_id: Optional[UUID] = None,
    ) -> List[RefundListItem]:
        """
        List all pending refunds, optionally filtered by hostel.

        Args:
            db: Database session
            hostel_id: Optional hostel filter

        Returns:
            List of pending RefundListItem objects
        """
        filters = {"status": RefundStatus.PENDING.value}
        if hostel_id:
            filters["hostel_id"] = hostel_id

        objs = self.refund_repo.list_refunds(db, filters=filters)
        return [RefundListItem.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Bulk operations
    # -------------------------------------------------------------------------

    def bulk_approve_refunds(
        self,
        db: Session,
        refund_ids: List[UUID],
        approved_by: UUID,
        approval_notes: Optional[str] = None,
        gateway_service: Optional[Any] = None,
    ) -> Dict[str, List[UUID]]:
        """
        Approve multiple refunds in bulk.

        Args:
            db: Database session
            refund_ids: List of refund UUIDs
            approved_by: UUID of approver
            approval_notes: Optional approval notes
            gateway_service: Optional gateway service for online refunds

        Returns:
            Dictionary with 'approved' and 'failed' refund IDs
        """
        results = {"approved": [], "failed": []}

        for refund_id in refund_ids:
            try:
                self.approve_refund(
                    db=db,
                    refund_id=refund_id,
                    approved_by=approved_by,
                    approval_notes=approval_notes,
                    gateway_service=gateway_service,
                )
                results["approved"].append(refund_id)
            except Exception as e:
                logger.warning(
                    f"Failed to approve refund {refund_id}: {str(e)}",
                    extra={"refund_id": str(refund_id)},
                )
                results["failed"].append(refund_id)

        logger.info(
            f"Bulk refund approval completed: "
            f"{len(results['approved'])} approved, {len(results['failed'])} failed"
        )

        return results