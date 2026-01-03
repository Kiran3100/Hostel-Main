"""
Subscription billing schemas.

Handles billing cycle information, invoice generation,
and invoice tracking for subscriptions.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from enum import Enum
from typing import Union, Annotated, List
from uuid import UUID

from pydantic import Field, HttpUrl, model_validator, computed_field, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseResponseSchema

__all__ = [
    "InvoiceStatus",
    "BillingCycleInfo",
    "GenerateInvoiceRequest",
    "InvoiceInfo",
    "SubscriptionInvoice",
    "InvoiceSummary",
]


class InvoiceStatus(str, Enum):
    """Invoice status enumeration."""

    DRAFT = "draft"
    ISSUED = "issued"
    SENT = "sent"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class BillingCycleInfo(BaseSchema):
    """
    Information about current billing cycle for subscription.

    Provides a comprehensive view of the current billing period,
    including dates, amounts, and renewal information.
    """
    model_config = ConfigDict(populate_by_name=True)

    subscription_id: UUID = Field(..., description="Subscription ID")
    hostel_id: UUID = Field(..., description="Hostel ID")
    plan_name: str = Field(..., description="Subscription plan name")
    plan_display_name: str = Field(
        ..., description="Plan display name for UI"
    )

    cycle_start: Date = Field(..., description="Current cycle start Date")
    cycle_end: Date = Field(..., description="Current cycle end Date")
    billing_cycle: str = Field(
        ...,
        pattern=r"^(monthly|yearly)$",
        description="Billing cycle type",
    )

    amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Billing amount for this cycle",
    )]
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code",
    )

    next_billing_date: Date = Field(..., description="Next billing Date")
    days_until_billing: int = Field(
        ...,
        description="Days until next billing",
    )
    auto_renew: bool = Field(..., description="Auto-renewal status")

    # Calculated fields
    is_in_trial: bool = Field(
        default=False, description="Whether currently in trial period"
    )
    trial_days_remaining: Union[int, None] = Field(
        None, description="Days remaining in trial"
    )

    @model_validator(mode="after")
    def validate_cycle_dates(self) -> "BillingCycleInfo":
        """Validate billing cycle Date relationships."""
        if self.cycle_end < self.cycle_start:
            raise ValueError("cycle_end must be after cycle_start")
        return self


class GenerateInvoiceRequest(BaseCreateSchema):
    """
    Request to generate invoice for subscription cycle.

    Allows specifying the billing Date and optionally overriding
    the standard billing amount.
    """
    model_config = ConfigDict(populate_by_name=True)

    subscription_id: UUID = Field(
        ..., description="Subscription to invoice"
    )
    billing_date: Date = Field(
        ..., description="Invoice billing Date"
    )

    # Optional overrides
    amount_override: Union[Annotated[Decimal, Field(
        None,
        ge=Decimal("0"),
        description="Override standard billing amount",
    )], None]
    due_date_override: Union[Date, None] = Field(
        None, description="Override standard due Date"
    )
    notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Additional invoice notes",
    )

    # Line item adjustments
    discount_amount: Union[Annotated[Decimal, Field(
        None,
        ge=Decimal("0"),
        description="Discount amount to apply",
    )], None]
    discount_reason: Union[str, None] = Field(
        None,
        max_length=200,
        description="Reason for discount",
    )

    @model_validator(mode="after")
    def validate_discount(self) -> "GenerateInvoiceRequest":
        """Validate discount fields."""
        if self.discount_amount is not None and self.discount_amount > Decimal("0"):
            if not self.discount_reason:
                raise ValueError(
                    "discount_reason is required when discount_amount is provided"
                )
        return self


class InvoiceInfo(BaseSchema):
    """
    Generated invoice information.

    Contains all details of a generated invoice including
    status, amounts, and access URLs.
    """
    model_config = ConfigDict(populate_by_name=True)

    invoice_id: UUID = Field(..., description="Invoice unique ID")
    subscription_id: UUID = Field(..., description="Associated subscription")
    hostel_id: UUID = Field(..., description="Hostel ID")

    invoice_number: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^INV-\d{4}-\d{6,}$",
        description="Invoice number (e.g., INV-2024-000001)",
    )
    invoice_date: Date = Field(..., description="Invoice issue Date")
    due_date: Date = Field(..., description="Payment due Date")

    # Amounts
    subtotal: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Subtotal before adjustments",
    )]
    discount_amount: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Total discount applied",
    )]
    tax_amount: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Tax amount",
    )]
    amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Total invoice amount",
    )]
    amount_paid: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Amount already paid",
    )]
    amount_due: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Remaining amount due",
    )]
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code",
    )

    status: InvoiceStatus = Field(
        default=InvoiceStatus.DRAFT,
        description="Invoice status",
    )

    # Access URLs
    invoice_url: Union[HttpUrl, None] = Field(
        None, description="URL to view/download invoice"
    )
    payment_url: Union[HttpUrl, None] = Field(
        None, description="URL to pay invoice online"
    )

    # Metadata
    notes: Union[str, None] = Field(None, description="Invoice notes")

    @model_validator(mode="after")
    def validate_invoice_dates_and_amounts(self) -> "InvoiceInfo":
        """Validate invoice Date relationships and amount calculations."""
        if self.due_date < self.invoice_date:
            raise ValueError("due_date cannot be before invoice_date")

        # Validate amount calculation
        expected_amount = self.subtotal - self.discount_amount + self.tax_amount
        if abs(self.amount - expected_amount) > Decimal("0.01"):
            raise ValueError(
                f"amount ({self.amount}) does not match calculated total ({expected_amount})"
            )

        # Validate amount_due
        expected_due = self.amount - self.amount_paid
        if abs(self.amount_due - expected_due) > Decimal("0.01"):
            raise ValueError(
                f"amount_due ({self.amount_due}) does not match outstanding ({expected_due})"
            )

        return self

    @computed_field  # type: ignore[misc]
    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue based on current Date."""
        return (
            self.status not in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED)
            and Date.today() > self.due_date
        )

    @computed_field  # type: ignore[misc]
    @property
    def is_fully_paid(self) -> bool:
        """Check if invoice is fully paid."""
        return self.amount_due <= Decimal("0")


class SubscriptionInvoice(BaseResponseSchema):
    """
    Complete subscription invoice with all details.

    Extended invoice information with subscription context,
    payment history, and billing cycle information.
    """
    model_config = ConfigDict(populate_by_name=True)

    # Basic invoice info
    invoice_id: UUID = Field(..., description="Invoice unique ID")
    invoice_number: str = Field(..., description="Invoice number")
    
    # Subscription context
    subscription_id: UUID = Field(..., description="Associated subscription")
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    
    # Plan information
    plan_id: UUID = Field(..., description="Subscription plan ID")
    plan_name: str = Field(..., description="Plan internal name")
    plan_display_name: str = Field(..., description="Plan display name")
    
    # Billing period
    billing_period_start: Date = Field(..., description="Billing period start")
    billing_period_end: Date = Field(..., description="Billing period end")
    billing_cycle: str = Field(..., description="Billing cycle (monthly/yearly)")
    
    # Dates
    invoice_date: Date = Field(..., description="Invoice issue date")
    due_date: Date = Field(..., description="Payment due date")
    paid_date: Union[Date, None] = Field(None, description="Date when paid")
    
    # Amounts
    subtotal: Annotated[Decimal, Field(..., description="Subtotal amount")]
    discount_amount: Annotated[Decimal, Field(
        default=Decimal("0.00"), description="Discount applied"
    )]
    tax_amount: Annotated[Decimal, Field(
        default=Decimal("0.00"), description="Tax amount"
    )]
    total_amount: Annotated[Decimal, Field(..., description="Total invoice amount")]
    amount_paid: Annotated[Decimal, Field(
        default=Decimal("0.00"), description="Amount paid"
    )]
    amount_due: Annotated[Decimal, Field(..., description="Amount still due")]
    currency: str = Field(default="INR", description="Currency code")
    
    # Status and tracking
    status: InvoiceStatus = Field(..., description="Invoice status")
    payment_method: Union[str, None] = Field(None, description="Payment method used")
    payment_reference: Union[str, None] = Field(None, description="Payment reference")
    
    # Links and files
    invoice_url: Union[HttpUrl, None] = Field(None, description="Invoice download URL")
    payment_url: Union[HttpUrl, None] = Field(None, description="Payment URL")
    
    # Additional info
    notes: Union[str, None] = Field(None, description="Invoice notes")
    description: Union[str, None] = Field(None, description="Invoice description")
    
    @computed_field  # type: ignore[misc]
    @property
    def is_paid(self) -> bool:
        """Check if invoice is fully paid."""
        return self.status == InvoiceStatus.PAID
    
    @computed_field  # type: ignore[misc]
    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue."""
        return (
            self.status not in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.REFUNDED)
            and Date.today() > self.due_date
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def days_overdue(self) -> int:
        """Calculate days overdue (0 if not overdue)."""
        if not self.is_overdue:
            return 0
        return (Date.today() - self.due_date).days


class InvoiceSummary(BaseSchema):
    """
    Aggregated invoice statistics and summaries.

    Provides overview of invoice metrics for reporting
    and dashboard purposes.
    """
    model_config = ConfigDict(populate_by_name=True)

    # Scope
    period_start: Date = Field(..., description="Summary period start")
    period_end: Date = Field(..., description="Summary period end")
    hostel_id: Union[UUID, None] = Field(None, description="Hostel ID (if hostel-specific)")
    
    # Counts
    total_invoices: int = Field(..., ge=0, description="Total invoices in period")
    paid_invoices: int = Field(..., ge=0, description="Paid invoices")
    pending_invoices: int = Field(..., ge=0, description="Pending invoices")
    overdue_invoices: int = Field(..., ge=0, description="Overdue invoices")
    cancelled_invoices: int = Field(..., ge=0, description="Cancelled invoices")
    
    # Amounts
    total_billed: Annotated[Decimal, Field(..., description="Total billed amount")]
    total_paid: Annotated[Decimal, Field(..., description="Total paid amount")]
    total_outstanding: Annotated[Decimal, Field(..., description="Total outstanding")]
    total_overdue: Annotated[Decimal, Field(..., description="Total overdue amount")]
    currency: str = Field(default="INR", description="Currency code")
    
    # Averages
    average_invoice_amount: Annotated[Decimal, Field(..., description="Average invoice amount")]
    average_payment_days: Union[float, None] = Field(None, description="Average days to payment")
    
    # Status breakdown
    status_breakdown: dict = Field(
        default_factory=dict,
        description="Invoice count by status"
    )
    monthly_breakdown: List[dict] = Field(
        default_factory=list,
        description="Monthly invoice statistics"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def collection_rate(self) -> Decimal:
        """Calculate collection rate percentage."""
        if self.total_billed == Decimal("0"):
            return Decimal("100.00")
        return (self.total_paid / self.total_billed * 100).quantize(Decimal("0.01"))
    
    @computed_field  # type: ignore[misc]
    @property
    def overdue_rate(self) -> Decimal:
        """Calculate overdue rate percentage."""
        if self.total_invoices == 0:
            return Decimal("0.00")
        return (Decimal(str(self.overdue_invoices)) / Decimal(str(self.total_invoices)) * 100).quantize(Decimal("0.01"))
    
    @model_validator(mode="after")
    def validate_invoice_counts(self) -> "InvoiceSummary":
        """Validate invoice count consistency."""
        calculated_total = (
            self.paid_invoices + self.pending_invoices + 
            self.overdue_invoices + self.cancelled_invoices
        )
        if calculated_total > self.total_invoices:
            raise ValueError("Sum of status-specific counts cannot exceed total")
        return self