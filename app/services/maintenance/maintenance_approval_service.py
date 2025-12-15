# app/services/maintenance/maintenance_approval_service.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol, Optional, Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import MaintenanceRepository
from app.schemas.maintenance import (
    ApprovalRequest,
    ApprovalResponse,
    ThresholdConfig,
    ApprovalWorkflow,
    RejectionRequest,
)
from app.services.common import UnitOfWork, errors


class ThresholdStore(Protocol):
    """
    Store for hostel-specific cost approval thresholds.
    Back it with Redis or a DB table.
    """

    def get_threshold(self, hostel_id: UUID) -> Optional[dict]: ...
    def save_threshold(self, hostel_id: UUID, data: dict) -> None: ...


class ApprovalStore(Protocol):
    """
    Store for pending/processed approval requests.

    Simplified: keyed by maintenance_id.
    """

    def get_workflow(self, maintenance_id: UUID) -> Optional[dict]: ...
    def save_workflow(self, maintenance_id: UUID, data: dict) -> None: ...


class MaintenanceApprovalService:
    """
    High-level cost approval service:

    - Maintain ThresholdConfig per hostel.
    - Process supervisor-initiated ApprovalRequest.
    - Mark Maintenance cost_approved / approval_threshold_exceeded.

    This service assumes:
    - Estimated cost is stored in Maintenance.estimated_cost.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        threshold_store: ThresholdStore,
        approval_store: ApprovalStore,
    ) -> None:
        self._session_factory = session_factory
        self._threshold_store = threshold_store
        self._approval_store = approval_store

    def _get_repo(self, uow: UnitOfWork) -> MaintenanceRepository:
        return uow.get_repo(MaintenanceRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Threshold configuration
    # ------------------------------------------------------------------ #
    def get_threshold_config(self, hostel_id: UUID) -> ThresholdConfig:
        record = self._threshold_store.get_threshold(hostel_id)
        if record:
            return ThresholdConfig.model_validate(record)
        # Default configuration if none stored
        default = ThresholdConfig(hostel_id=hostel_id)
        self._threshold_store.save_threshold(hostel_id, default.model_dump())
        return default

    def set_threshold_config(self, config: ThresholdConfig) -> None:
        self._threshold_store.save_threshold(config.hostel_id, config.model_dump())

    # ------------------------------------------------------------------ #
    # Approval flow
    # ------------------------------------------------------------------ #
    def request_approval(self, data: ApprovalRequest, *, requested_by_id: UUID) -> ApprovalWorkflow:
        """
        Supervisor requests approval for maintenance cost.

        We simply record the request in ApprovalStore; actual decision is
        handled by approve()/reject().
        """
        now = self._now()
        record = {
            "maintenance_id": str(data.maintenance_id),
            "estimated_cost": str(data.estimated_cost),
            "cost_breakdown": data.cost_breakdown or {},
            "approval_reason": data.approval_reason,
            "urgent": data.urgent,
            "preferred_vendor": data.preferred_vendor,
            "vendor_quote": data.vendor_quote,
            "requested_by_id": str(requested_by_id),
            "status": "pending",
            "submitted_for_approval_at": now,
            "approved_at": None,
            "rejected_at": None,
            "approved_by_id": None,
            "rejection_reason": None,
        }
        self._approval_store.save_workflow(data.maintenance_id, record)

        # Evaluate threshold for this maintenance
        with UnitOfWork(self._session_factory) as uow:
            maint_repo = self._get_repo(uow)
            m = maint_repo.get(data.maintenance_id)
            if m is None:
                raise errors.NotFoundError(f"Maintenance {data.maintenance_id} not found")

            config = self.get_threshold_config(m.hostel_id)
            threshold_exceeded = data.estimated_cost > config.admin_approval_required_above

        return ApprovalWorkflow(
            maintenance_id=data.maintenance_id,
            request_number=f"MTN-{str(data.maintenance_id)[:8].upper()}",
            estimated_cost=data.estimated_cost,
            threshold_exceeded=threshold_exceeded,
            requires_approval=True,
            approval_pending=True,
            pending_with=None,
            pending_with_name=None,
            submitted_for_approval_at=record["submitted_for_approval_at"],
            approval_deadline=None,
        )

    def approve(
        self,
        maintenance_id: UUID,
        *,
        approved_by_id: UUID,
        approved_by_name: str,
        approved_amount: Decimal,
        approval_conditions: Optional[str] = None,
    ) -> ApprovalResponse:
        now = self._now()
        workflow = self._approval_store.get_workflow(maintenance_id)
        if not workflow:
            # Create a basic workflow record if missing
            workflow = {
                "maintenance_id": str(maintenance_id),
                "status": "pending",
                "submitted_for_approval_at": now,
            }

        workflow["status"] = "approved"
        workflow["approved_by_id"] = str(approved_by_id)
        workflow["approved_at"] = now
        workflow["rejection_reason"] = None
        self._approval_store.save_workflow(maintenance_id, workflow)

        with UnitOfWork(self._session_factory) as uow:
            maint_repo = self._get_repo(uow)
            m = maint_repo.get(maintenance_id)
            if m is None:
                raise errors.NotFoundError(f"Maintenance {maintenance_id} not found")

            config = self.get_threshold_config(m.hostel_id)
            threshold_exceeded = approved_amount > config.admin_approval_required_above

            # Mark approval flags and adjust estimated_cost
            m.estimated_cost = approved_amount  # type: ignore[attr-defined]
            m.cost_approved = True  # type: ignore[attr-defined]
            m.approval_threshold_exceeded = threshold_exceeded  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return ApprovalResponse(
            maintenance_id=maintenance_id,
            request_number=f"MTN-{str(maintenance_id)[:8].upper()}",
            approved=True,
            approved_by=approved_by_id,
            approved_by_name=approved_by_name,
            approved_at=now,
            approved_amount=approved_amount,
            approval_conditions=approval_conditions,
            message="Maintenance cost approved",
        )

    def reject(
        self,
        data: RejectionRequest,
        *,
        rejected_by_id: UUID,
        rejected_by_name: str,
    ) -> ApprovalResponse:
        now = self._now()
        workflow = self._approval_store.get_workflow(data.maintenance_id)
        if not workflow:
            workflow = {
                "maintenance_id": str(data.maintenance_id),
                "submitted_for_approval_at": now,
            }

        workflow["status"] = "rejected"
        workflow["approved_by_id"] = None
        workflow["approved_at"] = None
        workflow["rejection_reason"] = data.rejection_reason
        workflow["rejected_at"] = now
        self._approval_store.save_workflow(data.maintenance_id, workflow)

        # Do not change Maintenance.cost_approved for rejection; caller may
        # set status separately.

        return ApprovalResponse(
            maintenance_id=data.maintenance_id,
            request_number=f"MTN-{str(data.maintenance_id)[:8].upper()}",
            approved=False,
            approved_by=rejected_by_id,
            approved_by_name=rejected_by_name,
            approved_at=now,
            approved_amount=Decimal("0"),
            approval_conditions=None,
            message="Maintenance approval rejected",
        )