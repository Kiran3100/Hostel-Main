"""
Dashboard analytics models for unified metrics display.

Provides persistent storage for:
- Generic KPI tracking
- Dashboard widgets and configurations
- Time-series metrics
- Alert notifications
- Role-specific dashboard data
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
    HostelScopedMixin,
    CachedAnalyticsMixin
)


class DashboardKPI(BaseAnalyticsModel, MetricMixin, HostelScopedMixin):
    """
    Generic KPI storage for dashboard display.
    
    Flexible KPI model supporting various metric types
    with target tracking and trend indicators.
    """
    
    __tablename__ = 'dashboard_kpis'
    
    kpi_key = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique identifier for the KPI"
    )
    
    kpi_name = Column(
        String(255),
        nullable=False,
        comment="Display name for the KPI"
    )
    
    kpi_category = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Category grouping (financial, operational, etc.)"
    )
    
    # Trend information
    trend_direction = Column(
        SQLEnum('up', 'down', 'stable', name='kpi_trend_direction'),
        nullable=True
    )
    
    trend_percentage = Column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Percentage change vs previous period"
    )
    
    # Display configuration
    format_pattern = Column(
        String(50),
        nullable=True,
        comment="Display format pattern"
    )
    
    icon = Column(String(50), nullable=True, comment="Icon identifier")
    color = Column(String(7), nullable=True, comment="Hex color code")
    
    good_when = Column(
        SQLEnum(
            'higher_is_better',
            'lower_is_better',
            'closer_to_target',
            name='kpi_interpretation'
        ),
        nullable=True,
        comment="KPI interpretation rule"
    )
    
    # Status indicators
    is_on_target = Column(
        Boolean,
        nullable=True,
        comment="Whether current value meets target"
    )
    
    performance_status = Column(
        String(20),
        nullable=True,
        comment="excellent, good, warning, critical"
    )
    
    # Period tracking
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    
    __table_args__ = (
        Index('ix_dashboard_kpi_hostel_key', 'hostel_id', 'kpi_key'),
        Index('ix_dashboard_kpi_period', 'period_start', 'period_end'),
        UniqueConstraint(
            'hostel_id',
            'kpi_key',
            'period_start',
            'period_end',
            name='uq_dashboard_kpi_unique'
        ),
    )


class TimeseriesMetric(BaseAnalyticsModel):
    """
    Time-series data points for charts and trends.
    
    Stores sequential metric values for visualization
    and trend analysis.
    """
    
    __tablename__ = 'timeseries_metrics'
    
    metric_key = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Metric identifier"
    )
    
    hostel_id = Column(
        UUID(as_uuid=True),
        ForeignKey('hostels.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    
    data_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Date of the data point"
    )
    
    value = Column(
        Numeric(precision=20, scale=4),
        nullable=False,
        comment="Metric value"
    )
    
    label = Column(
        String(100),
        nullable=True,
        comment="Optional label for the point"
    )
    
    metadata = Column(
        JSONB,
        nullable=True,
        comment="Additional metadata"
    )
    
    __table_args__ = (
        Index('ix_timeseries_hostel_key_date', 'hostel_id', 'metric_key', 'data_date'),
        UniqueConstraint(
            'hostel_id',
            'metric_key',
            'data_date',
            name='uq_timeseries_unique'
        ),
    )


class DashboardWidget(BaseAnalyticsModel):
    """
    Dashboard widget configuration and state.
    
    Stores user-specific or role-specific widget
    configurations for customizable dashboards.
    """
    
    __tablename__ = 'dashboard_widgets'
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
        comment="User ID for personalized widgets"
    )
    
    role = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Role for role-based widgets"
    )
    
    hostel_id = Column(
        UUID(as_uuid=True),
        ForeignKey('hostels.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    
    widget_id = Column(
        String(100),
        nullable=False,
        comment="Unique widget identifier"
    )
    
    widget_type = Column(
        SQLEnum('kpi', 'chart', 'table', 'list', 'stat', name='widget_type_enum'),
        nullable=False,
        comment="Widget type"
    )
    
    title = Column(
        String(255),
        nullable=False,
        comment="Widget title"
    )
    
    position = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Display position/order"
    )
    
    size = Column(
        SQLEnum('small', 'medium', 'large', 'full', name='widget_size_enum'),
        nullable=False,
        default='medium',
        comment="Widget size"
    )
    
    data_source = Column(
        String(100),
        nullable=False,
        comment="Data source identifier"
    )
    
    refresh_interval_seconds = Column(
        Integer,
        nullable=True,
        comment="Auto-refresh interval"
    )
    
    is_visible = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Widget visibility"
    )
    
    configuration = Column(
        JSONB,
        nullable=True,
        comment="Widget-specific configuration"
    )
    
    __table_args__ = (
        Index('ix_dashboard_widget_user', 'user_id'),
        Index('ix_dashboard_widget_role', 'role'),
        CheckConstraint(
            'position >= 0',
            name='ck_dashboard_widget_position_valid'
        ),
    )


class AlertNotification(BaseAnalyticsModel):
    """
    Dashboard alert notifications.
    
    Stores system-generated alerts and notifications
    for dashboard display.
    """
    
    __tablename__ = 'alert_notifications'
    
    hostel_id = Column(
        UUID(as_uuid=True),
        ForeignKey('hostels.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    
    severity = Column(
        SQLEnum('info', 'warning', 'error', 'critical', name='alert_severity_enum'),
        nullable=False,
        index=True,
        comment="Alert severity level"
    )
    
    title = Column(
        String(255),
        nullable=False,
        comment="Alert title"
    )
    
    message = Column(
        Text,
        nullable=False,
        comment="Alert message"
    )
    
    action_url = Column(
        String(500),
        nullable=True,
        comment="URL for alert action"
    )
    
    action_label = Column(
        String(100),
        nullable=True,
        comment="Label for action button"
    )
    
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Alert expiration time"
    )
    
    is_dismissed = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether alert has been dismissed"
    )
    
    dismissed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Dismissal timestamp"
    )
    
    dismissed_by = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        comment="User who dismissed the alert"
    )
    
    alert_metadata = Column(
        JSONB,
        nullable=True,
        comment="Additional alert metadata"
    )
    
    __table_args__ = (
        Index('ix_alert_hostel_severity', 'hostel_id', 'severity'),
        Index('ix_alert_expires_at', 'expires_at'),
    )


class QuickStats(BaseAnalyticsModel, HostelScopedMixin, CachedAnalyticsMixin):
    """
    Quick statistics for dashboard cards.
    
    Cached snapshot metrics for immediate dashboard
    visibility into system state.
    """
    
    __tablename__ = 'quick_stats'
    
    # Hostel metrics
    total_hostels = Column(Integer, nullable=False, default=0)
    active_hostels = Column(Integer, nullable=False, default=0)
    
    # Student metrics
    total_students = Column(Integer, nullable=False, default=0)
    active_students = Column(Integer, nullable=False, default=0)
    
    # Visitor metrics
    total_visitors = Column(Integer, nullable=False, default=0)
    active_visitors = Column(Integer, nullable=False, default=0)
    
    # Daily operations
    todays_check_ins = Column(Integer, nullable=False, default=0)
    todays_check_outs = Column(Integer, nullable=False, default=0)
    
    # Issues
    open_complaints = Column(Integer, nullable=False, default=0)
    urgent_complaints = Column(Integer, nullable=False, default=0)
    pending_maintenance = Column(Integer, nullable=False, default=0)
    overdue_maintenance = Column(Integer, nullable=False, default=0)
    
    # Financial
    todays_revenue = Column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=0
    )
    
    monthly_revenue = Column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=0
    )
    
    outstanding_payments = Column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=0
    )
    
    overdue_payments = Column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=0
    )
    
    # Calculated fields
    occupancy_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Approximate occupancy rate"
    )
    
    complaint_urgency_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Percentage of urgent complaints"
    )
    
    payment_collection_health = Column(
        String(20),
        nullable=True,
        comment="Payment collection health status"
    )
    
    snapshot_date = Column(
        Date,
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Date of snapshot"
    )
    
    __table_args__ = (
        Index('ix_quick_stats_hostel_date', 'hostel_id', 'snapshot_date'),
        UniqueConstraint(
            'hostel_id',
            'snapshot_date',
            name='uq_quick_stats_unique'
        ),
    )


class RoleSpecificDashboard(
    BaseAnalyticsModel,
    HostelScopedMixin,
    CachedAnalyticsMixin
):
    """
    Role-specific dashboard configurations.
    
    Stores customized dashboard data and layout
    for different user roles.
    """
    
    __tablename__ = 'role_specific_dashboards'
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    role = Column(
        String(50),
        nullable=False,
        index=True,
        comment="User role"
    )
    
    # Dashboard sections
    sections = Column(
        JSONB,
        nullable=True,
        comment="Dashboard section identifiers"
    )
    
    # Aggregated data
    metrics_by_section = Column(
        JSONB,
        nullable=True,
        comment="Section-wise metrics"
    )
    
    kpis_by_section = Column(
        JSONB,
        nullable=True,
        comment="Section-wise KPIs"
    )
    
    # Permissions
    accessible_features = Column(
        JSONB,
        nullable=True,
        comment="Accessible features list"
    )
    
    # Preferences
    default_section = Column(
        String(100),
        nullable=True,
        comment="Default section to display"
    )
    
    layout_preferences = Column(
        JSONB,
        nullable=True,
        comment="User layout preferences"
    )
    
    # Alerts
    has_critical_alerts = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Has critical alerts flag"
    )
    
    total_kpi_count = Column(
        Integer,
        nullable=True,
        comment="Total KPIs count"
    )
    
    __table_args__ = (
        Index('ix_role_dashboard_user_role', 'user_id', 'role'),
        UniqueConstraint(
            'user_id',
            'hostel_id',
            name='uq_role_dashboard_unique'
        ),
    )