# app/services/payment/payment_gateway_service.py
from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Callable, Optional, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import PaymentRepository
from app.repositories.core import UserRepository
from app.schemas.common.enums import PaymentStatus
from app.schemas.payment.payment_gateway import (
    GatewayRequest,
    GatewayResponse,
    GatewayWebhook,
    GatewayCallback,
    GatewayRefundRequest,
    GatewayRefundResponse,
)
from app.services.common import UnitOfWork, errors


class PaymentGatewayClient(Protocol):
    """
    Abstract payment gateway client.

    Implementations should wrap Razorpay/Stripe/Paytm SDKs.
    """

    def create_order(self, req: GatewayRequest) -> GatewayResponse: ...
    def process_refund(self, req: GatewayRefundRequest) -> GatewayRefundResponse: ...
    def verify_webhook(self, webhook: GatewayWebhook) -> bool: ...


class PaymentGatewayService:
    """
    Gateway-facing payment operations:

    - Build GatewayRequest from Payment + User data
    - Call PaymentGatewayClient to create orders
    - Handle gateway callbacks/webhooks to update Payment.status
    - Initiate and record refunds via gateway
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        client: PaymentGatewayClient,
    ) -> None:
        self._session_factory = session_factory
        self._client = client

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_payment_repo(self, uow: UnitOfWork) -> PaymentRepository:
        return uow.get_repo(PaymentRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Initiation
    # ------------------------------------------------------------------ #
    def build_gateway_request(self, payment_id: UUID, *, order_id: str, description: str,
                              callback_url: str, success_url: Optional[str] = None,
                              failure_url: Optional[str] = None) -> GatewayRequest:
        """
        Build a GatewayRequest from an existing Payment and its payer.
        """
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)
            user_repo = self._get_user_repo(uow)

            p = pay_repo.get(payment_id)
            if p is None:
                raise errors.NotFoundError(f"Payment {payment_id} not found")

            payer = user_repo.get(p.payer_id)
            if payer is None:
                raise errors.NotFoundError(f"Payer user {p.payer_id} not found")

            return GatewayRequest(
                payment_id=payment_id,
                amount=p.amount,
                currency=p.currency,
                customer_name=payer.full_name,
                customer_email=payer.email,
                customer_phone=getattr(payer, "phone", ""),
                order_id=order_id,
                description=description,
                callback_url=callback_url,
                success_url=success_url,
                failure_url=failure_url,
                metadata={},
            )

    def create_gateway_order(self, req: GatewayRequest) -> GatewayResponse:
        """
        Delegate to PaymentGatewayClient.create_order.
        """
        return self._client.create_order(req)

    # ------------------------------------------------------------------ #
    # Callbacks & webhooks
    # ------------------------------------------------------------------ #
    def handle_callback(self, cb: GatewayCallback) -> None:
        """
        Handle a synchronous callback (e.g. front-end redirect) from the gateway.

        - Updates payment_status based on cb.success.
        """
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)

            p = pay_repo.get(cb.payment_id)
            if p is None:
                raise errors.NotFoundError(f"Payment {cb.payment_id} not found")

            if cb.success:
                p.payment_status = PaymentStatus.COMPLETED  # type: ignore[attr-defined]
                p.paid_at = self._now()  # type: ignore[attr-defined]
            else:
                p.payment_status = PaymentStatus.FAILED  # type: ignore[attr-defined]
                p.failed_at = self._now()  # type: ignore[attr-defined]
                p.failure_reason = cb.error_message  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

    def handle_webhook(self, webhook: GatewayWebhook) -> None:
        """
        Handle gateway webhook:

        - Verify signature via client
        - Lookup Payment by gateway_order_id or gateway_payment_id (out of scope here)
        - Update Payment status as appropriate
        """
        if not self._client.verify_webhook(webhook):
            raise errors.ValidationError("Invalid webhook signature")

        # Application-specific mapping from gateway IDs to internal payment_id
        # is not implemented here; caller should extend this method.
        # This is a skeleton to update a known payment_id if present in metadata.

    # ------------------------------------------------------------------ #
    # Refunds
    # ------------------------------------------------------------------ #
    def request_refund(self, req: GatewayRefundRequest) -> GatewayRefundResponse:
        """
        Request a refund from the gateway.
        """
        return self._client.process_refund(req)