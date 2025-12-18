# --- File: C:\Hostel-Main\app\models\notification\sms_notification.py ---
"""
SMS-specific notification model with delivery tracking.

Handles SMS delivery, cost tracking, and provider integration.
"""

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.notification.notification import Notification


class SMSNotification(BaseModel, TimestampMixin):
    """
    SMS-specific notification details and tracking.
    
    Manages SMS delivery with provider integration, cost tracking,
    delivery confirmation, and DLT compliance (India).
    """

    __tablename__ = "sms_notifications"

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

    # SMS content
    message_text = Column(
        Text,
        nullable=False,
        comment="SMS message content",
    )

    # Sender configuration
    sender_id = Column(
        String(11),
        nullable=True,
        comment="Sender ID/Name (alphanumeric, max 11 chars)",
    )

    # DLT compliance (India-specific)
    dlt_template_id = Column(
        String(50),
        nullable=True,
        index=True,
        comment="DLT template ID for regulatory compliance",
    )
    dlt_entity_id = Column(
        String(50),
        nullable=True,
        comment="DLT entity ID",
    )

    # Message details
    segments_count = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Number of SMS segments (160 chars each)",
    )
    character_count = Column(
        Integer,
        nullable=False,
        comment="Total character count",
    )
    encoding = Column(
        String(20),
        nullable=False,
        default="GSM-7",
        comment="Message encoding (GSM-7 or Unicode)",
    )

    # Delivery status
    delivery_status = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Detailed delivery status",
    )
    delivered = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether SMS was successfully delivered",
    )

    # Error information
    error_code = Column(
        String(50),
        nullable=True,
        comment="Error code from SMS provider",
    )
    error_message = Column(
        Text,
        nullable=True,
        comment="Human-readable error message",
    )

    # Provider information
    provider_name = Column(
        String(100),
        nullable=True,
        comment="SMS provider used (Twilio, AWS SNS, MSG91, etc.)",
    )
    provider_message_id = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Provider's unique message ID",
    )
    provider_status = Column(
        String(100),
        nullable=True,
        comment="Raw status from provider",
    )
    provider_response = Column(
        JSONB,
        nullable=True,
        comment="Full provider response",
    )

    # Cost tracking
    cost = Column(
        Numeric(10, 4),
        nullable=True,
        comment="Cost for this SMS",
    )
    currency = Column(
        String(3),
        nullable=True,
        default="INR",
        comment="Currency code (ISO 4217)",
    )

    # Relationships
    notification = relationship(
        "Notification",
        back_populates="sms_details",
    )

    __table_args__ = (
        Index(
            "ix_sms_notifications_delivery_status",
            "delivery_status",
            "delivered",
        ),
        Index(
            "ix_sms_notifications_provider",
            "provider_name",
            "provider_message_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SMSNotification(id={self.id}, "
            f"delivered={self.delivered}, segments={self.segments_count})>"
        )

    @property
    def total_cost(self) -> Decimal:
        """Calculate total cost based on segments."""
        if self.cost:
            return Decimal(self.cost) * Decimal(self.segments_count)
        return Decimal("0")