# app/services/reporting/report_scheduling_service.py
"""
Report Scheduling Service

Manages scheduled execution of custom reports.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.analytics import (
    ReportSchedule,
    ReportExecutionHistory,
)
from app.repositories.analytics import CustomReportsRepository
from app.core.exceptions import ValidationException


class ReportSchedulingService:
    """
    High-level service for scheduling & executing custom reports.

    Responsibilities:
    - Create/update/delete schedules
    - List schedules
    - Process due schedules (for cron/worker)
    """

    def __init__(self, custom_reports_repo: CustomReportsRepository) -> None:
        self.custom_reports_repo = custom_reports_repo

    # -------------------------------------------------------------------------
    # Scheduling CRUD
    # -------------------------------------------------------------------------

    def create_schedule(
        self,
        db: Session,
        definition_id: UUID,
        schedule: ReportSchedule,
        owner_id: UUID,
    ) -> ReportSchedule:
        payload = schedule.model_dump(exclude_none=True)
        payload.update(
            {
                "definition_id": definition_id,
                "owner_id": owner_id,
            }
        )
        obj = self.custom_reports_repo.create_schedule(db, payload)
        return ReportSchedule.model_validate(obj)

    def update_schedule(
        self,
        db: Session,
        schedule_id: UUID,
        schedule: ReportSchedule,
    ) -> ReportSchedule:
        existing = self.custom_reports_repo.get_schedule_by_id(db, schedule_id)
        if not existing:
            raise ValidationException("Schedule not found")

        updated = self.custom_reports_repo.update_schedule(
            db, existing, schedule.model_dump(exclude_none=True)
        )
        return ReportSchedule.model_validate(updated)

    def delete_schedule(
        self,
        db: Session,
        schedule_id: UUID,
    ) -> None:
        existing = self.custom_reports_repo.get_schedule_by_id(db, schedule_id)
        if not existing:
            return
        self.custom_reports_repo.delete_schedule(db, existing)

    def list_schedules_for_definition(
        self,
        db: Session,
        definition_id: UUID,
    ) -> List[ReportSchedule]:
        objs = self.custom_reports_repo.get_schedules_for_definition(db, definition_id)
        return [ReportSchedule.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    def run_due_schedules(
        self,
        db: Session,
        now: Optional[datetime] = None,
    ) -> List[ReportExecutionHistory]:
        """
        Execute all schedules that are due as of `now`.

        Returns the created execution history records.
        """
        now = now or datetime.utcnow()

        due_schedules = self.custom_reports_repo.get_due_schedules(db, now)
        histories: List[ReportExecutionHistory] = []

        for schedule in due_schedules:
            history_obj = self.custom_reports_repo.execute_scheduled_report(
                db=db,
                schedule=schedule,
                run_at=now,
            )
            histories.append(ReportExecutionHistory.model_validate(history_obj))

            # Update schedule with last_run time and next_run time
            self.custom_reports_repo.update_next_run(db, schedule, now)

        return histories