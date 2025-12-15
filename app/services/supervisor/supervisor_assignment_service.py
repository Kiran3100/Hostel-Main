# app/services/supervisor/supervisor_assignment_service.py
from __future__ import annotations

from datetime import date
from typing import Callable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import SupervisorRepository, UserRepository, HostelRepository
from app.repositories.associations import SupervisorHostelRepository
from app.schemas.supervisor import (
    SupervisorAssignment,
    AssignmentRequest,
    AssignmentUpdate,
    RevokeAssignmentRequest,
)
from app.schemas.common.enums import EmploymentType, SupervisorStatus
from app.services.common import UnitOfWork, errors


class SupervisorAssignmentService:
    """
    Supervisor ↔ hostel assignments (multi-hostel):

    - Assign supervisor (user) to a hostel (creates core_supervisor if needed).
    - Update assignment metadata.
    - Revoke assignment.
    - List assignments for a supervisor or hostel (simple).
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # Helpers
    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_assoc_repo(self, uow: UnitOfWork) -> SupervisorHostelRepository:
        return uow.get_repo(SupervisorHostelRepository)

    # Mapping
    def _build_assignment(
        self,
        assoc,
        *,
        supervisor_name: str,
        hostel_name: str,
        assigned_by: UUID,
        assigned_by_name: str,
    ) -> SupervisorAssignment:
        return SupervisorAssignment(
            id=assoc.id,
            created_at=assoc.created_at,
            updated_at=assoc.updated_at,
            supervisor_id=assoc.supervisor_id,
            supervisor_name=supervisor_name,
            hostel_id=assoc.hostel_id,
            hostel_name=hostel_name,
            assigned_by=assigned_by,
            assigned_by_name=assigned_by_name,
            assigned_date=assoc.join_date,
            is_active=assoc.is_active,
            permission_level="standard",
            last_active=None,
        )

    # Assignment
    def assign_supervisor(
        self,
        data: AssignmentRequest,
        *,
        assigned_by: UUID,
    ) -> SupervisorAssignment:
        with UnitOfWork(self._session_factory) as uow:
            sup_repo = self._get_supervisor_repo(uow)
            user_repo = self._get_user_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            assoc_repo = self._get_assoc_repo(uow)

            user = user_repo.get(data.user_id)
            if user is None:
                raise errors.NotFoundError(f"User {data.user_id} not found")

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            # Ensure a core_supervisor exists for this user
            sup_list = sup_repo.get_multi(filters={"user_id": data.user_id})
            if sup_list:
                supervisor = sup_list[0]
            else:
                supervisor = sup_repo.create(
                    {
                        "user_id": data.user_id,
                        "hostel_id": data.hostel_id,
                        "employee_id": data.employee_id,
                        "join_date": data.join_date,
                        "employment_type": EmploymentType.FULL_TIME,
                        "shift_timing": data.shift_timing,
                        "status": SupervisorStatus.ACTIVE,
                        "is_active": True,
                        "permissions": data.permissions or {},
                    }
                )

            # Prevent duplicate assignment
            existing = assoc_repo.get_multi(
                skip=0,
                limit=1,
                filters={"supervisor_id": supervisor.id, "hostel_id": data.hostel_id},
            )
            if existing:
                raise errors.ConflictError("Supervisor already assigned to this hostel")

            assoc = assoc_repo.create(
                {
                    "supervisor_id": supervisor.id,
                    "hostel_id": data.hostel_id,
                    "employee_id": data.employee_id,
                    "join_date": data.join_date,
                    "employment_type": data.employment_type,
                    "shift_timing": data.shift_timing,
                    "is_active": True,
                    "permissions": data.permissions or {},
                }
            )

            assigned_by_user = user_repo.get(assigned_by)
            assigned_by_name = assigned_by_user.full_name if assigned_by_user else ""

            uow.commit()
            return self._build_assignment(
                assoc,
                supervisor_name=user.full_name,
                hostel_name=hostel.name,
                assigned_by=assigned_by,
                assigned_by_name=assigned_by_name,
            )

    def update_assignment(self, assignment_id: UUID, data: AssignmentUpdate) -> SupervisorAssignment:
        with UnitOfWork(self._session_factory) as uow:
            assoc_repo = self._get_assoc_repo(uow)
            user_repo = self._get_user_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            assoc = assoc_repo.get(assignment_id)
            if assoc is None:
                raise errors.NotFoundError(f"SupervisorHostel {assignment_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(assoc, field) and field != "id":
                    setattr(assoc, field, value)

            uow.session.flush()  # type: ignore[union-attr]

            sup_user = user_repo.get(assoc.supervisor_id)
            supervisor_name = sup_user.full_name if sup_user else ""
            hostel = hostel_repo.get(assoc.hostel_id)
            hostel_name = hostel.name if hostel else ""

            uow.commit()
            return self._build_assignment(
                assoc,
                supervisor_name=supervisor_name,
                hostel_name=hostel_name,
                assigned_by=UUID(int=0),
                assigned_by_name="",
            )

    def revoke_assignment(
        self,
        data: RevokeAssignmentRequest,
        *,
        revoked_by: UUID,
    ) -> None:
        """
        Mark supervisor-hostel association as inactive.
        """
        with UnitOfWork(self._session_factory) as uow:
            assoc_repo = self._get_assoc_repo(uow)

            # Find associations for this supervisor (all hostels)
            assocs = assoc_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"supervisor_id": data.supervisor_id},
            )
            if not assocs:
                raise errors.NotFoundError(f"No assignments found for supervisor {data.supervisor_id}")

            for a in assocs:
                a.is_active = False  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

    def list_assignments_for_supervisor(self, supervisor_id: UUID) -> List[SupervisorAssignment]:
        with UnitOfWork(self._session_factory) as uow:
            assoc_repo = self._get_assoc_repo(uow)
            user_repo = self._get_user_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            assocs = assoc_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"supervisor_id": supervisor_id},
            )

            sup_user = user_repo.get(supervisor_id)
            supervisor_name = sup_user.full_name if sup_user else ""

            results: List[SupervisorAssignment] = []
            for a in assocs:
                hostel = hostel_repo.get(a.hostel_id)
                hostel_name = hostel.name if hostel else ""
                results.append(
                    self._build_assignment(
                        a,
                        supervisor_name=supervisor_name,
                        hostel_name=hostel_name,
                        assigned_by=UUID(int=0),
                        assigned_by_name="",
                    )
                )
            return results