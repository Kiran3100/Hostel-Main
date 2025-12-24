"""
Supervisor Scheduling Service

Provides high-level operations around daily schedules for supervisors.
"""

from __future__ import annotations

from uuid import UUID
from datetime import date

from sqlalchemy.orm import Session

from app.repositories.supervisor import SupervisorDashboardRepository
from app.schemas.supervisor import TodaySchedule
from app.core.exceptions import ValidationException


class SupervisorSchedulingService:
    """
    Orchestrates schedule-related views for supervisors.

    Currently reuses SupervisorDashboardRepository for building 'TodaySchedule'.
    """

    def __init__(
        self,
        dashboard_repo: SupervisorDashboardRepository,
    ) -> None:
        self.dashboard_repo = dashboard_repo

    def get_today_schedule(
        self,
        db: Session,
        supervisor_id: UUID,
        hostel_id: UUID,
        schedule_date: date | None = None,
    ) -> TodaySchedule:
        """
        Get today's (or a specific date's) schedule for a supervisor.

        schedule_date is optional; if omitted, repository should default to today.
        """
        data = self.dashboard_repo.get_today_schedule(
            db=db,
            supervisor_id=supervisor_id,
            hostel_id=hostel_id,
            schedule_date=schedule_date,
        )
        if not data:
            # If no schedule entries, repository should return an empty dict;
            # only None indicates an invalid supervisor/hostel combination.
            raise ValidationException("No schedule data available")

        return TodaySchedule.model_validate(data)