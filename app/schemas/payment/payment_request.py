# --- File: app/schemas/payment/payment_request.py ---
"""
Payment request schemas for initiating payments.

This module defines schemas for various types of payment requests
including online payments, manual payments, and bulk operations.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Union
from uuid import UUID

from pydantic import Field, HttpUrl, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import PaymentMethod, PaymentType

__all__ = [
    "PaymentRequest",
    "PaymentInitiation",
    "ManualPaymentRequest",
    "BulkPaymentRequest",
    "SinglePaymentRecord",
]


class PaymentRequest(BaseCreateSchema):
    """
    Online payment request schema.
    
    Used to initiate online payments through payment gateways.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )
    student_id: Union[UUID, None] = Field(
        None,
        description="Student ID (for recurring fee payments)",
    )
    booking_id: Union[UUID, None] = Field(
        None,
        description="Booking ID (for booking-related payments)",
    )

    payment_type: PaymentType = Field(
        ...,
        description="Type of payment",
    )
    amount: Decimal = Field(
        ...,
        ge=0,
        description="Amount to pay",
    )

    # Payment Period (for recurring fees)
    payment_period_start: Union[Date, None] = Field(
        None,
        description="Period start Date",
    )
    payment_period_end: Union[Date, None] = Field(
        None,
        description="Period end Date",
    )

    # Payment Gateway Selection
    payment_method: PaymentMethod = Field(
        PaymentMethod.PAYMENT_GATEWAY,
        description="Payment method (must be online for this request type)",
    )
    payment_gateway: str = Field(
        "razorpay",
        pattern=r"^(razorpay|stripe|paytm|phonepe)$",
        description="Preferred payment gateway",
    )

    # Return URLs
    success_url: Union[HttpUrl, None] = Field(
        None,
        description="URL to redirect on successful payment",
    )
    failure_url: Union[HttpUrl, None] = Field(
        None,
        description="URL to redirect on payment failure",
    )
    cancel_url: Union[HttpUrl, None] = Field(
        None,
        description="URL to redirect if payment is cancelled",
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate payment amount."""
        if v <= 0:
            raise ValueError("Payment amount must be greater than zero")
        
        # Minimum online payment amount (to avoid gateway fees being higher than payment)
        min_amount = Decimal("1.00")
        if v < min_amount:
            raise ValueError(
                f"Minimum payment amount for online payments is ₹{min_amount}"
            )
        
        return v.quantize(Decimal("0.01"))

    @model_validator(mode="after")
    def validate_payment_method(self) -> "PaymentRequest":
        """Ensure payment method is suitable for online payment."""
        online_methods = [
            PaymentMethod.PAYMENT_GATEWAY,
            PaymentMethod.UPI,
            PaymentMethod.CARD,
            PaymentMethod.NET_BANKING,
        ]
        
        if self.payment_method not in online_methods:
            raise ValueError(
                f"Payment method {self.payment_method} not supported for online payments. "
                f"Use ManualPaymentRequest for offline payments."
            )
        
        return self

    @model_validator(mode="after")
    def validate_entity_reference(self) -> "PaymentRequest":
        """Ensure at least student_id or booking_id is provided."""
        if not self.student_id and not self.booking_id:
            raise ValueError(
                "Either student_id or booking_id must be provided"
            )
        
        return self


class PaymentInitiation(BaseSchema):
    """
    Payment initiation response from gateway.
    
    Contains all information needed to complete payment on client side.
    """

    payment_id: UUID = Field(
        ...,
        description="Internal payment ID",
    )
    payment_reference: str = Field(
        ...,
        description="Human-readable payment reference",
    )

    amount: Decimal = Field(
        ...,
        ge=0,
        description="Payment amount",
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Currency code",
    )

    # Gateway Details
    gateway: str = Field(
        ...,
        description="Payment gateway being used",
    )
    gateway_order_id: str = Field(
        ...,
        description="Order ID from payment gateway",
    )
    gateway_key: str = Field(
        ...,
        description="Gateway API key for client-side integration",
    )

    # Checkout Information
    checkout_url: Union[HttpUrl, None] = Field(
        None,
        description="Direct checkout URL (for redirect-based flows)",
    )
    checkout_token: Union[str, None] = Field(
        None,
        description="Checkout session token",
    )

    # Gateway-Specific Options
    gateway_options: dict = Field(
        ...,
        description="Gateway-specific configuration for client SDK",
    )

    # Expiry
    expires_at: Union[datetime, None] = Field(
        None,
        description="When this payment initiation expires",
    )


class ManualPaymentRequest(BaseCreateSchema):
    """
    Manual payment recording schema.
    
    Used for recording offline payments (cash, cheque, bank transfer)
    collected by hostel staff.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )
    student_id: UUID = Field(
        ...,
        description="Student ID",
    )

    payment_type: PaymentType = Field(
        ...,
        description="Type of payment",
    )
    amount: Decimal = Field(
        ...,
        ge=0,
        description="Payment amount",
    )

    payment_method: PaymentMethod = Field(
        ...,
        description="Payment method (cash, cheque, bank_transfer)",
    )

    # Cheque Details
    cheque_number: Union[str, None] = Field(
        None,
        max_length=50,
        description="Cheque number (if payment_method is cheque)",
    )
    cheque_date: Union[Date, None] = Field(
        None,
        description="Cheque Date",
    )
    bank_name: Union[str, None] = Field(
        None,
        max_length=100,
        description="Bank name (for cheque/bank transfer)",
    )

    # Bank Transfer Details
    transaction_reference: Union[str, None] = Field(
        None,
        max_length=100,
        description="Bank transaction reference number",
    )
    transfer_date: Union[Date, None] = Field(
        None,
        description="Date of bank transfer",
    )

    # Payment Period
    payment_period_start: Union[Date, None] = Field(
        None,
        description="Period start Date",
    )
    payment_period_end: Union[Date, None] = Field(
        None,
        description="Period end Date",
    )

    # Collection Details
    collected_by: UUID = Field(
        ...,
        description="Staff member who collected the payment",
    )
    collection_date: Date = Field(
        ...,
        description="Date payment was collected",
    )

    notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Additional notes",
    )

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v: PaymentMethod) -> PaymentMethod:
        """Ensure payment method is suitable for manual recording."""
        manual_methods = [
            PaymentMethod.CASH,
            PaymentMethod.CHEQUE,
            PaymentMethod.BANK_TRANSFER,
        ]
        
        if v not in manual_methods:
            raise ValueError(
                f"Payment method {v} not supported for manual recording. "
                f"Supported: {', '.join(m.value for m in manual_methods)}"
            )
        
        return v

    @model_validator(mode="after")
    def validate_cheque_details(self) -> "ManualPaymentRequest":
        """Validate cheque details if payment method is cheque."""
        if self.payment_method == PaymentMethod.CHEQUE:
            if not self.cheque_number:
                raise ValueError("cheque_number is required for cheque payments")
            
            if not self.cheque_date:
                raise ValueError("cheque_date is required for cheque payments")
            
            # Validate cheque Date is not in the future
            if self.cheque_date > Date.today():
                raise ValueError("Cheque Date cannot be in the future")
        
        return self

    @model_validator(mode="after")
    def validate_bank_transfer_details(self) -> "ManualPaymentRequest":
        """Validate bank transfer details if applicable."""
        if self.payment_method == PaymentMethod.BANK_TRANSFER:
            if not self.transaction_reference:
                raise ValueError(
                    "transaction_reference is required for bank transfers"
                )
            
            if not self.transfer_date:
                raise ValueError("transfer_date is required for bank transfers")
        
        return self

    @field_validator("collection_date")
    @classmethod
    def validate_collection_date(cls, v: Date) -> Date:
        """Validate collection Date."""
        if v > Date.today():
            raise ValueError("Collection Date cannot be in the future")
        
        # Warn if collection Date is too old
        days_ago = (Date.today() - v).days
        if days_ago > 90:
            # Log warning - in production, use proper logging
            pass
        
        return v


class SinglePaymentRecord(BaseSchema):
    """
    Single payment record in bulk operation.
    
    Minimal schema for individual payment within bulk request.
    """

    student_id: UUID = Field(
        ...,
        description="Student ID",
    )
    payment_type: PaymentType = Field(
        ...,
        description="Payment type",
    )
    amount: Decimal = Field(
        ...,
        ge=0,
        description="Payment amount",
    )
    payment_method: PaymentMethod = Field(
        ...,
        description="Payment method",
    )

    # Optional Fields
    transaction_reference: Union[str, None] = Field(
        None,
        max_length=100,
        description="Transaction reference",
    )
    notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Payment notes",
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate amount."""
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v.quantize(Decimal("0.01"))


class BulkPaymentRequest(BaseCreateSchema):
    """
    Record multiple payments in one operation.
    
    Used for batch recording of offline payments.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel ID for all payments",
    )
    payments: List[SinglePaymentRecord] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of payments to record (max 100)",
    )

    collected_by: UUID = Field(
        ...,
        description="Staff member who collected all payments",
    )
    collection_date: Date = Field(
        ...,
        description="Date all payments were collected",
    )

    @field_validator("payments")
    @classmethod
    def validate_payments(cls, v: List[SinglePaymentRecord]) -> List[SinglePaymentRecord]:
        """Validate payments list."""
        if len(v) == 0:
            raise ValueError("At least one payment is required")
        
        if len(v) > 100:
            raise ValueError("Maximum 100 payments allowed per bulk operation")
        
        # Check for duplicate student IDs
        student_ids = [p.student_id for p in v]
        if len(student_ids) != len(set(student_ids)):
            raise ValueError(
                "Duplicate student IDs found. Each student can only appear once per bulk operation."
            )
        
        return v

    @field_validator("collection_date")
    @classmethod
    def validate_collection_date(cls, v: Date) -> Date:
        """Validate collection Date."""
        if v > Date.today():
            raise ValueError("Collection Date cannot be in the future")
        return v