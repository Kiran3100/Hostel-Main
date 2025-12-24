"""
Communication analytics service with cross-channel insights.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum
import logging
from functools import lru_cache

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult
from app.repositories.notification import (
    NotificationRepository,
    NotificationAggregateRepository,
    EmailNotificationRepository,
    SMSNotificationRepository,
)
from app.models.notification.notification import Notification


logger = logging.getLogger(__name__)


class AnalyticsPeriod(str, Enum):
    """Predefined analytics periods."""
    LAST_HOUR = "last_hour"
    LAST_24_HOURS = "last_24_hours"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    CUSTOM = "custom"


class CommunicationAnalyticsService(BaseService[Notification, NotificationRepository]):
    """
    Cross-channel communication analytics and reporting service.
    
    Features:
    - Multi-channel performance metrics
    - Delivery and engagement analytics
    - Trend analysis
    - ROI calculations
    - Comparative channel analysis
    """

    # Constants
    CACHE_TTL_SECONDS = 300  # 5 minutes cache for analytics
    DEFAULT_PERIOD = AnalyticsPeriod.LAST_7_DAYS

    def __init__(
        self,
        repository: NotificationRepository,
        aggregate_repo: NotificationAggregateRepository,
        email_repo: EmailNotificationRepository,
        sms_repo: SMSNotificationRepository,
        db_session: Session,
    ):
        super().__init__(repository, db_session)
        self.aggregate_repo = aggregate_repo
        self.email_repo = email_repo
        self.sms_repo = sms_repo
        self._logger = logger

    def get_overview(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        period: Optional[AnalyticsPeriod] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get overall communication performance across all channels.
        
        Args:
            start: Start of period (mutually exclusive with period)
            end: End of period
            period: Predefined period (mutually exclusive with start/end)
            
        Returns:
            ServiceResult containing overview metrics
        """
        # Resolve time period
        start_time, end_time = self._resolve_time_period(start, end, period)
        
        self._logger.info(
            f"Retrieving communication overview for period {start_time} to {end_time}"
        )

        try:
            # Get aggregate data
            overview_data = self.aggregate_repo.get_overview(start_time, end_time)
            
            # Enhance with calculated metrics
            enhanced_overview = self._enhance_overview_metrics(
                overview_data or {},
                start_time,
                end_time
            )

            self._logger.debug("Successfully retrieved communication overview")

            return ServiceResult.success(
                enhanced_overview,
                metadata={
                    "period": {
                        "start": start_time.isoformat(),
                        "end": end_time.isoformat(),
                    }
                }
            )

        except Exception as e:
            self._logger.error(
                f"Error retrieving communication overview: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get communication overview")

    def get_channel_stats(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        period: Optional[AnalyticsPeriod] = None,
        channels: Optional[List[str]] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get detailed statistics for each communication channel.
        
        Args:
            start: Start of period
            end: End of period
            period: Predefined period
            channels: Specific channels to include (None = all)
            
        Returns:
            ServiceResult containing per-channel statistics
        """
        # Resolve time period
        start_time, end_time = self._resolve_time_period(start, end, period)
        
        self._logger.info(
            f"Retrieving channel stats for period {start_time} to {end_time}"
        )

        try:
            channel_data = {}
            
            # Collect stats for each channel
            if channels is None or "email" in channels:
                email_stats = self.email_repo.get_stats(start_time, end_time)
                channel_data["email"] = self._serialize_stats(email_stats)
            
            if channels is None or "sms" in channels:
                sms_stats = self.sms_repo.get_stats(start_time, end_time)
                channel_data["sms"] = self._serialize_stats(sms_stats)
            
            # Could add push/in_app if available
            if channels is None or "push" in channels:
                if hasattr(self.repository, 'get_push_stats'):
                    push_stats = self.repository.get_push_stats(start_time, end_time)
                    channel_data["push"] = self._serialize_stats(push_stats)
            
            if channels is None or "in_app" in channels:
                if hasattr(self.repository, 'get_in_app_stats'):
                    in_app_stats = self.repository.get_in_app_stats(start_time, end_time)
                    channel_data["in_app"] = self._serialize_stats(in_app_stats)

            # Add comparative analysis
            comparative_analysis = self._calculate_channel_comparison(channel_data)

            result = {
                "channels": channel_data,
                "comparison": comparative_analysis,
            }

            self._logger.debug(f"Retrieved stats for {len(channel_data)} channels")

            return ServiceResult.success(
                result,
                metadata={
                    "period": {
                        "start": start_time.isoformat(),
                        "end": end_time.isoformat(),
                    },
                    "channels_included": list(channel_data.keys()),
                }
            )

        except Exception as e:
            self._logger.error(
                f"Error retrieving channel stats: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get channel stats")

    def get_delivery_report(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        period: Optional[AnalyticsPeriod] = None,
        include_failures: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get detailed delivery report with success/failure breakdown.
        
        Args:
            start: Start of period
            end: End of period
            period: Predefined period
            include_failures: Include detailed failure analysis
            
        Returns:
            ServiceResult containing delivery report
        """
        # Resolve time period
        start_time, end_time = self._resolve_time_period(start, end, period)
        
        self._logger.info(
            f"Generating delivery report for period {start_time} to {end_time}"
        )

        try:
            # Get base delivery report
            report_data = self.aggregate_repo.get_delivery_report(start_time, end_time)
            
            # Enhance with additional metrics
            enhanced_report = self._enhance_delivery_report(
                report_data or {},
                start_time,
                end_time,
                include_failures
            )

            self._logger.debug("Successfully generated delivery report")

            return ServiceResult.success(
                enhanced_report,
                metadata={
                    "period": {
                        "start": start_time.isoformat(),
                        "end": end_time.isoformat(),
                    }
                }
            )

        except Exception as e:
            self._logger.error(
                f"Error generating delivery report: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get delivery report")

    def get_engagement_metrics(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        period: Optional[AnalyticsPeriod] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get engagement metrics (opens, clicks, responses).
        
        Args:
            start: Start of period
            end: End of period
            period: Predefined period
            
        Returns:
            ServiceResult containing engagement metrics
        """
        # Resolve time period
        start_time, end_time = self._resolve_time_period(start, end, period)
        
        self._logger.info(
            f"Calculating engagement metrics for period {start_time} to {end_time}"
        )

        try:
            engagement_data = {}
            
            # Email engagement
            if hasattr(self.email_repo, 'get_engagement_metrics'):
                email_engagement = self.email_repo.get_engagement_metrics(
                    start_time,
                    end_time
                )
                engagement_data["email"] = self._serialize_stats(email_engagement)
            
            # SMS engagement (if tracked)
            if hasattr(self.sms_repo, 'get_engagement_metrics'):
                sms_engagement = self.sms_repo.get_engagement_metrics(
                    start_time,
                    end_time
                )
                engagement_data["sms"] = self._serialize_stats(sms_engagement)

            # Calculate overall engagement score
            overall_score = self._calculate_engagement_score(engagement_data)

            result = {
                "channels": engagement_data,
                "overall_score": overall_score,
            }

            return ServiceResult.success(
                result,
                metadata={
                    "period": {
                        "start": start_time.isoformat(),
                        "end": end_time.isoformat(),
                    }
                }
            )

        except Exception as e:
            self._logger.error(
                f"Error calculating engagement metrics: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get engagement metrics")

    def get_trend_analysis(
        self,
        metric: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        period: Optional[AnalyticsPeriod] = None,
        granularity: str = "day",
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get trend analysis for a specific metric over time.
        
        Args:
            metric: Metric to analyze (e.g., 'sent', 'delivered', 'opened')
            start: Start of period
            end: End of period
            period: Predefined period
            granularity: Time granularity (hour, day, week, month)
            
        Returns:
            ServiceResult containing trend data
        """
        # Resolve time period
        start_time, end_time = self._resolve_time_period(start, end, period)
        
        self._logger.info(
            f"Generating trend analysis for '{metric}' with {granularity} granularity"
        )

        try:
            if hasattr(self.aggregate_repo, 'get_trend_data'):
                trend_data = self.aggregate_repo.get_trend_data(
                    metric=metric,
                    start=start_time,
                    end=end_time,
                    granularity=granularity,
                )
            else:
                trend_data = {"message": "Trend analysis not yet implemented"}

            return ServiceResult.success(
                trend_data or {},
                metadata={
                    "metric": metric,
                    "granularity": granularity,
                    "period": {
                        "start": start_time.isoformat(),
                        "end": end_time.isoformat(),
                    }
                }
            )

        except Exception as e:
            self._logger.error(
                f"Error generating trend analysis: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get trend analysis")

    # Private helper methods

    def _resolve_time_period(
        self,
        start: Optional[datetime],
        end: Optional[datetime],
        period: Optional[AnalyticsPeriod],
    ) -> tuple[datetime, datetime]:
        """
        Resolve time period from either explicit dates or predefined period.
        
        Returns:
            Tuple of (start_time, end_time)
        """
        if start and end:
            return start, end
        
        end_time = datetime.utcnow()
        
        if period == AnalyticsPeriod.LAST_HOUR:
            start_time = end_time - timedelta(hours=1)
        elif period == AnalyticsPeriod.LAST_24_HOURS:
            start_time = end_time - timedelta(days=1)
        elif period == AnalyticsPeriod.LAST_7_DAYS:
            start_time = end_time - timedelta(days=7)
        elif period == AnalyticsPeriod.LAST_30_DAYS:
            start_time = end_time - timedelta(days=30)
        elif period == AnalyticsPeriod.LAST_90_DAYS:
            start_time = end_time - timedelta(days=90)
        else:
            # Default to last 7 days
            start_time = end_time - timedelta(days=7)
        
        return start_time, end_time

    def _serialize_stats(self, stats: Any) -> Dict[str, Any]:
        """Serialize stats object to dictionary."""
        if hasattr(stats, "model_dump"):
            return stats.model_dump()
        elif hasattr(stats, "dict"):
            return stats.dict()
        elif isinstance(stats, dict):
            return stats
        return {}

    def _enhance_overview_metrics(
        self,
        overview: Dict[str, Any],
        start: datetime,
        end: datetime,
    ) -> Dict[str, Any]:
        """Add calculated metrics to overview."""
        enhanced = {**overview}
        
        # Calculate rates
        total_sent = overview.get("total_sent", 0)
        if total_sent > 0:
            enhanced["delivery_rate"] = (
                overview.get("total_delivered", 0) / total_sent * 100
            )
            enhanced["failure_rate"] = (
                overview.get("total_failed", 0) / total_sent * 100
            )
        
        # Add time context
        enhanced["period_duration_hours"] = (end - start).total_seconds() / 3600
        
        return enhanced

    def _enhance_delivery_report(
        self,
        report: Dict[str, Any],
        start: datetime,
        end: datetime,
        include_failures: bool,
    ) -> Dict[str, Any]:
        """Enhance delivery report with additional analysis."""
        enhanced = {**report}
        
        # Add failure analysis if requested
        if include_failures and hasattr(self.aggregate_repo, 'get_failure_breakdown'):
            try:
                failure_breakdown = self.aggregate_repo.get_failure_breakdown(
                    start,
                    end
                )
                enhanced["failure_analysis"] = failure_breakdown
            except Exception as e:
                self._logger.warning(f"Could not get failure breakdown: {str(e)}")
        
        return enhanced

    def _calculate_channel_comparison(
        self,
        channel_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate comparative metrics across channels."""
        comparison = {
            "best_delivery_rate": {"channel": None, "rate": 0},
            "best_engagement_rate": {"channel": None, "rate": 0},
            "total_volume_by_channel": {},
        }
        
        for channel, stats in channel_data.items():
            # Delivery rate
            if isinstance(stats, dict):
                delivery_rate = stats.get("delivery_rate", 0)
                if delivery_rate > comparison["best_delivery_rate"]["rate"]:
                    comparison["best_delivery_rate"] = {
                        "channel": channel,
                        "rate": delivery_rate,
                    }
                
                # Volume
                comparison["total_volume_by_channel"][channel] = stats.get(
                    "total_sent",
                    0
                )
        
        return comparison

    def _calculate_engagement_score(
        self,
        engagement_data: Dict[str, Any],
    ) -> float:
        """
        Calculate overall engagement score (0-100).
        
        Weighted average across channels based on volume and engagement.
        """
        if not engagement_data:
            return 0.0
        
        total_weight = 0
        weighted_sum = 0
        
        for channel, data in engagement_data.items():
            if isinstance(data, dict):
                # Use open rate or click rate as engagement indicator
                engagement_rate = data.get("open_rate", 0) or data.get("click_rate", 0)
                volume = data.get("total_sent", 0)
                
                weighted_sum += engagement_rate * volume
                total_weight += volume
        
        if total_weight > 0:
            return round(weighted_sum / total_weight, 2)
        
        return 0.0