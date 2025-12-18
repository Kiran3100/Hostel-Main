# --- File: app/models/visitor/visitor_dashboard.py ---
"""
Visitor dashboard models for analytics and insights.

This module defines models for visitor dashboard components including
saved hostels summary, recent activity, recommendations, and alerts.
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
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.visitor.visitor import Visitor
    from app.models.hostel.hostel import Hostel

__all__ = [
    "RecentSearch",
    "RecentlyViewedHostel",
    "RecommendedHostel",
    "PriceDropAlert",
    "AvailabilityAlert",
    "VisitorActivity",
]


class RecentSearch(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Recent search queries for quick access and analytics.
    
    Stores visitor's recent searches with filters and results
    for easy re-execution and pattern analysis.
    """

    __tablename__ = "recent_searches"
    __table_args__ = (
        Index("idx_recent_search_visitor_id", "visitor_id"),
        Index("idx_recent_search_searched_at", "searched_at"),
        Index("idx_recent_search_results_count", "results_count"),
        CheckConstraint(
            "results_count >= 0",
            name="ck_recent_search_results_positive",
        ),
        {"comment": "Visitor's recent search history"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to visitor",
    )

    # ==================== Search Details ====================
    search_query: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Search query text (if any)",
    )

    # ==================== Filters Applied ====================
    filters_applied: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Filters applied in this search",
    )

    # ==================== Search Criteria ====================
    cities: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Cities searched",
    )
    min_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Minimum price filter",
    )
    max_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Maximum price filter",
    )
    room_types: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Room types filtered",
    )
    amenities: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Amenities filtered",
    )

    # ==================== Results ====================
    results_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of results found",
    )
    result_hostel_ids: Mapped[List[UUID]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="List of hostel IDs in results",
    )

    # ==================== Timing ====================
    searched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When search was performed",
    )

    # ==================== Re-execution ====================
    times_re_executed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of times this search was re-run",
    )
    last_re_executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When search was last re-executed",
    )

    # ==================== Metadata ====================
    search_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional search data and analytics",
    )

    # ==================== Relationships ====================
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        foreign_keys=[visitor_id],
    )

    # ==================== Properties ====================
    @property
    def filters_count(self) -> int:
        """Count number of filters applied."""
        return len(self.filters_applied)

    @property
    def is_popular_search(self) -> bool:
        """Check if search has been re-executed multiple times."""
        return self.times_re_executed >= 3

    @property
    def has_results(self) -> bool:
        """Check if search returned results."""
        return self.results_count > 0

    def __repr__(self) -> str:
        return (
            f"<RecentSearch(id={self.id}, visitor_id={self.visitor_id}, "
            f"results={self.results_count})>"
        )


class RecentlyViewedHostel(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Recently viewed hostels for quick access.
    
    Tracks hostel views with frequency and recency for
    personalized recommendations and quick navigation.
    """

    __tablename__ = "recently_viewed_hostels"
    __table_args__ = (
        Index("idx_recently_viewed_visitor_id", "visitor_id"),
        Index("idx_recently_viewed_hostel_id", "hostel_id"),
        Index("idx_recently_viewed_viewed_at", "last_viewed_at"),
        Index("idx_recently_viewed_view_count", "view_count"),
        UniqueConstraint(
            "visitor_id",
            "hostel_id",
            name="uq_recently_viewed",
        ),
        CheckConstraint(
            "view_count > 0",
            name="ck_recently_viewed_count_positive",
        ),
        CheckConstraint(
            "time_spent_seconds >= 0",
            name="ck_recently_viewed_time_positive",
        ),
        {"comment": "Recently viewed hostels tracking"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to visitor",
    )
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to hostel",
    )

    # ==================== Cached Hostel Data ====================
    hostel_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Cached hostel name",
    )
    hostel_slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Cached hostel slug",
    )
    hostel_city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Cached hostel city",
    )
    starting_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Cached starting price",
    )
    average_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        nullable=False,
        server_default="0.00",
        comment="Cached average rating",
    )
    cover_image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Cached cover image URL",
    )

    # ==================== View Tracking ====================
    view_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        comment="Number of times hostel was viewed",
    )
    first_viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When hostel was first viewed",
    )
    last_viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When hostel was last viewed",
    )

    # ==================== Engagement Metrics ====================
    time_spent_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Total time spent viewing this hostel",
    )
    sections_viewed: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Hostel sections viewed (amenities, reviews, etc.)",
    )

    # ==================== Actions Taken ====================
    added_to_favorites: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether added to favorites",
    )
    inquiry_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether inquiry was sent",
    )
    booking_initiated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether booking was initiated",
    )

    # ==================== Metadata ====================
    view_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional view data and behavior",
    )

    # ==================== Relationships ====================
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        foreign_keys=[visitor_id],
    )
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        foreign_keys=[hostel_id],
    )

    # ==================== Properties ====================
    @property
    def is_highly_viewed(self) -> bool:
        """Check if hostel has been viewed multiple times."""
        return self.view_count >= 3

    @property
    def average_time_per_view(self) -> int:
        """Calculate average time spent per view."""
        if self.view_count == 0:
            return 0
        return self.time_spent_seconds // self.view_count

    @property
    def is_high_engagement(self) -> bool:
        """Check if visitor shows high engagement with this hostel."""
        return (
            self.view_count >= 2
            and self.time_spent_seconds >= 120
            and len(self.sections_viewed) >= 3
        )

    def __repr__(self) -> str:
        return (
            f"<RecentlyViewedHostel(id={self.id}, visitor_id={self.visitor_id}, "
            f"hostel_id={self.hostel_id}, views={self.view_count})>"
        )


class RecommendedHostel(UUIDMixin, TimestampModel):
    """
    Personalized hostel recommendations for visitors.
    
    AI/ML-driven recommendations based on preferences,
    behavior, and similar visitor patterns.
    """

    __tablename__ = "recommended_hostels"
    __table_args__ = (
        Index("idx_recommended_hostel_visitor_id", "visitor_id"),
        Index("idx_recommended_hostel_hostel_id", "hostel_id"),
        Index("idx_recommended_hostel_score", "match_score"),
        Index("idx_recommended_hostel_generated_at", "generated_at"),
        UniqueConstraint(
            "visitor_id",
            "hostel_id",
            "generated_at",
            name="uq_recommended_hostel_daily",
        ),
        CheckConstraint(
            "match_score >= 0 AND match_score <= 100",
            name="ck_recommended_hostel_score_range",
        ),
        {"comment": "Personalized hostel recommendations"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to visitor",
    )
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to recommended hostel",
    )

    # ==================== Cached Hostel Data ====================
    hostel_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Cached hostel name",
    )
    hostel_city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Cached hostel city",
    )
    starting_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Cached starting price",
    )
    average_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        nullable=False,
        comment="Cached average rating",
    )
    available_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Cached available beds",
    )
    cover_image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Cached cover image URL",
    )

    # ==================== Recommendation Scoring ====================
    match_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        index=True,
        comment="Match score (0-100) based on preferences",
    )
    recommendation_rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Rank among recommendations (1 = best match)",
    )

    # ==================== Match Reasons ====================
    match_reasons: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        comment="Reasons why this hostel is recommended",
    )
    matching_criteria: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Detailed matching criteria breakdown",
    )

    # ==================== Recommendation Type ====================
    recommendation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of recommendation (preference_based, behavioral, collaborative)",
    )
    recommendation_algorithm: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Algorithm used for recommendation",
    )

    # ==================== Timing ====================
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When recommendation was generated",
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When recommendation expires",
    )

    # ==================== Engagement Tracking ====================
    was_viewed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether recommendation was viewed",
    )
    was_clicked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether recommendation was clicked",
    )
    was_converted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether resulted in booking",
    )
    viewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When recommendation was viewed",
    )

    # ==================== Metadata ====================
    recommendation_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional recommendation data and ML features",
    )

    # ==================== Relationships ====================
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        foreign_keys=[visitor_id],
    )
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        foreign_keys=[hostel_id],
    )

    # ==================== Properties ====================
    @property
    def is_excellent_match(self) -> bool:
        """Check if this is an excellent match (score >= 80)."""
        return self.match_score >= Decimal("80")

    @property
    def is_active(self) -> bool:
        """Check if recommendation is still active."""
        if self.expires_at is None:
            return True
        return datetime.utcnow() < self.expires_at

    @property
    def engagement_level(self) -> str:
        """Get engagement level."""
        if self.was_converted:
            return "converted"
        elif self.was_clicked:
            return "clicked"
        elif self.was_viewed:
            return "viewed"
        else:
            return "not_engaged"

    def __repr__(self) -> str:
        return (
            f"<RecommendedHostel(id={self.id}, visitor_id={self.visitor_id}, "
            f"hostel_id={self.hostel_id}, score={self.match_score})>"
        )


class PriceDropAlert(UUIDMixin, TimestampModel):
    """
    Price drop alerts for saved hostels.
    
    Tracks price reductions on favorite hostels and
    manages alert delivery to visitors.
    """

    __tablename__ = "price_drop_alerts"
    __table_args__ = (
        Index("idx_price_drop_alert_visitor_id", "visitor_id"),
        Index("idx_price_drop_alert_hostel_id", "hostel_id"),
        Index("idx_price_drop_alert_created_at", "created_at"),
        Index("idx_price_drop_alert_is_read", "is_read"),
        CheckConstraint(
            "previous_price >= 0",
            name="ck_price_drop_previous_positive",
        ),
        CheckConstraint(
            "new_price >= 0",
            name="ck_price_drop_new_positive",
        ),
        CheckConstraint(
            "discount_percentage >= 0 AND discount_percentage <= 100",
            name="ck_price_drop_percentage_range",
        ),
        {"comment": "Price drop alerts for favorite hostels"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to visitor",
    )
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to hostel",
    )
    favorite_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitor_favorites.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to favorite record",
    )

    # ==================== Cached Hostel Data ====================
    hostel_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Cached hostel name",
    )
    hostel_slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Cached hostel slug",
    )

    # ==================== Price Information ====================
    previous_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Price before reduction",
    )
    new_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="New reduced price",
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Absolute discount amount",
    )
    discount_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Discount percentage",
    )

    # ==================== Alert Status ====================
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        index=True,
        comment="Whether alert has been read",
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When alert was read",
    )

    # ==================== Notification Delivery ====================
    email_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether email notification was sent",
    )
    sms_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether SMS notification was sent",
    )
    push_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether push notification was sent",
    )
    notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When notification was sent",
    )

    # ==================== Metadata ====================
    alert_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional alert data",
    )

    # ==================== Relationships ====================
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        foreign_keys=[visitor_id],
    )
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        foreign_keys=[hostel_id],
    )

    # ==================== Properties ====================
    @property
    def savings_amount(self) -> Decimal:
        """Get absolute savings amount."""
        return self.discount_amount

    @property
    def is_significant_drop(self) -> bool:
        """Check if price drop is significant (>= 10%)."""
        return self.discount_percentage >= Decimal("10")

    def __repr__(self) -> str:
        return (
            f"<PriceDropAlert(id={self.id}, visitor_id={self.visitor_id}, "
            f"hostel_id={self.hostel_id}, discount={self.discount_percentage}%)>"
        )


class AvailabilityAlert(UUIDMixin, TimestampModel):
    """
    Availability alerts for previously full hostels.
    
    Notifies visitors when saved hostels have new availability.
    """

    __tablename__ = "availability_alerts"
    __table_args__ = (
        Index("idx_availability_alert_visitor_id", "visitor_id"),
        Index("idx_availability_alert_hostel_id", "hostel_id"),
        Index("idx_availability_alert_created_at", "created_at"),
        Index("idx_availability_alert_is_read", "is_read"),
        CheckConstraint(
            "available_beds > 0",
            name="ck_availability_alert_beds_positive",
        ),
        {"comment": "Availability alerts for favorite hostels"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to visitor",
    )
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to hostel",
    )
    favorite_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitor_favorites.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to favorite record",
    )

    # ==================== Cached Hostel Data ====================
    hostel_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Cached hostel name",
    )
    hostel_slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Cached hostel slug",
    )

    # ==================== Availability Information ====================
    room_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Room type that became available",
    )
    available_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of beds now available",
    )

    # ==================== Alert Message ====================
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Alert message text",
    )

    # ==================== Alert Status ====================
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        index=True,
        comment="Whether alert has been read",
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When alert was read",
    )

    # ==================== Notification Delivery ====================
    email_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether email notification was sent",
    )
    sms_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether SMS notification was sent",
    )
    push_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether push notification was sent",
    )
    notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When notification was sent",
    )

    # ==================== Metadata ====================
    alert_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional alert data",
    )

    # ==================== Relationships ====================
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        foreign_keys=[visitor_id],
    )
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        foreign_keys=[hostel_id],
    )

    def __repr__(self) -> str:
        return (
            f"<AvailabilityAlert(id={self.id}, visitor_id={self.visitor_id}, "
            f"hostel_id={self.hostel_id}, beds={self.available_beds})>"
        )


class VisitorActivity(UUIDMixin, TimestampModel):
    """
    Comprehensive visitor activity log.
    
    Tracks all visitor actions for analytics and personalization.
    """

    __tablename__ = "visitor_activities"
    __table_args__ = (
        Index("idx_visitor_activity_visitor_id", "visitor_id"),
        Index("idx_visitor_activity_type", "activity_type"),
        Index("idx_visitor_activity_occurred_at", "occurred_at"),
        Index("idx_visitor_activity_entity", "entity_type", "entity_id"),
        {"comment": "Comprehensive visitor activity tracking"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to visitor",
    )

    # ==================== Activity Details ====================
    activity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of activity (search, view, favorite, inquiry, booking)",
    )
    activity_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Activity category (engagement, conversion, preference)",
    )
    activity_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable activity description",
    )

    # ==================== Entity Reference ====================
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Type of entity (hostel, search, booking)",
    )
    entity_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="ID of related entity",
    )

    # ==================== Timing ====================
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When activity occurred",
    )

    # ==================== Session Context ====================
    session_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="Session in which activity occurred",
    )
    device_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Device type",
    )

    # ==================== Activity Data ====================
    activity_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Detailed activity data and context",
    )

    # ==================== Metadata ====================
    activity_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional activity metadata",
    )

    # ==================== Relationships ====================
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        foreign_keys=[visitor_id],
    )

    def __repr__(self) -> str:
        return (
            f"<VisitorActivity(id={self.id}, visitor_id={self.visitor_id}, "
            f"type={self.activity_type})>"
        )