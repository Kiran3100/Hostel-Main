# --- File: C:\Hostel-Main\app\models\leave\leave_type.py ---
"""
Leave type configuration database models.

Provides SQLAlchemy models for leave type definitions,
policies, and configuration management.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import UUIDMixin, SoftDeleteMixin
from app.models.common.enums import LeaveType

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel

__all__ = [
    "LeaveTypeConfig",
    "LeavePolicy",
    "LeaveBlackoutDate",
]


class LeaveTypeConfig(BaseModel, TimestampModel, UUIDMixin, SoftDeleteMixin):
    """
    Leave type configuration and policies.
    
    Defines detailed configuration for each leave type
    including limits, rules, and requirements.
    """
    
    __tablename__ = "leave_type_configs"
    __table_args__ = (
        UniqueConstraint(
            "leave_type",
            "hostel_id",
            name="uq_leave_type_config_type_hostel"
        ),
        CheckConstraint(
            "max_days_per_year >= 0",
            name="ck_leave_type_config_max_days_non_negative"
        ),
        CheckConstraint(
            "max_consecutive_days > 0",
            name="ck_leave_type_config_consecutive_positive"
        ),
        Index("ix_leave_type_config_leave_type", "leave_type"),
        Index("ix_leave_type_config_hostel_id", "hostel_id"),
        Index("ix_leave_type_config_is_active", "is_active"),
        {"comment": "Leave type configurations and policies"}
    )

    # Leave type identification
    leave_type: Mapped[LeaveType] = mapped_column(
        Enum(LeaveType, name="leave_type_enum", create_type=False),
        nullable=False,
        comment="Leave type"
    )
    
    hostel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        comment="Hostel (NULL=global configuration)"
    )

    # Display information
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Display name for leave type"
    )
    
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description of leave type"
    )
    
    icon: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Icon identifier for UI"
    )
    
    color_code: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,
        comment="Color code for calendar display (#RRGGBB)"
    )

    # Quota and limits
    max_days_per_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Maximum days allowed per year (0=unlimited)"
    )
    
    max_days_per_semester: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum days per semester"
    )
    
    max_days_per_month: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum days per month"
    )
    
    max_consecutive_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        comment="Maximum consecutive days allowed"
    )
    
    min_days_per_application: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Minimum days per application"
    )

    # Application requirements
    min_notice_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Minimum advance notice required (days)"
    )
    
    max_advance_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        comment="Maximum days in advance leave can be applied"
    )
    
    allow_backdated_application: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Allow backdated leave applications"
    )
    
    max_backdated_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Maximum days in past for backdated applications"
    )

    # Documentation requirements
    requires_document: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether supporting document is mandatory"
    )
    
    requires_document_after_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Requires document after N consecutive days"
    )
    
    allowed_document_types: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Allowed document types (JSON array)"
    )

    # Approval requirements
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether leave requires approval"
    )
    
    auto_approve_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Enable automatic approval"
    )
    
    auto_approve_upto_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Auto-approve leaves up to N days"
    )
    
    auto_approve_conditions: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Conditions for auto-approval (JSON)"
    )
    
    approval_workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Associated approval workflow"
    )

    # Contact requirements
    requires_contact_info: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Require contact information during leave"
    )
    
    requires_emergency_contact: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Require emergency contact"
    )
    
    requires_destination: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Require destination address"
    )

    # Carry forward rules
    allow_carry_forward: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Allow unused days to carry forward"
    )
    
    carry_forward_max_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum days that can be carried forward"
    )
    
    carry_forward_expiry_months: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Months after which carried forward days expire"
    )

    # Additional rules
    can_be_cancelled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether leave can be cancelled by student"
    )
    
    cancellation_min_notice_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Minimum hours notice required for cancellation"
    )
    
    allow_partial_days: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Allow half-day or partial day leaves"
    )
    
    count_weekends: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Include weekends in leave duration calculation"
    )
    
    count_holidays: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Include public holidays in leave duration"
    )

    # Priority and display
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order in UI"
    )
    
    is_visible_to_students: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether students can see and apply for this leave type"
    )

    # Status and validity
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether leave type is active"
    )
    
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Effective start date"
    )
    
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Effective end date"
    )

    # Custom fields
    custom_fields: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Custom field definitions (JSON)"
    )
    
    validation_rules: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Custom validation rules (JSON)"
    )

    # Help text
    application_help_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Help text for students applying for this leave type"
    )
    
    policy_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to detailed policy document"
    )

    # Relationships
    hostel: Mapped["Hostel | None"] = relationship(
        "Hostel",
        back_populates="leave_type_configs",
        lazy="select"
    )
    
    blackout_dates: Mapped[list["LeaveBlackoutDate"]] = relationship(
        "LeaveBlackoutDate",
        back_populates="leave_type_config",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveTypeConfig(id={self.id}, type={self.leave_type.value}, "
            f"hostel_id={self.hostel_id}, active={self.is_active})>"
        )


class LeavePolicy(BaseModel, TimestampModel, UUIDMixin):
    """
    Comprehensive leave policy documents.
    
    Stores detailed leave policies with version control
    and acknowledgment tracking.
    """
    
    __tablename__ = "leave_policies"
    __table_args__ = (
        Index("ix_leave_policy_hostel_id", "hostel_id"),
        Index("ix_leave_policy_version", "version"),
        Index("ix_leave_policy_is_active", "is_active"),
        {"comment": "Leave policy documents and versions"}
    )

    # Policy identification
    policy_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Policy name"
    )
    
    policy_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        comment="Unique policy code"
    )
    
    version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Policy version"
    )

    # Scope
    hostel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        comment="Hostel (NULL=applies to all hostels)"
    )
    
    applies_to_leave_types: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Leave types this policy applies to (JSON array)"
    )

    # Policy content
    policy_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Brief policy summary"
    )
    
    policy_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full policy content (HTML/Markdown)"
    )
    
    policy_document_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to PDF or document file"
    )

    # Key points
    key_points: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Key policy points (JSON array)"
    )
    
    restrictions: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Policy restrictions (JSON array)"
    )
    
    requirements: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Policy requirements (JSON array)"
    )

    # Validity
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Policy effective start date"
    )
    
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Policy effective end date (NULL=indefinite)"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether policy is currently active"
    )

    # Acknowledgment requirements
    requires_acknowledgment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether students must acknowledge policy"
    )
    
    acknowledgment_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Text students must agree to"
    )

    # Approval and publishing
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who approved policy"
    )
    
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Policy approval timestamp"
    )
    
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Policy publication timestamp"
    )
    
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who published policy"
    )

    # Version control
    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_policies.id", ondelete="SET NULL"),
        nullable=True,
        comment="Previous version of policy"
    )
    
    change_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Summary of changes from previous version"
    )

    # Relationships
    hostel: Mapped["Hostel | None"] = relationship(
        "Hostel",
        back_populates="leave_policies",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeavePolicy(id={self.id}, code={self.policy_code}, "
            f"version={self.version}, active={self.is_active})>"
        )


class LeaveBlackoutDate(BaseModel, TimestampModel, UUIDMixin):
    """
    Blackout dates when leaves are restricted.
    
    Defines periods when certain leave types cannot be
    applied or must have special approval.
    """
    
    __tablename__ = "leave_blackout_dates"
    __table_args__ = (
        Index("ix_leave_blackout_date_config_id", "leave_type_config_id"),
        Index("ix_leave_blackout_date_start", "blackout_start_date"),
        Index("ix_leave_blackout_date_end", "blackout_end_date"),
        Index(
            "ix_leave_blackout_date_dates",
            "blackout_start_date",
            "blackout_end_date"
        ),
        {"comment": "Leave blackout dates and restrictions"}
    )

    # Reference to leave type config
    leave_type_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_type_configs.id", ondelete="CASCADE"),
        nullable=False,
        comment="Leave type configuration"
    )

    # Blackout period
    blackout_start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Blackout period start"
    )
    
    blackout_end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Blackout period end"
    )

    # Blackout details
    blackout_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Name/title of blackout period"
    )
    
    blackout_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Reason for blackout period"
    )
    
    blackout_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="complete",
        comment="Type of blackout (complete, restricted, special_approval)"
    )

    # Restrictions
    is_complete_blackout: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether leave is completely blocked"
    )
    
    allow_with_special_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Allow with special approval"
    )
    
    special_approval_role: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Role required for special approval"
    )

    # Messaging
    student_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Message to display to students"
    )
    
    admin_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Internal notes for administrators"
    )

    # Recurrence
    is_recurring: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether blackout recurs annually"
    )
    
    recurrence_pattern: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Recurrence pattern (annual, monthly)"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether blackout is active"
    )

    # Relationships
    leave_type_config: Mapped["LeaveTypeConfig"] = relationship(
        "LeaveTypeConfig",
        back_populates="blackout_dates",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveBlackoutDate(id={self.id}, name={self.blackout_name}, "
            f"start={self.blackout_start_date}, end={self.blackout_end_date})>"
        )