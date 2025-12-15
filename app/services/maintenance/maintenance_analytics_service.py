# app/services/maintenance/maintenance_analytics_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, List, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import MaintenanceRepository
from app.schemas.common.filters import DateRangeFilter
from app.schemas.maintenance import (
    MaintenanceAnalytics,
    TrendPoint,
    CostTrendPoint,
    CategoryBreakdown,
    VendorPerformance,
)
from app.services.common import UnitOfWork


class MaintenanceAnalyticsService:
    """
    Basic analytics for maintenance requests.

    - Counts and completion rates
    - Cost totals
    - Simple trends by period
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_repo(self, uow: UnitOfWork) -> MaintenanceRepository:
        return uow.get_repo(MaintenanceRepository)

    def get_analytics_for_hostel(
        self,
        hostel_id: Optional[UUID],
        period: DateRangeFilter,
    ) -> MaintenanceAnalytics:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            filters: dict = {}
            if hostel_id:
                filters["hostel_id"] = hostel_id
            maints = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=filters or None,
            )

        # Filter by created_at or completion date
        filtered = []
        for m in maints:
            created = m.created_at.date()
            if period.start_date and created < period.start_date:
                continue
            if period.end_date and created > period.end_date:
                continue
            filtered.append(m)

        total_requests = len(filtered)
        completed_requests = 0
        pending_requests = 0
        total_cost = Decimal("0")
        total_completed_hours = 0.0
        completed_with_time = 0

        requests_by_category: Dict[str, int] = {}
        cost_by_category: Dict[str, Decimal] = {}

        for m in filtered:
            if m.status.name == "COMPLETED":
                completed_requests += 1
            else:
                pending_requests += 1

            if m.actual_cost:
                total_cost += m.actual_cost

            cat = m.category.value if hasattr(m.category, "value") else str(m.category)
            requests_by_category[cat] = requests_by_category.get(cat, 0) + 1
            if m.actual_cost:
                cost_by_category[cat] = cost_by_category.get(cat, Decimal("0")) + m.actual_cost

            if m.started_at and m.completed_at:
                diff_hours = (m.completed_at - m.started_at).total_seconds() / 3600.0
                total_completed_hours += diff_hours
                completed_with_time += 1

        average_cost = (total_cost / completed_requests) if completed_requests > 0 else Decimal("0")
        average_completion_time = (
            Decimal(str(total_completed_hours / completed_with_time))
            if completed_with_time > 0
            else Decimal("0")
        )
        completion_rate = (
            Decimal(str(completed_requests / total_requests * 100)) if total_requests > 0 else Decimal("0")
        )

        # Simple trend by date
        trend_by_date: Dict[str, Dict[str, int]] = {}
        for m in filtered:
            d = m.created_at.date().isoformat()
            bucket = trend_by_date.setdefault(d, {"requests": 0, "completed": 0})
            bucket["requests"] += 1
            if m.status.name == "COMPLETED":
                bucket["completed"] += 1

        request_trend: List[TrendPoint] = []
        cost_trend: List[CostTrendPoint] = []
        for d, vals in sorted(trend_by_date.items()):
            request_trend.append(
                TrendPoint(
                    period=d,
                    request_count=vals["requests"],
                    completed_count=vals["completed"],
                )
            )
            day_cost = sum(
                (mm.actual_cost or Decimal("0"))
                for mm in filtered
                if mm.created_at.date().isoformat() == d
            )
            cost_trend.append(
                CostTrendPoint(
                    period=d,
                    total_cost=day_cost,
                    request_count=vals["requests"],
                    average_cost=(day_cost / vals["requests"]) if vals["requests"] else Decimal("0"),
                )
            )

        category_breakdowns: List[CategoryBreakdown] = []
        for cat, count in requests_by_category.items():
            avg_cost_cat = (
                cost_by_category.get(cat, Decimal("0")) / count if count > 0 else Decimal("0")
            )
            category_breakdowns.append(
                CategoryBreakdown(
                    category=cat,
                    total_requests=count,
                    completed_requests=0,
                    total_cost=cost_by_category.get(cat, Decimal("0")),
                    average_cost=avg_cost_cat,
                    average_completion_time_hours=average_completion_time,
                )
            )

        return MaintenanceAnalytics(
            hostel_id=hostel_id,
            period=period,
            generated_at=datetime.now(timezone.utc),
            total_requests=total_requests,
            completed_requests=completed_requests,
            pending_requests=pending_requests,
            total_cost=total_cost,
            average_cost=average_cost,
            average_completion_time_hours=average_completion_time,
            completion_rate=completion_rate,
            requests_by_category=requests_by_category,
            cost_by_category=cost_by_category,
            request_trend=request_trend,
            cost_trend=cost_trend,
        )