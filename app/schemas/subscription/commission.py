"""
Booking commission tracking schemas.

Handles commission configuration, calculation, and tracking for
platform revenue from hostel bookings.
"""

from datetime import date as Date
from decimal import Decimal
from enum import Enum
from typing import Dict, Union, Annotated
from uuid import UUID

from pydantic import Field, field_validator, model_validator, computed_field, ConfigDict

from app.schemas.common.base import BaseResponseSchema, BaseSchema

__all__ = [
    "CommissionStatus",
    "CommissionConfig",
    "BookingCommissionResponse",
    "CommissionSummary",
]


class CommissionStatus(str, Enum):
    """Commission payment status."""

    PENDING = "pending"
    CALCULATED = "calculated"
    INVOICED = "invoiced"
    PAID = "paid"
    WAIVED = "waived"
    DISPUTED = "disputed"


class CommissionConfig(BaseSchema):
    """
    Global/platform commission configuration.

    Defines default commission rates and per-plan overrides for
    calculating platform fees on bookings.
    """
    model_config = ConfigDict(populate_by_name=True)

    default_commission_percentage: Annotated[Decimal, Field(
        default=Decimal("5.00"),
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Default commission percentage for all plans",
    )]
    min_commission_percentage: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Minimum allowed commission percentage",
    )]
    max_commission_percentage: Annotated[Decimal, Field(
        default=Decimal("30.00"),
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Maximum allowed commission percentage",
    )]
    commission_by_plan: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Plan type to commission percentage mapping (e.g., {'premium': 3.00})",
    )

    @field_validator("commission_by_plan")
    @classmethod
    def validate_plan_commissions(
        cls, v: Dict[str, Decimal]
    ) -> Dict[str, Decimal]:
        """Validate all plan commission percentages are within valid range."""
        for plan_name, percentage in v.items():
            if not (Decimal("0") <= percentage <= Decimal("100")):
                raise ValueError(
                    f"Commission for plan '{plan_name}' must be between 0 and 100"
                )
        return v

    @model_validator(mode="after")
    def validate_min_max_range(self) -> "CommissionConfig":
        """Ensure min <= default <= max commission percentages."""
        if self.min_commission_percentage > self.max_commission_percentage:
            raise ValueError(
                "min_commission_percentage cannot exceed max_commission_percentage"
            )
        if not (
            self.min_commission_percentage
            <= self.default_commission_percentage
            <= self.max_commission_percentage
        ):
            raise ValueError(
                "default_commission_percentage must be between min and max"
            )
        return self

    def get_commission_for_plan(self, plan_type: str) -> Decimal:
        """
        Get commission percentage for a specific plan.

        Args:
            plan_type: The subscription plan type.

        Returns:
            Commission percentage for the plan, or default if not specified.
        """
        return self.commission_by_plan.get(
            plan_type, self.default_commission_percentage
        )


class BookingCommissionResponse(BaseResponseSchema):
    """
    Commission record for a booking.

    Tracks the commission owed to the platform for a specific booking,
    including calculation details and payment status.
    """
    model_config = ConfigDict(populate_by_name=True)

    booking_id: UUID = Field(..., description="Associated booking ID")
    hostel_id: UUID = Field(..., description="Hostel ID")
    subscription_id: UUID = Field(..., description="Active subscription ID")

    booking_amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Total booking amount",
    )]
    commission_percentage: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Applied commission percentage",
    )]
    commission_amount: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Calculated commission amount",
    )]
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code",
    )

    status: CommissionStatus = Field(
        default=CommissionStatus.PENDING,
        description="Commission payment status",
    )
    due_date: Union[Date, None] = Field(
        None, description="Commission payment due Date"
    )
    paid_date: Union[Date, None] = Field(
        None, description="Actual payment Date"
    )
    payment_reference: Union[str, None] = Field(
        None,
        max_length=100,
        description="Payment transaction reference",
    )

    @model_validator(mode="after")
    def validate_payment_dates(self) -> "BookingCommissionResponse":
        """Validate paid_date is set only when status is PAID."""
        if self.status == CommissionStatus.PAID and self.paid_date is None:
            raise ValueError("paid_date is required when status is PAID")
        if self.status != CommissionStatus.PAID and self.paid_date is not None:
            raise ValueError("paid_date should only be set when status is PAID")
        return self


class CommissionSummary(BaseSchema):
    """
    Commission summary for platform or hostel.

    Aggregates commission data over a specified period for
    reporting and reconciliation purposes.
    """
    model_config = ConfigDict(populate_by_name=True)

    scope_type: str = Field(
        ...,
        pattern=r"^(platform|hostel)$",
        description="Summary scope: 'platform' or 'hostel'",
    )
    hostel_id: Union[UUID, None] = Field(
        None,
        description="Hostel ID (required when scope_type is 'hostel')",
    )

    period_start: Date = Field(..., description="Summary period start Date")
    period_end: Date = Field(..., description="Summary period end Date")

    total_bookings_count: int = Field(
        ...,
        ge=0,
        description="Total number of bookings in period",
    )
    bookings_with_commission_count: int = Field(
        ...,
        ge=0,
        description="Bookings with commission calculated",
    )

    total_booking_amount: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Total booking value in period",
    )]
    total_commission_due: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Total commission amount due",
    )]
    total_commission_paid: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Total commission amount paid",
    )]
    total_commission_pending: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Outstanding commission amount",
    )]

    average_commission_rate: Union[Annotated[Decimal, Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Average commission rate applied",
    )], None]

    @model_validator(mode="after")
    def validate_scope_and_dates(self) -> "CommissionSummary":
        """Validate hostel scope and Date range."""
        if self.scope_type == "hostel" and self.hostel_id is None:
            raise ValueError("hostel_id is required when scope_type is 'hostel'")
        if self.period_end < self.period_start:
            raise ValueError("period_end must be after or equal to period_start")
        if self.bookings_with_commission_count > self.total_bookings_count:
            raise ValueError(
                "bookings_with_commission_count cannot exceed total_bookings_count"
            )
        return self

    @computed_field  # type: ignore[misc]
    @property
    def commission_collection_rate(self) -> Decimal:
        """Calculate commission collection rate as percentage."""
        if self.total_commission_due == Decimal("0"):
            return Decimal("100.00")
        return (
            self.total_commission_paid / self.total_commission_due * Decimal("100")
        ).quantize(Decimal("0.01"))