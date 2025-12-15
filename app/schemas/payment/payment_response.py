# --- File: app/schemas/payment/payment_response.py ---
"""
Payment response schemas for API responses.

This module defines response schemas for payment data including
basic responses, detailed information, receipts, and summaries.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import Field, computed_field

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import PaymentMethod, PaymentStatus, PaymentType

__all__ = [
    "PaymentResponse",
    "PaymentDetail",
    "PaymentReceipt",
    "PaymentListItem",
    "PaymentSummary",
    "PaymentAnalytics",
]


class PaymentResponse(BaseResponseSchema):
    """
    Standard payment response schema.
    
    Contains core payment information for API responses.
    """

    payment_reference: str = Field(
        ...,
        description="Unique payment reference number",
    )
    transaction_id: Optional[str] = Field(
        None,
        description="External transaction ID",
    )

    # Payer Information
    payer_id: UUID = Field(
        ...,
        description="Payer user ID",
    )
    payer_name: str = Field(
        ...,
        description="Payer full name",
    )

    # Hostel Information
    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )

    # Payment Details
    payment_type: PaymentType = Field(
        ...,
        description="Type of payment",
    )
    amount: Decimal = Field(
        ...,
        ge=0,
        description="Payment amount",
    )
    currency: str = Field(
        ...,
        description="Currency code",
    )

    # Payment Method
    payment_method: PaymentMethod = Field(
        ...,
        description="Payment method used",
    )
    payment_status: PaymentStatus = Field(
        ...,
        description="Current payment status",
    )

    # Timestamps
    paid_at: Optional[datetime] = Field(
        None,
        description="When payment was completed",
    )
    due_date: Optional[Date] = Field(
        None,
        description="Payment due Date",
    )
    is_overdue: bool = Field(
        ...,
        description="Whether payment is overdue",
    )

    # Receipt
    receipt_number: Optional[str] = Field(
        None,
        description="Receipt number if generated",
    )
    receipt_url: Optional[str] = Field(
        None,
        description="URL to download receipt",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def amount_display(self) -> str:
        """Get formatted amount for display."""
        return f"{self.currency} {self.amount:,.2f}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_badge_color(self) -> str:
        """Get color code for status badge."""
        color_map = {
            PaymentStatus.PENDING: "#FFA500",  # Orange
            PaymentStatus.PROCESSING: "#2196F3",  # Blue
            PaymentStatus.COMPLETED: "#4CAF50",  # Green
            PaymentStatus.FAILED: "#F44336",  # Red
            PaymentStatus.REFUNDED: "#9C27B0",  # Purple
            PaymentStatus.PARTIALLY_REFUNDED: "#FF9800",  # Amber
        }
        return color_map.get(self.payment_status, "#000000")


class PaymentDetail(BaseResponseSchema):
    """
    Detailed payment information schema.
    
    Contains complete payment details including payer info,
    gateway response, refund details, and collection information.
    """

    payment_reference: str = Field(
        ...,
        description="Payment reference",
    )
    transaction_id: Optional[str] = Field(
        None,
        description="Transaction ID",
    )

    # Payer Details
    payer_id: UUID = Field(..., description="Payer ID")
    payer_name: str = Field(..., description="Payer name")
    payer_email: str = Field(..., description="Payer email")
    payer_phone: str = Field(..., description="Payer phone")

    # Hostel Details
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")

    # Related Entities
    student_id: Optional[UUID] = Field(None, description="Student ID")
    student_name: Optional[str] = Field(None, description="Student name")
    booking_id: Optional[UUID] = Field(None, description="Booking ID")
    booking_reference: Optional[str] = Field(None, description="Booking reference")

    # Payment Details
    payment_type: PaymentType = Field(..., description="Payment type")
    amount: Decimal = Field(..., ge=0, description="Amount")
    currency: str = Field(..., description="Currency")

    # Payment Period
    payment_period_start: Optional[Date] = Field(None, description="Period start")
    payment_period_end: Optional[Date] = Field(None, description="Period end")

    # Payment Method
    payment_method: PaymentMethod = Field(..., description="Payment method")
    payment_gateway: Optional[str] = Field(None, description="Gateway used")

    # Status
    payment_status: PaymentStatus = Field(..., description="Payment status")
    paid_at: Optional[datetime] = Field(None, description="Payment completion time")
    failed_at: Optional[datetime] = Field(None, description="Payment failure time")
    failure_reason: Optional[str] = Field(None, description="Failure reason")

    # Gateway Response
    gateway_response: Optional[Dict] = Field(
        None,
        description="Raw gateway response data",
    )

    # Receipt
    receipt_number: Optional[str] = Field(None, description="Receipt number")
    receipt_url: Optional[str] = Field(None, description="Receipt download URL")
    receipt_generated_at: Optional[datetime] = Field(None, description="Receipt generation time")

    # Refund Information
    refund_amount: Decimal = Field(
        Decimal("0.00"),
        ge=0,
        description="Total refunded amount",
    )
    refund_status: str = Field(
        "none",
        description="Refund status",
    )
    refunded_at: Optional[datetime] = Field(None, description="Refund completion time")
    refund_transaction_id: Optional[str] = Field(None, description="Refund transaction ID")
    refund_reason: Optional[str] = Field(None, description="Refund reason")

    # Collection Information (for offline payments)
    collected_by: Optional[UUID] = Field(None, description="Staff who collected")
    collected_by_name: Optional[str] = Field(None, description="Collector name")
    collected_at: Optional[datetime] = Field(None, description="Collection timestamp")

    # Due Date
    due_date: Optional[Date] = Field(None, description="Due Date")
    is_overdue: bool = Field(..., description="Overdue status")

    # Reminders
    reminder_sent_count: int = Field(
        0,
        ge=0,
        description="Number of reminders sent",
    )
    last_reminder_sent_at: Optional[datetime] = Field(
        None,
        description="Last reminder timestamp",
    )

    # Notes
    notes: Optional[str] = Field(None, description="Additional notes")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def net_amount(self) -> Decimal:
        """Calculate net amount after refunds."""
        return (self.amount - self.refund_amount).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_fully_refunded(self) -> bool:
        """Check if payment is fully refunded."""
        return self.refund_amount >= self.amount

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_partially_refunded(self) -> bool:
        """Check if payment is partially refunded."""
        return Decimal("0") < self.refund_amount < self.amount

    @computed_field  # type: ignore[prop-decorator]
    @property
    def days_overdue(self) -> int:
        """Calculate days overdue."""
        if not self.is_overdue or self.due_date is None:
            return 0
        return (Date.today() - self.due_date).days

    @computed_field  # type: ignore[prop-decorator]
    @property
    def payment_period_display(self) -> Optional[str]:
        """Get formatted payment period."""
        if self.payment_period_start and self.payment_period_end:
            return (
                f"{self.payment_period_start.strftime('%b %d, %Y')} - "
                f"{self.payment_period_end.strftime('%b %d, %Y')}"
            )
        return None


class PaymentReceipt(BaseSchema):
    """
    Payment receipt schema for printing/download.
    
    Contains all information needed for a formal payment receipt.
    """

    receipt_number: str = Field(
        ...,
        description="Unique receipt number",
    )
    payment_reference: str = Field(
        ...,
        description="Payment reference",
    )

    # Payer Information
    payer_name: str = Field(..., description="Payer name")
    payer_email: str = Field(..., description="Payer email")
    payer_phone: str = Field(..., description="Payer phone")

    # Hostel Information
    hostel_name: str = Field(..., description="Hostel name")
    hostel_address: str = Field(..., description="Hostel full address")
    hostel_phone: str = Field(..., description="Hostel contact phone")
    hostel_email: Optional[str] = Field(None, description="Hostel email")
    hostel_gstin: Optional[str] = Field(None, description="Hostel GST number")

    # Payment Details
    payment_type: str = Field(..., description="Payment type")
    amount: Decimal = Field(..., ge=0, description="Payment amount")
    amount_in_words: str = Field(..., description="Amount in words")
    currency: str = Field(..., description="Currency")

    payment_method: str = Field(..., description="Payment method")
    transaction_id: Optional[str] = Field(None, description="Transaction ID")

    # Payment Period
    payment_for_period: Optional[str] = Field(
        None,
        description="Period description (e.g., 'January 2024')",
    )

    # Dates
    payment_date: datetime = Field(..., description="Payment Date")
    due_date: Optional[Date] = Field(None, description="Due Date")

    # Receipt Metadata
    receipt_generated_at: datetime = Field(..., description="Receipt generation time")
    receipt_url: str = Field(..., description="Receipt download URL")

    # Tax/GST Details
    tax_details: Optional[Dict] = Field(
        None,
        description="Tax breakdown if applicable",
    )

    # Additional Information
    remarks: Optional[str] = Field(None, description="Additional remarks")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def receipt_display_id(self) -> str:
        """Get formatted receipt ID for display."""
        return f"RCP-{self.receipt_number}"


class PaymentListItem(BaseSchema):
    """
    Payment list item for summary views.
    
    Optimized schema for displaying multiple payments.
    """

    id: UUID = Field(..., description="Payment ID")
    payment_reference: str = Field(..., description="Payment reference")
    payer_name: str = Field(..., description="Payer name")
    hostel_name: str = Field(..., description="Hostel name")

    payment_type: str = Field(..., description="Payment type")
    amount: Decimal = Field(..., ge=0, description="Amount")

    payment_method: str = Field(..., description="Payment method")
    payment_status: PaymentStatus = Field(..., description="Status")

    paid_at: Optional[datetime] = Field(None, description="Payment time")
    due_date: Optional[Date] = Field(None, description="Due Date")
    is_overdue: bool = Field(..., description="Overdue status")

    created_at: datetime = Field(..., description="Creation time")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_display(self) -> str:
        """Get user-friendly status display."""
        status_map = {
            PaymentStatus.PENDING: "Pending",
            PaymentStatus.PROCESSING: "Processing",
            PaymentStatus.COMPLETED: "Completed",
            PaymentStatus.FAILED: "Failed",
            PaymentStatus.REFUNDED: "Refunded",
            PaymentStatus.PARTIALLY_REFUNDED: "Partially Refunded",
        }
        return status_map.get(self.payment_status, "Unknown")


class PaymentSummary(BaseSchema):
    """
    Payment summary for student or hostel.
    
    Provides aggregate payment information and statistics.
    """

    entity_id: UUID = Field(
        ...,
        description="Entity ID (student or hostel)",
    )
    entity_type: str = Field(
        ...,
        pattern=r"^(student|hostel)$",
        description="Entity type",
    )

    # Totals
    total_paid: Decimal = Field(
        ...,
        ge=0,
        description="Total amount paid",
    )
    total_pending: Decimal = Field(
        ...,
        ge=0,
        description="Total pending amount",
    )
    total_overdue: Decimal = Field(
        ...,
        ge=0,
        description="Total overdue amount",
    )

    # Last Payment
    last_payment_date: Optional[Date] = Field(
        None,
        description="Date of last payment",
    )
    last_payment_amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Amount of last payment",
    )

    # Next Payment
    next_payment_due_date: Optional[Date] = Field(
        None,
        description="Next payment due Date",
    )
    next_payment_amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Next payment amount",
    )

    # Counts
    total_payments: int = Field(
        ...,
        ge=0,
        description="Total number of payments",
    )
    completed_payments: int = Field(
        ...,
        ge=0,
        description="Number of completed payments",
    )
    pending_payments: int = Field(
        ...,
        ge=0,
        description="Number of pending payments",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def payment_health_score(self) -> str:
        """
        Calculate payment health status.
        
        Returns: "excellent", "good", "warning", or "critical"
        """
        if self.total_overdue > 0:
            return "critical"
        elif self.total_pending > self.total_paid:
            return "warning"
        elif self.pending_payments == 0:
            return "excellent"
        else:
            return "good"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def completion_rate(self) -> float:
        """Calculate payment completion rate as percentage."""
        if self.total_payments == 0:
            return 0.0
        return round((self.completed_payments / self.total_payments) * 100, 2)


class PaymentAnalytics(BaseSchema):
    """
    Payment analytics and statistics.
    
    Provides comprehensive analytics for reporting and insights.
    """

    # Time Period
    period_start: Date = Field(..., description="Analytics period start")
    period_end: Date = Field(..., description="Analytics period end")

    # Volume Metrics
    total_transactions: int = Field(..., ge=0, description="Total transactions")
    total_amount: Decimal = Field(..., ge=0, description="Total amount")
    
    # Status Breakdown
    completed_transactions: int = Field(..., ge=0)
    completed_amount: Decimal = Field(..., ge=0)
    pending_transactions: int = Field(..., ge=0)
    pending_amount: Decimal = Field(..., ge=0)
    failed_transactions: int = Field(..., ge=0)
    failed_amount: Decimal = Field(..., ge=0)

    # Payment Method Breakdown
    payment_by_method: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Amount by payment method",
    )

    # Payment Type Breakdown
    payment_by_type: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Amount by payment type",
    )

    # Averages
    average_transaction_amount: Decimal = Field(
        ...,
        ge=0,
        description="Average transaction amount",
    )

    # Success Metrics
    success_rate: float = Field(
        ...,
        ge=0,
        le=100,
        description="Transaction success rate (%)",
    )

    # Collection Metrics
    collection_efficiency: float = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of dues collected on time",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_revenue(self) -> Decimal:
        """Calculate total revenue (completed payments only)."""
        return self.completed_amount

    @computed_field  # type: ignore[prop-decorator]
    @property
    def failure_rate(self) -> float:
        """Calculate transaction failure rate."""
        if self.total_transactions == 0:
            return 0.0
        return round((self.failed_transactions / self.total_transactions) * 100, 2)