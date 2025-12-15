# --- File: app/schemas/maintenance/maintenance_analytics.py ---
"""
Maintenance analytics schemas for insights and reporting.

Provides comprehensive analytics with trends, performance metrics,
and vendor analysis for data-driven decision making.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Annotated, Dict, List, Optional

from pydantic import ConfigDict, Field, computed_field
from uuid import UUID

from app.schemas.common.base import BaseSchema
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "MaintenanceAnalytics",
    "TrendPoint",
    "CostTrendPoint",
    "CategoryBreakdown",
    "VendorPerformance",
    "PerformanceMetrics",
    "ProductivityMetrics",
]


class TrendPoint(BaseSchema):
    """
    Single data point in trend analysis.
    
    Represents metrics for a specific time period.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "period": "2024-01",
                "period_start": "2024-01-01",
                "period_end": "2024-01-31",
                "request_count": 45,
                "completed_count": 38,
                "pending_count": 7,
                "average_completion_days": "3.5"
            }
        }
    )

    period: str = Field(
        ...,
        description="Period identifier (Date, week, month, etc.)",
    )
    period_start: Date = Field(
        ...,
        description="Period start Date",
    )
    period_end: Date = Field(
        ...,
        description="Period end Date",
    )
    request_count: int = Field(
        ...,
        ge=0,
        description="Total requests in period",
    )
    completed_count: int = Field(
        ...,
        ge=0,
        description="Completed requests",
    )
    pending_count: int = Field(
        default=0,
        ge=0,
        description="Pending requests",
    )
    average_completion_days: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Average days to complete",
    )

    @computed_field  # type: ignore[misc]
    @property
    def completion_rate(self) -> Decimal:
        """Calculate completion rate for period."""
        if self.request_count == 0:
            return Decimal("0.00")
        return round(
            Decimal(self.completed_count) / Decimal(self.request_count) * 100,
            2,
        )


class CostTrendPoint(BaseSchema):
    """
    Cost trend data point.
    
    Tracks cost metrics over time periods.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "period": "2024-01",
                "period_start": "2024-01-01",
                "period_end": "2024-01-31",
                "total_cost": "125000.00",
                "request_count": 45,
                "average_cost": "2777.78",
                "budget_allocated": "150000.00",
                "variance_from_budget": "-25000.00"
            }
        }
    )

    period: str = Field(
        ...,
        description="Period identifier",
    )
    period_start: Date = Field(
        ...,
        description="Period start Date",
    )
    period_end: Date = Field(
        ...,
        description="Period end Date",
    )
    total_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total cost in period",
    )
    request_count: int = Field(
        ...,
        ge=0,
        description="Number of requests",
    )
    average_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average cost per request",
    )
    budget_allocated: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Budget allocated for period",
    )
    variance_from_budget: Optional[Annotated[Decimal, Field(decimal_places=2)]] = Field(
        None,
        description="Variance from budget",
    )

    @computed_field  # type: ignore[misc]
    @property
    def budget_utilization(self) -> Optional[Decimal]:
        """Calculate budget utilization percentage."""
        if self.budget_allocated is None or self.budget_allocated == 0:
            return None
        return round(
            self.total_cost / self.budget_allocated * 100,
            2,
        )


class CategoryBreakdown(BaseSchema):
    """
    Detailed breakdown by maintenance category.
    
    Provides comprehensive metrics for a specific category.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "category": "Electrical",
                "category_code": "ELEC",
                "total_requests": 150,
                "completed_requests": 142,
                "pending_requests": 8,
                "cancelled_requests": 0,
                "total_cost": "450000.00",
                "average_cost": "3000.00"
            }
        }
    )

    category: str = Field(
        ...,
        description="Maintenance category name",
    )
    category_code: Optional[str] = Field(
        None,
        description="Category code",
    )
    total_requests: int = Field(
        ...,
        ge=0,
        description="Total requests in category",
    )
    completed_requests: int = Field(
        ...,
        ge=0,
        description="Completed requests",
    )
    pending_requests: int = Field(
        default=0,
        ge=0,
        description="Pending requests",
    )
    cancelled_requests: int = Field(
        default=0,
        ge=0,
        description="Cancelled requests",
    )
    total_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total cost for category",
    )
    average_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average cost per request",
    )
    median_cost: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Median cost",
    )
    average_completion_time_hours: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average completion time in hours",
    )
    average_completion_time_days: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average completion time in days",
    )
    on_time_completion_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Percentage completed on time",
    )
    
    # Priority distribution
    high_priority_count: int = Field(
        default=0,
        ge=0,
        description="High priority requests",
    )
    urgent_priority_count: int = Field(
        default=0,
        ge=0,
        description="Urgent priority requests",
    )
    
    # Quality metrics
    quality_check_pass_rate: Optional[Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)]] = Field(
        None,
        description="Quality check pass rate",
    )
    average_quality_rating: Optional[Annotated[Decimal, Field(ge=0, le=5, decimal_places=2)]] = Field(
        None,
        description="Average quality rating",
    )

    @computed_field  # type: ignore[misc]
    @property
    def completion_rate(self) -> Decimal:
        """Calculate completion rate."""
        if self.total_requests == 0:
            return Decimal("0.00")
        return round(
            Decimal(self.completed_requests) / Decimal(self.total_requests) * 100,
            2,
        )

    @computed_field  # type: ignore[misc]
    @property
    def cost_per_completed(self) -> Decimal:
        """Calculate cost per completed request."""
        if self.completed_requests == 0:
            return Decimal("0.00")
        return round(
            self.total_cost / Decimal(self.completed_requests),
            2,
        )


class VendorPerformance(BaseSchema):
    """
    Vendor performance metrics and analysis.
    
    Tracks vendor efficiency, cost, quality, and reliability.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vendor_name": "ABC Electricals",
                "total_jobs": 50,
                "completed_jobs": 48,
                "on_time_completion_rate": "92.50",
                "total_spent": "250000.00",
                "average_cost": "5000.00",
                "cost_competitiveness": "medium",
                "quality_rating": "4.2"
            }
        }
    )

    vendor_id: Optional[UUID] = Field(
        None,
        description="Vendor unique identifier",
    )
    vendor_name: str = Field(
        ...,
        description="Vendor company name",
    )
    vendor_category: Optional[str] = Field(
        None,
        description="Vendor specialization category",
    )
    
    # Job statistics
    total_jobs: int = Field(
        ...,
        ge=0,
        description="Total jobs assigned",
    )
    completed_jobs: int = Field(
        ...,
        ge=0,
        description="Jobs completed",
    )
    in_progress_jobs: int = Field(
        default=0,
        ge=0,
        description="Jobs currently in progress",
    )
    cancelled_jobs: int = Field(
        default=0,
        ge=0,
        description="Jobs cancelled",
    )
    
    # Timeliness metrics
    on_time_completion_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="Percentage completed on time",
    )
    average_delay_days: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Average delay in days (for delayed jobs)",
    )
    
    # Cost metrics
    total_spent: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total amount paid to vendor",
    )
    average_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average cost per job",
    )
    cost_competitiveness: str = Field(
        ...,
        pattern=r"^(low|medium|high)$",
        description="Cost competitiveness rating",
    )
    cost_variance_percentage: Optional[Annotated[Decimal, Field(decimal_places=2)]] = Field(
        None,
        description="Average cost variance from estimates",
    )
    
    # Quality metrics
    quality_rating: Optional[Annotated[Decimal, Field(ge=0, le=5, decimal_places=2)]] = Field(
        None,
        description="Average quality rating (1-5 stars)",
    )
    quality_check_pass_rate: Optional[Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)]] = Field(
        None,
        description="Quality check pass rate",
    )
    rework_rate: Optional[Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)]] = Field(
        None,
        description="Percentage requiring rework",
    )
    
    # Customer satisfaction
    customer_satisfaction_score: Optional[Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)]] = Field(
        None,
        description="Customer satisfaction score",
    )
    complaint_count: int = Field(
        default=0,
        ge=0,
        description="Number of complaints received",
    )
    
    # Reliability
    response_time_hours: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Average response time in hours",
    )
    availability_score: Optional[Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)]] = Field(
        None,
        description="Vendor availability score",
    )
    
    # Engagement period
    first_job_date: Optional[Date] = Field(
        None,
        description="Date of first job",
    )
    last_job_date: Optional[Date] = Field(
        None,
        description="Date of most recent job",
    )
    
    # Recommendations
    recommended: bool = Field(
        default=True,
        description="Whether vendor is recommended",
    )
    performance_tier: str = Field(
        ...,
        pattern=r"^(platinum|gold|silver|bronze|needs_improvement)$",
        description="Performance tier classification",
    )

    @computed_field  # type: ignore[misc]
    @property
    def completion_rate(self) -> Decimal:
        """Calculate job completion rate."""
        if self.total_jobs == 0:
            return Decimal("0.00")
        return round(
            Decimal(self.completed_jobs) / Decimal(self.total_jobs) * 100,
            2,
        )

    @computed_field  # type: ignore[misc]
    @property
    def overall_performance_score(self) -> Decimal:
        """
        Calculate overall performance score.
        
        Weighted average of completion rate, quality, and timeliness.
        """
        weights = {
            "completion": 0.3,
            "quality": 0.3,
            "timeliness": 0.4,
        }
        
        completion_score = float(self.completion_rate)
        quality_score = float(self.quality_rating or 3.0) * 20  # Convert 1-5 to 0-100
        timeliness_score = float(self.on_time_completion_rate)
        
        overall = (
            completion_score * weights["completion"]
            + quality_score * weights["quality"]
            + timeliness_score * weights["timeliness"]
        )
        
        return round(Decimal(str(overall)), 2)


class PerformanceMetrics(BaseSchema):
    """
    Overall maintenance performance metrics.
    
    Provides key performance indicators for maintenance operations.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_requests": 500,
                "completed_requests": 450,
                "completion_rate": "90.00",
                "average_completion_time_hours": "48.50",
                "on_time_completion_rate": "85.00",
                "total_cost": "1500000.00"
            }
        }
    )

    period: DateRangeFilter = Field(
        ...,
        description="Analysis period",
    )
    hostel_id: Optional[UUID] = Field(
        None,
        description="Hostel ID (if hostel-specific)",
    )
    
    # Request metrics
    total_requests: int = Field(
        ...,
        ge=0,
        description="Total maintenance requests",
    )
    completed_requests: int = Field(
        ...,
        ge=0,
        description="Completed requests",
    )
    pending_requests: int = Field(
        ...,
        ge=0,
        description="Pending requests",
    )
    cancelled_requests: int = Field(
        default=0,
        ge=0,
        description="Cancelled requests",
    )
    
    # Completion metrics
    completion_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="Overall completion rate",
    )
    average_completion_time_hours: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average time to complete (hours)",
    )
    average_completion_time_days: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average time to complete (days)",
    )
    median_completion_time_days: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Median completion time (days)",
    )
    on_time_completion_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="Percentage completed on time",
    )
    
    # Cost metrics
    total_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total maintenance cost",
    )
    average_cost_per_request: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average cost per request",
    )
    cost_variance_percentage: Annotated[Decimal, Field(decimal_places=2)] = Field(
        ...,
        description="Average cost variance from estimates",
    )
    within_budget_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="Percentage completed within budget",
    )
    
    # Quality metrics
    quality_check_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Percentage of requests quality checked",
    )
    quality_pass_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Quality check pass rate",
    )
    average_quality_rating: Optional[Annotated[Decimal, Field(ge=0, le=5, decimal_places=2)]] = Field(
        None,
        description="Average quality rating",
    )
    rework_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Percentage requiring rework",
    )
    
    # Response metrics
    average_response_time_hours: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Average time to assign/respond (hours)",
    )
    average_assignment_time_hours: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Average time to assign (hours)",
    )
    
    # Priority distribution
    critical_requests: int = Field(
        default=0,
        ge=0,
        description="Critical priority requests",
    )
    urgent_requests: int = Field(
        default=0,
        ge=0,
        description="Urgent priority requests",
    )
    high_requests: int = Field(
        default=0,
        ge=0,
        description="High priority requests",
    )

    @computed_field  # type: ignore[misc]
    @property
    def efficiency_score(self) -> Decimal:
        """
        Calculate overall efficiency score (0-100).
        
        Composite metric based on completion rate, timeliness, and quality.
        """
        weights = {
            "completion": 0.4,
            "timeliness": 0.3,
            "quality": 0.3,
        }
        
        completion_score = float(self.completion_rate)
        timeliness_score = float(self.on_time_completion_rate)
        quality_score = float(self.quality_pass_rate)
        
        efficiency = (
            completion_score * weights["completion"]
            + timeliness_score * weights["timeliness"]
            + quality_score * weights["quality"]
        )
        
        return round(Decimal(str(efficiency)), 2)


class ProductivityMetrics(BaseSchema):
    """
    Staff and team productivity metrics.
    
    Tracks productivity of maintenance teams and individuals.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_assignments": 100,
                "completed_assignments": 95,
                "average_jobs_per_day": "3.5",
                "average_hours_per_job": "4.25",
                "utilization_rate": "85.00",
                "on_time_rate": "92.00"
            }
        }
    )

    period: DateRangeFilter = Field(
        ...,
        description="Analysis period",
    )
    team_id: Optional[UUID] = Field(
        None,
        description="Team ID (if team-specific)",
    )
    staff_member_id: Optional[UUID] = Field(
        None,
        description="Staff member ID (if individual)",
    )
    
    # Workload metrics
    total_assignments: int = Field(
        ...,
        ge=0,
        description="Total assignments",
    )
    completed_assignments: int = Field(
        ...,
        ge=0,
        description="Completed assignments",
    )
    active_assignments: int = Field(
        default=0,
        ge=0,
        description="Currently active assignments",
    )
    
    # Productivity metrics
    average_jobs_per_day: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average jobs completed per day",
    )
    average_hours_per_job: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average hours spent per job",
    )
    utilization_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="Staff utilization rate",
    )
    
    # Quality and timeliness
    on_time_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="On-time completion rate",
    )
    quality_score: Optional[Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)]] = Field(
        None,
        description="Average quality score",
    )
    
    # Specialization
    top_categories: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Top maintenance categories handled",
    )
    specialization_score: Optional[Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)]] = Field(
        None,
        description="Specialization/expertise score",
    )

    @computed_field  # type: ignore[misc]
    @property
    def productivity_score(self) -> Decimal:
        """Calculate overall productivity score."""
        completion_rate = (
            Decimal(self.completed_assignments) / Decimal(self.total_assignments) * 100
            if self.total_assignments > 0
            else Decimal("0.00")
        )
        
        # Weighted average
        weights = {
            "completion": 0.4,
            "timeliness": 0.3,
            "quality": 0.3,
        }
        
        quality_component = float(self.quality_score or 70.0)
        
        score = (
            float(completion_rate) * weights["completion"]
            + float(self.on_time_rate) * weights["timeliness"]
            + quality_component * weights["quality"]
        )
        
        return round(Decimal(str(score)), 2)


class MaintenanceAnalytics(BaseSchema):
    """
    Comprehensive maintenance analytics dashboard.
    
    Aggregates all analytics components for complete insights.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hostel_name": "North Campus Hostel A",
                "total_requests": 500,
                "completed_requests": 450,
                "pending_requests": 50,
                "total_cost": "1500000.00",
                "average_cost": "3000.00",
                "completion_rate": "90.00",
                "on_time_rate": "85.00"
            }
        }
    )

    hostel_id: Optional[UUID] = Field(
        None,
        description="Hostel ID (None for system-wide)",
    )
    hostel_name: Optional[str] = Field(
        None,
        description="Hostel name",
    )
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period",
    )
    generated_at: datetime = Field(
        ...,
        description="Analytics generation timestamp",
    )
    
    # Summary metrics
    total_requests: int = Field(
        ...,
        ge=0,
        description="Total maintenance requests",
    )
    completed_requests: int = Field(
        ...,
        ge=0,
        description="Completed requests",
    )
    pending_requests: int = Field(
        ...,
        ge=0,
        description="Pending requests",
    )
    
    # Cost summary
    total_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total maintenance cost",
    )
    average_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average cost per request",
    )
    budget_utilization: Optional[Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)]] = Field(
        None,
        description="Budget utilization percentage",
    )
    
    # Performance summary
    average_completion_time_hours: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average completion time",
    )
    completion_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="Completion rate",
    )
    on_time_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="On-time completion rate",
    )
    
    # Breakdowns
    requests_by_category: Dict[str, int] = Field(
        ...,
        description="Request count by category",
    )
    cost_by_category: Dict[str, Decimal] = Field(
        ...,
        description="Cost breakdown by category",
    )
    requests_by_priority: Dict[str, int] = Field(
        default_factory=dict,
        description="Request count by priority",
    )
    
    # Trends
    request_trend: List[TrendPoint] = Field(
        ...,
        description="Request volume trends over time",
    )
    cost_trend: List[CostTrendPoint] = Field(
        ...,
        description="Cost trends over time",
    )
    
    # Detailed breakdowns
    category_breakdown: Optional[List[CategoryBreakdown]] = Field(
        None,
        description="Detailed category analysis",
    )
    vendor_performance: Optional[List[VendorPerformance]] = Field(
        None,
        description="Vendor performance metrics",
    )
    
    # Insights and recommendations
    top_cost_drivers: Optional[List[str]] = Field(
        None,
        max_length=5,
        description="Top cost drivers",
    )
    efficiency_opportunities: Optional[List[str]] = Field(
        None,
        max_length=10,
        description="Identified efficiency opportunities",
    )
    risk_areas: Optional[List[str]] = Field(
        None,
        max_length=10,
        description="Identified risk areas",
    )