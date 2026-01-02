# --- File: app/schemas/fee_structure/fee_config.py ---

from datetime import date as Date
from decimal import Decimal
from typing import Dict, Union, List, Any
from datetime import datetime   

from uuid import UUID

from pydantic import Field, computed_field, field_validator, model_validator

from app.schemas.common.base import BaseSchema, BaseCreateSchema, BaseUpdateSchema
from app.schemas.common.enums import ChargeType, FeeType, RoomType

__all__ = [
    "FeeQuoteRequest",
    "MonthlyProjection",
    "HistoricalData",
    "FeeProjection",
    "DiscountConfiguration",
    "DiscountCreate",
    "DiscountUpdate",
]

class FeeQuoteRequest(BaseSchema):
    """
    Request schema for fee quote calculation.
    
    Used to request a fee calculation without creating a booking.
    """
    
    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier for the quote"
    )
    
    room_type: RoomType = Field(
        ...,
        description="Type of room for the quote"
    )
    
    check_in_date: Date = Field(
        ...,
        description="Proposed check-in date"
    )
    
    check_out_date: Date = Field(
        ...,
        description="Proposed check-out date"
    )
    
    number_of_guests: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Number of guests (1-10)"
    )
    
    discount_code: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Optional discount/promo code"
    )
    
    include_mess: Union[bool, None] = Field(
        default=None,
        description="Override mess inclusion (if allowed)"
    )
    
    student_id: Union[UUID, None] = Field(
        default=None,
        description="Student ID for personalized quotes"
    )
    
    @field_validator("check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: Date) -> Date:
        """Validate check-in date is not in the past."""
        if v < Date.today():
            raise ValueError("Check-in date cannot be in the past")
        
        # Don't allow bookings too far in the future (e.g., 2 years)
        max_future_days = 730  # ~2 years
        if (v - Date.today()).days > max_future_days:
            raise ValueError(
                f"Check-in date cannot be more than {max_future_days} days in the future"
            )
        
        return v
    
    @field_validator("discount_code")
    @classmethod
    def validate_discount_code(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate and normalize discount code."""
        if v is not None:
            v = v.strip().upper()
            if len(v) == 0:
                return None
        return v
    
    @model_validator(mode="after")
    def validate_date_range(self):
        """Validate check-out is after check-in."""
        if self.check_out_date <= self.check_in_date:
            raise ValueError("Check-out date must be after check-in date")
        
        # Calculate stay duration
        stay_duration = (self.check_out_date - self.check_in_date).days
        
        # Minimum stay validation (e.g., 1 day)
        if stay_duration < 1:
            raise ValueError("Minimum stay duration is 1 day")
        
        # Maximum stay validation (e.g., 2 years)
        max_stay_days = 730  # ~2 years
        if stay_duration > max_stay_days:
            raise ValueError(
                f"Maximum stay duration is {max_stay_days} days"
            )
        
        return self
    
    @computed_field
    @property
    def stay_duration_days(self) -> int:
        """Calculate stay duration in days."""
        return (self.check_out_date - self.check_in_date).days
    
    @computed_field
    @property
    def stay_duration_months(self) -> int:
        """Calculate approximate stay duration in months."""
        days = self.stay_duration_days
        # Round up to nearest month
        return max(1, (days + 29) // 30)


class MonthlyProjection(BaseSchema):
    """
    Monthly revenue projection details.
    """
    
    month: int = Field(
        ...,
        ge=1,
        le=12,
        description="Month number (1-12)"
    )
    
    year: int = Field(
        ...,
        ge=2020,
        le=2100,
        description="Year"
    )
    
    month_name: str = Field(
        ...,
        description="Month name (e.g., 'January')"
    )
    
    # Projected Revenue
    projected_rent_revenue: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Projected rent revenue (precision: 2 decimal places)"
    )
    
    projected_mess_revenue: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Projected mess revenue (precision: 2 decimal places)"
    )
    
    projected_utility_revenue: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Projected utility revenue (precision: 2 decimal places)"
    )
    
    projected_other_revenue: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Projected other revenue (precision: 2 decimal places)"
    )
    
    # Occupancy Metrics
    projected_occupancy_rate: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Projected occupancy rate percentage (precision: 2 decimal places)"
    )
    
    projected_occupied_beds: int = Field(
        ...,
        ge=0,
        description="Projected number of occupied beds"
    )
    
    total_available_beds: int = Field(
        ...,
        ge=0,
        description="Total available beds"
    )
    
    # Adjustments
    seasonal_adjustment_factor: Decimal = Field(
        default=Decimal("1.00"),
        ge=Decimal("0"),
        description="Seasonal adjustment multiplier (precision: 2 decimal places)"
    )
    
    @field_validator(
        "projected_rent_revenue", "projected_mess_revenue",
        "projected_utility_revenue", "projected_other_revenue",
        "projected_occupancy_rate", "seasonal_adjustment_factor"
    )
    @classmethod
    def quantize_decimal_fields(cls, v: Decimal) -> Decimal:
        """Quantize decimal fields to 2 decimal places."""
        return v.quantize(Decimal("0.01"))
    
    @computed_field
    @property
    def total_projected_revenue(self) -> Decimal:
        """Calculate total projected revenue for the month."""
        return (
            self.projected_rent_revenue +
            self.projected_mess_revenue +
            self.projected_utility_revenue +
            self.projected_other_revenue
        ).quantize(Decimal("0.01"))
    
    @computed_field
    @property
    def month_year_display(self) -> str:
        """Get formatted month-year display."""
        return f"{self.month_name} {self.year}"
    
    @computed_field
    @property
    def vacancy_rate(self) -> Decimal:
        """Calculate vacancy rate percentage."""
        return (Decimal("100") - self.projected_occupancy_rate).quantize(
            Decimal("0.01")
        )


class HistoricalData(BaseSchema):
    """
    Historical revenue data for comparison.
    """
    
    period_start: Date = Field(
        ...,
        description="Start date of historical period"
    )
    
    period_end: Date = Field(
        ...,
        description="End date of historical period"
    )
    
    # Actual Revenue
    actual_rent_revenue: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Actual rent revenue (precision: 2 decimal places)"
    )
    
    actual_mess_revenue: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Actual mess revenue (precision: 2 decimal places)"
    )
    
    actual_utility_revenue: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Actual utility revenue (precision: 2 decimal places)"
    )
    
    actual_other_revenue: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Actual other revenue (precision: 2 decimal places)"
    )
    
    # Actual Occupancy
    average_occupancy_rate: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Average occupancy rate (precision: 2 decimal places)"
    )
    
    average_occupied_beds: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Average occupied beds (precision: 2 decimal places)"
    )
    
    @field_validator(
        "actual_rent_revenue", "actual_mess_revenue",
        "actual_utility_revenue", "actual_other_revenue",
        "average_occupancy_rate", "average_occupied_beds"
    )
    @classmethod
    def quantize_decimal_fields(cls, v: Decimal) -> Decimal:
        """Quantize decimal fields to 2 decimal places."""
        return v.quantize(Decimal("0.01"))
    
    @computed_field
    @property
    def total_actual_revenue(self) -> Decimal:
        """Calculate total actual revenue."""
        return (
            self.actual_rent_revenue +
            self.actual_mess_revenue +
            self.actual_utility_revenue +
            self.actual_other_revenue
        ).quantize(Decimal("0.01"))
    
    @computed_field
    @property
    def period_duration_days(self) -> int:
        """Calculate duration of historical period in days."""
        return (self.period_end - self.period_start).days


class FeeProjection(BaseSchema):
    """
    Complete fee/revenue projection for a hostel.
    
    Includes monthly breakdowns, totals, and historical comparisons.
    """
    
    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier"
    )
    
    hostel_name: str = Field(
        ...,
        description="Hostel name"
    )
    
    # Projection Period
    projection_start_date: Date = Field(
        ...,
        description="Start date of projection period"
    )
    
    projection_end_date: Date = Field(
        ...,
        description="End date of projection period"
    )
    
    projection_months: int = Field(
        ...,
        ge=1,
        le=60,
        description="Number of months projected"
    )
    
    # Monthly Projections
    monthly_projections: List[MonthlyProjection] = Field(
        default_factory=list,
        description="Month-by-month projections"
    )
    
    # Total Projections
    total_projected_revenue: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Total projected revenue for entire period (precision: 2 decimal places)"
    )
    
    total_projected_rent: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Total projected rent revenue (precision: 2 decimal places)"
    )
    
    total_projected_mess: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Total projected mess revenue (precision: 2 decimal places)"
    )
    
    total_projected_utilities: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Total projected utility revenue (precision: 2 decimal places)"
    )
    
    # Averages
    average_monthly_revenue: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Average monthly revenue (precision: 2 decimal places)"
    )
    
    average_occupancy_rate: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Average projected occupancy rate (precision: 2 decimal places)"
    )
    
    # Historical Comparison (optional)
    historical_data: Union[HistoricalData, None] = Field(
        default=None,
        description="Historical data for comparison"
    )
    
    # Metadata
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when projection was generated"
    )
    
    assumptions: Union[Dict[str, Any], None] = Field(
        default=None,
        description="Assumptions used in projection calculations"
    )
    
    confidence_level: Union[str, None] = Field(
        default=None,
        pattern=r"^(high|medium|low)$",
        description="Confidence level of projections"
    )
    
    @field_validator(
        "total_projected_revenue", "total_projected_rent",
        "total_projected_mess", "total_projected_utilities",
        "average_monthly_revenue", "average_occupancy_rate"
    )
    @classmethod
    def quantize_decimal_fields(cls, v: Decimal) -> Decimal:
        """Quantize decimal fields to 2 decimal places."""
        return v.quantize(Decimal("0.01"))
    
    @computed_field
    @property
    def projection_period_display(self) -> str:
        """Get formatted projection period."""
        return f"{self.projection_start_date} to {self.projection_end_date}"
    
    @computed_field
    @property
    def growth_rate_vs_historical(self) -> Union[Decimal, None]:
        """Calculate projected growth rate vs historical data."""
        if self.historical_data is None:
            return None
        
        if self.historical_data.total_actual_revenue == 0:
            return None
        
        # Compare average monthly revenues
        historical_monthly_avg = (
            self.historical_data.total_actual_revenue / 
            max(1, self.historical_data.period_duration_days / 30)
        )
        
        if historical_monthly_avg == 0:
            return None
        
        growth = (
            (self.average_monthly_revenue - historical_monthly_avg) / 
            historical_monthly_avg * 100
        )
        
        return Decimal(str(growth)).quantize(Decimal("0.01"))
    
    @computed_field
    @property
    def peak_month(self) -> Union[str, None]:
        """Identify month with highest projected revenue."""
        if not self.monthly_projections:
            return None
        
        peak = max(
            self.monthly_projections,
            key=lambda x: x.total_projected_revenue
        )
        
        return peak.month_year_display
    
    @computed_field
    @property
    def lowest_month(self) -> Union[str, None]:
        """Identify month with lowest projected revenue."""
        if not self.monthly_projections:
            return None
        
        lowest = min(
            self.monthly_projections,
            key=lambda x: x.total_projected_revenue
        )
        
        return lowest.month_year_display


# ===========================================================================
# Discount Configuration Schemas
# ===========================================================================


class DiscountConfiguration(BaseSchema):
    """
    Complete discount configuration response schema.
    
    Represents a discount rule that can be applied to fee structures.
    """
    
    id: UUID = Field(
        ...,
        description="Unique identifier of the discount"
    )
    
    hostel_id: UUID = Field(
        ...,
        description="Hostel this discount applies to"
    )
    
    discount_name: str = Field(
        ...,
        description="Name of the discount"
    )
    
    discount_code: Union[str, None] = Field(
        default=None,
        description="Promotional code for this discount"
    )
    
    discount_type: str = Field(
        ...,
        description="Type of discount (percentage, fixed_amount, waiver)"
    )
    
    # Discount Value
    discount_percentage: Union[Decimal, None] = Field(
        default=None,
        description="Discount percentage (if type is percentage)"
    )
    
    discount_amount: Union[Decimal, None] = Field(
        default=None,
        description="Fixed discount amount (if type is fixed_amount)"
    )
    
    # Applicability
    applies_to: str = Field(
        ...,
        description="What the discount applies to"
    )
    
    applicable_room_types: Union[List[str], None] = Field(
        default=None,
        description="List of room types this discount applies to"
    )
    
    # Conditions
    minimum_stay_months: Union[int, None] = Field(
        default=None,
        description="Minimum stay required for discount"
    )
    
    maximum_stay_months: Union[int, None] = Field(
        default=None,
        description="Maximum stay for discount eligibility"
    )
    
    valid_for_new_students_only: bool = Field(
        default=False,
        description="Whether discount is only for new students"
    )
    
    # Usage Limits
    usage_limit: Union[int, None] = Field(
        default=None,
        description="Maximum number of times discount can be used"
    )
    
    usage_limit_per_student: Union[int, None] = Field(
        default=None,
        description="Maximum uses per student"
    )
    
    current_usage_count: int = Field(
        default=0,
        description="Current number of times discount has been used"
    )
    
    # Validity Period
    valid_from: Union[Date, None] = Field(
        default=None,
        description="Discount valid from date"
    )
    
    valid_to: Union[Date, None] = Field(
        default=None,
        description="Discount valid until date"
    )
    
    # Stacking Rules
    can_stack_with_other_discounts: bool = Field(
        default=False,
        description="Whether this discount can be combined with others"
    )
    
    priority: int = Field(
        default=0,
        description="Priority for discount application"
    )
    
    # Status
    is_active: bool = Field(
        default=True,
        description="Whether discount is currently active"
    )
    
    # Display
    description: Union[str, None] = Field(
        default=None,
        description="Public description of the discount"
    )
    
    internal_notes: Union[str, None] = Field(
        default=None,
        description="Internal notes about this discount"
    )
    
    # Audit fields
    created_by: Union[UUID, None] = Field(
        default=None,
        description="User who created this discount"
    )
    
    created_by_name: Union[str, None] = Field(
        default=None,
        description="Name of user who created this discount"
    )
    
    updated_by: Union[UUID, None] = Field(
        default=None,
        description="User who last updated this discount"
    )
    
    updated_by_name: Union[str, None] = Field(
        default=None,
        description="Name of user who last updated this discount"
    )
    
    @field_validator("discount_percentage", "discount_amount")
    @classmethod
    def quantize_optional_decimals(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Quantize optional decimal fields to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v
    
    @computed_field
    @property
    def is_currently_valid(self) -> bool:
        """Check if discount is currently valid based on dates."""
        if not self.is_active:
            return False
        
        today = Date.today()
        
        if self.valid_from and today < self.valid_from:
            return False
        
        if self.valid_to and today > self.valid_to:
            return False
        
        return True
    
    @computed_field
    @property
    def is_usage_limit_reached(self) -> bool:
        """Check if usage limit has been reached."""
        if self.usage_limit is None:
            return False
        
        return self.current_usage_count >= self.usage_limit
    
    @computed_field
    @property
    def remaining_uses(self) -> Union[int, None]:
        """Calculate remaining uses of the discount."""
        if self.usage_limit is None:
            return None
        
        remaining = self.usage_limit - self.current_usage_count
        return max(0, remaining)
    
    @computed_field
    @property
    def discount_value_display(self) -> str:
        """Get formatted discount value for display."""
        if self.discount_type == "percentage":
            return f"{self.discount_percentage}% off"
        elif self.discount_type == "fixed_amount":
            return f"₹{self.discount_amount} off"
        elif self.discount_type == "waiver":
            return "100% waiver"
        else:
            return "Unknown"


class DiscountCreate(BaseCreateSchema):
    """
    Schema for creating a new discount configuration.
    """
    
    hostel_id: UUID = Field(
        ...,
        description="Hostel this discount applies to"
    )
    
    discount_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Name of the discount"
    )
    
    discount_code: Union[str, None] = Field(
        default=None,
        min_length=3,
        max_length=50,
        description="Promotional code for this discount"
    )
    
    discount_type: str = Field(
        ...,
        pattern=r"^(percentage|fixed_amount|waiver)$",
        description="Type of discount"
    )
    
    # Discount Value
    discount_percentage: Union[Decimal, None] = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Discount percentage (if type is percentage)"
    )
    
    discount_amount: Union[Decimal, None] = Field(
        default=None,
        ge=Decimal("0"),
        description="Fixed discount amount (if type is fixed_amount)"
    )
    
    # Applicability
    applies_to: str = Field(
        ...,
        pattern=r"^(base_rent|mess_charges|total|security_deposit|utilities)$",
        description="What the discount applies to"
    )
    
    # Room Type Restrictions
    applicable_room_types: Union[List[str], None] = Field(
        default=None,
        description="List of room types this discount applies to (null = all)"
    )
    
    # Conditions
    minimum_stay_months: Union[int, None] = Field(
        default=None,
        ge=1,
        le=60,
        description="Minimum stay required for discount"
    )
    
    maximum_stay_months: Union[int, None] = Field(
        default=None,
        ge=1,
        le=60,
        description="Maximum stay for discount eligibility"
    )
    
    valid_for_new_students_only: bool = Field(
        default=False,
        description="Whether discount is only for new students"
    )
    
    # Usage Limits
    usage_limit: Union[int, None] = Field(
        default=None,
        ge=1,
        description="Maximum number of times discount can be used"
    )
    
    usage_limit_per_student: Union[int, None] = Field(
        default=None,
        ge=1,
        description="Maximum uses per student"
    )
    
    # Validity Period
    valid_from: Union[Date, None] = Field(
        default=None,
        description="Discount valid from date"
    )
    
    valid_to: Union[Date, None] = Field(
        default=None,
        description="Discount valid until date"
    )
    
    # Stacking Rules
    can_stack_with_other_discounts: bool = Field(
        default=False,
        description="Whether this discount can be combined with others"
    )
    
    priority: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Priority for discount application (higher = applied first)"
    )
    
    # Status
    is_active: bool = Field(
        default=True,
        description="Whether discount is currently active"
    )
    
    # Display
    description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Public description of the discount"
    )
    
    internal_notes: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Internal notes about this discount"
    )
    
    @field_validator("discount_name")
    @classmethod
    def validate_discount_name(cls, v: str) -> str:
        """Validate discount name."""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Discount name must be at least 3 characters")
        return v
    
    @field_validator("discount_code")
    @classmethod
    def validate_discount_code(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate and normalize discount code."""
        if v is not None:
            v = v.strip().upper()
            if len(v) == 0:
                return None
            # Ensure code is alphanumeric with optional hyphens/underscores
            import re
            if not re.match(r'^[A-Z0-9_-]+$', v):
                raise ValueError(
                    "Discount code must contain only letters, numbers, hyphens, and underscores"
                )
        return v
    
    @field_validator("discount_type", "applies_to")
    @classmethod
    def normalize_string_fields(cls, v: str) -> str:
        """Normalize string fields to lowercase."""
        return v.lower()
    
    @field_validator("discount_percentage", "discount_amount")
    @classmethod
    def quantize_optional_decimals(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Quantize optional decimal fields to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v
    
    @model_validator(mode="after")
    def validate_discount_create(self):
        """Validate discount creation constraints."""
        # Validate discount type and value
        if self.discount_type == "percentage":
            if self.discount_percentage is None or self.discount_percentage <= 0:
                raise ValueError(
                    "discount_percentage is required and must be greater than 0 "
                    "when discount_type is 'percentage'"
                )
            object.__setattr__(self, 'discount_amount', None)
        
        elif self.discount_type == "fixed_amount":
            if self.discount_amount is None or self.discount_amount <= 0:
                raise ValueError(
                    "discount_amount is required and must be greater than 0 "
                    "when discount_type is 'fixed_amount'"
                )
            object.__setattr__(self, 'discount_percentage', None)
        
        elif self.discount_type == "waiver":
            # Waiver = 100% discount
            object.__setattr__(self, 'discount_percentage', Decimal("100.00"))
            object.__setattr__(self, 'discount_amount', None)
        
        # Validate validity period
        if self.valid_from and self.valid_to:
            if self.valid_to <= self.valid_from:
                raise ValueError("valid_to must be after valid_from")
        
        # Validate stay duration constraints
        if self.minimum_stay_months and self.maximum_stay_months:
            if self.maximum_stay_months < self.minimum_stay_months:
                raise ValueError(
                    "maximum_stay_months must be greater than or equal to minimum_stay_months"
                )
        
        return self


class DiscountUpdate(BaseUpdateSchema):
    """
    Schema for updating an existing discount configuration.
    
    All fields are optional for partial updates.
    """
    
    discount_name: Union[str, None] = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="Update discount name"
    )
    
    discount_code: Union[str, None] = Field(
        default=None,
        min_length=3,
        max_length=50,
        description="Update discount code"
    )
    
    discount_percentage: Union[Decimal, None] = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Update discount percentage"
    )
    
    discount_amount: Union[Decimal, None] = Field(
        default=None,
        ge=Decimal("0"),
        description="Update discount amount"
    )
    
    applies_to: Union[str, None] = Field(
        default=None,
        pattern=r"^(base_rent|mess_charges|total|security_deposit|utilities)$",
        description="Update what discount applies to"
    )
    
    applicable_room_types: Union[List[str], None] = Field(
        default=None,
        description="Update applicable room types"
    )
    
    minimum_stay_months: Union[int, None] = Field(
        default=None,
        ge=1,
        le=60,
        description="Update minimum stay requirement"
    )
    
    valid_for_new_students_only: Union[bool, None] = Field(
        default=None,
        description="Update new students only flag"
    )
    
    usage_limit: Union[int, None] = Field(
        default=None,
        ge=1,
        description="Update usage limit"
    )
    
    valid_from: Union[Date, None] = Field(
        default=None,
        description="Update valid from date"
    )
    
    valid_to: Union[Date, None] = Field(
        default=None,
        description="Update valid to date"
    )
    
    is_active: Union[bool, None] = Field(
        default=None,
        description="Update active status"
    )
    
    description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Update description"
    )
    
    @field_validator("discount_percentage", "discount_amount")
    @classmethod
    def quantize_optional_decimals(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Quantize optional decimal fields to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v