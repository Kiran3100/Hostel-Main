# --- File: app/schemas/supervisor/supervisor_dashboard.py ---
"""
Supervisor dashboard schemas with real-time metrics and insights.

Provides comprehensive dashboard data with performance indicators,
task management, and actionable insights.
"""

from datetime import datetime, time, date as Date
from decimal import Decimal
from typing import Any, Dict, List, Union

from pydantic import Field, computed_field

from app.schemas.common.base import BaseSchema

__all__ = [
    "SupervisorDashboard",
    "DashboardMetrics",
    "TaskSummary",
    "RecentComplaintItem",
    "RecentMaintenanceItem",
    "PendingLeaveItem",
    "TodaySchedule",
    "DashboardAlert",
    "QuickActions",
    "PerformanceIndicators",
    "ScheduledMaintenanceItem",
    "ScheduledMeeting",
    "QuickAction",
]


class DashboardMetrics(BaseSchema):
    """
    Key performance metrics for supervisor dashboard.
    
    Real-time metrics with trend indicators and benchmarks.
    """

    # Student metrics
    total_students: int = Field(..., ge=0, description="Total students in hostel")
    active_students: int = Field(..., ge=0, description="Currently active students")
    students_on_leave: int = Field(..., ge=0, description="Students on approved leave")
    new_students_this_month: int = Field(..., ge=0, description="New admissions this month")
    
    # Occupancy metrics
    total_beds: int = Field(..., ge=0, description="Total bed capacity")
    occupied_beds: int = Field(..., ge=0, description="Currently occupied beds")
    available_beds: int = Field(..., ge=0, description="Available beds")
    occupancy_percentage: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Current occupancy percentage",
    )
    occupancy_trend: str = Field(
        ...,
        pattern=r"^(increasing|stable|decreasing)$",
        description="Occupancy trend direction",
    )
    
    # Complaint metrics
    total_complaints: int = Field(..., ge=0, description="Total complaints (all time)")
    open_complaints: int = Field(..., ge=0, description="Currently open complaints")
    assigned_to_me: int = Field(..., ge=0, description="Complaints assigned to me")
    resolved_today: int = Field(..., ge=0, description="Complaints resolved today")
    resolved_this_week: int = Field(..., ge=0, description="Resolved this week")
    average_resolution_time_hours: Decimal = Field(
        ...,
        ge=0,
        description="Average resolution time in hours",
    )
    sla_compliance_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="SLA compliance percentage",
    )
    
    # Maintenance metrics
    pending_maintenance: int = Field(..., ge=0, description="Pending maintenance requests")
    in_progress_maintenance: int = Field(..., ge=0, description="In-progress maintenance")
    completed_today: int = Field(..., ge=0, description="Completed today")
    overdue_maintenance: int = Field(..., ge=0, description="Overdue maintenance")
    maintenance_budget_used: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of maintenance budget used",
    )
    
    # Attendance metrics
    attendance_marked_today: bool = Field(..., description="Today's attendance marked")
    total_present_today: int = Field(..., ge=0, description="Students present today")
    total_absent_today: int = Field(..., ge=0, description="Students absent today")
    attendance_percentage_today: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Today's attendance percentage",
    )
    
    # Payment metrics (view-only)
    overdue_payments_count: int = Field(..., ge=0, description="Students with overdue payments")
    payment_collection_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Monthly payment collection rate",
    )
    
    # Communication metrics
    unread_admin_messages: int = Field(..., ge=0, description="Unread messages from admin")
    pending_announcements: int = Field(..., ge=0, description="Announcements pending approval")

    @computed_field
    @property
    def overall_health_score(self) -> Decimal:
        """Calculate overall hostel health score (0-100)."""
        # Weighted scoring based on key metrics
        occupancy_score = min(float(self.occupancy_percentage), 100) * 0.25
        complaint_score = max(0, 100 - (self.open_complaints * 5)) * 0.25
        maintenance_score = max(0, 100 - (self.pending_maintenance * 10)) * 0.25
        attendance_score = float(self.attendance_percentage_today) * 0.25
        
        total_score = occupancy_score + complaint_score + maintenance_score + attendance_score
        return Decimal(str(total_score)).quantize(Decimal("0.1"))

    @computed_field
    @property
    def needs_attention(self) -> List[str]:
        """Identify areas needing immediate attention."""
        issues = []
        
        if self.open_complaints > 5:
            issues.append("High number of open complaints")
        
        if self.overdue_maintenance > 0:
            issues.append("Overdue maintenance requests")
        
        if not self.attendance_marked_today:
            issues.append("Attendance not marked today")
        
        if self.occupancy_percentage < 70:
            issues.append("Low occupancy rate")
        
        if self.overdue_payments_count > 10:
            issues.append("Multiple overdue payments")
        
        return issues


class TaskSummary(BaseSchema):
    """
    Summary of pending tasks and priorities.
    
    Actionable task list with urgency indicators.
    """

    # High priority tasks
    urgent_complaints: int = Field(..., ge=0, description="Urgent complaints requiring attention")
    critical_maintenance: int = Field(..., ge=0, description="Critical maintenance requests")
    pending_leave_approvals: int = Field(..., ge=0, description="Leave requests awaiting approval")
    overdue_tasks: int = Field(..., ge=0, description="Overdue tasks")
    
    # Daily routine tasks
    attendance_pending: bool = Field(..., description="Daily attendance not yet marked")
    menu_published_today: bool = Field(..., description="Today's menu published")
    daily_inspection_done: bool = Field(..., description="Daily inspection completed")
    reports_pending: int = Field(..., ge=0, description="Reports pending submission")
    
    # Administrative tasks
    document_verifications_pending: int = Field(
        ...,
        ge=0,
        description="Student documents awaiting verification",
    )
    room_assignments_pending: int = Field(
        ...,
        ge=0,
        description="Room assignments to be processed",
    )
    
    # Overdue items
    overdue_complaint_resolutions: int = Field(
        ...,
        ge=0,
        description="Complaints past SLA deadline",
    )
    overdue_maintenance: int = Field(
        ...,
        ge=0,
        description="Maintenance past due Date",
    )
    
    # Total pending
    total_pending_tasks: int = Field(
        ...,
        ge=0,
        description="Total tasks requiring action",
    )

    @computed_field
    @property
    def priority_score(self) -> int:
        """Calculate task priority score (higher = more urgent)."""
        score = 0
        score += self.urgent_complaints * 10
        score += self.critical_maintenance * 8
        score += self.overdue_complaint_resolutions * 15
        score += self.overdue_maintenance * 12
        score += self.pending_leave_approvals * 3
        
        if self.attendance_pending:
            score += 20
        
        return score

    @computed_field
    @property
    def workload_level(self) -> str:
        """Assess current workload level."""
        if self.total_pending_tasks == 0:
            return "Light"
        elif self.total_pending_tasks <= 5:
            return "Moderate"
        elif self.total_pending_tasks <= 15:
            return "Heavy"
        else:
            return "Overwhelming"


class RecentComplaintItem(BaseSchema):
    """Recent complaint for dashboard display."""
    
    complaint_id: str = Field(..., description="Complaint ID")
    complaint_number: str = Field(..., description="Complaint reference number")
    title: str = Field(..., description="Complaint title")
    category: str = Field(..., description="Complaint category")
    priority: str = Field(..., description="Priority level")
    status: str = Field(..., description="Current status")
    
    # Student info
    student_name: str = Field(..., description="Student name")
    room_number: str = Field(..., description="Room number")
    
    # Timing
    created_at: datetime = Field(..., description="Complaint creation time")
    age_hours: int = Field(..., ge=0, description="Hours since creation")
    sla_deadline: Union[datetime, None] = Field(
        default=None,
        description="SLA deadline for resolution",
    )

    @computed_field
    @property
    def is_overdue(self) -> bool:
        """Check if complaint is past SLA deadline."""
        if not self.sla_deadline:
            return False
        return datetime.now() > self.sla_deadline

    @computed_field
    @property
    def urgency_indicator(self) -> str:
        """Get urgency indicator for UI."""
        if self.is_overdue:
            return "overdue"
        elif self.priority in ["urgent", "high"]:
            return "urgent"
        elif self.age_hours > 24:
            return "attention"
        else:
            return "normal"


class RecentMaintenanceItem(BaseSchema):
    """Recent maintenance request for dashboard."""
    
    request_id: str = Field(..., description="Maintenance request ID")
    request_number: str = Field(..., description="Request reference number")
    title: str = Field(..., description="Maintenance title")
    category: str = Field(..., description="Maintenance category")
    priority: str = Field(..., description="Priority level")
    status: str = Field(..., description="Current status")
    
    # Location
    room_number: Union[str, None] = Field(default=None, description="Room number")
    location_description: Union[str, None] = Field(
        default=None,
        description="Location description",
    )
    
    # Cost and timing
    estimated_cost: Union[Decimal, None] = Field(
        default=None,
        ge=0,
        description="Estimated cost",
    )
    created_at: datetime = Field(..., description="Request creation time")
    scheduled_date: Union[Date, None] = Field(
        default=None,
        description="Scheduled completion Date",
    )
    
    # Assignment
    assigned_to: Union[str, None] = Field(
        default=None,
        description="Assigned staff/vendor",
    )

    @computed_field
    @property
    def is_overdue(self) -> bool:
        """Check if maintenance is overdue."""
        if not self.scheduled_date:
            return False
        return Date.today() > self.scheduled_date

    @computed_field
    @property
    def days_pending(self) -> int:
        """Calculate days since request creation."""
        return (datetime.now() - self.created_at).days


class PendingLeaveItem(BaseSchema):
    """Pending leave approval for dashboard."""
    
    leave_id: str = Field(..., description="Leave application ID")
    student_name: str = Field(..., description="Student name")
    room_number: str = Field(..., description="Room number")
    
    # Leave details
    leave_type: str = Field(..., description="Type of leave")
    from_date: Date = Field(..., description="Leave start Date")
    to_date: Date = Field(..., description="Leave end Date")
    total_days: int = Field(..., ge=1, description="Total leave days")
    reason: str = Field(..., description="Leave reason")
    
    # Application details
    applied_at: datetime = Field(..., description="Application timestamp")
    emergency_contact: Union[str, None] = Field(
        default=None,
        description="Emergency contact during leave",
    )
    supporting_documents: bool = Field(
        default=False,
        description="Supporting documents provided",
    )

    @computed_field
    @property
    def is_urgent(self) -> bool:
        """Check if leave approval is urgent."""
        # Urgent if leave starts within 2 days
        return (self.from_date - Date.today()).days <= 2

    @computed_field
    @property
    def pending_days(self) -> int:
        """Days since application was submitted."""
        return (datetime.now() - self.applied_at).days


class ScheduledMaintenanceItem(BaseSchema):
    """Scheduled maintenance for today."""
    
    maintenance_id: str = Field(..., description="Maintenance ID")
    title: str = Field(..., description="Maintenance title")
    scheduled_time: time = Field(..., description="Scheduled time")
    estimated_duration_hours: Union[int, None] = Field(
        default=None,
        ge=1,
        description="Estimated duration in hours",
    )
    room_number: Union[str, None] = Field(default=None, description="Room number")
    assigned_staff: Union[str, None] = Field(default=None, description="Assigned staff")
    priority: str = Field(..., description="Priority level")


class ScheduledMeeting(BaseSchema):
    """Scheduled meeting for today."""
    
    meeting_id: str = Field(..., description="Meeting ID")
    title: str = Field(..., description="Meeting title")
    start_time: time = Field(..., description="Meeting start time")
    end_time: time = Field(..., description="Meeting end time")
    attendees: List[str] = Field(default_factory=list, description="Attendee names")
    location: str = Field(..., description="Meeting location")
    meeting_type: str = Field(
        ...,
        pattern=r"^(staff|admin|student|vendor|other)$",
        description="Type of meeting",
    )


class TodaySchedule(BaseSchema):
    """Today's schedule and planned activities."""
    
    Date: Date = Field(..., description="Schedule Date")
    
    # Routine tasks
    attendance_marking_time: time = Field(
        ...,
        description="Expected time for attendance marking",
    )
    inspection_rounds: List[str] = Field(
        default_factory=list,
        description="Scheduled inspection areas",
    )
    
    # Scheduled activities
    scheduled_maintenance: List[ScheduledMaintenanceItem] = Field(
        default_factory=list,
        description="Maintenance scheduled for today",
    )
    scheduled_meetings: List[ScheduledMeeting] = Field(
        default_factory=list,
        description="Meetings scheduled for today",
    )
    
    # Special events
    special_events: List[str] = Field(
        default_factory=list,
        description="Special events or occasions",
    )
    
    # Deadlines
    report_deadlines: List[str] = Field(
        default_factory=list,
        description="Reports due today",
    )

    @computed_field
    @property
    def total_scheduled_items(self) -> int:
        """Count total scheduled items for the day."""
        return (
            len(self.scheduled_maintenance) +
            len(self.scheduled_meetings) +
            len(self.special_events) +
            len(self.report_deadlines)
        )

    @computed_field
    @property
    def schedule_density(self) -> str:
        """Assess schedule density for the day."""
        if self.total_scheduled_items == 0:
            return "Light"
        elif self.total_scheduled_items <= 3:
            return "Moderate"
        elif self.total_scheduled_items <= 6:
            return "Busy"
        else:
            return "Very Busy"


class DashboardAlert(BaseSchema):
    """Dashboard alert/notification with action support."""
    
    alert_id: str = Field(..., description="Alert ID")
    alert_type: str = Field(
        ...,
        pattern=r"^(urgent|warning|info|success)$",
        description="Alert severity level",
    )
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Alert message")
    
    # Action support
    action_required: bool = Field(..., description="Whether action is required")
    action_url: Union[str, None] = Field(default=None, description="Action URL")
    action_label: Union[str, None] = Field(default=None, description="Action button label")
    
    # Metadata
    created_at: datetime = Field(..., description="Alert creation time")
    expires_at: Union[datetime, None] = Field(default=None, description="Alert expiration")
    is_dismissible: bool = Field(default=True, description="Can be dismissed by user")
    
    # Context
    related_entity_type: Union[str, None] = Field(
        default=None,
        description="Related entity type",
    )
    related_entity_id: Union[str, None] = Field(
        default=None,
        description="Related entity ID",
    )

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if alert has expired."""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at

    @computed_field
    @property
    def age_minutes(self) -> int:
        """Calculate alert age in minutes."""
        return int((datetime.now() - self.created_at).total_seconds() / 60)


class QuickAction(BaseSchema):
    """Individual quick action button."""
    
    action_id: str = Field(..., description="Action identifier")
    label: str = Field(..., description="Action label")
    icon: str = Field(..., description="Icon identifier")
    url: str = Field(..., description="Action URL")
    
    # Badge support
    badge_count: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Number indicator (e.g., pending items)",
    )
    badge_type: Union[str, None] = Field(
        default=None,
        pattern=r"^(info|warning|danger|success)$",
        description="Badge color type",
    )
    
    # Permissions
    requires_permission: Union[str, None] = Field(
        default=None,
        description="Required permission to show action",
    )
    
    # Grouping
    category: str = Field(
        default="general",
        description="Action category for grouping",
    )


class QuickActions(BaseSchema):
    """Quick action buttons for dashboard."""
    
    actions: List[QuickAction] = Field(
        ...,
        description="Available quick actions",
    )

    @computed_field
    @property
    def actions_by_category(self) -> Dict[str, List[QuickAction]]:
        """Group actions by category."""
        grouped: Dict[str, List[QuickAction]] = {}
        for action in self.actions:
            category = action.category
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(action)
        return grouped


class PerformanceIndicators(BaseSchema):
    """Key performance indicators for supervisor."""
    
    # Efficiency metrics
    complaint_resolution_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Complaint resolution rate %",
    )
    average_response_time_hours: Decimal = Field(
        ...,
        ge=0,
        description="Average response time to issues",
    )
    task_completion_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Task completion rate %",
    )
    
    # Quality metrics
    student_satisfaction_score: Union[Decimal, None] = Field(
        default=None,
        ge=0,
        le=5,
        description="Student satisfaction rating",
    )
    sla_compliance_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="SLA compliance rate %",
    )
    
    # Activity metrics
    daily_activity_score: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Daily activity score",
    )
    consistency_score: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Performance consistency score",
    )
    
    # Trend indicators
    performance_trend: str = Field(
        ...,
        pattern=r"^(improving|stable|declining)$",
        description="Overall performance trend",
    )
    
    # Benchmarking
    rank_among_peers: Union[int, None] = Field(
        default=None,
        ge=1,
        description="Rank among peer supervisors",
    )
    total_peers: Union[int, None] = Field(
        default=None,
        ge=1,
        description="Total number of peer supervisors",
    )

    @computed_field
    @property
    def overall_performance_score(self) -> Decimal:
        """Calculate overall performance score."""
        # Weighted average of key metrics
        weights = {
            'complaint_resolution': 0.25,
            'task_completion': 0.25,
            'sla_compliance': 0.25,
            'activity': 0.25,
        }
        
        score = (
            float(self.complaint_resolution_rate) * weights['complaint_resolution'] +
            float(self.task_completion_rate) * weights['task_completion'] +
            float(self.sla_compliance_rate) * weights['sla_compliance'] +
            float(self.daily_activity_score) * weights['activity']
        )
        
        return Decimal(str(score)).quantize(Decimal("0.1"))

    @computed_field
    @property
    def performance_grade(self) -> str:
        """Get performance grade based on overall score."""
        score = float(self.overall_performance_score)
        
        if score >= 90:
            return "A+"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B+"
        elif score >= 60:
            return "B"
        elif score >= 50:
            return "C"
        else:
            return "D"


class SupervisorDashboard(BaseSchema):
    """
    Complete supervisor dashboard with real-time data.
    
    Comprehensive dashboard providing all necessary information
    for effective hostel management.
    """

    supervisor_id: str = Field(..., description="Supervisor ID")
    supervisor_name: str = Field(..., description="Supervisor name")
    hostel_id: str = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    
    # Core metrics
    metrics: DashboardMetrics = Field(..., description="Key performance metrics")
    
    # Task management
    tasks: TaskSummary = Field(..., description="Pending tasks summary")
    
    # Recent activity
    recent_complaints: List[RecentComplaintItem] = Field(
        default_factory=list,
        max_length=5,
        description="Recent complaints (max 5)",
    )
    recent_maintenance: List[RecentMaintenanceItem] = Field(
        default_factory=list,
        max_length=5,
        description="Recent maintenance requests (max 5)",
    )
    pending_leaves: List[PendingLeaveItem] = Field(
        default_factory=list,
        max_length=10,
        description="Pending leave approvals (max 10)",
    )
    
    # Schedule
    today_schedule: TodaySchedule = Field(..., description="Today's schedule")
    
    # Alerts and notifications
    alerts: List[DashboardAlert] = Field(
        default_factory=list,
        description="Active alerts and notifications",
    )
    
    # Quick actions
    quick_actions: QuickActions = Field(..., description="Available quick actions")
    
    # Performance indicators
    performance: PerformanceIndicators = Field(
        ...,
        description="Performance indicators",
    )
    
    # Activity tracking
    last_login: Union[datetime, None] = Field(
        default=None,
        description="Last login timestamp",
    )
    actions_today: int = Field(
        default=0,
        ge=0,
        description="Actions performed today",
    )
    online_duration_minutes: int = Field(
        default=0,
        ge=0,
        description="Online duration today (minutes)",
    )
    
    # Dashboard metadata
    dashboard_updated_at: datetime = Field(
        ...,
        description="Dashboard data timestamp",
    )
    refresh_interval_seconds: int = Field(
        default=300,
        ge=60,
        description="Recommended refresh interval",
    )

    @computed_field
    @property
    def critical_alerts_count(self) -> int:
        """Count critical alerts requiring immediate attention."""
        return sum(1 for alert in self.alerts if alert.alert_type == "urgent")

    @computed_field
    @property
    def workload_summary(self) -> str:
        """Get workload summary description."""
        total_pending = self.tasks.total_pending_tasks
        urgent_items = (
            self.tasks.urgent_complaints +
            self.tasks.critical_maintenance +
            self.tasks.overdue_tasks
        )
        
        if urgent_items > 5:
            return "Critical workload - immediate attention required"
        elif total_pending > 15:
            return "Heavy workload - prioritize urgent tasks"
        elif total_pending > 5:
            return "Moderate workload - manageable"
        else:
            return "Light workload - good job!"

    @computed_field
    @property
    def dashboard_health_status(self) -> str:
        """Overall dashboard health status."""
        health_score = float(self.metrics.overall_health_score)
        critical_alerts = self.critical_alerts_count
        urgent_tasks = (
            self.tasks.urgent_complaints +
            self.tasks.critical_maintenance +
            self.tasks.overdue_tasks
        )
        
        if critical_alerts > 0 or urgent_tasks > 5:
            return "Critical"
        elif health_score < 60 or urgent_tasks > 2:
            return "Warning"
        elif health_score < 80:
            return "Good"
        else:
            return "Excellent"