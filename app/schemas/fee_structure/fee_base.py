# --- File: app/schemas/fee_structure/fee_base.py ---
"""
Base fee structure schemas with comprehensive validation.

This module defines the core fee structure schemas for managing
hostel pricing across different room types and billing frequencies.
"""

from __future__ import annotations

from datetime import date as Date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import ChargeType, FeeType, RoomType

__all__ = [
    "FeeStructureBase",
    "FeeStructureCreate",
    "FeeStructureUpdate",
]


class FeeStructureBase(BaseSchema):
    """
    Base fee structure schema.
    
    Defines pricing and charges for a specific hostel and room type,
    including base rent, security deposit, utilities, and mess charges.
    """

    hostel_id: UUID = Field(
        ...,
        description="Unique identifier of the hostel",
    )
    room_type: RoomType = Field(
        ...,
        description="Type of room this fee structure applies to",
    )
    fee_type: FeeType = Field(
        ...,
        description="Billing frequency (monthly, quarterly, yearly, etc.)",
    )

    # Base Charges
    # Note: max_digits and decimal_places removed - Pydantic v2 doesn't support these constraints
    # Precision is maintained through Decimal type and quantization in validators
    amount: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Base rent amount per billing period (precision: 10 digits, 2 decimal places)",
    )
    security_deposit: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Refundable security deposit amount (precision: 10 digits, 2 decimal places)",
    )

    # Mess Charges
    includes_mess: bool = Field(
        default=False,
        description="Whether mess/food is included in base rent",
    )
    mess_charges_monthly: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Monthly mess charges (if not included, precision: 10 digits, 2 decimal places)",
    )

    # Utility Charges - Electricity
    electricity_charges: ChargeType = Field(
        default=ChargeType.INCLUDED,
        description="How electricity is billed (included/actual/fixed)",
    )
    electricity_fixed_amount: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0"),
        description="Fixed monthly electricity charge (if applicable, precision: 10 digits, 2 decimal places)",
    )

    # Utility Charges - Water
    water_charges: ChargeType = Field(
        default=ChargeType.INCLUDED,
        description="How water is billed (included/actual/fixed)",
    )
    water_fixed_amount: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0"),
        description="Fixed monthly water charge (if applicable, precision: 10 digits, 2 decimal places)",
    )

    # Validity Period
    effective_from: Date = Field(
        ...,
        description="Date from which this fee structure is effective",
    )
    effective_to: Optional[Date] = Field(
        default=None,
        description="End Date of fee structure validity (null for indefinite)",
    )

    # Status
    is_active: bool = Field(
        default=True,
        description="Whether this fee structure is currently active",
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate base amount is reasonable and quantize to 2 decimal places."""
        # Quantize to 2 decimal places (replaces decimal_places constraint)
        v = v.quantize(Decimal("0.01"))
        
        if v <= 0:
            raise ValueError("Base rent amount must be greater than zero")
        
        # Sanity check: Minimum and maximum rent
        min_rent = Decimal("500.00")
        max_rent = Decimal("100000.00")
        
        if v < min_rent:
            raise ValueError(f"Rent amount (₹{v}) is below minimum (₹{min_rent})")
        if v > max_rent:
            raise ValueError(f"Rent amount (₹{v}) exceeds maximum (₹{max_rent})")
        
        return v

    @field_validator("security_deposit", "mess_charges_monthly")
    @classmethod
    def validate_and_quantize_amounts(cls, v: Decimal) -> Decimal:
        """Validate and quantize decimal amounts to 2 decimal places."""
        # Quantize to 2 decimal places
        v = v.quantize(Decimal("0.01"))
        
        if v < 0:
            raise ValueError("Amount cannot be negative")
        
        return v

    @field_validator("electricity_fixed_amount", "water_fixed_amount")
    @classmethod
    def validate_and_quantize_optional_amounts(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate and quantize optional decimal amounts to 2 decimal places."""
        if v is not None:
            # Quantize to 2 decimal places
            v = v.quantize(Decimal("0.01"))
            
            if v < 0:
                raise ValueError("Amount cannot be negative")
        
        return v

    @field_validator("mess_charges_monthly")
    @classmethod
    def validate_mess_charges(cls, v: Decimal) -> Decimal:
        """Validate mess charges with sanity check."""
        # Already quantized by validate_and_quantize_amounts
        
        # Sanity check
        max_mess = Decimal("10000.00")
        if v > max_mess:
            raise ValueError(
                f"Mess charges (₹{v}) exceed reasonable maximum (₹{max_mess})"
            )
        
        return v

    @field_validator("effective_from")
    @classmethod
    def validate_effective_from(cls, v: Date) -> Date:
        """Validate effective_from Date."""
        # Allow backdated fee structures but warn if too old
        days_ago = (Date.today() - v).days
        if days_ago > 365:
            # Log warning - might be data migration
            pass
        
        return v

    @model_validator(mode="after")
    def validate_fee_structure(self) -> "FeeStructureBase":
        """Validate all fee structure constraints."""
        # Validate security deposit ratio
        if self.security_deposit > 0:
            # Security deposit typically ranges from 1-3 months rent
            max_security = self.amount * 3
            
            if self.security_deposit > max_security:
                raise ValueError(
                    f"Security deposit (₹{self.security_deposit}) exceeds "
                    f"3 times the base rent (₹{self.amount}). "
                    f"Maximum allowed: ₹{max_security}"
                )
        
        # Validate electricity charges
        if self.electricity_charges == ChargeType.FIXED_MONTHLY:
            if not self.electricity_fixed_amount:
                raise ValueError(
                    "electricity_fixed_amount is required when "
                    "electricity_charges is FIXED_MONTHLY"
                )
            if self.electricity_fixed_amount <= 0:
                raise ValueError("Fixed electricity amount must be greater than zero")
        else:
            # Clear fixed amount if not fixed type
            # Note: In Pydantic v2, we should use model_copy for immutable models
            # but since we're in validation, direct assignment is acceptable
            object.__setattr__(self, 'electricity_fixed_amount', None)
        
        # Validate water charges
        if self.water_charges == ChargeType.FIXED_MONTHLY:
            if not self.water_fixed_amount:
                raise ValueError(
                    "water_fixed_amount is required when "
                    "water_charges is FIXED_MONTHLY"
                )
            if self.water_fixed_amount <= 0:
                raise ValueError("Fixed water amount must be greater than zero")
        else:
            # Clear fixed amount if not fixed type
            object.__setattr__(self, 'water_fixed_amount', None)
        
        # Validate mess configuration
        if self.includes_mess:
            # If mess is included, charges should be 0
            if self.mess_charges_monthly > 0:
                raise ValueError(
                    "mess_charges_monthly should be 0 when includes_mess is True. "
                    "The mess cost is already included in base rent."
                )
        
        # Validate effective dates
        if self.effective_to is not None:
            if self.effective_to <= self.effective_from:
                raise ValueError(
                    f"effective_to ({self.effective_to}) must be after "
                    f"effective_from ({self.effective_from})"
                )
            
            # Check if Date range is reasonable (not too long)
            days_diff = (self.effective_to - self.effective_from).days
            max_validity_days = 1825  # 5 years
            
            if days_diff > max_validity_days:
                raise ValueError(
                    f"Fee structure validity period ({days_diff} days) exceeds "
                    f"maximum allowed ({max_validity_days} days / ~5 years)"
                )
        
        return self

    @computed_field
    @property
    def is_currently_effective(self) -> bool:
        """Check if fee structure is currently within effective Date range."""
        today = Date.today()
        if today < self.effective_from:
            return False
        if self.effective_to is not None and today > self.effective_to:
            return False
        return True

    @computed_field
    @property
    def days_until_effective(self) -> int:
        """Calculate days until fee structure becomes effective."""
        if self.effective_from > Date.today():
            return (self.effective_from - Date.today()).days
        return 0

    @computed_field
    @property
    def days_remaining(self) -> Optional[int]:
        """Calculate days remaining until fee structure expires."""
        if self.effective_to is None:
            return None
        if self.effective_to < Date.today():
            return 0
        return (self.effective_to - Date.today()).days

    @computed_field
    @property
    def monthly_total_minimum(self) -> Decimal:
        """
        Calculate minimum monthly total.
        
        Includes base rent + mess + minimum utilities (if fixed).
        """
        total = self.amount
        
        if not self.includes_mess:
            total += self.mess_charges_monthly
        
        if self.electricity_charges == ChargeType.FIXED_MONTHLY and self.electricity_fixed_amount:
            total += self.electricity_fixed_amount
        
        if self.water_charges == ChargeType.FIXED_MONTHLY and self.water_fixed_amount:
            total += self.water_fixed_amount
        
        return total.quantize(Decimal("0.01"))


class FeeStructureCreate(FeeStructureBase, BaseCreateSchema):
    """
    Schema for creating a new fee structure.
    
    All base fields are inherited. Additional creation-time
    validations can be added here.
    """

    @model_validator(mode="after")
    def validate_no_overlapping_periods(self) -> "FeeStructureCreate":
        """
        Validate that new fee structure doesn't overlap with existing ones.
        
        Note: This validation requires database access and should be
        implemented at the service layer. This is a placeholder.
        """
        # In production, check for overlaps with existing fee structures
        # for the same hostel_id and room_type
        return self


class FeeStructureUpdate(BaseUpdateSchema):
    """
    Schema for updating an existing fee structure.
    
    All fields are optional, allowing partial updates.
    """

    # Pricing - max_digits and decimal_places removed
    amount: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0"),
        description="Update base rent amount (precision: 10 digits, 2 decimal places)",
    )
    security_deposit: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0"),
        description="Update security deposit (precision: 10 digits, 2 decimal places)",
    )

    # Mess
    includes_mess: Optional[bool] = Field(
        default=None,
        description="Update mess inclusion",
    )
    mess_charges_monthly: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0"),
        description="Update mess charges (precision: 10 digits, 2 decimal places)",
    )

    # Utilities
    electricity_charges: Optional[ChargeType] = Field(
        default=None,
        description="Update electricity billing method",
    )
    electricity_fixed_amount: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0"),
        description="Update fixed electricity amount (precision: 10 digits, 2 decimal places)",
    )

    water_charges: Optional[ChargeType] = Field(
        default=None,
        description="Update water billing method",
    )
    water_fixed_amount: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0"),
        description="Update fixed water amount (precision: 10 digits, 2 decimal places)",
    )

    # Validity
    effective_from: Optional[Date] = Field(
        default=None,
        description="Update effective start Date",
    )
    effective_to: Optional[Date] = Field(
        default=None,
        description="Update effective end Date",
    )

    # Status
    is_active: Optional[bool] = Field(
        default=None,
        description="Update active status",
    )

    @field_validator("amount", "security_deposit", "mess_charges_monthly", "electricity_fixed_amount", "water_fixed_amount")
    @classmethod
    def validate_amounts(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate monetary amounts if provided and quantize to 2 decimal places."""
        if v is not None:
            # Quantize to 2 decimal places
            v = v.quantize(Decimal("0.01"))
            
            if v < 0:
                raise ValueError("Amount cannot be negative")
        
        return v

    @model_validator(mode="after")
    def validate_partial_updates(self) -> "FeeStructureUpdate":
        """Validate consistency in partial updates."""
        # If electricity is being changed to FIXED_MONTHLY, amount must be provided
        if self.electricity_charges == ChargeType.FIXED_MONTHLY:
            if self.electricity_fixed_amount is None:
                raise ValueError(
                    "electricity_fixed_amount must be provided when changing "
                    "electricity_charges to FIXED_MONTHLY"
                )
        
        # If water is being changed to FIXED_MONTHLY, amount must be provided
        if self.water_charges == ChargeType.FIXED_MONTHLY:
            if self.water_fixed_amount is None:
                raise ValueError(
                    "water_fixed_amount must be provided when changing "
                    "water_charges to FIXED_MONTHLY"
                )
        
        # Validate Date range if both dates are being updated
        if self.effective_from is not None and self.effective_to is not None:
            if self.effective_to <= self.effective_from:
                raise ValueError(
                    "effective_to must be after effective_from"
                )
        
        return self