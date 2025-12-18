"""
Occupancy analytics models with forecasting capabilities.

Provides persistent storage for:
- Occupancy KPIs and utilization metrics
- Time-series trend data
- Room type and floor breakdowns
- Seasonal patterns
- Predictive forecasting
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


class OccupancyKPI(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Occupancy Key Performance Indicators.
    
    Comprehensive occupancy statistics for capacity
    planning and performance monitoring.
    """
    
    __tablename__ = 'occupancy_kpis'
    
    # Current state
    current_occupancy_percentage = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Current occupancy rate"
    )
    
    # Period averages
    average_occupancy_percentage = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Average occupancy over period"
    )
    
    peak_occupancy_percentage = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Peak occupancy in period"
    )
    
    low_occupancy_percentage = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Lowest occupancy in period"
    )
    
    # Capacity metrics
    total_beds = Column(
        Integer,
        nullable=False,
        comment="Total bed capacity"
    )
    
    occupied_beds = Column(
        Integer,
        nullable=False,
        comment="Currently occupied beds"
    )
    
    available_beds = Column(
        Integer,
        nullable=False,
        comment="Currently available beds"
    )
    
    reserved_beds = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Reserved but not occupied"
    )
    
    maintenance_beds = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Beds under maintenance"
    )
    
    # Utilization metrics
    utilization_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Actual utilization rate"
    )
    
    turnover_rate = Column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Bed turnover rate"
    )
    
    # Calculated fields
    occupancy_status = Column(
        String(20),
        nullable=True,
        comment="high, optimal, moderate, low, critical"
    )
    
    capacity_pressure = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Capacity pressure score (0-100)"
    )
    
    vacancy_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Vacancy rate percentage"
    )
    
    __table_args__ = (
        Index('ix_occupancy_kpi_hostel_period', 'hostel_id', 'period_start', 'period_end'),
        CheckConstraint(
            'occupied_beds <= total_beds',
            name='ck_occupancy_kpi_occupied_valid'
        ),
        CheckConstraint(
            'current_occupancy_percentage >= 0 AND current_occupancy_percentage <= 100',
            name='ck_occupancy_kpi_percentage_valid'
        ),
    )
    
    # Relationships
    trends = relationship(
        'OccupancyTrendPoint',
        back_populates='kpi',
        cascade='all, delete-orphan'
    )


class OccupancyTrendPoint(BaseAnalyticsModel, TrendMixin):
    """
    Daily occupancy trend data points.
    
    Time-series occupancy data for trend analysis
    and visualization.
    """
    
    __tablename__ = 'occupancy_trend_points'
    
    kpi_id = Column(
        UUID(as_uuid=True),
        ForeignKey('occupancy_kpis.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    trend_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Date of data point"
    )
    
    occupancy_percentage = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Occupancy rate for this date"
    )
    
    occupied_beds = Column(
        Integer,
        nullable=False,
        comment="Occupied beds"
    )
    
    total_beds = Column(
        Integer,
        nullable=False,
        comment="Total beds available"
    )
    
    check_ins = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Check-ins on this date"
    )
    
    check_outs = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Check-outs on this date"
    )
    
    net_change = Column(
        Integer,
        nullable=True,
        comment="Net change in occupancy"
    )
    
    __table_args__ = (
        Index('ix_occupancy_trend_date', 'trend_date'),
        UniqueConstraint('kpi_id', 'trend_date', name='uq_occupancy_trend_kpi_date'),
        CheckConstraint(
            'occupied_beds <= total_beds',
            name='ck_occupancy_trend_beds_valid'
        ),
    )
    
    # Relationships
    kpi = relationship('OccupancyKPI', back_populates='trends')


class OccupancyByRoomType(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Occupancy breakdown by room type.
    
    Granular occupancy metrics per room type for
    optimization opportunities.
    """
    
    __tablename__ = 'occupancy_by_room_type'
    
    room_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Room type"
    )
    
    room_type_name = Column(
        String(100),
        nullable=True,
        comment="Human-readable room type name"
    )
    
    total_rooms = Column(
        Integer,
        nullable=False,
        comment="Total rooms of this type"
    )
    
    total_beds = Column(
        Integer,
        nullable=False,
        comment="Total beds in this room type"
    )
    
    occupied_beds = Column(
        Integer,
        nullable=False,
        comment="Occupied beds"
    )
    
    occupancy_percentage = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Occupancy rate"
    )
    
    # Revenue metrics
    average_rate = Column(
        Numeric(precision=12, scale=2),
        nullable=True,
        comment="Average rate charged"
    )
    
    revenue_generated = Column(
        Numeric(precision=15, scale=2),
        nullable=True,
        comment="Revenue from this room type"
    )
    
    revenue_per_bed = Column(
        Numeric(precision=12, scale=2),
        nullable=True,
        comment="Revenue per bed"
    )
    
    available_beds = Column(
        Integer,
        nullable=True,
        comment="Available beds"
    )
    
    __table_args__ = (
        Index(
            'ix_occupancy_room_type_hostel_period',
            'hostel_id',
            'period_start',
            'period_end',
            'room_type'
        ),
        UniqueConstraint(
            'hostel_id',
            'period_start',
            'period_end',
            'room_type',
            name='uq_occupancy_room_type_unique'
        ),
        CheckConstraint(
            'occupied_beds <= total_beds',
            name='ck_occupancy_room_type_beds_valid'
        ),
    )


class OccupancyByFloor(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Occupancy breakdown by floor.
    
    Floor-wise occupancy metrics for facility management.
    """
    
    __tablename__ = 'occupancy_by_floor'
    
    floor_number = Column(
        Integer,
        nullable=False,
        index=True,
        comment="Floor number"
    )
    
    floor_name = Column(
        String(100),
        nullable=True,
        comment="Floor name/identifier"
    )
    
    total_rooms = Column(
        Integer,
        nullable=False,
        comment="Total rooms on floor"
    )
    
    total_beds = Column(
        Integer,
        nullable=False,
        comment="Total beds on floor"
    )
    
    occupied_beds = Column(
        Integer,
        nullable=False,
        comment="Occupied beds"
    )
    
    occupancy_percentage = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Occupancy rate"
    )
    
    __table_args__ = (
        Index(
            'ix_occupancy_floor_hostel_period',
            'hostel_id',
            'period_start',
            'period_end',
            'floor_number'
        ),
        UniqueConstraint(
            'hostel_id',
            'period_start',
            'period_end',
            'floor_number',
            name='uq_occupancy_floor_unique'
        ),
    )


class SeasonalPattern(BaseAnalyticsModel, HostelScopedMixin):
    """
    Identified seasonal occupancy patterns.
    
    Recurring patterns for strategic planning.
    """
    
    __tablename__ = 'seasonal_patterns'
    
    pattern_name = Column(
        String(100),
        nullable=False,
        comment="Pattern identifier"
    )
    
    start_month = Column(
        Integer,
        nullable=False,
        comment="Starting month (1-12)"
    )
    
    end_month = Column(
        Integer,
        nullable=False,
        comment="Ending month (1-12)"
    )
    
    average_occupancy = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Average occupancy during pattern"
    )
    
    occupancy_variance = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Variance in occupancy"
    )
    
    confidence = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Confidence in pattern (0-100)"
    )
    
    is_high_season = Column(
        Boolean,
        nullable=True,
        comment="Whether this is high season"
    )
    
    year_identified = Column(
        Integer,
        nullable=False,
        comment="Year pattern was identified"
    )
    
    __table_args__ = (
        Index('ix_seasonal_pattern_hostel', 'hostel_id'),
        CheckConstraint(
            'start_month >= 1 AND start_month <= 12',
            name='ck_seasonal_pattern_start_month_valid'
        ),
        CheckConstraint(
            'end_month >= 1 AND end_month <= 12',
            name='ck_seasonal_pattern_end_month_valid'
        ),
    )


class ForecastPoint(BaseAnalyticsModel):
    """
    Single occupancy forecast data point.
    
    Predicted occupancy for a future date with
    confidence intervals.
    """
    
    __tablename__ = 'forecast_points'
    
    forecast_data_id = Column(
        UUID(as_uuid=True),
        ForeignKey('forecast_data.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    forecast_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Forecast date"
    )
    
    forecasted_occupancy_percentage = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Predicted occupancy rate"
    )
    
    forecasted_occupied_beds = Column(
        Integer,
        nullable=False,
        comment="Predicted occupied beds"
    )
    
    # Confidence intervals
    lower_bound = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Lower confidence bound"
    )
    
    upper_bound = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Upper confidence bound"
    )
    
    confidence_level = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Confidence level (e.g., 95)"
    )
    
    __table_args__ = (
        Index('ix_forecast_point_date', 'forecast_date'),
        UniqueConstraint(
            'forecast_data_id',
            'forecast_date',
            name='uq_forecast_point_unique'
        ),
    )
    
    # Relationships
    forecast_data = relationship('ForecastData', back_populates='forecast_points')


class ForecastData(BaseAnalyticsModel, HostelScopedMixin, CachedAnalyticsMixin):
    """
    Occupancy forecast data with model information.
    
    Predicted occupancy with metadata about forecasting
    methodology and confidence.
    """
    
    __tablename__ = 'forecast_data'
    
    forecast_horizon_days = Column(
        Integer,
        nullable=False,
        comment="Days forecasted into future"
    )
    
    # Model information
    model_used = Column(
        SQLEnum(
            'moving_average',
            'exponential_smoothing',
            'arima',
            'linear_regression',
            'simple_extrapolation',
            'ml_based',
            name='forecast_model_enum'
        ),
        nullable=False,
        comment="Forecasting model used"
    )
    
    model_accuracy = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Historical model accuracy %"
    )
    
    confidence_interval = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Confidence interval (e.g., 95)"
    )
    
    # Training data info
    training_data_start = Column(
        Date,
        nullable=True,
        comment="Training data start date"
    )
    
    training_data_end = Column(
        Date,
        nullable=True,
        comment="Training data end date"
    )
    
    training_samples = Column(
        Integer,
        nullable=True,
        comment="Number of training samples"
    )
    
    # Calculated fields
    average_forecasted_occupancy = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Average forecasted occupancy"
    )
    
    peak_forecasted_date = Column(
        Date,
        nullable=True,
        comment="Date with highest forecast"
    )
    
    low_forecasted_date = Column(
        Date,
        nullable=True,
        comment="Date with lowest forecast"
    )
    
    # Metadata
    last_updated = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last update timestamp"
    )
    
    __table_args__ = (
        Index('ix_forecast_data_hostel', 'hostel_id'),
        CheckConstraint(
            'forecast_horizon_days >= 1 AND forecast_horizon_days <= 365',
            name='ck_forecast_horizon_valid'
        ),
    )
    
    # Relationships
    forecast_points = relationship(
        'ForecastPoint',
        back_populates='forecast_data',
        cascade='all, delete-orphan'
    )
    
    seasonal_patterns = relationship(
        'SeasonalPattern',
        secondary='forecast_seasonal_patterns',
        backref='forecasts'
    )


# Association table for forecast and seasonal patterns
from sqlalchemy import Table

forecast_seasonal_patterns = Table(
    'forecast_seasonal_patterns',
    BaseAnalyticsModel.metadata,
    Column(
        'forecast_id',
        UUID(as_uuid=True),
        ForeignKey('forecast_data.id', ondelete='CASCADE'),
        primary_key=True
    ),
    Column(
        'pattern_id',
        UUID(as_uuid=True),
        ForeignKey('seasonal_patterns.id', ondelete='CASCADE'),
        primary_key=True
    )
)


class OccupancyReport(
    BaseAnalyticsModel,
    AnalyticsMixin,
    HostelScopedMixin,
    CachedAnalyticsMixin
):
    """
    Comprehensive occupancy analytics report.
    
    Consolidates metrics, trends, breakdowns, and forecasts.
    """
    
    __tablename__ = 'occupancy_reports'
    
    kpi_id = Column(
        UUID(as_uuid=True),
        ForeignKey('occupancy_kpis.id', ondelete='SET NULL'),
        nullable=True
    )
    
    forecast_id = Column(
        UUID(as_uuid=True),
        ForeignKey('forecast_data.id', ondelete='SET NULL'),
        nullable=True
    )
    
    # Quick insights
    best_performing_room_type = Column(
        String(50),
        nullable=True,
        comment="Room type with highest occupancy"
    )
    
    worst_performing_room_type = Column(
        String(50),
        nullable=True,
        comment="Room type with lowest occupancy"
    )
    
    occupancy_trend_direction = Column(
        String(20),
        nullable=True,
        comment="increasing, decreasing, stable"
    )
    
    # Breakdowns (JSONB for flexibility)
    room_type_breakdown = Column(
        JSONB,
        nullable=True,
        comment="Room type breakdown data"
    )
    
    floor_breakdown = Column(
        JSONB,
        nullable=True,
        comment="Floor breakdown data"
    )
    
    # Actionable insights
    optimization_insights = Column(
        JSONB,
        nullable=True,
        comment="Generated optimization recommendations"
    )
    
    __table_args__ = (
        Index(
            'ix_occupancy_report_hostel_period',
            'hostel_id',
            'period_start',
            'period_end'
        ),
        UniqueConstraint(
            'hostel_id',
            'period_start',
            'period_end',
            name='uq_occupancy_report_unique'
        ),
    )
    
    # Relationships
    kpi = relationship('OccupancyKPI', foreign_keys=[kpi_id])
    forecast = relationship('ForecastData', foreign_keys=[forecast_id])