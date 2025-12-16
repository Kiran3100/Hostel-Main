"""
Complaint analytics and reporting schemas.

Provides comprehensive analytics, metrics, and insights
for complaint management performance.
"""

from datetime import date as Date
from decimal import Decimal
from typing import Annotated, Dict, List, Union

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.common.base import BaseSchema

__all__ = [
    "ComplaintAnalytics",
    "ResolutionMetrics",
    "CategoryAnalysis",
    "CategoryMetrics",
    "ComplaintTrendPoint",
    "StaffPerformance",
    "ComplaintHeatmap",
    "RoomComplaintCount",
]


class ResolutionMetrics(BaseSchema):
    """
    Detailed complaint resolution performance metrics.
    
    Tracks resolution efficiency and quality indicators.
    """
    model_config = ConfigDict(from_attributes=True)

    total_resolved: int = Field(..., ge=0, description="Total resolved count")

    # Time metrics (in hours)
    # Note: Pydantic v2 requires Decimal constraints in Annotated for optional fields
    average_resolution_time_hours: Annotated[
        Decimal,
        Field(ge=Decimal("0"), description="Average resolution time (hours)")
    ]
    median_resolution_time_hours: Annotated[
        Decimal,
        Field(ge=Decimal("0"), description="Median resolution time (hours)")
    ]
    fastest_resolution_hours: Annotated[
        Decimal,
        Field(ge=Decimal("0"), description="Fastest resolution time (hours)")
    ]
    slowest_resolution_hours: Annotated[
        Decimal,
        Field(ge=Decimal("0"), description="Slowest resolution time (hours)")
    ]

    # Performance rates
    resolution_rate: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            description="% of complaints resolved"
        )
    ]
    same_day_resolution_rate: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            description="% resolved within 24 hours"
        )
    ]

    # Escalation metrics
    escalation_rate: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            description="% of complaints escalated"
        )
    ]

    # Quality metrics
    reopen_rate: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            description="% of resolved complaints reopened"
        )
    ]


class CategoryMetrics(BaseSchema):
    """
    Metrics for a single complaint category.
    
    Provides detailed performance data per category.
    """
    model_config = ConfigDict(from_attributes=True)

    category: str = Field(..., description="Category name")
    total_complaints: int = Field(..., ge=0, description="Total complaints")
    open_complaints: int = Field(..., ge=0, description="Open complaints")
    resolved_complaints: int = Field(..., ge=0, description="Resolved complaints")

    average_resolution_time_hours: Annotated[
        Decimal,
        Field(ge=Decimal("0"), description="Average resolution time (hours)")
    ]
    resolution_rate: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            description="Resolution rate percentage"
        )
    ]

    percentage_of_total: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            description="% of total complaints"
        )
    ]


class CategoryAnalysis(BaseSchema):
    """
    Category-wise complaint analysis.
    
    Identifies problem areas and trends by category.
    """
    model_config = ConfigDict(from_attributes=True)

    categories: List[CategoryMetrics] = Field(
        default_factory=list,
        description="Metrics for each category",
    )

    most_common_category: str = Field(
        ...,
        description="Category with most complaints",
    )
    most_problematic_category: str = Field(
        ...,
        description="Category with longest avg resolution time",
    )


class ComplaintTrendPoint(BaseSchema):
    """
    Time-series data point for complaint trends.
    
    Represents complaint metrics for a specific period.
    """
    model_config = ConfigDict(from_attributes=True)

    period: str = Field(
        ...,
        description="Time period (Date, week, or month)",
        examples=["2024-01-15", "2024-W03", "2024-01"],
    )
    total_complaints: int = Field(..., ge=0, description="Total complaints")
    open_complaints: int = Field(..., ge=0, description="Open complaints")
    resolved_complaints: int = Field(..., ge=0, description="Resolved complaints")

    # Priority breakdown
    urgent_count: int = Field(..., ge=0, description="Urgent priority count")
    high_count: int = Field(..., ge=0, description="High priority count")
    medium_count: int = Field(..., ge=0, description="Medium priority count")
    low_count: int = Field(..., ge=0, description="Low priority count")


class StaffPerformance(BaseSchema):
    """
    Individual staff member complaint resolution performance.
    
    Tracks productivity and quality metrics per staff member.
    """
    model_config = ConfigDict(from_attributes=True)

    staff_id: str = Field(..., description="Staff member user ID")
    staff_name: str = Field(..., description="Staff member name")
    staff_role: str = Field(..., description="Staff member role")

    complaints_assigned: int = Field(
        ...,
        ge=0,
        description="Total complaints assigned",
    )
    complaints_resolved: int = Field(
        ...,
        ge=0,
        description="Total complaints resolved",
    )

    average_resolution_time_hours: Annotated[
        Decimal,
        Field(ge=Decimal("0"), description="Average resolution time (hours)")
    ]
    resolution_rate: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            description="Resolution rate percentage"
        )
    ]

    average_rating: Union[Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("5"),
            description="Average feedback rating (1-5)"
        )
    ], None] = None


class RoomComplaintCount(BaseSchema):
    """
    Complaint count and analysis for specific room.
    
    Helps identify problematic rooms.
    """
    model_config = ConfigDict(from_attributes=True)

    room_id: str = Field(..., description="Room identifier")
    room_number: str = Field(..., description="Room number")
    complaint_count: int = Field(..., ge=0, description="Total complaints")

    most_common_category: str = Field(
        ...,
        description="Most frequent complaint category",
    )


class ComplaintHeatmap(BaseSchema):
    """
    Complaint heatmap for pattern analysis.
    
    Identifies temporal and spatial complaint patterns.
    """
    model_config = ConfigDict(from_attributes=True)

    hostel_id: str = Field(..., description="Hostel identifier")

    # Temporal patterns
    complaints_by_hour: Dict[int, int] = Field(
        default_factory=dict,
        description="Complaint count by hour of day (0-23)",
    )
    complaints_by_day: Dict[str, int] = Field(
        default_factory=dict,
        description="Complaint count by day of week",
    )

    # Spatial patterns
    complaints_by_room: List[RoomComplaintCount] = Field(
        default_factory=list,
        description="Complaint count by room",
    )
    complaints_by_floor: Dict[int, int] = Field(
        default_factory=dict,
        description="Complaint count by floor number",
    )

    @field_validator("complaints_by_hour")
    @classmethod
    def validate_hour_keys(cls, v: Dict[int, int]) -> Dict[int, int]:
        """Validate hour keys are in valid range (0-23)."""
        for hour in v.keys():
            if not 0 <= hour <= 23:
                raise ValueError(f"Invalid hour: {hour}. Must be 0-23")
        return v


class ComplaintAnalytics(BaseSchema):
    """
    Comprehensive complaint analytics dashboard.
    
    Provides holistic view of complaint management performance.
    """
    model_config = ConfigDict(from_attributes=True)

    hostel_id: Union[str, None] = Field(
        default=None,
        description="Hostel ID (None for system-wide analytics)",
    )
    period_start: Date = Field(..., description="Analytics period start")
    period_end: Date = Field(..., description="Analytics period end")

    # Summary counts
    total_complaints: int = Field(..., ge=0, description="Total complaints")
    open_complaints: int = Field(..., ge=0, description="Open complaints")
    resolved_complaints: int = Field(..., ge=0, description="Resolved complaints")
    closed_complaints: int = Field(..., ge=0, description="Closed complaints")

    # Detailed metrics
    resolution_metrics: ResolutionMetrics = Field(
        ...,
        description="Resolution performance metrics",
    )

    category_analysis: CategoryAnalysis = Field(
        ...,
        description="Category-wise breakdown",
    )

    priority_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution by priority level",
    )

    complaint_trend: List[ComplaintTrendPoint] = Field(
        default_factory=list,
        description="Time-series trend data",
    )

    # SLA metrics
    sla_compliance_rate: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            description="SLA compliance percentage"
        )
    ]
    sla_breached_count: int = Field(
        ...,
        ge=0,
        description="SLA breached complaint count",
    )

    # Staff performance
    top_resolvers: List[StaffPerformance] = Field(
        default_factory=list,
        max_length=10,
        description="Top 10 complaint resolvers",
    )

    @model_validator(mode="after")
    def validate_period_range(self):
        """Validate analytics period is logical."""
        if self.period_end < self.period_start:
            raise ValueError("period_end must be >= period_start")
        return self