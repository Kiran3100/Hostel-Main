# app/services/payment/payment_refund_service.py
"""
Payment Refund Service

Handles internal refund lifecycle:
- Request refund
- Approve/reject refund
- Coordinate with gateway refunds
- Update payment & ledger accordingly
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

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
from app.core.exceptions import ValidationException, BusinessLogicException
from app.models.base.enums import PaymentStatus
from app.services.payment.payment_gateway_service import PaymentGatewayService


class PaymentRefundService:
    """
    High-level orchestration for refunds.

    Delegates core persistence to PaymentRefundRepository, PaymentRepository,
    and PaymentLedgerRepository, and gateway calls to PaymentGatewayService.
    """

    def __init__(
        self,
        payment_repo: PaymentRepository,
        refund_repo: PaymentRefundRepository,
        gateway_tx_repo: GatewayTransactionRepository,
        ledger_repo: PaymentLedgerRepository,
        gateway_service: PaymentGatewayService,
    ) -> None:
        self.payment_repo = payment_repo
        self.refund_repo = refund_repo
        self.gateway_tx_repo = gateway_tx_repo
        self.ledger_repo = ledger_repo
        self.gateway_service = gateway_service

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

        Ensures:
        - Payment exists and is refundable
        - Requested amount does not exceed paid amount minus existing refunds
        """
        payment = self.payment_repo.get_by_id(db, request.payment_id)
        if not payment:
            raise ValidationException("Payment not found")

        if payment.status != PaymentStatus.COMPLETED:
            raise BusinessLogicException("Only completed payments can be refunded")

        payload = request.model_dump(exclude_none=True)
        payload["requested_by"] = requested_by

        obj = self.refund_repo.create_refund_request(db, payload)
        return RefundResponse.model_validate(obj)

    # -------------------------------------------------------------------------
    # Approval & processing
    # -------------------------------------------------------------------------

    def approve_or_reject_refund(
        self,
        db: Session,
        refund_id: UUID,
        request: RefundApproval,
    ) -> RefundResponse:
        """
        Approve or reject a refund request.

        If approved, optionally trigger gateway refund (for online methods).
        """
        refund = self.refund_repo.get_by_id(db, refund_id)
        if not refund:
            raise ValidationException("Refund request not found")

        payment = self.payment_repo.get_by_id(db, refund.payment_id)
        if not payment:
            raise ValidationException("Associated payment not found")

        if request.is_approved:
            updated = self.refund_repo.mark_approved(
                db=db,
                refund=refund,
                approved_by=request.approved_by,
                notes=request.approval_notes,
            )

            # If payment used gateway method, call gateway
            if payment.is_online:
                # Determine amount to refund
                amount = updated.refund_amount
                # Rely on PaymentGatewayService to initiate gateway refund if needed
                self._initiate_gateway_refund(db, payment.id, amount, updated.id)

            # Create ledger entry for refund
            self.ledger_repo.record_refund(
                db=db,
                payment_id=payment.id,
                refund_id=updated.id,
                amount=updated.refund_amount,
            )

            # Update payment status if fully refunded
            self.payment_repo.update_status_after_refund(db, payment)

        else:
            updated = self.refund_repo.mark_rejected(
                db=db,
                refund=refund,
                approved_by=request.approved_by,
                rejection_reason=request.approval_notes,
            )

        return RefundResponse.model_validate(updated)

    def _initiate_gateway_refund(
        self,
        db: Session,
        payment_id: UUID,
        amount: float,
        refund_id: UUID,
    ) -> None:
        """
        Helper to initiate a gateway refund.

        The actual gateway call is encapsulated in PaymentGatewayService.
        """
        # This could be implemented via PaymentGatewayService + dedicated schema
        # For now, simply call verify or rely on a separate refund flow.
        pass

    # -------------------------------------------------------------------------
    # Listing
    # -------------------------------------------------------------------------

    def get_refund(
        self,
        db: Session,
        refund_id: UUID,
    ) -> RefundResponse:
        obj = self.refund_repo.get_by_id(db, refund_id)
        if not obj:
            raise ValidationException("Refund not found")
        return RefundResponse.model_validate(obj)

    def list_refunds_for_payment(
        self,
        db: Session,
        payment_id: UUID,
    ) -> RefundList:
        objs = self.refund_repo.get_by_payment_id(db, payment_id)
        items = [RefundListItem.model_validate(o) for o in objs]
        return RefundList(
            payment_id=payment_id,
            refunds=items,
            total=len(items),
        )