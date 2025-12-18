# --- File: C:\Hostel-Main\app\models\hostel\hostel_policy.py ---
"""
Hostel policy model for managing rules and regulations.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel


class HostelPolicy(TimestampModel, UUIDMixin):
    """
    Hostel policy and rules management.
    
    Manages detailed policies, rules, and regulations for hostels
    with version control and acknowledgment tracking.
    """

    __tablename__ = "hostel_policies"

    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to hostel",
    )

    # Policy Information
    policy_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Policy type (general, visitor, payment, conduct, etc.)",
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Policy title",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Brief policy description",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed policy content",
    )

    # Version Control
    version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Policy version",
    )
    version_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Version change notes",
    )

    # Effective Dates
    effective_from: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Policy effective from date",
    )
    effective_until: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        index=True,
        comment="Policy effective until date",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Active status",
    )
    is_mandatory: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Requires acknowledgment",
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Published to students",
    )

    # Display
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order",
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Policy category for grouping",
    )

    # Rich Content
    formatted_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="HTML formatted content",
    )
    attachments: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Policy document attachments",
    )

    # Approval
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Admin who approved policy",
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Approval timestamp",
    )

    # Metadata
    created_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User who created policy",
    )
    last_modified_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User who last modified policy",
    )

    # Analytics
    acknowledgment_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of acknowledgments",
    )
    view_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of views",
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="policies",
    )

    # Table Arguments
    __table_args__ = (
        # Indexes
        Index("idx_policy_hostel_type", "hostel_id", "policy_type"),
        Index("idx_policy_effective", "effective_from", "effective_until"),
        Index("idx_policy_active_published", "is_active", "is_published"),
        Index("idx_policy_category", "category"),
        
        # Check constraints
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name="check_effective_dates_valid",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="check_policy_display_order_positive",
        ),
        CheckConstraint(
            "acknowledgment_count >= 0",
            name="check_acknowledgment_count_positive",
        ),
        CheckConstraint(
            "view_count >= 0",
            name="check_policy_view_count_positive",
        ),
        
        # Unique constraint for active version
        UniqueConstraint(
            "hostel_id",
            "policy_type",
            "version",
            name="uq_hostel_policy_type_version",
        ),
        
        {"comment": "Hostel policies and rules management"},
    )

    def __repr__(self) -> str:
        return (
            f"<HostelPolicy(id={self.id}, hostel_id={self.hostel_id}, "
            f"type='{self.policy_type}', version='{self.version}')>"
        )

    @property
    def is_current(self) -> bool:
        """Check if policy is currently effective."""
        now = datetime.utcnow()
        if not self.is_active:
            return False
        if now < self.effective_from:
            return False
        if self.effective_until and now > self.effective_until:
            return False
        return True

    def increment_views(self) -> None:
        """Increment view count."""
        self.view_count += 1

    def increment_acknowledgments(self) -> None:
        """Increment acknowledgment count."""
        self.acknowledgment_count += 1


class PolicyAcknowledgment(TimestampModel, UUIDMixin):
    """
    Student policy acknowledgment tracking.
    
    Tracks which students have acknowledged which policies.
    """

    __tablename__ = "policy_acknowledgments"

    # Foreign Keys
    policy_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostel_policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to policy",
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to student",
    )

    # Acknowledgment Details
    acknowledged_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        comment="Acknowledgment timestamp",
    )
    policy_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Version acknowledged",
    )

    # Device and IP
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address at acknowledgment",
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="User agent string",
    )

    # Signature/Consent
    digital_signature: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Digital signature if applicable",
    )
    consent_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Specific consent text acknowledged",
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes",
    )

    # Table Arguments
    __table_args__ = (
        Index("idx_acknowledgment_policy", "policy_id"),
        Index("idx_acknowledgment_student", "student_id"),
        Index("idx_acknowledgment_date", "acknowledged_at"),
        UniqueConstraint(
            "policy_id",
            "student_id",
            "policy_version",
            name="uq_policy_student_version_acknowledgment",
        ),
        {"comment": "Student policy acknowledgment tracking"},
    )

    def __repr__(self) -> str:
        return (
            f"<PolicyAcknowledgment(id={self.id}, policy_id={self.policy_id}, "
            f"student_id={self.student_id})>"
        )


class PolicyViolation(TimestampModel, UUIDMixin):
    """
    Policy violation tracking and consequences.
    
    Tracks violations of hostel policies with disciplinary actions.
    """

    __tablename__ = "policy_violations"

    # Foreign Keys
    policy_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostel_policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to violated policy",
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to student",
    )
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to hostel",
    )

    # Violation Details
    violation_date: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Date of violation",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Violation description",
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Severity level (minor, moderate, major, critical)",
    )

    # Evidence
    evidence: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Evidence documents/photos",
    )
    witness_statements: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Witness statements",
    )

    # Reported By
    reported_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="User who reported violation",
    )
    reported_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        comment="Report timestamp",
    )

    # Status and Action
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="reported",
        index=True,
        comment="Violation status",
    )
    action_taken: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Disciplinary action taken",
    )
    action_date: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Action date",
    )

    # Fine/Penalty
    fine_amount: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Fine amount if applicable",
    )
    fine_paid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Fine payment status",
    )

    # Resolution
    resolved_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Admin who resolved",
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Resolution timestamp",
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Resolution notes",
    )

    # Table Arguments
    __table_args__ = (
        Index("idx_violation_student", "student_id", "violation_date"),
        Index("idx_violation_hostel_status", "hostel_id", "status"),
        Index("idx_violation_severity", "severity"),
        CheckConstraint(
            "severity IN ('minor', 'moderate', 'major', 'critical')",
            name="check_violation_severity_valid",
        ),
        CheckConstraint(
            "status IN ('reported', 'investigating', 'confirmed', 'disputed', 'resolved', 'dismissed')",
            name="check_violation_status_valid",
        ),
        CheckConstraint(
            "fine_amount IS NULL OR fine_amount >= 0",
            name="check_fine_amount_positive",
        ),
        {"comment": "Policy violation tracking and management"},
    )

    def __repr__(self) -> str:
        return (
            f"<PolicyViolation(id={self.id}, student_id={self.student_id}, "
            f"severity='{self.severity}', status='{self.status}')>"
        )