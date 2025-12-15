# app/services/supervisor/supervisor_activity_service.py
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.audit import SupervisorActivityRepository
from app.repositories.core import SupervisorRepository, HostelRepository
from app.schemas.common.filters import DateTimeRangeFilter
from app.schemas.supervisor.supervisor_activity import (
    SupervisorActivityLog,
    ActivitySummary,
    ActivityDetail,
    ActivityFilterParams,
    TopActivity,
    ActivityTimelinePoint,
)
from app.services.common import UnitOfWork, errors


class SupervisorActivityService:
    """
    Supervisor activity reporting:

    - List activity logs with filtering
    - Get single activity detail
    - Build summary over a period
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # Helpers
    def _get_repo(self, uow: UnitOfWork) -> SupervisorActivityRepository:
        return uow.get_repo(SupervisorActivityRepository)

    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # Mapping
    def _to_log(
        self,
        rec,
        *,
        supervisor_name: str,
        hostel_name: str,
    ) -> SupervisorActivityLog:
        from app.schemas.common.enums import AuditActionCategory

        category = rec.action_category
        if not isinstance(category, AuditActionCategory):
            try:
                category = AuditActionCategory(category)
            except Exception:
                category = AuditActionCategory.OTHER  # type: ignore[attr-defined]

        return SupervisorActivityLog(
            id=rec.id,
            created_at=rec.created_at,
            updated_at=rec.created_at,
            supervisor_id=rec.supervisor_id,
            supervisor_name=supervisor_name,
            hostel_id=rec.hostel_id,
            hostel_name=hostel_name,
            action_type=rec.action_type,
            action_category=category,
            entity_type=rec.entity_type,
            entity_id=rec.entity_id,
            action_description=rec.action_description,
            metadata=rec.metadata or {},
            ip_address=rec.ip_address,
            user_agent=rec.user_agent,
        )

    # Listing
    def list_activity_logs(self, filters: ActivityFilterParams) -> List[SupervisorActivityLog]:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            raw_filters: Dict[str, object] = {}
            if filters.supervisor_id:
                raw_filters["supervisor_id"] = filters.supervisor_id
            elif filters.supervisor_ids:
                raw_filters["supervisor_id"] = filters.supervisor_ids
            if filters.hostel_id:
                raw_filters["hostel_id"] = filters.hostel_id
            if filters.action_type:
                raw_filters["action_type"] = filters.action_type
            if filters.entity_type:
                raw_filters["entity_type"] = filters.entity_type
            if filters.entity_id:
                raw_filters["entity_id"] = filters.entity_id

            recs = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=raw_filters or None,
                order_by=[repo.model.created_at.desc()],  # type: ignore[attr-defined]
            )

            def _in_range(rec) -> bool:
                dr: Optional[DateTimeRangeFilter] = filters.date_range
                if not dr:
                    return True
                if dr.start and rec.created_at < dr.start:
                    return False
                if dr.end and rec.created_at > dr.end:
                    return False
                return True

            def _cat_ok(rec) -> bool:
                if filters.action_category:
                    return rec.action_category == filters.action_category
                if filters.action_categories:
                    return rec.action_category in filters.action_categories
                return True

            def _success_ok(rec) -> bool:
                # Success/failure flags not in model; treat all as success
                if filters.success_only:
                    return True
                if filters.failed_only:
                    return False
                return True

            filtered = [r for r in recs if _in_range(r) and _cat_ok(r) and _success_ok(r)]

            # Pagination
            page = filters.page
            page_size = filters.page_size
            offset = (page - 1) * page_size
            page_recs = filtered[offset : offset + page_size]

            # Cache names
            sup_cache: Dict[UUID, str] = {}
            hostel_cache: Dict[UUID, str] = {}

            logs: List[SupervisorActivityLog] = []
            for r in page_recs:
                if r.supervisor_id not in sup_cache:
                    sup = sup_repo.get(r.supervisor_id)
                    sup_cache[r.supervisor_id] = (
                        sup.user.full_name if sup and getattr(sup, "user", None) else ""
                    )
                supervisor_name = sup_cache[r.supervisor_id]

                if r.hostel_id not in hostel_cache:
                    h = hostel_repo.get(r.hostel_id)
                    hostel_cache[r.hostel_id] = h.name if h else ""
                hostel_name = hostel_cache[r.hostel_id]

                logs.append(self._to_log(r, supervisor_name=supervisor_name, hostel_name=hostel_name))

            return logs

    # Detail
    def get_activity_detail(self, activity_id: UUID) -> ActivityDetail:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            sup_repo = self._get_supervisor_repo(uow)

            r = repo.get(activity_id)
            if r is None:
                raise errors.NotFoundError(f"SupervisorActivity {activity_id} not found")

            sup = sup_repo.get(r.supervisor_id)
            sup_name = sup.user.full_name if sup and getattr(sup, "user", None) else ""

        return ActivityDetail(
            activity_id=r.id,
            supervisor_id=r.supervisor_id,
            supervisor_name=sup_name,
            timestamp=r.created_at,
            action_type=r.action_type,
            action_category=r.action_category,
            action_description=r.action_description,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            entity_name=None,
            old_values=None,
            new_values=None,
            ip_address=r.ip_address,
            user_agent=r.user_agent,
            location=None,
            success=True,
            error_message=None,
        )

    # Summary
    def get_activity_summary(self, filters: ActivityFilterParams) -> ActivitySummary:
        logs = self.list_activity_logs(filters)

        if filters.date_range and filters.date_range.start and filters.date_range.end:
            period_start = filters.date_range.start
            period_end = filters.date_range.end
        elif logs:
            period_start = logs[-1].created_at
            period_end = logs[0].created_at
        else:
            now = self._now()
            period_start = period_end = now

        total_actions = len(logs)
        actions_by_category: Dict[str, int] = defaultdict(int)
        actions_by_type: Dict[str, int] = defaultdict(int)
        timeline_map: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        type_cat_counts: Dict[tuple[str, str], Dict[str, object]] = {}

        for l in logs:
            cat_key = l.action_category.value if hasattr(l.action_category, "value") else str(l.action_category)
            type_key = l.action_type
            actions_by_category[cat_key] += 1
            actions_by_type[type_key] += 1

            # timeline (per day)
            day_label = l.created_at.date().isoformat()
            timeline_map[day_label][cat_key] += 1

            key = (type_key, cat_key)
            rec = type_cat_counts.setdefault(
                key,
                {"count": 0, "last": l.created_at},
            )
            rec["count"] += 1
            if l.created_at > rec["last"]:
                rec["last"] = l.created_at

        # Top activities
        top_activities: List[TopActivity] = []
        for (act_type, cat), v in sorted(
            type_cat_counts.items(), key=lambda kv: kv[1]["count"], reverse=True
        )[:5]:
            top_activities.append(
                TopActivity(
                    action_type=act_type,
                    action_category=cat,
                    count=v["count"],
                    last_performed=v["last"],
                )
            )

        # Timeline points
        timeline: List[ActivityTimelinePoint] = []
        for day, cats in sorted(timeline_map.items()):
            ts = datetime.fromisoformat(day)
            total_day = sum(cats.values())
            timeline.append(
                ActivityTimelinePoint(
                    timestamp=ts,
                    action_count=total_day,
                    categories=dict(cats),
                )
            )

        # Peak hours
        hour_counts: Dict[int, int] = defaultdict(int)
        for l in logs:
            hour_counts[l.created_at.hour] += 1
        sorted_hours = sorted(hour_counts.items(), key=lambda kv: kv[1], reverse=True)
        peak_hours = [h for h, _ in sorted_hours[:3]]

        supervisor_id = filters.supervisor_id or UUID(int=0)
        supervisor_name = ""

        return ActivitySummary(
            supervisor_id=supervisor_id,
            supervisor_name=supervisor_name,
            period_start=period_start,
            period_end=period_end,
            total_actions=total_actions,
            actions_by_category=dict(actions_by_category),
            actions_by_type=dict(actions_by_type),
            top_activities=top_activities,
            activity_timeline=timeline,
            peak_hours=peak_hours,
        )