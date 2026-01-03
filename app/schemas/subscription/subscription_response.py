"""
Subscription response schemas.

Provides comprehensive response structures for subscription
data, billing history, and subscription summaries.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Union, Annotated, Dict, Any
from uuid import UUID

from pydantic import Field, HttpUrl, computed_field, model_validator, ConfigDict

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import (
    BillingCycle,
    SubscriptionPlan,
    SubscriptionStatus,
)

__all__ = [
    "SubscriptionResponse",
    "SubscriptionDetail",
    "SubscriptionSummary",
    "SubscriptionMetrics",
    "BillingHistoryItem",
    "BillingHistory",
]


class SubscriptionResponse(BaseResponseSchema):
    """
    Complete hostel subscription response.

    Returns all subscription details including plan information,
    billing details, and current status.
    """
    model_config = ConfigDict(populate_by_name=True)

    # Hostel info
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")

    # Plan info
    plan_id: UUID = Field(..., description="Subscription plan ID")
    plan_name: str = Field(..., description="Plan internal name")
    display_name: str = Field(..., description="Plan display name")
    plan_type: SubscriptionPlan = Field(..., description="Plan tier")

    # Subscription details
    subscription_reference: str = Field(
        ..., description="Unique subscription reference"
    )
    billing_cycle: BillingCycle = Field(..., description="Billing cycle")
    amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Billing amount",
    )]
    currency: str = Field(default="INR", description="Currency code")

    # Dates
    start_date: Date = Field(..., description="Subscription start Date")
    end_date: Date = Field(..., description="Subscription end Date")
    auto_renew: bool = Field(..., description="Auto-renewal enabled")
    next_billing_date: Union[Date, None] = Field(
        None, description="Next billing Date"
    )
    status: SubscriptionStatus = Field(..., description="Current status")

    # Trial info
    trial_end_date: Union[Date, None] = Field(
        None, description="Trial period end Date"
    )
    is_in_trial: bool = Field(
        default=False, description="Currently in trial period"
    )

    # Payment info
    last_payment_date: Union[Date, None] = Field(
        None, description="Last payment Date"
    )
    last_payment_amount: Union[Annotated[Decimal, Field(
        None,
        ge=Decimal("0"),
        description="Last payment amount",
    )], None]

    # Cancellation info (if applicable)
    cancelled_at: Union[datetime, None] = Field(
        None, description="Cancellation timestamp"
    )
    cancellation_effective_date: Union[Date, None] = Field(
        None, description="When cancellation takes effect"
    )

    @computed_field  # type: ignore[misc]
    @property
    def days_until_expiry(self) -> int:
        """Calculate days until subscription expires."""
        today = Date.today()
        if self.end_date < today:
            return 0
        return (self.end_date - today).days

    @computed_field  # type: ignore[misc]
    @property
    def days_until_billing(self) -> Union[int, None]:
        """Calculate days until next billing."""
        if self.next_billing_date is None:
            return None
        today = Date.today()
        if self.next_billing_date < today:
            return 0
        return (self.next_billing_date - today).days

    @computed_field  # type: ignore[misc]
    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        return self.status == SubscriptionStatus.ACTIVE

    @computed_field  # type: ignore[misc]
    @property
    def is_expiring_soon(self) -> bool:
        """Check if subscription expires within 7 days."""
        return 0 < self.days_until_expiry <= 7

    @computed_field  # type: ignore[misc]
    @property
    def amount_formatted(self) -> str:
        """Format amount with currency."""
        cycle_label = "mo" if self.billing_cycle == BillingCycle.MONTHLY else "yr"
        return f"{self.currency} {self.amount:,.2f}/{cycle_label}"


class SubscriptionDetail(BaseResponseSchema):
    """
    Detailed subscription information with comprehensive data.

    Extended subscription response with additional context,
    usage statistics, and related information.
    """
    model_config = ConfigDict(populate_by_name=True)

    # Core subscription info (inherited from SubscriptionResponse)
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    hostel_owner_name: Union[str, None] = Field(None, description="Hostel owner name")
    
    # Plan details
    plan_id: UUID = Field(..., description="Subscription plan ID")
    plan_name: str = Field(..., description="Plan internal name")
    plan_display_name: str = Field(..., description="Plan display name")
    plan_type: SubscriptionPlan = Field(..., description="Plan tier")
    plan_features: Dict[str, Any] = Field(
        default_factory=dict, description="Plan features"
    )
    
    # Subscription details
    subscription_reference: str = Field(..., description="Subscription reference")
    billing_cycle: BillingCycle = Field(..., description="Billing cycle")
    amount: Annotated[Decimal, Field(..., description="Billing amount")]
    currency: str = Field(default="INR", description="Currency code")
    
    # Extended date information
    start_date: Date = Field(..., description="Subscription start date")
    end_date: Date = Field(..., description="Subscription end date")
    auto_renew: bool = Field(..., description="Auto-renewal enabled")
    next_billing_date: Union[Date, None] = Field(None, description="Next billing date")
    last_billing_date: Union[Date, None] = Field(None, description="Last billing date")
    
    # Status and lifecycle
    status: SubscriptionStatus = Field(..., description="Current status")
    previous_status: Union[SubscriptionStatus, None] = Field(
        None, description="Previous status"
    )
    status_changed_at: Union[datetime, None] = Field(
        None, description="When status last changed"
    )
    
    # Trial information
    trial_start_date: Union[Date, None] = Field(None, description="Trial start date")
    trial_end_date: Union[Date, None] = Field(None, description="Trial end date")
    is_in_trial: bool = Field(default=False, description="Currently in trial")
    trial_days_remaining: Union[int, None] = Field(None, description="Trial days left")
    
    # Payment and billing
    total_paid: Annotated[Decimal, Field(
        default=Decimal("0.00"), description="Total amount paid"
    )]
    total_outstanding: Annotated[Decimal, Field(
        default=Decimal("0.00"), description="Total outstanding amount"
    )]
    last_payment_date: Union[Date, None] = Field(None, description="Last payment date")
    last_payment_amount: Union[Annotated[Decimal, Field(
        None, description="Last payment amount"
    )], None]
    last_payment_method: Union[str, None] = Field(None, description="Last payment method")
    
    # Cancellation details
    cancelled_at: Union[datetime, None] = Field(None, description="Cancellation timestamp")
    cancelled_by: Union[str, None] = Field(None, description="Who cancelled")
    cancellation_reason: Union[str, None] = Field(None, description="Cancellation reason")
    cancellation_effective_date: Union[Date, None] = Field(
        None, description="Cancellation effective date"
    )
    
    # Plan change information
    pending_plan_change: Union[Dict[str, Any], None] = Field(
        None, description="Pending plan change details"
    )
    last_plan_change: Union[Dict[str, Any], None] = Field(
        None, description="Last plan change details"
    )
    
    # Usage and limits
    current_usage: Dict[str, Any] = Field(
        default_factory=dict, description="Current usage statistics"
    )
    usage_limits: Dict[str, Any] = Field(
        default_factory=dict, description="Plan usage limits"
    )
    
    # Metadata
    notes: Union[str, None] = Field(None, description="Subscription notes")
    tags: List[str] = Field(default_factory=list, description="Subscription tags")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def subscription_age_days(self) -> int:
        """Calculate subscription age in days."""
        return (Date.today() - self.start_date).days
    
    @computed_field  # type: ignore[misc]
    @property
    def payment_health_score(self) -> float:
        """Calculate payment health score (0-100)."""
        if self.total_paid == Decimal("0"):
            return 100.0 if self.is_in_trial else 0.0
        
        total_expected = self.total_paid + self.total_outstanding
        if total_expected == Decimal("0"):
            return 100.0
        
        return float((self.total_paid / total_expected * 100).quantize(Decimal("0.1")))
    
    @computed_field  # type: ignore[misc]
    @property
    def days_until_expiry(self) -> int:
        """Days until subscription expires."""
        today = Date.today()
        if self.end_date < today:
            return 0
        return (self.end_date - today).days
    
    @computed_field  # type: ignore[misc]
    @property
    def is_expiring_soon(self) -> bool:
        """Check if expires within 7 days."""
        return 0 < self.days_until_expiry <= 7


class SubscriptionSummary(BaseSchema):
    """
    Condensed subscription summary for listings.

    Provides essential subscription information for dashboards
    and list views.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Subscription ID")
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")

    plan_name: str = Field(..., description="Plan name")
    plan_type: SubscriptionPlan = Field(..., description="Plan tier")
    status: SubscriptionStatus = Field(..., description="Status")

    billing_cycle: BillingCycle = Field(..., description="Billing cycle")
    amount: Annotated[Decimal, Field(..., description="Billing amount")]
    currency: str = Field(default="INR")

    end_date: Date = Field(..., description="Expiry Date")
    auto_renew: bool = Field(..., description="Auto-renewal status")

    is_in_trial: bool = Field(default=False)
    days_until_expiry: int = Field(..., description="Days until expiry")


class SubscriptionMetrics(BaseSchema):
    """
    Comprehensive subscription metrics and analytics.

    Provides detailed usage statistics, billing metrics,
    and performance indicators for a subscription.
    """
    model_config = ConfigDict(populate_by_name=True)

    # Basic info
    subscription_id: UUID = Field(..., description="Subscription ID")
    hostel_id: UUID = Field(..., description="Hostel ID")
    
    # Time periods
    current_period_start: Date = Field(..., description="Current period start")
    current_period_end: Date = Field(..., description="Current period end")
    lifetime_start: Date = Field(..., description="Subscription lifetime start")
    
    # Usage metrics
    current_period_usage: Dict[str, Any] = Field(
        default_factory=dict, description="Current period usage stats"
    )
    lifetime_usage: Dict[str, Any] = Field(
        default_factory=dict, description="Lifetime usage stats"
    )
    usage_trends: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict, description="Usage trends over time"
    )
    
    # Plan limits and utilization
    plan_limits: Dict[str, Any] = Field(
        default_factory=dict, description="Plan usage limits"
    )
    utilization_percentages: Dict[str, float] = Field(
        default_factory=dict, description="Usage vs limits percentages"
    )
    
    # Billing and revenue metrics
    total_revenue: Annotated[Decimal, Field(..., description="Total revenue generated")]
    current_period_revenue: Annotated[Decimal, Field(
        ..., description="Current period revenue"
    )]
    average_monthly_revenue: Annotated[Decimal, Field(
        ..., description="Average monthly revenue"
    )]
    currency: str = Field(default="INR", description="Currency code")
    
    # Payment metrics
    total_invoices: int = Field(..., ge=0, description="Total invoices generated")
    paid_invoices: int = Field(..., ge=0, description="Paid invoices")
    overdue_invoices: int = Field(..., ge=0, description="Overdue invoices")
    payment_success_rate: float = Field(
        ..., ge=0.0, le=100.0, description="Payment success rate percentage"
    )
    average_payment_days: Union[float, None] = Field(
        None, description="Average days to payment"
    )
    
    # Plan change history
    plan_changes_count: int = Field(
        ..., ge=0, description="Number of plan changes"
    )
    upgrades_count: int = Field(..., ge=0, description="Number of upgrades")
    downgrades_count: int = Field(..., ge=0, description="Number of downgrades")
    
    # Feature usage
    feature_usage: Dict[str, Any] = Field(
        default_factory=dict, description="Individual feature usage stats"
    )
    most_used_features: List[str] = Field(
        default_factory=list, description="Most used features"
    )
    unused_features: List[str] = Field(
        default_factory=list, description="Unused features"
    )
    
    # Performance indicators
    subscription_health_score: float = Field(
        ..., ge=0.0, le=100.0, description="Overall subscription health score"
    )
    churn_risk_score: float = Field(
        ..., ge=0.0, le=100.0, description="Churn risk score"
    )
    upgrade_likelihood: float = Field(
        ..., ge=0.0, le=100.0, description="Likelihood of upgrade"
    )
    
    # Support and satisfaction
    support_tickets_count: int = Field(
        ..., ge=0, description="Number of support tickets"
    )
    satisfaction_score: Union[float, None] = Field(
        None, ge=0.0, le=10.0, description="Customer satisfaction score"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def subscription_lifetime_days(self) -> int:
        """Calculate subscription lifetime in days."""
        return (Date.today() - self.lifetime_start).days
    
    @computed_field  # type: ignore[misc]
    @property
    def revenue_per_day(self) -> Decimal:
        """Calculate average revenue per day."""
        if self.subscription_lifetime_days == 0:
            return Decimal("0")
        return (self.total_revenue / Decimal(str(self.subscription_lifetime_days))).quantize(
            Decimal("0.01")
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def overall_utilization(self) -> float:
        """Calculate overall utilization percentage."""
        if not self.utilization_percentages:
            return 0.0
        return sum(self.utilization_percentages.values()) / len(self.utilization_percentages)
    
    @model_validator(mode="after")
    def validate_metrics_consistency(self) -> "SubscriptionMetrics":
        """Validate metrics consistency."""
        if self.paid_invoices > self.total_invoices:
            raise ValueError("paid_invoices cannot exceed total_invoices")
        if self.overdue_invoices > self.total_invoices:
            raise ValueError("overdue_invoices cannot exceed total_invoices")
        return self


class BillingHistoryItem(BaseSchema):
    """
    Single billing event in history.

    Represents one billing transaction with all relevant details.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: Union[UUID, None] = Field(None, description="Transaction ID")
    billing_date: Date = Field(..., description="Billing Date")

    # Amounts
    amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Billed amount",
    )]
    currency: str = Field(default="INR", description="Currency code")

    # Status and references
    status: str = Field(
        ...,
        description="Payment status (pending, paid, failed, refunded)",
    )
    payment_reference: Union[str, None] = Field(
        None,
        max_length=100,
        description="Payment transaction reference",
    )
    payment_method: Union[str, None] = Field(
        None, description="Payment method used"
    )

    # Invoice
    invoice_number: Union[str, None] = Field(
        None, description="Associated invoice number"
    )
    invoice_url: Union[HttpUrl, None] = Field(
        None, description="Invoice download URL"
    )

    # Description
    description: Union[str, None] = Field(
        None,
        max_length=255,
        description="Billing description",
    )

    # Period covered
    period_start: Union[Date, None] = Field(
        None, description="Billing period start"
    )
    period_end: Union[Date, None] = Field(
        None, description="Billing period end"
    )

    @computed_field  # type: ignore[misc]
    @property
    def is_paid(self) -> bool:
        """Check if billing item is paid."""
        return self.status.lower() == "paid"


class BillingHistory(BaseSchema):
    """
    Complete subscription billing history.

    Aggregates all billing events with summary statistics.
    """
    model_config = ConfigDict(populate_by_name=True)

    subscription_id: UUID = Field(..., description="Subscription ID")
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: Union[str, None] = Field(None, description="Hostel name")

    # Billing items
    items: List[BillingHistoryItem] = Field(
        default_factory=list,
        description="List of billing events",
    )

    # Summary totals
    total_billed: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Total amount billed",
    )]
    total_paid: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Total amount paid",
    )]
    total_outstanding: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Outstanding amount",
    )]
    total_refunded: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Total refunded amount",
    )]

    currency: str = Field(default="INR", description="Currency code")

    # Pagination info
    total_count: int = Field(
        default=0, ge=0, description="Total billing events"
    )
    page: int = Field(default=1, ge=1, description="Current page")
    page_size: int = Field(default=20, ge=1, description="Page size")

    @model_validator(mode="after")
    def validate_totals(self) -> "BillingHistory":
        """Validate total calculations."""
        expected_outstanding = self.total_billed - self.total_paid - self.total_refunded
        if expected_outstanding < Decimal("0"):
            expected_outstanding = Decimal("0")

        # Allow small floating point differences
        if abs(self.total_outstanding - expected_outstanding) > Decimal("0.01"):
            raise ValueError(
                f"total_outstanding ({self.total_outstanding}) does not match "
                f"calculated value ({expected_outstanding})"
            )
        return self

    @computed_field  # type: ignore[misc]
    @property
    def has_outstanding(self) -> bool:
        """Check if there's outstanding balance."""
        return self.total_outstanding > Decimal("0")

    @computed_field  # type: ignore[misc]
    @property
    def payment_rate(self) -> Decimal:
        """Calculate payment collection rate percentage."""
        if self.total_billed == Decimal("0"):
            return Decimal("100.00")
        return (
            (self.total_paid + self.total_refunded) / self.total_billed * 100
        ).quantize(Decimal("0.01"))