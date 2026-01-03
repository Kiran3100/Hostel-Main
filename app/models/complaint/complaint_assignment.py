"""
Complaint assignment tracking model.

Handles assignment history, reassignments, and workload tracking
for complaint management staff.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.complaint.complaint import Complaint
    from app.models.user.user import User

__all__ = ["ComplaintAssignment"]


class ComplaintAssignment(BaseModel, TimestampMixin):
    """
    Complaint assignment history tracking.
    
    Maintains complete audit trail of all assignment changes with reasons,
    duration tracking, and performance metrics.
    
    Attributes:
        complaint_id: Associated complaint identifier
        assigned_to: User ID of assignee
        assigned_by: User ID who performed assignment
        assigned_at: Assignment timestamp
        unassigned_at: Unassignment timestamp (if reassigned)
        
        assignment_type: Type of assignment (INITIAL, REASSIGNMENT, ESCALATION)
        assignment_reason: Reason for assignment/reassignment
        assignment_notes: Additional assignment context
        
        estimated_resolution_time: Estimated resolution timestamp
        workload_score: Calculated workload score at assignment time
        
        is_current: Flag indicating if this is the current assignment
        duration_hours: Duration of assignment in hours
        
        metadata: Additional assignment metadata
    """

    __tablename__ = "complaint_assignments"
    __table_args__ = (
        # Indexes
        Index("ix_complaint_assignments_complaint_id", "complaint_id"),
        Index("ix_complaint_assignments_assigned_to", "assigned_to"),
        Index("ix_complaint_assignments_assigned_at", "assigned_at"),
        Index("ix_complaint_assignments_current", "complaint_id", "is_current"),
        
        # Unique constraint for current assignment
        Index(
            "ix_complaint_assignments_unique_current",
            "complaint_id",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
        
        # Check constraints
        CheckConstraint(
            "unassigned_at IS NULL OR unassigned_at >= assigned_at",
            name="check_unassigned_after_assigned",
        ),
        CheckConstraint(
            "duration_hours IS NULL OR duration_hours >= 0",
            name="check_duration_positive",
        ),
        CheckConstraint(
            "workload_score >= 0",
            name="check_workload_score_positive",
        ),
        
        {"comment": "Complaint assignment history and tracking"},
    )

    # Foreign Keys
    complaint_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated complaint identifier",
    )
    
    assigned_to: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="User ID of assignee",
    )
    
    assigned_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="User ID who performed assignment",
    )

    # Assignment Details
    assigned_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Assignment timestamp",
    )
    
    unassigned_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Unassignment timestamp (if reassigned)",
    )
    
    assignment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="INITIAL",
        comment="Type: INITIAL, REASSIGNMENT, ESCALATION",
    )
    
    assignment_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for assignment/reassignment",
    )
    
    assignment_notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Additional assignment context or instructions",
    )

    # Performance Tracking
    estimated_resolution_time: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Estimated resolution timestamp",
    )
    
    workload_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Calculated workload score at assignment time",
    )

    # Status Tracking
    is_current: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        index=True,
        comment="Flag indicating if this is the current assignment",
    )
    
    duration_hours: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Duration of assignment in hours",
    )

    # Metadata
    assignment_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Additional assignment metadata",
    )

    # Relationships
    complaint: Mapped["Complaint"] = relationship(
        "Complaint",
        back_populates="assignments",
        lazy="joined",
    )
    
    assignee: Mapped["User"] = relationship(
        "User",
        foreign_keys=[assigned_to],
        lazy="joined",
    )
    
    assigner: Mapped["User"] = relationship(
        "User",
        foreign_keys=[assigned_by],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation of ComplaintAssignment."""
        return (
            f"<ComplaintAssignment(id={self.id}, "
            f"complaint_id={self.complaint_id}, "
            f"assigned_to={self.assigned_to}, "
            f"is_current={self.is_current})>"
        )

    def calculate_duration(self) -> None:
        """Calculate and update duration_hours."""
        if self.unassigned_at:
            delta = self.unassigned_at - self.assigned_at
            self.duration_hours = int(delta.total_seconds() / 3600)