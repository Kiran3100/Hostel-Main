"""
Complaint analytics service (dashboard & breakdowns).

Provides comprehensive analytics including dashboards, KPIs, trends,
and various data breakdowns for complaint analysis.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, timedelta, datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.analytics.complaint_analytics_repository import ComplaintAnalyticsRepository
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
    Analytics wrapper for complaints: dashboard, KPIs, trends, breakdowns.
    
    Provides comprehensive analytical capabilities for complaint data
    including real-time dashboards and historical trend analysis.
    """

    def __init__(self, repository: ComplaintAnalyticsRepository, db_session: Session):
        """
        Initialize analytics service.
        
        Args:
            repository: Complaint analytics repository instance
            db_session: Active database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    # -------------------------------------------------------------------------
    # Dashboard
    # -------------------------------------------------------------------------

    def dashboard(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[ComplaintDashboard]:
        """
        Get comprehensive complaint dashboard data.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start date for dashboard
            end_date: End date for dashboard
            
        Returns:
            ServiceResult containing ComplaintDashboard or error
        """
        try:
            # Validate date range
            date_validation = self._validate_date_range(start_date, end_date)
            if not date_validation.success:
                return date_validation
            
            self._logger.debug(
                f"Fetching complaint dashboard for hostel {hostel_id}, "
                f"date range: {start_date} to {end_date}"
            )
            
            payload = self.repository.get_dashboard(hostel_id, start_date, end_date)
            
            return ServiceResult.success(
                payload,
                metadata={
                    "hostel_id": str(hostel_id),
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "generated_at": datetime.utcnow().isoformat(),
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching dashboard for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint dashboard", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching dashboard for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint dashboard", hostel_id)

    # -------------------------------------------------------------------------
    # KPIs
    # -------------------------------------------------------------------------

    def kpis(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[ComplaintKPI]:
        """
        Get key performance indicators for complaints.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start date for KPIs
            end_date: End date for KPIs
            
        Returns:
            ServiceResult containing ComplaintKPI or error
        """
        try:
            # Validate date range
            date_validation = self._validate_date_range(start_date, end_date)
            if not date_validation.success:
                return date_validation
            
            self._logger.debug(
                f"Fetching complaint KPIs for hostel {hostel_id}, "
                f"date range: {start_date} to {end_date}"
            )
            
            kpi = self.repository.get_kpis(hostel_id, start_date, end_date)
            
            return ServiceResult.success(
                kpi,
                metadata={
                    "hostel_id": str(hostel_id),
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching KPIs for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint kpis", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching KPIs for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint kpis", hostel_id)

    # -------------------------------------------------------------------------
    # Trends
    # -------------------------------------------------------------------------

    def trend(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        interval: str = "daily",
    ) -> ServiceResult[ComplaintTrend]:
        """
        Get complaint trends over time.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start date for trend
            end_date: End date for trend
            interval: Aggregation interval ("daily", "weekly", "monthly")
            
        Returns:
            ServiceResult containing ComplaintTrend or error
        """
        try:
            # Validate date range
            date_validation = self._validate_date_range(start_date, end_date)
            if not date_validation.success:
                return date_validation
            
            # Validate interval
            valid_intervals = ["daily", "weekly", "monthly"]
            if interval not in valid_intervals:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid interval. Must be one of: {', '.join(valid_intervals)}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            self._logger.debug(
                f"Fetching complaint trend for hostel {hostel_id}, "
                f"interval: {interval}, date range: {start_date} to {end_date}"
            )
            
            trend = self.repository.get_trend(hostel_id, start_date, end_date)
            
            return ServiceResult.success(
                trend,
                metadata={
                    "hostel_id": str(hostel_id),
                    "interval": interval,
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "data_points": len(trend.points) if hasattr(trend, 'points') else 0,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching trend for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint trend", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching trend for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint trend", hostel_id)

    # -------------------------------------------------------------------------
    # Breakdowns
    # -------------------------------------------------------------------------

    def category_breakdown(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[List[CategoryBreakdown]]:
        """
        Get breakdown of complaints by category.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start date for breakdown
            end_date: End date for breakdown
            
        Returns:
            ServiceResult containing list of CategoryBreakdown or error
        """
        try:
            # Validate date range
            date_validation = self._validate_date_range(start_date, end_date)
            if not date_validation.success:
                return date_validation
            
            self._logger.debug(
                f"Fetching category breakdown for hostel {hostel_id}, "
                f"date range: {start_date} to {end_date}"
            )
            
            breakdown = self.repository.get_category_breakdown(hostel_id, start_date, end_date)
            
            return ServiceResult.success(
                breakdown,
                metadata={
                    "count": len(breakdown),
                    "hostel_id": str(hostel_id),
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching category breakdown for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint category breakdown", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching category breakdown for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint category breakdown", hostel_id)

    def priority_breakdown(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[List[PriorityBreakdown]]:
        """
        Get breakdown of complaints by priority.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start date for breakdown
            end_date: End date for breakdown
            
        Returns:
            ServiceResult containing list of PriorityBreakdown or error
        """
        try:
            # Validate date range
            date_validation = self._validate_date_range(start_date, end_date)
            if not date_validation.success:
                return date_validation
            
            self._logger.debug(
                f"Fetching priority breakdown for hostel {hostel_id}, "
                f"date range: {start_date} to {end_date}"
            )
            
            breakdown = self.repository.get_priority_breakdown(hostel_id, start_date, end_date)
            
            return ServiceResult.success(
                breakdown,
                metadata={
                    "count": len(breakdown),
                    "hostel_id": str(hostel_id),
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching priority breakdown for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint priority breakdown", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching priority breakdown for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint priority breakdown", hostel_id)

    def status_breakdown(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get breakdown of complaints by status.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start date for breakdown
            end_date: End date for breakdown
            
        Returns:
            ServiceResult containing status breakdown or error
        """
        try:
            # Validate date range
            date_validation = self._validate_date_range(start_date, end_date)
            if not date_validation.success:
                return date_validation
            
            self._logger.debug(
                f"Fetching status breakdown for hostel {hostel_id}, "
                f"date range: {start_date} to {end_date}"
            )
            
            # Implementation would call repository method
            breakdown: List[Dict[str, Any]] = []
            
            return ServiceResult.success(
                breakdown,
                metadata={
                    "count": len(breakdown),
                    "hostel_id": str(hostel_id),
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                }
            )
            
        except Exception as e:
            self._logger.error(
                f"Error fetching status breakdown for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get status breakdown", hostel_id)

    # -------------------------------------------------------------------------
    # Comparison Analytics
    # -------------------------------------------------------------------------

    def compare_periods(
        self,
        hostel_id: UUID,
        current_start: date,
        current_end: date,
        previous_start: date,
        previous_end: date,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Compare complaint metrics between two time periods.
        
        Args:
            hostel_id: UUID of hostel
            current_start: Current period start date
            current_end: Current period end date
            previous_start: Previous period start date
            previous_end: Previous period end date
            
        Returns:
            ServiceResult containing comparison data or error
        """
        try:
            # Validate both date ranges
            current_validation = self._validate_date_range(current_start, current_end)
            if not current_validation.success:
                return current_validation
            
            previous_validation = self._validate_date_range(previous_start, previous_end)
            if not previous_validation.success:
                return previous_validation
            
            self._logger.debug(
                f"Comparing periods for hostel {hostel_id}: "
                f"current ({current_start} to {current_end}) vs "
                f"previous ({previous_start} to {previous_end})"
            )
            
            # Get KPIs for both periods
            current_kpi = self.repository.get_kpis(hostel_id, current_start, current_end)
            previous_kpi = self.repository.get_kpis(hostel_id, previous_start, previous_end)
            
            # Calculate comparisons
            comparison = self._calculate_period_comparison(current_kpi, previous_kpi)
            
            return ServiceResult.success(
                comparison,
                metadata={
                    "hostel_id": str(hostel_id),
                    "current_period": f"{current_start} to {current_end}",
                    "previous_period": f"{previous_start} to {previous_end}",
                }
            )
            
        except Exception as e:
            self._logger.error(
                f"Error comparing periods for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "compare periods", hostel_id)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _validate_date_range(
        self,
        start_date: date,
        end_date: date,
        max_range_days: int = 365
    ) -> ServiceResult[None]:
        """
        Validate date range for queries.
        
        Args:
            start_date: Start date
            end_date: End date
            max_range_days: Maximum allowed range in days
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if start_date > end_date:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Start date must be before or equal to end date",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        delta = end_date - start_date
        if delta.days > max_range_days:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Date range cannot exceed {max_range_days} days",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)

    def _calculate_period_comparison(
        self,
        current: ComplaintKPI,
        previous: ComplaintKPI
    ) -> Dict[str, Any]:
        """
        Calculate comparison metrics between two periods.
        
        Args:
            current: Current period KPIs
            previous: Previous period KPIs
            
        Returns:
            Dictionary containing comparison metrics
        """
        comparison = {
            "current": current,
            "previous": previous,
            "changes": {},
        }
        
        # Calculate percentage changes for key metrics
        # This would be implemented based on your KPI structure
        
        return comparison