# --- File: C:\Hostel-Main\app\models\fee_structure\charge_component.py ---
"""
Charge Component Model

Manages individual fee components and detailed charge breakdown.
Maps to fee_structure/fee_config.py schemas.
"""

from datetime import date as Date
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date as SQLDate,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin


class ChargeComponent(BaseModel, TimestampModel, UUIDMixin, SoftDeleteMixin):
    """
    Charge Component Model
    
    Detailed breakdown of individual fee components that make up
    the total fee structure. Allows for flexible charge composition.
    """
    
    __tablename__ = "charge_components"
    
    # Foreign Keys
    fee_structure_id: Mapped[UUID] = mapped_column(
        ForeignKey("fee_structures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Component Details
    component_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    component_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    
    # Amount Details
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
    )
    
    is_mandatory: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    is_refundable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    is_recurring: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    # Calculation Details
    calculation_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="fixed",
    )
    
    calculation_basis: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    proration_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    # Tax Details
    is_taxable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    tax_percentage: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )
    
    # Description
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    display_order: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )
    
    # Visibility
    is_visible_to_student: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    # Applicability Rules
    applies_to_room_types: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Comma-separated room types",
    )
    
    applies_from_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
    )
    
    applies_to_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
    )
    
    # Relationships
    fee_structure = relationship(
        "FeeStructure",
        back_populates="charge_components",
    )
    
    charge_rules = relationship(
        "ChargeRule",
        back_populates="charge_component",
        cascade="all, delete-orphan",
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "amount >= 0",
            name="ck_charge_component_amount_positive",
        ),
        CheckConstraint(
            "tax_percentage >= 0 AND tax_percentage <= 100",
            name="ck_charge_component_tax_range",
        ),
        CheckConstraint(
            "component_type IN ('rent', 'deposit', 'mess', 'electricity', 'water', 'maintenance', 'amenity', 'other')",
            name="ck_charge_component_type",
        ),
        CheckConstraint(
            "calculation_method IN ('fixed', 'variable', 'percentage', 'tiered', 'actual')",
            name="ck_charge_component_calculation_method",
        ),
        CheckConstraint(
            "applies_to_date IS NULL OR applies_to_date > applies_from_date",
            name="ck_charge_component_date_range",
        ),
        Index(
            "ix_charge_component_fee_structure_type",
            "fee_structure_id",
            "component_type",
        ),
        Index(
            "ix_charge_component_dates",
            "applies_from_date",
            "applies_to_date",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<ChargeComponent(id={self.id}, "
            f"name={self.component_name}, "
            f"type={self.component_type}, "
            f"amount={self.amount})>"
        )
    
    @property
    def total_amount_with_tax(self) -> Decimal:
        """Calculate total amount including tax."""
        tax_amount = (self.amount * self.tax_percentage / 100).quantize(Decimal("0.01"))
        return (self.amount + tax_amount).quantize(Decimal("0.01"))
    
    @property
    def tax_amount(self) -> Decimal:
        """Calculate tax amount."""
        return (self.amount * self.tax_percentage / 100).quantize(Decimal("0.01"))


class ChargeRule(BaseModel, TimestampModel, UUIDMixin):
    """
    Charge Rule Model
    
    Defines business rules for charge application and calculation.
    """
    
    __tablename__ = "charge_rules"
    
    # Foreign Keys
    charge_component_id: Mapped[UUID] = mapped_column(
        ForeignKey("charge_components.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Rule Details
    rule_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    rule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    
    rule_condition: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON or expression defining the rule condition",
    )
    
    rule_action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON or expression defining the rule action",
    )
    
    # Priority and Status
    priority: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    # Relationships
    charge_component = relationship(
        "ChargeComponent",
        back_populates="charge_rules",
    )
    
    __table_args__ = (
        CheckConstraint(
            "rule_type IN ('discount', 'surcharge', 'waiver', 'proration', 'conditional')",
            name="ck_charge_rule_type",
        ),
        Index(
            "ix_charge_rule_component_priority",
            "charge_component_id",
            "priority",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<ChargeRule(id={self.id}, "
            f"name={self.rule_name}, "
            f"type={self.rule_type})>"
        )


class DiscountConfiguration(BaseModel, TimestampModel, UUIDMixin, SoftDeleteMixin):
    """
    Discount Configuration Model
    
    Manages various types of discounts applicable to fee structures.
    Maps to fee_structure/fee_config.py DiscountConfiguration schema.
    """
    
    __tablename__ = "discount_configurations"
    
    # Discount Details
    discount_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    discount_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        unique=True,
        index=True,
    )
    
    discount_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    
    # Discount Value
    discount_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=5, scale=2),
        nullable=True,
    )
    
    discount_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
    )
    
    # Applicability
    applies_to: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    
    hostel_ids: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Comma-separated hostel IDs or NULL for all",
    )
    
    room_types: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Comma-separated room types or NULL for all",
    )
    
    # Conditions
    minimum_stay_months: Mapped[Optional[int]] = mapped_column(
        nullable=True,
    )
    
    valid_for_new_students_only: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    max_usage_count: Mapped[Optional[int]] = mapped_column(
        nullable=True,
    )
    
    current_usage_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )
    
    # Validity Period
    valid_from: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
    )
    
    valid_to: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    
    # Description
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    terms_and_conditions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "discount_type IN ('percentage', 'fixed_amount', 'waiver')",
            name="ck_discount_type",
        ),
        CheckConstraint(
            "applies_to IN ('base_rent', 'mess_charges', 'total', 'security_deposit')",
            name="ck_discount_applies_to",
        ),
        CheckConstraint(
            "discount_percentage IS NULL OR (discount_percentage >= 0 AND discount_percentage <= 100)",
            name="ck_discount_percentage_range",
        ),
        CheckConstraint(
            "discount_amount IS NULL OR discount_amount >= 0",
            name="ck_discount_amount_positive",
        ),
        CheckConstraint(
            "(discount_percentage IS NOT NULL AND discount_amount IS NULL) OR "
            "(discount_percentage IS NULL AND discount_amount IS NOT NULL)",
            name="ck_discount_value_exclusive",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_discount_date_range",
        ),
        CheckConstraint(
            "max_usage_count IS NULL OR max_usage_count > 0",
            name="ck_discount_max_usage_positive",
        ),
        CheckConstraint(
            "current_usage_count >= 0",
            name="ck_discount_current_usage_positive",
        ),
        Index(
            "ix_discount_active_dates",
            "is_active",
            "valid_from",
            "valid_to",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DiscountConfiguration(id={self.id}, "
            f"name={self.discount_name}, "
            f"type={self.discount_type})>"
        )
    
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
        
        if self.max_usage_count and self.current_usage_count >= self.max_usage_count:
            return False
        
        return True
    
    @property
    def remaining_usage_count(self) -> Optional[int]:
        """Get remaining usage count."""
        if self.max_usage_count is None:
            return None
        
        return max(0, self.max_usage_count - self.current_usage_count)