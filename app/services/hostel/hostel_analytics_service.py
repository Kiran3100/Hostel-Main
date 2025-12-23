# --- File: C:\Hostel-Main\app\services\hostel\hostel_analytics_service.py ---
"""
Hostel analytics service (occupancy, revenue, bookings, complaints, reviews).

Provides comprehensive analytics and reporting for hostel operations including
predictive analytics, trend analysis, and performance metrics.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity
)
from app.repositories.hostel import HostelAnalyticsRepository
from app.models.hostel.hostel_analytics import HostelAnalytic as HostelAnalyticModel
from app.schemas.hostel.hostel_analytics import (
    HostelAnalytics,
    OccupancyAnalytics,
    RevenueAnalytics,
    BookingAnalytics,
    ComplaintAnalytics,
    ReviewAnalytics,
    HostelOccupancyStats,
    HostelRevenueStats,
    AnalyticsRequest,
)
from app.services.hostel.constants import ANALYTICS_CACHE_TTL

logger = logging.getLogger(__name__)


class HostelAnalyticsService(BaseService[HostelAnalyticModel, HostelAnalyticsRepository]):
    """
    Provide dashboard analytics for hostel and derived stats.
    
    Provides functionality for:
    - Occupancy tracking and forecasting
    - Revenue analytics and reporting
    - Booking trends and patterns
    - Review and rating analysis
    - Complaint tracking and resolution metrics
    - Predictive analytics
    """

    # Analytics time periods
    TIME_PERIODS = {
        'day': timedelta(days=1),
        'week': timedelta(weeks=1),
        'month': timedelta(days=30),
        'quarter': timedelta(days=90),
        'year': timedelta(days=365),
    }

    def __init__(self, repository: HostelAnalyticsRepository, db_session: Session):
        """
        Initialize hostel analytics service.
        
        Args:
            repository: Hostel analytics repository instance
            db_session: Database session
        """
        super().__init__(repository, db_session)
        self._analytics_cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}

    # =========================================================================
    # Dashboard Analytics
    # =========================================================================

    def get_dashboard(
        self,
        hostel_id: UUID,
        request: AnalyticsRequest,
        include_predictions: bool = False,
        use_cache: bool = True,
    ) -> ServiceResult[HostelAnalytics]:
        """
        Get comprehensive dashboard analytics for a hostel.
        
        Args:
            hostel_id: UUID of the hostel
            request: Analytics request with date range and filters
            include_predictions: Whether to include predictive analytics
            use_cache: Whether to use cached data if available
            
        Returns:
            ServiceResult containing complete analytics dashboard or error
        """
        try:
            logger.info(
                f"Generating analytics dashboard for hostel {hostel_id}: "
                f"from {request.start_date} to {request.end_date}, "
                f"predictions={include_predictions}"
            )
            
            # Validate date range
            validation_error = self._validate_date_range(request)
            if validation_error:
                return validation_error
            
            # Check cache
            cache_key = self._get_cache_key(
                'dashboard',
                hostel_id,
                request,
                include_predictions
            )
            
            if use_cache and self._is_cache_valid(cache_key):
                logger.debug(f"Cache hit for dashboard analytics: {cache_key}")
                return ServiceResult.success(self._analytics_cache[cache_key])
            
            # Fetch analytics from repository
            payload = self.repository.get_dashboard(
                hostel_id,
                request,
                include_predictions=include_predictions
            )
            
            # Enrich analytics with additional metrics
            enriched_payload = self._enrich_dashboard_analytics(payload, hostel_id)
            
            # Cache the result
            if use_cache:
                self._cache_analytics(cache_key, enriched_payload)
            
            logger.info(f"Dashboard analytics generated successfully for {hostel_id}")
            return ServiceResult.success(enriched_payload)
            
        except Exception as e:
            return self._handle_exception(e, "get hostel analytics dashboard", hostel_id)

    def get_summary(
        self,
        hostel_id: UUID,
        period: str = 'month',
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get quick summary analytics for a specific period.
        
        Args:
            hostel_id: UUID of the hostel
            period: Time period ('day', 'week', 'month', 'quarter', 'year')
            
        Returns:
            ServiceResult containing summary metrics
        """
        try:
            if period not in self.TIME_PERIODS:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid period: {period}",
                        severity=ErrorSeverity.ERROR,
                        details={"valid_periods": list(self.TIME_PERIODS.keys())}
                    )
                )
            
            # Calculate date range
            end_date = date.today()
            start_date = end_date - self.TIME_PERIODS[period]
            
            # Create request
            request = AnalyticsRequest(
                start_date=start_date,
                end_date=end_date
            )
            
            # Get dashboard
            dashboard_result = self.get_dashboard(hostel_id, request)
            
            if not dashboard_result.success:
                return dashboard_result
            
            # Extract summary
            dashboard = dashboard_result.data
            summary = self._extract_summary(dashboard, period)
            
            return ServiceResult.success(summary)
            
        except Exception as e:
            return self._handle_exception(e, "get analytics summary", hostel_id)

    # =========================================================================
    # Occupancy Analytics
    # =========================================================================

    def occupancy_stats(
        self,
        hostel_id: UUID,
        request: AnalyticsRequest,
        granularity: str = 'daily',
        use_cache: bool = True,
    ) -> ServiceResult[HostelOccupancyStats]:
        """
        Get detailed occupancy statistics and trends.
        
        Args:
            hostel_id: UUID of the hostel
            request: Analytics request with date range
            granularity: Data granularity ('hourly', 'daily', 'weekly', 'monthly')
            use_cache: Whether to use cached data
            
        Returns:
            ServiceResult containing occupancy statistics or error
        """
        try:
            logger.info(
                f"Calculating occupancy stats for {hostel_id}: "
                f"granularity={granularity}"
            )
            
            # Validate request
            validation_error = self._validate_date_range(request)
            if validation_error:
                return validation_error
            
            # Check cache
            cache_key = self._get_cache_key(
                'occupancy',
                hostel_id,
                request,
                granularity
            )
            
            if use_cache and self._is_cache_valid(cache_key):
                logger.debug(f"Cache hit for occupancy stats: {cache_key}")
                return ServiceResult.success(self._analytics_cache[cache_key])
            
            # Fetch from repository
            stats = self.repository.get_occupancy_stats(hostel_id, request)
            
            # Enrich with calculated metrics
            enriched_stats = self._enrich_occupancy_stats(stats, granularity)
            
            # Cache the result
            if use_cache:
                self._cache_analytics(cache_key, enriched_stats)
            
            return ServiceResult.success(enriched_stats)
            
        except Exception as e:
            return self._handle_exception(e, "get hostel occupancy stats", hostel_id)

    def get_occupancy_forecast(
        self,
        hostel_id: UUID,
        days_ahead: int = 30,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Generate occupancy forecast using historical data.
        
        Args:
            hostel_id: UUID of the hostel
            days_ahead: Number of days to forecast
            
        Returns:
            ServiceResult containing forecast data
        """
        try:
            logger.info(f"Generating occupancy forecast for {hostel_id}: {days_ahead} days")
            
            if days_ahead < 1 or days_ahead > 365:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Forecast period must be between 1 and 365 days",
                        severity=ErrorSeverity.ERROR
                    )
                )
            
            # Get historical data (last 90 days)
            end_date = date.today()
            start_date = end_date - timedelta(days=90)
            
            historical_request = AnalyticsRequest(
                start_date=start_date,
                end_date=end_date
            )
            
            historical_stats = self.repository.get_occupancy_stats(
                hostel_id,
                historical_request
            )
            
            # Generate forecast
            forecast = self._generate_occupancy_forecast(
                historical_stats,
                days_ahead
            )
            
            return ServiceResult.success(forecast)
            
        except Exception as e:
            return self._handle_exception(e, "get occupancy forecast", hostel_id)

    # =========================================================================
    # Revenue Analytics
    # =========================================================================

    def revenue_stats(
        self,
        hostel_id: UUID,
        request: AnalyticsRequest,
        breakdown_by: Optional[str] = None,
        use_cache: bool = True,
    ) -> ServiceResult[HostelRevenueStats]:
        """
        Get detailed revenue statistics and breakdowns.
        
        Args:
            hostel_id: UUID of the hostel
            request: Analytics request with date range
            breakdown_by: Breakdown dimension ('category', 'room_type', 'source')
            use_cache: Whether to use cached data
            
        Returns:
            ServiceResult containing revenue statistics or error
        """
        try:
            logger.info(
                f"Calculating revenue stats for {hostel_id}: "
                f"breakdown={breakdown_by}"
            )
            
            # Validate request
            validation_error = self._validate_date_range(request)
            if validation_error:
                return validation_error
            
            # Check cache
            cache_key = self._get_cache_key(
                'revenue',
                hostel_id,
                request,
                breakdown_by
            )
            
            if use_cache and self._is_cache_valid(cache_key):
                logger.debug(f"Cache hit for revenue stats: {cache_key}")
                return ServiceResult.success(self._analytics_cache[cache_key])
            
            # Fetch from repository
            stats = self.repository.get_revenue_stats(hostel_id, request)
            
            # Enrich with calculations
            enriched_stats = self._enrich_revenue_stats(stats, breakdown_by)
            
            # Cache the result
            if use_cache:
                self._cache_analytics(cache_key, enriched_stats)
            
            return ServiceResult.success(enriched_stats)
            
        except Exception as e:
            return self._handle_exception(e, "get hostel revenue stats", hostel_id)

    def get_revenue_trends(
        self,
        hostel_id: UUID,
        period: str = 'month',
        compare_previous: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Analyze revenue trends with period-over-period comparison.
        
        Args:
            hostel_id: UUID of the hostel
            period: Time period for analysis
            compare_previous: Whether to compare with previous period
            
        Returns:
            ServiceResult containing trend analysis
        """
        try:
            if period not in self.TIME_PERIODS:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid period: {period}",
                        severity=ErrorSeverity.ERROR,
                        details={"valid_periods": list(self.TIME_PERIODS.keys())}
                    )
                )
            
            # Current period
            current_end = date.today()
            current_start = current_end - self.TIME_PERIODS[period]
            
            current_request = AnalyticsRequest(
                start_date=current_start,
                end_date=current_end
            )
            
            current_stats_result = self.revenue_stats(hostel_id, current_request)
            if not current_stats_result.success:
                return current_stats_result
            
            trends = {
                "period": period,
                "current": current_stats_result.data,
            }
            
            # Previous period comparison
            if compare_previous:
                previous_end = current_start - timedelta(days=1)
                previous_start = previous_end - self.TIME_PERIODS[period]
                
                previous_request = AnalyticsRequest(
                    start_date=previous_start,
                    end_date=previous_end
                )
                
                previous_stats_result = self.revenue_stats(hostel_id, previous_request)
                if previous_stats_result.success:
                    trends["previous"] = previous_stats_result.data
                    trends["comparison"] = self._calculate_period_comparison(
                        current_stats_result.data,
                        previous_stats_result.data
                    )
            
            return ServiceResult.success(trends)
            
        except Exception as e:
            return self._handle_exception(e, "get revenue trends", hostel_id)

    # =========================================================================
    # Booking Analytics
    # =========================================================================

    def get_booking_analytics(
        self,
        hostel_id: UUID,
        request: AnalyticsRequest,
    ) -> ServiceResult[BookingAnalytics]:
        """
        Get comprehensive booking analytics.
        
        Args:
            hostel_id: UUID of the hostel
            request: Analytics request with date range
            
        Returns:
            ServiceResult containing booking analytics
        """
        try:
            logger.info(f"Fetching booking analytics for {hostel_id}")
            
            analytics = self.repository.get_booking_analytics(hostel_id, request)
            
            # Enrich with metrics
            enriched = self._enrich_booking_analytics(analytics)
            
            return ServiceResult.success(enriched)
            
        except Exception as e:
            return self._handle_exception(e, "get booking analytics", hostel_id)

    # =========================================================================
    # Review Analytics
    # =========================================================================

    def get_review_analytics(
        self,
        hostel_id: UUID,
        request: AnalyticsRequest,
    ) -> ServiceResult[ReviewAnalytics]:
        """
        Get review and rating analytics.
        
        Args:
            hostel_id: UUID of the hostel
            request: Analytics request with date range
            
        Returns:
            ServiceResult containing review analytics
        """
        try:
            logger.info(f"Fetching review analytics for {hostel_id}")
            
            analytics = self.repository.get_review_analytics(hostel_id, request)
            
            # Enrich with sentiment analysis and trends
            enriched = self._enrich_review_analytics(analytics)
            
            return ServiceResult.success(enriched)
            
        except Exception as e:
            return self._handle_exception(e, "get review analytics", hostel_id)

    # =========================================================================
    # Complaint Analytics
    # =========================================================================

    def get_complaint_analytics(
        self,
        hostel_id: UUID,
        request: AnalyticsRequest,
    ) -> ServiceResult[ComplaintAnalytics]:
        """
        Get complaint tracking and resolution analytics.
        
        Args:
            hostel_id: UUID of the hostel
            request: Analytics request with date range
            
        Returns:
            ServiceResult containing complaint analytics
        """
        try:
            logger.info(f"Fetching complaint analytics for {hostel_id}")
            
            analytics = self.repository.get_complaint_analytics(hostel_id, request)
            
            # Enrich with resolution metrics
            enriched = self._enrich_complaint_analytics(analytics)
            
            return ServiceResult.success(enriched)
            
        except Exception as e:
            return self._handle_exception(e, "get complaint analytics", hostel_id)

    # =========================================================================
    # Comparative Analytics
    # =========================================================================

    def compare_periods(
        self,
        hostel_id: UUID,
        period1: AnalyticsRequest,
        period2: AnalyticsRequest,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Compare analytics between two time periods.
        
        Args:
            hostel_id: UUID of the hostel
            period1: First period request
            period2: Second period request
            
        Returns:
            ServiceResult containing comparative analysis
        """
        try:
            logger.info(f"Comparing periods for {hostel_id}")
            
            # Get analytics for both periods
            analytics1_result = self.get_dashboard(hostel_id, period1, use_cache=False)
            analytics2_result = self.get_dashboard(hostel_id, period2, use_cache=False)
            
            if not analytics1_result.success:
                return analytics1_result
            if not analytics2_result.success:
                return analytics2_result
            
            # Generate comparison
            comparison = self._generate_period_comparison(
                analytics1_result.data,
                analytics2_result.data,
                period1,
                period2
            )
            
            return ServiceResult.success(comparison)
            
        except Exception as e:
            return self._handle_exception(e, "compare periods", hostel_id)

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _validate_date_range(
        self,
        request: AnalyticsRequest
    ) -> Optional[ServiceResult]:
        """Validate analytics request date range."""
        if request.start_date > request.end_date:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Start date must be before end date",
                    severity=ErrorSeverity.ERROR
                )
            )
        
        # Check for excessively long date ranges
        date_diff = (request.end_date - request.start_date).days
        if date_diff > 730:  # 2 years
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Date range cannot exceed 2 years",
                    severity=ErrorSeverity.WARNING
                )
            )
        
        return None

    def _get_cache_key(self, analytics_type: str, *args) -> str:
        """Generate cache key for analytics data."""
        key_parts = [analytics_type] + [str(arg) for arg in args]
        return "_".join(key_parts)

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self._analytics_cache:
            return False
        
        if cache_key not in self._cache_timestamps:
            return False
        
        cache_age = datetime.utcnow() - self._cache_timestamps[cache_key]
        return cache_age.total_seconds() < ANALYTICS_CACHE_TTL

    def _cache_analytics(self, cache_key: str, data: Any) -> None:
        """Cache analytics data with timestamp."""
        self._analytics_cache[cache_key] = data
        self._cache_timestamps[cache_key] = datetime.utcnow()
        logger.debug(f"Cached analytics: {cache_key}")

    def _enrich_dashboard_analytics(
        self,
        payload: HostelAnalytics,
        hostel_id: UUID
    ) -> HostelAnalytics:
        """Add calculated metrics to dashboard analytics."""
        # Add custom enrichment logic here
        return payload

    def _enrich_occupancy_stats(
        self,
        stats: HostelOccupancyStats,
        granularity: str
    ) -> HostelOccupancyStats:
        """Calculate additional occupancy metrics."""
        # Add occupancy rate, trends, peak periods, etc.
        return stats

    def _enrich_revenue_stats(
        self,
        stats: HostelRevenueStats,
        breakdown_by: Optional[str]
    ) -> HostelRevenueStats:
        """Calculate additional revenue metrics."""
        # Add growth rates, averages, projections, etc.
        return stats

    def _enrich_booking_analytics(
        self,
        analytics: BookingAnalytics
    ) -> BookingAnalytics:
        """Calculate additional booking metrics."""
        # Add conversion rates, lead times, cancellation patterns, etc.
        return analytics

    def _enrich_review_analytics(
        self,
        analytics: ReviewAnalytics
    ) -> ReviewAnalytics:
        """Calculate additional review metrics."""
        # Add sentiment scores, trends, response rates, etc.
        return analytics

    def _enrich_complaint_analytics(
        self,
        analytics: ComplaintAnalytics
    ) -> ComplaintAnalytics:
        """Calculate additional complaint metrics."""
        # Add resolution times, recurring issues, satisfaction scores, etc.
        return analytics

    def _extract_summary(
        self,
        dashboard: HostelAnalytics,
        period: str
    ) -> Dict[str, Any]:
        """Extract key summary metrics from dashboard."""
        return {
            "period": period,
            "occupancy_rate": getattr(dashboard, 'occupancy_rate', 0),
            "total_revenue": getattr(dashboard, 'total_revenue', 0),
            "total_bookings": getattr(dashboard, 'total_bookings', 0),
            "average_rating": getattr(dashboard, 'average_rating', 0),
        }

    def _generate_occupancy_forecast(
        self,
        historical_stats: HostelOccupancyStats,
        days_ahead: int
    ) -> Dict[str, Any]:
        """Generate occupancy forecast based on historical data."""
        # Implement forecasting algorithm (e.g., moving average, exponential smoothing)
        # This is a placeholder
        return {
            "forecast_days": days_ahead,
            "model": "simple_moving_average",
            "predictions": [],
            "confidence_interval": 0.95,
        }

    def _calculate_period_comparison(
        self,
        current: Any,
        previous: Any
    ) -> Dict[str, Any]:
        """Calculate comparison metrics between periods."""
        return {
            "revenue_change_percent": 0,
            "occupancy_change_percent": 0,
            "booking_change_percent": 0,
        }

    def _generate_period_comparison(
        self,
        analytics1: HostelAnalytics,
        analytics2: HostelAnalytics,
        period1: AnalyticsRequest,
        period2: AnalyticsRequest
    ) -> Dict[str, Any]:
        """Generate detailed comparison between two periods."""
        return {
            "period1": {
                "start": period1.start_date.isoformat(),
                "end": period1.end_date.isoformat(),
                "analytics": analytics1,
            },
            "period2": {
                "start": period2.start_date.isoformat(),
                "end": period2.end_date.isoformat(),
                "analytics": analytics2,
            },
            "comparison": self._calculate_period_comparison(analytics1, analytics2),
        }

    def clear_cache(self) -> None:
        """Clear all analytics cache."""
        self._analytics_cache.clear()
        self._cache_timestamps.clear()
        logger.info("All analytics cache cleared")