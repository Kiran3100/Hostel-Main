"""
Admin User Model

Extends the base User model with admin-specific capabilities for multi-hostel management.
Supports role hierarchies, cross-hostel access, and comprehensive permission management.
"""

from datetime import datetime
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
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin, SoftDeleteMixin, AuditMixin
from app.models.base.enums import UserRole

if TYPE_CHECKING:
    from app.models.user.user import User
    from app.models.admin.admin_hostel_assignment import AdminHostelAssignment
    from app.models.admin.admin_override import AdminOverride
    from app.models.admin.hostel_context import HostelContext

__all__ = ["AdminUser", "AdminProfile", "AdminRole", "AdminSession"]


class AdminUser(TimestampModel, UUIDMixin, SoftDeleteMixin, AuditMixin):
    """
    Admin User entity with multi-hostel management capabilities.
    
    Extends base User with admin-specific fields including hierarchies,
    permission overrides, and cross-hostel access control.
    
    Relationships:
        - user: One-to-one with User (base user account)
        - hostel_assignments: One-to-many with AdminHostelAssignment
        - admin_profile: One-to-one with AdminProfile
        - overrides: One-to-many with AdminOverride
        - contexts: One-to-many with HostelContext
    """
    
    __tablename__ = "admin_users"
    __table_args__ = (
        Index("idx_admin_user_id", "user_id"),
        Index("idx_admin_is_super", "is_super_admin"),
        Index("idx_admin_status", "is_active", "is_deleted"),
        Index("idx_admin_level", "admin_level"),
        CheckConstraint("admin_level >= 1 AND admin_level <= 10", name="check_admin_level_range"),
    )
    
    # Foreign Keys
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to base user account"
    )
    
    # Admin Hierarchy
    admin_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Admin hierarchy level (1=lowest, 10=highest)"
    )
    
    is_super_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Super admin with platform-wide access"
    )
    
    reports_to_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Reporting manager admin ID"
    )
    
    # Employment Details
    employee_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        unique=True,
        index=True,
        comment="Unique employee identifier"
    )
    
    department: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Department or division"
    )
    
    designation: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Job title or designation"
    )
    
    join_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date of joining as admin"
    )
    
    # Status and Access
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Admin account is active"
    )
    
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Admin account has been verified"
    )
    
    can_manage_admins: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can create/manage other admin accounts"
    )
    
    can_access_all_hostels: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Has access to all hostels without explicit assignment"
    )
    
    # Permission Override
    permissions_override: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Global permission overrides for this admin"
    )
    
    # Multi-Hostel Management
    max_hostel_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum number of hostels this admin can manage (NULL = unlimited)"
    )
    
    primary_hostel_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Primary/default hostel for this admin"
    )
    
    # Activity Tracking
    last_active_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Last activity timestamp"
    )
      
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful login"
    )
    
    login_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of logins"
    )
    
    # Security
    two_factor_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Two-factor authentication enabled"
    )
    
    two_factor_secret: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Encrypted 2FA secret"
    )
    
    # Suspension/Termination
    suspended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Suspension timestamp"
    )
    
    suspended_by_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who suspended this account"
    )
    
    suspension_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for suspension"
    )
    
    terminated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Termination timestamp"
    )
    
    termination_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for termination"
    )
    
    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Internal admin notes"
    )
    
    settings: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Admin-specific settings and preferences"
    )
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="admin_user",
        lazy="joined",
        uselist=False
    )
    
    admin_profile: Mapped[Optional["AdminProfile"]] = relationship(
        "AdminProfile",
        back_populates="admin_user",
        lazy="select",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    hostel_assignments: Mapped[List["AdminHostelAssignment"]] = relationship(
        "AdminHostelAssignment",
        back_populates="admin",
        lazy="select",
        cascade="all, delete-orphan",
        foreign_keys="[AdminHostelAssignment.admin_id]"
    )
    
    overrides: Mapped[List["AdminOverride"]] = relationship(
        "AdminOverride",
        back_populates="admin",
        lazy="select",
        foreign_keys="[AdminOverride.admin_id]"
    )
    
    contexts: Mapped[List["HostelContext"]] = relationship(
        "HostelContext",
        back_populates="admin",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Self-referential relationships
    reports_to: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        remote_side="AdminUser.id",
        back_populates="subordinates",
        lazy="select",
        foreign_keys=[reports_to_id]
    )
    
    subordinates: Mapped[List["AdminUser"]] = relationship(
        "AdminUser",
        back_populates="reports_to",
        lazy="select",
        cascade="all"
    )
    
    suspended_by: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        remote_side="AdminUser.id",
        lazy="select",
        foreign_keys=[suspended_by_id]
    )
    
    primary_hostel: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[primary_hostel_id]
    )
    
    # Hybrid Properties
    @hybrid_property
    def is_suspended(self) -> bool:
        """Check if admin is currently suspended."""
        return self.suspended_at is not None and self.terminated_at is None
    
    @hybrid_property
    def is_terminated(self) -> bool:
        """Check if admin account is terminated."""
        return self.terminated_at is not None
    
    @hybrid_property
    def can_login(self) -> bool:
        """Check if admin can currently login."""
        return (
            self.is_active
            and not self.is_deleted
            and not self.is_suspended
            and not self.is_terminated
        )
    
    @hybrid_property
    def full_name(self) -> Optional[str]:
        """Get admin's full name from user relationship."""
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}".strip()
        return None
    
    @hybrid_property
    def email(self) -> Optional[str]:
        """Get admin's email from user relationship."""
        return self.user.email if self.user else None
    
    def __repr__(self) -> str:
        return (
            f"<AdminUser(id={self.id}, user_id={self.user_id}, "
            f"level={self.admin_level}, super={self.is_super_admin})>"
        )


class AdminProfile(TimestampModel, UUIDMixin):
    """
    Extended admin profile with employment and personal details.
    
    Stores additional information beyond the core AdminUser entity
    for comprehensive admin management and HR integration.
    """
    
    __tablename__ = "admin_profiles"
    __table_args__ = (
        Index("idx_admin_profile_admin_id", "admin_id"),
    )
    
    # Foreign Keys
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    
    # Personal Details
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date of birth"
    )
    
    nationality: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Nationality"
    )
    
    id_proof_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Government ID type (passport, driver's license, etc.)"
    )
    
    id_proof_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Government ID number"
    )
    
    # Employment Details
    contract_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Employment contract type (full-time, part-time, contract)"
    )
    
    probation_end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Probation period end date"
    )
    
    salary_currency: Mapped[Optional[str]] = mapped_column(
        String(3),
        nullable=True,
        comment="Salary currency code (ISO 4217)"
    )
    
    # Contact Details
    work_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Work phone number"
    )
    
    personal_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Personal phone number"
    )
    
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Emergency contact person name"
    )
    
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Emergency contact phone"
    )
    
    emergency_contact_relationship: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Relationship with emergency contact"
    )
    
    # Address
    current_address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Current residential address"
    )
    
    permanent_address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Permanent address"
    )
    
    # Professional Details
    qualifications: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Educational qualifications and certifications"
    )
    
    experience_years: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Years of relevant experience"
    )
    
    previous_employment: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Previous employment history"
    )
    
    skills: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Professional skills and competencies"
    )
    
    certifications: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Professional certifications"
    )
    
    # Bio and Social
    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Professional biography"
    )
    
    profile_picture_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Profile picture URL"
    )
    
    social_links: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Social media and professional network links"
    )
    
    # Performance and Recognition
    performance_rating: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="Current performance rating"
    )
    
    awards: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Awards and recognition"
    )
    
    # Additional Info
    languages: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Languages spoken"
    )
    
    hobbies: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Personal hobbies and interests"
    )
    
    custom_fields: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Organization-specific custom fields"
    )
    
    # Relationships
    admin_user: Mapped["AdminUser"] = relationship(
        "AdminUser",
        back_populates="admin_profile",
        lazy="joined"
    )
    
    def __repr__(self) -> str:
        return f"<AdminProfile(id={self.id}, admin_id={self.admin_id})>"


class AdminRole(TimestampModel, UUIDMixin, SoftDeleteMixin):
    """
    Admin role definitions with hierarchical permissions.
    
    Defines reusable admin roles that can be assigned to AdminUser entities,
    supporting role-based access control (RBAC) with permission inheritance.
    """
    
    __tablename__ = "admin_roles"
    __table_args__ = (
        Index("idx_admin_role_name", "name"),
        Index("idx_admin_role_active", "is_active"),
        CheckConstraint("hierarchy_level >= 1 AND hierarchy_level <= 10", name="check_role_hierarchy"),
    )
    
    # Role Definition
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique role name"
    )
    
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable role name"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Role description and purpose"
    )
    
    # Hierarchy
    hierarchy_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Role hierarchy level (1=lowest, 10=highest)"
    )
    
    parent_role_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_roles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent role for permission inheritance"
    )
    
    # Permissions
    permissions: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Role-specific permissions configuration"
    )
    
    inherits_permissions: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Inherit permissions from parent role"
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Role is active and assignable"
    )
    
    is_system_role: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="System-defined role (cannot be deleted)"
    )
    
    # Constraints
    max_assignments: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum number of admins that can have this role"
    )
    
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Role assignment requires approval"
    )
    
    # Metadata
    color_code: Mapped[Optional[str]] = mapped_column(
        String(7),
        nullable=True,
        comment="Color code for UI display (hex)"
    )
    
    icon: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Icon identifier for UI"
    )
    
    # Relationships
    parent_role: Mapped[Optional["AdminRole"]] = relationship(
        "AdminRole",
        remote_side="AdminRole.id",
        back_populates="child_roles",
        lazy="select",
        foreign_keys=[parent_role_id]
    )
    
    child_roles: Mapped[List["AdminRole"]] = relationship(
        "AdminRole",
        back_populates="parent_role",
        lazy="select",
        cascade="all"
    )
    
    def __repr__(self) -> str:
        return f"<AdminRole(id={self.id}, name='{self.name}', level={self.hierarchy_level})>"


class AdminSession(TimestampModel, UUIDMixin):
    """
    Admin session tracking for security and audit.
    
    Tracks active admin sessions with device information,
    IP addresses, and session metadata for security monitoring.
    """
    
    __tablename__ = "admin_sessions"
    __table_args__ = (
        Index("idx_admin_session_admin_id", "admin_id"),
        Index("idx_admin_session_active", "is_active", "expires_at"),
        Index("idx_admin_session_token", "session_token"),
    )
    
    # Foreign Keys
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Session Details
    session_token: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique session token (hashed)"
    )
    
    refresh_token: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Refresh token for session renewal"
    )
    
    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Session start timestamp"
    )
    
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Session expiration timestamp"
    )
    
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Last activity in this session"
    )
    
    # Device and Location
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        index=True,
        comment="IP address of the session"
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent string"
    )
    
    device_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Device type (desktop, mobile, tablet)"
    )
    
    device_info: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed device information"
    )
    
    location_info: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Geographic location information"
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Session is currently active"
    )
    
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Session end timestamp"
    )
    
    end_reason: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Reason for session termination"
    )
    
    # Security
    is_suspicious: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Session flagged as suspicious"
    )
    
    security_flags: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Security-related flags and alerts"
    )
    
    # Session Metadata - RENAMED FROM 'metadata' to avoid SQLAlchemy conflict
    session_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional session metadata"
    )
    
    # Relationships
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        lazy="select"
    )
    
    @hybrid_property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.utcnow() > self.expires_at
    
    @hybrid_property
    def duration_seconds(self) -> int:
        """Calculate session duration in seconds."""
        end_time = self.ended_at or datetime.utcnow()
        return int((end_time - self.started_at).total_seconds())
    
    def __repr__(self) -> str:
        return (
            f"<AdminSession(id={self.id}, admin_id={self.admin_id}, "
            f"active={self.is_active})>"
        )