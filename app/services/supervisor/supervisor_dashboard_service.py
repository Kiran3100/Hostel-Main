"""
Supervisor Dashboard Service

Builds the supervisor dashboard view.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.supervisor import SupervisorDashboardRepository
from app.schemas.supervisor import SupervisorDashboard
from app.core.exceptions import ValidationException


class SupervisorDashboardService:
    """
    High-level service to build supervisor dashboard data structure.

    Aggregates:
    - Dashboard metrics
    - Tasks & recents
    - Today schedule
    - Alerts
    - Performance indicators
    """

    def __init__(
        self,
        dashboard_repo: SupervisorDashboardRepository,
    ) -> None:
        self.dashboard_repo = dashboard_repo

    def get_dashboard(
        self,
        db: Session,
        supervisor_id: UUID,
        hostel_id: UUID,
    ) -> SupervisorDashboard:
        """
        Build and return the supervisor dashboard payload.

        hostel_id is used when supervisors manage multiple hostels.
        """
        data = self.dashboard_repo.get_dashboard_data(
            db=db,
            supervisor_id=supervisor_id,
            hostel_id=hostel_id,
        )
        if not data:
            raise ValidationException("Dashboard data not found")

        return SupervisorDashboard.model_validate(data)