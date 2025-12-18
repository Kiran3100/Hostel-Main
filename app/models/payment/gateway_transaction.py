# --- File: C:\Hostel-Main\app\models\payment\gateway_transaction.py ---
"""
Gateway transaction model.

Detailed tracking of payment gateway interactions including
requests, responses, webhooks, and transaction lifecycle.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
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


class GatewayTransactionType(str, Enum):
    """Gateway transaction type enum."""
    
    PAYMENT = "payment"
    REFUND = "refund"
    VERIFICATION = "verification"
    CAPTURE = "capture"
    AUTHORIZATION = "authorization"
    VOID = "void"


class GatewayProvider(str, Enum):
    """Payment gateway provider enum."""
    
    RAZORPAY = "razorpay"
    STRIPE = "stripe"
    PAYTM = "paytm"
    PHONEPE = "phonepe"
    CASHFREE = "cashfree"
    INSTAMOJO = "instamojo"
    PAYPAL = "paypal"
    MANUAL = "manual"


class GatewayTransaction(TimestampModel, UUIDMixin, SoftDeleteMixin):
    """
    Gateway transaction model for tracking payment gateway interactions.
    
    Records all communication with payment gateways including:
    - Payment initiation and processing
    - Refunds and reversals
    - Webhooks and callbacks
    - Verification and reconciliation
    """

    __tablename__ = "gateway_transactions"

    # ==================== Foreign Keys ====================
    payment_id: Mapped[UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ==================== Gateway Identification ====================
    gateway_name: Mapped[GatewayProvider] = mapped_column(
        SQLEnum(GatewayProvider, name="gateway_provider_enum", create_type=True),
        nullable=False,
        index=True,
        comment="Payment gateway provider name",
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
    
    gateway_refund_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Refund ID from gateway (if applicable)",
    )

    # ==================== Transaction Details ====================
    transaction_type: Mapped[GatewayTransactionType] = mapped_column(
        SQLEnum(GatewayTransactionType, name="gateway_transaction_type_enum", create_type=True),
        nullable=False,
        index=True,
        comment="Type of transaction",
    )
    
    transaction_status: Mapped[GatewayTransactionStatus] = mapped_column(
        SQLEnum(GatewayTransactionStatus, name="gateway_transaction_status_enum", create_type=True),
        nullable=False,
        index=True,
        comment="Current transaction status",
    )
    
    transaction_reference: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Internal transaction reference",
    )

    # ==================== Amount Details ====================
    transaction_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Transaction amount",
    )
    
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        comment="Currency code (ISO 4217)",
    )
    
    gateway_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Gateway processing fee",
    )
    
    tax_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Tax amount on gateway fee (GST)",
    )
    
    net_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Net amount after deducting fees",
    )

    # ==================== Request Data ====================
    request_payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Request payload sent to gateway",
    )
    
    request_headers: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="HTTP headers sent with request",
    )
    
    request_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Gateway API endpoint called",
    )
    
    request_method: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="HTTP method used (GET, POST, etc.)",
    )

    # ==================== Response Data ====================
    response_payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Response received from gateway",
    )
    
    response_headers: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="HTTP headers from response",
    )
    
    response_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="HTTP status code",
    )
    
    response_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Response time in milliseconds",
    )

    # ==================== Webhook Data ====================
    webhook_payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Webhook data received from gateway",
    )
    
    webhook_event_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Type of webhook event",
    )
    
    webhook_signature: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Webhook signature for verification",
    )
    
    webhook_received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When webhook was received",
    )

    # ==================== Callback Data ====================
    callback_payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Callback data from payment redirect",
    )
    
    callback_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Callback URL used",
    )
    
    callback_received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When callback was received",
    )

    # ==================== Payment Method Details ====================
    payment_method_used: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Actual payment method used (card, upi, netbanking, wallet)",
    )
    
    # Card Details (if applicable)
    card_last4: Mapped[str | None] = mapped_column(
        String(4),
        nullable=True,
        comment="Last 4 digits of card number",
    )
    
    card_first6: Mapped[str | None] = mapped_column(
        String(6),
        nullable=True,
        comment="First 6 digits of card (BIN)",
    )
    
    card_network: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Card network (Visa, Mastercard, RuPay, etc.)",
    )
    
    card_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Card type (credit, debit, prepaid)",
    )
    
    card_issuer: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Card issuing bank",
    )
    
    card_country: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        comment="Card issuing country code",
    )
    
    # Bank Details (if applicable)
    bank_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Bank name (for netbanking/upi)",
    )
    
    bank_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Bank code or IFSC",
    )
    
    # UPI Details (if applicable)
    upi_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="UPI ID used for payment",
    )
    
    upi_transaction_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="UPI transaction reference",
    )
    
    # Wallet Details (if applicable)
    wallet_name: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Wallet provider name (PayTM, PhonePe, etc.)",
    )
    
    wallet_transaction_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Wallet transaction ID",
    )

    # ==================== Customer Details ====================
    customer_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Customer name used in gateway",
    )
    
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
    
    customer_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="Customer IP address",
    )
    
    customer_user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Customer browser user agent",
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
        index=True,
        comment="Whether transaction is verified with gateway",
    )
    
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When transaction was verified",
    )
    
    verification_method: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Method used for verification (signature, api_call, etc.)",
    )

    # ==================== Timestamps ====================
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When transaction was initiated",
    )
    
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When processing started",
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
    
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When transaction was cancelled",
    )
    
    timeout_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When transaction timed out",
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
    
    error_source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Source of error (gateway, bank, network, etc.)",
    )
    
    error_reason: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Categorized error reason",
    )

    # ==================== Retry Information ====================
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of retry attempts",
    )
    
    last_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When last retry was attempted",
    )
    
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Maximum number of retries allowed",
    )
    
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When next retry should be attempted",
    )

    # ==================== Reconciliation ====================
    is_reconciled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether transaction is reconciled",
    )
    
    reconciled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When transaction was reconciled",
    )
    
    reconciliation_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Reconciliation reference number",
    )

    # ==================== Settlement ====================
    settlement_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Settlement batch ID from gateway",
    )
    
    settlement_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When settlement occurred",
    )
    
    settlement_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Actual settled amount",
    )
    
    settlement_utr: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Settlement UTR/reference number",
    )

    # ==================== Risk and Fraud ====================
    risk_score: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Risk score from gateway (0-100)",
    )
    
    fraud_detected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether fraud was detected",
    )
    
    fraud_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for fraud detection",
    )

    # ==================== Additional Data ====================
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
    
    raw_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Complete raw data from all interactions",
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
        Index("idx_gateway_payment_id_ref", "gateway_payment_id"),
        Index("idx_gateway_transaction_id", "gateway_transaction_id"),
        Index("idx_gateway_initiated_at", "initiated_at"),
        Index("idx_gateway_status", "transaction_status"),
        Index("idx_gateway_type", "transaction_type"),
        Index("idx_gateway_name_status", "gateway_name", "transaction_status"),
        Index("idx_gateway_name_type", "gateway_name", "transaction_type"),
        Index("idx_gateway_verified", "is_verified"),
        Index("idx_gateway_reconciled", "is_reconciled"),
        Index("idx_gateway_webhook_event", "webhook_event_type"),
        Index("idx_gateway_payment_method", "payment_method_used"),
        Index("idx_gateway_reference_lower", "lower(transaction_reference)"),
        {"comment": "Payment gateway transaction records and lifecycle tracking"},
    )

    # ==================== Properties ====================
    @property
    def is_success(self) -> bool:
        """Check if transaction was successful."""
        return self.transaction_status == GatewayTransactionStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        """Check if transaction failed."""
        return self.transaction_status == GatewayTransactionStatus.FAILED

    @property
    def is_pending(self) -> bool:
        """Check if transaction is pending."""
        return self.transaction_status in [
            GatewayTransactionStatus.INITIATED,
            GatewayTransactionStatus.PENDING,
            GatewayTransactionStatus.PROCESSING,
        ]

    @property
    def is_refund_transaction(self) -> bool:
        """Check if this is a refund transaction."""
        return self.transaction_type == GatewayTransactionType.REFUND

    @property
    def processing_duration_ms(self) -> int | None:
        """Calculate processing duration in milliseconds."""
        if self.completed_at and self.initiated_at:
            delta = self.completed_at - self.initiated_at
            return int(delta.total_seconds() * 1000)
        return None

    @property
    def can_retry(self) -> bool:
        """Check if transaction can be retried."""
        return (
            self.is_failed
            and self.retry_count < self.max_retries
        )

    @property
    def effective_amount(self) -> Decimal:
        """Get effective amount after fees."""
        if self.net_amount is not None:
            return self.net_amount
        return self.transaction_amount

    @property
    def total_fees(self) -> Decimal:
        """Calculate total fees (gateway fee + tax)."""
        total = Decimal("0.00")
        if self.gateway_fee:
            total += self.gateway_fee
        if self.tax_amount:
            total += self.tax_amount
        return total

    # ==================== Methods ====================
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<GatewayTransaction("
            f"id={self.id}, "
            f"gateway={self.gateway_name.value}, "
            f"order_id={self.gateway_order_id}, "
            f"type={self.transaction_type.value}, "
            f"status={self.transaction_status.value}"
            f")>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "payment_id": str(self.payment_id),
            "transaction_reference": self.transaction_reference,
            "gateway_name": self.gateway_name.value,
            "gateway_order_id": self.gateway_order_id,
            "gateway_payment_id": self.gateway_payment_id,
            "transaction_type": self.transaction_type.value,
            "transaction_status": self.transaction_status.value,
            "transaction_amount": float(self.transaction_amount),
            "currency": self.currency,
            "payment_method_used": self.payment_method_used,
            "initiated_at": self.initiated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat(),
        }

    def mark_verified(self) -> None:
        """Mark transaction as verified."""
        self.is_verified = True
        self.verified_at = datetime.utcnow()

    def mark_reconciled(self, reference: str | None = None) -> None:
        """Mark transaction as reconciled."""
        self.is_reconciled = True
        self.reconciled_at = datetime.utcnow()
        if reference:
            self.reconciliation_reference = reference

    def increment_retry(self) -> None:
        """Increment retry count and update timestamp."""
        self.retry_count += 1
        self.last_retry_at = datetime.utcnow()