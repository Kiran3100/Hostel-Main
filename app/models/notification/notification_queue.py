# --- File: C:\Hostel-Main\app\models\notification\notification_queue.py ---
"""
Notification queue management for batch processing and priority handling.

Manages notification queue, batch processing, and delivery optimization.
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
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin
from app.schemas.common.enums import NotificationStatus, NotificationType, Priority

if TYPE_CHECKING:
    from app.models.notification.notification import Notification


class NotificationQueue(BaseModel, TimestampMixin):
    """
    Queue management for notification processing.
    
    Manages notification queuing, prioritization, retry logic,
    and batch processing for optimal delivery performance.
    """

    __tablename__ = "notification_queue"

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
        unique=True,
        index=True,
    )

    # Queue metadata
    notification_type = Column(
        Enum(NotificationType),
        nullable=False,
        index=True,
        comment="Notification type for queue routing",
    )
    priority = Column(
        Enum(Priority),
        nullable=False,
        index=True,
        comment="Processing priority",
    )
    status = Column(
        Enum(NotificationStatus),
        nullable=False,
        default=NotificationStatus.QUEUED,
        index=True,
        comment="Current queue status",
    )

    # Scheduling
    scheduled_for = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When to process this notification",
    )
    queued_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When notification was queued",
    )
    processing_started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When processing started",
    )
    processing_completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When processing completed",
    )

    # Retry management
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
    next_retry_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When next retry will be attempted",
    )

    # Processing metadata
    worker_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="ID of worker processing this notification",
    )
    processing_duration_ms = Column(
        Integer,
        nullable=True,
        comment="Processing duration in milliseconds",
    )

    # Error tracking
    last_error = Column(
        Text,
        nullable=True,
        comment="Last error message if processing failed",
    )
    error_details = Column(
        JSONB,
        nullable=True,
        comment="Detailed error information",
    )

    # Batch tracking
    batch_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("notification_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Batch this notification belongs to",
    )

    # Relationships
    notification = relationship(
        "Notification",
        backref="queue_entry",
    )
    batch = relationship(
        "NotificationBatch",
        backref="queued_notifications",
    )

    __table_args__ = (
        Index(
            "ix_notification_queue_priority_status",
            "priority",
            "status",
            "scheduled_for",
        ),
        Index(
            "ix_notification_queue_retry",
            "next_retry_at",
            "retry_count",
            postgresql_where="next_retry_at IS NOT NULL",
        ),
        Index(
            "ix_notification_queue_processing",
            "status",
            "processing_started_at",
            postgresql_where="status = 'PROCESSING'",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationQueue(notification_id={self.notification_id}, "
            f"status={self.status.value}, priority={self.priority.value})>"
        )

    @property
    def age_minutes(self) -> int:
        """Calculate how long notification has been in queue."""
        return int((datetime.utcnow() - self.queued_at).total_seconds() / 60)

    @property
    def can_retry(self) -> bool:
        """Check if notification can be retried."""
        return (
            self.status == NotificationStatus.FAILED
            and self.retry_count < self.max_retries
        )


class NotificationBatch(BaseModel, TimestampMixin):
    """
    Batch processing management for bulk notifications.
    
    Groups notifications for efficient batch processing with
    progress tracking and performance metrics.
    """

    __tablename__ = "notification_batches"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Batch metadata
    batch_name = Column(
        String(100),
        nullable=True,
        comment="Optional batch/campaign name",
    )
    notification_type = Column(
        Enum(NotificationType),
        nullable=False,
        index=True,
        comment="Type of notifications in this batch",
    )

    # Counts
    total_notifications = Column(
        Integer,
        nullable=False,
        comment="Total notifications in batch",
    )
    processed = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Notifications processed so far",
    )
    successful = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Successfully delivered notifications",
    )
    failed = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Failed notifications",
    )

    # Status
    status = Column(
        String(50),
        nullable=False,
        default="queued",
        index=True,
        comment="Batch processing status",
    )

    # Timing
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When batch processing started",
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When batch processing completed",
    )
    estimated_completion = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Estimated completion time",
    )

    # Performance metrics
    current_throughput = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Current processing rate (per minute)",
    )
    average_processing_time_ms = Column(
        Integer,
        nullable=True,
        comment="Average time per notification in milliseconds",
    )

    # Error summary
    error_summary = Column(
        Text,
        nullable=True,
        comment="Summary of errors encountered",
    )

    __table_args__ = (
        Index(
            "ix_notification_batches_status_created",
            "status",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationBatch(id={self.id}, "
            f"total={self.total_notifications}, processed={self.processed})>"
        )

    @property
    def progress_percentage(self) -> float:
        """Calculate batch progress percentage."""
        if self.total_notifications == 0:
            return 0.0
        return round((self.processed / self.total_notifications) * 100, 2)

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.processed == 0:
            return 0.0
        return round((self.successful / self.processed) * 100, 2)