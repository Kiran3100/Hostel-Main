# --- File: app/models/visitor/saved_search.py ---
"""
Saved search model for persistent search criteria and alerts.

This module defines saved search functionality allowing visitors
to save search criteria and receive automated notifications for
new matching hostels.
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

__all__ = [
    "SavedSearch",
    "SavedSearchExecution",
    "SavedSearchMatch",
    "SavedSearchNotification",
]


class SavedSearch(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Saved search criteria with automated monitoring.
    
    Allows visitors to save search parameters and receive
    notifications when new hostels match their criteria.
    """

    __tablename__ = "saved_searches"
    __table_args__ = (
        Index("idx_saved_search_visitor_id", "visitor_id"),
        Index("idx_saved_search_is_active", "is_active"),
        Index("idx_saved_search_next_check", "next_check_at"),
        Index("idx_saved_search_last_checked", "last_checked_at"),
        CheckConstraint(
            "min_price IS NULL OR min_price >= 0",
            name="ck_saved_search_min_price_positive",
        ),
        CheckConstraint(
            "max_price IS NULL OR max_price >= 0",
            name="ck_saved_search_max_price_positive",
        ),
        CheckConstraint(
            "min_price IS NULL OR max_price IS NULL OR max_price >= min_price",
            name="ck_saved_search_price_range",
        ),
        CheckConstraint(
            "notification_frequency IN ('instant', 'daily', 'weekly', 'monthly')",
            name="ck_saved_search_frequency",
        ),
        CheckConstraint(
            "total_matches >= 0",
            name="ck_saved_search_matches_positive",
        ),
        CheckConstraint(
            "new_matches_count >= 0",
            name="ck_saved_search_new_matches_positive",
        ),
        {"comment": "Saved search criteria with automated monitoring"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to visitor",
    )

    # ==================== Search Identification ====================
    search_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="User-defined name for this search",
    )
    search_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description of search criteria",
    )

    # ==================== Basic Search Criteria ====================
    search_query: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Text search query",
    )

    # ==================== Location Criteria ====================
    cities: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Cities to search in",
    )
    areas: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Specific areas/localities",
    )

    # ==================== Room Criteria ====================
    room_types: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Room types to include (single, double, etc.)",
    )
    hostel_types: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Hostel types (boys, girls, co-ed)",
    )

    # ==================== Price Criteria ====================
    min_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Minimum price per month",
    )
    max_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Maximum price per month",
    )

    # ==================== Amenities Criteria ====================
    required_amenities: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Required amenities (must have all)",
    )
    preferred_amenities: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Preferred amenities (nice to have)",
    )

    # ==================== Additional Filters ====================
    min_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        comment="Minimum average rating",
    )
    require_availability: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Only show hostels with availability",
    )

    # ==================== Complete Criteria JSON ====================
    search_criteria: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Complete search criteria including all filters",
    )

    # ==================== Notification Settings ====================
    notify_on_new_matches: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Send notifications for new matches",
    )
    notification_frequency: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="'daily'",
        comment="How often to check and notify (instant/daily/weekly/monthly)",
    )
    notification_channels: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="ARRAY['email']",
        comment="Notification channels (email, sms, push)",
    )

    # ==================== Search Status ====================
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        index=True,
        comment="Whether search is actively monitored",
    )
    is_paused: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Temporarily paused by user",
    )

    # ==================== Execution Tracking ====================
    total_matches: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Current total matching hostels",
    )
    new_matches_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="New matches since last notification",
    )
    last_match_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Match count from previous check",
    )

    # ==================== Timestamps ====================
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When search was last executed",
    )
    next_check_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When next check is scheduled",
    )
    last_notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When last notification was sent",
    )

    # ==================== Performance Metrics ====================
    total_executions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Total number of times search was executed",
    )
    average_execution_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Average execution time in milliseconds",
    )

    # ==================== User Engagement ====================
    times_edited: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of times search was edited",
    )
    last_edited_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When search was last edited",
    )

    # ==================== Metadata ====================
    search_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional search configuration and analytics",
    )

    # ==================== Relationships ====================
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        back_populates="saved_searches",
    )

    executions: Mapped[List["SavedSearchExecution"]] = relationship(
        "SavedSearchExecution",
        back_populates="saved_search",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    matches: Mapped[List["SavedSearchMatch"]] = relationship(
        "SavedSearchMatch",
        back_populates="saved_search",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    notifications: Mapped[List["SavedSearchNotification"]] = relationship(
        "SavedSearchNotification",
        back_populates="saved_search",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # ==================== Properties ====================
    @property
    def has_new_matches(self) -> bool:
        """Check if there are new matches."""
        return self.new_matches_count > 0

    @property
    def should_execute(self) -> bool:
        """Check if search should be executed now."""
        if not self.is_active or self.is_paused:
            return False

        if self.next_check_at is None:
            return True

        return datetime.utcnow() >= self.next_check_at

    @property
    def should_send_notification(self) -> bool:
        """Check if notification should be sent."""
        if not self.notify_on_new_matches or not self.has_new_matches:
            return False

        if self.notification_frequency == "instant":
            return True

        if self.last_notification_sent_at is None:
            return True

        now = datetime.utcnow()
        time_since_last = now - self.last_notification_sent_at

        if self.notification_frequency == "daily":
            return time_since_last.days >= 1
        elif self.notification_frequency == "weekly":
            return time_since_last.days >= 7
        elif self.notification_frequency == "monthly":
            return time_since_last.days >= 30

        return False

    @property
    def criteria_summary(self) -> dict:
        """Get human-readable criteria summary."""
        summary = {}

        if self.cities:
            summary["cities"] = ", ".join(self.cities)
        if self.room_types:
            summary["room_types"] = ", ".join(self.room_types)
        if self.min_price or self.max_price:
            price_range = []
            if self.min_price:
                price_range.append(f"₹{self.min_price:,.0f}")
            if self.max_price:
                price_range.append(f"₹{self.max_price:,.0f}")
            summary["price_range"] = " - ".join(price_range)
        if self.required_amenities:
            summary["required_amenities"] = ", ".join(self.required_amenities)

        return summary

    def __repr__(self) -> str:
        return (
            f"<SavedSearch(id={self.id}, visitor_id={self.visitor_id}, "
            f"name='{self.search_name}', matches={self.total_matches})>"
        )


class SavedSearchExecution(UUIDMixin, TimestampModel):
    """
    Execution log for saved searches.
    
    Tracks each execution of a saved search with performance
    metrics and result statistics.
    """

    __tablename__ = "saved_search_executions"
    __table_args__ = (
        Index("idx_saved_search_exec_search_id", "saved_search_id"),
        Index("idx_saved_search_exec_executed_at", "executed_at"),
        Index("idx_saved_search_exec_success", "execution_successful"),
        CheckConstraint(
            "results_count >= 0",
            name="ck_saved_search_exec_results_positive",
        ),
        CheckConstraint(
            "execution_time_ms >= 0",
            name="ck_saved_search_exec_time_positive",
        ),
        {"comment": "Saved search execution history and performance"},
    )

    # ==================== Core Fields ====================
    saved_search_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("saved_searches.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to saved search",
    )

    # ==================== Execution Details ====================
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When search was executed",
    )
    execution_successful: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        index=True,
        comment="Whether execution completed successfully",
    )
    execution_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if execution failed",
    )

    # ==================== Performance Metrics ====================
    execution_time_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Execution time in milliseconds",
    )
    database_query_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Database query time in milliseconds",
    )

    # ==================== Results ====================
    results_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of matching hostels found",
    )
    new_results_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of new matches since last execution",
    )
    removed_results_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of matches that are no longer matching",
    )

    # ==================== Result Data ====================
    result_hostel_ids: Mapped[List[UUID]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="List of matching hostel IDs",
    )
    new_hostel_ids: Mapped[List[UUID]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="List of new matching hostel IDs",
    )

    # ==================== Criteria Snapshot ====================
    criteria_used: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Snapshot of search criteria used for this execution",
    )

    # ==================== Metadata ====================
    execution_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional execution data and diagnostics",
    )

    # ==================== Relationships ====================
    saved_search: Mapped["SavedSearch"] = relationship(
        "SavedSearch",
        back_populates="executions",
    )

    # ==================== Properties ====================
    @property
    def has_new_results(self) -> bool:
        """Check if execution found new results."""
        return self.new_results_count > 0

    @property
    def performance_rating(self) -> str:
        """Rate execution performance."""
        if self.execution_time_ms < 100:
            return "excellent"
        elif self.execution_time_ms < 500:
            return "good"
        elif self.execution_time_ms < 1000:
            return "acceptable"
        else:
            return "slow"

    def __repr__(self) -> str:
        return (
            f"<SavedSearchExecution(id={self.id}, search_id={self.saved_search_id}, "
            f"results={self.results_count}, time={self.execution_time_ms}ms)>"
        )


class SavedSearchMatch(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Individual hostel matches for saved searches.
    
    Tracks which hostels match which saved searches with
    match scoring and temporal tracking.
    """

    __tablename__ = "saved_search_matches"
    __table_args__ = (
        Index("idx_saved_search_match_search_id", "saved_search_id"),
        Index("idx_saved_search_match_hostel_id", "hostel_id"),
        Index("idx_saved_search_match_first_matched", "first_matched_at"),
        Index("idx_saved_search_match_is_new", "is_new"),
        UniqueConstraint(
            "saved_search_id",
            "hostel_id",
            name="uq_saved_search_match",
        ),
        CheckConstraint(
            "match_score >= 0 AND match_score <= 100",
            name="ck_saved_search_match_score_range",
        ),
        {"comment": "Hostel matches for saved searches"},
    )

    # ==================== Core Fields ====================
    saved_search_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("saved_searches.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to saved search",
    )
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to matching hostel",
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

    # ==================== Match Scoring ====================
    match_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default="100.00",
        comment="Match quality score (0-100)",
    )
    match_criteria_met: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Which criteria were met",
    )

    # ==================== Match Status ====================
    is_new: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        index=True,
        comment="Whether this is a new match",
    )
    is_notified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether visitor was notified about this match",
    )

    # ==================== Timestamps ====================
    first_matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When hostel first matched criteria",
    )
    last_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When match was last verified",
    )
    notified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When visitor was notified",
    )

    # ==================== User Engagement ====================
    was_viewed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether visitor viewed this match",
    )
    viewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When match was viewed",
    )

    # ==================== Metadata ====================
    match_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional match data and context",
    )

    # ==================== Relationships ====================
    saved_search: Mapped["SavedSearch"] = relationship(
        "SavedSearch",
        back_populates="matches",
    )
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        foreign_keys=[hostel_id],
    )

    # ==================== Properties ====================
    @property
    def is_excellent_match(self) -> bool:
        """Check if match score is excellent (>= 90)."""
        return self.match_score >= Decimal("90")

    @property
    def days_since_matched(self) -> int:
        """Calculate days since first matched."""
        return (datetime.utcnow() - self.first_matched_at).days

    def __repr__(self) -> str:
        return (
            f"<SavedSearchMatch(id={self.id}, search_id={self.saved_search_id}, "
            f"hostel_id={self.hostel_id}, score={self.match_score})>"
        )


class SavedSearchNotification(UUIDMixin, TimestampModel):
    """
    Notification log for saved search alerts.
    
    Tracks all notifications sent for saved search matches.
    """

    __tablename__ = "saved_search_notifications"
    __table_args__ = (
        Index("idx_saved_search_notif_search_id", "saved_search_id"),
        Index("idx_saved_search_notif_sent_at", "sent_at"),
        Index("idx_saved_search_notif_status", "delivery_status"),
        CheckConstraint(
            "new_matches_count >= 0",
            name="ck_saved_search_notif_matches_positive",
        ),
        {"comment": "Notification tracking for saved searches"},
    )

    # ==================== Core Fields ====================
    saved_search_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("saved_searches.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to saved search",
    )

    # ==================== Notification Content ====================
    notification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of notification (new_matches, price_drop, etc.)",
    )
    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Notification subject/title",
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Notification message body",
    )

    # ==================== Match Information ====================
    new_matches_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of new matches included",
    )
    match_hostel_ids: Mapped[List[UUID]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="List of matching hostel IDs in this notification",
    )

    # ==================== Delivery Details ====================
    delivery_channels: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        comment="Channels used (email, sms, push)",
    )
    delivery_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="'pending'",
        index=True,
        comment="Delivery status (pending, sent, delivered, failed)",
    )

    # ==================== Timestamps ====================
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When notification was sent",
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When notification was delivered",
    )
    opened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When notification was opened/read",
    )

    # ==================== Engagement ====================
    was_opened: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether notification was opened",
    )
    links_clicked: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of links clicked in notification",
    )

    # ==================== Metadata ====================
    notification_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional notification data",
    )

    # ==================== Relationships ====================
    saved_search: Mapped["SavedSearch"] = relationship(
        "SavedSearch",
        back_populates="notifications",
    )

    # ==================== Properties ====================
    @property
    def is_successful(self) -> bool:
        """Check if notification was successfully delivered."""
        return self.delivery_status in ["sent", "delivered"]

    @property
    def engagement_rate(self) -> Decimal:
        """Calculate engagement rate."""
        if not self.was_opened:
            return Decimal("0.00")
        if self.new_matches_count == 0:
            return Decimal("0.00")
        return Decimal(
            (self.links_clicked / self.new_matches_count) * 100
        ).quantize(Decimal("0.01"))

    def __repr__(self) -> str:
        return (
            f"<SavedSearchNotification(id={self.id}, search_id={self.saved_search_id}, "
            f"matches={self.new_matches_count}, status={self.delivery_status})>"
        )