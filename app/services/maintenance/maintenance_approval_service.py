"""
Maintenance Approval Service

Wrapper around approval workflow for maintenance requests:
- Submit for approval (already handled at request submission)
- Approve/reject maintenance approvals
- Retrieve approval workflow and thresholds
"""

from __future__ import annotations

from uuid import UUID
from typing import List

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceApprovalRepository
from app.schemas.maintenance import (
    ApprovalRequest,
    ApprovalResponse,
    ThresholdConfig,
    ApprovalWorkflow,
    RejectionRequest,
)
from app.core.exceptions import ValidationException
from app.services.workflows import ApprovalWorkflowService


class MaintenanceApprovalService:
    """
    High-level orchestration for maintenance approvals.

    Uses:
    - MaintenanceApprovalRepository for read-side / admin management
    - ApprovalWorkflowService for actual multi-step approval workflow
    """

    def __init__(
        self,
        approval_repo: MaintenanceApprovalRepository,
        approval_workflow: ApprovalWorkflowService,
    ) -> None:
        self.approval_repo = approval_repo
        self.approval_workflow = approval_workflow

    # -------------------------------------------------------------------------
    # Approvals
    # -------------------------------------------------------------------------

    async def approve_maintenance_request(
        self,
        db: Session,
        approval_id: UUID,
        approved_by: UUID,
        approved_amount: float | None = None,
        notes: str | None = None,
    ) -> ApprovalResponse:
        """
        Approve a maintenance approval record via workflow.
        """
        result = await self.approval_workflow.approve_maintenance(
            db=db,
            approval_id=approval_id,
            approved_by=approved_by,
            approved_amount=approved_amount,
            notes=notes,
        )
        return ApprovalResponse.model_validate(result or {})

    async def reject_maintenance_request(
        self,
        db: Session,
        approval_id: UUID,
        rejected_by: UUID,
        reason: str,
    ) -> ApprovalResponse:
        """
        Reject a maintenance approval (fast path using repository).
        """
        approval = self.approval_repo.get_by_id(db, approval_id)
        if not approval:
            raise ValidationException("Approval record not found")

        updated = self.approval_repo.reject(
            db=db,
            approval=approval,
            rejected_by=rejected_by,
            reason=reason,
        )
        return ApprovalResponse.model_validate(updated)

    # -------------------------------------------------------------------------
    # Thresholds & workflows
    # -------------------------------------------------------------------------

    def get_threshold_config_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> ThresholdConfig:
        cfg = self.approval_repo.get_threshold_config_for_hostel(db, hostel_id)
        if not cfg:
            # Provide empty config with defaults
            return ThresholdConfig(
                hostel_id=hostel_id,
                approval_required_above_amount=0.0,
                manager_approval_above_amount=None,
                senior_manager_approval_above_amount=None,
                auto_approve_below_amount=None,
            )
        return ThresholdConfig.model_validate(cfg)

    def get_workflow_for_request(
        self,
        db: Session,
        request_id: UUID,
    ) -> ApprovalWorkflow:
        data = self.approval_repo.get_workflow_for_request(db, request_id)
        if not data:
            raise ValidationException("Approval workflow not found")
        return ApprovalWorkflow.model_validate(data)