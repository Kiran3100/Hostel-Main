# app/services/analytics/complaint_analytics_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import ComplaintRepository
from app.repositories.core import HostelRepository
from app.schemas.analytics.complaint_analytics import (
    ComplaintKPI,
    ComplaintTrend,
    ComplaintTrendPoint,
    CategoryBreakdown,
    ComplaintDashboard,
)
from app.schemas.common.enums import ComplaintStatus, Priority
from app.schemas.common.filters import DateRangeFilter
from app.services.common import UnitOfWork


class ComplaintAnalyticsService:
    """
    Dashboard-level complaint analytics using analytics.complaint_analytics schemas.

    For more detailed per-complaint analytics, see services/complaint.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_complaint_repo(self, uow: UnitOfWork) -> ComplaintRepository:
        return uow.get_repo(ComplaintRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    # ------------------------------------------------------------------ #
    # Dashboard
    # ------------------------------------------------------------------ #
    def get_dashboard_for_hostel(
        self,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> ComplaintDashboard:
        with UnitOfWork(self._session_factory) as uow:
            complaint_repo = self._get_complaint_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            hostel_name = hostel.name if hostel else ""

            complaints = complaint_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"hostel_id": hostel_id},
            )

        # Filter by opened_at within period
        start = period.start_date or date.min
        end = period.end_date or date.max

        filtered = []
        for c in complaints:
            opened_date = c.opened_at.date() if c.opened_at else None
            if opened_date is None:
                continue
            if opened_date < start or opened_date > end:
                continue
            filtered.append(c)

        total = len(filtered)
        open_count = resolved_count = closed_count = 0

        total_resolved_hours = 0.0
        resolved_with_time = 0
        sla_breached = 0

        # Category + priority aggregation
        category_counts: Dict[str, int] = {}
        total_resolution_time_by_cat: Dict[str, float] = {}
        priority_counts: Dict[str, int] = {}

        for c in filtered:
            if c.status == ComplaintStatus.OPEN:
                open_count += 1
            if c.status == ComplaintStatus.RESOLVED:
                resolved_count += 1
            if c.status == ComplaintStatus.CLOSED:
                closed_count += 1
            if c.sla_breach:
                sla_breached += 1

            cat_key = c.category.value if hasattr(c.category, "value") else str(c.category)
            category_counts[cat_key] = category_counts.get(cat_key, 0) + 1

            if c.priority in (Priority.URGENT, Priority.CRITICAL):
                prio_key = "urgent"
            else:
                prio_key = (c.priority.value if hasattr(c.priority, "value") else str(c.priority))
            priority_counts[prio_key] = priority_counts.get(prio_key, 0) + 1

            if c.resolved_at and c.opened_at:
                diff_hours = (c.resolved_at - c.opened_at).total_seconds() / 3600.0
                total_resolved_hours += diff_hours
                resolved_with_time += 1
                total_resolution_time_by_cat[cat_key] = total_resolution_time_by_cat.get(cat_key, 0.0) + diff_hours

        avg_resolution = (
            Decimal(str(total_resolved_hours / resolved_with_time))
            if resolved_with_time > 0
            else Decimal("0")
        )

        sla_compliance_rate = (
            Decimal(str((total - sla_breached) / total * 100)) if total > 0 else Decimal("0")
        )
        escalation_rate = Decimal("0")  # not tracked in Complaint model
        reopen_rate = Decimal("0")  # also not tracked here

        kpi = ComplaintKPI(
            hostel_id=hostel_id,
            hostel_name=hostel_name,
            total_complaints=total,
            open_complaints=open_count,
            resolved_complaints=resolved_count,
            closed_complaints=closed_count,
            average_resolution_time_hours=avg_resolution,
            sla_compliance_rate=sla_compliance_rate,
            escalation_rate=escalation_rate,
            reopen_rate=reopen_rate,
        )

        # Trend
        trend_by_date: Dict[str, Dict[str, int]] = {}
        for c in filtered:
            if not c.opened_at:
                continue
            d = c.opened_at.date().isoformat()
            bucket = trend_by_date.setdefault(
                d,
                {
                    "total": 0,
                    "open": 0,
                    "resolved": 0,
                    "escalated": 0,
                    "sla_breached": 0,
                },
            )
            bucket["total"] += 1
            if c.status == ComplaintStatus.OPEN:
                bucket["open"] += 1
            if c.status == ComplaintStatus.RESOLVED:
                bucket["resolved"] += 1
            # escalate / SLA not explicitly modeled; sla_breach used
            if c.sla_breach:
                bucket["sla_breached"] += 1

        points: List[ComplaintTrendPoint] = []
        for d, vals in sorted(trend_by_date.items()):
            points.append(
                ComplaintTrendPoint(
                    date=date.fromisoformat(d),
                    total_complaints=vals["total"],
                    open_complaints=vals["open"],
                    resolved_complaints=vals["resolved"],
                    escalated=vals["escalated"],
                    sla_breached=vals["sla_breached"],
                )
            )

        trend = ComplaintTrend(
            period=period,
            points=points,
        )

        # Category breakdown
        cat_breakdown: List[CategoryBreakdown] = []
        for cat, count in category_counts.items():
            pct = Decimal(str(count / total * 100)) if total > 0 else Decimal("0")
            avg_cat_res = Decimal(
                str(total_resolution_time_by_cat.get(cat, 0.0) / count if count > 0 else 0.0)
            )
            cat_breakdown.append(
                CategoryBreakdown(
                    category=cat,
                    count=count,
                    percentage_of_total=pct,
                    average_resolution_time_hours=avg_cat_res,
                )
            )

        return ComplaintDashboard(
            hostel_id=hostel_id,
            hostel_name=hostel_name,
            period=period,
            generated_at=datetime.utcnow(),
            kpi=kpi,
            trend=trend,
            by_category=cat_breakdown,
            by_priority=priority_counts,
        )