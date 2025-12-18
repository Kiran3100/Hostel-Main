# app/models/room/room.py
"""
Room models with comprehensive tracking and management.

Implements core room entity with specifications, pricing history,
maintenance status, and access control.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.enums import RoomStatus, RoomType as RoomTypeEnum
from app.models.base.mixins import (
    SoftDeleteMixin,
    UUIDMixin,
    AuditMixin,
    MediaMixin,
)

__all__ = [
    "Room",
    "RoomSpecification",
    "RoomPricingHistory",
    "RoomMaintenanceStatus",
    "RoomAccessControl",
    "RoomOccupancyLimit",
]


class Room(BaseModel, UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin):
    """
    Core room entity with comprehensive details.
    
    Represents a physical room within a hostel with all specifications,
    pricing, amenities, and availability tracking.
    """

    __tablename__ = "rooms"

    # Basic Information
    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    floor_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    wing: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    # Type and Capacity
    room_type: Mapped[RoomTypeEnum] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    total_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    occupied_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    available_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Pricing (Monthly base price)
    price_monthly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    price_quarterly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    price_half_yearly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    price_yearly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Physical Specifications
    room_size_sqft: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    is_ac: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    has_attached_bathroom: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    has_balcony: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_wifi: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Amenities and Furnishing (JSON arrays)
    amenities: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        default=list,
    )
    furnishing: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        default=list,
    )

    # Status and Availability
    status: Mapped[RoomStatus] = mapped_column(
        String(50),
        nullable=False,
        default=RoomStatus.AVAILABLE,
        index=True,
    )
    is_available_for_booking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    is_under_maintenance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    # Maintenance Tracking
    maintenance_start_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    maintenance_end_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    maintenance_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    last_maintenance_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Media (JSON array of URLs)
    room_images: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        default=list,
    )
    primary_image: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    virtual_tour_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Additional Information
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    special_features: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Metadata
    last_occupancy_change: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_status_change: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    hostel = relationship(
        "Hostel",
        back_populates="rooms",
        lazy="joined",
    )
    beds = relationship(
        "Bed",
        back_populates="room",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    specifications = relationship(
        "RoomSpecification",
        back_populates="room",
        uselist=False,
        cascade="all, delete-orphan",
    )
    pricing_history = relationship(
        "RoomPricingHistory",
        back_populates="room",
        cascade="all, delete-orphan",
        order_by="desc(RoomPricingHistory.effective_from)",
    )
    maintenance_status = relationship(
        "RoomMaintenanceStatus",
        back_populates="room",
        uselist=False,
        cascade="all, delete-orphan",
    )
    access_control = relationship(
        "RoomAccessControl",
        back_populates="room",
        uselist=False,
        cascade="all, delete-orphan",
    )
    occupancy_limit = relationship(
        "RoomOccupancyLimit",
        back_populates="room",
        uselist=False,
        cascade="all, delete-orphan",
    )
    availability = relationship(
        "RoomAvailability",
        back_populates="room",
        uselist=False,
        cascade="all, delete-orphan",
    )
    amenity_associations = relationship(
        "RoomAmenity",
        back_populates="room",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        UniqueConstraint(
            "hostel_id",
            "room_number",
            name="uq_hostel_room_number",
        ),
        Index("ix_room_hostel_type", "hostel_id", "room_type"),
        Index("ix_room_hostel_status", "hostel_id", "status"),
        Index("ix_room_availability", "is_available_for_booking", "status"),
        Index("ix_room_occupancy", "hostel_id", "occupied_beds", "total_beds"),
        Index("ix_room_pricing", "price_monthly"),
        Index("ix_room_features", "is_ac", "has_attached_bathroom"),
    )

    def __repr__(self) -> str:
        return (
            f"<Room(id={self.id}, room_number={self.room_number}, "
            f"type={self.room_type}, status={self.status})>"
        )

    @property
    def occupancy_rate(self) -> Decimal:
        """Calculate current occupancy rate as percentage."""
        if self.total_beds == 0:
            return Decimal("0.00")
        return Decimal(
            (self.occupied_beds / self.total_beds * 100)
        ).quantize(Decimal("0.01"))

    @property
    def is_fully_occupied(self) -> bool:
        """Check if room is fully occupied."""
        return self.occupied_beds >= self.total_beds

    @property
    def vacancy_count(self) -> int:
        """Get number of vacant beds."""
        return max(0, self.total_beds - self.occupied_beds)

    def update_occupancy(self) -> None:
        """Update available beds count based on occupied beds."""
        self.available_beds = max(0, self.total_beds - self.occupied_beds)

    def can_accommodate(self, beds_required: int) -> bool:
        """Check if room can accommodate required number of beds."""
        return self.available_beds >= beds_required and self.is_available_for_booking


class RoomSpecification(BaseModel, UUIDMixin, TimestampModel):
    """
    Detailed room specifications and features.
    
    Extended technical and physical specifications for a room.
    """

    __tablename__ = "room_specifications"

    room_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Dimensions
    length_feet: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    width_feet: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    height_feet: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    carpet_area_sqft: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Windows and Ventilation
    number_of_windows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    window_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    has_exhaust_fan: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    natural_light_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,  # 1-5 scale
    )

    # Electrical
    number_of_power_outlets: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
    )
    has_ups_backup: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    lighting_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Bathroom Details (if attached)
    bathroom_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # "Western", "Indian", "Both"
    )
    has_geyser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_shower: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    bathroom_ventilation: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Storage
    number_of_wardrobes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    wardrobe_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    has_storage_shelves: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Furniture Details
    bed_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # "Single", "Bunk", "Double"
    )
    mattress_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    has_study_table: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_chair: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Climate Control
    ac_capacity_ton: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 2),
        nullable=True,
    )
    ac_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # "Split", "Window", "Cassette"
    )
    has_ceiling_fan: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Flooring and Finishing
    flooring_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    wall_finish: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    ceiling_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Safety and Security
    has_smoke_detector: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_fire_extinguisher: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_cctv_coverage: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    door_lock_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Additional Features
    special_features: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    accessibility_features: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Quality Ratings
    overall_condition_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,  # 1-5 scale
    )
    last_renovation_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    next_renovation_due: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Notes
    specification_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    room = relationship(
        "Room",
        back_populates="specifications",
    )

    def __repr__(self) -> str:
        return f"<RoomSpecification(room_id={self.room_id})>"


class RoomPricingHistory(BaseModel, UUIDMixin, TimestampModel, AuditMixin):
    """
    Historical pricing data for rooms with effective dates.
    
    Tracks all pricing changes over time with audit trail.
    """

    __tablename__ = "room_pricing_history"

    room_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Pricing
    price_monthly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    price_quarterly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    price_half_yearly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    price_yearly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Validity Period
    effective_from: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # Change Details
    change_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    previous_price_monthly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    price_change_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    # Approval
    approved_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Additional Info
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    room = relationship(
        "Room",
        back_populates="pricing_history",
    )

    __table_args__ = (
        Index("ix_pricing_history_room_current", "room_id", "is_current"),
        Index("ix_pricing_history_effective", "effective_from", "effective_to"),
    )

    def __repr__(self) -> str:
        return (
            f"<RoomPricingHistory(room_id={self.room_id}, "
            f"effective_from={self.effective_from}, "
            f"price_monthly={self.price_monthly})>"
        )


class RoomMaintenanceStatus(BaseModel, UUIDMixin, TimestampModel):
    """
    Real-time maintenance and availability status for rooms.
    
    Tracks current maintenance state and upcoming maintenance schedules.
    """

    __tablename__ = "room_maintenance_status"

    room_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Current Maintenance
    is_under_maintenance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    maintenance_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    maintenance_priority: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # LOW, MEDIUM, HIGH, URGENT
    )
    maintenance_start_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expected_completion_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_completion_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Maintenance Details
    maintenance_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    assigned_to: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    vendor_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    # Cost Tracking
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    actual_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Maintenance History Summary
    last_maintenance_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    last_maintenance_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    total_maintenance_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_maintenance_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Preventive Maintenance Schedule
    next_preventive_maintenance: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    preventive_maintenance_frequency_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Condition Assessment
    overall_condition_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,  # 1-10 scale
    )
    last_inspection_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    inspector_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    inspection_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Issues and Defects
    reported_issues: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    pending_repairs: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Status Flags
    requires_deep_cleaning: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    requires_painting: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    requires_fumigation: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Notes
    maintenance_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    room = relationship(
        "Room",
        back_populates="maintenance_status",
    )

    def __repr__(self) -> str:
        return (
            f"<RoomMaintenanceStatus(room_id={self.room_id}, "
            f"is_under_maintenance={self.is_under_maintenance})>"
        )


class RoomAccessControl(BaseModel, UUIDMixin, TimestampModel):
    """
    Access control and security features for rooms.
    
    Manages room access permissions, entry logs, and security settings.
    """

    __tablename__ = "room_access_control"

    room_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Access Method
    access_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="KEY",  # KEY, RFID, BIOMETRIC, PIN, SMART_LOCK
    )
    
    # Key Management
    key_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    master_key_access: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    spare_keys_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Digital Access
    rfid_card_numbers: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    pin_code: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # Encrypted
    )
    pin_last_changed: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Access Permissions
    allowed_user_ids: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    staff_access_level: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # FULL, LIMITED, EMERGENCY_ONLY
    )

    # Security Features
    has_door_sensor: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_motion_detector: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_panic_button: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_cctv_at_entrance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Entry Log Summary
    last_entry_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_entry_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
    )
    total_entries_today: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Security Alerts
    unauthorized_access_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_alert_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    alert_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Access Restrictions
    restricted_hours: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,  # {"start": "22:00", "end": "06:00"}
    )
    visitor_access_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    requires_escort: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Lockout/Emergency
    is_locked_out: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    lockout_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    lockout_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Notes
    access_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    room = relationship(
        "Room",
        back_populates="access_control",
    )

    def __repr__(self) -> str:
        return (
            f"<RoomAccessControl(room_id={self.room_id}, "
            f"access_method={self.access_method})>"
        )


class RoomOccupancyLimit(BaseModel, UUIDMixin, TimestampModel):
    """
    Occupancy limits and enforcement rules for rooms.
    
    Manages capacity constraints and occupancy policies.
    """

    __tablename__ = "room_occupancy_limits"

    room_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Capacity Limits
    maximum_occupants: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    minimum_occupants: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    recommended_occupants: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Current Occupancy
    current_occupants: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    current_male_occupants: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    current_female_occupants: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Gender Policy
    gender_policy: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ANY",  # MALE_ONLY, FEMALE_ONLY, CO_ED, ANY
    )
    allow_mixed_gender: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Age Restrictions
    minimum_age: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    maximum_age: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Occupancy Rules
    allow_overbooking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    overbooking_percentage: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    requires_approval_when_full: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Occupancy Tracking
    occupancy_history: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    peak_occupancy_reached: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    average_occupancy_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Alerts and Thresholds
    high_occupancy_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=80,  # Percentage
    )
    send_alert_when_full: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    alert_recipients: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Seasonal Adjustments
    seasonal_capacity_adjustments: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Special Conditions
    special_requirements: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    
    # Notes
    occupancy_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    room = relationship(
        "Room",
        back_populates="occupancy_limit",
    )

    __table_args__ = (
        Index("ix_occupancy_limit_capacity", "current_occupants", "maximum_occupants"),
    )

    def __repr__(self) -> str:
        return (
            f"<RoomOccupancyLimit(room_id={self.room_id}, "
            f"current={self.current_occupants}/{self.maximum_occupants})>"
        )

    @property
    def is_at_capacity(self) -> bool:
        """Check if room is at maximum capacity."""
        return self.current_occupants >= self.maximum_occupants

    @property
    def available_capacity(self) -> int:
        """Get available capacity."""
        return max(0, self.maximum_occupants - self.current_occupants)

    @property
    def occupancy_percentage(self) -> Decimal:
        """Calculate current occupancy percentage."""
        if self.maximum_occupants == 0:
            return Decimal("0.00")
        return Decimal(
            (self.current_occupants / self.maximum_occupants * 100)
        ).quantize(Decimal("0.01"))