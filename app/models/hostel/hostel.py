# --- File: C:\Hostel-Main\app\models\hostel\hostel.py ---
"""
Hostel core model with comprehensive details and relationships.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Index,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.enums import HostelStatus, HostelType
from app.models.base.mixins import (
    AddressMixin,
    ContactMixin,
    LocationMixin,
    SEOMixin,
    UUIDMixin,
)

if TYPE_CHECKING:
    from app.models.admin.admin_hostel_assignment import AdminHostelAssignment
    from app.models.hostel.hostel_amenity import HostelAmenity
    from app.models.hostel.hostel_media import HostelMedia
    from app.models.hostel.hostel_policy import HostelPolicy
    from app.models.hostel.hostel_settings import HostelSettings
    from app.models.room.room import Room
    from app.models.student.student import Student


class Hostel(
    TimestampModel,
    UUIDMixin,
    AddressMixin,
    ContactMixin,
    LocationMixin,
    SEOMixin,
):
    """
    Core hostel entity with comprehensive information.
    
    Manages hostel details, capacity, pricing, and operational status.
    Serves as the central entity for hostel management system.
    """

    __tablename__ = "hostels"

    # Basic Information
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Hostel name",
    )
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="URL-friendly slug (lowercase, alphanumeric, hyphens)",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed hostel description",
    )

    # Type and Classification
    hostel_type: Mapped[HostelType] = mapped_column(
        nullable=False,
        index=True,
        comment="Hostel type (boys/girls/co-ed)",
    )

    # Website
    website_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Official hostel website URL",
    )

    # Pricing Information
    starting_price_monthly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Starting monthly price (lowest room type)",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        comment="Currency code (ISO 4217)",
    )

    # Capacity Information
    total_rooms: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Total number of rooms",
    )
    total_beds: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Total number of beds",
    )
    occupied_beds: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Currently occupied beds",
    )
    available_beds: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Available beds (calculated)",
    )

    # Features and Amenities (stored as JSON arrays)
    amenities: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="List of amenities (WiFi, AC, etc.)",
    )
    facilities: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="List of facilities (Gym, Library, etc.)",
    )
    security_features: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="Security features (CCTV, Guards, etc.)",
    )

    # Policies and Rules
    rules: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Hostel rules and regulations",
    )
    check_in_time: Mapped[Optional[Time]] = mapped_column(
        Time,
        nullable=True,
        comment="Standard check-in time",
    )
    check_out_time: Mapped[Optional[Time]] = mapped_column(
        Time,
        nullable=True,
        comment="Standard check-out time",
    )
    visitor_policy: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Visitor policy details",
    )
    late_entry_policy: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Late entry policy and timings",
    )

    # Location Information (JSONB for flexible structure)
    nearby_landmarks: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="Nearby landmarks with name, type, and distance",
    )
    connectivity_info: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Public transport and connectivity information",
    )

    # Media Information
    cover_image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Cover/main image URL",
    )
    gallery_images: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="Gallery image URLs",
    )
    virtual_tour_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="360° virtual tour URL",
    )
    video_urls: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="Video URLs",
    )

    # Status and Visibility
    status: Mapped[HostelStatus] = mapped_column(
        nullable=False,
        default=HostelStatus.ACTIVE,
        index=True,
        comment="Operational status",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Active status",
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Public listing visibility",
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Featured in listings",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Verification status",
    )

    # Rating Information
    average_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average rating from reviews",
    )
    total_reviews: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Total number of reviews",
    )

    # Statistics (cached/computed values)
    total_students: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Total registered students",
    )
    active_students: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Currently active students",
    )
    occupancy_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Current occupancy percentage",
    )

    # Financial Statistics
    total_revenue_this_month: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total revenue for current month",
    )
    outstanding_payments: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total outstanding payment amount",
    )

    # Pending Items Count
    pending_bookings: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Number of pending booking requests",
    )
    pending_complaints: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Number of open/pending complaints",
    )
    pending_maintenance: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Number of pending maintenance requests",
    )

    # Additional Information
    established_year: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Year hostel was established",
    )

    # Relationships
    rooms: Mapped[List["Room"]] = relationship(
        "Room",
        back_populates="hostel",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    students: Mapped[List["Student"]] = relationship(
        "Student",
        back_populates="hostel",
        lazy="dynamic",
    )

    admin_assignments: Mapped[List["AdminHostelAssignment"]] = relationship(
        "AdminHostelAssignment",
        back_populates="hostel",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    amenity_details: Mapped[List["HostelAmenity"]] = relationship(
        "HostelAmenity",
        back_populates="hostel",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    media_items: Mapped[List["HostelMedia"]] = relationship(
        "HostelMedia",
        back_populates="hostel",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    policies: Mapped[List["HostelPolicy"]] = relationship(
        "HostelPolicy",
        back_populates="hostel",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    settings: Mapped[Optional["HostelSettings"]] = relationship(
        "HostelSettings",
        back_populates="hostel",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Table Arguments
    __table_args__ = (
        # Indexes for common queries
        Index("idx_hostel_city_type", "city", "hostel_type"),
        Index("idx_hostel_status_active", "status", "is_active"),
        Index("idx_hostel_featured_public", "is_featured", "is_public"),
        Index("idx_hostel_rating", "average_rating"),
        Index("idx_hostel_price", "starting_price_monthly"),
        Index("idx_hostel_location", "latitude", "longitude"),
        
        # Check constraints
        CheckConstraint(
            "total_beds >= 0",
            name="check_total_beds_positive",
        ),
        CheckConstraint(
            "occupied_beds >= 0",
            name="check_occupied_beds_positive",
        ),
        CheckConstraint(
            "occupied_beds <= total_beds",
            name="check_occupied_not_exceed_total",
        ),
        CheckConstraint(
            "available_beds >= 0",
            name="check_available_beds_positive",
        ),
        CheckConstraint(
            "total_rooms >= 0",
            name="check_total_rooms_positive",
        ),
        CheckConstraint(
            "starting_price_monthly >= 0",
            name="check_starting_price_positive",
        ),
        CheckConstraint(
            "average_rating >= 0 AND average_rating <= 5",
            name="check_rating_range",
        ),
        CheckConstraint(
            "total_reviews >= 0",
            name="check_total_reviews_positive",
        ),
        CheckConstraint(
            "occupancy_percentage >= 0 AND occupancy_percentage <= 100",
            name="check_occupancy_percentage_range",
        ),
        CheckConstraint(
            "total_students >= 0",
            name="check_total_students_positive",
        ),
        CheckConstraint(
            "active_students >= 0",
            name="check_active_students_positive",
        ),
        CheckConstraint(
            "active_students <= total_students",
            name="check_active_not_exceed_total_students",
        ),
        
        # Unique constraints
        UniqueConstraint("slug", name="uq_hostel_slug"),
        
        {"comment": "Core hostel entity with comprehensive information"},
    )

    def __repr__(self) -> str:
        return f"<Hostel(id={self.id}, name='{self.name}', slug='{self.slug}')>"

    def calculate_occupancy_percentage(self) -> Decimal:
        """Calculate and update occupancy percentage."""
        if self.total_beds > 0:
            self.occupancy_percentage = Decimal(
                (self.occupied_beds / self.total_beds) * 100
            ).quantize(Decimal("0.01"))
        else:
            self.occupancy_percentage = Decimal("0.00")
        return self.occupancy_percentage

    def update_available_beds(self) -> int:
        """Calculate and update available beds."""
        self.available_beds = max(0, self.total_beds - self.occupied_beds)
        return self.available_beds

    def update_capacity_stats(self) -> None:
        """Update all capacity-related statistics."""
        self.update_available_beds()
        self.calculate_occupancy_percentage()

    @property
    def full_address(self) -> str:
        """Get formatted full address."""
        parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.state,
            self.pincode,
            self.country,
        ]
        return ", ".join(filter(None, parts))

    @property
    def is_fully_occupied(self) -> bool:
        """Check if hostel is fully occupied."""
        return self.available_beds == 0 and self.total_beds > 0

    @property
    def has_availability(self) -> bool:
        """Check if hostel has available beds."""
        return self.available_beds > 0

    def can_accommodate(self, required_beds: int) -> bool:
        """Check if hostel can accommodate required number of beds."""
        return self.available_beds >= required_beds