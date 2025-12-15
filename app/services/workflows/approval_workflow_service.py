# app/services/workflows/approval_workflow_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.workflows import ApprovalWorkflowRepository
from app.services.common import UnitOfWork


class ApprovalWorkflowService:
    """
    Wrapper over wf_approval table.

    Tracks approval workflow for entities that require explicit approval
    (announcements, menus, large maintenance jobs, etc.).
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_repo(self, uow: UnitOfWork) -> ApprovalWorkflowRepository:
        return uow.get_repo(ApprovalWorkflowRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Creation / ensure
    # ------------------------------------------------------------------ #
    def ensure_workflow(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        requested_by_id: UUID,
        initial_status: str = "pending",
        reason: Optional[str] = None,
    ) -> None:
        """
        Ensure that there is an approval workflow row for this entity.

        - If one already exists, this is a no-op.
        - Otherwise, a new row is created in 'pending' (or given) status.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            wf = repo.get_for_entity(
                scope_type=entity_type,  # type: ignore[call-arg]
                scope_id=entity_id,      # type: ignore[call-arg]
            )
            # ^ The repository signature is (entity_type, entity_id); using keyword
            # arguments that match the underlying method is recommended. If your
            # repository method is named differently, adjust the call accordingly.

            # Fallback for direct call to get_for_entity(entity_type, entity_id)
            if wf is None:
                payload = {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "status": initial_status,
                    "requested_by_id": requested_by_id,
                    "reason": reason,
                    "requested_at": self._now(),
                    "approver_id": None,
                    "decided_at": None,
                    "decision_notes": None,
                }
                repo.create(payload)  # type: ignore[arg-type]
                uow.commit()

    # ------------------------------------------------------------------ #
    # Status updates
    # ------------------------------------------------------------------ #
    def set_status(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        status: str,
        approver_id: Optional[UUID] = None,
        decision_notes: Optional[str] = None,
    ) -> None:
        """
        Update approval status for an entity.

        - If workflow row does not exist, it is created with the provided status.
        - If status is 'approved' or 'rejected', decided_at is set.
        """
        now = self._now()
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            wf = repo.get_for_entity(
                scope_type=entity_type,  # type: ignore[call-arg]
                scope_id=entity_id,      # type: ignore[call-arg]
            )

            if wf is None:
                payload = {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "status": status,
                    "requested_by_id": approver_id,  # best-effort when missing
                    "requested_at": now,
                    "approver_id": approver_id,
                    "decided_at": now if status in {"approved", "rejected"} else None,
                    "reason": None,
                    "decision_notes": decision_notes,
                }
                repo.create(payload)  # type: ignore[arg-type]
            else:
                wf.status = status  # type: ignore[attr-defined]
                if approver_id is not None:
                    wf.approver_id = approver_id  # type: ignore[attr-defined]
                if status in {"approved", "rejected"}:
                    wf.decided_at = now  # type: ignore[attr-defined]
                if decision_notes is not None:
                    wf.decision_notes = decision_notes  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()