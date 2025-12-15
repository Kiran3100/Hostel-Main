# --- File: app/schemas/payment/payment_gateway.py ---
"""
Payment gateway integration schemas.

This module defines schemas for payment gateway requests, responses,
webhooks, callbacks, and refund operations.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import PaymentStatus

__all__ = [
    "GatewayRequest",
    "GatewayResponse",
    "GatewayWebhook",
    "GatewayCallback",
    "GatewayRefundRequest",
    "GatewayRefundResponse",
    "GatewayVerification",
]


class GatewayRequest(BaseSchema):
    """
    Gateway payment initiation request.
    
    Data sent to payment gateway to initiate a transaction.
    """

    # Internal References
    payment_id: UUID = Field(
        ...,
        description="Internal payment ID",
    )
    order_id: str = Field(
        ...,
        max_length=100,
        description="Unique order identifier",
    )

    # Amount Details
    amount: Decimal = Field(
        ...,
        ge=0,
        description="Amount to charge",
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Currency code",
    )

    # Customer Details
    customer_name: str = Field(
        ...,
        max_length=100,
        description="Customer full name",
    )
    customer_email: str = Field(
        ...,
        max_length=100,
        description="Customer email",
    )
    customer_phone: str = Field(
        ...,
        max_length=15,
        description="Customer phone number",
    )

    # Payment Details
    description: str = Field(
        ...,
        max_length=500,
        description="Payment description",
    )
    notes: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata",
    )

    # Callback URLs
    callback_url: str = Field(
        ...,
        description="URL for payment callback",
    )
    cancel_url: Optional[str] = Field(
        None,
        description="URL if payment is cancelled",
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate amount."""
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v.quantize(Decimal("0.01"))

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate currency code."""
        return v.upper().strip()


class GatewayResponse(BaseSchema):
    """
    Gateway payment initiation response.
    
    Response received from payment gateway after initiating payment.
    """

    # Gateway Details
    gateway_name: str = Field(
        ...,
        description="Payment gateway name",
    )
    gateway_order_id: str = Field(
        ...,
        description="Gateway's order ID",
    )
    gateway_payment_id: Optional[str] = Field(
        None,
        description="Gateway's payment ID (if available)",
    )

    # Status
    status: str = Field(
        ...,
        description="Initial status from gateway",
    )
    is_successful: bool = Field(
        ...,
        description="Whether initiation was successful",
    )

    # Checkout Details
    checkout_url: Optional[str] = Field(
        None,
        description="URL to redirect user for payment",
    )
    checkout_token: Optional[str] = Field(
        None,
        description="Checkout session token",
    )

    # SDK Options
    sdk_options: Optional[Dict[str, Any]] = Field(
        None,
        description="Options for client-side SDK integration",
    )

    # Raw Response
    raw_response: Dict[str, Any] = Field(
        ...,
        description="Complete raw response from gateway",
    )

    # Timestamps
    initiated_at: datetime = Field(
        ...,
        description="When payment was initiated",
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="When checkout session expires",
    )

    # Error Details
    error_code: Optional[str] = Field(
        None,
        description="Error code if initiation failed",
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if initiation failed",
    )


class GatewayWebhook(BaseSchema):
    """
    Gateway webhook payload.
    
    Data received from payment gateway webhook notifications.
    """

    # Gateway Identification
    gateway_name: str = Field(
        ...,
        description="Payment gateway name",
    )
    event_type: str = Field(
        ...,
        description="Type of webhook event",
    )
    event_id: str = Field(
        ...,
        description="Unique event ID",
    )

    # Payment Details
    gateway_order_id: str = Field(
        ...,
        description="Gateway order ID",
    )
    gateway_payment_id: Optional[str] = Field(
        None,
        description="Gateway payment ID",
    )

    # Status
    payment_status: str = Field(
        ...,
        description="Payment status from gateway",
    )

    # Amount
    amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Payment amount",
    )
    currency: Optional[str] = Field(
        None,
        min_length=3,
        max_length=3,
        description="Currency code",
    )

    # Raw Payload
    raw_payload: Dict[str, Any] = Field(
        ...,
        description="Complete webhook payload",
    )

    # Signature (for verification)
    signature: Optional[str] = Field(
        None,
        description="Webhook signature for verification",
    )

    # Timestamp
    occurred_at: datetime = Field(
        ...,
        description="When event occurred",
    )
    received_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When webhook was received",
    )


class GatewayCallback(BaseSchema):
    """
    Gateway callback/redirect parameters.
    
    Parameters received when user is redirected back from payment gateway.
    """

    # Gateway Details
    gateway_order_id: str = Field(
        ...,
        description="Gateway order ID",
    )
    gateway_payment_id: Optional[str] = Field(
        None,
        description="Gateway payment ID",
    )

    # Payment Status
    status: str = Field(
        ...,
        description="Payment status",
    )
    is_successful: bool = Field(
        ...,
        description="Whether payment was successful",
    )

    # Transaction Details
    transaction_id: Optional[str] = Field(
        None,
        description="Transaction reference ID",
    )
    amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Paid amount",
    )

    # Signature (for verification)
    signature: Optional[str] = Field(
        None,
        description="Callback signature",
    )

    # Additional Parameters
    additional_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Any additional callback parameters",
    )


class GatewayRefundRequest(BaseSchema):
    """
    Gateway refund initiation request.
    
    Request to initiate a refund through payment gateway.
    """

    # Payment Reference
    payment_id: UUID = Field(
        ...,
        description="Internal payment ID",
    )
    gateway_payment_id: str = Field(
        ...,
        description="Gateway payment ID to refund",
    )

    # Refund Amount
    refund_amount: Decimal = Field(
        ...,
        ge=0,
        description="Amount to refund",
    )
    original_amount: Decimal = Field(
        ...,
        ge=0,
        description="Original payment amount",
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Currency code",
    )

    # Refund Details
    refund_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for refund",
    )
    is_partial: bool = Field(
        ...,
        description="Whether this is a partial refund",
    )

    # Notes
    notes: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional refund metadata",
    )

    @field_validator("refund_amount")
    @classmethod
    def validate_refund_amount(cls, v: Decimal) -> Decimal:
        """Validate refund amount."""
        if v <= 0:
            raise ValueError("Refund amount must be greater than zero")
        return v.quantize(Decimal("0.01"))

    @model_validator(mode="after")
    def validate_refund_limits(self) -> "GatewayRefundRequest":
        """Validate refund amount against original amount."""
        if self.refund_amount > self.original_amount:
            raise ValueError(
                f"Refund amount ({self.refund_amount}) cannot exceed "
                f"original amount ({self.original_amount})"
            )
        
        # Determine if partial based on amounts
        calculated_is_partial = self.refund_amount < self.original_amount
        if self.is_partial != calculated_is_partial:
            # Auto-correct is_partial flag
            self.is_partial = calculated_is_partial
        
        return self

    @field_validator("refund_reason")
    @classmethod
    def validate_refund_reason(cls, v: str) -> str:
        """Validate refund reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Refund reason must be at least 10 characters")
        return v


class GatewayRefundResponse(BaseSchema):
    """
    Gateway refund response.
    
    Response received from payment gateway after refund initiation.
    """

    # Gateway Details
    gateway_name: str = Field(
        ...,
        description="Payment gateway name",
    )
    gateway_refund_id: str = Field(
        ...,
        description="Gateway's refund ID",
    )
    gateway_payment_id: str = Field(
        ...,
        description="Original payment ID",
    )

    # Refund Status
    status: str = Field(
        ...,
        description="Refund status",
    )
    is_successful: bool = Field(
        ...,
        description="Whether refund initiation was successful",
    )

    # Amount
    refund_amount: Decimal = Field(
        ...,
        ge=0,
        description="Refunded amount",
    )
    currency: str = Field(
        ...,
        description="Currency code",
    )

    # Timing
    initiated_at: datetime = Field(
        ...,
        description="When refund was initiated",
    )
    processed_at: Optional[datetime] = Field(
        None,
        description="When refund was processed",
    )
    expected_completion: Optional[datetime] = Field(
        None,
        description="Expected refund completion time",
    )

    # Raw Response
    raw_response: Dict[str, Any] = Field(
        ...,
        description="Complete raw response from gateway",
    )

    # Error Details
    error_code: Optional[str] = Field(
        None,
        description="Error code if refund failed",
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if refund failed",
    )


class GatewayVerification(BaseSchema):
    """
    Gateway payment verification request/response.
    
    Used to verify payment status with gateway.
    """

    # Payment Reference
    gateway_order_id: str = Field(
        ...,
        description="Gateway order ID to verify",
    )
    gateway_payment_id: Optional[str] = Field(
        None,
        description="Gateway payment ID",
    )

    # Verification Result
    is_verified: bool = Field(
        ...,
        description="Whether payment is verified",
    )
    verification_status: str = Field(
        ...,
        description="Detailed verification status",
    )

    # Payment Details
    amount: Decimal = Field(
        ...,
        ge=0,
        description="Verified amount",
    )
    currency: str = Field(
        ...,
        description="Currency code",
    )
    payment_status: PaymentStatus = Field(
        ...,
        description="Current payment status",
    )

    # Transaction Details
    transaction_id: Optional[str] = Field(
        None,
        description="Transaction reference",
    )
    payment_method_used: Optional[str] = Field(
        None,
        description="Actual payment method used",
    )

    # Timestamps
    verified_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When verification was performed",
    )
    payment_completed_at: Optional[datetime] = Field(
        None,
        description="When payment was completed (if applicable)",
    )

    # Raw Data
    raw_verification_data: Dict[str, Any] = Field(
        ...,
        description="Complete verification response",
    )

    # Mismatch Detection
    has_discrepancy: bool = Field(
        False,
        description="Whether any discrepancy was detected",
    )
    discrepancy_details: Optional[str] = Field(
        None,
        description="Details of any discrepancy",
    )