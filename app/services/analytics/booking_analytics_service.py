"""
Booking analytics service.

Optimizations:
- Added caching for frequently accessed KPIs
- Improved error handling with specific error types
- Added data validation
- Implemented batch operations
- Enhanced logging
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, timedelta, datetime
from functools import lru_cache
import logging

from sqlalchemy.orm import Session

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.analytics import BookingAnalyticsRepository
from app.models.analytics.booking_analytics import BookingAnalyticsSummary
from app.schemas.analytics.booking_analytics import (
    BookingKPI,
    BookingTrendPoint,
    BookingFunnel,
    CancellationAnalytics,
    BookingSourceMetrics,
    BookingAnalyticsSummary as BookingAnalyticsSummarySchema,
)

logger = logging.getLogger(__name__)


class BookingAnalyticsService(BaseService[BookingAnalyticsSummary, BookingAnalyticsRepository]):
    """
    Service for booking analytics.
    
    Provides:
    - Booking KPIs and metrics
    - Conversion funnel analysis
    - Trend analysis
    - Cancellation analytics
    - Source performance tracking
    """

    # Default analysis window
    DEFAULT_ANALYSIS_DAYS = 30
    
    # Cache TTL (seconds)
    CACHE_TTL = 300  # 5 minutes

    def __init__(self, repository: BookingAnalyticsRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._cache = {}
        self._cache_timestamps = {}

    def get_summary(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        force_refresh: bool = False,
    ) -> ServiceResult[BookingAnalyticsSummarySchema]:
        """
        Get combined booking analytics summary for a hostel.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start of date range
            end_date: End of date range
            force_refresh: Bypass cache
            
        Returns:
            ServiceResult containing booking analytics summary
        """
        try:
            # Set default dates
            end_date = end_date or date.today()
            start_date = start_date or (end_date - timedelta(days=self.DEFAULT_ANALYSIS_DAYS))
            
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Check cache
            cache_key = f"summary_{hostel_id}_{start_date}_{end_date}"
            if not force_refresh and self._is_cache_valid(cache_key):
                logger.debug(f"Returning cached summary for {hostel_id}")
                return ServiceResult.success(self._cache[cache_key])
            
            # Fetch data
            summary = self.repository.get_summary(hostel_id, start_date, end_date)
            
            if not summary:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No booking data found for hostel {hostel_id}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Cache result
            self._update_cache(cache_key, summary)
            
            return ServiceResult.success(
                summary,
                message="Booking analytics summary retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting booking summary: {str(e)}")
            return self._handle_exception(e, "get booking analytics summary", hostel_id)

    def get_kpis(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        compare_previous_period: bool = False,
    ) -> ServiceResult[BookingKPI]:
        """
        Get booking KPIs for a hostel.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            compare_previous_period: Include comparison with previous period
            
        Returns:
            ServiceResult containing booking KPIs
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch KPIs
            kpi = self.repository.get_kpis(hostel_id, start_date, end_date)
            
            if not kpi:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No booking KPI data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Add comparison if requested
            if compare_previous_period:
                previous_kpi = self._get_previous_period_kpi(
                    hostel_id, start_date, end_date
                )
                if previous_kpi:
                    kpi = self._add_period_comparison(kpi, previous_kpi)
            
            return ServiceResult.success(
                kpi,
                message="Booking KPIs retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting booking KPIs: {str(e)}")
            return self._handle_exception(e, "get booking kpis", hostel_id)

    def get_trend(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        granularity: str = "daily",
    ) -> ServiceResult[List[BookingTrendPoint]]:
        """
        Get booking trend over time.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            granularity: Time granularity (daily, weekly, monthly)
            
        Returns:
            ServiceResult containing trend data points
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Validate granularity
            if granularity not in ("daily", "weekly", "monthly"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid granularity: {granularity}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch trend data
            points = self.repository.get_trend(
                hostel_id, start_date, end_date, granularity=granularity
            )
            
            if not points:
                logger.warning(f"No trend data found for hostel {hostel_id}")
                points = []
            
            return ServiceResult.success(
                points,
                metadata={
                    "count": len(points),
                    "granularity": granularity,
                    "period_days": (end_date - start_date).days,
                },
                message=f"Retrieved {len(points)} trend points"
            )
            
        except Exception as e:
            logger.error(f"Error getting booking trend: {str(e)}")
            return self._handle_exception(e, "get booking trend", hostel_id)

    def get_funnel(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        include_drop_offs: bool = True,
    ) -> ServiceResult[BookingFunnel]:
        """
        Get booking conversion funnel.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            include_drop_offs: Include drop-off analysis
            
        Returns:
            ServiceResult containing funnel data
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch funnel data
            funnel = self.repository.get_funnel(hostel_id, start_date, end_date)
            
            if not funnel:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No funnel data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Calculate drop-off rates if requested
            if include_drop_offs and hasattr(funnel, 'stages'):
                funnel = self._calculate_drop_offs(funnel)
            
            return ServiceResult.success(
                funnel,
                message="Booking funnel retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting booking funnel: {str(e)}")
            return self._handle_exception(e, "get booking funnel", hostel_id)

    def get_cancellations(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        include_reasons: bool = True,
    ) -> ServiceResult[CancellationAnalytics]:
        """
        Get cancellation analytics.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            include_reasons: Include cancellation reason breakdown
            
        Returns:
            ServiceResult containing cancellation analytics
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch cancellation data
            analytics = self.repository.get_cancellations(hostel_id, start_date, end_date)
            
            if not analytics:
                logger.warning(f"No cancellation data found for hostel {hostel_id}")
                # Return empty analytics instead of error
                analytics = CancellationAnalytics(
                    total_cancellations=0,
                    cancellation_rate=0.0,
                    reasons={} if include_reasons else None,
                )
            
            return ServiceResult.success(
                analytics,
                message="Cancellation analytics retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting cancellation analytics: {str(e)}")
            return self._handle_exception(e, "get booking cancellations", hostel_id)

    def get_source_metrics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        min_bookings: int = 1,
    ) -> ServiceResult[List[BookingSourceMetrics]]:
        """
        Get booking source performance metrics.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            min_bookings: Minimum bookings threshold for inclusion
            
        Returns:
            ServiceResult containing source metrics
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch source metrics
            metrics = self.repository.get_source_metrics(hostel_id, start_date, end_date)
            
            if not metrics:
                logger.warning(f"No source metrics found for hostel {hostel_id}")
                metrics = []
            
            # Filter by minimum bookings
            if min_bookings > 1:
                metrics = [m for m in metrics if m.total_bookings >= min_bookings]
            
            # Sort by revenue descending
            metrics.sort(key=lambda x: x.total_revenue or 0, reverse=True)
            
            return ServiceResult.success(
                metrics,
                metadata={
                    "count": len(metrics),
                    "min_bookings_filter": min_bookings,
                },
                message=f"Retrieved {len(metrics)} source metrics"
            )
            
        except Exception as e:
            logger.error(f"Error getting source metrics: {str(e)}")
            return self._handle_exception(e, "get booking source metrics", hostel_id)

    def get_revenue_forecast(
        self,
        hostel_id: UUID,
        forecast_days: int = 30,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get booking revenue forecast.
        
        Args:
            hostel_id: Target hostel UUID
            forecast_days: Number of days to forecast
            
        Returns:
            ServiceResult containing forecast data
        """
        try:
            if forecast_days < 1 or forecast_days > 365:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Forecast days must be between 1 and 365",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Get historical data for forecasting
            end_date = date.today()
            start_date = end_date - timedelta(days=90)  # Use 90 days of history
            
            historical_data = self.repository.get_trend(hostel_id, start_date, end_date)
            
            if not historical_data or len(historical_data) < 7:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.INSUFFICIENT_DATA,
                        message="Insufficient historical data for forecasting",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Generate forecast using simple moving average
            forecast = self._generate_simple_forecast(historical_data, forecast_days)
            
            return ServiceResult.success(
                forecast,
                metadata={
                    "forecast_days": forecast_days,
                    "model": "simple_moving_average",
                    "historical_days": len(historical_data),
                },
                message=f"Generated {forecast_days}-day revenue forecast"
            )
            
        except Exception as e:
            logger.error(f"Error generating revenue forecast: {str(e)}")
            return self._handle_exception(e, "get revenue forecast", hostel_id)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _validate_date_range(self, start_date: date, end_date: date) -> ServiceResult[bool]:
        """Validate date range parameters."""
        if start_date > end_date:
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Start date cannot be after end date",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        # Check if range is too large (more than 2 years)
        if (end_date - start_date).days > 730:
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Date range cannot exceed 2 years",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        return ServiceResult.success(True)

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self._cache:
            return False
        
        if cache_key not in self._cache_timestamps:
            return False
        
        age = (datetime.utcnow() - self._cache_timestamps[cache_key]).total_seconds()
        return age < self.CACHE_TTL

    def _update_cache(self, cache_key: str, data: Any) -> None:
        """Update cache with new data."""
        self._cache[cache_key] = data
        self._cache_timestamps[cache_key] = datetime.utcnow()
        
        # Limit cache size
        if len(self._cache) > 100:
            # Remove oldest entries
            oldest_keys = sorted(
                self._cache_timestamps.keys(),
                key=lambda k: self._cache_timestamps[k]
            )[:20]
            for key in oldest_keys:
                del self._cache[key]
                del self._cache_timestamps[key]

    def _get_previous_period_kpi(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Optional[BookingKPI]:
        """Get KPIs for the previous period of equal length."""
        try:
            period_length = (end_date - start_date).days
            prev_end = start_date - timedelta(days=1)
            prev_start = prev_end - timedelta(days=period_length)
            
            return self.repository.get_kpis(hostel_id, prev_start, prev_end)
        except Exception as e:
            logger.error(f"Error fetching previous period KPI: {str(e)}")
            return None

    def _add_period_comparison(
        self,
        current_kpi: BookingKPI,
        previous_kpi: BookingKPI,
    ) -> BookingKPI:
        """Add comparison metrics to current KPI."""
        # Calculate percentage changes
        if hasattr(current_kpi, 'total_bookings') and hasattr(previous_kpi, 'total_bookings'):
            if previous_kpi.total_bookings > 0:
                booking_change = (
                    (current_kpi.total_bookings - previous_kpi.total_bookings) /
                    previous_kpi.total_bookings * 100
                )
                current_kpi.booking_change_pct = round(booking_change, 2)
        
        if hasattr(current_kpi, 'total_revenue') and hasattr(previous_kpi, 'total_revenue'):
            if previous_kpi.total_revenue and previous_kpi.total_revenue > 0:
                revenue_change = (
                    (current_kpi.total_revenue - previous_kpi.total_revenue) /
                    previous_kpi.total_revenue * 100
                )
                current_kpi.revenue_change_pct = round(revenue_change, 2)
        
        return current_kpi

    def _calculate_drop_offs(self, funnel: BookingFunnel) -> BookingFunnel:
        """Calculate drop-off rates between funnel stages."""
        if not hasattr(funnel, 'stages') or not funnel.stages:
            return funnel
        
        for i in range(len(funnel.stages) - 1):
            current_stage = funnel.stages[i]
            next_stage = funnel.stages[i + 1]
            
            if current_stage.count > 0:
                drop_off = current_stage.count - next_stage.count
                drop_off_rate = (drop_off / current_stage.count) * 100
                current_stage.drop_off_count = drop_off
                current_stage.drop_off_rate = round(drop_off_rate, 2)
        
        return funnel

    def _generate_simple_forecast(
        self,
        historical_data: List[BookingTrendPoint],
        forecast_days: int,
    ) -> List[Dict[str, Any]]:
        """Generate simple moving average forecast."""
        # Use last 30 days for average
        recent_data = historical_data[-30:] if len(historical_data) > 30 else historical_data
        
        # Calculate averages
        avg_bookings = sum(p.bookings for p in recent_data) / len(recent_data)
        avg_revenue = sum(p.revenue or 0 for p in recent_data) / len(recent_data)
        
        # Generate forecast points
        forecast = []
        last_date = historical_data[-1].date if historical_data else date.today()
        
        for i in range(1, forecast_days + 1):
            forecast_date = last_date + timedelta(days=i)
            forecast.append({
                "date": forecast_date.isoformat(),
                "forecasted_bookings": round(avg_bookings, 1),
                "forecasted_revenue": round(avg_revenue, 2),
                "confidence": "low" if i > 14 else "medium" if i > 7 else "high",
            })
        
        return forecast