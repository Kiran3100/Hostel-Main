"""
Admin Hostel Assignment Model

Manages admin-to-hostel relationships with comprehensive permission tracking,
assignment history, and multi-hostel administration support.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Numeric,
    Index,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin, SoftDeleteMixin, AuditMixin
from app.models.base.enums import PermissionLevel

if TYPE_CHECKING:
    from app.models.admin.admin_user import AdminUser
    from app.models.hostel.hostel import Hostel

__all__ = [
    "AdminHostelAssignment",
    "AssignmentPermission",
    "AssignmentHistory",
    "PrimaryHostelDesignation",
]


class AdminHostelAssignment(TimestampModel, UUIDMixin, SoftDeleteMixin, AuditMixin):
    """
    Admin-to-hostel assignment with comprehensive tracking.
    
    Manages the relationship between admins and hostels, including
    permissions, activity metrics, and performance tracking.
    
    Supports:
        - Multi-hostel admin management
        - Granular permission control per hostel
        - Activity and performance tracking
        - Assignment history and audit trail
        - Primary hostel designation
    """
    
    __tablename__ = "admin_hostel_assignments"
    __table_args__ = (
        UniqueConstraint("admin_id", "hostel_id", "is_deleted", name="uq_admin_hostel_active"),
        Index("idx_assignment_admin_id", "admin_id"),
        Index("idx_assignment_hostel_id", "hostel_id"),
        Index("idx_assignment_status", "is_active", "is_deleted"),
        Index("idx_assignment_primary", "is_primary"),
        Index("idx_assignment_assigned_date", "assigned_date"),
    )
    
    # Foreign Keys
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin user ID"
    )
    
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel ID"
    )
    
    # Assignment Details
    assigned_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        default=date.today,
        index=True,
        comment="Date of assignment"
    )
    
    assigned_by_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who created this assignment"
    )
    
    effective_from: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Effective start date of assignment"
    )
    
    effective_until: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Effective end date of assignment"
    )
    
    # Permission Configuration
    permission_level: Mapped[str] = mapped_column(
        Enum(PermissionLevel, name="permission_level_enum"),
        nullable=False,
        default=PermissionLevel.FULL_ACCESS,
        index=True,
        comment="Overall permission level for this assignment"
    )
    
    permissions: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Granular permissions for this hostel"
    )
    
    # Assignment Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Assignment is currently active"
    )
    
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="This is the admin's primary hostel"
    )
    
    # Revocation Details
    revoked_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="Date assignment was revoked"
    )
    
    revoked_by_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who revoked this assignment"
    )
    
    revoke_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for revocation"
    )
    
    # Activity Tracking
    last_accessed: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Last time admin accessed this hostel"
    )
    
    access_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of times accessed"
    )
    
    total_session_time_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total time spent managing this hostel (minutes)"
    )
    
    # Performance Metrics
    decisions_made: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total decisions/actions made for this hostel"
    )
    
    avg_response_time_minutes: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Average response time for actions (minutes)"
    )
    
    satisfaction_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        comment="Admin satisfaction score for this hostel (0-5)"
    )
    
    # Transfer Management
    transferred_from_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Previous admin (if this is a transfer)"
    )
    
    transfer_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes about the transfer"
    )
    
    handover_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Handover process completed for transfer"
    )
    
    handover_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Handover completion timestamp"
    )
    
    # Metadata
    assignment_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Internal notes about this assignment"
    )
    
    settings: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Assignment-specific settings"
    )
    
    # Relationships
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        back_populates="hostel_assignments",
        lazy="select",
        foreign_keys=[admin_id]
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="admin_assignments",
        lazy="select",
        foreign_keys=[hostel_id]
    )
    
    assigned_by: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[assigned_by_id]
    )
    
    revoked_by: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[revoked_by_id]
    )
    
    transferred_from: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[transferred_from_id]
    )
    
    assignment_permissions: Mapped[List["AssignmentPermission"]] = relationship(
        "AssignmentPermission",
        back_populates="assignment",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    assignment_history: Mapped[List["AssignmentHistory"]] = relationship(
        "AssignmentHistory",
        back_populates="assignment",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Hybrid Properties
    @hybrid_property
    def assignment_duration_days(self) -> int:
        """Calculate assignment duration in days."""
        end_date = self.revoked_date or date.today()
        return (end_date - self.assigned_date).days
    
    @hybrid_property
    def is_recently_accessed(self) -> bool:
        """Check if accessed within last 24 hours."""
        if not self.last_accessed:
            return False
        hours_since = (datetime.utcnow() - self.last_accessed).total_seconds() / 3600
        return hours_since <= 24
    
    @hybrid_property
    def avg_session_duration_minutes(self) -> Decimal:
        """Calculate average session duration."""
        if self.access_count == 0:
            return Decimal("0.00")
        return Decimal(self.total_session_time_minutes) / Decimal(self.access_count)
    
    @hybrid_property
    def is_valid(self) -> bool:
        """Check if assignment is currently valid."""
        today = date.today()
        
        # Check if active and not deleted
        if not self.is_active or self.is_deleted:
            return False
        
        # Check effective dates
        if self.effective_from and today < self.effective_from:
            return False
        
        if self.effective_until and today > self.effective_until:
            return False
        
        # Check if not revoked
        if self.revoked_date:
            return False
        
        return True
    
    def __repr__(self) -> str:
        return (
            f"<AdminHostelAssignment(id={self.id}, admin_id={self.admin_id}, "
            f"hostel_id={self.hostel_id}, active={self.is_active})>"
        )


class AssignmentPermission(TimestampModel, UUIDMixin):
    """
    Specific permission overrides for individual assignments.
    
    Allows fine-grained permission control that overrides default
    admin permissions for specific hostel assignments.
    """
    
    __tablename__ = "assignment_permissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "permission_key", name="uq_assignment_permission"),
        Index("idx_assignment_permission_assignment_id", "assignment_id"),
        Index("idx_assignment_permission_key", "permission_key"),
    )
    
    # Foreign Keys
    assignment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_hostel_assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Assignment ID"
    )
    
    # Permission Details
    permission_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Permission key (e.g., can_manage_rooms)"
    )
    
    permission_value: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Permission granted or denied"
    )
    
    constraint_value: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Constraint value for limit-based permissions"
    )
    
    # Metadata
    set_by_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who set this permission"
    )
    
    set_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When permission was set"
    )
    
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes about this permission override"
    )
    
    # Relationships
    assignment: Mapped["AdminHostelAssignment"] = relationship(
        "AdminHostelAssignment",
        back_populates="assignment_permissions",
        lazy="select"
    )
    
    set_by: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[set_by_id]
    )
    
    def __repr__(self) -> str:
        return (
            f"<AssignmentPermission(id={self.id}, assignment_id={self.assignment_id}, "
            f"key='{self.permission_key}', value={self.permission_value})>"
        )


class AssignmentHistory(TimestampModel, UUIDMixin):
    """
    Historical record of assignment changes.
    
    Tracks all changes to admin-hostel assignments for audit trail,
    compliance, and historical analysis.
    """
    
    __tablename__ = "assignment_history"
    __table_args__ = (
        Index("idx_assignment_history_assignment_id", "assignment_id"),
        Index("idx_assignment_history_action", "action"),
        Index("idx_assignment_history_timestamp", "action_timestamp"),
        Index("idx_assignment_history_admin", "admin_id"),
    )
    
    # Foreign Keys
    assignment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_hostel_assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Assignment ID"
    )
    
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin user ID"
    )
    
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel ID"
    )
    
    # Action Details
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Action performed (created, updated, revoked, reactivated)"
    )
    
    action_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When action occurred"
    )
    
    performed_by_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who performed the action"
    )
    
    # Change Data
    old_values: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Previous values before change"
    )
    
    new_values: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="New values after change"
    )
    
    changed_fields: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of fields that changed"
    )
    
    # Context
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for the change"
    )
    
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of action performer"
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent of action performer"
    )
    
    # Relationships
    assignment: Mapped["AdminHostelAssignment"] = relationship(
        "AdminHostelAssignment",
        back_populates="assignment_history",
        lazy="select"
    )
    
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[admin_id]
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[hostel_id]
    )
    
    performed_by: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[performed_by_id]
    )
    
    def __repr__(self) -> str:
        return (
            f"<AssignmentHistory(id={self.id}, assignment_id={self.assignment_id}, "
            f"action='{self.action}', timestamp={self.action_timestamp})>"
        )


class PrimaryHostelDesignation(TimestampModel, UUIDMixin):
    """
    Primary hostel designation history.
    
    Tracks changes to an admin's primary hostel designation over time,
    maintaining a complete audit trail of primary hostel changes.
    """
    
    __tablename__ = "primary_hostel_designations"
    __table_args__ = (
        Index("idx_primary_designation_admin_id", "admin_id"),
        Index("idx_primary_designation_hostel_id", "hostel_id"),
        Index("idx_primary_designation_dates", "designated_from", "designated_until"),
    )
    
    # Foreign Keys
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin user ID"
    )
    
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel designated as primary"
    )
    
    # Designation Period
    designated_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Start date of primary designation"
    )
    
    designated_until: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="End date of primary designation (NULL if current)"
    )
    
    # Metadata
    designated_by_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who set this designation"
    )
    
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for designation"
    )
    
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="This is the current primary designation"
    )
    
    # Relationships
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[admin_id]
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[hostel_id]
    )
    
    designated_by: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[designated_by_id]
    )
    
    @hybrid_property
    def designation_duration_days(self) -> int:
        """Calculate designation duration in days."""
        end_date = self.designated_until or date.today()
        return (end_date - self.designated_from).days
    
    def __repr__(self) -> str:
        return (
            f"<PrimaryHostelDesignation(id={self.id}, admin_id={self.admin_id}, "
            f"hostel_id={self.hostel_id}, current={self.is_current})>"
        )