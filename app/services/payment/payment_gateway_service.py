# app/services/payment/payment_gateway_service.py
"""
Payment Gateway Service

Handles gateway-specific flows:
- Initiate online payments
- Process callbacks and webhooks
- Verify payments with the gateway
"""

from __future__ import annotations

from typing import Protocol, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.payment import (
    PaymentRepository,
    GatewayTransactionRepository,
)
from app.schemas.payment import (
    PaymentRequest,
    PaymentInitiation,
    GatewayRequest,
    GatewayResponse,
    GatewayCallback,
    GatewayWebhook,
    GatewayVerification,
)
from app.models.base.enums import PaymentStatus, PaymentMethod
from app.core.exceptions import ValidationException, BusinessLogicException
from app.core.logging import LoggingContext


class GatewayClient(Protocol):
    """
    Protocol for a gateway client implementation.

    Your real implementation should abide by this interface.
    """

    def initiate_payment(self, request: GatewayRequest) -> GatewayResponse: ...
    def verify_payment(self, verification: GatewayVerification) -> GatewayVerification: ...


class PaymentGatewayService:
    """
    High-level payment/gateway orchestration.

    Responsibilities:
    - Create Payment + GatewayTransaction records
    - Call external gateway client
    - Handle callbacks/webhooks and reconcile status
    """

    def __init__(
        self,
        payment_repo: PaymentRepository,
        gateway_tx_repo: GatewayTransactionRepository,
        gateway_client: GatewayClient,
    ) -> None:
        self.payment_repo = payment_repo
        self.gateway_tx_repo = gateway_tx_repo
        self.gateway_client = gateway_client

    # -------------------------------------------------------------------------
    # Initiation
    # -------------------------------------------------------------------------

    def initiate_online_payment(
        self,
        db: Session,
        request: PaymentRequest,
    ) -> PaymentInitiation:
        """
        Initiate an online payment:
        - Create Payment record (PENDING)
        - Create GatewayTransaction record
        - Call gateway to get payment URL/token
        """
        if request.payment_method not in {
            PaymentMethod.UPI,
            PaymentMethod.CARD,
            PaymentMethod.ONLINE,
            PaymentMethod.BANK_TRANSFER,
        }:
            raise ValidationException("Payment method is not online")

        payload = request.model_dump(exclude_none=True)
        payment = self.payment_repo.create_online_payment(db, payload)

        gateway_request = GatewayRequest(
            payment_id=payment.id,
            order_id=payment.payment_reference,
            amount=payment.amount,
            currency=payment.currency,
            customer_email=payment.payer_email or "",
            customer_phone=payment.payer_phone or "",
            description=payload.get("description", ""),
            metadata={"hostel_id": str(payment.hostel_id) if payment.hostel_id else None},
            success_callback_url=request.success_url,
            failure_callback_url=request.failure_url,
            cancel_url=request.cancel_url,
        )

        with LoggingContext(payment_id=str(payment.id)):
            response = self.gateway_client.initiate_payment(gateway_request)

        # Persist gateway transaction
        self.gateway_tx_repo.create_from_gateway_response(
            db=db,
            payment=payment,
            gateway_request=gateway_request,
            gateway_response=response,
        )

        # Return initiation info to client
        return PaymentInitiation(
            payment_id=payment.id,
            payment_reference=payment.payment_reference,
            amount=payment.amount,
            currency=payment.currency,
            gateway_name=response.gateway_name,
            gateway_order_id=response.gateway_order_id,
            gateway_key=response.gateway_public_key,
            checkout_url=response.checkout_url,
            gateway_options=response.gateway_options,
            expires_at=response.expires_at,
        )

    # -------------------------------------------------------------------------
    # Callback & webhook handling
    # -------------------------------------------------------------------------

    def handle_callback(
        self,
        db: Session,
        callback: GatewayCallback,
    ) -> None:
        """
        Handle browser callback after gateway payment attempt.

        This should:
        - Find matching GatewayTransaction
        - Update its status
        - Update corresponding Payment status
        """
        tx = self.gateway_tx_repo.get_by_gateway_payment_id(
            db,
            gateway_payment_id=callback.gateway_payment_id,
        )
        if not tx:
            raise ValidationException("Gateway transaction not found")

        payment = self.payment_repo.get_by_id(db, tx.payment_id)
        if not payment:
            raise ValidationException("Associated payment not found")

        self.gateway_tx_repo.update_from_callback(db, tx, callback)

        if callback.success:
            self.payment_repo.mark_paid(
                db,
                payment=payment,
                transaction_id=callback.gateway_payment_id,
            )
        else:
            self.payment_repo.mark_failed(
                db,
                payment=payment,
                failure_reason=callback.error_message or "Gateway callback failure",
            )

    def handle_webhook(
        self,
        db: Session,
        webhook: GatewayWebhook,
    ) -> None:
        """
        Handle server-side webhook from gateway.

        Logic is similar to callback but usually idempotent and robust
        against retries.
        """
        tx = self.gateway_tx_repo.get_by_gateway_payment_id(
            db,
            gateway_payment_id=webhook.gateway_payment_id,
        )
        if not tx:
            # Optionally: create a new tx record in reconciliation scenarios
            return

        payment = self.payment_repo.get_by_id(db, tx.payment_id)
        if not payment:
            return

        self.gateway_tx_repo.update_from_webhook(db, tx, webhook)

        if webhook.status == "success":
            self.payment_repo.mark_paid(
                db,
                payment=payment,
                transaction_id=webhook.gateway_payment_id,
            )
        elif webhook.status in ("failed", "cancelled"):
            self.payment_repo.mark_failed(
                db,
                payment=payment,
                failure_reason=webhook.error_message or "Gateway webhook failure",
            )

    # -------------------------------------------------------------------------
    # Verification
    # -------------------------------------------------------------------------

    def verify_payment_with_gateway(
        self,
        db: Session,
        payment_id: UUID,
    ) -> GatewayVerification:
        """
        Explicitly verify a payment with the gateway.
        """
        payment = self.payment_repo.get_by_id(db, payment_id)
        if not payment:
            raise ValidationException("Payment not found")

        tx = self.gateway_tx_repo.get_latest_for_payment(db, payment_id)
        if not tx:
            raise ValidationException("Gateway transaction not found")

        verification = GatewayVerification(
            gateway_order_id=tx.gateway_order_id,
            gateway_payment_id=tx.gateway_payment_id,
            is_verified=False,
            verification_status="pending",
            verified_amount=payment.amount,
            verified_currency=payment.currency,
            mapped_payment_status=payment.status,
            transaction_details={},
        )

        result = self.gateway_client.verify_payment(verification)

        # Update transaction and payment based on verification
        self.gateway_tx_repo.update_after_verification(db, tx, result)

        if result.is_verified and result.mapped_payment_status == PaymentStatus.COMPLETED:
            self.payment_repo.mark_paid(
                db,
                payment=payment,
                transaction_id=result.gateway_payment_id,
            )

        return result