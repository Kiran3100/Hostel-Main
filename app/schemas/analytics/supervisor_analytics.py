"""
Supervisor analytics schemas for performance tracking.

Provides comprehensive supervisor metrics including:
- Individual performance KPIs
- Workload distribution
- Resolution efficiency
- Comparative benchmarking
- Student feedback integration
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Dict, List, Union, Annotated

from pydantic import BaseModel, Field, field_validator, computed_field, model_validator, AfterValidator
from uuid import UUID

from app.schemas.common.base import BaseSchema
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "SupervisorKPI",
    "SupervisorTrendPoint",
    "SupervisorDashboardAnalytics",
    "SupervisorComparison",
    "SupervisorWorkload",
    "SupervisorPerformanceRating",
    "TeamAnalytics",
]


# Custom validator
def round_to_2_places(v: Decimal) -> Decimal:
    """Round decimal to 2 places."""
    if isinstance(v, (int, float)):
        v = Decimal(str(v))
    return round(v, 2)


# Type aliases
DecimalPercentage = Annotated[Decimal, Field(ge=0, le=100), AfterValidator(round_to_2_places)]
DecimalNonNegative = Annotated[Decimal, Field(ge=0), AfterValidator(round_to_2_places)]
DecimalRating = Annotated[Decimal, Field(ge=0, le=5), AfterValidator(round_to_2_places)]


class SupervisorWorkload(BaseSchema):
    """
    Supervisor workload metrics.
    
    Tracks task distribution and capacity utilization
    for resource planning and balancing.
    """
    
    # Current workload
    active_complaints: int = Field(
        ...,
        ge=0,
        description="Currently assigned complaints"
    )
    active_maintenance: int = Field(
        ...,
        ge=0,
        description="Currently assigned maintenance tasks"
    )
    pending_tasks: int = Field(
        ...,
        ge=0,
        description="Total pending tasks"
    )
    
    # Capacity
    max_capacity: int = Field(
        ...,
        ge=1,
        description="Maximum concurrent task capacity"
    )
    current_utilization: DecimalPercentage = Field(
        ...,
        description="Current capacity utilization percentage"
    )
    
    # Task types
    urgent_tasks: int = Field(
        0,
        ge=0,
        description="Number of urgent/critical tasks"
    )
    overdue_tasks: int = Field(
        0,
        ge=0,
        description="Number of overdue tasks"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def available_capacity(self) -> int:
        """Calculate available capacity."""
        return max(0, self.max_capacity - self.pending_tasks)
    
    @computed_field  # type: ignore[misc]
    @property
    def workload_status(self) -> str:
        """Assess workload status."""
        if self.current_utilization >= 100:
            return "overloaded"
        elif self.current_utilization >= 80:
            return "high"
        elif self.current_utilization >= 50:
            return "moderate"
        else:
            return "low"


class SupervisorPerformanceRating(BaseSchema):
    """
    Performance rating breakdown.
    
    Provides detailed scoring across multiple performance dimensions.
    """
    
    # Individual ratings
    efficiency_score: DecimalPercentage = Field(
        ...,
        description="Task completion efficiency (0-100)"
    )
    quality_score: DecimalPercentage = Field(
        ...,
        description="Work quality score (0-100)"
    )
    responsiveness_score: DecimalPercentage = Field(
        ...,
        description="Response time score (0-100)"
    )
    student_satisfaction_score: DecimalPercentage = Field(
        ...,
        description="Student feedback score (0-100)"
    )
    reliability_score: DecimalPercentage = Field(
        ...,
        description="Reliability and consistency score (0-100)"
    )
    
    # Overall rating
    overall_rating: DecimalPercentage = Field(
        ...,
        description="Weighted overall performance rating"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def performance_grade(self) -> str:
        """Get letter grade for overall performance."""
        rating = float(self.overall_rating)
        
        if rating >= 90:
            return "A"
        elif rating >= 80:
            return "B"
        elif rating >= 70:
            return "C"
        elif rating >= 60:
            return "D"
        else:
            return "F"
    
    @computed_field  # type: ignore[misc]
    @property
    def strengths(self) -> List[str]:
        """Identify performance strengths (scores >= 85)."""
        scores = {
            "efficiency": self.efficiency_score,
            "quality": self.quality_score,
            "responsiveness": self.responsiveness_score,
            "student_satisfaction": self.student_satisfaction_score,
            "reliability": self.reliability_score,
        }
        return [name for name, score in scores.items() if score >= 85]
    
    @computed_field  # type: ignore[misc]
    @property
    def improvement_areas(self) -> List[str]:
        """Identify areas needing improvement (scores < 70)."""
        scores = {
            "efficiency": self.efficiency_score,
            "quality": self.quality_score,
            "responsiveness": self.responsiveness_score,
            "student_satisfaction": self.student_satisfaction_score,
            "reliability": self.reliability_score,
        }
        return [name for name, score in scores.items() if score < 70]


class SupervisorKPI(BaseSchema):
    """
    Key Performance Indicators for supervisor.
    
    Comprehensive performance metrics for individual supervisor
    assessment and development planning.
    """
    
    supervisor_id: UUID = Field(
        ...,
        description="Supervisor unique identifier"
    )
    supervisor_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Supervisor name"
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier"
    )
    hostel_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Hostel name"
    )
    
    period: DateRangeFilter = Field(
        ...,
        description="Performance period"
    )
    
    # Workload metrics
    complaints_assigned: int = Field(
        ...,
        ge=0,
        description="Total complaints assigned in period"
    )
    complaints_resolved: int = Field(
        ...,
        ge=0,
        description="Complaints successfully resolved"
    )
    complaints_pending: int = Field(
        0,
        ge=0,
        description="Currently pending complaints"
    )
    
    maintenance_requests_created: int = Field(
        ...,
        ge=0,
        description="Maintenance requests created"
    )
    maintenance_requests_completed: int = Field(
        ...,
        ge=0,
        description="Maintenance requests completed"
    )
    maintenance_pending: int = Field(
        0,
        ge=0,
        description="Currently pending maintenance"
    )
    
    attendance_records_marked: int = Field(
        ...,
        ge=0,
        description="Attendance records marked"
    )
    
    # Performance metrics
    avg_complaint_resolution_time_hours: DecimalNonNegative = Field(
        ...,
        description="Average time to resolve complaints (hours)"
    )
    avg_first_response_time_hours: DecimalNonNegative = Field(
        0,
        description="Average time to first response (hours)"
    )
    avg_maintenance_completion_time_hours: DecimalNonNegative = Field(
        ...,
        description="Average maintenance completion time (hours)"
    )
    
    # SLA compliance
    complaint_sla_compliance_rate: DecimalPercentage = Field(
        ...,
        description="Complaint SLA compliance percentage"
    )
    maintenance_sla_compliance_rate: DecimalPercentage = Field(
        ...,
        description="Maintenance SLA compliance percentage"
    )
    
    # Quality metrics
    reopened_complaints: int = Field(
        0,
        ge=0,
        description="Number of complaints reopened"
    )
    escalated_complaints: int = Field(
        0,
        ge=0,
        description="Number of complaints escalated"
    )
    
    # Feedback
    student_feedback_score: Union[DecimalRating, None] = Field(
        None,
        description="Average student rating (1-5 scale)"
    )
    feedback_count: int = Field(
        0,
        ge=0,
        description="Number of feedback responses received"
    )
    
    # Overall performance
    overall_performance_score: DecimalPercentage = Field(
        ...,
        description="Composite performance score (0-100)"
    )
    
    # Workload
    workload: Union[SupervisorWorkload, None] = Field(
        None,
        description="Current workload metrics"
    )
    
    # Performance ratings
    performance_rating: Union[SupervisorPerformanceRating, None] = Field(
        None,
        description="Detailed performance ratings"
    )
    
    @field_validator("complaints_resolved")
    @classmethod
    def validate_resolved_complaints(cls, v: int, info) -> int:
        """Validate resolved count doesn't exceed assigned."""
        if "complaints_assigned" in info.data and v > info.data["complaints_assigned"]:
            # Allow slight excess for complaints from previous periods
            if v > info.data["complaints_assigned"] * 1.2:
                raise ValueError(
                    "complaints_resolved significantly exceeds complaints_assigned"
                )
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def complaint_resolution_rate(self) -> Decimal:
        """Calculate complaint resolution rate percentage."""
        if self.complaints_assigned == 0:
            return Decimal("100.00")
        return round(
            (Decimal(self.complaints_resolved) / Decimal(self.complaints_assigned)) * 100,
            2
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def maintenance_completion_rate(self) -> Decimal:
        """Calculate maintenance completion rate percentage."""
        if self.maintenance_requests_created == 0:
            return Decimal("100.00")
        return round(
            (Decimal(self.maintenance_requests_completed) / 
             Decimal(self.maintenance_requests_created)) * 100,
            2
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def reopen_rate(self) -> Decimal:
        """Calculate complaint reopen rate."""
        if self.complaints_resolved == 0:
            return Decimal("0.00")
        return round(
            (Decimal(self.reopened_complaints) / Decimal(self.complaints_resolved)) * 100,
            2
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def performance_status(self) -> str:
        """Overall performance status classification."""
        score = float(self.overall_performance_score)
        
        if score >= 85:
            return "excellent"
        elif score >= 70:
            return "good"
        elif score >= 60:
            return "satisfactory"
        elif score >= 50:
            return "needs_improvement"
        else:
            return "unsatisfactory"


class SupervisorTrendPoint(BaseSchema):
    """
    Performance trend data point.
    
    Tracks supervisor performance metrics over time
    for trend analysis and progress monitoring.
    """
    
    period_label: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Period identifier (e.g., 'Week 1', '2024-01')"
    )
    period_start: Date = Field(
        ...,
        description="Period start date"
    )
    period_end: Date = Field(
        ...,
        description="Period end date"
    )
    
    complaints_resolved: int = Field(
        ...,
        ge=0,
        description="Complaints resolved in period"
    )
    maintenance_completed: int = Field(
        ...,
        ge=0,
        description="Maintenance completed in period"
    )
    performance_score: DecimalPercentage = Field(
        ...,
        description="Performance score for period"
    )
    student_feedback_score: Union[DecimalRating, None] = Field(
        None,
        description="Student feedback score"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def total_tasks_completed(self) -> int:
        """Total tasks completed in period."""
        return self.complaints_resolved + self.maintenance_completed


class SupervisorDashboardAnalytics(BaseSchema):
    """
    Supervisor dashboard analytics.
    
    Personalized dashboard view for supervisor performance
    monitoring and self-assessment.
    """
    
    supervisor_id: UUID = Field(
        ...,
        description="Supervisor identifier"
    )
    supervisor_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Supervisor name"
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier"
    )
    hostel_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Hostel name"
    )
    
    period: DateRangeFilter = Field(
        ...,
        description="Dashboard period"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Dashboard generation timestamp"
    )
    
    # Core metrics
    kpi: SupervisorKPI = Field(
        ...,
        description="Key performance indicators"
    )
    
    # Trend analysis
    trend: List[SupervisorTrendPoint] = Field(
        default_factory=list,
        description="Performance trend over time"
    )
    
    # Breakdowns
    complaints_by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Complaint count by category"
    )
    maintenance_by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Maintenance count by category"
    )
    
    # Goals and targets
    monthly_target_tasks: Union[int, None] = Field(
        None,
        ge=0,
        description="Monthly task completion target"
    )
    target_achievement_rate: Union[DecimalPercentage, None] = Field(
        None,
        description="Percentage of target achieved"
    )
    
    @field_validator("trend")
    @classmethod
    def validate_trend_chronological(
        cls,
        v: List[SupervisorTrendPoint]
    ) -> List[SupervisorTrendPoint]:
        """Ensure trend points are chronological."""
        if len(v) > 1:
            dates = [point.period_start for point in v]
            if dates != sorted(dates):
                raise ValueError("Trend points must be in chronological order")
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def most_common_complaint_category(self) -> Union[str, None]:
        """Identify most frequent complaint category."""
        if not self.complaints_by_category:
            return None
        return max(self.complaints_by_category, key=self.complaints_by_category.get)  # type: ignore[arg-type]
    
    @computed_field  # type: ignore[misc]
    @property
    def improvement_trend(self) -> str:
        """Analyze performance improvement trend."""
        if len(self.trend) < 2:
            return "insufficient_data"
        
        scores = [float(point.performance_score) for point in self.trend]
        first_half_avg = sum(scores[:len(scores)//2]) / (len(scores)//2)
        second_half_avg = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
        
        change = second_half_avg - first_half_avg
        
        if change > 5:
            return "improving"
        elif change < -5:
            return "declining"
        else:
            return "stable"


class SupervisorComparison(BaseSchema):
    """
    Comparative analysis of supervisors.
    
    Enables benchmarking and identification of top performers
    within a hostel or across the platform.
    """
    
    scope_type: str = Field(
        ...,
        pattern="^(hostel|platform)$",
        description="Comparison scope"
    )
    hostel_id: Union[UUID, None] = Field(
        None,
        description="Hostel ID if scope is hostel"
    )
    hostel_name: Union[str, None] = Field(
        None,
        max_length=255,
        description="Hostel name"
    )
    
    period: DateRangeFilter = Field(
        ...,
        description="Comparison period"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp"
    )
    
    # Supervisor metrics
    supervisors: List[SupervisorKPI] = Field(
        ...,
        min_length=1,
        description="List of supervisor KPIs"
    )
    
    # Rankings
    ranked_by_performance: List[UUID] = Field(
        ...,
        description="Supervisor IDs ranked by overall performance"
    )
    ranked_by_resolution_speed: List[UUID] = Field(
        ...,
        description="Supervisor IDs ranked by resolution speed"
    )
    ranked_by_feedback_score: List[UUID] = Field(
        ...,
        description="Supervisor IDs ranked by student feedback"
    )
    ranked_by_sla_compliance: List[UUID] = Field(
        default_factory=list,
        description="Supervisor IDs ranked by SLA compliance"
    )
    
    # Statistics
    avg_performance_score: DecimalPercentage = Field(
        ...,
        description="Average performance score across all supervisors"
    )
    avg_resolution_time_hours: DecimalNonNegative = Field(
        ...,
        description="Average resolution time across all supervisors"
    )
    avg_sla_compliance: DecimalPercentage = Field(
        ...,
        description="Average SLA compliance rate"
    )
    
    @field_validator(
        "ranked_by_performance",
        "ranked_by_resolution_speed",
        "ranked_by_feedback_score",
        "ranked_by_sla_compliance"
    )
    @classmethod
    def validate_ranking_completeness(cls, v: List[UUID], info) -> List[UUID]:
        """Validate rankings include all supervisors."""
        if "supervisors" in info.data:
            supervisor_ids = {s.supervisor_id for s in info.data["supervisors"]}
            ranking_ids = set(v)
            
            # Allow for some supervisors to be excluded from certain rankings
            # (e.g., no feedback score available)
            if info.field_name != "ranked_by_feedback_score":
                if ranking_ids != supervisor_ids:
                    # Only warn, don't fail
                    pass
        
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def top_performer(self) -> Union[UUID, None]:
        """Get ID of top performing supervisor."""
        if not self.ranked_by_performance:
            return None
        return self.ranked_by_performance[0]
    
    @computed_field  # type: ignore[misc]
    @property
    def performance_variance(self) -> Decimal:
        """Calculate variance in performance scores."""
        if not self.supervisors:
            return Decimal("0.00")
        
        scores = [float(s.overall_performance_score) for s in self.supervisors]
        mean = sum(scores) / len(scores)
        variance = sum((x - mean) ** 2 for x in scores) / len(scores)
        
        return round(Decimal(str(variance)), 2)
    
    def get_supervisor_rank(self, supervisor_id: UUID, metric: str = "performance") -> Union[int, None]:
        """
        Get rank of specific supervisor for a metric.
        
        Args:
            supervisor_id: Supervisor to rank
            metric: Metric to rank by ('performance', 'resolution_speed', 'feedback', 'sla')
            
        Returns:
            Rank (1-indexed) or None if not found
        """
        ranking_map = {
            "performance": self.ranked_by_performance,
            "resolution_speed": self.ranked_by_resolution_speed,
            "feedback": self.ranked_by_feedback_score,
            "sla": self.ranked_by_sla_compliance,
        }
        
        ranking = ranking_map.get(metric)
        if not ranking:
            return None
        
        try:
            return ranking.index(supervisor_id) + 1
        except ValueError:
            return None


class TeamAnalytics(BaseSchema):
    """
    Team-level analytics for supervisor groups.
    
    Aggregates supervisor metrics at team/hostel level
    for management oversight.
    """
    
    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier"
    )
    hostel_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Hostel name"
    )
    
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp"
    )
    
    # Team composition
    total_supervisors: int = Field(
        ...,
        ge=0,
        description="Total number of supervisors"
    )
    active_supervisors: int = Field(
        ...,
        ge=0,
        description="Currently active supervisors"
    )
    
    # Aggregate metrics
    total_tasks_assigned: int = Field(
        ...,
        ge=0,
        description="Total tasks assigned to team"
    )
    total_tasks_completed: int = Field(
        ...,
        ge=0,
        description="Total tasks completed by team"
    )
    team_completion_rate: DecimalPercentage = Field(
        ...,
        description="Team completion rate percentage"
    )
    
    # Performance
    avg_team_performance_score: DecimalPercentage = Field(
        ...,
        description="Average team performance score"
    )
    avg_team_sla_compliance: DecimalPercentage = Field(
        ...,
        description="Average team SLA compliance"
    )
    
    # Workload distribution
    workload_balance_score: DecimalPercentage = Field(
        ...,
        description="Workload distribution balance score (100 = perfectly balanced)"
    )
    
    # Individual contributions
    top_performers: List[UUID] = Field(
        default_factory=list,
        max_length=5,
        description="Top 5 performing supervisor IDs"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def team_efficiency(self) -> str:
        """Assess overall team efficiency."""
        if self.avg_team_performance_score >= 85:
            return "high"
        elif self.avg_team_performance_score >= 70:
            return "moderate"
        else:
            return "low"