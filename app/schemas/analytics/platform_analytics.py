# --- File: app/schemas/analytics/platform_analytics.py ---
"""
Platform-wide analytics schemas for super admin oversight.

Provides comprehensive platform metrics including:
- Multi-tenant statistics
- Growth metrics and trends
- Platform usage analytics
- System performance metrics
- Revenue aggregation across tenants
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Union, Annotated
from enum import Enum

from pydantic import BaseModel, Field, field_validator, computed_field, model_validator, AfterValidator
from uuid import UUID

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import SubscriptionPlan, SubscriptionStatus
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "TenantStatus",
    "PlatformMetrics",
    "MonthlyMetric",
    "GrowthMetrics",
    "TenantMetrics",
    "PlatformUsageAnalytics",
    "SystemHealthMetrics",
    "RevenueMetrics",
    "ChurnAnalysis",
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
DecimalAmount = Annotated[Decimal, AfterValidator(round_to_2_places)]


class TenantStatus(str, Enum):
    """Tenant (hostel) status categories."""
    
    TRIAL = "trial"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CHURNED = "churned"
    INACTIVE = "inactive"


class TenantMetrics(BaseSchema):
    """
    Metrics for a single tenant (hostel).
    
    Provides individual tenant performance data for
    platform-level aggregation and analysis.
    """
    
    tenant_id: UUID = Field(
        ...,
        description="Hostel/tenant unique identifier"
    )
    tenant_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Tenant display name"
    )
    
    # Subscription info
    subscription_plan: SubscriptionPlan = Field(
        ...,
        description="Current subscription plan"
    )
    subscription_status: SubscriptionStatus = Field(
        ...,
        description="Subscription status"
    )
    subscription_start_date: Date = Field(
        ...,
        description="Subscription start date"
    )
    subscription_mrr: DecimalNonNegative = Field(
        ...,
        description="Monthly recurring revenue from this tenant"
    )
    
    # Usage metrics
    total_students: int = Field(
        ...,
        ge=0,
        description="Total students in this hostel"
    )
    active_students: int = Field(
        ...,
        ge=0,
        description="Active students"
    )
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total bed capacity"
    )
    occupancy_rate: DecimalPercentage = Field(
        ...,
        description="Current occupancy rate"
    )
    
    # Activity metrics
    last_login: Optional[datetime] = Field(
        None,
        description="Last admin login timestamp"
    )
    daily_active_users: int = Field(
        0,
        ge=0,
        description="Daily active users (last 24h)"
    )
    monthly_active_users: int = Field(
        0,
        ge=0,
        description="Monthly active users (last 30 days)"
    )
    
    # Health indicators
    payment_status: str = Field(
        ...,
        pattern="^(current|overdue|suspended)$",
        description="Payment status"
    )
    health_score: DecimalPercentage = Field(
        ...,
        description="Overall tenant health score"
    )
    churn_risk_score: DecimalPercentage = Field(
        ...,
        description="Churn risk score (higher = higher risk)"
    )
    
    @field_validator("active_students")
    @classmethod
    def validate_active_students(cls, v: int, info) -> int:
        """Validate active students don't exceed total."""
        if "total_students" in info.data and v > info.data["total_students"]:
            raise ValueError("active_students cannot exceed total_students")
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def is_at_risk(self) -> bool:
        """Check if tenant is at risk of churning."""
        return self.churn_risk_score >= 70
    
    @computed_field  # type: ignore[misc]
    @property
    def revenue_per_bed(self) -> Decimal:
        """Calculate revenue per bed."""
        if self.total_beds == 0:
            return Decimal("0.00")
        return round(self.subscription_mrr / Decimal(self.total_beds), 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def engagement_status(self) -> str:
        """Assess tenant engagement level."""
        if self.last_login is None:
            return "inactive"
        
        days_since_login = (datetime.utcnow() - self.last_login).days
        
        if days_since_login <= 1:
            return "highly_active"
        elif days_since_login <= 7:
            return "active"
        elif days_since_login <= 30:
            return "moderate"
        else:
            return "low"


class PlatformMetrics(BaseSchema):
    """
    High-level platform metrics across all tenants.
    
    Provides aggregate statistics for platform monitoring
    and strategic decision-making.
    """
    
    period: DateRangeFilter = Field(
        ...,
        description="Reporting period"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp"
    )
    
    # Tenant metrics
    total_hostels: int = Field(
        ...,
        ge=0,
        description="Total registered hostels"
    )
    active_hostels: int = Field(
        ...,
        ge=0,
        description="Currently active hostels"
    )
    hostels_on_trial: int = Field(
        ...,
        ge=0,
        description="Hostels on trial period"
    )
    suspended_hostels: int = Field(
        0,
        ge=0,
        description="Suspended hostels"
    )
    churned_hostels: int = Field(
        0,
        ge=0,
        description="Churned hostels in period"
    )
    
    # User metrics
    total_users: int = Field(
        ...,
        ge=0,
        description="Total registered users across platform"
    )
    total_students: int = Field(
        ...,
        ge=0,
        description="Total students"
    )
    total_supervisors: int = Field(
        ...,
        ge=0,
        description="Total supervisors"
    )
    total_admins: int = Field(
        ...,
        ge=0,
        description="Total hostel admins"
    )
    total_visitors: int = Field(
        0,
        ge=0,
        description="Total visitors/prospects"
    )
    
    # Engagement metrics
    avg_daily_active_users: int = Field(
        ...,
        ge=0,
        description="Average daily active users"
    )
    avg_monthly_active_users: int = Field(
        0,
        ge=0,
        description="Average monthly active users"
    )
    peak_concurrent_sessions: int = Field(
        0,
        ge=0,
        description="Peak concurrent sessions in period"
    )
    
    # Capacity metrics
    total_beds_platform: int = Field(
        0,
        ge=0,
        description="Total bed capacity across all hostels"
    )
    total_occupied_beds: int = Field(
        0,
        ge=0,
        description="Total occupied beds platform-wide"
    )
    platform_occupancy_rate: DecimalPercentage = Field(
        0,
        description="Platform-wide occupancy rate"
    )
    
    @field_validator(
        "active_hostels",
        "hostels_on_trial",
        "suspended_hostels"
    )
    @classmethod
    def validate_hostel_counts(cls, v: int, info) -> int:
        """Validate hostel segment counts."""
        if "total_hostels" in info.data:
            total = info.data["total_hostels"]
            # Allow some flexibility as counts may overlap during transitions
            if v > total:
                raise ValueError(f"{info.field_name} cannot exceed total_hostels")
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def activation_rate(self) -> Decimal:
        """Calculate percentage of hostels that are active."""
        if self.total_hostels == 0:
            return Decimal("0.00")
        return round(
            (Decimal(self.active_hostels) / Decimal(self.total_hostels)) * 100,
            2
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def trial_conversion_potential(self) -> int:
        """Estimate potential conversions from trial hostels."""
        # Assume 60% trial conversion rate
        return int(self.hostels_on_trial * 0.6)
    
    @computed_field  # type: ignore[misc]
    @property
    def user_growth_rate(self) -> Optional[Decimal]:
        """Calculate user growth rate if previous period data available."""
        # This would need previous period data - placeholder
        return None


class MonthlyMetric(BaseSchema):
    """
    Monthly metric data point for trend analysis.
    
    Represents a single metric value for a specific month.
    """
    
    month: str = Field(
        ...,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Month in YYYY-MM format"
    )
    value: Union[Decimal, int, float] = Field(
        ...,
        description="Metric value for the month"
    )
    label: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional display label"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def month_name(self) -> str:
        """Get human-readable month name."""
        try:
            year, month = self.month.split("-")
            dt = datetime(int(year), int(month), 1)
            return dt.strftime("%B %Y")
        except (ValueError, AttributeError):
            return self.month


class GrowthMetrics(BaseSchema):
    """
    Growth metrics and trends over time.
    
    Provides detailed growth analysis across key dimensions
    for strategic planning and investor reporting.
    """
    
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period"
    )
    
    # Hostel growth
    new_hostels: int = Field(
        ...,
        ge=0,
        description="New hostels added in period"
    )
    churned_hostels: int = Field(
        ...,
        ge=0,
        description="Hostels churned in period"
    )
    net_hostel_growth: int = Field(
        ...,
        description="Net change in hostel count"
    )
    hostel_growth_rate: DecimalAmount = Field(
        ...,
        description="Hostel growth rate percentage"
    )
    
    # Revenue growth
    total_revenue: DecimalNonNegative = Field(
        ...,
        description="Total revenue for period"
    )
    previous_period_revenue: DecimalNonNegative = Field(
        ...,
        description="Revenue from previous period"
    )
    revenue_growth_amount: DecimalAmount = Field(
        ...,
        description="Absolute revenue growth"
    )
    revenue_growth_rate: DecimalAmount = Field(
        ...,
        description="Revenue growth rate percentage"
    )
    
    # User growth
    new_users: int = Field(
        ...,
        ge=0,
        description="New users registered in period"
    )
    churned_users: int = Field(
        0,
        ge=0,
        description="Users churned in period"
    )
    net_user_growth: int = Field(
        ...,
        description="Net change in user count"
    )
    user_growth_rate: DecimalAmount = Field(
        ...,
        description="User growth rate percentage"
    )
    
    # MRR (Monthly Recurring Revenue) growth
    current_mrr: DecimalNonNegative = Field(
        ...,
        description="Current monthly recurring revenue"
    )
    previous_mrr: DecimalNonNegative = Field(
        ...,
        description="Previous period MRR"
    )
    mrr_growth_rate: DecimalAmount = Field(
        ...,
        description="MRR growth rate percentage"
    )
    
    # Time series data
    monthly_revenue: List[MonthlyMetric] = Field(
        default_factory=list,
        description="Monthly revenue trend"
    )
    monthly_new_hostels: List[MonthlyMetric] = Field(
        default_factory=list,
        description="Monthly new hostel acquisitions"
    )
    monthly_new_users: List[MonthlyMetric] = Field(
        default_factory=list,
        description="Monthly new user registrations"
    )
    monthly_mrr: List[MonthlyMetric] = Field(
        default_factory=list,
        description="Monthly MRR trend"
    )
    
    @model_validator(mode="after")
    def validate_growth_calculations(self) -> "GrowthMetrics":
        """Validate growth calculations are consistent."""
        
        # Net hostel growth
        expected_net = self.new_hostels - self.churned_hostels
        if self.net_hostel_growth != expected_net:
            raise ValueError(
                f"net_hostel_growth ({self.net_hostel_growth}) should equal "
                f"new_hostels ({self.new_hostels}) - churned_hostels ({self.churned_hostels})"
            )
        
        # Revenue growth
        expected_revenue_growth = self.total_revenue - self.previous_period_revenue
        if abs(self.revenue_growth_amount - expected_revenue_growth) > Decimal("0.01"):
            raise ValueError(
                "revenue_growth_amount should equal total_revenue - previous_period_revenue"
            )
        
        return self
    
    @computed_field  # type: ignore[misc]
    @property
    def is_growing(self) -> bool:
        """Check if platform is growing across key metrics."""
        return (
            self.net_hostel_growth > 0 and
            self.revenue_growth_rate > 0 and
            self.user_growth_rate > 0
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def growth_health_score(self) -> Decimal:
        """
        Calculate overall growth health score (0-100).
        
        Weighted combination of hostel, revenue, and user growth.
        """
        weights = {
            "hostel": Decimal("0.3"),
            "revenue": Decimal("0.5"),
            "user": Decimal("0.2"),
        }
        
        # Normalize growth rates to 0-100 scale
        hostel_score = min(max(self.hostel_growth_rate, Decimal("0")), Decimal("100"))
        revenue_score = min(max(self.revenue_growth_rate, Decimal("0")), Decimal("100"))
        user_score = min(max(self.user_growth_rate, Decimal("0")), Decimal("100"))
        
        score = (
            hostel_score * weights["hostel"] +
            revenue_score * weights["revenue"] +
            user_score * weights["user"]
        )
        
        return round(score, 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def compound_annual_growth_rate(self) -> Optional[Decimal]:
        """
        Calculate CAGR if sufficient historical data available.
        
        Requires at least 12 months of revenue data.
        """
        if len(self.monthly_revenue) < 12:
            return None
        
        beginning_value = float(self.monthly_revenue[0].value)
        ending_value = float(self.monthly_revenue[-1].value)
        periods = len(self.monthly_revenue) / 12  # Convert to years
        
        if beginning_value <= 0 or periods <= 0:
            return None
        
        cagr = ((ending_value / beginning_value) ** (1 / periods) - 1) * 100
        return round(Decimal(str(cagr)), 2)


class ChurnAnalysis(BaseSchema):
    """
    Customer churn analysis and prediction.
    
    Provides insights into churn patterns and at-risk tenants.
    """
    
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period"
    )
    
    # Churn metrics
    churned_count: int = Field(
        ...,
        ge=0,
        description="Number of churned tenants in period"
    )
    churn_rate: DecimalPercentage = Field(
        ...,
        description="Churn rate percentage"
    )
    revenue_churned: DecimalNonNegative = Field(
        ...,
        description="MRR lost to churn"
    )
    
    # Churn reasons
    churn_reasons: Dict[str, int] = Field(
        default_factory=dict,
        description="Churn count by reason"
    )
    
    # At-risk analysis
    at_risk_count: int = Field(
        ...,
        ge=0,
        description="Number of tenants at risk of churning"
    )
    at_risk_tenants: List[TenantMetrics] = Field(
        default_factory=list,
        description="Details of at-risk tenants"
    )
    
    # Retention metrics
    retention_rate: DecimalPercentage = Field(
        ...,
        description="Retention rate percentage"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def top_churn_reason(self) -> Optional[str]:
        """Identify most common churn reason."""
        if not self.churn_reasons:
            return None
        return max(self.churn_reasons, key=self.churn_reasons.get)  # type: ignore[arg-type]
    
    @computed_field  # type: ignore[misc]
    @property
    def churn_risk_status(self) -> str:
        """Assess overall churn risk status."""
        if self.churn_rate <= 3:
            return "low"
        elif self.churn_rate <= 7:
            return "moderate"
        elif self.churn_rate <= 12:
            return "high"
        else:
            return "critical"


class SystemHealthMetrics(BaseSchema):
    """
    Platform system health and performance metrics.
    
    Tracks technical performance, reliability, and capacity.
    """
    
    period: DateRangeFilter = Field(
        ...,
        description="Monitoring period"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp"
    )
    
    # Availability
    uptime_percentage: Annotated[Decimal, Field(ge=0, le=100), AfterValidator(lambda v: round(v, 4))] = Field(
        ...,
        description="System uptime percentage"
    )
    downtime_minutes: int = Field(
        ...,
        ge=0,
        description="Total downtime in minutes"
    )
    incident_count: int = Field(
        0,
        ge=0,
        description="Number of incidents in period"
    )
    
    # Performance
    average_response_time_ms: DecimalNonNegative = Field(
        ...,
        description="Average API response time in milliseconds"
    )
    p50_response_time_ms: DecimalNonNegative = Field(
        ...,
        description="50th percentile response time"
    )
    p95_response_time_ms: DecimalNonNegative = Field(
        ...,
        description="95th percentile response time"
    )
    p99_response_time_ms: DecimalNonNegative = Field(
        ...,
        description="99th percentile response time"
    )
    
    # Error rates
    error_rate_percentage: Annotated[Decimal, Field(ge=0, le=100), AfterValidator(lambda v: round(v, 4))] = Field(
        ...,
        description="Overall error rate percentage"
    )
    server_error_rate: Annotated[Decimal, Field(ge=0, le=100), AfterValidator(lambda v: round(v, 4))] = Field(
        ...,
        description="5xx error rate percentage"
    )
    client_error_rate: Annotated[Decimal, Field(ge=0, le=100), AfterValidator(lambda v: round(v, 4))] = Field(
        ...,
        description="4xx error rate percentage"
    )
    
    # Resource utilization
    avg_cpu_usage_percent: Optional[DecimalPercentage] = Field(
        None,
        description="Average CPU usage percentage"
    )
    peak_cpu_usage_percent: Optional[DecimalPercentage] = Field(
        None,
        description="Peak CPU usage"
    )
    avg_memory_usage_percent: Optional[DecimalPercentage] = Field(
        None,
        description="Average memory usage percentage"
    )
    peak_memory_usage_percent: Optional[DecimalPercentage] = Field(
        None,
        description="Peak memory usage"
    )
    
    # Database performance
    avg_db_query_time_ms: Optional[DecimalNonNegative] = Field(
        None,
        description="Average database query time"
    )
    slow_query_count: Optional[int] = Field(
        None,
        ge=0,
        description="Number of slow queries (>1s)"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def health_status(self) -> str:
        """Overall system health status."""
        if self.uptime_percentage >= Decimal("99.9") and self.error_rate_percentage <= Decimal("0.1"):
            return "excellent"
        elif self.uptime_percentage >= Decimal("99.5") and self.error_rate_percentage <= Decimal("0.5"):
            return "good"
        elif self.uptime_percentage >= Decimal("99.0") and self.error_rate_percentage <= Decimal("1.0"):
            return "fair"
        else:
            return "poor"
    
    @computed_field  # type: ignore[misc]
    @property
    def performance_grade(self) -> str:
        """Performance grade based on response times."""
        avg_time = float(self.average_response_time_ms)
        
        if avg_time <= 100:
            return "A"
        elif avg_time <= 200:
            return "B"
        elif avg_time <= 500:
            return "C"
        elif avg_time <= 1000:
            return "D"
        else:
            return "F"


class RevenueMetrics(BaseSchema):
    """
    Platform-wide revenue metrics and analysis.
    
    Aggregates revenue data across all tenants for
    financial planning and reporting.
    """
    
    period: DateRangeFilter = Field(
        ...,
        description="Revenue period"
    )
    
    # Total revenue
    total_revenue: DecimalNonNegative = Field(
        ...,
        description="Total platform revenue"
    )
    subscription_revenue: DecimalNonNegative = Field(
        ...,
        description="Revenue from subscriptions"
    )
    transaction_fees: DecimalNonNegative = Field(
        0,
        description="Revenue from transaction fees"
    )
    other_revenue: DecimalNonNegative = Field(
        0,
        description="Other revenue sources"
    )
    
    # MRR metrics
    mrr: DecimalNonNegative = Field(
        ...,
        description="Monthly Recurring Revenue"
    )
    arr: DecimalNonNegative = Field(
        ...,
        description="Annual Recurring Revenue"
    )
    
    # Revenue by plan
    revenue_by_plan: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Revenue breakdown by subscription plan"
    )
    
    # Customer metrics
    arpu: DecimalNonNegative = Field(
        ...,
        description="Average Revenue Per User (monthly)"
    )
    ltv: Optional[DecimalNonNegative] = Field(
        None,
        description="Lifetime Value estimate"
    )
    
    # Cohort analysis
    new_customer_revenue: DecimalNonNegative = Field(
        0,
        description="Revenue from new customers"
    )
    expansion_revenue: DecimalNonNegative = Field(
        0,
        description="Revenue from upgrades/expansion"
    )
    churned_revenue: DecimalNonNegative = Field(
        0,
        description="Revenue lost to churn"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def revenue_diversity_score(self) -> Decimal:
        """
        Calculate revenue diversification score (0-100).
        
        Higher score indicates better diversification across plans.
        """
        if not self.revenue_by_plan or self.total_revenue == 0:
            return Decimal("0.00")
        
        # Calculate Herfindahl index (lower = more diverse)
        total = float(self.total_revenue)
        herfindahl = sum(
            (float(rev) / total) ** 2
            for rev in self.revenue_by_plan.values()
        )
        
        # Convert to 0-100 scale (invert so higher is better)
        diversity = (1 - herfindahl) * 100
        return round(Decimal(str(diversity)), 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def net_new_mrr(self) -> Decimal:
        """Calculate net new MRR."""
        return (
            self.new_customer_revenue +
            self.expansion_revenue -
            self.churned_revenue
        )


class PlatformUsageAnalytics(BaseSchema):
    """
    Platform usage and engagement analytics.
    
    Tracks how tenants and users interact with the platform
    for product optimization and support planning.
    """
    
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp"
    )
    
    # Traffic metrics
    total_requests: int = Field(
        ...,
        ge=0,
        description="Total API requests in period"
    )
    unique_sessions: int = Field(
        ...,
        ge=0,
        description="Unique user sessions"
    )
    avg_requests_per_minute: DecimalNonNegative = Field(
        ...,
        description="Average requests per minute"
    )
    peak_requests_per_minute: int = Field(
        0,
        ge=0,
        description="Peak requests per minute"
    )
    
    # Error tracking
    api_error_rate: Annotated[Decimal, Field(ge=0, le=100), AfterValidator(lambda v: round(v, 4))] = Field(
        ...,
        description="API error rate percentage"
    )
    total_errors: int = Field(
        0,
        ge=0,
        description="Total error count"
    )
    
    # Module usage
    requests_by_module: Dict[str, int] = Field(
        default_factory=dict,
        description="Request count by module/feature"
    )
    
    # Feature adoption
    feature_adoption_rates: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Adoption rate by feature (%)"
    )
    
    # Performance
    avg_response_time_ms: DecimalNonNegative = Field(
        ...,
        description="Average response time"
    )
    p95_response_time_ms: DecimalNonNegative = Field(
        ...,
        description="95th percentile response time"
    )
    p99_response_time_ms: DecimalNonNegative = Field(
        ...,
        description="99th percentile response time"
    )
    
    # Resource usage
    avg_cpu_usage_percent: Optional[DecimalPercentage] = Field(
        None,
        description="Average CPU usage"
    )
    avg_memory_usage_percent: Optional[DecimalPercentage] = Field(
        None,
        description="Average memory usage"
    )
    
    # Storage
    total_storage_used_gb: Optional[DecimalNonNegative] = Field(
        None,
        description="Total storage used in GB"
    )
    avg_storage_per_tenant_gb: Optional[DecimalNonNegative] = Field(
        None,
        description="Average storage per tenant"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def most_used_module(self) -> Optional[str]:
        """Identify most frequently used module."""
        if not self.requests_by_module:
            return None
        return max(self.requests_by_module, key=self.requests_by_module.get)  # type: ignore[arg-type]
    
    @computed_field  # type: ignore[misc]
    @property
    def least_adopted_features(self) -> List[str]:
        """Identify features with low adoption (< 20%)."""
        return [
            feature for feature, rate in self.feature_adoption_rates.items()
            if rate < 20
        ]
    
    @computed_field  # type: ignore[misc]
    @property
    def platform_health_indicator(self) -> str:
        """Overall platform health indicator."""
        if (
            self.api_error_rate <= Decimal("0.1") and
            float(self.avg_response_time_ms) <= 200
        ):
            return "healthy"
        elif (
            self.api_error_rate <= Decimal("0.5") and
            float(self.avg_response_time_ms) <= 500
        ):
            return "stable"
        elif (
            self.api_error_rate <= Decimal("1.0") and
            float(self.avg_response_time_ms) <= 1000
        ):
            return "degraded"
        else:
            return "critical"