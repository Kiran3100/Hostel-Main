# --- File: C:\Hostel-Main\app\models\notification\push_notification.py ---
"""
Push notification model with device and platform management.

Handles push notifications for mobile (iOS/Android) and web platforms.
"""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.notification.notification import Notification
    from app.models.notification.device_token import DeviceToken


class PushNotification(BaseModel, TimestampMixin):
    """
    Push notification details and tracking.
    
    Manages push notifications across platforms (iOS, Android, Web)
    with rich content, actions, and engagement tracking.
    """

    __tablename__ = "push_notifications"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Reference to base notification (one-to-one)
    notification_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Device targeting
    device_token_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("device_tokens.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Specific device token if targeting single device",
    )

    # Content
    title = Column(
        String(100),
        nullable=False,
        comment="Notification title",
    )
    body = Column(
        String(500),
        nullable=False,
        comment="Notification body text",
    )

    # Rich content
    image_url = Column(
        String(500),
        nullable=True,
        comment="Large image URL for rich notification",
    )
    icon = Column(
        String(100),
        nullable=True,
        comment="Small icon identifier",
    )

    # Custom data payload
    data = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Custom data payload sent to app",
    )

    # Actions
    action_url = Column(
        String(500),
        nullable=True,
        comment="Deep link or URL to open on tap",
    )
    actions = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="Action buttons configuration",
    )

    # Badge (iOS)
    badge_count = Column(
        Integer,
        nullable=True,
        comment="Badge count for app icon",
    )
    badge_strategy = Column(
        String(20),
        nullable=True,
        comment="How to update badge (set/increment/decrement)",
    )

    # Sound
    sound = Column(
        String(100),
        nullable=False,
        default="default",
        comment="Notification sound",
    )

    # Priority and delivery
    priority = Column(
        String(20),
        nullable=False,
        default="normal",
        comment="Notification priority (low/normal/high)",
    )
    ttl = Column(
        Integer,
        nullable=False,
        default=86400,
        comment="Time to live in seconds",
    )

    # Collapse/grouping
    collapse_key = Column(
        String(100),
        nullable=True,
        comment="Collapse key for grouping notifications",
    )
    thread_id = Column(
        String(100),
        nullable=True,
        comment="Thread ID for notification grouping",
    )

    # Platform-specific
    android_channel_id = Column(
        String(100),
        nullable=True,
        comment="Android notification channel ID",
    )
    ios_category = Column(
        String(100),
        nullable=True,
        comment="iOS notification category",
    )

    # Delivery tracking
    delivery_status = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Delivery status (sent/delivered/failed/clicked)",
    )
    delivered = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether notification was delivered",
    )

    # Engagement tracking
    tapped = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether notification was tapped",
    )
    tapped_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When notification was tapped",
    )
    action_taken = Column(
        String(100),
        nullable=True,
        comment="Which action button was tapped (if any)",
    )

    # Error tracking
    error_code = Column(
        String(50),
        nullable=True,
        comment="Error code from push provider",
    )
    error_message = Column(
        Text,
        nullable=True,
        comment="Error message",
    )

    # Provider details
    provider_message_id = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Provider's message ID (FCM/APNs)",
    )
    provider_response = Column(
        JSONB,
        nullable=True,
        comment="Raw provider response",
    )

    # Relationships
    notification = relationship(
        "Notification",
        back_populates="push_details",
    )
    device_token = relationship(
        "DeviceToken",
        backref="push_notifications",
    )

    __table_args__ = (
        Index(
            "ix_push_notifications_delivery",
            "delivery_status",
            "delivered",
            "tapped",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PushNotification(id={self.id}, "
            f"delivered={self.delivered}, tapped={self.tapped})>"
        )