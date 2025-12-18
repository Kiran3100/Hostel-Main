"""
Admin Permissions Model

Granular permission system for hostel-level access control.
Defines permission structures, role mappings, and permission validation
for fine-grained authorization management.
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID, ARRAY
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin, SoftDeleteMixin, AuditMixin
from app.models.base.enums import PermissionLevel

if TYPE_CHECKING:
    from app.models.admin.admin_user import AdminUser
    from app.models.hostel.hostel import Hostel

__all__ = [
    "AdminPermission",
    "PermissionGroup",
    "RolePermission",
    "PermissionAudit",
    "PermissionTemplate",
]


class AdminPermission(TimestampModel, UUIDMixin, SoftDeleteMixin):
    """
    Admin-specific permissions for a hostel.
    
    Provides granular control over admin capabilities with comprehensive
    coverage of all admin functions at the hostel level.
    
    Permission Categories:
        - Room Management
        - Student Management
        - Booking Management
        - Fee Management
        - Supervisor Management
        - Financial Access
        - Hostel Configuration
        - Data Management
    """
    
    __tablename__ = "admin_permissions"
    __table_args__ = (
        UniqueConstraint("admin_id", "hostel_id", name="uq_admin_hostel_permission"),
        Index("idx_admin_permission_admin_id", "admin_id"),
        Index("idx_admin_permission_hostel_id", "hostel_id"),
        Index("idx_admin_permission_level", "permission_level"),
    )
    
    # Foreign Keys
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin user ID"
    )
    
    hostel_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Hostel ID (NULL for global permissions)"
    )
    
    # Permission Level
    permission_level: Mapped[str] = mapped_column(
        Enum(PermissionLevel, name="permission_level_enum"),
        nullable=False,
        default=PermissionLevel.FULL_ACCESS,
        index=True,
        comment="Overall permission level"
    )
    
    # Room Management Permissions
    can_manage_rooms: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can create/edit/delete rooms"
    )
    
    can_manage_beds: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can manage bed assignments"
    )
    
    # Student Management Permissions
    can_manage_students: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can add/edit/remove students"
    )
    
    can_check_in_students: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can check-in students"
    )
    
    can_check_out_students: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can check-out students"
    )
    
    # Booking Management Permissions
    can_approve_bookings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can approve/reject bookings"
    )
    
    can_manage_waitlist: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can manage booking waitlist"
    )
    
    # Fee Management Permissions
    can_manage_fees: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can configure fee structures"
    )
    
    can_process_payments: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can process manual payments"
    )
    
    can_issue_refunds: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can issue refunds"
    )
    
    # Supervisor Management Permissions
    can_manage_supervisors: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can assign/remove supervisors"
    )
    
    can_configure_supervisor_permissions: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can modify supervisor permissions"
    )
    
    can_override_supervisor_actions: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can override supervisor decisions"
    )
    
    # Financial Access Permissions
    can_view_financials: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can view financial reports"
    )
    
    can_export_financial_data: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can export financial data"
    )
    
    # Hostel Configuration Permissions
    can_manage_hostel_settings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can modify hostel settings"
    )
    
    can_manage_hostel_profile: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can edit public hostel profile"
    )
    
    can_toggle_public_visibility: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can make hostel public/private"
    )
    
    # Data Management Permissions
    can_delete_records: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can permanently delete records"
    )
    
    can_export_data: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can export data"
    )
    
    can_import_data: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can bulk import data"
    )
    
    can_view_analytics: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can view analytics and reports"
    )
    
    can_manage_announcements: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can create/manage announcements"
    )
    
    # Maintenance Permissions
    can_manage_maintenance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can manage maintenance requests"
    )
    
    can_approve_maintenance_costs: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can approve maintenance costs"
    )
    
    # Complaint Permissions
    can_manage_complaints: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can manage and resolve complaints"
    )
    
    can_escalate_complaints: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can escalate complaints"
    )
    
    # Mess Permissions
    can_manage_mess_menu: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can manage mess menu"
    )
    
    can_manage_dietary_options: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can manage dietary options"
    )
    
    # Attendance Permissions
    can_manage_attendance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can manage attendance records"
    )
    
    can_configure_attendance_policies: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can configure attendance policies"
    )
    
    # Leave Permissions
    can_approve_leaves: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can approve/reject leave requests"
    )
    
    can_manage_leave_policies: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can manage leave policies"
    )
    
    # Custom Permissions (for extensibility)
    custom_permissions: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Custom permission configurations"
    )
    
    # Permission Constraints
    max_amount_approval_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum amount this admin can approve (in base currency)"
    )
    
    max_refund_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum refund amount admin can issue"
    )
    
    max_discount_percentage: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum discount percentage admin can apply"
    )
    
    # Metadata
    granted_by_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who granted these permissions"
    )
    
    granted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=datetime.utcnow,
        comment="Timestamp when permissions were granted"
    )
    
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Permission expiration timestamp"
    )
    
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes about these permissions"
    )
    
    # Relationships
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        back_populates="permissions",
        lazy="select",
        foreign_keys=[admin_id]
    )
    
    hostel: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[hostel_id]
    )
    
    granted_by: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[granted_by_id]
    )
    
    permission_audits: Mapped[List["PermissionAudit"]] = relationship(
        "PermissionAudit",
        back_populates="permission",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Hybrid Properties
    @hybrid_property
    def is_expired(self) -> bool:
        """Check if permissions have expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    @hybrid_property
    def permission_count(self) -> int:
        """Count granted permissions."""
        permission_fields = [
            self.can_manage_rooms, self.can_manage_beds,
            self.can_manage_students, self.can_check_in_students,
            self.can_check_out_students, self.can_approve_bookings,
            self.can_manage_waitlist, self.can_manage_fees,
            self.can_process_payments, self.can_issue_refunds,
            self.can_manage_supervisors, self.can_configure_supervisor_permissions,
            self.can_override_supervisor_actions, self.can_view_financials,
            self.can_export_financial_data, self.can_manage_hostel_settings,
            self.can_manage_hostel_profile, self.can_toggle_public_visibility,
            self.can_delete_records, self.can_export_data, self.can_import_data,
            self.can_view_analytics, self.can_manage_announcements,
            self.can_manage_maintenance, self.can_approve_maintenance_costs,
            self.can_manage_complaints, self.can_escalate_complaints,
            self.can_manage_mess_menu, self.can_manage_dietary_options,
            self.can_manage_attendance, self.can_configure_attendance_policies,
            self.can_approve_leaves, self.can_manage_leave_policies,
        ]
        return sum(1 for perm in permission_fields if perm)
    
    @hybrid_property
    def has_full_access(self) -> bool:
        """Check if has all permissions."""
        return self.permission_level == PermissionLevel.FULL_ACCESS
    
    def __repr__(self) -> str:
        return (
            f"<AdminPermission(id={self.id}, admin_id={self.admin_id}, "
            f"hostel_id={self.hostel_id}, level={self.permission_level})>"
        )


class PermissionGroup(TimestampModel, UUIDMixin, SoftDeleteMixin):
    """
    Permission group for organizing related permissions.
    
    Groups permissions into logical categories for easier management
    and assignment to admin roles.
    """
    
    __tablename__ = "permission_groups"
    __table_args__ = (
        Index("idx_permission_group_name", "name"),
        Index("idx_permission_group_category", "category"),
    )
    
    # Group Definition
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique group name"
    )
    
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable group name"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Group description"
    )
    
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Permission category (room, student, financial, etc.)"
    )
    
    # Permissions in Group
    permission_keys: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="List of permission field names in this group"
    )
    
    # Display
    icon: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Icon for UI display"
    )
    
    color_code: Mapped[Optional[str]] = mapped_column(
        String(7),
        nullable=True,
        comment="Color code for UI (hex)"
    )
    
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order in UI"
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Group is active"
    )
    
    def __repr__(self) -> str:
        return f"<PermissionGroup(id={self.id}, name='{self.name}', category='{self.category}')>"


class RolePermission(TimestampModel, UUIDMixin):
    """
    Many-to-many relationship between admin roles and permissions.
    
    Maps which permissions are granted to each admin role,
    supporting role-based access control (RBAC).
    """
    
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_key", name="uq_role_permission"),
        Index("idx_role_permission_role_id", "role_id"),
        Index("idx_role_permission_key", "permission_key"),
    )
    
    # Foreign Keys
    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin role ID"
    )
    
    # Permission Definition
    permission_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Permission field name (e.g., can_manage_rooms)"
    )
    
    permission_value: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Permission granted (True) or denied (False)"
    )
    
    # Constraints (for permissions with limits)
    constraint_value: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Constraint value for limit-based permissions"
    )
    
    # Metadata
    granted_by_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who granted this permission to the role"
    )
    
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes about this permission assignment"
    )
    
    # Relationships
    role: Mapped["AdminRole"] = relationship(
        "AdminRole",
        back_populates="role_permissions",
        lazy="select"
    )
    
    granted_by: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[granted_by_id]
    )
    
    def __repr__(self) -> str:
        return (
            f"<RolePermission(id={self.id}, role_id={self.role_id}, "
            f"key='{self.permission_key}', value={self.permission_value})>"
        )


class PermissionAudit(TimestampModel, UUIDMixin):
    """
    Audit trail for permission changes.
    
    Tracks all changes to admin permissions for compliance,
    security monitoring, and accountability.
    """
    
    __tablename__ = "permission_audits"
    __table_args__ = (
        Index("idx_permission_audit_permission_id", "permission_id"),
        Index("idx_permission_audit_admin_id", "admin_id"),
        Index("idx_permission_audit_changed_by", "changed_by_id"),
        Index("idx_permission_audit_action", "action"),
        Index("idx_permission_audit_timestamp", "changed_at"),
    )
    
    # Foreign Keys
    permission_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Permission record ID"
    )
    
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin whose permissions changed"
    )
    
    # Change Details
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Action performed (created, updated, deleted, granted, revoked)"
    )
    
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Timestamp of change"
    )
    
    changed_by_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Admin who made the change"
    )
    
    # Change Data
    old_values: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Previous permission values"
    )
    
    new_values: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="New permission values"
    )
    
    changed_fields: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        comment="List of fields that changed"
    )
    
    # Context
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for permission change"
    )
    
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of change initiator"
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent of change initiator"
    )
    
    # Approval (if required)
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Change requires approval"
    )
    
    approved_by_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who approved the change"
    )
    
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Approval timestamp"
    )
    
    # Relationships
    permission: Mapped["AdminPermission"] = relationship(
        "AdminPermission",
        back_populates="permission_audits",
        lazy="select"
    )
    
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[admin_id]
    )
    
    changed_by: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[changed_by_id]
    )
    
    approved_by: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[approved_by_id]
    )
    
    def __repr__(self) -> str:
        return (
            f"<PermissionAudit(id={self.id}, permission_id={self.permission_id}, "
            f"action='{self.action}', changed_at={self.changed_at})>"
        )


class PermissionTemplate(TimestampModel, UUIDMixin, SoftDeleteMixin):
    """
    Permission templates for quick assignment.
    
    Predefined permission sets that can be quickly applied to admins,
    reducing configuration time and ensuring consistency.
    """
    
    __tablename__ = "permission_templates"
    __table_args__ = (
        Index("idx_permission_template_name", "name"),
        Index("idx_permission_template_category", "category"),
    )
    
    # Template Definition
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique template name"
    )
    
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable template name"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Template description and use case"
    )
    
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Template category (junior_admin, senior_admin, etc.)"
    )
    
    # Permission Configuration
    permission_level: Mapped[str] = mapped_column(
        Enum(PermissionLevel, name="permission_level_enum"),
        nullable=False,
        default=PermissionLevel.LIMITED_ACCESS,
        comment="Default permission level"
    )
    
    permissions: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Permission configuration to apply"
    )
    
    # Constraints
    constraints: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Permission constraints (limits, thresholds)"
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Template is active and available"
    )
    
    is_system_template: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="System template (cannot be deleted)"
    )
    
    # Metadata
    created_by_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who created this template"
    )
    
    usage_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times template has been used"
    )
    
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time template was used"
    )
    
    # Relationships
    created_by: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[created_by_id]
    )
    
    def __repr__(self) -> str:
        return (
            f"<PermissionTemplate(id={self.id}, name='{self.name}', "
            f"category='{self.category}')>"
        )