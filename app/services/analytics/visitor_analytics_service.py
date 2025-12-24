"""
Visitor analytics service.

Optimizations:
- Added comprehensive funnel analysis with drop-off tracking
- Implemented traffic source attribution
- Enhanced conversion path analysis
- Added visitor segmentation
- Improved engagement tracking
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
from app.repositories.analytics import VisitorAnalyticsRepository
from app.models.analytics.visitor_analytics import VisitorBehaviorAnalytics as VisitorBehaviorAnalyticsModel
from app.schemas.analytics.visitor_analytics import (
    FunnelStage,
    TrafficSourceMetrics,
    VisitorFunnel,
    TrafficSourceAnalytics,
    SearchBehavior,
    EngagementMetrics,
    VisitorBehaviorAnalytics,
    ConversionPathAnalysis,
)

logger = logging.getLogger(__name__)


class TrafficSource(str, Enum):
    """Traffic source types."""
    ORGANIC = "organic"
    DIRECT = "direct"
    REFERRAL = "referral"
    SOCIAL = "social"
    PAID = "paid"
    EMAIL = "email"


class VisitorSegment(str, Enum):
    """Visitor segment types."""
    NEW = "new"
    RETURNING = "returning"
    LOYAL = "loyal"
    AT_RISK = "at_risk"


class VisitorAnalyticsService(BaseService[VisitorBehaviorAnalyticsModel, VisitorAnalyticsRepository]):
    """
    Service for visitor analytics.
    
    Provides:
    - Visitor funnel analysis
    - Traffic source analytics
    - Search behavior tracking
    - Engagement metrics
    - Conversion path analysis
    - Visitor segmentation
    """

    # Default analysis period
    DEFAULT_ANALYSIS_DAYS = 30
    
    # Engagement thresholds
    ENGAGEMENT_THRESHOLDS = {
        "high": 300,  # seconds
        "medium": 120,
        "low": 30,
    }
    
    # Conversion benchmarks
    CONVERSION_BENCHMARKS = {
        "excellent": 0.05,  # 5%
        "good": 0.03,       # 3%
        "fair": 0.02,       # 2%
        "poor": 0.01,       # 1%
    }
    
    # Cache TTL
    CACHE_TTL = 600  # 10 minutes

    def __init__(self, repository: VisitorAnalyticsRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._cache = {}
        self._cache_timestamps = {}

    def get_funnel(
        self,
        start_date: date,
        end_date: date,
        segment: Optional[str] = None,
    ) -> ServiceResult[VisitorFunnel]:
        """
        Get visitor conversion funnel.
        
        Args:
            start_date: Start date
            end_date: End date
            segment: Optional visitor segment filter
            
        Returns:
            ServiceResult containing funnel data
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Validate segment
            if segment:
                try:
                    VisitorSegment(segment)
                except ValueError:
                    return ServiceResult.error(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Invalid visitor segment: {segment}",
                            severity=ErrorSeverity.ERROR,
                        )
                    )
            
            # Check cache
            cache_key = f"funnel_{start_date}_{end_date}_{segment}"
            if self._is_cache_valid(cache_key):
                logger.debug("Returning cached funnel data")
                return ServiceResult.success(self._cache[cache_key])
            
            # Fetch funnel data
            funnel = self.repository.get_funnel(start_date, end_date, segment)
            
            if not funnel:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No funnel data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Enhance funnel with analytics
            funnel = self._enhance_funnel(funnel)
            
            # Cache result
            self._update_cache(cache_key, funnel)
            
            return ServiceResult.success(
                funnel,
                message="Visitor funnel retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting visitor funnel: {str(e)}")
            return self._handle_exception(e, "get visitor funnel")

    def get_traffic_source_analytics(
        self,
        start_date: date,
        end_date: date,
        include_roi: bool = True,
    ) -> ServiceResult[TrafficSourceAnalytics]:
        """
        Get traffic source analytics.
        
        Args:
            start_date: Start date
            end_date: End date
            include_roi: Include ROI calculations
            
        Returns:
            ServiceResult containing traffic source analytics
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch traffic source data
            analytics = self.repository.get_traffic_source_analytics(start_date, end_date)
            
            if not analytics:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No traffic source data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Calculate source metrics
            analytics = self._calculate_source_metrics(analytics)
            
            # Add ROI if requested
            if include_roi:
                analytics = self._calculate_source_roi(analytics)
            
            return ServiceResult.success(
                analytics,
                message="Traffic source analytics retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting traffic source analytics: {str(e)}")
            return self._handle_exception(e, "get traffic source analytics")

    def get_behavior_analytics(
        self,
        start_date: date,
        end_date: date,
        include_segmentation: bool = True,
    ) -> ServiceResult[VisitorBehaviorAnalytics]:
        """
        Get visitor behavior analytics.
        
        Args:
            start_date: Start date
            end_date: End date
            include_segmentation: Include visitor segmentation
            
        Returns:
            ServiceResult containing behavior analytics
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch behavior analytics
            behavior = self.repository.get_behavior_analytics(start_date, end_date)
            
            if not behavior:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No behavior data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Calculate engagement metrics
            behavior = self._calculate_engagement_metrics(behavior)
            
            # Add segmentation if requested
            if include_segmentation:
                behavior.segments = self._segment_visitors(behavior)
            
            return ServiceResult.success(
                behavior,
                message="Visitor behavior analytics retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting behavior analytics: {str(e)}")
            return self._handle_exception(e, "get visitor behavior analytics")

    def get_conversion_paths(
        self,
        start_date: date,
        end_date: date,
        min_path_frequency: int = 5,
    ) -> ServiceResult[ConversionPathAnalysis]:
        """
        Get conversion path analysis.
        
        Args:
            start_date: Start date
            end_date: End date
            min_path_frequency: Minimum frequency for path inclusion
            
        Returns:
            ServiceResult containing conversion path analysis
        """
        try:
            # Validate inputs
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            if min_path_frequency < 1:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Min path frequency must be at least 1",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch conversion paths
            analysis = self.repository.get_conversion_paths(
                start_date, end_date, min_path_frequency
            )
            
            if not analysis:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No conversion path data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Analyze paths
            analysis = self._analyze_conversion_paths(analysis)
            
            return ServiceResult.success(
                analysis,
                message="Conversion path analysis retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting conversion paths: {str(e)}")
            return self._handle_exception(e, "get conversion paths")

    def get_search_behavior(
        self,
        start_date: date,
        end_date: date,
        top_n: int = 20,
    ) -> ServiceResult[SearchBehavior]:
        """
        Get search behavior analytics.
        
        Args:
            start_date: Start date
            end_date: End date
            top_n: Number of top searches to return
            
        Returns:
            ServiceResult containing search behavior
        """
        try:
            # Validate inputs
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            if top_n < 1 or top_n > 100:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Top N must be between 1 and 100",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch search behavior
            behavior = self.repository.get_search_behavior(start_date, end_date, top_n)
            
            if not behavior:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No search behavior data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Analyze search patterns
            behavior = self._analyze_search_patterns(behavior)
            
            return ServiceResult.success(
                behavior,
                message="Search behavior retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting search behavior: {str(e)}")
            return self._handle_exception(e, "get search behavior")

    def get_engagement_metrics(
        self,
        start_date: date,
        end_date: date,
        group_by: str = "daily",
    ) -> ServiceResult[EngagementMetrics]:
        """
        Get visitor engagement metrics.
        
        Args:
            start_date: Start date
            end_date: End date
            group_by: Grouping granularity (daily, weekly, monthly)
            
        Returns:
            ServiceResult containing engagement metrics
        """
        try:
            # Validate inputs
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            if group_by not in ("daily", "weekly", "monthly"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid group_by: {group_by}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch engagement metrics
            metrics = self.repository.get_engagement_metrics(
                start_date, end_date, group_by
            )
            
            if not metrics:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No engagement data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Calculate engagement scores
            metrics = self._calculate_engagement_scores(metrics)
            
            return ServiceResult.success(
                metrics,
                message="Engagement metrics retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting engagement metrics: {str(e)}")
            return self._handle_exception(e, "get engagement metrics")

    def get_visitor_segmentation(
        self,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get visitor segmentation analysis.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            ServiceResult containing segmentation data
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch visitor data
            behavior = self.repository.get_behavior_analytics(start_date, end_date)
            
            if not behavior:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No visitor data available for segmentation",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Perform segmentation
            segments = self._segment_visitors(behavior)
            
            return ServiceResult.success(
                segments,
                message="Visitor segmentation retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting visitor segmentation: {str(e)}")
            return self._handle_exception(e, "get visitor segmentation")

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
        
        if len(self._cache) > 50:
            oldest_keys = sorted(
                self._cache_timestamps.keys(),
                key=lambda k: self._cache_timestamps[k]
            )[:10]
            for key in oldest_keys:
                del self._cache[key]
                del self._cache_timestamps[key]

    def _enhance_funnel(self, funnel: VisitorFunnel) -> VisitorFunnel:
        """Enhance funnel with conversion rates and drop-offs."""
        if not hasattr(funnel, 'stages') or not funnel.stages:
            return funnel
        
        total_visitors = funnel.stages[0].count if funnel.stages else 0
        
        for i, stage in enumerate(funnel.stages):
            # Calculate conversion rate from initial stage
            if total_visitors > 0:
                stage.conversion_rate = round((stage.count / total_visitors) * 100, 2)
            else:
                stage.conversion_rate = 0.0
            
            # Calculate drop-off from previous stage
            if i > 0:
                previous_stage = funnel.stages[i - 1]
                if previous_stage.count > 0:
                    drop_off = previous_stage.count - stage.count
                    drop_off_rate = (drop_off / previous_stage.count) * 100
                    
                    stage.drop_off_count = drop_off
                    stage.drop_off_rate = round(drop_off_rate, 2)
        
        # Calculate overall conversion rate
        if total_visitors > 0 and funnel.stages:
            final_stage = funnel.stages[-1]
            funnel.overall_conversion_rate = round(
                (final_stage.count / total_visitors) * 100, 4
            )
            
            # Benchmark comparison
            if funnel.overall_conversion_rate >= self.CONVERSION_BENCHMARKS['excellent'] * 100:
                funnel.conversion_benchmark = "excellent"
            elif funnel.overall_conversion_rate >= self.CONVERSION_BENCHMARKS['good'] * 100:
                funnel.conversion_benchmark = "good"
            elif funnel.overall_conversion_rate >= self.CONVERSION_BENCHMARKS['fair'] * 100:
                funnel.conversion_benchmark = "fair"
            else:
                funnel.conversion_benchmark = "needs_improvement"
        
        return funnel

    def _calculate_source_metrics(
        self,
        analytics: TrafficSourceAnalytics,
    ) -> TrafficSourceAnalytics:
        """Calculate traffic source metrics."""
        if not hasattr(analytics, 'sources') or not analytics.sources:
            return analytics
        
        total_visitors = sum(s.visitors for s in analytics.sources)
        total_conversions = sum(s.conversions for s in analytics.sources)
        
        for source in analytics.sources:
            # Calculate percentage of total traffic
            if total_visitors > 0:
                source.traffic_percentage = round(
                    (source.visitors / total_visitors) * 100, 2
                )
            
            # Calculate conversion rate
            if source.visitors > 0:
                source.conversion_rate = round(
                    (source.conversions / source.visitors) * 100, 2
                )
            
            # Calculate bounce rate
            if hasattr(source, 'bounces') and source.visitors > 0:
                source.bounce_rate = round(
                    (source.bounces / source.visitors) * 100, 2
                )
        
        # Sort by visitors descending
        analytics.sources.sort(key=lambda x: x.visitors, reverse=True)
        
        return analytics

    def _calculate_source_roi(
        self,
        analytics: TrafficSourceAnalytics,
    ) -> TrafficSourceAnalytics:
        """Calculate ROI for traffic sources."""
        if not hasattr(analytics, 'sources'):
            return analytics
        
        for source in analytics.sources:
            # Calculate ROI if cost and revenue data available
            if hasattr(source, 'cost') and hasattr(source, 'revenue'):
                if source.cost and source.cost > 0:
                    roi = ((source.revenue - source.cost) / source.cost) * 100
                    source.roi = round(roi, 2)
                    
                    # ROI category
                    if roi >= 200:
                        source.roi_category = "excellent"
                    elif roi >= 100:
                        source.roi_category = "good"
                    elif roi >= 0:
                        source.roi_category = "break_even"
                    else:
                        source.roi_category = "negative"
            
            # Calculate cost per conversion
            if hasattr(source, 'cost') and source.conversions > 0:
                source.cost_per_conversion = round(source.cost / source.conversions, 2)
        
        return analytics

    def _calculate_engagement_metrics(
        self,
        behavior: VisitorBehaviorAnalytics,
    ) -> VisitorBehaviorAnalytics:
        """Calculate visitor engagement metrics."""
        # Calculate average session duration
        if hasattr(behavior, 'total_session_time') and hasattr(behavior, 'total_sessions'):
            if behavior.total_sessions > 0:
                behavior.avg_session_duration = round(
                    behavior.total_session_time / behavior.total_sessions, 2
                )
        
        # Calculate pages per session
        if hasattr(behavior, 'total_page_views') and hasattr(behavior, 'total_sessions'):
            if behavior.total_sessions > 0:
                behavior.avg_pages_per_session = round(
                    behavior.total_page_views / behavior.total_sessions, 2
                )
        
        # Calculate bounce rate
        if hasattr(behavior, 'bounced_sessions') and hasattr(behavior, 'total_sessions'):
            if behavior.total_sessions > 0:
                behavior.bounce_rate = round(
                    (behavior.bounced_sessions / behavior.total_sessions) * 100, 2
                )
        
        # Engagement level
        if hasattr(behavior, 'avg_session_duration'):
            if behavior.avg_session_duration >= self.ENGAGEMENT_THRESHOLDS['high']:
                behavior.engagement_level = "high"
            elif behavior.avg_session_duration >= self.ENGAGEMENT_THRESHOLDS['medium']:
                behavior.engagement_level = "medium"
            else:
                behavior.engagement_level = "low"
        
        return behavior

    def _segment_visitors(self, behavior: VisitorBehaviorAnalytics) -> Dict[str, Any]:
        """Segment visitors based on behavior."""
        segments = {
            VisitorSegment.NEW.value: 0,
            VisitorSegment.RETURNING.value: 0,
            VisitorSegment.LOYAL.value: 0,
            VisitorSegment.AT_RISK.value: 0,
        }
        
        # Simplified segmentation logic
        if hasattr(behavior, 'new_visitors'):
            segments[VisitorSegment.NEW.value] = behavior.new_visitors
        
        if hasattr(behavior, 'returning_visitors'):
            segments[VisitorSegment.RETURNING.value] = behavior.returning_visitors
        
        # Calculate percentages
        total = sum(segments.values())
        if total > 0:
            segment_percentages = {
                segment: round((count / total) * 100, 2)
                for segment, count in segments.items()
            }
        else:
            segment_percentages = {segment: 0.0 for segment in segments.keys()}
        
        return {
            "segments": segments,
            "segment_percentages": segment_percentages,
            "total_visitors": total,
        }

    def _analyze_conversion_paths(
        self,
        analysis: ConversionPathAnalysis,
    ) -> ConversionPathAnalysis:
        """Analyze conversion paths."""
        if not hasattr(analysis, 'paths') or not analysis.paths:
            return analysis
        
        # Sort paths by frequency
        analysis.paths.sort(key=lambda x: x.frequency, reverse=True)
        
        # Calculate path metrics
        total_conversions = sum(p.conversions for p in analysis.paths)
        
        for path in analysis.paths:
            # Calculate conversion rate
            if path.frequency > 0:
                path.conversion_rate = round(
                    (path.conversions / path.frequency) * 100, 2
                )
            
            # Calculate contribution to total conversions
            if total_conversions > 0:
                path.conversion_contribution = round(
                    (path.conversions / total_conversions) * 100, 2
                )
        
        # Identify most efficient path
        if analysis.paths:
            most_efficient = max(
                analysis.paths,
                key=lambda x: x.conversion_rate if hasattr(x, 'conversion_rate') else 0
            )
            analysis.most_efficient_path = most_efficient
        
        return analysis

    def _analyze_search_patterns(self, behavior: SearchBehavior) -> SearchBehavior:
        """Analyze search patterns."""
        if not hasattr(behavior, 'top_searches') or not behavior.top_searches:
            return behavior
        
        # Calculate search success rate
        if hasattr(behavior, 'total_searches') and hasattr(behavior, 'successful_searches'):
            if behavior.total_searches > 0:
                behavior.search_success_rate = round(
                    (behavior.successful_searches / behavior.total_searches) * 100, 2
                )
        
        # Calculate average results per search
        if hasattr(behavior, 'total_results') and hasattr(behavior, 'total_searches'):
            if behavior.total_searches > 0:
                behavior.avg_results_per_search = round(
                    behavior.total_results / behavior.total_searches, 2
                )
        
        # Identify trending searches (simplified)
        if hasattr(behavior, 'top_searches'):
            # Top 5 as trending
            behavior.trending_searches = behavior.top_searches[:5]
        
        return behavior

    def _calculate_engagement_scores(
        self,
        metrics: EngagementMetrics,
    ) -> EngagementMetrics:
        """Calculate engagement scores."""
        scores = []
        
        # Session duration score
        if hasattr(metrics, 'avg_session_duration'):
            duration_score = min(100, (metrics.avg_session_duration / 600) * 100)  # 10 min = 100
            scores.append(duration_score)
        
        # Pages per session score
        if hasattr(metrics, 'avg_pages_per_session'):
            pages_score = min(100, (metrics.avg_pages_per_session / 10) * 100)  # 10 pages = 100
            scores.append(pages_score)
        
        # Bounce rate score (inverted - lower is better)
        if hasattr(metrics, 'bounce_rate'):
            bounce_score = max(0, 100 - metrics.bounce_rate)
            scores.append(bounce_score)
        
        # Calculate overall engagement score
        if scores:
            metrics.overall_engagement_score = round(statistics.mean(scores), 2)
            
            # Categorize
            if metrics.overall_engagement_score >= 75:
                metrics.engagement_category = "highly_engaged"
            elif metrics.overall_engagement_score >= 50:
                metrics.engagement_category = "engaged"
            elif metrics.overall_engagement_score >= 25:
                metrics.engagement_category = "moderately_engaged"
            else:
                metrics.engagement_category = "low_engagement"
        
        return metrics