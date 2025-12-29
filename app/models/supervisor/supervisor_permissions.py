# app/models/supervisor/supervisor_permissions.py
"""
Supervisor permission management model.

Handles granular permission control with threshold-based permissions,
audit tracking, and template-based configuration.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, DateTime, Numeric as SQLDecimal, ForeignKey,
    Integer, String, Text, UniqueConstraint, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.supervisor.supervisor import Supervisor
    from app.models.user.user import User

__all__ = [
    "SupervisorPermission",
    "PermissionTemplate", 
    "PermissionAuditLog",
]


class SupervisorPermission(UUIDMixin, TimestampModel, BaseModel):
    """
    Granular permission configuration for supervisors.
    
    Provides comprehensive permission management with dependency
    validation and threshold-based controls.
    """
    
    __tablename__ = "supervisor_permissions"
    
    # ============ Relationship ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Supervisor reference"
    )
    
    # ============ Complaint Management ============
    can_manage_complaints: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can view and manage complaints"
    )
    
    can_assign_complaints: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can assign complaints to staff/vendors"
    )
    
    can_resolve_complaints: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can mark complaints as resolved"
    )
    
    can_close_complaints: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can permanently close complaints"
    )
    
    complaint_priority_limit: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Max priority level: low, medium, high, urgent"
    )
    
    # ============ Attendance Management ============
    can_record_attendance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can record daily student attendance"
    )
    
    can_approve_leaves: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can approve leave applications"
    )
    
    max_leave_days_approval: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Max days of leave can approve independently"
    )
    
    can_edit_past_attendance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can edit past attendance records"
    )
    
    past_attendance_edit_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=7,
        comment="Days back can edit attendance"
    )
    
    # ============ Maintenance Management ============
    can_manage_maintenance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can create and manage maintenance requests"
    )
    
    can_assign_maintenance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can assign maintenance tasks"
    )
    
    can_approve_maintenance_costs: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can approve maintenance costs"
    )
    
    maintenance_approval_threshold: Mapped[Decimal] = mapped_column(
        SQLDecimal(10, 2),
        nullable=False,
        default=Decimal("5000.00"),
        comment="Max repair cost can approve (INR)"
    )
    
    can_schedule_preventive_maintenance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can schedule preventive maintenance"
    )
    
    # ============ Mess/Menu Management ============
    can_update_mess_menu: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can update daily mess menu"
    )
    
    menu_requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Menu changes require admin approval"
    )
    
    can_publish_special_menus: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can publish special occasion menus"
    )
    
    can_manage_meal_preferences: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can manage student meal preferences"
    )
    
    # ============ Communication ============
    can_create_announcements: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can create announcements"
    )
    
    urgent_announcement_requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Urgent announcements require approval"
    )
    
    can_send_push_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can send push notifications"
    )
    
    can_send_sms: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can send SMS to students"
    )
    
    can_send_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can send emails to students"
    )
    
    # ============ Student Management ============
    can_view_student_profiles: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can view student profiles"
    )
    
    can_update_student_contacts: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can update student contact info"
    )
    
    can_view_student_payments: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can view student payment status"
    )
    
    can_view_student_documents: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can view student documents"
    )
    
    can_verify_student_documents: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can verify student documents"
    )
    
    # ============ Financial Access ============
    can_view_financial_reports: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can view detailed financial reports"
    )
    
    can_view_revenue_data: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can view revenue data"
    )
    
    can_view_expense_data: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can view expense data"
    )
    
    can_generate_payment_reminders: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can generate payment reminders"
    )
    
    # ============ Room and Bed Management ============
    can_view_room_availability: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can view room availability"
    )
    
    can_suggest_room_transfers: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can suggest room transfers"
    )
    
    can_assign_beds: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can assign beds to students"
    )
    
    can_update_room_status: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can update room maintenance status"
    )
    
    # ============ Booking Management ============
    can_view_bookings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can view booking requests"
    )
    
    can_contact_visitors: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can contact visitors"
    )
    
    can_approve_bookings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can approve booking requests"
    )
    
    # ============ Reporting ============
    can_generate_reports: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can generate operational reports"
    )
    
    can_export_data: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can export data (CSV, Excel)"
    )
    
    # ============ Security and Access ============
    can_view_cctv: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Can access CCTV footage"
    )
    
    can_manage_visitor_log: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can manage visitor entry/exit log"
    )
    
    # ============ Metadata ============
    template_applied: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Permission template name if applied"
    )
    
    last_modified_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Last admin who modified permissions"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        back_populates="permissions"
    )
    
    modified_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[last_modified_by],
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_permissions_supervisor", "supervisor_id"),
        Index("idx_permissions_template", "template_applied"),
        {
            "comment": "Granular permission configuration for supervisors",
            "extend_existing": True
        }
    )
    
    def __repr__(self) -> str:
        return f"<SupervisorPermission(supervisor={self.supervisor_id})>"


class PermissionTemplate(UUIDMixin, TimestampModel, BaseModel):
    """
    Permission templates for quick assignment.
    
    Predefined permission sets for different supervisor levels
    with system and custom template support.
    """
    
    __tablename__ = "permission_templates"
    
    # ============ Template Details ============
    template_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Template name"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Template description"
    )
    
    # ============ Template Configuration ============
    permissions_config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="Permission configuration as JSON"
    )
    
    # ============ Template Type ============
    is_system_template: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="System-defined template"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Template is active"
    )
    
    # ============ Usage Tracking ============
    usage_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Times template has been applied"
    )
    
    # ============ Authorship ============
    created_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who created template"
    )
    
    # ============ Relationships ============
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_template_name", "template_name"),
        Index("idx_template_active", "is_active", "is_system_template"),
        {
            "comment": "Permission templates for supervisor role assignment",
            "extend_existing": True
        }
    )
    
    def __repr__(self) -> str:
        return f"<PermissionTemplate(name={self.template_name}, system={self.is_system_template})>"


class PermissionAuditLog(UUIDMixin, TimestampModel, BaseModel):
    """
    Permission change audit log.
    
    Comprehensive tracking of permission modifications for
    compliance and security auditing.
    """
    
    __tablename__ = "permission_audit_logs"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor reference"
    )
    
    # ============ Change Metadata ============
    changed_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        comment="Admin who made changes"
    )
    
    changed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Change timestamp"
    )
    
    # ============ Change Details ============
    permission_changes: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="Permission changes: {permission: {old: value, new: value}}"
    )
    
    change_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type: grant, revoke, update, template_applied"
    )
    
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for change"
    )
    
    # ============ Context ============
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of change initiator"
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent string"
    )
    
    template_applied: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Template name if applied"
    )
    
    # ============ Approval Tracking ============
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Change requires approval"
    )
    
    approved_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who approved"
    )
    
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Approval timestamp"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        lazy="select"
    )
    
    changed_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[changed_by],
        lazy="joined"
    )
    
    approved_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="select"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_audit_supervisor_date", "supervisor_id", "changed_at"),
        Index("idx_audit_changed_by", "changed_by", "changed_at"),
        Index("idx_audit_change_type", "change_type", "changed_at"),
        {
            "comment": "Permission change audit trail for compliance",
            "extend_existing": True
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<PermissionAuditLog(supervisor={self.supervisor_id}, "
            f"type={self.change_type}, date={self.changed_at})>"
        )