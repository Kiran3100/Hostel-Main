"""
Fee Calculation Model

Manages fee calculations, projections, and historical calculation records.
Maps to fee_structure/fee_response.py FeeCalculation schema.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date as SQLDate,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.enums import FeeType, RoomType
from app.models.base.mixins import UUIDMixin


class FeeBaseModel(UUIDMixin, TimestampModel, BaseModel):
    """Combined base model for fee-related entities."""
    __abstract__ = True


class FeeCalculation(FeeBaseModel):
    """
    Fee Calculation Model
    
    Stores detailed fee calculations for bookings, students, or estimates.
    Provides audit trail and historical calculation records.
    """
    
    __tablename__ = "fee_calculations"
    
    # Foreign Keys
    fee_structure_id: Mapped[UUID] = mapped_column(
        ForeignKey("fee_structures.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    
    student_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    
    booking_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    
    # Calculation Context
    calculation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    
    calculation_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        default=Date.today,
        index=True,
    )
    
    # Input Parameters
    room_type: Mapped[RoomType] = mapped_column(
        String(50),
        nullable=False,
    )
    
    fee_type: Mapped[FeeType] = mapped_column(
        String(50),
        nullable=False,
    )
    
    stay_duration_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    
    move_in_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
    )
    
    move_out_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
    )
    
    # Base Charges
    monthly_rent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
    )
    
    security_deposit: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
    )
    
    # Additional Charges
    mess_charges_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )
    
    utility_charges_estimated: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )
    
    other_charges: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )
    
    # Discounts
    discount_applied: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )
    
    discount_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    discount_config_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("discount_configurations.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Tax
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )
    
    tax_percentage: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )
    
    # Totals
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
    )
    
    total_payable: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
    )
    
    first_month_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
    )
    
    monthly_recurring: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
    )
    
    # Detailed Breakdown
    payment_schedule: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Monthly payment schedule as JSON",
    )
    
    charge_breakdown: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Detailed charge breakdown as JSON",
    )
    
    # Calculation Metadata
    calculation_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="standard",
    )
    
    calculation_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    calculated_by_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Proration Details
    is_prorated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    proration_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    proration_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
    )
    
    # Status
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    approved_by_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    # Relationships
    fee_structure = relationship(
        "FeeStructure",
        back_populates="fee_calculations",
    )
    
    student = relationship(
        "Student",
        foreign_keys=[student_id],
        backref="fee_calculations",
    )
    
    booking = relationship(
        "Booking",
        foreign_keys=[booking_id],
        backref="fee_calculations",
    )
    
    discount_config = relationship(
        "DiscountConfiguration",
        foreign_keys=[discount_config_id],
    )
    
    calculated_by = relationship(
        "User",
        foreign_keys=[calculated_by_id],
    )
    
    approved_by = relationship(
        "User",
        foreign_keys=[approved_by_id],
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "calculation_type IN ('estimate', 'booking', 'student', 'renewal', 'modification')",
            name="ck_fee_calculation_type",
        ),
        CheckConstraint(
            "stay_duration_months >= 1",
            name="ck_fee_calculation_duration_positive",
        ),
        CheckConstraint(
            "monthly_rent >= 0",
            name="ck_fee_calculation_rent_positive",
        ),
        CheckConstraint(
            "security_deposit >= 0",
            name="ck_fee_calculation_deposit_positive",
        ),
        CheckConstraint(
            "subtotal >= 0",
            name="ck_fee_calculation_subtotal_positive",
        ),
        CheckConstraint(
            "total_payable >= 0",
            name="ck_fee_calculation_total_positive",
        ),
        CheckConstraint(
            "discount_applied >= 0",
            name="ck_fee_calculation_discount_positive",
        ),
        CheckConstraint(
            "tax_amount >= 0",
            name="ck_fee_calculation_tax_positive",
        ),
        CheckConstraint(
            "tax_percentage >= 0 AND tax_percentage <= 100",
            name="ck_fee_calculation_tax_percentage_range",
        ),
        CheckConstraint(
            "move_out_date IS NULL OR move_out_date > move_in_date",
            name="ck_fee_calculation_date_range",
        ),
        CheckConstraint(
            "NOT is_prorated OR (proration_days IS NOT NULL AND proration_amount IS NOT NULL)",
            name="ck_fee_calculation_proration_complete",
        ),
        Index(
            "ix_fee_calculation_student_date",
            "student_id",
            "calculation_date",
        ),
        Index(
            "ix_fee_calculation_booking_date",
            "booking_id",
            "calculation_date",
        ),
        Index(
            "ix_fee_calculation_type_date",
            "calculation_type",
            "calculation_date",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<FeeCalculation(id={self.id}, "
            f"type={self.calculation_type}, "
            f"total={self.total_payable})>"
        )
    
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
    
    @property
    def savings_percentage(self) -> Decimal:
        """Calculate savings as percentage of original amount."""
        if self.subtotal == 0:
            return Decimal("0.00")
        
        return ((self.discount_applied / self.subtotal) * 100).quantize(
            Decimal("0.01")
        )


class FeeProjection(FeeBaseModel):
    """
    Fee Projection Model
    
    Stores future fee projections and forecasts.
    """
    
    __tablename__ = "fee_projections"
    
    # Foreign Keys
    fee_structure_id: Mapped[UUID] = mapped_column(
        ForeignKey("fee_structures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Projection Details
    projection_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
    )
    
    projection_period_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    
    # Projected Values
    projected_revenue: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
    )
    
    projected_occupancy: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=2),
        nullable=False,
    )
    
    projected_bookings: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    
    # Projection Metadata
    projection_model: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    
    confidence_level: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=2),
        nullable=True,
    )
    
    projection_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    
    # Relationships
    fee_structure = relationship(
        "FeeStructure",
        backref="projections",
    )
    
    __table_args__ = (
        CheckConstraint(
            "projection_period_months >= 1",
            name="ck_fee_projection_period_positive",
        ),
        CheckConstraint(
            "projected_revenue >= 0",
            name="ck_fee_projection_revenue_positive",
        ),
        CheckConstraint(
            "projected_occupancy >= 0 AND projected_occupancy <= 100",
            name="ck_fee_projection_occupancy_range",
        ),
        CheckConstraint(
            "projected_bookings >= 0",
            name="ck_fee_projection_bookings_positive",
        ),
        CheckConstraint(
            "confidence_level IS NULL OR (confidence_level >= 0 AND confidence_level <= 100)",
            name="ck_fee_projection_confidence_range",
        ),
        Index(
            "ix_fee_projection_date_period",
            "projection_date",
            "projection_period_months",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<FeeProjection(id={self.id}, "
            f"date={self.projection_date}, "
            f"revenue={self.projected_revenue})>"
        )