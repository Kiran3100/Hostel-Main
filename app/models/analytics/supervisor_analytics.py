"""
Supervisor analytics models for performance tracking.

Provides persistent storage for:
- Individual supervisor KPIs
- Workload distribution
- Performance ratings
- Comparative benchmarking
- Team analytics
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


class SupervisorWorkload(BaseAnalyticsModel):
    """
    Supervisor workload metrics.
    
    Tracks task distribution and capacity utilization
    for resource planning.
    """
    
    __tablename__ = 'supervisor_workloads'
    
    supervisor_kpi_id = Column(
        UUID(as_uuid=True),
        ForeignKey('supervisor_kpis.id', ondelete='CASCADE'),
        nullable=False,
        unique=True
    )
    
    # Current workload
    active_complaints = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Currently assigned complaints"
    )
    
    active_maintenance = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Currently assigned maintenance"
    )
    
    pending_tasks = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total pending tasks"
    )
    
    # Capacity
    max_capacity = Column(
        Integer,
        nullable=False,
        comment="Maximum concurrent capacity"
    )
    
    current_utilization = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Capacity utilization %"
    )
    
    # Task types
    urgent_tasks = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Urgent/critical tasks"
    )
    
    overdue_tasks = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Overdue tasks"
    )
    
    # Calculated fields
    available_capacity = Column(
        Integer,
        nullable=True,
        comment="Available capacity"
    )
    
    workload_status = Column(
        String(20),
        nullable=True,
        comment="overloaded, high, moderate, low"
    )
    
    __table_args__ = (
        CheckConstraint(
            'max_capacity > 0',
            name='ck_workload_capacity_valid'
        ),
    )
    
    # Relationships
    supervisor_kpi = relationship('SupervisorKPI', back_populates='workload')


class SupervisorPerformanceRating(BaseAnalyticsModel):
    """
    Multi-dimensional performance ratings.
    
    Detailed scoring across performance dimensions.
    """
    
    __tablename__ = 'supervisor_performance_ratings'
    
    supervisor_kpi_id = Column(
        UUID(as_uuid=True),
        ForeignKey('supervisor_kpis.id', ondelete='CASCADE'),
        nullable=False,
        unique=True
    )
    
    # Individual ratings
    efficiency_score = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Task efficiency (0-100)"
    )
    
    quality_score = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Work quality (0-100)"
    )
    
    responsiveness_score = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Response time (0-100)"
    )
    
    student_satisfaction_score = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Student feedback (0-100)"
    )
    
    reliability_score = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Reliability (0-100)"
    )
    
    # Overall
    overall_rating = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Weighted overall rating"
    )
    
    # Insights
    performance_grade = Column(
        String(5),
        nullable=True,
        comment="Letter grade (A-F)"
    )
    
    strengths = Column(
        JSONB,
        nullable=True,
        comment="Performance strengths"
    )
    
    improvement_areas = Column(
        JSONB,
        nullable=True,
        comment="Areas needing improvement"
    )
    
    __table_args__ = (
        CheckConstraint(
            'efficiency_score >= 0 AND efficiency_score <= 100',
            name='ck_rating_efficiency_valid'
        ),
        CheckConstraint(
            'overall_rating >= 0 AND overall_rating <= 100',
            name='ck_rating_overall_valid'
        ),
    )
    
    # Relationships
    supervisor_kpi = relationship('SupervisorKPI', back_populates='performance_rating')


class SupervisorKPI(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Supervisor Key Performance Indicators.
    
    Comprehensive performance metrics for individual
    supervisor assessment.
    """
    
    __tablename__ = 'supervisor_kpis'
    
    supervisor_id = Column(
        UUID(as_uuid=True),
        ForeignKey('supervisors.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="Supervisor ID"
    )
    
    supervisor_name = Column(
        String(255),
        nullable=False,
        comment="Supervisor name"
    )
    
    # Workload metrics
    complaints_assigned = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Complaints assigned"
    )
    
    complaints_resolved = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Complaints resolved"
    )
    
    complaints_pending = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Currently pending"
    )
    
    maintenance_requests_created = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Maintenance requests created"
    )
    
    maintenance_requests_completed = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Maintenance completed"
    )
    
    maintenance_pending = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Maintenance pending"
    )
    
    attendance_records_marked = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Attendance records marked"
    )
    
    # Performance metrics
    avg_complaint_resolution_time_hours = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Avg complaint resolution time"
    )
    
    avg_first_response_time_hours = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        default=0,
        comment="Avg first response time"
    )
    
    avg_maintenance_completion_time_hours = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Avg maintenance completion time"
    )
    
    # SLA compliance
    complaint_sla_compliance_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Complaint SLA compliance %"
    )
    
    maintenance_sla_compliance_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Maintenance SLA compliance %"
    )
    
    # Quality metrics
    reopened_complaints = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Reopened complaints"
    )
    
    escalated_complaints = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Escalated complaints"
    )
    
    # Feedback
    student_feedback_score = Column(
        Numeric(precision=3, scale=2),
        nullable=True,
        comment="Average student rating (1-5)"
    )
    
    feedback_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Feedback responses"
    )
    
    # Overall
    overall_performance_score = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Composite score (0-100)"
    )
    
    # Calculated fields
    complaint_resolution_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Complaint resolution rate %"
    )
    
    maintenance_completion_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Maintenance completion rate %"
    )
    
    reopen_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Complaint reopen rate %"
    )
    
    performance_status = Column(
        String(20),
        nullable=True,
        comment="excellent, good, satisfactory, needs_improvement, unsatisfactory"
    )
    
    __table_args__ = (
        Index(
            'ix_supervisor_kpi_hostel_period',
            'hostel_id',
            'supervisor_id',
            'period_start',
            'period_end'
        ),
        UniqueConstraint(
            'supervisor_id',
            'hostel_id',
            'period_start',
            'period_end',
            name='uq_supervisor_kpi_unique'
        ),
    )
    
    # Relationships
    workload = relationship(
        'SupervisorWorkload',
        back_populates='supervisor_kpi',
        uselist=False,
        cascade='all, delete-orphan'
    )
    
    performance_rating = relationship(
        'SupervisorPerformanceRating',
        back_populates='supervisor_kpi',
        uselist=False,
        cascade='all, delete-orphan'
    )
    
    trends = relationship(
        'SupervisorTrendPoint',
        back_populates='supervisor_kpi',
        cascade='all, delete-orphan'
    )


class SupervisorTrendPoint(BaseAnalyticsModel):
    """
    Performance trend data point.
    
    Tracks supervisor performance over time for
    progress monitoring.
    """
    
    __tablename__ = 'supervisor_trend_points'
    
    supervisor_kpi_id = Column(
        UUID(as_uuid=True),
        ForeignKey('supervisor_kpis.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    period_label = Column(
        String(100),
        nullable=False,
        comment="Period identifier"
    )
    
    period_start = Column(
        Date,
        nullable=False,
        index=True,
        comment="Period start"
    )
    
    period_end = Column(
        Date,
        nullable=False,
        comment="Period end"
    )
    
    complaints_resolved = Column(
        Integer,
        nullable=False,
        default=0
    )
    
    maintenance_completed = Column(
        Integer,
        nullable=False,
        default=0
    )
    
    performance_score = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Performance score"
    )
    
    student_feedback_score = Column(
        Numeric(precision=3, scale=2),
        nullable=True,
        comment="Student feedback"
    )
    
    total_tasks_completed = Column(
        Integer,
        nullable=True,
        comment="Total tasks"
    )
    
    __table_args__ = (
        Index('ix_supervisor_trend_period', 'period_start', 'period_end'),
    )
    
    # Relationships
    supervisor_kpi = relationship('SupervisorKPI', back_populates='trends')


class SupervisorComparison(
    BaseAnalyticsModel,
    AnalyticsMixin,
    HostelScopedMixin,
    CachedAnalyticsMixin
):
    """
    Comparative analysis of supervisors.
    
    Benchmarking and ranking within hostel or platform.
    """
    
    __tablename__ = 'supervisor_comparisons'
    
    scope_type = Column(
        String(20),
        nullable=False,
        comment="hostel or platform"
    )
    
    # Rankings (JSONB arrays of supervisor IDs)
    ranked_by_performance = Column(
        JSONB,
        nullable=True,
        comment="Ranked by overall performance"
    )
    
    ranked_by_resolution_speed = Column(
        JSONB,
        nullable=True,
        comment="Ranked by resolution speed"
    )
    
    ranked_by_feedback_score = Column(
        JSONB,
        nullable=True,
        comment="Ranked by student feedback"
    )
    
    ranked_by_sla_compliance = Column(
        JSONB,
        nullable=True,
        comment="Ranked by SLA compliance"
    )
    
    # Statistics
    avg_performance_score = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Average performance"
    )
    
    avg_resolution_time_hours = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Average resolution time"
    )
    
    avg_sla_compliance = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Average SLA compliance"
    )
    
    # Insights
    top_performer = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Top performing supervisor ID"
    )
    
    performance_variance = Column(
        Numeric(precision=10, scale=4),
        nullable=True,
        comment="Performance variance"
    )
    
    __table_args__ = (
        Index(
            'ix_supervisor_comparison_hostel_period',
            'hostel_id',
            'period_start',
            'period_end'
        ),
    )


class TeamAnalytics(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Team-level supervisor analytics.
    
    Aggregated metrics at team/hostel level for
    management oversight.
    """
    
    __tablename__ = 'team_analytics'
    
    # Team composition
    total_supervisors = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total supervisors"
    )
    
    active_supervisors = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Active supervisors"
    )
    
    # Aggregate metrics
    total_tasks_assigned = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total tasks assigned"
    )
    
    total_tasks_completed = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total tasks completed"
    )
    
    team_completion_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Team completion rate %"
    )
    
    # Performance
    avg_team_performance_score = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Average team score"
    )
    
    avg_team_sla_compliance = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Average SLA compliance"
    )
    
    # Workload
    workload_balance_score = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Workload balance (100 = perfect)"
    )
    
    # Top performers
    top_performers = Column(
        JSONB,
        nullable=True,
        comment="Top 5 performer IDs"
    )
    
    team_efficiency = Column(
        String(20),
        nullable=True,
        comment="high, moderate, low"
    )
    
    __table_args__ = (
        Index(
            'ix_team_analytics_hostel_period',
            'hostel_id',
            'period_start',
            'period_end'
        ),
    )