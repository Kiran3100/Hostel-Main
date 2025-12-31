"""
Booking conversion models.

This module defines the conversion of bookings to student profiles
after check-in, including validation checklists and conversion tracking.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date as SQLDate,
    DateTime,
    ForeignKey,
    Index,
    Integer,  # Added missing Integer import
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.booking.booking import Booking
    from app.models.student.student import Student
    from app.models.user.user import User

__all__ = [
    "BookingConversion",
    "ConversionChecklist",
    "ChecklistItem",
]


class BookingConversion(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Booking to student conversion record.
    
    Tracks the conversion of a confirmed booking into an active
    student profile after check-in, including all validation
    steps and financial confirmations.
    
    Attributes:
        booking_id: Reference to the booking (one-to-one)
        student_profile_id: Created student profile ID
        actual_check_in_date: Actual check-in date
        security_deposit_paid: Whether security deposit was paid
        first_month_rent_paid: Whether first month rent was paid
        student_id_number: Student ID or enrollment number
        guardian_address: Guardian's address
        id_proof_uploaded: Whether ID proof was uploaded
        photo_uploaded: Whether student photo was uploaded
        conversion_notes: Notes about the conversion
        converted_by: Admin who performed the conversion
        converted_at: When conversion was completed
        checklist_completed: Whether all checklist items completed
        checklist_completion_rate: Percentage of checklist completed
    """

    __tablename__ = "booking_conversions"

    # Foreign Key (One-to-One with Booking)
    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to booking (one-to-one)",
    )

    # Student Profile
    student_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
        comment="Created student profile ID",
    )

    # Check-in Details
    actual_check_in_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Actual check-in date (may differ from preferred)",
    )

    # Financial Confirmation
    security_deposit_paid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether security deposit has been paid",
    )

    security_deposit_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Security deposit amount paid",
    )

    security_deposit_payment_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to security deposit payment",
    )

    first_month_rent_paid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether first month's rent has been paid",
    )

    first_month_rent_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="First month rent amount paid",
    )

    first_month_rent_payment_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to first month rent payment",
    )

    # Additional Student Details
    student_id_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Student ID or enrollment number",
    )

    guardian_address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Guardian's address",
    )

    # Document Verification
    id_proof_uploaded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether ID proof document has been uploaded",
    )

    photo_uploaded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether student photo has been uploaded",
    )

    documents_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether all documents have been verified",
    )

    documents_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When documents were verified",
    )

    documents_verified_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who verified documents",
    )

    # Conversion Metadata
    conversion_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes about the conversion process",
    )

    converted_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who performed the conversion",
    )

    converted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When conversion was completed",
    )

    # Checklist Tracking
    checklist_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether all checklist items are completed",
    )

    checklist_completion_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Percentage of checklist items completed",
    )

    # Next Payment Information
    next_payment_due_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Next rent payment due date",
    )

    monthly_rent_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Monthly rent amount for student",
    )

    # Conversion Status
    is_successful: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether conversion was successful",
    )

    conversion_errors: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Errors encountered during conversion (JSON)",
    )

    # Relationships
    booking: Mapped["Booking"] = relationship(
        "Booking",
        back_populates="conversion",
    )

    student_profile: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_profile_id],
        lazy="select",
    )

    converter: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[converted_by],
        lazy="select",
    )

    documents_verifier: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[documents_verified_by],
        lazy="select",
    )

    checklist: Mapped["ConversionChecklist"] = relationship(
        "ConversionChecklist",
        back_populates="conversion",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        CheckConstraint(
            "security_deposit_amount >= 0",
            name="ck_conversion_deposit_positive",
        ),
        CheckConstraint(
            "first_month_rent_amount >= 0",
            name="ck_conversion_rent_positive",
        ),
        CheckConstraint(
            "monthly_rent_amount >= 0",
            name="ck_conversion_monthly_rent_positive",
        ),
        CheckConstraint(
            "checklist_completion_rate >= 0 AND checklist_completion_rate <= 100",
            name="ck_conversion_completion_rate_range",
        ),
        Index("ix_conversion_booking", "booking_id"),
        Index("ix_conversion_student", "student_profile_id"),
        Index("ix_conversion_converted_at", "converted_at"),
        Index("ix_conversion_check_in", "actual_check_in_date"),
        UniqueConstraint("booking_id", name="uq_conversion_booking"),
        UniqueConstraint("student_profile_id", name="uq_conversion_student"),
        {
            "comment": "Booking to student conversion records",
            "extend_existing": True,
        },
    )

    # Validators
    @validates("actual_check_in_date")
    def validate_check_in_date(self, key: str, value: Date) -> Date:
        """Validate check-in date is not in future."""
        if value > Date.today():
            raise ValueError("Actual check-in date cannot be in the future")
        return value

    @validates("security_deposit_amount", "first_month_rent_amount", "monthly_rent_amount")
    def validate_amounts(self, key: str, value: Decimal) -> Decimal:
        """Validate monetary amounts are non-negative."""
        if value < 0:
            raise ValueError(f"{key} cannot be negative")
        return value

    @validates("checklist_completion_rate")
    def validate_completion_rate(self, key: str, value: Decimal) -> Decimal:
        """Validate completion rate is in valid range."""
        if value < 0 or value > 100:
            raise ValueError("Completion rate must be between 0 and 100")
        return value

    # Properties
    @property
    def days_since_check_in(self) -> int:
        """Calculate days since check-in."""
        return (Date.today() - self.actual_check_in_date).days

    @property
    def all_payments_received(self) -> bool:
        """Check if all required payments are received."""
        return self.security_deposit_paid and self.first_month_rent_paid

    @property
    def all_documents_uploaded(self) -> bool:
        """Check if all required documents are uploaded."""
        return self.id_proof_uploaded and self.photo_uploaded

    @property
    def is_ready_for_conversion(self) -> bool:
        """Check if booking is ready for conversion."""
        return (
            self.all_payments_received
            and self.all_documents_uploaded
            and self.checklist_completed
        )

    # Methods
    def verify_documents(self, verified_by: UUID) -> None:
        """
        Mark documents as verified.
        
        Args:
            verified_by: ID of admin verifying documents
        """
        if not self.all_documents_uploaded:
            raise ValueError("Cannot verify documents - not all documents uploaded")
        
        self.documents_verified = True
        self.documents_verified_at = datetime.utcnow()
        self.documents_verified_by = verified_by

    def update_checklist_completion(self, completion_rate: Decimal, is_complete: bool) -> None:
        """
        Update checklist completion status.
        
        Args:
            completion_rate: Completion rate percentage
            is_complete: Whether checklist is fully complete
        """
        self.checklist_completion_rate = completion_rate
        self.checklist_completed = is_complete

    def mark_as_failed(self, errors: dict) -> None:
        """
        Mark conversion as failed.
        
        Args:
            errors: Dictionary of errors encountered
        """
        self.is_successful = False
        self.conversion_errors = errors

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<BookingConversion(booking_id={self.booking_id}, "
            f"student_id={self.student_profile_id}, "
            f"check_in={self.actual_check_in_date})>"
        )


class ConversionChecklist(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Pre-conversion checklist validation.
    
    Tracks all required checklist items that must be completed
    before a booking can be converted to a student profile.
    
    Attributes:
        conversion_id: Reference to conversion record
        booking_id: Reference to booking
        all_checks_passed: Whether all required checks passed
        can_convert: Whether conversion can proceed
        total_items: Total number of checklist items
        completed_items: Number of completed items
        missing_items: List of missing/incomplete items (JSON)
        last_checked_at: When checklist was last evaluated
        last_checked_by: Who last checked the checklist
    """

    __tablename__ = "conversion_checklists"

    # Foreign Keys
    conversion_id: Mapped[UUID] = mapped_column(
        ForeignKey("booking_conversions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to conversion record",
    )

    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to booking",
    )

    # Checklist Status
    all_checks_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether all required checks passed",
    )

    can_convert: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether conversion can proceed",
    )

    # Checklist Metrics
    total_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of checklist items",
    )

    completed_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of completed items",
    )

    required_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of required (mandatory) items",
    )

    # Missing Items
    missing_items: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of missing/incomplete required items (JSON array)",
    )

    # Tracking
    last_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When checklist was last evaluated",
    )

    last_checked_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Who last checked the checklist",
    )

    # Relationships
    conversion: Mapped["BookingConversion"] = relationship(
        "BookingConversion",
        back_populates="checklist",
    )

    booking: Mapped["Booking"] = relationship(
        "Booking",
        foreign_keys=[booking_id],
        lazy="select",
    )

    checker: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[last_checked_by],
        lazy="select",
    )

    items: Mapped[list["ChecklistItem"]] = relationship(
        "ChecklistItem",
        back_populates="checklist",
        cascade="all, delete-orphan",
        order_by="ChecklistItem.item_order",
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        CheckConstraint(
            "total_items >= 0",
            name="ck_checklist_total_positive",
        ),
        CheckConstraint(
            "completed_items >= 0",
            name="ck_checklist_completed_positive",
        ),
        CheckConstraint(
            "completed_items <= total_items",
            name="ck_checklist_completed_not_exceed_total",
        ),
        Index("ix_checklist_conversion", "conversion_id"),
        Index("ix_checklist_booking", "booking_id"),
        UniqueConstraint("conversion_id", name="uq_checklist_conversion"),
        UniqueConstraint("booking_id", name="uq_checklist_booking"),
        {
            "comment": "Pre-conversion checklist validation",
            "extend_existing": True,
        },
    )

    # Properties
    @property
    def completion_percentage(self) -> Decimal:
        """Calculate completion percentage."""
        if self.total_items == 0:
            return Decimal("0.00")
        return Decimal(
            (self.completed_items / self.total_items * 100)
        ).quantize(Decimal("0.01"))

    @property
    def required_completion_percentage(self) -> Decimal:
        """Calculate required items completion percentage."""
        if self.required_items == 0:
            return Decimal("100.00")
        completed_required = sum(
            1 for item in self.items if item.is_required and item.is_completed
        )
        return Decimal(
            (completed_required / self.required_items * 100)
        ).quantize(Decimal("0.01"))

    # Methods
    def evaluate_checklist(self, checked_by: Optional[UUID] = None) -> None:
        """
        Evaluate checklist status and update metrics.
        
        Args:
            checked_by: ID of user checking the checklist
        """
        self.total_items = len(self.items)
        self.completed_items = sum(1 for item in self.items if item.is_completed)
        self.required_items = sum(1 for item in self.items if item.is_required)
        
        # Check if all required items are completed
        required_completed = all(
            item.is_completed for item in self.items if item.is_required
        )
        
        self.all_checks_passed = required_completed
        self.can_convert = required_completed
        
        # Update missing items
        self.missing_items = [
            item.item_name for item in self.items
            if item.is_required and not item.is_completed
        ]
        
        self.last_checked_at = datetime.utcnow()
        if checked_by:
            self.last_checked_by = checked_by

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ConversionChecklist(booking_id={self.booking_id}, "
            f"completed={self.completed_items}/{self.total_items}, "
            f"can_convert={self.can_convert})>"
        )


class ChecklistItem(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Individual checklist item for conversion validation.
    
    Represents a single requirement that must be met before
    conversion can proceed.
    
    Attributes:
        checklist_id: Reference to checklist
        item_name: Name of checklist item
        item_description: Detailed description
        is_completed: Whether item is completed
        is_required: Whether item is mandatory
        item_order: Display order
        completed_at: When item was completed
        completed_by: Who completed the item
        verification_notes: Notes about verification
        item_category: Category of item
    """

    __tablename__ = "checklist_items"

    # Foreign Key
    checklist_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversion_checklists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to checklist",
    )

    # Item Details
    item_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Name of checklist item",
    )

    item_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed description of requirement",
    )

    # Status
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether item is completed",
    )

    is_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether item is mandatory for conversion",
    )

    # Ordering
    item_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order of item",
    )

    # Completion Details
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When item was completed",
    )

    completed_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Who completed the item",
    )

    verification_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes about verification or completion",
    )

    # Categorization
    item_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="general",
        comment="Category of item (financial, documents, profile, etc.)",
    )

    # Relationships
    checklist: Mapped["ConversionChecklist"] = relationship(
        "ConversionChecklist",
        back_populates="items",
    )

    completer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[completed_by],
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        Index("ix_item_checklist", "checklist_id"),
        Index("ix_item_completed", "is_completed"),
        Index("ix_item_required", "is_required"),
        Index("ix_item_order", "item_order"),
        {
            "comment": "Individual checklist items for conversion",
            "extend_existing": True,
        },
    )

    # Validators
    @validates("item_category")
    def validate_category(self, key: str, value: str) -> str:
        """Validate item category."""
        valid_categories = {
            "general", "financial", "documents", "profile",
            "verification", "assignment", "other"
        }
        if value.lower() not in valid_categories:
            raise ValueError(f"Invalid category. Must be one of {valid_categories}")
        return value.lower()

    # Methods
    def mark_completed(self, completed_by: UUID, notes: Optional[str] = None) -> None:
        """
        Mark item as completed.
        
        Args:
            completed_by: ID of user completing the item
            notes: Optional verification notes
        """
        if self.is_completed:
            raise ValueError("Item is already completed")
        
        self.is_completed = True
        self.completed_at = datetime.utcnow()
        self.completed_by = completed_by
        if notes:
            self.verification_notes = notes

    def mark_incomplete(self, reason: Optional[str] = None) -> None:
        """
        Mark item as incomplete.
        
        Args:
            reason: Optional reason for marking incomplete
        """
        if not self.is_completed:
            raise ValueError("Item is already incomplete")
        
        self.is_completed = False
        self.completed_at = None
        self.completed_by = None
        if reason:
            self.verification_notes = f"REVERTED: {reason}"

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ChecklistItem(name={self.item_name}, "
            f"completed={self.is_completed}, required={self.is_required})>"
        )