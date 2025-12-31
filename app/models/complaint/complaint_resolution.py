"""
Complaint resolution tracking model.

Handles complaint resolution workflow including marking as resolved,
reopening, and final closure with comprehensive validation.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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
from app.models.base.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.complaint.complaint import Complaint
    from app.models.user.user import User

__all__ = ["ComplaintResolution"]


class ComplaintResolution(BaseModel, TimestampMixin):
    """
    Complaint resolution tracking and documentation.
    
    Maintains complete resolution history including actions taken,
    follow-up requirements, and quality validation.
    
    Attributes:
        complaint_id: Associated complaint identifier
        resolved_by: User ID who resolved the complaint
        resolved_at: Resolution timestamp
        
        resolution_notes: Detailed resolution description
        resolution_attachments: Proof of resolution (photos/documents)
        
        actions_taken: List of specific actions performed
        materials_used: Materials/parts used in resolution
        
        actual_resolution_time: Actual completion time
        time_to_resolve_hours: Time taken to resolve in hours
        
        follow_up_required: Flag if follow-up check needed
        follow_up_date: Scheduled follow-up date
        follow_up_notes: Follow-up instructions
        follow_up_completed: Follow-up completion flag
        follow_up_completed_at: Follow-up completion timestamp
        
        quality_checked: Quality validation flag
        quality_checked_by: User who performed quality check
        quality_checked_at: Quality check timestamp
        quality_score: Quality score (1-10)
        quality_notes: Quality check notes
        
        reopened: Flag if complaint was reopened after this resolution
        reopened_at: Reopening timestamp
        reopen_reason: Reason for reopening
        
        is_final_resolution: Flag indicating final/latest resolution
        
        metadata: Additional resolution metadata
    """

    __tablename__ = "complaint_resolutions"
    __table_args__ = (
        # Indexes
        Index("ix_complaint_resolutions_complaint_id", "complaint_id"),
        Index("ix_complaint_resolutions_resolved_by", "resolved_by"),
        Index("ix_complaint_resolutions_resolved_at", "resolved_at"),
        Index("ix_complaint_resolutions_follow_up", "follow_up_required", "follow_up_completed"),
        Index("ix_complaint_resolutions_quality", "quality_checked"),
        Index("ix_complaint_resolutions_final", "complaint_id", "is_final_resolution"),
        
        # Unique constraint for final resolution
        Index(
            "ix_complaint_resolutions_unique_final",
            "complaint_id",
            unique=True,
            postgresql_where=text("is_final_resolution = true"),
        ),
        
        # Check constraints
        CheckConstraint(
            "time_to_resolve_hours IS NULL OR time_to_resolve_hours >= 0",
            name="check_time_to_resolve_positive",
        ),
        CheckConstraint(
            "quality_score IS NULL OR (quality_score >= 1 AND quality_score <= 10)",
            name="check_quality_score_range",
        ),
        CheckConstraint(
            "follow_up_completed_at IS NULL OR follow_up_completed_at >= resolved_at",
            name="check_follow_up_after_resolution",
        ),
        CheckConstraint(
            "quality_checked_at IS NULL OR quality_checked_at >= resolved_at",
            name="check_quality_check_after_resolution",
        ),
        CheckConstraint(
            "reopened_at IS NULL OR reopened_at >= resolved_at",
            name="check_reopen_after_resolution",
        ),
        
        {"comment": "Complaint resolution tracking and documentation"},
    )

    # Foreign Keys
    complaint_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated complaint identifier",
    )
    
    resolved_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="User ID who resolved the complaint",
    )

    # Resolution Details
    resolved_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Resolution timestamp",
    )
    
    resolution_notes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed resolution description and actions taken",
    )
    
    resolution_attachments: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        server_default=text("'{}'::varchar[]"),
        comment="URLs of resolution proof/documents",
    )

    # Actions and Materials
    actions_taken: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        server_default=text("'{}'::varchar[]"),
        comment="List of specific actions performed",
    )
    
    materials_used: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Materials/parts used in resolution",
    )

    # Time Tracking
    actual_resolution_time: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Actual completion time (if different from resolved_at)",
    )
    
    time_to_resolve_hours: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Time taken to resolve in hours",
    )

    # Follow-up Management
    follow_up_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Flag if follow-up check is needed",
    )
    
    follow_up_date: Mapped[Optional[Date]] = mapped_column(
        Date,
        nullable=True,
        comment="Scheduled follow-up date",
    )
    
    follow_up_notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Follow-up instructions and requirements",
    )
    
    follow_up_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Follow-up completion flag",
    )
    
    follow_up_completed_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Follow-up completion timestamp",
    )

    # Quality Control
    quality_checked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Quality validation flag",
    )
    
    quality_checked_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who performed quality check",
    )
    
    quality_checked_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Quality check timestamp",
    )
    
    quality_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Quality score (1-10)",
    )
    
    quality_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Quality check notes and observations",
    )

    # Reopening Tracking
    reopened: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Flag if complaint was reopened after this resolution",
    )
    
    reopened_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Reopening timestamp",
    )
    
    reopen_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for reopening",
    )

    # Resolution Status
    is_final_resolution: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Flag indicating final/latest resolution",
    )

    # Metadata
    resolution_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Additional resolution metadata",
    )

    # Relationships
    complaint: Mapped["Complaint"] = relationship(
        "Complaint",
        back_populates="resolutions",
        lazy="joined",
    )
    
    resolver: Mapped["User"] = relationship(
        "User",
        foreign_keys=[resolved_by],
        lazy="joined",
    )
    
    quality_checker: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[quality_checked_by],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation of ComplaintResolution."""
        return (
            f"<ComplaintResolution(id={self.id}, "
            f"complaint_id={self.complaint_id}, "
            f"resolved_by={self.resolved_by}, "
            f"is_final={self.is_final_resolution})>"
        )

    @property
    def is_follow_up_overdue(self) -> bool:
        """Check if follow-up is overdue."""
        if not self.follow_up_required or self.follow_up_completed:
            return False
        if self.follow_up_date is None:
            return False
        
        from datetime import date
        return date.today() > self.follow_up_date

    @property
    def resolution_efficiency(self) -> Optional[str]:
        """Calculate resolution efficiency rating."""
        if self.time_to_resolve_hours is None:
            return None
        
        hours = self.time_to_resolve_hours
        
        if hours <= 4:
            return "EXCELLENT"
        elif hours <= 12:
            return "GOOD"
        elif hours <= 24:
            return "AVERAGE"
        else:
            return "POOR"