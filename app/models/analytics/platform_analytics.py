"""
Platform-wide analytics models for super admin oversight.

Provides persistent storage for:
- Multi-tenant statistics
- Growth metrics and trends
- Platform usage analytics
- System performance metrics
- Revenue aggregation
- Churn analysis
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, String, Integer, Numeric, DateTime, Date, Boolean,
    ForeignKey, Text, Index, CheckConstraint, UniqueConstraint,
    Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.models.analytics.base_analytics import (
    BaseAnalyticsModel,
    AnalyticsMixin,
    MetricMixin,
    TrendMixin,
    CachedAnalyticsMixin
)


class TenantMetrics(BaseAnalyticsModel, AnalyticsMixin):
    """
    Individual tenant (hostel) performance metrics.
    
    Per-tenant analytics for platform-level aggregation
    and comparison.
    """
    
    __tablename__ = 'tenant_metrics'
    
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey('hostels.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="Hostel/tenant ID"
    )
    
    tenant_name = Column(
        String(255),
        nullable=False,
        comment="Tenant name"
    )
    
    # Subscription info
    subscription_plan = Column(
        String(50),
        nullable=False,
        comment="Current subscription plan"
    )
    
    subscription_status = Column(
        String(50),
        nullable=False,
        comment="Subscription status"
    )
    
    subscription_start_date = Column(
        Date,
        nullable=False,
        comment="Subscription start"
    )
    
    subscription_mrr = Column(
        Numeric(precision=12, scale=2),
        nullable=False,
        comment="Monthly recurring revenue"
    )
    
    # Usage metrics
    total_students = Column(Integer, nullable=False, default=0)
    active_students = Column(Integer, nullable=False, default=0)
    total_beds = Column(Integer, nullable=False, default=0)
    
    occupancy_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Current occupancy rate"
    )
    
    # Activity metrics
    last_login = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last admin login"
    )
    
    daily_active_users = Column(
        Integer,
        nullable=False,
        default=0,
        comment="DAU (last 24h)"
    )
    
    monthly_active_users = Column(
        Integer,
        nullable=False,
        default=0,
        comment="MAU (last 30 days)"
    )
    
    # Health indicators
    payment_status = Column(
        SQLEnum('current', 'overdue', 'suspended', name='payment_status_enum'),
        nullable=False,
        comment="Payment status"
    )
    
    health_score = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Overall tenant health (0-100)"
    )
    
    churn_risk_score = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Churn risk score (0-100)"
    )
    
    # Calculated fields
    is_at_risk = Column(
        Boolean,
        nullable=True,
        comment="At risk of churning"
    )
    
    revenue_per_bed = Column(
        Numeric(precision=12, scale=2),
        nullable=True,
        comment="MRR per bed"
    )
    
    engagement_status = Column(
        String(20),
        nullable=True,
        comment="highly_active, active, moderate, low, inactive"
    )
    
    __table_args__ = (
        Index('ix_tenant_metrics_tenant_period', 'tenant_id', 'period_start', 'period_end'),
        CheckConstraint(
            'active_students <= total_students',
            name='ck_tenant_metrics_students_valid'
        ),
    )


class PlatformMetrics(BaseAnalyticsModel, AnalyticsMixin, CachedAnalyticsMixin):
    """
    High-level platform metrics across all tenants.
    
    Aggregate statistics for platform monitoring
    and strategic decisions.
    """
    
    __tablename__ = 'platform_metrics'
    
    # Tenant metrics
    total_hostels = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total registered hostels"
    )
    
    active_hostels = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Currently active hostels"
    )
    
    hostels_on_trial = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Hostels on trial"
    )
    
    suspended_hostels = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Suspended hostels"
    )
    
    churned_hostels = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Churned in period"
    )
    
    # User metrics
    total_users = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total platform users"
    )
    
    total_students = Column(Integer, nullable=False, default=0)
    total_supervisors = Column(Integer, nullable=False, default=0)
    total_admins = Column(Integer, nullable=False, default=0)
    total_visitors = Column(Integer, nullable=False, default=0)
    
    # Engagement
    avg_daily_active_users = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Average DAU"
    )
    
    avg_monthly_active_users = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Average MAU"
    )
    
    peak_concurrent_sessions = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Peak concurrent sessions"
    )
    
    # Capacity
    total_beds_platform = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total platform bed capacity"
    )
    
    total_occupied_beds = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total occupied beds"
    )
    
    platform_occupancy_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        default=0,
        comment="Platform-wide occupancy"
    )
    
    # Calculated fields
    activation_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Active hostels percentage"
    )
    
    trial_conversion_potential = Column(
        Integer,
        nullable=True,
        comment="Estimated trial conversions"
    )
    
    __table_args__ = (
        Index('ix_platform_metrics_period', 'period_start', 'period_end'),
        UniqueConstraint(
            'period_start',
            'period_end',
            name='uq_platform_metrics_unique'
        ),
    )


class MonthlyMetric(BaseAnalyticsModel):
    """
    Monthly metric data point for trend analysis.
    
    Single metric value for a specific month.
    """
    
    __tablename__ = 'monthly_metrics'
    
    growth_metrics_id = Column(
        UUID(as_uuid=True),
        ForeignKey('growth_metrics.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    
    metric_key = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Metric identifier"
    )
    
    month = Column(
        String(7),
        nullable=False,
        index=True,
        comment="Month in YYYY-MM format"
    )
    
    value = Column(
        Numeric(precision=20, scale=4),
        nullable=False,
        comment="Metric value"
    )
    
    label = Column(
        String(100),
        nullable=True,
        comment="Display label"
    )
    
    __table_args__ = (
        Index('ix_monthly_metric_key_month', 'metric_key', 'month'),
    )


class GrowthMetrics(BaseAnalyticsModel, AnalyticsMixin, CachedAnalyticsMixin):
    """
    Growth metrics and trends over time.
    
    Detailed growth analysis for strategic planning
    and investor reporting.
    """
    
    __tablename__ = 'growth_metrics'
    
    # Hostel growth
    new_hostels = Column(
        Integer,
        nullable=False,
        default=0,
        comment="New hostels in period"
    )
    
    churned_hostels = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Churned hostels"
    )
    
    net_hostel_growth = Column(
        Integer,
        nullable=False,
        comment="Net hostel change"
    )
    
    hostel_growth_rate = Column(
        Numeric(precision=10, scale=4),
        nullable=False,
        comment="Hostel growth rate %"
    )
    
    # Revenue growth
    total_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        comment="Total revenue"
    )
    
    previous_period_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        comment="Previous period revenue"
    )
    
    revenue_growth_amount = Column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Revenue growth amount"
    )
    
    revenue_growth_rate = Column(
        Numeric(precision=10, scale=4),
        nullable=False,
        comment="Revenue growth rate %"
    )
    
    # User growth
    new_users = Column(
        Integer,
        nullable=False,
        default=0,
        comment="New users in period"
    )
    
    churned_users = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Churned users"
    )
    
    net_user_growth = Column(
        Integer,
        nullable=False,
        comment="Net user change"
    )
    
    user_growth_rate = Column(
        Numeric(precision=10, scale=4),
        nullable=False,
        comment="User growth rate %"
    )
    
    # MRR metrics
    current_mrr = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        comment="Current MRR"
    )
    
    previous_mrr = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        comment="Previous MRR"
    )
    
    mrr_growth_rate = Column(
        Numeric(precision=10, scale=4),
        nullable=False,
        comment="MRR growth rate %"
    )
    
    # Calculated fields
    is_growing = Column(
        Boolean,
        nullable=True,
        comment="Whether platform is growing"
    )
    
    growth_health_score = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Overall growth health (0-100)"
    )
    
    compound_annual_growth_rate = Column(
        Numeric(precision=10, scale=4),
        nullable=True,
        comment="CAGR if applicable"
    )
    
    __table_args__ = (
        Index('ix_growth_metrics_period', 'period_start', 'period_end'),
        UniqueConstraint(
            'period_start',
            'period_end',
            name='uq_growth_metrics_unique'
        ),
    )
    
    # Relationships
    monthly_data = relationship(
        'MonthlyMetric',
        foreign_keys=[MonthlyMetric.growth_metrics_id],
        cascade='all, delete-orphan'
    )


class ChurnAnalysis(BaseAnalyticsModel, AnalyticsMixin, CachedAnalyticsMixin):
    """
    Customer churn analysis and prediction.
    
    Insights into churn patterns and at-risk tenants.
    """
    
    __tablename__ = 'churn_analysis'
    
    # Churn metrics
    churned_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Churned tenants"
    )
    
    churn_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Churn rate %"
    )
    
    revenue_churned = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        comment="MRR lost to churn"
    )
    
    # Churn reasons
    churn_reasons = Column(
        JSONB,
        nullable=True,
        comment="Churn count by reason"
    )
    
    # At-risk analysis
    at_risk_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Tenants at risk"
    )
    
    # Retention
    retention_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Retention rate %"
    )
    
    # Insights
    top_churn_reason = Column(
        String(100),
        nullable=True,
        comment="Most common churn reason"
    )
    
    churn_risk_status = Column(
        String(20),
        nullable=True,
        comment="low, moderate, high, critical"
    )
    
    __table_args__ = (
        Index('ix_churn_analysis_period', 'period_start', 'period_end'),
    )


class SystemHealthMetrics(BaseAnalyticsModel, AnalyticsMixin, CachedAnalyticsMixin):
    """
    Platform system health and performance metrics.
    
    Technical performance, reliability, and capacity tracking.
    """
    
    __tablename__ = 'system_health_metrics'
    
    # Availability
    uptime_percentage = Column(
        Numeric(precision=7, scale=4),
        nullable=False,
        comment="System uptime %"
    )
    
    downtime_minutes = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total downtime"
    )
    
    incident_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of incidents"
    )
    
    # Performance
    average_response_time_ms = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Average API response time"
    )
    
    p50_response_time_ms = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="50th percentile response time"
    )
    
    p95_response_time_ms = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="95th percentile response time"
    )
    
    p99_response_time_ms = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="99th percentile response time"
    )
    
    # Error rates
    error_rate_percentage = Column(
        Numeric(precision=7, scale=4),
        nullable=False,
        comment="Overall error rate %"
    )
    
    server_error_rate = Column(
        Numeric(precision=7, scale=4),
        nullable=False,
        comment="5xx error rate %"
    )
    
    client_error_rate = Column(
        Numeric(precision=7, scale=4),
        nullable=False,
        comment="4xx error rate %"
    )
    
    # Resource utilization
    avg_cpu_usage_percent = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Average CPU usage"
    )
    
    peak_cpu_usage_percent = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Peak CPU usage"
    )
    
    avg_memory_usage_percent = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Average memory usage"
    )
    
    peak_memory_usage_percent = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Peak memory usage"
    )
    
    # Database performance
    avg_db_query_time_ms = Column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Average DB query time"
    )
    
    slow_query_count = Column(
        Integer,
        nullable=True,
        comment="Slow queries (>1s)"
    )
    
    # Calculated fields
    health_status = Column(
        String(20),
        nullable=True,
        comment="excellent, good, fair, poor"
    )
    
    performance_grade = Column(
        String(5),
        nullable=True,
        comment="Performance letter grade"
    )
    
    __table_args__ = (
        Index('ix_system_health_period', 'period_start', 'period_end'),
    )


class PlatformUsageAnalytics(
    BaseAnalyticsModel,
    AnalyticsMixin,
    CachedAnalyticsMixin
):
    """
    Platform usage and engagement analytics.
    
    Tracks how tenants and users interact with platform
    for product optimization.
    """
    
    __tablename__ = 'platform_usage_analytics'
    
    # Traffic metrics
    total_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total API requests"
    )
    
    unique_sessions = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Unique sessions"
    )
    
    avg_requests_per_minute = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Average requests/min"
    )
    
    peak_requests_per_minute = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Peak requests/min"
    )
    
    # Error tracking
    api_error_rate = Column(
        Numeric(precision=7, scale=4),
        nullable=False,
        comment="API error rate %"
    )
    
    total_errors = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total errors"
    )
    
    # Module usage
    requests_by_module = Column(
        JSONB,
        nullable=True,
        comment="Request count by module"
    )
    
    # Feature adoption
    feature_adoption_rates = Column(
        JSONB,
        nullable=True,
        comment="Adoption rate by feature"
    )
    
    # Performance
    avg_response_time_ms = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Average response time"
    )
    
    p95_response_time_ms = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="95th percentile"
    )
    
    p99_response_time_ms = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="99th percentile"
    )
    
    # Resource usage
    avg_cpu_usage_percent = Column(
        Numeric(precision=5, scale=2),
        nullable=True
    )
    
    avg_memory_usage_percent = Column(
        Numeric(precision=5, scale=2),
        nullable=True
    )
    
    # Storage
    total_storage_used_gb = Column(
        Numeric(precision=12, scale=2),
        nullable=True,
        comment="Total storage in GB"
    )
    
    avg_storage_per_tenant_gb = Column(
        Numeric(precision=12, scale=2),
        nullable=True,
        comment="Average storage per tenant"
    )
    
    # Insights
    most_used_module = Column(
        String(100),
        nullable=True,
        comment="Most used module"
    )
    
    least_adopted_features = Column(
        JSONB,
        nullable=True,
        comment="Features with low adoption"
    )
    
    platform_health_indicator = Column(
        String(20),
        nullable=True,
        comment="healthy, stable, degraded, critical"
    )
    
    __table_args__ = (
        Index('ix_usage_analytics_period', 'period_start', 'period_end'),
    )


class RevenueMetrics(BaseAnalyticsModel, AnalyticsMixin, CachedAnalyticsMixin):
    """
    Platform-wide revenue metrics and analysis.
    
    Aggregates revenue data across all tenants.
    """
    
    __tablename__ = 'revenue_metrics'
    
    # Total revenue
    total_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        comment="Total platform revenue"
    )
    
    subscription_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        comment="Subscription revenue"
    )
    
    transaction_fees = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Transaction fee revenue"
    )
    
    other_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Other revenue"
    )
    
    # MRR/ARR
    mrr = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        comment="Monthly Recurring Revenue"
    )
    
    arr = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        comment="Annual Recurring Revenue"
    )
    
    # Revenue by plan
    revenue_by_plan = Column(
        JSONB,
        nullable=True,
        comment="Revenue by subscription plan"
    )
    
    # Customer metrics
    arpu = Column(
        Numeric(precision=12, scale=2),
        nullable=False,
        comment="Average Revenue Per User"
    )
    
    ltv = Column(
        Numeric(precision=12, scale=2),
        nullable=True,
        comment="Lifetime Value estimate"
    )
    
    # Cohort analysis
    new_customer_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Revenue from new customers"
    )
    
    expansion_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Revenue from upgrades"
    )
    
    churned_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Revenue lost to churn"
    )
    
    # Calculated fields
    revenue_diversity_score = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Revenue diversification (0-100)"
    )
    
    net_new_mrr = Column(
        Numeric(precision=15, scale=4),
        nullable=True,
        comment="Net new MRR"
    )
    
    __table_args__ = (
        Index('ix_revenue_metrics_period', 'period_start', 'period_end'),
    )