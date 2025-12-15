# --- File: app/schemas/supervisor/supervisor_profile.py ---
"""
Supervisor profile schemas with employment and personal information.

Provides comprehensive profile management with employment history,
performance summaries, and personal preferences.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import Field, field_validator, computed_field

from app.schemas.common.base import BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import EmploymentType, SupervisorStatus

__all__ = [
    "SupervisorProfile",
    "SupervisorEmployment",
    "PerformanceSummary",
    "SupervisorProfileUpdate",
    "EmploymentHistory",
    "SupervisorPreferences",
]


class SupervisorEmployment(BaseSchema):
    """Detailed supervisor employment information."""
    
    employee_id: Optional[str] = Field(
        default=None,
        description="Employee/Staff ID",
    )
    join_date: Date = Field(..., description="Joining Date")
    employment_type: EmploymentType = Field(..., description="Employment type")
    shift_timing: Optional[str] = Field(
        default=None,
        description="Shift timing or working hours",
    )
    designation: Optional[str] = Field(
        default=None,
        description="Job designation/title",
    )
    
    # Current status
    status: SupervisorStatus = Field(..., description="Current employment status")
    is_active: bool = Field(..., description="Active employment status")
    
    # Contract details
    contract_start_date: Optional[Date] = Field(
        default=None,
        description="Contract start Date (for contract employees)",
    )
    contract_end_date: Optional[Date] = Field(
        default=None,
        description="Contract end Date (for contract employees)",
    )
    
    # Termination details (if applicable)
    termination_date: Optional[Date] = Field(
        default=None,
        description="Termination Date",
    )
    termination_reason: Optional[str] = Field(
        default=None,
        description="Termination reason",
    )
    eligible_for_rehire: Optional[bool] = Field(
        default=None,
        description="Eligible for rehire",
    )
    
    # Assignment details
    assigned_by: str = Field(..., description="Admin who assigned")
    assigned_by_name: str = Field(..., description="Admin name")
    assigned_date: Date = Field(..., description="Assignment Date")
    
    # Compensation (admin view only)
    salary: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Monthly salary",
    )
    last_salary_revision: Optional[Date] = Field(
        default=None,
        description="Last salary revision Date",
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
    def is_contract_employee(self) -> bool:
        """Check if employee is on contract."""
        return self.employment_type == EmploymentType.CONTRACT

    @computed_field
    @property
    def contract_status(self) -> Optional[str]:
        """Get contract status for contract employees."""
        if not self.is_contract_employee or not self.contract_end_date:
            return None
        
        today = Date.today()
        days_remaining = (self.contract_end_date - today).days
        
        if days_remaining < 0:
            return "Expired"
        elif days_remaining == 0:
            return "Expires Today"
        elif days_remaining <= 30:
            return f"Expires in {days_remaining} days"
        else:
            return "Active"


class PerformanceSummary(BaseSchema):
    """Performance summary for supervisor profile."""
    
    # Complaint handling
    total_complaints_resolved: int = Field(
        default=0,
        ge=0,
        description="Total complaints resolved",
    )
    average_resolution_time_hours: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Average resolution time in hours",
    )
    sla_compliance_rate: Decimal = Field(
        default=Decimal("100.00"),
        ge=0,
        le=100,
        description="SLA compliance rate percentage",
    )
    
    # Attendance management
    total_attendance_records: int = Field(
        default=0,
        ge=0,
        description="Total attendance records created",
    )
    attendance_punctuality_rate: Decimal = Field(
        default=Decimal("100.00"),
        ge=0,
        le=100,
        description="On-time attendance marking rate",
    )
    
    # Maintenance management
    total_maintenance_requests: int = Field(
        default=0,
        ge=0,
        description="Total maintenance requests handled",
    )
    maintenance_completion_rate: Decimal = Field(
        default=Decimal("100.00"),
        ge=0,
        le=100,
        description="Maintenance completion rate",
    )
    
    # Current month performance
    current_month_complaints: int = Field(
        default=0,
        ge=0,
        description="Complaints handled this month",
    )
    current_month_attendance_records: int = Field(
        default=0,
        ge=0,
        description="Attendance records this month",
    )
    current_month_maintenance: int = Field(
        default=0,
        ge=0,
        description="Maintenance requests this month",
    )
    
    # Overall ratings
    performance_rating: Optional[Decimal] = Field(
        default=None,
        ge=0,
        le=5,
        description="Latest performance rating (1-5 scale)",
    )
    last_performance_review: Optional[Date] = Field(
        default=None,
        description="Last performance review Date",
    )
    
    # Student feedback
    student_satisfaction_score: Optional[Decimal] = Field(
        default=None,
        ge=0,
        le=5,
        description="Average student satisfaction rating",
    )
    student_feedback_count: int = Field(
        default=0,
        ge=0,
        description="Number of student feedback responses",
    )

    @computed_field
    @property
    def overall_efficiency_score(self) -> Decimal:
        """Calculate overall efficiency score."""
        scores = [
            float(self.sla_compliance_rate),
            float(self.attendance_punctuality_rate),
            float(self.maintenance_completion_rate),
        ]
        
        average_score = sum(scores) / len(scores)
        return Decimal(str(average_score)).quantize(Decimal("0.1"))

    @computed_field
    @property
    def performance_level(self) -> str:
        """Categorize performance level."""
        if not self.performance_rating:
            return "Not Rated"
        
        rating = float(self.performance_rating)
        if rating >= 4.5:
            return "Outstanding"
        elif rating >= 4.0:
            return "Excellent"
        elif rating >= 3.5:
            return "Good"
        elif rating >= 3.0:
            return "Satisfactory"
        elif rating >= 2.0:
            return "Needs Improvement"
        else:
            return "Unsatisfactory"


class EmploymentHistory(BaseSchema):
    """Employment history entry."""
    
    hostel_id: str = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    start_date: Date = Field(..., description="Assignment start Date")
    end_date: Optional[Date] = Field(
        default=None,
        description="Assignment end Date (null if current)",
    )
    designation: Optional[str] = Field(
        default=None,
        description="Designation during this period",
    )
    employment_type: EmploymentType = Field(
        ...,
        description="Employment type during this period",
    )
    reason_for_change: Optional[str] = Field(
        default=None,
        description="Reason for assignment change/end",
    )
    performance_rating: Optional[Decimal] = Field(
        default=None,
        ge=0,
        le=5,
        description="Performance rating for this period",
    )

    @computed_field
    @property
    def duration_days(self) -> int:
        """Calculate duration of this assignment."""
        end = self.end_date or Date.today()
        return (end - self.start_date).days

    @computed_field
    @property
    def is_current(self) -> bool:
        """Check if this is the current assignment."""
        return self.end_date is None


class SupervisorPreferences(BaseSchema):
    """Supervisor personal preferences and settings."""
    
    # Notification preferences
    email_notifications: bool = Field(
        default=True,
        description="Enable email notifications",
    )
    sms_notifications: bool = Field(
        default=True,
        description="Enable SMS notifications",
    )
    push_notifications: bool = Field(
        default=True,
        description="Enable push notifications",
    )
    
    # Notification types
    complaint_notifications: bool = Field(
        default=True,
        description="Receive complaint notifications",
    )
    maintenance_notifications: bool = Field(
        default=True,
        description="Receive maintenance notifications",
    )
    attendance_reminders: bool = Field(
        default=True,
        description="Receive attendance marking reminders",
    )
    admin_announcements: bool = Field(
        default=True,
        description="Receive admin announcements",
    )
    
    # Dashboard preferences
    dashboard_refresh_interval: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Dashboard auto-refresh interval in seconds",
    )
    default_view: str = Field(
        default="dashboard",
        pattern=r"^(dashboard|complaints|attendance|maintenance|reports)$",
        description="Default view on login",
    )
    
    # Language and locale
    preferred_language: str = Field(
        default="en",
        pattern=r"^(en|hi|ta|te|bn|mr|gu)$",
        description="Preferred language",
    )
    timezone: str = Field(
        default="Asia/Kolkata",
        description="Preferred timezone",
    )
    
    # Working hours
    work_start_time: Optional[str] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Work start time (HH:MM)",
    )
    work_end_time: Optional[str] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Work end time (HH:MM)",
    )


class SupervisorProfile(BaseSchema):
    """Complete supervisor profile with all information."""
    
    id: str = Field(..., description="Supervisor ID")
    user_id: str = Field(..., description="User ID")
    
    # Personal information
    full_name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    phone: str = Field(..., description="Phone number")
    profile_image_url: Optional[str] = Field(
        default=None,
        description="Profile image URL",
    )
    
    # Current assignment
    hostel_id: str = Field(..., description="Current hostel ID")
    hostel_name: str = Field(..., description="Current hostel name")
    
    # Employment details
    employment: SupervisorEmployment = Field(
        ...,
        description="Current employment information",
    )
    
    # Employment history
    employment_history: List[EmploymentHistory] = Field(
        default_factory=list,
        description="Employment history",
    )
    
    # Permissions
    permissions: dict = Field(
        default_factory=dict,
        description="Current permission settings",
    )
    
    # Performance
    performance_summary: PerformanceSummary = Field(
        ...,
        description="Performance summary",
    )
    
    # Preferences
    preferences: SupervisorPreferences = Field(
        ...,
        description="Personal preferences",
    )
    
    # Activity tracking
    last_login: Optional[datetime] = Field(
        default=None,
        description="Last login timestamp",
    )
    total_logins: int = Field(
        default=0,
        ge=0,
        description="Total login count",
    )
    last_activity: Optional[datetime] = Field(
        default=None,
        description="Last activity timestamp",
    )

    @computed_field
    @property
    def total_experience_days(self) -> int:
        """Calculate total experience across all assignments."""
        total_days = 0
        for history in self.employment_history:
            total_days += history.duration_days
        
        # Add current assignment
        total_days += self.employment.tenure_days
        return total_days

    @computed_field
    @property
    def experience_display(self) -> str:
        """Get human-readable total experience."""
        days = self.total_experience_days
        
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
    def hostels_worked(self) -> int:
        """Count number of different hostels worked at."""
        hostel_ids = {self.hostel_id}
        for history in self.employment_history:
            hostel_ids.add(history.hostel_id)
        return len(hostel_ids)


class SupervisorProfileUpdate(BaseUpdateSchema):
    """Update supervisor profile (supervisor can update own profile)."""
    
    # Contact updates (may require admin approval)
    phone: Optional[str] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Phone number",
    )
    
    # Preferences updates
    preferences: Optional[SupervisorPreferences] = Field(
        default=None,
        description="Updated preferences",
    )
    
    # Emergency contact
    emergency_contact_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Emergency contact name",
    )
    emergency_contact_phone: Optional[str] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Emergency contact phone",
    )
    emergency_contact_relation: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Emergency contact relation",
    )
    
    # Personal notes
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Personal notes",
    )

    @field_validator("phone", "emergency_contact_phone")
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone numbers."""
        if v is not None:
            return v.replace(" ", "").replace("-", "").strip()
        return v