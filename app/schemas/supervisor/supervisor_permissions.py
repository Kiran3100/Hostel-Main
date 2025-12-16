# --- File: app/schemas/supervisor/supervisor_permissions.py ---
"""
Supervisor permission schemas with comprehensive access control.

Provides granular permission management with templates, bulk operations,
and audit tracking. Optimized for performance and maintainability.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Union

from pydantic import Field, field_validator, model_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema

__all__ = [
    "SupervisorPermissions",
    "PermissionUpdate",
    "PermissionCheckRequest",
    "PermissionCheckResponse",
    "BulkPermissionUpdate",
    "PermissionTemplate",
    "ApplyPermissionTemplate",
    "PermissionAuditLog",
    "PermissionConstants",
]


class PermissionConstants:
    """Centralized constants for permission management."""
    
    # Permission categories
    COMPLAINT_PERMISSIONS = {
        "can_manage_complaints",
        "can_assign_complaints",
        "can_resolve_complaints",
        "can_close_complaints",
    }
    
    ATTENDANCE_PERMISSIONS = {
        "can_record_attendance",
        "can_approve_leaves",
        "can_edit_past_attendance",
    }
    
    MAINTENANCE_PERMISSIONS = {
        "can_manage_maintenance",
        "can_assign_maintenance",
        "can_approve_maintenance_costs",
        "can_schedule_preventive_maintenance",
    }
    
    COMMUNICATION_PERMISSIONS = {
        "can_create_announcements",
        "can_send_push_notifications",
        "can_send_sms",
        "can_send_email",
    }
    
    # Threshold defaults
    DEFAULT_MAINTENANCE_THRESHOLD = Decimal("5000.00")
    DEFAULT_LEAVE_APPROVAL_DAYS = 3
    DEFAULT_PAST_ATTENDANCE_EDIT_DAYS = 7
    
    # Permission templates
    JUNIOR_SUPERVISOR_TEMPLATE = "junior_supervisor"
    SENIOR_SUPERVISOR_TEMPLATE = "senior_supervisor"
    HEAD_SUPERVISOR_TEMPLATE = "head_supervisor"
    LIMITED_ACCESS_TEMPLATE = "limited_access"
    
    # Validation constraints
    MIN_LEAVE_APPROVAL_DAYS = 1
    MAX_LEAVE_APPROVAL_DAYS = 10
    MIN_PAST_EDIT_DAYS = 1
    MAX_PAST_EDIT_DAYS = 30
    MIN_MAINTENANCE_THRESHOLD = Decimal("0.00")
    MAX_MAINTENANCE_THRESHOLD = Decimal("100000.00")


class SupervisorPermissions(BaseSchema):
    """
    Comprehensive supervisor permission configuration.
    
    Provides granular control over supervisor capabilities with
    dependency validation and threshold-based permissions.
    """

    # ============ Complaint Management ============
    can_manage_complaints: bool = Field(
        default=True,
        description="Can view and manage complaints",
    )
    can_assign_complaints: bool = Field(
        default=True,
        description="Can assign complaints to staff/vendors",
    )
    can_resolve_complaints: bool = Field(
        default=True,
        description="Can mark complaints as resolved",
    )
    can_close_complaints: bool = Field(
        default=False,
        description="Can permanently close complaints (admin-level)",
    )
    complaint_priority_limit: Union[Literal["low", "medium", "high", "urgent"], None] = Field(
        default=None,
        description="Maximum priority level can handle independently",
    )

    # ============ Attendance Management ============
    can_record_attendance: bool = Field(
        default=True,
        description="Can record daily student attendance",
    )
    can_approve_leaves: bool = Field(
        default=True,
        description="Can approve leave applications",
    )
    max_leave_days_approval: int = Field(
        default=PermissionConstants.DEFAULT_LEAVE_APPROVAL_DAYS,
        ge=PermissionConstants.MIN_LEAVE_APPROVAL_DAYS,
        le=PermissionConstants.MAX_LEAVE_APPROVAL_DAYS,
        description="Maximum days of leave can approve independently",
    )
    can_edit_past_attendance: bool = Field(
        default=False,
        description="Can edit past attendance records",
    )
    past_attendance_edit_days: int = Field(
        default=PermissionConstants.DEFAULT_PAST_ATTENDANCE_EDIT_DAYS,
        ge=PermissionConstants.MIN_PAST_EDIT_DAYS,
        le=PermissionConstants.MAX_PAST_EDIT_DAYS,
        description="Days back can edit attendance (if permitted)",
    )

    # ============ Maintenance Management ============
    can_manage_maintenance: bool = Field(
        default=True,
        description="Can create and manage maintenance requests",
    )
    can_assign_maintenance: bool = Field(
        default=True,
        description="Can assign maintenance tasks to staff",
    )
    can_approve_maintenance_costs: bool = Field(
        default=False,
        description="Can approve maintenance costs",
    )
    maintenance_approval_threshold: Decimal = Field(
        default=PermissionConstants.DEFAULT_MAINTENANCE_THRESHOLD,
        ge=PermissionConstants.MIN_MAINTENANCE_THRESHOLD,
        le=PermissionConstants.MAX_MAINTENANCE_THRESHOLD,
        max_digits=10,
        decimal_places=2,
        description="Maximum repair cost can approve independently (INR)",
    )
    can_schedule_preventive_maintenance: bool = Field(
        default=True,
        description="Can schedule preventive maintenance",
    )

    # ============ Mess/Menu Management ============
    can_update_mess_menu: bool = Field(
        default=True,
        description="Can update daily mess menu",
    )
    menu_requires_approval: bool = Field(
        default=False,
        description="Menu changes require admin approval",
    )
    can_publish_special_menus: bool = Field(
        default=False,
        description="Can publish special occasion menus",
    )
    can_manage_meal_preferences: bool = Field(
        default=True,
        description="Can manage student meal preferences",
    )

    # ============ Communication ============
    can_create_announcements: bool = Field(
        default=True,
        description="Can create announcements",
    )
    urgent_announcement_requires_approval: bool = Field(
        default=True,
        description="Urgent announcements require admin approval",
    )
    can_send_push_notifications: bool = Field(
        default=False,
        description="Can send push notifications to students",
    )
    can_send_sms: bool = Field(
        default=False,
        description="Can send SMS to students",
    )
    can_send_email: bool = Field(
        default=True,
        description="Can send emails to students",
    )

    # ============ Student Management ============
    can_view_student_profiles: bool = Field(
        default=True,
        description="Can view student profiles and details",
    )
    can_update_student_contacts: bool = Field(
        default=True,
        description="Can update student contact information",
    )
    can_view_student_payments: bool = Field(
        default=True,
        description="Can view student payment status (read-only)",
    )
    can_view_student_documents: bool = Field(
        default=True,
        description="Can view student documents",
    )
    can_verify_student_documents: bool = Field(
        default=False,
        description="Can verify student documents",
    )

    # ============ Financial Access ============
    can_view_financial_reports: bool = Field(
        default=False,
        description="Can view detailed financial reports",
    )
    can_view_revenue_data: bool = Field(
        default=False,
        description="Can view revenue and collection data",
    )
    can_view_expense_data: bool = Field(
        default=False,
        description="Can view expense data",
    )
    can_generate_payment_reminders: bool = Field(
        default=True,
        description="Can generate payment reminders",
    )

    # ============ Room and Bed Management ============
    can_view_room_availability: bool = Field(
        default=True,
        description="Can view room and bed availability",
    )
    can_suggest_room_transfers: bool = Field(
        default=True,
        description="Can suggest room transfers (requires admin approval)",
    )
    can_assign_beds: bool = Field(
        default=False,
        description="Can assign beds to students",
    )
    can_update_room_status: bool = Field(
        default=True,
        description="Can update room maintenance status",
    )

    # ============ Booking Management ============
    can_view_bookings: bool = Field(
        default=True,
        description="Can view booking requests",
    )
    can_contact_visitors: bool = Field(
        default=True,
        description="Can contact visitors for inquiries",
    )
    can_approve_bookings: bool = Field(
        default=False,
        description="Can approve booking requests",
    )

    # ============ Reporting ============
    can_generate_reports: bool = Field(
        default=True,
        description="Can generate operational reports",
    )
    can_export_data: bool = Field(
        default=False,
        description="Can export data (CSV, Excel)",
    )

    # ============ Security and Access ============
    can_view_cctv: bool = Field(
        default=False,
        description="Can access CCTV footage",
    )
    can_manage_visitor_log: bool = Field(
        default=True,
        description="Can manage visitor entry/exit log",
    )

    @model_validator(mode="after")
    def validate_permission_dependencies(self) -> "SupervisorPermissions":
        """
        Validate permission dependencies and ensure consistency.
        
        Returns:
            Self with validated and corrected permissions
        """
        # Complaint management hierarchy
        if not self.can_manage_complaints:
            self.can_assign_complaints = False
            self.can_resolve_complaints = False
            self.can_close_complaints = False
        
        # Maintenance management hierarchy
        if not self.can_manage_maintenance:
            self.can_assign_maintenance = False
            self.can_approve_maintenance_costs = False
            self.can_schedule_preventive_maintenance = False
        
        # Menu management hierarchy
        if not self.can_update_mess_menu:
            self.can_publish_special_menus = False
        
        return self

    @model_validator(mode="after")
    def validate_threshold_consistency(self) -> "SupervisorPermissions":
        """
        Validate threshold-based permissions.
        
        Returns:
            Self with validated thresholds
        """
        # If can't approve costs, threshold is irrelevant
        if not self.can_approve_maintenance_costs:
            self.maintenance_approval_threshold = Decimal("0.00")
        
        # If can't approve leaves, max days is irrelevant
        if not self.can_approve_leaves:
            self.max_leave_days_approval = 0
        
        # If can't edit past attendance, days limit is irrelevant
        if not self.can_edit_past_attendance:
            self.past_attendance_edit_days = 0
        
        return self

    def get_permission_summary(self) -> Dict[str, int]:
        """
        Get summary of permissions by category.
        
        Returns:
            Dictionary with permission counts per category
        """
        summary = {
            "complaint_permissions": 0,
            "attendance_permissions": 0,
            "maintenance_permissions": 0,
            "communication_permissions": 0,
            "student_permissions": 0,
            "financial_permissions": 0,
            "room_permissions": 0,
            "booking_permissions": 0,
            "reporting_permissions": 0,
            "security_permissions": 0,
        }
        
        # Count enabled permissions per category
        if self.can_manage_complaints:
            summary["complaint_permissions"] += 1
        if self.can_assign_complaints:
            summary["complaint_permissions"] += 1
        if self.can_resolve_complaints:
            summary["complaint_permissions"] += 1
        if self.can_close_complaints:
            summary["complaint_permissions"] += 1
        
        if self.can_record_attendance:
            summary["attendance_permissions"] += 1
        if self.can_approve_leaves:
            summary["attendance_permissions"] += 1
        if self.can_edit_past_attendance:
            summary["attendance_permissions"] += 1
        
        if self.can_manage_maintenance:
            summary["maintenance_permissions"] += 1
        if self.can_assign_maintenance:
            summary["maintenance_permissions"] += 1
        if self.can_approve_maintenance_costs:
            summary["maintenance_permissions"] += 1
        if self.can_schedule_preventive_maintenance:
            summary["maintenance_permissions"] += 1
        
        if self.can_create_announcements:
            summary["communication_permissions"] += 1
        if self.can_send_push_notifications:
            summary["communication_permissions"] += 1
        if self.can_send_sms:
            summary["communication_permissions"] += 1
        if self.can_send_email:
            summary["communication_permissions"] += 1
        
        if self.can_view_student_profiles:
            summary["student_permissions"] += 1
        if self.can_update_student_contacts:
            summary["student_permissions"] += 1
        if self.can_view_student_payments:
            summary["student_permissions"] += 1
        if self.can_view_student_documents:
            summary["student_permissions"] += 1
        if self.can_verify_student_documents:
            summary["student_permissions"] += 1
        
        if self.can_view_financial_reports:
            summary["financial_permissions"] += 1
        if self.can_view_revenue_data:
            summary["financial_permissions"] += 1
        if self.can_view_expense_data:
            summary["financial_permissions"] += 1
        if self.can_generate_payment_reminders:
            summary["financial_permissions"] += 1
        
        if self.can_view_room_availability:
            summary["room_permissions"] += 1
        if self.can_suggest_room_transfers:
            summary["room_permissions"] += 1
        if self.can_assign_beds:
            summary["room_permissions"] += 1
        if self.can_update_room_status:
            summary["room_permissions"] += 1
        
        if self.can_view_bookings:
            summary["booking_permissions"] += 1
        if self.can_contact_visitors:
            summary["booking_permissions"] += 1
        if self.can_approve_bookings:
            summary["booking_permissions"] += 1
        
        if self.can_generate_reports:
            summary["reporting_permissions"] += 1
        if self.can_export_data:
            summary["reporting_permissions"] += 1
        
        if self.can_view_cctv:
            summary["security_permissions"] += 1
        if self.can_manage_visitor_log:
            summary["security_permissions"] += 1
        
        return summary


class PermissionUpdate(BaseUpdateSchema):
    """
    Update supervisor permissions with validation.
    
    Allows partial permission updates with audit trail support.
    """

    permissions: Dict[str, Union[bool, int, Decimal]] = Field(
        ...,
        description="Permission key-value pairs to update",
    )
    reason: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Reason for permission change",
    )

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: Dict[str, Union[bool, int, Decimal]]) -> Dict[str, Union[bool, int, Decimal]]:
        """
        Validate permission keys and value types.
        
        Args:
            v: Permissions dictionary
            
        Returns:
            Validated permissions
            
        Raises:
            ValueError: If invalid keys or value types
        """
        valid_keys = set(SupervisorPermissions.model_fields.keys())
        provided_keys = set(v.keys())
        
        # Check for invalid keys
        invalid_keys = provided_keys - valid_keys
        if invalid_keys:
            raise ValueError(
                f"Invalid permission keys: {', '.join(sorted(invalid_keys))}"
            )
        
        # Validate value types based on field annotations
        for key, value in v.items():
            field_info = SupervisorPermissions.model_fields.get(key)
            if not field_info:
                continue
            
            # Get expected type
            expected_type = field_info.annotation
            
            # Handle Optional types
            if hasattr(expected_type, "__origin__") and expected_type.__origin__ is Union:
                # Extract actual type from Optional/Union
                args = getattr(expected_type, "__args__", ())
                # Filter out None type
                non_none_args = [arg for arg in args if arg is not type(None)]
                if non_none_args:
                    expected_type = non_none_args[0]
            
            # Validate type
            if expected_type == bool:
                if not isinstance(value, bool):
                    raise ValueError(f"{key} must be a boolean value")
            elif expected_type == int:
                if not isinstance(value, int) or isinstance(value, bool):
                    raise ValueError(f"{key} must be an integer value")
            elif expected_type == Decimal:
                if not isinstance(value, (Decimal, int, float)):
                    raise ValueError(f"{key} must be a numeric value")
                # Convert to Decimal if needed
                if not isinstance(value, Decimal):
                    v[key] = Decimal(str(value))
        
        return v


class PermissionCheckRequest(BaseCreateSchema):
    """
    Request to check specific permission.
    
    Validates supervisor permission with optional context for
    threshold-based permissions.
    """

    supervisor_id: str = Field(
        ...,
        description="Supervisor ID to check",
    )
    permission_key: str = Field(
        ...,
        description="Permission to check",
        examples=[
            "can_resolve_complaints",
            "can_approve_leaves",
            "can_approve_maintenance_costs",
        ],
    )
    context: Union[Dict[str, Any], None] = Field(
        default=None,
        description="Additional context for permission check",
        examples=[
            {"amount": 7500},
            {"leave_days": 5},
            {"priority": "urgent"},
        ],
    )

    @field_validator("permission_key")
    @classmethod
    def validate_permission_key(cls, v: str) -> str:
        """
        Validate permission key exists.
        
        Args:
            v: Permission key to validate
            
        Returns:
            Validated permission key
            
        Raises:
            ValueError: If permission key doesn't exist
        """
        valid_keys = set(SupervisorPermissions.model_fields.keys())
        if v not in valid_keys:
            raise ValueError(
                f"Invalid permission key: {v}. "
                f"Valid keys: {', '.join(sorted(valid_keys))}"
            )
        return v


class PermissionCheckResponse(BaseSchema):
    """
    Response for permission check.
    
    Provides detailed information about permission status and
    any threshold restrictions.
    """

    supervisor_id: str = Field(..., description="Supervisor ID")
    permission_key: str = Field(..., description="Permission checked")
    has_permission: bool = Field(
        ...,
        description="Whether supervisor has permission",
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether action requires admin approval",
    )
    threshold_exceeded: bool = Field(
        default=False,
        description="Whether threshold limit is exceeded",
    )
    message: Union[str, None] = Field(
        default=None,
        description="Explanation message",
    )

    # Threshold details
    threshold_value: Union[Decimal, None] = Field(
        default=None,
        description="Configured threshold value",
    )
    actual_value: Union[Decimal, None] = Field(
        default=None,
        description="Actual value being checked",
    )
    allowed_value: Union[Decimal, None] = Field(
        default=None,
        description="Maximum allowed value",
    )

    def get_detailed_message(self) -> str:
        """
        Get detailed human-readable message.
        
        Returns:
            Detailed explanation of permission status
        """
        if self.has_permission and not self.threshold_exceeded:
            return f"Permission granted for {self.permission_key}"
        
        if self.threshold_exceeded:
            return (
                f"Threshold exceeded: {self.actual_value} exceeds "
                f"allowed limit of {self.threshold_value}. Admin approval required."
            )
        
        if self.requires_approval:
            return f"Action requires admin approval for {self.permission_key}"
        
        return f"Permission denied for {self.permission_key}"


class BulkPermissionUpdate(BaseUpdateSchema):
    """
    Update permissions for multiple supervisors.
    
    Efficient batch permission updates with validation and audit support.
    """

    supervisor_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Supervisor IDs to update (max 50)",
    )
    permissions: Dict[str, Union[bool, int, Decimal]] = Field(
        ...,
        description="Permissions to update for all supervisors",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for bulk permission change",
    )
    effective_date: Union[datetime, None] = Field(
        default=None,
        description="Effective date for permission change",
    )

    @field_validator("supervisor_ids")
    @classmethod
    def validate_unique_ids(cls, v: List[str]) -> List[str]:
        """Ensure supervisor IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Supervisor IDs must be unique")
        return v

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: Dict[str, Union[bool, int, Decimal]]) -> Dict[str, Union[bool, int, Decimal]]:
        """Validate permissions using PermissionUpdate validator."""
        # Reuse the validation logic from PermissionUpdate
        return PermissionUpdate.validate_permissions(v)


class PermissionTemplate(BaseSchema):
    """
    Permission template for quick assignment.
    
    Predefined permission sets for different supervisor levels.
    Supports system templates and custom templates.
    """

    template_id: str = Field(
        ...,
        description="Template unique identifier",
    )
    template_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Template name",
    )
    description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Template description",
    )
    permissions: SupervisorPermissions = Field(
        ...,
        description="Permission configuration",
    )
    is_system_template: bool = Field(
        default=False,
        description="System-defined template (cannot be modified)",
    )
    is_active: bool = Field(
        default=True,
        description="Template is active and can be used",
    )
    created_at: Union[datetime, None] = Field(
        default=None,
        description="Template creation timestamp",
    )
    created_by: Union[str, None] = Field(
        default=None,
        description="Admin who created template",
    )
    updated_at: Union[datetime, None] = Field(
        default=None,
        description="Last update timestamp",
    )

    @classmethod
    def get_system_templates(cls) -> Dict[str, "PermissionTemplate"]:
        """
        Get predefined system templates.
        
        Returns:
            Dictionary of template name to template object
        """
        templates = {}
        
        # Junior Supervisor Template - Basic permissions
        templates[PermissionConstants.JUNIOR_SUPERVISOR_TEMPLATE] = cls(
            template_id="sys_junior_supervisor",
            template_name="Junior Supervisor",
            description="Basic permissions for junior supervisors",
            permissions=SupervisorPermissions(
                can_manage_complaints=True,
                can_assign_complaints=False,
                can_resolve_complaints=True,
                can_close_complaints=False,
                can_record_attendance=True,
                can_approve_leaves=True,
                max_leave_days_approval=2,
                can_edit_past_attendance=False,
                can_manage_maintenance=True,
                can_assign_maintenance=False,
                can_approve_maintenance_costs=False,
                can_update_mess_menu=True,
                can_publish_special_menus=False,
                can_create_announcements=True,
                urgent_announcement_requires_approval=True,
                can_send_email=True,
                can_send_sms=False,
                can_send_push_notifications=False,
                can_view_student_profiles=True,
                can_view_student_payments=True,
                can_view_financial_reports=False,
                can_generate_reports=True,
                can_export_data=False,
            ),
            is_system_template=True,
        )
        
        # Senior Supervisor Template - Extended permissions
        templates[PermissionConstants.SENIOR_SUPERVISOR_TEMPLATE] = cls(
            template_id="sys_senior_supervisor",
            template_name="Senior Supervisor",
            description="Extended permissions for senior supervisors",
            permissions=SupervisorPermissions(
                can_manage_complaints=True,
                can_assign_complaints=True,
                can_resolve_complaints=True,
                can_close_complaints=False,
                can_record_attendance=True,
                can_approve_leaves=True,
                max_leave_days_approval=5,
                can_edit_past_attendance=True,
                past_attendance_edit_days=7,
                can_manage_maintenance=True,
                can_assign_maintenance=True,
                can_approve_maintenance_costs=True,
                maintenance_approval_threshold=Decimal("10000.00"),
                can_schedule_preventive_maintenance=True,
                can_update_mess_menu=True,
                can_publish_special_menus=True,
                can_create_announcements=True,
                urgent_announcement_requires_approval=False,
                can_send_email=True,
                can_send_sms=True,
                can_send_push_notifications=False,
                can_view_student_profiles=True,
                can_view_student_payments=True,
                can_view_financial_reports=True,
                can_view_revenue_data=True,
                can_generate_reports=True,
                can_export_data=True,
                can_suggest_room_transfers=True,
                can_assign_beds=False,
            ),
            is_system_template=True,
        )
        
        # Head Supervisor Template - Full permissions
        templates[PermissionConstants.HEAD_SUPERVISOR_TEMPLATE] = cls(
            template_id="sys_head_supervisor",
            template_name="Head Supervisor",
            description="Full permissions for head supervisors",
            permissions=SupervisorPermissions(
                can_manage_complaints=True,
                can_assign_complaints=True,
                can_resolve_complaints=True,
                can_close_complaints=True,
                can_record_attendance=True,
                can_approve_leaves=True,
                max_leave_days_approval=10,
                can_edit_past_attendance=True,
                past_attendance_edit_days=30,
                can_manage_maintenance=True,
                can_assign_maintenance=True,
                can_approve_maintenance_costs=True,
                maintenance_approval_threshold=Decimal("50000.00"),
                can_schedule_preventive_maintenance=True,
                can_update_mess_menu=True,
                can_publish_special_menus=True,
                can_create_announcements=True,
                urgent_announcement_requires_approval=False,
                can_send_email=True,
                can_send_sms=True,
                can_send_push_notifications=True,
                can_view_student_profiles=True,
                can_update_student_contacts=True,
                can_view_student_payments=True,
                can_view_student_documents=True,
                can_verify_student_documents=True,
                can_view_financial_reports=True,
                can_view_revenue_data=True,
                can_view_expense_data=True,
                can_generate_reports=True,
                can_export_data=True,
                can_view_room_availability=True,
                can_suggest_room_transfers=True,
                can_assign_beds=True,
                can_update_room_status=True,
                can_approve_bookings=True,
                can_view_cctv=True,
            ),
            is_system_template=True,
        )
        
        # Limited Access Template - Minimal permissions
        templates[PermissionConstants.LIMITED_ACCESS_TEMPLATE] = cls(
            template_id="sys_limited_access",
            template_name="Limited Access",
            description="Minimal permissions for restricted access",
            permissions=SupervisorPermissions(
                can_manage_complaints=True,
                can_assign_complaints=False,
                can_resolve_complaints=False,
                can_close_complaints=False,
                can_record_attendance=True,
                can_approve_leaves=False,
                can_edit_past_attendance=False,
                can_manage_maintenance=True,
                can_assign_maintenance=False,
                can_approve_maintenance_costs=False,
                can_update_mess_menu=False,
                can_create_announcements=False,
                can_send_email=False,
                can_send_sms=False,
                can_send_push_notifications=False,
                can_view_student_profiles=True,
                can_view_student_payments=False,
                can_view_financial_reports=False,
                can_generate_reports=False,
                can_export_data=False,
            ),
            is_system_template=True,
        )
        
        return templates


class ApplyPermissionTemplate(BaseCreateSchema):
    """
    Apply permission template to supervisor(s).
    
    Supports both override and merge modes with validation.
    """

    supervisor_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Supervisor IDs to apply template to (max 50)",
    )
    template_name: str = Field(
        ...,
        description="Template name to apply",
    )
    override_existing: bool = Field(
        default=True,
        description="Override existing permissions completely",
    )
    merge_permissions: bool = Field(
        default=False,
        description="Merge with existing permissions (upgrade only)",
    )
    reason: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Reason for applying template",
    )

    @field_validator("supervisor_ids")
    @classmethod
    def validate_unique_ids(cls, v: List[str]) -> List[str]:
        """Ensure supervisor IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Supervisor IDs must be unique")
        return v

    @model_validator(mode="after")
    def validate_mode_selection(self) -> "ApplyPermissionTemplate":
        """
        Ensure only one application mode is selected.
        
        Returns:
            Self with validated mode
            
        Raises:
            ValueError: If both modes are selected
        """
        if self.override_existing and self.merge_permissions:
            raise ValueError(
                "Cannot both override and merge permissions. "
                "Choose either override_existing=True OR merge_permissions=True"
            )
        
        if not self.override_existing and not self.merge_permissions:
            # Default to override
            self.override_existing = True
        
        return self


class PermissionAuditLog(BaseSchema):
    """
    Permission change audit log.
    
    Comprehensive tracking of permission modifications for compliance
    and security auditing.
    """

    audit_id: str = Field(..., description="Audit log ID")
    supervisor_id: str = Field(..., description="Supervisor ID")
    supervisor_name: str = Field(..., description="Supervisor name")
    hostel_id: str = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")

    # Change metadata
    changed_by: str = Field(..., description="Admin who made changes")
    changed_by_name: str = Field(..., description="Admin name")
    changed_at: datetime = Field(..., description="Change timestamp")

    # Change details
    permission_changes: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="Permission changes in format {permission: {old: value, new: value}}",
    )
    change_type: Literal["grant", "revoke", "update", "template_applied"] = Field(
        ...,
        description="Type of change",
    )
    reason: Union[str, None] = Field(
        default=None,
        description="Reason for change",
    )

    # Context
    ip_address: Union[str, None] = Field(
        default=None,
        description="IP address of change initiator",
    )
    user_agent: Union[str, None] = Field(
        default=None,
        description="User agent string",
    )
    template_applied: Union[str, None] = Field(
        default=None,
        description="Template name if template was applied",
    )

    # Approval tracking (if applicable)
    requires_approval: bool = Field(
        default=False,
        description="Whether change requires approval",
    )
    approved_by: Union[str, None] = Field(
        default=None,
        description="Admin who approved change",
    )
    approved_at: Union[datetime, None] = Field(
        default=None,
        description="Approval timestamp",
    )

    @computed_field
    @property
    def changes_count(self) -> int:
        """Count of permission changes made."""
        return len(self.permission_changes)

    @computed_field
    @property
    def change_summary(self) -> str:
        """Human-readable summary of changes."""
        if self.template_applied:
            return f"Applied template '{self.template_applied}' ({self.changes_count} permissions changed)"
        
        return f"{self.change_type.title()}: {self.changes_count} permission(s) modified"