"""
Booking analytics models for performance tracking and forecasting.

Provides persistent storage for:
- Booking KPIs and metrics
- Conversion funnel data
- Cancellation analytics
- Source-based performance
- Trend analysis
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


class BookingKPI(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Booking Key Performance Indicators storage.
    
    Stores calculated KPIs for booking performance including
    conversion rates, cancellation metrics, and lead times.
    """
    
    __tablename__ = 'booking_kpis'
    
    # Booking counts
    total_bookings = Column(Integer, nullable=False, default=0)
    confirmed_bookings = Column(Integer, nullable=False, default=0)
    cancelled_bookings = Column(Integer, nullable=False, default=0)
    rejected_bookings = Column(Integer, nullable=False, default=0)
    pending_bookings = Column(Integer, nullable=False, default=0)
    
    # Performance metrics
    booking_conversion_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Percentage of bookings confirmed"
    )
    
    cancellation_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Percentage of bookings cancelled"
    )
    
    average_lead_time_days = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Average days from booking to check-in"
    )
    
    approval_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Approval rate (confirmed / confirmed + rejected)"
    )
    
    __table_args__ = (
        Index('ix_booking_kpis_hostel_period', 'hostel_id', 'period_start', 'period_end'),
        CheckConstraint(
            'confirmed_bookings <= total_bookings',
            name='ck_booking_kpis_confirmed_valid'
        ),
        CheckConstraint(
            'cancelled_bookings <= total_bookings',
            name='ck_booking_kpis_cancelled_valid'
        ),
        CheckConstraint(
            'booking_conversion_rate >= 0 AND booking_conversion_rate <= 100',
            name='ck_booking_kpis_conversion_valid'
        ),
    )
    
    # Relationships
    trends = relationship(
        'BookingTrendPoint',
        back_populates='kpi',
        cascade='all, delete-orphan'
    )


class BookingTrendPoint(BaseAnalyticsModel, TrendMixin):
    """
    Daily booking trend data points.
    
    Time-series data for booking metrics enabling
    trend analysis and visualization.
    """
    
    __tablename__ = 'booking_trend_points'
    
    kpi_id = Column(
        UUID(as_uuid=True),
        ForeignKey('booking_kpis.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    trend_date = Column(Date, nullable=False, index=True)
    
    # Daily metrics
    total_bookings = Column(Integer, nullable=False, default=0)
    confirmed = Column(Integer, nullable=False, default=0)
    cancelled = Column(Integer, nullable=False, default=0)
    rejected = Column(Integer, nullable=False, default=0)
    pending = Column(Integer, nullable=False, default=0)
    
    revenue_for_day = Column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=0,
        comment="Revenue generated on this date"
    )
    
    conversion_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Conversion rate for this date"
    )
    
    __table_args__ = (
        Index('ix_booking_trends_date', 'trend_date'),
        UniqueConstraint('kpi_id', 'trend_date', name='uq_booking_trend_kpi_date'),
        CheckConstraint(
            'confirmed <= total_bookings',
            name='ck_booking_trends_confirmed_valid'
        ),
    )
    
    # Relationships
    kpi = relationship('BookingKPI', back_populates='trends')


class BookingFunnelAnalytics(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Booking conversion funnel analytics.
    
    Tracks visitor journey from page view to confirmed booking
    with drop-off analysis at each stage.
    """
    
    __tablename__ = 'booking_funnel_analytics'
    
    # Funnel stages
    hostel_page_views = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total hostel detail page views"
    )
    
    booking_form_starts = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Users who started booking form"
    )
    
    booking_submissions = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Completed booking submissions"
    )
    
    bookings_confirmed = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Final confirmed bookings"
    )
    
    # Conversion rates
    view_to_start_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Page view to form start conversion"
    )
    
    start_to_submit_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Form start to submission conversion"
    )
    
    submit_to_confirm_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Submission to confirmation conversion"
    )
    
    view_to_confirm_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Overall conversion rate"
    )
    
    # Drop-off analysis
    largest_drop_off_stage = Column(
        String(50),
        nullable=True,
        comment="Stage with largest drop-off"
    )
    
    total_drop_offs = Column(
        Integer,
        nullable=True,
        comment="Total users who dropped off"
    )
    
    __table_args__ = (
        Index(
            'ix_booking_funnel_hostel_period',
            'hostel_id',
            'period_start',
            'period_end'
        ),
        CheckConstraint(
            'booking_form_starts <= hostel_page_views',
            name='ck_funnel_form_starts_valid'
        ),
        CheckConstraint(
            'booking_submissions <= booking_form_starts',
            name='ck_funnel_submissions_valid'
        ),
    )


class CancellationAnalytics(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Detailed cancellation analytics and patterns.
    
    Analyzes cancellation reasons, timing, and patterns
    to reduce cancellation rates.
    """
    
    __tablename__ = 'cancellation_analytics'
    
    total_cancellations = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total cancellations in period"
    )
    
    cancellation_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Cancellation rate percentage"
    )
    
    # Timing analysis
    average_time_before_checkin_days = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Average days before check-in when cancelled"
    )
    
    cancellations_within_24h = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Cancellations within 24h of check-in"
    )
    
    cancellations_within_week = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Cancellations within 1 week of check-in"
    )
    
    early_cancellation_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Percentage cancelled >7 days before"
    )
    
    # Reason breakdown (JSONB for flexibility)
    cancellations_by_reason = Column(
        JSONB,
        nullable=True,
        comment="Cancellation count by reason"
    )
    
    cancellations_by_status = Column(
        JSONB,
        nullable=True,
        comment="Cancellation count by booking status"
    )
    
    top_cancellation_reason = Column(
        String(100),
        nullable=True,
        comment="Most common cancellation reason"
    )
    
    __table_args__ = (
        Index(
            'ix_cancellation_hostel_period',
            'hostel_id',
            'period_start',
            'period_end'
        ),
        CheckConstraint(
            'cancellations_within_24h <= total_cancellations',
            name='ck_cancellation_24h_valid'
        ),
    )


class BookingSourceMetrics(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Performance metrics by booking source.
    
    Tracks booking performance across different acquisition
    channels to optimize marketing spend.
    """
    
    __tablename__ = 'booking_source_metrics'
    
    source = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Booking source identifier"
    )
    
    total_bookings = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total bookings from this source"
    )
    
    confirmed_bookings = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Confirmed bookings from source"
    )
    
    conversion_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Source conversion rate"
    )
    
    # Revenue metrics
    total_revenue = Column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=0,
        comment="Revenue from this source"
    )
    
    average_booking_value = Column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=0,
        comment="Average revenue per booking"
    )
    
    revenue_per_confirmed_booking = Column(
        Numeric(precision=12, scale=2),
        nullable=True,
        comment="Revenue per confirmed booking"
    )
    
    # Marketing metrics (if available)
    marketing_cost = Column(
        Numeric(precision=12, scale=2),
        nullable=True,
        comment="Marketing cost for this source"
    )
    
    roi = Column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Return on investment percentage"
    )
    
    __table_args__ = (
        Index(
            'ix_source_metrics_hostel_period_source',
            'hostel_id',
            'period_start',
            'period_end',
            'source'
        ),
        UniqueConstraint(
            'hostel_id',
            'period_start',
            'period_end',
            'source',
            name='uq_source_metrics_unique'
        ),
    )


class BookingAnalyticsSummary(
    BaseAnalyticsModel,
    AnalyticsMixin,
    HostelScopedMixin,
    CachedAnalyticsMixin
):
    """
    Comprehensive booking analytics summary.
    
    Cached aggregate view combining all booking analytics
    for dashboard and reporting.
    """
    
    __tablename__ = 'booking_analytics_summaries'
    
    kpi_id = Column(
        UUID(as_uuid=True),
        ForeignKey('booking_kpis.id', ondelete='SET NULL'),
        nullable=True
    )
    
    funnel_id = Column(
        UUID(as_uuid=True),
        ForeignKey('booking_funnel_analytics.id', ondelete='SET NULL'),
        nullable=True
    )
    
    cancellation_id = Column(
        UUID(as_uuid=True),
        ForeignKey('cancellation_analytics.id', ondelete='SET NULL'),
        nullable=True
    )
    
    # Quick access fields for common queries
    total_bookings = Column(Integer, nullable=False, default=0)
    total_revenue = Column(Numeric(precision=12, scale=2), nullable=False, default=0)
    overall_conversion_rate = Column(Numeric(precision=5, scale=2), nullable=True)
    
    # Source breakdown (JSONB for flexibility)
    bookings_by_source = Column(
        JSONB,
        nullable=True,
        comment="Booking count by source"
    )
    
    revenue_by_source = Column(
        JSONB,
        nullable=True,
        comment="Revenue by source"
    )
    
    # Best performing indicators
    best_performing_source = Column(
        String(50),
        nullable=True,
        comment="Source with highest conversion"
    )
    
    highest_revenue_source = Column(
        String(50),
        nullable=True,
        comment="Source with highest revenue"
    )
    
    # Trend summary
    trend_summary = Column(
        JSONB,
        nullable=True,
        comment="Summary of booking trends"
    )
    
    __table_args__ = (
        Index(
            'ix_booking_summary_hostel_period',
            'hostel_id',
            'period_start',
            'period_end'
        ),
        Index('ix_booking_summary_cache_key', 'cache_key'),
    )
    
    # Relationships
    kpi = relationship('BookingKPI', foreign_keys=[kpi_id])
    funnel = relationship('BookingFunnelAnalytics', foreign_keys=[funnel_id])
    cancellation = relationship('CancellationAnalytics', foreign_keys=[cancellation_id])