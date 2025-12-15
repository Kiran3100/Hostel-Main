# app/services/maintenance/maintenance_schedule_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol, List, Optional
from uuid import UUID

from app.schemas.maintenance import (
    PreventiveSchedule,
    ScheduleCreate,
    RecurrenceConfig,
    ScheduleExecution,
    ScheduleUpdate,
    ScheduleHistory,
    ExecutionHistoryItem,
)
from app.services.common import errors


class ScheduleStore(Protocol):
    """
    Store preventive maintenance schedules and their execution history.
    """

    def create_schedule(self, data: dict) -> dict: ...
    def update_schedule(self, schedule_id: UUID, data: dict) -> dict: ...
    def get_schedule(self, schedule_id: UUID) -> Optional[dict]: ...
    def list_schedules_for_hostel(self, hostel_id: UUID) -> List[dict]: ...
    def add_execution(self, schedule_id: UUID, execution: dict) -> None: ...
    def list_executions(self, schedule_id: UUID) -> List[dict]: ...


class MaintenanceScheduleService:
    """
    Manage preventive maintenance schedules (non-SQL storage via ScheduleStore).

    - Create/update schedules
    - Record executions
    - Produce schedule history
    """

    def __init__(self, store: ScheduleStore) -> None:
        self._store = store

    # ------------------------------------------------------------------ #
    # Scheduling
    # ------------------------------------------------------------------ #
    def create_schedule(self, data: ScheduleCreate, *, hostel_name: str) -> PreventiveSchedule:
        record = {
            "hostel_id": str(data.hostel_id),
            "hostel_name": hostel_name,
            "title": data.title,
            "description": data.description,
            "category": data.category.value if hasattr(data.category, "value") else str(data.category),
            "recurrence": data.recurrence.value if hasattr(data.recurrence, "value") else str(data.recurrence),
            "next_due_date": data.start_date.isoformat(),
            "assigned_to": str(data.assigned_to) if data.assigned_to else None,
            "assigned_to_name": None,
            "estimated_cost": str(data.estimated_cost) if data.estimated_cost is not None else None,
            "is_active": True,
            "last_completed_date": None,
        }
        created = self._store.create_schedule(record)
        return PreventiveSchedule(
            id=UUID(created["id"]),
            created_at=None,
            updated_at=None,
            hostel_id=data.hostel_id,
            hostel_name=hostel_name,
            title=data.title,
            description=data.description,
            category=data.category,
            recurrence=data.recurrence,
            next_due_date=data.start_date,
            assigned_to=data.assigned_to,
            assigned_to_name=None,
            estimated_cost=data.estimated_cost,
            is_active=True,
            last_completed_date=None,
        )

    def update_schedule(self, schedule_id: UUID, data: ScheduleUpdate) -> PreventiveSchedule:
        existing = self._store.get_schedule(schedule_id)
        if not existing:
            raise errors.NotFoundError(f"Preventive schedule {schedule_id} not found")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "recurrence" and value is not None:
                existing["recurrence"] = value.value if hasattr(value, "value") else str(value)
            elif field == "next_due_date" and value is not None:
                existing["next_due_date"] = value.isoformat()
            else:
                existing[field] = value

        updated = self._store.update_schedule(schedule_id, existing)
        return PreventiveSchedule(
            id=schedule_id,
            created_at=None,
            updated_at=None,
            hostel_id=UUID(updated["hostel_id"]),
            hostel_name=updated.get("hostel_name", ""),
            title=updated["title"],
            description=updated.get("description"),
            category=data.recurrence or updated["category"],
            recurrence=data.recurrence or updated["recurrence"],
            next_due_date=date.fromisoformat(updated["next_due_date"]),
            assigned_to=UUID(updated["assigned_to"]) if updated.get("assigned_to") else None,
            assigned_to_name=updated.get("assigned_to_name"),
            estimated_cost=Decimal(updated["estimated_cost"]) if updated.get("estimated_cost") else None,
            is_active=updated.get("is_active", True),
            last_completed_date=date.fromisoformat(updated["last_completed_date"]) if updated.get("last_completed_date") else None,
        )

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #
    def record_execution(self, data: ScheduleExecution, *, completed_by_name: Optional[str] = None) -> None:
        exec_record = {
            "execution_date": data.execution_date.isoformat(),
            "completed": data.completed,
            "actual_cost": str(data.actual_cost) if data.actual_cost is not None else None,
            "completion_notes": data.completion_notes,
            "completed_by": completed_by_name,
            "skip_next_occurrence": data.skip_next_occurrence,
            "reschedule_next_to": data.reschedule_next_to.isoformat() if data.reschedule_next_to else None,
        }
        self._store.add_execution(data.schedule_id, exec_record)

    def get_history(self, schedule_id: UUID, title: str) -> ScheduleHistory:
        executions = self._store.list_executions(schedule_id)
        items: List[ExecutionHistoryItem] = []
        completed_count = 0
        skipped_count = 0
        for ex in executions:
            completed = ex.get("completed", False)
            if completed:
                completed_count += 1
            if ex.get("skip_next_occurrence"):
                skipped_count += 1

            items.append(
                ExecutionHistoryItem(
                    execution_date=date.fromisoformat(ex["execution_date"]),
                    completed=completed,
                    actual_cost=Decimal(ex["actual_cost"]) if ex.get("actual_cost") else None,
                    completion_notes=ex.get("completion_notes"),
                    completed_by=None,
                    completed_by_name=ex.get("completed_by"),
                )
            )

        return ScheduleHistory(
            schedule_id=schedule_id,
            title=title,
            total_executions=len(executions),
            completed_executions=completed_count,
            skipped_executions=skipped_count,
            executions=items,
        )