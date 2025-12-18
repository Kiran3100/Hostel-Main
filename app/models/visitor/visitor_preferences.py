# --- File: app/models/visitor/visitor_preferences.py ---
"""
Visitor preferences model for detailed preference management.

This module defines visitor preferences including search criteria,
notification settings, and saved search configurations.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin
from app.models.base.enums import (
    DietaryPreference,
    HostelType,
    RoomType,
)

if TYPE_CHECKING:
    from app.models.visitor.visitor import Visitor

__all__ = [
    "VisitorPreferences",
    "SearchPreferences",
    "NotificationPreferences",
]


class VisitorPreferences(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Comprehensive visitor preferences for personalization.
    
    Stores detailed preferences including room requirements,
    budget, location, amenities, and dietary preferences.
    """

    __tablename__ = "visitor_preferences"
    __table_args__ = (
        Index("idx_visitor_preferences_visitor_id", "visitor_id"),
        UniqueConstraint("visitor_id", name="uq_visitor_preferences_visitor"),
        CheckConstraint(
            "budget_min IS NULL OR budget_min >= 0",
            name="ck_visitor_pref_budget_min_positive",
        ),
        CheckConstraint(
            "budget_max IS NULL OR budget_max >= 0",
            name="ck_visitor_pref_budget_max_positive",
        ),
        CheckConstraint(
            "budget_min IS NULL OR budget_max IS NULL OR budget_max >= budget_min",
            name="ck_visitor_pref_budget_range",
        ),
        CheckConstraint(
            "max_distance_from_work_km IS NULL OR "
            "(max_distance_from_work_km >= 0 AND max_distance_from_work_km <= 50)",
            name="ck_visitor_pref_distance_range",
        ),
        CheckConstraint(
            "preferred_lease_duration_months IS NULL OR "
            "(preferred_lease_duration_months >= 1 AND preferred_lease_duration_months <= 24)",
            name="ck_visitor_pref_lease_duration_range",
        ),
        {"comment": "Detailed visitor preferences for search and matching"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="Reference to visitor (one-to-one)",
    )

    # ==================== Room Preferences ====================
    preferred_room_type: Mapped[Optional[RoomType]] = mapped_column(
        nullable=True,
        comment="Preferred room type (single, double, dormitory, etc.)",
    )
    preferred_hostel_type: Mapped[Optional[HostelType]] = mapped_column(
        nullable=True,
        comment="Preferred hostel type (boys, girls, co-ed)",
    )

    # ==================== Budget Constraints ====================
    budget_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Minimum monthly budget in local currency",
    )
    budget_max: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Maximum monthly budget in local currency",
    )

    # ==================== Location Preferences ====================
    preferred_cities: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="List of preferred cities",
    )
    preferred_areas: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Preferred areas/localities within cities",
    )
    max_distance_from_work_km: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Maximum acceptable distance from workplace in km (0-50)",
    )

    # ==================== Amenities ====================
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
        comment="Nice-to-have amenities (preferences)",
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
        comment="Dietary preference (vegetarian, non-vegetarian, vegan, jain)",
    )

    # ==================== Move-in Details ====================
    earliest_move_in_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
        comment="Earliest date willing to move in",
    )
    preferred_lease_duration_months: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Preferred lease duration in months (1-24)",
    )

    # ==================== Notification Preferences ====================
    email_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Enable email notifications",
    )
    sms_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Enable SMS notifications",
    )
    push_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Enable push notifications",
    )

    # ==================== Specific Notification Types ====================
    notify_on_price_drop: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Notify when saved hostel reduces price",
    )
    notify_on_availability: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Notify when saved hostel has new availability",
    )
    notify_on_new_listings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Notify about new hostels matching preferences",
    )

    # ==================== Preference Metadata ====================
    preference_strength: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Strength/importance of each preference (for matching)",
    )
    last_updated_fields: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Recently updated preference fields",
    )

    # ==================== Metadata ====================
    preferences_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional preferences and settings",
    )

    # ==================== Relationships ====================
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        back_populates="preferences",
    )

    # ==================== Properties ====================
    @property
    def has_budget_preference(self) -> bool:
        """Check if budget preferences are set."""
        return self.budget_min is not None or self.budget_max is not None

    @property
    def has_location_preference(self) -> bool:
        """Check if location preferences are set."""
        return len(self.preferred_cities) > 0 or len(self.preferred_areas) > 0

    @property
    def notification_channels_count(self) -> int:
        """Count enabled notification channels."""
        return sum(
            [
                self.email_notifications,
                self.sms_notifications,
                self.push_notifications,
            ]
        )

    @property
    def total_required_amenities(self) -> int:
        """Count total required amenities."""
        return len(self.required_amenities)

    @property
    def total_preferred_amenities(self) -> int:
        """Count total preferred amenities."""
        return len(self.preferred_amenities)

    def __repr__(self) -> str:
        return f"<VisitorPreferences(visitor_id={self.visitor_id})>"


class SearchPreferences(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Saved search preferences with alert configuration.
    
    Allows visitors to save specific search criteria and receive
    notifications when new matches are found.
    """

    __tablename__ = "search_preferences"
    __table_args__ = (
        Index("idx_search_preferences_visitor_id", "visitor_id"),
        Index("idx_search_preferences_active", "is_active"),
        Index("idx_search_preferences_last_checked", "last_checked_at"),
        CheckConstraint(
            "min_price IS NULL OR min_price >= 0",
            name="ck_search_pref_min_price_positive",
        ),
        CheckConstraint(
            "max_price IS NULL OR max_price >= 0",
            name="ck_search_pref_max_price_positive",
        ),
        CheckConstraint(
            "min_price IS NULL OR max_price IS NULL OR max_price >= min_price",
            name="ck_search_pref_price_range",
        ),
        CheckConstraint(
            "notification_frequency IN ('instant', 'daily', 'weekly')",
            name="ck_search_pref_notification_frequency",
        ),
        {"comment": "Saved search preferences with notifications"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to visitor",
    )

    search_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Descriptive name for this saved search",
    )

    # ==================== Search Criteria ====================
    cities: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Cities to search in",
    )
    room_types: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Room types to include",
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
    amenities: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
        comment="Required amenities",
    )

    # ==================== Search Criteria JSON ====================
    search_criteria: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Complete search criteria as JSON",
    )

    # ==================== Alert Settings ====================
    notify_on_new_matches: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Send notifications when new hostels match this search",
    )
    notification_frequency: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="'daily'",
        comment="Notification frequency: instant, daily, or weekly",
    )

    # ==================== Statistics ====================
    total_matches: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Current number of hostels matching this search",
    )
    new_matches_since_last_check: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of new matches since last notification",
    )

    # ==================== Status ====================
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        index=True,
        comment="Whether search is actively monitored",
    )

    # ==================== Timestamps ====================
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When this search was last executed",
    )
    last_notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When last notification was sent",
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
        foreign_keys=[visitor_id],
    )

    # ==================== Properties ====================
    @property
    def has_new_matches(self) -> bool:
        """Check if there are new matches."""
        return self.new_matches_since_last_check > 0

    @property
    def should_send_notification(self) -> bool:
        """Check if notification should be sent based on frequency."""
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

        return False

    def __repr__(self) -> str:
        return (
            f"<SearchPreferences(id={self.id}, visitor_id={self.visitor_id}, "
            f"name='{self.search_name}')>"
        )


class NotificationPreferences(UUIDMixin, TimestampModel):
    """
    Detailed notification preferences and settings.
    
    Granular control over notification channels, timing,
    and content preferences.
    """

    __tablename__ = "notification_preferences"
    __table_args__ = (
        Index("idx_notification_pref_visitor_id", "visitor_id"),
        UniqueConstraint("visitor_id", name="uq_notification_pref_visitor"),
        {"comment": "Granular notification preferences and controls"},
    )

    # ==================== Core Fields ====================
    visitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="Reference to visitor (one-to-one)",
    )

    # ==================== Channel Preferences ====================
    email_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Master email notification toggle",
    )
    sms_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Master SMS notification toggle",
    )
    push_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Master push notification toggle",
    )
    in_app_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Master in-app notification toggle",
    )

    # ==================== Notification Types ====================
    # Price Alerts
    price_drop_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Email for price drops",
    )
    price_drop_sms: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="SMS for price drops",
    )
    price_drop_push: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Push for price drops",
    )

    # Availability Alerts
    availability_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Email for new availability",
    )
    availability_sms: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="SMS for new availability",
    )
    availability_push: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Push for new availability",
    )

    # New Listings
    new_listing_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Email for new matching listings",
    )
    new_listing_sms: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="SMS for new listings",
    )
    new_listing_push: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Push for new listings",
    )

    # Booking Updates
    booking_confirmation_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Email for booking confirmations",
    )
    booking_confirmation_sms: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="SMS for booking confirmations",
    )
    booking_reminder_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Email for booking reminders",
    )

    # Marketing Communications
    promotional_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Promotional emails",
    )
    newsletter_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Newsletter subscriptions",
    )

    # ==================== Timing Preferences ====================
    quiet_hours_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Enable quiet hours (no notifications)",
    )
    quiet_hours_start: Mapped[Optional[str]] = mapped_column(
        String(5),
        nullable=True,
        comment="Quiet hours start time (HH:MM format)",
    )
    quiet_hours_end: Mapped[Optional[str]] = mapped_column(
        String(5),
        nullable=True,
        comment="Quiet hours end time (HH:MM format)",
    )

    # ==================== Frequency Controls ====================
    digest_mode: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Batch notifications into daily digest",
    )
    max_notifications_per_day: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum notifications per day (null = unlimited)",
    )

    # ==================== Metadata ====================
    notification_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional notification settings and preferences",
    )

    # ==================== Relationships ====================
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        foreign_keys=[visitor_id],
    )

    # ==================== Properties ====================
    @property
    def any_channel_enabled(self) -> bool:
        """Check if any notification channel is enabled."""
        return any(
            [
                self.email_enabled,
                self.sms_enabled,
                self.push_enabled,
                self.in_app_enabled,
            ]
        )

    @property
    def total_enabled_channels(self) -> int:
        """Count total enabled channels."""
        return sum(
            [
                self.email_enabled,
                self.sms_enabled,
                self.push_enabled,
                self.in_app_enabled,
            ]
        )

    def __repr__(self) -> str:
        return f"<NotificationPreferences(visitor_id={self.visitor_id})>"