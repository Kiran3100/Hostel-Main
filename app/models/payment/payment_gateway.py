# --- File: C:\Hostel-Main\app\models\payment\payment_gateway.py ---
"""
Payment gateway transaction model.

Tracks interactions with payment gateways for online payment processing.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.payment.payment import Payment


class GatewayTransactionStatus(str, Enum):
    """Gateway transaction status enum."""
    
    INITIATED = "initiated"
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    REFUND_INITIATED = "refund_initiated"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"
    REFUND_FAILED = "refund_failed"


class GatewayTransaction(TimestampModel, UUIDMixin, SoftDeleteMixin):
    """
    Gateway transaction model for tracking payment gateway interactions.
    
    Records all communication with payment gateways including
    requests, responses, webhooks, and callbacks.
    """

    __tablename__ = "gateway_transactions"

    # ==================== Foreign Keys ====================
    payment_id: Mapped[UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ==================== Gateway Details ====================
    gateway_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Payment gateway name (razorpay, stripe, paytm, etc.)",
    )
    
    gateway_order_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Order ID from payment gateway",
    )
    
    gateway_payment_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Payment ID from gateway (after payment attempt)",
    )
    
    gateway_transaction_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
        comment="Unique transaction ID from gateway",
    )

    # ==================== Transaction Details ====================
    transaction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of transaction (payment, refund, verification)",
    )
    
    transaction_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Current transaction status",
    )

    # ==================== Amount Details ====================
    transaction_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Transaction amount",
    )
    
    gateway_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Gateway processing fee",
    )
    
    tax_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Tax amount on gateway fee",
    )
    
    net_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Net amount after deducting fees",
    )

    # ==================== Request/Response Data ====================
    request_payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Request payload sent to gateway",
    )
    
    response_payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Response received from gateway",
    )
    
    webhook_payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Webhook data received from gateway",
    )
    
    callback_payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Callback data from payment redirect",
    )

    # ==================== Payment Method Details ====================
    payment_method_used: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Actual payment method used (card, upi, netbanking, etc.)",
    )
    
    card_last4: Mapped[str | None] = mapped_column(
        String(4),
        nullable=True,
        comment="Last 4 digits of card (if card payment)",
    )
    
    card_network: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Card network (Visa, Mastercard, etc.)",
    )
    
    bank_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Bank name (for netbanking/upi)",
    )
    
    upi_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="UPI ID used for payment",
    )

    # ==================== Verification ====================
    signature: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Gateway signature for verification",
    )
    
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether transaction is verified with gateway",
    )
    
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When transaction was verified",
    )

    # ==================== Timestamps ====================
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When transaction was initiated",
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When transaction was completed",
    )
    
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When transaction failed",
    )
    
    webhook_received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When webhook was received",
    )

    # ==================== Error Details ====================
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Error code from gateway",
    )
    
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message from gateway",
    )
    
    error_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed error description",
    )

    # ==================== Retry Information ====================
    retry_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Number of retry attempts",
    )
    
    last_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When last retry was attempted",
    )

    # ==================== Additional Data ====================
    customer_email: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Customer email used in gateway",
    )
    
    customer_phone: Mapped[str | None] = mapped_column(
        String(15),
        nullable=True,
        comment="Customer phone used in gateway",
    )
    
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes",
    )
    
    metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata",
    )

    # ==================== Relationships ====================
    payment: Mapped["Payment"] = relationship(
        "Payment",
        back_populates="gateway_transactions",
        lazy="selectin",
    )

    # ==================== Indexes ====================
    __table_args__ = (
        Index("idx_gateway_payment_id", "payment_id", "transaction_status"),
        Index("idx_gateway_order_id", "gateway_order_id"),
        Index("idx_gateway_initiated_at", "initiated_at"),
        Index("idx_gateway_status", "transaction_status"),
        Index("idx_gateway_name_status", "gateway_name", "transaction_status"),
        {"comment": "Payment gateway transaction records"},
    )

    # ==================== Methods ====================
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<GatewayTransaction("
            f"id={self.id}, "
            f"gateway={self.gateway_name}, "
            f"order_id={self.gateway_order_id}, "
            f"status={self.transaction_status}"
            f")>"
        )