"""
Complaint analytics schemas with enhanced metrics and validation.

Provides comprehensive analytics for complaint management including:
- Service level metrics (SLA compliance, resolution time)
- Trend analysis and forecasting
- Category and priority breakdowns
- Performance benchmarking
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Dict, List, Union, Annotated

from pydantic import BaseModel, Field, field_validator, computed_field
from uuid import UUID

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import ComplaintStatus, ComplaintCategory, Priority
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "ComplaintKPI",
    "ComplaintTrendPoint",
    "ComplaintTrend",
    "CategoryBreakdown",
    "PriorityBreakdown",
    "ComplaintDashboard",
    "SLAMetrics",
]


# Type aliases for Decimal fields
DecimalPercentage = Annotated[Decimal, Field(ge=0, le=100)]
DecimalNonNegative = Annotated[Decimal, Field(ge=0)]


class SLAMetrics(BaseSchema):
    """
    Service Level Agreement metrics for complaint handling.
    
    Tracks compliance with defined service level targets
    and identifies areas needing improvement.
    """
    
    total_with_sla: int = Field(
        ...,
        ge=0,
        description="Total complaints with defined SLA"
    )
    met_sla: int = Field(
        ...,
        ge=0,
        description="Complaints resolved within SLA"
    )
    breached_sla: int = Field(
        ...,
        ge=0,
        description="Complaints that breached SLA"
    )
    sla_compliance_rate: DecimalPercentage = Field(
        ...,
        description="Percentage of complaints meeting SLA"
    )
    average_sla_buffer_hours: Decimal = Field(
        ...,
        description="Average time buffer (positive) or breach (negative) in hours"
    )
    
    @field_validator("met_sla", "breached_sla")
    @classmethod
    def validate_sla_counts(cls, v: int, info) -> int:
        """Validate SLA counts don't exceed total."""
        if "total_with_sla" in info.data and v > info.data["total_with_sla"]:
            raise ValueError(f"{info.field_name} cannot exceed total_with_sla")
        return v
    
    @field_validator("sla_compliance_rate")
    @classmethod
    def round_percentage(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @field_validator("average_sla_buffer_hours")
    @classmethod
    def round_hours(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def at_risk_count(self) -> int:
        """Complaints currently at risk of SLA breach (estimated as 20% of total)."""
        return max(0, int(self.total_with_sla * 0.2))


class ComplaintKPI(BaseSchema):
    """
    Key Performance Indicators for complaint management.
    
    Provides comprehensive metrics on complaint volumes, resolution efficiency,
    and service quality for a specific hostel or platform-wide.
    """
    
    hostel_id: Union[UUID, None] = Field(
        None,
        description="Hostel identifier. None indicates platform-wide metrics"
    )
    hostel_name: Union[str, None] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Hostel name for display"
    )
    
    # Volume metrics
    total_complaints: int = Field(
        ...,
        ge=0,
        description="Total complaints in the period"
    )
    open_complaints: int = Field(
        ...,
        ge=0,
        description="Currently open complaints"
    )
    in_progress_complaints: int = Field(
        0,
        ge=0,
        description="Complaints currently being worked on"
    )
    resolved_complaints: int = Field(
        ...,
        ge=0,
        description="Resolved complaints in the period"
    )
    closed_complaints: int = Field(
        ...,
        ge=0,
        description="Closed complaints in the period"
    )
    
    # Performance metrics
    average_resolution_time_hours: DecimalNonNegative = Field(
        ...,
        description="Average time to resolve complaints in hours"
    )
    median_resolution_time_hours: DecimalNonNegative = Field(
        0,
        description="Median resolution time in hours"
    )
    sla_compliance_rate: DecimalPercentage = Field(
        ...,
        description="Percentage of complaints resolved within SLA"
    )
    escalation_rate: DecimalPercentage = Field(
        ...,
        description="Percentage of complaints escalated"
    )
    reopen_rate: DecimalPercentage = Field(
        ...,
        description="Percentage of resolved complaints that were reopened"
    )
    
    # First response time
    average_first_response_time_hours: DecimalNonNegative = Field(
        0,
        description="Average time to first response in hours"
    )
    
    # Customer satisfaction
    average_satisfaction_score: Union[Annotated[Decimal, Field(ge=0, le=5)], None] = Field(
        None,
        description="Average customer satisfaction score (1-5 scale)"
    )
    
    @field_validator(
        "open_complaints",
        "in_progress_complaints",
        "resolved_complaints",
        "closed_complaints"
    )
    @classmethod
    def validate_complaint_counts(cls, v: int, info) -> int:
        """Validate individual counts are reasonable."""
        if "total_complaints" in info.data:
            total = info.data["total_complaints"]
            if v > total and info.field_name != "open_complaints":
                # open_complaints can exceed total as it includes historical
                raise ValueError(
                    f"{info.field_name} ({v}) should not exceed total_complaints ({total})"
                )
        return v
    
    @field_validator(
        "average_resolution_time_hours",
        "median_resolution_time_hours",
        "average_first_response_time_hours"
    )
    @classmethod
    def round_hours(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @field_validator("sla_compliance_rate", "escalation_rate", "reopen_rate")
    @classmethod
    def round_percentage(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @field_validator("average_satisfaction_score")
    @classmethod
    def round_satisfaction(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Round to 2 decimal places."""
        return round(v, 2) if v is not None else None
    
    @computed_field  # type: ignore[misc]
    @property
    def resolution_rate(self) -> Decimal:
        """Calculate percentage of total complaints that have been resolved."""
        if self.total_complaints == 0:
            return Decimal("0.00")
        return round(
            (Decimal(self.resolved_complaints) / Decimal(self.total_complaints)) * 100,
            2
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def backlog(self) -> int:
        """Calculate current complaint backlog."""
        return self.open_complaints + self.in_progress_complaints
    
    @computed_field  # type: ignore[misc]
    @property
    def efficiency_score(self) -> Decimal:
        """
        Calculate overall efficiency score (0-100).
        
        Combines resolution rate, SLA compliance, and low reopen rate.
        """
        weights = {
            "resolution": 0.4,
            "sla": 0.4,
            "reopen": 0.2
        }
        
        resolution_score = self.resolution_rate
        sla_score = self.sla_compliance_rate
        reopen_score = 100 - self.reopen_rate  # Lower is better
        
        score = (
            resolution_score * Decimal(str(weights["resolution"])) +
            sla_score * Decimal(str(weights["sla"])) +
            reopen_score * Decimal(str(weights["reopen"]))
        )
        
        return round(score, 2)


class ComplaintTrendPoint(BaseSchema):
    """
    Single data point in complaint trend analysis.
    
    Represents complaint metrics for a specific date,
    enabling time-series visualization.
    """
    
    trend_date: Date = Field(
        ...,
        description="Date of the data point"
    )
    total_complaints: int = Field(
        ...,
        ge=0,
        description="Total complaints on this date"
    )
    open_complaints: int = Field(
        ...,
        ge=0,
        description="Open complaints on this date"
    )
    resolved_complaints: int = Field(
        ...,
        ge=0,
        description="Resolved complaints on this date"
    )
    escalated: int = Field(
        ...,
        ge=0,
        description="Escalated complaints on this date"
    )
    sla_breached: int = Field(
        ...,
        ge=0,
        description="SLA breaches on this date"
    )
    
    @field_validator("escalated", "sla_breached")
    @classmethod
    def validate_subset_counts(cls, v: int, info) -> int:
        """Validate that subset counts don't exceed total."""
        if "total_complaints" in info.data and v > info.data["total_complaints"]:
            raise ValueError(
                f"{info.field_name} ({v}) cannot exceed total_complaints"
            )
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def resolution_rate(self) -> Decimal:
        """Calculate resolution rate for this date."""
        if self.total_complaints == 0:
            return Decimal("0.00")
        return round(
            (Decimal(self.resolved_complaints) / Decimal(self.total_complaints)) * 100,
            2
        )


class ComplaintTrend(BaseSchema):
    """
    Time-series trend analysis for complaints.
    
    Provides historical data points and trend indicators
    for complaint volume and resolution patterns.
    """
    
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period"
    )
    points: List[ComplaintTrendPoint] = Field(
        default_factory=list,
        description="Chronological data points"
    )
    
    @field_validator("points")
    @classmethod
    def validate_chronological_order(
        cls,
        v: List[ComplaintTrendPoint]
    ) -> List[ComplaintTrendPoint]:
        """Ensure trend points are in chronological order."""
        if len(v) > 1:
            dates = [point.trend_date for point in v]
            if dates != sorted(dates):
                raise ValueError("Trend points must be in chronological order")
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def trend_direction(self) -> str:
        """
        Determine overall trend direction.
        
        Returns:
            'increasing', 'decreasing', or 'stable'
        """
        if len(self.points) < 2:
            return "stable"
        
        first_half = self.points[:len(self.points)//2]
        second_half = self.points[len(self.points)//2:]
        
        first_avg = sum(p.total_complaints for p in first_half) / len(first_half)
        second_avg = sum(p.total_complaints for p in second_half) / len(second_half)
        
        change_percent = ((second_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
        
        if change_percent > 10:
            return "increasing"
        elif change_percent < -10:
            return "decreasing"
        return "stable"
    
    @computed_field  # type: ignore[misc]
    @property
    def peak_complaint_date(self) -> Union[Date, None]:
        """Identify date with highest complaint volume."""
        if not self.points:
            return None
        return max(self.points, key=lambda x: x.total_complaints).trend_date


class CategoryBreakdown(BaseSchema):
    """
    Complaint breakdown by category.
    
    Provides insights into complaint distribution and
    resolution efficiency by category.
    """
    
    category: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Complaint category"
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of complaints in this category"
    )
    percentage_of_total: DecimalPercentage = Field(
        ...,
        description="Percentage of total complaints"
    )
    average_resolution_time_hours: DecimalNonNegative = Field(
        ...,
        description="Average resolution time for this category in hours"
    )
    resolved_count: int = Field(
        0,
        ge=0,
        description="Number of resolved complaints in this category"
    )
    open_count: int = Field(
        0,
        ge=0,
        description="Number of open complaints in this category"
    )
    
    @field_validator("resolved_count", "open_count")
    @classmethod
    def validate_status_counts(cls, v: int, info) -> int:
        """Validate status counts don't exceed category total."""
        if "count" in info.data and v > info.data["count"]:
            raise ValueError(f"{info.field_name} cannot exceed count")
        return v
    
    @field_validator("percentage_of_total")
    @classmethod
    def round_percentage(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @field_validator("average_resolution_time_hours")
    @classmethod
    def round_hours(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def resolution_rate(self) -> Decimal:
        """Calculate resolution rate for this category."""
        if self.count == 0:
            return Decimal("0.00")
        return round(
            (Decimal(self.resolved_count) / Decimal(self.count)) * 100,
            2
        )


class PriorityBreakdown(BaseSchema):
    """
    Complaint breakdown by priority level.
    
    Helps identify resource allocation needs based on
    complaint urgency distribution.
    """
    
    priority: Priority = Field(
        ...,
        description="Priority level"
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of complaints at this priority"
    )
    percentage_of_total: DecimalPercentage = Field(
        ...,
        description="Percentage of total complaints"
    )
    average_resolution_time_hours: DecimalNonNegative = Field(
        ...,
        description="Average resolution time for this priority"
    )
    sla_compliance_rate: DecimalPercentage = Field(
        ...,
        description="SLA compliance rate for this priority level"
    )
    
    @field_validator("percentage_of_total", "sla_compliance_rate")
    @classmethod
    def round_percentage(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @field_validator("average_resolution_time_hours")
    @classmethod
    def round_hours(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def priority_score(self) -> int:
        """Get numeric priority score for sorting (higher = more urgent)."""
        priority_scores = {
            Priority.LOW: 1,
            Priority.MEDIUM: 2,
            Priority.HIGH: 3,
            Priority.URGENT: 4,
            Priority.CRITICAL: 5,
        }
        return priority_scores.get(self.priority, 0)


class ComplaintDashboard(BaseSchema):
    """
    Comprehensive complaint dashboard analytics.
    
    Consolidates all complaint metrics, trends, and breakdowns
    into a single actionable dashboard view.
    """
    
    hostel_id: Union[UUID, None] = Field(
        None,
        description="Hostel identifier. None for platform-wide analytics"
    )
    hostel_name: Union[str, None] = Field(
        None,
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
    
    # Core metrics
    kpi: ComplaintKPI = Field(
        ...,
        description="Key performance indicators"
    )
    sla_metrics: SLAMetrics = Field(
        ...,
        description="Service level agreement metrics"
    )
    trend: ComplaintTrend = Field(
        ...,
        description="Time-series trend analysis"
    )
    
    # Breakdowns
    by_category: List[CategoryBreakdown] = Field(
        default_factory=list,
        description="Breakdown by complaint category"
    )
    by_priority: List[PriorityBreakdown] = Field(
        default_factory=list,
        description="Breakdown by priority level"
    )
    
    # Legacy support
    by_priority_dict: Dict[str, int] = Field(
        default_factory=dict,
        description="Priority counts as dict (deprecated: use by_priority)"
    )
    
    @field_validator("by_category")
    @classmethod
    def validate_category_percentages(
        cls,
        v: List[CategoryBreakdown]
    ) -> List[CategoryBreakdown]:
        """Validate that category percentages sum to ~100%."""
        if v:
            total_percentage = sum(cat.percentage_of_total for cat in v)
            # Allow 1% tolerance for rounding
            if not (99 <= total_percentage <= 101):
                raise ValueError(
                    f"Category percentages should sum to 100%, got {total_percentage}%"
                )
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def most_common_category(self) -> Union[str, None]:
        """Identify the most common complaint category."""
        if not self.by_category:
            return None
        return max(self.by_category, key=lambda x: x.count).category
    
    @computed_field  # type: ignore[misc]
    @property
    def slowest_category(self) -> Union[str, None]:
        """Identify category with slowest average resolution time."""
        if not self.by_category:
            return None
        return max(
            self.by_category,
            key=lambda x: x.average_resolution_time_hours
        ).category
    
    @computed_field  # type: ignore[misc]
    @property
    def high_priority_percentage(self) -> Decimal:
        """Calculate percentage of high/urgent/critical priority complaints."""
        if not self.by_priority:
            return Decimal("0.00")
        
        high_priorities = [
            Priority.HIGH,
            Priority.URGENT,
            Priority.CRITICAL
        ]
        high_count = sum(
            p.count for p in self.by_priority
            if p.priority in high_priorities
        )
        total = sum(p.count for p in self.by_priority)
        
        if total == 0:
            return Decimal("0.00")
        
        return round((Decimal(high_count) / Decimal(total)) * 100, 2)
    
    def get_actionable_insights(self) -> List[str]:
        """
        Generate actionable insights based on analytics.
        
        Returns:
            List of insight strings highlighting areas needing attention.
        """
        insights = []
        
        # SLA compliance check
        if self.sla_metrics.sla_compliance_rate < 80:
            insights.append(
                f"SLA compliance at {self.sla_metrics.sla_compliance_rate}% "
                "- consider resource allocation"
            )
        
        # Backlog check
        if self.kpi.backlog > 50:
            insights.append(
                f"High backlog of {self.kpi.backlog} complaints - "
                "prioritize resolution efforts"
            )
        
        # Reopen rate check
        if self.kpi.reopen_rate > 15:
            insights.append(
                f"High reopen rate of {self.kpi.reopen_rate}% - "
                "review resolution quality"
            )
        
        # Trend check
        if self.trend.trend_direction == "increasing":
            insights.append(
                "Complaint volume trending upward - "
                "investigate root causes"
            )
        
        # Category focus
        if self.most_common_category:
            insights.append(
                f"Most complaints in '{self.most_common_category}' category - "
                "consider preventive measures"
            )
        
        return insights