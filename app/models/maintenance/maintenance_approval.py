# app/models/maintenance/maintenance_approval.py
"""
Maintenance approval models.

Approval workflow tracking for maintenance requests requiring
authorization based on cost thresholds and policies.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin, AuditMixin


class MaintenanceApproval(BaseModel, UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin):
    """
    Approval workflow tracking for maintenance requests.
    
    Manages approval requests when costs exceed thresholds
    or special authorization is required.
    """
    
    __tablename__ = "maintenance_approvals"
    
    maintenance_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related maintenance request",
    )
    
    # Request details
    requested_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
        comment="User requesting approval (usually supervisor)",
    )
    
    requested_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Approval request timestamp",
    )
    
    # Cost justification
    estimated_cost = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Estimated total cost requiring approval",
    )
    
    cost_breakdown = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Detailed cost breakdown by category",
    )
    
    cost_justification = Column(
        Text,
        nullable=False,
        comment="Detailed justification for cost estimate",
    )
    
    # Approval reason
    approval_reason = Column(
        Text,
        nullable=False,
        comment="Reason why approval is needed",
    )
    
    business_impact = Column(
        Text,
        nullable=True,
        comment="Impact on business/operations if not approved",
    )
    
    # Urgency
    urgent = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether approval is urgent",
    )
    
    urgency_reason = Column(
        Text,
        nullable=True,
        comment="Reason for urgency if urgent",
    )
    
    # Vendor information
    preferred_vendor = Column(
        String(255),
        nullable=True,
        comment="Preferred vendor/contractor",
    )
    
    vendor_quote = Column(
        String(500),
        nullable=True,
        comment="Vendor quote reference or URL",
    )
    
    alternative_quotes = Column(
        Integer,
        nullable=True,
        comment="Number of alternative quotes obtained",
    )
    
    # Timeline
    requested_completion_date = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Requested completion date",
    )
    
    # Approval decision
    approved = Column(
        Boolean,
        nullable=True,
        index=True,
        comment="Whether request was approved (NULL = pending)",
    )
    
    approved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who made approval decision",
    )
    
    approved_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Approval decision timestamp",
    )
    
    # Approved details
    approved_amount = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Approved amount (may differ from requested)",
    )
    
    approval_conditions = Column(
        Text,
        nullable=True,
        comment="Conditions or requirements for approval",
    )
    
    approval_notes = Column(
        Text,
        nullable=True,
        comment="Additional approval notes",
    )
    
    # Rejection details
    rejection_reason = Column(
        Text,
        nullable=True,
        comment="Detailed rejection reason",
    )
    
    suggested_alternative = Column(
        Text,
        nullable=True,
        comment="Suggested alternative approach",
    )
    
    resubmission_allowed = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether request can be resubmitted",
    )
    
    # Workflow tracking
    approval_level = Column(
        String(50),
        nullable=True,
        comment="Approval level (supervisor, admin, senior_management)",
    )
    
    escalated = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether request was escalated to higher authority",
    )
    
    escalated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Escalation timestamp",
    )
    
    escalation_reason = Column(
        Text,
        nullable=True,
        comment="Reason for escalation",
    )
    
    # Notification tracking
    notifications_sent = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether notifications were sent",
    )
    
    # Metadata
    metadata = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional flexible metadata",
    )
    
    # Relationships
    maintenance_request = relationship(
        "MaintenanceRequest",
        back_populates="approvals"
    )
    requester = relationship(
        "User",
        foreign_keys=[requested_by],
        back_populates="approval_requests"
    )
    approver = relationship(
        "User",
        foreign_keys=[approved_by],
        back_populates="approval_decisions"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "estimated_cost >= 0",
            name="ck_approval_estimated_cost_positive"
        ),
        CheckConstraint(
            "approved_amount >= 0",
            name="ck_approval_approved_amount_positive"
        ),
        CheckConstraint(
            "alternative_quotes >= 0",
            name="ck_approval_alternative_quotes_positive"
        ),
        Index("idx_approval_request_pending", "maintenance_request_id", "approved"),
        Index("idx_approval_requester_pending", "requested_by", "approved"),
        Index("idx_approval_approver", "approved_by", "approved_at"),
        {"comment": "Approval workflow tracking for maintenance requests"}
    )
    
    def __repr__(self) -> str:
        status = "Pending" if self.approved is None else ("Approved" if self.approved else "Rejected")
        return f"<MaintenanceApproval {self.maintenance_request_id} - {status}>"
    
    @validates("estimated_cost", "approved_amount")
    def validate_costs(self, key: str, value: Optional[Decimal]) -> Optional[Decimal]:
        """Validate cost values are positive."""
        if value is not None and value < 0:
            raise ValueError(f"{key} must be positive")
        return value
    
    @hybrid_property
    def is_pending(self) -> bool:
        """Check if approval is still pending."""
        return self.approved is None
    
    @hybrid_property
    def is_approved(self) -> bool:
        """Check if request was approved."""
        return self.approved is True
    
    @hybrid_property
    def is_rejected(self) -> bool:
        """Check if request was rejected."""
        return self.approved is False
    
    @hybrid_property
    def response_time_hours(self) -> Optional[float]:
        """Calculate hours taken to respond to approval request."""
        if self.approved_at:
            delta = self.approved_at - self.requested_at
            return delta.total_seconds() / 3600
        return None
    
    def approve(
        self,
        approved_by: UUID,
        approved_amount: Optional[Decimal] = None,
        conditions: Optional[str] = None,
        notes: Optional[str] = None
    ) -> None:
        """
        Approve the maintenance request.
        
        Args:
            approved_by: User ID approving the request
            approved_amount: Approved budget (defaults to requested amount)
            conditions: Any conditions for approval
            notes: Additional approval notes
        """
        self.approved = True
        self.approved_by = approved_by
        self.approved_at = datetime.utcnow()
        self.approved_amount = approved_amount or self.estimated_cost
        self.approval_conditions = conditions
        self.approval_notes = notes
    
    def reject(
        self,
        rejected_by: UUID,
        rejection_reason: str,
        suggested_alternative: Optional[str] = None,
        allow_resubmission: bool = True
    ) -> None:
        """
        Reject the maintenance request.
        
        Args:
            rejected_by: User ID rejecting the request
            rejection_reason: Detailed reason for rejection
            suggested_alternative: Alternative approach suggestion
            allow_resubmission: Whether resubmission is allowed
        """
        self.approved = False
        self.approved_by = rejected_by
        self.approved_at = datetime.utcnow()
        self.rejection_reason = rejection_reason
        self.suggested_alternative = suggested_alternative
        self.resubmission_allowed = allow_resubmission
    
    def escalate(
        self,
        escalation_reason: str,
        new_approval_level: str
    ) -> None:
        """
        Escalate approval to higher authority.
        
        Args:
            escalation_reason: Reason for escalation
            new_approval_level: New approval level
        """
        self.escalated = True
        self.escalated_at = datetime.utcnow()
        self.escalation_reason = escalation_reason
        self.approval_level = new_approval_level


class ApprovalThreshold(BaseModel, UUIDMixin, TimestampModel):
    """
    Approval threshold configuration for hostels.
    
    Defines cost limits and approval requirements for different
    authorization levels.
    """
    
    __tablename__ = "approval_thresholds"
    
    hostel_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel this threshold applies to",
    )
    
    # Supervisor approval threshold
    supervisor_approval_limit = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("5000.00"),
        comment="Maximum amount supervisor can approve independently",
    )
    
    # Admin approval required above
    admin_approval_required_above = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("5000.00"),
        comment="Amount above which admin approval is required",
    )
    
    # Auto-approve threshold
    auto_approve_below = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("1000.00"),
        comment="Amount below which requests are auto-approved",
    )
    
    auto_approve_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether auto-approval is enabled",
    )
    
    # Senior management threshold
    senior_management_required_above = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Amount requiring senior management approval",
    )
    
    # Emergency handling
    emergency_bypass_threshold = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Allow emergency requests to bypass normal thresholds",
    )
    
    emergency_approval_limit = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Special limit for emergency approvals",
    )
    
    # Category-specific thresholds
    category_specific_limits = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Custom limits per maintenance category",
    )
    
    # Approval workflow
    require_multiple_quotes_above = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Amount above which multiple quotes required",
    )
    
    minimum_quotes_required = Column(
        Integer,
        nullable=False,
        default=3,
        comment="Minimum number of quotes for high-value work",
    )
    
    # Configuration metadata
    last_updated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who last updated configuration",
    )
    
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this threshold configuration is active",
    )
    
    # Relationships
    hostel = relationship("Hostel", back_populates="approval_thresholds")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "supervisor_approval_limit >= 0",
            name="ck_threshold_supervisor_limit_positive"
        ),
        CheckConstraint(
            "admin_approval_required_above >= 0",
            name="ck_threshold_admin_limit_positive"
        ),
        CheckConstraint(
            "auto_approve_below >= 0",
            name="ck_threshold_auto_approve_positive"
        ),
        CheckConstraint(
            "minimum_quotes_required >= 1 AND minimum_quotes_required <= 5",
            name="ck_threshold_quotes_range"
        ),
        Index("idx_threshold_hostel_active", "hostel_id", "is_active"),
        {"comment": "Approval threshold configuration per hostel"}
    )
    
    def __repr__(self) -> str:
        return f"<ApprovalThreshold hostel={self.hostel_id}>"
    
    def get_required_approval_level(self, amount: Decimal) -> str:
        """
        Determine required approval level for given amount.
        
        Args:
            amount: Cost amount to check
            
        Returns:
            Required approval level (auto, supervisor, admin, senior_management)
        """
        if self.auto_approve_enabled and amount < self.auto_approve_below:
            return "auto"
        
        if amount <= self.supervisor_approval_limit:
            return "supervisor"
        
        if self.senior_management_required_above and amount >= self.senior_management_required_above:
            return "senior_management"
        
        if amount > self.admin_approval_required_above:
            return "admin"
        
        return "supervisor"


class ApprovalWorkflow(BaseModel, UUIDMixin, TimestampModel):
    """
    Approval workflow state tracking.
    
    Tracks current state of approval process and pending actions.
    """
    
    __tablename__ = "approval_workflows"
    
    maintenance_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_requests.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Related maintenance request",
    )
    
    # Current state
    requires_approval = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether approval is required",
    )
    
    approval_pending = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether approval is currently pending",
    )
    
    approval_level_required = Column(
        String(50),
        nullable=True,
        comment="Required approval level",
    )
    
    # Current approver
    pending_with = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User ID of current pending approver",
    )
    
    # Timeline
    submitted_for_approval_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When request was submitted for approval",
    )
    
    approval_deadline = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Deadline for approval decision",
    )
    
    is_overdue = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether approval is overdue",
    )
    
    # Escalation tracking
    escalation_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times escalated",
    )
    
    last_escalated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last escalation timestamp",
    )
    
    # Multi-level approval tracking
    approval_steps_completed = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of approval steps completed",
    )
    
    total_approval_steps = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Total approval steps required",
    )
    
    previous_approvals = Column(
        JSONB,
        nullable=True,
        default=[],
        comment="Previous approval steps (for multi-level workflows)",
    )
    
    # Metadata
    metadata = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional workflow metadata",
    )
    
    # Relationships
    maintenance_request = relationship(
        "MaintenanceRequest",
        back_populates="approval_workflow"
    )
    current_approver = relationship(
        "User",
        foreign_keys=[pending_with]
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "escalation_count >= 0",
            name="ck_workflow_escalation_count_positive"
        ),
        CheckConstraint(
            "approval_steps_completed >= 0",
            name="ck_workflow_steps_completed_positive"
        ),
        CheckConstraint(
            "total_approval_steps >= 1",
            name="ck_workflow_total_steps_positive"
        ),
        Index("idx_workflow_pending", "approval_pending", "pending_with"),
        Index("idx_workflow_overdue", "is_overdue", "approval_deadline"),
        {"comment": "Approval workflow state tracking"}
    )
    
    def __repr__(self) -> str:
        return f"<ApprovalWorkflow request={self.maintenance_request_id} pending={self.approval_pending}>"
    
    @hybrid_property
    def is_complete(self) -> bool:
        """Check if all approval steps are completed."""
        return self.approval_steps_completed >= self.total_approval_steps
    
    def update_overdue_status(self) -> None:
        """Update overdue status based on current time."""
        if self.approval_pending and self.approval_deadline:
            self.is_overdue = datetime.now(self.approval_deadline.tzinfo) > self.approval_deadline