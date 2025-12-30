"""
Core announcement models.

This module defines the main announcement entity and related models
for managing announcements throughout their lifecycle.
"""

from datetime import datetime
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
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.combined_base import AnnouncementBaseModel, SimpleBaseModel
from app.models.base.enums import (
    AnnouncementCategory,
    AnnouncementStatus,
    Priority,
    TargetAudience,
)

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel
    from app.models.user.user import User
    from app.models.announcement.announcement_targeting import AnnouncementTarget
    from app.models.announcement.announcement_scheduling import AnnouncementSchedule
    from app.models.announcement.announcement_approval import AnnouncementApproval
    from app.models.announcement.announcement_delivery import AnnouncementDelivery
    from app.models.announcement.announcement_tracking import (
        AnnouncementView,
        ReadReceipt,
    )

__all__ = [
    "Announcement",
    "AnnouncementAttachment",
    "AnnouncementVersion",
    "AnnouncementRecipient",
]


class Announcement(AnnouncementBaseModel):
    """
    Core announcement entity.
    
    Manages the complete lifecycle of announcements from creation
    through publication, delivery, and tracking.
    """
    
    __tablename__ = "announcements"
    
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
        index=True,
        comment="User who created the announcement",
    )
    
    # Content Fields
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Announcement title",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Announcement content/body",
    )
    
    # Classification
    category: Mapped[AnnouncementCategory] = mapped_column(
        Enum(AnnouncementCategory, name="announcement_category_enum"),
        nullable=False,
        index=True,
        comment="Announcement category",
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority_enum"),
        nullable=False,
        default=Priority.MEDIUM,
        index=True,
        comment="Priority level",
    )
    status: Mapped[AnnouncementStatus] = mapped_column(
        Enum(AnnouncementStatus, name="announcement_status_enum"),
        nullable=False,
        default=AnnouncementStatus.DRAFT,
        index=True,
        comment="Current status",
    )
    
    # Visibility Flags
    is_urgent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Mark as urgent for highlighted display",
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Pin to top of announcement list",
    )
    
    # Target Audience Configuration
    target_audience: Mapped[TargetAudience] = mapped_column(
        Enum(TargetAudience, name="target_audience_enum"),
        nullable=False,
        default=TargetAudience.ALL,
        index=True,
        comment="Target audience type",
    )
    target_room_ids: Mapped[Optional[List[UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="Specific room UUIDs when targeting specific rooms",
    )
    target_student_ids: Mapped[Optional[List[UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="Specific student UUIDs for individual targeting",
    )
    target_floor_numbers: Mapped[Optional[List[int]]] = mapped_column(
        ARRAY(Integer),
        nullable=True,
        comment="Specific floor numbers when targeting floors",
    )
    
    # Attachments (stored as JSON array of URLs)
    attachments: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="Attachment URLs",
    )
    
    # Publication and Scheduling
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether announcement is published",
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When announcement was published",
    )
    published_by_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who published the announcement",
    )
    scheduled_publish_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Scheduled publication time",
    )
    
    # Expiry
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When announcement expires and becomes inactive",
    )
    
    # Delivery Channel Settings
    send_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Send email notification to recipients",
    )
    send_sms: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Send SMS notification to recipients",
    )
    send_push: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Send push notification to recipients",
    )
    
    # Delivery Timestamps
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When email notifications were sent",
    )
    sms_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When SMS notifications were sent",
    )
    push_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When push notifications were sent",
    )
    
    # Acknowledgment Settings
    requires_acknowledgment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether recipients must acknowledge reading",
    )
    acknowledgment_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Deadline for acknowledgment if required",
    )
    
    # Approval Settings
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether announcement requires approval",
    )
    approved_by_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who approved the announcement",
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When announcement was approved",
    )
    approval_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes from approver",
    )
    
    # Metrics and Engagement
    total_recipients: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of recipients",
    )
    read_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of recipients who read",
    )
    acknowledged_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of recipients who acknowledged",
    )
    engagement_rate: Mapped[Numeric] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=0.00,
        comment="Engagement rate percentage (0-100)",
    )
    
    # Metadata
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        comment="Additional metadata and custom fields",
    )
    
    # Version Control
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Version number for tracking edits",
    )
    
    # Archive
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether announcement is archived",
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When announcement was archived",
    )
    archived_by_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who archived the announcement",
    )
    
    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="announcements",
        lazy="joined",
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by_id],
        back_populates="created_announcements",
        lazy="joined",
    )
    published_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[published_by_id],
        lazy="select",
    )
    approved_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by_id],
        lazy="select",
    )
    archived_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[archived_by_id],
        lazy="select",
    )
    
    # Related entities
    attachments_rel: Mapped[List["AnnouncementAttachment"]] = relationship(
        "AnnouncementAttachment",
        back_populates="announcement",
        cascade="all, delete-orphan",
        lazy="select",
    )
    versions: Mapped[List["AnnouncementVersion"]] = relationship(
        "AnnouncementVersion",
        back_populates="announcement",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="AnnouncementVersion.version_number.desc()",
    )
    recipients: Mapped[List["AnnouncementRecipient"]] = relationship(
        "AnnouncementRecipient",
        back_populates="announcement",
        cascade="all, delete-orphan",
        lazy="select",
    )
    targets: Mapped[List["AnnouncementTarget"]] = relationship(
        "AnnouncementTarget",
        back_populates="announcement",
        cascade="all, delete-orphan",
        lazy="select",
    )
    schedules: Mapped[List["AnnouncementSchedule"]] = relationship(
        "AnnouncementSchedule",
        back_populates="announcement",
        cascade="all, delete-orphan",
        lazy="select",
    )
    approvals: Mapped[List["AnnouncementApproval"]] = relationship(
        "AnnouncementApproval",
        back_populates="announcement",
        cascade="all, delete-orphan",
        lazy="select",
    )
    deliveries: Mapped[List["AnnouncementDelivery"]] = relationship(
        "AnnouncementDelivery",
        back_populates="announcement",
        cascade="all, delete-orphan",
        lazy="select",
    )
    views: Mapped[List["AnnouncementView"]] = relationship(
        "AnnouncementView",
        back_populates="announcement",
        cascade="all, delete-orphan",
        lazy="select",
    )
    read_receipts: Mapped[List["ReadReceipt"]] = relationship(
        "ReadReceipt",
        back_populates="announcement",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_announcements_hostel_status", "hostel_id", "status"),
        Index("ix_announcements_hostel_published", "hostel_id", "is_published"),
        Index("ix_announcements_category_priority", "category", "priority"),
        Index("ix_announcements_published_at_desc", "published_at", postgresql_using="btree"),
        Index("ix_announcements_expires_at", "expires_at", postgresql_using="btree"),
        Index("ix_announcements_urgent_pinned", "is_urgent", "is_pinned"),
        CheckConstraint(
            "engagement_rate >= 0 AND engagement_rate <= 100",
            name="ck_announcements_engagement_rate_range",
        ),
        CheckConstraint(
            "read_count <= total_recipients",
            name="ck_announcements_read_count_valid",
        ),
        CheckConstraint(
            "acknowledged_count <= total_recipients",
            name="ck_announcements_acknowledged_count_valid",
        ),
        CheckConstraint(
            "(published_at IS NULL AND is_published = FALSE) OR "
            "(published_at IS NOT NULL AND is_published = TRUE)",
            name="ck_announcements_published_consistency",
        ),
        CheckConstraint(
            "(requires_acknowledgment = FALSE) OR "
            "(requires_acknowledgment = TRUE AND acknowledgment_deadline IS NOT NULL)",
            name="ck_announcements_acknowledgment_deadline",
        ),
        {"comment": "Core announcement entity with complete lifecycle management"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<Announcement(id={self.id}, title='{self.title[:30]}...', "
            f"status={self.status.value}, hostel_id={self.hostel_id})>"
        )
    
    @property
    def is_active(self) -> bool:
        """Check if announcement is currently active."""
        if not self.is_published:
            return False
        if self.is_archived or self.is_deleted:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True
    
    @property
    def is_expired(self) -> bool:
        """Check if announcement has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def read_percentage(self) -> float:
        """Calculate read percentage."""
        if self.total_recipients == 0:
            return 0.0
        return round((self.read_count / self.total_recipients) * 100, 2)
    
    @property
    def acknowledgment_percentage(self) -> float:
        """Calculate acknowledgment percentage."""
        if not self.requires_acknowledgment or self.total_recipients == 0:
            return 0.0
        return round((self.acknowledged_count / self.total_recipients) * 100, 2)


class AnnouncementAttachment(SimpleBaseModel):
    """
    Announcement file attachments.
    
    Manages file attachments associated with announcements
    including images, documents, and other media.
    """
    
    __tablename__ = "announcement_attachments"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated announcement",
    )
    uploaded_by_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who uploaded the attachment",
    )
    
    # File Information
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original file name",
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Storage path or URL",
    )
    file_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="MIME type",
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="File size in bytes",
    )
    
    # Display Information
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order in attachment list",
    )
    caption: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Optional caption for the attachment",
    )
    
    # Image-specific metadata (if applicable)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Thumbnail image path for images",
    )
    image_width: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Image width in pixels",
    )
    image_height: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Image height in pixels",
    )
    
    # Metadata
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        comment="Additional file metadata",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        back_populates="attachments_rel",
    )
    uploaded_by: Mapped[Optional["User"]] = relationship(
        "User",
        lazy="select",
    )
    
    __table_args__ = (
        Index("ix_announcement_attachments_announcement", "announcement_id"),
        CheckConstraint(
            "file_size > 0",
            name="ck_announcement_attachments_file_size_positive",
        ),
        {"comment": "File attachments for announcements"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<AnnouncementAttachment(id={self.id}, "
            f"file_name='{self.file_name}', announcement_id={self.announcement_id})>"
        )


class AnnouncementVersion(SimpleBaseModel):
    """
    Announcement version history.
    
    Tracks changes to announcements for audit and rollback purposes.
    """
    
    __tablename__ = "announcement_versions"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated announcement",
    )
    modified_by_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who made the modification",
    )
    
    # Version Information
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Version number",
    )
    
    # Snapshot of content at this version
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Title at this version",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Content at this version",
    )
    
    # Change Information
    change_summary: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Summary of changes in this version",
    )
    changed_fields: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of fields that were changed",
    )
    
    # Complete snapshot
    version_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Complete announcement data at this version",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        back_populates="versions",
    )
    modified_by: Mapped[Optional["User"]] = relationship(
        "User",
        lazy="select",
    )
    
    __table_args__ = (
        UniqueConstraint(
            "announcement_id",
            "version_number",
            name="uq_announcement_versions_announcement_version",
        ),
        Index("ix_announcement_versions_announcement", "announcement_id"),
        Index("ix_announcement_versions_created_at", "created_at"),
        CheckConstraint(
            "version_number > 0",
            name="ck_announcement_versions_version_positive",
        ),
        {"comment": "Version history for announcements"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<AnnouncementVersion(id={self.id}, announcement_id={self.announcement_id}, "
            f"version={self.version_number})>"
        )


class AnnouncementRecipient(SimpleBaseModel):
    """
    Calculated recipients for announcements.
    
    Stores the final list of students who should receive
    the announcement based on targeting rules.
    """
    
    __tablename__ = "announcement_recipients"
    
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
        comment="Recipient student",
    )
    
    # Targeting Information
    matched_by: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="How student was targeted (all, room, floor, individual)",
    )
    room_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Student's room at time of targeting",
    )
    floor_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Student's floor at time of targeting",
    )
    
    # Delivery Status
    is_delivered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether announcement was delivered",
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When announcement was delivered",
    )
    delivery_channel: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Primary delivery channel used",
    )
    
    # Read Status
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether student has read",
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When student read the announcement",
    )
    
    # Acknowledgment Status
    is_acknowledged: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether student has acknowledged",
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When student acknowledged",
    )
    
    # Metadata
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        comment="Additional recipient-specific metadata",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        back_populates="recipients",
    )
    student: Mapped["User"] = relationship(
        "User",
        lazy="select",
    )
    
    __table_args__ = (
        UniqueConstraint(
            "announcement_id",
            "student_id",
            name="uq_announcement_recipients_announcement_student",
        ),
        Index("ix_announcement_recipients_announcement", "announcement_id"),
        Index("ix_announcement_recipients_student", "student_id"),
        Index("ix_announcement_recipients_read_status", "announcement_id", "is_read"),
        Index("ix_announcement_recipients_ack_status", "announcement_id", "is_acknowledged"),
        {"comment": "Calculated recipients for announcements"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<AnnouncementRecipient(id={self.id}, "
            f"announcement_id={self.announcement_id}, student_id={self.student_id})>"
        )