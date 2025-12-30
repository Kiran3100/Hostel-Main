"""
Room type models with features, pricing, and comparison.

Manages standardized room type definitions with associated
features, pricing structures, and upgrade paths.
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
from app.models.base.enums import RoomType as RoomTypeEnum
from app.models.base.mixins import (
    SoftDeleteMixin,
    UUIDMixin,
    AuditMixin,
)

__all__ = [
    "RoomTypeDefinition",
    "RoomTypeFeature",
    "RoomTypePricing",
    "RoomTypeAvailability",
    "RoomTypeComparison",
    "RoomTypeUpgrade",
]


class RoomTypeDefinition(UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin, BaseModel):
    """
    Room type definitions with standardized categories.
    
    Master configuration for different room types across hostels.
    """

    __tablename__ = "room_type_definitions"

    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Type Information
    room_type: Mapped[RoomTypeEnum] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    type_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    type_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    
    # Capacity
    standard_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    minimum_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    maximum_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Description
    short_description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    detailed_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Standard Features
    standard_features: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    standard_amenities: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    standard_furnishing: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Physical Specifications
    standard_size_sqft: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    minimum_size_sqft: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Pricing Guidelines
    base_price_monthly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    price_range_min: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    price_range_max: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    # Availability
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    is_available_for_booking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Marketing
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    is_popular: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    marketing_tags: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
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
    floor_plan_image: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Metadata
    total_rooms_of_type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    currently_occupied: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    average_occupancy_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Relationships
    hostel = relationship(
        "Hostel",
        back_populates="room_types",
    )
    features = relationship(
        "RoomTypeFeature",
        back_populates="room_type_definition",
        cascade="all, delete-orphan",
    )
    pricing = relationship(
        "RoomTypePricing",
        back_populates="room_type_definition",
        cascade="all, delete-orphan",
    )
    availability = relationship(
        "RoomTypeAvailability",
        back_populates="room_type_definition",
        uselist=False,
        cascade="all, delete-orphan",
    )
    comparisons = relationship(
        "RoomTypeComparison",
        foreign_keys="RoomTypeComparison.room_type_id",
        back_populates="room_type",
        cascade="all, delete-orphan",
    )
    upgrade_from = relationship(
        "RoomTypeUpgrade",
        foreign_keys="RoomTypeUpgrade.from_room_type_id",
        back_populates="from_room_type",
        cascade="all, delete-orphan",
    )
    upgrade_to = relationship(
        "RoomTypeUpgrade",
        foreign_keys="RoomTypeUpgrade.to_room_type_id",
        back_populates="to_room_type",
    )

    __table_args__ = (
        UniqueConstraint(
            "hostel_id",
            "room_type",
            name="uq_hostel_room_type",
        ),
        UniqueConstraint(
            "hostel_id",
            "type_code",
            name="uq_hostel_type_code",
        ),
        Index("ix_room_type_def_active", "hostel_id", "is_active"),
        Index("ix_room_type_def_featured", "is_featured", "is_popular"),
    )

    def __repr__(self) -> str:
        return (
            f"<RoomTypeDefinition(id={self.id}, type={self.room_type}, "
            f"name={self.type_name})>"
        )


class RoomTypeFeature(UUIDMixin, TimestampModel, BaseModel):
    """
    Features and amenities per room type.
    
    Detailed feature configuration for each room type.
    """

    __tablename__ = "room_type_features"

    room_type_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_type_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Feature Details
    feature_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    feature_category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,  # AMENITY, FURNITURE, UTILITY, TECHNOLOGY, SAFETY
    )
    feature_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Availability
    is_standard: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    is_optional: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    additional_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Display
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    icon_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    is_highlighted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Specifications
    specifications: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationship
    room_type_definition = relationship(
        "RoomTypeDefinition",
        back_populates="features",
    )

    __table_args__ = (
        Index("ix_room_type_feature_category", "room_type_id", "feature_category"),
    )

    def __repr__(self) -> str:
        return (
            f"<RoomTypeFeature(room_type_id={self.room_type_id}, "
            f"feature={self.feature_name})>"
        )


class RoomTypePricing(UUIDMixin, TimestampModel, AuditMixin, BaseModel):
    """
    Base pricing structure per room type.
    
    Manages pricing tiers and seasonal adjustments.
    """

    __tablename__ = "room_type_pricing"

    room_type_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_type_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Pricing Tier
    pricing_tier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="STANDARD",  # STANDARD, PREMIUM, ECONOMY, SEASONAL
    )
    tier_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Base Pricing
    base_price_monthly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    base_price_quarterly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    base_price_half_yearly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    base_price_yearly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Discounts
    quarterly_discount_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    half_yearly_discount_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    yearly_discount_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
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

    # Seasonal Adjustments
    is_seasonal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    season_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    seasonal_markup_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Additional Charges
    security_deposit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    registration_fee: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    maintenance_fee_monthly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Special Offers
    has_special_offer: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    special_offer_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    special_offer_discount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Notes
    pricing_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    room_type_definition = relationship(
        "RoomTypeDefinition",
        back_populates="pricing",
    )

    __table_args__ = (
        Index("ix_room_type_pricing_current", "room_type_id", "is_current"),
        Index("ix_room_type_pricing_effective", "effective_from", "effective_to"),
    )

    def __repr__(self) -> str:
        return (
            f"<RoomTypePricing(room_type_id={self.room_type_id}, "
            f"tier={self.pricing_tier}, price={self.base_price_monthly})>"
        )


class RoomTypeAvailability(UUIDMixin, TimestampModel, BaseModel):
    """
    Availability patterns and seasonal adjustments.
    
    Manages availability rules and capacity planning for room types.
    """

    __tablename__ = "room_type_availability"

    room_type_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_type_definitions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Current Availability
    total_rooms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    available_rooms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    occupied_rooms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    reserved_rooms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    maintenance_rooms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Capacity Metrics
    total_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    available_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    occupancy_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Booking Settings
    min_advance_booking_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    max_advance_booking_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=365,
    )
    allow_instant_booking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Seasonal Patterns
    peak_season_dates: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    off_season_dates: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    seasonal_capacity_adjustments: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Availability Forecasting
    forecasted_demand: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    expected_occupancy_next_month: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Alerts
    low_availability_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,  # Percentage
    )
    send_alert_when_low: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    last_alert_sent: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Last Updated
    last_availability_check: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship
    room_type_definition = relationship(
        "RoomTypeDefinition",
        back_populates="availability",
    )

    def __repr__(self) -> str:
        return (
            f"<RoomTypeAvailability(room_type_id={self.room_type_id}, "
            f"available={self.available_rooms}/{self.total_rooms})>"
        )

    @property
    def availability_percentage(self) -> Decimal:
        """Calculate availability percentage."""
        if self.total_rooms == 0:
            return Decimal("0.00")
        return Decimal(
            (self.available_rooms / self.total_rooms * 100)
        ).quantize(Decimal("0.01"))


class RoomTypeComparison(UUIDMixin, TimestampModel, BaseModel):
    """
    Comparative analysis between room types.
    
    Facilitates side-by-side comparison of room types for decision making.
    """

    __tablename__ = "room_type_comparisons"

    room_type_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_type_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    compared_with_type_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_type_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Comparison Metrics
    price_difference: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    price_difference_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )
    
    # Feature Comparison
    additional_features: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    missing_features: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    
    # Space Comparison
    size_difference_sqft: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    capacity_difference: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Value Analysis
    value_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 2),
        nullable=True,  # 1-10 scale
    )
    recommendation: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Popularity Comparison
    popularity_difference: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    occupancy_rate_difference: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Notes
    comparison_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    room_type = relationship(
        "RoomTypeDefinition",
        foreign_keys=[room_type_id],
        back_populates="comparisons",
    )

    __table_args__ = (
        UniqueConstraint(
            "room_type_id",
            "compared_with_type_id",
            name="uq_room_type_comparison",
        ),
        Index("ix_room_type_comparison", "room_type_id", "compared_with_type_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<RoomTypeComparison(room_type_id={self.room_type_id}, "
            f"vs={self.compared_with_type_id})>"
        )


class RoomTypeUpgrade(UUIDMixin, TimestampModel, AuditMixin, BaseModel):
    """
    Upgrade paths and pricing differentials.
    
    Manages room type upgrade options and associated costs.
    """

    __tablename__ = "room_type_upgrades"

    from_room_type_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_type_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_room_type_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_type_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Upgrade Details
    upgrade_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    upgrade_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Pricing
    upgrade_fee_one_time: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    price_difference_monthly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    price_difference_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )

    # Availability
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    # Conditions
    minimum_stay_months: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    blackout_dates: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Benefits
    upgrade_benefits: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    additional_features: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Marketing
    is_promoted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    promotion_text: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    discount_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Validity
    valid_from: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    valid_to: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    # Tracking
    total_upgrades_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_upgrade_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Notes
    upgrade_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    from_room_type = relationship(
        "RoomTypeDefinition",
        foreign_keys=[from_room_type_id],
        back_populates="upgrade_from",
    )
    to_room_type = relationship(
        "RoomTypeDefinition",
        foreign_keys=[to_room_type_id],
        back_populates="upgrade_to",
    )

    __table_args__ = (
        UniqueConstraint(
            "from_room_type_id",
            "to_room_type_id",
            name="uq_room_type_upgrade_path",
        ),
        Index("ix_room_type_upgrade_available", "is_available", "is_promoted"),
    )

    def __repr__(self) -> str:
        return (
            f"<RoomTypeUpgrade(from={self.from_room_type_id}, "
            f"to={self.to_room_type_id}, fee={self.price_difference_monthly})>"
        )

    @property
    def is_valid(self) -> bool:
        """Check if upgrade path is currently valid."""
        from datetime import date
        today = date.today()
        
        if not self.is_available:
            return False
            
        if self.valid_from and today < self.valid_from:
            return False
            
        if self.valid_to and today > self.valid_to:
            return False
            
        return True