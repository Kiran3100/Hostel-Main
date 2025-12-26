# app/services/mess/menu_approval_service.py
"""
Menu Approval Service

Handles menu approval workflows:
- Submit for approval
- Approve/reject
- Track approval history & workflows
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.mess import MenuApprovalRepository
from app.schemas.mess import (
    MenuApprovalRequest,
    MenuApprovalResponse,
    ApprovalWorkflow,
    ApprovalHistory,
    BulkApproval,
)
from app.core.exceptions import ValidationException, BusinessLogicException


class MenuApprovalService:
    """
    High-level service for menu approvals.
    """

    def __init__(self, approval_repo: MenuApprovalRepository) -> None:
        self.approval_repo = approval_repo

    # -------------------------------------------------------------------------
    # Submissions
    # -------------------------------------------------------------------------

    def submit_for_approval(
        self,
        db: Session,
        menu_id: UUID,
        request: MenuApprovalRequest,
        requested_by: UUID,
    ) -> MenuApprovalResponse:
        payload = request.model_dump(exclude_none=True)
        payload.update({"menu_id": menu_id, "requested_by": requested_by})

        obj = self.approval_repo.submit_for_approval(db, payload)
        return MenuApprovalResponse.model_validate(obj)

    # -------------------------------------------------------------------------
    # Approve / reject
    # -------------------------------------------------------------------------

    def approve_menu(
        self,
        db: Session,
        menu_id: UUID,
        approver_id: UUID,
        notes: str | None = None,
    ) -> MenuApprovalResponse:
        approval = self.approval_repo.get_current_approval_for_menu(db, menu_id)
        if not approval:
            raise ValidationException("No approval pending for this menu")

        obj = self.approval_repo.approve(
            db,
            approval=approval,
            approver_id=approver_id,
            notes=notes,
        )
        return MenuApprovalResponse.model_validate(obj)

    def reject_menu(
        self,
        db: Session,
        menu_id: UUID,
        approver_id: UUID,
        reason: str,
    ) -> MenuApprovalResponse:
        approval = self.approval_repo.get_current_approval_for_menu(db, menu_id)
        if not approval:
            raise ValidationException("No approval pending for this menu")

        obj = self.approval_repo.reject(
            db,
            approval=approval,
            approver_id=approver_id,
            reason=reason,
        )
        return MenuApprovalResponse.model_validate(obj)

    def bulk_approve(
        self,
        db: Session,
        request: BulkApproval,
        approver_id: UUID,
    ) -> List[MenuApprovalResponse]:
        responses: List[MenuApprovalResponse] = []

        for menu_id in request.menu_ids:
            try:
                resp = self.approve_menu(db, menu_id, approver_id, request.notes)
                responses.append(resp)
            except (ValidationException, BusinessLogicException):
                if not request.skip_failed:
                    raise

        return responses

    # -------------------------------------------------------------------------
    # Workflow & history
    # -------------------------------------------------------------------------

    def get_workflow_for_menu(
        self,
        db: Session,
        menu_id: UUID,
    ) -> ApprovalWorkflow:
        data = self.approval_repo.get_workflow_for_menu(db, menu_id)
        if not data:
            raise ValidationException("Approval workflow not found")
        return ApprovalWorkflow.model_validate(data)

    def get_approval_history_for_menu(
        self,
        db: Session,
        menu_id: UUID,
    ) -> List[ApprovalHistory]:
        objs = self.approval_repo.get_history_for_menu(db, menu_id)
        return [ApprovalHistory.model_validate(o) for o in objs]