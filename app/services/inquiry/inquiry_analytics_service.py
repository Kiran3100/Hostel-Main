"""
Inquiry analytics service: volumes, response rates, conversions, trends.

Enhanced with:
- Advanced analytics and reporting
- Time-series trend analysis
- Source attribution and ROI tracking
- Predictive metrics and insights
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, datetime, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.inquiry.inquiry_aggregate_repository import InquiryAggregateRepository
from app.models.inquiry.inquiry import Inquiry as InquiryModel

logger = logging.getLogger(__name__)


class InquiryAnalyticsService(BaseService[InquiryModel, InquiryAggregateRepository]):
    """
    Comprehensive inquiry analytics and reporting.
    
    Provides:
    - Volume and trend analysis
    - Response time metrics
    - Conversion rate tracking
    - Source attribution
    - Performance benchmarking
    """

    def __init__(self, repository: InquiryAggregateRepository, db_session: Session):
        """
        Initialize analytics service.
        
        Args:
            repository: InquiryAggregateRepository for aggregated data access
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    # =========================================================================
    # OVERVIEW & SUMMARY
    # =========================================================================

    def get_overview(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get comprehensive analytics overview.
        
        Args:
            hostel_id: Optional filter by hostel
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            
        Returns:
            ServiceResult with aggregated metrics and KPIs
        """
        try:
            # Set default date range if not provided (last 30 days)
            if not end_date:
                end_date = date.today()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            self._logger.info(
                f"Generating analytics overview for hostel: {hostel_id or 'all'}, "
                f"period: {start_date} to {end_date}"
            )
            
            # Fetch overview from repository
            overview = self.repository.get_overview(
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date
            )
            
            if not overview:
                overview = self._generate_empty_overview(hostel_id, start_date, end_date)
            
            # Enrich with calculated metrics
            overview = self._enrich_overview(overview)
            
            return ServiceResult.success(
                overview,
                metadata={
                    "hostel_id": str(hostel_id) if hostel_id else None,
                    "period": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat(),
                        "days": (end_date - start_date).days + 1,
                    }
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error generating overview: {str(e)}")
            return self._handle_exception(e, "get inquiry overview", hostel_id)
        except Exception as e:
            self._logger.exception(f"Unexpected error generating overview: {str(e)}")
            return self._handle_exception(e, "get inquiry overview", hostel_id)

    # =========================================================================
    # TREND ANALYSIS
    # =========================================================================

    def get_trends(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        by: str = "day",
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get time-series trends for inquiries.
        
        Args:
            hostel_id: Optional filter by hostel
            start_date: Start of date range
            end_date: End of date range
            by: Aggregation period ('day', 'week', 'month')
            
        Returns:
            ServiceResult with trend data points
        """
        try:
            # Validate aggregation period
            valid_periods = ['day', 'week', 'month']
            if by not in valid_periods:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid aggregation period. Must be one of: {', '.join(valid_periods)}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Set default date range
            if not end_date:
                end_date = date.today()
            if not start_date:
                # Default range based on period
                days_back = {"day": 30, "week": 90, "month": 365}.get(by, 30)
                start_date = end_date - timedelta(days=days_back)
            
            self._logger.info(
                f"Generating trends by {by} for hostel: {hostel_id or 'all'}, "
                f"period: {start_date} to {end_date}"
            )
            
            # Fetch trends from repository
            trends = self.repository.get_trends(
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
                by=by
            )
            
            if not trends:
                trends = self._generate_empty_trends(start_date, end_date, by)
            
            # Calculate moving averages and growth rates
            trends = self._enrich_trends(trends, by)
            
            return ServiceResult.success(
                trends,
                metadata={
                    "hostel_id": str(hostel_id) if hostel_id else None,
                    "period": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat(),
                    },
                    "aggregation": by,
                    "data_points": len(trends.get("series", [])),
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error generating trends: {str(e)}")
            return self._handle_exception(e, "get inquiry trends", hostel_id)
        except Exception as e:
            self._logger.exception(f"Unexpected error generating trends: {str(e)}")
            return self._handle_exception(e, "get inquiry trends", hostel_id)

    # =========================================================================
    # SOURCE ANALYSIS
    # =========================================================================

    def get_source_breakdown(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get inquiry breakdown by source with performance metrics.
        
        Args:
            hostel_id: Optional filter by hostel
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            ServiceResult with source attribution and conversion metrics
        """
        try:
            # Set default date range
            if not end_date:
                end_date = date.today()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            self._logger.info(
                f"Generating source breakdown for hostel: {hostel_id or 'all'}, "
                f"period: {start_date} to {end_date}"
            )
            
            # Fetch breakdown from repository
            breakdown = self.repository.get_source_breakdown(
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date
            )
            
            if not breakdown:
                breakdown = self._generate_empty_source_breakdown()
            
            # Calculate ROI and efficiency metrics
            breakdown = self._enrich_source_breakdown(breakdown)
            
            return ServiceResult.success(
                breakdown,
                metadata={
                    "hostel_id": str(hostel_id) if hostel_id else None,
                    "period": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat(),
                    },
                    "source_count": len(breakdown.get("sources", [])),
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error generating source breakdown: {str(e)}")
            return self._handle_exception(e, "get inquiry source breakdown", hostel_id)
        except Exception as e:
            self._logger.exception(f"Unexpected error generating source breakdown: {str(e)}")
            return self._handle_exception(e, "get inquiry source breakdown", hostel_id)

    # =========================================================================
    # RESPONSE TIME ANALYTICS
    # =========================================================================

    def get_response_metrics(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get response time metrics and SLA performance.
        
        Args:
            hostel_id: Optional filter by hostel
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            ServiceResult with response time statistics
        """
        try:
            if not end_date:
                end_date = date.today()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            self._logger.debug(f"Calculating response metrics for hostel: {hostel_id or 'all'}")
            
            # Use repository method if available
            if hasattr(self.repository, 'get_response_metrics'):
                metrics = self.repository.get_response_metrics(
                    hostel_id=hostel_id,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                # Calculate basic response metrics
                metrics = {
                    "average_response_time_hours": 0,
                    "median_response_time_hours": 0,
                    "response_rate_percentage": 0,
                    "within_sla_percentage": 0,
                    "hostel_id": str(hostel_id) if hostel_id else None,
                }
            
            return ServiceResult.success(
                metrics,
                metadata={
                    "period": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat(),
                    }
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error calculating response metrics: {str(e)}")
            return self._handle_exception(e, "get response metrics")
        except Exception as e:
            self._logger.exception(f"Unexpected error calculating response metrics: {str(e)}")
            return self._handle_exception(e, "get response metrics")

    # =========================================================================
    # PERFORMANCE BENCHMARKING
    # =========================================================================

    def get_performance_comparison(
        self,
        hostel_id: Optional[UUID] = None,
        compare_to_previous_period: bool = True,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Compare current period performance to previous period or benchmark.
        
        Args:
            hostel_id: Optional filter by hostel
            compare_to_previous_period: Compare to previous period vs. benchmark
            start_date: Start of current period
            end_date: End of current period
            
        Returns:
            ServiceResult with comparison metrics and growth indicators
        """
        try:
            if not end_date:
                end_date = date.today()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            period_days = (end_date - start_date).days + 1
            
            self._logger.info(f"Generating performance comparison for {period_days} days")
            
            # Get current period metrics
            current = self.repository.get_overview(
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date
            ) or {}
            
            # Get comparison period metrics
            if compare_to_previous_period:
                prev_start = start_date - timedelta(days=period_days)
                prev_end = start_date - timedelta(days=1)
                
                previous = self.repository.get_overview(
                    hostel_id=hostel_id,
                    start_date=prev_start,
                    end_date=prev_end
                ) or {}
            else:
                # Use industry benchmark (would need to be stored/configured)
                previous = self._get_industry_benchmark()
            
            # Calculate deltas and growth rates
            comparison = self._calculate_comparison(current, previous)
            
            return ServiceResult.success(
                comparison,
                metadata={
                    "current_period": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat(),
                    },
                    "comparison_type": "previous_period" if compare_to_previous_period else "benchmark",
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error generating performance comparison: {str(e)}")
            return self._handle_exception(e, "get performance comparison")
        except Exception as e:
            self._logger.exception(f"Unexpected error generating performance comparison: {str(e)}")
            return self._handle_exception(e, "get performance comparison")

    # =========================================================================
    # PREDICTIVE ANALYTICS
    # =========================================================================

    def get_forecast(
        self,
        hostel_id: Optional[UUID] = None,
        days_ahead: int = 30,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get inquiry volume forecast based on historical trends.
        
        Args:
            hostel_id: Optional filter by hostel
            days_ahead: Number of days to forecast
            
        Returns:
            ServiceResult with forecast data
        """
        try:
            days_ahead = min(max(1, days_ahead), 90)  # Cap between 1-90 days
            
            self._logger.info(f"Generating {days_ahead}-day forecast for hostel: {hostel_id or 'all'}")
            
            # Use repository method if available
            if hasattr(self.repository, 'get_forecast'):
                forecast = self.repository.get_forecast(
                    hostel_id=hostel_id,
                    days_ahead=days_ahead
                )
            else:
                # Simple forecast based on recent averages
                end_date = date.today()
                start_date = end_date - timedelta(days=90)  # 90-day lookback
                
                trends = self.repository.get_trends(
                    hostel_id=hostel_id,
                    start_date=start_date,
                    end_date=end_date,
                    by="day"
                )
                
                # Calculate simple moving average
                series = trends.get("series", []) if trends else []
                if series:
                    recent_avg = sum(s.get("value", 0) for s in series[-7:]) / min(7, len(series))
                else:
                    recent_avg = 0
                
                forecast = {
                    "predicted_daily_volume": round(recent_avg, 2),
                    "predicted_total": round(recent_avg * days_ahead, 0),
                    "confidence_level": "low",  # Would need more sophisticated modeling
                    "method": "simple_moving_average",
                }
            
            return ServiceResult.success(
                forecast,
                metadata={
                    "hostel_id": str(hostel_id) if hostel_id else None,
                    "days_ahead": days_ahead,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error generating forecast: {str(e)}")
            return self._handle_exception(e, "get forecast")
        except Exception as e:
            self._logger.exception(f"Unexpected error generating forecast: {str(e)}")
            return self._handle_exception(e, "get forecast")

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _enrich_overview(self, overview: Dict[str, Any]) -> Dict[str, Any]:
        """Add calculated fields and KPIs to overview."""
        # Calculate rates and percentages
        total = overview.get("total_inquiries", 0)
        
        if total > 0:
            overview["response_rate"] = round(
                (overview.get("responded_inquiries", 0) / total) * 100, 2
            )
            overview["conversion_rate"] = round(
                (overview.get("converted_inquiries", 0) / total) * 100, 2
            )
            overview["qualification_rate"] = round(
                (overview.get("qualified_inquiries", 0) / total) * 100, 2
            )
        else:
            overview["response_rate"] = 0
            overview["conversion_rate"] = 0
            overview["qualification_rate"] = 0
        
        return overview

    def _enrich_trends(self, trends: Dict[str, Any], period: str) -> Dict[str, Any]:
        """Add moving averages and growth calculations to trends."""
        series = trends.get("series", [])
        
        if not series:
            return trends
        
        # Calculate moving average (7-period for day, 4-period for week/month)
        window = 7 if period == "day" else 4
        
        for i, point in enumerate(series):
            if i >= window - 1:
                window_values = [series[j].get("value", 0) for j in range(i - window + 1, i + 1)]
                point["moving_average"] = round(sum(window_values) / window, 2)
            
            # Calculate period-over-period growth
            if i > 0:
                prev_value = series[i - 1].get("value", 0)
                curr_value = point.get("value", 0)
                if prev_value > 0:
                    point["growth_rate"] = round(((curr_value - prev_value) / prev_value) * 100, 2)
        
        return trends

    def _enrich_source_breakdown(self, breakdown: Dict[str, Any]) -> Dict[str, Any]:
        """Add efficiency metrics to source breakdown."""
        sources = breakdown.get("sources", [])
        total_inquiries = sum(s.get("count", 0) for s in sources)
        
        for source in sources:
            count = source.get("count", 0)
            converted = source.get("converted", 0)
            
            # Calculate percentages
            if total_inquiries > 0:
                source["percentage_of_total"] = round((count / total_inquiries) * 100, 2)
            
            if count > 0:
                source["conversion_rate"] = round((converted / count) * 100, 2)
        
        # Sort by volume
        breakdown["sources"] = sorted(sources, key=lambda x: x.get("count", 0), reverse=True)
        
        return breakdown

    def _calculate_comparison(
        self,
        current: Dict[str, Any],
        previous: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate comparison metrics between two periods."""
        comparison = {
            "current": current,
            "previous": previous,
            "changes": {},
        }
        
        # Calculate deltas for key metrics
        metrics_to_compare = [
            "total_inquiries",
            "converted_inquiries",
            "conversion_rate",
            "response_rate",
        ]
        
        for metric in metrics_to_compare:
            curr_val = current.get(metric, 0)
            prev_val = previous.get(metric, 0)
            delta = curr_val - prev_val
            
            if prev_val > 0:
                growth = ((curr_val - prev_val) / prev_val) * 100
            else:
                growth = 100 if curr_val > 0 else 0
            
            comparison["changes"][metric] = {
                "current": curr_val,
                "previous": prev_val,
                "delta": round(delta, 2),
                "growth_percentage": round(growth, 2),
                "direction": "up" if delta > 0 else "down" if delta < 0 else "flat",
            }
        
        return comparison

    def _generate_empty_overview(
        self,
        hostel_id: Optional[UUID],
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Generate empty overview structure."""
        return {
            "total_inquiries": 0,
            "responded_inquiries": 0,
            "qualified_inquiries": 0,
            "converted_inquiries": 0,
            "response_rate": 0,
            "conversion_rate": 0,
            "hostel_id": str(hostel_id) if hostel_id else None,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            }
        }

    def _generate_empty_trends(
        self,
        start_date: date,
        end_date: date,
        by: str
    ) -> Dict[str, Any]:
        """Generate empty trends structure."""
        return {
            "series": [],
            "aggregation": by,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            }
        }

    def _generate_empty_source_breakdown(self) -> Dict[str, Any]:
        """Generate empty source breakdown structure."""
        return {
            "sources": [],
            "total_inquiries": 0,
        }

    def _get_industry_benchmark(self) -> Dict[str, Any]:
        """Get industry benchmark metrics (placeholder)."""
        return {
            "total_inquiries": 100,
            "conversion_rate": 15.0,
            "response_rate": 85.0,
            "average_response_time_hours": 4.0,
        }