# app/models/mess/menu_approval.py
"""
Menu Approval SQLAlchemy Models.

Complete approval workflow system for menu management with
multi-level approval, history tracking, and compliance monitoring.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, SoftDeleteModel
from app.models.base.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.mess.mess_menu import MessMenu
    from app.models.user.user import User
    from app.models.hostel.hostel import Hostel

__all__ = [
    "MenuApproval",
    "MenuApprovalRequest",
    "ApprovalWorkflow",
    "ApprovalHistory",
    "ApprovalAttempt",
    "ApprovalRule",
    "BulkApproval",
]


class MenuApproval(BaseModel, UUIDMixin, TimestampMixin, SoftDeleteModel):
    """
    Core menu approval entity.
    
    Tracks approval status and workflow for individual menus
    with complete decision history and audit trail.
    """

    __tablename__ = "menu_approvals"

    menu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mess_menus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Approval workflow
    approval_status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
        index=True,
        comment="pending, approved, rejected, approved_with_conditions, revision_requested",
    )
    
    # Current approver
    current_approver_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    current_approver_role: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Approval decision
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    
    # Rejection details
    rejected_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rejected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Approval notes and conditions
    approval_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    conditions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Conditions for conditional approval",
    )
    suggested_changes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Budget approval
    requested_budget: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    approved_budget: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    budget_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Priority and urgency
    priority: Mapped[str] = mapped_column(
        String(20),
        default="normal",
        nullable=False,
        comment="low, normal, high, urgent",
    )
    urgency_level: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="1-10 scale",
    )
    
    # Deadline tracking
    approval_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    is_overdue: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    
    # Escalation
    is_escalated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    escalated_to: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    escalated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    escalation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Revision tracking
    requires_revision: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    revision_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_revision_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Compliance checks
    compliance_checked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    compliance_issues: Mapped[List[str]] = mapped_column(
        ARRAY(String(255)),
        default=list,
        nullable=False,
    )
    nutritional_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    # Auto-approval
    auto_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    auto_approval_rule_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("approval_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Response message
    response_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Next steps
    can_publish: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    requires_resubmission: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    # Additional metadata
    approval_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    menu: Mapped["MessMenu"] = relationship(
        "MessMenu",
        back_populates="approvals",
    )
    current_approver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[current_approver_id],
        back_populates="pending_menu_approvals",
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        back_populates="menu_approvals_given",
    )
    rejecter: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[rejected_by],
        back_populates="menu_rejections_given",
    )
    escalated_to_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[escalated_to],
        back_populates="escalated_menu_approvals",
    )
    
    approval_attempts: Mapped[List["ApprovalAttempt"]] = relationship(
        "ApprovalAttempt",
        back_populates="menu_approval",
        cascade="all, delete-orphan",
        order_by="ApprovalAttempt.attempt_number.asc()",
    )

    __table_args__ = (
        Index("ix_approval_status_deadline", "approval_status", "approval_deadline"),
        Index("ix_approval_overdue", "is_overdue", "approval_deadline"),
        CheckConstraint(
            "urgency_level IS NULL OR (urgency_level >= 1 AND urgency_level <= 10)",
            name="ck_urgency_level_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<MenuApproval(id={self.id}, menu_id={self.menu_id}, "
            f"status={self.approval_status})>"
        )

    @property
    def days_pending(self) -> Optional[int]:
        """Calculate days approval has been pending."""
        if self.approval_status == "pending" and self.created_at:
            return (datetime.utcnow() - self.created_at).days
        return None

    @property
    def time_to_approval_hours(self) -> Optional[float]:
        """Calculate hours taken for approval."""
        if self.approved_at and self.created_at:
            return (self.approved_at - self.created_at).total_seconds() / 3600
        return None


class MenuApprovalRequest(BaseModel, UUIDMixin, TimestampMixin):
    """
    Menu approval request submission.
    
    Records detailed approval request with justification,
    cost estimates, and special requirements.
    """

    __tablename__ = "menu_approval_requests"

    menu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mess_menus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Requester information
    requested_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requested_by_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    requested_by_role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    
    # Request details
    submission_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    urgency: Mapped[str] = mapped_column(
        String(20),
        default="normal",
        nullable=False,
        comment="low, normal, high, urgent",
    )
    
    # Budget information
    estimated_cost_per_person: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    total_estimated_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    expected_students: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    # Special requirements
    requires_special_procurement: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    special_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    procurement_lead_time_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    # Justification
    reason_for_special_menu: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    justification: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    expected_benefits: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Request status
    request_status: Mapped[str] = mapped_column(
        String(30),
        default="submitted",
        nullable=False,
        index=True,
        comment="submitted, under_review, approved, rejected, withdrawn",
    )
    
    # Attachments
    attachment_urls: Mapped[List[str]] = mapped_column(
        ARRAY(String(500)),
        default=list,
        nullable=False,
    )
    
    # Response
    response_received: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    response_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Request metadata
    request_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    menu: Mapped["MessMenu"] = relationship(
        "MessMenu",
        back_populates="approval_requests",
    )
    requester: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="menu_approval_requests",
    )

    __table_args__ = (
        Index("ix_approval_request_status", "request_status", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<MenuApprovalRequest(id={self.id}, menu_id={self.menu_id}, "
            f"status={self.request_status})>"
        )


class ApprovalWorkflow(BaseModel, UUIDMixin, TimestampMixin):
    """
    Menu approval workflow tracking.
    
    Tracks complete workflow state with all stages,
    transitions, and timeline information.
    """

    __tablename__ = "approval_workflows"

    menu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mess_menus.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Workflow configuration
    workflow_type: Mapped[str] = mapped_column(
        String(50),
        default="standard",
        nullable=False,
        comment="standard, expedited, special_occasion, emergency",
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    
    # Current state
    current_stage: Mapped[str] = mapped_column(
        String(30),
        default="draft",
        nullable=False,
        index=True,
        comment="draft, submitted, under_review, approved, rejected, published",
    )
    approval_status: Mapped[str] = mapped_column(
        String(30),
        default="not_required",
        nullable=False,
        comment="not_required, pending, approved, rejected, revision_requested",
    )
    
    # Timeline
    created_at_workflow: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    submitted_for_approval_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    review_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Current handler
    pending_with: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    pending_with_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    pending_with_role: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Deadlines
    approval_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    publication_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_overdue: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    
    # Revision tracking
    revision_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_revision_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revision_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Approval levels
    approval_levels_required: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    approval_levels_completed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Stage history
    stage_history: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Complete stage transition history",
    )
    
    # Performance metrics
    time_in_draft_hours: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    time_in_review_hours: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    time_to_approval_hours: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    total_workflow_hours: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    
    # Workflow metadata
    workflow_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    menu: Mapped["MessMenu"] = relationship(
        "MessMenu",
        back_populates="workflow",
    )
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="menu_workflows",
    )
    pending_with_user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="pending_workflows",
    )

    __table_args__ = (
        Index("ix_workflow_stage_status", "current_stage", "approval_status"),
        Index("ix_workflow_overdue", "is_overdue", "approval_deadline"),
    )

    def __repr__(self) -> str:
        return (
            f"<ApprovalWorkflow(id={self.id}, menu_id={self.menu_id}, "
            f"stage={self.current_stage}, status={self.approval_status})>"
        )

    @property
    def days_pending(self) -> Optional[int]:
        """Calculate days approval has been pending."""
        if self.submitted_for_approval_at and self.approval_status == "pending":
            return (datetime.utcnow() - self.submitted_for_approval_at).days
        return None

    @property
    def completion_percentage(self) -> float:
        """Calculate workflow completion percentage."""
        if self.approval_levels_required == 0:
            return 0.0
        return (self.approval_levels_completed / self.approval_levels_required) * 100


class ApprovalHistory(BaseModel, UUIDMixin, TimestampMixin):
    """
    Complete approval history for menu.
    
    Maintains comprehensive audit trail of all approval
    attempts and decisions.
    """

    __tablename__ = "approval_history"

    menu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mess_menus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Submission information
    total_submissions: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    first_submission_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_submission_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Current status
    current_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    
    # Final decision
    final_decision: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        comment="approved, rejected, withdrawn",
    )
    final_approver: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    final_decision_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Summary statistics
    total_approvals: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_rejections: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_revisions: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Timeline metrics
    average_review_time_hours: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    total_time_in_approval_hours: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    
    # Detailed history (JSON)
    approval_timeline: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Complete chronological approval timeline",
    )
    decision_history: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="All approval decisions with details",
    )
    
    # Comments and feedback summary
    all_comments: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    common_concerns: Mapped[List[str]] = mapped_column(
        ARRAY(String(255)),
        default=list,
        nullable=False,
    )

    # Relationships
    menu: Mapped["MessMenu"] = relationship(
        "MessMenu",
        back_populates="approval_history",
    )

    def __repr__(self) -> str:
        return (
            f"<ApprovalHistory(id={self.id}, menu_id={self.menu_id}, "
            f"submissions={self.total_submissions})>"
        )


class ApprovalAttempt(BaseModel, UUIDMixin, TimestampMixin):
    """
    Individual approval attempt record.
    
    Represents single submission in the approval workflow
    with complete submission details.
    """

    __tablename__ = "approval_attempts"

    menu_approval_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("menu_approvals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Attempt information
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    attempt_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="initial, revision, resubmission, escalation",
    )
    
    # Submitter
    submitted_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_by_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    
    # Reviewer
    reviewed_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_by_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Decision
    decision: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        index=True,
        comment="approved, rejected, revision_requested, pending",
    )
    decision_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Feedback
    feedback: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    suggestions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Changes made (if revision)
    changes_made: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    changes_summary: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    
    # Review time
    review_time_hours: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    
    # Attachments
    attachment_urls: Mapped[List[str]] = mapped_column(
        ARRAY(String(500)),
        default=list,
        nullable=False,
    )
    
    # Attempt metadata
    attempt_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    menu_approval: Mapped["MenuApproval"] = relationship(
        "MenuApproval",
        back_populates="approval_attempts",
    )
    submitter: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[submitted_by],
        back_populates="approval_attempt_submissions",
    )
    reviewer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[reviewed_by],
        back_populates="approval_attempt_reviews",
    )

    __table_args__ = (
        UniqueConstraint(
            "menu_approval_id",
            "attempt_number",
            name="uq_approval_attempt",
        ),
        Index("ix_approval_attempt_decision", "decision", "reviewed_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ApprovalAttempt(id={self.id}, approval_id={self.menu_approval_id}, "
            f"attempt={self.attempt_number}, decision={self.decision})>"
        )


class ApprovalRule(BaseModel, UUIDMixin, TimestampMixin, SoftDeleteModel):
    """
    Automated approval rules configuration.
    
    Defines rules for automatic approval based on various
    criteria to streamline approval process.
    """

    __tablename__ = "approval_rules"

    hostel_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="NULL means global rule",
    )
    
    # Rule information
    rule_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    rule_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    rule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="auto_approve, fast_track, skip_approval, conditional",
    )
    
    # Rule conditions (JSON)
    conditions: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Conditions for rule application",
    )
    
    # Rule criteria
    max_cost_per_person: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    max_total_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    allowed_menu_types: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )
    excluded_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    
    # Time-based criteria
    applies_to_weekdays: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    applies_to_weekends: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    applies_to_special_occasions: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    # Rule priority
    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Higher number = higher priority",
    )
    
    # Rule status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    
    # Effectiveness tracking
    times_applied: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    successful_applications: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Validity period
    valid_from: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    valid_until: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    
    # Created by
    created_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    hostel: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        back_populates="approval_rules",
    )

    __table_args__ = (
        Index("ix_approval_rule_active", "is_active", "hostel_id"),
        Index("ix_approval_rule_priority", "priority", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<ApprovalRule(id={self.id}, name={self.rule_name}, "
            f"type={self.rule_type}, active={self.is_active})>"
        )

    @property
    def success_rate(self) -> float:
        """Calculate rule success rate."""
        if self.times_applied == 0:
            return 0.0
        return (self.successful_applications / self.times_applied) * 100


class BulkApproval(BaseModel, UUIDMixin, TimestampMixin):
    """
    Bulk approval operation tracking.
    
    Records bulk approval/rejection operations for efficiency
    and audit purposes.
    """

    __tablename__ = "bulk_approvals"

    # Operation details
    operation_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="approve, reject",
    )
    
    # Menus affected
    menu_ids: Mapped[List[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        nullable=False,
    )
    total_menus: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    
    # Operator
    approver_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approver_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    # Common decision details
    approval_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    conditions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Budget
    approved_budget_per_menu: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    
    # Operation results
    successful_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    failed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Operation status
    operation_status: Mapped[str] = mapped_column(
        String(20),
        default="processing",
        nullable=False,
        index=True,
        comment="processing, completed, partial_success, failed",
    )
    
    # Execution tracking
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Results details
    success_menu_ids: Mapped[List[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        default=list,
        nullable=False,
    )
    failed_menu_ids: Mapped[List[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        default=list,
        nullable=False,
    )
    error_details: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    approver: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="bulk_approvals",
    )

    __table_args__ = (
        Index("ix_bulk_approval_status", "operation_status", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<BulkApproval(id={self.id}, type={self.operation_type}, "
            f"total={self.total_menus}, status={self.operation_status})>"
        )

    @property
    def success_rate(self) -> float:
        """Calculate operation success rate."""
        if self.total_menus == 0:
            return 0.0
        return (self.successful_count / self.total_menus) * 100