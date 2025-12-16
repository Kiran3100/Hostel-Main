# --- File: app/schemas/announcement/announcement_tracking.py ---
"""
Announcement tracking and engagement schemas.

This module defines schemas for tracking read receipts,
acknowledgments, and engagement metrics.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Optional, Union
from uuid import UUID

from pydantic import Field, computed_field, field_validator, ConfigDict

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseSchema,
)

__all__ = [
    "DeviceType",
    "ReadReceipt",
    "ReadReceiptResponse",
    "AcknowledgmentRequest",
    "AcknowledgmentResponse",
    "AcknowledgmentTracking",
    "PendingAcknowledgment",
    "EngagementMetrics",
    "ReadingTime",
    "AnnouncementAnalytics",
    "StudentEngagement",
    "EngagementTrend",
]


class DeviceType(str, Enum):
    """Device type enumeration."""
    
    MOBILE = "mobile"
    WEB = "web"
    TABLET = "tablet"
    DESKTOP = "desktop"


class ReadReceipt(BaseCreateSchema):
    """
    Mark announcement as read by student.
    
    Records when and how a student viewed the announcement.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    student_id: UUID = Field(
        ...,
        description="Student UUID who read the announcement",
    )
    
    read_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the announcement was read",
    )
    
    # Reading context
    reading_time_seconds: Union[int, None] = Field(
        None,
        ge=0,
        le=3600,
        description="Time spent reading in seconds (max 1 hour)",
    )
    device_type: Union[DeviceType, None] = Field(
        None,
        description="Device used to read",
    )
    
    # Scroll tracking (for long announcements)
    scroll_percentage: Union[int, None] = Field(
        None,
        ge=0,
        le=100,
        description="How far user scrolled (0-100%)",
    )
    
    # Source
    source: str = Field(
        "app",
        pattern=r"^(app|email|push_notification|web)$",
        description="How user accessed the announcement",
    )


class ReadReceiptResponse(BaseResponseSchema):
    """
    Response after recording read receipt.
    
    Confirms the read was recorded and indicates next actions.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    student_id: UUID = Field(
        ...,
        description="Student UUID",
    )
    read_at: datetime = Field(
        ...,
        description="Read timestamp",
    )
    
    # If acknowledgment is required
    requires_acknowledgment: bool = Field(
        ...,
        description="Whether acknowledgment is required",
    )
    acknowledged: bool = Field(
        ...,
        description="Whether already acknowledged",
    )
    acknowledgment_deadline: Union[datetime, None] = Field(
        None,
        description="Deadline for acknowledgment if required",
    )
    
    # Message
    message: str = Field(
        ...,
        description="Response message",
    )


class AcknowledgmentRequest(BaseCreateSchema):
    """
    Submit acknowledgment for announcement.
    
    Confirms student has read and understood the announcement.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    student_id: UUID = Field(
        ...,
        description="Student UUID",
    )
    
    acknowledged: bool = Field(
        True,
        description="Acknowledgment confirmation",
    )
    acknowledgment_note: Union[str, None] = Field(
        None,
        max_length=500,
        description="Optional note from student",
    )
    
    # For announcements requiring specific action
    action_taken: Union[str, None] = Field(
        None,
        max_length=500,
        description="Description of action taken if required",
    )


class AcknowledgmentResponse(BaseResponseSchema):
    """
    Response after acknowledgment submission.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    student_id: UUID = Field(
        ...,
        description="Student UUID",
    )
    acknowledged_at: datetime = Field(
        ...,
        description="Acknowledgment timestamp",
    )
    
    # Status
    on_time: bool = Field(
        ...,
        description="Whether acknowledged before deadline",
    )
    message: str = Field(
        ...,
        description="Response message",
    )


class PendingAcknowledgment(BaseSchema):
    """
    Student pending acknowledgment record.
    
    Used in lists of students who haven't acknowledged.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    student_id: UUID = Field(
        ...,
        description="Student UUID",
    )
    student_name: str = Field(
        ...,
        description="Student name",
    )
    room_number: Union[str, None] = Field(
        None,
        description="Room number",
    )
    floor_number: Union[int, None] = Field(
        None,
        description="Floor number",
    )
    
    # Delivery info
    delivered_at: datetime = Field(
        ...,
        description="When notification was delivered",
    )
    delivery_channel: str = Field(
        ...,
        description="Channel used for delivery",
    )
    
    # Read status
    is_read: bool = Field(
        ...,
        description="Whether announcement was read",
    )
    read_at: Union[datetime, None] = Field(
        None,
        description="When announcement was read",
    )
    
    # Contact info for follow-up
    phone: Union[str, None] = Field(
        None,
        description="Student phone for follow-up",
    )
    email: Union[str, None] = Field(
        None,
        description="Student email for follow-up",
    )
    
    @computed_field
    @property
    def hours_since_delivery(self) -> float:
        """Hours since delivery."""
        delta = datetime.utcnow() - self.delivered_at
        return round(delta.total_seconds() / 3600, 2)


class AcknowledgmentTracking(BaseSchema):
    """
    Complete acknowledgment tracking for announcement.
    
    Overview of acknowledgment status and pending students.
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
    
    # Requirement
    requires_acknowledgment: bool = Field(
        ...,
        description="Whether acknowledgment is required",
    )
    acknowledgment_deadline: Union[datetime, None] = Field(
        None,
        description="Acknowledgment deadline",
    )
    
    # Counts
    total_recipients: int = Field(
        ...,
        ge=0,
        description="Total recipients",
    )
    acknowledged_count: int = Field(
        ...,
        ge=0,
        description="Number who acknowledged",
    )
    pending_acknowledgments: int = Field(
        ...,
        ge=0,
        description="Number pending acknowledgment",
    )
    
    # On-time tracking
    on_time_count: int = Field(
        0,
        ge=0,
        description="Acknowledged before deadline",
    )
    late_count: int = Field(
        0,
        ge=0,
        description="Acknowledged after deadline",
    )
    
    # Rates
    acknowledgment_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Acknowledgment rate percentage",
    )
    
    # Pending students list
    pending_students: list[PendingAcknowledgment] = Field(
        default_factory=list,
        description="Students pending acknowledgment",
    )
    
    # Time tracking
    average_time_to_acknowledge_hours: Union[Annotated[Decimal, Field(ge=0)], None] = Field(
        None,
        description="Average hours to acknowledge",
    )
    
    @computed_field
    @property
    def is_deadline_passed(self) -> bool:
        """Check if acknowledgment deadline has passed."""
        if self.acknowledgment_deadline is None:
            return False
        return datetime.utcnow() > self.acknowledgment_deadline
    
    @computed_field
    @property
    def hours_until_deadline(self) -> Union[float, None]:
        """Hours remaining until deadline."""
        if self.acknowledgment_deadline is None:
            return None
        delta = self.acknowledgment_deadline - datetime.utcnow()
        hours = delta.total_seconds() / 3600
        return round(max(0, hours), 2)


class EngagementMetrics(BaseSchema):
    """
    Comprehensive engagement metrics for announcement.
    
    Measures how recipients interacted with the announcement.
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
    published_at: datetime = Field(
        ...,
        description="Publication timestamp",
    )
    
    # Delivery metrics
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
    delivery_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Delivery rate percentage",
    )
    
    # Reading metrics
    read_count: int = Field(
        ...,
        ge=0,
        description="Number who read",
    )
    read_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Read rate percentage",
    )
    
    # Reading depth
    average_reading_time_seconds: Union[Annotated[Decimal, Field(ge=0)], None] = Field(
        None,
        description="Average reading time",
    )
    average_scroll_percentage: Union[Annotated[Decimal, Field(ge=0, le=100)], None] = Field(
        None,
        description="Average scroll depth",
    )
    
    # Acknowledgment metrics
    requires_acknowledgment: bool = Field(
        ...,
        description="Whether acknowledgment required",
    )
    acknowledged_count: int = Field(
        0,
        ge=0,
        description="Number who acknowledged",
    )
    acknowledgment_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        Decimal("0"),
        description="Acknowledgment rate percentage",
    )
    
    # Timing metrics
    average_time_to_read_hours: Union[Annotated[Decimal, Field(ge=0)], None] = Field(
        None,
        description="Average hours from delivery to read",
    )
    average_time_to_acknowledge_hours: Union[Annotated[Decimal, Field(ge=0)], None] = Field(
        None,
        description="Average hours from delivery to acknowledge",
    )
    
    # Engagement score
    engagement_score: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Overall engagement score (0-100)",
    )
    
    # Comparison
    is_above_average: Union[bool, None] = Field(
        None,
        description="Whether engagement is above hostel average",
    )
    hostel_average_engagement: Union[Annotated[Decimal, Field(ge=0, le=100)], None] = Field(
        None,
        description="Hostel average engagement score",
    )


class ReadingTime(BaseSchema):
    """
    Reading time analytics for announcement.
    
    Detailed analysis of how long recipients spent reading.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    
    # Basic stats
    total_readers: int = Field(
        ...,
        ge=0,
        description="Number of readers with time data",
    )
    
    # Statistics
    average_reading_time_seconds: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Average reading time",
    )
    median_reading_time_seconds: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Median reading time",
    )
    min_reading_time_seconds: int = Field(
        ...,
        ge=0,
        description="Minimum reading time",
    )
    max_reading_time_seconds: int = Field(
        ...,
        ge=0,
        description="Maximum reading time",
    )
    
    # Distribution
    quick_readers: int = Field(
        ...,
        ge=0,
        description="Read in < 30 seconds",
    )
    normal_readers: int = Field(
        ...,
        ge=0,
        description="Read in 30-120 seconds",
    )
    thorough_readers: int = Field(
        ...,
        ge=0,
        description="Read in > 120 seconds",
    )
    
    # Percentages
    quick_readers_percentage: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Percentage of quick readers",
    )
    normal_readers_percentage: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Percentage of normal readers",
    )
    thorough_readers_percentage: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Percentage of thorough readers",
    )


class StudentEngagement(BaseSchema):
    """
    Individual student engagement record.
    
    Tracks a specific student's interaction with announcement.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    student_id: UUID = Field(
        ...,
        description="Student UUID",
    )
    student_name: str = Field(
        ...,
        description="Student name",
    )
    room_number: Union[str, None] = Field(
        None,
        description="Room number",
    )
    
    # Delivery
    delivered_at: Union[datetime, None] = Field(
        None,
        description="Delivery timestamp",
    )
    delivery_channel: Union[str, None] = Field(
        None,
        description="Delivery channel used",
    )
    
    # Reading
    is_read: bool = Field(
        ...,
        description="Whether read",
    )
    read_at: Union[datetime, None] = Field(
        None,
        description="Read timestamp",
    )
    reading_time_seconds: Union[int, None] = Field(
        None,
        description="Time spent reading",
    )
    device_type: Union[DeviceType, None] = Field(
        None,
        description="Device used",
    )
    
    # Acknowledgment
    is_acknowledged: bool = Field(
        False,
        description="Whether acknowledged",
    )
    acknowledged_at: Union[datetime, None] = Field(
        None,
        description="Acknowledgment timestamp",
    )
    acknowledgment_note: Union[str, None] = Field(
        None,
        description="Student's acknowledgment note",
    )
    
    @computed_field
    @property
    def time_to_read_hours(self) -> Union[float, None]:
        """Hours from delivery to read."""
        if self.delivered_at and self.read_at:
            delta = self.read_at - self.delivered_at
            return round(delta.total_seconds() / 3600, 2)
        return None


class EngagementTrend(BaseSchema):
    """
    Engagement trend over time.
    
    Shows how engagement changed over the announcement lifecycle.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    
    # Time range
    period_start: datetime = Field(
        ...,
        description="Analysis period start",
    )
    period_end: datetime = Field(
        ...,
        description="Analysis period end",
    )
    
    # Trend data
    reads_by_hour: dict[str, int] = Field(
        default_factory=dict,
        description="Reads per hour (ISO hour string -> count)",
    )
    reads_by_day: dict[str, int] = Field(
        default_factory=dict,
        description="Reads per day (ISO date string -> count)",
    )
    acknowledgments_by_hour: dict[str, int] = Field(
        default_factory=dict,
        description="Acknowledgments per hour",
    )
    
    # Peak times
    peak_reading_hour: Union[str, None] = Field(
        None,
        description="Hour with most reads",
    )
    peak_reading_day: Union[str, None] = Field(
        None,
        description="Day with most reads",
    )
    
    # Device breakdown
    reads_by_device: dict[str, int] = Field(
        default_factory=dict,
        description="Reads by device type",
    )
    
    # Source breakdown
    reads_by_source: dict[str, int] = Field(
        default_factory=dict,
        description="Reads by access source",
    )


class AnnouncementAnalytics(BaseSchema):
    """
    Complete analytics dashboard for announcement.
    
    Comprehensive view combining all metrics.
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
    published_at: datetime = Field(
        ...,
        description="Publication timestamp",
    )
    
    # Core metrics
    engagement_metrics: EngagementMetrics = Field(
        ...,
        description="Engagement metrics",
    )
    
    # Reading patterns
    reading_time: ReadingTime = Field(
        ...,
        description="Reading time analytics",
    )
    
    # Trends
    engagement_trend: EngagementTrend = Field(
        ...,
        description="Engagement over time",
    )
    
    # Acknowledgment (if applicable)
    acknowledgment_tracking: Union[AcknowledgmentTracking, None] = Field(
        None,
        description="Acknowledgment tracking if required",
    )
    
    # Top engaged students (for recognition)
    fastest_readers: list[StudentEngagement] = Field(
        default_factory=list,
        max_length=10,
        description="Top 10 fastest to read",
    )
    
    # Report metadata
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp",
    )
    data_freshness_minutes: int = Field(
        ...,
        ge=0,
        description="Minutes since last data update",
    )