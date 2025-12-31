"""
Fee Structure Model

Manages pricing and fee configurations for different hostel room types.
Maps to fee_structure/fee_base.py schemas.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.enums import ChargeType, FeeType, RoomType
from app.models.base.mixins import AuditMixin, SoftDeleteMixin, UUIDMixin


class FeeStructure(UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin, BaseModel):
    """
    Fee Structure Model
    
    Defines pricing and charges for a specific hostel and room type,
    including base rent, security deposit, utilities, and mess charges.
    """
    
    __tablename__ = "fee_structures"
    
    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Room and Fee Type
    room_type: Mapped[RoomType] = mapped_column(
        Enum(RoomType, name="room_type_enum"),
        nullable=False,
        index=True,
    )
    fee_type: Mapped[FeeType] = mapped_column(
        Enum(FeeType, name="fee_type_enum"),
        nullable=False,
        index=True,
    )
    
    # Base Charges
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
    )
    security_deposit: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )
    
    # Mess Charges
    includes_mess: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    mess_charges_monthly: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )
    
    # Utility Charges - Electricity
    electricity_charges: Mapped[ChargeType] = mapped_column(
        Enum(ChargeType, name="charge_type_enum"),
        nullable=False,
        default=ChargeType.INCLUDED,
    )
    electricity_fixed_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
    )
    
    # Utility Charges - Water
    water_charges: Mapped[ChargeType] = mapped_column(
        Enum(ChargeType, name="charge_type_enum"),
        nullable=False,
        default=ChargeType.INCLUDED,
    )
    water_fixed_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
    )
    
    # Validity Period
    effective_from: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
    )
    effective_to: Mapped[Optional[Date]] = mapped_column(
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
    
    # Additional Information
    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    # Version Control
    version: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
    )
    replaced_by_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("fee_structures.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Relationships
    hostel = relationship(
        "Hostel",
        back_populates="fee_structures",
        lazy="select",
    )
    
    charge_components = relationship(
        "ChargeComponent",
        back_populates="fee_structure",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    fee_calculations = relationship(
        "FeeCalculation",
        back_populates="fee_structure",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    approvals = relationship(
        "FeeApproval",
        back_populates="fee_structure",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    replaced_by = relationship(
        "FeeStructure",
        remote_side="FeeStructure.id",
        foreign_keys=[replaced_by_id],
        uselist=False,
    )
    
    # Constraints
    __table_args__ = (
        # Amount validations
        CheckConstraint(
            "amount >= 0",
            name="ck_fee_structure_amount_positive",
        ),
        CheckConstraint(
            "amount >= 500.00 AND amount <= 100000.00",
            name="ck_fee_structure_amount_range",
        ),
        CheckConstraint(
            "security_deposit >= 0",
            name="ck_fee_structure_security_deposit_positive",
        ),
        CheckConstraint(
            "security_deposit <= (amount * 3)",
            name="ck_fee_structure_security_deposit_ratio",
        ),
        CheckConstraint(
            "mess_charges_monthly >= 0",
            name="ck_fee_structure_mess_charges_positive",
        ),
        CheckConstraint(
            "mess_charges_monthly <= 10000.00",
            name="ck_fee_structure_mess_charges_max",
        ),
        
        # Utility charge validations
        CheckConstraint(
            "electricity_fixed_amount IS NULL OR electricity_fixed_amount >= 0",
            name="ck_fee_structure_electricity_amount_positive",
        ),
        CheckConstraint(
            "water_fixed_amount IS NULL OR water_fixed_amount >= 0",
            name="ck_fee_structure_water_amount_positive",
        ),
        
        # Mess logic validation
        CheckConstraint(
            "NOT (includes_mess = true AND mess_charges_monthly > 0)",
            name="ck_fee_structure_mess_logic",
        ),
        
        # Date validations
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_fee_structure_date_range",
        ),
        
        # Unique constraint for active fee structures
        UniqueConstraint(
            "hostel_id",
            "room_type",
            "fee_type",
            "effective_from",
            name="uq_fee_structure_hostel_room_fee_date",
        ),
        
        # Indexes for common queries
        Index(
            "ix_fee_structure_hostel_active",
            "hostel_id",
            "is_active",
        ),
        Index(
            "ix_fee_structure_hostel_room_type",
            "hostel_id",
            "room_type",
        ),
        Index(
            "ix_fee_structure_effective_dates",
            "effective_from",
            "effective_to",
        ),
        Index(
            "ix_fee_structure_current",
            "hostel_id",
            "room_type",
            "is_active",
            "effective_from",
            "effective_to",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<FeeStructure(id={self.id}, "
            f"hostel_id={self.hostel_id}, "
            f"room_type={self.room_type.value}, "
            f"fee_type={self.fee_type.value}, "
            f"amount={self.amount})>"
        )
    
    @property
    def is_currently_effective(self) -> bool:
        """Check if fee structure is currently within effective date range."""
        today = Date.today()
        if today < self.effective_from:
            return False
        if self.effective_to is not None and today > self.effective_to:
            return False
        return True
    
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
    
    @property
    def has_variable_charges(self) -> bool:
        """Check if configuration includes variable/actual charges."""
        return (
            self.electricity_charges == ChargeType.ACTUAL
            or self.water_charges == ChargeType.ACTUAL
        )
    
    @property
    def is_all_inclusive(self) -> bool:
        """Check if all charges are included in base rent."""
        return (
            self.includes_mess
            and self.electricity_charges == ChargeType.INCLUDED
            and self.water_charges == ChargeType.INCLUDED
        )


class FeeApproval(UUIDMixin, TimestampModel, BaseModel):
    """
    Fee Approval Model
    
    Tracks approval workflow for fee structure changes.
    """
    
    __tablename__ = "fee_approvals"
    
    # Foreign Keys
    fee_structure_id: Mapped[UUID] = mapped_column(
        ForeignKey("fee_structures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    approved_by_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Approval Details
    approval_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    
    approved_at: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
    )
    
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    # Change Details
    change_summary: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
    )
    
    previous_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
    )
    
    new_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
    )
    
    # Relationships
    fee_structure = relationship(
        "FeeStructure",
        back_populates="approvals",
    )
    
    approved_by = relationship(
        "User",
        foreign_keys=[approved_by_id],
    )
    
    __table_args__ = (
        CheckConstraint(
            "approval_status IN ('pending', 'approved', 'rejected')",
            name="ck_fee_approval_status",
        ),
        Index(
            "ix_fee_approval_status_created",
            "approval_status",
            "created_at",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<FeeApproval(id={self.id}, "
            f"fee_structure_id={self.fee_structure_id}, "
            f"status={self.approval_status})>"
        )