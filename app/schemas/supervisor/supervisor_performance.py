# --- File: app/schemas/supervisor/supervisor_performance.py ---
"""
Supervisor performance tracking schemas with comprehensive analytics.

Provides detailed performance measurement, goal tracking, and
comparative analysis with peer benchmarking.
"""

from datetime import date as Date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Union

from pydantic import Field, field_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "PerformanceMetrics",
    "PerformanceReport",
    "ComplaintPerformance",
    "AttendancePerformance",
    "MaintenancePerformance",
    "PerformanceTrendPoint",
    "PeerComparison",
    "MetricComparison",
    "PeriodComparison",
    "PerformanceReview",
    "PerformanceReviewResponse",
    "PerformanceGoal",
    "PerformanceGoalProgress",
    "PerformanceInsights",
]


class PerformanceMetrics(BaseSchema):
    """
    Comprehensive supervisor performance metrics.
    
    Aggregated performance data across all key areas with
    trend analysis and benchmarking.
    """

    supervisor_id: str = Field(..., description="Supervisor ID")
    supervisor_name: str = Field(..., description="Supervisor name")
    hostel_id: str = Field(..., description="Hostel ID")
    period_start: Date = Field(..., description="Metrics period start")
    period_end: Date = Field(..., description="Metrics period end")
    
    # ============ Complaint Handling Metrics ============
    complaints_handled: int = Field(..., ge=0, description="Total complaints handled")
    complaints_resolved: int = Field(..., ge=0, description="Complaints resolved")
    complaint_resolution_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Complaint resolution rate percentage",
    )
    average_resolution_time_hours: Decimal = Field(
        ...,
        ge=0,
        description="Average time to resolve complaints",
    )
    sla_compliance_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="SLA compliance rate percentage",
    )
    first_response_time_minutes: Decimal = Field(
        ...,
        ge=0,
        description="Average first response time",
    )
    
    # ============ Attendance Management Metrics ============
    attendance_records_created: int = Field(
        ...,
        ge=0,
        description="Attendance records created",
    )
    attendance_accuracy: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Attendance accuracy percentage",
    )
    leaves_approved: int = Field(..., ge=0, description="Leave applications approved")
    leaves_rejected: int = Field(..., ge=0, description="Leave applications rejected")
    attendance_punctuality_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="On-time attendance marking rate",
    )
    
    # ============ Maintenance Management Metrics ============
    maintenance_requests_created: int = Field(
        ...,
        ge=0,
        description="Maintenance requests created",
    )
    maintenance_completed: int = Field(
        ...,
        ge=0,
        description="Maintenance requests completed",
    )
    maintenance_completion_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Maintenance completion rate",
    )
    average_maintenance_time_hours: Decimal = Field(
        ...,
        ge=0,
        description="Average maintenance completion time",
    )
    maintenance_cost_efficiency: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Cost efficiency percentage",
    )
    
    # ============ Communication Metrics ============
    announcements_created: int = Field(
        ...,
        ge=0,
        description="Announcements created",
    )
    announcement_reach: int = Field(
        ...,
        ge=0,
        description="Total students reached by announcements",
    )
    student_interactions: int = Field(
        ...,
        ge=0,
        description="Direct student interactions",
    )
    
    # ============ Responsiveness Metrics ============
    average_first_response_time_minutes: Decimal = Field(
        ...,
        ge=0,
        description="Average first response time to issues",
    )
    availability_percentage: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Availability during working hours",
    )
    response_consistency_score: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Consistency in response times",
    )
    
    # ============ Student Satisfaction ============
    student_feedback_score: Union[Decimal, None] = Field(
        default=None,
        ge=0,
        le=5,
        description="Average student feedback rating",
    )
    student_feedback_count: int = Field(
        ...,
        ge=0,
        description="Number of student feedback responses",
    )
    complaint_escalation_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of complaints escalated",
    )
    
    # ============ Overall Performance ============
    overall_performance_score: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Calculated overall performance score",
    )
    performance_grade: str = Field(
        ...,
        pattern=r"^(A\+|A|B\+|B|C|D)$",
        description="Performance grade",
    )

    @computed_field
    @property
    def efficiency_score(self) -> Decimal:
        """Calculate efficiency score based on time metrics."""
        # Weighted score based on response times and completion rates
        response_score = max(0, 100 - float(self.average_first_response_time_minutes))
        completion_score = float(self.complaint_resolution_rate + self.maintenance_completion_rate) / 2
        
        efficiency = (response_score * 0.4 + completion_score * 0.6)
        return Decimal(str(efficiency)).quantize(Decimal("0.1"))

    @computed_field
    @property
    def quality_score(self) -> Decimal:
        """Calculate quality score based on accuracy and satisfaction."""
        quality_metrics = [
            float(self.attendance_accuracy),
            float(self.sla_compliance_rate),
            float(self.maintenance_cost_efficiency),
        ]
        
        if self.student_feedback_score:
            quality_metrics.append(float(self.student_feedback_score) * 20)  # Convert 5-point to 100-point
        
        average_quality = sum(quality_metrics) / len(quality_metrics)
        return Decimal(str(average_quality)).quantize(Decimal("0.1"))


class ComplaintPerformance(BaseSchema):
    """Detailed complaint handling performance analysis."""
    
    total_complaints: int = Field(..., ge=0, description="Total complaints handled")
    resolved_complaints: int = Field(..., ge=0, description="Successfully resolved")
    pending_complaints: int = Field(..., ge=0, description="Currently pending")
    escalated_complaints: int = Field(..., ge=0, description="Escalated to admin")
    
    # Category breakdown
    complaints_by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Complaints by category",
    )
    
    # Priority breakdown
    complaints_by_priority: Dict[str, int] = Field(
        default_factory=dict,
        description="Complaints by priority level",
    )
    
    # Resolution time analysis
    average_resolution_time_hours: Decimal = Field(
        ...,
        ge=0,
        description="Average resolution time",
    )
    fastest_resolution_hours: Decimal = Field(
        ...,
        ge=0,
        description="Fastest resolution time",
    )
    slowest_resolution_hours: Decimal = Field(
        ...,
        ge=0,
        description="Slowest resolution time",
    )
    median_resolution_time_hours: Decimal = Field(
        ...,
        ge=0,
        description="Median resolution time",
    )
    
    # SLA performance
    within_sla: int = Field(..., ge=0, description="Complaints resolved within SLA")
    breached_sla: int = Field(..., ge=0, description="SLA breaches")
    sla_compliance_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="SLA compliance percentage",
    )
    
    # Student satisfaction
    average_complaint_rating: Union[Decimal, None] = Field(
        default=None,
        ge=0,
        le=5,
        description="Average student rating for resolved complaints",
    )
    satisfaction_responses: int = Field(
        ...,
        ge=0,
        description="Number of satisfaction responses received",
    )

    @computed_field
    @property
    def resolution_efficiency(self) -> str:
        """Categorize resolution efficiency."""
        avg_hours = float(self.average_resolution_time_hours)
        
        if avg_hours <= 4:
            return "Excellent"
        elif avg_hours <= 12:
            return "Good"
        elif avg_hours <= 24:
            return "Average"
        elif avg_hours <= 48:
            return "Below Average"
        else:
            return "Poor"


class AttendancePerformance(BaseSchema):
    """Attendance management performance details."""
    
    total_attendance_records: int = Field(
        ...,
        ge=0,
        description="Total attendance records created",
    )
    days_attendance_marked: int = Field(
        ...,
        ge=0,
        description="Days attendance was marked",
    )
    days_attendance_missed: int = Field(
        ...,
        ge=0,
        description="Days attendance was not marked",
    )
    
    # Timeliness metrics
    on_time_marking_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of on-time attendance marking",
    )
    average_marking_delay_minutes: Decimal = Field(
        ...,
        ge=0,
        description="Average delay in attendance marking",
    )
    
    # Accuracy metrics
    corrections_made: int = Field(
        ...,
        ge=0,
        description="Number of attendance corrections made",
    )
    accuracy_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Attendance accuracy rate",
    )
    
    # Leave management
    leaves_processed: int = Field(
        ...,
        ge=0,
        description="Total leave applications processed",
    )
    leaves_approved: int = Field(
        ...,
        ge=0,
        description="Leave applications approved",
    )
    leaves_rejected: int = Field(
        ...,
        ge=0,
        description="Leave applications rejected",
    )
    average_leave_approval_time_hours: Decimal = Field(
        ...,
        ge=0,
        description="Average time to process leave applications",
    )

    @computed_field
    @property
    def attendance_consistency(self) -> str:
        """Assess attendance marking consistency."""
        total_days = self.days_attendance_marked + self.days_attendance_missed
        if total_days == 0:
            return "No Data"
        
        consistency_rate = (self.days_attendance_marked / total_days) * 100
        
        if consistency_rate >= 95:
            return "Excellent"
        elif consistency_rate >= 85:
            return "Good"
        elif consistency_rate >= 70:
            return "Average"
        else:
            return "Poor"

    @computed_field
    @property
    def leave_approval_rate(self) -> Decimal:
        """Calculate leave approval rate."""
        if self.leaves_processed == 0:
            return Decimal("0.00")
        
        rate = (self.leaves_approved / self.leaves_processed) * 100
        return Decimal(str(rate)).quantize(Decimal("0.01"))


class MaintenancePerformance(BaseSchema):
    """Maintenance management performance details."""
    
    requests_created: int = Field(
        ...,
        ge=0,
        description="Maintenance requests created",
    )
    requests_completed: int = Field(
        ...,
        ge=0,
        description="Maintenance requests completed",
    )
    requests_pending: int = Field(
        ...,
        ge=0,
        description="Currently pending requests",
    )
    requests_overdue: int = Field(
        ...,
        ge=0,
        description="Overdue maintenance requests",
    )
    
    # Category breakdown
    requests_by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Requests by maintenance category",
    )
    
    # Completion time analysis
    average_completion_time_hours: Decimal = Field(
        ...,
        ge=0,
        description="Average completion time",
    )
    fastest_completion_hours: Decimal = Field(
        ...,
        ge=0,
        description="Fastest completion time",
    )
    slowest_completion_hours: Decimal = Field(
        ...,
        ge=0,
        description="Slowest completion time",
    )
    
    # Cost management
    total_maintenance_cost: Decimal = Field(
        ...,
        ge=0,
        description="Total maintenance costs",
    )
    average_cost_per_request: Decimal = Field(
        ...,
        ge=0,
        description="Average cost per request",
    )
    budget_allocated: Decimal = Field(
        ...,
        ge=0,
        description="Allocated maintenance budget",
    )
    within_budget_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of requests within budget",
    )
    
    # Preventive maintenance
    preventive_tasks_completed: int = Field(
        ...,
        ge=0,
        description="Preventive maintenance tasks completed",
    )
    preventive_tasks_scheduled: int = Field(
        ...,
        ge=0,
        description="Preventive maintenance tasks scheduled",
    )
    preventive_compliance_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Preventive maintenance compliance rate",
    )

    @computed_field
    @property
    def completion_rate(self) -> Decimal:
        """Calculate maintenance completion rate."""
        total_requests = self.requests_created
        if total_requests == 0:
            return Decimal("100.00")
        
        rate = (self.requests_completed / total_requests) * 100
        return Decimal(str(rate)).quantize(Decimal("0.01"))

    @computed_field
    @property
    def budget_utilization(self) -> Decimal:
        """Calculate budget utilization percentage."""
        if self.budget_allocated == 0:
            return Decimal("0.00")
        
        utilization = (self.total_maintenance_cost / self.budget_allocated) * 100
        return Decimal(str(utilization)).quantize(Decimal("0.01"))


class PerformanceTrendPoint(BaseSchema):
    """Performance trend data point for analysis."""
    
    period: str = Field(
        ...,
        description="Time period identifier",
        examples=["2024-01", "Week 15", "Q1 2024"],
    )
    overall_score: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Overall performance score for period",
    )
    complaint_score: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Complaint handling score",
    )
    attendance_score: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Attendance management score",
    )
    maintenance_score: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Maintenance management score",
    )
    student_satisfaction_score: Union[Decimal, None] = Field(
        default=None,
        ge=0,
        le=100,
        description="Student satisfaction score",
    )

    @computed_field
    @property
    def trend_indicator(self) -> str:
        """Get trend indicator for the period."""
        # This would typically be calculated by comparing with previous period
        # For now, return based on overall score
        score = float(self.overall_score)
        if score >= 85:
            return "excellent"
        elif score >= 70:
            return "good"
        elif score >= 55:
            return "average"
        else:
            return "needs_improvement"


class MetricComparison(BaseSchema):
    """Individual metric comparison with peers."""
    
    metric_name: str = Field(..., description="Name of the metric")
    supervisor_value: Decimal = Field(..., description="Supervisor's value")
    peer_average: Decimal = Field(..., description="Peer average value")
    peer_median: Decimal = Field(..., description="Peer median value")
    best_peer_value: Decimal = Field(..., description="Best peer value")
    difference_from_average: Decimal = Field(
        ...,
        description="Difference from peer average",
    )
    difference_percentage: Decimal = Field(
        ...,
        description="Percentage difference from average",
    )
    better_than_average: bool = Field(
        ...,
        description="Whether supervisor performs better than average",
    )

    @computed_field
    @property
    def performance_vs_peers(self) -> str:
        """Describe performance relative to peers."""
        if self.better_than_average:
            if float(self.difference_percentage) >= 20:
                return "Significantly Above Average"
            elif float(self.difference_percentage) >= 10:
                return "Above Average"
            else:
                return "Slightly Above Average"
        else:
            if float(abs(self.difference_percentage)) >= 20:
                return "Significantly Below Average"
            elif float(abs(self.difference_percentage)) >= 10:
                return "Below Average"
            else:
                return "Slightly Below Average"


class PeerComparison(BaseSchema):
    """Comparison with peer supervisors."""
    
    total_supervisors: int = Field(
        ...,
        ge=1,
        description="Total number of supervisors in comparison",
    )
    rank: int = Field(
        ...,
        ge=1,
        description="Supervisor's rank among peers (1 = best)",
    )
    percentile: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Performance percentile",
    )
    
    # Metric comparisons
    metrics_vs_average: Dict[str, MetricComparison] = Field(
        default_factory=dict,
        description="Individual metric comparisons",
    )
    
    # Top performers
    top_performer_score: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Score of top performer",
    )
    score_gap_to_top: Decimal = Field(
        ...,
        ge=0,
        description="Gap to top performer",
    )

    @computed_field
    @property
    def performance_tier(self) -> str:
        """Categorize performance tier among peers."""
        if self.percentile >= 90:
            return "Top Performer"
        elif self.percentile >= 75:
            return "High Performer"
        elif self.percentile >= 50:
            return "Average Performer"
        elif self.percentile >= 25:
            return "Below Average"
        else:
            return "Needs Improvement"


class PeriodComparison(BaseSchema):
    """Comparison with previous period."""
    
    previous_period: DateRangeFilter = Field(
        ...,
        description="Previous comparison period",
    )
    current_period: DateRangeFilter = Field(
        ...,
        description="Current period",
    )
    
    # Overall change
    overall_score_change: Decimal = Field(
        ...,
        description="Percentage change in overall score",
    )
    
    # Metric changes
    metric_changes: Dict[str, Decimal] = Field(
        ...,
        description="Percentage change for each metric",
    )
    
    # Improvement/decline indicators
    improved_metrics: List[str] = Field(
        default_factory=list,
        description="Metrics that improved",
    )
    declined_metrics: List[str] = Field(
        default_factory=list,
        description="Metrics that declined",
    )
    stable_metrics: List[str] = Field(
        default_factory=list,
        description="Metrics that remained stable",
    )

    @computed_field
    @property
    def overall_trend(self) -> str:
        """Determine overall performance trend."""
        if self.overall_score_change >= 5:
            return "Improving"
        elif self.overall_score_change <= -5:
            return "Declining"
        else:
            return "Stable"

    @computed_field
    @property
    def improvement_summary(self) -> str:
        """Generate improvement summary."""
        improved_count = len(self.improved_metrics)
        declined_count = len(self.declined_metrics)
        
        if improved_count > declined_count:
            return f"Improved in {improved_count} areas, declined in {declined_count}"
        elif declined_count > improved_count:
            return f"Declined in {declined_count} areas, improved in {improved_count}"
        else:
            return f"Mixed performance: {improved_count} improved, {declined_count} declined"


# MOVED THESE CLASSES BEFORE PerformanceReport
class PerformanceGoal(BaseCreateSchema):
    """Set performance goal for supervisor."""
    
    supervisor_id: str = Field(..., description="Supervisor ID")
    goal_name: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Goal name",
    )
    goal_description: str = Field(
        ...,
        min_length=20,
        max_length=1000,
        description="Detailed goal description",
    )
    
    # Measurable target
    metric_name: str = Field(
        ...,
        description="Metric to measure",
        examples=[
            "complaint_resolution_rate",
            "sla_compliance_rate",
            "attendance_punctuality_rate",
        ],
    )
    target_value: Decimal = Field(
        ...,
        description="Target value to achieve",
    )
    current_value: Union[Decimal, None] = Field(
        default=None,
        description="Current baseline value",
    )
    
    # Timeline
    start_date: Date = Field(..., description="Goal start Date")
    end_date: Date = Field(..., description="Goal target completion Date")
    
    # Priority and category
    priority: str = Field(
        default="medium",
        pattern=r"^(low|medium|high|critical)$",
        description="Goal priority level",
    )
    category: str = Field(
        ...,
        pattern=r"^(complaint|attendance|maintenance|communication|efficiency|quality)$",
        description="Goal category",
    )
    
    # Tracking
    measurement_frequency: str = Field(
        default="weekly",
        pattern=r"^(daily|weekly|monthly)$",
        description="How often to measure progress",
    )

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: Date, info) -> Date:
        """Validate end Date is after start Date."""
        # In Pydantic v2, we use info.data instead of values
        start_date = info.data.get("start_date")
        if start_date and v <= start_date:
            raise ValueError("End Date must be after start Date")
        return v

    @computed_field
    @property
    def duration_days(self) -> int:
        """Calculate goal duration in days."""
        return (self.end_date - self.start_date).days


class PerformanceGoalProgress(BaseSchema):
    """Track progress on performance goal."""
    
    goal_id: str = Field(..., description="Goal ID")
    goal_name: str = Field(..., description="Goal name")
    metric_name: str = Field(..., description="Metric being measured")
    
    # Values
    target_value: Decimal = Field(..., description="Target value")
    current_value: Decimal = Field(..., description="Current achieved value")
    baseline_value: Union[Decimal, None] = Field(
        default=None,
        description="Starting baseline value",
    )
    
    # Progress calculation
    progress_percentage: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Progress percentage towards goal",
    )
    
    # Timeline
    start_date: Date = Field(..., description="Goal start Date")
    end_date: Date = Field(..., description="Goal end Date")
    days_remaining: int = Field(..., ge=0, description="Days remaining to achieve goal")
    
    # Status
    status: str = Field(
        ...,
        pattern=r"^(on_track|at_risk|behind|completed|failed|paused)$",
        description="Goal progress status",
    )
    
    # Tracking
    last_updated: datetime = Field(..., description="Last progress update")
    measurement_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Historical measurements",
    )

    @computed_field
    @property
    def days_elapsed(self) -> int:
        """Calculate days elapsed since goal start."""
        return (Date.today() - self.start_date).days

    @computed_field
    @property
    def time_progress_percentage(self) -> Decimal:
        """Calculate time progress percentage."""
        total_days = (self.end_date - self.start_date).days
        if total_days == 0:
            return Decimal("100.00")
        
        elapsed_days = self.days_elapsed
        time_progress = min(100, (elapsed_days / total_days) * 100)
        return Decimal(str(time_progress)).quantize(Decimal("0.01"))

    @computed_field
    @property
    def is_on_schedule(self) -> bool:
        """Check if goal progress is on schedule."""
        time_progress = float(self.time_progress_percentage)
        actual_progress = float(self.progress_percentage)
        
        # Allow 10% tolerance
        return actual_progress >= (time_progress - 10)

    @computed_field
    @property
    def projected_completion_date(self) -> Union[Date, None]:
        """Project completion Date based on current progress rate."""
        if self.progress_percentage == 0:
            return None
        
        days_elapsed = self.days_elapsed
        if days_elapsed == 0:
            return None
        
        progress_rate = float(self.progress_percentage) / days_elapsed
        if progress_rate == 0:
            return None
        
        remaining_progress = 100 - float(self.progress_percentage)
        days_to_complete = remaining_progress / progress_rate
        
        projected_date = Date.today() + timedelta(days=int(days_to_complete))
        return projected_date


class PerformanceReport(BaseSchema):
    """Comprehensive performance report."""
    
    supervisor_id: str = Field(..., description="Supervisor ID")
    supervisor_name: str = Field(..., description="Supervisor name")
    hostel_name: str = Field(..., description="Hostel name")
    report_period: DateRangeFilter = Field(..., description="Report period")
    generated_at: datetime = Field(..., description="Report generation timestamp")
    
    # Summary metrics
    summary: PerformanceMetrics = Field(..., description="Summary performance metrics")
    
    # Detailed breakdown
    complaint_performance: ComplaintPerformance = Field(
        ...,
        description="Complaint handling performance",
    )
    attendance_performance: AttendancePerformance = Field(
        ...,
        description="Attendance management performance",
    )
    maintenance_performance: MaintenancePerformance = Field(
        ...,
        description="Maintenance management performance",
    )
    
    # Trends and comparisons
    performance_trends: List[PerformanceTrendPoint] = Field(
        default_factory=list,
        description="Performance trends over time",
    )
    comparison_with_peers: Union[PeerComparison, None] = Field(
        default=None,
        description="Comparison with peer supervisors",
    )
    comparison_with_previous_period: Union[PeriodComparison, None] = Field(
        default=None,
        description="Comparison with previous period",
    )
    
    # Insights and recommendations
    strengths: List[str] = Field(
        default_factory=list,
        description="Identified strengths",
    )
    areas_for_improvement: List[str] = Field(
        default_factory=list,
        description="Areas needing improvement",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Specific recommendations",
    )
    
    # Goals and targets
    current_goals: List[PerformanceGoalProgress] = Field(  # NOW THIS WORKS!
        default_factory=list,
        description="Current performance goals progress",
    )

    @computed_field
    @property
    def report_summary(self) -> str:
        """Generate executive summary of the report."""
        score = float(self.summary.overall_performance_score)
        grade = self.summary.performance_grade
        
        summary = f"Overall Performance: {score:.1f}/100 (Grade: {grade}). "
        
        if self.comparison_with_previous_period:
            trend = self.comparison_with_previous_period.overall_trend
            summary += f"Trend: {trend}. "
        
        if self.comparison_with_peers:
            tier = self.comparison_with_peers.performance_tier
            summary += f"Peer Ranking: {tier}."
        
        return summary


class PerformanceReview(BaseCreateSchema):
    """Performance review by admin."""
    
    supervisor_id: str = Field(..., description="Supervisor being reviewed")
    review_period: DateRangeFilter = Field(..., description="Review period")
    
    # Ratings (1-5 scale)
    complaint_handling_rating: Decimal = Field(
        ...,
        ge=1,
        le=5,
        description="Complaint handling rating",
    )
    attendance_management_rating: Decimal = Field(
        ...,
        ge=1,
        le=5,
        description="Attendance management rating",
    )
    maintenance_management_rating: Decimal = Field(
        ...,
        ge=1,
        le=5,
        description="Maintenance management rating",
    )
    communication_rating: Decimal = Field(
        ...,
        ge=1,
        le=5,
        description="Communication skills rating",
    )
    professionalism_rating: Decimal = Field(
        ...,
        ge=1,
        le=5,
        description="Professionalism rating",
    )
    reliability_rating: Decimal = Field(
        ...,
        ge=1,
        le=5,
        description="Reliability rating",
    )
    initiative_rating: Decimal = Field(
        ...,
        ge=1,
        le=5,
        description="Initiative and proactiveness rating",
    )
    
    # Overall rating
    overall_rating: Decimal = Field(
        ...,
        ge=1,
        le=5,
        description="Overall performance rating",
    )
    
    # Textual feedback
    strengths: str = Field(
        ...,
        min_length=20,
        max_length=1000,
        description="Supervisor strengths",
    )
    areas_for_improvement: str = Field(
        ...,
        min_length=20,
        max_length=1000,
        description="Areas to improve",
    )
    goals_for_next_period: str = Field(
        ...,
        min_length=20,
        max_length=1000,
        description="Goals for next review period",
    )
    
    # Additional feedback
    admin_comments: Union[str, None] = Field(
        default=None,
        max_length=2000,
        description="Additional admin comments",
    )
    
    # Action items
    action_items: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Specific action items (max 10)",
    )
    
    # Development recommendations
    training_recommendations: List[str] = Field(
        default_factory=list,
        description="Recommended training or development",
    )

    @field_validator("action_items", "training_recommendations")
    @classmethod
    def validate_non_empty_items(cls, v: List[str]) -> List[str]:
        """Remove empty items from lists."""
        return [item.strip() for item in v if item.strip()]

    @computed_field
    @property
    def average_rating(self) -> Decimal:
        """Calculate average of all individual ratings."""
        ratings = [
            self.complaint_handling_rating,
            self.attendance_management_rating,
            self.maintenance_management_rating,
            self.communication_rating,
            self.professionalism_rating,
            self.reliability_rating,
            self.initiative_rating,
        ]
        
        average = sum(float(r) for r in ratings) / len(ratings)
        return Decimal(str(average)).quantize(Decimal("0.1"))


class PerformanceReviewResponse(BaseSchema):
    """Performance review response with acknowledgment."""
    
    review_id: str = Field(..., description="Review ID")
    supervisor_id: str = Field(..., description="Supervisor ID")
    supervisor_name: str = Field(..., description="Supervisor name")
    reviewed_by: str = Field(..., description="Reviewer ID")
    reviewed_by_name: str = Field(..., description="Reviewer name")
    review_date: Date = Field(..., description="Review Date")
    
    review_period: DateRangeFilter = Field(..., description="Review period")
    
    # Ratings
    ratings: Dict[str, Decimal] = Field(
        ...,
        description="All ratings by category",
    )
    overall_rating: Decimal = Field(..., description="Overall rating")
    
    # Feedback
    strengths: str = Field(..., description="Identified strengths")
    areas_for_improvement: str = Field(..., description="Areas for improvement")
    goals_for_next_period: str = Field(..., description="Next period goals")
    admin_comments: Union[str, None] = Field(default=None, description="Admin comments")
    
    # Actions and development
    action_items: List[str] = Field(default_factory=list, description="Action items")
    training_recommendations: List[str] = Field(
        default_factory=list,
        description="Training recommendations",
    )
    
    # Supervisor acknowledgment
    acknowledged: bool = Field(default=False, description="Supervisor acknowledged review")
    acknowledged_at: Union[datetime, None] = Field(
        default=None,
        description="Acknowledgment timestamp",
    )
    supervisor_comments: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Supervisor's response comments",
    )

    @computed_field
    @property
    def performance_level(self) -> str:
        """Categorize performance level based on overall rating."""
        rating = float(self.overall_rating)
        
        if rating >= 4.5:
            return "Outstanding"
        elif rating >= 4.0:
            return "Exceeds Expectations"
        elif rating >= 3.0:
            return "Meets Expectations"
        elif rating >= 2.0:
            return "Below Expectations"
        else:
            return "Unsatisfactory"


class PerformanceInsights(BaseSchema):
    """AI-generated performance insights and recommendations."""
    
    supervisor_id: str = Field(..., description="Supervisor ID")
    analysis_period: DateRangeFilter = Field(..., description="Analysis period")
    generated_at: datetime = Field(..., description="Insights generation timestamp")
    
    # Key insights
    top_strengths: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Top 5 identified strengths",
    )
    improvement_opportunities: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Top 5 improvement opportunities",
    )
    
    # Trend analysis
    performance_trends: Dict[str, str] = Field(
        default_factory=dict,
        description="Trend analysis for each metric",
    )
    
    # Predictive insights
    risk_factors: List[str] = Field(
        default_factory=list,
        description="Identified risk factors",
    )
    success_indicators: List[str] = Field(
        default_factory=list,
        description="Positive success indicators",
    )
    
    # Recommendations
    immediate_actions: List[str] = Field(
        default_factory=list,
        max_length=3,
        description="Immediate actions recommended",
    )
    long_term_development: List[str] = Field(
        default_factory=list,
        max_length=3,
        description="Long-term development recommendations",
    )
    
    # Benchmarking insights
    peer_comparison_insights: List[str] = Field(
        default_factory=list,
        description="Insights from peer comparison",
    )
    
    # Confidence scores
    insight_confidence: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Confidence level in insights (0-100)",
    )

    @computed_field
    @property
    def overall_assessment(self) -> str:
        """Generate overall performance assessment."""
        strengths_count = len(self.top_strengths)
        improvements_count = len(self.improvement_opportunities)
        risks_count = len(self.risk_factors)
        
        if strengths_count > improvements_count and risks_count == 0:
            return "Strong performer with consistent results"
        elif improvements_count > strengths_count:
            return "Developing performer with growth potential"
        elif risks_count > 0:
            return "Requires attention and support"
        else:
            return "Balanced performer with mixed results"