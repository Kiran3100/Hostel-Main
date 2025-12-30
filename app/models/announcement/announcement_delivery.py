# --- File: app/models/announcement/announcement_delivery.py ---
"""
Announcement delivery models.

This module defines models for managing announcement delivery
across multiple channels (email, SMS, push, in-app).
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.announcement.announcement import Announcement
    from app.models.user.user import User

__all__ = [
    "AnnouncementDelivery",
    "DeliveryChannel",
    "DeliveryBatch",
    "DeliveryFailure",
    "DeliveryRetry",
]


class DeliveryChannelType:
    """Delivery channel enumeration."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


class DeliveryState:
    """Delivery state enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class DeliveryStrategy:
    """Delivery strategy enumeration."""
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    BATCHED = "batched"


class AnnouncementDelivery(UUIDMixin, TimestampModel, BaseModel):
    """
    Announcement delivery tracking.
    
    Tracks delivery status of announcements to individual
    recipients across all channels.
    """
    
    __tablename__ = "announcement_deliveries"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated announcement",
    )
    recipient_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Recipient student",
    )
    
    # Delivery Channel
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Delivery channel (email, sms, push, in_app)",
    )
    
    # Delivery Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DeliveryState.PENDING,
        index=True,
        comment="Delivery status",
    )
    
    # Delivery Timing
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When delivery is scheduled",
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When delivery was sent",
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When delivery was confirmed",
    )
    
    # Recipient Contact Information (cached)
    recipient_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Recipient email address",
    )
    recipient_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Recipient phone number",
    )
    recipient_device_token: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Recipient push notification token",
    )
    
    # Delivery Metadata
    provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Service provider used (e.g., SendGrid, Twilio)",
    )
    provider_message_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Provider's message ID for tracking",
    )
    provider_response: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Provider response data",
    )
    
    # Delivery Success Indicators
    is_delivered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether delivery was successful",
    )
    is_bounced: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether delivery bounced",
    )
    is_opened: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether message was opened (email/push)",
    )
    opened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When message was opened",
    )
    is_clicked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether links were clicked",
    )
    clicked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When links were clicked",
    )
    
    # Failure Details
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for delivery failure",
    )
    failure_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Error code if delivery failed",
    )
    
    # Retry Information
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of retry attempts",
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Maximum retry attempts allowed",
    )
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When to retry delivery",
    )
    
    # Performance Metrics
    delivery_time_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Time taken to deliver in seconds",
    )
    
    # Batch Information
    batch_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcement_delivery_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Associated delivery batch",
    )
    
    # Metadata
    meta_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional delivery metadata",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        back_populates="deliveries",
    )
    recipient: Mapped["User"] = relationship(
        "User",
        lazy="select",
    )
    batch: Mapped[Optional["DeliveryBatch"]] = relationship(
        "DeliveryBatch",
        back_populates="deliveries",
    )
    failures: Mapped[List["DeliveryFailure"]] = relationship(
        "DeliveryFailure",
        back_populates="delivery",
        cascade="all, delete-orphan",
        lazy="select",
    )
    retries: Mapped[List["DeliveryRetry"]] = relationship(
        "DeliveryRetry",
        back_populates="delivery",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    __table_args__ = (
        UniqueConstraint(
            "announcement_id",
            "recipient_id",
            "channel",
            name="uq_announcement_deliveries_announcement_recipient_channel",
        ),
        Index("ix_announcement_deliveries_announcement", "announcement_id"),
        Index("ix_announcement_deliveries_recipient", "recipient_id"),
        Index("ix_announcement_deliveries_channel", "channel"),
        Index("ix_announcement_deliveries_status", "status"),
        Index("ix_announcement_deliveries_batch", "batch_id"),
        Index("ix_announcement_deliveries_provider_id", "provider_message_id"),
        Index("ix_announcement_deliveries_scheduled", "scheduled_for"),
        Index("ix_announcement_deliveries_next_retry", "next_retry_at"),
        Index("ix_announcement_deliveries_pending", "status", "scheduled_for"),
        CheckConstraint(
            "channel IN ('email', 'sms', 'push', 'in_app')",
            name="ck_announcement_deliveries_channel_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'paused', 'cancelled')",
            name="ck_announcement_deliveries_status_valid",
        ),
        CheckConstraint(
            "retry_count >= 0",
            name="ck_announcement_deliveries_retry_count",
        ),
        CheckConstraint(
            "retry_count <= max_retries",
            name="ck_announcement_deliveries_retry_limit",
        ),
        CheckConstraint(
            "delivery_time_seconds IS NULL OR delivery_time_seconds >= 0",
            name="ck_announcement_deliveries_time_positive",
        ),
        {"comment": "Announcement delivery tracking per recipient and channel"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<AnnouncementDelivery(id={self.id}, announcement_id={self.announcement_id}, "
            f"recipient_id={self.recipient_id}, channel={self.channel}, status={self.status})>"
        )


class DeliveryChannel(UUIDMixin, TimestampModel, BaseModel):
    """
    Delivery channel configuration.
    
    Stores configuration for each delivery channel including
    provider settings and rate limits.
    """
    
    __tablename__ = "announcement_delivery_channels"
    
    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated hostel",
    )
    
    # Channel Configuration
    channel_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Channel type (email, sms, push, in_app)",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether channel is enabled",
    )
    
    # Provider Configuration
    provider_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Service provider name",
    )
    provider_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Provider configuration (API keys, etc.)",
    )
    
    # Priority and Fallback
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Channel priority (higher = preferred)",
    )
    fallback_channel_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcement_delivery_channels.id", ondelete="SET NULL"),
        nullable=True,
        comment="Fallback channel if this one fails",
    )
    
    # Rate Limiting
    max_per_minute: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum deliveries per minute",
    )
    max_per_hour: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum deliveries per hour",
    )
    max_per_day: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum deliveries per day",
    )
    
    # Current Usage
    sent_today: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number sent today",
    )
    sent_this_hour: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number sent this hour",
    )
    sent_this_minute: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number sent this minute",
    )
    last_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When counters were last reset",
    )
    
    # Health Status
    is_healthy: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether channel is healthy",
    )
    last_health_check: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last health check timestamp",
    )
    health_check_failures: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Consecutive health check failures",
    )
    
    # Statistics
    total_sent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total messages sent through this channel",
    )
    total_delivered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total messages successfully delivered",
    )
    total_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total messages failed",
    )
    
    # Metadata
    meta_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional channel metadata",
    )
    
    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
    )
    fallback_channel: Mapped[Optional["DeliveryChannel"]] = relationship(
        "DeliveryChannel",
        remote_side="DeliveryChannel.id",
        lazy="select",
    )
    
    __table_args__ = (
        UniqueConstraint(
            "hostel_id",
            "channel_type",
            "provider_name",
            name="uq_delivery_channels_hostel_type_provider",
        ),
        Index("ix_delivery_channels_hostel", "hostel_id"),
        Index("ix_delivery_channels_type", "channel_type"),
        Index("ix_delivery_channels_enabled", "is_enabled"),
        Index("ix_delivery_channels_healthy", "is_healthy"),
        Index("ix_delivery_channels_priority", "priority"),
        CheckConstraint(
            "channel_type IN ('email', 'sms', 'push', 'in_app')",
            name="ck_delivery_channels_type_valid",
        ),
        CheckConstraint(
            "max_per_minute IS NULL OR max_per_minute > 0",
            name="ck_delivery_channels_rate_limit_minute",
        ),
        CheckConstraint(
            "max_per_hour IS NULL OR max_per_hour > 0",
            name="ck_delivery_channels_rate_limit_hour",
        ),
        CheckConstraint(
            "max_per_day IS NULL OR max_per_day > 0",
            name="ck_delivery_channels_rate_limit_day",
        ),
        CheckConstraint(
            "sent_today >= 0 AND sent_this_hour >= 0 AND sent_this_minute >= 0",
            name="ck_delivery_channels_sent_counts",
        ),
        CheckConstraint(
            "total_sent >= 0 AND total_delivered >= 0 AND total_failed >= 0",
            name="ck_delivery_channels_totals",
        ),
        {"comment": "Delivery channel configuration and health monitoring"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeliveryChannel(id={self.id}, hostel_id={self.hostel_id}, "
            f"type={self.channel_type}, provider={self.provider_name}, enabled={self.is_enabled})>"
        )


class DeliveryBatch(UUIDMixin, TimestampModel, BaseModel):
    """
    Delivery batch for processing.
    
    Groups deliveries into batches for efficient processing
    and rate limit management.
    """
    
    __tablename__ = "announcement_delivery_batches"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated announcement",
    )
    
    # Batch Configuration
    batch_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Batch sequence number",
    )
    batch_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of recipients in this batch",
    )
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Delivery channel for this batch",
    )
    
    # Batch Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DeliveryState.PENDING,
        index=True,
        comment="Batch processing status",
    )
    
    # Timing
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When batch is scheduled to process",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When batch processing started",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When batch processing completed",
    )
    
    # Progress Tracking
    total_recipients: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Total recipients in batch",
    )
    processed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number processed so far",
    )
    sent_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number successfully sent",
    )
    failed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number failed",
    )
    
    # Performance Metrics
    processing_duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Total processing time in seconds",
    )
    average_delivery_time_seconds: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Average delivery time per message",
    )
    
    # Control Flags
    is_paused: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether batch processing is paused",
    )
    paused_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When batch was paused",
    )
    pause_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for pausing",
    )
    
    # Worker Assignment
    worker_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Worker ID processing this batch",
    )
    
    # Metadata
    meta_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional batch metadata",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        lazy="select",
    )
    deliveries: Mapped[List["AnnouncementDelivery"]] = relationship(
        "AnnouncementDelivery",
        back_populates="batch",
        lazy="select",
    )
    
    __table_args__ = (
        UniqueConstraint(
            "announcement_id",
            "batch_number",
            name="uq_delivery_batches_announcement_number",
        ),
        Index("ix_delivery_batches_announcement", "announcement_id"),
        Index("ix_delivery_batches_status", "status"),
        Index("ix_delivery_batches_channel", "channel"),
        Index("ix_delivery_batches_scheduled", "scheduled_at"),
        Index("ix_delivery_batches_paused", "is_paused"),
        CheckConstraint(
            "batch_number > 0",
            name="ck_delivery_batches_number_positive",
        ),
        CheckConstraint(
            "batch_size > 0",
            name="ck_delivery_batches_size_positive",
        ),
        CheckConstraint(
            "total_recipients >= 0",
            name="ck_delivery_batches_recipients_positive",
        ),
        CheckConstraint(
            "processed_count >= 0 AND processed_count <= total_recipients",
            name="ck_delivery_batches_processed_valid",
        ),
        CheckConstraint(
            "sent_count >= 0 AND sent_count <= processed_count",
            name="ck_delivery_batches_sent_valid",
        ),
        CheckConstraint(
            "failed_count >= 0 AND failed_count <= processed_count",
            name="ck_delivery_batches_failed_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'paused', 'cancelled')",
            name="ck_delivery_batches_status_valid",
        ),
        {"comment": "Delivery batches for efficient processing"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeliveryBatch(id={self.id}, announcement_id={self.announcement_id}, "
            f"batch={self.batch_number}, status={self.status}, "
            f"progress={self.processed_count}/{self.total_recipients})>"
        )


class DeliveryFailure(UUIDMixin, TimestampModel, BaseModel):
    """
    Delivery failure tracking.
    
    Records detailed information about failed deliveries
    for troubleshooting and analysis.
    """
    
    __tablename__ = "announcement_delivery_failures"
    
    # Foreign Keys
    delivery_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcement_deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated delivery",
    )
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated announcement",
    )
    recipient_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Recipient who didn't receive",
    )
    
    # Failure Details
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Channel that failed",
    )
    failure_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Reason for failure",
    )
    failure_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Error code if available",
    )
    failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When failure occurred",
    )
    
    # Provider Information
    provider_name: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Provider that failed",
    )
    provider_error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Provider's error message",
    )
    provider_error_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Provider's error code",
    )
    provider_response: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Complete provider response",
    )
    
    # Recipient Information (cached for analysis)
    recipient_contact: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Contact info used (email/phone)",
    )
    
    # Failure Classification
    is_permanent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether this is a permanent failure (no retry)",
    )
    is_temporary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this is a temporary failure (can retry)",
    )
    
    # Resolution
    is_resolved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether issue is resolved",
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When issue was resolved",
    )
    resolution_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="How issue was resolved (retry, manual, fallback)",
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Resolution notes",
    )
    
    # Metadata
    meta_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional failure metadata",
    )
    
    # Relationships
    delivery: Mapped["AnnouncementDelivery"] = relationship(
        "AnnouncementDelivery",
        back_populates="failures",
    )
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        lazy="select",
    )
    recipient: Mapped["User"] = relationship(
        "User",
        lazy="select",
    )
    
    __table_args__ = (
        Index("ix_delivery_failures_delivery", "delivery_id"),
        Index("ix_delivery_failures_announcement", "announcement_id"),
        Index("ix_delivery_failures_recipient", "recipient_id"),
        Index("ix_delivery_failures_channel", "channel"),
        Index("ix_delivery_failures_failed_at", "failed_at"),
        Index("ix_delivery_failures_code", "failure_code"),
        Index("ix_delivery_failures_permanent", "is_permanent"),
        Index("ix_delivery_failures_resolved", "is_resolved"),
        CheckConstraint(
            "channel IN ('email', 'sms', 'push', 'in_app')",
            name="ck_delivery_failures_channel_valid",
        ),
        {"comment": "Delivery failure tracking and resolution"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeliveryFailure(id={self.id}, delivery_id={self.delivery_id}, "
            f"channel={self.channel}, resolved={self.is_resolved})>"
        )


class DeliveryRetry(UUIDMixin, TimestampModel, BaseModel):
    """
    Delivery retry attempts.
    
    Tracks retry attempts for failed deliveries including
    timing and outcomes.
    """
    
    __tablename__ = "announcement_delivery_retries"
    
    # Foreign Keys
    delivery_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcement_deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated delivery",
    )
    failure_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcement_delivery_failures.id", ondelete="SET NULL"),
        nullable=True,
        comment="Associated failure record",
    )
    
    # Retry Details
    retry_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Retry attempt number (1, 2, 3, etc.)",
    )
    retry_scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When retry was scheduled",
    )
    retry_attempted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When retry was actually attempted",
    )
    
    # Retry Configuration
    retry_strategy: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="exponential_backoff",
        comment="Retry strategy used",
    )
    delay_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Delay before retry in seconds",
    )
    
    # Retry Outcome
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Retry status (pending, success, failed, cancelled)",
    )
    succeeded: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        index=True,
        comment="Whether retry succeeded",
    )
    
    # Failure Details (if retry also failed)
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Failure reason if retry failed",
    )
    failure_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Error code if retry failed",
    )
    
    # Channel Used
    channel_used: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Channel used for retry (may differ from original)",
    )
    is_fallback_channel: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether a fallback channel was used",
    )
    
    # Metadata
    meta_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional retry metadata",
    )
    
    # Relationships
    delivery: Mapped["AnnouncementDelivery"] = relationship(
        "AnnouncementDelivery",
        back_populates="retries",
    )
    failure: Mapped[Optional["DeliveryFailure"]] = relationship(
        "DeliveryFailure",
        lazy="select",
    )
    
    __table_args__ = (
        Index("ix_delivery_retries_delivery", "delivery_id"),
        Index("ix_delivery_retries_failure", "failure_id"),
        Index("ix_delivery_retries_scheduled", "retry_scheduled_at"),
        Index("ix_delivery_retries_status", "status"),
        Index("ix_delivery_retries_succeeded", "succeeded"),
        CheckConstraint(
            "retry_number > 0",
            name="ck_delivery_retries_number_positive",
        ),
        CheckConstraint(
            "delay_seconds >= 0",
            name="ck_delivery_retries_delay_positive",
        ),
        CheckConstraint(
            "status IN ('pending', 'success', 'failed', 'cancelled')",
            name="ck_delivery_retries_status_valid",
        ),
        CheckConstraint(
            "channel_used IN ('email', 'sms', 'push', 'in_app')",
            name="ck_delivery_retries_channel_valid",
        ),
        {"comment": "Delivery retry attempt tracking"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeliveryRetry(id={self.id}, delivery_id={self.delivery_id}, "
            f"retry={self.retry_number}, status={self.status})>"
        )