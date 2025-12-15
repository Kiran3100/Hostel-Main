# --- File: app/schemas/fee_structure/fee_config.py ---
"""
Fee configuration and breakdown schemas.

This module defines schemas for fee calculations, breakdowns,
and comprehensive fee configurations.
"""

from __future__ import annotations

from datetime import date as Date
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID

from pydantic import Field, computed_field, field_validator

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import ChargeType, FeeType, RoomType

__all__ = [
    "ChargesBreakdown",
    "FeeConfiguration",
    "FeeComparison",
    "DiscountConfiguration",
]


class ChargesBreakdown(BaseSchema):
    """
    Detailed breakdown of all fee components.
    
    Provides transparent itemization of all charges that make up
    the total fee for a student.
    """

    # Base Components - decimal_places removed
    base_rent: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Base rent per period (precision: 2 decimal places)",
    )
    mess_charges: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Mess/food charges (precision: 2 decimal places)",
    )
    electricity_charges: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Electricity charges (precision: 2 decimal places)",
    )
    water_charges: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Water charges (precision: 2 decimal places)",
    )
    other_charges: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Other miscellaneous charges (precision: 2 decimal places)",
    )

    # Totals
    total_monthly: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Total monthly recurring charges (precision: 2 decimal places)",
    )
    total_first_month: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Total for first month (may include one-time charges, precision: 2 decimal places)",
    )
    security_deposit: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="One-time refundable security deposit (precision: 2 decimal places)",
    )

    # Optional Discount
    discount_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Total discount applied (precision: 2 decimal places)",
    )
    discount_percentage: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Discount as percentage (precision: 2 decimal places)",
    )

    # Tax (if applicable)
    tax_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Tax amount (GST, etc., precision: 2 decimal places)",
    )
    tax_percentage: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Tax rate as percentage (precision: 2 decimal places)",
    )

    @field_validator(
        "base_rent", "mess_charges", "electricity_charges", "water_charges",
        "other_charges", "total_monthly", "total_first_month", "security_deposit",
        "discount_amount", "discount_percentage", "tax_amount", "tax_percentage"
    )
    @classmethod
    def quantize_decimal_fields(cls, v: Decimal) -> Decimal:
        """Quantize all decimal fields to 2 decimal places."""
        return v.quantize(Decimal("0.01"))

    @computed_field
    @property
    def subtotal(self) -> Decimal:
        """Calculate subtotal before discount and tax."""
        return (
            self.base_rent
            + self.mess_charges
            + self.electricity_charges
            + self.water_charges
            + self.other_charges
        ).quantize(Decimal("0.01"))

    @computed_field
    @property
    def total_after_discount(self) -> Decimal:
        """Calculate total after applying discount."""
        return (self.total_monthly - self.discount_amount).quantize(Decimal("0.01"))

    @computed_field
    @property
    def grand_total(self) -> Decimal:
        """Calculate grand total including tax."""
        return (self.total_after_discount + self.tax_amount).quantize(Decimal("0.01"))

    @computed_field
    @property
    def total_upfront_payment(self) -> Decimal:
        """
        Calculate total upfront payment required.
        
        Includes security deposit + first month charges.
        """
        return (self.security_deposit + self.total_first_month).quantize(
            Decimal("0.01")
        )


class FeeConfiguration(BaseSchema):
    """
    Complete fee configuration for a hostel/room combination.
    
    Contains all pricing information and calculated breakdowns
    for a specific booking or student assignment.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    room_type: RoomType = Field(
        ...,
        description="Room type",
    )
    fee_type: FeeType = Field(
        ...,
        description="Billing frequency",
    )

    # Base Components - decimal_places removed
    base_amount: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Base rent amount (precision: 2 decimal places)",
    )
    security_deposit: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Security deposit (precision: 2 decimal places)",
    )

    # Mess Configuration
    includes_mess: bool = Field(
        ...,
        description="Whether mess is included",
    )
    mess_charges_monthly: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Monthly mess charges (precision: 2 decimal places)",
    )

    # Utility Configurations
    electricity_charges: ChargeType = Field(
        ...,
        description="Electricity billing method",
    )
    electricity_fixed_amount: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0"),
        description="Fixed electricity amount (precision: 2 decimal places)",
    )

    water_charges: ChargeType = Field(
        ...,
        description="Water billing method",
    )
    water_fixed_amount: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0"),
        description="Fixed water amount (precision: 2 decimal places)",
    )

    # Calculated Breakdown
    breakdown: ChargesBreakdown = Field(
        ...,
        description="Detailed charges breakdown",
    )

    # Additional Configuration
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Configuration description or notes",
    )

    @field_validator("base_amount", "security_deposit", "mess_charges_monthly")
    @classmethod
    def quantize_required_decimals(cls, v: Decimal) -> Decimal:
        """Quantize required decimal fields to 2 decimal places."""
        return v.quantize(Decimal("0.01"))

    @field_validator("electricity_fixed_amount", "water_fixed_amount")
    @classmethod
    def quantize_optional_decimals(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Quantize optional decimal fields to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @computed_field
    @property
    def has_variable_charges(self) -> bool:
        """Check if configuration includes variable/actual charges."""
        return (
            self.electricity_charges == ChargeType.ACTUAL
            or self.water_charges == ChargeType.ACTUAL
        )

    @computed_field
    @property
    def is_all_inclusive(self) -> bool:
        """Check if all charges are included in base rent."""
        return (
            self.includes_mess
            and self.electricity_charges == ChargeType.INCLUDED
            and self.water_charges == ChargeType.INCLUDED
        )


class DiscountConfiguration(BaseSchema):
    """
    Discount configuration schema.
    
    Defines various types of discounts that can be applied
    to fee structures.
    """

    discount_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Name of the discount",
    )
    discount_type: str = Field(
        ...,
        pattern=r"^(percentage|fixed_amount|waiver)$",
        description="Type of discount",
    )

    # Discount Value - decimal_places removed
    discount_percentage: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Discount percentage (if type is percentage, precision: 2 decimal places)",
    )
    discount_amount: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0"),
        description="Fixed discount amount (if type is fixed_amount, precision: 2 decimal places)",
    )

    # Applicability
    applies_to: str = Field(
        ...,
        pattern=r"^(base_rent|mess_charges|total|security_deposit)$",
        description="What the discount applies to",
    )

    # Conditions
    minimum_stay_months: Optional[int] = Field(
        default=None,
        ge=1,
        description="Minimum stay required for discount",
    )
    valid_for_new_students_only: bool = Field(
        default=False,
        description="Whether discount is only for new students",
    )

    # Validity
    valid_from: Optional[Date] = Field(
        default=None,
        description="Discount valid from Date",
    )
    valid_to: Optional[Date] = Field(
        default=None,
        description="Discount valid until Date",
    )

    is_active: bool = Field(
        default=True,
        description="Whether discount is currently active",
    )

    @field_validator("discount_type", "applies_to")
    @classmethod
    def normalize_string_fields(cls, v: str) -> str:
        """Normalize string fields to lowercase."""
        return v.lower()

    @field_validator("discount_name")
    @classmethod
    def validate_discount_name(cls, v: str) -> str:
        """Validate discount name."""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Discount name must be at least 3 characters")
        return v

    @field_validator("discount_percentage", "discount_amount")
    @classmethod
    def quantize_optional_decimals(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Quantize optional decimal fields to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @computed_field
    @property
    def is_currently_valid(self) -> bool:
        """Check if discount is currently valid."""
        if not self.is_active:
            return False
        
        today = Date.today()
        
        if self.valid_from and today < self.valid_from:
            return False
        
        if self.valid_to and today > self.valid_to:
            return False
        
        return True


class FeeComparison(BaseSchema):
    """
    Fee comparison schema for comparing different room types or periods.
    
    Useful for displaying pricing comparisons to potential students.
    """

    room_types: Dict[str, ChargesBreakdown] = Field(
        ...,
        description="Breakdown by room type",
    )

    # Comparison Metadata
    hostel_id: UUID = Field(
        ...,
        description="Hostel being compared",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    fee_type: FeeType = Field(
        ...,
        description="Billing frequency for comparison",
    )

    # Recommendations
    most_economical: str = Field(
        ...,
        description="Most economical room type",
    )
    most_popular: Optional[str] = Field(
        default=None,
        description="Most popular room type",
    )
    best_value: Optional[str] = Field(
        default=None,
        description="Best value room type",
    )

    @computed_field
    @property
    def price_range(self) -> str:
        """Get price range across all room types."""
        if not self.room_types:
            return "Not available"
        
        prices = [breakdown.total_monthly for breakdown in self.room_types.values()]
        min_price = min(prices)
        max_price = max(prices)
        
        return f"₹{min_price:,.2f} - ₹{max_price:,.2f}"

    @computed_field
    @property
    def average_price(self) -> Decimal:
        """Calculate average price across room types."""
        if not self.room_types:
            return Decimal("0.00")
        
        total = sum(breakdown.total_monthly for breakdown in self.room_types.values())
        return (total / len(self.room_types)).quantize(Decimal("0.01"))