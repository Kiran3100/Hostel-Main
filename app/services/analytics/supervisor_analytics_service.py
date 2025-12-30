"""
Supervisor analytics service.

Optimizations:
- Added performance benchmarking
- Implemented team analytics and comparisons
- Enhanced workload analysis
- Added productivity metrics
- Improved trend analysis
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, timedelta, datetime
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
from app.repositories.analytics import SupervisorAnalyticsRepository
from app.models.analytics.supervisor_analytics import SupervisorKPI
from app.schemas.analytics.supervisor_analytics import (
    SupervisorWorkload,
    SupervisorPerformanceRating,
    SupervisorKPI as SupervisorKPISchema,
    SupervisorTrendPoint,
    SupervisorDashboardAnalytics,
    SupervisorComparison,
    TeamAnalytics,
)

logger = logging.getLogger(__name__)


class SupervisorAnalyticsService(BaseService[SupervisorKPI, SupervisorAnalyticsRepository]):
    """
    Service for supervisor analytics.
    
    Provides:
    - Supervisor KPIs and performance metrics
    - Workload analysis
    - Team analytics
    - Comparative analytics
    - Performance trends
    """

    # Default analysis period
    DEFAULT_ANALYSIS_DAYS = 30
    
    # Performance thresholds
    PERFORMANCE_THRESHOLDS = {
        "excellent": 90,
        "good": 75,
        "fair": 60,
        "poor": 40,
    }
    
    # Cache TTL
    CACHE_TTL = 300  # 5 minutes

    def __init__(self, repository: SupervisorAnalyticsRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._cache = {}
        self._cache_timestamps = {}

    def get_dashboard(
        self,
        supervisor_id: UUID,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        include_team: bool = True,
    ) -> ServiceResult[SupervisorDashboardAnalytics]:
        """
        Get supervisor dashboard analytics.
        
        Args:
            supervisor_id: Supervisor UUID
            hostel_id: Hostel UUID
            start_date: Start date
            end_date: End date
            include_team: Include team analytics
            
        Returns:
            ServiceResult containing supervisor dashboard
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Check cache
            cache_key = f"supervisor_dashboard_{supervisor_id}_{hostel_id}_{start_date}_{end_date}"
            if self._is_cache_valid(cache_key):
                logger.debug(f"Returning cached dashboard for supervisor {supervisor_id}")
                return ServiceResult.success(self._cache[cache_key])
            
            # Fetch dashboard data
            data = self.repository.get_dashboard(supervisor_id, hostel_id, start_date, end_date)
            
            if not data:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No data found for supervisor {supervisor_id}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Enhance dashboard
            data = self._enhance_supervisor_dashboard(data)
            
            # Add team analytics if requested
            if include_team:
                team_result = self.get_team_analytics(hostel_id, start_date, end_date)
                if team_result.success:
                    data.team_analytics = team_result.data
            
            # Cache result
            self._update_cache(cache_key, data)
            
            return ServiceResult.success(
                data,
                message="Supervisor dashboard retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting supervisor dashboard: {str(e)}")
            return self._handle_exception(e, "get supervisor dashboard", supervisor_id)

    def compare_supervisors(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        metric: str = "performance",
    ) -> ServiceResult[SupervisorComparison]:
        """
        Compare supervisors within a hostel.
        
        Args:
            hostel_id: Hostel UUID
            start_date: Start date
            end_date: End date
            metric: Metric to compare (performance, workload, resolution_time)
            
        Returns:
            ServiceResult containing supervisor comparison
        """
        try:
            # Validate inputs
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            if metric not in ("performance", "workload", "resolution_time", "satisfaction"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid comparison metric: {metric}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch comparison data
            comparison = self.repository.get_comparison(hostel_id, start_date, end_date, metric)
            
            if not comparison:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No comparison data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Enhance comparison with rankings and insights
            comparison = self._enhance_comparison(comparison, metric)
            
            return ServiceResult.success(
                comparison,
                message="Supervisor comparison retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error comparing supervisors: {str(e)}")
            return self._handle_exception(e, "compare supervisors", hostel_id)

    def get_team_analytics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[TeamAnalytics]:
        """
        Get team-wide analytics.
        
        Args:
            hostel_id: Hostel UUID
            start_date: Start date
            end_date: End date
            
        Returns:
            ServiceResult containing team analytics
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch team analytics
            team = self.repository.get_team_analytics(hostel_id, start_date, end_date)
            
            if not team:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No team analytics available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Calculate team metrics
            team = self._calculate_team_metrics(team)
            
            return ServiceResult.success(
                team,
                message="Team analytics retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting team analytics: {str(e)}")
            return self._handle_exception(e, "get team analytics", hostel_id)

    def get_workload_analysis(
        self,
        supervisor_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[SupervisorWorkload]:
        """
        Get detailed workload analysis for a supervisor.
        
        Args:
            supervisor_id: Supervisor UUID
            start_date: Start date
            end_date: End date
            
        Returns:
            ServiceResult containing workload analysis
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch workload data
            workload = self.repository.get_workload(supervisor_id, start_date, end_date)
            
            if not workload:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No workload data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Analyze workload
            workload = self._analyze_workload(workload)
            
            return ServiceResult.success(
                workload,
                message="Workload analysis retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting workload analysis: {str(e)}")
            return self._handle_exception(e, "get workload analysis", supervisor_id)

    def get_performance_rating(
        self,
        supervisor_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[SupervisorPerformanceRating]:
        """
        Get performance rating for a supervisor.
        
        Args:
            supervisor_id: Supervisor UUID
            start_date: Start date
            end_date: End date
            
        Returns:
            ServiceResult containing performance rating
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch performance data
            performance = self.repository.get_performance_rating(
                supervisor_id, start_date, end_date
            )
            
            if not performance:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No performance data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Calculate performance score
            performance = self._calculate_performance_score(performance)
            
            return ServiceResult.success(
                performance,
                message="Performance rating retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting performance rating: {str(e)}")
            return self._handle_exception(e, "get performance rating", supervisor_id)

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
        
        if len(self._cache) > 100:
            oldest_keys = sorted(
                self._cache_timestamps.keys(),
                key=lambda k: self._cache_timestamps[k]
            )[:20]
            for key in oldest_keys:
                del self._cache[key]
                del self._cache_timestamps[key]

    def _enhance_supervisor_dashboard(
        self,
        data: SupervisorDashboardAnalytics,
    ) -> SupervisorDashboardAnalytics:
        """Enhance dashboard with additional metrics."""
        # Add performance indicator
        if hasattr(data, 'kpi') and hasattr(data.kpi, 'performance_score'):
            score = data.kpi.performance_score
            
            if score >= self.PERFORMANCE_THRESHOLDS['excellent']:
                data.performance_indicator = "excellent"
            elif score >= self.PERFORMANCE_THRESHOLDS['good']:
                data.performance_indicator = "good"
            elif score >= self.PERFORMANCE_THRESHOLDS['fair']:
                data.performance_indicator = "fair"
            else:
                data.performance_indicator = "needs_improvement"
        
        # Add generated timestamp
        data.generated_at = datetime.utcnow()
        
        return data

    def _enhance_comparison(
        self,
        comparison: SupervisorComparison,
        metric: str,
    ) -> SupervisorComparison:
        """Enhance comparison with rankings and insights."""
        if not hasattr(comparison, 'supervisor_metrics') or not comparison.supervisor_metrics:
            return comparison
        
        # Sort by metric
        metric_map = {
            "performance": "performance_score",
            "workload": "total_tasks",
            "resolution_time": "avg_resolution_time",
            "satisfaction": "satisfaction_score",
        }
        
        sort_key = metric_map.get(metric, "performance_score")
        reverse = metric != "resolution_time"  # Lower is better for resolution time
        
        sorted_metrics = sorted(
            comparison.supervisor_metrics,
            key=lambda x: getattr(x, sort_key, 0) or 0,
            reverse=reverse
        )
        
        # Add rankings
        for i, supervisor_metric in enumerate(sorted_metrics, 1):
            supervisor_metric.rank = i
        
        comparison.supervisor_metrics = sorted_metrics
        
        # Add insights
        if len(sorted_metrics) > 0:
            best = sorted_metrics[0]
            worst = sorted_metrics[-1]
            
            comparison.insights = {
                "top_performer": getattr(best, 'supervisor_id', None),
                "needs_support": getattr(worst, 'supervisor_id', None),
                "metric_analyzed": metric,
            }
        
        return comparison

    def _calculate_team_metrics(self, team: TeamAnalytics) -> TeamAnalytics:
        """Calculate team-wide metrics."""
        if hasattr(team, 'supervisor_count') and team.supervisor_count > 0:
            # Calculate averages
            if hasattr(team, 'total_tasks') and hasattr(team, 'supervisor_count'):
                team.avg_tasks_per_supervisor = round(
                    team.total_tasks / team.supervisor_count, 1
                )
            
            if hasattr(team, 'total_resolution_time') and hasattr(team, 'total_tasks'):
                if team.total_tasks > 0:
                    team.avg_resolution_time = round(
                        team.total_resolution_time / team.total_tasks, 2
                    )
        
        # Calculate team efficiency
        if hasattr(team, 'completed_tasks') and hasattr(team, 'total_tasks'):
            if team.total_tasks > 0:
                team.completion_rate = round(
                    (team.completed_tasks / team.total_tasks) * 100, 2
                )
        
        return team

    def _analyze_workload(self, workload: SupervisorWorkload) -> SupervisorWorkload:
        """Analyze workload and add insights."""
        # Calculate workload balance
        if hasattr(workload, 'assigned_tasks') and hasattr(workload, 'team_avg_tasks'):
            if workload.team_avg_tasks > 0:
                balance_ratio = workload.assigned_tasks / workload.team_avg_tasks
                
                if balance_ratio > 1.2:
                    workload.workload_status = "overloaded"
                elif balance_ratio < 0.8:
                    workload.workload_status = "underutilized"
                else:
                    workload.workload_status = "balanced"
        
        # Calculate task completion velocity
        if hasattr(workload, 'completed_tasks') and hasattr(workload, 'period_days'):
            if workload.period_days > 0:
                workload.daily_completion_rate = round(
                    workload.completed_tasks / workload.period_days, 2
                )
        
        return workload

    def _calculate_performance_score(
        self,
        performance: SupervisorPerformanceRating,
    ) -> SupervisorPerformanceRating:
        """Calculate overall performance score."""
        scores = []
        weights = {}
        
        # Task completion score (30%)
        if hasattr(performance, 'task_completion_rate'):
            scores.append(performance.task_completion_rate)
            weights[len(scores) - 1] = 0.30
        
        # Resolution time score (25%)
        if hasattr(performance, 'avg_resolution_time') and hasattr(performance, 'target_resolution_time'):
            if performance.target_resolution_time > 0:
                # Lower is better - invert the score
                time_score = min(100, (performance.target_resolution_time / performance.avg_resolution_time) * 100)
                scores.append(time_score)
                weights[len(scores) - 1] = 0.25
        
        # Customer satisfaction score (25%)
        if hasattr(performance, 'satisfaction_score'):
            scores.append(performance.satisfaction_score)
            weights[len(scores) - 1] = 0.25
        
        # Quality score (20%)
        if hasattr(performance, 'quality_score'):
            scores.append(performance.quality_score)
            weights[len(scores) - 1] = 0.20
        
        # Calculate weighted average
        if scores:
            weighted_sum = sum(score * weights.get(i, 1) for i, score in enumerate(scores))
            total_weight = sum(weights.values())
            
            if total_weight > 0:
                performance.overall_score = round(weighted_sum / total_weight, 2)
                
                # Determine rating
                if performance.overall_score >= self.PERFORMANCE_THRESHOLDS['excellent']:
                    performance.rating = "excellent"
                elif performance.overall_score >= self.PERFORMANCE_THRESHOLDS['good']:
                    performance.rating = "good"
                elif performance.overall_score >= self.PERFORMANCE_THRESHOLDS['fair']:
                    performance.rating = "fair"
                else:
                    performance.rating = "needs_improvement"
        
        return performance