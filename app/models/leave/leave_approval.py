# --- File: C:\Hostel-Main\app\models\leave\leave_approval.py ---
"""
Leave approval workflow database models.

Provides SQLAlchemy models for leave approval processes,
multi-level approvals, and approval tracking.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import UUIDMixin
from app.models.common.enums import LeaveStatus

if TYPE_CHECKING:
    from app.models.leave.leave_application import LeaveApplication
    from app.models.user.user import User

__all__ = [
    "LeaveApproval",
    "LeaveApprovalWorkflow",
    "LeaveApprovalStep",
]


class LeaveApproval(BaseModel, TimestampModel, UUIDMixin):
    """
    Leave approval decision tracking.
    
    Records individual approval/rejection decisions with
    complete audit trail and decision rationale.
    """
    
    __tablename__ = "leave_approvals"
    __table_args__ = (
        Index("ix_leave_approval_leave_id", "leave_id"),
        Index("ix_leave_approval_approver_id", "approver_id"),
        Index("ix_leave_approval_decision_at", "decision_at"),
        Index("ix_leave_approval_is_approved", "is_approved"),
        {"comment": "Leave approval decisions and tracking"}
    )

    # Reference to leave application
    leave_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_applications.id", ondelete="CASCADE"),
        nullable=False,
        comment="Leave application being approved/rejected"
    )

    # Approver details
    approver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User making approval decision"
    )
    
    approver_role: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Role of approver at time of decision"
    )

    # Decision details
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="True if approved, False if rejected"
    )
    
    decision_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Decision timestamp"
    )
    
    decision_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notes explaining the decision"
    )

    # Approval-specific fields
    approval_comments: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Comments when approving"
    )
    
    conditions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Conditions for approved leave"
    )

    # Rejection-specific fields
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for rejection"
    )
    
    rejection_category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Category of rejection reason"
    )

    # Workflow tracking
    approval_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Approval level in multi-level workflow"
    )
    
    is_final_decision: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this is the final approval decision"
    )
    
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_approval_workflows.id", ondelete="SET NULL"),
        nullable=True,
        comment="Associated approval workflow"
    )

    # Notification tracking
    student_notified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether student was notified of decision"
    )
    
    student_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Student notification timestamp"
    )
    
    guardian_notified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether guardian was notified"
    )
    
    guardian_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Guardian notification timestamp"
    )

    # Administrative fields
    is_auto_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether approval was automatic"
    )
    
    auto_approval_rule: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Rule that triggered auto-approval"
    )

    # Device and IP tracking
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of approver"
    )
    
    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="User agent string"
    )

    # Relationships
    leave_application: Mapped["LeaveApplication"] = relationship(
        "LeaveApplication",
        back_populates="approvals",
        lazy="select"
    )
    
    approver: Mapped["User | None"] = relationship(
        "User",
        lazy="select"
    )
    
    workflow: Mapped["LeaveApprovalWorkflow | None"] = relationship(
        "LeaveApprovalWorkflow",
        back_populates="approval_steps",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveApproval(id={self.id}, leave_id={self.leave_id}, "
            f"approved={self.is_approved}, approver_id={self.approver_id})>"
        )


class LeaveApprovalWorkflow(BaseModel, TimestampModel, UUIDMixin):
    """
    Multi-level approval workflow configuration.
    
    Defines approval workflows for different leave types,
    durations, or student categories.
    """
    
    __tablename__ = "leave_approval_workflows"
    __table_args__ = (
        Index("ix_leave_approval_workflow_hostel_id", "hostel_id"),
        Index("ix_leave_approval_workflow_is_active", "is_active"),
        {"comment": "Leave approval workflow configurations"}
    )

    # Workflow identification
    workflow_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Workflow name"
    )
    
    workflow_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Workflow description"
    )

    # Scope
    hostel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        comment="Hostel this workflow applies to (NULL=all hostels)"
    )
    
    leave_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Leave type this workflow applies to (NULL=all types)"
    )

    # Approval levels
    requires_multi_level: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether workflow requires multiple approval levels"
    )
    
    total_levels: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Total number of approval levels"
    )
    
    parallel_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether approvals can happen in parallel"
    )

    # Automatic approval rules
    auto_approve_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether automatic approval is enabled"
    )
    
    auto_approve_max_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum days for auto-approval"
    )
    
    auto_approve_conditions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Conditions for automatic approval (JSON)"
    )

    # Escalation rules
    escalation_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether escalation is enabled"
    )
    
    escalation_hours: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Hours before escalation"
    )
    
    escalation_role: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Role to escalate to"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether workflow is active"
    )
    
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Workflow effective start date"
    )
    
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Workflow effective end date"
    )

    # Priority
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Workflow priority (higher number = higher priority)"
    )

    # Relationships
    approval_steps: Mapped[list["LeaveApproval"]] = relationship(
        "LeaveApproval",
        back_populates="workflow",
        lazy="select"
    )
    
    workflow_steps: Mapped[list["LeaveApprovalStep"]] = relationship(
        "LeaveApprovalStep",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="LeaveApprovalStep.step_order",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveApprovalWorkflow(id={self.id}, name={self.workflow_name}, "
            f"levels={self.total_levels}, active={self.is_active})>"
        )


class LeaveApprovalStep(BaseModel, TimestampModel, UUIDMixin):
    """
    Individual steps in approval workflow.
    
    Defines each step in a multi-level approval workflow
    with role requirements and conditions.
    """
    
    __tablename__ = "leave_approval_steps"
    __table_args__ = (
        Index("ix_leave_approval_step_workflow_id", "workflow_id"),
        Index(
            "ix_leave_approval_step_workflow_order",
            "workflow_id",
            "step_order"
        ),
        {"comment": "Steps in leave approval workflows"}
    )

    # Reference to workflow
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_approval_workflows.id", ondelete="CASCADE"),
        nullable=False,
        comment="Approval workflow"
    )

    # Step details
    step_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Step order in workflow (1, 2, 3...)"
    )
    
    step_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Step name"
    )
    
    step_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Step description"
    )

    # Approver requirements
    required_role: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Role required to approve at this step"
    )
    
    required_permission: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Permission required to approve"
    )
    
    specific_approver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Specific user required to approve"
    )

    # Conditions
    conditions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Conditions for this step (JSON)"
    )
    
    skip_if: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Conditions to skip this step (JSON)"
    )

    # SLA
    sla_hours: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="SLA hours for this step"
    )
    
    reminder_hours: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Hours before sending reminder"
    )

    # Delegation
    allow_delegation: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether delegation is allowed at this step"
    )
    
    delegate_to_role: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Role that can be delegated to"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether step is active"
    )

    # Relationships
    workflow: Mapped["LeaveApprovalWorkflow"] = relationship(
        "LeaveApprovalWorkflow",
        back_populates="workflow_steps",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveApprovalStep(id={self.id}, workflow_id={self.workflow_id}, "
            f"order={self.step_order}, name={self.step_name})>"
        )