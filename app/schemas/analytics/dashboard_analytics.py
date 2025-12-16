"""
Dashboard-level analytics schemas with role-based views.

Provides comprehensive dashboard metrics including:
- Key Performance Indicators (KPIs)
- Quick statistics for dashboard cards
- Time-series data for charts
- Role-specific dashboard configurations
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Union, Annotated

from pydantic import BaseModel, Field, field_validator, computed_field
from uuid import UUID

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import UserRole
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "KPIResponse",
    "QuickStats",
    "TimeseriesPoint",
    "DashboardMetrics",
    "RoleSpecificDashboard",
    "AlertNotification",
    "DashboardWidget",
]


# Type aliases
DecimalPercentage = Annotated[Decimal, Field(ge=0, le=100)]
DecimalNonNegative = Annotated[Decimal, Field(ge=0)]


class KPIResponse(BaseSchema):
    """
    Single Key Performance Indicator for dashboard display.
    
    Represents a measurable metric with trend information,
    targets, and interpretation guidelines.
    """
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="KPI display name"
    )
    key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique identifier key for the KPI"
    )
    value: Union[Decimal, int, float] = Field(
        ...,
        description="Current KPI value"
    )
    unit: Union[str, None] = Field(
        None,
        max_length=20,
        description="Unit of measurement (e.g., 'INR', '%', 'students')"
    )
    
    # Trend analysis
    trend_direction: Union[str, None] = Field(
        None,
        pattern="^(up|down|stable)$",
        description="Trend indicator vs previous period"
    )
    trend_percentage: Union[Decimal, None] = Field(
        None,
        description="Percentage change vs previous period"
    )
    previous_value: Union[Decimal, int, float, None] = Field(
        None,
        description="Value from previous period for comparison"
    )
    
    # Target and context
    target_value: Union[Decimal, None] = Field(
        None,
        description="Target/goal value for this KPI"
    )
    good_when: Union[str, None] = Field(
        None,
        pattern="^(higher_is_better|lower_is_better|closer_to_target)$",
        description="Interpretation rule for the KPI"
    )
    
    # Display hints
    format_pattern: Union[str, None] = Field(
        None,
        max_length=50,
        description="Format pattern for display (e.g., '%.2f')"
    )
    icon: Union[str, None] = Field(
        None,
        max_length=50,
        description="Icon identifier for UI"
    )
    color: Union[str, None] = Field(
        None,
        pattern="^#[0-9A-Fa-f]{6}$",
        description="Hex color code for UI theming"
    )
    
    @field_validator("trend_percentage")
    @classmethod
    def validate_trend_percentage(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Round trend percentage to 2 decimal places."""
        if v is not None:
            return round(v, 2)
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def is_on_target(self) -> Union[bool, None]:
        """Check if current value meets target."""
        if self.target_value is None:
            return None
        
        if self.good_when == "higher_is_better":
            return float(self.value) >= float(self.target_value)
        elif self.good_when == "lower_is_better":
            return float(self.value) <= float(self.target_value)
        elif self.good_when == "closer_to_target":
            # Within 5% of target is considered on-target
            tolerance = float(self.target_value) * 0.05
            return abs(float(self.value) - float(self.target_value)) <= tolerance
        
        return None
    
    @computed_field  # type: ignore[misc]
    @property
    def performance_status(self) -> str:
        """
        Get performance status: 'excellent', 'good', 'warning', 'critical'.
        """
        if self.target_value is None or self.good_when is None:
            return "unknown"
        
        value_float = float(self.value)
        target_float = float(self.target_value)
        
        if self.good_when == "higher_is_better":
            ratio = value_float / target_float if target_float > 0 else 0
            if ratio >= 1.1:
                return "excellent"
            elif ratio >= 1.0:
                return "good"
            elif ratio >= 0.9:
                return "warning"
            else:
                return "critical"
        
        elif self.good_when == "lower_is_better":
            ratio = target_float / value_float if value_float > 0 else float('inf')
            if ratio >= 1.1:
                return "excellent"
            elif ratio >= 1.0:
                return "good"
            elif ratio >= 0.9:
                return "warning"
            else:
                return "critical"
        
        elif self.good_when == "closer_to_target":
            deviation = abs(value_float - target_float) / target_float if target_float > 0 else 0
            if deviation <= 0.05:
                return "excellent"
            elif deviation <= 0.10:
                return "good"
            elif deviation <= 0.20:
                return "warning"
            else:
                return "critical"
        
        return "unknown"
    
    def format_value(self) -> str:
        """Format value for display using format_pattern."""
        if self.format_pattern:
            try:
                return self.format_pattern % float(self.value)
            except (ValueError, TypeError):
                pass
        
        # Default formatting
        if self.unit == "%":
            return f"{float(self.value):.2f}%"
        elif self.unit == "INR":
            return f"₹{float(self.value):,.2f}"
        else:
            return f"{self.value}"


class QuickStats(BaseSchema):
    """
    Quick statistics for dashboard cards.
    
    Provides snapshot metrics for immediate visibility
    into system state and operations.
    """
    
    # Hostel metrics
    total_hostels: int = Field(
        ...,
        ge=0,
        description="Total number of hostels in system"
    )
    active_hostels: int = Field(
        ...,
        ge=0,
        description="Number of active hostels"
    )
    
    # Student metrics
    total_students: int = Field(
        ...,
        ge=0,
        description="Total registered students"
    )
    active_students: int = Field(
        ...,
        ge=0,
        description="Currently active students"
    )
    
    # Visitor metrics
    total_visitors: int = Field(
        0,
        ge=0,
        description="Total registered visitors"
    )
    active_visitors: int = Field(
        0,
        ge=0,
        description="Currently active visitors"
    )
    
    # Daily operations
    todays_check_ins: int = Field(
        ...,
        ge=0,
        description="Check-ins scheduled for today"
    )
    todays_check_outs: int = Field(
        ...,
        ge=0,
        description="Check-outs scheduled for today"
    )
    
    # Issues and maintenance
    open_complaints: int = Field(
        ...,
        ge=0,
        description="Currently open complaints"
    )
    urgent_complaints: int = Field(
        0,
        ge=0,
        description="Urgent/critical complaints"
    )
    pending_maintenance: int = Field(
        ...,
        ge=0,
        description="Pending maintenance requests"
    )
    overdue_maintenance: int = Field(
        0,
        ge=0,
        description="Overdue maintenance requests"
    )
    
    # Financial metrics
    todays_revenue: DecimalNonNegative = Field(
        ...,
        description="Revenue collected today"
    )
    monthly_revenue: DecimalNonNegative = Field(
        ...,
        description="Revenue for current month"
    )
    outstanding_payments: DecimalNonNegative = Field(
        ...,
        description="Total outstanding payment amount"
    )
    overdue_payments: DecimalNonNegative = Field(
        0,
        description="Overdue payment amount"
    )
    
    @field_validator(
        "active_hostels",
        "active_students",
        "active_visitors"
    )
    @classmethod
    def validate_active_counts(cls, v: int, info) -> int:
        """Validate active counts don't exceed totals."""
        field_name = info.field_name
        data = info.data
        
        if field_name == "active_hostels" and "total_hostels" in data:
            if v > data["total_hostels"]:
                raise ValueError("active_hostels cannot exceed total_hostels")
        elif field_name == "active_students" and "total_students" in data:
            if v > data["total_students"]:
                raise ValueError("active_students cannot exceed total_students")
        elif field_name == "active_visitors" and "total_visitors" in data:
            if v > data["total_visitors"]:
                raise ValueError("active_visitors cannot exceed total_visitors")
        
        return v
    
    @field_validator("todays_revenue", "monthly_revenue", "outstanding_payments", "overdue_payments")
    @classmethod
    def round_currency(cls, v: Decimal) -> Decimal:
        """Round to 2 decimal places."""
        return round(v, 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def occupancy_rate(self) -> Decimal:
        """Calculate approximate occupancy rate."""
        if self.total_students == 0:
            return Decimal("0.00")
        # Simplified calculation - would need total bed count for accuracy
        return round(
            (Decimal(self.active_students) / Decimal(self.total_students)) * 100,
            2
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def complaint_urgency_rate(self) -> Decimal:
        """Calculate percentage of urgent complaints."""
        if self.open_complaints == 0:
            return Decimal("0.00")
        return round(
            (Decimal(self.urgent_complaints) / Decimal(self.open_complaints)) * 100,
            2
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def payment_collection_health(self) -> str:
        """Assess payment collection health."""
        if self.outstanding_payments == 0:
            return "excellent"
        
        overdue_ratio = (
            self.overdue_payments / self.outstanding_payments
            if self.outstanding_payments > 0
            else 0
        )
        
        if overdue_ratio <= Decimal("0.1"):
            return "good"
        elif overdue_ratio <= Decimal("0.25"):
            return "warning"
        else:
            return "critical"


class TimeseriesPoint(BaseSchema):
    """
    Single data point in a time series.
    """

    date_: Date = Field(
        ...,
        description="Date of the data point",
        serialization_alias="date"
    )
    value: Union[Decimal, int, float] = Field(
        ...,
        description="Metric value"
    )
    label: Union[str, None] = Field(
        None,
        max_length=100,
        description="Optional label for this point"
    )
    metadata: Union[Dict[str, Any], None] = Field(
        None,
        description="Additional metadata for this point"
    )

    @computed_field  # type: ignore[misc]
    @property
    def formatted_date(self) -> str:
        """Get formatted date string."""
        return self.date_.strftime("%Y-%m-%d")


class AlertNotification(BaseSchema):
    """Dashboard alert notification."""
    
    id: UUID = Field(
        ...,
        description="Alert identifier"
    )
    severity: str = Field(
        ...,
        pattern="^(info|warning|error|critical)$",
        description="Alert severity level"
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Alert title"
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Alert message"
    )
    action_url: Union[str, None] = Field(
        None,
        max_length=500,
        description="URL for alert action"
    )
    action_label: Union[str, None] = Field(
        None,
        max_length=100,
        description="Label for action button"
    )
    created_at: datetime = Field(
        ...,
        description="Alert creation time"
    )
    expires_at: Union[datetime, None] = Field(
        None,
        description="Alert expiration time"
    )
    is_dismissed: bool = Field(
        False,
        description="Whether alert has been dismissed"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def is_active(self) -> bool:
        """Check if alert is still active."""
        if self.is_dismissed:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True


class DashboardWidget(BaseSchema):
    """Configuration for a dashboard widget."""
    
    widget_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique widget identifier"
    )
    widget_type: str = Field(
        ...,
        pattern="^(kpi|chart|table|list|stat)$",
        description="Widget type"
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Widget title"
    )
    position: int = Field(
        ...,
        ge=0,
        description="Display position/order"
    )
    size: str = Field(
        "medium",
        pattern="^(small|medium|large|full)$",
        description="Widget size"
    )
    data_source: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Data source identifier"
    )
    refresh_interval_seconds: Union[int, None] = Field(
        None,
        ge=10,
        description="Auto-refresh interval in seconds"
    )
    is_visible: bool = Field(
        True,
        description="Whether widget is visible"
    )


class DashboardMetrics(BaseSchema):
    """
    Aggregated dashboard metrics for a given scope.
    
    Provides comprehensive analytics tailored to specific
    scope (hostel, platform, or admin).
    """
    
    scope_type: str = Field(
        ...,
        pattern="^(hostel|platform|admin)$",
        description="Scope of the dashboard"
    )
    scope_id: Union[UUID, None] = Field(
        None,
        description="Hostel ID or admin ID if applicable"
    )
    scope_name: Union[str, None] = Field(
        None,
        max_length=255,
        description="Display name for the scope"
    )
    
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Dashboard generation timestamp"
    )
    
    # Core metrics
    kpis: List[KPIResponse] = Field(
        default_factory=list,
        description="Key performance indicators"
    )
    quick_stats: QuickStats = Field(
        ...,
        description="Quick statistics for dashboard cards"
    )
    
    # Time series data for charts
    revenue_timeseries: List[TimeseriesPoint] = Field(
        default_factory=list,
        description="Revenue over time"
    )
    occupancy_timeseries: List[TimeseriesPoint] = Field(
        default_factory=list,
        description="Occupancy rate over time"
    )
    booking_timeseries: List[TimeseriesPoint] = Field(
        default_factory=list,
        description="Bookings over time"
    )
    complaint_timeseries: List[TimeseriesPoint] = Field(
        default_factory=list,
        description="Complaints over time"
    )
    
    # Alerts and notifications
    alerts: List[AlertNotification] = Field(
        default_factory=list,
        description="Active alerts for this dashboard"
    )
    
    # Custom widgets
    widgets: List[DashboardWidget] = Field(
        default_factory=list,
        description="Custom dashboard widgets"
    )
    
    @field_validator(
        "revenue_timeseries",
        "occupancy_timeseries",
        "booking_timeseries",
        "complaint_timeseries"
    )
    @classmethod
    def validate_timeseries_chronological(
        cls,
        v: List[TimeseriesPoint]
    ) -> List[TimeseriesPoint]:
        """Ensure timeseries data is in chronological order."""
        if len(v) > 1:
            dates = [point.date_ for point in v]
            if dates != sorted(dates):
                raise ValueError("Timeseries points must be in chronological order")
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def active_alert_count(self) -> int:
        """Count of active alerts."""
        return sum(1 for alert in self.alerts if alert.is_active)
    
    @computed_field  # type: ignore[misc]
    @property
    def critical_alert_count(self) -> int:
        """Count of critical active alerts."""
        return sum(
            1 for alert in self.alerts
            if alert.is_active and alert.severity == "critical"
        )
    
    def get_kpi_by_key(self, key: str) -> Union[KPIResponse, None]:
        """Retrieve a specific KPI by its key."""
        for kpi in self.kpis:
            if kpi.key == key:
                return kpi
        return None
    
    def get_trending_kpis(self) -> List[KPIResponse]:
        """Get KPIs that are trending (up or down)."""
        return [
            kpi for kpi in self.kpis
            if kpi.trend_direction and kpi.trend_direction != "stable"
        ]
    
    def get_off_target_kpis(self) -> List[KPIResponse]:
        """Get KPIs that are not meeting targets."""
        return [
            kpi for kpi in self.kpis
            if kpi.is_on_target is False
        ]


class RoleSpecificDashboard(BaseSchema):
    """
    Role-specific dashboard configuration and data.
    
    Provides customized dashboard views based on user role,
    showing only relevant metrics and actions.
    """
    
    role: UserRole = Field(
        ...,
        description="User role for this dashboard"
    )
    user_id: UUID = Field(
        ...,
        description="User identifier"
    )
    user_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User display name"
    )
    
    # Section-based organization
    sections: List[str] = Field(
        default_factory=list,
        description="Dashboard section identifiers"
    )
    
    # Metrics organized by section
    metrics_by_section: Dict[str, DashboardMetrics] = Field(
        default_factory=dict,
        description="Section name -> Dashboard metrics"
    )
    
    # Quick stats organized by section
    stats_by_section: Dict[str, QuickStats] = Field(
        default_factory=dict,
        description="Section name -> Quick stats"
    )
    
    # KPIs organized by section
    kpis_by_section: Dict[str, List[KPIResponse]] = Field(
        default_factory=dict,
        description="Section name -> KPI list"
    )
    
    # Permissions
    accessible_features: List[str] = Field(
        default_factory=list,
        description="List of features accessible to this role"
    )
    
    # Preferences
    default_section: Union[str, None] = Field(
        None,
        description="Default section to display"
    )
    layout_preferences: Union[Dict[str, Any], None] = Field(
        None,
        description="User's layout preferences"
    )
    
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Dashboard generation timestamp"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def total_kpi_count(self) -> int:
        """Total number of KPIs across all sections."""
        return sum(len(kpis) for kpis in self.kpis_by_section.values())
    
    @computed_field  # type: ignore[misc]
    @property
    def has_critical_alerts(self) -> bool:
        """Check if any section has critical alerts."""
        for metrics in self.metrics_by_section.values():
            if metrics.critical_alert_count > 0:
                return True
        return False
    
    def get_section_metrics(self, section_name: str) -> Union[DashboardMetrics, None]:
        """Get metrics for a specific section."""
        return self.metrics_by_section.get(section_name)
    
    def get_all_alerts(self) -> List[AlertNotification]:
        """Get all alerts from all sections."""
        all_alerts = []
        for metrics in self.metrics_by_section.values():
            all_alerts.extend(metrics.alerts)
        
        # Sort by severity and creation time
        severity_order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
        return sorted(
            all_alerts,
            key=lambda x: (severity_order.get(x.severity, 999), x.created_at),
            reverse=True
        )