# --- File: C:\Hostel-Main\app\models\notification\email_notification.py ---
"""
Email-specific notification model with delivery tracking.

Handles email delivery, tracking, analytics, and attachments.
"""

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
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.notification.notification import Notification


class EmailNotification(BaseModel, TimestampMixin):
    """
    Email-specific notification details and tracking.
    
    Extends base notification with email-specific features including
    CC/BCC, attachments, open tracking, click tracking, and bounce handling.
    """

    __tablename__ = "email_notifications"

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

    # Email-specific recipients
    cc_emails = Column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="CC recipients",
    )
    bcc_emails = Column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="BCC recipients",
    )

    # Content
    body_html = Column(
        Text,
        nullable=False,
        comment="HTML email body",
    )
    body_text = Column(
        Text,
        nullable=True,
        comment="Plain text fallback body",
    )

    # Sender customization
    reply_to = Column(
        String(255),
        nullable=True,
        comment="Reply-to email address",
    )
    from_name = Column(
        String(100),
        nullable=True,
        comment="Sender display name",
    )
    from_email = Column(
        String(255),
        nullable=True,
        comment="Actual sender email (may differ from reply_to)",
    )

    # Tracking settings
    track_opens = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Enable open tracking",
    )
    track_clicks = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Enable click tracking",
    )

    # Engagement tracking
    opened = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether email was opened",
    )
    first_opened_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When email was first opened",
    )
    last_opened_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When email was last opened",
    )
    open_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times email was opened",
    )

    clicked = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether any link was clicked",
    )
    first_clicked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When first link was clicked",
    )
    last_clicked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When last link was clicked",
    )
    click_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of link clicks",
    )

    # Link-level tracking
    clicked_links = Column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="URLs that were clicked",
    )

    # Delivery status
    delivery_status = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Detailed delivery status (sent/delivered/bounced/failed/spam)",
    )
    bounced = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether email bounced",
    )
    bounce_type = Column(
        String(20),
        nullable=True,
        comment="Type of bounce (hard/soft/complaint)",
    )
    bounce_reason = Column(
        Text,
        nullable=True,
        comment="Detailed bounce reason",
    )

    # Spam handling
    marked_as_spam = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether recipient marked as spam",
    )
    spam_reported_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When marked as spam",
    )

    # Provider information
    provider_message_id = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Email service provider's message ID",
    )
    provider_response = Column(
        JSONB,
        nullable=True,
        comment="Raw response from email provider",
    )

    # Relationships
    notification = relationship(
        "Notification",
        back_populates="email_details",
    )

    attachments = relationship(
        "EmailAttachment",
        back_populates="email",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_email_notifications_opened_clicked",
            "opened",
            "clicked",
        ),
        Index(
            "ix_email_notifications_delivery_status",
            "delivery_status",
            "bounced",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<EmailNotification(id={self.id}, "
            f"opened={self.opened}, clicked={self.clicked})>"
        )


class EmailAttachment(BaseModel, TimestampMixin):
    """
    Email attachments with size and type tracking.
    
    Manages file attachments for emails with validation,
    storage, and access tracking.
    """

    __tablename__ = "email_attachments"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Reference to email
    email_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("email_notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Attachment details
    filename = Column(
        String(255),
        nullable=False,
        comment="Original filename",
    )
    file_url = Column(
        String(500),
        nullable=False,
        comment="URL to attachment file",
    )
    mime_type = Column(
        String(100),
        nullable=True,
        comment="MIME type of attachment",
    )
    size_bytes = Column(
        Integer,
        nullable=True,
        comment="File size in bytes",
    )

    # Tracking
    download_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times attachment was downloaded",
    )

    # Relationships
    email = relationship(
        "EmailAttachment",
        back_populates="attachments",
    )

    def __repr__(self) -> str:
        return (
            f"<EmailAttachment(filename={self.filename}, "
            f"size={self.size_bytes} bytes)>"
        )


class EmailClickEvent(BaseModel, TimestampMixin):
    """
    Individual email link click events for analytics.
    
    Tracks every click on links within emails for detailed
    engagement analytics and conversion tracking.
    """

    __tablename__ = "email_click_events"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Reference to email
    email_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("email_notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Click details
    url = Column(
        String(500),
        nullable=False,
        comment="URL that was clicked",
    )
    clicked_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When link was clicked",
    )

    # Context
    ip_address = Column(
        String(45),
        nullable=True,
        comment="IP address of clicker",
    )
    user_agent = Column(
        Text,
        nullable=True,
        comment="Browser user agent",
    )
    device_type = Column(
        String(50),
        nullable=True,
        comment="Device type (mobile/desktop/tablet)",
    )

    __table_args__ = (
        Index(
            "ix_email_clicks_email_url_clicked",
            "email_id",
            "url",
            "clicked_at",
        ),
    )

    def __repr__(self) -> str:
        return f"<EmailClickEvent(email_id={self.email_id}, url={self.url})>"