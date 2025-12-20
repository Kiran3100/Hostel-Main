"""
Payment Gateway Service.

Multi-gateway integration with support for Razorpay, Stripe, PayTM, PhonePe, etc.
Handles order creation, webhook verification, and transaction management.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import hashlib
import hmac
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    GatewayError,
    WebhookVerificationError,
)
from app.models.payment.payment import Payment
from app.models.payment.gateway_transaction import (
    GatewayProvider,
    GatewayTransaction,
    GatewayTransactionStatus,
    GatewayTransactionType,
)
from app.repositories.payment.gateway_transaction_repository import (
    GatewayTransactionRepository,
)
from app.repositories.payment.payment_repository import PaymentRepository


class PaymentGatewayService:
    """
    Service for payment gateway integrations.
    
    Supports multiple payment gateways with a unified interface.
    """

    def __init__(
        self,
        session: AsyncSession,
        gateway_repo: GatewayTransactionRepository,
        payment_repo: PaymentRepository,
    ):
        """Initialize gateway service."""
        self.session = session
        self.gateway_repo = gateway_repo
        self.payment_repo = payment_repo
        
        # Gateway configurations
        self.gateways = {
            "razorpay": RazorpayGateway(),
            "stripe": StripeGateway(),
            "paytm": PaytmGateway(),
            "phonepe": PhonePeGateway(),
        }

    # ==================== Order Creation ====================

    async def create_order(
        self,
        payment: Payment,
        gateway_name: str = "razorpay",
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create payment order with specified gateway.
        
        Args:
            payment: Payment record
            gateway_name: Gateway to use
            return_url: Success redirect URL
            cancel_url: Cancellation redirect URL
            
        Returns:
            Gateway order details
            {
                "gateway": "razorpay",
                "order_id": "order_xxx",
                "amount": 10000,
                "currency": "INR",
                "key": "rzp_xxx",
                "checkout_url": "https://...",
            }
        """
        # Get gateway instance
        gateway = self._get_gateway(gateway_name)
        
        # Create gateway order
        try:
            order_response = await gateway.create_order(
                amount=payment.amount,
                currency=payment.currency,
                receipt=payment.payment_reference,
                notes={
                    "payment_id": str(payment.id),
                    "student_id": str(payment.student_id),
                    "hostel_id": str(payment.hostel_id),
                },
            )
            
            # Create transaction record
            transaction = await self.gateway_repo.create_transaction(
                payment_id=payment.id,
                gateway_name=GatewayProvider(gateway_name),
                transaction_type=GatewayTransactionType.PAYMENT,
                transaction_amount=payment.amount,
                currency=payment.currency,
                request_payload=order_response.get("request"),
                metadata={
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                },
            )
            
            # Update transaction with gateway IDs
            await self.gateway_repo.update(
                transaction.id,
                {
                    "gateway_order_id": order_response["order_id"],
                    "response_payload": order_response,
                },
            )
            
            return {
                "gateway": gateway_name,
                "transaction_id": str(transaction.id),
                "order_id": order_response["order_id"],
                "amount": int(payment.amount * 100),  # In paise
                "currency": payment.currency,
                "key": gateway.get_public_key(),
                "checkout_url": order_response.get("checkout_url"),
                "return_url": return_url,
                "cancel_url": cancel_url,
            }
            
        except Exception as e:
            raise GatewayError(f"Failed to create {gateway_name} order: {str(e)}")

    # ==================== Payment Verification ====================

    async def verify_payment(
        self,
        gateway_name: str,
        payment_id: str,
        order_id: str,
        signature: str,
    ) -> dict[str, Any]:
        """
        Verify payment signature from gateway.
        
        Args:
            gateway_name: Gateway used
            payment_id: Gateway payment ID
            order_id: Gateway order ID
            signature: Payment signature
            
        Returns:
            Verification result
        """
        gateway = self._get_gateway(gateway_name)
        
        try:
            is_valid = await gateway.verify_signature(
                payment_id=payment_id,
                order_id=order_id,
                signature=signature,
            )
            
            if not is_valid:
                raise WebhookVerificationError("Invalid payment signature")
            
            # Get transaction
            transaction = await self.gateway_repo.find_by_gateway_order_id(order_id)
            if not transaction:
                raise GatewayError(f"Transaction not found for order: {order_id}")
            
            # Update transaction
            await self.gateway_repo.update_transaction_status(
                transaction_id=transaction.id,
                status=GatewayTransactionStatus.SUCCESS,
                gateway_payment_id=payment_id,
                response_payload={"signature": signature},
            )
            
            # Mark as verified
            await self.gateway_repo.mark_verified(
                transaction_id=transaction.id,
                verification_method="signature",
            )
            
            return {
                "verified": True,
                "transaction_id": str(transaction.id),
                "payment_id": str(transaction.payment_id),
            }
            
        except WebhookVerificationError:
            raise
        except Exception as e:
            raise GatewayError(f"Payment verification failed: {str(e)}")

    # ==================== Webhook Processing ====================

    async def process_webhook(
        self,
        gateway_name: str,
        webhook_payload: dict,
        webhook_signature: Optional[str] = None,
        webhook_headers: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Process webhook from payment gateway.
        
        Args:
            gateway_name: Gateway sending webhook
            webhook_payload: Webhook data
            webhook_signature: Webhook signature for verification
            webhook_headers: HTTP headers
            
        Returns:
            Processing result
        """
        gateway = self._get_gateway(gateway_name)
        
        # Verify webhook signature
        if webhook_signature:
            is_valid = await gateway.verify_webhook_signature(
                payload=webhook_payload,
                signature=webhook_signature,
                headers=webhook_headers,
            )
            
            if not is_valid:
                raise WebhookVerificationError("Invalid webhook signature")
        
        # Extract event type and data
        event_type = webhook_payload.get("event")
        entity = webhook_payload.get("payload", {}).get("payment", {}).get("entity", {})
        
        order_id = entity.get("order_id")
        payment_id = entity.get("id")
        status = entity.get("status")
        
        # Find transaction
        transaction = await self.gateway_repo.find_by_gateway_order_id(order_id)
        if not transaction:
            raise GatewayError(f"Transaction not found for order: {order_id}")
        
        # Record webhook
        await self.gateway_repo.record_webhook(
            transaction_id=transaction.id,
            webhook_payload=webhook_payload,
            webhook_event_type=event_type,
            webhook_signature=webhook_signature,
        )
        
        # Process based on event type
        result = await self._process_webhook_event(
            transaction=transaction,
            event_type=event_type,
            payment_id=payment_id,
            status=status,
            entity=entity,
        )
        
        return result

    async def _process_webhook_event(
        self,
        transaction: GatewayTransaction,
        event_type: str,
        payment_id: str,
        status: str,
        entity: dict,
    ) -> dict[str, Any]:
        """Process specific webhook event."""
        if event_type == "payment.captured":
            # Payment successful
            await self.gateway_repo.update_transaction_status(
                transaction_id=transaction.id,
                status=GatewayTransactionStatus.SUCCESS,
                gateway_payment_id=payment_id,
                response_payload=entity,
            )
            
            # Extract payment method details
            method = entity.get("method")
            if method == "card":
                await self.gateway_repo.update(
                    transaction.id,
                    {
                        "payment_method_used": "card",
                        "card_last4": entity.get("card", {}).get("last4"),
                        "card_network": entity.get("card", {}).get("network"),
                        "card_type": entity.get("card", {}).get("type"),
                    },
                )
            elif method == "upi":
                await self.gateway_repo.update(
                    transaction.id,
                    {
                        "payment_method_used": "upi",
                        "upi_id": entity.get("vpa"),
                    },
                )
            
            return {"status": "success", "action": "payment_captured"}
            
        elif event_type == "payment.failed":
            # Payment failed
            await self.gateway_repo.update_transaction_status(
                transaction_id=transaction.id,
                status=GatewayTransactionStatus.FAILED,
                gateway_payment_id=payment_id,
                error_code=entity.get("error_code"),
                error_message=entity.get("error_description"),
            )
            
            return {"status": "failed", "action": "payment_failed"}
            
        elif event_type == "refund.created":
            # Refund initiated
            await self.gateway_repo.update_transaction_status(
                transaction_id=transaction.id,
                status=GatewayTransactionStatus.REFUND_INITIATED,
            )
            
            return {"status": "refund_initiated", "action": "refund_created"}
            
        else:
            return {"status": "ignored", "action": "unknown_event"}

    # ==================== Refund Processing ====================

    async def process_refund(
        self,
        payment_id: UUID,
        refund_amount: Decimal,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Process refund through gateway.
        
        Args:
            payment_id: Payment to refund
            refund_amount: Amount to refund
            reason: Refund reason
            
        Returns:
            Refund result
        """
        # Get payment
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise GatewayError(f"Payment not found: {payment_id}")
        
        # Get original transaction
        transactions = await self.gateway_repo.find_by_payment(
            payment_id=payment_id,
            transaction_type=GatewayTransactionType.PAYMENT,
        )
        
        if not transactions:
            raise GatewayError("No gateway transaction found for payment")
        
        original_transaction = transactions[0]
        gateway_name = original_transaction.gateway_name.value
        
        # Get gateway
        gateway = self._get_gateway(gateway_name)
        
        # Process refund
        try:
            refund_response = await gateway.create_refund(
                payment_id=original_transaction.gateway_payment_id,
                amount=refund_amount,
                notes={"reason": reason},
            )
            
            # Create refund transaction
            refund_transaction = await self.gateway_repo.create_transaction(
                payment_id=payment_id,
                gateway_name=GatewayProvider(gateway_name),
                transaction_type=GatewayTransactionType.REFUND,
                transaction_amount=refund_amount,
                currency=payment.currency,
                request_payload={"refund_amount": float(refund_amount)},
            )
            
            # Update with gateway response
            await self.gateway_repo.update(
                refund_transaction.id,
                {
                    "gateway_refund_id": refund_response["refund_id"],
                    "transaction_status": GatewayTransactionStatus.REFUND_PENDING,
                    "response_payload": refund_response,
                },
            )
            
            return {
                "refund_id": refund_response["refund_id"],
                "transaction_id": str(refund_transaction.id),
                "status": "pending",
                "amount": float(refund_amount),
            }
            
        except Exception as e:
            raise GatewayError(f"Refund failed: {str(e)}")

    # ==================== Gateway Selection ====================

    def _get_gateway(self, gateway_name: str):
        """Get gateway instance by name."""
        gateway = self.gateways.get(gateway_name.lower())
        if not gateway:
            raise GatewayError(f"Unsupported gateway: {gateway_name}")
        return gateway

    async def get_best_gateway(
        self,
        amount: Decimal,
        payment_method: Optional[str] = None,
    ) -> str:
        """
        Select best gateway based on amount, fees, and availability.
        
        This is where you'd implement intelligent gateway routing.
        """
        # Simple example: use Razorpay for amounts > 10000, else Stripe
        if amount > Decimal("10000"):
            return "razorpay"
        return "stripe"


# ==================== Gateway Implementations ====================

class RazorpayGateway:
    """Razorpay payment gateway implementation."""
    
    def __init__(self):
        """Initialize Razorpay client."""
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        # In production: import razorpay; self.client = razorpay.Client(auth=(key_id, key_secret))

    async def create_order(
        self,
        amount: Decimal,
        currency: str,
        receipt: str,
        notes: dict,
    ) -> dict:
        """Create Razorpay order."""
        # Razorpay expects amount in paise (smallest currency unit)
        amount_paise = int(amount * 100)
        
        # In production, call actual Razorpay API
        # order = self.client.order.create({
        #     "amount": amount_paise,
        #     "currency": currency,
        #     "receipt": receipt,
        #     "notes": notes,
        # })
        
        # Mock response for now
        order = {
            "id": f"order_{datetime.utcnow().timestamp()}",
            "amount": amount_paise,
            "currency": currency,
            "receipt": receipt,
            "status": "created",
        }
        
        return {
            "order_id": order["id"],
            "amount": amount_paise,
            "currency": currency,
            "checkout_url": f"https://checkout.razorpay.com/{order['id']}",
        }

    async def verify_signature(
        self,
        payment_id: str,
        order_id: str,
        signature: str,
    ) -> bool:
        """Verify Razorpay payment signature."""
        # Generate expected signature
        message = f"{order_id}|{payment_id}"
        expected_signature = hmac.new(
            self.key_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)

    async def verify_webhook_signature(
        self,
        payload: dict,
        signature: str,
        headers: Optional[dict] = None,
    ) -> bool:
        """Verify Razorpay webhook signature."""
        # In production: use razorpay utility
        # return self.client.utility.verify_webhook_signature(
        #     json.dumps(payload), signature, self.webhook_secret
        # )
        return True  # Mock

    async def create_refund(
        self,
        payment_id: str,
        amount: Decimal,
        notes: dict,
    ) -> dict:
        """Create Razorpay refund."""
        amount_paise = int(amount * 100)
        
        # In production: self.client.payment.refund(payment_id, amount_paise, notes)
        
        return {
            "refund_id": f"rfnd_{datetime.utcnow().timestamp()}",
            "payment_id": payment_id,
            "amount": amount_paise,
            "status": "pending",
        }

    def get_public_key(self) -> str:
        """Get public API key for client-side."""
        return self.key_id


class StripeGateway:
    """Stripe payment gateway implementation."""
    
    def __init__(self):
        """Initialize Stripe client."""
        self.api_key = settings.STRIPE_API_KEY
        # In production: import stripe; stripe.api_key = self.api_key

    async def create_order(self, amount: Decimal, currency: str, receipt: str, notes: dict) -> dict:
        """Create Stripe payment intent."""
        # Mock implementation
        return {
            "order_id": f"pi_{datetime.utcnow().timestamp()}",
            "amount": int(amount * 100),
            "currency": currency,
            "client_secret": "pi_xxx_secret_xxx",
        }

    async def verify_signature(self, payment_id: str, order_id: str, signature: str) -> bool:
        """Verify Stripe signature."""
        return True  # Mock

    async def verify_webhook_signature(self, payload: dict, signature: str, headers: Optional[dict] = None) -> bool:
        """Verify Stripe webhook."""
        return True  # Mock

    async def create_refund(self, payment_id: str, amount: Decimal, notes: dict) -> dict:
        """Create Stripe refund."""
        return {
            "refund_id": f"re_{datetime.utcnow().timestamp()}",
            "payment_id": payment_id,
            "amount": int(amount * 100),
            "status": "pending",
        }

    def get_public_key(self) -> str:
        """Get publishable key."""
        return settings.STRIPE_PUBLISHABLE_KEY


class PaytmGateway:
    """PayTM gateway stub."""
    async def create_order(self, *args, **kwargs): raise NotImplementedError
    async def verify_signature(self, *args, **kwargs): raise NotImplementedError
    async def verify_webhook_signature(self, *args, **kwargs): raise NotImplementedError
    async def create_refund(self, *args, **kwargs): raise NotImplementedError
    def get_public_key(self): return ""


class PhonePeGateway:
    """PhonePe gateway stub."""
    async def create_order(self, *args, **kwargs): raise NotImplementedError
    async def verify_signature(self, *args, **kwargs): raise NotImplementedError
    async def verify_webhook_signature(self, *args, **kwargs): raise NotImplementedError
    async def create_refund(self, *args, **kwargs): raise NotImplementedError
    def get_public_key(self): return ""