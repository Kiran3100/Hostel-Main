# app/services/leave/leave_approval_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import LeaveApplicationRepository
from app.repositories.core import SupervisorRepository
from app.schemas.common.enums import LeaveStatus
from app.schemas.leave import (
    LeaveApprovalRequest,
    LeaveApprovalResponse,
)
from app.services.common import UnitOfWork, errors


class LeaveApprovalService:
    """
    Approval / rejection of leave applications by supervisor/admin.

    - Approve or reject using LeaveApprovalRequest
    - Update LeaveApplication.status, approved_by_id/rejected_by_id, rejection_reason
    - Return LeaveApprovalResponse
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_leave_repo(self, uow: UnitOfWork) -> LeaveApplicationRepository:
        return uow.get_repo(LeaveApplicationRepository)

    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Approval / rejection
    # ------------------------------------------------------------------ #
    def process_approval(
        self,
        data: LeaveApprovalRequest,
    ) -> LeaveApprovalResponse:
        """
        Process leave approval or rejection.

        Business rules:
        - Only PENDING requests should be processed.
        """
        now = self._now()

        with UnitOfWork(self._session_factory) as uow:
            leave_repo = self._get_leave_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)

            leave = leave_repo.get(data.leave_id)
            if leave is None:
                raise errors.NotFoundError(f"Leave {data.leave_id} not found")

            if leave.status != LeaveStatus.PENDING:
                raise errors.ValidationError(
                    f"Leave {data.leave_id} is not in PENDING state"
                )

            supervisor = sup_repo.get(data.approver_id)
            if supervisor is None:
                raise errors.NotFoundError(
                    f"Supervisor {data.approver_id} not found"
                )

            approver_name = (
                supervisor.user.full_name
                if getattr(supervisor, "user", None)
                else None
            )

            approved_by: Optional[UUID] = None
            approved_by_name: Optional[str] = None
            approved_at: Optional[datetime] = None

            rejected_by: Optional[UUID] = None
            rejected_by_name: Optional[str] = None
            rejected_at: Optional[datetime] = None

            if data.approve:
                # Approve
                leave.status = LeaveStatus.APPROVED  # type: ignore[attr-defined]
                leave.approved_by_id = data.approver_id  # type: ignore[attr-defined]
                leave.rejection_reason = None  # type: ignore[attr-defined]

                approved_by = data.approver_id
                approved_by_name = approver_name
                approved_at = now
            else:
                # Reject
                leave.status = LeaveStatus.REJECTED  # type: ignore[attr-defined]
                leave.rejected_by_id = data.approver_id  # type: ignore[attr-defined]
                leave.rejection_reason = data.rejection_reason  # type: ignore[attr-defined]

                rejected_by = data.approver_id
                rejected_by_name = approver_name
                rejected_at = now

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        msg = "Leave approved successfully" if data.approve else "Leave rejected successfully"

        return LeaveApprovalResponse(
            leave_id=data.leave_id,
            status=leave.status,
            approved_by=approved_by,
            approved_by_name=approved_by_name,
            approved_at=approved_at,
            rejected_by=rejected_by,
            rejected_by_name=rejected_by_name,
            rejected_at=rejected_at,
            message=msg,
        )