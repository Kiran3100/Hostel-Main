# app/models/room/bed.py
"""
Bed models with comprehensive management and tracking.

Implements individual bed entities with condition tracking,
configuration, accessibility features, preferences, and utilization analytics.
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
from app.models.base.enums import BedStatus
from app.models.base.mixins import (
    SoftDeleteMixin,
    UUIDMixin,
    AuditMixin,
)

__all__ = [
    "Bed",
    "BedCondition",
    "BedConfiguration",
    "BedAccessibility",
    "BedPreference",
    "BedUtilization",
]


class Bed(BaseModel, UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin):
    """
    Individual bed entity with position and specifications.
    
    Represents a single bed/berth within a room with complete tracking.
    """

    __tablename__ = "beds"

    # Room Association
    room_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Bed Identification
    bed_number: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
    )
    bed_label: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    bed_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        unique=True,
    )

    # Position
    position_in_room: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # "Near window", "Corner", "Center", etc.
    )
    bed_row: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    bed_column: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    is_upper_bunk: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    is_lower_bunk: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Type and Specifications
    bed_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="SINGLE",  # SINGLE, BUNK, DOUBLE, CUSTOM
        index=True,
    )
    bed_size: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # TWIN, FULL, QUEEN, KING
    )
    dimensions: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,  # {"length": 75, "width": 36, "height": 18}
    )

    # Mattress
    mattress_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # FOAM, SPRING, MEMORY_FOAM, HYBRID
    )
    mattress_thickness_inches: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    mattress_brand: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    mattress_purchase_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Status
    status: Mapped[BedStatus] = mapped_column(
        String(50),
        nullable=False,
        default=BedStatus.AVAILABLE,
        index=True,
    )
    is_occupied: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    is_functional: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Current Occupant
    current_student_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    occupied_from: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    expected_vacate_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Features
    has_storage: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    storage_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # UNDER_BED, WARDROBE, LOCKER
    )
    has_study_lamp: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_power_outlet: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    has_privacy_curtain: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Bedding
    bedding_provided: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    bedding_items: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    last_bedding_change: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Maintenance
    last_maintenance_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    next_maintenance_due: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    maintenance_frequency_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=90,
    )

    # Quality
    condition_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,  # 1-10 scale
    )
    comfort_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,  # Average from user feedback
    )
    cleanliness_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )

    # Pricing (if different from room base price)
    has_custom_pricing: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    price_adjustment: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,  # Additional charge or discount
    )
    price_adjustment_reason: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    # Preferences and Restrictions
    gender_restriction: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,  # MALE, FEMALE, ANY
    )
    age_restriction_min: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    age_restriction_max: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    special_requirements: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Assignment Tracking
    total_assignments: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_occupancy_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_assignment_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    last_release_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Media
    images: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    primary_image: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Notes
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    special_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Metadata
    last_status_change: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_inspection_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Relationships
    room = relationship(
        "Room",
        back_populates="beds",
    )
    current_student = relationship(
        "Student",
        foreign_keys=[current_student_id],
        back_populates="current_bed",
    )
    assignments = relationship(
        "BedAssignment",
        back_populates="bed",
        cascade="all, delete-orphan",
        order_by="desc(BedAssignment.occupied_from)",
    )
    condition = relationship(
        "BedCondition",
        back_populates="bed",
        uselist=False,
        cascade="all, delete-orphan",
    )
    configuration = relationship(
        "BedConfiguration",
        back_populates="bed",
        uselist=False,
        cascade="all, delete-orphan",
    )
    accessibility = relationship(
        "BedAccessibility",
        back_populates="bed",
        uselist=False,
        cascade="all, delete-orphan",
    )
    preferences = relationship(
        "BedPreference",
        back_populates="bed",
        cascade="all, delete-orphan",
    )
    utilization = relationship(
        "BedUtilization",
        back_populates="bed",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "room_id",
            "bed_number",
            name="uq_room_bed_number",
        ),
        Index("ix_bed_room_status", "room_id", "status"),
        Index("ix_bed_availability", "is_available", "is_occupied"),
        Index("ix_bed_occupant", "current_student_id", "occupied_from"),
    )

    def __repr__(self) -> str:
        return (
            f"<Bed(id={self.id}, room_id={self.room_id}, "
            f"bed_number={self.bed_number}, status={self.status})>"
        )

    @property
    def is_bunk_bed(self) -> bool:
        """Check if this is a bunk bed."""
        return self.is_upper_bunk or self.is_lower_bunk

    @property
    def days_occupied_current(self) -> Optional[int]:
        """Calculate days occupied in current assignment."""
        if not self.occupied_from:
            return None
        from datetime import date
        return (date.today() - self.occupied_from).days

    @property
    def occupancy_rate(self) -> Decimal:
        """Calculate historical occupancy rate."""
        if self.total_occupancy_days == 0:
            return Decimal("0.00")
        from datetime import date
        if not self.created_at:
            return Decimal("0.00")
        total_days = (date.today() - self.created_at.date()).days
        if total_days == 0:
            return Decimal("0.00")
        return Decimal(
            (self.total_occupancy_days / total_days * 100)
        ).quantize(Decimal("0.01"))


class BedCondition(BaseModel, UUIDMixin, TimestampModel):
    """
    Bed condition and maintenance tracking.
    
    Monitors physical condition, wear and tear, and maintenance needs.
    """

    __tablename__ = "bed_conditions"

    bed_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("beds.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Overall Condition
    condition_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,  # 1-10 scale (10 being excellent)
    )
    condition_grade: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="A",  # A, B, C, D, F
    )
    overall_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="EXCELLENT",  # EXCELLENT, GOOD, FAIR, POOR, CRITICAL
    )

    # Bed Frame Condition
    frame_condition: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="GOOD",
    )
    frame_material: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # WOOD, METAL, COMPOSITE
    )
    frame_issues: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    frame_repair_needed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Mattress Condition
    mattress_condition: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="GOOD",
    )
    mattress_firmness: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # SOFT, MEDIUM, FIRM
    )
    mattress_sagging: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    mattress_stains: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    mattress_odor: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    mattress_replacement_needed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    mattress_last_cleaned: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Bedding Condition
    bedding_condition: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    bedding_issues: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    bedding_last_replaced: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Structural Issues
    has_structural_damage: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    structural_issues: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    safety_concerns: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    is_safe_to_use: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Cleanliness
    cleanliness_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,  # 1-10 scale
    )
    last_cleaned: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    last_deep_cleaned: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    requires_cleaning: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    requires_sanitization: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Pest Issues
    has_pest_issues: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    pest_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    last_pest_treatment: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Wear and Tear
    wear_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="MINIMAL",  # MINIMAL, MODERATE, SIGNIFICANT, SEVERE
    )
    estimated_remaining_life_months: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    replacement_priority: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="LOW",  # LOW, MEDIUM, HIGH, URGENT
    )

    # Inspection Details
    last_inspection_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    inspected_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    inspection_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    next_inspection_due: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    inspection_frequency_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=90,
    )

    # Maintenance Requirements
    requires_immediate_attention: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    maintenance_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    maintenance_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    maintenance_priority: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="LOW",
    )
    recommended_actions: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Cost Estimates
    estimated_repair_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    estimated_replacement_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Documentation
    condition_images: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    issue_images: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # History
    condition_history: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,  # Track condition changes over time
    )
    total_repairs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_repair_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Notes
    condition_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    bed = relationship(
        "Bed",
        back_populates="condition",
    )

    def __repr__(self) -> str:
        return (
            f"<BedCondition(bed_id={self.bed_id}, "
            f"score={self.condition_score}, grade={self.condition_grade})>"
        )

    @property
    def needs_replacement(self) -> bool:
        """Determine if bed needs replacement."""
        return (
            self.mattress_replacement_needed or
            self.replacement_priority in ["HIGH", "URGENT"] or
            not self.is_safe_to_use or
            self.condition_score <= 3
        )


class BedConfiguration(BaseModel, UUIDMixin, TimestampModel, AuditMixin):
    """
    Bed setup and configuration options.
    
    Manages customizable bed configurations and setup preferences.
    """

    __tablename__ = "bed_configurations"

    bed_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("beds.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Configuration Type
    configuration_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="STANDARD",  # STANDARD, CUSTOM, PREMIUM, BASIC
    )
    configuration_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    # Bed Frame Setup
    frame_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="PLATFORM",  # PLATFORM, BOX_SPRING, ADJUSTABLE, STORAGE
    )
    frame_height_inches: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    has_headboard: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    has_footboard: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Mattress Setup
    mattress_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="FOAM",
    )
    mattress_firmness: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="MEDIUM",  # SOFT, MEDIUM, FIRM, EXTRA_FIRM
    )
    has_mattress_topper: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    topper_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    has_mattress_protector: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Bedding Configuration
    pillow_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    pillow_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    blanket_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    comforter_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    sheet_thread_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Storage Configuration
    storage_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    storage_capacity_cubic_ft: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    has_under_bed_storage: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    storage_drawers_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Lighting
    has_reading_light: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    light_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # LED, HALOGEN, INCANDESCENT
    )
    light_position: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # HEADBOARD, WALL_MOUNTED, BEDSIDE
    )
    has_dimmer: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Power and Connectivity
    power_outlets_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    has_usb_charging: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    usb_ports_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Privacy Features
    has_privacy_curtain: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    curtain_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    curtain_color: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Comfort Features
    has_shelf: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    shelf_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    has_hooks: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    hooks_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    has_mirror: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Safety Features
    has_bed_rail: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_ladder: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    ladder_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    has_anti_slip: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Temperature Control
    has_heating_pad: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_cooling_pad: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Additional Features
    additional_features: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    custom_modifications: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Configuration Cost
    base_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    upgrade_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    total_configuration_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Configuration Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    configuration_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
    )
    last_modified_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Notes
    configuration_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    special_instructions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    bed = relationship(
        "Bed",
        back_populates="configuration",
    )

    def __repr__(self) -> str:
        return (
            f"<BedConfiguration(bed_id={self.bed_id}, "
            f"type={self.configuration_type})>"
        )


class BedAccessibility(BaseModel, UUIDMixin, TimestampModel):
    """
    Accessibility features and accommodations.
    
    Manages special accessibility features for beds to accommodate
    students with disabilities or special needs.
    """

    __tablename__ = "bed_accessibility"

    bed_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("beds.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Accessibility Level
    accessibility_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="STANDARD",  # STANDARD, ENHANCED, FULLY_ACCESSIBLE
    )
    is_ada_compliant: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    is_wheelchair_accessible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Physical Accessibility
    bed_height_adjustable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    minimum_height_inches: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    maximum_height_inches: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    current_height_inches: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Transfer Features
    has_transfer_board: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_grab_bars: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    grab_bar_locations: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    has_bed_rail: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    rail_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Mobility Aids
    clearance_around_bed_inches: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    wheelchair_turning_radius_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_under_bed_clearance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    under_bed_clearance_inches: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Special Mattress
    has_medical_mattress: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    medical_mattress_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # PRESSURE_RELIEF, ORTHOPEDIC, ADJUSTABLE
    )
    has_alternating_pressure: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Support Features
    has_lumbar_support: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_elevation_capability: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    elevation_zones: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,  # HEAD, FEET, KNEES
    )

    # Sensory Accommodations
    has_reduced_allergens: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    hypoallergenic_materials: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_noise_reduction: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Visual Accommodations
    has_high_contrast_markings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_tactile_indicators: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_enhanced_lighting: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Emergency Features
    has_emergency_call_button: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    call_button_location: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    has_fall_detection: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Storage Accessibility
    has_accessible_storage: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    storage_height_range: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,  # {"min": 24, "max": 48}
    )
    has_pull_out_storage: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Communication Aids
    has_communication_board: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_voice_control: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Documented Needs
    documented_needs: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    medical_documentation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    accommodation_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Customizations
    custom_modifications: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    modification_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Certification
    is_certified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    certification_type: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    certification_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    certification_expiry: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Last Assessment
    last_assessment_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    assessed_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    next_assessment_due: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Notes
    accessibility_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    special_requirements: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    bed = relationship(
        "Bed",
        back_populates="accessibility",
    )

    def __repr__(self) -> str:
        return (
            f"<BedAccessibility(bed_id={self.bed_id}, "
            f"level={self.accessibility_level})>"
        )


class BedPreference(BaseModel, UUIDMixin, TimestampModel):
    """
    Student preferences for bed selection.
    
    Tracks individual student preferences and matching criteria for bed assignments.
    """

    __tablename__ = "bed_preferences"

    bed_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("beds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Preference Priority
    preference_priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,  # 1 being highest priority
    )
    is_primary_preference: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Position Preferences
    preferred_position: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # NEAR_WINDOW, NEAR_DOOR, CORNER, CENTER
    )
    prefers_upper_bunk: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )
    prefers_lower_bunk: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )

    # Environmental Preferences
    light_preference: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # BRIGHT, MODERATE, DIM
    )
    noise_preference: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # QUIET, MODERATE, SOCIAL
    )
    temperature_preference: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # COOL, MODERATE, WARM
    )

    # Comfort Preferences
    mattress_firmness_preference: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # SOFT, MEDIUM, FIRM
    )
    pillow_preference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    bedding_material_preference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Privacy Preferences
    privacy_level_needed: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # HIGH, MODERATE, LOW
    )
    prefers_privacy_curtain: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Accessibility Needs
    requires_accessibility: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    accessibility_requirements: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    has_medical_needs: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    medical_requirements: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Roommate Preferences
    preferred_roommate_ids: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    roommate_compatibility_factors: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Schedule Preferences
    sleep_schedule: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # EARLY_BIRD, NIGHT_OWL, FLEXIBLE
    )
    study_schedule: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Feature Preferences
    preferred_features: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    must_have_features: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    deal_breakers: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Budget
    max_price_willing: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    prefers_economy_option: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Matching Score
    compatibility_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # 0-100 scale
    )
    match_factors: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Preference Status
    preference_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ACTIVE",  # ACTIVE, FULFILLED, EXPIRED, CANCELLED
        index=True,
    )
    is_flexible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    flexibility_level: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # HIGH, MODERATE, LOW
    )

    # Dates
    preference_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
    )
    valid_from: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    valid_to: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Fulfillment
    is_fulfilled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    fulfilled_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    fulfillment_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Notes
    preference_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    special_requests: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    bed = relationship(
        "Bed",
        back_populates="preferences",
    )

    __table_args__ = (
        Index("ix_bed_preference_student", "bed_id", "student_id"),
        Index("ix_bed_preference_status", "preference_status", "is_fulfilled"),
    )

    def __repr__(self) -> str:
        return (
            f"<BedPreference(bed_id={self.bed_id}, student_id={self.student_id}, "
            f"priority={self.preference_priority})>"
        )


class BedUtilization(BaseModel, UUIDMixin, TimestampModel):
    """
    Bed utilization analytics and optimization.
    
    Tracks usage patterns, occupancy metrics, and revenue analytics per bed.
    """

    __tablename__ = "bed_utilization"

    bed_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("beds.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Current Period Metrics
    current_month: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        index=True,  # YYYY-MM format
    )
    current_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    # Occupancy Metrics
    days_occupied_current_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    days_occupied_current_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    days_occupied_lifetime: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Availability Metrics
    days_available_current_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    days_maintenance_current_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Occupancy Rates
    occupancy_rate_current_month: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),  # Percentage
    )
    occupancy_rate_current_year: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    occupancy_rate_lifetime: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Assignment Metrics
    total_assignments: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    assignments_current_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    average_assignment_duration_days: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    longest_assignment_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    shortest_assignment_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Turnover Metrics
    turnover_count_current_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    turnover_rate_annual: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # Turnovers per year
    )
    average_vacancy_duration_days: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )

    # Revenue Metrics
    revenue_current_month: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    revenue_current_year: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    revenue_lifetime: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    average_monthly_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Revenue Per Day
    revenue_per_day_occupied: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    potential_revenue_current_month: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    revenue_loss_due_to_vacancy: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Maintenance Impact
    maintenance_cost_current_year: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    maintenance_cost_lifetime: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    revenue_loss_due_to_maintenance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Performance Metrics
    performance_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # 0-100 scale
    )
    efficiency_rating: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,  # EXCELLENT, GOOD, AVERAGE, POOR
    )
    profitability_index: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )

    # Demand Metrics
    booking_requests_current_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    booking_conversion_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    average_lead_time_days: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )

    # Satisfaction Metrics
    average_satisfaction_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,  # 1-5 scale
    )
    total_feedback_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    positive_feedback_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Issue Tracking
    total_issues_reported: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    issues_current_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    average_issue_resolution_days: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )

    # Benchmarking
    percentile_rank_occupancy: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,  # 0-100 percentile within hostel
    )
    percentile_rank_revenue: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    is_top_performer: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    is_underperformer: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Forecasting
    forecasted_occupancy_next_month: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    forecasted_revenue_next_month: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    demand_trend: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # INCREASING, STABLE, DECREASING
    )

    # Analytics Metadata
    last_calculated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    calculation_frequency_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=24,
    )
    next_calculation_due: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Historical Data
    historical_metrics: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,  # Store monthly/yearly trends
    )
    occupancy_pattern: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,  # Weekly/seasonal patterns
    )

    # Optimization Recommendations
    optimization_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # 0-100 scale
    )
    recommended_actions: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    improvement_opportunities: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Notes
    utilization_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    bed = relationship(
        "Bed",
        back_populates="utilization",
    )

    __table_args__ = (
        Index("ix_bed_util_performance", "performance_score", "efficiency_rating"),
        Index("ix_bed_util_occupancy", "occupancy_rate_current_month"),
    )

    def __repr__(self) -> str:
        return (
            f"<BedUtilization(bed_id={self.bed_id}, "
            f"occupancy_rate={self.occupancy_rate_current_month}%, "
            f"revenue={self.revenue_current_month})>"
        )

    @property
    def roi_percentage(self) -> Decimal:
        """Calculate ROI based on revenue vs maintenance cost."""
        if self.maintenance_cost_lifetime == 0:
            return Decimal("100.00")
        return Decimal(
            ((self.revenue_lifetime - self.maintenance_cost_lifetime) / 
             self.maintenance_cost_lifetime * 100)
        ).quantize(Decimal("0.01"))

    @property
    def net_revenue_current_year(self) -> Decimal:
        """Calculate net revenue after maintenance costs."""
        return self.revenue_current_year - self.maintenance_cost_current_year