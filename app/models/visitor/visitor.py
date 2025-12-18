# --- File: app/models/visitor/visitor.py ---
"""
Visitor core model with profile and behavioral tracking.

This module defines the core Visitor entity with comprehensive
profile management, session tracking, and conversion analytics.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import (
    AuditMixin,
    SoftDeleteMixin,
    UUIDMixin,
)
from app.models.base.enums import (
    DietaryPreference,
    HostelType,
    RoomType,
)

if TYPE_CHECKING:
    from app.models.user.user import User
    from app.models.visitor.visitor_preferences import VisitorPreferences
    from app.models.visitor.visitor_favorite import VisitorFavorite
    from app.models.visitor.saved_search import SavedSearch
    from app.models.booking.booking import Booking
    from app.models.inquiry.inquiry import Inquiry
    from app.models.review.review import Review

__all__ = [
    "Visitor",
    "VisitorSession",
    "VisitorJourney",
    "VisitorSegment",
    "VisitorEngagement",
]


class Visitor(UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin):
    """
    Core Visitor entity with profile and behavioral tracking.
    
    Represents a platform visitor with preferences, search history,
    and conversion tracking. Extends User with visitor-specific data.
    """

    __tablename__ = "visitors"
    __table_args__ = (
        Index("idx_visitor_user_id", "user_id"),
        Index("idx_visitor_email", "email"),
        Index("idx_visitor_phone", "phone"),
        Index("idx_visitor_created_at", "created_at"),
        Index("idx_visitor_last_active", "last_active_at"),
        Index(
            "idx_visitor_engagement_score",
            "engagement_score",
            postgresql_where="is_deleted = false",
        ),
        UniqueConstraint("user_id", name="uq_visitor_user_id"),
        CheckConstraint(
            "budget_min IS NULL OR budget_min >= 0",
            name="ck_visitor_budget_min_positive",
        ),
        CheckConstraint(
            "budget_max IS NULL OR budget_max >= 0",
            name="ck_visitor_budget_max_positive",
        ),
        CheckConstraint(
            "budget_min IS NULL OR budget_max IS NULL OR budget_max >= budget_min",
            name="ck_visitor_budget_range",
        ),
        CheckConstraint(
            "engagement_score >= 0 AND engagement_score <= 100",
            name="ck_visitor_engagement_score_range",
        ),
        {"comment": "Visitor profiles with preferences and behavioral tracking"},
    )

    # ==================== Core Fields ====================
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to User account",
    )

    # Cached user fields for query optimization
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Cached email from user",
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Cached phone from user",
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Full name for personalization",
    )

    # ==================== Room Preferences ====================
    preferred_room_type: Mapped[Optional[RoomType]] = mapped_column(
        nullable=True,
        comment="Preferred room type",
    )
    preferred_hostel_type: Mapped[Optional[HostelType]] = mapped_column(
        nullable=True,
        comment="Preferred hostel type (male/female/co-ed)",
    )

    # ==================== Budget Constraints ====================
    budget_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Minimum monthly budget",
    )
    budget_max: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Maximum monthly budget",
    )

    # ==================== Location Preferences ====================
    preferred_cities: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Preferred cities list",
    )
    preferred_areas: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Preferred areas/localities",
    )
    max_distance_from_work_km: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Maximum acceptable distance from workplace",
    )

    # ==================== Amenity Preferences ====================
    required_amenities: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Must-have amenities (deal-breakers)",
    )
    preferred_amenities: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Nice-to-have amenities",
    )

    # ==================== Facility Requirements ====================
    need_parking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Requires parking facility",
    )
    need_gym: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Requires gym facility",
    )
    need_laundry: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Requires laundry facility",
    )
    need_mess: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Requires mess/dining facility",
    )

    # ==================== Dietary Preferences ====================
    dietary_preference: Mapped[Optional[DietaryPreference]] = mapped_column(
        nullable=True,
        comment="Dietary preference (vegetarian/non-veg/vegan/jain)",
    )

    # ==================== Move-in Details ====================
    earliest_move_in_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Earliest date willing to move in",
    )
    preferred_lease_duration_months: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Preferred lease duration (1-24 months)",
    )

    # ==================== Notification Preferences ====================
    email_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Email notifications enabled",
    )
    sms_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="SMS notifications enabled",
    )
    push_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Push notifications enabled",
    )
    notify_on_price_drop: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Notify on price drops for saved hostels",
    )
    notify_on_availability: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Notify on new availability",
    )
    notify_on_new_listings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Notify on new matching hostels",
    )

    # ==================== Saved Hostels ====================
    favorite_hostel_ids: Mapped[List[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        nullable=False,
        server_default="{}",
        comment="List of favorite/saved hostel IDs",
    )

    # ==================== Activity Tracking ====================
    total_searches: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Total number of searches performed",
    )
    total_hostel_views: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Total hostel detail page views",
    )
    total_inquiries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Total inquiries sent",
    )
    total_bookings: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Total bookings made",
    )
    completed_bookings: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of completed stays",
    )
    cancelled_bookings: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of cancelled bookings",
    )

    # ==================== Engagement Metrics ====================
    engagement_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default="0.00",
        comment="Engagement score (0-100) based on activity",
    )
    last_active_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Last activity timestamp",
    )
    last_search_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last search performed",
    )
    last_booking_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last booking made",
    )

    # ==================== Segmentation ====================
    visitor_segment: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Visitor segment (high_intent, browser, etc.)",
    )
    conversion_likelihood: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Predicted conversion likelihood (0-100)",
    )

    # ==================== Metadata ====================
    search_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Search behavior metadata and patterns",
    )
    preferences_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional preferences and settings",
    )

    # ==================== Relationships ====================
    user: Mapped["User"] = relationship(
        "User",
        back_populates="visitor_profile",
        lazy="joined",
    )

    preferences: Mapped[Optional["VisitorPreferences"]] = relationship(
        "VisitorPreferences",
        back_populates="visitor",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    favorites: Mapped[List["VisitorFavorite"]] = relationship(
        "VisitorFavorite",
        back_populates="visitor",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    saved_searches: Mapped[List["SavedSearch"]] = relationship(
        "SavedSearch",
        back_populates="visitor",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    sessions: Mapped[List["VisitorSession"]] = relationship(
        "VisitorSession",
        back_populates="visitor",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    bookings: Mapped[List["Booking"]] = relationship(
        "Booking",
        back_populates="visitor",
        foreign_keys="[Booking.visitor_id]",
        lazy="dynamic",
    )

    inquiries: Mapped[List["Inquiry"]] = relationship(
        "Inquiry",
        back_populates="visitor",
        lazy="dynamic",
    )

    reviews: Mapped[List["Review"]] = relationship(
        "Review",
        back_populates="visitor",
        lazy="dynamic",
    )

    # ==================== Properties ====================
    @property
    def has_budget_preference(self) -> bool:
        """Check if visitor has set budget preferences."""
        return self.budget_min is not None or self.budget_max is not None

    @property
    def has_location_preference(self) -> bool:
        """Check if visitor has set location preferences."""
        return len(self.preferred_cities) > 0 or len(self.preferred_areas) > 0

    @property
    def notification_channels_enabled(self) -> int:
        """Count enabled notification channels."""
        return sum(
            [
                self.email_notifications,
                self.sms_notifications,
                self.push_notifications,
            ]
        )

    @property
    def booking_conversion_rate(self) -> Decimal:
        """Calculate booking conversion rate."""
        if self.total_searches == 0:
            return Decimal("0.00")
        return Decimal(
            (self.total_bookings / self.total_searches) * 100
        ).quantize(Decimal("0.01"))

    @property
    def is_active_visitor(self) -> bool:
        """Check if visitor is recently active (within 30 days)."""
        if self.last_active_at is None:
            return False
        days_since_active = (datetime.utcnow() - self.last_active_at).days
        return days_since_active <= 30

    def __repr__(self) -> str:
        return (
            f"<Visitor(id={self.id}, email={self.email}, "
            f"engagement_score={self.engagement_score})>"
        )


class VisitorSession(UUIDMixin, TimestampModel):
    """
    Visitor session tracking for analytics and personalization.
    
    Tracks individual visitor sessions with device info,
    activity tracking, and conversion metrics.
    """

    __tablename__ = "visitor_sessions"
    __table_args__ = (
        Index("idx_visitor_session_visitor_id", "visitor_id"),
        Index("idx_visitor_session_started_at", "started_at"),
        Index("idx_visitor_session_ended_at", "ended_at"),
        Index("idx_visitor_session_device", "device_type"),
        CheckConstraint(
            "duration_seconds >= 0",
            name="ck_visitor_session_duration_positive",
        ),
        CheckConstraint(
            "page_views >= 0",
            name="ck_visitor_session_page_views_positive",
        ),
        {"comment": "Visitor session tracking and analytics"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to visitor",
    )

    session_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique session identifier",
    )

    # ==================== Session Timing ====================
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Session start timestamp",
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Session end timestamp",
    )
    duration_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Total session duration in seconds",
    )

    # ==================== Device Information ====================
    device_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Device type (desktop/mobile/tablet)",
    )
    device_os: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Operating system",
    )
    browser: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Browser type and version",
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Full user agent string",
    )

    # ==================== Location Information ====================
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address (IPv4/IPv6)",
    )
    country: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Country from IP geolocation",
    )
    city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="City from IP geolocation",
    )

    # ==================== Activity Metrics ====================
    page_views: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of pages viewed in session",
    )
    searches_performed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Searches performed in session",
    )
    hostels_viewed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Hostels viewed in session",
    )
    inquiries_sent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Inquiries sent in session",
    )

    # ==================== Conversion Tracking ====================
    booking_made: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether booking was made in this session",
    )
    booking_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="Booking ID if conversion occurred",
    )

    # ==================== Traffic Source ====================
    referrer_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Referrer URL",
    )
    utm_source: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="UTM source parameter",
    )
    utm_medium: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="UTM medium parameter",
    )
    utm_campaign: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="UTM campaign parameter",
    )

    # ==================== Metadata ====================
    session_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional session data and analytics",
    )

    # ==================== Relationships ====================
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        back_populates="sessions",
    )

    def __repr__(self) -> str:
        return (
            f"<VisitorSession(id={self.id}, visitor_id={self.visitor_id}, "
            f"started_at={self.started_at})>"
        )


class VisitorJourney(UUIDMixin, TimestampModel):
    """
    Visitor journey mapping and funnel analysis.
    
    Tracks visitor's complete journey from first visit
    to conversion with touchpoint analysis.
    """

    __tablename__ = "visitor_journeys"
    __table_args__ = (
        Index("idx_visitor_journey_visitor_id", "visitor_id"),
        Index("idx_visitor_journey_stage", "current_stage"),
        Index("idx_visitor_journey_created_at", "created_at"),
        {"comment": "Visitor journey and funnel tracking"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to visitor",
    )

    # ==================== Journey Stages ====================
    current_stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Current funnel stage (awareness/consideration/decision/conversion)",
    )

    first_visit_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="First platform visit timestamp",
    )
    first_search_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="First search performed",
    )
    first_hostel_view_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="First hostel detail view",
    )
    first_inquiry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="First inquiry sent",
    )
    first_booking_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="First booking made",
    )

    # ==================== Touchpoint Tracking ====================
    total_touchpoints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Total number of touchpoints",
    )
    touchpoint_sequence: Mapped[List[dict]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="Ordered list of touchpoints with timestamps",
    )

    # ==================== Channel Attribution ====================
    first_channel: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="First acquisition channel",
    )
    last_channel: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Last interaction channel before conversion",
    )
    channel_sequence: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Sequence of channels in journey",
    )

    # ==================== Conversion Metrics ====================
    is_converted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether journey resulted in conversion",
    )
    conversion_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date of conversion",
    )
    time_to_conversion_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Days from first visit to conversion",
    )

    # ==================== Metadata ====================
    journey_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional journey analytics and insights",
    )

    # ==================== Relationships ====================
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        foreign_keys=[visitor_id],
    )

    def __repr__(self) -> str:
        return (
            f"<VisitorJourney(id={self.id}, visitor_id={self.visitor_id}, "
            f"stage={self.current_stage})>"
        )


class VisitorSegment(UUIDMixin, TimestampModel):
    """
    Visitor segmentation for targeted marketing and personalization.
    
    Defines visitor segments based on behavior, preferences,
    and conversion likelihood for personalized experiences.
    """

    __tablename__ = "visitor_segments"
    __table_args__ = (
        Index("idx_visitor_segment_name", "segment_name"),
        Index("idx_visitor_segment_active", "is_active"),
        UniqueConstraint("segment_name", name="uq_visitor_segment_name"),
        {"comment": "Visitor segmentation definitions"},
    )

    # ==================== Core Fields ====================
    segment_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique segment name",
    )
    segment_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Segment description and criteria",
    )

    # ==================== Segment Rules ====================
    inclusion_rules: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Rules for segment inclusion",
    )
    exclusion_rules: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Rules for segment exclusion",
    )

    # ==================== Segment Metrics ====================
    total_visitors: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Total visitors in segment",
    )
    active_visitors: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Currently active visitors in segment",
    )
    conversion_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default="0.00",
        comment="Segment conversion rate percentage",
    )

    # ==================== Segment Status ====================
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        index=True,
        comment="Whether segment is actively tracked",
    )

    # ==================== Metadata ====================
    segment_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional segment configuration and analytics",
    )

    def __repr__(self) -> str:
        return f"<VisitorSegment(id={self.id}, name={self.segment_name})>"


class VisitorEngagement(UUIDMixin, TimestampModel):
    """
    Detailed visitor engagement tracking and scoring.
    
    Tracks granular engagement metrics for personalization
    and behavior analysis.
    """

    __tablename__ = "visitor_engagements"
    __table_args__ = (
        Index("idx_visitor_engagement_visitor_id", "visitor_id"),
        Index("idx_visitor_engagement_date", "engagement_date"),
        Index("idx_visitor_engagement_score", "engagement_score"),
        UniqueConstraint(
            "visitor_id",
            "engagement_date",
            name="uq_visitor_engagement_daily",
        ),
        {"comment": "Daily visitor engagement metrics"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to visitor",
    )

    engagement_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Date of engagement metrics",
    )

    # ==================== Engagement Metrics ====================
    page_views: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Page views for the day",
    )
    time_on_site_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Total time spent on site",
    )
    searches_performed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of searches",
    )
    hostels_viewed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Hostels viewed",
    )
    favorites_added: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Hostels added to favorites",
    )
    inquiries_sent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Inquiries sent",
    )

    # ==================== Engagement Score ====================
    engagement_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default="0.00",
        index=True,
        comment="Calculated engagement score for the day",
    )

    # ==================== Metadata ====================
    engagement_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional engagement data and patterns",
    )

    # ==================== Relationships ====================
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        foreign_keys=[visitor_id],
    )

    def __repr__(self) -> str:
        return (
            f"<VisitorEngagement(visitor_id={self.visitor_id}, "
            f"date={self.engagement_date}, score={self.engagement_score})>"
        )