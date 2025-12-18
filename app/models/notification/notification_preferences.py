# --- File: C:\Hostel-Main\app\models\notification\notification_preferences.py ---
"""
User notification preferences model.

Manages user-specific notification preferences including channels,
frequency settings, and quiet hours.
"""

from datetime import time
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.user.user import User


class NotificationPreference(BaseModel, TimestampMixin):
    """
    User notification preferences and settings.
    
    Controls notification delivery preferences including channels,
    frequency, quiet hours, and category-specific settings.
    """

    __tablename__ = "notification_preferences"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # User reference
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="User these preferences belong to",
    )

    # Global settings
    notifications_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Master notification toggle",
    )

    # Channel toggles
    email_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Enable email notifications",
    )
    sms_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Enable SMS notifications",
    )
    push_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Enable push notifications",
    )
    in_app_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Enable in-app notifications",
    )

    # Category preferences (global overrides)
    payment_notifications = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Receive payment notifications",
    )
    booking_notifications = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Receive booking notifications",
    )
    complaint_notifications = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Receive complaint notifications",
    )
    announcement_notifications = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Receive announcement notifications",
    )
    maintenance_notifications = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Receive maintenance notifications",
    )
    attendance_notifications = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Receive attendance notifications",
    )
    marketing_notifications = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Receive marketing notifications",
    )

    # Frequency settings
    immediate_notifications = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Send notifications immediately",
    )
    batch_notifications = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Batch notifications instead of immediate",
    )
    batch_interval_hours = Column(
        Integer,
        nullable=False,
        default=4,
        comment="Hours between batched notifications",
    )

    # Digest settings
    daily_digest_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Enable daily digest email",
    )
    daily_digest_time = Column(
        Time,
        nullable=True,
        comment="Time to send daily digest (HH:MM)",
    )
    weekly_digest_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Enable weekly digest email",
    )
    weekly_digest_day = Column(
        String(10),
        nullable=True,
        comment="Day for weekly digest (monday, tuesday, etc.)",
    )
    weekly_digest_time = Column(
        Time,
        nullable=True,
        comment="Time to send weekly digest",
    )

    # Quiet hours
    quiet_hours_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Enable quiet hours",
    )
    quiet_hours_start = Column(
        Time,
        nullable=True,
        comment="Quiet hours start time (HH:MM)",
    )
    quiet_hours_end = Column(
        Time,
        nullable=True,
        comment="Quiet hours end time (HH:MM)",
    )
    quiet_hours_weekdays = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Apply quiet hours on weekdays",
    )
    quiet_hours_weekends = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Apply quiet hours on weekends",
    )
    quiet_hours_allow_urgent = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Allow urgent notifications during quiet hours",
    )

    # Language and timezone
    preferred_language = Column(
        String(5),
        nullable=False,
        default="en",
        comment="Preferred language for notifications",
    )
    timezone = Column(
        String(100),
        nullable=False,
        default="UTC",
        comment="User timezone for scheduling",
    )

    # Relationships
    user = relationship(
        "User",
        backref="notification_preferences",
    )

    channel_preferences = relationship(
        "ChannelPreference",
        back_populates="user_preference",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_notification_preferences_user",
            "user_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationPreference(user_id={self.user_id}, "
            f"enabled={self.notifications_enabled})>"
        )


class ChannelPreference(BaseModel, TimestampMixin):
    """
    Channel-specific notification preferences.
    
    Fine-grained control over notification preferences per channel
    (email, SMS, push) with category-level settings.
    """

    __tablename__ = "channel_preferences"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Reference to user preference
    preference_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("notification_preferences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Channel type
    channel = Column(
        String(20),
        nullable=False,
        comment="Channel type (email, sms, push, in_app)",
    )

    # Channel-specific settings (stored as JSON for flexibility)
    settings = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Channel-specific preference settings",
    )

    # Category preferences for this channel
    category_preferences = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Category-level preferences for this channel",
    )

    # Relationships
    user_preference = relationship(
        "NotificationPreference",
        back_populates="channel_preferences",
    )

    __table_args__ = (
        UniqueConstraint(
            "preference_id",
            "channel",
            name="uq_channel_preference_user_channel",
        ),
        Index(
            "ix_channel_preferences_preference_channel",
            "preference_id",
            "channel",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ChannelPreference(preference_id={self.preference_id}, "
            f"channel={self.channel})>"
        )


class UnsubscribeToken(BaseModel, TimestampMixin):
    """
    Unsubscribe token management.
    
    Secure tokens for one-click unsubscribe functionality
    with audit trail and resubscribe capability.
    """

    __tablename__ = "unsubscribe_tokens"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # User reference
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Token
    token = Column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
        comment="Secure unsubscribe token",
    )

    # Unsubscribe details
    unsubscribe_type = Column(
        String(50),
        nullable=False,
        comment="Type of unsubscription (all, email, sms, marketing, etc.)",
    )
    category = Column(
        String(100),
        nullable=True,
        comment="Specific category to unsubscribe from",
    )

    # Status
    is_used = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether token has been used",
    )
    used_at = Column(
        DateTime,
        nullable=True,
        comment="When token was used",
    )

    # Reason (optional)
    reason = Column(
        String(500),
        nullable=True,
        comment="User-provided reason for unsubscribing",
    )

    # IP tracking
    ip_address = Column(
        String(45),
        nullable=True,
        comment="IP address when unsubscribed",
    )

    # Relationships
    user = relationship(
        "User",
        backref="unsubscribe_tokens",
    )

    __table_args__ = (
        Index(
            "ix_unsubscribe_tokens_user_type",
            "user_id",
            "unsubscribe_type",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<UnsubscribeToken(user_id={self.user_id}, "
            f"type={self.unsubscribe_type}, used={self.is_used})>"
        )