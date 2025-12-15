# --- File: app/schemas/supervisor/supervisor_activity.py ---
"""
Supervisor activity and audit log schemas with enhanced tracking.

Provides comprehensive activity monitoring, audit trails, and
performance analytics with optimized filtering and export capabilities.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator, computed_field, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseFilterSchema, BaseResponseSchema, BaseSchema
from app.schemas.common.enums import AuditActionCategory
from app.schemas.common.filters import DateTimeRangeFilter

__all__ = [
    "SupervisorActivityLog",
    "ActivityDetail",
    "ActivitySummary",
    "ActivityFilterParams",
    "ActivityExportRequest",
    "TopActivity",
    "ActivityTimelinePoint",
    "ActivityMetrics",
]


class SupervisorActivityLog(BaseResponseSchema):
    """
    Supervisor activity log entry with enhanced metadata.
    
    Tracks all supervisor actions with context and performance data.
    """

    supervisor_id: str = Field(..., description="Supervisor ID")
    supervisor_name: str = Field(..., description="Supervisor name")
    hostel_id: str = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    
    # Action details
    action_type: str = Field(
        ...,
        description="Specific action performed",
        examples=[
            "complaint_resolved",
            "attendance_marked",
            "maintenance_created",
            "announcement_published",
        ],
    )
    action_category: AuditActionCategory = Field(
        ...,
        description="Action category for grouping",
    )
    action_description: str = Field(
        ...,
        description="Human-readable description",
    )
    
    # Entity affected
    entity_type: Optional[str] = Field(
        default=None,
        description="Type of entity affected",
        examples=["complaint", "student", "room", "maintenance_request"],
    )
    entity_id: Optional[str] = Field(
        default=None,
        description="ID of affected entity",
    )
    entity_name: Optional[str] = Field(
        default=None,
        description="Name/title of affected entity",
    )
    
    # Context and metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional action details and context",
    )
    
    # Technical details
    ip_address: Optional[str] = Field(
        default=None,
        description="IP address of action origin",
    )
    user_agent: Optional[str] = Field(
        default=None,
        description="User agent string",
    )
    device_type: Optional[str] = Field(
        default=None,
        description="Device type (mobile/desktop/tablet)",
    )
    
    # Performance tracking
    response_time_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Action response time in milliseconds",
    )
    success: bool = Field(
        default=True,
        description="Whether action completed successfully",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if action failed",
    )

    @computed_field
    @property
    def action_display_name(self) -> str:
        """Get human-readable action name."""
        action_names = {
            "complaint_resolved": "Resolved Complaint",
            "complaint_assigned": "Assigned Complaint",
            "attendance_marked": "Marked Attendance",
            "leave_approved": "Approved Leave",
            "maintenance_created": "Created Maintenance Request",
            "maintenance_assigned": "Assigned Maintenance",
            "announcement_published": "Published Announcement",
            "student_contacted": "Contacted Student",
            "room_status_updated": "Updated Room Status",
            "menu_updated": "Updated Menu",
        }
        return action_names.get(self.action_type, self.action_type.replace("_", " ").title())


class ActivityDetail(BaseSchema):
    """
    Detailed activity information with change tracking.
    
    Comprehensive activity record with before/after states.
    """

    activity_id: str = Field(..., description="Activity ID")
    supervisor_id: str = Field(..., description="Supervisor ID")
    supervisor_name: str = Field(..., description="Supervisor name")
    
    timestamp: datetime = Field(..., description="Activity timestamp")
    action_type: str = Field(..., description="Action type")
    action_category: AuditActionCategory = Field(..., description="Action category")
    action_description: str = Field(..., description="Action description")
    
    # Entity details
    entity_type: Optional[str] = Field(default=None, description="Entity type")
    entity_id: Optional[str] = Field(default=None, description="Entity ID")
    entity_name: Optional[str] = Field(default=None, description="Entity name")
    
    # Change tracking
    old_values: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Previous values before change",
    )
    new_values: Optional[Dict[str, Any]] = Field(
        default=None,
        description="New values after change",
    )
    
    # Context
    ip_address: Optional[str] = Field(default=None, description="IP address")
    user_agent: Optional[str] = Field(default=None, description="User agent")
    location: Optional[str] = Field(default=None, description="Geographic location")
    device_info: Optional[Dict[str, str]] = Field(
        default=None,
        description="Device information",
    )
    
    # Result
    success: bool = Field(default=True, description="Action success status")
    error_message: Optional[str] = Field(default=None, description="Error message")
    response_time_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Response time in milliseconds",
    )
    
    # Impact assessment
    impact_level: Optional[str] = Field(
        default=None,
        pattern=r"^(low|medium|high|critical)$",
        description="Impact level of the action",
    )
    affected_users_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of users affected by action",
    )

    @computed_field
    @property
    def has_changes(self) -> bool:
        """Check if activity involved data changes."""
        return bool(self.old_values or self.new_values)

    @computed_field
    @property
    def change_summary(self) -> Optional[str]:
        """Generate summary of changes made."""
        if not self.has_changes:
            return None
        
        if not self.old_values or not self.new_values:
            return "Data modified"
        
        changes = []
        for key in self.new_values:
            if key in self.old_values and self.old_values[key] != self.new_values[key]:
                changes.append(f"{key}: {self.old_values[key]} → {self.new_values[key]}")
        
        return "; ".join(changes) if changes else "No changes detected"


class TopActivity(BaseSchema):
    """
    Top activity item for summary reports.
    
    Represents frequently performed activities.
    """

    action_type: str = Field(..., description="Action type")
    action_category: str = Field(..., description="Action category")
    action_display_name: str = Field(..., description="Human-readable name")
    count: int = Field(..., ge=0, description="Number of times performed")
    last_performed: datetime = Field(..., description="Last time performed")
    average_response_time_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Average response time",
    )
    success_rate: float = Field(
        ...,
        ge=0,
        le=100,
        description="Success rate percentage",
    )

    @computed_field
    @property
    def frequency_description(self) -> str:
        """Get frequency description."""
        if self.count >= 100:
            return "Very Frequent"
        elif self.count >= 50:
            return "Frequent"
        elif self.count >= 20:
            return "Regular"
        elif self.count >= 10:
            return "Occasional"
        else:
            return "Rare"


class ActivityTimelinePoint(BaseSchema):
    """
    Activity timeline data point for trend analysis.
    
    Represents activity volume over time periods.
    """

    timestamp: datetime = Field(..., description="Time period")
    action_count: int = Field(..., ge=0, description="Total actions in period")
    unique_action_types: int = Field(..., ge=0, description="Unique action types")
    success_rate: float = Field(..., ge=0, le=100, description="Success rate %")
    
    # Category breakdown
    categories: Dict[str, int] = Field(
        default_factory=dict,
        description="Action count by category",
    )
    
    # Performance metrics
    average_response_time_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Average response time",
    )

    @computed_field
    @property
    def activity_level(self) -> str:
        """Categorize activity level."""
        if self.action_count >= 50:
            return "High"
        elif self.action_count >= 20:
            return "Medium"
        elif self.action_count >= 5:
            return "Low"
        else:
            return "Minimal"


class ActivityMetrics(BaseSchema):
    """
    Comprehensive activity metrics for performance analysis.
    
    Aggregated metrics for supervisor activity assessment.
    """

    supervisor_id: str = Field(..., description="Supervisor ID")
    period_start: datetime = Field(..., description="Metrics period start")
    period_end: datetime = Field(..., description="Metrics period end")
    
    # Volume metrics
    total_actions: int = Field(..., ge=0, description="Total actions performed")
    unique_action_types: int = Field(..., ge=0, description="Unique action types")
    active_days: int = Field(..., ge=0, description="Days with activity")
    
    # Performance metrics
    overall_success_rate: float = Field(
        ...,
        ge=0,
        le=100,
        description="Overall success rate percentage",
    )
    average_response_time_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Average response time",
    )
    
    # Category distribution
    actions_by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Action count by category",
    )
    
    # Peak activity analysis
    peak_hour: Optional[int] = Field(
        default=None,
        ge=0,
        le=23,
        description="Hour with most activity (0-23)",
    )
    peak_day_of_week: Optional[int] = Field(
        default=None,
        ge=0,
        le=6,
        description="Day of week with most activity (0=Monday)",
    )
    
    # Efficiency metrics
    actions_per_day: float = Field(
        ...,
        ge=0,
        description="Average actions per active day",
    )
    response_time_trend: Optional[str] = Field(
        default=None,
        pattern=r"^(improving|stable|declining)$",
        description="Response time trend",
    )

    @computed_field
    @property
    def activity_score(self) -> float:
        """Calculate overall activity score (0-100)."""
        # Weighted scoring based on volume, consistency, and performance
        volume_score = min(self.total_actions / 100 * 40, 40)  # Max 40 points
        consistency_score = min(self.active_days / 30 * 30, 30)  # Max 30 points
        performance_score = self.overall_success_rate * 0.3  # Max 30 points
        
        return round(volume_score + consistency_score + performance_score, 2)

    @computed_field
    @property
    def productivity_level(self) -> str:
        """Categorize productivity level."""
        score = self.activity_score
        if score >= 80:
            return "Excellent"
        elif score >= 60:
            return "Good"
        elif score >= 40:
            return "Average"
        elif score >= 20:
            return "Below Average"
        else:
            return "Poor"


class ActivitySummary(BaseSchema):
    """
    Activity summary for supervisor dashboard.
    
    High-level activity overview with key insights.
    """

    supervisor_id: str = Field(..., description="Supervisor ID")
    supervisor_name: str = Field(..., description="Supervisor name")
    period_start: datetime = Field(..., description="Summary period start")
    period_end: datetime = Field(..., description="Summary period end")
    
    total_actions: int = Field(..., ge=0, description="Total actions")
    
    # Category breakdown
    actions_by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of actions by category",
    )
    
    # Type breakdown
    actions_by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of actions by type",
    )
    
    # Top activities
    top_activities: List[TopActivity] = Field(
        default_factory=list,
        max_length=10,
        description="Most frequent activities",
    )
    
    # Activity timeline
    activity_timeline: List[ActivityTimelinePoint] = Field(
        default_factory=list,
        description="Activity over time",
    )
    
    # Performance insights
    peak_hours: List[int] = Field(
        default_factory=list,
        description="Hours with most activity (0-23)",
    )
    most_productive_day: Optional[str] = Field(
        default=None,
        description="Day of week with highest activity",
    )
    
    # Efficiency metrics
    average_daily_actions: float = Field(
        ...,
        ge=0,
        description="Average actions per day",
    )
    success_rate: float = Field(
        ...,
        ge=0,
        le=100,
        description="Overall success rate",
    )

    @computed_field
    @property
    def most_common_activity(self) -> Optional[str]:
        """Get most frequently performed activity."""
        if not self.top_activities:
            return None
        return self.top_activities[0].action_display_name

    @computed_field
    @property
    def activity_consistency(self) -> str:
        """Assess activity consistency."""
        if not self.activity_timeline:
            return "Unknown"
        
        # Calculate coefficient of variation
        counts = [point.action_count for point in self.activity_timeline]
        if not counts:
            return "No Data"
        
        mean_count = sum(counts) / len(counts)
        if mean_count == 0:
            return "No Activity"
        
        variance = sum((x - mean_count) ** 2 for x in counts) / len(counts)
        cv = (variance ** 0.5) / mean_count
        
        if cv < 0.3:
            return "Very Consistent"
        elif cv < 0.6:
            return "Consistent"
        elif cv < 1.0:
            return "Moderately Variable"
        else:
            return "Highly Variable"


class ActivityFilterParams(BaseFilterSchema):
    """
    Enhanced filter parameters for activity logs.
    
    Comprehensive filtering with performance optimizations.
    """

    # Supervisor filters
    supervisor_id: Optional[str] = Field(
        default=None,
        description="Filter by specific supervisor",
    )
    supervisor_ids: Optional[List[str]] = Field(
        default=None,
        max_length=20,
        description="Filter by multiple supervisors (max 20)",
    )
    
    # Hostel filter
    hostel_id: Optional[str] = Field(
        default=None,
        description="Filter by hostel",
    )
    
    # Time range
    date_range: Optional[DateTimeRangeFilter] = Field(
        default=None,
        description="Filter by Date/time range",
    )
    
    # Action filters
    action_category: Optional[AuditActionCategory] = Field(
        default=None,
        description="Filter by action category",
    )
    action_categories: Optional[List[AuditActionCategory]] = Field(
        default=None,
        max_length=10,
        description="Filter by multiple categories",
    )
    action_type: Optional[str] = Field(
        default=None,
        description="Filter by specific action type",
    )
    action_types: Optional[List[str]] = Field(
        default=None,
        max_length=20,
        description="Filter by multiple action types",
    )
    
    # Entity filter
    entity_type: Optional[str] = Field(
        default=None,
        description="Filter by entity type",
    )
    entity_id: Optional[str] = Field(
        default=None,
        description="Filter by specific entity",
    )
    
    # Success filter
    success_only: Optional[bool] = Field(
        default=None,
        description="Show only successful actions",
    )
    failed_only: Optional[bool] = Field(
        default=None,
        description="Show only failed actions",
    )
    
    # Performance filters
    min_response_time_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum response time filter",
    )
    max_response_time_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum response time filter",
    )
    
    # Device filters
    device_type: Optional[str] = Field(
        default=None,
        pattern=r"^(mobile|desktop|tablet)$",
        description="Filter by device type",
    )
    
    # Pagination and sorting
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=50, ge=1, le=100, description="Items per page")
    sort_by: str = Field(
        default="created_at",
        pattern=r"^(created_at|action_type|success|response_time_ms)$",
        description="Sort field",
    )
    sort_order: str = Field(
        default="desc",
        pattern=r"^(asc|desc)$",
        description="Sort order",
    )

    @field_validator("supervisor_ids")
    @classmethod
    def validate_supervisor_ids(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate supervisor IDs list."""
        if v is not None:
            # Remove duplicates while preserving order
            seen = set()
            unique_ids = []
            for supervisor_id in v:
                if supervisor_id not in seen:
                    seen.add(supervisor_id)
                    unique_ids.append(supervisor_id)
            return unique_ids
        return v

    @model_validator(mode="after")
    def validate_filter_consistency(self) -> "ActivityFilterParams":
        """Validate filter consistency."""
        # Can't have both success_only and failed_only
        if self.success_only and self.failed_only:
            raise ValueError("Cannot filter for both success_only and failed_only")
        
        # Validate response time range
        if (self.min_response_time_ms is not None and 
            self.max_response_time_ms is not None and
            self.min_response_time_ms > self.max_response_time_ms):
            raise ValueError("min_response_time_ms cannot be greater than max_response_time_ms")
        
        return self


class ActivityExportRequest(BaseCreateSchema):
    """
    Export activity logs with customizable format and fields.
    
    Supports various export formats with field selection.
    """

    filters: ActivityFilterParams = Field(
        ...,
        description="Filter criteria for export",
    )
    format: str = Field(
        default="csv",
        pattern=r"^(csv|excel|pdf|json)$",
        description="Export file format",
    )
    
    # Field selection
    include_metadata: bool = Field(
        default=False,
        description="Include full metadata in export",
    )
    include_technical_details: bool = Field(
        default=False,
        description="Include IP, user agent, etc.",
    )
    include_performance_metrics: bool = Field(
        default=True,
        description="Include response times and success rates",
    )
    include_change_tracking: bool = Field(
        default=False,
        description="Include old/new values for changes",
    )
    
    # Grouping options
    group_by_category: bool = Field(
        default=False,
        description="Group activities by category",
    )
    group_by_date: bool = Field(
        default=False,
        description="Group activities by Date",
    )
    
    # Summary options
    include_summary: bool = Field(
        default=True,
        description="Include summary statistics",
    )
    include_charts: bool = Field(
        default=False,
        description="Include charts (for PDF/Excel)",
    )

    @field_validator("format")
    @classmethod
    def normalize_format(cls, v: str) -> str:
        """Normalize format to lowercase."""
        return v.lower().strip()