"""
Visitor Dashboard Service

Builds the visitor dashboard view by aggregating data from multiple repositories.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.visitor import VisitorAggregateRepository
from app.schemas.visitor import VisitorDashboard
from app.core.exceptions import ValidationException


class VisitorDashboardService:
    """
    Aggregate service for visitor dashboards.

    Uses VisitorAggregateRepository (read model) to collect:
    - Saved hostels
    - Booking history
    - Recent searches & views
    - Recommendations
    - Price/availability alerts
    """

    def __init__(
        self,
        aggregate_repo: VisitorAggregateRepository,
    ) -> None:
        self.aggregate_repo = aggregate_repo

    def get_dashboard(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> VisitorDashboard:
        """
        Build the dashboard for a specific visitor.
        """
        data = self.aggregate_repo.get_dashboard_data(db, visitor_id)
        if not data:
            raise ValidationException("Visitor not found or no dashboard data")

        # data is expected to be a dict compatible with VisitorDashboard
        return VisitorDashboard.model_validate(data)