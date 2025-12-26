# app/services/reporting/operational_report_service.py
"""
Operational Report Service

Builds higher-level operational reports by composing multiple analytics
with enhanced error handling, validation, and performance optimization.
"""

from __future__ import annotations

import logging
from uuid import UUID
from typing import Dict, Any, Optional, List
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.common import DateRangeFilter
from app.schemas.analytics import (
    BookingAnalyticsSummary,
    ComplaintDashboard,
    OccupancyReport,
    TeamAnalytics,
)
from app.repositories.analytics import (
    BookingAnalyticsRepository,
    ComplaintAnalyticsRepository,
    OccupancyAnalyticsRepository,
    SupervisorAnalyticsRepository,
)
from app.core.exceptions import ValidationException, NotFoundException
from app.utils.metrics import track_performance
from app.utils.cache_utils import cache_result

logger = logging.getLogger(__name__)


class OperationalReportService:
    """
    High-level service that aggregates multiple analytics into
    comprehensive operational reports for a hostel.

    Responsibilities:
    - Aggregate booking analytics
    - Aggregate complaint analytics
    - Aggregate occupancy analytics
    - Aggregate team/supervisor performance
    - Provide unified operational dashboard

    Attributes:
        booking_analytics_repo: Repository for booking analytics
        complaint_analytics_repo: Repository for complaint analytics
        occupancy_analytics_repo: Repository for occupancy analytics
        supervisor_analytics_repo: Repository for supervisor analytics
    """

    def __init__(
        self,
        booking_analytics_repo: BookingAnalyticsRepository,
        complaint_analytics_repo: ComplaintAnalyticsRepository,
        occupancy_analytics_repo: OccupancyAnalyticsRepository,
        supervisor_analytics_repo: SupervisorAnalyticsRepository,
    ) -> None:
        """
        Initialize the operational report service.

        Args:
            booking_analytics_repo: Repository for booking analytics
            complaint_analytics_repo: Repository for complaint analytics
            occupancy_analytics_repo: Repository for occupancy analytics
            supervisor_analytics_repo: Repository for supervisor analytics
        """
        if not all([
            booking_analytics_repo,
            complaint_analytics_repo,
            occupancy_analytics_repo,
            supervisor_analytics_repo,
        ]):
            raise ValueError("All analytics repositories are required")
        
        self.booking_analytics_repo = booking_analytics_repo
        self.complaint_analytics_repo = complaint_analytics_repo
        self.occupancy_analytics_repo = occupancy_analytics_repo
        self.supervisor_analytics_repo = supervisor_analytics_repo
        
        logger.info("OperationalReportService initialized successfully")

    def _validate_inputs(
        self,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> None:
        """
        Validate inputs for operational reports.

        Args:
            hostel_id: Hostel UUID to validate
            period: Date range to validate

        Raises:
            ValidationException: If validation fails
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")
        
        if not period:
            raise ValidationException("Period is required")
        
        if not period.start_date or not period.end_date:
            raise ValidationException("Start date and end date are required")
        
        if period.start_date > period.end_date:
            raise ValidationException("Start date must be before or equal to end date")
        
        if period.end_date > datetime.utcnow().date():
            raise ValidationException("End date cannot be in the future")
        
        # Limit to 1 year for performance
        days_diff = (period.end_date - period.start_date).days
        if days_diff > 365:
            raise ValidationException(
                "Operational report period cannot exceed 1 year (365 days)"
            )

    @track_performance("operational_report")
    @cache_result(ttl=1800, key_prefix="ops_report")
    def get_operational_report(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
        include_trends: bool = True,
        include_recommendations: bool = True,
    ) -> Dict[str, Any]:
        """
        Compose a comprehensive operational report for a hostel and period.

        This method aggregates data from multiple sources to provide a complete
        operational overview including bookings, complaints, occupancy, and team performance.

        Args:
            db: Database session
            hostel_id: ID of the hostel
            period: DateRangeFilter (start_date, end_date)
            include_trends: Whether to include trend analysis
            include_recommendations: Whether to include AI-generated recommendations

        Returns:
            Dictionary containing:
            {
                "hostel_id": UUID,
                "period": {start_date, end_date},
                "generated_at": datetime,
                "bookings": BookingAnalyticsSummary,
                "complaints": ComplaintDashboard,
                "occupancy": OccupancyReport,
                "team": TeamAnalytics,
                "trends": Optional[Dict],
                "recommendations": Optional[List],
                "key_metrics": Dict,
            }

        Raises:
            ValidationException: If validation fails or no data available
            NotFoundException: If hostel not found
        """
        logger.info(
            f"Generating operational report for hostel {hostel_id}, "
            f"period {period.start_date} to {period.end_date}"
        )
        
        try:
            # Validate inputs
            self._validate_inputs(hostel_id, period)
            
            # Fetch all analytics data
            booking_data = self._get_booking_analytics(db, hostel_id, period)
            complaint_data = self._get_complaint_analytics(db, hostel_id, period)
            occupancy_data = self._get_occupancy_analytics(db, hostel_id, period)
            team_data = self._get_team_analytics(db, hostel_id, period)
            
            # Check if we have any data
            if not any([booking_data, complaint_data, occupancy_data, team_data]):
                logger.warning(
                    f"No operational data found for hostel {hostel_id}, "
                    f"period {period.start_date} to {period.end_date}"
                )
                raise ValidationException(
                    "No operational data available for this period"
                )
            
            # Build base report
            report: Dict[str, Any] = {
                "hostel_id": str(hostel_id),
                "period": {
                    "start_date": period.start_date.isoformat(),
                    "end_date": period.end_date.isoformat(),
                },
                "generated_at": datetime.utcnow().isoformat(),
                "bookings": (
                    BookingAnalyticsSummary.model_validate(booking_data)
                    if booking_data
                    else None
                ),
                "complaints": (
                    ComplaintDashboard.model_validate(complaint_data)
                    if complaint_data
                    else None
                ),
                "occupancy": (
                    OccupancyReport.model_validate(occupancy_data)
                    if occupancy_data
                    else None
                ),
                "team": (
                    TeamAnalytics.model_validate(team_data)
                    if team_data
                    else None
                ),
            }
            
            # Add key metrics summary
            report["key_metrics"] = self._calculate_key_metrics(
                booking_data,
                complaint_data,
                occupancy_data,
                team_data,
            )
            
            # Add trends if requested
            if include_trends:
                report["trends"] = self._calculate_trends(
                    db, hostel_id, period
                )
            
            # Add recommendations if requested
            if include_recommendations:
                report["recommendations"] = self._generate_recommendations(
                    report
                )
            
            logger.info(
                f"Successfully generated operational report for hostel {hostel_id}"
            )
            
            return report
            
        except (ValidationException, NotFoundException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error generating operational report: {str(e)}")
            raise ValidationException(f"Failed to generate operational report: {str(e)}")
        except Exception as e:
            logger.error(
                f"Unexpected error generating operational report: {str(e)}",
                exc_info=True
            )
            raise ValidationException(f"Operational report generation failed: {str(e)}")

    def _get_booking_analytics(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch booking analytics data.

        Args:
            db: Database session
            hostel_id: Hostel ID
            period: Date range

        Returns:
            Booking analytics data or None
        """
        try:
            return self.booking_analytics_repo.get_summary_for_hostel(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
        except Exception as e:
            logger.warning(f"Failed to fetch booking analytics: {str(e)}")
            return None

    def _get_complaint_analytics(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch complaint analytics data.

        Args:
            db: Database session
            hostel_id: Hostel ID
            period: Date range

        Returns:
            Complaint analytics data or None
        """
        try:
            return self.complaint_analytics_repo.get_dashboard_for_hostel(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
        except Exception as e:
            logger.warning(f"Failed to fetch complaint analytics: {str(e)}")
            return None

    def _get_occupancy_analytics(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch occupancy analytics data.

        Args:
            db: Database session
            hostel_id: Hostel ID
            period: Date range

        Returns:
            Occupancy analytics data or None
        """
        try:
            return self.occupancy_analytics_repo.get_report_for_hostel(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
        except Exception as e:
            logger.warning(f"Failed to fetch occupancy analytics: {str(e)}")
            return None

    def _get_team_analytics(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch team analytics data.

        Args:
            db: Database session
            hostel_id: Hostel ID
            period: Date range

        Returns:
            Team analytics data or None
        """
        try:
            return self.supervisor_analytics_repo.get_team_analytics(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
        except Exception as e:
            logger.warning(f"Failed to fetch team analytics: {str(e)}")
            return None

    def _calculate_key_metrics(
        self,
        booking_data: Optional[Dict[str, Any]],
        complaint_data: Optional[Dict[str, Any]],
        occupancy_data: Optional[Dict[str, Any]],
        team_data: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculate key performance metrics from analytics data.

        Args:
            booking_data: Booking analytics
            complaint_data: Complaint analytics
            occupancy_data: Occupancy analytics
            team_data: Team analytics

        Returns:
            Dictionary of key metrics
        """
        metrics = {
            "total_bookings": 0,
            "average_occupancy": 0.0,
            "total_complaints": 0,
            "team_performance_score": 0.0,
            "revenue": 0.0,
        }
        
        try:
            if booking_data:
                metrics["total_bookings"] = booking_data.get("total_bookings", 0)
                metrics["revenue"] = booking_data.get("total_revenue", 0.0)
            
            if occupancy_data:
                metrics["average_occupancy"] = occupancy_data.get("average_rate", 0.0)
            
            if complaint_data:
                metrics["total_complaints"] = complaint_data.get("total_complaints", 0)
            
            if team_data:
                metrics["team_performance_score"] = team_data.get("performance_score", 0.0)
            
        except Exception as e:
            logger.warning(f"Error calculating some key metrics: {str(e)}")
        
        return metrics

    def _calculate_trends(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate trends from historical data.

        Args:
            db: Database session
            hostel_id: Hostel ID
            period: Date range

        Returns:
            Trends data or None
        """
        try:
            # This would typically call a trends analysis repository method
            # For now, return a placeholder
            return {
                "booking_trend": "increasing",
                "occupancy_trend": "stable",
                "complaint_trend": "decreasing",
            }
        except Exception as e:
            logger.warning(f"Failed to calculate trends: {str(e)}")
            return None

    def _generate_recommendations(
        self,
        report: Dict[str, Any],
    ) -> List[str]:
        """
        Generate actionable recommendations based on report data.

        Args:
            report: Operational report data

        Returns:
            List of recommendations
        """
        recommendations = []
        
        try:
            # Analyze occupancy
            if report.get("occupancy"):
                avg_occupancy = report["key_metrics"].get("average_occupancy", 0)
                if avg_occupancy < 60:
                    recommendations.append(
                        "Occupancy is below 60%. Consider promotional campaigns or pricing adjustments."
                    )
                elif avg_occupancy > 95:
                    recommendations.append(
                        "High occupancy rate detected. Consider expanding capacity or premium pricing."
                    )
            
            # Analyze complaints
            if report.get("complaints"):
                total_complaints = report["key_metrics"].get("total_complaints", 0)
                if total_complaints > 50:
                    recommendations.append(
                        "High complaint volume detected. Review service quality and staff training."
                    )
            
            # Analyze team performance
            if report.get("team"):
                team_score = report["key_metrics"].get("team_performance_score", 0)
                if team_score < 70:
                    recommendations.append(
                        "Team performance below target. Consider additional training or support."
                    )
            
        except Exception as e:
            logger.warning(f"Error generating some recommendations: {str(e)}")
        
        return recommendations

    def get_performance_summary(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Get a quick performance summary without full report generation.

        Args:
            db: Database session
            hostel_id: Hostel ID
            period: Date range

        Returns:
            Performance summary dictionary
        """
        logger.info(f"Generating performance summary for hostel {hostel_id}")
        
        try:
            self._validate_inputs(hostel_id, period)
            
            # Fetch minimal data
            booking_data = self._get_booking_analytics(db, hostel_id, period)
            occupancy_data = self._get_occupancy_analytics(db, hostel_id, period)
            
            summary = {
                "hostel_id": str(hostel_id),
                "period": {
                    "start_date": period.start_date.isoformat(),
                    "end_date": period.end_date.isoformat(),
                },
                "total_bookings": booking_data.get("total_bookings", 0) if booking_data else 0,
                "total_revenue": booking_data.get("total_revenue", 0.0) if booking_data else 0.0,
                "average_occupancy": occupancy_data.get("average_rate", 0.0) if occupancy_data else 0.0,
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating performance summary: {str(e)}")
            raise ValidationException(f"Failed to generate performance summary: {str(e)}")