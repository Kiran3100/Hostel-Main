# app/services/complaint/complaint_assignment_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import ComplaintRepository
from app.repositories.core import SupervisorRepository, UserRepository
from app.schemas.complaint import (
    AssignmentRequest,
    AssignmentResponse,
    ReassignmentRequest,
    BulkAssignment,
    UnassignRequest,
)
from app.schemas.common.enums import ComplaintStatus
from app.services.common import UnitOfWork, errors


class ComplaintAssignmentService:
    """
    Handle assigning / reassigning complaints to supervisors.

    This service updates:
    - complaint.assigned_to_id
    - complaint.status (e.g. ASSIGNED)
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_complaint_repo(self, uow: UnitOfWork) -> ComplaintRepository:
        return uow.get_repo(ComplaintRepository)

    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _complaint_number(self, complaint_id: UUID) -> str:
        return f"CMP-{str(complaint_id)[:8].upper()}"

    # ------------------------------------------------------------------ #
    # Assignment
    # ------------------------------------------------------------------ #
    def assign(self, data: AssignmentRequest, *, assigned_by_id: UUID) -> AssignmentResponse:
        with UnitOfWork(self._session_factory) as uow:
            complaint_repo = self._get_complaint_repo(uow)
            supervisor_repo = self._get_supervisor_repo(uow)
            user_repo = self._get_user_repo(uow)

            complaint = complaint_repo.get(data.complaint_id)
            if complaint is None:
                raise errors.NotFoundError(f"Complaint {data.complaint_id} not found")

            supervisor = supervisor_repo.get(data.assigned_to)
            if supervisor is None:
                raise errors.NotFoundError(f"Supervisor {data.assigned_to} not found")

            assigned_to_user = user_repo.get(supervisor.user_id)
            assigned_by_user = user_repo.get(assigned_by_id)

            complaint.assigned_to_id = data.assigned_to  # type: ignore[attr-defined]
            # Move status to ASSIGNED if currently OPEN
            if complaint.status == ComplaintStatus.OPEN:
                complaint.status = ComplaintStatus.ASSIGNED  # type: ignore[attr-defined]

            assigned_at = self._now()
            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            return AssignmentResponse(
                complaint_id=complaint.id,
                complaint_number=self._complaint_number(complaint.id),
                assigned_to=data.assigned_to,
                assigned_to_name=assigned_to_user.full_name if assigned_to_user else "",
                assigned_by=assigned_by_id,
                assigned_by_name=assigned_by_user.full_name if assigned_by_user else "",
                assigned_at=assigned_at,
                message="Complaint assigned successfully",
            )

    def reassign(self, data: ReassignmentRequest, *, reassigned_by_id: UUID) -> AssignmentResponse:
        """
        Reassign complaint to a different supervisor.
        """
        with UnitOfWork(self._session_factory) as uow:
            complaint_repo = self._get_complaint_repo(uow)
            supervisor_repo = self._get_supervisor_repo(uow)
            user_repo = self._get_user_repo(uow)

            complaint = complaint_repo.get(data.complaint_id)
            if complaint is None:
                raise errors.NotFoundError(f"Complaint {data.complaint_id} not found")

            supervisor = supervisor_repo.get(data.new_assigned_to)
            if supervisor is None:
                raise errors.NotFoundError(f"Supervisor {data.new_assigned_to} not found")

            assigned_to_user = user_repo.get(supervisor.user_id)
            reassigned_by_user = user_repo.get(reassigned_by_id)

            complaint.assigned_to_id = data.new_assigned_to  # type: ignore[attr-defined]
            if complaint.status in (ComplaintStatus.OPEN, ComplaintStatus.ASSIGNED):
                complaint.status = ComplaintStatus.ASSIGNED  # type: ignore[attr-defined]

            assigned_at = self._now()
            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            return AssignmentResponse(
                complaint_id=complaint.id,
                complaint_number=self._complaint_number(complaint.id),
                assigned_to=data.new_assigned_to,
                assigned_to_name=assigned_to_user.full_name if assigned_to_user else "",
                assigned_by=reassigned_by_id,
                assigned_by_name=reassigned_by_user.full_name if reassigned_by_user else "",
                assigned_at=assigned_at,
                message="Complaint reassigned successfully",
            )

    def bulk_assign(self, data: BulkAssignment, *, assigned_by_id: UUID) -> List[AssignmentResponse]:
        responses: List[AssignmentResponse] = []
        for cid in data.complaint_ids:
            req = AssignmentRequest(
                complaint_id=cid,
                assigned_to=data.assigned_to,
                estimated_resolution_time=None,
                assignment_notes=data.assignment_notes,
            )
            responses.append(self.assign(req, assigned_by_id=assigned_by_id))
        return responses

    def unassign(self, data: UnassignRequest, *, unassigned_by_id: UUID) -> None:
        with UnitOfWork(self._session_factory) as uow:
            complaint_repo = self._get_complaint_repo(uow)

            complaint = complaint_repo.get(data.complaint_id)
            if complaint is None:
                raise errors.NotFoundError(f"Complaint {data.complaint_id} not found")

            complaint.assigned_to_id = None  # type: ignore[attr-defined]
            # Optionally move back to OPEN
            complaint.status = ComplaintStatus.OPEN  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()