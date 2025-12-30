"""
Admin permission schemas for hostel-level access control.

Defines comprehensive permission structures and role mappings
for fine-grained authorization and access management.

Migrated to Pydantic v2.
"""

from typing import Dict, List, Union, Set, Optional
from uuid import UUID
from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import UserRole

__all__ = [
    "AdminPermissions",
    "AdminPermissionsUpdate",
    "RolePermissionsUpdate",
    "PermissionMatrix",
    "RolePermissions",
    "PermissionCheck",
    "PermissionCheckRequest",
    "PermissionCheckResponse",
    "BulkPermissionUpdate",
]


# Permission categories for organization
ROOM_PERMISSIONS = {"can_manage_rooms", "can_manage_beds"}
STUDENT_PERMISSIONS = {
    "can_manage_students",
    "can_check_in_students",
    "can_check_out_students",
}
BOOKING_PERMISSIONS = {"can_approve_bookings", "can_manage_waitlist"}
FEE_PERMISSIONS = {"can_manage_fees", "can_process_payments", "can_issue_refunds"}
SUPERVISOR_PERMISSIONS = {
    "can_manage_supervisors",
    "can_configure_supervisor_permissions",
    "can_override_supervisor_actions",
}
FINANCIAL_PERMISSIONS = {"can_view_financials", "can_export_financial_data"}
HOSTEL_PERMISSIONS = {
    "can_manage_hostel_settings",
    "can_manage_hostel_profile",
    "can_toggle_public_visibility",
}
DATA_PERMISSIONS = {"can_delete_records", "can_export_data", "can_import_data"}

ALL_PERMISSION_KEYS: Set[str] = (
    ROOM_PERMISSIONS
    | STUDENT_PERMISSIONS
    | BOOKING_PERMISSIONS
    | FEE_PERMISSIONS
    | SUPERVISOR_PERMISSIONS
    | FINANCIAL_PERMISSIONS
    | HOSTEL_PERMISSIONS
    | DATA_PERMISSIONS
)


class AdminPermissions(BaseSchema):
    """
    Admin-specific permissions for a hostel.

    Provides granular control over admin capabilities with
    sensible defaults and comprehensive coverage of all admin functions.
    """

    # Room management
    can_manage_rooms: bool = Field(True, description="Can create/edit/delete rooms")
    can_manage_beds: bool = Field(True, description="Can manage bed assignments")

    # Student management
    can_manage_students: bool = Field(True, description="Can add/edit/remove students")
    can_check_in_students: bool = Field(True, description="Can check-in students")
    can_check_out_students: bool = Field(True, description="Can check-out students")

    # Booking management
    can_approve_bookings: bool = Field(True, description="Can approve/reject bookings")
    can_manage_waitlist: bool = Field(True, description="Can manage waitlist")

    # Fee management
    can_manage_fees: bool = Field(True, description="Can configure fee structures")
    can_process_payments: bool = Field(True, description="Can process manual payments")
    can_issue_refunds: bool = Field(True, description="Can issue refunds")

    # Supervisor management
    can_manage_supervisors: bool = Field(True, description="Can assign/remove supervisors")
    can_configure_supervisor_permissions: bool = Field(
        True, description="Can modify supervisor permissions"
    )
    can_override_supervisor_actions: bool = Field(
        True, description="Can override supervisor decisions"
    )

    # Financial access
    can_view_financials: bool = Field(True, description="Can view financial reports")
    can_export_financial_data: bool = Field(
        True, description="Can export financial data"
    )

    # Hostel configuration
    can_manage_hostel_settings: bool = Field(
        True, description="Can modify hostel settings"
    )
    can_manage_hostel_profile: bool = Field(
        True, description="Can edit public hostel profile"
    )
    can_toggle_public_visibility: bool = Field(
        True, description="Can make hostel public/private"
    )

    # Data management
    can_delete_records: bool = Field(
        False, description="Can permanently delete records"
    )
    can_export_data: bool = Field(True, description="Can export data")
    can_import_data: bool = Field(True, description="Can bulk import data")

    def has_permission(self, permission_key: str) -> bool:
        """Check if specific permission is granted."""
        if permission_key not in ALL_PERMISSION_KEYS:
            return False
        return bool(getattr(self, permission_key, False))

    def get_granted_permissions(self) -> List[str]:
        """Get list of all granted permissions."""
        return [key for key in ALL_PERMISSION_KEYS if self.has_permission(key)]

    def get_denied_permissions(self) -> List[str]:
        """Get list of all denied permissions."""
        return [key for key in ALL_PERMISSION_KEYS if not self.has_permission(key)]

    @property
    def permission_count(self) -> int:
        """Count of granted permissions."""
        return len(self.get_granted_permissions())

    @property
    def has_full_access(self) -> bool:
        """Check if has all permissions."""
        return self.permission_count == len(ALL_PERMISSION_KEYS)

    @property
    def has_limited_access(self) -> bool:
        """Check if has limited permissions."""
        return 0 < self.permission_count < len(ALL_PERMISSION_KEYS)

    @property
    def has_no_access(self) -> bool:
        """Check if has no permissions."""
        return self.permission_count == 0


class AdminPermissionsUpdate(BaseSchema):
    """
    Schema for updating admin permissions.
    
    Used to update admin permissions for a specific hostel or globally.
    """
    
    hostel_id: Optional[UUID] = Field(None, description="Hostel ID for hostel-specific permissions, None for global")
    
    # Room management - all optional for partial updates
    can_manage_rooms: Optional[bool] = Field(None, description="Can create/edit/delete rooms")
    can_manage_beds: Optional[bool] = Field(None, description="Can manage bed assignments")

    # Student management
    can_manage_students: Optional[bool] = Field(None, description="Can add/edit/remove students")
    can_check_in_students: Optional[bool] = Field(None, description="Can check-in students")
    can_check_out_students: Optional[bool] = Field(None, description="Can check-out students")

    # Booking management
    can_approve_bookings: Optional[bool] = Field(None, description="Can approve/reject bookings")
    can_manage_waitlist: Optional[bool] = Field(None, description="Can manage waitlist")

    # Fee management
    can_manage_fees: Optional[bool] = Field(None, description="Can configure fee structures")
    can_process_payments: Optional[bool] = Field(None, description="Can process manual payments")
    can_issue_refunds: Optional[bool] = Field(None, description="Can issue refunds")

    # Supervisor management
    can_manage_supervisors: Optional[bool] = Field(None, description="Can assign/remove supervisors")
    can_configure_supervisor_permissions: Optional[bool] = Field(
        None, description="Can modify supervisor permissions"
    )
    can_override_supervisor_actions: Optional[bool] = Field(
        None, description="Can override supervisor decisions"
    )

    # Financial access
    can_view_financials: Optional[bool] = Field(None, description="Can view financial reports")
    can_export_financial_data: Optional[bool] = Field(
        None, description="Can export financial data"
    )

    # Hostel configuration
    can_manage_hostel_settings: Optional[bool] = Field(
        None, description="Can modify hostel settings"
    )
    can_manage_hostel_profile: Optional[bool] = Field(
        None, description="Can edit public hostel profile"
    )
    can_toggle_public_visibility: Optional[bool] = Field(
        None, description="Can make hostel public/private"
    )

    # Data management
    can_delete_records: Optional[bool] = Field(
        None, description="Can permanently delete records"
    )
    can_export_data: Optional[bool] = Field(None, description="Can export data")
    can_import_data: Optional[bool] = Field(None, description="Can bulk import data")

    @model_validator(mode="after")
    def validate_at_least_one_permission(self) -> "AdminPermissionsUpdate":
        """Validate that at least one permission is being updated."""
        permission_fields = {
            field_name: getattr(self, field_name) 
            for field_name in self.model_fields 
            if field_name.startswith("can_") and getattr(self, field_name) is not None
        }
        
        if not permission_fields:
            raise ValueError("At least one permission must be specified for update")
            
        return self

    def get_updated_permissions(self) -> Dict[str, bool]:
        """Get dictionary of permissions that are being updated."""
        return {
            field_name: getattr(self, field_name)
            for field_name in self.model_fields
            if field_name.startswith("can_") and getattr(self, field_name) is not None
        }


class RolePermissionsUpdate(BaseSchema):
    """
    Schema for updating role-based permission templates.
    
    Used to update the default permissions associated with a specific role.
    This affects the permission template for the role, not individual admin permissions.
    """
    
    # Room management - all optional for partial updates
    can_manage_rooms: Optional[bool] = Field(None, description="Can create/edit/delete rooms")
    can_manage_beds: Optional[bool] = Field(None, description="Can manage bed assignments")

    # Student management
    can_manage_students: Optional[bool] = Field(None, description="Can add/edit/remove students")
    can_check_in_students: Optional[bool] = Field(None, description="Can check-in students")
    can_check_out_students: Optional[bool] = Field(None, description="Can check-out students")

    # Booking management
    can_approve_bookings: Optional[bool] = Field(None, description="Can approve/reject bookings")
    can_manage_waitlist: Optional[bool] = Field(None, description="Can manage waitlist")

    # Fee management
    can_manage_fees: Optional[bool] = Field(None, description="Can configure fee structures")
    can_process_payments: Optional[bool] = Field(None, description="Can process manual payments")
    can_issue_refunds: Optional[bool] = Field(None, description="Can issue refunds")

    # Supervisor management
    can_manage_supervisors: Optional[bool] = Field(None, description="Can assign/remove supervisors")
    can_configure_supervisor_permissions: Optional[bool] = Field(
        None, description="Can modify supervisor permissions"
    )
    can_override_supervisor_actions: Optional[bool] = Field(
        None, description="Can override supervisor decisions"
    )

    # Financial access
    can_view_financials: Optional[bool] = Field(None, description="Can view financial reports")
    can_export_financial_data: Optional[bool] = Field(
        None, description="Can export financial data"
    )

    # Hostel configuration
    can_manage_hostel_settings: Optional[bool] = Field(
        None, description="Can modify hostel settings"
    )
    can_manage_hostel_profile: Optional[bool] = Field(
        None, description="Can edit public hostel profile"
    )
    can_toggle_public_visibility: Optional[bool] = Field(
        None, description="Can make hostel public/private"
    )

    # Data management
    can_delete_records: Optional[bool] = Field(
        None, description="Can permanently delete records"
    )
    can_export_data: Optional[bool] = Field(None, description="Can export data")
    can_import_data: Optional[bool] = Field(None, description="Can bulk import data")

    @model_validator(mode="after")
    def validate_at_least_one_permission(self) -> "RolePermissionsUpdate":
        """Validate that at least one permission is being updated."""
        permission_fields = {
            field_name: getattr(self, field_name) 
            for field_name in self.model_fields 
            if field_name.startswith("can_") and getattr(self, field_name) is not None
        }
        
        if not permission_fields:
            raise ValueError("At least one permission must be specified for update")
            
        return self

    def get_updated_permissions(self) -> Dict[str, bool]:
        """Get dictionary of permissions that are being updated."""
        return {
            field_name: getattr(self, field_name)
            for field_name in self.model_fields
            if field_name.startswith("can_") and getattr(self, field_name) is not None
        }

    @property
    def permission_count(self) -> int:
        """Get count of permissions being updated."""
        return len(self.get_updated_permissions())

    def to_admin_permissions(self) -> Dict[str, bool]:
        """
        Convert role permission updates to admin permissions format.
        
        Returns:
            Dictionary suitable for AdminPermissions creation
        """
        updated_perms = self.get_updated_permissions()
        
        # Set defaults for any permissions not specified
        defaults = {
            'can_manage_rooms': True,
            'can_manage_beds': True,
            'can_manage_students': True,
            'can_check_in_students': True,
            'can_check_out_students': True,
            'can_approve_bookings': True,
            'can_manage_waitlist': True,
            'can_manage_fees': True,
            'can_process_payments': True,
            'can_issue_refunds': True,
            'can_manage_supervisors': True,
            'can_configure_supervisor_permissions': True,
            'can_override_supervisor_actions': True,
            'can_view_financials': True,
            'can_export_financial_data': True,
            'can_manage_hostel_settings': True,
            'can_manage_hostel_profile': True,
            'can_toggle_public_visibility': True,
            'can_delete_records': False,  # This should default to False for security
            'can_export_data': True,
            'can_import_data': True,
        }
        
        # Update defaults with specified values
        defaults.update(updated_perms)
        
        return defaults


class PermissionCheckRequest(BaseSchema):
    """
    Request schema for checking permissions.
    
    Used to request permission verification for a user.
    """
    
    admin_id: UUID = Field(..., description="Admin user ID to check")
    permission_key: str = Field(..., description="Permission key to check")
    hostel_id: Optional[UUID] = Field(None, description="Hostel ID context for hostel-specific permissions")
    context: Optional[Dict[str, Union[str, int, float, bool]]] = Field(
        None, description="Additional context for permission checking (amounts, priorities, etc.)"
    )
    
    @field_validator("permission_key")
    @classmethod
    def validate_permission_key(cls, v: str) -> str:
        """Validate permission key is valid."""
        value = v.strip()
        if not value:
            raise ValueError("permission_key cannot be empty")

        if value not in ALL_PERMISSION_KEYS:
            raise ValueError(
                f"Invalid permission key: '{value}'. "
                f"Valid keys: {', '.join(sorted(ALL_PERMISSION_KEYS))}"
            )

        return value


class BulkPermissionUpdate(BaseSchema):
    """
    Schema for bulk updating permissions for multiple admins.
    
    Used to apply the same permission changes to multiple admins at once.
    """
    
    admin_ids: List[UUID] = Field(..., min_length=1, description="List of admin IDs to update")
    permissions: Dict[str, bool] = Field(..., description="Permission key-value pairs to update")
    hostel_id: Optional[UUID] = Field(None, description="Hostel ID for hostel-specific permissions")
    
    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: Dict[str, bool]) -> Dict[str, bool]:
        """Validate all permission keys are valid."""
        if not v:
            raise ValueError("At least one permission must be specified")
            
        invalid_keys = set(v.keys()) - ALL_PERMISSION_KEYS
        if invalid_keys:
            raise ValueError(
                f"Invalid permission keys: {', '.join(invalid_keys)}. "
                f"Valid keys: {', '.join(sorted(ALL_PERMISSION_KEYS))}"
            )
        return v
    
    @field_validator("admin_ids")
    @classmethod
    def validate_admin_ids(cls, v: List[UUID]) -> List[UUID]:
        """Validate admin IDs list is not empty and has no duplicates."""
        if not v:
            raise ValueError("admin_ids cannot be empty")
            
        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for admin_id in v:
            if admin_id not in seen:
                seen.add(admin_id)
                unique_ids.append(admin_id)
                
        return unique_ids

    @property
    def admin_count(self) -> int:
        """Get count of admins being updated."""
        return len(self.admin_ids)
    
    @property
    def permission_count(self) -> int:
        """Get count of permissions being updated."""
        return len(self.permissions)


class PermissionMatrix(BaseSchema):
    """
    Permission matrix showing capabilities for each role.

    Provides comprehensive mapping of roles to permissions
    for authorization and UI rendering.
    """

    # Note: In Pydantic v2, Dict keys must be JSON-serializable strings
    # We'll use role.value (string) as keys instead of UserRole enum directly
    permissions: Dict[str, List[str]] = Field(
        ..., description="Map of role value to list of permission keys"
    )

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Validate permission keys are valid."""
        # Validate that role keys are valid
        valid_role_values = {role.value for role in UserRole}
        
        for role_str, perms in v.items():
            if role_str not in valid_role_values:
                raise ValueError(f"Invalid role: {role_str}")
            
            invalid_perms = set(perms) - ALL_PERMISSION_KEYS
            if invalid_perms:
                raise ValueError(
                    f"Invalid permissions for role {role_str}: {', '.join(invalid_perms)}"
                )
        return v

    def get_role_permissions(self, role: UserRole) -> List[str]:
        """Get permissions for a specific role."""
        return self.permissions.get(role.value, [])

    def role_has_permission(self, role: UserRole, permission_key: str) -> bool:
        """Check if role has specific permission."""
        return permission_key in self.permissions.get(role.value, [])


class RolePermissions(BaseSchema):
    """
    Permissions for a specific role with metadata.

    Provides detailed information about role capabilities
    with descriptions for documentation and UI display.
    """

    role: UserRole = Field(..., description="User role")
    permissions: List[str] = Field(..., description="List of permission keys")
    description: str = Field(..., min_length=10, description="Role description")

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: List[str]) -> List[str]:
        """Validate all permission keys are valid."""
        invalid = set(v) - ALL_PERMISSION_KEYS
        if invalid:
            raise ValueError(
                f"Invalid permission keys: {', '.join(invalid)}. "
                f"Valid keys: {', '.join(sorted(ALL_PERMISSION_KEYS))}"
            )
        # Remove duplicates while preserving order
        seen = set()
        unique_perms = []
        for perm in v:
            if perm not in seen:
                seen.add(perm)
                unique_perms.append(perm)
        return unique_perms

    @property
    def permission_categories(self) -> Dict[str, List[str]]:
        """Organize permissions by category."""
        categories = {
            "Room Management": [],
            "Student Management": [],
            "Booking Management": [],
            "Fee Management": [],
            "Supervisor Management": [],
            "Financial Access": [],
            "Hostel Configuration": [],
            "Data Management": [],
        }

        for perm in self.permissions:
            if perm in ROOM_PERMISSIONS:
                categories["Room Management"].append(perm)
            elif perm in STUDENT_PERMISSIONS:
                categories["Student Management"].append(perm)
            elif perm in BOOKING_PERMISSIONS:
                categories["Booking Management"].append(perm)
            elif perm in FEE_PERMISSIONS:
                categories["Fee Management"].append(perm)
            elif perm in SUPERVISOR_PERMISSIONS:
                categories["Supervisor Management"].append(perm)
            elif perm in FINANCIAL_PERMISSIONS:
                categories["Financial Access"].append(perm)
            elif perm in HOSTEL_PERMISSIONS:
                categories["Hostel Configuration"].append(perm)
            elif perm in DATA_PERMISSIONS:
                categories["Data Management"].append(perm)

        # Remove empty categories
        return {k: v for k, v in categories.items() if v}


class PermissionCheck(BaseSchema):
    """
    Permission check request and result.

    Used to verify if a user has specific permission
    with detailed reasoning for access decisions.
    """

    user_id: UUID = Field(..., description="User ID to check")
    hostel_id: UUID = Field(..., description="Hostel ID context")
    permission_key: str = Field(..., description="Permission key to check")

    has_permission: bool = Field(..., description="Whether user has permission")
    reason: Union[str, None] = Field(None, description="Reason if permission denied")

    @field_validator("permission_key")
    @classmethod
    def validate_permission_key(cls, v: str) -> str:
        """Validate permission key is valid."""
        value = v.strip()
        if not value:
            raise ValueError("permission_key cannot be empty")

        if value not in ALL_PERMISSION_KEYS:
            raise ValueError(
                f"Invalid permission key: '{value}'. "
                f"Valid keys: {', '.join(sorted(ALL_PERMISSION_KEYS))}"
            )

        return value

    @model_validator(mode="after")
    def validate_reason_requirement(self) -> "PermissionCheck":
        """Validate reason is provided when permission is denied."""
        if not self.has_permission and not self.reason:
            raise ValueError("reason is required when permission is denied")
        return self

    @property
    def access_status(self) -> str:
        """Get human-readable access status."""
        return "Granted" if self.has_permission else "Denied"

    @property
    def permission_category(self) -> str:
        """Get category of checked permission."""
        if self.permission_key in ROOM_PERMISSIONS:
            return "Room Management"
        elif self.permission_key in STUDENT_PERMISSIONS:
            return "Student Management"
        elif self.permission_key in BOOKING_PERMISSIONS:
            return "Booking Management"
        elif self.permission_key in FEE_PERMISSIONS:
            return "Fee Management"
        elif self.permission_key in SUPERVISOR_PERMISSIONS:
            return "Supervisor Management"
        elif self.permission_key in FINANCIAL_PERMISSIONS:
            return "Financial Access"
        elif self.permission_key in HOSTEL_PERMISSIONS:
            return "Hostel Configuration"
        elif self.permission_key in DATA_PERMISSIONS:
            return "Data Management"
        else:
            return "Unknown"


class PermissionCheckResponse(BaseSchema):
    """
    Permission check response.
    
    Response format for permission verification requests.
    """
    
    has_permission: bool = Field(..., description="Whether user has permission")
    reason: Union[str, None] = Field(None, description="Reason if permission denied or additional context")
    
    @model_validator(mode="after")
    def validate_reason_for_denied(self) -> "PermissionCheckResponse":
        """Validate reason is provided when permission is denied."""
        if not self.has_permission and not self.reason:
            raise ValueError("reason is required when permission is denied")
        return self
    
    @property
    def access_status(self) -> str:
        """Get human-readable access status."""
        return "Granted" if self.has_permission else "Denied"
    
    @property
    def is_success(self) -> bool:
        """Check if permission check was successful (has permission)."""
        return self.has_permission