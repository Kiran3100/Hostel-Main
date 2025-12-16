# --- File: app/schemas/fee_structure/fee_response.py ---
"""
Fee structure response schemas for API responses.

This module defines response schemas for fee structure data including
basic responses, detailed information, and list views.
"""

from datetime import date as Date
from decimal import Decimal
from typing import Dict, List, Union
from uuid import UUID

from pydantic import Field, computed_field, field_validator

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import ChargeType, FeeType, RoomType

__all__ = [
    "FeeStructureResponse",
    "FeeDetail",
    "FeeStructureList",
    "FeeHistory",
    "FeeHistoryItem",
    "FeeCalculation",
]


class FeeStructureResponse(BaseResponseSchema):
    """
    Standard fee structure response schema.
    
    Contains core fee structure information for API responses.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )

    # Fee Configuration
    room_type: RoomType = Field(
        ...,
        description="Room type",
    )
    fee_type: FeeType = Field(
        ...,
        description="Billing frequency",
    )

    # Base Charges - decimal_places removed
    amount: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Base rent amount (precision: 2 decimal places)",
    )
    security_deposit: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Security deposit (precision: 2 decimal places)",
    )

    # Mess Charges
    includes_mess: bool = Field(
        ...,
        description="Whether mess is included",
    )
    mess_charges_monthly: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Monthly mess charges (precision: 2 decimal places)",
    )

    # Utility Charges
    electricity_charges: ChargeType = Field(
        ...,
        description="Electricity billing method",
    )
    electricity_fixed_amount: Union[Decimal, None] = Field(
        default=None,
        ge=Decimal("0"),
        description="Fixed electricity amount (precision: 2 decimal places)",
    )

    water_charges: ChargeType = Field(
        ...,
        description="Water billing method",
    )
    water_fixed_amount: Union[Decimal, None] = Field(
        default=None,
        ge=Decimal("0"),
        description="Fixed water amount (precision: 2 decimal places)",
    )

    # Validity Period
    effective_from: Date = Field(
        ...,
        description="Effective start Date",
    )
    effective_to: Union[Date, None] = Field(
        default=None,
        description="Effective end Date",
    )

    # Status
    is_active: bool = Field(
        ...,
        description="Active status",
    )

    @field_validator("amount", "security_deposit", "mess_charges_monthly")
    @classmethod
    def quantize_required_decimals(cls, v: Decimal) -> Decimal:
        """Quantize required decimal fields to 2 decimal places."""
        return v.quantize(Decimal("0.01"))

    @field_validator("electricity_fixed_amount", "water_fixed_amount")
    @classmethod
    def quantize_optional_decimals(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Quantize optional decimal fields to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @computed_field
    @property
    def total_monthly_minimum(self) -> Decimal:
        """
        Calculate minimum monthly total.
        
        Includes all fixed charges that apply monthly.
        """
        total = self.amount
        
        # Add mess charges if not included
        if not self.includes_mess:
            total += self.mess_charges_monthly
        
        # Add fixed utility charges
        if self.electricity_charges == ChargeType.FIXED_MONTHLY and self.electricity_fixed_amount:
            total += self.electricity_fixed_amount
        
        if self.water_charges == ChargeType.FIXED_MONTHLY and self.water_fixed_amount:
            total += self.water_fixed_amount
        
        return total.quantize(Decimal("0.01"))

    @computed_field
    @property
    def is_currently_effective(self) -> bool:
        """Check if fee structure is currently in effect."""
        today = Date.today()
        
        if today < self.effective_from:
            return False
        
        if self.effective_to is not None and today > self.effective_to:
            return False
        
        return True

    @computed_field
    @property
    def status_display(self) -> str:
        """Get user-friendly status display."""
        if not self.is_active:
            return "Inactive"
        
        if not self.is_currently_effective:
            if Date.today() < self.effective_from:
                return "Scheduled"
            else:
                return "Expired"
        
        return "Active"

    @computed_field
    @property
    def has_variable_charges(self) -> bool:
        """Check if structure includes variable charges."""
        return (
            self.electricity_charges == ChargeType.ACTUAL
            or self.water_charges == ChargeType.ACTUAL
        )


class FeeDetail(BaseSchema):
    """
    Detailed fee information for a room type.
    
    Assembled view optimized for UI display with all calculations
    pre-computed.
    """

    room_type: RoomType = Field(
        ...,
        description="Room type",
    )
    room_type_display: str = Field(
        ...,
        description="Human-readable room type name",
    )

    fee_type: FeeType = Field(
        ...,
        description="Billing frequency",
    )

    # Breakdown - decimal_places removed
    amount: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Base rent amount (precision: 2 decimal places)",
    )
    security_deposit: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Security deposit (precision: 2 decimal places)",
    )

    includes_mess: bool = Field(
        ...,
        description="Mess included",
    )
    mess_charges_monthly: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Monthly mess charges (precision: 2 decimal places)",
    )

    # Calculated Totals
    total_first_month_payable: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Total amount due for first month (including security deposit, precision: 2 decimal places)",
    )
    total_recurring_monthly: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Recurring monthly charges (precision: 2 decimal places)",
    )

    # Utility Information
    utilities_included: bool = Field(
        ...,
        description="Whether utilities are included in base rent",
    )
    utilities_description: str = Field(
        ...,
        description="Description of utility billing",
    )

    # Availability
    available_beds: int = Field(
        ...,
        ge=0,
        description="Number of available beds for this room type",
    )

    # Discounts
    has_discounts: bool = Field(
        default=False,
        description="Whether discounts are available",
    )
    discount_info: Union[str, None] = Field(
        default=None,
        description="Discount information",
    )

    @field_validator(
        "amount", "security_deposit", "mess_charges_monthly",
        "total_first_month_payable", "total_recurring_monthly"
    )
    @classmethod
    def quantize_decimal_fields(cls, v: Decimal) -> Decimal:
        """Quantize decimal fields to 2 decimal places."""
        return v.quantize(Decimal("0.01"))

    @computed_field
    @property
    def is_available(self) -> bool:
        """Check if room type has availability."""
        return self.available_beds > 0

    @computed_field
    @property
    def savings_with_longer_stay(self) -> Union[Decimal, None]:
        """Calculate potential savings with longer billing periods."""
        # This would be calculated based on quarterly/yearly discounts
        # Placeholder for business logic
        return None


class FeeStructureList(BaseSchema):
    """
    List of fee structures for a hostel.
    
    Provides organized view of all fee structures.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )

    # Fee Structures
    items: List[FeeStructureResponse] = Field(
        default_factory=list,
        description="List of fee structures",
    )

    # Summary Statistics
    total_structures: int = Field(
        ...,
        ge=0,
        description="Total number of fee structures",
    )
    active_structures: int = Field(
        ...,
        ge=0,
        description="Number of active structures",
    )

    # Price Range - decimal_places removed
    min_monthly_rent: Union[Decimal, None] = Field(
        default=None,
        ge=Decimal("0"),
        description="Minimum monthly rent across all room types (precision: 2 decimal places)",
    )
    max_monthly_rent: Union[Decimal, None] = Field(
        default=None,
        ge=Decimal("0"),
        description="Maximum monthly rent across all room types (precision: 2 decimal places)",
    )

    @field_validator("min_monthly_rent", "max_monthly_rent")
    @classmethod
    def quantize_optional_decimals(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Quantize optional decimal fields to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @computed_field
    @property
    def price_range_display(self) -> str:
        """Get formatted price range."""
        if self.min_monthly_rent is None or self.max_monthly_rent is None:
            return "Not available"
        
        if self.min_monthly_rent == self.max_monthly_rent:
            return f"₹{self.min_monthly_rent:,.2f}/month"
        
        return f"₹{self.min_monthly_rent:,.2f} - ₹{self.max_monthly_rent:,.2f}/month"

    @computed_field
    @property
    def room_types_available(self) -> List[str]:
        """Get list of available room types."""
        return list(set(item.room_type.value for item in self.items if item.is_active))


class FeeHistoryItem(BaseSchema):
    """
    Individual fee history entry.
    
    Represents a single historical fee structure.
    """

    fee_structure_id: UUID = Field(
        ...,
        description="Fee structure ID",
    )

    room_type: RoomType = Field(
        ...,
        description="Room type",
    )

    # decimal_places removed
    amount: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Rent amount (precision: 2 decimal places)",
    )

    effective_from: Date = Field(
        ...,
        description="Effective start Date",
    )
    effective_to: Union[Date, None] = Field(
        default=None,
        description="Effective end Date",
    )

    # Change Information
    changed_by: Union[UUID, None] = Field(
        default=None,
        description="Admin who made the change",
    )
    changed_by_name: Union[str, None] = Field(
        default=None,
        description="Name of admin who made change",
    )
    change_reason: Union[str, None] = Field(
        default=None,
        description="Reason for change",
    )

    # Previous Value (for comparison)
    previous_amount: Union[Decimal, None] = Field(
        default=None,
        ge=Decimal("0"),
        description="Previous rent amount (precision: 2 decimal places)",
    )

    @field_validator("amount", "previous_amount")
    @classmethod
    def quantize_decimal_fields(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Quantize decimal fields to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @computed_field
    @property
    def amount_change(self) -> Union[Decimal, None]:
        """Calculate amount change from previous."""
        if self.previous_amount is None:
            return None
        return (self.amount - self.previous_amount).quantize(Decimal("0.01"))

    @computed_field
    @property
    def amount_change_percentage(self) -> Union[Decimal, None]:
        """Calculate percentage change."""
        if self.previous_amount is None or self.previous_amount == 0:
            return None
        
        change = ((self.amount - self.previous_amount) / self.previous_amount) * 100
        return Decimal(str(change)).quantize(Decimal("0.01"))

    @computed_field
    @property
    def is_increase(self) -> bool:
        """Check if this was a price increase."""
        if self.amount_change is None:
            return False
        return self.amount_change > 0


class FeeHistory(BaseSchema):
    """
    Fee history for a hostel/room type.
    
    Tracks all historical changes to fee structures.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    room_type: RoomType = Field(
        ...,
        description="Room type",
    )

    # History Entries
    history: List[FeeHistoryItem] = Field(
        default_factory=list,
        description="List of historical fee structures (ordered by Date)",
    )

    # Statistics
    total_changes: int = Field(
        ...,
        ge=0,
        description="Total number of fee changes",
    )
    average_change_interval_days: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Average days between fee changes",
    )

    @computed_field
    @property
    def current_fee(self) -> Union[FeeHistoryItem, None]:
        """Get current active fee structure."""
        today = Date.today()
        
        for entry in self.history:
            if entry.effective_from <= today:
                if entry.effective_to is None or entry.effective_to >= today:
                    return entry
        
        return None

    @computed_field
    @property
    def total_increases(self) -> int:
        """Count number of price increases."""
        return sum(1 for entry in self.history if entry.is_increase)

    @computed_field
    @property
    def total_decreases(self) -> int:
        """Count number of price decreases."""
        return sum(
            1 for entry in self.history 
            if entry.amount_change is not None and entry.amount_change < 0
        )


class FeeCalculation(BaseSchema):
    """
    Fee calculation result.
    
    Contains detailed calculation for a specific student booking
    or fee estimation.
    """

    # Input Parameters
    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )
    room_type: RoomType = Field(
        ...,
        description="Room type",
    )
    fee_type: FeeType = Field(
        ...,
        description="Billing frequency",
    )
    stay_duration_months: int = Field(
        ...,
        ge=1,
        description="Stay duration in months",
    )

    # Base Charges - decimal_places removed
    monthly_rent: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Monthly rent (precision: 2 decimal places)",
    )
    security_deposit: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Security deposit (precision: 2 decimal places)",
    )

    # Additional Charges
    mess_charges_total: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Total mess charges for duration (precision: 2 decimal places)",
    )
    utility_charges_estimated: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Estimated utility charges (precision: 2 decimal places)",
    )

    # Discounts
    discount_applied: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Total discount amount (precision: 2 decimal places)",
    )
    discount_description: Union[str, None] = Field(
        default=None,
        description="Discount details",
    )

    # Totals
    subtotal: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Subtotal before discount (precision: 2 decimal places)",
    )
    total_payable: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Total amount payable (precision: 2 decimal places)",
    )
    first_month_total: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Amount due for first month (precision: 2 decimal places)",
    )

    # Payment Schedule
    monthly_recurring: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Recurring monthly amount (precision: 2 decimal places)",
    )

    # Breakdown by Period
    payment_schedule: Dict[int, Decimal] = Field(
        default_factory=dict,
        description="Payment schedule by month number",
    )

    @field_validator(
        "monthly_rent", "security_deposit", "mess_charges_total",
        "utility_charges_estimated", "discount_applied", "subtotal",
        "total_payable", "first_month_total", "monthly_recurring"
    )
    @classmethod
    def quantize_decimal_fields(cls, v: Decimal) -> Decimal:
        """Quantize decimal fields to 2 decimal places."""
        return v.quantize(Decimal("0.01"))

    @computed_field
    @property
    def average_monthly_cost(self) -> Decimal:
        """Calculate average monthly cost including all charges."""
        if self.stay_duration_months == 0:
            return Decimal("0.00")
        
        # Exclude security deposit from average (it's refundable)
        total_without_deposit = self.total_payable - self.security_deposit
        
        return (total_without_deposit / self.stay_duration_months).quantize(
            Decimal("0.01")
        )

    @computed_field
    @property
    def total_savings(self) -> Decimal:
        """Calculate total savings from discounts."""
        return self.discount_applied

    @computed_field
    @property
    def savings_percentage(self) -> Decimal:
        """Calculate savings as percentage of original amount."""
        if self.subtotal == 0:
            return Decimal("0.00")
        
        return ((self.discount_applied / self.subtotal) * 100).quantize(
            Decimal("0.01")
        )