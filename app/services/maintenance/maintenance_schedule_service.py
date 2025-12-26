"""
Maintenance Schedule Service

Manages preventive maintenance schedules:
- Create/update schedules
- Record executions
- Retrieve history
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceScheduleRepository
from app.schemas.maintenance import (
    PreventiveSchedule,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleExecution,
    ExecutionHistoryItem,
    ScheduleHistory,
)
from app.core.exceptions import ValidationException


class MaintenanceScheduleService:
    """
    High-level service for preventive maintenance schedules.
    """

    def __init__(self, schedule_repo: MaintenanceScheduleRepository) -> None:
        self.schedule_repo = schedule_repo

    # -------------------------------------------------------------------------
    # Schedules
    # -------------------------------------------------------------------------

    def create_schedule(
        self,
        db: Session,
        request: ScheduleCreate,
    ) -> PreventiveSchedule:
        obj = self.schedule_repo.create_schedule(
            db=db,
            data=request.model_dump(exclude_none=True),
        )
        return PreventiveSchedule.model_validate(obj)

    def update_schedule(
        self,
        db: Session,
        schedule_id: UUID,
        request: ScheduleUpdate,
    ) -> PreventiveSchedule:
        schedule = self.schedule_repo.get_by_id(db, schedule_id)
        if not schedule:
            raise ValidationException("Schedule not found")

        updated = self.schedule_repo.update_schedule(
            db=db,
            schedule=schedule,
            data=request.model_dump(exclude_none=True),
        )
        return PreventiveSchedule.model_validate(updated)

    def get_schedule(
        self,
        db: Session,
        schedule_id: UUID,
    ) -> PreventiveSchedule:
        schedule = self.schedule_repo.get_by_id(db, schedule_id)
        if not schedule:
            raise ValidationException("Schedule not found")
        return PreventiveSchedule.model_validate(schedule)

    def list_schedules_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[PreventiveSchedule]:
        objs = self.schedule_repo.get_by_hostel_id(db, hostel_id)
        return [PreventiveSchedule.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Executions & history
    # -------------------------------------------------------------------------

    def record_execution(
        self,
        db: Session,
        request: ScheduleExecution,
    ) -> ExecutionHistoryItem:
        payload = request.model_dump(exclude_none=True)
        obj = self.schedule_repo.record_execution(db, payload)
        return ExecutionHistoryItem.model_validate(obj)

    def get_history_for_schedule(
        self,
        db: Session,
        schedule_id: UUID,
    ) -> ScheduleHistory:
        data = self.schedule_repo.get_history_for_schedule(db, schedule_id)
        if not data:
            return ScheduleHistory(
                schedule_id=schedule_id,
                executions=[],
                total_executions=0,
                average_completion_time_hours=None,
                on_time_rate=None,
            )
        return ScheduleHistory.model_validate(data)