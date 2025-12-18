# --- File: C:\Hostel-Main\app\models\audit\admin_override_log.py ---
"""
Admin override audit log model.

Tracks admin interventions and overrides of supervisor decisions
for accountability, performance review, and governance.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Index, Integer, String, Text, Numeric,
    ForeignKey, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, INET
from sqlalchemy.orm import relationship, validates

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin


class AdminOverrideLog(BaseModel, TimestampMixin):
    """
    Admin override tracking for governance and accountability.
    
    Records admin interventions in supervisor decisions with
    full context and justification for oversight.
    """
    
    __tablename__ = "admin_override_logs"
    
    # Primary key
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True
    )
    
    # Actors
    admin_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin who performed the override"
    )
    admin_name = Column(
        String(255),
        nullable=True,
        comment="Admin name for display"
    )
    
    supervisor_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Supervisor whose decision was overridden"
    )
    supervisor_name = Column(
        String(255),
        nullable=True,
        comment="Supervisor name for display"
    )
    
    # Context
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel where override occurred"
    )
    hostel_name = Column(
        String(255),
        nullable=True,
        comment="Hostel name for display"
    )
    
    # Override details
    override_type = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of override"
    )
    override_category = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Category of override"
    )
    
    # Entity affected
    entity_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Entity type affected"
    )
    entity_id = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Primary key of affected entity"
    )
    entity_name = Column(
        String(255),
        nullable=True,
        comment="Display name of entity"
    )
    
    # Reason and justification
    reason = Column(
        Text,
        nullable=False,
        comment="Why the override was performed"
    )
    justification_category = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Category of justification"
    )
    
    # Original and override actions
    original_action = Column(
        JSONB,
        nullable=True,
        comment="Supervisor's original action/decision"
    )
    override_action = Column(
        JSONB,
        nullable=False,
        comment="Admin's override decision"
    )
    
    # Impact assessment
    severity = Column(
        String(20),
        nullable=False,
        default="medium",
        index=True,
        comment="Severity/impact of the override"
    )
    urgency = Column(
        String(20),
        nullable=False,
        default="normal",
        index=True,
        comment="Urgency of the override"
    )
    
    # Computed impact score (stored for performance)
    impact_score = Column(
        Numeric(5, 2),
        nullable=False,
        default=50.00,
        comment="Impact score (0-100)"
    )
    
    # Notification
    supervisor_notified = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether supervisor was notified"
    )
    notification_sent_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When notification was sent"
    )
    
    # Approval workflow
    requires_approval = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Requires higher approval"
    )
    approved_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Senior admin who approved"
    )
    approved_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When override was approved"
    )
    
    # Outcome
    outcome = Column(
        String(500),
        nullable=True,
        comment="Outcome of the override"
    )
    outcome_status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Status of override outcome"
    )
    
    # Follow-up
    follow_up_required = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Follow-up action required"
    )
    follow_up_completed = Column(
        Boolean,
        nullable=True,
        comment="Follow-up completed"
    )
    
    # Relationships
    admin = relationship(
        "User",
        foreign_keys=[admin_id],
        backref="admin_overrides"
    )
    supervisor = relationship(
        "User",
        foreign_keys=[supervisor_id],
        backref="overridden_decisions"
    )
    approver = relationship(
        "User",
        foreign_keys=[approved_by],
        backref="approved_overrides"
    )
    hostel = relationship(
        "Hostel",
        backref="admin_overrides"
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_override_admin_created', 'admin_id', 'created_at'),
        Index('idx_override_supervisor_created', 'supervisor_id', 'created_at'),
        Index('idx_override_hostel_created', 'hostel_id', 'created_at'),
        Index('idx_override_type_created', 'override_type', 'created_at'),
        Index('idx_override_category_created', 'override_category', 'created_at'),
        Index('idx_override_entity_created', 'entity_type', 'entity_id', 'created_at'),
        Index('idx_override_severity_created', 'severity', 'created_at'),
        Index('idx_override_urgency_created', 'urgency', 'created_at'),
        Index('idx_override_outcome_created', 'outcome_status', 'created_at'),
        Index('idx_override_approval', 'requires_approval', 'approved_at'),
        Index('idx_override_follow_up', 'follow_up_required', 'follow_up_completed'),
        # Composite indexes
        Index('idx_override_admin_type_created', 'admin_id', 'override_type', 'created_at'),
        Index('idx_override_sup_type_created', 'supervisor_id', 'override_type', 'created_at'),
        # GIN indexes
        Index('idx_override_original_gin', 'original_action', postgresql_using='gin'),
        Index('idx_override_action_gin', 'override_action', postgresql_using='gin'),
        # Constraints
        CheckConstraint(
            "override_category IN ('decision_reversal', 'task_reassignment', 'priority_change', 'approval', 'rejection', 'other')",
            name='ck_override_category'
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name='ck_override_severity'
        ),
        CheckConstraint(
            "urgency IN ('low', 'normal', 'high', 'urgent')",
            name='ck_override_urgency'
        ),
        CheckConstraint(
            "outcome_status IN ('pending', 'successful', 'failed', 'reversed')",
            name='ck_override_outcome_status'
        ),
        CheckConstraint(
            "justification_category IS NULL OR justification_category IN ('quality_issue', 'policy_violation', 'emergency', 'customer_complaint', 'other')",
            name='ck_override_justification'
        ),
        CheckConstraint(
            "impact_score >= 0 AND impact_score <= 100",
            name='ck_override_impact_range'
        ),
        {'comment': 'Admin override tracking for governance'}
    )
    
    @validates('reason')
    def validate_reason(self, key: str, value: str) -> str:
        """Validate override reason."""
        if not value or len(value.strip()) < 10:
            raise ValueError("Override reason must be at least 10 characters")
        if len(value) > 2000:
            raise ValueError("Override reason too long (max 2000 characters)")
        return value.strip()
    
    @validates('impact_score')
    def validate_impact_score(self, key: str, value: Decimal) -> Decimal:
        """Validate impact score range."""
        if value < 0 or value > 100:
            raise ValueError("impact_score must be between 0 and 100")
        return value
    
    def is_pending_approval(self) -> bool:
        """Check if override is pending approval."""
        return self.requires_approval and self.approved_at is None
    
    def __repr__(self) -> str:
        return (
            f"<AdminOverrideLog(id={self.id}, "
            f"admin_id={self.admin_id}, "
            f"supervisor_id={self.supervisor_id}, "
            f"override_type='{self.override_type}')>"
        )