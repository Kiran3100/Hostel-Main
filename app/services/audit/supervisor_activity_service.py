# app/services/audit/supervisor_activity_service.py
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.audit import SupervisorActivityRepository
from app.repositories.core import HostelRepository, SupervisorRepository
from app.schemas.audit import (
    SupervisorActivityCreate,
    SupervisorActivityLogResponse,
    SupervisorActivityDetail,
    SupervisorActivityFilter,
    SupervisorActivitySummary,
    SupervisorActivityTimelinePoint,
)
from app.schemas.common.pagination import PaginatedResponse
from app.services.common import UnitOfWork, errors


class SupervisorActivityService:
    """
    Supervisor activity logging and reporting:

    - Log supervisor actions
    - List actions with filters + pagination
    - Fetch detailed entry
    - Summarize actions over a period (per category/type + timeline)
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_repo(self, uow: UnitOfWork) -> SupervisorActivityRepository:
        return uow.get_repo(SupervisorActivityRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_log_response(
        self,
        rec,
        *,
        supervisor_name: Optional[str],
        hostel_name: Optional[str],
    ) -> SupervisorActivityLogResponse:
        return SupervisorActivityLogResponse(
            id=rec.id,
            created_at=rec.created_at,
            updated_at=rec.created_at,
            supervisor_id=rec.supervisor_id,
            supervisor_name=supervisor_name,
            hostel_id=rec.hostel_id,
            hostel_name=hostel_name,
            action_type=rec.action_type,
            action_category=rec.action_category,
            entity_type=rec.entity_type,
            entity_id=rec.entity_id,
            action_description=rec.action_description,
            ip_address=rec.ip_address,
            user_agent=rec.user_agent,
        )

    def _to_detail(
        self,
        rec,
        *,
        supervisor_name: Optional[str],
        hostel_name: Optional[str],
    ) -> SupervisorActivityDetail:
        return SupervisorActivityDetail(
            id=rec.id,
            created_at=rec.created_at,
            updated_at=rec.created_at,
            supervisor_id=rec.supervisor_id,
            supervisor_name=supervisor_name,
            hostel_id=rec.hostel_id,
            hostel_name=hostel_name,
            action_type=rec.action_type,
            action_category=rec.action_category,
            entity_type=rec.entity_type,
            entity_id=rec.entity_id,
            action_description=rec.action_description,
            metadata=rec.metadata or {},
            ip_address=rec.ip_address,
            user_agent=rec.user_agent,
        )

    # ------------------------------------------------------------------ #
    # Log activity
    # ------------------------------------------------------------------ #
    def log_activity(self, data: SupervisorActivityCreate) -> SupervisorActivityLogResponse:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)

            payload = data.model_dump()
            rec = repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            sup = sup_repo.get(rec.supervisor_id)
            supervisor_name = (
                sup.user.full_name
                if sup and getattr(sup, "user", None)
                else None
            )

            hostel = hostel_repo.get(rec.hostel_id)
            hostel_name = hostel.name if hostel else None

            return self._to_log_response(
                rec,
                supervisor_name=supervisor_name,
                hostel_name=hostel_name,
            )

    # ------------------------------------------------------------------ #
    # Read operations
    # ------------------------------------------------------------------ #
    def get_activity(self, activity_id: UUID) -> SupervisorActivityDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)

            rec = repo.get(activity_id)
            if rec is None:
                raise errors.NotFoundError(
                    f"SupervisorActivity {activity_id} not found"
                )

            sup = sup_repo.get(rec.supervisor_id)
            supervisor_name = (
                sup.user.full_name
                if sup and getattr(sup, "user", None)
                else None
            )

            hostel = hostel_repo.get(rec.hostel_id)
            hostel_name = hostel.name if hostel else None

            return self._to_detail(
                rec,
                supervisor_name=supervisor_name,
                hostel_name=hostel_name,
            )

    def list_activities(
        self,
        filters: SupervisorActivityFilter,
    ) -> PaginatedResponse[SupervisorActivityLogResponse]:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)

            raw_filters: Dict[str, object] = {}
            if filters.supervisor_id:
                raw_filters["supervisor_id"] = filters.supervisor_id
            if filters.hostel_id:
                raw_filters["hostel_id"] = filters.hostel_id
            if filters.action_type:
                raw_filters["action_type"] = filters.action_type
            if filters.action_category:
                raw_filters["action_category"] = filters.action_category
            if filters.entity_type:
                raw_filters["entity_type"] = filters.entity_type
            if filters.entity_id:
                raw_filters["entity_id"] = filters.entity_id

            records = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=raw_filters or None,
                order_by=[repo.model.created_at.desc()],  # type: ignore[attr-defined]
            )

            # datetime_range filtering
            def _in_range(rec) -> bool:
                if not filters.datetime_range:
                    return True
                dr = filters.datetime_range
                created = rec.created_at
                if dr.start and created < dr.start:
                    return False
                if dr.end and created > dr.end:
                    return False
                return True

            filtered = [r for r in records if _in_range(r)]

            page = filters.page
            page_size = filters.page_size
            offset = (page - 1) * page_size
            page_records = filtered[offset : offset + page_size]

            # Cache names
            sup_cache: Dict[UUID, Optional[str]] = {}
            hostel_cache: Dict[UUID, Optional[str]] = {}

            items: List[SupervisorActivityLogResponse] = []
            for r in page_records:
                if r.supervisor_id not in sup_cache:
                    sup = sup_repo.get(r.supervisor_id)
                    sup_cache[r.supervisor_id] = (
                        sup.user.full_name
                        if sup and getattr(sup, "user", None)
                        else None
                    )
                supervisor_name = sup_cache[r.supervisor_id]

                if r.hostel_id not in hostel_cache:
                    h = hostel_repo.get(r.hostel_id)
                    hostel_cache[r.hostel_id] = h.name if h else None
                hostel_name = hostel_cache[r.hostel_id]

                items.append(
                    self._to_log_response(
                        r,
                        supervisor_name=supervisor_name,
                        hostel_name=hostel_name,
                    )
                )

            return PaginatedResponse[SupervisorActivityLogResponse].create(
                items=items,
                total_items=len(filtered),
                page=page,
                page_size=page_size,
            )

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    def get_summary(
        self,
        filters: SupervisorActivityFilter,
    ) -> SupervisorActivitySummary:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)

            raw_filters: Dict[str, object] = {}
            if filters.supervisor_id:
                raw_filters["supervisor_id"] = filters.supervisor_id
            if filters.hostel_id:
                raw_filters["hostel_id"] = filters.hostel_id

            records = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=raw_filters or None,
                order_by=[repo.model.created_at.asc()],  # type: ignore[attr-defined]
            )

            # datetime_range filter
            logs: List = []
            start = None
            end = None
            if filters.datetime_range:
                start = filters.datetime_range.start
                end = filters.datetime_range.end

            for r in records:
                if start and r.created_at < start:
                    continue
                if end and r.created_at > end:
                    continue
                logs.append(r)

            total_actions = len(logs)
            actions_by_category: Dict[str, int] = defaultdict(int)
            actions_by_type: Dict[str, int] = defaultdict(int)
            timeline_map: Dict[str, int] = defaultdict(int)

            for r in logs:
                actions_by_category[r.action_category] += 1
                actions_by_type[r.action_type] += 1
                bucket = r.created_at.date().isoformat()
                timeline_map[bucket] += 1

            # Supervisor / hostel names
            sup = (
                sup_repo.get(filters.supervisor_id)
                if filters.supervisor_id
                else None
            )
            supervisor_name = (
                sup.user.full_name
                if sup and getattr(sup, "user", None)
                else None
            )

            hostel = (
                hostel_repo.get(filters.hostel_id)
                if filters.hostel_id
                else None
            )
            hostel_name = hostel.name if hostel else None

            # Period
            if start and end:
                period_start = start
                period_end = end
            elif logs:
                period_start = logs[0].created_at
                period_end = logs[-1].created_at
            else:
                # No logs; default to now
                now = self._now()
                period_start = now
                period_end = now

            timeline: List[SupervisorActivityTimelinePoint] = [
                SupervisorActivityTimelinePoint(
                    bucket_label=day,
                    action_count=count,
                )
                for day, count in sorted(timeline_map.items())
            ]

            return SupervisorActivitySummary(
                supervisor_id=filters.supervisor_id or UUID(int=0),
                supervisor_name=supervisor_name,
                hostel_id=filters.hostel_id or UUID(int=0),
                hostel_name=hostel_name,
                period_start=period_start,
                period_end=period_end,
                total_actions=total_actions,
                actions_by_category=dict(actions_by_category),
                actions_by_type=dict(actions_by_type),
                timeline=timeline,
            )