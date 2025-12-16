# --- File: app/schemas/notification/notification_queue.py ---
"""
Notification queue schemas.

This module provides schemas for managing notification queues, batch
processing, and monitoring queue performance and health.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, List, Union
from uuid import UUID

from pydantic import Field, computed_field

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import NotificationStatus, NotificationType, Priority

__all__ = [
    "QueueStatus",
    "QueuedNotification",
    "BatchProcessing",
    "QueueStats",
    "QueueHealth",
    "QueuePriority",
]


class QueueStatus(BaseSchema):
    """
    Current notification queue status.

    Provides real-time overview of queue state across all channels
    and priorities.
    """

    # Overall queue counts
    total_queued: int = Field(
        ...,
        ge=0,
        description="Total notifications in queue",
    )
    total_processing: int = Field(
        ...,
        ge=0,
        description="Notifications currently being processed",
    )
    total_failed: int = Field(
        ...,
        ge=0,
        description="Failed notifications awaiting retry",
    )

    # By priority
    urgent_queued: int = Field(
        default=0,
        ge=0,
        description="Urgent/critical priority notifications queued",
    )
    high_queued: int = Field(
        default=0,
        ge=0,
        description="High priority notifications queued",
    )
    medium_queued: int = Field(
        default=0,
        ge=0,
        description="Medium priority notifications queued",
    )
    low_queued: int = Field(
        default=0,
        ge=0,
        description="Low priority notifications queued",
    )

    # By notification type
    email_queued: int = Field(
        default=0,
        ge=0,
        description="Email notifications queued",
    )
    sms_queued: int = Field(
        default=0,
        ge=0,
        description="SMS notifications queued",
    )
    push_queued: int = Field(
        default=0,
        ge=0,
        description="Push notifications queued",
    )

    # Processing performance
    avg_processing_time_seconds: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Average processing time per notification",
    )
    throughput_per_minute: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Notifications processed per minute",
    )

    # Queue health
    is_healthy: bool = Field(
        ...,
        description="Whether queue is operating normally",
    )
    oldest_queued_age_minutes: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Age of oldest queued notification in minutes",
    )

    # Timestamp
    checked_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When status was checked",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_in_system(self) -> int:
        """Calculate total notifications in the system."""
        return self.total_queued + self.total_processing + self.total_failed

    @computed_field  # type: ignore[prop-decorator]
    @property
    def queue_utilization_percent(self) -> float:
        """Calculate queue utilization as a percentage."""
        # Assuming a max queue size (configurable)
        max_queue_size = 10000
        if self.total_queued == 0:
            return 0.0
        return round((self.total_queued / max_queue_size) * 100, 2)


class QueuedNotification(BaseSchema):
    """
    Individual queued notification details.

    Represents a notification waiting in queue for processing.
    """

    notification_id: UUID = Field(
        ...,
        description="Notification ID",
    )

    # Notification details
    notification_type: NotificationType = Field(
        ...,
        description="Notification channel",
    )
    priority: Priority = Field(
        ...,
        description="Delivery priority",
    )
    status: NotificationStatus = Field(
        ...,
        description="Current status",
    )

    # Recipient
    recipient: str = Field(
        ...,
        max_length=255,
        description="Recipient identifier (email/phone/user_id)",
    )

    # Timing
    scheduled_at: Union[datetime, None] = Field(
        default=None,
        description="Scheduled delivery time",
    )
    queued_at: datetime = Field(
        ...,
        description="When notification was queued",
    )
    processing_started_at: Union[datetime, None] = Field(
        default=None,
        description="When processing started",
    )

    # Retry information
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retry attempts",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum allowed retries",
    )
    next_retry_at: Union[datetime, None] = Field(
        default=None,
        description="When next retry will be attempted",
    )

    # Estimates
    estimated_send_time: Union[datetime, None] = Field(
        default=None,
        description="Estimated send time based on queue position",
    )
    queue_position: Union[int, None] = Field(
        default=None,
        ge=1,
        description="Position in queue (by priority)",
    )

    # Error tracking
    last_error: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Last error message if failed",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def age_minutes(self) -> int:
        """Calculate how long notification has been in queue."""
        return int((datetime.utcnow() - self.queued_at).total_seconds() / 60)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def can_retry(self) -> bool:
        """Check if notification can be retried."""
        return (
            self.status == NotificationStatus.FAILED
            and self.retry_count < self.max_retries
        )


class BatchProcessing(BaseSchema):
    """
    Batch processing status and progress.

    Tracks bulk notification sends with detailed progress metrics.
    """

    batch_id: UUID = Field(
        ...,
        description="Unique batch identifier",
    )

    # Batch details
    batch_name: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Batch/campaign name",
    )
    notification_type: NotificationType = Field(
        ...,
        description="Type of notifications in batch",
    )

    # Counts
    total_notifications: int = Field(
        ...,
        ge=1,
        description="Total notifications in batch",
    )
    processed: int = Field(
        ...,
        ge=0,
        description="Notifications processed so far",
    )
    successful: int = Field(
        ...,
        ge=0,
        description="Successfully sent notifications",
    )
    failed: int = Field(
        ...,
        ge=0,
        description="Failed notifications",
    )
    pending: int = Field(
        ...,
        ge=0,
        description="Notifications still pending",
    )

    # Status
    status: str = Field(
        ...,
        pattern="^(queued|processing|paused|completed|failed|cancelled)$",
        description="Batch processing status",
    )

    # Timing
    created_at: datetime = Field(
        ...,
        description="When batch was created",
    )
    started_at: Union[datetime, None] = Field(
        default=None,
        description="When processing started",
    )
    completed_at: Union[datetime, None] = Field(
        default=None,
        description="When processing completed",
    )

    # Estimates
    estimated_completion: Union[datetime, None] = Field(
        default=None,
        description="Estimated completion time",
    )
    estimated_duration_seconds: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Estimated total duration",
    )

    # Performance
    current_throughput_per_minute: Annotated[Decimal, Field(ge=0)] = Field(
        default=Decimal("0"),
        description="Current processing rate",
    )
    average_processing_time_seconds: Annotated[Decimal, Field(ge=0)] = Field(
        default=Decimal("0"),
        description="Average time per notification",
    )

    # Error summary
    error_summary: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Summary of errors encountered",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def progress_percentage(self) -> float:
        """Calculate batch progress percentage."""
        if self.total_notifications == 0:
            return 0.0
        return round((self.processed / self.total_notifications) * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.processed == 0:
            return 0.0
        return round((self.successful / self.processed) * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate percentage."""
        if self.processed == 0:
            return 0.0
        return round((self.failed / self.processed) * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_complete(self) -> bool:
        """Check if batch processing is complete."""
        return self.status in ["completed", "failed", "cancelled"]


class QueueStats(BaseSchema):
    """
    Comprehensive queue statistics.

    Provides historical and current performance metrics for the
    notification queue system.
    """

    # Current state
    current_queue_size: int = Field(
        ...,
        ge=0,
        description="Current number of queued notifications",
    )
    oldest_queued_age_minutes: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Age of oldest notification in queue",
    )

    # Today's statistics
    today_processed: int = Field(
        ...,
        ge=0,
        description="Notifications processed today",
    )
    today_successful: int = Field(
        ...,
        ge=0,
        description="Successful notifications today",
    )
    today_failed: int = Field(
        ...,
        ge=0,
        description="Failed notifications today",
    )

    # Success/failure rates
    success_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Overall success rate percentage",
    )
    failure_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Overall failure rate percentage",
    )

    # Performance metrics
    average_queue_time_minutes: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Average time notifications spend in queue",
    )
    average_processing_time_seconds: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Average processing time per notification",
    )
    average_total_time_seconds: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Average total time from queue to delivery",
    )

    # Throughput
    current_throughput_per_minute: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Current processing throughput",
    )
    peak_throughput_per_minute: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Peak throughput achieved today",
    )
    average_throughput_per_minute: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Average throughput",
    )

    # By type breakdown
    email_processed_today: int = Field(default=0, ge=0)
    sms_processed_today: int = Field(default=0, ge=0)
    push_processed_today: int = Field(default=0, ge=0)

    # By priority breakdown
    urgent_processed_today: int = Field(default=0, ge=0)
    high_processed_today: int = Field(default=0, ge=0)
    medium_processed_today: int = Field(default=0, ge=0)
    low_processed_today: int = Field(default=0, ge=0)

    # Retry statistics
    total_retries_today: int = Field(
        default=0,
        ge=0,
        description="Total retry attempts today",
    )
    retry_success_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        default=Decimal("0"),
        description="Percentage of retries that succeeded",
    )

    # Worker health
    active_workers: int = Field(
        ...,
        ge=0,
        description="Number of active queue workers",
    )
    idle_workers: int = Field(
        ...,
        ge=0,
        description="Number of idle workers",
    )

    # Timestamp
    stats_generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When statistics were generated",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_workers(self) -> int:
        """Calculate total number of workers."""
        return self.active_workers + self.idle_workers

    @computed_field  # type: ignore[prop-decorator]
    @property
    def worker_utilization_percent(self) -> float:
        """Calculate worker utilization percentage."""
        if self.total_workers == 0:
            return 0.0
        return round((self.active_workers / self.total_workers) * 100, 2)


class QueueHealth(BaseSchema):
    """
    Queue health monitoring and diagnostics.

    Provides health status and alerts for queue system monitoring.
    """

    # Overall health
    is_healthy: bool = Field(
        ...,
        description="Overall queue health status",
    )
    health_score: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Health score (0-100)",
    )

    # Component health
    queue_healthy: bool = Field(
        ...,
        description="Queue is processing normally",
    )
    workers_healthy: bool = Field(
        ...,
        description="Workers are functioning properly",
    )
    database_healthy: bool = Field(
        ...,
        description="Database connection is healthy",
    )
    external_services_healthy: bool = Field(
        ...,
        description="External notification services are reachable",
    )

    # Issues and alerts
    active_issues: List[str] = Field(
        default_factory=list,
        description="List of active issues",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of warnings",
    )

    # Performance indicators
    queue_backlog_minutes: int = Field(
        ...,
        ge=0,
        description="Estimated backlog in minutes",
    )
    is_overloaded: bool = Field(
        ...,
        description="Whether queue is overloaded",
    )
    is_underutilized: bool = Field(
        ...,
        description="Whether queue has excess capacity",
    )

    # Resource usage
    memory_usage_percent: Union[Annotated[Decimal, Field(ge=0, le=100)], None] = Field(
        default=None,
        description="Memory usage percentage",
    )
    cpu_usage_percent: Union[Annotated[Decimal, Field(ge=0, le=100)], None] = Field(
        default=None,
        description="CPU usage percentage",
    )

    # Recommendations
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommended actions",
    )

    # Timestamp
    checked_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When health check was performed",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues."""
        return len(self.active_issues) > 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def needs_attention(self) -> bool:
        """Check if queue needs administrator attention."""
        return not self.is_healthy or self.has_critical_issues


class QueuePriority(BaseSchema):
    """
    Queue priority configuration and status.

    Manages priority-based queue processing rules.
    """

    priority_level: Priority = Field(
        ...,
        description="Priority level",
    )

    # Processing rules
    processing_weight: int = Field(
        ...,
        ge=1,
        le=100,
        description="Relative processing weight (higher = more priority)",
    )
    max_concurrent: int = Field(
        ...,
        ge=1,
        description="Maximum concurrent processing for this priority",
    )

    # Current state
    queued_count: int = Field(
        ...,
        ge=0,
        description="Currently queued notifications",
    )
    processing_count: int = Field(
        ...,
        ge=0,
        description="Currently processing notifications",
    )

    # Performance
    average_wait_time_seconds: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Average wait time for this priority",
    )
    throughput_per_minute: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Processing throughput for this priority",
    )

    # SLA
    target_processing_time_seconds: int = Field(
        ...,
        ge=1,
        description="Target processing time SLA",
    )
    sla_compliance_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Percentage meeting SLA",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_meeting_sla(self) -> bool:
        """Check if priority level is meeting SLA targets."""
        return self.sla_compliance_rate >= Decimal("95.0")  # 95% threshold