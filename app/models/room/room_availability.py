"""
Room availability models with real-time tracking and forecasting.

Manages dynamic room availability, time-based windows, rules,
forecasting, alerts, and optimization algorithms.
"""

from datetime import datetime, date as Date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date as DateColumn,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import (
    SoftDeleteMixin,
    UUIDMixin,
    AuditMixin,
)

__all__ = [
    "RoomAvailability",
    "AvailabilityWindow",
    "AvailabilityRule",
    "AvailabilityForecast",
    "AvailabilityAlert",
    "AvailabilityOptimization",
]


class RoomAvailability(UUIDMixin, TimestampModel, BaseModel):
    """
    Real-time room availability tracking.
    
    Maintains current availability status with dynamic updates.
    """

    __tablename__ = "room_availability"

    room_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Current Availability
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    available_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    occupied_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    reserved_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    blocked_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Availability Status
    availability_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="AVAILABLE",  # AVAILABLE, LIMITED, FULL, BLOCKED, MAINTENANCE
        index=True,
    )
    availability_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("100.00"),
    )

    # Date Tracking
    last_available_date: Mapped[Optional[datetime]] = mapped_column(
        DateColumn,
        nullable=True,
    )
    last_fully_occupied_date: Mapped[Optional[datetime]] = mapped_column(
        DateColumn,
        nullable=True,
    )
    next_expected_vacancy_date: Mapped[Optional[datetime]] = mapped_column(
        DateColumn,
        nullable=True,
    )

    # Booking Window
    min_advance_booking_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_advance_booking_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=365,
    )
    instant_booking_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Availability Restrictions
    has_restrictions: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    restriction_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # GENDER, AGE, STUDENT_TYPE, CUSTOM
    )
    restrictions: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Blackout Dates
    has_blackout_dates: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    blackout_dates: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,  # ISO date strings
    )
    blackout_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Capacity Management
    soft_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,  # Recommended max capacity
    )
    hard_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,  # Absolute max capacity
    )
    allow_overbooking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    overbooking_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Real-time Updates
    last_checked: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    check_frequency_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
    )
    auto_update_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Waitlist Management
    has_waitlist: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    waitlist_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    waitlist_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    max_waitlist_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Demand Tracking
    current_demand_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="NORMAL",  # LOW, NORMAL, HIGH, VERY_HIGH
    )
    demand_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # 0.00 - 100.00
    )
    inquiry_count_24h: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    booking_count_7d: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Performance Metrics
    average_occupancy_30d: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    average_occupancy_90d: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    turnover_rate_30d: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Pricing Impact
    dynamic_pricing_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    current_price_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
        default=Decimal("1.00"),  # 0.50 - 2.00
    )
    price_adjustment_reason: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    # Alerts
    low_availability_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,  # Number of beds
    )
    send_alerts: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    last_alert_sent: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Metadata
    availability_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    cache_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Notes
    availability_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    room = relationship(
        "Room",
        back_populates="availability",
    )
    windows = relationship(
        "AvailabilityWindow",
        back_populates="room_availability",
        cascade="all, delete-orphan",
    )
    rules = relationship(
        "AvailabilityRule",
        back_populates="room_availability",
        cascade="all, delete-orphan",
    )
    forecast = relationship(
        "AvailabilityForecast",
        back_populates="room_availability",
        uselist=False,
        cascade="all, delete-orphan",
    )
    alerts = relationship(
        "AvailabilityAlert",
        back_populates="room_availability",
        cascade="all, delete-orphan",
    )
    optimization = relationship(
        "AvailabilityOptimization",
        back_populates="room_availability",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_room_avail_status", "availability_status", "is_available"),
        Index("ix_room_avail_beds", "available_beds", "total_beds"),
    )

    def __repr__(self) -> str:
        return (
            f"<RoomAvailability(room_id={self.room_id}, "
            f"available={self.available_beds}/{self.total_beds})>"
        )

    def update_availability(self) -> None:
        """Update availability status based on current bed counts."""
        if self.total_beds == 0:
            self.availability_percentage = Decimal("0.00")
            self.availability_status = "BLOCKED"
            self.is_available = False
            return

        # Calculate availability percentage
        self.availability_percentage = Decimal(
            (self.available_beds / self.total_beds * 100)
        ).quantize(Decimal("0.01"))

        # Update status
        if self.available_beds == 0:
            self.availability_status = "FULL"
            self.is_available = False
        elif self.available_beds <= self.low_availability_threshold:
            self.availability_status = "LIMITED"
            self.is_available = True
        else:
            self.availability_status = "AVAILABLE"
            self.is_available = True

        self.last_checked = datetime.utcnow()

    @property
    def occupancy_rate(self) -> Decimal:
        """Calculate current occupancy rate."""
        if self.total_beds == 0:
            return Decimal("0.00")
        return Decimal(
            (self.occupied_beds / self.total_beds * 100)
        ).quantize(Decimal("0.01"))


class AvailabilityWindow(UUIDMixin, TimestampModel, SoftDeleteMixin, BaseModel):
    """
    Time-based availability windows.
    
    Defines specific time periods with custom availability rules.
    """

    __tablename__ = "availability_windows"

    room_availability_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_availability.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Window Definition
    window_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    window_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="CUSTOM",  # PEAK, OFF_PEAK, SEASONAL, CUSTOM, SPECIAL_EVENT
    )
    window_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Date Range
    start_date: Mapped[datetime] = mapped_column(
        DateColumn,
        nullable=False,
        index=True,
    )
    end_date: Mapped[datetime] = mapped_column(
        DateColumn,
        nullable=False,
        index=True,
    )
    is_recurring: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    recurrence_pattern: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # DAILY, WEEKLY, MONTHLY, YEARLY, CUSTOM
    )

    # Availability Rules
    availability_override: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    is_available_in_window: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    available_beds_override: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Pricing Adjustments
    has_price_adjustment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    price_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
        default=Decimal("1.00"),
    )
    fixed_price_override: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Minimum Stay Requirements
    minimum_stay_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    maximum_stay_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Booking Restrictions
    advance_booking_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    last_minute_booking_hours: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Priority and Status
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,  # 1-10, higher takes precedence
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # Special Conditions
    conditions: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    restrictions: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Performance Tracking
    times_applied: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    bookings_during_window: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    revenue_during_window: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Notes
    window_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    room_availability = relationship(
        "RoomAvailability",
        back_populates="windows",
    )

    __table_args__ = (
        Index("ix_avail_window_dates", "start_date", "end_date", "is_active"),
        Index("ix_avail_window_type", "window_type", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<AvailabilityWindow(name={self.window_name}, "
            f"start={self.start_date}, end={self.end_date})>"
        )

    def is_active_for_date(self, check_date: Date) -> bool:
        """Check if window is active for given date."""
        if not self.is_active:
            return False
        return self.start_date <= check_date <= self.end_date


class AvailabilityRule(UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin, BaseModel):
    """
    Rules governing availability calculation.
    
    Business rules that affect availability determination.
    """

    __tablename__ = "availability_rules"

    room_availability_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_availability.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Rule Definition
    rule_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    rule_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    rule_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Rule Type
    rule_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,  # CAPACITY, RESTRICTION, TIMING, PRICING, CUSTOM
    )
    rule_category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Rule Logic
    rule_logic: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    conditions: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    actions: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Priority
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,  # 1-10
    )
    execution_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
    )

    # Constraint Type
    is_hard_constraint: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,  # Must be satisfied
    )
    is_soft_constraint: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,  # Preferred but not required
    )

    # Applicability
    applies_to_all_dates: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    applicable_dates: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    applicable_days_of_week: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,  # MON, TUE, WED, etc.
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    is_system_rule: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    can_be_overridden: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Execution Tracking
    execution_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    success_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_executed: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Performance
    average_execution_time_ms: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Validity
    valid_from: Mapped[Optional[datetime]] = mapped_column(
        DateColumn,
        nullable=True,
    )
    valid_until: Mapped[Optional[datetime]] = mapped_column(
        DateColumn,
        nullable=True,
    )

    # Error Handling
    on_error_action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="SKIP",  # SKIP, FAIL, RETRY, ALERT
    )
    max_retry_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    # Notes
    rule_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    room_availability = relationship(
        "RoomAvailability",
        back_populates="rules",
    )

    __table_args__ = (
        Index("ix_avail_rule_type_active", "rule_type", "is_active"),
        Index("ix_avail_rule_priority", "priority", "execution_order"),
    )

    def __repr__(self) -> str:
        return (
            f"<AvailabilityRule(name={self.rule_name}, "
            f"type={self.rule_type}, priority={self.priority})>"
        )


class AvailabilityForecast(UUIDMixin, TimestampModel, BaseModel):
    """
    Predictive availability modeling.
    
    Forecasts future availability based on historical data and trends.
    """

    __tablename__ = "availability_forecasts"

    room_availability_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_availability.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Forecast Period
    forecast_generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    forecast_horizon_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=90,
    )
    forecast_valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Model Information
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    model_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,  # TIME_SERIES, REGRESSION, ML, HYBRID
    )
    algorithm_used: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Training Data
    training_data_start_date: Mapped[datetime] = mapped_column(
        DateColumn,
        nullable=False,
    )
    training_data_end_date: Mapped[datetime] = mapped_column(
        DateColumn,
        nullable=False,
    )
    data_points_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Model Performance
    model_accuracy: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # Percentage
    )
    mean_absolute_error: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    confidence_interval: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # Percentage
    )

    # Daily Forecasts
    daily_forecasts: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )  # {date: {available_beds, occupancy_rate, confidence}}

    # Weekly Aggregates
    weekly_forecasts: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Monthly Aggregates
    monthly_forecasts: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Next 30 Days Summary
    avg_availability_next_30d: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    avg_occupancy_next_30d: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    expected_full_days_next_30d: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Peak Periods
    peak_demand_dates: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    low_demand_dates: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Seasonal Patterns
    seasonal_trends: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    holiday_impact: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Revenue Forecast
    forecasted_revenue_30d: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    forecasted_revenue_90d: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    # Recommendations
    pricing_recommendations: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    capacity_recommendations: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Uncertainty Factors
    uncertainty_factors: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    external_factors_considered: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Validation
    last_validated: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    validation_accuracy: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Update Frequency
    auto_refresh_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    refresh_frequency_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=24,
    )

    # Notes
    forecast_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    assumptions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    room_availability = relationship(
        "RoomAvailability",
        back_populates="forecast",
    )

    def __repr__(self) -> str:
        return (
            f"<AvailabilityForecast(room_availability_id={self.room_availability_id}, "
            f"horizon={self.forecast_horizon_days}d, "
            f"accuracy={self.model_accuracy}%)>"
        )

    def get_forecast_for_date(self, forecast_date: Date) -> Optional[dict]:
        """Get forecast data for specific date."""
        date_str = forecast_date.isoformat()
        return self.daily_forecasts.get(date_str)


class AvailabilityAlert(UUIDMixin, TimestampModel, BaseModel):
    """
    Low availability alerts and notifications.
    
    Manages alerts for critical availability thresholds.
    """

    __tablename__ = "availability_alerts"

    room_availability_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_availability.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Alert Definition
    alert_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,  # LOW_AVAILABILITY, FULL, OVERBOOKED, HIGH_DEMAND, CAPACITY_WARNING
    )
    alert_severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="MEDIUM",  # LOW, MEDIUM, HIGH, CRITICAL
        index=True,
    )
    alert_title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    alert_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Trigger Conditions
    trigger_condition: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    trigger_threshold: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    trigger_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Alert Status
    alert_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ACTIVE",  # ACTIVE, ACKNOWLEDGED, RESOLVED, DISMISSED
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Timing
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    auto_resolve_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Context
    available_beds_at_trigger: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    total_beds_at_trigger: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    occupancy_rate_at_trigger: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )
    context_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Notification
    notifications_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    notification_channels: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,  # EMAIL, SMS, PUSH, IN_APP
    )
    notification_recipients: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Actions
    recommended_actions: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    actions_taken: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    action_taken_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    action_taken_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Escalation
    is_escalated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    escalated_to: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    escalated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    escalation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Auto-resolution
    auto_resolvable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    auto_resolve_condition: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    # Acknowledgment
    acknowledged_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    acknowledgment_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Resolution
    resolved_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    resolution_method: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,  # AUTO, MANUAL, CAPACITY_INCREASED, DEMAND_DECREASED
    )

    # Analytics
    response_time_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    resolution_time_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Notes
    alert_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    room_availability = relationship(
        "RoomAvailability",
        back_populates="alerts",
    )

    __table_args__ = (
        Index("ix_alert_type_status", "alert_type", "alert_status"),
        Index("ix_alert_severity_active", "alert_severity", "is_active"),
        Index("ix_alert_triggered", "triggered_at", "alert_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<AvailabilityAlert(type={self.alert_type}, "
            f"severity={self.alert_severity}, status={self.alert_status})>"
        )

    def acknowledge(self, user_id: str, notes: Optional[str] = None) -> None:
        """Acknowledge the alert."""
        self.acknowledged_at = datetime.utcnow()
        self.acknowledged_by = user_id
        self.acknowledgment_notes = notes
        if self.alert_status == "ACTIVE":
            self.alert_status = "ACKNOWLEDGED"

    def resolve(
        self,
        user_id: str,
        method: str,
        notes: Optional[str] = None,
    ) -> None:
        """Resolve the alert."""
        self.resolved_at = datetime.utcnow()
        self.resolved_by = user_id
        self.resolution_method = method
        self.resolution_notes = notes
        self.alert_status = "RESOLVED"
        self.is_active = False

        # Calculate resolution time
        if self.triggered_at:
            duration = datetime.utcnow() - self.triggered_at
            self.resolution_time_minutes = int(duration.total_seconds() / 60)


class AvailabilityOptimization(UUIDMixin, TimestampModel, BaseModel):
    """
    Availability optimization algorithms and recommendations.
    
    Analyzes and optimizes availability management strategies.
    """

    __tablename__ = "availability_optimizations"

    room_availability_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("room_availability.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Optimization Run
    optimization_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    optimization_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,  # OCCUPANCY, REVENUE, UTILIZATION, BALANCED
    )
    optimization_algorithm: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Analysis Period
    analysis_start_date: Mapped[datetime] = mapped_column(
        DateColumn,
        nullable=False,
    )
    analysis_end_date: Mapped[datetime] = mapped_column(
        DateColumn,
        nullable=False,
    )
    data_points_analyzed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Current Performance
    current_occupancy_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )
    current_utilization_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )
    current_revenue_per_day: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    current_turnover_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )

    # Optimization Targets
    target_occupancy_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )
    target_revenue_increase: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )

    # Recommendations
    recommendations: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    priority_actions: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
    )

    # Pricing Optimization
    optimal_price_range_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    optimal_price_range_max: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    dynamic_pricing_suggestion: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Capacity Optimization
    optimal_available_beds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    capacity_utilization_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 2),
        nullable=True,  # 1.00 - 10.00
    )

    # Marketing Optimization
    target_market_segments: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    promotional_periods: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Predicted Impact
    predicted_occupancy_improvement: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    predicted_revenue_improvement: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    predicted_efficiency_gain: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Risk Assessment
    risk_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="LOW",  # LOW, MEDIUM, HIGH
    )
    risk_factors: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    mitigation_strategies: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Implementation
    implemented: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    implementation_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    implementation_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # Percentage of recommendations implemented
    )

    # Results Tracking
    actual_occupancy_change: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    actual_revenue_change: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    optimization_effectiveness: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,  # Percentage
    )

    # Next Optimization
    next_optimization_due: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    optimization_frequency_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
    )

    # Notes
    optimization_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    implementation_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship
    room_availability = relationship(
        "RoomAvailability",
        back_populates="optimization",
    )

    def __repr__(self) -> str:
        return (
            f"<AvailabilityOptimization(room_availability_id={self.room_availability_id}, "
            f"type={self.optimization_type}, implemented={self.implemented})>"
        )

    @property
    def improvement_potential(self) -> Decimal:
        """Calculate total improvement potential."""
        if not self.predicted_occupancy_improvement:
            return Decimal("0.00")
        
        occupancy_potential = self.predicted_occupancy_improvement or Decimal("0.00")
        revenue_potential = self.predicted_revenue_improvement or Decimal("0.00")
        
        # Weighted average (60% revenue, 40% occupancy)
        return Decimal(
            (revenue_potential * Decimal("0.6") + occupancy_potential * Decimal("0.4"))
        ).quantize(Decimal("0.01"))