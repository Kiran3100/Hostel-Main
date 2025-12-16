# --- File: app/schemas/supervisor/supervisor_response.py ---
"""
Supervisor response schemas for API responses.

Provides optimized response formats with computed properties
and efficient data serialization.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Dict, Union

from pydantic import Field, computed_field

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import EmploymentType, SupervisorStatus

__all__ = [
    "SupervisorResponse",
    "SupervisorDetail",
    "SupervisorListItem",
    "SupervisorSummary",
    "SupervisorEmploymentInfo",
    "SupervisorStatistics",
]


class SupervisorResponse(BaseResponseSchema):
    """
    Standard supervisor response schema.
    
    Optimized for general API responses with essential information.
    """

    user_id: str = Field(..., description="User ID")
    full_name: str = Field(..., description="Supervisor full name")
    email: str = Field(..., description="Email address")
    phone: str = Field(..., description="Phone number")
    profile_image_url: Union[str, None] = Field(
        default=None,
        description="Profile image URL",
    )

    # Assignment
    assigned_hostel_id: str = Field(..., description="Assigned hostel ID")
    hostel_name: str = Field(..., description="Hostel name")

    # Employment
    employee_id: Union[str, None] = Field(default=None, description="Employee ID")
    join_date: Date = Field(..., description="Joining Date")
    employment_type: EmploymentType = Field(..., description="Employment type")
    designation: Union[str, None] = Field(default=None, description="Designation")

    # Status
    status: SupervisorStatus = Field(..., description="Current status")
    is_active: bool = Field(..., description="Active status")

    # Assignment metadata
    assigned_by: str = Field(..., description="Admin who assigned")
    assigned_date: Date = Field(..., description="Assignment Date")

    @computed_field
    @property
    def tenure_days(self) -> int:
        """Calculate tenure in days since joining."""
        return (Date.today() - self.join_date).days

    @computed_field
    @property
    def tenure_months(self) -> int:
        """Calculate approximate tenure in months."""
        return self.tenure_days // 30

    @computed_field
    @property
    def is_probation(self) -> bool:
        """Check if supervisor is in probation period (first 3 months)."""
        return self.tenure_months < 3


class SupervisorDetail(BaseResponseSchema):
    """
    Detailed supervisor information.
    
    Comprehensive profile with all attributes and computed metrics.
    """

    # User information
    user_id: str = Field(..., description="User ID")
    full_name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email")
    phone: str = Field(..., description="Phone")
    gender: Union[str, None] = Field(default=None, description="Gender")
    date_of_birth: Union[Date, None] = Field(default=None, description="Date of birth")
    profile_image_url: Union[str, None] = Field(
        default=None,
        description="Profile image",
    )

    # Hostel assignment
    assigned_hostel_id: str = Field(..., description="Assigned hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    assigned_by: str = Field(..., description="Admin user ID who assigned")
    assigned_by_name: str = Field(..., description="Admin name")
    assigned_date: Date = Field(..., description="Assignment Date")

    # Employment details
    employee_id: Union[str, None] = Field(default=None, description="Employee ID")
    join_date: Date = Field(..., description="Joining Date")
    employment_type: EmploymentType = Field(..., description="Employment type")
    shift_timing: Union[str, None] = Field(default=None, description="Shift timing")
    designation: Union[str, None] = Field(default=None, description="Designation")
    salary: Union[Decimal, None] = Field(
        default=None,
        description="Monthly salary (admin view only)",
    )

    # Status
    status: SupervisorStatus = Field(..., description="Current status")
    is_active: bool = Field(..., description="Active status")

    # Termination information
    termination_date: Union[Date, None] = Field(
        default=None,
        description="Termination Date",
    )
    termination_reason: Union[str, None] = Field(
        default=None,
        description="Termination reason",
    )
    eligible_for_rehire: Union[bool, None] = Field(
        default=None,
        description="Rehire eligibility",
    )

    # Suspension information
    suspension_start_date: Union[Date, None] = Field(
        default=None,
        description="Suspension start Date",
    )
    suspension_end_date: Union[Date, None] = Field(
        default=None,
        description="Suspension end Date",
    )
    suspension_reason: Union[str, None] = Field(
        default=None,
        description="Suspension reason",
    )

    # Permissions (optimized structure)
    permissions: Dict[str, Union[bool, int, Decimal]] = Field(
        default_factory=dict,
        description="Permission settings",
    )

    # Performance metrics (aggregated)
    total_complaints_resolved: int = Field(
        default=0,
        ge=0,
        description="Total complaints resolved",
    )
    average_resolution_time_hours: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Average complaint resolution time",
    )
    total_attendance_records: int = Field(
        default=0,
        ge=0,
        description="Total attendance records created",
    )
    total_maintenance_requests: int = Field(
        default=0,
        ge=0,
        description="Total maintenance requests",
    )
    last_performance_review: Union[Date, None] = Field(
        default=None,
        description="Last performance review Date",
    )
    performance_rating: Union[Decimal, None] = Field(
        default=None,
        ge=0,
        le=5,
        description="Latest performance rating",
    )

    # Activity tracking
    last_login: Union[datetime, None] = Field(
        default=None,
        description="Last login timestamp",
    )
    total_logins: int = Field(
        default=0,
        ge=0,
        description="Total login count",
    )
    last_activity: Union[datetime, None] = Field(
        default=None,
        description="Last activity timestamp",
    )

    # Administrative notes
    notes: Union[str, None] = Field(
        default=None,
        description="Administrative notes",
    )

    @computed_field
    @property
    def age(self) -> Union[int, None]:
        """Calculate age from Date of birth."""
        if not self.date_of_birth:
            return None
        
        today = Date.today()
        age = (
            today.year
            - self.date_of_birth.year
            - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        )
        return age

    @computed_field
    @property
    def tenure_months(self) -> int:
        """Calculate tenure in complete months."""
        return (Date.today() - self.join_date).days // 30

    @computed_field
    @property
    def tenure_years(self) -> int:
        """Calculate tenure in complete years."""
        return self.tenure_months // 12

    @computed_field
    @property
    def is_probation(self) -> bool:
        """Check if supervisor is in probation period."""
        return self.tenure_months < 3

    @computed_field
    @property
    def can_work(self) -> bool:
        """Check if supervisor is currently allowed to work."""
        return self.is_active and self.status == SupervisorStatus.ACTIVE

    @computed_field
    @property
    def suspension_days_remaining(self) -> Union[int, None]:
        """Calculate remaining suspension days if currently suspended."""
        if self.status != SupervisorStatus.SUSPENDED or not self.suspension_end_date:
            return None
        
        remaining = (self.suspension_end_date - Date.today()).days
        return max(0, remaining)


class SupervisorListItem(BaseSchema):
    """
    Supervisor list item for efficient list rendering.
    
    Minimal information optimized for table/grid views.
    """

    id: str = Field(..., description="Supervisor ID")
    user_id: str = Field(..., description="User ID")
    full_name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email")
    phone: str = Field(..., description="Phone")
    profile_image_url: Union[str, None] = Field(
        default=None,
        description="Profile image",
    )

    # Assignment
    hostel_name: str = Field(..., description="Assigned hostel")
    employee_id: Union[str, None] = Field(default=None, description="Employee ID")
    designation: Union[str, None] = Field(default=None, description="Designation")

    # Employment
    employment_type: EmploymentType = Field(..., description="Employment type")
    join_date: Date = Field(..., description="Joining Date")

    # Status
    status: SupervisorStatus = Field(..., description="Status")
    is_active: bool = Field(..., description="Active status")

    # Performance (current month)
    performance_rating: Union[Decimal, None] = Field(
        default=None,
        ge=0,
        le=5,
        description="Performance rating",
    )
    complaints_resolved_this_month: int = Field(
        default=0,
        ge=0,
        description="Complaints resolved this month",
    )

    # Activity
    last_login: Union[datetime, None] = Field(
        default=None,
        description="Last login",
    )

    @computed_field
    @property
    def tenure_months(self) -> int:
        """Calculate tenure in months."""
        return (Date.today() - self.join_date).days // 30

    @computed_field
    @property
    def display_status(self) -> str:
        """Get human-readable status."""
        status_map = {
            SupervisorStatus.ACTIVE: "Active",
            SupervisorStatus.ON_LEAVE: "On Leave",
            SupervisorStatus.SUSPENDED: "Suspended",
            SupervisorStatus.TERMINATED: "Terminated",
        }
        return status_map.get(self.status, self.status.value)


class SupervisorSummary(BaseSchema):
    """
    Supervisor summary for dashboards.
    
    Optimized for quick overview with key metrics.
    """

    supervisor_id: str = Field(..., description="Supervisor ID")
    full_name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email")
    phone: str = Field(..., description="Phone")
    employee_id: Union[str, None] = Field(default=None, description="Employee ID")
    designation: Union[str, None] = Field(default=None, description="Designation")

    # Status
    status: SupervisorStatus = Field(..., description="Status")
    is_active: bool = Field(..., description="Active status")
    shift_timing: Union[str, None] = Field(default=None, description="Shift timing")

    # Current month metrics
    complaints_handled_this_month: int = Field(
        default=0,
        ge=0,
        description="Complaints handled",
    )
    complaints_resolved_this_month: int = Field(
        default=0,
        ge=0,
        description="Complaints resolved",
    )
    attendance_records_this_month: int = Field(
        default=0,
        ge=0,
        description="Attendance records",
    )
    maintenance_requests_this_month: int = Field(
        default=0,
        ge=0,
        description="Maintenance requests",
    )

    # Activity
    last_active: Union[datetime, None] = Field(
        default=None,
        description="Last activity",
    )
    is_online: bool = Field(
        default=False,
        description="Currently online",
    )

    @computed_field
    @property
    def complaint_resolution_rate(self) -> Decimal:
        """Calculate complaint resolution rate percentage."""
        if self.complaints_handled_this_month == 0:
            return Decimal("100.00")
        
        rate = (
            self.complaints_resolved_this_month
            / self.complaints_handled_this_month
            * 100
        )
        return Decimal(str(rate)).quantize(Decimal("0.01"))

    @computed_field
    @property
    def activity_status(self) -> str:
        """Get human-readable activity status."""
        if self.is_online:
            return "Online"
        
        if not self.last_active:
            return "Never"
        
        hours_ago = (datetime.now() - self.last_active).total_seconds() / 3600
        
        if hours_ago < 1:
            return "Active recently"
        elif hours_ago < 24:
            return f"Active {int(hours_ago)}h ago"
        else:
            days_ago = int(hours_ago / 24)
            return f"Active {days_ago}d ago"


class SupervisorEmploymentInfo(BaseSchema):
    """
    Detailed employment information.
    
    Comprehensive contract and compensation details.
    """

    supervisor_id: str = Field(..., description="Supervisor ID")
    supervisor_name: str = Field(..., description="Supervisor name")

    # Employment details
    employee_id: Union[str, None] = Field(default=None, description="Employee ID")
    join_date: Date = Field(..., description="Joining Date")
    employment_type: EmploymentType = Field(..., description="Employment type")
    designation: Union[str, None] = Field(default=None, description="Designation")
    shift_timing: Union[str, None] = Field(default=None, description="Shift timing")

    # Contract
    contract_start_date: Union[Date, None] = Field(
        default=None,
        description="Contract start Date",
    )
    contract_end_date: Union[Date, None] = Field(
        default=None,
        description="Contract end Date",
    )
    is_contract_active: bool = Field(
        default=True,
        description="Contract active status",
    )

    # Compensation
    salary: Union[Decimal, None] = Field(
        default=None,
        description="Monthly salary",
    )
    last_salary_revision: Union[Date, None] = Field(
        default=None,
        description="Last salary revision Date",
    )

    # Status
    status: SupervisorStatus = Field(..., description="Current status")
    is_active: bool = Field(..., description="Active status")

    # Assignment
    assigned_hostel: str = Field(..., description="Assigned hostel")
    assigned_by: str = Field(..., description="Admin who assigned")
    assigned_date: Date = Field(..., description="Assignment Date")

    # Termination
    termination_date: Union[Date, None] = Field(
        default=None,
        description="Termination Date",
    )
    termination_reason: Union[str, None] = Field(
        default=None,
        description="Termination reason",
    )
    eligible_for_rehire: Union[bool, None] = Field(
        default=None,
        description="Rehire eligibility",
    )

    @computed_field
    @property
    def tenure_days(self) -> int:
        """Calculate total tenure in days."""
        end_date = self.termination_date or Date.today()
        return (end_date - self.join_date).days

    @computed_field
    @property
    def tenure_display(self) -> str:
        """Get human-readable tenure."""
        days = self.tenure_days
        
        if days < 30:
            return f"{days} days"
        
        months = days // 30
        if months < 12:
            return f"{months} months"
        
        years = months // 12
        remaining_months = months % 12
        
        if remaining_months == 0:
            return f"{years} {'year' if years == 1 else 'years'}"
        
        return f"{years}y {remaining_months}m"

    @computed_field
    @property
    def is_contract_expiring_soon(self) -> bool:
        """Check if contract expires within 30 days."""
        if not self.contract_end_date or not self.is_contract_active:
            return False
        
        days_until_expiry = (self.contract_end_date - Date.today()).days
        return 0 < days_until_expiry <= 30

    @computed_field
    @property
    def contract_status(self) -> str:
        """Get contract status description."""
        if not self.contract_end_date:
            return "Permanent"
        
        if not self.is_contract_active:
            return "Expired"
        
        days_remaining = (self.contract_end_date - Date.today()).days
        
        if days_remaining < 0:
            return "Expired"
        elif days_remaining == 0:
            return "Expires today"
        elif days_remaining <= 7:
            return f"Expires in {days_remaining} days (urgent)"
        elif days_remaining <= 30:
            return f"Expires in {days_remaining} days"
        else:
            return f"Active (expires {self.contract_end_date.strftime('%b %Y')})"


class SupervisorStatistics(BaseSchema):
    """
    Comprehensive statistics and performance metrics.
    
    Aggregated data for reporting and analysis.
    """

    supervisor_id: str = Field(..., description="Supervisor ID")
    supervisor_name: str = Field(..., description="Supervisor name")
    calculation_period: str = Field(
        ...,
        description="Period for statistics",
        examples=["Last 30 days", "This month", "2024-01"],
    )

    # Complaint metrics
    total_complaints_assigned: int = Field(
        default=0,
        ge=0,
        description="Total complaints assigned",
    )
    complaints_resolved: int = Field(
        default=0,
        ge=0,
        description="Complaints resolved",
    )
    complaints_pending: int = Field(
        default=0,
        ge=0,
        description="Complaints pending",
    )
    average_resolution_time_hours: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Average resolution time",
    )
    sla_compliance_rate: Decimal = Field(
        default=Decimal("100.00"),
        ge=0,
        le=100,
        description="SLA compliance percentage",
    )

    # Attendance metrics
    attendance_records_created: int = Field(
        default=0,
        ge=0,
        description="Attendance records created",
    )
    attendance_marked_on_time: int = Field(
        default=0,
        ge=0,
        description="Attendance marked on time",
    )
    leaves_processed: int = Field(
        default=0,
        ge=0,
        description="Leave requests processed",
    )

    # Maintenance metrics
    maintenance_requests_created: int = Field(
        default=0,
        ge=0,
        description="Maintenance requests created",
    )
    maintenance_completed: int = Field(
        default=0,
        ge=0,
        description="Maintenance completed",
    )
    average_maintenance_completion_hours: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Average completion time",
    )

    # Communication metrics
    announcements_created: int = Field(
        default=0,
        ge=0,
        description="Announcements created",
    )
    announcement_reach: int = Field(
        default=0,
        ge=0,
        description="Total students reached",
    )

    # Activity metrics
    total_logins: int = Field(
        default=0,
        ge=0,
        description="Total logins",
    )
    active_days: int = Field(
        default=0,
        ge=0,
        description="Days with activity",
    )
    average_response_time_minutes: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Average response time",
    )

    # Overall performance
    overall_performance_score: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=100,
        description="Calculated performance score",
    )

    @computed_field
    @property
    def complaint_resolution_rate(self) -> Decimal:
        """Calculate complaint resolution rate percentage."""
        if self.total_complaints_assigned == 0:
            return Decimal("100.00")
        
        rate = (self.complaints_resolved / self.total_complaints_assigned * 100)
        return Decimal(str(rate)).quantize(Decimal("0.01"))

    @computed_field
    @property
    def maintenance_completion_rate(self) -> Decimal:
        """Calculate maintenance completion rate percentage."""
        if self.maintenance_requests_created == 0:
            return Decimal("100.00")
        
        rate = (self.maintenance_completed / self.maintenance_requests_created * 100)
        return Decimal(str(rate)).quantize(Decimal("0.01"))

    @computed_field
    @property
    def attendance_punctuality_rate(self) -> Decimal:
        """Calculate attendance marking punctuality rate."""
        if self.attendance_records_created == 0:
            return Decimal("100.00")
        
        rate = (self.attendance_marked_on_time / self.attendance_records_created * 100)
        return Decimal(str(rate)).quantize(Decimal("0.01"))

    @computed_field
    @property
    def activity_rate(self) -> Decimal:
        """Calculate activity rate (active days / total days in period)."""
        # Assuming 30 days for "This month" or "Last 30 days"
        # In real implementation, this would be calculated from period
        total_days = 30
        
        if self.active_days == 0:
            return Decimal("0.00")
        
        rate = (self.active_days / total_days * 100)
        return Decimal(str(rate)).quantize(Decimal("0.01"))

    @computed_field
    @property
    def performance_grade(self) -> str:
        """Get performance grade based on overall score."""
        score = float(self.overall_performance_score)
        
        if score >= 90:
            return "A+ (Excellent)"
        elif score >= 80:
            return "A (Very Good)"
        elif score >= 70:
            return "B+ (Good)"
        elif score >= 60:
            return "B (Satisfactory)"
        elif score >= 50:
            return "C (Needs Improvement)"
        else:
            return "D (Poor)"