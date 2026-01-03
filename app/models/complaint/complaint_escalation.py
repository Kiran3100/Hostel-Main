"""
Complaint escalation tracking model.

Handles complaint escalation workflow, auto-escalation rules,
and escalation history management with performance tracking.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
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

__all__ = ["ComplaintEscalation", "AutoEscalationRule"]


class ComplaintEscalation(BaseModel, TimestampMixin):
    """
    Complaint escalation tracking.
    
    Maintains complete escalation history with reasons, response tracking,
    and resolution outcomes for each escalation level.
    
    Attributes:
        complaint_id: Associated complaint identifier
        escalated_to: User ID to whom complaint was escalated
        escalated_by: User ID who performed escalation
        escalated_at: Escalation timestamp
        
        escalation_level: Escalation level (1, 2, 3, etc.)
        escalation_reason: Detailed reason for escalation
        is_urgent: Urgent escalation flag
        
        status_before: Complaint status before escalation
        status_after: Complaint status after escalation
        priority_before: Priority level before escalation
        priority_after: Priority level after escalation
        
        responded_at: Response timestamp
        responded_by: User who responded to escalation
        response_notes: Response notes and actions taken
        
        resolved_at: Escalation resolution timestamp
        resolved_after_escalation: Flag if complaint resolved after this escalation
        resolution_time_hours: Time taken to respond in hours
        
        auto_escalated: Flag indicating automatic escalation
        auto_escalation_rule_id: Auto-escalation rule that triggered this
        
        metadata: Additional escalation metadata
    """

    __tablename__ = "complaint_escalations"
    __table_args__ = (
        # Indexes
        Index("ix_complaint_escalations_complaint_id", "complaint_id"),
        Index("ix_complaint_escalations_escalated_to", "escalated_to"),
        Index("ix_complaint_escalations_escalated_at", "escalated_at"),
        Index("ix_complaint_escalations_level", "escalation_level"),
        Index("ix_complaint_escalations_urgent", "is_urgent"),
        Index("ix_complaint_escalations_auto", "auto_escalated"),
        
        # Check constraints
        CheckConstraint(
            "escalation_level > 0",
            name="check_escalation_level_positive",
        ),
        CheckConstraint(
            "resolution_time_hours IS NULL OR resolution_time_hours >= 0",
            name="check_resolution_time_positive",
        ),
        CheckConstraint(
            "responded_at IS NULL OR responded_at >= escalated_at",
            name="check_responded_after_escalated",
        ),
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= escalated_at",
            name="check_resolved_after_escalated",
        ),
        
        {"comment": "Complaint escalation history and tracking"},
    )

    # Foreign Keys
    complaint_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated complaint identifier",
    )
    
    escalated_to: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="User ID to whom complaint was escalated",
    )
    
    escalated_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="User ID who performed escalation",
    )

    # Escalation Details
    escalated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Escalation timestamp",
    )
    
    escalation_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        index=True,
        comment="Escalation level (1, 2, 3, etc.)",
    )
    
    escalation_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed reason for escalation",
    )
    
    is_urgent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Urgent escalation flag",
    )

    # State Tracking
    status_before: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Complaint status before escalation",
    )
    
    status_after: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Complaint status after escalation",
    )
    
    priority_before: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Priority level before escalation",
    )
    
    priority_after: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Priority level after escalation",
    )

    # Response Tracking
    responded_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Response timestamp",
    )
    
    responded_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who responded to escalation",
    )
    
    response_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Response notes and actions taken",
    )

    # Resolution Tracking
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Escalation resolution timestamp",
    )
    
    resolved_after_escalation: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Flag if complaint resolved after this escalation",
    )
    
    resolution_time_hours: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Time taken to respond in hours",
    )

    # Auto-Escalation
    auto_escalated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Flag indicating automatic escalation",
    )
    
    auto_escalation_rule_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("auto_escalation_rules.id", ondelete="SET NULL"),
        nullable=True,
        comment="Auto-escalation rule that triggered this",
    )

    # Metadata
    escalation_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Additional escalation metadata",
    )

    # Relationships
    complaint: Mapped["Complaint"] = relationship(
        "Complaint",
        back_populates="escalations",
        lazy="joined",
    )
    
    escalated_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[escalated_to],
        lazy="joined",
    )
    
    escalator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[escalated_by],
        lazy="selectin",
    )
    
    responder: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[responded_by],
        lazy="selectin",
    )
    
    auto_rule: Mapped[Optional["AutoEscalationRule"]] = relationship(
        "AutoEscalationRule",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation of ComplaintEscalation."""
        return (
            f"<ComplaintEscalation(id={self.id}, "
            f"complaint_id={self.complaint_id}, "
            f"level={self.escalation_level}, "
            f"auto={self.auto_escalated})>"
        )

    def calculate_resolution_time(self) -> None:
        """Calculate and update resolution_time_hours."""
        if self.responded_at:
            delta = self.responded_at - self.escalated_at
            self.resolution_time_hours = int(delta.total_seconds() / 3600)


class AutoEscalationRule(BaseModel, TimestampMixin):
    """
    Auto-escalation rule configuration.
    
    Defines automatic escalation triggers based on time, SLA conditions,
    and priority levels with configurable escalation chains.
    
    Attributes:
        hostel_id: Hostel identifier for rule scope
        rule_name: Descriptive rule name
        
        escalate_after_hours: Hours before auto-escalation
        escalate_on_sla_breach: Auto-escalate on SLA breach flag
        
        urgent_escalation_hours: Threshold for urgent complaints
        high_escalation_hours: Threshold for high priority
        medium_escalation_hours: Threshold for medium priority
        low_escalation_hours: Threshold for low priority
        
        first_escalation_to: First level escalation target user ID
        second_escalation_to: Second level escalation target
        third_escalation_to: Third level escalation target
        
        is_active: Rule active status
        priority: Rule priority for conflict resolution
        
        conditions: Additional escalation conditions (JSONB)
        metadata: Additional rule metadata
    """

    __tablename__ = "auto_escalation_rules"
    __table_args__ = (
        # Indexes
        Index("ix_auto_escalation_rules_hostel_id", "hostel_id"),
        Index("ix_auto_escalation_rules_active", "is_active"),
        Index("ix_auto_escalation_rules_priority", "priority"),
        
        # Check constraints
        CheckConstraint(
            "escalate_after_hours > 0",
            name="check_escalate_hours_positive",
        ),
        CheckConstraint(
            "urgent_escalation_hours > 0 AND high_escalation_hours > 0 AND "
            "medium_escalation_hours > 0 AND low_escalation_hours > 0",
            name="check_priority_hours_positive",
        ),
        CheckConstraint(
            "urgent_escalation_hours < high_escalation_hours AND "
            "high_escalation_hours < medium_escalation_hours AND "
            "medium_escalation_hours < low_escalation_hours",
            name="check_priority_hours_logical",
        ),
        CheckConstraint(
            "priority > 0",
            name="check_priority_positive",
        ),
        
        {"comment": "Auto-escalation rule configuration"},
    )

    # Hostel Association
    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel identifier for rule scope",
    )
    
    rule_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Descriptive rule name",
    )

    # Base Escalation Settings
    escalate_after_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=24,
        comment="Hours before auto-escalation (default)",
    )
    
    escalate_on_sla_breach: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Auto-escalate on SLA breach flag",
    )

    # Priority-Specific Thresholds
    urgent_escalation_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=4,
        comment="Escalation threshold for urgent complaints (hours)",
    )
    
    high_escalation_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=12,
        comment="Escalation threshold for high priority (hours)",
    )
    
    medium_escalation_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=24,
        comment="Escalation threshold for medium priority (hours)",
    )
    
    low_escalation_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=48,
        comment="Escalation threshold for low priority (hours)",
    )

    # Escalation Chain
    first_escalation_to: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="First level escalation target user ID",
    )
    
    second_escalation_to: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Second level escalation target",
    )
    
    third_escalation_to: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Third level escalation target",
    )

    # Rule Management
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Rule active status",
    )
    
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        index=True,
        comment="Rule priority for conflict resolution",
    )

    # Additional Conditions (JSONB for flexibility)
    conditions: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Additional escalation conditions",
    )
    
    escalation_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Additional rule metadata",
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="joined",
    )
    
    first_escalation_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[first_escalation_to],
        lazy="selectin",
    )
    
    second_escalation_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[second_escalation_to],
        lazy="selectin",
    )
    
    third_escalation_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[third_escalation_to],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation of AutoEscalationRule."""
        return (
            f"<AutoEscalationRule(id={self.id}, "
            f"hostel_id={self.hostel_id}, "
            f"rule_name={self.rule_name}, "
            f"is_active={self.is_active})>"
        )

    def get_threshold_for_priority(self, priority: str) -> int:
        """Get escalation threshold for given priority."""
        priority_map = {
            "CRITICAL": self.urgent_escalation_hours,
            "URGENT": self.urgent_escalation_hours,
            "HIGH": self.high_escalation_hours,
            "MEDIUM": self.medium_escalation_hours,
            "LOW": self.low_escalation_hours,
        }
        return priority_map.get(priority.upper(), self.escalate_after_hours)