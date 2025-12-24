# app/services/reporting/operational_report_service.py
"""
Operational Report Service

Builds higher-level operational reports by composing multiple analytics:

- Bookings
- Complaints
- Occupancy
- Team/supervisor performance
"""

from __future__ import annotations

from uuid import UUID
from typing import Dict, Any

from sqlalchemy.orm import Session

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
from app.core.exceptions import ValidationException


class OperationalReportService:
    """
    High-level service that aggregates multiple analytics into
    a single "Operational Report" payload for a hostel.
    """

    def __init__(
        self,
        booking_analytics_repo: BookingAnalyticsRepository,
        complaint_analytics_repo: ComplaintAnalyticsRepository,
        occupancy_analytics_repo: OccupancyAnalyticsRepository,
        supervisor_analytics_repo: SupervisorAnalyticsRepository,
    ) -> None:
        self.booking_analytics_repo = booking_analytics_repo
        self.complaint_analytics_repo = complaint_analytics_repo
        self.occupancy_analytics_repo = occupancy_analytics_repo
        self.supervisor_analytics_repo = supervisor_analytics_repo

    def get_operational_report(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Compose an operational report for a hostel and period.

        Returns:
            {
                "hostel_id": ...,
                "period": {start_date, end_date},
                "bookings": BookingAnalyticsSummary,
                "complaints": ComplaintDashboard,
                "occupancy": OccupancyReport,
                "team": TeamAnalytics,
            }
        """
        booking_data = self.booking_analytics_repo.get_summary_for_hostel(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        complaint_data = self.complaint_analytics_repo.get_dashboard_for_hostel(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        occupancy_data = self.occupancy_analytics_repo.get_report_for_hostel(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        team_data = self.supervisor_analytics_repo.get_team_analytics(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )

        if not any([booking_data, complaint_data, occupancy_data, team_data]):
            raise ValidationException("No operational data available for this period")

        report: Dict[str, Any] = {
            "hostel_id": str(hostel_id),
            "period": {
                "start_date": period.start_date,
                "end_date": period.end_date,
            },
            "bookings": BookingAnalyticsSummary.model_validate(booking_data)
            if booking_data
            else None,
            "complaints": ComplaintDashboard.model_validate(complaint_data)
            if complaint_data
            else None,
            "occupancy": OccupancyReport.model_validate(occupancy_data)
            if occupancy_data
            else None,
            "team": TeamAnalytics.model_validate(team_data)
            if team_data
            else None,
        }
        return report