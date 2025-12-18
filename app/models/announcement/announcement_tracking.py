# --- File: app/models/announcement/announcement_tracking.py ---
"""
Announcement tracking and engagement models.

This module defines models for tracking read receipts,
acknowledgments, and engagement metrics.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.announcement.announcement import Announcement
    from app.models.user.user import User

__all__ = [
    "AnnouncementView",
    "ReadReceipt",
    "Acknowledgment",
    "EngagementMetric",
    "ReadingTimeAnalytic",
]


class DeviceType:
    """Device type enumeration."""
    MOBILE = "mobile"
    WEB = "web"
    TABLET = "tablet"
    DESKTOP = "desktop"


class AnnouncementView(BaseModel, UUIDMixin, TimestampModel):
    """
    Announcement view tracking.
    
    Records each time a student views an announcement
    for analytics and engagement tracking.
    """
    
    __tablename__ = "announcement_views"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated announcement",
    )
    student_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Student who viewed",
    )
    
    # View Details
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When announcement was viewed",
    )
    
    # Reading Context
    device_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Device used to view",
    )
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="app",
        comment="How user accessed (app, email, push_notification, web)",
    )
    
    # Reading Behavior
    reading_time_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Time spent reading in seconds",
    )
    scroll_percentage: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="How far user scrolled (0-100%)",
    )
    
    # Session Information
    session_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="User session ID",
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of viewer",
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="User agent string",
    )
    
    # Engagement Indicators
    clicked_links: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether user clicked any links",
    )
    downloaded_attachments: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether user downloaded attachments",
    )
    shared: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether user shared the announcement",
    )
    
    # View Count (for this session)
    view_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Number of times viewed in this session",
    )
    
    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional view metadata",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        back_populates="views",
    )
    student: Mapped["User"] = relationship(
        "User",
        lazy="select",
    )
    
    __table_args__ = (
        Index("ix_announcement_views_announcement", "announcement_id"),
        Index("ix_announcement_views_student", "student_id"),
        Index("ix_announcement_views_viewed_at", "viewed_at"),
        Index("ix_announcement_views_device", "device_type"),
        Index("ix_announcement_views_source", "source"),
        Index("ix_announcement_views_announcement_student", "announcement_id", "student_id"),
        CheckConstraint(
            "reading_time_seconds IS NULL OR (reading_time_seconds >= 0 AND reading_time_seconds <= 3600)",
            name="ck_announcement_views_reading_time",
        ),
        CheckConstraint(
            "scroll_percentage IS NULL OR (scroll_percentage >= 0 AND scroll_percentage <= 100)",
            name="ck_announcement_views_scroll_percentage",
        ),
        CheckConstraint(
            "view_count > 0",
            name="ck_announcement_views_count_positive",
        ),
        CheckConstraint(
            "device_type IN ('mobile', 'web', 'tablet', 'desktop') OR device_type IS NULL",
            name="ck_announcement_views_device_type",
        ),
        {"comment": "Announcement view tracking for analytics"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<AnnouncementView(id={self.id}, announcement_id={self.announcement_id}, "
            f"student_id={self.student_id}, viewed_at={self.viewed_at})>"
        )


class ReadReceipt(BaseModel, UUIDMixin, TimestampModel):
    """
    Read receipt tracking.
    
    Confirms that a student has read an announcement,
    distinct from just viewing it.
    """
    
    __tablename__ = "announcement_read_receipts"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated announcement",
    )
    student_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Student who read",
    )
    
    # Read Details
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When announcement was read",
    )
    
    # Reading Context
    device_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Device used to read",
    )
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="app",
        comment="How user accessed",
    )
    
    # Reading Metrics
    reading_time_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Time spent reading",
    )
    scroll_percentage: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Scroll completion percentage",
    )
    completed_reading: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether student completed reading (scrolled to end)",
    )
    
    # Delivery to Read Time
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When announcement was delivered",
    )
    time_to_read_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Seconds from delivery to read",
    )
    
    # First Read Indicator
    is_first_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this is the first time reading",
    )
    
    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional read receipt metadata",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        back_populates="read_receipts",
    )
    student: Mapped["User"] = relationship(
        "User",
        lazy="select",
    )
    
    __table_args__ = (
        UniqueConstraint(
            "announcement_id",
            "student_id",
            name="uq_read_receipts_announcement_student",
        ),
        Index("ix_read_receipts_announcement", "announcement_id"),
        Index("ix_read_receipts_student", "student_id"),
        Index("ix_read_receipts_read_at", "read_at"),
        Index("ix_read_receipts_completed", "completed_reading"),
        CheckConstraint(
            "reading_time_seconds IS NULL OR reading_time_seconds >= 0",
            name="ck_read_receipts_reading_time",
        ),
        CheckConstraint(
            "scroll_percentage IS NULL OR (scroll_percentage >= 0 AND scroll_percentage <= 100)",
            name="ck_read_receipts_scroll_percentage",
        ),
        CheckConstraint(
            "time_to_read_seconds IS NULL OR time_to_read_seconds >= 0",
            name="ck_read_receipts_time_to_read",
        ),
        {"comment": "Read receipt confirmation tracking"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<ReadReceipt(id={self.id}, announcement_id={self.announcement_id}, "
            f"student_id={self.student_id}, read_at={self.read_at})>"
        )


class Acknowledgment(BaseModel, UUIDMixin, TimestampModel):
    """
    Announcement acknowledgment.
    
    Records when students acknowledge they have read and
    understood important announcements.
    """
    
    __tablename__ = "announcement_acknowledgments"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated announcement",
    )
    student_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Student acknowledging",
    )
    
    # Acknowledgment Details
    acknowledged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When acknowledgment was made",
    )
    
    # Student Note
    acknowledgment_note: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional note from student",
    )
    
    # Action Taken (for announcements requiring specific action)
    action_taken: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description of action taken if required",
    )
    action_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether action has been verified",
    )
    
    # Timing
    deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Acknowledgment deadline",
    )
    on_time: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether acknowledged before deadline",
    )
    
    # Delivery to Acknowledgment Time
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When announcement was delivered",
    )
    time_to_acknowledge_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Seconds from delivery to acknowledgment",
    )
    
    # Read Before Acknowledge
    read_before_acknowledge: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether student read before acknowledging",
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When student read the announcement",
    )
    
    # IP and Device
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address when acknowledged",
    )
    device_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Device used for acknowledgment",
    )
    
    # Verification
    verified_by_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who verified the acknowledgment",
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When acknowledgment was verified",
    )
    verification_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Verification notes",
    )
    
    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional acknowledgment metadata",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        lazy="select",
    )
    student: Mapped["User"] = relationship(
        "User",
        foreign_keys=[student_id],
        lazy="select",
    )
    verified_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[verified_by_id],
        lazy="select",
    )
    
    __table_args__ = (
        UniqueConstraint(
            "announcement_id",
            "student_id",
            name="uq_acknowledgments_announcement_student",
        ),
        Index("ix_acknowledgments_announcement", "announcement_id"),
        Index("ix_acknowledgments_student", "student_id"),
        Index("ix_acknowledgments_acknowledged_at", "acknowledged_at"),
        Index("ix_acknowledgments_on_time", "on_time"),
        Index("ix_acknowledgments_deadline", "deadline"),
        CheckConstraint(
            "time_to_acknowledge_seconds IS NULL OR time_to_acknowledge_seconds >= 0",
            name="ck_acknowledgments_time_positive",
        ),
        {"comment": "Announcement acknowledgment tracking"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<Acknowledgment(id={self.id}, announcement_id={self.announcement_id}, "
            f"student_id={self.student_id}, on_time={self.on_time})>"
        )


class EngagementMetric(BaseModel, UUIDMixin, TimestampModel):
    """
    Engagement metrics for announcements.
    
    Aggregated engagement statistics for performance analysis.
    """
    
    __tablename__ = "announcement_engagement_metrics"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
        comment="Associated announcement",
    )
    
    # Delivery Metrics
    total_recipients: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total recipients",
    )
    delivered_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Successfully delivered",
    )
    delivery_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Delivery rate percentage",
    )
    
    # Reading Metrics
    view_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total views (may include multiple per user)",
    )
    unique_readers: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Unique students who read",
    )
    read_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Read rate percentage",
    )
    
    # Reading Depth
    average_reading_time_seconds: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Average reading time",
    )
    average_scroll_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Average scroll depth",
    )
    completion_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Percentage who read completely",
    )
    
    # Acknowledgment Metrics
    requires_acknowledgment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether acknowledgment required",
    )
    acknowledged_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number who acknowledged",
    )
    acknowledgment_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Acknowledgment rate percentage",
    )
    on_time_acknowledgments: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Acknowledgments before deadline",
    )
    late_acknowledgments: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Acknowledgments after deadline",
    )
    
    # Timing Metrics
    average_time_to_read_hours: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Average hours from delivery to read",
    )
    average_time_to_acknowledge_hours: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Average hours from delivery to acknowledge",
    )
    
    # Engagement Score
    engagement_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Overall engagement score (0-100)",
    )
    
    # Channel Breakdown
    email_delivered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Emails delivered",
    )
    sms_delivered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="SMS delivered",
    )
    push_delivered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Push notifications delivered",
    )
    in_app_delivered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="In-app notifications delivered",
    )
    
    # Device Breakdown
    mobile_views: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Views from mobile",
    )
    web_views: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Views from web",
    )
    tablet_views: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Views from tablet",
    )
    desktop_views: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Views from desktop",
    )
    
    # Interaction Metrics
    link_clicks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of link clicks",
    )
    attachment_downloads: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of attachment downloads",
    )
    shares: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of shares",
    )
    
    # Last Updated
    last_calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When metrics were last calculated",
    )
    
    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional engagement metadata",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        lazy="select",
    )
    
    __table_args__ = (
        Index("ix_engagement_metrics_announcement", "announcement_id"),
        Index("ix_engagement_metrics_engagement_score", "engagement_score"),
        Index("ix_engagement_metrics_read_rate", "read_rate"),
        CheckConstraint(
            "total_recipients >= 0",
            name="ck_engagement_metrics_recipients",
        ),
        CheckConstraint(
            "delivered_count >= 0 AND delivered_count <= total_recipients",
            name="ck_engagement_metrics_delivered",
        ),
        CheckConstraint(
            "unique_readers >= 0 AND unique_readers <= delivered_count",
            name="ck_engagement_metrics_readers",
        ),
        CheckConstraint(
            "delivery_rate >= 0 AND delivery_rate <= 100",
            name="ck_engagement_metrics_delivery_rate",
        ),
        CheckConstraint(
            "read_rate >= 0 AND read_rate <= 100",
            name="ck_engagement_metrics_read_rate",
        ),
        CheckConstraint(
            "acknowledgment_rate >= 0 AND acknowledgment_rate <= 100",
            name="ck_engagement_metrics_ack_rate",
        ),
        CheckConstraint(
            "engagement_score >= 0 AND engagement_score <= 100",
            name="ck_engagement_metrics_score",
        ),
        {"comment": "Aggregated engagement metrics for announcements"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<EngagementMetric(id={self.id}, announcement_id={self.announcement_id}, "
            f"score={self.engagement_score}, read_rate={self.read_rate})>"
        )


class ReadingTimeAnalytic(BaseModel, UUIDMixin, TimestampModel):
    """
    Reading time analytics.
    
    Detailed analysis of reading time patterns for
    announcement optimization.
    """
    
    __tablename__ = "announcement_reading_time_analytics"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
        comment="Associated announcement",
    )
    
    # Basic Statistics
    total_readers: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of readers with time data",
    )
    
    # Time Statistics
    average_reading_time_seconds: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average reading time",
    )
    median_reading_time_seconds: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Median reading time",
    )
    min_reading_time_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Minimum reading time",
    )
    max_reading_time_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Maximum reading time",
    )
    
    # Distribution
    quick_readers: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Read in < 30 seconds",
    )
    normal_readers: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Read in 30-120 seconds",
    )
    thorough_readers: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Read in > 120 seconds",
    )
    
    # Percentages
    quick_readers_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Percentage of quick readers",
    )
    normal_readers_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Percentage of normal readers",
    )
    thorough_readers_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Percentage of thorough readers",
    )
    
    # Time Distribution by Hour
    reads_by_hour: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Distribution of reads by hour of day",
    )
    
    # Device-based Reading Time
    mobile_avg_time: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Average reading time on mobile",
    )
    web_avg_time: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Average reading time on web",
    )
    
    # Last Calculated
    last_calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When analytics were last calculated",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        lazy="select",
    )
    
    __table_args__ = (
        Index("ix_reading_time_analytics_announcement", "announcement_id"),
        CheckConstraint(
            "total_readers >= 0",
            name="ck_reading_time_analytics_readers",
        ),
        CheckConstraint(
            "min_reading_time_seconds >= 0",
            name="ck_reading_time_analytics_min_time",
        ),
        CheckConstraint(
            "max_reading_time_seconds >= min_reading_time_seconds",
            name="ck_reading_time_analytics_max_time",
        ),
        CheckConstraint(
            "quick_readers + normal_readers + thorough_readers <= total_readers",
            name="ck_reading_time_analytics_distribution",
        ),
        {"comment": "Reading time analytics for announcements"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<ReadingTimeAnalytic(id={self.id}, announcement_id={self.announcement_id}, "
            f"avg_time={self.average_reading_time_seconds})>"
        )