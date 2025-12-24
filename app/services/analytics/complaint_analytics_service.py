"""
Complaint analytics service.

Optimizations:
- Added SLA tracking and alerts
- Improved trend analysis with anomaly detection
- Enhanced error handling
- Added caching for frequently accessed metrics
- Implemented batch processing for large datasets
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, timedelta, datetime
from collections import defaultdict
import logging

from sqlalchemy.orm import Session

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.analytics import ComplaintAnalyticsRepository
from app.models.analytics.complaint_analytics import ComplaintDashboard as ComplaintDashboardModel
from app.schemas.analytics.complaint_analytics import (
    SLAMetrics,
    ComplaintKPI,
    ComplaintTrendPoint,
    ComplaintTrend,
    CategoryBreakdown,
    PriorityBreakdown,
    ComplaintDashboard,
)

logger = logging.getLogger(__name__)


class ComplaintAnalyticsService(BaseService[ComplaintDashboardModel, ComplaintAnalyticsRepository]):
    """
    Service for complaint analytics.
    
    Provides:
    - Complaint KPIs and SLA metrics
    - Trend analysis with anomaly detection
    - Category and priority breakdowns
    - Resolution time analytics
    - Dashboard aggregations
    """

    # Default analysis window
    DEFAULT_ANALYSIS_DAYS = 30
    
    # SLA thresholds (hours)
    SLA_THRESHOLDS = {
        "critical": 4,
        "high": 24,
        "medium": 48,
        "low": 72,
    }
    
    # Cache TTL
    CACHE_TTL = 300  # 5 minutes

    def __init__(self, repository: ComplaintAnalyticsRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._cache = {}
        self._cache_timestamps = {}

    def get_dashboard(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_alerts: bool = True,
    ) -> ServiceResult[ComplaintDashboard]:
        """
        Get comprehensive complaint analytics dashboard.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start of date range
            end_date: End of date range
            include_alerts: Include SLA alerts and warnings
            
        Returns:
            ServiceResult containing complaint dashboard
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
            cache_key = f"dashboard_{hostel_id}_{start_date}_{end_date}"
            if self._is_cache_valid(cache_key):
                logger.debug(f"Returning cached dashboard for {hostel_id}")
                return ServiceResult.success(self._cache[cache_key])
            
            # Fetch dashboard data
            dashboard = self.repository.get_dashboard(hostel_id, start_date, end_date)
            
            if not dashboard:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No complaint data found for hostel {hostel_id}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Add alerts if requested
            if include_alerts:
                dashboard = self._add_sla_alerts(dashboard)
            
            # Cache result
            self._update_cache(cache_key, dashboard)
            
            return ServiceResult.success(
                dashboard,
                message="Complaint dashboard retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting complaint dashboard: {str(e)}")
            return self._handle_exception(e, "get complaint dashboard", hostel_id)

    def get_kpis(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        compare_previous_period: bool = False,
    ) -> ServiceResult[ComplaintKPI]:
        """
        Get complaint KPIs for a hostel.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            compare_previous_period: Include comparison with previous period
            
        Returns:
            ServiceResult containing complaint KPIs
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
                        message="No complaint KPI data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Add SLA metrics
            kpi = self._enhance_kpi_with_sla(kpi)
            
            # Add comparison if requested
            if compare_previous_period:
                previous_kpi = self._get_previous_period_kpi(
                    hostel_id, start_date, end_date
                )
                if previous_kpi:
                    kpi = self._add_period_comparison(kpi, previous_kpi)
            
            return ServiceResult.success(
                kpi,
                message="Complaint KPIs retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting complaint KPIs: {str(e)}")
            return self._handle_exception(e, "get complaint kpis", hostel_id)

    def get_trend(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        granularity: str = "daily",
        detect_anomalies: bool = True,
    ) -> ServiceResult[ComplaintTrend]:
        """
        Get complaint trend over time.
        
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
            trend = self.repository.get_trend(
                hostel_id, start_date, end_date, granularity=granularity
            )
            
            if not trend or not hasattr(trend, 'points') or not trend.points:
                logger.warning(f"No trend data found for hostel {hostel_id}")
                trend = ComplaintTrend(points=[], anomalies=[])
            
            # Detect anomalies if requested
            if detect_anomalies and trend.points:
                trend = self._detect_trend_anomalies(trend)
            
            return ServiceResult.success(
                trend,
                metadata={
                    "points_count": len(trend.points) if hasattr(trend, 'points') else 0,
                    "granularity": granularity,
                    "anomalies_detected": len(trend.anomalies) if hasattr(trend, 'anomalies') else 0,
                },
                message=f"Retrieved complaint trend with {len(trend.points) if hasattr(trend, 'points') else 0} points"
            )
            
        except Exception as e:
            logger.error(f"Error getting complaint trend: {str(e)}")
            return self._handle_exception(e, "get complaint trend", hostel_id)

    def get_category_breakdown(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        min_count: int = 1,
    ) -> ServiceResult[List[CategoryBreakdown]]:
        """
        Get complaint breakdown by category.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            min_count: Minimum complaint count for inclusion
            
        Returns:
            ServiceResult containing category breakdown
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch category breakdown
            breakdown = self.repository.get_category_breakdown(hostel_id, start_date, end_date)
            
            if not breakdown:
                logger.warning(f"No category data found for hostel {hostel_id}")
                breakdown = []
            
            # Filter by minimum count
            if min_count > 1:
                breakdown = [b for b in breakdown if b.count >= min_count]
            
            # Sort by count descending
            breakdown.sort(key=lambda x: x.count, reverse=True)
            
            # Calculate percentages
            total_count = sum(b.count for b in breakdown)
            for b in breakdown:
                if total_count > 0:
                    b.percentage = round((b.count / total_count) * 100, 2)
                else:
                    b.percentage = 0.0
            
            return ServiceResult.success(
                breakdown,
                metadata={
                    "count": len(breakdown),
                    "total_complaints": total_count,
                    "min_count_filter": min_count,
                },
                message=f"Retrieved {len(breakdown)} category breakdowns"
            )
            
        except Exception as e:
            logger.error(f"Error getting category breakdown: {str(e)}")
            return self._handle_exception(e, "get complaint category breakdown", hostel_id)

    def get_priority_breakdown(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        include_sla: bool = True,
    ) -> ServiceResult[List[PriorityBreakdown]]:
        """
        Get complaint breakdown by priority.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            include_sla: Include SLA compliance metrics
            
        Returns:
            ServiceResult containing priority breakdown
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch priority breakdown
            breakdown = self.repository.get_priority_breakdown(hostel_id, start_date, end_date)
            
            if not breakdown:
                logger.warning(f"No priority data found for hostel {hostel_id}")
                breakdown = []
            
            # Sort by priority order (critical first)
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            breakdown.sort(
                key=lambda x: priority_order.get(x.priority.lower(), 999)
            )
            
            # Calculate percentages and add SLA info
            total_count = sum(b.count for b in breakdown)
            for b in breakdown:
                if total_count > 0:
                    b.percentage = round((b.count / total_count) * 100, 2)
                else:
                    b.percentage = 0.0
                
                if include_sla:
                    b.sla_threshold_hours = self.SLA_THRESHOLDS.get(
                        b.priority.lower(), 72
                    )
            
            return ServiceResult.success(
                breakdown,
                metadata={
                    "count": len(breakdown),
                    "total_complaints": total_count,
                    "sla_included": include_sla,
                },
                message=f"Retrieved {len(breakdown)} priority breakdowns"
            )
            
        except Exception as e:
            logger.error(f"Error getting priority breakdown: {str(e)}")
            return self._handle_exception(e, "get complaint priority breakdown", hostel_id)

    def get_sla_metrics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[SLAMetrics]:
        """
        Get SLA compliance metrics.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            
        Returns:
            ServiceResult containing SLA metrics
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch SLA metrics from repository
            sla_metrics = self.repository.get_sla_metrics(hostel_id, start_date, end_date)
            
            if not sla_metrics:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No SLA data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Add breach analysis
            sla_metrics = self._analyze_sla_breaches(sla_metrics)
            
            return ServiceResult.success(
                sla_metrics,
                message="SLA metrics retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting SLA metrics: {str(e)}")
            return self._handle_exception(e, "get SLA metrics", hostel_id)

    def get_resolution_analytics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get detailed resolution time analytics.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            
        Returns:
            ServiceResult containing resolution analytics
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch resolution data
            analytics = self.repository.get_resolution_analytics(
                hostel_id, start_date, end_date
            )
            
            if not analytics:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No resolution data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Enhance with percentile calculations
            if hasattr(analytics, 'resolution_times') and analytics.resolution_times:
                analytics = self._calculate_resolution_percentiles(analytics)
            
            return ServiceResult.success(
                analytics,
                message="Resolution analytics retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting resolution analytics: {str(e)}")
            return self._handle_exception(e, "get resolution analytics", hostel_id)

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
        
        # Check if range is too large
        if (end_date - start_date).days > 365:
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Date range cannot exceed 1 year",
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

    def _enhance_kpi_with_sla(self, kpi: ComplaintKPI) -> ComplaintKPI:
        """Enhance KPI with SLA compliance information."""
        if hasattr(kpi, 'sla_compliance_rate'):
            # Add health status based on compliance rate
            if kpi.sla_compliance_rate >= 95:
                kpi.sla_health = "excellent"
            elif kpi.sla_compliance_rate >= 85:
                kpi.sla_health = "good"
            elif kpi.sla_compliance_rate >= 75:
                kpi.sla_health = "fair"
            else:
                kpi.sla_health = "poor"
        
        return kpi

    def _get_previous_period_kpi(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Optional[ComplaintKPI]:
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
        current_kpi: ComplaintKPI,
        previous_kpi: ComplaintKPI,
    ) -> ComplaintKPI:
        """Add comparison metrics to current KPI."""
        # Calculate percentage changes
        if hasattr(current_kpi, 'total_complaints') and hasattr(previous_kpi, 'total_complaints'):
            if previous_kpi.total_complaints > 0:
                change = (
                    (current_kpi.total_complaints - previous_kpi.total_complaints) /
                    previous_kpi.total_complaints * 100
                )
                current_kpi.complaints_change_pct = round(change, 2)
        
        if hasattr(current_kpi, 'avg_resolution_time') and hasattr(previous_kpi, 'avg_resolution_time'):
            if previous_kpi.avg_resolution_time and previous_kpi.avg_resolution_time > 0:
                change = (
                    (current_kpi.avg_resolution_time - previous_kpi.avg_resolution_time) /
                    previous_kpi.avg_resolution_time * 100
                )
                current_kpi.resolution_time_change_pct = round(change, 2)
        
        return current_kpi

    def _add_sla_alerts(self, dashboard: ComplaintDashboard) -> ComplaintDashboard:
        """Add SLA alerts to dashboard."""
        alerts = []
        
        if hasattr(dashboard, 'sla_metrics'):
            sla = dashboard.sla_metrics
            
            # Check for critical SLA breaches
            if hasattr(sla, 'breach_rate') and sla.breach_rate > 20:
                alerts.append({
                    "severity": "high",
                    "message": f"SLA breach rate is {sla.breach_rate}% (threshold: 20%)",
                    "type": "sla_breach",
                })
            
            # Check for high average resolution time
            if hasattr(sla, 'avg_resolution_hours') and sla.avg_resolution_hours > 48:
                alerts.append({
                    "severity": "medium",
                    "message": f"Average resolution time is {sla.avg_resolution_hours} hours",
                    "type": "resolution_time",
                })
        
        if hasattr(dashboard, 'kpi'):
            kpi = dashboard.kpi
            
            # Check for spike in complaints
            if hasattr(kpi, 'complaints_change_pct') and kpi.complaints_change_pct > 50:
                alerts.append({
                    "severity": "medium",
                    "message": f"Complaints increased by {kpi.complaints_change_pct}%",
                    "type": "volume_spike",
                })
        
        if alerts:
            dashboard.alerts = alerts
        
        return dashboard

    def _detect_trend_anomalies(self, trend: ComplaintTrend) -> ComplaintTrend:
        """Detect anomalies in trend data using simple statistical method."""
        if not trend.points or len(trend.points) < 7:
            return trend
        
        # Calculate mean and standard deviation
        values = [p.count for p in trend.points]
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5
        
        # Flag points beyond 2 standard deviations
        anomalies = []
        threshold = 2 * std_dev
        
        for point in trend.points:
            if abs(point.count - mean) > threshold:
                anomalies.append({
                    "date": point.date,
                    "count": point.count,
                    "expected_range": (mean - threshold, mean + threshold),
                    "deviation": abs(point.count - mean),
                })
        
        trend.anomalies = anomalies
        trend.anomaly_detection_method = "statistical_outlier"
        
        return trend

    def _analyze_sla_breaches(self, sla_metrics: SLAMetrics) -> SLAMetrics:
        """Analyze and categorize SLA breaches."""
        if hasattr(sla_metrics, 'breaches_by_priority'):
            # Calculate breach impact
            total_breaches = sum(sla_metrics.breaches_by_priority.values())
            
            if total_breaches > 0:
                critical_impact = sla_metrics.breaches_by_priority.get('critical', 0)
                if critical_impact / total_breaches > 0.5:
                    sla_metrics.breach_severity = "critical"
                elif critical_impact > 0:
                    sla_metrics.breach_severity = "high"
                else:
                    sla_metrics.breach_severity = "medium"
        
        return sla_metrics

    def _calculate_resolution_percentiles(
        self,
        analytics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate resolution time percentiles."""
        if 'resolution_times' not in analytics:
            return analytics
        
        times = sorted(analytics['resolution_times'])
        
        if not times:
            return analytics
        
        def percentile(data: List[float], p: float) -> float:
            """Calculate percentile value."""
            k = (len(data) - 1) * p
            f = int(k)
            c = k - f
            if f + 1 < len(data):
                return data[f] + c * (data[f + 1] - data[f])
            return data[f]
        
        analytics['percentiles'] = {
            'p50': round(percentile(times, 0.5), 2),
            'p75': round(percentile(times, 0.75), 2),
            'p90': round(percentile(times, 0.90), 2),
            'p95': round(percentile(times, 0.95), 2),
            'p99': round(percentile(times, 0.99), 2),
        }
        
        return analytics