# app/services/complaint/complaint_analytics_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, List, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import ComplaintRepository
from app.schemas.complaint import (
    ComplaintAnalytics,
    ResolutionMetrics,
    CategoryAnalysis,
    CategoryMetrics,
    ComplaintTrendPoint,
    ComplaintHeatmap,
    RoomComplaintCount,
)
from app.schemas.common.filters import DateRangeFilter
from app.schemas.common.enums import ComplaintStatus, Priority
from app.services.common import UnitOfWork


class ComplaintAnalyticsService:
    """
    Basic complaint analytics computed from svc_complaint.

    For heavy reporting, consider dedicated reporting/ETL paths;
    this is intended for dashboard-level stats.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_repo(self, uow: UnitOfWork) -> ComplaintRepository:
        return uow.get_repo(ComplaintRepository)

    # ------------------------------------------------------------------ #
    # High-level analytics
    # ------------------------------------------------------------------ #
    def get_analytics_for_hostel(
        self,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> ComplaintAnalytics:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            complaints = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters={"hostel_id": hostel_id},
            )

            # Filter by opened_at date range in Python for simplicity
            filtered = []
            for c in complaints:
                opened_date = c.opened_at.date() if c.opened_at else None
                if opened_date is None:
                    continue
                if period.start_date and opened_date < period.start_date:
                    continue
                if period.end_date and opened_date > period.end_date:
                    continue
                filtered.append(c)

            total = len(filtered)
            open_count = 0
            resolved_count = 0
            closed_count = 0

            total_resolved_hours = 0.0
            resolved_with_time = 0
            sla_breached = 0
            escalated = 0  # not explicitly tracked; left as 0

            category_counts: Dict[str, int] = {}
            total_resolution_time_by_cat: Dict[str, float] = {}

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

                if c.resolved_at and c.opened_at:
                    diff_hours = (c.resolved_at - c.opened_at).total_seconds() / 3600.0
                    total_resolved_hours += diff_hours
                    resolved_with_time += 1
                    total_resolution_time_by_cat[cat_key] = (
                        total_resolution_time_by_cat.get(cat_key, 0.0) + diff_hours
                    )

            avg_resolution = (
                Decimal(str(total_resolved_hours / resolved_with_time))
                if resolved_with_time > 0
                else Decimal("0")
            )

            resolution_rate = (
                Decimal(str(resolved_count / total * 100)) if total > 0 else Decimal("0")
            )
            same_day_rate = Decimal("0")  # can be derived if needed
            escalation_rate = Decimal("0")  # placeholder
            reopen_rate = Decimal("0")

            res_metrics = ResolutionMetrics(
                total_resolved=resolved_count,
                average_resolution_time_hours=avg_resolution,
                median_resolution_time_hours=Decimal("0"),
                fastest_resolution_hours=Decimal("0"),
                slowest_resolution_hours=Decimal("0"),
                resolution_rate=resolution_rate,
                same_day_resolution_rate=same_day_rate,
                escalation_rate=escalation_rate,
                reopen_rate=reopen_rate,
            )

            cat_metrics: List[CategoryMetrics] = []
            for cat, count in category_counts.items():
                avg_cat_res = Decimal(
                    str(
                        total_resolution_time_by_cat.get(cat, 0.0) / count
                        if count > 0
                        else 0.0
                    )
                )
                cat_metrics.append(
                    CategoryMetrics(
                        category=cat,
                        total_complaints=count,
                        open_complaints=0,
                        resolved_complaints=0,
                        average_resolution_time_hours=avg_cat_res,
                        resolution_rate=Decimal("0"),
                        percentage_of_total=Decimal(
                            str(count / total * 100) if total > 0 else "0"
                        ),
                    )
                )

            cat_analysis = CategoryAnalysis(
                categories=cat_metrics,
                most_common_category=cat_metrics[0].category if cat_metrics else "",
                most_problematic_category=cat_metrics[0].category if cat_metrics else "",
            )

            # Simple trend: group by date
            trend_by_date: Dict[str, Dict[str, int]] = {}
            for c in filtered:
                d = c.opened_at.date().isoformat() if c.opened_at else None
                if not d:
                    continue
                bucket = trend_by_date.setdefault(
                    d, {"total": 0, "open": 0, "resolved": 0, "urgent": 0, "high": 0, "medium": 0, "low": 0}
                )
                bucket["total"] += 1
                if c.status == ComplaintStatus.OPEN:
                    bucket["open"] += 1
                if c.status == ComplaintStatus.RESOLVED:
                    bucket["resolved"] += 1
                # Priority buckets
                if c.priority in (Priority.URGENT, Priority.CRITICAL):
                    bucket["urgent"] += 1
                elif c.priority == Priority.HIGH:
                    bucket["high"] += 1
                elif c.priority == Priority.MEDIUM:
                    bucket["medium"] += 1
                else:
                    bucket["low"] += 1

            trend_points: List[ComplaintTrendPoint] = []
            for d, vals in sorted(trend_by_date.items()):
                trend_points.append(
                    ComplaintTrendPoint(
                        period=d,
                        total_complaints=vals["total"],
                        open_complaints=vals["open"],
                        resolved_complaints=vals["resolved"],
                        urgent_count=vals["urgent"],
                        high_count=vals["high"],
                        medium_count=vals["medium"],
                        low_count=vals["low"],
                    )
                )

            priority_dist: Dict[str, int] = {}
            for c in filtered:
                key = c.priority.value if hasattr(c.priority, "value") else str(c.priority)
                priority_dist[key] = priority_dist.get(key, 0) + 1

            return ComplaintAnalytics(
                hostel_id=hostel_id,
                period_start=period.start_date or date.min,
                period_end=period.end_date or date.max,
                total_complaints=total,
                open_complaints=open_count,
                resolved_complaints=resolved_count,
                closed_complaints=closed_count,
                resolution_metrics=res_metrics,
                category_analysis=cat_analysis,
                priority_distribution=priority_dist,
                complaint_trend=trend_points,
                sla_compliance_rate=Decimal(
                    str((total - sla_breached) / total * 100) if total > 0 else "0"
                ),
                sla_breached_count=sla_breached,
                top_resolvers=[],
            )