# --- File: app/schemas/fee_structure/charge_component.py ---
"""
Charge Component Schemas

This module defines schemas for individual charge components that
make up a fee structure (rent, utilities, maintenance, etc.).
"""

from datetime import date as Date
from decimal import Decimal
from typing import Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import ChargeType

__all__ = [
    "ChargeComponentBase",
    "ChargeComponentCreate",
    "ChargeComponentUpdate",
    "ChargeComponent",
]


class ChargeComponentBase(BaseSchema):
    """
    Base schema for charge components.
    
    A charge component represents an individual fee element within
    a fee structure (e.g., base rent, electricity, maintenance).
    """
    
    component_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Name of the charge component"
    )
    
    component_type: ChargeType = Field(
        ...,
        description="Type of charge (INCLUDED, ACTUAL, FIXED_MONTHLY)"
    )
    
    description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Detailed description of the component"
    )
    
    # Pricing
    amount: Union[Decimal, None] = Field(
        default=None,
        ge=Decimal("0"),
        description="Fixed amount (if applicable, precision: 2 decimal places)"
    )
    
    # Calculation Method
    is_percentage: bool = Field(
        default=False,
        description="Whether amount is a percentage of base rent"
    )
    
    percentage_value: Union[Decimal, None] = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Percentage value if is_percentage is True"
    )
    
    # Tax Configuration
    is_taxable: bool = Field(
        default=True,
        description="Whether this component is subject to tax"
    )
    
    tax_percentage: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Tax percentage applicable to this component"
    )
    
    # Billing Configuration
    is_mandatory: bool = Field(
        default=True,
        description="Whether this component is mandatory"
    )
    
    is_refundable: bool = Field(
        default=False,
        description="Whether this component is refundable"
    )
    
    billing_frequency: str = Field(
        default="monthly",
        pattern=r"^(monthly|quarterly|yearly|one_time)$",
        description="How often this component is billed"
    )
    
    # Conditional Application
    applies_to_all_rooms: bool = Field(
        default=True,
        description="Whether component applies to all room types"
    )
    
    min_stay_months: Union[int, None] = Field(
        default=None,
        ge=1,
        description="Minimum stay months required for this component"
    )
    
    # Status
    is_active: bool = Field(
        default=True,
        description="Whether this component is currently active"
    )
    
    effective_from: Union[Date, None] = Field(
        default=None,
        description="Date from which this component is effective"
    )
    
    effective_to: Union[Date, None] = Field(
        default=None,
        description="Date until which this component is effective"
    )
    
    # Display
    display_order: int = Field(
        default=0,
        ge=0,
        description="Order in which to display this component"
    )
    
    @field_validator("component_name")
    @classmethod
    def validate_component_name(cls, v: str) -> str:
        """Validate and normalize component name."""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Component name must be at least 3 characters")
        return v
    
    @field_validator("amount", "percentage_value", "tax_percentage")
    @classmethod
    def quantize_optional_decimals(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Quantize optional decimal fields to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v
    
    @field_validator("billing_frequency")
    @classmethod
    def normalize_billing_frequency(cls, v: str) -> str:
        """Normalize billing frequency."""
        return v.lower()
    
    @model_validator(mode="after")
    def validate_charge_component(self):
        """Validate charge component constraints."""
        # Validate percentage-based charges
        if self.is_percentage:
            if self.percentage_value is None or self.percentage_value <= 0:
                raise ValueError(
                    "percentage_value is required and must be greater than 0 "
                    "when is_percentage is True"
                )
            # Clear fixed amount if percentage-based
            object.__setattr__(self, 'amount', None)
        else:
            # For fixed charges
            if self.component_type == ChargeType.FIXED_MONTHLY:
                if self.amount is None or self.amount <= 0:
                    raise ValueError(
                        "amount is required and must be greater than 0 "
                        "when component_type is FIXED_MONTHLY"
                    )
            # Clear percentage if not percentage-based
            object.__setattr__(self, 'percentage_value', None)
        
        # Validate effective dates
        if self.effective_from and self.effective_to:
            if self.effective_to <= self.effective_from:
                raise ValueError(
                    "effective_to must be after effective_from"
                )
        
        return self
    
    @computed_field
    @property
    def is_currently_effective(self) -> bool:
        """Check if component is currently effective."""
        if not self.is_active:
            return False
        
        today = Date.today()
        
        if self.effective_from and today < self.effective_from:
            return False
        
        if self.effective_to and today > self.effective_to:
            return False
        
        return True


class ChargeComponentCreate(ChargeComponentBase, BaseCreateSchema):
    """
    Schema for creating a new charge component.
    
    Requires fee_structure_id to associate with a fee structure.
    """
    
    fee_structure_id: UUID = Field(
        ...,
        description="Fee structure this component belongs to"
    )
    
    @model_validator(mode="after")
    def validate_create_component(self):
        """Additional validation for component creation."""
        # Set default effective_from if not provided
        if self.effective_from is None:
            object.__setattr__(self, 'effective_from', Date.today())
        
        return self


class ChargeComponentUpdate(BaseUpdateSchema):
    """
    Schema for updating an existing charge component.
    
    All fields are optional for partial updates.
    """
    
    component_name: Union[str, None] = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="Update component name"
    )
    
    component_type: Union[ChargeType, None] = Field(
        default=None,
        description="Update component type"
    )
    
    description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Update description"
    )
    
    amount: Union[Decimal, None] = Field(
        default=None,
        ge=Decimal("0"),
        description="Update fixed amount"
    )
    
    is_percentage: Union[bool, None] = Field(
        default=None,
        description="Update percentage flag"
    )
    
    percentage_value: Union[Decimal, None] = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Update percentage value"
    )
    
    is_taxable: Union[bool, None] = Field(
        default=None,
        description="Update taxable flag"
    )
    
    tax_percentage: Union[Decimal, None] = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Update tax percentage"
    )
    
    is_mandatory: Union[bool, None] = Field(
        default=None,
        description="Update mandatory flag"
    )
    
    is_refundable: Union[bool, None] = Field(
        default=None,
        description="Update refundable flag"
    )
    
    billing_frequency: Union[str, None] = Field(
        default=None,
        pattern=r"^(monthly|quarterly|yearly|one_time)$",
        description="Update billing frequency"
    )
    
    is_active: Union[bool, None] = Field(
        default=None,
        description="Update active status"
    )
    
    display_order: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Update display order"
    )
    
    @field_validator("amount", "percentage_value", "tax_percentage")
    @classmethod
    def quantize_optional_decimals(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Quantize optional decimal fields to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v
    
    @field_validator("component_name")
    @classmethod
    def validate_component_name(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate component name if provided."""
        if v is not None:
            v = v.strip()
            if len(v) < 3:
                raise ValueError("Component name must be at least 3 characters")
        return v


class ChargeComponent(ChargeComponentBase):
    """
    Complete charge component response schema.
    
    Includes all base fields plus database-generated fields.
    """
    
    id: UUID = Field(
        ...,
        description="Unique identifier of the component"
    )
    
    fee_structure_id: UUID = Field(
        ...,
        description="Associated fee structure ID"
    )
    
    # Audit fields
    created_by: Union[UUID, None] = Field(
        default=None,
        description="User who created this component"
    )
    
    created_by_name: Union[str, None] = Field(
        default=None,
        description="Name of user who created this component"
    )
    
    updated_by: Union[UUID, None] = Field(
        default=None,
        description="User who last updated this component"
    )
    
    updated_by_name: Union[str, None] = Field(
        default=None,
        description="Name of user who last updated this component"
    )
    
    @computed_field
    @property
    def calculated_amount(self) -> Union[Decimal, None]:
        """
        Get the calculated amount for display purposes.
        
        Note: Percentage-based amounts need base rent context
        which should be provided by the service layer.
        """
        if self.is_percentage:
            return None  # Requires base rent context
        return self.amount
    
    @computed_field
    @property
    def amount_with_tax(self) -> Union[Decimal, None]:
        """Calculate amount including tax."""
        if self.amount is None:
            return None
        
        if not self.is_taxable or self.tax_percentage == 0:
            return self.amount
        
        tax = self.amount * (self.tax_percentage / Decimal("100"))
        return (self.amount + tax).quantize(Decimal("0.01"))
    
    @computed_field
    @property
    def component_category(self) -> str:
        """Categorize component for grouping."""
        name_lower = self.component_name.lower()
        
        if any(word in name_lower for word in ["rent", "rental"]):
            return "rent"
        elif any(word in name_lower for word in ["electricity", "water", "utility"]):
            return "utilities"
        elif any(word in name_lower for word in ["security", "deposit"]):
            return "deposits"
        elif any(word in name_lower for word in ["maintenance", "cleaning"]):
            return "maintenance"
        elif any(word in name_lower for word in ["mess", "food", "meal"]):
            return "food"
        else:
            return "other"