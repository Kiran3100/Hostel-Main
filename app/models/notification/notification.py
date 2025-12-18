# --- File: C:\Hostel-Main\app\models\notification\notification.py ---
"""
Core notification model.

Handles all notification types (email, SMS, push) with unified interface.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin, SoftDeleteMixin
from app.schemas.common.enums import (
    NotificationStatus,
    NotificationType,
    Priority,
)

if TYPE_CHECKING:
    from app.models.notification.email_notification import EmailNotification
    from app.models.notification.sms_notification import SMSNotification
    from app.models.notification.push_notification import PushNotification
    from app.models.notification.notification_template import NotificationTemplate
    from app.models.user.user import User
    from app.models.hostel.hostel import Hostel


class Notification(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Core notification model supporting all notification channels.
    
    This is the unified notification system that handles email, SMS,
    push notifications, and in-app notifications with common tracking
    and lifecycle management.
    """

    __tablename__ = "notifications"

    # Primary key
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )

    # Recipient information (at least one must be set)
    recipient_user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Recipient user ID for user-based routing",
    )
    recipient_email = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Recipient email address for email notifications",
    )
    recipient_phone = Column(
        String(20),
        nullable=True,
        index=True,
        comment="Recipient phone number for SMS notifications",
    )

    # Notification channel and type
    notification_type = Column(
        Enum(NotificationType),
        nullable=False,
        index=True,
        comment="Notification delivery channel (email/sms/push/in_app)",
    )

    # Template support
    template_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("notification_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Template used for this notification",
    )
    template_code = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Template code for quick lookups",
    )

    # Content
    subject = Column(
        String(255),
        nullable=True,
        comment="Notification subject/title (required for email and push)",
    )
    message_body = Column(
        Text,
        nullable=False,
        comment="Notification message content",
    )

    # Priority and scheduling
    priority = Column(
        Enum(Priority),
        nullable=False,
        default=Priority.MEDIUM,
        index=True,
        comment="Notification delivery priority",
    )
    scheduled_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Scheduled delivery time (null for immediate)",
    )

    # Status tracking
    status = Column(
        Enum(NotificationStatus),
        nullable=False,
        default=NotificationStatus.PENDING,
        index=True,
        comment="Current notification status",
    )

    # Delivery tracking
    sent_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When notification was actually sent",
    )
    delivered_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When notification was delivered to recipient",
    )
    failed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When delivery failed",
    )

    # Error handling
    failure_reason = Column(
        Text,
        nullable=True,
        comment="Reason for delivery failure",
    )
    retry_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of retry attempts",
    )
    max_retries = Column(
        Integer,
        nullable=False,
        default=3,
        comment="Maximum allowed retries",
    )

    # Engagement tracking
    read_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When notification was read (in-app/push)",
    )
    clicked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When any link in notification was clicked",
    )

    # Metadata and context
    metadata = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Additional notification context and data",
    )

    # Related entities
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Associated hostel for hostel-specific notifications",
    )

    # Relationships
    recipient_user = relationship(
        "User",
        foreign_keys=[recipient_user_id],
        backref="received_notifications",
    )
    template = relationship(
        "NotificationTemplate",
        foreign_keys=[template_id],
        backref="sent_notifications",
    )
    hostel = relationship(
        "Hostel",
        foreign_keys=[hostel_id],
        backref="notifications",
    )

    # Channel-specific relationships (one-to-one)
    email_details = relationship(
        "EmailNotification",
        back_populates="notification",
        uselist=False,
        cascade="all, delete-orphan",
    )
    sms_details = relationship(
        "SMSNotification",
        back_populates="notification",
        uselist=False,
        cascade="all, delete-orphan",
    )
    push_details = relationship(
        "PushNotification",
        back_populates="notification",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Indexes for performance
    __table_args__ = (
        Index(
            "ix_notifications_recipient_user_status",
            "recipient_user_id",
            "status",
        ),
        Index(
            "ix_notifications_type_status_priority",
            "notification_type",
            "status",
            "priority",
        ),
        Index(
            "ix_notifications_scheduled_status",
            "scheduled_at",
            "status",
        ),
        Index(
            "ix_notifications_hostel_created",
            "hostel_id",
            "created_at",
        ),
        Index(
            "ix_notifications_user_unread",
            "recipient_user_id",
            "read_at",
            postgresql_where="read_at IS NULL",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification(id={self.id}, type={self.notification_type.value}, "
            f"status={self.status.value}, recipient={self.recipient_email or self.recipient_phone})>"
        )

    @property
    def is_sent(self) -> bool:
        """Check if notification has been sent."""
        return self.status in [
            NotificationStatus.SENT,
            NotificationStatus.DELIVERED,
            NotificationStatus.COMPLETED,
        ]

    @property
    def is_pending(self) -> bool:
        """Check if notification is pending delivery."""
        return self.status in [
            NotificationStatus.PENDING,
            NotificationStatus.QUEUED,
            NotificationStatus.PROCESSING,
        ]

    @property
    def is_read(self) -> bool:
        """Check if notification has been read."""
        return self.read_at is not None

    @property
    def can_retry(self) -> bool:
        """Check if notification can be retried."""
        return (
            self.status == NotificationStatus.FAILED
            and self.retry_count < self.max_retries
        )

    @property
    def delivery_duration_seconds(self) -> int | None:
        """Calculate delivery duration in seconds."""
        if self.sent_at and self.delivered_at:
            return int((self.delivered_at - self.sent_at).total_seconds())
        return None


class NotificationStatusHistory(BaseModel, TimestampMixin):
    """
    Track notification status changes for audit trail.
    
    Records every status transition with timestamp and reason
    for comprehensive audit and debugging capabilities.
    """

    __tablename__ = "notification_status_history"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Reference to notification
    notification_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Status transition
    from_status = Column(
        Enum(NotificationStatus),
        nullable=True,
        comment="Previous status (null for initial creation)",
    )
    to_status = Column(
        Enum(NotificationStatus),
        nullable=False,
        comment="New status",
    )

    # Context
    changed_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who triggered the change (if manual)",
    )
    change_reason = Column(
        Text,
        nullable=True,
        comment="Reason for status change",
    )
    metadata = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Additional context data",
    )

    # Relationships
    notification = relationship(
        "Notification",
        backref="status_history",
    )
    changed_by_user = relationship(
        "User",
        foreign_keys=[changed_by],
    )

    __table_args__ = (
        Index(
            "ix_notification_status_history_notification_created",
            "notification_id",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationStatusHistory(notification_id={self.notification_id}, "
            f"{self.from_status} → {self.to_status})>"
        )


class NotificationReadReceipt(BaseModel, TimestampMixin):
    """
    Track when and how users read notifications.
    
    Provides detailed read tracking including device, location,
    and interaction context for analytics and engagement metrics.
    """

    __tablename__ = "notification_read_receipts"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # References
    notification_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Read context
    read_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When notification was read",
    )
    read_method = Column(
        String(50),
        nullable=True,
        comment="How notification was read (email_open, push_tap, in_app_view)",
    )

    # Device and location
    device_type = Column(
        String(50),
        nullable=True,
        comment="Device type (mobile, desktop, tablet)",
    )
    device_id = Column(
        String(255),
        nullable=True,
        comment="Device identifier",
    )
    ip_address = Column(
        String(45),
        nullable=True,
        comment="IP address of reader",
    )
    user_agent = Column(
        Text,
        nullable=True,
        comment="Browser/app user agent",
    )

    # Engagement
    time_to_read_seconds = Column(
        Integer,
        nullable=True,
        comment="Seconds from delivery to read",
    )
    interaction_duration_seconds = Column(
        Integer,
        nullable=True,
        comment="How long user interacted with notification",
    )

    # Relationships
    notification = relationship(
        "Notification",
        backref="read_receipts",
    )
    user = relationship(
        "User",
        backref="notification_read_receipts",
    )

    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            "user_id",
            name="uq_notification_user_read",
        ),
        Index(
            "ix_read_receipts_user_read_at",
            "user_id",
            "read_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationReadReceipt(notification_id={self.notification_id}, "
            f"user_id={self.user_id}, read_at={self.read_at})>"
        )