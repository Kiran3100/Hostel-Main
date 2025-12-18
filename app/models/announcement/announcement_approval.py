# --- File: app/models/announcement/announcement_approval.py ---
"""
Announcement approval workflow models.

This module defines models for the approval process when
supervisors create announcements requiring admin approval.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
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
    "AnnouncementApproval",
    "ApprovalWorkflow",
    "ApprovalHistory",
    "ApprovalRule",
]


class ApprovalStatus:
    """Approval status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NOT_REQUIRED = "not_required"


class AnnouncementApproval(BaseModel, UUIDMixin, TimestampModel):
    """
    Announcement approval tracking.
    
    Manages the approval workflow for announcements created
    by supervisors that require admin approval.
    """
    
    __tablename__ = "announcement_approvals"
    
    # Foreign Keys
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
        comment="Associated announcement",
    )
    requested_by_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User requesting approval (supervisor)",
    )
    
    # Approval Request
    approval_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Justification for why approval is needed",
    )
    is_urgent_request: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Mark as urgent for prioritized review",
    )
    
    # Preferred Approver
    preferred_approver_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Preferred admin to review (optional)",
    )
    
    # Auto-Publish Setting
    auto_publish_on_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Automatically publish when approved",
    )
    
    # Approval Status
    approval_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ApprovalStatus.PENDING,
        index=True,
        comment="Current approval status",
    )
    
    # Decision Details
    approved: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        index=True,
        comment="Whether approved (True) or rejected (False)",
    )
    decided_by_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who made the decision",
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When decision was made",
    )
    
    # Approval Notes
    approval_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes from the approver",
    )
    
    # Rejection Details
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed reason for rejection",
    )
    suggested_modifications: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Suggestions for improving the announcement",
    )
    allow_resubmission: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether creator can resubmit after modifications",
    )
    
    # Publication Status
    auto_published: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether announcement was auto-published",
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Publication timestamp if published",
    )
    
    # Timing Metrics
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When submitted for approval",
    )
    time_pending_hours: Mapped[Optional[float]] = mapped_column(
        Integer,
        nullable=True,
        comment="Hours in pending state",
    )
    
    # Assignment
    assigned_to_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin currently reviewing",
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When assigned to reviewer",
    )
    
    # Escalation
    is_escalated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether approval has been escalated",
    )
    escalated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When approval was escalated",
    )
    escalation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for escalation",
    )
    
    # SLA Tracking
    sla_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="SLA deadline for approval decision",
    )
    sla_breached: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether SLA was breached",
    )
    
    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional approval metadata",
    )
    
    # Relationships
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        back_populates="approvals",
    )
    requested_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[requested_by_id],
        lazy="select",
    )
    preferred_approver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[preferred_approver_id],
        lazy="select",
    )
    decided_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[decided_by_id],
        lazy="select",
    )
    assigned_to: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_to_id],
        lazy="select",
    )
    history: Mapped[List["ApprovalHistory"]] = relationship(
        "ApprovalHistory",
        back_populates="approval",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="ApprovalHistory.created_at.desc()",
    )
    
    __table_args__ = (
        Index("ix_announcement_approvals_announcement", "announcement_id"),
        Index("ix_announcement_approvals_status", "approval_status"),
        Index("ix_announcement_approvals_urgent", "is_urgent_request"),
        Index("ix_announcement_approvals_pending", "approval_status", "submitted_at"),
        Index("ix_announcement_approvals_sla", "sla_deadline", "sla_breached"),
        Index("ix_announcement_approvals_assigned", "assigned_to_id", "approval_status"),
        CheckConstraint(
            "approval_status IN ('pending', 'approved', 'rejected', 'not_required')",
            name="ck_announcement_approvals_status_valid",
        ),
        CheckConstraint(
            "(approval_status = 'pending') OR "
            "(approval_status != 'pending' AND decided_by_id IS NOT NULL AND decided_at IS NOT NULL)",
            name="ck_announcement_approvals_decision_data",
        ),
        {"comment": "Announcement approval tracking"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<AnnouncementApproval(id={self.id}, announcement_id={self.announcement_id}, "
            f"status={self.approval_status})>"
        )


class ApprovalWorkflow(BaseModel, UUIDMixin, TimestampModel):
    """
    Approval workflow configuration.
    
    Defines approval workflows with multiple steps and
    conditional routing.
    """
    
    __tablename__ = "announcement_approval_workflows"
    
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
        comment="User who created the workflow",
    )
    
    # Workflow Configuration
    workflow_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Workflow name",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Workflow description",
    )
    
    # Workflow Steps (ordered)
    steps: Mapped[List[dict]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Ordered list of approval steps",
    )
    
    # Routing Rules
    routing_rules: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Conditional routing rules",
    )
    
    # Default Approvers
    default_approvers: Mapped[Optional[List[UUID]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Default approver user IDs",
    )
    
    # SLA Configuration
    sla_hours: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="SLA in hours for approval",
    )
    
    # Auto-Approval Rules
    auto_approval_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether auto-approval is enabled",
    )
    auto_approval_rules: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Rules for automatic approval",
    )
    
    # Escalation
    escalation_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether escalation is enabled",
    )
    escalation_after_hours: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Hours before escalation",
    )
    escalation_approvers: Mapped[Optional[List[UUID]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Escalation approver user IDs",
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether workflow is active",
    )
    
    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional workflow metadata",
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
        Index("ix_approval_workflows_hostel", "hostel_id"),
        Index("ix_approval_workflows_active", "is_active"),
        CheckConstraint(
            "sla_hours IS NULL OR sla_hours > 0",
            name="ck_approval_workflows_sla_positive",
        ),
        CheckConstraint(
            "escalation_after_hours IS NULL OR escalation_after_hours > 0",
            name="ck_approval_workflows_escalation_positive",
        ),
        {"comment": "Approval workflow configurations"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<ApprovalWorkflow(id={self.id}, name='{self.workflow_name}', "
            f"hostel_id={self.hostel_id}, active={self.is_active})>"
        )


class ApprovalHistory(BaseModel, UUIDMixin, TimestampModel):
    """
    Approval history entry for audit trail.
    
    Records each action in the approval workflow for
    complete audit trail.
    """
    
    __tablename__ = "announcement_approval_history"
    
    # Foreign Keys
    approval_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcement_approvals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated approval",
    )
    announcement_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated announcement",
    )
    performed_by_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who performed the action",
    )
    
    # Action Details
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Action taken (submitted, approved, rejected, resubmitted, etc.)",
    )
    previous_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Status before action",
    )
    new_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Status after action",
    )
    
    # Actor Information
    performed_by_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Name of user who performed action (cached)",
    )
    performed_by_role: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Role of user who performed action",
    )
    
    # Action Details
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes about the action",
    )
    
    # Timestamp
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When action was performed",
    )
    
    # Additional Data
    action_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional action-specific data",
    )
    
    # Relationships
    approval: Mapped["AnnouncementApproval"] = relationship(
        "AnnouncementApproval",
        back_populates="history",
    )
    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        lazy="select",
    )
    performed_by: Mapped[Optional["User"]] = relationship(
        "User",
        lazy="select",
    )
    
    __table_args__ = (
        Index("ix_approval_history_approval", "approval_id"),
        Index("ix_approval_history_announcement", "announcement_id"),
        Index("ix_approval_history_performed_at", "performed_at"),
        Index("ix_approval_history_action", "action"),
        {"comment": "Approval action history for audit trail"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<ApprovalHistory(id={self.id}, approval_id={self.approval_id}, "
            f"action={self.action}, performed_at={self.performed_at})>"
        )


class ApprovalRule(BaseModel, UUIDMixin, TimestampModel):
    """
    Automatic approval rules.
    
    Defines conditions under which announcements can be
    automatically approved without manual review.
    """
    
    __tablename__ = "announcement_approval_rules"
    
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
        comment="User who created the rule",
    )
    
    # Rule Configuration
    rule_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Rule name",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Rule description",
    )
    
    # Rule Conditions
    conditions: Mapped[List[dict]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Conditions that must be met for auto-approval",
    )
    
    # Priority
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Rule evaluation priority",
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether rule is active",
    )
    
    # Usage Tracking
    times_applied: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times rule has been applied",
    )
    last_applied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When rule was last applied",
    )
    
    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional rule metadata",
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
        Index("ix_approval_rules_hostel", "hostel_id"),
        Index("ix_approval_rules_active", "is_active"),
        Index("ix_approval_rules_priority", "priority"),
        CheckConstraint(
            "times_applied >= 0",
            name="ck_approval_rules_times_applied",
        ),
        {"comment": "Automatic approval rules"},
    )
    
    def __repr__(self) -> str:
        return (
            f"<ApprovalRule(id={self.id}, name='{self.rule_name}', "
            f"hostel_id={self.hostel_id}, active={self.is_active})>"
        )