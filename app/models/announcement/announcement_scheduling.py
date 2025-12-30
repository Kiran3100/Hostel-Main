# --- File: app/models/announcement/announcement_scheduling.py ---
"""
Announcement scheduling models.

This module defines models for scheduling announcements,
including one-time and recurring schedules.
"""

from datetime import datetime, time
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
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
    "AnnouncementSchedule",
    "RecurringAnnouncement",
    "ScheduleExecution",
    "PublishQueue",
]


class RecurrencePattern:
    """Recurrence pattern enumeration."""
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class ScheduleStatus:
    """Schedule status enumeration."""
    PENDING = "pending"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    FAILED = "failed"


class AnnouncementSchedule(UUIDMixin, TimestampModel, BaseModel):
    """
    Announcement scheduling configuration.
    
    Manages scheduled publication of announcements including
    one-time and recurring schedules.
    """
    
    __tablename__ = "announcement_schedules"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
        comment="Associated announcement",
    )
    scheduled_by_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who scheduled the announcement",
    )
    
    # Schedule Configuration
    scheduled_publish_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When to publish the announcement",
    )
    
    # Timezone Handling
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="UTC",
        comment="Timezone for scheduled time",
    )
    
    # Auto-Expire Settings
    auto_expire: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Automatically expire after specified duration",
    )
    expire_after_hours: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Hours after publication to auto-expire",
    )
    calculated_expire_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Calculated expiry datetime",
    )
    
    # Recurrence Settings
    is_recurring: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether this is a recurring announcement",
    )
    recurrence_pattern: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Recurrence pattern (daily, weekly, monthly)",
    )
    recurrence_end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When recurrence ends",
    )
    max_occurrences: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum number of occurrences",
    )
    occurrences_completed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Occurrences already published",
    )
    
    # Next Occurrence
    next_publish_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Next scheduled publication time",
    )
    
    # Schedule Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ScheduleStatus.PENDING,
        index=True,
        comment="Current schedule status",
    )
    
    # Execution Tracking
    last_executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When schedule was last executed",
    )
    execution_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times schedule has executed",
    )
    
    # Failure Handling
    failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of failed execution attempts",
    )
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When last failure occurred",
    )
    last_failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for last failure",
    )
    
    # Cancellation
    is_cancelled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether schedule has been cancelled",
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When schedule was cancelled",
    )
    cancelled_by_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who cancelled the schedule",
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for cancellation",
    )
    
    # Metadata
    meta_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional scheduling metadata",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        back_populates="schedules",
    )
    scheduled_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[scheduled_by_id],
        lazy="select",
    )
    cancelled_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[cancelled_by_id],
        lazy="select",
    )
    executions: Mapped[List["ScheduleExecution"]] = relationship(
        "ScheduleExecution",
        back_populates="schedule",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="ScheduleExecution.executed_at.desc()",
    )
    
    __table_args__ = (
        Index("ix_announcement_schedules_announcement", "announcement_id"),
        Index("ix_announcement_schedules_next_publish", "next_publish_at"),
        Index("ix_announcement_schedules_status", "status"),
        Index("ix_announcement_schedules_pending", "status", "next_publish_at"),
        CheckConstraint(
            "(auto_expire = FALSE) OR "
            "(auto_expire = TRUE AND expire_after_hours IS NOT NULL AND expire_after_hours > 0)",
            name="ck_announcement_schedules_auto_expire",
        ),
        CheckConstraint(
            "(is_recurring = FALSE) OR "
            "(is_recurring = TRUE AND recurrence_pattern IS NOT NULL)",
            name="ck_announcement_schedules_recurrence_pattern",
        ),
        CheckConstraint(
            "(is_recurring = FALSE) OR "
            "(is_recurring = TRUE AND (recurrence_end_date IS NOT NULL OR max_occurrences IS NOT NULL))",
            name="ck_announcement_schedules_recurrence_end",
        ),
        CheckConstraint(
            "occurrences_completed >= 0",
            name="ck_announcement_schedules_occurrences_positive",
        ),
        CheckConstraint(
            "execution_count >= 0",
            name="ck_announcement_schedules_execution_count_positive",
        ),
        CheckConstraint(
            "failure_count >= 0",
            name="ck_announcement_schedules_failure_count_positive",
        ),
        CheckConstraint(
            "status IN ('pending', 'published', 'cancelled', 'failed')",
            name="ck_announcement_schedules_status_valid",
        ),
        {"comment": "Announcement scheduling configuration"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<AnnouncementSchedule(id={self.id}, announcement_id={self.announcement_id}, "
            f"publish_at={self.scheduled_publish_at}, status={self.status})>"
        )


class RecurringAnnouncement(UUIDMixin, TimestampModel, BaseModel):
    """
    Recurring announcement template.
    
    Stores templates for announcements that should be published
    automatically on a recurring basis.
    """
    
    __tablename__ = "recurring_announcements"
    
    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated hostel",
    )
    created_by_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created the recurring announcement",
    )
    
    # Template Content
    title_template: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Announcement title template",
    )
    content_template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Announcement content template",
    )
    
    # Recurrence Configuration
    recurrence_pattern: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Recurrence pattern (daily, weekly, monthly)",
    )
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When to start recurring publications",
    )
    end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When to stop recurring publications",
    )
    max_occurrences: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum number of publications",
    )
    
    # Weekly Recurrence Options
    weekdays: Mapped[Optional[List[int]]] = mapped_column(
        ARRAY(Integer),
        nullable=True,
        comment="Days of week for weekly recurrence (0=Monday, 6=Sunday)",
    )
    
    # Time Settings
    publish_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        comment="Time of day to publish",
    )
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="UTC",
        comment="Timezone for publish time",
    )
    
    # Targeting
    target_audience: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="all",
        comment="Target audience type",
    )
    target_room_ids: Mapped[Optional[List[UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="Specific room UUIDs",
    )
    target_floor_numbers: Mapped[Optional[List[int]]] = mapped_column(
        ARRAY(Integer),
        nullable=True,
        comment="Specific floor numbers",
    )
    
    # Delivery Settings
    send_push: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Send push notifications",
    )
    send_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Send email notifications",
    )
    send_sms: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Send SMS notifications",
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether recurring announcement is active",
    )
    is_paused: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether recurring announcement is paused",
    )
    paused_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When recurring announcement was paused",
    )
    
    # Tracking
    last_published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When last occurrence was published",
    )
    next_publish_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Next scheduled publication time",
    )
    total_published: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of announcements published",
    )
    
    # Generated Announcements
    generated_announcement_ids: Mapped[Optional[List[UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="IDs of announcements generated from this template",
    )
    
    # Metadata
    meta_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata",
    )
    
    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        lazy="select",
    )
    
    __table_args__ = (
        Index("ix_recurring_announcements_hostel", "hostel_id"),
        Index("ix_recurring_announcements_active", "is_active"),
        Index("ix_recurring_announcements_next_publish", "next_publish_at"),
        Index("ix_recurring_announcements_pattern", "recurrence_pattern"),
        CheckConstraint(
            "total_published >= 0",
            name="ck_recurring_announcements_published_count",
        ),
        CheckConstraint(
            "(end_date IS NULL) OR (end_date > start_date)",
            name="ck_recurring_announcements_date_range",
        ),
        CheckConstraint(
            "recurrence_pattern IN ('daily', 'weekly', 'biweekly', 'monthly')",
            name="ck_recurring_announcements_pattern_valid",
        ),
        {"comment": "Recurring announcement templates"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<RecurringAnnouncement(id={self.id}, hostel_id={self.hostel_id}, "
            f"pattern={self.recurrence_pattern}, active={self.is_active})>"
        )


class ScheduleExecution(UUIDMixin, TimestampModel, BaseModel):
    """
    Schedule execution tracking.
    
    Records each execution attempt of a scheduled announcement
    for monitoring and debugging.
    """
    
    __tablename__ = "announcement_schedule_executions"
    
    # Foreign Keys
    schedule_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcement_schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated schedule",
    )
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated announcement",
    )
    
    # Execution Details
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When execution was scheduled",
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When execution actually occurred",
    )
    
    # Execution Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Execution status (success, failed, skipped)",
    )
    
    # Success Details
    published: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether announcement was successfully published",
    )
    recipients_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of recipients for this execution",
    )
    
    # Failure Details
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if execution failed",
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Error code if execution failed",
    )
    error_details: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed error information",
    )
    
    # Retry Information
    is_retry: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is a retry attempt",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of retry attempts",
    )
    parent_execution_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcement_schedule_executions.id", ondelete="SET NULL"),
        nullable=True,
        comment="Original execution if this is a retry",
    )
    
    # Performance Metrics
    execution_duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Execution duration in milliseconds",
    )
    
    # Metadata
    meta_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional execution metadata",
    )
    
    # Relationships
    schedule: Mapped["AnnouncementSchedule"] = relationship(
        "AnnouncementSchedule",
        back_populates="executions",
    )
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        lazy="select",
    )
    parent_execution: Mapped[Optional["ScheduleExecution"]] = relationship(
        "ScheduleExecution",
        remote_side="ScheduleExecution.id",
        lazy="select",
    )
    
    __table_args__ = (
        Index("ix_schedule_executions_schedule", "schedule_id"),
        Index("ix_schedule_executions_announcement", "announcement_id"),
        Index("ix_schedule_executions_executed_at", "executed_at"),
        Index("ix_schedule_executions_status", "status"),
        CheckConstraint(
            "recipients_count >= 0",
            name="ck_schedule_executions_recipients_count",
        ),
        CheckConstraint(
            "retry_count >= 0",
            name="ck_schedule_executions_retry_count",
        ),
        CheckConstraint(
            "status IN ('success', 'failed', 'skipped')",
            name="ck_schedule_executions_status_valid",
        ),
        {"comment": "Schedule execution tracking"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<ScheduleExecution(id={self.id}, schedule_id={self.schedule_id}, "
            f"status={self.status}, executed_at={self.executed_at})>"
        )


class PublishQueue(UUIDMixin, TimestampModel, BaseModel):
    """
    Publication queue for batch processing.
    
    Manages the queue of announcements waiting to be published.
    """
    
    __tablename__ = "announcement_publish_queue"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
        comment="Associated announcement",
    )
    schedule_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcement_schedules.id", ondelete="SET NULL"),
        nullable=True,
        comment="Associated schedule if scheduled",
    )
    
    # Queue Details
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When announcement was queued",
    )
    scheduled_publish_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When announcement should be published",
    )
    
    # Priority
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        comment="Queue priority (higher = more urgent)",
    )
    is_urgent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether this is an urgent publication",
    )
    
    # Processing Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Queue processing status",
    )
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When processing started",
    )
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When processing completed",
    )
    
    # Worker Assignment
    worker_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="ID of worker processing this item",
    )
    lock_acquired_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When worker lock was acquired",
    )
    lock_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When worker lock expires",
    )
    
    # Retry Handling
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of processing attempts",
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Maximum retry attempts",
    )
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When to retry if failed",
    )
    
    # Failure Details
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Last error message",
    )
    error_history: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="History of errors",
    )
    
    # Metadata
    meta_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional queue metadata",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        lazy="select",
    )
    schedule: Mapped[Optional["AnnouncementSchedule"]] = relationship(
        "AnnouncementSchedule",
        lazy="select",
    )
    
    __table_args__ = (
        Index("ix_publish_queue_announcement", "announcement_id"),
        Index("ix_publish_queue_scheduled_publish", "scheduled_publish_at"),
        Index("ix_publish_queue_status", "status"),
        Index("ix_publish_queue_priority", "priority", postgresql_using="btree"),
        Index("ix_publish_queue_urgent", "is_urgent", "scheduled_publish_at"),
        Index("ix_publish_queue_pending", "status", "scheduled_publish_at"),
        Index("ix_publish_queue_lock_expires", "lock_expires_at"),
        Index("ix_publish_queue_next_retry", "next_retry_at"),
        CheckConstraint(
            "retry_count >= 0",
            name="ck_publish_queue_retry_count",
        ),
        CheckConstraint(
            "max_retries >= 0",
            name="ck_publish_queue_max_retries",
        ),
        CheckConstraint(
            "retry_count <= max_retries",
            name="ck_publish_queue_retry_limit",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')",
            name="ck_publish_queue_status_valid",
        ),
        {"comment": "Publication queue for batch processing"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<PublishQueue(id={self.id}, announcement_id={self.announcement_id}, "
            f"status={self.status}, scheduled_at={self.scheduled_publish_at})>"
        )