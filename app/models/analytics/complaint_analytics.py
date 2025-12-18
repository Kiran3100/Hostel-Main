"""
Complaint analytics models for service quality tracking.

Provides persistent storage for:
- Complaint KPIs and resolution metrics
- SLA compliance tracking
- Category and priority breakdowns
- Trend analysis
- Staff performance metrics
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, String, Integer, Numeric, DateTime, Date, Boolean,
    ForeignKey, Text, Index, CheckConstraint, UniqueConstraint
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


class ComplaintKPI(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Complaint Key Performance Indicators.
    
    Stores calculated KPIs for complaint management including
    resolution times, SLA compliance, and quality metrics.
    """
    
    __tablename__ = 'complaint_kpis'
    
    # Volume metrics
    total_complaints = Column(Integer, nullable=False, default=0)
    open_complaints = Column(Integer, nullable=False, default=0)
    in_progress_complaints = Column(Integer, nullable=False, default=0)
    resolved_complaints = Column(Integer, nullable=False, default=0)
    closed_complaints = Column(Integer, nullable=False, default=0)
    
    # Performance metrics
    average_resolution_time_hours = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Average time to resolve complaints"
    )
    
    median_resolution_time_hours = Column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Median resolution time"
    )
    
    average_first_response_time_hours = Column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Average time to first response"
    )
    
    # SLA metrics
    sla_compliance_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Percentage meeting SLA"
    )
    
    escalation_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Percentage of complaints escalated"
    )
    
    reopen_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Percentage of resolved complaints reopened"
    )
    
    # Quality metrics
    average_satisfaction_score = Column(
        Numeric(precision=3, scale=2),
        nullable=True,
        comment="Average satisfaction score (1-5)"
    )
    
    # Calculated metrics
    resolution_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Percentage resolved"
    )
    
    backlog = Column(
        Integer,
        nullable=True,
        comment="Current complaint backlog"
    )
    
    efficiency_score = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Overall efficiency score (0-100)"
    )
    
    __table_args__ = (
        Index('ix_complaint_kpis_hostel_period', 'hostel_id', 'period_start', 'period_end'),
        CheckConstraint(
            'resolved_complaints <= total_complaints',
            name='ck_complaint_kpis_resolved_valid'
        ),
        CheckConstraint(
            'sla_compliance_rate >= 0 AND sla_compliance_rate <= 100',
            name='ck_complaint_kpis_sla_valid'
        ),
    )
    
    # Relationships
    trends = relationship(
        'ComplaintTrendPoint',
        back_populates='kpi',
        cascade='all, delete-orphan'
    )
    
    sla_metrics = relationship(
        'SLAMetrics',
        back_populates='complaint_kpi',
        uselist=False,
        cascade='all, delete-orphan'
    )


class SLAMetrics(BaseAnalyticsModel):
    """
    Service Level Agreement compliance metrics.
    
    Detailed SLA tracking and compliance analysis.
    """
    
    __tablename__ = 'sla_metrics'
    
    complaint_kpi_id = Column(
        UUID(as_uuid=True),
        ForeignKey('complaint_kpis.id', ondelete='CASCADE'),
        nullable=False,
        unique=True
    )
    
    total_with_sla = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total complaints with defined SLA"
    )
    
    met_sla = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Complaints resolved within SLA"
    )
    
    breached_sla = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Complaints that breached SLA"
    )
    
    sla_compliance_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="SLA compliance percentage"
    )
    
    average_sla_buffer_hours = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Average buffer/breach time in hours"
    )
    
    at_risk_count = Column(
        Integer,
        nullable=True,
        comment="Complaints at risk of SLA breach"
    )
    
    __table_args__ = (
        CheckConstraint(
            'met_sla <= total_with_sla',
            name='ck_sla_metrics_met_valid'
        ),
        CheckConstraint(
            'breached_sla <= total_with_sla',
            name='ck_sla_metrics_breached_valid'
        ),
    )
    
    # Relationships
    complaint_kpi = relationship('ComplaintKPI', back_populates='sla_metrics')


class ComplaintTrendPoint(BaseAnalyticsModel, TrendMixin):
    """
    Daily complaint trend data points.
    
    Time-series data for complaint metrics enabling
    trend analysis and pattern detection.
    """
    
    __tablename__ = 'complaint_trend_points'
    
    kpi_id = Column(
        UUID(as_uuid=True),
        ForeignKey('complaint_kpis.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    trend_date = Column(Date, nullable=False, index=True)
    
    # Daily metrics
    total_complaints = Column(Integer, nullable=False, default=0)
    open_complaints = Column(Integer, nullable=False, default=0)
    resolved_complaints = Column(Integer, nullable=False, default=0)
    escalated = Column(Integer, nullable=False, default=0)
    sla_breached = Column(Integer, nullable=False, default=0)
    
    resolution_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Resolution rate for this date"
    )
    
    __table_args__ = (
        Index('ix_complaint_trends_date', 'trend_date'),
        UniqueConstraint('kpi_id', 'trend_date', name='uq_complaint_trend_kpi_date'),
        CheckConstraint(
            'resolved_complaints <= total_complaints',
            name='ck_complaint_trends_resolved_valid'
        ),
    )
    
    # Relationships
    kpi = relationship('ComplaintKPI', back_populates='trends')


class CategoryBreakdown(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Complaint breakdown by category.
    
    Analyzes complaint distribution and resolution
    efficiency by category.
    """
    
    __tablename__ = 'complaint_category_breakdowns'
    
    category = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Complaint category"
    )
    
    count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of complaints in category"
    )
    
    percentage_of_total = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Percentage of total complaints"
    )
    
    average_resolution_time_hours = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Average resolution time for category"
    )
    
    resolved_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Resolved complaints in category"
    )
    
    open_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Open complaints in category"
    )
    
    resolution_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Category resolution rate"
    )
    
    __table_args__ = (
        Index(
            'ix_category_breakdown_hostel_period',
            'hostel_id',
            'period_start',
            'period_end',
            'category'
        ),
        UniqueConstraint(
            'hostel_id',
            'period_start',
            'period_end',
            'category',
            name='uq_category_breakdown_unique'
        ),
        CheckConstraint(
            'resolved_count <= count',
            name='ck_category_breakdown_resolved_valid'
        ),
    )


class PriorityBreakdown(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Complaint breakdown by priority level.
    
    Analyzes resource allocation and response times
    by priority tier.
    """
    
    __tablename__ = 'complaint_priority_breakdowns'
    
    priority = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Priority level"
    )
    
    count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Complaints at this priority"
    )
    
    percentage_of_total = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Percentage of total"
    )
    
    average_resolution_time_hours = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Average resolution time"
    )
    
    sla_compliance_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="SLA compliance for this priority"
    )
    
    priority_score = Column(
        Integer,
        nullable=True,
        comment="Numeric priority score for sorting"
    )
    
    __table_args__ = (
        Index(
            'ix_priority_breakdown_hostel_period',
            'hostel_id',
            'period_start',
            'period_end',
            'priority'
        ),
        UniqueConstraint(
            'hostel_id',
            'period_start',
            'period_end',
            'priority',
            name='uq_priority_breakdown_unique'
        ),
    )


class ComplaintDashboard(
    BaseAnalyticsModel,
    AnalyticsMixin,
    HostelScopedMixin,
    CachedAnalyticsMixin
):
    """
    Comprehensive complaint dashboard analytics.
    
    Cached aggregate view for complaint management
    dashboard and reporting.
    """
    
    __tablename__ = 'complaint_dashboards'
    
    kpi_id = Column(
        UUID(as_uuid=True),
        ForeignKey('complaint_kpis.id', ondelete='SET NULL'),
        nullable=True
    )
    
    # Quick access aggregates
    total_complaints = Column(Integer, nullable=False, default=0)
    open_complaints = Column(Integer, nullable=False, default=0)
    urgent_complaints = Column(Integer, nullable=False, default=0)
    
    # Category insights
    most_common_category = Column(
        String(100),
        nullable=True,
        comment="Most frequent complaint category"
    )
    
    slowest_category = Column(
        String(100),
        nullable=True,
        comment="Category with slowest resolution"
    )
    
    # Priority insights
    high_priority_percentage = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Percentage of high/urgent/critical"
    )
    
    # Breakdowns (JSONB for flexibility)
    category_breakdown_json = Column(
        JSONB,
        nullable=True,
        comment="Category breakdown data"
    )
    
    priority_breakdown_json = Column(
        JSONB,
        nullable=True,
        comment="Priority breakdown data"
    )
    
    # Actionable insights
    actionable_insights = Column(
        JSONB,
        nullable=True,
        comment="Generated insights and recommendations"
    )
    
    __table_args__ = (
        Index(
            'ix_complaint_dashboard_hostel_period',
            'hostel_id',
            'period_start',
            'period_end'
        ),
        Index('ix_complaint_dashboard_cache_key', 'cache_key'),
    )
    
    # Relationships
    kpi = relationship('ComplaintKPI', foreign_keys=[kpi_id])