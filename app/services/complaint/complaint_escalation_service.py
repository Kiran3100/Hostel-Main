# app/services/complaint/complaint_escalation_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, List, Optional
from uuid import UUID

from app.schemas.complaint import (
    EscalationRequest,
    EscalationResponse,
    EscalationHistory,
    EscalationEntry,
    AutoEscalationRule,
)
from app.services.common import errors


class EscalationStore(Protocol):
    """
    Abstract storage for complaint escalations and auto-escalation rules.

    Implementations can use Redis, a dedicated DB table, etc.
    """

    def save_escalation(self, complaint_id: UUID, record: dict) -> None: ...
    def list_escalations(self, complaint_id: UUID) -> List[dict]: ...
    def get_rule(self, hostel_id: UUID) -> Optional[dict]: ...
    def save_rule(self, hostel_id: UUID, rule: dict) -> None: ...


class ComplaintEscalationService:
    """
    Manage manual and automatic escalations for complaints.

    NOTE:
    - This service does not modify the Complaint model directly; it records
      escalation metadata in an EscalationStore. You can hook it together
      with ComplaintService / ComplaintAssignmentService as needed.
    """

    def __init__(self, store: EscalationStore) -> None:
        self._store = store

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Manual escalation
    # ------------------------------------------------------------------ #
    def escalate(
        self,
        data: EscalationRequest,
        *,
        escalated_by_id: UUID,
        escalated_by_name: str,
        escalated_to_name: str,
    ) -> EscalationResponse:
        now = self._now()
        record = {
            "id": UUID.hex(UUID(int=0)),  # placeholder if you want IDs; customize
            "escalated_to": str(data.escalate_to),
            "escalated_to_name": escalated_to_name,
            "escalated_by": str(escalated_by_id),
            "escalated_by_name": escalated_by_name,
            "escalated_at": now,
            "reason": data.escalation_reason,
            "status_before": None,
            "priority_before": None,
            "priority_after": None,
        }
        self._store.save_escalation(data.complaint_id, record)

        return EscalationResponse(
            complaint_id=data.complaint_id,
            complaint_number="",  # can be filled by caller with ComplaintService
            escalated=True,
            escalated_to=data.escalate_to,
            escalated_to_name=escalated_to_name,
            escalated_by=escalated_by_id,
            escalated_by_name=escalated_by_name,
            escalated_at=now,
            new_priority="",
            message="Complaint escalated successfully",
        )

    def get_history(self, complaint_id: UUID, complaint_number: str) -> EscalationHistory:
        records = self._store.list_escalations(complaint_id)
        entries: List[EscalationEntry] = []
        for r in records:
            entries.append(
                EscalationEntry(
                    id=None,  # BaseResponseSchema fields can be left None if not used
                    created_at=r.get("escalated_at"),
                    updated_at=r.get("escalated_at"),
                    escalated_to=UUID(r["escalated_to"]),
                    escalated_to_name=r.get("escalated_to_name"),
                    escalated_by=UUID(r["escalated_by"]),
                    escalated_by_name=r.get("escalated_by_name"),
                    escalated_at=r.get("escalated_at"),
                    reason=r.get("reason"),
                    status_before=r.get("status_before"),
                    priority_before=r.get("priority_before"),
                    priority_after=r.get("priority_after"),
                    response_time_hours=None,
                    resolved_after_escalation=False,
                )
            )

        return EscalationHistory(
            complaint_id=complaint_id,
            complaint_number=complaint_number,
            escalations=entries,
            total_escalations=len(entries),
        )

    # ------------------------------------------------------------------ #
    # Auto-escalation rule config (hostel-level)
    # ------------------------------------------------------------------ #
    def get_auto_rule(self, hostel_id: UUID) -> Optional[AutoEscalationRule]:
        record = self._store.get_rule(hostel_id)
        if not record:
            return None
        return AutoEscalationRule.model_validate(record)

    def set_auto_rule(self, rule: AutoEscalationRule) -> None:
        self._store.save_rule(rule.hostel_id, rule.model_dump())