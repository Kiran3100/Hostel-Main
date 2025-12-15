# app/services/audit/audit_log_service.py
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.audit import AuditLogRepository
from app.repositories.core import UserRepository
from app.schemas.audit import (
    AuditLogCreate,
    AuditLogResponse,
    AuditLogDetail,
    AuditFilterParams,
    AuditReport,
    AuditSummary,
    UserActivitySummary,
    EntityChangeHistory,
)
from app.schemas.audit.audit_reports import EntityChangeSummary
from app.schemas.common.enums import AuditActionCategory, UserRole
from app.schemas.common.filters import DateRangeFilter
from app.schemas.common.pagination import PaginatedResponse
from app.services.common import UnitOfWork, errors


class AuditLogService:
    """
    Generic audit log service:

    - Create audit log entries
    - List logs with filters + pagination
    - Fetch log detail
    - Build high-level AuditReport (summary + per-entity summaries)
    - Build change history for a specific entity
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_repo(self, uow: UnitOfWork) -> AuditLogRepository:
        return uow.get_repo(AuditLogRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_response(self, log) -> AuditLogResponse:
        return AuditLogResponse(
            id=log.id,
            created_at=log.created_at,
            updated_at=log.created_at,
            user_id=log.user_id,
            user_role=log.user_role,
            action_type=log.action_type,
            action_category=log.action_category,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            hostel_id=log.hostel_id,
            description=log.description,
            ip_address=log.ip_address,
        )

    def _to_detail(self, log) -> AuditLogDetail:
        return AuditLogDetail(
            id=log.id,
            created_at=log.created_at,
            updated_at=log.created_at,
            user_id=log.user_id,
            user_role=log.user_role,
            action_type=log.action_type,
            action_category=log.action_category,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            hostel_id=log.hostel_id,
            description=log.description,
            old_values=log.old_values,
            new_values=log.new_values,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            request_id=log.request_id,
        )

    # ------------------------------------------------------------------ #
    # Create / read
    # ------------------------------------------------------------------ #
    def log_action(self, data: AuditLogCreate) -> AuditLogResponse:
        """
        Persist a new audit log entry.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            payload = data.model_dump()
            # created_at has default in model; rely on DB default or pass explicitly
            log = repo.create(payload)  # type: ignore[arg-type]
            uow.commit()
            return self._to_response(log)

    def get_log(self, log_id: UUID) -> AuditLogDetail:
        """
        Fetch a single audit log entry.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            log = repo.get(log_id)
            if log is None:
                raise errors.NotFoundError(f"AuditLog {log_id} not found")
            return self._to_detail(log)

    # ------------------------------------------------------------------ #
    # Listing with filters
    # ------------------------------------------------------------------ #
    def list_logs(
        self,
        filters: AuditFilterParams,
    ) -> PaginatedResponse[AuditLogResponse]:
        """
        List audit logs with filters and pagination.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)

            raw_filters: Dict[str, object] = {}
            if filters.user_id:
                raw_filters["user_id"] = filters.user_id
            if filters.user_role:
                raw_filters["user_role"] = filters.user_role
            if filters.hostel_id:
                raw_filters["hostel_id"] = filters.hostel_id
            if filters.entity_type:
                raw_filters["entity_type"] = filters.entity_type
            if filters.entity_id:
                raw_filters["entity_id"] = filters.entity_id
            if filters.action_type:
                raw_filters["action_type"] = filters.action_type
            if filters.action_category:
                raw_filters["action_category"] = filters.action_category
            if filters.request_id:
                raw_filters["request_id"] = filters.request_id

            records = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=raw_filters or None,
                order_by=[repo.model.created_at.desc()],  # type: ignore[attr-defined]
            )

            # Advanced datetime_range filter
            def _in_range(log) -> bool:
                if not filters.datetime_range:
                    return True
                rng = filters.datetime_range
                created = log.created_at
                if rng.start and created < rng.start:
                    return False
                if rng.end and created > rng.end:
                    return False
                return True

            filtered = [l for l in records if _in_range(l)]

            # Pagination
            page = filters.page
            page_size = filters.page_size
            offset = (page - 1) * page_size
            page_items = filtered[offset : offset + page_size]

            items = [self._to_response(l) for l in page_items]

            return PaginatedResponse[AuditLogResponse].create(
                items=items,
                total_items=len(filtered),
                page=page,
                page_size=page_size,
            )

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #
    def build_report(
        self,
        period: DateRangeFilter,
        *,
        hostel_id: Optional[UUID] = None,
    ) -> AuditReport:
        """
        Build a high-level AuditReport for the given period (and optional hostel).
        """
        if not (period.start_date and period.end_date):
            raise errors.ValidationError(
                "Both start_date and end_date are required for audit report"
            )

        start_dt = datetime.combine(period.start_date, datetime.min.time())
        end_dt = datetime.combine(period.end_date, datetime.max.time())

        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            user_repo = self._get_user_repo(uow)

            base_filters: Dict[str, object] = {}
            if hostel_id:
                base_filters["hostel_id"] = hostel_id

            records = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=base_filters or None,
                order_by=[repo.model.created_at.asc()],  # type: ignore[attr-defined]
            )

            # Filter by period
            logs = [
                l for l in records if start_dt <= l.created_at <= end_dt
            ]

            total_events = len(logs)

            events_by_category: Dict[AuditActionCategory, int] = defaultdict(int)
            events_by_user_role: Dict[UserRole, int] = defaultdict(int)
            user_stats: Dict[UUID, Dict[str, object]] = {}

            entity_summaries_map: Dict[str, EntityChangeSummary] = {}

            for l in logs:
                events_by_category[l.action_category] += 1
                if l.user_role:
                    events_by_user_role[l.user_role] += 1

                # User aggregation
                if l.user_id:
                    if l.user_id not in user_stats:
                        user_stats[l.user_id] = {
                            "role": l.user_role,
                            "total": 0,
                            "by_cat": defaultdict(int),
                        }
                    us = user_stats[l.user_id]
                    us["total"] = int(us["total"]) + 1
                    us["by_cat"][l.action_category] += 1  # type: ignore[index]

                # Entity summaries (by entity_type)
                etype = l.entity_type or "unknown"
                if etype not in entity_summaries_map:
                    entity_summaries_map[etype] = EntityChangeSummary(
                        entity_type=etype,
                        change_count=0,
                        last_change_at=l.created_at,
                    )
                es = entity_summaries_map[etype]
                es.change_count += 1
                if l.created_at > es.last_change_at:
                    es.last_change_at = l.created_at

            # Build UserActivitySummary list
            user_summaries: List[UserActivitySummary] = []
            for uid, data in user_stats.items():
                role = data["role"]
                total = data["total"]
                by_cat = data["by_cat"]  # type: ignore[assignment]

                user = user_repo.get(uid)
                user_name = user.full_name if user else None

                user_summaries.append(
                    UserActivitySummary(
                        user_id=uid,
                        user_name=user_name,
                        user_role=role,
                        total_events=total,
                        events_by_category=dict(by_cat),
                    )
                )

            # Sort top users by total events
            user_summaries.sort(key=lambda s: s.total_events, reverse=True)

            summary = AuditSummary(
                period=period,
                total_events=total_events,
                events_by_category=dict(events_by_category),
                events_by_user_role=dict(events_by_user_role),
                top_users_by_events=user_summaries[:10],
            )

            entity_summaries = list(entity_summaries_map.values())

        return AuditReport(
            generated_at=datetime.utcnow(),
            period=period,
            summary=summary,
            entity_summaries=entity_summaries,
        )

    # ------------------------------------------------------------------ #
    # Entity history
    # ------------------------------------------------------------------ #
    def get_entity_history(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
    ) -> EntityChangeHistory:
        """
        Build an EntityChangeHistory for a specific entity instance.
        """
        from app.schemas.audit.audit_reports import EntityChangeRecord

        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            user_repo = self._get_user_repo(uow)

            logs = repo.list_for_entity(
                entity_type=entity_type,
                entity_id=entity_id,
            )

            changes: List[EntityChangeRecord] = []
            for l in logs:
                user_name = None
                if l.user_id:
                    u = user_repo.get(l.user_id)
                    user_name = u.full_name if u else None

                changes.append(
                    EntityChangeRecord(
                        log_id=l.id,
                        action_type=l.action_type,
                        description=l.description,
                        old_values=l.old_values,
                        new_values=l.new_values,
                        changed_by=l.user_id,
                        changed_by_name=user_name,
                        changed_at=l.created_at,
                    )
                )

        # Ensure chronological order
        changes.sort(key=lambda c: c.changed_at)

        return EntityChangeHistory(
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes,
        )