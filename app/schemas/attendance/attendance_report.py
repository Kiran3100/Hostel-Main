# --- File: app/schemas/attendance/attendance_report.py ---
"""
Attendance reporting schemas with analytics and trends.

Provides comprehensive reporting capabilities including summaries,
trends, comparisons, and multi-level aggregations.
"""

from datetime import date as Date, datetime, time
from decimal import Decimal
from typing import Dict, List, Union, Any

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic.types import UUID4 as UUID

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import AttendanceStatus
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "AttendanceReport",
    "AttendanceSummary",
    "DailyAttendanceRecord",
    "TrendAnalysis",
    "WeeklyAttendance",
    "WeeklySummary",
    "MonthlyComparison",
    "MonthlyReport",
    "StudentMonthlySummary",
    "AttendanceComparison",
    "ComparisonItem",
    "CustomReportConfig",
    "ReportSchedule",
    "DashboardData",
    "ReportJobStatus",
]


class AttendanceSummary(BaseSchema):
    """
    Comprehensive attendance summary statistics.
    
    Provides aggregated metrics, percentages, streaks, and status
    assessment for a given period.
    """

    total_days: int = Field(
        ...,
        ge=0,
        description="Total number of days in period",
    )
    total_present: int = Field(
        ...,
        ge=0,
        description="Total present days",
    )
    total_absent: int = Field(
        ...,
        ge=0,
        description="Total absent days",
    )
    total_late: int = Field(
        ...,
        ge=0,
        description="Total late arrivals",
    )
    total_on_leave: int = Field(
        ...,
        ge=0,
        description="Total days on leave",
    )
    total_half_day: int = Field(
        default=0,
        ge=0,
        description="Total half-day attendances",
    )
    attendance_percentage: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Overall attendance percentage",
    )
    late_percentage: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Percentage of late arrivals",
    )

    # Streak tracking
    current_present_streak: int = Field(
        ...,
        ge=0,
        description="Current consecutive present days",
    )
    longest_present_streak: int = Field(
        ...,
        ge=0,
        description="Longest consecutive present streak in period",
    )
    current_absent_streak: int = Field(
        ...,
        ge=0,
        description="Current consecutive absent days",
    )
    longest_absent_streak: int = Field(
        default=0,
        ge=0,
        description="Longest consecutive absent streak in period",
    )

    # Status assessment
    attendance_status: str = Field(
        ...,
        pattern=r"^(excellent|good|warning|critical)$",
        description="Qualitative attendance assessment",
    )
    meets_minimum_requirement: bool = Field(
        ...,
        description="Whether attendance meets minimum policy requirement",
    )
    minimum_requirement_percentage: Union[Decimal, None] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Minimum required attendance percentage",
    )

    @field_validator("attendance_percentage", "late_percentage")
    @classmethod
    def round_percentage(cls, v: Decimal) -> Decimal:
        """Round percentages to 2 decimal places."""
        return round(v, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_accounted_days(self) -> int:
        """Calculate total days with attendance recorded."""
        return (
            self.total_present
            + self.total_absent
            + self.total_late
            + self.total_on_leave
            + self.total_half_day
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def unrecorded_days(self) -> int:
        """Calculate days without attendance record."""
        return max(0, self.total_days - self.total_accounted_days)


class DailyAttendanceRecord(BaseSchema):
    """
    Individual daily attendance record for reports.
    
    Represents a single day's attendance with complete details
    for timeline views and detailed reports.
    """

    date: Date = Field(
        ...,
        description="Attendance Date",
    )
    day_of_week: str = Field(
        ...,
        description="Day name (Monday, Tuesday, etc.)",
    )
    status: AttendanceStatus = Field(
        ...,
        description="Attendance status",
    )
    check_in_time: Union[time, None] = Field(
        None,
        description="Check-in time",
    )
    check_out_time: Union[time, None] = Field(
        None,
        description="Check-out time",
    )
    is_late: bool = Field(
        ...,
        description="Late arrival indicator",
    )
    late_minutes: Union[int, None] = Field(
        None,
        ge=0,
        description="Minutes late",
    )
    notes: Union[str, None] = Field(
        None,
        description="Additional notes or remarks",
    )
    is_holiday: bool = Field(
        default=False,
        description="Whether day was a holiday",
    )
    is_weekend: bool = Field(
        default=False,
        description="Whether day was a weekend",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_display(self) -> str:
        """Human-readable status display."""
        return self.status.value.replace("_", " ").title()


class WeeklyAttendance(BaseSchema):
    """
    Weekly attendance aggregation.
    
    Provides week-level summary for trend analysis and reporting.
    """

    week_number: int = Field(
        ...,
        ge=1,
        le=53,
        description="Week number in year (ISO week)",
    )
    year: int = Field(
        ...,
        ge=2000,
        description="Year for the week",
    )
    week_start_date: Date = Field(
        ...,
        description="Monday of the week",
    )
    week_end_date: Date = Field(
        ...,
        description="Sunday of the week",
    )
    total_days: int = Field(
        ...,
        ge=0,
        le=7,
        description="Total working days in week",
    )
    present_days: int = Field(
        ...,
        ge=0,
        description="Days present",
    )
    absent_days: int = Field(
        ...,
        ge=0,
        description="Days absent",
    )
    late_days: int = Field(
        default=0,
        ge=0,
        description="Days marked late",
    )
    attendance_percentage: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Weekly attendance percentage",
    )

    @field_validator("week_end_date")
    @classmethod
    def validate_week_dates(cls, v: Date, info) -> Date:
        """Validate week end Date is after start Date."""
        if info.data.get("week_start_date"):
            if v < info.data["week_start_date"]:
                raise ValueError("week_end_date must be after week_start_date")
        return v


class WeeklySummary(BaseSchema):
    """
    Weekly attendance summary with trends.
    
    Provides focused weekly attendance summary with day-by-day analysis
    and week-over-week trend comparisons.
    """
    
    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    week_number: int = Field(
        ...,
        ge=1,
        le=53,
        description="Week number in year (ISO week)",
    )
    year: int = Field(
        ...,
        ge=2000,
        description="Year for the week",
    )
    week_start_date: Date = Field(
        ...,
        description="Monday of the week",
    )
    week_end_date: Date = Field(
        ...,
        description="Sunday of the week",
    )
    
    # Summary statistics
    total_working_days: int = Field(
        ...,
        ge=0,
        le=7,
        description="Total working days in week",
    )
    average_attendance_percentage: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Average attendance for the week",
    )
    total_students: int = Field(
        ...,
        ge=0,
        description="Total number of students",
    )
    
    # Daily breakdown (if requested)
    daily_breakdown: Union[List[DailyAttendanceRecord], None] = Field(
        None,
        description="Day-by-day detailed breakdown",
    )
    
    # Week-over-week trends (if requested)
    previous_week_percentage: Union[Decimal, None] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Previous week's attendance percentage",
    )
    percentage_change: Union[Decimal, None] = Field(
        None,
        description="Percentage point change from previous week",
    )
    trend_direction: Union[str, None] = Field(
        None,
        pattern=r"^(improving|declining|stable)$",
        description="Trend direction compared to previous week",
    )
    
    # Analytics
    best_attendance_day: Union[str, None] = Field(
        None,
        description="Day with best attendance",
    )
    worst_attendance_day: Union[str, None] = Field(
        None,
        description="Day with worst attendance",
    )
    total_late_instances: int = Field(
        default=0,
        ge=0,
        description="Total late arrivals in the week",
    )
    total_absences: int = Field(
        default=0,
        ge=0,
        description="Total absences in the week",
    )
    
    # Report metadata
    generated_at: datetime = Field(
        ...,
        description="Report generation timestamp",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def trend_indicator(self) -> str:
        """Get trend indicator icon/color."""
        if self.trend_direction == "improving":
            return "↑"
        elif self.trend_direction == "declining":
            return "↓"
        else:
            return "→"


class MonthlyComparison(BaseSchema):
    """
    Monthly attendance comparison data.
    
    Used for month-over-month trend analysis and visualizations.
    """

    month: str = Field(
        ...,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Month in YYYY-MM format",
    )
    month_name: str = Field(
        ...,
        description="Month name (January, February, etc.)",
    )
    year: int = Field(
        ...,
        ge=2000,
        description="Year",
    )
    attendance_percentage: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Monthly attendance percentage",
    )
    total_present: int = Field(
        ...,
        ge=0,
        description="Total present days",
    )
    total_absent: int = Field(
        ...,
        ge=0,
        description="Total absent days",
    )
    total_late: int = Field(
        default=0,
        ge=0,
        description="Total late days",
    )
    working_days: int = Field(
        ...,
        ge=0,
        description="Total working days in month",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def trend_indicator(self) -> str:
        """Get trend indicator (up, down, stable) - requires comparison context."""
        # This would typically compare with previous month
        # Placeholder for illustration
        return "stable"


class TrendAnalysis(BaseSchema):
    """
    Attendance trend analysis over time.
    
    Provides insights into attendance patterns, improvements,
    and concerning trends.
    """

    period_start: Date = Field(
        ...,
        description="Analysis period start Date",
    )
    period_end: Date = Field(
        ...,
        description="Analysis period end Date",
    )
    
    # Weekly breakdown
    weekly_attendance: List[WeeklyAttendance] = Field(
        default_factory=list,
        description="Week-by-week attendance data",
    )
    
    # Monthly comparison
    monthly_comparison: Union[List[MonthlyComparison], None] = Field(
        None,
        description="Month-by-month comparison data",
    )
    
    # Pattern insights
    most_absent_day: Union[str, None] = Field(
        None,
        description="Day of week with most absences",
    )
    most_present_day: Union[str, None] = Field(
        None,
        description="Day of week with best attendance",
    )
    average_late_minutes: Union[Decimal, None] = Field(
        None,
        ge=Decimal("0"),
        description="Average minutes late across period",
    )
    
    # Trend indicators
    attendance_improving: bool = Field(
        ...,
        description="Whether attendance is trending upward",
    )
    improvement_rate: Union[Decimal, None] = Field(
        None,
        description="Rate of improvement (percentage points per month)",
    )
    trend_direction: str = Field(
        ...,
        pattern=r"^(improving|declining|stable)$",
        description="Overall trend direction",
    )
    
    # Predictive metrics
    projected_end_of_month_percentage: Union[Decimal, None] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Projected attendance percentage at month end",
    )

    @field_validator("period_end")
    @classmethod
    def validate_period(cls, v: Date, info) -> Date:
        """Validate period dates are logical."""
        if info.data.get("period_start"):
            if v < info.data["period_start"]:
                raise ValueError("period_end must be after period_start")
        return v


class AttendanceReport(BaseSchema):
    """
    Comprehensive attendance report.
    
    Main report schema combining summary statistics, detailed records,
    and trend analysis.
    """

    hostel_id: Union[UUID, None] = Field(
        None,
        description="Hostel ID (if hostel-specific report)",
    )
    hostel_name: Union[str, None] = Field(
        None,
        description="Hostel name",
    )
    student_id: Union[UUID, None] = Field(
        None,
        description="Student ID (if student-specific report)",
    )
    student_name: Union[str, None] = Field(
        None,
        description="Student name",
    )
    report_period: DateRangeFilter = Field(
        ...,
        description="Report Date range",
    )
    generated_at: datetime = Field(
        ...,
        description="Report generation timestamp",
    )
    generated_by: Union[UUID, None] = Field(
        None,
        description="User who generated the report",
    )
    
    # Core data
    summary: AttendanceSummary = Field(
        ...,
        description="Aggregated summary statistics",
    )
    daily_records: List[DailyAttendanceRecord] = Field(
        default_factory=list,
        description="Day-by-day attendance records",
    )
    
    # Analysis
    trend_analysis: Union[TrendAnalysis, None] = Field(
        None,
        description="Trend analysis and insights",
    )
    
    # Metadata
    report_type: str = Field(
        default="standard",
        pattern=r"^(standard|detailed|summary|comparison)$",
        description="Type of report",
    )
    includes_weekends: bool = Field(
        default=False,
        description="Whether weekends are included",
    )
    includes_holidays: bool = Field(
        default=False,
        description="Whether holidays are included",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_days_analyzed(self) -> int:
        """Total days included in analysis."""
        return len(self.daily_records)


class StudentMonthlySummary(BaseSchema):
    """
    Monthly attendance summary for individual student.
    
    Used in monthly reports to show per-student statistics.
    """

    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    student_name: str = Field(
        ...,
        description="Student full name",
    )
    room_number: Union[str, None] = Field(
        None,
        description="Room number",
    )
    email: Union[str, None] = Field(
        None,
        description="Student email",
    )
    phone: Union[str, None] = Field(
        None,
        description="Student phone",
    )
    total_days: int = Field(
        ...,
        ge=0,
        description="Total working days in month",
    )
    present_days: int = Field(
        ...,
        ge=0,
        description="Days present",
    )
    absent_days: int = Field(
        ...,
        ge=0,
        description="Days absent",
    )
    late_days: int = Field(
        ...,
        ge=0,
        description="Days marked late",
    )
    on_leave_days: int = Field(
        ...,
        ge=0,
        description="Days on leave",
    )
    half_days: int = Field(
        default=0,
        ge=0,
        description="Half-day attendances",
    )
    attendance_percentage: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Monthly attendance percentage",
    )
    meets_requirement: bool = Field(
        ...,
        description="Meets minimum attendance requirement",
    )
    
    # Action flags
    requires_attention: bool = Field(
        ...,
        description="Requires supervisor/admin attention",
    )
    action_required: Union[str, None] = Field(
        None,
        description="Specific action needed (if any)",
    )
    
    # Additional metrics
    consecutive_absences: int = Field(
        default=0,
        ge=0,
        description="Current consecutive absent days",
    )
    improvement_from_last_month: Union[Decimal, None] = Field(
        None,
        description="Percentage point change from last month",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_indicator(self) -> str:
        """
        Get status indicator based on attendance.
        
        Returns: excellent, good, warning, or critical
        """
        percentage = float(self.attendance_percentage)
        if percentage >= 95:
            return "excellent"
        elif percentage >= 85:
            return "good"
        elif percentage >= 75:
            return "warning"
        else:
            return "critical"


class MonthlyReport(BaseSchema):
    """
    Comprehensive monthly attendance report for hostel.
    
    Aggregates all students' attendance for a given month with
    hostel-wide statistics.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    month: str = Field(
        ...,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Month in YYYY-MM format",
    )
    month_name: str = Field(
        ...,
        description="Month name",
    )
    year: int = Field(
        ...,
        ge=2000,
        description="Year",
    )
    working_days: int = Field(
        ...,
        ge=0,
        description="Total working days in month",
    )
    
    # Student summaries
    student_summaries: List[StudentMonthlySummary] = Field(
        ...,
        description="Per-student monthly summaries",
    )
    
    # Hostel-wide statistics
    hostel_average_attendance: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Average attendance across all students",
    )
    total_students: int = Field(
        ...,
        ge=0,
        description="Total number of students",
    )
    students_meeting_requirement: int = Field(
        ...,
        ge=0,
        description="Students meeting minimum requirement",
    )
    students_below_requirement: int = Field(
        ...,
        ge=0,
        description="Students below minimum requirement",
    )
    students_needing_attention: int = Field(
        default=0,
        ge=0,
        description="Students requiring attention",
    )
    
    # Additional metrics
    total_late_instances: int = Field(
        default=0,
        ge=0,
        description="Total late arrivals across all students",
    )
    average_late_percentage: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Average late percentage",
    )
    
    # Report metadata
    generated_at: datetime = Field(
        ...,
        description="Report generation timestamp",
    )
    generated_by: Union[UUID, None] = Field(
        None,
        description="User who generated report",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def compliance_rate(self) -> Decimal:
        """Calculate percentage of students meeting requirements."""
        if self.total_students == 0:
            return Decimal("0.00")
        return round(
            Decimal(self.students_meeting_requirement) / Decimal(self.total_students) * 100,
            2,
        )


class ComparisonItem(BaseSchema):
    """
    Individual item in attendance comparison.
    
    Represents a single entity (student/hostel/room) in comparative analysis.
    """

    entity_id: UUID = Field(
        ...,
        description="Entity unique identifier",
    )
    entity_name: str = Field(
        ...,
        description="Entity name (student/hostel/room name)",
    )
    entity_type: str = Field(
        ...,
        pattern=r"^(student|hostel|room)$",
        description="Type of entity being compared",
    )
    attendance_percentage: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Attendance percentage",
    )
    total_present: int = Field(
        ...,
        ge=0,
        description="Total present count",
    )
    total_absent: int = Field(
        ...,
        ge=0,
        description="Total absent count",
    )
    total_days: int = Field(
        ...,
        ge=0,
        description="Total days in comparison period",
    )
    rank: int = Field(
        ...,
        ge=1,
        description="Rank in comparison (1 = best)",
    )
    percentile: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Percentile ranking",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def performance_indicator(self) -> str:
        """Get performance indicator based on percentile."""
        percentile_float = float(self.percentile)
        if percentile_float >= 90:
            return "top_performer"
        elif percentile_float >= 75:
            return "above_average"
        elif percentile_float >= 50:
            return "average"
        elif percentile_float >= 25:
            return "below_average"
        else:
            return "needs_improvement"


class AttendanceComparison(BaseSchema):
    """
    Comparative attendance analysis across entities.
    
    Enables benchmarking and performance comparison across
    students, hostels, or rooms.
    """

    comparison_type: str = Field(
        ...,
        pattern=r"^(student|hostel|room)$",
        description="Type of entities being compared",
    )
    period: DateRangeFilter = Field(
        ...,
        description="Comparison period",
    )
    hostel_id: Union[UUID, None] = Field(
        None,
        description="Hostel ID (for student/room comparisons)",
    )
    comparisons: List[ComparisonItem] = Field(
        ...,
        min_length=1,
        description="Comparison items sorted by rank",
    )
    
    # Statistical metrics
    average_attendance: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Average attendance across all entities",
    )
    median_attendance: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Median attendance",
    )
    highest_attendance: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Highest attendance percentage",
    )
    lowest_attendance: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Lowest attendance percentage",
    )
    standard_deviation: Union[Decimal, None] = Field(
        None,
        ge=Decimal("0"),
        description="Standard deviation of attendance",
    )
    
    # Report metadata
    generated_at: datetime = Field(
        ...,
        description="Comparison generation timestamp",
    )

    @field_validator("comparisons")
    @classmethod
    def validate_rankings(cls, v: List[ComparisonItem]) -> List[ComparisonItem]:
        """Validate rankings are sequential."""
        if v:
            ranks = sorted([item.rank for item in v])
            expected_ranks = list(range(1, len(v) + 1))
            if ranks != expected_ranks:
                raise ValueError("Comparison rankings must be sequential from 1")
        return v


class CustomReportConfig(BaseSchema):
    """
    Custom report configuration.
    
    Allows users to define custom reports with specific metrics,
    filters, and visualization options.
    """
    
    report_name: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Custom report name",
    )
    report_description: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Report description",
    )
    
    # Date range
    date_range: DateRangeFilter = Field(
        ...,
        description="Report date range",
    )
    
    # Entity filters
    hostel_id: Union[UUID, None] = Field(
        None,
        description="Specific hostel filter",
    )
    student_ids: Union[List[UUID], None] = Field(
        None,
        max_length=500,
        description="Specific students to include",
    )
    room_ids: Union[List[UUID], None] = Field(
        None,
        max_length=100,
        description="Specific rooms to include",
    )
    
    # Metrics to include
    include_summary: bool = Field(
        True,
        description="Include summary statistics",
    )
    include_daily_records: bool = Field(
        True,
        description="Include daily attendance records",
    )
    include_trends: bool = Field(
        True,
        description="Include trend analysis",
    )
    include_comparisons: bool = Field(
        False,
        description="Include comparative analysis",
    )
    include_violations: bool = Field(
        False,
        description="Include policy violations",
    )
    
    # Grouping options
    group_by: str = Field(
        "student",
        pattern=r"^(student|date|room|status|none)$",
        description="Group results by field",
    )
    
    # Sorting
    sort_by: str = Field(
        "date",
        pattern=r"^(date|student_name|attendance_percentage|room)$",
        description="Sort field",
    )
    sort_order: str = Field(
        "asc",
        pattern=r"^(asc|desc)$",
        description="Sort order",
    )
    
    # Visualization
    chart_types: List[str] = Field(
        default_factory=list,
        description="Chart types to include",
    )
    
    # Template saving
    save_template: bool = Field(
        default=False,
        description="Save as reusable template",
    )
    template_name: Union[str, None] = Field(
        None,
        max_length=200,
        description="Template name if saving",
    )

    @field_validator("chart_types")
    @classmethod
    def validate_chart_types(cls, v: List[str]) -> List[str]:
        """Validate chart types."""
        valid_types = {"line", "bar", "pie", "area", "heatmap"}
        for chart_type in v:
            if chart_type not in valid_types:
                raise ValueError(f"Invalid chart type: {chart_type}")
        return v

    @model_validator(mode="after")
    def validate_template_saving(self) -> "CustomReportConfig":
        """Validate template saving requirements."""
        if self.save_template and not self.template_name:
            raise ValueError("template_name is required when save_template is True")
        return self


class ReportSchedule(BaseSchema):
    """
    Scheduled report configuration.
    
    Defines automated report generation and delivery schedule.
    """
    
    id: Union[UUID, None] = Field(
        None,
        description="Schedule unique identifier",
    )
    schedule_name: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Schedule name",
    )
    
    # Report configuration
    report_config: CustomReportConfig = Field(
        ...,
        description="Report configuration to execute",
    )
    
    # Schedule settings
    frequency: str = Field(
        ...,
        pattern=r"^(daily|weekly|monthly|quarterly|custom)$",
        description="Report frequency",
    )
    cron_expression: Union[str, None] = Field(
        None,
        description="Cron expression for custom frequency",
    )
    
    # Execution time
    execution_time: time = Field(
        ...,
        description="Time of day to execute",
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone for execution",
    )
    
    # Delivery settings
    delivery_channels: List[str] = Field(
        ...,
        min_length=1,
        description="Delivery channels (email, dashboard, etc.)",
    )
    recipients: List[UUID] = Field(
        ...,
        min_length=1,
        description="Recipient user IDs",
    )
    
    # Status
    is_active: bool = Field(
        True,
        description="Whether schedule is active",
    )
    last_run: Union[datetime, None] = Field(
        None,
        description="Last execution timestamp",
    )
    next_run: Union[datetime, None] = Field(
        None,
        description="Next scheduled execution",
    )
    
    # Metadata
    created_by: UUID = Field(
        ...,
        description="User who created schedule",
    )
    created_at: Union[datetime, None] = Field(
        None,
        description="Schedule creation timestamp",
    )

    @field_validator("delivery_channels")
    @classmethod
    def validate_channels(cls, v: List[str]) -> List[str]:
        """Validate delivery channels."""
        valid_channels = {"email", "dashboard", "sms", "webhook"}
        for channel in v:
            if channel not in valid_channels:
                raise ValueError(f"Invalid delivery channel: {channel}")
        return v

    @model_validator(mode="after")
    def validate_custom_frequency(self) -> "ReportSchedule":
        """Validate cron expression is provided for custom frequency."""
        if self.frequency == "custom" and not self.cron_expression:
            raise ValueError("cron_expression is required when frequency is 'custom'")
        return self


class DashboardData(BaseSchema):
    """
    Real-time dashboard analytics data.
    
    Optimized data structure for attendance analytics dashboards.
    """
    
    hostel_id: Union[UUID, None] = Field(
        None,
        description="Hostel filter (if applicable)",
    )
    time_range: str = Field(
        ...,
        pattern=r"^(today|week|month|quarter)$",
        description="Time range for analytics",
    )
    generated_at: datetime = Field(
        ...,
        description="Data generation timestamp",
    )
    
    # Current statistics
    current_attendance_percentage: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Current attendance percentage",
    )
    total_students: int = Field(
        ...,
        ge=0,
        description="Total students",
    )
    present_today: int = Field(
        ...,
        ge=0,
        description="Students present today",
    )
    absent_today: int = Field(
        ...,
        ge=0,
        description="Students absent today",
    )
    late_today: int = Field(
        default=0,
        ge=0,
        description="Late arrivals today",
    )
    
    # Trends
    trend_data: Union[List[Dict[str, Any]], None] = Field(
        None,
        description="Trend chart data",
    )
    comparison_data: Union[Dict[str, Any], None] = Field(
        None,
        description="Comparison metrics",
    )
    
    # Alerts
    active_alerts: int = Field(
        default=0,
        ge=0,
        description="Number of active alerts",
    )
    critical_alerts: int = Field(
        default=0,
        ge=0,
        description="Number of critical alerts",
    )
    
    # Quick stats
    top_performers: Union[List[Dict[str, Any]], None] = Field(
        None,
        description="Top performing students",
    )
    needs_attention: Union[List[Dict[str, Any]], None] = Field(
        None,
        description="Students needing attention",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def attendance_status(self) -> str:
        """Get overall attendance status indicator."""
        percentage = float(self.current_attendance_percentage)
        if percentage >= 95:
            return "excellent"
        elif percentage >= 85:
            return "good"
        elif percentage >= 75:
            return "average"
        else:
            return "poor"


class ReportJobStatus(BaseSchema):
    """
    Background report job status.
    
    Tracks status of long-running report generation jobs.
    """
    
    job_id: str = Field(
        ...,
        description="Job unique identifier",
    )
    job_type: str = Field(
        ...,
        pattern=r"^(export|comparison|custom_report)$",
        description="Type of job",
    )
    status: str = Field(
        ...,
        pattern=r"^(queued|processing|completed|failed|cancelled)$",
        description="Current job status",
    )
    
    # Progress tracking
    progress_percentage: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Job completion percentage",
    )
    current_step: Union[str, None] = Field(
        None,
        description="Current processing step",
    )
    
    # Timing
    created_at: datetime = Field(
        ...,
        description="Job creation timestamp",
    )
    started_at: Union[datetime, None] = Field(
        None,
        description="Job start timestamp",
    )
    completed_at: Union[datetime, None] = Field(
        None,
        description="Job completion timestamp",
    )
    estimated_completion: Union[datetime, None] = Field(
        None,
        description="Estimated completion time",
    )
    
    # Results
    result_file_path: Union[str, None] = Field(
        None,
        description="Path to result file (if completed)",
    )
    result_file_size: Union[int, None] = Field(
        None,
        ge=0,
        description="Result file size in bytes",
    )
    error_message: Union[str, None] = Field(
        None,
        description="Error message (if failed)",
    )
    
    # Metadata
    created_by: UUID = Field(
        ...,
        description="User who created job",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_complete(self) -> bool:
        """Check if job is complete."""
        return self.status in ["completed", "failed", "cancelled"]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_successful(self) -> bool:
        """Check if job completed successfully."""
        return self.status == "completed"