# app/services/payment/payment_gateway_service.py
"""
Payment Gateway Service

Handles gateway-specific flows:
- Initiate online payments
- Process callbacks and webhooks
- Verify payments with the gateway
- Handle gateway-specific errors and retries
"""

from __future__ import annotations

from typing import Protocol, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

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
from app.core.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
    GatewayException,
)
from app.core.logging import LoggingContext, logger


class GatewayClient(Protocol):
    """
    Protocol for a gateway client implementation.

    All gateway integrations should implement this interface.
    """

    def initiate_payment(self, request: GatewayRequest) -> GatewayResponse:
        """Initiate a payment with the gateway."""
        ...

    def verify_payment(
        self, verification: GatewayVerification
    ) -> GatewayVerification:
        """Verify a payment with the gateway."""
        ...

    def refund_payment(
        self, payment_id: str, amount: float, reason: str
    ) -> Dict[str, Any]:
        """Initiate a refund with the gateway."""
        ...


class PaymentGatewayService:
    """
    High-level payment gateway orchestration.

    Responsibilities:
    - Create Payment + GatewayTransaction records
    - Call external gateway client with retry logic
    - Handle callbacks/webhooks and reconcile status
    - Manage idempotency for webhook processing
    - Verify payments and handle discrepancies
    """

    __slots__ = (
        "payment_repo",
        "gateway_tx_repo",
        "gateway_client",
        "_max_retries",
        "_retry_delay",
    )

    # Gateway-specific configuration
    ONLINE_PAYMENT_METHODS = {
        PaymentMethod.UPI,
        PaymentMethod.CARD,
        PaymentMethod.ONLINE,
        PaymentMethod.BANK_TRANSFER,
        PaymentMethod.NET_BANKING,
        PaymentMethod.WALLET,
    }

    def __init__(
        self,
        payment_repo: PaymentRepository,
        gateway_tx_repo: GatewayTransactionRepository,
        gateway_client: GatewayClient,
        max_retries: int = 3,
        retry_delay: int = 5,
    ) -> None:
        self.payment_repo = payment_repo
        self.gateway_tx_repo = gateway_tx_repo
        self.gateway_client = gateway_client
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    # -------------------------------------------------------------------------
    # Initiation
    # -------------------------------------------------------------------------

    def initiate_online_payment(
        self,
        db: Session,
        request: PaymentRequest,
    ) -> PaymentInitiation:
        """
        Initiate an online payment.

        Process:
        1. Validate payment method is online
        2. Create Payment record (INITIATED status)
        3. Create GatewayTransaction record
        4. Call gateway to get checkout URL/token
        5. Update transaction with gateway response
        6. Return initiation details to client

        Args:
            db: Database session
            request: Payment request details

        Returns:
            PaymentInitiation with checkout URL and gateway details

        Raises:
            ValidationException: If payment method is not online
            GatewayException: If gateway call fails
        """
        self._validate_online_payment_request(request)

        payload = request.model_dump(exclude_none=True)

        with LoggingContext(
            payment_method=request.payment_method.value,
            amount=float(request.amount),
        ):
            # Create payment record
            payment = self.payment_repo.create_online_payment(db, payload)
            logger.info(
                f"Online payment initiated: {payment.id}",
                extra={"payment_id": str(payment.id)},
            )

            try:
                # Prepare gateway request
                gateway_request = self._prepare_gateway_request(payment, request)

                # Call gateway with retry logic
                response = self._call_gateway_with_retry(gateway_request)

                # Persist gateway transaction
                gateway_tx = self.gateway_tx_repo.create_from_gateway_response(
                    db=db,
                    payment=payment,
                    gateway_request=gateway_request,
                    gateway_response=response,
                )

                logger.info(
                    f"Gateway transaction created: {gateway_tx.id}",
                    extra={
                        "payment_id": str(payment.id),
                        "gateway_order_id": response.gateway_order_id,
                    },
                )

                # Return initiation info
                return PaymentInitiation(
                    payment_id=payment.id,
                    payment_reference=payment.payment_reference,
                    amount=payment.amount,
                    currency=payment.currency,
                    gateway_name=response.gateway_name,
                    gateway_order_id=response.gateway_order_id,
                    gateway_key=response.gateway_public_key,
                    checkout_url=response.checkout_url,
                    gateway_options=response.gateway_options or {},
                    expires_at=response.expires_at or self._calculate_expiry(),
                )

            except Exception as e:
                # Mark payment as failed
                self.payment_repo.mark_failed(
                    db=db,
                    payment=payment,
                    failure_reason=f"Gateway initiation failed: {str(e)}",
                )
                logger.error(
                    f"Failed to initiate gateway payment: {str(e)}",
                    extra={"payment_id": str(payment.id)},
                )
                raise GatewayException(f"Failed to initiate payment: {str(e)}")

    def _validate_online_payment_request(self, request: PaymentRequest) -> None:
        """Validate that payment request is for online payment."""
        if request.payment_method not in self.ONLINE_PAYMENT_METHODS:
            raise ValidationException(
                f"Payment method {request.payment_method.value} is not supported for online payments"
            )

        if request.amount <= 0:
            raise ValidationException("Payment amount must be positive")

        if not request.success_url:
            raise ValidationException("Success URL is required for online payments")

        if not request.failure_url:
            raise ValidationException("Failure URL is required for online payments")

    def _prepare_gateway_request(
        self, payment: Any, request: PaymentRequest
    ) -> GatewayRequest:
        """Prepare gateway request from payment and request data."""
        return GatewayRequest(
            payment_id=payment.id,
            order_id=payment.payment_reference,
            amount=payment.amount,
            currency=payment.currency or "INR",
            customer_email=payment.payer_email or request.payer_email or "",
            customer_phone=payment.payer_phone or request.payer_phone or "",
            customer_name=request.payer_name or "",
            description=request.description or f"Payment for {payment.fee_type}",
            metadata={
                "hostel_id": str(payment.hostel_id) if payment.hostel_id else None,
                "student_id": str(payment.student_id) if payment.student_id else None,
                "fee_type": payment.fee_type,
            },
            success_callback_url=request.success_url,
            failure_callback_url=request.failure_url,
            cancel_url=request.cancel_url,
        )

    def _call_gateway_with_retry(
        self, request: GatewayRequest
    ) -> GatewayResponse:
        """
        Call gateway with retry logic for transient failures.

        Args:
            request: Gateway request

        Returns:
            Gateway response

        Raises:
            GatewayException: If all retries fail
        """
        last_exception = None

        for attempt in range(self._max_retries):
            try:
                response = self.gateway_client.initiate_payment(request)
                logger.debug(f"Gateway call successful on attempt {attempt + 1}")
                return response
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Gateway call failed on attempt {attempt + 1}: {str(e)}"
                )

                if attempt < self._max_retries - 1:
                    import time
                    time.sleep(self._retry_delay * (attempt + 1))  # Exponential backoff

        raise GatewayException(
            f"Gateway call failed after {self._max_retries} attempts: {str(last_exception)}"
        )

    def _calculate_expiry(self) -> datetime:
        """Calculate default payment expiry time (15 minutes from now)."""
        return datetime.utcnow() + timedelta(minutes=15)

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

        This is typically called from the frontend after redirect from gateway.

        Process:
        1. Find matching GatewayTransaction
        2. Update transaction status from callback
        3. Update corresponding Payment status
        4. Handle success/failure scenarios

        Args:
            db: Database session
            callback: Gateway callback data

        Raises:
            NotFoundException: If transaction not found
        """
        with LoggingContext(
            gateway_payment_id=callback.gateway_payment_id,
            callback_status="success" if callback.success else "failure",
        ):
            tx = self.gateway_tx_repo.get_by_gateway_payment_id(
                db, gateway_payment_id=callback.gateway_payment_id
            )

            if not tx:
                logger.error(
                    f"Gateway transaction not found for callback: {callback.gateway_payment_id}"
                )
                raise NotFoundException(
                    f"Gateway transaction not found: {callback.gateway_payment_id}"
                )

            payment = self.payment_repo.get_by_id(db, tx.payment_id)
            if not payment:
                logger.error(f"Associated payment not found: {tx.payment_id}")
                raise NotFoundException(f"Payment not found: {tx.payment_id}")

            # Update transaction from callback
            self.gateway_tx_repo.update_from_callback(db, tx, callback)

            # Update payment status
            if callback.success:
                self.payment_repo.mark_paid(
                    db=db,
                    payment=payment,
                    transaction_id=callback.gateway_payment_id,
                )
                logger.info(
                    f"Payment marked as paid from callback: {payment.id}",
                    extra={"payment_id": str(payment.id)},
                )
            else:
                self.payment_repo.mark_failed(
                    db=db,
                    payment=payment,
                    failure_reason=callback.error_message or "Gateway callback failure",
                )
                logger.warning(
                    f"Payment marked as failed from callback: {payment.id}",
                    extra={
                        "payment_id": str(payment.id),
                        "error": callback.error_message,
                    },
                )

    def handle_webhook(
        self,
        db: Session,
        webhook: GatewayWebhook,
    ) -> None:
        """
        Handle server-side webhook from gateway.

        Webhooks are more reliable than callbacks and should be the source of truth.
        This method is idempotent and can handle duplicate webhook deliveries.

        Process:
        1. Check if webhook already processed (idempotency)
        2. Find matching GatewayTransaction
        3. Update transaction status from webhook
        4. Update corresponding Payment status
        5. Mark webhook as processed

        Args:
            db: Database session
            webhook: Gateway webhook data
        """
        with LoggingContext(
            gateway_payment_id=webhook.gateway_payment_id,
            webhook_status=webhook.status,
        ):
            # Check idempotency
            if self._is_webhook_processed(db, webhook):
                logger.info(
                    f"Webhook already processed: {webhook.gateway_payment_id}",
                    extra={"webhook_id": webhook.webhook_id},
                )
                return

            tx = self.gateway_tx_repo.get_by_gateway_payment_id(
                db, gateway_payment_id=webhook.gateway_payment_id
            )

            if not tx:
                logger.warning(
                    f"Gateway transaction not found for webhook: {webhook.gateway_payment_id}"
                )
                # In reconciliation scenarios, this might be expected
                return

            payment = self.payment_repo.get_by_id(db, tx.payment_id)
            if not payment:
                logger.warning(f"Associated payment not found: {tx.payment_id}")
                return

            # Update transaction from webhook
            self.gateway_tx_repo.update_from_webhook(db, tx, webhook)

            # Update payment status based on webhook
            if webhook.status == "success":
                self.payment_repo.mark_paid(
                    db=db,
                    payment=payment,
                    transaction_id=webhook.gateway_payment_id,
                )
                logger.info(
                    f"Payment marked as paid from webhook: {payment.id}",
                    extra={"payment_id": str(payment.id)},
                )
            elif webhook.status in ("failed", "cancelled"):
                self.payment_repo.mark_failed(
                    db=db,
                    payment=payment,
                    failure_reason=webhook.error_message or "Gateway webhook failure",
                )
                logger.info(
                    f"Payment marked as {webhook.status} from webhook: {payment.id}",
                    extra={"payment_id": str(payment.id)},
                )

            # Mark webhook as processed
            self._mark_webhook_processed(db, webhook)

    def _is_webhook_processed(
        self, db: Session, webhook: GatewayWebhook
    ) -> bool:
        """Check if webhook has already been processed (idempotency check)."""
        if not webhook.webhook_id:
            return False

        # This would check a webhook_logs table or similar
        # For now, check if transaction is already in final state
        tx = self.gateway_tx_repo.get_by_gateway_payment_id(
            db, gateway_payment_id=webhook.gateway_payment_id
        )

        if not tx:
            return False

        # If transaction is already in a final state matching webhook, consider it processed
        final_statuses = {"success", "failed", "cancelled"}
        return tx.status in final_statuses and tx.status == webhook.status

    def _mark_webhook_processed(
        self, db: Session, webhook: GatewayWebhook
    ) -> None:
        """Mark webhook as processed to prevent duplicate processing."""
        # This would insert into webhook_logs table
        # Implementation depends on your webhook tracking requirements
        pass

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

        This is useful for:
        - Reconciliation
        - Confirming payment status when callback/webhook is missing
        - Resolving discrepancies

        Args:
            db: Database session
            payment_id: Payment UUID

        Returns:
            GatewayVerification with verification results

        Raises:
            NotFoundException: If payment or transaction not found
            GatewayException: If verification fails
        """
        payment = self.payment_repo.get_by_id(db, payment_id)
        if not payment:
            raise NotFoundException(f"Payment not found: {payment_id}")

        tx = self.gateway_tx_repo.get_latest_for_payment(db, payment_id)
        if not tx:
            raise NotFoundException(
                f"Gateway transaction not found for payment: {payment_id}"
            )

        with LoggingContext(
            payment_id=str(payment_id),
            gateway_order_id=tx.gateway_order_id,
        ):
            verification = GatewayVerification(
                gateway_order_id=tx.gateway_order_id,
                gateway_payment_id=tx.gateway_payment_id,
                is_verified=False,
                verification_status="pending",
                verified_amount=payment.amount,
                verified_currency=payment.currency or "INR",
                mapped_payment_status=payment.status,
                transaction_details={},
            )

            try:
                # Call gateway for verification
                result = self.gateway_client.verify_payment(verification)

                # Update transaction with verification results
                self.gateway_tx_repo.update_after_verification(db, tx, result)

                # Update payment if verification confirms different status
                if (
                    result.is_verified
                    and result.mapped_payment_status == PaymentStatus.COMPLETED
                    and payment.status != PaymentStatus.COMPLETED
                ):
                    self.payment_repo.mark_paid(
                        db=db,
                        payment=payment,
                        transaction_id=result.gateway_payment_id,
                    )
                    logger.info(
                        f"Payment status corrected after verification: {payment_id}",
                        extra={"payment_id": str(payment_id)},
                    )

                return result

            except Exception as e:
                logger.error(
                    f"Gateway verification failed: {str(e)}",
                    extra={"payment_id": str(payment_id)},
                )
                raise GatewayException(f"Payment verification failed: {str(e)}")

    def verify_payment_by_reference(
        self,
        db: Session,
        payment_reference: str,
    ) -> GatewayVerification:
        """
        Verify a payment by its reference number.

        Args:
            db: Database session
            payment_reference: Payment reference

        Returns:
            GatewayVerification with verification results
        """
        payment = self.payment_repo.get_by_reference(db, payment_reference)
        if not payment:
            raise NotFoundException(
                f"Payment not found with reference: {payment_reference}"
            )

        return self.verify_payment_with_gateway(db, payment.id)

    # -------------------------------------------------------------------------
    # Refund initiation
    # -------------------------------------------------------------------------

    def initiate_gateway_refund(
        self,
        db: Session,
        payment_id: UUID,
        amount: float,
        reason: str,
        refund_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Initiate a refund with the payment gateway.

        Args:
            db: Database session
            payment_id: Payment UUID
            amount: Refund amount
            reason: Refund reason
            refund_id: Optional refund record ID

        Returns:
            Gateway refund response

        Raises:
            NotFoundException: If payment or transaction not found
            GatewayException: If refund initiation fails
        """
        payment = self.payment_repo.get_by_id(db, payment_id)
        if not payment:
            raise NotFoundException(f"Payment not found: {payment_id}")

        tx = self.gateway_tx_repo.get_latest_for_payment(db, payment_id)
        if not tx or not tx.gateway_payment_id:
            raise NotFoundException(
                f"Gateway transaction not found for payment: {payment_id}"
            )

        with LoggingContext(
            payment_id=str(payment_id),
            refund_amount=amount,
        ):
            try:
                response = self.gateway_client.refund_payment(
                    payment_id=tx.gateway_payment_id,
                    amount=amount,
                    reason=reason,
                )

                logger.info(
                    f"Gateway refund initiated: {payment_id}",
                    extra={
                        "payment_id": str(payment_id),
                        "refund_id": str(refund_id) if refund_id else None,
                        "amount": amount,
                    },
                )

                return response

            except Exception as e:
                logger.error(
                    f"Gateway refund failed: {str(e)}",
                    extra={"payment_id": str(payment_id)},
                )
                raise GatewayException(f"Refund initiation failed: {str(e)}")