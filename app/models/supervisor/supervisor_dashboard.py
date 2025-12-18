# app/models/supervisor/supervisor_dashboard.py
"""
Supervisor dashboard data models.

Manages dashboard metrics, task summaries, and real-time data
for supervisor interface with caching and optimization.
"""

from datetime import date as Date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, Date as SQLDate, DateTime, Decimal as SQLDecimal,
    ForeignKey, Integer, String, Text, Time, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.supervisor.supervisor import Supervisor
    from app.models.hostel.hostel import Hostel

__all__ = [
    "DashboardMetrics",
    "DashboardAlert",
    "QuickAction",
    "TodaySchedule",
    "PerformanceIndicator",
]


class DashboardMetrics(BaseModel, TimestampModel, UUIDMixin):
    """
    Cached dashboard metrics for supervisors.
    
    Pre-calculated metrics for efficient dashboard loading
    with periodic refresh and real-time updates.
    """
    
    __tablename__ = "supervisor_dashboard_metrics"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Supervisor reference"
    )
    
    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel reference"
    )
    
    # ============ Student Metrics ============
    total_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total students in hostel"
    )
    
    active_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Currently active students"
    )
    
    students_on_leave: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Students on approved leave"
    )
    
    new_students_this_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="New admissions this month"
    )
    
    # ============ Occupancy Metrics ============
    total_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total bed capacity"
    )
    
    occupied_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Currently occupied beds"
    )
    
    available_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Available beds"
    )
    
    occupancy_percentage: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Current occupancy percentage"
    )
    
    occupancy_trend: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="stable",
        comment="Trend: increasing, stable, decreasing"
    )
    
    # ============ Complaint Metrics ============
    total_complaints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total complaints (all time)"
    )
    
    open_complaints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Currently open complaints"
    )
    
    assigned_to_me: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Complaints assigned to me"
    )
    
    resolved_today: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Complaints resolved today"
    )
    
    resolved_this_week: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Resolved this week"
    )
    
    average_resolution_time_hours: Mapped[Decimal] = mapped_column(
        SQLDecimal(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average resolution time"
    )
    
    sla_compliance_rate: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("100.00"),
        comment="SLA compliance percentage"
    )
    
    # ============ Maintenance Metrics ============
    pending_maintenance: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Pending maintenance requests"
    )
    
    in_progress_maintenance: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="In-progress maintenance"
    )
    
    completed_today: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Completed today"
    )
    
    overdue_maintenance: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Overdue maintenance"
    )
    
    maintenance_budget_used: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Budget used percentage"
    )
    
    # ============ Attendance Metrics ============
    attendance_marked_today: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Today's attendance marked"
    )
    
    total_present_today: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Students present today"
    )
    
    total_absent_today: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Students absent today"
    )
    
    attendance_percentage_today: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Today's attendance percentage"
    )
    
    # ============ Payment Metrics ============
    overdue_payments_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Students with overdue payments"
    )
    
    payment_collection_rate: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Monthly payment collection rate"
    )
    
    # ============ Communication Metrics ============
    unread_admin_messages: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Unread messages from admin"
    )
    
    pending_announcements: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Announcements pending approval"
    )
    
    # ============ Health Score ============
    overall_health_score: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Overall hostel health score (0-100)"
    )
    
    # ============ Cache Metadata ============
    last_calculated: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Last calculation timestamp"
    )
    
    next_refresh_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="Next scheduled refresh"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        lazy="joined"
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_dashboard_metrics_supervisor", "supervisor_id"),
        Index("idx_dashboard_metrics_hostel", "hostel_id"),
        Index("idx_dashboard_metrics_refresh", "next_refresh_at"),
        {
            "comment": "Cached dashboard metrics for supervisor interface"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<DashboardMetrics(supervisor={self.supervisor_id}, "
            f"health_score={self.overall_health_score})>"
        )


class DashboardAlert(BaseModel, TimestampModel, UUIDMixin):
    """
    Dashboard alerts and notifications for supervisors.
    
    Real-time alerts with action support and priority handling
    for supervisor dashboard interface.
    """
    
    __tablename__ = "supervisor_dashboard_alerts"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor reference"
    )
    
    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel reference"
    )
    
    # ============ Alert Details ============
    alert_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Type: urgent, warning, info, success"
    )
    
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Alert title"
    )
    
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Alert message"
    )
    
    # ============ Action Support ============
    action_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether action is required"
    )
    
    action_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Action URL"
    )
    
    action_label: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Action button label"
    )
    
    # ============ Alert Lifecycle ============
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Alert creation time"
    )
    
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
        comment="Alert expiration time"
    )
    
    is_dismissible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Can be dismissed by user"
    )
    
    dismissed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Alert has been dismissed"
    )
    
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Dismissal timestamp"
    )
    
    # ============ Context ============
    related_entity_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Related entity type"
    )
    
    related_entity_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="Related entity ID"
    )
    
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional alert metadata"
    )
    
    # ============ Priority ============
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Alert priority (higher = more important)"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        lazy="joined"
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_alert_supervisor_dismissed", "supervisor_id", "dismissed"),
        Index("idx_alert_type_priority", "alert_type", "priority"),
        Index("idx_alert_expires", "expires_at", "dismissed"),
        Index("idx_alert_entity", "related_entity_type", "related_entity_id"),
        {
            "comment": "Dashboard alerts and notifications for supervisors"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<DashboardAlert(supervisor={self.supervisor_id}, "
            f"type={self.alert_type}, dismissed={self.dismissed})>"
        )
    
    @property
    def is_expired(self) -> bool:
        """Check if alert has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def age_minutes(self) -> int:
        """Calculate alert age in minutes."""
        return int((datetime.utcnow() - self.created_at).total_seconds() / 60)


class QuickAction(BaseModel, TimestampModel, UUIDMixin):
    """
    Quick action buttons for supervisor dashboard.
    
    Configurable quick actions with badge counts and
    permission-based visibility.
    """
    
    __tablename__ = "supervisor_quick_actions"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor reference"
    )
    
    # ============ Action Details ============
    action_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Action identifier"
    )
    
    label: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Action label"
    )
    
    icon: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Icon identifier"
    )
    
    url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Action URL"
    )
    
    # ============ Badge Support ============
    badge_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number indicator (e.g., pending items)"
    )
    
    badge_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Badge color: info, warning, danger, success"
    )
    
    # ============ Permissions ============
    requires_permission: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Required permission to show action"
    )
    
    # ============ Grouping ============
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="general",
        comment="Action category for grouping"
    )
    
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order in category"
    )
    
    # ============ Visibility ============
    is_visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Action is visible"
    )
    
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Action is enabled"
    )
    
    # ============ Cache ============
    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Last update timestamp"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_quick_action_supervisor", "supervisor_id", "is_visible"),
        Index("idx_quick_action_category", "category", "display_order"),
        {
            "comment": "Configurable quick actions for supervisor dashboard"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<QuickAction(supervisor={self.supervisor_id}, "
            f"action={self.action_id}, visible={self.is_visible})>"
        )


class TodaySchedule(BaseModel, TimestampModel, UUIDMixin):
    """
    Today's schedule for supervisor dashboard.
    
    Daily schedule with tasks, meetings, and maintenance
    for supervisor planning and execution.
    """
    
    __tablename__ = "supervisor_today_schedules"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor reference"
    )
    
    hostel_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel reference"
    )
    
    # ============ Schedule Date ============
    schedule_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Schedule date"
    )
    
    # ============ Routine Tasks ============
    attendance_marking_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(9, 0),
        comment="Expected time for attendance marking"
    )
    
    attendance_marked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Attendance marked status"
    )
    
    inspection_rounds: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Scheduled inspection areas and times"
    )
    
    # ============ Scheduled Activities ============
    scheduled_maintenance: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Maintenance scheduled for today"
    )
    
    scheduled_meetings: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Meetings scheduled for today"
    )
    
    special_events: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Special events or occasions"
    )
    
    # ============ Deadlines ============
    report_deadlines: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Reports due today"
    )
    
    # ============ Summary Counts ============
    total_scheduled_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total scheduled items"
    )
    
    completed_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Completed items"
    )
    
    pending_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Pending items"
    )
    
    # ============ Schedule Density ============
    schedule_density: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="light",
        comment="Density: light, moderate, busy, very_busy"
    )
    
    # ============ Notes ============
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional schedule notes"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        lazy="joined"
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_schedule_supervisor_date", "supervisor_id", "schedule_date"),
        Index("idx_schedule_hostel_date", "hostel_id", "schedule_date"),
        Index("idx_schedule_density", "schedule_density", "schedule_date"),
        {
            "comment": "Daily schedule for supervisor planning and tracking"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<TodaySchedule(supervisor={self.supervisor_id}, "
            f"date={self.schedule_date}, items={self.total_scheduled_items})>"
        )
    
    @property
    def completion_rate(self) -> float:
        """Calculate completion rate percentage."""
        if self.total_scheduled_items == 0:
            return 100.0
        return (self.completed_items / self.total_scheduled_items) * 100


class PerformanceIndicator(BaseModel, TimestampModel, UUIDMixin):
    """
    Key performance indicators for supervisor dashboard.
    
    Real-time KPIs with trends and targets for supervisor
    performance monitoring and improvement.
    """
    
    __tablename__ = "supervisor_performance_indicators"
    
    # ============ Relationships ============
    supervisor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Supervisor reference"
    )
    
    # ============ Measurement Period ============
    measurement_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Measurement date"
    )
    
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="daily",
        comment="Period: daily, weekly, monthly"
    )
    
    # ============ Efficiency Metrics ============
    complaint_resolution_rate: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Complaint resolution rate %"
    )
    
    average_response_time_hours: Mapped[Decimal] = mapped_column(
        SQLDecimal(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average response time to issues"
    )
    
    task_completion_rate: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Task completion rate %"
    )
    
    # ============ Quality Metrics ============
    student_satisfaction_score: Mapped[Optional[Decimal]] = mapped_column(
        SQLDecimal(3, 2),
        nullable=True,
        comment="Student satisfaction rating (0-5)"
    )
    
    sla_compliance_rate: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("100.00"),
        comment="SLA compliance rate %"
    )
    
    # ============ Activity Metrics ============
    daily_activity_score: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Daily activity score (0-100)"
    )
    
    consistency_score: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Performance consistency score"
    )
    
    # ============ Trend Indicators ============
    performance_trend: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="stable",
        comment="Trend: improving, stable, declining"
    )
    
    # ============ Benchmarking ============
    rank_among_peers: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Rank among peer supervisors"
    )
    
    total_peers: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Total peer supervisors"
    )
    
    # ============ Overall Score ============
    overall_performance_score: Mapped[Decimal] = mapped_column(
        SQLDecimal(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Overall performance score (0-100)"
    )
    
    performance_grade: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="C",
        comment="Performance grade: A+, A, B+, B, C, D"
    )
    
    # ============ Relationships ============
    supervisor: Mapped["Supervisor"] = relationship(
        "Supervisor",
        lazy="joined"
    )
    
    # ============ Indexes ============
    __table_args__ = (
        Index("idx_kpi_supervisor_date", "supervisor_id", "measurement_date"),
        Index("idx_kpi_period_type", "period_type", "measurement_date"),
        Index("idx_kpi_grade", "performance_grade", "measurement_date"),
        {
            "comment": "Key performance indicators for supervisor dashboard"
        }
    )
    
    def __repr__(self) -> str:
        return (
            f"<PerformanceIndicator(supervisor={self.supervisor_id}, "
            f"date={self.measurement_date}, grade={self.performance_grade})>"
        )