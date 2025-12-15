"""
Student dashboard schemas with comprehensive overview data.

Provides schemas for student dashboard, statistics, summaries,
and quick-view information.
"""

from __future__ import annotations

from datetime import datetime
from datetime import date as Date
from decimal import Decimal
from typing import List, Optional, Annotated

from pydantic import Field, computed_field, ConfigDict

from app.schemas.common.base import BaseSchema

__all__ = [
    "StudentDashboard",
    "StudentFinancialSummary",
    "AttendanceSummary",
    "StudentStats",
    "RecentPayment",
    "RecentComplaint",
    "PendingLeave",
    "RecentAnnouncement",
    "TodayMessMenu",
    "UpcomingEvent",
]

# Type aliases for Pydantic v2 decimal constraints
PercentageDecimal = Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)]
MoneyAmount = Annotated[Decimal, Field(max_digits=10, decimal_places=2, ge=0)]


class StudentFinancialSummary(BaseSchema):
    """
    Financial summary for student dashboard.
    
    Provides quick overview of payment status and dues.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    monthly_rent: MoneyAmount = Field(..., description="Monthly rent amount")
    next_due_date: Date = Field(..., description="Next payment due date")
    amount_due: MoneyAmount = Field(..., description="Current amount due")
    amount_overdue: MoneyAmount = Field(..., description="Overdue amount")
    advance_balance: MoneyAmount = Field(..., description="Advance payment balance")
    security_deposit: MoneyAmount = Field(..., description="Security deposit amount")

    # Mess charges
    mess_charges: MoneyAmount = Field(
        default=Decimal("0.00"),
        description="Monthly mess charges",
    )
    mess_balance: MoneyAmount = Field(
        default=Decimal("0.00"),
        description="Mess account balance",
    )

    # Payment status
    payment_status: str = Field(
        ...,
        pattern=r"^(current|due_soon|overdue)$",
        description="Overall payment status",
    )
    days_until_due: Optional[int] = Field(
        default=None,
        description="Days until next payment due",
    )
    days_overdue: Optional[int] = Field(
        default=None,
        ge=0,
        description="Days payment is overdue",
    )

    @computed_field
    @property
    def total_outstanding(self) -> Decimal:
        """Calculate total outstanding amount."""
        return self.amount_due + self.amount_overdue

    @computed_field
    @property
    def net_balance(self) -> Decimal:
        """Calculate net balance (advance - dues)."""
        return self.advance_balance - self.total_outstanding

    @computed_field
    @property
    def is_payment_urgent(self) -> bool:
        """Check if payment is urgent (due in 3 days or overdue)."""
        if self.amount_overdue > 0:
            return True
        if self.days_until_due is not None and self.days_until_due <= 3:
            return True
        return False


class AttendanceSummary(BaseSchema):
    """
    Attendance summary for student dashboard.
    
    Provides attendance statistics and status.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Current month
    current_month_percentage: PercentageDecimal = Field(
        ...,
        description="Current month attendance percentage",
    )
    current_month_present: int = Field(
        ...,
        ge=0,
        description="Days present this month",
    )
    current_month_absent: int = Field(
        ...,
        ge=0,
        description="Days absent this month",
    )
    current_month_leaves: int = Field(
        ...,
        ge=0,
        description="Days on leave this month",
    )
    current_month_total_days: int = Field(
        ...,
        ge=0,
        description="Total trackable days this month",
    )

    # Last 30 days
    last_30_days_percentage: PercentageDecimal = Field(
        ...,
        description="Last 30 days attendance percentage",
    )

    # Overall
    overall_percentage: PercentageDecimal = Field(
        ...,
        description="Overall attendance percentage",
    )
    minimum_required_percentage: PercentageDecimal = Field(
        default=Decimal("75.00"),
        description="Minimum required attendance",
    )

    # Status
    attendance_status: str = Field(
        ...,
        pattern=r"^(good|warning|critical)$",
        description="Attendance status indicator",
    )

    # Leaves
    leave_balance: int = Field(
        default=0,
        ge=0,
        description="Remaining leave balance",
    )
    pending_leave_requests: int = Field(
        default=0,
        ge=0,
        description="Pending leave applications",
    )

    @computed_field
    @property
    def is_below_minimum(self) -> bool:
        """Check if attendance is below minimum requirement."""
        return self.overall_percentage < self.minimum_required_percentage

    @computed_field
    @property
    def percentage_gap(self) -> Decimal:
        """Calculate gap from minimum requirement."""
        return self.minimum_required_percentage - self.overall_percentage


class StudentStats(BaseSchema):
    """
    Quick statistics for student dashboard.
    
    Provides key metrics and counts.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    days_in_hostel: int = Field(
        ...,
        ge=0,
        description="Total days as hostel resident",
    )
    months_in_hostel: int = Field(
        ...,
        ge=0,
        description="Total months in hostel",
    )

    # Payments
    total_payments_made: int = Field(
        ...,
        ge=0,
        description="Total number of payments",
    )
    total_amount_paid: MoneyAmount = Field(
        ...,
        description="Total amount paid",
    )
    last_payment_date: Optional[Date] = Field(
        default=None,
        description="Last payment date",
    )

    # Complaints
    complaints_raised: int = Field(
        ...,
        ge=0,
        description="Total complaints raised",
    )
    complaints_resolved: int = Field(
        ...,
        ge=0,
        description="Resolved complaints",
    )
    complaints_pending: int = Field(
        ...,
        ge=0,
        description="Pending complaints",
    )

    # Attendance
    current_attendance_percentage: PercentageDecimal = Field(
        ...,
        description="Current attendance percentage",
    )

    # Mess
    mess_meals_consumed: int = Field(
        default=0,
        ge=0,
        description="Total mess meals consumed",
    )

    @computed_field
    @property
    def complaint_resolution_rate(self) -> Decimal:
        """Calculate complaint resolution rate."""
        if self.complaints_raised == 0:
            return Decimal("100.00")
        return Decimal(
            (self.complaints_resolved / self.complaints_raised * 100)
        ).quantize(Decimal("0.01"))


class RecentPayment(BaseSchema):
    """
    Recent payment item for dashboard.
    
    Displays recent payment transaction.
    """

    payment_id: str = Field(..., description="Payment ID")
    amount: MoneyAmount = Field(..., description="Payment amount")
    payment_type: str = Field(..., description="Payment type")
    payment_date: Date = Field(..., description="Payment date")
    status: str = Field(..., description="Payment status")
    receipt_url: Optional[str] = Field(
        default=None,
        description="Receipt download URL",
    )
    payment_method: Optional[str] = Field(
        default=None,
        description="Payment method used",
    )


class RecentComplaint(BaseSchema):
    """
    Recent complaint item for dashboard.
    
    Displays recent complaint with status.
    """

    complaint_id: str = Field(..., description="Complaint ID")
    title: str = Field(..., description="Complaint title")
    category: str = Field(..., description="Complaint category")
    status: str = Field(..., description="Current status")
    priority: str = Field(..., description="Priority level")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    assigned_to: Optional[str] = Field(
        default=None,
        description="Assigned staff name",
    )

    @computed_field
    @property
    def days_open(self) -> int:
        """Calculate days since complaint was raised."""
        return (datetime.now() - self.created_at).days


class PendingLeave(BaseSchema):
    """
    Pending leave application for dashboard.
    
    Displays leave request awaiting approval.
    """

    leave_id: str = Field(..., description="Leave application ID")
    leave_type: str = Field(..., description="Leave type")
    from_date: Date = Field(..., description="Leave start date")
    to_date: Date = Field(..., description="Leave end date")
    total_days: int = Field(..., ge=1, description="Total leave days")
    reason: Optional[str] = Field(default=None, description="Leave reason")
    status: str = Field(..., description="Application status")
    applied_at: datetime = Field(..., description="Application timestamp")

    @computed_field
    @property
    def is_upcoming(self) -> bool:
        """Check if leave is upcoming."""
        return self.from_date > Date.today()


class RecentAnnouncement(BaseSchema):
    """
    Recent announcement for dashboard.
    
    Displays hostel announcement.
    """

    announcement_id: str = Field(..., description="Announcement ID")
    title: str = Field(..., description="Announcement title")
    content: Optional[str] = Field(default=None, description="Announcement content")
    category: str = Field(..., description="Category")
    priority: str = Field(..., description="Priority level")
    published_at: datetime = Field(..., description="Published timestamp")
    is_read: bool = Field(default=False, description="Read status")
    is_important: bool = Field(default=False, description="Important flag")

    @computed_field
    @property
    def is_new(self) -> bool:
        """Check if announcement is new (within 24 hours)."""
        from datetime import timedelta

        return datetime.now() - self.published_at < timedelta(hours=24)


class TodayMessMenu(BaseSchema):
    """
    Today's mess menu for dashboard.
    
    Displays daily meal menu.
    """

    date: Date = Field(..., description="Menu date")
    breakfast: List[str] = Field(
        default_factory=list,
        description="Breakfast items",
    )
    lunch: List[str] = Field(
        default_factory=list,
        description="Lunch items",
    )
    snacks: List[str] = Field(
        default_factory=list,
        description="Snacks/tea items",
    )
    dinner: List[str] = Field(
        default_factory=list,
        description="Dinner items",
    )
    is_special: bool = Field(
        default=False,
        description="Special menu (festival, etc.)",
    )
    special_occasion: Optional[str] = Field(
        default=None,
        description="Special occasion name",
    )


class UpcomingEvent(BaseSchema):
    """
    Upcoming event for dashboard.
    
    Displays hostel event or activity.
    """

    event_id: str = Field(..., description="Event ID")
    title: str = Field(..., description="Event title")
    description: Optional[str] = Field(default=None, description="Event description")
    event_date: Date = Field(..., description="Event date")
    event_time: Optional[str] = Field(default=None, description="Event time")
    location: Optional[str] = Field(default=None, description="Event location")
    category: str = Field(..., description="Event category")
    is_registered: bool = Field(
        default=False,
        description="Student registration status",
    )
    registration_required: bool = Field(
        default=False,
        description="Whether registration is required",
    )

    @computed_field
    @property
    def days_until_event(self) -> int:
        """Calculate days until event."""
        return (self.event_date - Date.today()).days


class StudentDashboard(BaseSchema):
    """
    Complete student dashboard.
    
    Aggregates all dashboard components for student overview.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    student_id: str = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    profile_image_url: Optional[str] = Field(
        default=None,
        description="Profile image",
    )

    # Hostel info
    hostel_name: str = Field(..., description="Current hostel")
    room_number: str = Field(..., description="Room number")
    bed_number: str = Field(..., description="Bed number")
    floor_number: Optional[int] = Field(default=None, description="Floor number")

    # Summaries
    financial_summary: StudentFinancialSummary = Field(
        ...,
        description="Financial overview",
    )
    attendance_summary: AttendanceSummary = Field(
        ...,
        description="Attendance overview",
    )
    stats: StudentStats = Field(
        ...,
        description="Quick statistics",
    )

    # Recent activity
    recent_payments: List[RecentPayment] = Field(
        default_factory=list,
        max_length=5,
        description="Last 5 payments",
    )
    recent_complaints: List[RecentComplaint] = Field(
        default_factory=list,
        max_length=5,
        description="Recent complaints",
    )
    pending_leave_applications: List[PendingLeave] = Field(
        default_factory=list,
        description="Pending leave requests",
    )

    # Announcements and events
    recent_announcements: List[RecentAnnouncement] = Field(
        default_factory=list,
        max_length=5,
        description="Recent announcements",
    )
    upcoming_events: List[UpcomingEvent] = Field(
        default_factory=list,
        max_length=5,
        description="Upcoming events",
    )
    unread_announcements_count: int = Field(
        default=0,
        ge=0,
        description="Unread announcements count",
    )

    # Mess menu
    today_mess_menu: Optional[TodayMessMenu] = Field(
        default=None,
        description="Today's mess menu",
    )

    # Notifications
    unread_notifications_count: int = Field(
        default=0,
        ge=0,
        description="Unread notifications count",
    )

    # Last updated
    dashboard_updated_at: datetime = Field(
        ...,
        description="Dashboard data timestamp",
    )

    @computed_field
    @property
    def has_urgent_items(self) -> bool:
        """Check if there are urgent items requiring attention."""
        # Check for urgent payments
        if self.financial_summary.is_payment_urgent:
            return True

        # Check for critical attendance
        if self.attendance_summary.attendance_status == "critical":
            return True

        # Check for high-priority complaints
        if any(c.priority in ["high", "urgent"] for c in self.recent_complaints):
            return True

        return False

    @computed_field
    @property
    def action_items_count(self) -> int:
        """Count items requiring action."""
        count = 0

        # Pending payments
        if self.financial_summary.amount_due > 0:
            count += 1

        # Pending leave approvals
        count += len(self.pending_leave_applications)

        # Open complaints
        count += sum(
            1 for c in self.recent_complaints if c.status != "resolved"
        )

        return count