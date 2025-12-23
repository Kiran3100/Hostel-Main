"""
Platform (multi-tenant) analytics service.

Optimizations:
- Added tenant segmentation and cohort analysis
- Implemented growth tracking with detailed metrics
- Enhanced churn analysis with predictive indicators
- Added system health monitoring
- Improved usage analytics with granular breakdowns
"""

from typing import Optional, Dict, Any, List, Tuple
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
from app.repositories.analytics import PlatformAnalyticsRepository
from app.models.analytics.platform_analytics import PlatformMetrics as PlatformMetricsModel
from app.schemas.analytics.platform_analytics import (
    TenantMetrics,
    PlatformMetrics,
    MonthlyMetric,
    GrowthMetrics,
    ChurnAnalysis,
    SystemHealthMetrics,
    RevenueMetrics,
    PlatformUsageAnalytics,
)

logger = logging.getLogger(__name__)


class TenantSegment(str, Enum):
    """Tenant segmentation categories."""
    ENTERPRISE = "enterprise"
    PROFESSIONAL = "professional"
    STARTER = "starter"
    TRIAL = "trial"


class HealthStatus(str, Enum):
    """System health status."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class PlatformAnalyticsService(BaseService[PlatformMetricsModel, PlatformAnalyticsRepository]):
    """
    Service for platform-wide analytics.
    
    Provides:
    - Tenant metrics and segmentation
    - Growth and churn analysis
    - System health monitoring
    - Usage analytics
    - Revenue metrics
    - Cohort analysis
    """

    # Default analysis period
    DEFAULT_ANALYSIS_DAYS = 30
    
    # Health thresholds
    HEALTH_THRESHOLDS = {
        "cpu_usage": 80,
        "memory_usage": 85,
        "error_rate": 1.0,  # 1%
        "response_time": 2000,  # 2 seconds
    }
    
    # Churn risk thresholds
    CHURN_RISK_THRESHOLDS = {
        "low_usage_days": 7,
        "no_logins_days": 14,
        "failed_payments": 2,
    }
    
    # Cache TTL
    CACHE_TTL = 600  # 10 minutes

    def __init__(self, repository: PlatformAnalyticsRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._cache = {}
        self._cache_timestamps = {}

    def get_platform_metrics(
        self,
        start_date: date,
        end_date: date,
        include_breakdown: bool = True,
    ) -> ServiceResult[PlatformMetrics]:
        """
        Get comprehensive platform metrics.
        
        Args:
            start_date: Start date
            end_date: End date
            include_breakdown: Include detailed breakdowns
            
        Returns:
            ServiceResult containing platform metrics
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Check cache
            cache_key = f"platform_metrics_{start_date}_{end_date}"
            if self._is_cache_valid(cache_key):
                logger.debug("Returning cached platform metrics")
                return ServiceResult.success(self._cache[cache_key])
            
            # Fetch metrics
            metrics = self.repository.get_platform_metrics(start_date, end_date)
            
            if not metrics:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No platform metrics available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Enhance with additional analytics
            if include_breakdown:
                metrics = self._enhance_platform_metrics(metrics, start_date, end_date)
            
            # Add summary statistics
            metrics.summary = self._calculate_platform_summary(metrics)
            
            # Cache result
            self._update_cache(cache_key, metrics)
            
            return ServiceResult.success(
                metrics,
                message="Platform metrics retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting platform metrics: {str(e)}")
            return self._handle_exception(e, "get platform metrics")

    def get_growth(
        self,
        start_date: date,
        end_date: date,
        granularity: str = "monthly",
    ) -> ServiceResult[GrowthMetrics]:
        """
        Get growth metrics.
        
        Args:
            start_date: Start date
            end_date: End date
            granularity: Time granularity (daily, weekly, monthly)
            
        Returns:
            ServiceResult containing growth metrics
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
            
            # Fetch growth metrics
            growth = self.repository.get_growth_metrics(start_date, end_date, granularity)
            
            if not growth:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No growth data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Calculate growth rates
            growth = self._calculate_growth_rates(growth)
            
            # Add trend analysis
            growth.trend = self._analyze_growth_trend(growth)
            
            return ServiceResult.success(
                growth,
                message="Growth metrics retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting growth metrics: {str(e)}")
            return self._handle_exception(e, "get growth metrics")

    def get_churn(
        self,
        start_date: date,
        end_date: date,
        include_predictions: bool = True,
    ) -> ServiceResult[ChurnAnalysis]:
        """
        Get churn analysis.
        
        Args:
            start_date: Start date
            end_date: End date
            include_predictions: Include churn predictions
            
        Returns:
            ServiceResult containing churn analysis
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch churn analysis
            churn = self.repository.get_churn_analysis(start_date, end_date)
            
            if not churn:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No churn data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Calculate churn metrics
            churn = self._calculate_churn_metrics(churn)
            
            # Add churn predictions if requested
            if include_predictions:
                churn.at_risk_tenants = self._identify_churn_risk()
                churn.churn_forecast = self._forecast_churn(churn)
            
            return ServiceResult.success(
                churn,
                message="Churn analysis retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting churn analysis: {str(e)}")
            return self._handle_exception(e, "get churn analysis")

    def get_system_health(
        self,
        start_date: date,
        end_date: date,
        include_alerts: bool = True,
    ) -> ServiceResult[SystemHealthMetrics]:
        """
        Get system health metrics.
        
        Args:
            start_date: Start date
            end_date: End date
            include_alerts: Include health alerts
            
        Returns:
            ServiceResult containing system health metrics
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch health metrics
            health = self.repository.get_system_health(start_date, end_date)
            
            if not health:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No health data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Calculate health score
            health.overall_score = self._calculate_health_score(health)
            health.status = self._determine_health_status(health.overall_score)
            
            # Add alerts if requested
            if include_alerts:
                health.alerts = self._generate_health_alerts(health)
            
            return ServiceResult.success(
                health,
                message="System health metrics retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            return self._handle_exception(e, "get system health")

    def get_usage_analytics(
        self,
        start_date: date,
        end_date: date,
        segment_by: Optional[str] = None,
    ) -> ServiceResult[PlatformUsageAnalytics]:
        """
        Get platform usage analytics.
        
        Args:
            start_date: Start date
            end_date: End date
            segment_by: Optional segmentation (tenant_type, plan, region)
            
        Returns:
            ServiceResult containing usage analytics
        """
        try:
            # Validate inputs
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            if segment_by and segment_by not in ("tenant_type", "plan", "region"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid segment_by: {segment_by}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch usage analytics
            usage = self.repository.get_usage_analytics(start_date, end_date, segment_by)
            
            if not usage:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No usage data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Calculate usage metrics
            usage = self._calculate_usage_metrics(usage)
            
            # Add engagement scoring
            usage.engagement_scores = self._calculate_engagement_scores(usage)
            
            return ServiceResult.success(
                usage,
                message="Usage analytics retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting usage analytics: {str(e)}")
            return self._handle_exception(e, "get platform usage analytics")

    def get_revenue_metrics(
        self,
        start_date: date,
        end_date: date,
        include_forecast: bool = False,
    ) -> ServiceResult[RevenueMetrics]:
        """
        Get revenue metrics.
        
        Args:
            start_date: Start date
            end_date: End date
            include_forecast: Include revenue forecast
            
        Returns:
            ServiceResult containing revenue metrics
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch revenue metrics
            revenue = self.repository.get_revenue_metrics(start_date, end_date)
            
            if not revenue:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No revenue data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Calculate revenue KPIs
            revenue = self._calculate_revenue_kpis(revenue)
            
            # Add forecast if requested
            if include_forecast:
                revenue.forecast = self._forecast_revenue(revenue)
            
            return ServiceResult.success(
                revenue,
                message="Revenue metrics retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting revenue metrics: {str(e)}")
            return self._handle_exception(e, "get revenue metrics")

    def get_tenant_metrics(
        self,
        start_date: date,
        end_date: date,
        segment: Optional[str] = None,
    ) -> ServiceResult[List[TenantMetrics]]:
        """
        Get individual tenant metrics.
        
        Args:
            start_date: Start date
            end_date: End date
            segment: Optional tenant segment filter
            
        Returns:
            ServiceResult containing tenant metrics
        """
        try:
            # Validate inputs
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            if segment:
                try:
                    TenantSegment(segment)
                except ValueError:
                    return ServiceResult.error(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Invalid tenant segment: {segment}",
                            severity=ErrorSeverity.ERROR,
                        )
                    )
            
            # Fetch tenant metrics
            metrics = self.repository.get_tenant_metrics(start_date, end_date, segment)
            
            if not metrics:
                logger.warning("No tenant metrics available")
                metrics = []
            
            # Sort by revenue descending
            metrics.sort(
                key=lambda x: getattr(x, 'total_revenue', 0) or 0,
                reverse=True
            )
            
            return ServiceResult.success(
                metrics,
                metadata={
                    "count": len(metrics),
                    "segment": segment,
                },
                message=f"Retrieved {len(metrics)} tenant metrics"
            )
            
        except Exception as e:
            logger.error(f"Error getting tenant metrics: {str(e)}")
            return self._handle_exception(e, "get tenant metrics")

    def get_cohort_analysis(
        self,
        cohort_period: str = "monthly",
        metric: str = "retention",
        lookback_months: int = 12,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get cohort analysis.
        
        Args:
            cohort_period: Cohort grouping period (weekly, monthly)
            metric: Metric to analyze (retention, revenue, usage)
            lookback_months: Months to look back
            
        Returns:
            ServiceResult containing cohort analysis
        """
        try:
            # Validate inputs
            if cohort_period not in ("weekly", "monthly"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid cohort period: {cohort_period}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            if metric not in ("retention", "revenue", "usage"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid metric: {metric}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            if lookback_months < 1 or lookback_months > 24:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Lookback months must be between 1 and 24",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch cohort data
            analysis = self.repository.get_cohort_analysis(
                cohort_period, metric, lookback_months
            )
            
            if not analysis:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No cohort data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Enhance analysis
            analysis = self._enhance_cohort_analysis(analysis, metric)
            
            return ServiceResult.success(
                analysis,
                message="Cohort analysis retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting cohort analysis: {str(e)}")
            return self._handle_exception(e, "get cohort analysis")

    def get_platform_overview(
        self,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get comprehensive platform overview.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            ServiceResult containing platform overview
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch all key metrics
            overview = {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "generated_at": datetime.utcnow().isoformat(),
            }
            
            # Platform metrics
            platform_result = self.get_platform_metrics(start_date, end_date)
            if platform_result.success:
                overview["platform_metrics"] = platform_result.data
            
            # Growth metrics
            growth_result = self.get_growth(start_date, end_date)
            if growth_result.success:
                overview["growth_metrics"] = growth_result.data
            
            # Churn analysis
            churn_result = self.get_churn(start_date, end_date)
            if churn_result.success:
                overview["churn_analysis"] = churn_result.data
            
            # System health
            health_result = self.get_system_health(start_date, end_date)
            if health_result.success:
                overview["system_health"] = health_result.data
            
            # Revenue metrics
            revenue_result = self.get_revenue_metrics(start_date, end_date)
            if revenue_result.success:
                overview["revenue_metrics"] = revenue_result.data
            
            return ServiceResult.success(
                overview,
                message="Platform overview retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting platform overview: {str(e)}")
            return self._handle_exception(e, "get platform overview")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

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
        
        if len(self._cache) > 50:
            oldest_keys = sorted(
                self._cache_timestamps.keys(),
                key=lambda k: self._cache_timestamps[k]
            )[:10]
            for key in oldest_keys:
                del self._cache[key]
                del self._cache_timestamps[key]

    def _enhance_platform_metrics(
        self,
        metrics: PlatformMetrics,
        start_date: date,
        end_date: date,
    ) -> PlatformMetrics:
        """Enhance platform metrics with additional analytics."""
        # Add tenant segmentation
        if hasattr(metrics, 'tenant_breakdown'):
            metrics.tenant_segments = self._segment_tenants(metrics.tenant_breakdown)
        
        # Add growth indicators
        if hasattr(metrics, 'current_tenants') and hasattr(metrics, 'previous_tenants'):
            if metrics.previous_tenants > 0:
                metrics.tenant_growth_rate = round(
                    ((metrics.current_tenants - metrics.previous_tenants) /
                     metrics.previous_tenants) * 100, 2
                )
        
        return metrics

    def _calculate_platform_summary(self, metrics: PlatformMetrics) -> Dict[str, Any]:
        """Calculate platform summary statistics."""
        summary = {
            "total_tenants": getattr(metrics, 'total_tenants', 0),
            "active_tenants": getattr(metrics, 'active_tenants', 0),
            "total_revenue": getattr(metrics, 'total_revenue', 0),
            "avg_revenue_per_tenant": 0,
        }
        
        if summary["active_tenants"] > 0:
            summary["avg_revenue_per_tenant"] = round(
                summary["total_revenue"] / summary["active_tenants"], 2
            )
        
        # Activity rate
        if summary["total_tenants"] > 0:
            summary["activity_rate"] = round(
                (summary["active_tenants"] / summary["total_tenants"]) * 100, 2
            )
        
        return summary

    def _calculate_growth_rates(self, growth: GrowthMetrics) -> GrowthMetrics:
        """Calculate growth rates."""
        if hasattr(growth, 'monthly_data') and growth.monthly_data:
            # Calculate month-over-month growth
            for i in range(1, len(growth.monthly_data)):
                current = growth.monthly_data[i]
                previous = growth.monthly_data[i - 1]
                
                if hasattr(previous, 'value') and previous.value > 0:
                    mom_growth = (
                        (current.value - previous.value) / previous.value * 100
                    )
                    current.mom_growth_rate = round(mom_growth, 2)
        
        # Calculate CAGR if year-over-year data available
        if hasattr(growth, 'yearly_data') and len(growth.yearly_data) >= 2:
            first_year = growth.yearly_data[0]
            last_year = growth.yearly_data[-1]
            years = len(growth.yearly_data) - 1
            
            if hasattr(first_year, 'value') and first_year.value > 0:
                cagr = (
                    ((last_year.value / first_year.value) ** (1 / years) - 1) * 100
                )
                growth.cagr = round(cagr, 2)
        
        return growth

    def _analyze_growth_trend(self, growth: GrowthMetrics) -> str:
        """Analyze overall growth trend."""
        if not hasattr(growth, 'monthly_data') or not growth.monthly_data:
            return "insufficient_data"
        
        # Count positive vs negative growth months
        positive_months = sum(
            1 for m in growth.monthly_data
            if hasattr(m, 'mom_growth_rate') and m.mom_growth_rate > 0
        )
        
        total_months = len([
            m for m in growth.monthly_data
            if hasattr(m, 'mom_growth_rate')
        ])
        
        if total_months == 0:
            return "insufficient_data"
        
        positive_ratio = positive_months / total_months
        
        if positive_ratio >= 0.8:
            return "strong_growth"
        elif positive_ratio >= 0.6:
            return "moderate_growth"
        elif positive_ratio >= 0.4:
            return "mixed"
        else:
            return "declining"

    def _calculate_churn_metrics(self, churn: ChurnAnalysis) -> ChurnAnalysis:
        """Calculate churn metrics."""
        # Calculate churn rate
        if hasattr(churn, 'churned_tenants') and hasattr(churn, 'total_tenants'):
            if churn.total_tenants > 0:
                churn.churn_rate = round(
                    (churn.churned_tenants / churn.total_tenants) * 100, 2
                )
        
        # Calculate retention rate
        if hasattr(churn, 'churn_rate'):
            churn.retention_rate = round(100 - churn.churn_rate, 2)
        
        # Calculate customer lifetime value impact
        if hasattr(churn, 'avg_tenant_value') and hasattr(churn, 'churned_tenants'):
            churn.revenue_lost = round(
                churn.avg_tenant_value * churn.churned_tenants, 2
            )
        
        return churn

    def _identify_churn_risk(self) -> List[Dict[str, Any]]:
        """Identify tenants at risk of churning."""
        try:
            at_risk = self.repository.identify_churn_risk(self.CHURN_RISK_THRESHOLDS)
            return at_risk or []
        except Exception as e:
            logger.error(f"Error identifying churn risk: {str(e)}")
            return []

    def _forecast_churn(self, churn: ChurnAnalysis) -> Dict[str, Any]:
        """Forecast future churn."""
        if not hasattr(churn, 'monthly_churn_data') or not churn.monthly_churn_data:
            return {}
        
        # Simple moving average forecast
        recent_months = churn.monthly_churn_data[-6:]  # Last 6 months
        avg_churn = statistics.mean([m.churn_rate for m in recent_months])
        
        return {
            "forecasted_monthly_churn_rate": round(avg_churn, 2),
            "confidence": "medium",
            "method": "moving_average",
        }

    def _calculate_health_score(self, health: SystemHealthMetrics) -> float:
        """Calculate overall health score (0-100)."""
        scores = []
        
        # CPU usage score
        if hasattr(health, 'avg_cpu_usage'):
            cpu_score = max(0, 100 - (health.avg_cpu_usage / self.HEALTH_THRESHOLDS['cpu_usage']) * 100)
            scores.append(cpu_score)
        
        # Memory usage score
        if hasattr(health, 'avg_memory_usage'):
            mem_score = max(0, 100 - (health.avg_memory_usage / self.HEALTH_THRESHOLDS['memory_usage']) * 100)
            scores.append(mem_score)
        
        # Error rate score
        if hasattr(health, 'error_rate'):
            error_score = max(0, 100 - (health.error_rate / self.HEALTH_THRESHOLDS['error_rate']) * 100)
            scores.append(error_score)
        
        # Response time score
        if hasattr(health, 'avg_response_time'):
            response_score = max(0, 100 - (health.avg_response_time / self.HEALTH_THRESHOLDS['response_time']) * 100)
            scores.append(response_score)
        
        if not scores:
            return 0.0
        
        return round(statistics.mean(scores), 2)

    def _determine_health_status(self, score: float) -> str:
        """Determine health status from score."""
        if score >= 90:
            return HealthStatus.EXCELLENT.value
        elif score >= 75:
            return HealthStatus.GOOD.value
        elif score >= 60:
            return HealthStatus.FAIR.value
        elif score >= 40:
            return HealthStatus.POOR.value
        else:
            return HealthStatus.CRITICAL.value

    def _generate_health_alerts(self, health: SystemHealthMetrics) -> List[Dict[str, Any]]:
        """Generate health alerts based on thresholds."""
        alerts = []
        
        # CPU usage alert
        if hasattr(health, 'avg_cpu_usage') and health.avg_cpu_usage > self.HEALTH_THRESHOLDS['cpu_usage']:
            alerts.append({
                "severity": "high",
                "type": "cpu_usage",
                "message": f"CPU usage at {health.avg_cpu_usage}% (threshold: {self.HEALTH_THRESHOLDS['cpu_usage']}%)",
                "value": health.avg_cpu_usage,
            })
        
        # Memory usage alert
        if hasattr(health, 'avg_memory_usage') and health.avg_memory_usage > self.HEALTH_THRESHOLDS['memory_usage']:
            alerts.append({
                "severity": "high",
                "type": "memory_usage",
                "message": f"Memory usage at {health.avg_memory_usage}% (threshold: {self.HEALTH_THRESHOLDS['memory_usage']}%)",
                "value": health.avg_memory_usage,
            })
        
        # Error rate alert
        if hasattr(health, 'error_rate') and health.error_rate > self.HEALTH_THRESHOLDS['error_rate']:
            alerts.append({
                "severity": "critical",
                "type": "error_rate",
                "message": f"Error rate at {health.error_rate}% (threshold: {self.HEALTH_THRESHOLDS['error_rate']}%)",
                "value": health.error_rate,
            })
        
        # Response time alert
        if hasattr(health, 'avg_response_time') and health.avg_response_time > self.HEALTH_THRESHOLDS['response_time']:
            alerts.append({
                "severity": "medium",
                "type": "response_time",
                "message": f"Response time at {health.avg_response_time}ms (threshold: {self.HEALTH_THRESHOLDS['response_time']}ms)",
                "value": health.avg_response_time,
            })
        
        return alerts

    def _calculate_usage_metrics(self, usage: PlatformUsageAnalytics) -> PlatformUsageAnalytics:
        """Calculate usage metrics."""
        # Calculate usage rates
        if hasattr(usage, 'total_users') and hasattr(usage, 'active_users'):
            if usage.total_users > 0:
                usage.user_activity_rate = round(
                    (usage.active_users / usage.total_users) * 100, 2
                )
        
        # Calculate average sessions per user
        if hasattr(usage, 'total_sessions') and hasattr(usage, 'active_users'):
            if usage.active_users > 0:
                usage.avg_sessions_per_user = round(
                    usage.total_sessions / usage.active_users, 2
                )
        
        # Calculate average session duration
        if hasattr(usage, 'total_session_time') and hasattr(usage, 'total_sessions'):
            if usage.total_sessions > 0:
                usage.avg_session_duration = round(
                    usage.total_session_time / usage.total_sessions, 2
                )
        
        return usage

    def _calculate_engagement_scores(self, usage: PlatformUsageAnalytics) -> Dict[str, float]:
        """Calculate user engagement scores."""
        scores = {}
        
        # Activity score (based on login frequency)
        if hasattr(usage, 'user_activity_rate'):
            scores['activity'] = min(100, usage.user_activity_rate * 1.2)
        
        # Session score (based on sessions per user)
        if hasattr(usage, 'avg_sessions_per_user'):
            # Normalize to 0-100 (assume 10 sessions = 100)
            scores['sessions'] = min(100, (usage.avg_sessions_per_user / 10) * 100)
        
        # Duration score (based on session duration)
        if hasattr(usage, 'avg_session_duration'):
            # Normalize to 0-100 (assume 30 min = 100)
            scores['duration'] = min(100, (usage.avg_session_duration / 30) * 100)
        
        # Overall engagement score
        if scores:
            scores['overall'] = round(statistics.mean(scores.values()), 2)
        
        return scores

    def _calculate_revenue_kpis(self, revenue: RevenueMetrics) -> RevenueMetrics:
        """Calculate revenue KPIs."""
        # Calculate MRR (Monthly Recurring Revenue)
        if hasattr(revenue, 'total_revenue') and hasattr(revenue, 'period_days'):
            if revenue.period_days > 0:
                revenue.mrr = round((revenue.total_revenue / revenue.period_days) * 30, 2)
        
        # Calculate ARPU (Average Revenue Per User)
        if hasattr(revenue, 'total_revenue') and hasattr(revenue, 'total_users'):
            if revenue.total_users > 0:
                revenue.arpu = round(revenue.total_revenue / revenue.total_users, 2)
        
        # Calculate LTV (Lifetime Value) estimate
        if hasattr(revenue, 'arpu') and hasattr(revenue, 'avg_customer_lifetime_months'):
            revenue.ltv = round(revenue.arpu * revenue.avg_customer_lifetime_months, 2)
        
        return revenue

    def _forecast_revenue(self, revenue: RevenueMetrics) -> Dict[str, Any]:
        """Forecast future revenue."""
        if not hasattr(revenue, 'monthly_revenue_data') or not revenue.monthly_revenue_data:
            return {}
        
        # Calculate growth rate from recent months
        recent_months = revenue.monthly_revenue_data[-6:]
        
        if len(recent_months) < 2:
            return {}
        
        growth_rates = []
        for i in range(1, len(recent_months)):
            if recent_months[i - 1].value > 0:
                growth = (
                    (recent_months[i].value - recent_months[i - 1].value) /
                    recent_months[i - 1].value
                )
                growth_rates.append(growth)
        
        if not growth_rates:
            return {}
        
        avg_growth = statistics.mean(growth_rates)
        last_revenue = recent_months[-1].value
        
        # Forecast next 3 months
        forecast = []
        for i in range(1, 4):
            forecasted_value = last_revenue * ((1 + avg_growth) ** i)
            forecast.append({
                "month": i,
                "forecasted_revenue": round(forecasted_value, 2),
            })
        
        return {
            "forecast_months": forecast,
            "avg_growth_rate": round(avg_growth * 100, 2),
            "confidence": "medium",
            "method": "growth_rate_projection",
        }

    def _segment_tenants(self, tenant_breakdown: List[TenantMetrics]) -> Dict[str, int]:
        """Segment tenants by type."""
        segments = {
            TenantSegment.ENTERPRISE.value: 0,
            TenantSegment.PROFESSIONAL.value: 0,
            TenantSegment.STARTER.value: 0,
            TenantSegment.TRIAL.value: 0,
        }
        
        for tenant in tenant_breakdown:
            segment = getattr(tenant, 'segment', TenantSegment.STARTER.value)
            if segment in segments:
                segments[segment] += 1
        
        return segments

    def _enhance_cohort_analysis(
        self,
        analysis: Dict[str, Any],
        metric: str,
    ) -> Dict[str, Any]:
        """Enhance cohort analysis with insights."""
        if 'cohorts' not in analysis:
            return analysis
        
        # Calculate retention curves
        if metric == "retention":
            analysis['retention_insights'] = self._analyze_retention_cohorts(
                analysis['cohorts']
            )
        
        # Calculate revenue trends
        elif metric == "revenue":
            analysis['revenue_insights'] = self._analyze_revenue_cohorts(
                analysis['cohorts']
            )
        
        return analysis

    def _analyze_retention_cohorts(self, cohorts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze retention cohort data."""
        insights = {
            "avg_30_day_retention": 0,
            "avg_90_day_retention": 0,
            "best_cohort": None,
            "worst_cohort": None,
        }
        
        if not cohorts:
            return insights
        
        # Calculate averages
        retention_30 = [c.get('day_30_retention', 0) for c in cohorts if 'day_30_retention' in c]
        retention_90 = [c.get('day_90_retention', 0) for c in cohorts if 'day_90_retention' in c]
        
        if retention_30:
            insights['avg_30_day_retention'] = round(statistics.mean(retention_30), 2)
        
        if retention_90:
            insights['avg_90_day_retention'] = round(statistics.mean(retention_90), 2)
        
        # Identify best and worst cohorts
        if retention_90:
            best_idx = retention_90.index(max(retention_90))
            worst_idx = retention_90.index(min(retention_90))
            insights['best_cohort'] = cohorts[best_idx].get('cohort_name')
            insights['worst_cohort'] = cohorts[worst_idx].get('cohort_name')
        
        return insights

    def _analyze_revenue_cohorts(self, cohorts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze revenue cohort data."""
        insights = {
            "avg_revenue_per_cohort": 0,
            "highest_revenue_cohort": None,
            "growth_trend": "stable",
        }
        
        if not cohorts:
            return insights
        
        # Calculate average revenue
        revenues = [c.get('total_revenue', 0) for c in cohorts]
        
        if revenues:
            insights['avg_revenue_per_cohort'] = round(statistics.mean(revenues), 2)
            
            # Identify highest revenue cohort
            max_idx = revenues.index(max(revenues))
            insights['highest_revenue_cohort'] = cohorts[max_idx].get('cohort_name')
            
            # Analyze growth trend
            if len(revenues) >= 3:
                recent_avg = statistics.mean(revenues[-3:])
                older_avg = statistics.mean(revenues[:3])
                
                if recent_avg > older_avg * 1.1:
                    insights['growth_trend'] = "growing"
                elif recent_avg < older_avg * 0.9:
                    insights['growth_trend'] = "declining"
        
        return insights