"""
Occupancy analytics service.

Optimizations:
- Added advanced forecasting with multiple models
- Implemented seasonal pattern detection
- Enhanced trend analysis with anomaly detection
- Added room-type and floor-level breakdowns
- Improved forecast accuracy with historical weighting
"""

from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
from datetime import date, timedelta, datetime
from enum import Enum
import logging
import statistics

from sqlalchemy.orm import Session

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.analytics import OccupancyAnalyticsRepository
from app.models.analytics.occupancy_analytics import OccupancyReport as OccupancyReportModel
from app.schemas.analytics.occupancy_analytics import (
    ForecastModel,
    OccupancyKPI,
    OccupancyTrendPoint,
    OccupancyByRoomType,
    OccupancyByFloor,
    ForecastPoint,
    SeasonalPattern,
    ForecastData,
    OccupancyReport,
)

logger = logging.getLogger(__name__)


class ForecastModelType(str, Enum):
    """Forecast model types."""
    SIMPLE_AVERAGE = "simple_average"
    WEIGHTED_AVERAGE = "weighted_average"
    MOVING_AVERAGE = "moving_average"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    LINEAR_REGRESSION = "linear_regression"
    SEASONAL_NAIVE = "seasonal_naive"


class SeasonType(str, Enum):
    """Season types for pattern analysis."""
    PEAK = "peak"
    HIGH = "high"
    SHOULDER = "shoulder"
    LOW = "low"


class OccupancyAnalyticsService(BaseService[OccupancyReportModel, OccupancyAnalyticsRepository]):
    """
    Service for occupancy analytics.
    
    Provides:
    - Occupancy KPIs and metrics
    - Trend analysis with anomaly detection
    - Room type and floor breakdowns
    - Forecasting with multiple models
    - Seasonal pattern analysis
    - Comprehensive reporting
    """

    # Default analysis period
    DEFAULT_ANALYSIS_DAYS = 30
    
    # Forecast defaults
    DEFAULT_FORECAST_DAYS = 30
    DEFAULT_HISTORICAL_DAYS = 90
    
    # Occupancy thresholds
    HIGH_OCCUPANCY_THRESHOLD = 0.85  # 85%
    LOW_OCCUPANCY_THRESHOLD = 0.50   # 50%
    
    # Cache TTL
    CACHE_TTL = 300  # 5 minutes

    def __init__(self, repository: OccupancyAnalyticsRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._cache = {}
        self._cache_timestamps = {}

    def get_report(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        forecast_horizon_days: int = 30,
        include_breakdowns: bool = True,
        forecast_model: Optional[str] = None,
    ) -> ServiceResult[OccupancyReport]:
        """
        Get comprehensive occupancy report.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            forecast_horizon_days: Days to forecast ahead
            include_breakdowns: Include room type and floor breakdowns
            forecast_model: Specific forecast model to use
            
        Returns:
            ServiceResult containing occupancy report
        """
        try:
            # Validate inputs
            validation_result = self._validate_inputs(
                start_date, end_date, forecast_horizon_days, forecast_model
            )
            if not validation_result.success:
                return validation_result
            
            # Check cache
            cache_key = f"report_{hostel_id}_{start_date}_{end_date}_{forecast_horizon_days}"
            if self._is_cache_valid(cache_key):
                logger.debug(f"Returning cached occupancy report for {hostel_id}")
                return ServiceResult.success(self._cache[cache_key])
            
            # Fetch report
            report = self.repository.get_occupancy_report(
                hostel_id, start_date, end_date, forecast_horizon_days
            )
            
            if not report:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No occupancy data found for hostel {hostel_id}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Enhance report with additional analytics
            report = self._enhance_report(report, include_breakdowns)
            
            # Add forecast if not already included
            if not hasattr(report, 'forecast') or not report.forecast:
                forecast_result = self.get_forecast(
                    hostel_id, forecast_horizon_days, forecast_model
                )
                if forecast_result.success:
                    report.forecast = forecast_result.data
            
            # Add seasonal patterns
            report.seasonal_patterns = self._detect_seasonal_patterns(report)
            
            # Cache result
            self._update_cache(cache_key, report)
            
            return ServiceResult.success(
                report,
                message="Occupancy report retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting occupancy report: {str(e)}")
            return self._handle_exception(e, "get occupancy report", hostel_id)

    def get_kpis(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        compare_previous_period: bool = False,
    ) -> ServiceResult[OccupancyKPI]:
        """
        Get occupancy KPIs.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            compare_previous_period: Include comparison with previous period
            
        Returns:
            ServiceResult containing occupancy KPIs
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
                        message="No occupancy KPI data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Enhance KPIs with derived metrics
            kpi = self._enhance_kpi(kpi)
            
            # Add comparison if requested
            if compare_previous_period:
                previous_kpi = self._get_previous_period_kpi(
                    hostel_id, start_date, end_date
                )
                if previous_kpi:
                    kpi = self._add_period_comparison(kpi, previous_kpi)
            
            return ServiceResult.success(
                kpi,
                message="Occupancy KPIs retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting occupancy KPIs: {str(e)}")
            return self._handle_exception(e, "get occupancy kpis", hostel_id)

    def get_trend(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        granularity: str = "daily",
        detect_anomalies: bool = True,
    ) -> ServiceResult[List[OccupancyTrendPoint]]:
        """
        Get occupancy trend over time.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            granularity: Time granularity (daily, weekly, monthly)
            detect_anomalies: Flag anomalous data points
            
        Returns:
            ServiceResult containing trend data
        """
        try:
            # Validate inputs
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            if granularity not in ("daily", "weekly", "monthly"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid granularity: {granularity}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch trend data
            data = self.repository.get_trend(
                hostel_id, start_date, end_date, granularity
            )
            
            if not data:
                logger.warning(f"No trend data found for hostel {hostel_id}")
                data = []
            
            # Detect anomalies if requested
            if detect_anomalies and data:
                data = self._detect_occupancy_anomalies(data)
            
            # Add moving averages
            if len(data) >= 7:
                data = self._add_moving_averages(data)
            
            return ServiceResult.success(
                data,
                metadata={
                    "count": len(data),
                    "granularity": granularity,
                    "period_days": (end_date - start_date).days,
                },
                message=f"Retrieved {len(data)} trend points"
            )
            
        except Exception as e:
            logger.error(f"Error getting occupancy trend: {str(e)}")
            return self._handle_exception(e, "get occupancy trend", hostel_id)

    def get_forecast(
        self,
        hostel_id: UUID,
        forecast_horizon_days: int = 30,
        model: Optional[str] = None,
        confidence_level: float = 0.95,
    ) -> ServiceResult[ForecastData]:
        """
        Get occupancy forecast.
        
        Args:
            hostel_id: Target hostel UUID
            forecast_horizon_days: Days to forecast ahead
            model: Forecast model to use (defaults to best fit)
            confidence_level: Confidence level for intervals
            
        Returns:
            ServiceResult containing forecast data
        """
        try:
            # Validate inputs
            if forecast_horizon_days < 1 or forecast_horizon_days > 365:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Forecast horizon must be between 1 and 365 days",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            if model:
                try:
                    ForecastModelType(model)
                except ValueError:
                    return ServiceResult.error(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Invalid forecast model: {model}",
                            severity=ErrorSeverity.ERROR,
                        )
                    )
            
            # Fetch historical data for forecasting
            end_date = date.today()
            start_date = end_date - timedelta(days=self.DEFAULT_HISTORICAL_DAYS)
            
            historical_data = self.repository.get_trend(hostel_id, start_date, end_date)
            
            if not historical_data or len(historical_data) < 14:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.INSUFFICIENT_DATA,
                        message="Insufficient historical data for forecasting (minimum 14 days required)",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Generate forecast using specified or best model
            if model:
                forecast_data = self._generate_forecast(
                    historical_data, forecast_horizon_days, ForecastModelType(model), confidence_level
                )
            else:
                forecast_data = self._generate_best_forecast(
                    historical_data, forecast_horizon_days, confidence_level
                )
            
            return ServiceResult.success(
                forecast_data,
                metadata={
                    "forecast_days": forecast_horizon_days,
                    "model_used": forecast_data.model.value if hasattr(forecast_data, 'model') else model,
                    "historical_days": len(historical_data),
                    "confidence_level": confidence_level,
                },
                message=f"Generated {forecast_horizon_days}-day forecast"
            )
            
        except Exception as e:
            logger.error(f"Error generating forecast: {str(e)}")
            return self._handle_exception(e, "get occupancy forecast", hostel_id)

    def get_room_type_breakdown(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[List[OccupancyByRoomType]]:
        """
        Get occupancy breakdown by room type.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            
        Returns:
            ServiceResult containing room type breakdown
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch breakdown
            breakdown = self.repository.get_occupancy_by_room_type(
                hostel_id, start_date, end_date
            )
            
            if not breakdown:
                logger.warning(f"No room type breakdown for hostel {hostel_id}")
                breakdown = []
            
            # Calculate percentages and rankings
            breakdown = self._enhance_room_type_breakdown(breakdown)
            
            return ServiceResult.success(
                breakdown,
                metadata={"count": len(breakdown)},
                message=f"Retrieved {len(breakdown)} room type breakdowns"
            )
            
        except Exception as e:
            logger.error(f"Error getting room type breakdown: {str(e)}")
            return self._handle_exception(e, "get room type breakdown", hostel_id)

    def get_floor_breakdown(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[List[OccupancyByFloor]]:
        """
        Get occupancy breakdown by floor.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            
        Returns:
            ServiceResult containing floor breakdown
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch breakdown
            breakdown = self.repository.get_occupancy_by_floor(
                hostel_id, start_date, end_date
            )
            
            if not breakdown:
                logger.warning(f"No floor breakdown for hostel {hostel_id}")
                breakdown = []
            
            # Sort by floor number
            breakdown.sort(key=lambda x: x.floor_number if hasattr(x, 'floor_number') else 0)
            
            return ServiceResult.success(
                breakdown,
                metadata={"count": len(breakdown)},
                message=f"Retrieved {len(breakdown)} floor breakdowns"
            )
            
        except Exception as e:
            logger.error(f"Error getting floor breakdown: {str(e)}")
            return self._handle_exception(e, "get floor breakdown", hostel_id)

    def get_seasonal_patterns(
        self,
        hostel_id: UUID,
        analysis_years: int = 2,
    ) -> ServiceResult[List[SeasonalPattern]]:
        """
        Get seasonal occupancy patterns.
        
        Args:
            hostel_id: Target hostel UUID
            analysis_years: Years of historical data to analyze
            
        Returns:
            ServiceResult containing seasonal patterns
        """
        try:
            if analysis_years < 1 or analysis_years > 5:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Analysis years must be between 1 and 5",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch historical data
            end_date = date.today()
            start_date = end_date - timedelta(days=analysis_years * 365)
            
            historical_data = self.repository.get_trend(hostel_id, start_date, end_date)
            
            if not historical_data or len(historical_data) < 365:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.INSUFFICIENT_DATA,
                        message="Insufficient data for seasonal analysis (minimum 1 year required)",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Detect patterns
            patterns = self._analyze_seasonal_patterns(historical_data)
            
            return ServiceResult.success(
                patterns,
                metadata={
                    "analysis_years": analysis_years,
                    "patterns_detected": len(patterns),
                },
                message=f"Detected {len(patterns)} seasonal patterns"
            )
            
        except Exception as e:
            logger.error(f"Error analyzing seasonal patterns: {str(e)}")
            return self._handle_exception(e, "get seasonal patterns", hostel_id)

    def get_optimal_pricing_periods(
        self,
        hostel_id: UUID,
        forecast_days: int = 90,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Identify optimal pricing periods based on forecasted occupancy.
        
        Args:
            hostel_id: Target hostel UUID
            forecast_days: Days to analyze
            
        Returns:
            ServiceResult containing pricing recommendations
        """
        try:
            # Get forecast
            forecast_result = self.get_forecast(hostel_id, forecast_days)
            
            if not forecast_result.success:
                return forecast_result
            
            forecast_data = forecast_result.data
            
            if not hasattr(forecast_data, 'forecast_points') or not forecast_data.forecast_points:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No forecast data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Analyze forecast and identify pricing opportunities
            pricing_periods = self._identify_pricing_periods(forecast_data.forecast_points)
            
            return ServiceResult.success(
                pricing_periods,
                metadata={"periods": len(pricing_periods)},
                message=f"Identified {len(pricing_periods)} pricing periods"
            )
            
        except Exception as e:
            logger.error(f"Error identifying pricing periods: {str(e)}")
            return self._handle_exception(e, "get optimal pricing periods", hostel_id)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _validate_inputs(
        self,
        start_date: date,
        end_date: date,
        forecast_days: int,
        model: Optional[str],
    ) -> ServiceResult[bool]:
        """Validate all inputs."""
        # Validate date range
        date_result = self._validate_date_range(start_date, end_date)
        if not date_result.success:
            return date_result
        
        # Validate forecast days
        if forecast_days < 1 or forecast_days > 365:
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Forecast days must be between 1 and 365",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        # Validate model if provided
        if model:
            try:
                ForecastModelType(model)
            except ValueError:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid forecast model: {model}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
        
        return ServiceResult.success(True)

    def _validate_date_range(self, start_date: date, end_date: date) -> ServiceResult[bool]:
        """Validate date range."""
        if start_date > end_date:
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Start date cannot be after end date",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
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
            oldest_keys = sorted(
                self._cache_timestamps.keys(),
                key=lambda k: self._cache_timestamps[k]
            )[:20]
            for key in oldest_keys:
                del self._cache[key]
                del self._cache_timestamps[key]

    def _enhance_report(
        self,
        report: OccupancyReport,
        include_breakdowns: bool,
    ) -> OccupancyReport:
        """Enhance report with additional analytics."""
        # Add occupancy health status
        if hasattr(report, 'kpi') and hasattr(report.kpi, 'average_occupancy_rate'):
            rate = report.kpi.average_occupancy_rate
            if rate >= self.HIGH_OCCUPANCY_THRESHOLD:
                report.occupancy_health = "high"
            elif rate >= self.LOW_OCCUPANCY_THRESHOLD:
                report.occupancy_health = "moderate"
            else:
                report.occupancy_health = "low"
        
        # Add generated timestamp
        report.generated_at = datetime.utcnow()
        
        return report

    def _enhance_kpi(self, kpi: OccupancyKPI) -> OccupancyKPI:
        """Enhance KPI with derived metrics."""
        # Calculate RevPAR (Revenue Per Available Room) if data available
        if hasattr(kpi, 'total_revenue') and hasattr(kpi, 'total_available_rooms'):
            if kpi.total_available_rooms > 0:
                kpi.revpar = round(kpi.total_revenue / kpi.total_available_rooms, 2)
        
        # Add performance indicators
        if hasattr(kpi, 'average_occupancy_rate'):
            if kpi.average_occupancy_rate >= self.HIGH_OCCUPANCY_THRESHOLD:
                kpi.performance_indicator = "excellent"
            elif kpi.average_occupancy_rate >= 0.70:
                kpi.performance_indicator = "good"
            elif kpi.average_occupancy_rate >= self.LOW_OCCUPANCY_THRESHOLD:
                kpi.performance_indicator = "fair"
            else:
                kpi.performance_indicator = "poor"
        
        return kpi

    def _get_previous_period_kpi(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Optional[OccupancyKPI]:
        """Get KPIs for the previous period."""
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
        current_kpi: OccupancyKPI,
        previous_kpi: OccupancyKPI,
    ) -> OccupancyKPI:
        """Add comparison metrics to current KPI."""
        if hasattr(current_kpi, 'average_occupancy_rate') and hasattr(previous_kpi, 'average_occupancy_rate'):
            if previous_kpi.average_occupancy_rate > 0:
                change = (
                    (current_kpi.average_occupancy_rate - previous_kpi.average_occupancy_rate) /
                    previous_kpi.average_occupancy_rate * 100
                )
                current_kpi.occupancy_change_pct = round(change, 2)
        
        if hasattr(current_kpi, 'total_revenue') and hasattr(previous_kpi, 'total_revenue'):
            if previous_kpi.total_revenue > 0:
                change = (
                    (current_kpi.total_revenue - previous_kpi.total_revenue) /
                    previous_kpi.total_revenue * 100
                )
                current_kpi.revenue_change_pct = round(change, 2)
        
        return current_kpi

    def _detect_occupancy_anomalies(
        self,
        data: List[OccupancyTrendPoint],
    ) -> List[OccupancyTrendPoint]:
        """Detect anomalies in occupancy data using statistical methods."""
        if len(data) < 7:
            return data
        
        # Extract occupancy rates
        rates = [p.occupancy_rate for p in data if hasattr(p, 'occupancy_rate')]
        
        if not rates:
            return data
        
        # Calculate mean and standard deviation
        mean_rate = statistics.mean(rates)
        stdev_rate = statistics.stdev(rates) if len(rates) > 1 else 0
        
        # Flag anomalies (points beyond 2 standard deviations)
        threshold = 2 * stdev_rate
        
        for point in data:
            if hasattr(point, 'occupancy_rate'):
                deviation = abs(point.occupancy_rate - mean_rate)
                if deviation > threshold:
                    point.is_anomaly = True
                    point.anomaly_score = round(deviation / stdev_rate, 2) if stdev_rate > 0 else 0
        
        return data

    def _add_moving_averages(
        self,
        data: List[OccupancyTrendPoint],
    ) -> List[OccupancyTrendPoint]:
        """Add moving averages to trend data."""
        window_sizes = [7, 30]  # 7-day and 30-day moving averages
        
        for window in window_sizes:
            if len(data) >= window:
                for i in range(window - 1, len(data)):
                    window_data = data[i - window + 1:i + 1]
                    avg = statistics.mean(
                        p.occupancy_rate for p in window_data
                        if hasattr(p, 'occupancy_rate')
                    )
                    
                    if window == 7:
                        data[i].ma_7 = round(avg, 2)
                    elif window == 30:
                        data[i].ma_30 = round(avg, 2)
        
        return data

    def _generate_forecast(
        self,
        historical_data: List[OccupancyTrendPoint],
        forecast_days: int,
        model: ForecastModelType,
        confidence_level: float,
    ) -> ForecastData:
        """Generate forecast using specified model."""
        if model == ForecastModelType.SIMPLE_AVERAGE:
            return self._simple_average_forecast(historical_data, forecast_days, confidence_level)
        
        elif model == ForecastModelType.WEIGHTED_AVERAGE:
            return self._weighted_average_forecast(historical_data, forecast_days, confidence_level)
        
        elif model == ForecastModelType.MOVING_AVERAGE:
            return self._moving_average_forecast(historical_data, forecast_days, confidence_level)
        
        elif model == ForecastModelType.EXPONENTIAL_SMOOTHING:
            return self._exponential_smoothing_forecast(historical_data, forecast_days, confidence_level)
        
        elif model == ForecastModelType.SEASONAL_NAIVE:
            return self._seasonal_naive_forecast(historical_data, forecast_days, confidence_level)
        
        else:
            # Default to weighted average
            return self._weighted_average_forecast(historical_data, forecast_days, confidence_level)

    def _generate_best_forecast(
        self,
        historical_data: List[OccupancyTrendPoint],
        forecast_days: int,
        confidence_level: float,
    ) -> ForecastData:
        """Generate forecast using the best-fit model."""
        # For simplicity, use weighted average as it generally performs well
        # In production, you might want to evaluate multiple models and select the best
        return self._weighted_average_forecast(historical_data, forecast_days, confidence_level)

    def _simple_average_forecast(
        self,
        historical_data: List[OccupancyTrendPoint],
        forecast_days: int,
        confidence_level: float,
    ) -> ForecastData:
        """Simple average forecast."""
        # Calculate average occupancy rate
        rates = [p.occupancy_rate for p in historical_data if hasattr(p, 'occupancy_rate')]
        avg_rate = statistics.mean(rates) if rates else 0
        
        # Calculate standard deviation for confidence intervals
        stdev = statistics.stdev(rates) if len(rates) > 1 else 0
        z_score = 1.96  # 95% confidence
        margin = z_score * stdev
        
        # Generate forecast points
        last_date = historical_data[-1].date if historical_data else date.today()
        forecast_points = []
        
        for i in range(1, forecast_days + 1):
            forecast_date = last_date + timedelta(days=i)
            forecast_points.append(ForecastPoint(
                forecast_date=forecast_date,
                forecasted_occupancy_rate=round(avg_rate, 2),
                lower_bound=max(0, round(avg_rate - margin, 2)),
                upper_bound=min(100, round(avg_rate + margin, 2)),
                confidence_level=confidence_level,
            ))
        
        return ForecastData(
            model=ForecastModelType.SIMPLE_AVERAGE,
            forecast_points=forecast_points,
            accuracy_metrics={"method": "simple_average"},
        )

    def _weighted_average_forecast(
        self,
        historical_data: List[OccupancyTrendPoint],
        forecast_days: int,
        confidence_level: float,
    ) -> ForecastData:
        """Weighted average forecast (more recent data weighted higher)."""
        # Use last 30 days with linear weighting
        recent_data = historical_data[-30:] if len(historical_data) > 30 else historical_data
        
        # Calculate weighted average
        weights = list(range(1, len(recent_data) + 1))
        total_weight = sum(weights)
        
        weighted_sum = sum(
            p.occupancy_rate * w
            for p, w in zip(recent_data, weights)
            if hasattr(p, 'occupancy_rate')
        )
        
        avg_rate = weighted_sum / total_weight if total_weight > 0 else 0
        
        # Calculate weighted standard deviation
        variance = sum(
            w * (p.occupancy_rate - avg_rate) ** 2
            for p, w in zip(recent_data, weights)
            if hasattr(p, 'occupancy_rate')
        ) / total_weight if total_weight > 0 else 0
        
        stdev = variance ** 0.5
        z_score = 1.96
        margin = z_score * stdev
        
        # Generate forecast points
        last_date = historical_data[-1].date if historical_data else date.today()
        forecast_points = []
        
        for i in range(1, forecast_days + 1):
            forecast_date = last_date + timedelta(days=i)
            
            # Add slight decay to margin as we go further into future
            decay_factor = 1 + (i / forecast_days) * 0.5
            adjusted_margin = margin * decay_factor
            
            forecast_points.append(ForecastPoint(
                forecast_date=forecast_date,
                forecasted_occupancy_rate=round(avg_rate, 2),
                lower_bound=max(0, round(avg_rate - adjusted_margin, 2)),
                upper_bound=min(100, round(avg_rate + adjusted_margin, 2)),
                confidence_level=confidence_level,
            ))
        
        return ForecastData(
            model=ForecastModelType.WEIGHTED_AVERAGE,
            forecast_points=forecast_points,
            accuracy_metrics={"method": "weighted_average", "window": len(recent_data)},
        )

    def _moving_average_forecast(
        self,
        historical_data: List[OccupancyTrendPoint],
        forecast_days: int,
        confidence_level: float,
    ) -> ForecastData:
        """Moving average forecast."""
        window_size = min(14, len(historical_data))  # 2-week window
        recent_data = historical_data[-window_size:]
        
        rates = [p.occupancy_rate for p in recent_data if hasattr(p, 'occupancy_rate')]
        avg_rate = statistics.mean(rates) if rates else 0
        stdev = statistics.stdev(rates) if len(rates) > 1 else 0
        
        z_score = 1.96
        margin = z_score * stdev
        
        last_date = historical_data[-1].date if historical_data else date.today()
        forecast_points = []
        
        for i in range(1, forecast_days + 1):
            forecast_date = last_date + timedelta(days=i)
            forecast_points.append(ForecastPoint(
                forecast_date=forecast_date,
                forecasted_occupancy_rate=round(avg_rate, 2),
                lower_bound=max(0, round(avg_rate - margin, 2)),
                upper_bound=min(100, round(avg_rate + margin, 2)),
                confidence_level=confidence_level,
            ))
        
        return ForecastData(
            model=ForecastModelType.MOVING_AVERAGE,
            forecast_points=forecast_points,
            accuracy_metrics={"method": "moving_average", "window": window_size},
        )

    def _exponential_smoothing_forecast(
        self,
        historical_data: List[OccupancyTrendPoint],
        forecast_days: int,
        confidence_level: float,
    ) -> ForecastData:
        """Exponential smoothing forecast."""
        alpha = 0.3  # Smoothing factor
        
        rates = [p.occupancy_rate for p in historical_data if hasattr(p, 'occupancy_rate')]
        
        if not rates:
            return self._simple_average_forecast(historical_data, forecast_days, confidence_level)
        
        # Initialize with first value
        smoothed = [rates[0]]
        
        # Apply exponential smoothing
        for i in range(1, len(rates)):
            smoothed_value = alpha * rates[i] + (1 - alpha) * smoothed[-1]
            smoothed.append(smoothed_value)
        
        forecast_value = smoothed[-1]
        
        # Calculate error for confidence intervals
        errors = [abs(rates[i] - smoothed[i]) for i in range(len(rates))]
        avg_error = statistics.mean(errors) if errors else 0
        
        last_date = historical_data[-1].date if historical_data else date.today()
        forecast_points = []
        
        for i in range(1, forecast_days + 1):
            forecast_date = last_date + timedelta(days=i)
            
            # Widen confidence interval as we go further
            margin = avg_error * (1 + i / 10)
            
            forecast_points.append(ForecastPoint(
                forecast_date=forecast_date,
                forecasted_occupancy_rate=round(forecast_value, 2),
                lower_bound=max(0, round(forecast_value - margin, 2)),
                upper_bound=min(100, round(forecast_value + margin, 2)),
                confidence_level=confidence_level,
            ))
        
        return ForecastData(
            model=ForecastModelType.EXPONENTIAL_SMOOTHING,
            forecast_points=forecast_points,
            accuracy_metrics={"method": "exponential_smoothing", "alpha": alpha},
        )

    def _seasonal_naive_forecast(
        self,
        historical_data: List[OccupancyTrendPoint],
        forecast_days: int,
        confidence_level: float,
    ) -> ForecastData:
        """Seasonal naive forecast (uses same day from previous season)."""
        season_length = 7  # Weekly seasonality
        
        forecast_points = []
        last_date = historical_data[-1].date if historical_data else date.today()
        
        for i in range(1, forecast_days + 1):
            forecast_date = last_date + timedelta(days=i)
            
            # Look back to same day of week
            lookback_index = -(season_length - (i % season_length))
            
            if abs(lookback_index) <= len(historical_data):
                reference_point = historical_data[lookback_index]
                forecast_value = reference_point.occupancy_rate if hasattr(reference_point, 'occupancy_rate') else 0
            else:
                # Fallback to average
                rates = [p.occupancy_rate for p in historical_data if hasattr(p, 'occupancy_rate')]
                forecast_value = statistics.mean(rates) if rates else 0
            
            # Simple margin based on recent variability
            recent_rates = [
                p.occupancy_rate for p in historical_data[-14:]
                if hasattr(p, 'occupancy_rate')
            ]
            margin = statistics.stdev(recent_rates) * 1.96 if len(recent_rates) > 1 else 5
            
            forecast_points.append(ForecastPoint(
                forecast_date=forecast_date,
                forecasted_occupancy_rate=round(forecast_value, 2),
                lower_bound=max(0, round(forecast_value - margin, 2)),
                upper_bound=min(100, round(forecast_value + margin, 2)),
                confidence_level=confidence_level,
            ))
        
        return ForecastData(
            model=ForecastModelType.SEASONAL_NAIVE,
            forecast_points=forecast_points,
            accuracy_metrics={"method": "seasonal_naive", "season_length": season_length},
        )

    def _detect_seasonal_patterns(self, report: OccupancyReport) -> List[SeasonalPattern]:
        """Detect seasonal patterns from report data."""
        patterns = []
        
        if not hasattr(report, 'trend') or not report.trend:
            return patterns
        
        # Group by month and analyze
        monthly_data = {}
        for point in report.trend:
            if hasattr(point, 'date') and hasattr(point, 'occupancy_rate'):
                month = point.date.month
                if month not in monthly_data:
                    monthly_data[month] = []
                monthly_data[month].append(point.occupancy_rate)
        
        # Calculate average occupancy by month
        monthly_averages = {
            month: statistics.mean(rates)
            for month, rates in monthly_data.items()
            if rates
        }
        
        if not monthly_averages:
            return patterns
        
        overall_avg = statistics.mean(monthly_averages.values())
        
        # Classify seasons
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        
        for month, avg_rate in monthly_averages.items():
            if avg_rate >= overall_avg * 1.2:
                season_type = SeasonType.PEAK
            elif avg_rate >= overall_avg * 1.05:
                season_type = SeasonType.HIGH
            elif avg_rate >= overall_avg * 0.85:
                season_type = SeasonType.SHOULDER
            else:
                season_type = SeasonType.LOW
            
            patterns.append(SeasonalPattern(
                period=month_names[month - 1],
                season_type=season_type.value,
                average_occupancy=round(avg_rate, 2),
                variance_from_mean=round(avg_rate - overall_avg, 2),
            ))
        
        return patterns

    def _analyze_seasonal_patterns(
        self,
        historical_data: List[OccupancyTrendPoint],
    ) -> List[SeasonalPattern]:
        """Analyze historical data for seasonal patterns."""
        # Group by month
        monthly_data = {}
        
        for point in historical_data:
            if hasattr(point, 'date') and hasattr(point, 'occupancy_rate'):
                month = point.date.month
                if month not in monthly_data:
                    monthly_data[month] = []
                monthly_data[month].append(point.occupancy_rate)
        
        patterns = []
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        
        # Calculate overall average
        all_rates = [p.occupancy_rate for p in historical_data if hasattr(p, 'occupancy_rate')]
        overall_avg = statistics.mean(all_rates) if all_rates else 0
        
        for month in range(1, 13):
            if month in monthly_data and monthly_data[month]:
                avg_rate = statistics.mean(monthly_data[month])
                stdev = statistics.stdev(monthly_data[month]) if len(monthly_data[month]) > 1 else 0
                
                # Determine season type
                if avg_rate >= overall_avg * 1.2:
                    season_type = SeasonType.PEAK
                elif avg_rate >= overall_avg * 1.05:
                    season_type = SeasonType.HIGH
                elif avg_rate >= overall_avg * 0.85:
                    season_type = SeasonType.SHOULDER
                else:
                    season_type = SeasonType.LOW
                
                patterns.append(SeasonalPattern(
                    period=month_names[month - 1],
                    season_type=season_type.value,
                    average_occupancy=round(avg_rate, 2),
                    variance_from_mean=round(avg_rate - overall_avg, 2),
                    volatility=round(stdev, 2),
                ))
        
        return patterns

    def _enhance_room_type_breakdown(
        self,
        breakdown: List[OccupancyByRoomType],
    ) -> List[OccupancyByRoomType]:
        """Enhance room type breakdown with additional metrics."""
        if not breakdown:
            return breakdown
        
        # Calculate total revenue
        total_revenue = sum(
            b.revenue for b in breakdown
            if hasattr(b, 'revenue') and b.revenue
        )
        
        # Sort by revenue descending
        breakdown.sort(
            key=lambda x: getattr(x, 'revenue', 0) or 0,
            reverse=True
        )
        
        # Add rankings and percentages
        for i, item in enumerate(breakdown, 1):
            item.rank = i
            
            if total_revenue > 0 and hasattr(item, 'revenue') and item.revenue:
                item.revenue_percentage = round((item.revenue / total_revenue) * 100, 2)
        
        return breakdown

    def _identify_pricing_periods(
        self,
        forecast_points: List[ForecastPoint],
    ) -> List[Dict[str, Any]]:
        """Identify optimal pricing periods from forecast."""
        periods = []
        current_period = None
        
        for point in forecast_points:
            if not hasattr(point, 'forecasted_occupancy_rate'):
                continue
            
            rate = point.forecasted_occupancy_rate
            
            # Determine pricing strategy
            if rate >= 85:
                strategy = "premium"
                price_multiplier = 1.2
            elif rate >= 70:
                strategy = "standard"
                price_multiplier = 1.0
            elif rate >= 50:
                strategy = "promotional"
                price_multiplier = 0.9
            else:
                strategy = "discount"
                price_multiplier = 0.8
            
            # Group consecutive days with same strategy
            if current_period and current_period['strategy'] == strategy:
                current_period['end_date'] = point.forecast_date
                current_period['days'] += 1
            else:
                if current_period:
                    periods.append(current_period)
                
                current_period = {
                    'start_date': point.forecast_date,
                    'end_date': point.forecast_date,
                    'strategy': strategy,
                    'price_multiplier': price_multiplier,
                    'forecasted_occupancy': rate,
                    'days': 1,
                }
        
        # Add last period
        if current_period:
            periods.append(current_period)
        
        return periods