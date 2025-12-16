"""
Enhanced admin-hostel assignment schemas with comprehensive validation and performance optimizations.

Provides robust assignment management with audit trails, bulk operations,
and detailed permission tracking for multi-hostel administration.

Fully migrated to Pydantic v2 with proper Decimal field handling.
"""

from datetime import datetime
from datetime import date as Date
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Union
from uuid import UUID

from pydantic import Field, computed_field, field_validator, model_validator, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import PermissionLevel

__all__ = [
    "AdminHostelAssignment",
    "AssignmentCreate",
    "AssignmentUpdate",
    "BulkAssignment",
    "RevokeAssignment",
    "AssignmentList",
    "HostelAdminList",
    "HostelAdminItem",
]


class AdminHostelAssignment(BaseResponseSchema):
    """
    Enhanced admin-hostel assignment with comprehensive tracking and analytics.
    
    Provides complete assignment information including permissions, activity tracking,
    and performance metrics for effective multi-hostel management.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "assignment_id": "123e4567-e89b-12d3-a456-426614174000",
                "admin_id": "123e4567-e89b-12d3-a456-426614174001",
                "admin_name": "John Doe",
                "admin_email": "john@example.com",
                "hostel_id": "123e4567-e89b-12d3-a456-426614174002",
                "hostel_name": "Campus Hostel A",
                "hostel_city": "Mumbai",
                "hostel_type": "boys",
                "assigned_date": "2024-01-01",
                "permission_level": "FULL_ACCESS",
                "is_active": True,
                "is_primary": True,
            }
        }
    )
    
    # Core assignment identifiers
    assignment_id: UUID = Field(..., description="Unique assignment identifier")
    admin_id: UUID = Field(..., description="Admin user ID")
    admin_name: str = Field(..., description="Admin full name")
    admin_email: str = Field(..., description="Admin email address")
    
    # Hostel information
    hostel_id: UUID = Field(..., description="Assigned hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    hostel_city: str = Field(..., description="Hostel city location")
    hostel_type: str = Field(..., description="Hostel type (boys/girls/co-ed)")
    
    # Assignment metadata
    assigned_by: Union[UUID, None] = Field(None, description="Admin who created this assignment")
    assigned_by_name: Union[str, None] = Field(None, description="Name of assigning admin")
    assigned_date: Date = Field(..., description="Date assignment was created")
    
    # Permission configuration
    permission_level: PermissionLevel = Field(..., description="Overall permission level")
    permissions: Dict[str, Union[bool, int, str]] = Field(
        default_factory=dict,
        description="Granular permissions for this hostel assignment"
    )
    
    # Assignment status
    is_active: bool = Field(True, description="Assignment is currently active")
    is_primary: bool = Field(False, description="Primary hostel for this admin")
    
    # Revocation tracking
    revoked_date: Union[Date, None] = Field(None, description="Date assignment was revoked")
    revoked_by: Union[UUID, None] = Field(None, description="Admin who revoked assignment")
    revoke_reason: Union[str, None] = Field(None, description="Reason for revocation")
    
    # Activity and performance tracking
    last_accessed: Union[datetime, None] = Field(None, description="Last access timestamp")
    access_count: int = Field(0, ge=0, description="Total access count")
    total_session_time_minutes: int = Field(0, ge=0, description="Total time spent in hostel")
    
    # Performance metrics
    decisions_made: int = Field(0, ge=0, description="Total decisions made for this hostel")
    
    # Pydantic v2: Decimal fields with constraints using ge/le instead of max_digits/decimal_places
    avg_response_time_minutes: Union[Decimal, None] = Field(
        None, ge=Decimal("0"), description="Average response time for this hostel"
    )
    satisfaction_score: Union[Decimal, None] = Field(
        None, ge=Decimal("0"), le=Decimal("5"), description="Admin satisfaction score for this hostel"
    )

    @computed_field
    @property
    def assignment_duration_days(self) -> int:
        """Calculate total assignment duration in days."""
        end_date = self.revoked_date or Date.today()
        return max(0, (end_date - self.assigned_date).days)

    @computed_field
    @property
    def is_recently_accessed(self) -> bool:
        """Check if hostel was accessed within last 24 hours."""
        if not self.last_accessed:
            return False
        hours_since_access = (datetime.utcnow() - self.last_accessed).total_seconds() / 3600
        return hours_since_access <= 24

    @computed_field
    @property
    def permission_summary(self) -> str:
        """Generate human-readable permission summary."""
        level_descriptions = {
            PermissionLevel.FULL_ACCESS: "Full Administrative Access",
            PermissionLevel.LIMITED_ACCESS: "Limited Access with Restrictions",
            PermissionLevel.VIEW_ONLY: "Read-Only Access"
        }
        return level_descriptions.get(self.permission_level, "Unknown Access Level")

    @computed_field
    @property
    def activity_level(self) -> str:
        """Categorize admin activity level for this hostel."""
        if self.access_count == 0:
            return "No Activity"
        elif self.access_count < 10:
            return "Low Activity"
        elif self.access_count < 50:
            return "Moderate Activity"
        elif self.access_count < 100:
            return "High Activity"
        else:
            return "Very High Activity"

    @computed_field
    @property
    def avg_session_duration_minutes(self) -> Decimal:
        """Calculate average session duration."""
        if self.access_count == 0:
            return Decimal("0.00")
        return Decimal(self.total_session_time_minutes / self.access_count).quantize(Decimal("0.01"))


class AssignmentCreate(BaseCreateSchema):
    """
    Enhanced assignment creation with comprehensive validation.
    
    Supports flexible permission configuration and proper validation
    for different access levels and assignment scenarios.
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    admin_id: UUID = Field(..., description="Admin user ID to assign")
    hostel_id: UUID = Field(..., description="Hostel ID for assignment")
    
    permission_level: PermissionLevel = Field(
        PermissionLevel.FULL_ACCESS,
        description="Permission level for this assignment"
    )
    
    permissions: Union[Dict[str, Union[bool, int, str]], None] = Field(
        None,
        description="Specific permissions (required for LIMITED_ACCESS level)"
    )
    
    is_primary: bool = Field(False, description="Set as primary hostel for admin")
    
    # Assignment metadata
    assignment_notes: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Administrative notes about this assignment"
    )
    effective_date: Union[Date, None] = Field(
        None,
        description="Effective Date for assignment (defaults to today)"
    )
    
    # Notification preferences
    notify_admin: bool = Field(True, description="Send notification to admin about assignment")
    send_welcome_email: bool = Field(True, description="Send welcome email with hostel details")

    @model_validator(mode="after")
    def validate_assignment_requirements(self) -> "AssignmentCreate":
        """Validate assignment-specific business rules."""
        # Require permissions for limited access
        if self.permission_level == PermissionLevel.LIMITED_ACCESS:
            if not self.permissions:
                raise ValueError(
                    "Specific permissions are required when permission_level is LIMITED_ACCESS"
                )
            if not isinstance(self.permissions, dict) or len(self.permissions) == 0:
                raise ValueError("Permissions must be a non-empty dictionary for LIMITED_ACCESS")
        
        # Validate effective Date
        if self.effective_date:
            if self.effective_date < Date.today():
                # Allow past dates for historical assignments but validate reasonableness
                days_past = (Date.today() - self.effective_date).days
                if days_past > 365:  # More than 1 year in past
                    raise ValueError("Effective Date cannot be more than 1 year in the past")
            elif self.effective_date > Date.today():
                # Allow future dates for scheduled assignments
                days_future = (self.effective_date - Date.today()).days
                if days_future > 90:  # More than 3 months in future
                    raise ValueError("Effective Date cannot be more than 90 days in the future")
        
        return self

    @field_validator("permissions")
    @classmethod
    def validate_permissions_structure(
        cls, v: Union[Dict[str, Union[bool, int, str]], None]
    ) -> Union[Dict[str, Union[bool, int, str]], None]:
        """Validate permissions dictionary structure and values."""
        if v is None:
            return None
        
        # Define valid permission keys
        valid_permission_keys = {
            "can_manage_rooms", "can_manage_students", "can_approve_bookings",
            "can_manage_fees", "can_view_financials", "can_manage_supervisors",
            "can_override_decisions", "can_export_data", "can_delete_records",
            "can_manage_hostel_settings", "can_view_analytics", "can_manage_announcements"
        }
        
        # Validate each permission
        for key, value in v.items():
            if key not in valid_permission_keys:
                raise ValueError(f"Invalid permission key: {key}")
            
            # Validate value types
            if not isinstance(value, (bool, int, str)):
                raise ValueError(f"Invalid permission value type for {key}: {type(value)}")
            
            # Validate specific permission constraints
            if key.endswith("_threshold") and isinstance(value, (int, float)):
                if value < 0:
                    raise ValueError(f"Threshold values must be non-negative: {key}")
        
        return v

    @field_validator("assignment_notes")
    @classmethod
    def validate_assignment_notes(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate and clean assignment notes."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            # Remove excessive whitespace
            v = " ".join(v.split())
        return v


class AssignmentUpdate(BaseUpdateSchema):
    """
    Enhanced assignment update with selective field modifications.
    
    Allows partial updates while maintaining data consistency
    and proper validation for permission changes.
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    permission_level: Union[PermissionLevel, None] = Field(
        None, description="Updated permission level"
    )
    permissions: Union[Dict[str, Union[bool, int, str]], None] = Field(
        None, description="Updated specific permissions"
    )
    is_primary: Union[bool, None] = Field(None, description="Update primary hostel status")
    is_active: Union[bool, None] = Field(None, description="Update assignment active status")
    
    assignment_notes: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Updated assignment notes"
    )
    
    # Update metadata
    update_reason: Union[str, None] = Field(
        None,
        max_length=500,
        description="Reason for this update"
    )

    @model_validator(mode="after")
    def validate_update_consistency(self) -> "AssignmentUpdate":
        """Validate update field consistency and business rules."""
        # Ensure permissions are provided for limited access
        if self.permission_level == PermissionLevel.LIMITED_ACCESS:
            if self.permissions is None:
                raise ValueError(
                    "Permissions must be specified when updating to LIMITED_ACCESS level"
                )
        
        # Validate that at least one field is being updated
        update_fields = [
            self.permission_level, self.permissions, self.is_primary,
            self.is_active, self.assignment_notes
        ]
        if all(field is None for field in update_fields):
            raise ValueError("At least one field must be specified for update")
        
        return self

    @field_validator("permissions")
    @classmethod
    def validate_permissions_structure(
        cls, v: Union[Dict[str, Union[bool, int, str]], None]
    ) -> Union[Dict[str, Union[bool, int, str]], None]:
        """Validate permissions dictionary structure and values."""
        if v is None:
            return None
        
        # Define valid permission keys
        valid_permission_keys = {
            "can_manage_rooms", "can_manage_students", "can_approve_bookings",
            "can_manage_fees", "can_view_financials", "can_manage_supervisors",
            "can_override_decisions", "can_export_data", "can_delete_records",
            "can_manage_hostel_settings", "can_view_analytics", "can_manage_announcements"
        }
        
        # Validate each permission
        for key, value in v.items():
            if key not in valid_permission_keys:
                raise ValueError(f"Invalid permission key: {key}")
            
            # Validate value types
            if not isinstance(value, (bool, int, str)):
                raise ValueError(f"Invalid permission value type for {key}: {type(value)}")
            
            # Validate specific permission constraints
            if key.endswith("_threshold") and isinstance(value, (int, float)):
                if value < 0:
                    raise ValueError(f"Threshold values must be non-negative: {key}")
        
        return v


class BulkAssignment(BaseCreateSchema):
    """
    Enhanced bulk assignment with comprehensive validation and options.
    
    Supports efficient batch operations while maintaining data integrity
    and providing flexible assignment strategies.
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    admin_id: UUID = Field(..., description="Admin user ID for all assignments")
    hostel_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of hostel IDs for bulk assignment (max 50)"
    )
    
    permission_level: PermissionLevel = Field(
        PermissionLevel.FULL_ACCESS,
        description="Permission level for all assignments"
    )
    permissions: Union[Dict[str, Union[bool, int, str]], None] = Field(
        None,
        description="Permissions applied to all assignments"
    )
    
    primary_hostel_id: Union[UUID, None] = Field(
        None,
        description="Which hostel should be set as primary (must be in hostel_ids)"
    )
    
    # Bulk operation strategies
    skip_existing: bool = Field(
        True,
        description="Skip hostels where admin already has active assignment"
    )
    update_existing: bool = Field(
        False,
        description="Update existing assignments with new permissions"
    )
    force_primary: bool = Field(
        False,
        description="Force primary hostel change even if admin has existing primary"
    )
    
    # Metadata and notifications
    bulk_notes: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Notes applied to all assignments in this bulk operation"
    )
    notify_admin: bool = Field(True, description="Send notification about bulk assignment")
    send_summary_email: bool = Field(True, description="Send summary email after completion")

    @field_validator("hostel_ids")
    @classmethod
    def validate_unique_hostel_ids(cls, v: List[UUID]) -> List[UUID]:
        """Ensure hostel IDs are unique and validate list size."""
        if len(v) != len(set(v)):
            raise ValueError("Hostel IDs must be unique in bulk assignment")
        
        if len(v) > 50:
            raise ValueError("Cannot assign more than 50 hostels in a single bulk operation")
        
        return v

    @model_validator(mode="after")
    def validate_bulk_assignment_logic(self) -> "BulkAssignment":
        """Validate bulk assignment business logic and constraints."""
        # Validate primary hostel selection
        if self.primary_hostel_id and self.primary_hostel_id not in self.hostel_ids:
            raise ValueError("Primary hostel ID must be included in the hostel_ids list")
        
        # Validate operation strategy
        if self.skip_existing and self.update_existing:
            raise ValueError(
                "Cannot both skip_existing and update_existing. Choose one strategy."
            )
        
        # Validate permissions for limited access
        if self.permission_level == PermissionLevel.LIMITED_ACCESS and not self.permissions:
            raise ValueError(
                "Permissions must be specified for LIMITED_ACCESS level in bulk assignment"
            )
        
        return self

    @field_validator("permissions")
    @classmethod
    def validate_permissions_structure(
        cls, v: Union[Dict[str, Union[bool, int, str]], None]
    ) -> Union[Dict[str, Union[bool, int, str]], None]:
        """Validate permissions dictionary structure and values."""
        if v is None:
            return None
        
        # Define valid permission keys
        valid_permission_keys = {
            "can_manage_rooms", "can_manage_students", "can_approve_bookings",
            "can_manage_fees", "can_view_financials", "can_manage_supervisors",
            "can_override_decisions", "can_export_data", "can_delete_records",
            "can_manage_hostel_settings", "can_view_analytics", "can_manage_announcements"
        }
        
        # Validate each permission
        for key, value in v.items():
            if key not in valid_permission_keys:
                raise ValueError(f"Invalid permission key: {key}")
            
            # Validate value types
            if not isinstance(value, (bool, int, str)):
                raise ValueError(f"Invalid permission value type for {key}: {type(value)}")
            
            # Validate specific permission constraints
            if key.endswith("_threshold") and isinstance(value, (int, float)):
                if value < 0:
                    raise ValueError(f"Threshold values must be non-negative: {key}")
        
        return v


class RevokeAssignment(BaseCreateSchema):
    """
    Enhanced assignment revocation with comprehensive audit trail.
    
    Provides detailed revocation tracking with proper validation
    and support for different revocation scenarios.
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    assignment_id: UUID = Field(..., description="Assignment ID to revoke")
    revoke_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Detailed reason for assignment revocation"
    )
    
    # Revocation timing and options
    effective_date: Union[Date, None] = Field(
        None,
        description="Effective revocation Date (defaults to today)"
    )
    immediate_revocation: bool = Field(
        True,
        description="Revoke immediately or schedule for effective_date"
    )
    
    # Transition management
    transfer_to_admin_id: Union[UUID, None] = Field(
        None,
        description="Transfer responsibilities to another admin"
    )
    handover_notes: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Handover notes for responsibility transfer"
    )
    
    # Notification preferences
    notify_affected_admin: bool = Field(True, description="Notify admin being revoked")
    notify_hostel_supervisors: bool = Field(True, description="Notify hostel supervisors")
    
    # Data retention
    retain_access_logs: bool = Field(True, description="Retain access logs for audit")
    archive_permissions: bool = Field(True, description="Archive permission history")

    @field_validator("revoke_reason")
    @classmethod
    def validate_revoke_reason(cls, v: str) -> str:
        """Validate and normalize revocation reason."""
        reason = v.strip()
        if len(reason) < 10:
            raise ValueError("Revocation reason must be at least 10 characters")
        
        # Remove excessive whitespace
        reason = " ".join(reason.split())
        return reason

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, v: Union[Date, None]) -> Union[Date, None]:
        """Validate revocation effective Date."""
        if v is not None:
            today = Date.today()
            
            # Allow past dates for historical revocations
            if v < today:
                days_past = (today - v).days
                if days_past > 30:  # More than 30 days in past
                    raise ValueError("Effective Date cannot be more than 30 days in the past")
            
            # Allow future dates for scheduled revocations
            elif v > today:
                days_future = (v - today).days
                if days_future > 90:  # More than 90 days in future
                    raise ValueError("Effective Date cannot be more than 90 days in the future")
        
        return v

    @model_validator(mode="after")
    def validate_revocation_logic(self) -> "RevokeAssignment":
        """Validate revocation business logic."""
        # Validate transfer requirements
        if self.transfer_to_admin_id:
            if not self.handover_notes:
                raise ValueError(
                    "Handover notes are required when transferring to another admin"
                )
        
        # Validate immediate vs scheduled revocation
        if not self.immediate_revocation and not self.effective_date:
            raise ValueError(
                "Effective Date must be specified for non-immediate revocation"
            )
        
        if self.immediate_revocation and self.effective_date and self.effective_date != Date.today():
            raise ValueError(
                "Immediate revocation cannot have future effective Date"
            )
        
        return self


class AssignmentList(BaseSchema):
    """
    Enhanced assignment list with comprehensive admin overview.
    
    Provides aggregated view of all assignments for an admin
    with summary statistics and quick access information.
    """
    
    model_config = ConfigDict()
    
    admin_id: UUID = Field(..., description="Admin user ID")
    admin_name: str = Field(..., description="Admin full name")
    admin_email: str = Field(..., description="Admin email address")
    
    # Assignment statistics
    total_hostels: int = Field(..., ge=0, description="Total hostels assigned")
    active_hostels: int = Field(..., ge=0, description="Currently active assignments")
    inactive_hostels: int = Field(..., ge=0, description="Inactive assignments")
    
    # Primary hostel information
    primary_hostel_id: Union[UUID, None] = Field(None, description="Primary hostel ID")
    primary_hostel_name: Union[str, None] = Field(None, description="Primary hostel name")
    
    # Activity summary
    last_activity: Union[datetime, None] = Field(None, description="Last activity across all hostels")
    total_access_count: int = Field(0, ge=0, description="Total access count across hostels")
    
    # Assignment details
    assignments: List[AdminHostelAssignment] = Field(
        default_factory=list,
        description="Detailed assignment information"
    )
    
    # Performance metrics - Pydantic v2: use ge constraint instead of max_digits/decimal_places
    avg_response_time_minutes: Union[Decimal, None] = Field(
        None, ge=Decimal("0"), description="Average response time across all hostels"
    )
    total_decisions_made: int = Field(0, ge=0, description="Total decisions across hostels")

    @computed_field
    @property
    def assignment_utilization_rate(self) -> Decimal:
        """Calculate assignment utilization rate."""
        if self.total_hostels == 0:
            return Decimal("0.00")
        return Decimal((self.active_hostels / self.total_hostels * 100)).quantize(Decimal("0.01"))

    @computed_field
    @property
    def most_active_hostel(self) -> Union[str, None]:
        """Identify most active hostel by access count."""
        if not self.assignments:
            return None
        
        most_active = max(self.assignments, key=lambda x: x.access_count)
        return most_active.hostel_name if most_active.access_count > 0 else None

    @computed_field
    @property
    def permission_distribution(self) -> Dict[str, int]:
        """Calculate distribution of permission levels."""
        distribution = {level.value: 0 for level in PermissionLevel}
        
        for assignment in self.assignments:
            if assignment.is_active:
                distribution[assignment.permission_level.value] += 1
        
        return distribution


class HostelAdminItem(BaseSchema):
    """
    Enhanced admin item with detailed assignment information.
    
    Represents individual admin assignment within hostel admin list
    with comprehensive permission and activity tracking.
    """
    
    model_config = ConfigDict()
    
    # Admin identification
    admin_id: UUID = Field(..., description="Admin user ID")
    admin_name: str = Field(..., description="Admin full name")
    admin_email: str = Field(..., description="Admin email address")
    
    # Assignment details
    assignment_id: UUID = Field(..., description="Assignment ID")
    permission_level: PermissionLevel = Field(..., description="Permission level")
    is_primary: bool = Field(False, description="Primary admin for this hostel")
    is_active: bool = Field(True, description="Assignment is active")
    
    # Assignment metadata
    assigned_date: Date = Field(..., description="Assignment creation Date")
    assigned_by_name: Union[str, None] = Field(None, description="Name of assigning admin")
    
    # Activity tracking
    last_active: Union[datetime, None] = Field(None, description="Last activity timestamp")
    access_count: int = Field(0, ge=0, description="Total access count")
    
    # Pydantic v2: Decimal with ge constraint
    avg_session_duration_minutes: Union[Decimal, None] = Field(
        None, ge=Decimal("0"), description="Average session duration"
    )
    
    # Performance metrics
    decisions_made: int = Field(0, ge=0, description="Total decisions made")
    response_time_avg_minutes: Union[Decimal, None] = Field(
        None, ge=Decimal("0"), description="Average response time"
    )
    
    # Specific permissions (for limited access)
    specific_permissions: Dict[str, Union[bool, int, str]] = Field(
        default_factory=dict,
        description="Specific permissions for limited access admins"
    )

    @computed_field
    @property
    def assignment_duration_days(self) -> int:
        """Calculate assignment duration in days."""
        return (Date.today() - self.assigned_date).days

    @computed_field
    @property
    def activity_status(self) -> str:
        """Determine admin activity status."""
        if not self.last_active:
            return "Never Active"
        
        hours_since_activity = (datetime.utcnow() - self.last_active).total_seconds() / 3600
        
        if hours_since_activity <= 1:
            return "Online"
        elif hours_since_activity <= 24:
            return "Recently Active"
        elif hours_since_activity <= 168:  # 1 week
            return "Active This Week"
        else:
            return "Inactive"

    @computed_field
    @property
    def permission_summary(self) -> str:
        """Generate human-readable permission summary."""
        if self.permission_level == PermissionLevel.FULL_ACCESS:
            return "Full Administrative Access"
        elif self.permission_level == PermissionLevel.LIMITED_ACCESS:
            perm_count = len([p for p in self.specific_permissions.values() if p is True])
            return f"Limited Access ({perm_count} permissions)"
        else:
            return "View Only Access"

    def has_specific_permission(self, permission_key: str) -> bool:
        """Check if admin has a specific permission."""
        if self.permission_level == PermissionLevel.FULL_ACCESS:
            return True
        elif self.permission_level == PermissionLevel.LIMITED_ACCESS:
            return self.specific_permissions.get(permission_key, False) is True
        else:
            return False

    @computed_field
    @property
    def performance_score(self) -> Decimal:
        """Calculate overall performance score for this admin-hostel assignment."""
        score = Decimal("0.00")
        
        # Activity score (40 points max)
        if self.access_count > 0:
            activity_score = min(self.access_count * 2, 40)
            score += Decimal(str(activity_score))
        
        # Decision making score (30 points max)
        if self.decisions_made > 0:
            decision_score = min(self.decisions_made * 3, 30)
            score += Decimal(str(decision_score))
        
        # Response time score (30 points max)
        if self.response_time_avg_minutes:
            # Better response time = higher score
            # Assuming 30 minutes or less is excellent (30 points)
            # More than 120 minutes is poor (0 points)
            response_minutes = float(self.response_time_avg_minutes)
            if response_minutes <= 30:
                response_score = 30
            elif response_minutes >= 120:
                response_score = 0
            else:
                # Linear interpolation
                response_score = 30 * (1 - (response_minutes - 30) / 90)
            score += Decimal(str(response_score))
        
        return score.quantize(Decimal("0.01"))


class HostelAdminList(BaseSchema):
    """
    Enhanced hostel admin list with comprehensive hostel overview.
    
    Provides detailed view of all admins assigned to a specific hostel
    with their permissions and activity levels.
    """
    
    model_config = ConfigDict()
    
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    hostel_city: str = Field(..., description="Hostel city")
    hostel_type: str = Field(..., description="Hostel type")
    
    # Admin statistics
    total_admins: int = Field(..., ge=0, description="Total assigned admins")
    active_admins: int = Field(..., ge=0, description="Currently active admin assignments")
    
    # Primary admin information
    primary_admin_id: Union[UUID, None] = Field(None, description="Primary admin ID")
    primary_admin_name: Union[str, None] = Field(None, description="Primary admin name")
    
    # Coverage information
    coverage_24x7: bool = Field(False, description="24x7 admin coverage available")
    last_admin_activity: Union[datetime, None] = Field(None, description="Last admin activity")
    
    # Admin details - Now HostelAdminItem is defined above, so no quotes needed
    admins: List[HostelAdminItem] = Field(
        default_factory=list,
        description="Detailed admin assignment information"
    )

    @computed_field
    @property
    def admin_coverage_score(self) -> Decimal:
        """Calculate admin coverage adequacy score."""
        if self.total_admins == 0:
            return Decimal("0.00")
        
        # Base score from admin count (max 50 points)
        count_score = min(self.total_admins * 25, 50)
        
        # Activity score (max 30 points)
        activity_score = 30 if self.active_admins > 0 else 0
        
        # Coverage score (max 20 points)
        coverage_score = 20 if self.coverage_24x7 else 10
        
        total_score = count_score + activity_score + coverage_score
        return Decimal(str(total_score)).quantize(Decimal("0.01"))

    @computed_field
    @property
    def permission_coverage(self) -> Dict[str, bool]:
        """Check if all critical permissions are covered by at least one admin."""
        critical_permissions = [
            "can_manage_students", "can_approve_bookings", "can_manage_fees",
            "can_override_decisions", "can_manage_supervisors"
        ]
        
        coverage = {}
        for permission in critical_permissions:
            coverage[permission] = any(
                admin.permission_level == PermissionLevel.FULL_ACCESS or
                admin.has_specific_permission(permission)
                for admin in self.admins
                if admin.is_active
            )
        
        return coverage