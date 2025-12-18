# --- File: C:\Hostel-Main\app\models\hostel\hostel_amenity.py ---
"""
Hostel amenity model with detailed amenity management.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel


class HostelAmenity(TimestampModel, UUIDMixin):
    """
    Hostel amenity entity with detailed tracking.
    
    Manages individual amenities with availability, condition,
    and maintenance information.
    """

    __tablename__ = "hostel_amenities"

    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to hostel",
    )

    # Amenity Information
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Amenity name",
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Amenity category (basic, premium, recreational, etc.)",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed amenity description",
    )

    # Availability
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Current availability status",
    )
    is_bookable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can be booked/reserved by students",
    )
    is_chargeable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Requires additional charges",
    )

    # Condition and Maintenance
    condition_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="good",
        comment="Condition status (excellent, good, fair, poor)",
    )
    last_maintained_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Last maintenance date",
    )
    next_maintenance_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Next scheduled maintenance",
    )

    # Location
    location: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Specific location within hostel",
    )
    floor: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Floor number where amenity is located",
    )

    # Capacity (for bookable amenities)
    capacity: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Maximum capacity (if applicable)",
    )
    current_usage: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Current usage count",
    )

    # Operating Hours
    operating_hours: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Operating hours (e.g., '6:00 AM - 10:00 PM')",
    )

    # Priority and Display
    display_order: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Display order priority",
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Featured amenity status",
    )

    # Icon and Image
    icon_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Icon/image URL for amenity",
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="amenity_details",
    )

    # Table Arguments
    __table_args__ = (
        # Indexes
        Index("idx_amenity_hostel_category", "hostel_id", "category"),
        Index("idx_amenity_hostel_available", "hostel_id", "is_available"),
        Index("idx_amenity_bookable", "is_bookable"),
        Index("idx_amenity_featured", "is_featured"),
        
        # Check constraints
        CheckConstraint(
            "condition_status IN ('excellent', 'good', 'fair', 'poor')",
            name="check_condition_status_valid",
        ),
        CheckConstraint(
            "capacity IS NULL OR capacity >= 0",
            name="check_capacity_positive",
        ),
        CheckConstraint(
            "current_usage >= 0",
            name="check_current_usage_positive",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="check_display_order_positive",
        ),
        
        # Unique constraint
        UniqueConstraint(
            "hostel_id",
            "name",
            "category",
            name="uq_hostel_amenity_name_category",
        ),
        
        {"comment": "Hostel amenity details with availability tracking"},
    )

    def __repr__(self) -> str:
        return f"<HostelAmenity(id={self.id}, name='{self.name}', hostel_id={self.hostel_id})>"

    @property
    def is_fully_utilized(self) -> bool:
        """Check if amenity is at full capacity."""
        if self.capacity is None:
            return False
        return self.current_usage >= self.capacity

    @property
    def has_capacity(self) -> bool:
        """Check if amenity has available capacity."""
        if self.capacity is None:
            return True
        return self.current_usage < self.capacity

    def can_be_used(self) -> bool:
        """Check if amenity can be used (available and has capacity)."""
        return self.is_available and self.has_capacity


class AmenityCategory(TimestampModel, UUIDMixin):
    """
    Amenity category master for standardization.
    
    Defines standard amenity categories and their properties.
    """

    __tablename__ = "amenity_categories"

    # Category Information
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        comment="Category name",
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Display name for category",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Category description",
    )

    # Properties
    is_basic: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Basic/essential amenity category",
    )
    requires_booking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Amenities in this category require booking",
    )
    is_chargeable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Amenities in this category have charges",
    )

    # Display
    icon_name: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Icon identifier",
    )
    display_order: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Display order",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Active status",
    )

    # Table Arguments
    __table_args__ = (
        Index("idx_amenity_category_active", "is_active"),
        CheckConstraint(
            "display_order >= 0",
            name="check_category_display_order_positive",
        ),
        {"comment": "Amenity category master data"},
    )

    def __repr__(self) -> str:
        return f"<AmenityCategory(id={self.id}, name='{self.name}')>"


class AmenityBooking(TimestampModel, UUIDMixin):
    """
    Amenity booking/reservation tracking.
    
    Manages bookings for amenities that can be reserved.
    """

    __tablename__ = "amenity_bookings"

    # Foreign Keys
    amenity_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostel_amenities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to amenity",
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to student",
    )

    # Booking Details
    booking_date: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Date of booking",
    )
    start_time: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="Booking start time",
    )
    end_time: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="Booking end time",
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Booking status",
    )
    participants_count: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
        comment="Number of participants",
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Booking notes",
    )

    # Cancellation
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Cancellation timestamp",
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for cancellation",
    )

    # Table Arguments
    __table_args__ = (
        Index("idx_amenity_booking_date", "amenity_id", "booking_date"),
        Index("idx_amenity_booking_status", "status"),
        Index("idx_amenity_booking_student", "student_id", "status"),
        CheckConstraint(
            "end_time > start_time",
            name="check_end_after_start",
        ),
        CheckConstraint(
            "participants_count > 0",
            name="check_participants_positive",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'completed', 'cancelled')",
            name="check_booking_status_valid",
        ),
        {"comment": "Amenity booking and reservation tracking"},
    )

    def __repr__(self) -> str:
        return f"<AmenityBooking(id={self.id}, amenity_id={self.amenity_id}, status='{self.status}')>"