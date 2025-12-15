# app/services/auth/context_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, Optional, List
from uuid import UUID

from app.schemas.admin import (
    HostelContext,
    HostelSwitchRequest,
    ActiveHostelResponse,
    ContextHistory,
    ContextSwitch,
)
from app.services.common import errors


class ContextStore(Protocol):
    """
    Abstract store for admin's active hostel context and history.

    Implementations can use Redis, DB tables, etc.
    """

    def get_active_hostel(self, admin_id: UUID) -> Optional[dict]: ...
    def set_active_hostel(self, admin_id: UUID, context: dict) -> None: ...
    def add_switch_record(self, admin_id: UUID, record: dict) -> None: ...
    def list_switches(self, admin_id: UUID) -> List[dict]: ...


class ContextService:
    """
    Manages the current "active hostel" context for multi-hostel admins.
    """

    def __init__(self, store: ContextStore) -> None:
        self._store = store

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def get_active_context(self, admin_id: UUID) -> Optional[HostelContext]:
        record = self._store.get_active_hostel(admin_id)
        if not record:
            return None
        return HostelContext.model_validate(record)

    def switch_hostel(
        self,
        admin_id: UUID,
        req: HostelSwitchRequest,
        *,
        hostel_name: str,
        hostel_city: str,
        permission_level: str,
    ) -> ActiveHostelResponse:
        """
        Switch active hostel for an admin.

        Caller is responsible for validating that the admin has access to
        the requested hostel and retrieving hostel/permission metadata.
        """
        now = self._now()
        prev = self._store.get_active_hostel(admin_id)
        previous_hostel_id = prev.get("active_hostel_id") if prev else None

        context = {
            "admin_id": admin_id,
            "active_hostel_id": req.hostel_id,
            "hostel_name": hostel_name,
            "hostel_city": hostel_city,
            "permission_level": permission_level,
            "context_started_at": now,
            "last_accessed_at": now,
            "total_students": 0,
            "occupancy_percentage": 0,
            "pending_tasks": 0,
        }
        self._store.set_active_hostel(admin_id, context)

        # Record switch in history
        switch_record = {
            "from_hostel_id": previous_hostel_id,
            "from_hostel_name": prev.get("hostel_name") if prev else None,
            "to_hostel_id": req.hostel_id,
            "to_hostel_name": hostel_name,
            "switched_at": now,
            "session_duration_minutes": None,
        }
        self._store.add_switch_record(admin_id, switch_record)

        return ActiveHostelResponse(
            admin_id=admin_id,
            previous_hostel_id=previous_hostel_id,
            active_hostel_id=req.hostel_id,
            hostel_name=hostel_name,
            permission_level=permission_level,
            permissions={},
            switched_at=now,
            message="Switched active hostel successfully",
        )

    def get_context_history(self, admin_id: UUID) -> ContextHistory:
        records = self._store.list_switches(admin_id)
        switches = [ContextSwitch.model_validate(r) for r in records]
        return ContextHistory(admin_id=admin_id, switches=switches)