# app/services/maintenance/maintenance_assignment_service.py
from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Callable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import MaintenanceRepository
from app.repositories.core import SupervisorRepository, UserRepository
from app.schemas.maintenance import (
    TaskAssignment,
    AssignmentUpdate,
    BulkAssignment,
)
from app.services.common import UnitOfWork, errors


class MaintenanceAssignmentService:
    """
    Assign/reassign maintenance tasks to supervisors/staff.

    This service updates:
    - maintenance.assigned_to_id
    - optionally status/transitions (e.g., ASSIGNED)
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_maintenance_repo(self, uow: UnitOfWork) -> MaintenanceRepository:
        return uow.get_repo(MaintenanceRepository)

    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _request_number(self, maintenance_id: UUID) -> str:
        return f"MTN-{str(maintenance_id)[:8].upper()}"

    # ------------------------------------------------------------------ #
    # Assignment
    # ------------------------------------------------------------------ #
    def assign(
        self,
        maintenance_id: UUID,
        assigned_to_id: UUID,
        *,
        assigned_by_id: UUID,
        deadline: Optional[date] = None,
        instructions: Optional[str] = None,
    ) -> TaskAssignment:
        with UnitOfWork(self._session_factory) as uow:
            maint_repo = self._get_maintenance_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)
            user_repo = self._get_user_repo(uow)

            m = maint_repo.get(maintenance_id)
            if m is None:
                raise errors.NotFoundError(f"Maintenance {maintenance_id} not found")

            supervisor = sup_repo.get(assigned_to_id)
            if supervisor is None:
                raise errors.NotFoundError(f"Supervisor {assigned_to_id} not found")

            assigned_to_user = user_repo.get(supervisor.user_id)
            assigned_by_user = user_repo.get(assigned_by_id)

            m.assigned_to_id = assigned_to_id  # type: ignore[attr-defined]

            assigned_at = self._now()
            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            return TaskAssignment(
                id=None,
                created_at=assigned_at,
                updated_at=assigned_at,
                maintenance_id=m.id,
                request_number=self._request_number(m.id),
                assigned_to=assigned_to_id,
                assigned_to_name=assigned_to_user.full_name if assigned_to_user else "",
                assigned_by=assigned_by_id,
                assigned_by_name=assigned_by_user.full_name if assigned_by_user else "",
                assigned_at=assigned_at,
                deadline=deadline,
                instructions=instructions,
            )

    def update_assignment(self, data: AssignmentUpdate, *, updated_by_id: UUID) -> None:
        """
        Basic reassignment/deadline change, without changing status.
        This demonstrates how you can extend for more complex logic.
        """
        with UnitOfWork(self._session_factory) as uow:
            maint_repo = self._get_maintenance_repo(uow)
            m = maint_repo.get(data.maintenance_id)
            if m is None:
                raise errors.NotFoundError(f"Maintenance {data.maintenance_id} not found")

            if data.new_assigned_to:
                m.assigned_to_id = data.new_assigned_to  # type: ignore[attr-defined]

            # The rest of fields (new_deadline, additional_instructions) would be
            # stored in a separate assignment-history structure; not present in
            # the current Maintenance model, so skipped here.

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

    def bulk_assign(self, data: BulkAssignment, *, assigned_by_id: UUID) -> List[TaskAssignment]:
        responses: List[TaskAssignment] = []
        for maintenance_id in data.maintenance_ids:
            resp = self.assign(
                maintenance_id=maintenance_id,
                assigned_to_id=data.assigned_to,
                assigned_by_id=assigned_by_id,
                deadline=data.common_deadline,
                instructions=data.instructions,
            )
            responses.append(resp)
        return responses