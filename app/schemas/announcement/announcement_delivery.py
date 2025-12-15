# --- File: app/schemas/announcement/announcement_delivery.py ---
"""
Announcement delivery schemas.

This module defines schemas for managing announcement delivery
across multiple channels (email, SMS, push, in-app).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "DeliveryChannel",
    "DeliveryStrategy",
    "DeliveryState",
    "DeliveryConfig",
    "DeliveryChannels",
    "DeliveryStatus",
    "DeliveryReport",
    "ChannelDeliveryStats",
    "FailedDelivery",
    "BatchDelivery",
    "RetryDelivery",
    "DeliveryPause",
    "DeliveryResume",
]


class DeliveryChannel(str, Enum):
    """Delivery channel enumeration."""
    
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


class DeliveryStrategy(str, Enum):
    """Delivery strategy enumeration."""
    
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    BATCHED = "batched"


class DeliveryState(str, Enum):
    """Delivery state enumeration."""
    
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class DeliveryChannels(BaseSchema):
    """
    Delivery channel configuration.
    
    Defines which channels to use and their priorities.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    email: bool = Field(
        False,
        description="Enable email delivery",
    )
    sms: bool = Field(
        False,
        description="Enable SMS delivery",
    )
    push: bool = Field(
        True,
        description="Enable push notification delivery",
    )
    in_app: bool = Field(
        True,
        description="Enable in-app notification",
    )
    
    # Channel priority for fallback
    primary_channel: DeliveryChannel = Field(
        DeliveryChannel.PUSH,
        description="Primary delivery channel",
    )
    fallback_channels: list[DeliveryChannel] = Field(
        default_factory=list,
        description="Fallback channels if primary fails",
    )
    
    @model_validator(mode="after")
    def validate_channels(self) -> "DeliveryChannels":
        """Ensure at least one channel is enabled."""
        if not any([self.email, self.sms, self.push, self.in_app]):
            raise ValueError("At least one delivery channel must be enabled")
        
        # Validate primary channel is enabled
        channel_map = {
            DeliveryChannel.EMAIL: self.email,
            DeliveryChannel.SMS: self.sms,
            DeliveryChannel.PUSH: self.push,
            DeliveryChannel.IN_APP: self.in_app,
        }
        
        if not channel_map.get(self.primary_channel, False):
            raise ValueError(
                f"Primary channel '{self.primary_channel.value}' is not enabled"
            )
        
        # Validate fallback channels are enabled
        for channel in self.fallback_channels:
            if not channel_map.get(channel, False):
                raise ValueError(
                    f"Fallback channel '{channel.value}' is not enabled"
                )
        
        return self


class DeliveryConfig(BaseSchema):
    """
    Complete delivery configuration for announcement.
    
    Defines how and when to deliver the announcement.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    
    # Channels
    channels: DeliveryChannels = Field(
        ...,
        description="Channel configuration",
    )
    
    # Delivery strategy
    delivery_strategy: DeliveryStrategy = Field(
        DeliveryStrategy.IMMEDIATE,
        description="Delivery timing strategy",
    )
    
    # Batch settings (if batched)
    batch_size: Optional[int] = Field(
        None,
        ge=10,
        le=1000,
        description="Recipients per batch (10-1000)",
    )
    batch_interval_minutes: Optional[int] = Field(
        None,
        ge=1,
        le=60,
        description="Minutes between batches (1-60)",
    )
    
    # Rate limiting
    max_per_minute: Optional[int] = Field(
        None,
        ge=1,
        le=10000,
        description="Maximum deliveries per minute",
    )
    
    # Retry settings
    max_retries: int = Field(
        3,
        ge=0,
        le=10,
        description="Maximum retry attempts for failed deliveries",
    )
    retry_delay_minutes: int = Field(
        5,
        ge=1,
        le=60,
        description="Minutes between retries",
    )
    
    @model_validator(mode="after")
    def validate_batch_settings(self) -> "DeliveryConfig":
        """Validate batch settings when using batched strategy."""
        if self.delivery_strategy == DeliveryStrategy.BATCHED:
            if not self.batch_size:
                raise ValueError(
                    "batch_size required for batched delivery strategy"
                )
        return self


class ChannelDeliveryStats(BaseSchema):
    """
    Delivery statistics for a specific channel.
    
    Provides detailed metrics for channel performance.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    channel: DeliveryChannel = Field(
        ...,
        description="Delivery channel",
    )
    
    # Counts
    sent: int = Field(
        ...,
        ge=0,
        description="Number sent",
    )
    
    delivered: int = Field(
        ...,
        ge=0,
        description="Number successfully delivered",
    )
    failed: int = Field(
        ...,
        ge=0,
        description="Number failed",
    )
    pending: int = Field(
        ...,
        ge=0,
        description="Number pending",
    )
    bounced: int = Field(
        0,
        ge=0,
        description="Number bounced (email)",
    )
    
    # Rates - Using Annotated for Decimal constraints in Pydantic v2
    # Pydantic v2: Decimal constraints work differently; ge/le constraints are preserved
    delivery_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Delivery success rate percentage",
    )
    
    # Timing - Using Decimal for precision, but ge constraint only (no decimal_places needed)
    average_delivery_time_seconds: Optional[Annotated[Decimal, Field(ge=0)]] = Field(
        None,
        description="Average time to deliver in seconds",
    )
    fastest_delivery_seconds: Optional[int] = Field(
        None,
        ge=0,
        description="Fastest delivery time",
    )
    slowest_delivery_seconds: Optional[int] = Field(
        None,
        ge=0,
        description="Slowest delivery time",
    )


class DeliveryStatus(BaseSchema):
    """
    Current delivery status for announcement.
    
    Real-time status of delivery progress across all channels.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    
    # Overall status
    state: DeliveryState = Field(
        ...,
        description="Overall delivery state",
    )
    
    # Total counts
    total_recipients: int = Field(
        ...,
        ge=0,
        description="Total recipients",
    )
    total_delivered: int = Field(
        ...,
        ge=0,
        description="Total successfully delivered",
    )
    total_failed: int = Field(
        ...,
        ge=0,
        description="Total failed",
    )
    total_pending: int = Field(
        ...,
        ge=0,
        description="Total pending",
    )
    
    # By channel
    email_sent: int = Field(
        0,
        ge=0,
        description="Emails sent",
    )
    email_delivered: int = Field(
        0,
        ge=0,
        description="Emails delivered",
    )
    email_failed: int = Field(
        0,
        ge=0,
        description="Emails failed",
    )
    
    sms_sent: int = Field(
        0,
        ge=0,
        description="SMS sent",
    )
    sms_delivered: int = Field(
        0,
        ge=0,
        description="SMS delivered",
    )
    sms_failed: int = Field(
        0,
        ge=0,
        description="SMS failed",
    )
    
    push_sent: int = Field(
        0,
        ge=0,
        description="Push notifications sent",
    )
    push_delivered: int = Field(
        0,
        ge=0,
        description="Push notifications delivered",
    )
    push_failed: int = Field(
        0,
        ge=0,
        description="Push notifications failed",
    )
    
    in_app_sent: int = Field(
        0,
        ge=0,
        description="In-app notifications sent",
    )
    in_app_delivered: int = Field(
        0,
        ge=0,
        description="In-app notifications delivered",
    )
    
    # Rates
    delivery_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Overall delivery rate percentage",
    )
    
    # Timeline
    delivery_started_at: Optional[datetime] = Field(
        None,
        description="When delivery started",
    )
    delivery_completed_at: Optional[datetime] = Field(
        None,
        description="When delivery completed",
    )
    last_activity_at: Optional[datetime] = Field(
        None,
        description="Last delivery activity timestamp",
    )
    
    # Progress (for batched delivery)
    progress_percentage: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        Decimal("0"),
        description="Delivery progress percentage",
    )
    estimated_completion: Optional[datetime] = Field(
        None,
        description="Estimated completion time",
    )


class FailedDelivery(BaseSchema):
    """
    Failed delivery record for troubleshooting.
    
    Contains details about why delivery failed.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(
        ...,
        description="Failed delivery record UUID",
    )
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    
    # Recipient info
    recipient_id: UUID = Field(
        ...,
        description="Recipient student UUID",
    )
    recipient_name: str = Field(
        ...,
        description="Recipient name",
    )
    recipient_contact: str = Field(
        ...,
        description="Contact info used (email/phone)",
    )
    
    # Failure details
    channel: DeliveryChannel = Field(
        ...,
        description="Channel that failed",
    )
    failure_reason: str = Field(
        ...,
        description="Reason for failure",
    )
    failure_code: Optional[str] = Field(
        None,
        description="Error code if available",
    )
    failed_at: datetime = Field(
        ...,
        description="Failure timestamp",
    )
    
    # Retry info
    retry_count: int = Field(
        0,
        ge=0,
        description="Number of retry attempts",
    )
    retry_attempted: bool = Field(
        False,
        description="Whether retry was attempted",
    )
    retry_successful: Optional[bool] = Field(
        None,
        description="Whether retry succeeded",
    )
    last_retry_at: Optional[datetime] = Field(
        None,
        description="Last retry timestamp",
    )
    next_retry_at: Optional[datetime] = Field(
        None,
        description="Next scheduled retry",
    )
    
    # Resolution
    is_resolved: bool = Field(
        False,
        description="Whether issue is resolved",
    )
    resolution_notes: Optional[str] = Field(
        None,
        description="Resolution notes",
    )


class DeliveryReport(BaseSchema):
    """
    Comprehensive delivery report for announcement.
    
    Full analytics on delivery performance.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    title: str = Field(
        ...,
        description="Announcement title",
    )
    
    # Overall metrics
    total_recipients: int = Field(
        ...,
        ge=0,
        description="Total recipients",
    )
    delivered_count: int = Field(
        ...,
        ge=0,
        description="Successfully delivered",
    )
    failed_count: int = Field(
        ...,
        ge=0,
        description="Failed deliveries",
    )
    pending_count: int = Field(
        ...,
        ge=0,
        description="Pending deliveries",
    )
    
    # Rates
    overall_delivery_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Overall delivery success rate",
    )
    
    # By channel breakdown
    channel_breakdown: dict[str, ChannelDeliveryStats] = Field(
        default_factory=dict,
        description="Stats per delivery channel",
    )
    
    # Failed recipients (limited list)
    failed_recipients: list[FailedDelivery] = Field(
        default_factory=list,
        max_length=100,
        description="Failed delivery records (max 100)",
    )
    has_more_failures: bool = Field(
        False,
        description="Whether there are more failures not shown",
    )
    total_failures: int = Field(
        0,
        ge=0,
        description="Total number of failures",
    )
    
    # Timeline
    delivery_started_at: Optional[datetime] = Field(
        None,
        description="Delivery start time",
    )
    delivery_completed_at: Optional[datetime] = Field(
        None,
        description="Delivery completion time",
    )
    delivery_duration_minutes: Optional[int] = Field(
        None,
        ge=0,
        description="Total delivery duration in minutes",
    )
    
    # Report metadata
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp",
    )


class BatchDelivery(BaseSchema):
    """
    Batch delivery progress tracking.
    
    Shows progress of batched delivery operations.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    
    # Batch info
    total_batches: int = Field(
        ...,
        ge=1,
        description="Total number of batches",
    )
    completed_batches: int = Field(
        ...,
        ge=0,
        description="Completed batches",
    )
    current_batch: int = Field(
        ...,
        ge=0,
        description="Currently processing batch",
    )
    batch_size: int = Field(
        ...,
        ge=1,
        description="Recipients per batch",
    )
    
    # Recipient counts
    total_recipients: int = Field(
        ...,
        ge=0,
        description="Total recipients",
    )
    processed_recipients: int = Field(
        ...,
        ge=0,
        description="Recipients processed so far",
    )
    
    # Current batch stats
    current_batch_sent: int = Field(
        0,
        ge=0,
        description="Sent in current batch",
    )
    current_batch_failed: int = Field(
        0,
        ge=0,
        description="Failed in current batch",
    )
    
    # Timing
    started_at: datetime = Field(
        ...,
        description="Batch delivery start time",
    )
    estimated_completion: Optional[datetime] = Field(
        None,
        description="Estimated completion time",
    )
    
    # Status
    status: DeliveryState = Field(
        ...,
        description="Current batch delivery status",
    )
    
    # Control
    is_paused: bool = Field(
        False,
        description="Whether batch delivery is paused",
    )
    pause_reason: Optional[str] = Field(
        None,
        description="Reason for pause if paused",
    )


class RetryDelivery(BaseCreateSchema):
    """
    Retry failed deliveries for an announcement.
    
    Allows selective retry of failed delivery attempts.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    initiated_by: UUID = Field(
        ...,
        description="User initiating the retry",
    )
    
    # Retry scope
    retry_failed_only: bool = Field(
        True,
        description="Only retry failed deliveries",
    )
    retry_channels: list[DeliveryChannel] = Field(
        default_factory=list,
        description="Specific channels to retry (empty = all)",
    )
    
    # Specific recipients
    recipient_ids: Optional[list[UUID]] = Field(
        None,
        description="Retry specific recipients only",
    )
    
    # Retry settings
    max_retry_attempts: int = Field(
        1,
        ge=1,
        le=5,
        description="Maximum retry attempts (1-5)",
    )
    use_fallback_channels: bool = Field(
        True,
        description="Use fallback channels if primary fails again",
    )
    
    # Timing
    delay_minutes: int = Field(
        0,
        ge=0,
        le=60,
        description="Delay before starting retry (0-60 minutes)",
    )
    
    @field_validator("recipient_ids")
    @classmethod
    def validate_recipient_ids(
        cls, v: Optional[list[UUID]]
    ) -> Optional[list[UUID]]:
        """Ensure recipient IDs are unique."""
        if v:
            if len(v) != len(set(v)):
                raise ValueError("Duplicate recipient IDs not allowed")
            if len(v) > 1000:
                raise ValueError("Maximum 1000 recipients per retry request")
        return v


class DeliveryPause(BaseCreateSchema):
    """
    Pause ongoing delivery.
    
    Temporarily stops batch delivery processing.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    paused_by: UUID = Field(
        ...,
        description="User pausing delivery",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for pausing (10-500 chars)",
    )
    
    # Resume settings
    auto_resume: bool = Field(
        False,
        description="Automatically resume after duration",
    )
    resume_after_minutes: Optional[int] = Field(
        None,
        ge=5,
        le=1440,
        description="Minutes until auto-resume (5-1440)",
    )
    
    @model_validator(mode="after")
    def validate_auto_resume(self) -> "DeliveryPause":
        """Validate auto-resume settings."""
        if self.auto_resume and not self.resume_after_minutes:
            raise ValueError(
                "resume_after_minutes required when auto_resume is True"
            )
        return self


class DeliveryResume(BaseCreateSchema):
    """
    Resume paused delivery.
    
    Continues batch delivery from where it stopped.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    resumed_by: UUID = Field(
        ...,
        description="User resuming delivery",
    )
    
    # Resume options
    skip_failed: bool = Field(
        False,
        description="Skip previously failed recipients",
    )
    restart_current_batch: bool = Field(
        False,
        description="Restart current batch from beginning",
    )