# app/services/maintenance/maintenance_completion_service.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol, List, Optional, Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import MaintenanceRepository
from app.schemas.maintenance import (
    CompletionRequest,
    CompletionResponse,
    QualityCheck,
    CompletionCertificate,
    MaterialItem,
    ChecklistItem,
)
from app.services.common import UnitOfWork, errors


class CompletionStore(Protocol):
    """
    Store for completion details (materials, labor, quality checks, certificates).
    Maintenance model itself does not contain these extended fields.
    """

    def save_completion(self, maintenance_id: UUID, data: dict) -> None: ...
    def get_completion(self, maintenance_id: UUID) -> Optional[dict]: ...


class MaintenanceCompletionService:
    """
    Mark maintenance as completed and record completion details & quality checks.

    This service:
    - Updates Maintenance.actual_cost, completed_at, actual_completion_date.
    - Stores extended details in a CompletionStore.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        store: CompletionStore,
    ) -> None:
        self._session_factory = session_factory
        self._store = store

    def _get_repo(self, uow: UnitOfWork) -> MaintenanceRepository:
        return uow.get_repo(MaintenanceRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _request_number(self, maintenance_id: UUID) -> str:
        return f"MTN-{str(maintenance_id)[:8].upper()}"

    # ------------------------------------------------------------------ #
    # Completion
    # ------------------------------------------------------------------ #
    def complete(
        self,
        data: CompletionRequest,
        *,
        completed_by_id: UUID,
        completed_by_name: str,
    ) -> CompletionResponse:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            m = repo.get(data.maintenance_id)
            if m is None:
                raise errors.NotFoundError(f"Maintenance {data.maintenance_id} not found")

            m.actual_cost = data.actual_cost  # type: ignore[attr-defined]
            m.actual_completion_date = data.actual_completion_date  # type: ignore[attr-defined]
            completed_at = self._now()
            m.completed_at = completed_at  # type: ignore[attr-defined]
            # Status update is usually done via MaintenanceService.update_status

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        # Save extended completion metadata
        record = {
            "work_notes": data.work_notes,
            "materials_used": [mi.model_dump() for mi in data.materials_used],
            "labor_hours": str(data.labor_hours),
            "cost_breakdown": data.cost_breakdown or {},
            "completion_photos": [str(p) for p in data.completion_photos],
            "follow_up_required": data.follow_up_required,
            "follow_up_notes": data.follow_up_notes,
        }
        self._store.save_completion(data.maintenance_id, record)

        estimated_cost = m.estimated_cost or Decimal("0")  # type: ignore[name-defined]
        cost_variance = data.actual_cost - estimated_cost
        within_budget = cost_variance <= 0

        return CompletionResponse(
            maintenance_id=data.maintenance_id,
            request_number=self._request_number(data.maintenance_id),
            completed=True,
            completed_at=completed_at,
            completed_by=completed_by_id,
            completed_by_name=completed_by_name,
            estimated_cost=estimated_cost,
            actual_cost=data.actual_cost,
            cost_variance=cost_variance,
            within_budget=within_budget,
            quality_checked=False,
            quality_check_passed=None,
            message="Maintenance marked as completed",
        )

    # ------------------------------------------------------------------ #
    # Quality check
    # ------------------------------------------------------------------ #
    def record_quality_check(self, data: QualityCheck) -> None:
        existing = self._store.get_completion(data.maintenance_id) or {}
        existing["quality_check_passed"] = data.quality_check_passed
        existing["checklist_items"] = [ci.model_dump() for ci in data.checklist_items]
        existing["quality_check_notes"] = data.quality_check_notes
        existing["checked_by"] = str(data.checked_by)
        existing["rework_required"] = data.rework_required
        existing["rework_details"] = data.rework_details
        existing["quality_checked_at"] = self._now()
        self._store.save_completion(data.maintenance_id, existing)

    # ------------------------------------------------------------------ #
    # Certificate (read-only assembly)
    # ------------------------------------------------------------------ #
    def get_completion_certificate(
        self,
        maintenance_id: UUID,
        *,
        verified_by: str,
        approved_by: str,
    ) -> CompletionCertificate:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            m = repo.get(maintenance_id)
            if m is None:
                raise errors.NotFoundError(f"Maintenance {maintenance_id} not found")

        details = self._store.get_completion(maintenance_id) or {}
        materials = [
            MaterialItem.model_validate(mi) for mi in details.get("materials_used", [])
        ]
        labor_hours = Decimal(details.get("labor_hours", "0"))
        total_cost = m.actual_cost or Decimal("0")

        today = date.today()
        return CompletionCertificate(
            maintenance_id=maintenance_id,
            request_number=self._request_number(maintenance_id),
            certificate_number=f"CERT-{str(maintenance_id)[:8].upper()}",
            work_description=details.get("work_notes", ""),
            materials_used=materials,
            labor_hours=labor_hours,
            total_cost=total_cost,
            completed_by="",  # can be filled by caller from user context
            verified_by=verified_by,
            approved_by=approved_by,
            completion_date=m.actual_completion_date or today,
            verification_date=today,
            certificate_issue_date=today,
            warranty_period_months=None,
            warranty_terms=None,
        )