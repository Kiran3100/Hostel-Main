# app/services/audit/admin_override_service.py
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.audit import AdminOverrideRepository
from app.repositories.core import HostelRepository, SupervisorRepository, UserRepository
from app.schemas.audit import (
    AdminOverrideCreate,
    AdminOverrideLogResponse,
    AdminOverrideDetail,
    AdminOverrideSummary,
    AdminOverrideTimelinePoint,
)
from app.schemas.common.filters import DateRangeFilter
from app.services.common import UnitOfWork, errors


class AdminOverrideAuditService:
    """
    Audit-focused service for admin overrides:

    - Record overrides (low-level)
    - List overrides for an entity
    - Fetch override detail
    - Summarize overrides over a period
    - Generate simple override timeline
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_repo(self, uow: UnitOfWork) -> AdminOverrideRepository:
        return uow.get_repo(AdminOverrideRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Create
    # ------------------------------------------------------------------ #
    def record_override(self, data: AdminOverrideCreate) -> AdminOverrideDetail:
        """
        Persist an AdminOverride record and return full detail.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)
            user_repo = self._get_user_repo(uow)

            payload = data.model_dump()
            rec = repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            admin_user = user_repo.get(rec.admin_id)
            admin_name = admin_user.full_name if admin_user else None

            sup_name = None
            if rec.supervisor_id:
                sup = sup_repo.get(rec.supervisor_id)
                if sup and getattr(sup, "user", None):
                    sup_name = sup.user.full_name

            hostel = hostel_repo.get(rec.hostel_id)
            hostel_name = hostel.name if hostel else None

            return AdminOverrideDetail(
                id=rec.id,
                created_at=rec.created_at,
                updated_at=rec.created_at,
                admin_id=rec.admin_id,
                admin_name=admin_name,
                supervisor_id=rec.supervisor_id,
                supervisor_name=sup_name,
                hostel_id=rec.hostel_id,
                hostel_name=hostel_name,
                override_type=rec.override_type,
                entity_type=rec.entity_type,
                entity_id=rec.entity_id,
                reason=rec.reason,
                original_action=rec.original_action,
                override_action=rec.override_action,
            )

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #
    def list_overrides_for_entity(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
    ) -> List[AdminOverrideLogResponse]:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            recs = repo.list_for_entity(entity_type=entity_type, entity_id=entity_id)

            return [
                AdminOverrideLogResponse(
                    id=r.id,
                    created_at=r.created_at,
                    updated_at=r.created_at,
                    admin_id=r.admin_id,
                    admin_name=None,
                    supervisor_id=r.supervisor_id,
                    supervisor_name=None,
                    hostel_id=r.hostel_id,
                    hostel_name=None,
                    override_type=r.override_type,
                    entity_type=r.entity_type,
                    entity_id=r.entity_id,
                    reason=r.reason,
                )
                for r in recs
            ]

    def get_override_detail(self, override_id: UUID) -> AdminOverrideDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)
            user_repo = self._get_user_repo(uow)

            r = repo.get(override_id)
            if r is None:
                raise errors.NotFoundError(f"AdminOverride {override_id} not found")

            admin_user = user_repo.get(r.admin_id)
            admin_name = admin_user.full_name if admin_user else None

            sup_name = None
            if r.supervisor_id:
                sup = sup_repo.get(r.supervisor_id)
                if sup and getattr(sup, "user", None):
                    sup_name = sup.user.full_name

            hostel = hostel_repo.get(r.hostel_id)
            hostel_name = hostel.name if hostel else None

            return AdminOverrideDetail(
                id=r.id,
                created_at=r.created_at,
                updated_at=r.created_at,
                admin_id=r.admin_id,
                admin_name=admin_name,
                supervisor_id=r.supervisor_id,
                supervisor_name=sup_name,
                hostel_id=r.hostel_id,
                hostel_name=hostel_name,
                override_type=r.override_type,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                reason=r.reason,
                original_action=r.original_action,
                override_action=r.override_action,
            )

    # ------------------------------------------------------------------ #
    # Summary & timeline
    # ------------------------------------------------------------------ #
    def get_summary(
        self,
        *,
        period: DateRangeFilter,
        supervisor_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
    ) -> AdminOverrideSummary:
        """
        Build AdminOverrideSummary for given period & optional scope.
        """
        if not (period.start_date and period.end_date):
            raise errors.ValidationError(
                "Both start_date and end_date are required for override summary"
            )

        start_dt = datetime.combine(period.start_date, datetime.min.time())
        end_dt = datetime.combine(period.end_date, datetime.max.time())

        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            base_filters: Dict[str, object] = {}
            if supervisor_id:
                base_filters["supervisor_id"] = supervisor_id
            if hostel_id:
                base_filters["hostel_id"] = hostel_id

            recs = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=base_filters or None,
            )

            logs = [
                r for r in recs if start_dt <= r.created_at <= end_dt
            ]

            total_overrides = len(logs)
            overrides_by_type: Dict[str, int] = defaultdict(int)
            overrides_by_admin: Dict[UUID, int] = defaultdict(int)

            for r in logs:
                overrides_by_type[r.override_type] += 1
                overrides_by_admin[r.admin_id] += 1

        return AdminOverrideSummary(
            period_start=start_dt,
            period_end=end_dt,
            supervisor_id=supervisor_id,
            hostel_id=hostel_id,
            total_overrides=total_overrides,
            overrides_by_type=dict(overrides_by_type),
            overrides_by_admin=dict(overrides_by_admin),
            override_rate_for_supervisor=None,
        )

    def get_timeline(
        self,
        *,
        period: DateRangeFilter,
        supervisor_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
    ) -> List[AdminOverrideTimelinePoint]:
        """
        Simple date-bucketed override count timeline.
        """
        if not (period.start_date and period.end_date):
            raise errors.ValidationError(
                "Both start_date and end_date are required for override timeline"
            )

        start_dt = datetime.combine(period.start_date, datetime.min.time())
        end_dt = datetime.combine(period.end_date, datetime.max.time())

        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            base_filters: Dict[str, object] = {}
            if supervisor_id:
                base_filters["supervisor_id"] = supervisor_id
            if hostel_id:
                base_filters["hostel_id"] = hostel_id

            recs = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=base_filters or None,
            )

            buckets: Dict[str, int] = defaultdict(int)
            for r in recs:
                if r.created_at < start_dt or r.created_at > end_dt:
                    continue
                label = r.created_at.date().isoformat()
                buckets[label] += 1

        return [
            AdminOverrideTimelinePoint(
                bucket_label=label,
                override_count=count,
            )
            for label, count in sorted(buckets.items())
        ]