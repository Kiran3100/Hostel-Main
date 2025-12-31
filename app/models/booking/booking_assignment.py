"""
Booking assignment models.

This module defines room and bed assignment for bookings,
including assignment history and conflict resolution.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.booking.booking import Booking
    from app.models.room.bed import Bed
    from app.models.room.room import Room
    from app.models.user.user import User

__all__ = [
    "BookingAssignment",
    "AssignmentHistory",
]


class BookingAssignment(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Room and bed assignment for confirmed bookings.
    
    Manages the assignment of specific rooms and beds to approved bookings,
    including assignment tracking, validation, and lifecycle management.
    
    Attributes:
        booking_id: Reference to the booking (one-to-one)
        room_id: Assigned room ID
        bed_id: Assigned bed ID
        assigned_by: Admin who made the assignment
        assigned_at: When assignment was made
        assignment_notes: Notes about the assignment
        auto_assigned: Whether assignment was automatic
        override_check_in_date: Overridden check-in date
        is_active: Whether assignment is currently active
        deactivated_at: When assignment was deactivated
        deactivated_by: Who deactivated the assignment
        deactivation_reason: Reason for deactivation
    """

    __tablename__ = "booking_assignments"

    # Foreign Key (One-to-One with Booking)
    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to booking (one-to-one)",
    )

    # Room and Bed Assignment
    room_id: Mapped[UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Assigned room ID",
    )

    bed_id: Mapped[UUID] = mapped_column(
        ForeignKey("beds.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Assigned bed ID",
    )

    # Assignment Metadata
    assigned_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who made the assignment",
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When assignment was made",
    )

    assignment_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes about the assignment",
    )

    auto_assigned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether assignment was automatic",
    )

    # Override Check-in Date
    override_check_in_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Overridden check-in date if different from booking",
    )

    # Assignment Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether assignment is currently active",
    )

    deactivated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When assignment was deactivated",
    )

    deactivated_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Who deactivated the assignment",
    )

    deactivation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for deactivation",
    )

    # Relationships
    booking: Mapped["Booking"] = relationship(
        "Booking",
        back_populates="assignment",
    )

    room: Mapped["Room"] = relationship(
        "Room",
        back_populates="booking_assignments",
        lazy="select",
    )

    bed: Mapped["Bed"] = relationship(
        "Bed",
        back_populates="booking_assignments",
        lazy="select",
    )

    assigner: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_by],
        lazy="select",
    )

    deactivator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[deactivated_by],
        lazy="select",
    )

    history: Mapped[list["AssignmentHistory"]] = relationship(
        "AssignmentHistory",
        back_populates="current_assignment",
        cascade="all, delete-orphan",
        order_by="AssignmentHistory.changed_at.desc()",
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        Index("ix_assignment_room_bed", "room_id", "bed_id"),
        Index("ix_assignment_booking", "booking_id"),
        Index("ix_assignment_active", "is_active"),
        UniqueConstraint("booking_id", name="uq_assignment_booking"),
        {
            "comment": "Room and bed assignments for bookings",
            "extend_existing": True,
        },
    )

    # Methods
    def deactivate(self, deactivated_by: UUID, reason: str) -> None:
        """
        Deactivate the assignment.
        
        Args:
            deactivated_by: ID of user deactivating the assignment
            reason: Reason for deactivation
        """
        if not self.is_active:
            raise ValueError("Assignment is already deactivated")
        
        self.is_active = False
        self.deactivated_at = datetime.utcnow()
        self.deactivated_by = deactivated_by
        self.deactivation_reason = reason

    def reactivate(self) -> None:
        """Reactivate the assignment."""
        if self.is_active:
            raise ValueError("Assignment is already active")
        
        self.is_active = True
        self.deactivated_at = None
        self.deactivated_by = None
        self.deactivation_reason = None

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<BookingAssignment(booking_id={self.booking_id}, "
            f"room_id={self.room_id}, bed_id={self.bed_id}, "
            f"active={self.is_active})>"
        )


class AssignmentHistory(UUIDMixin, TimestampModel):
    """
    Assignment change history for audit trail.
    
    Tracks all changes to room and bed assignments for bookings,
    including reassignments and the reasons for changes.
    
    Attributes:
        assignment_id: Reference to current assignment
        booking_id: Reference to booking
        from_room_id: Previous room (NULL for initial assignment)
        from_bed_id: Previous bed (NULL for initial assignment)
        to_room_id: New room
        to_bed_id: New bed
        changed_by: Admin who made the change
        changed_at: When change was made
        change_reason: Reason for change
        change_type: Type of change (initial, reassignment, correction)
    """

    __tablename__ = "assignment_history"

    # Foreign Keys
    assignment_id: Mapped[UUID] = mapped_column(
        ForeignKey("booking_assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to current assignment",
    )

    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to booking",
    )

    # Previous Assignment (NULL for initial)
    from_room_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        comment="Previous room (NULL for initial assignment)",
    )

    from_bed_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("beds.id", ondelete="SET NULL"),
        nullable=True,
        comment="Previous bed (NULL for initial assignment)",
    )

    # New Assignment
    to_room_id: Mapped[UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="RESTRICT"),
        nullable=False,
        comment="New room",
    )

    to_bed_id: Mapped[UUID] = mapped_column(
        ForeignKey("beds.id", ondelete="RESTRICT"),
        nullable=False,
        comment="New bed",
    )

    # Change Metadata
    changed_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who made the change",
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When change was made",
    )

    change_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Reason for change",
    )

    change_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="reassignment",
        comment="Type of change (initial, reassignment, correction)",
    )

    # Relationships
    current_assignment: Mapped["BookingAssignment"] = relationship(
        "BookingAssignment",
        back_populates="history",
    )

    booking: Mapped["Booking"] = relationship(
        "Booking",
        foreign_keys=[booking_id],
        lazy="select",
    )

    from_room: Mapped[Optional["Room"]] = relationship(
        "Room",
        foreign_keys=[from_room_id],
        lazy="select",
    )

    from_bed: Mapped[Optional["Bed"]] = relationship(
        "Bed",
        foreign_keys=[from_bed_id],
        lazy="select",
    )

    to_room: Mapped["Room"] = relationship(
        "Room",
        foreign_keys=[to_room_id],
        lazy="select",
    )

    to_bed: Mapped["Bed"] = relationship(
        "Bed",
        foreign_keys=[to_bed_id],
        lazy="select",
    )

    changer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[changed_by],
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        Index("ix_history_assignment_changed", "assignment_id", "changed_at"),
        Index("ix_history_booking_changed", "booking_id", "changed_at"),
        {
            "comment": "Assignment change history for audit trail",
            "extend_existing": True,
        },
    )

    # Validators
    @validates("change_type")
    def validate_change_type(self, key: str, value: str) -> str:
        """Validate change type."""
        valid_types = {"initial", "reassignment", "correction", "upgrade", "downgrade"}
        if value.lower() not in valid_types:
            raise ValueError(f"Invalid change type. Must be one of {valid_types}")
        return value.lower()

    # Properties
    @property
    def is_initial_assignment(self) -> bool:
        """Check if this is the initial assignment."""
        return self.from_room_id is None and self.from_bed_id is None

    @property
    def is_room_change(self) -> bool:
        """Check if room was changed."""
        return self.from_room_id != self.to_room_id

    @property
    def is_bed_change(self) -> bool:
        """Check if bed was changed (within same or different room)."""
        return self.from_bed_id != self.to_bed_id

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<AssignmentHistory(booking_id={self.booking_id}, "
            f"type={self.change_type}, changed_at={self.changed_at})>"
        )