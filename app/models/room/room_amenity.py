"""
Room amenity models with condition tracking and maintenance.

Manages room-specific amenities, their conditions, usage,
feedback, and inventory.
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
from app.models.base.mixins import (
    SoftDeleteMixin,
    UUIDMixin,
    AuditMixin,
)

__all__ = [
    "RoomAmenity",
    "AmenityCondition",
    "AmenityMaintenance",
    "AmenityUsage",
    "AmenityFeedback",
    "AmenityInventory",
]


class RoomAmenity(UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin, BaseModel):
    """
    Room-specific amenities and features.
    
    Tracks individual amenities available in rooms with detailed management.
    """

    __tablename__ = "room_amenities"

    room_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Amenity Information
    amenity_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )
    amenity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,  # FURNITURE, APPLIANCE, FIXTURE, UTILITY, TECHNOLOGY
    )
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,  # ESSENTIAL, COMFORT, LUXURY, ENTERTAINMENT
    )

    # Specifications
    brand: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    model_number: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    serial_number: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    specifications: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Status
    is_functional: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    current_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ACTIVE",  # ACTIVE, MAINTENANCE, DEFECTIVE, REPLACED
        index=True,
    )

    # Procurement
    purchase_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    purchase_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    vendor_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    invoice_number: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    # Warranty
    warranty_period_months: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    warranty_expiry_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    is_under_warranty: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Lifecycle
    installation_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    expected_lifespan_years: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    replacement_due_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Value
    current_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    depreciation_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Display
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    icon_name: Mapped[Optional[str]] = mapped_column(
        String(100),
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

    # Description
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    usage_instructions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    room = relationship(
        "Room",
        back_populates="amenity_associations",
    )
    condition = relationship(
        "AmenityCondition",
        back_populates="amenity",
        uselist=False,
        cascade="all, delete-orphan",
    )
    maintenance_records = relationship(
        "AmenityMaintenance",
        back_populates="amenity",
        cascade="all, delete-orphan",
        order_by="desc(AmenityMaintenance.maintenance_date)",
    )
    usage_logs = relationship(
        "AmenityUsage",
        back_populates="amenity",
        cascade="all, delete-orphan",
    )
    feedback_records = relationship(
        "AmenityFeedback",
        back_populates="amenity",
        cascade="all, delete-orphan",
    )
    inventory_record = relationship(
        "AmenityInventory",
        back_populates="amenity",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_room_amenity_room_type", "room_id", "amenity_type"),
        Index("ix_room_amenity_status", "current_status", "is_functional"),
    )

    def __repr__(self) -> str:
        return (
            f"<RoomAmenity(id={self.id}, room_id={self.room_id}, "
            f"name={self.amenity_name}, status={self.current_status})>"
        )


class AmenityCondition(UUIDMixin, TimestampModel, BaseModel):
    """
    Condition tracking for amenities.
    
    Monitors current condition and degradation of room amenities.
    """

    __tablename__ = "amenity_conditions"

    amenity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_amenities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Condition Rating
    condition_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,  # 1-10 scale
    )
    condition_grade: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="A",  # A, B, C, D, F
    )
    condition_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Assessment Details
    last_assessed_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    assessed_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assessment_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Wear and Tear
    wear_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="MINIMAL",  # MINIMAL, MODERATE, SIGNIFICANT, SEVERE
    )
    visible_damage: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    damage_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    damage_images: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Functionality
    is_fully_functional: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    functional_issues: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    performance_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,  # 1-10 scale
    )

    # Cleanliness
    cleanliness_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,  # 1-10 scale
    )
    last_cleaned_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    requires_cleaning: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Maintenance Requirements
    requires_maintenance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    maintenance_priority: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # LOW, MEDIUM, HIGH, URGENT
    )
    recommended_actions: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Replacement Indicators
    requires_replacement: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    replacement_priority: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    replacement_cost_estimate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # History Tracking
    condition_history: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    degradation_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # Points per month
    )

    # Next Actions
    next_inspection_due: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    inspection_frequency_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=90,
    )

    # Relationship
    amenity = relationship(
        "RoomAmenity",
        back_populates="condition",
    )

    def __repr__(self) -> str:
        return (
            f"<AmenityCondition(amenity_id={self.amenity_id}, "
            f"score={self.condition_score}, grade={self.condition_grade})>"
        )


class AmenityMaintenance(UUIDMixin, TimestampModel, AuditMixin, BaseModel):
    """
    Maintenance schedule for room amenities.
    
    Tracks all maintenance activities performed on amenities.
    """

    __tablename__ = "amenity_maintenance"

    amenity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_amenities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Maintenance Details
    maintenance_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,  # PREVENTIVE, CORRECTIVE, REPAIR, REPLACEMENT, CLEANING
    )
    maintenance_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    maintenance_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Work Performed
    work_performed: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    parts_replaced: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    materials_used: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Personnel
    performed_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    vendor_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    technician_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    # Duration and Cost
    duration_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    labor_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    parts_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Status
    maintenance_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="COMPLETED",  # SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED
        index=True,
    )
    completion_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Quality Check
    quality_checked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    quality_check_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    quality_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,  # 1-10 scale
    )

    # Warranty
    covered_under_warranty: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    warranty_claim_number: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    # Follow-up
    requires_follow_up: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    follow_up_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    follow_up_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Documentation
    before_images: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    after_images: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    invoice_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Notes
    maintenance_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    amenity = relationship(
        "RoomAmenity",
        back_populates="maintenance_records",
    )

    __table_args__ = (
        Index("ix_amenity_maintenance_date", "amenity_id", "maintenance_date"),
        Index("ix_amenity_maintenance_type", "amenity_id", "maintenance_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<AmenityMaintenance(amenity_id={self.amenity_id}, "
            f"type={self.maintenance_type}, date={self.maintenance_date})>"
        )


class AmenityUsage(UUIDMixin, TimestampModel, BaseModel):
    """
    Usage tracking and analytics for amenities.
    
    Monitors amenity usage patterns and intensity.
    """

    __tablename__ = "amenity_usage"

    amenity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_amenities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Usage Period
    usage_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    usage_month: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        index=True,  # YYYY-MM format
    )

    # Usage Metrics
    usage_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    usage_duration_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    usage_intensity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="NORMAL",  # LIGHT, NORMAL, HEAVY, INTENSIVE
    )

    # Users
    unique_users_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    primary_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Performance
    performance_issues_reported: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    downtime_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Energy/Resource Consumption (if applicable)
    energy_consumption_kwh: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    water_consumption_liters: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Cost Impact
    operational_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    maintenance_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Analytics
    usage_pattern: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,  # Peak hours, usage distribution, etc.
    )
    utilization_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # Percentage
    )

    # Notes
    usage_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    amenity = relationship(
        "RoomAmenity",
        back_populates="usage_logs",
    )

    __table_args__ = (
        Index("ix_amenity_usage_period", "amenity_id", "usage_date"),
        Index("ix_amenity_usage_month", "amenity_id", "usage_month"),
    )

    def __repr__(self) -> str:
        return (
            f"<AmenityUsage(amenity_id={self.amenity_id}, "
            f"date={self.usage_date}, count={self.usage_count})>"
        )


class AmenityFeedback(UUIDMixin, TimestampModel, BaseModel):
    """
    Guest feedback on amenities.
    
    Collects and manages user feedback for amenity quality and satisfaction.
    """

    __tablename__ = "amenity_feedback"

    amenity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_amenities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Ratings
    overall_rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,  # 1-5 scale
    )
    quality_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,  # 1-5 scale
    )
    functionality_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,  # 1-5 scale
    )
    condition_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,  # 1-5 scale
    )

    # Feedback Content
    feedback_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    likes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    dislikes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    suggestions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Issues Reported
    has_issues: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    issue_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    issue_severity: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # LOW, MEDIUM, HIGH, CRITICAL
    )

    # Media
    feedback_images: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Response
    has_response: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    response_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    responded_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    responded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Action Taken
    action_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    action_taken: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    action_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # PENDING, IN_PROGRESS, COMPLETED
    )

    # Verification
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    verified_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Sentiment Analysis
    sentiment_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 2),
        nullable=True,  # -1.00 to 1.00
    )
    sentiment_label: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # POSITIVE, NEUTRAL, NEGATIVE
    )

    # Relationship
    amenity = relationship(
        "RoomAmenity",
        back_populates="feedback_records",
    )

    __table_args__ = (
        Index("ix_amenity_feedback_rating", "amenity_id", "overall_rating"),
        Index("ix_amenity_feedback_issues", "has_issues", "issue_severity"),
    )

    def __repr__(self) -> str:
        return (
            f"<AmenityFeedback(amenity_id={self.amenity_id}, "
            f"rating={self.overall_rating}, student_id={self.student_id})>"
        )


class AmenityInventory(UUIDMixin, TimestampModel, BaseModel):
    """
    Inventory management for amenities.
    
    Tracks amenity inventory, stock levels, and procurement needs.
    """

    __tablename__ = "amenity_inventory"

    amenity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_amenities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Inventory Details
    inventory_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    asset_tag: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    barcode: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    qr_code: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    # Stock Information
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    unit_of_measure: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PIECE",
    )

    # Location
    storage_location: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    current_location: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    is_installed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Valuation
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    current_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    depreciation_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,  # STRAIGHT_LINE, DECLINING_BALANCE
    )
    accumulated_depreciation: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Lifecycle
    acquisition_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
    )
    installation_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    expected_retirement_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    actual_retirement_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Status
    inventory_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ACTIVE",  # ACTIVE, IN_STORAGE, IN_MAINTENANCE, RETIRED, DISPOSED
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Transfer History
    transfer_history: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    last_transfer_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    transfer_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Audit Trail
    last_physical_verification: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    verified_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    verification_frequency_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=180,
    )
    next_verification_due: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Insurance
    is_insured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    insurance_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    insurance_policy_number: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    insurance_expiry_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Disposal
    disposal_method: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    disposal_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    disposal_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Notes
    inventory_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    amenity = relationship(
        "RoomAmenity",
        back_populates="inventory_record",
    )

    __table_args__ = (
        Index("ix_amenity_inventory_status", "inventory_status", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<AmenityInventory(amenity_id={self.amenity_id}, "
            f"code={self.inventory_code}, status={self.inventory_status})>"
        )

    @property
    def net_book_value(self) -> Decimal:
        """Calculate net book value."""
        return self.current_value - self.accumulated_depreciation

    @property
    def age_in_years(self) -> Decimal:
        """Calculate age in years from acquisition date."""
        from datetime import date
        today = date.today()
        days_old = (today - self.acquisition_date).days
        return Decimal(days_old / 365).quantize(Decimal("0.1"))