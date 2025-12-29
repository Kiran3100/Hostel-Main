"""
Admin Override Model

Tracks admin overrides of supervisor decisions with comprehensive audit trails,
impact assessment, and analytics for accountability and performance monitoring.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Numeric,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin, AuditMixin

if TYPE_CHECKING:
    from app.models.admin.admin_user import AdminUser
    from app.models.supervisor.supervisor import Supervisor
    from app.models.hostel.hostel import Hostel

__all__ = [
    "AdminOverride",
    "OverrideReason",
    "OverrideApproval",
    "OverrideImpact",
]


class AdminOverride(TimestampModel, UUIDMixin, AuditMixin):
    """
    Admin override of supervisor decisions.
    
    Comprehensive tracking of all instances where an admin overrides
    a supervisor's action or decision, with full audit trail and
    impact assessment for accountability.
    
    Supports:
        - Multiple override types (complaint, maintenance, booking, etc.)
        - Detailed reason tracking
        - Original and override action comparison
        - Impact assessment
        - Notification and escalation
    """
    
    __tablename__ = "admin_overrides"
    __table_args__ = (
        Index("idx_override_admin_id", "admin_id"),
        Index("idx_override_supervisor_id", "supervisor_id"),
        Index("idx_override_hostel_id", "hostel_id"),
        Index("idx_override_type", "override_type"),
        Index("idx_override_entity", "entity_type", "entity_id"),
        Index("idx_override_timestamp", "override_timestamp"),
    )
    
    # Foreign Keys
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin who performed the override"
    )
    
    supervisor_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("supervisors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Supervisor whose action was overridden"
    )
    
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel where override occurred"
    )
    
    # Override Classification
    override_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of override (complaint_reassignment, maintenance_approval, etc.)"
    )
    
    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of entity being modified (complaint, maintenance_request, etc.)"
    )
    
    entity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="ID of the entity being modified"
    )
    
    # Override Details
    override_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When the override occurred"
    )
    
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed reason for the override"
    )
    
    reason_category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Categorized reason (policy_violation, quality_issue, etc.)"
    )
    
    # Action Comparison
    original_action: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Original supervisor action details"
    )
    
    override_action: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Admin's override action details"
    )
    
    action_diff: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Computed differences between original and override actions"
    )
    
    # Impact Assessment
    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="medium",
        index=True,
        comment="Override severity (low, medium, high, critical)"
    )
    
    impact_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Calculated impact score (0-100)"
    )
    
    financial_impact: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Financial impact of the override"
    )
    
    affected_parties: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of affected parties (students, staff, etc.)"
    )
    
    # Notification
    supervisor_notified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Supervisor was notified of override"
    )
    
    supervisor_notified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When supervisor was notified"
    )
    
    notification_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="How supervisor was notified (email, sms, in-app)"
    )
        
    # Approval (for high-severity overrides)
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Override requires higher-level approval"
    )
    
    approval_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Approval status (pending, approved, rejected)"
    )
    
    approved_by_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Senior admin who approved the override"
    )
    
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When override was approved"
    )
    
    approval_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Approval/rejection notes"
    )
    
    # Reversal
    is_reversed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Override was reversed"
    )
    
    reversed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When override was reversed"
    )
    
    reversed_by_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who reversed the override"
    )
    
    reversal_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for reversal"
    )
    
    # Additional Data - RENAMED from 'metadata' to avoid SQLAlchemy conflict
    additional_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional override metadata"
    )
    
    tags: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Tags for categorization and search"
    )
    
    # Relationships
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        back_populates="overrides",
        lazy="select",
        foreign_keys=[admin_id]
    )
    
    supervisor: Mapped[Optional["Supervisor"]] = relationship(
        "Supervisor",
        back_populates="admin_overrides",
        lazy="select",
        foreign_keys=[supervisor_id]
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[hostel_id]
    )
    
    approved_by: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[approved_by_id]
    )
    
    reversed_by: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[reversed_by_id]
    )
    
    override_impact: Mapped[Optional["OverrideImpact"]] = relationship(
        "OverrideImpact",
        back_populates="override",
        lazy="select",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    # Hybrid Properties
    @hybrid_property
    def is_pending_approval(self) -> bool:
        """Check if override is pending approval."""
        return self.requires_approval and self.approval_status == "pending"
    
    @hybrid_property
    def is_approved(self) -> bool:
        """Check if override is approved."""
        return not self.requires_approval or self.approval_status == "approved"
    
    @hybrid_property
    def hours_since_override(self) -> int:
        """Calculate hours since override occurred."""
        delta = datetime.utcnow() - self.override_timestamp
        return int(delta.total_seconds() // 3600)
    
    @hybrid_property
    def is_high_impact(self) -> bool:
        """Check if this is a high-impact override."""
        return (
            self.severity in ("high", "critical") or
            (self.impact_score and self.impact_score > 70) or
            (self.financial_impact and self.financial_impact > 1000)
        )
    
    def __repr__(self) -> str:
        return (
            f"<AdminOverride(id={self.id}, admin_id={self.admin_id}, "
            f"type='{self.override_type}', severity='{self.severity}')>"
        )


class OverrideReason(TimestampModel, UUIDMixin):
    """
    Predefined override reasons for standardization.
    
    Provides common override reasons to ensure consistency
    and facilitate analytics across the system.
    """
    
    __tablename__ = "override_reasons"
    __table_args__ = (
        Index("idx_override_reason_code", "reason_code"),
        Index("idx_override_reason_category", "category"),
    )
    
    # Reason Definition
    reason_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique reason code"
    )
    
    reason_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Reason description"
    )
    
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Reason category (policy, quality, emergency, etc.)"
    )
    
    # Configuration
    requires_detailed_explanation: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Requires detailed explanation beyond standard text"
    )
    
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Override with this reason requires approval"
    )
    
    severity_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="medium",
        comment="Default severity for this reason"
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Reason is active and available for selection"
    )
    
    # Analytics
    usage_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times this reason has been used"
    )
    
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time this reason was used"
    )
    
    # Display
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order in UI"
    )
    
    icon: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Icon for UI display"
    )
    
    def __repr__(self) -> str:
        return (
            f"<OverrideReason(id={self.id}, code='{self.reason_code}', "
            f"category='{self.category}')>"
        )


class OverrideApproval(TimestampModel, UUIDMixin):
    """
    Higher-level approval for significant overrides.
    
    Tracks approval workflow for overrides that require additional
    authorization due to severity, financial impact, or policy.
    """
    
    __tablename__ = "override_approvals"
    __table_args__ = (
        Index("idx_override_approval_override_id", "override_id"),
        Index("idx_override_approval_approver_id", "approver_id"),
        Index("idx_override_approval_status", "approval_status"),
        Index("idx_override_approval_timestamp", "created_at"),
    )
    
    # Foreign Keys
    override_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_overrides.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Override requiring approval"
    )
    
    approver_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin approver"
    )
    
    # Approval Details
    approval_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        comment="Approval status (pending, approved, rejected, expired)"
    )
    
    decision_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When approval decision was made"
    )
    
    decision_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes on the approval decision"
    )
    
    # Conditions
    conditions: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Conditions or requirements for approval"
    )
    
    conditions_met: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="All approval conditions have been met"
    )
    
    # Escalation
    escalation_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Escalation level (1 = first level, 2 = second level, etc.)"
    )
    
    escalated_from_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("override_approvals.id", ondelete="SET NULL"),
        nullable=True,
        comment="Previous approval if escalated"
    )
    
    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Approval request expiration"
    )
    
    # Relationships
    override: Mapped["AdminOverride"] = relationship(
        "AdminOverride",
        lazy="select",
        foreign_keys=[override_id]
    )
    
    approver: Mapped["AdminUser"] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[approver_id]
    )
    
    escalated_from: Mapped[Optional["OverrideApproval"]] = relationship(
        "OverrideApproval",
        remote_side="OverrideApproval.id",
        lazy="select",
        foreign_keys=[escalated_from_id]
    )
    
    @hybrid_property
    def is_expired(self) -> bool:
        """Check if approval request has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @hybrid_property
    def response_time_hours(self) -> Optional[int]:
        """Calculate response time in hours."""
        if not self.decision_timestamp:
            return None
        delta = self.decision_timestamp - self.created_at
        return int(delta.total_seconds() // 3600)
    
    def __repr__(self) -> str:
        return (
            f"<OverrideApproval(id={self.id}, override_id={self.override_id}, "
            f"status='{self.approval_status}')>"
        )


class OverrideImpact(TimestampModel, UUIDMixin):
    """
    Impact assessment and tracking for overrides.
    
    Detailed analysis of the impact of each override on operations,
    finances, stakeholders, and performance metrics.
    """
    
    __tablename__ = "override_impacts"
    __table_args__ = (
        Index("idx_override_impact_override_id", "override_id"),
        Index("idx_override_impact_score", "overall_impact_score"),
    )
    
    # Foreign Keys
    override_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_overrides.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Override being assessed"
    )
    
    # Impact Scores (0-100)
    operational_impact_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Impact on operations (0-100)"
    )
    
    financial_impact_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Financial impact score (0-100)"
    )
    
    stakeholder_impact_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Impact on stakeholders (0-100)"
    )
    
    reputation_impact_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Reputational impact (0-100)"
    )
    
    overall_impact_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        index=True,
        comment="Overall weighted impact score (0-100)"
    )
    
    # Financial Impact Details
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Estimated cost of the override"
    )
    
    actual_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Actual realized cost"
    )
    
    cost_savings: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Cost savings from the override"
    )
    
    revenue_impact: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Impact on revenue (positive or negative)"
    )
    
    # Stakeholder Impact
    students_affected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of students affected"
    )
    
    staff_affected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of staff members affected"
    )
    
    affected_parties_details: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed list of affected parties"
    )
    
    # Operational Impact
    process_delay_hours: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Delay caused to processes (hours)"
    )
    
    services_disrupted: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of disrupted services"
    )
    
    # Outcome Tracking
    outcome_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Outcome status (positive, negative, neutral, pending)"
    )
    
    outcome_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description of the outcome"
    )
    
    lessons_learned: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Lessons learned from this override"
    )
    
    # Follow-up
    follow_up_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Follow-up action required"
    )
    
    follow_up_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Follow-up has been completed"
    )
    
    follow_up_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Follow-up action notes"
    )
    
    # Assessment Metadata
    assessed_by_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who performed impact assessment"
    )
    
    assessed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When impact was assessed"
    )
    
    # Relationships
    override: Mapped["AdminOverride"] = relationship(
        "AdminOverride",
        back_populates="override_impact",
        lazy="select"
    )
    
    assessed_by: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[assessed_by_id]
    )
    
    @hybrid_property
    def total_people_affected(self) -> int:
        """Total number of people affected."""
        return self.students_affected + self.staff_affected
    
    @hybrid_property
    def net_financial_impact(self) -> Decimal:
        """Calculate net financial impact."""
        cost = self.actual_cost or self.estimated_cost or Decimal("0.00")
        savings = self.cost_savings or Decimal("0.00")
        revenue = self.revenue_impact or Decimal("0.00")
        return revenue + savings - cost
    
    @hybrid_property
    def is_high_impact(self) -> bool:
        """Check if this is a high-impact override."""
        return float(self.overall_impact_score) >= 70.0
    
    def __repr__(self) -> str:
        return (
            f"<OverrideImpact(id={self.id}, override_id={self.override_id}, "
            f"score={self.overall_impact_score})>"
        )