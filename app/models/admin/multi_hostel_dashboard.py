"""
Multi-Hostel Dashboard Model

Provides aggregated dashboard data, cross-hostel analytics, and
performance comparisons for multi-hostel admin portfolio management.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    String,
    ForeignKey,
    Text,
    Numeric,
    Index,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.admin.admin_user import AdminUser
    from app.models.hostel.hostel import Hostel

__all__ = [
    "MultiHostelDashboard",
    "CrossHostelMetric",
    "HostelPerformanceRanking",
    "DashboardWidget",
    "DashboardSnapshot",
]


class MultiHostelDashboard(TimestampModel, UUIDMixin):
    """
    Aggregated dashboard data for multi-hostel admin.
    
    Pre-computed portfolio-wide statistics with real-time updates
    for efficient dashboard rendering and decision-making.
    """
    
    __tablename__ = "multi_hostel_dashboards"
    __table_args__ = (
        UniqueConstraint("admin_id", "dashboard_date", name="uq_admin_dashboard_date"),
        Index("idx_dashboard_admin_id", "admin_id"),
        Index("idx_dashboard_date", "dashboard_date"),
        Index("idx_dashboard_updated", "last_updated"),
    )
    
    # Foreign Keys
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin user ID"
    )
    
    # Dashboard Period
    dashboard_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        default=date.today,
        index=True,
        comment="Dashboard date"
    )
    
    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Reporting period start"
    )
    
    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Reporting period end"
    )
    
    # Portfolio Statistics
    total_hostels: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total hostels managed"
    )
    
    active_hostels: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Active hostel assignments"
    )
    
    # Student Statistics
    total_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total students across all hostels"
    )
    
    active_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Active students"
    )
    
    total_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total bed capacity"
    )
    
    # Occupancy
    avg_occupancy_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average occupancy across hostels"
    )
    
    highest_occupancy_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Highest occupancy among hostels"
    )
    
    lowest_occupancy_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Lowest occupancy among hostels"
    )
    
    # Workload
    total_pending_tasks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total pending tasks"
    )
    
    total_urgent_alerts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total urgent alerts"
    )
    
    total_open_complaints: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total open complaints"
    )
    
    tasks_completed_today: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Tasks completed today"
    )
    
    # Financial Summary
    total_revenue_this_month: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total revenue this month"
    )
    
    total_outstanding_payments: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total outstanding payments"
    )
    
    avg_collection_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average collection rate (%)"
    )
    
    # Satisfaction Metrics
    avg_student_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        comment="Average student rating across hostels"
    )
    
    avg_admin_satisfaction_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Average admin satisfaction score"
    )
    
    # Performance Indicators
    portfolio_health_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Overall portfolio health (0-100)"
    )
    
    attention_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="low",
        comment="Overall attention level (low, medium, high, critical)"
    )
    
    hostels_requiring_attention: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of hostels requiring attention"
    )
    
    # Trends
    occupancy_trend: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Portfolio occupancy trend"
    )
    
    revenue_trend: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Portfolio revenue trend"
    )
    
    # Top/Bottom Performers
    top_performer_hostel_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="SET NULL"),
        nullable=True,
        comment="Best performing hostel"
    )
    
    top_performer_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Top performer score"
    )
    
    bottom_performer_hostel_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="SET NULL"),
        nullable=True,
        comment="Bottom performing hostel"
    )
    
    bottom_performer_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Bottom performer score"
    )
    
    # Detailed Breakdown
    hostel_breakdown: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Per-hostel detailed statistics"
    )
    
    metric_comparisons: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Cross-hostel metric comparisons"
    )
    
    # Cache Management
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Last update timestamp"
    )
    
    cache_ttl_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300,
        comment="Cache TTL (default 5 minutes)"
    )
    
    build_duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Dashboard build time (ms)"
    )
    
    # Relationships
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[admin_id]
    )
    
    top_performer: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[top_performer_hostel_id]
    )
    
    bottom_performer: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[bottom_performer_hostel_id]
    )
    
    cross_hostel_metrics: Mapped[List["CrossHostelMetric"]] = relationship(
        "CrossHostelMetric",
        back_populates="dashboard",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    performance_rankings: Mapped[List["HostelPerformanceRanking"]] = relationship(
        "HostelPerformanceRanking",
        back_populates="dashboard",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Hybrid Properties
    @hybrid_property
    def is_stale(self) -> bool:
        """Check if dashboard cache is stale."""
        age_seconds = (datetime.utcnow() - self.last_updated).total_seconds()
        return age_seconds > self.cache_ttl_seconds
    
    @hybrid_property
    def hostel_utilization_rate(self) -> Decimal:
        """Percentage of hostels that are actively managed."""
        if self.total_hostels == 0:
            return Decimal("0.00")
        rate = Decimal(self.active_hostels) / Decimal(self.total_hostels) * 100
        return rate.quantize(Decimal("0.01"))
    
    @hybrid_property
    def student_occupancy_rate(self) -> Decimal:
        """Overall bed occupancy rate."""
        if self.total_capacity == 0:
            return Decimal("0.00")
        rate = Decimal(self.active_students) / Decimal(self.total_capacity) * 100
        return rate.quantize(Decimal("0.01"))
    
    @hybrid_property
    def has_critical_issues(self) -> bool:
        """Check if portfolio has critical issues."""
        return (
            self.attention_level in ("high", "critical") or
            self.total_urgent_alerts > 0 or
            self.hostels_requiring_attention > 0
        )
    
    @hybrid_property
    def financial_health_indicator(self) -> str:
        """Financial health indicator."""
        if self.total_outstanding_payments > self.total_revenue_this_month:
            return "at_risk"
        elif self.total_outstanding_payments > self.total_revenue_this_month * Decimal("0.5"):
            return "watch"
        return "healthy"
    
    def __repr__(self) -> str:
        return (
            f"<MultiHostelDashboard(id={self.id}, admin_id={self.admin_id}, "
            f"date={self.dashboard_date}, hostels={self.total_hostels})>"
        )


class CrossHostelMetric(TimestampModel, UUIDMixin):
    """
    Cross-hostel metric comparison.
    
    Compares specific metrics across hostels with best/worst values
    and portfolio averages for performance analysis.
    """
    
    __tablename__ = "cross_hostel_metrics"
    __table_args__ = (
        UniqueConstraint("dashboard_id", "metric_name", name="uq_dashboard_metric"),
        Index("idx_cross_metric_dashboard_id", "dashboard_id"),
        Index("idx_cross_metric_name", "metric_name"),
    )
    
    # Foreign Keys
    dashboard_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("multi_hostel_dashboards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Dashboard ID"
    )
    
    # Metric Definition
    metric_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Metric name (occupancy, revenue, etc.)"
    )
    
    metric_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Metric category (operational, financial, satisfaction)"
    )
    
    display_unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Display unit (%, count, currency)"
    )
    
    # Portfolio Statistics
    portfolio_average: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Portfolio average"
    )
    
    portfolio_median: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Portfolio median"
    )
    
    portfolio_std_dev: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Standard deviation"
    )
    
    # Best Performer
    best_hostel_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="SET NULL"),
        nullable=True,
        comment="Best performing hostel"
    )
    
    best_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Best value"
    )
    
    # Worst Performer
    worst_hostel_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="SET NULL"),
        nullable=True,
        comment="Worst performing hostel"
    )
    
    worst_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Worst value"
    )
    
    # Variance Analysis
    value_range: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Range (best - worst)"
    )
    
    variation_coefficient: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Coefficient of variation (%)"
    )
    
    # Hostel Distribution
    hostel_values: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Per-hostel metric values"
    )
    
    # Relationships
    dashboard: Mapped["MultiHostelDashboard"] = relationship(
        "MultiHostelDashboard",
        back_populates="cross_hostel_metrics",
        lazy="select"
    )
    
    best_hostel: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[best_hostel_id]
    )
    
    worst_hostel: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[worst_hostel_id]
    )
    
    @hybrid_property
    def has_significant_variation(self) -> bool:
        """Check if metric shows significant variation."""
        return (
            self.variation_coefficient is not None and
            float(self.variation_coefficient) > 20.0
        )
    
    def __repr__(self) -> str:
        return (
            f"<CrossHostelMetric(id={self.id}, metric='{self.metric_name}', "
            f"avg={self.portfolio_average})>"
        )


class HostelPerformanceRanking(TimestampModel, UUIDMixin):
    """
    Performance ranking for individual hostels.
    
    Ranks hostels based on composite performance scores
    across multiple dimensions.
    """
    
    __tablename__ = "hostel_performance_rankings"
    __table_args__ = (
        UniqueConstraint("dashboard_id", "hostel_id", name="uq_dashboard_hostel_ranking"),
        Index("idx_ranking_dashboard_id", "dashboard_id"),
        Index("idx_ranking_hostel_id", "hostel_id"),
        Index("idx_ranking_rank", "overall_rank"),
        Index("idx_ranking_score", "overall_score"),
    )
    
    # Foreign Keys
    dashboard_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("multi_hostel_dashboards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Dashboard ID"
    )
    
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel ID"
    )
    
    # Overall Ranking
    overall_rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Overall rank (1 = best)"
    )
    
    overall_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        index=True,
        comment="Overall performance score (0-100)"
    )
    
    # Dimensional Scores
    occupancy_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Occupancy performance (0-100)"
    )
    
    financial_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Financial performance (0-100)"
    )
    
    operational_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Operational efficiency (0-100)"
    )
    
    satisfaction_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Student satisfaction (0-100)"
    )
    
    # Dimensional Rankings
    occupancy_rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Occupancy rank"
    )
    
    financial_rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Financial rank"
    )
    
    operational_rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Operational rank"
    )
    
    satisfaction_rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Satisfaction rank"
    )
    
    # Performance Category
    performance_category: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Performance category (excellent, good, fair, poor)"
    )
    
    # Trend
    rank_change: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Rank change from previous period"
    )
    
    score_change: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Score change from previous period"
    )
    
    # Key Metrics
    key_metrics: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Key performance metrics"
    )
    
    # Strengths and Weaknesses
    top_strengths: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Top 3 strengths"
    )
    
    areas_for_improvement: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Areas needing improvement"
    )
    
    # Relationships
    dashboard: Mapped["MultiHostelDashboard"] = relationship(
        "MultiHostelDashboard",
        back_populates="performance_rankings",
        lazy="select"
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
        foreign_keys=[hostel_id]
    )
    
    @hybrid_property
    def is_top_performer(self) -> bool:
        """Check if this is a top performer."""
        return self.overall_rank <= 3
    
    @hybrid_property
    def is_improving(self) -> bool:
        """Check if performance is improving."""
        return self.rank_change < 0 or self.score_change > 0  # Negative rank change = improvement
    
    def __repr__(self) -> str:
        return (
            f"<HostelPerformanceRanking(id={self.id}, hostel_id={self.hostel_id}, "
            f"rank={self.overall_rank}, score={self.overall_score})>"
        )


class DashboardWidget(TimestampModel, UUIDMixin):
    """
    Configurable dashboard widget.
    
    Allows admins to customize their multi-hostel dashboard
    with personalized widgets and layouts.
    """
    
    __tablename__ = "dashboard_widgets"
    __table_args__ = (
        Index("idx_widget_admin_id", "admin_id"),
        Index("idx_widget_type", "widget_type"),
        Index("idx_widget_position", "position_row", "position_col"),
    )
    
    # Foreign Keys
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin user ID"
    )
    
    # Widget Definition
    widget_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Widget type (chart, table, kpi, etc.)"
    )
    
    widget_title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Widget display title"
    )
    
    widget_size: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
        comment="Widget size (small, medium, large, full)"
    )
    
    # Position
    position_row: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        comment="Grid row position"
    )
    
    position_col: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        comment="Grid column position"
    )
    
    # Configuration
    widget_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Widget configuration and settings"
    )
    
    data_source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Data source for widget"
    )
    
    refresh_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300,
        comment="Auto-refresh interval (seconds)"
    )
    
    # Status
    is_visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Widget is visible"
    )
    
    is_minimized: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Widget is minimized"
    )
    
    # Cached Data
    cached_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Cached widget data"
    )
    
    last_refreshed: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last data refresh"
    )
    
    # Relationships
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[admin_id]
    )
    
    @hybrid_property
    def needs_refresh(self) -> bool:
        """Check if widget needs data refresh."""
        if not self.last_refreshed:
            return True
        age_seconds = (datetime.utcnow() - self.last_refreshed).total_seconds()
        return age_seconds > self.refresh_interval_seconds
    
    def __repr__(self) -> str:
        return (
            f"<DashboardWidget(id={self.id}, type='{self.widget_type}', "
            f"title='{self.widget_title}')>"
        )


class DashboardSnapshot(TimestampModel, UUIDMixin):
    """
    Historical dashboard snapshot.
    
    Captures complete dashboard state at specific points in time
    for historical analysis and trend tracking.
    """
    
    __tablename__ = "dashboard_snapshots"
    __table_args__ = (
        Index("idx_snapshot_admin_id", "admin_id"),
        Index("idx_snapshot_timestamp", "snapshot_timestamp"),
        Index("idx_snapshot_date", "snapshot_date"),
    )
    
    # Foreign Keys
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin user ID"
    )
    
    # Snapshot Details
    snapshot_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Snapshot timestamp"
    )
    
    snapshot_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        default=date.today,
        index=True,
        comment="Snapshot date"
    )
    
    snapshot_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="daily",
        comment="Snapshot type (daily, weekly, monthly, on-demand)"
    )
    
    # Dashboard Data
    dashboard_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Complete dashboard data"
    )
    
    # Summary Statistics
    total_hostels: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total hostels at snapshot time"
    )
    
    avg_occupancy: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average occupancy at snapshot"
    )
    
    total_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total revenue at snapshot"
    )
    
    portfolio_health_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Portfolio health score"
    )
    
    # Metadata
    snapshot_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Snapshot format version"
    )
    
    retention_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=90,
        comment="Retention period (days)"
    )
    
    # Relationships
    admin: Mapped["AdminUser"] = relationship(
        "AdminUser",
        lazy="select",
        foreign_keys=[admin_id]
    )
    
    @hybrid_property
    def age_days(self) -> int:
        """Calculate snapshot age in days."""
        return (date.today() - self.snapshot_date).days
    
    @hybrid_property
    def should_be_deleted(self) -> bool:
        """Check if snapshot should be deleted based on retention."""
        return self.age_days > self.retention_days
    
    def __repr__(self) -> str:
        return (
            f"<DashboardSnapshot(id={self.id}, admin_id={self.admin_id}, "
            f"date={self.snapshot_date}, type='{self.snapshot_type}')>"
        )