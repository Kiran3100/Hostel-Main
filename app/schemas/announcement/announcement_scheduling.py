# --- File: app/schemas/announcement/announcement_scheduling.py ---
"""
Announcement scheduling schemas.

This module defines schemas for scheduling announcements,
including one-time and recurring schedules.
"""

from datetime import datetime, time
from enum import Enum
from typing import Optional, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import TargetAudience

__all__ = [
    "RecurrencePattern",
    "ScheduleStatus",
    "ScheduleRequest",
    "ScheduleConfig",
    "RecurringAnnouncement",
    "ScheduleUpdate",
    "ScheduleCancel",
    "PublishNow",
    "ScheduledAnnouncementsList",
    "ScheduledAnnouncementItem",
]


class RecurrencePattern(str, Enum):
    """Recurrence pattern enumeration."""
    
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class ScheduleStatus(str, Enum):
    """Schedule status enumeration."""
    
    PENDING = "pending"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ScheduleRequest(BaseCreateSchema):
    """
    Schedule an announcement for later publication.
    
    Allows setting publication time and optional auto-expiry.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="UUID of the announcement to schedule",
    )
    scheduled_by: UUID = Field(
        ...,
        description="UUID of user scheduling the announcement",
    )
    
    scheduled_publish_at: datetime = Field(
        ...,
        description="When to publish the announcement",
    )
    
    # Auto-expire settings
    auto_expire: bool = Field(
        False,
        description="Automatically expire after specified duration",
    )
    expire_after_hours: Union[int, None] = Field(
        None,
        ge=1,
        le=720,  # Max 30 days
        description="Hours after publication to auto-expire (1-720)",
    )
    
    # Timezone handling
    timezone: str = Field(
        "Asia/Kolkata",
        description="Timezone for scheduled time",
    )
    
    @field_validator("scheduled_publish_at")
    @classmethod
    def validate_future_time(cls, v: datetime) -> datetime:
        """Ensure scheduled time is in the future."""
        if v <= datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")
        return v
    
    @model_validator(mode="after")
    def validate_expiry_settings(self) -> "ScheduleRequest":
        """Validate auto-expiry configuration."""
        if self.auto_expire and not self.expire_after_hours:
            raise ValueError(
                "expire_after_hours required when auto_expire is True"
            )
        return self


class ScheduleConfig(BaseSchema):
    """
    Complete schedule configuration for announcement.
    
    Shows current scheduling state including recurrence settings.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    
    # Basic schedule
    is_scheduled: bool = Field(
        ...,
        description="Whether announcement is scheduled",
    )
    scheduled_publish_at: Union[datetime, None] = Field(
        None,
        description="Scheduled publication time",
    )
    schedule_status: ScheduleStatus = Field(
        ...,
        description="Current schedule status",
    )
    
    # Recurrence
    is_recurring: bool = Field(
        False,
        description="Whether this is a recurring announcement",
    )
    recurrence_pattern: Union[RecurrencePattern, None] = Field(
        None,
        description="Recurrence pattern if recurring",
    )
    
    # End conditions
    recurrence_end_date: Union[datetime, None] = Field(
        None,
        description="When recurrence ends",
    )
    max_occurrences: Union[int, None] = Field(
        None,
        ge=1,
        description="Maximum number of occurrences",
    )
    occurrences_completed: int = Field(
        0,
        ge=0,
        description="Occurrences already published",
    )
    
    # Next occurrence
    next_publish_at: Union[datetime, None] = Field(
        None,
        description="Next scheduled publication time",
    )
    
    # Audit
    scheduled_by: Union[UUID, None] = Field(
        None,
        description="User who created the schedule",
    )
    scheduled_at: Union[datetime, None] = Field(
        None,
        description="When schedule was created",
    )


class RecurringAnnouncement(BaseCreateSchema):
    """
    Create a recurring announcement.
    
    Announcements will be automatically published according
    to the recurrence pattern.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    hostel_id: UUID = Field(
        ...,
        description="Hostel UUID",
    )
    created_by: UUID = Field(
        ...,
        description="Creator UUID",
    )
    
    # Content
    title: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Announcement title",
    )
    content: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Announcement content",
    )
    
    # Recurrence settings
    recurrence_pattern: RecurrencePattern = Field(
        ...,
        description="How often to publish",
    )
    start_date: datetime = Field(
        ...,
        description="When to start recurring publications",
    )
    
    # End conditions (at least one required)
    end_date: Union[datetime, None] = Field(
        None,
        description="When to stop recurring publications",
    )
    max_occurrences: Union[int, None] = Field(
        None,
        ge=1,
        le=365,
        description="Maximum number of publications (1-365)",
    )
    
    # Weekly recurrence options
    weekdays: Union[list[int], None] = Field(
        None,
        description="Days of week for weekly recurrence (0=Monday, 6=Sunday)",
    )
    
    # Time settings
    publish_time: time = Field(
        ...,
        description="Time of day to publish (HH:MM)",
    )
    timezone: str = Field(
        "Asia/Kolkata",
        description="Timezone for publish time",
    )
    
    # Targeting
    target_audience: TargetAudience = Field(
        TargetAudience.ALL,
        description="Target audience",
    )
    target_room_ids: list[UUID] = Field(
        default_factory=list,
        description="Specific room UUIDs",
    )
    target_floor_numbers: list[int] = Field(
        default_factory=list,
        description="Specific floor numbers",
    )
    
    # Delivery
    send_push: bool = Field(
        True,
        description="Send push notifications",
    )
    send_email: bool = Field(
        False,
        description="Send email notifications",
    )
    
    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v: datetime) -> datetime:
        """Ensure start date is in the future."""
        if v <= datetime.utcnow():
            raise ValueError("Start date must be in the future")
        return v
    
    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: Union[datetime, None], info) -> Union[datetime, None]:
        """Ensure end date is after start date."""
        start_date = info.data.get("start_date")
        if v and start_date and v <= start_date:
            raise ValueError("End date must be after start date")
        return v
    
    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, v: Union[list[int], None]) -> Union[list[int], None]:
        """Validate weekday values."""
        if v:
            if any(d < 0 or d > 6 for d in v):
                raise ValueError("Weekdays must be 0-6 (Monday-Sunday)")
            return sorted(set(v))
        return v
    
    @model_validator(mode="after")
    def validate_end_condition(self) -> "RecurringAnnouncement":
        """Ensure at least one end condition is specified."""
        if not self.end_date and not self.max_occurrences:
            raise ValueError(
                "Either end_date or max_occurrences must be specified"
            )
        return self
    
    @model_validator(mode="after")
    def validate_weekly_days(self) -> "RecurringAnnouncement":
        """Validate weekdays for weekly recurrence."""
        if self.recurrence_pattern == RecurrencePattern.WEEKLY:
            if not self.weekdays:
                raise ValueError(
                    "weekdays required for weekly recurrence pattern"
                )
        return self


class ScheduleUpdate(BaseCreateSchema):
    """
    Update scheduled announcement timing.
    
    Reschedule a pending announcement to a new time.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    updated_by: UUID = Field(
        ...,
        description="User making the update",
    )
    
    new_scheduled_time: datetime = Field(
        ...,
        description="New scheduled publication time",
    )
    
    reason: Union[str, None] = Field(
        None,
        max_length=500,
        description="Reason for rescheduling",
    )
    
    @field_validator("new_scheduled_time")
    @classmethod
    def validate_future_time(cls, v: datetime) -> datetime:
        """Ensure new time is in the future."""
        if v <= datetime.utcnow():
            raise ValueError("New scheduled time must be in the future")
        return v


class ScheduleCancel(BaseCreateSchema):
    """
    Cancel a scheduled announcement.
    
    Prevents publication of a scheduled announcement.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    cancelled_by: UUID = Field(
        ...,
        description="User cancelling the schedule",
    )
    
    cancellation_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for cancellation (10-500 chars)",
    )
    
    # What to do with the announcement
    delete_announcement: bool = Field(
        False,
        description="Delete the announcement entirely (vs keeping as draft)",
    )
    
    # For recurring announcements
    cancel_all_future: bool = Field(
        True,
        description="Cancel all future occurrences (for recurring)",
    )


class PublishNow(BaseCreateSchema):
    """
    Publish a scheduled announcement immediately.
    
    Overrides the scheduled time and publishes now.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    published_by: UUID = Field(
        ...,
        description="User publishing the announcement",
    )
    
    override_schedule: bool = Field(
        True,
        description="Confirm override of existing schedule",
    )
    
    reason: Union[str, None] = Field(
        None,
        max_length=500,
        description="Reason for immediate publication",
    )


class ScheduledAnnouncementItem(BaseSchema):
    """
    Scheduled announcement list item.
    
    Lightweight representation for scheduled announcement lists.
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
    scheduled_for: datetime = Field(
        ...,
        description="Scheduled publication time",
    )
    
    # Recurrence info
    is_recurring: bool = Field(
        ...,
        description="Whether recurring",
    )
    recurrence_pattern: Union[RecurrencePattern, None] = Field(
        None,
        description="Recurrence pattern",
    )
    next_occurrence: Union[datetime, None] = Field(
        None,
        description="Next occurrence after this one",
    )
    occurrences_remaining: Union[int, None] = Field(
        None,
        description="Remaining occurrences",
    )
    
    # Targeting summary
    target_audience: TargetAudience = Field(
        ...,
        description="Target audience",
    )
    estimated_recipients: int = Field(
        ...,
        ge=0,
        description="Estimated recipient count",
    )
    
    # Creator
    created_by_name: str = Field(
        ...,
        description="Creator name",
    )
    
    # Status
    schedule_status: ScheduleStatus = Field(
        ...,
        description="Current schedule status",
    )


class ScheduledAnnouncementsList(BaseSchema):
    """
    List of scheduled announcements.
    
    Includes summary statistics for the schedule queue.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    hostel_id: UUID = Field(
        ...,
        description="Hostel UUID",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    
    # Counts
    total_scheduled: int = Field(
        ...,
        ge=0,
        description="Total scheduled announcements",
    )
    upcoming_24h: int = Field(
        ...,
        ge=0,
        description="Announcements scheduled within 24 hours",
    )
    recurring_count: int = Field(
        ...,
        ge=0,
        description="Number of recurring announcements",
    )
    
    # Items
    announcements: list[ScheduledAnnouncementItem] = Field(
        default_factory=list,
        description="Scheduled announcements",
    )
    
    # Next publication
    next_scheduled: Union[datetime, None] = Field(
        None,
        description="Next scheduled publication time",
    )