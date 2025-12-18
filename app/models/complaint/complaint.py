"""
Core complaint model with comprehensive tracking and lifecycle management.

Handles complaint creation, status tracking, SLA management, and relationships
with students, hostels, rooms, and staff members.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.enums import ComplaintCategory, ComplaintStatus, Priority
from app.models.base.mixins import AuditMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.complaint.complaint_assignment import ComplaintAssignment
    from app.models.complaint.complaint_comment import ComplaintComment
    from app.models.complaint.complaint_escalation import ComplaintEscalation
    from app.models.complaint.complaint_feedback import ComplaintFeedback
    from app.models.complaint.complaint_resolution import ComplaintResolution
    from app.models.hostel.hostel import Hostel
    from app.models.room.room import Room
    from app.models.student.student import Student
    from app.models.user.user import User

__all__ = ["Complaint"]


class Complaint(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Core complaint entity with comprehensive tracking.
    
    Manages complaint lifecycle from creation to resolution with SLA tracking,
    escalation support, and multi-dimensional categorization.
    
    Attributes:
        complaint_number: Unique human-readable complaint reference (e.g., CMP-2024-001)
        hostel_id: Associated hostel identifier
        raised_by: User ID who raised the complaint
        student_id: Student ID if complaint raised by student
        
        title: Brief complaint summary
        description: Detailed complaint description
        category: Primary complaint category
        sub_category: Optional sub-category for finer classification
        priority: Complaint priority level
        
        room_id: Room identifier if complaint is room-specific
        location_details: Detailed location information
        attachments: URLs of supporting documents/photos
        
        status: Current complaint status
        assigned_to: Currently assigned staff member
        assigned_by: User who performed assignment
        assigned_at: Assignment timestamp
        
        escalated: Escalation flag
        escalated_to: User to whom complaint was escalated
        escalated_at: Escalation timestamp
        escalation_reason: Reason for escalation
        
        sla_breach: SLA breach flag
        sla_breach_reason: Reason for SLA breach
        sla_due_at: SLA deadline timestamp
        
        opened_at: Complaint opening timestamp
        in_progress_at: Status change to in-progress timestamp
        resolved_at: Resolution timestamp
        closed_at: Closure timestamp
        closed_by: User who closed the complaint
        
        resolution_notes: Resolution description
        resolution_attachments: Proof of resolution
        estimated_resolution_time: Estimated resolution timestamp
        actual_resolution_time: Actual resolution completion time
        
        overridden_by_admin: Admin override flag
        override_admin_id: Admin who performed override
        override_timestamp: Override timestamp
        override_reason: Reason for override
        
        reopened_count: Number of times complaint was reopened
        reassigned_count: Number of times complaint was reassigned
        
        total_comments: Comment count (denormalized for performance)
        internal_notes_count: Internal notes count
        
        student_feedback: Student feedback text
        student_rating: Student rating (1-5)
        feedback_submitted_at: Feedback submission timestamp
    """

    __tablename__ = "complaints"
    __table_args__ = (
        # Indexes for common queries
        Index("ix_complaints_hostel_status", "hostel_id", "status"),
        Index("ix_complaints_assigned_to_status", "assigned_to", "status"),
        Index("ix_complaints_raised_by", "raised_by"),
        Index("ix_complaints_student_id", "student_id"),
        Index("ix_complaints_category_priority", "category", "priority"),
        Index("ix_complaints_opened_at", "opened_at"),
        Index("ix_complaints_sla_breach", "sla_breach", "status"),
        Index("ix_complaints_escalated", "escalated", "status"),
        Index("ix_complaints_complaint_number", "complaint_number", unique=True),
        
        # Partial indexes for active complaints
        Index(
            "ix_complaints_active_sla_breach",
            "hostel_id",
            "status",
            "sla_breach",
            postgresql_where=text("status NOT IN ('RESOLVED', 'CLOSED') AND sla_breach = true"),
        ),
        Index(
            "ix_complaints_active_escalated",
            "hostel_id",
            "status",
            "escalated",
            postgresql_where=text("status NOT IN ('RESOLVED', 'CLOSED') AND escalated = true"),
        ),
        
        # Check constraints
        CheckConstraint(
            "student_rating IS NULL OR (student_rating >= 1 AND student_rating <= 5)",
            name="check_student_rating_range",
        ),
        CheckConstraint(
            "reopened_count >= 0",
            name="check_reopened_count_positive",
        ),
        CheckConstraint(
            "reassigned_count >= 0",
            name="check_reassigned_count_positive",
        ),
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= opened_at",
            name="check_resolved_after_opened",
        ),
        CheckConstraint(
            "closed_at IS NULL OR closed_at >= opened_at",
            name="check_closed_after_opened",
        ),
        
        {"comment": "Core complaint entity with comprehensive tracking"},
    )

    # Unique complaint reference number
    complaint_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique human-readable complaint reference",
    )

    # Relationships - Basic Info
    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Associated hostel identifier",
    )
    
    raised_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="User ID who raised complaint",
    )
    
    student_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Student ID if complaint raised by student",
    )

    # Complaint Content
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Brief complaint summary",
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed complaint description",
    )

    # Categorization
    category: Mapped[ComplaintCategory] = mapped_column(
        Enum(ComplaintCategory, name="complaint_category_enum", create_type=True),
        nullable=False,
        index=True,
        comment="Primary complaint category",
    )
    
    sub_category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Optional sub-category for finer classification",
    )
    
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority_enum", create_type=True),
        nullable=False,
        default=Priority.MEDIUM,
        index=True,
        comment="Complaint priority level",
    )

    # Location Details
    room_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Room identifier if complaint is room-specific",
    )
    
    location_details: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Detailed location information within hostel",
    )

    # Media Attachments (URLs stored as JSON array)
    attachments: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        server_default=text("'{}'::varchar[]"),
        comment="URLs of supporting documents/photos",
    )

    # Status and Workflow
    status: Mapped[ComplaintStatus] = mapped_column(
        Enum(ComplaintStatus, name="complaint_status_enum", create_type=True),
        nullable=False,
        default=ComplaintStatus.OPEN,
        index=True,
        comment="Current complaint status",
    )

    # Assignment Details
    assigned_to: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Currently assigned staff member ID",
    )
    
    assigned_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who performed assignment",
    )
    
    assigned_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Assignment timestamp",
    )

    # Escalation Details
    escalated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Escalation flag",
    )
    
    escalated_to: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User to whom complaint was escalated",
    )
    
    escalated_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Escalation timestamp",
    )
    
    escalation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for escalation",
    )

    # SLA Tracking
    sla_breach: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="SLA breach flag",
    )
    
    sla_breach_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Reason for SLA breach",
    )
    
    sla_due_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        index=True,
        comment="SLA deadline timestamp",
    )

    # Lifecycle Timestamps
    opened_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Complaint opening timestamp",
    )
    
    in_progress_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Status change to in-progress timestamp",
    )
    
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        index=True,
        comment="Resolution timestamp",
    )
    
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Closure timestamp",
    )
    
    closed_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who closed the complaint",
    )

    # Resolution Details
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Resolution description and actions taken",
    )
    
    resolution_attachments: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        server_default=text("'{}'::varchar[]"),
        comment="URLs of resolution proof/documents",
    )
    
    estimated_resolution_time: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Estimated resolution timestamp",
    )
    
    actual_resolution_time: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Actual resolution completion time",
    )

    # Admin Override
    overridden_by_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Admin override flag",
    )
    
    override_admin_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who performed override",
    )
    
    override_timestamp: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Override timestamp",
    )
    
    override_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for admin override",
    )

    # Metrics (Denormalized for performance)
    reopened_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times complaint was reopened",
    )
    
    reassigned_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times complaint was reassigned",
    )
    
    total_comments: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total comment count (denormalized)",
    )
    
    internal_notes_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Internal notes count (denormalized)",
    )

    # Student Feedback
    student_feedback: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Student feedback text after resolution",
    )
    
    student_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Student rating (1-5)",
    )
    
    feedback_submitted_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Feedback submission timestamp",
    )

    # Additional metadata (JSONB for flexible storage)
    metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Additional complaint metadata",
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        foreign_keys=[hostel_id],
        back_populates="complaints",
        lazy="joined",
    )
    
    raiser: Mapped["User"] = relationship(
        "User",
        foreign_keys=[raised_by],
        back_populates="raised_complaints",
        lazy="joined",
    )
    
    student: Mapped[Optional["Student"]] = relationship(
        "Student",
        foreign_keys=[student_id],
        back_populates="complaints",
        lazy="selectin",
    )
    
    room: Mapped[Optional["Room"]] = relationship(
        "Room",
        foreign_keys=[room_id],
        back_populates="complaints",
        lazy="selectin",
    )
    
    assignee: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_to],
        back_populates="assigned_complaints",
        lazy="selectin",
    )
    
    assigner: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_by],
        lazy="selectin",
    )
    
    escalated_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[escalated_to],
        lazy="selectin",
    )
    
    closer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[closed_by],
        lazy="selectin",
    )
    
    override_admin: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[override_admin_id],
        lazy="selectin",
    )

    # Child relationships
    assignments: Mapped[List["ComplaintAssignment"]] = relationship(
        "ComplaintAssignment",
        back_populates="complaint",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ComplaintAssignment.assigned_at.desc()",
    )
    
    comments: Mapped[List["ComplaintComment"]] = relationship(
        "ComplaintComment",
        back_populates="complaint",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ComplaintComment.created_at.asc()",
    )
    
    escalations: Mapped[List["ComplaintEscalation"]] = relationship(
        "ComplaintEscalation",
        back_populates="complaint",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ComplaintEscalation.escalated_at.desc()",
    )
    
    resolutions: Mapped[List["ComplaintResolution"]] = relationship(
        "ComplaintResolution",
        back_populates="complaint",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ComplaintResolution.resolved_at.desc()",
    )
    
    feedback_records: Mapped[List["ComplaintFeedback"]] = relationship(
        "ComplaintFeedback",
        back_populates="complaint",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ComplaintFeedback.submitted_at.desc()",
    )

    def __repr__(self) -> str:
        """String representation of Complaint."""
        return (
            f"<Complaint(id={self.id}, "
            f"number={self.complaint_number}, "
            f"status={self.status.value}, "
            f"priority={self.priority.value})>"
        )

    @property
    def age_hours(self) -> int:
        """Calculate complaint age in hours."""
        now = datetime.now(timezone.utc)
        delta = now - self.opened_at
        return int(delta.total_seconds() / 3600)

    @property
    def time_to_resolve_hours(self) -> Optional[int]:
        """Calculate time taken to resolve in hours."""
        if not self.resolved_at:
            return None
        delta = self.resolved_at - self.opened_at
        return int(delta.total_seconds() / 3600)

    @property
    def is_active(self) -> bool:
        """Check if complaint is in an active state."""
        active_statuses = {
            ComplaintStatus.OPEN,
            ComplaintStatus.ASSIGNED,
            ComplaintStatus.IN_PROGRESS,
            ComplaintStatus.REOPENED,
        }
        return self.status in active_statuses

    @property
    def is_overdue(self) -> bool:
        """Check if complaint is overdue based on SLA."""
        if not self.is_active:
            return False
        if self.sla_due_at is None:
            return False
        return datetime.now(timezone.utc) > self.sla_due_at