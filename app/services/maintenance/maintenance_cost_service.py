# app/services/maintenance/maintenance_cost_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol, List, Dict, Optional, Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.services import MaintenanceRepository
from app.schemas.common.filters import DateRangeFilter
from app.schemas.maintenance import (
    CostTracking,
    BudgetAllocation,
    CategoryBudget,
    ExpenseReport,
    MonthlyExpense,
    ExpenseItem,
    CostAnalysis,
)
from app.services.common import UnitOfWork


class BudgetStore(Protocol):
    """
    Store for hostel maintenance budgets by fiscal year and category.
    """

    def get_budget(self, hostel_id: UUID, fiscal_year: str) -> Optional[dict]: ...
    def save_budget(self, hostel_id: UUID, fiscal_year: str, data: dict) -> None: ...


class CostMetadataStore(Protocol):
    """
    Optional metadata store for materials/labor/vendor_charges breakdown per request.
    """

    def get_cost_metadata(self, maintenance_id: UUID) -> Optional[dict]: ...


class MaintenanceCostService:
    """
    Generate cost tracking and budget/expense analytics for maintenance.

    - Uses Maintenance.actual_cost as primary cost figure.
    - Optionally enriches with metadata from CostMetadataStore.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        budget_store: BudgetStore,
        cost_metadata_store: Optional[CostMetadataStore] = None,
    ) -> None:
        self._session_factory = session_factory
        self._budget_store = budget_store
        self._cost_meta = cost_metadata_store

    def _get_repo(self, uow: UnitOfWork) -> MaintenanceRepository:
        return uow.get_repo(MaintenanceRepository)

    # ------------------------------------------------------------------ #
    # Cost tracking per request
    # ------------------------------------------------------------------ #
    def get_cost_tracking(self, maintenance_id: UUID) -> CostTracking:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            m = repo.get(maintenance_id)
            if not m:
                raise ValueError(f"Maintenance {maintenance_id} not found")

        meta = self._cost_meta.get_cost_metadata(maintenance_id) if self._cost_meta else {}
        materials_cost = Decimal(str(meta.get("materials_cost", "0")))
        labor_cost = Decimal(str(meta.get("labor_cost", "0")))
        vendor_charges = Decimal(str(meta.get("vendor_charges", "0")))
        other_costs = Decimal(str(meta.get("other_costs", "0")))
        actual_cost = m.actual_cost or Decimal("0")
        estimated_cost = m.estimated_cost or Decimal("0")
        variance = actual_cost - estimated_cost
        variance_pct = Decimal("0")
        if estimated_cost > 0:
            variance_pct = (variance / estimated_cost) * 100

        return CostTracking(
            maintenance_id=maintenance_id,
            request_number=f"MTN-{str(maintenance_id)[:8].upper()}",
            estimated_cost=estimated_cost,
            approved_cost=estimated_cost,
            actual_cost=actual_cost,
            variance=variance,
            variance_percentage=variance_pct,
            within_budget=variance <= 0,
            materials_cost=materials_cost,
            labor_cost=labor_cost,
            vendor_charges=vendor_charges,
            other_costs=other_costs,
        )

    # ------------------------------------------------------------------ #
    # Budget allocation
    # ------------------------------------------------------------------ #
    def get_budget_allocation(self, hostel_id: UUID, fiscal_year: str) -> BudgetAllocation:
        record = self._budget_store.get_budget(hostel_id, fiscal_year)
        if not record:
            # Default zero budget allocation
            return BudgetAllocation(
                hostel_id=hostel_id,
                hostel_name="",
                fiscal_year=fiscal_year,
                total_budget=Decimal("0"),
                allocated_budget=Decimal("0"),
                spent_amount=Decimal("0"),
                remaining_budget=Decimal("0"),
                utilization_percentage=Decimal("0"),
                budget_by_category={},
            )
        return BudgetAllocation.model_validate(record)

    # ------------------------------------------------------------------ #
    # Expense report
    # ------------------------------------------------------------------ #
    def get_expense_report(
        self,
        hostel_id: Optional[UUID],
        period: DateRangeFilter,
    ) -> ExpenseReport:
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

        # Filter by completion_date range
        records = []
        for m in maints:
            comp_date = m.actual_completion_date
            if not comp_date:
                continue
            if period.start_date and comp_date < period.start_date:
                continue
            if period.end_date and comp_date > period.end_date:
                continue
            records.append(m)

        total_exp = Decimal("0")
        expenses_by_category: Dict[str, Decimal] = {}
        monthly_map: Dict[str, List[Decimal]] = {}
        expenses_by_priority: Dict[str, Decimal] = {}
        items: List[ExpenseItem] = []

        for m in records:
            cost = m.actual_cost or Decimal("0")
            total_exp += cost
            cat = m.category.value if hasattr(m.category, "value") else str(m.category)
            expenses_by_category[cat] = expenses_by_category.get(cat, Decimal("0")) + cost
            prio = m.priority.value if hasattr(m.priority, "value") else str(m.priority)
            expenses_by_priority[prio] = expenses_by_priority.get(prio, Decimal("0")) + cost

            month_key = m.actual_completion_date.strftime("%Y-%m")  # type: ignore[union-attr]
            monthly_map.setdefault(month_key, []).append(cost)

            items.append(
                ExpenseItem(
                    maintenance_id=m.id,
                    request_number=f"MTN-{str(m.id)[:8].upper()}",
                    title=m.title,
                    category=cat,
                    actual_cost=cost,
                    completion_date=m.actual_completion_date,  # type: ignore[arg-defined]
                )
            )

        monthly_expenses: List[MonthlyExpense] = []
        for month, costs in sorted(monthly_map.items()):
            total_month = sum(costs)
            monthly_expenses.append(
                MonthlyExpense(
                    month=month,
                    total_expenses=total_month,
                    request_count=len(costs),
                    average_cost=(total_month / len(costs)) if costs else Decimal("0"),
                )
            )

        avg_cost = (total_exp / len(records)) if records else Decimal("0")
        return ExpenseReport(
            hostel_id=hostel_id,
            report_period=period,
            generated_at=datetime.now(timezone.utc),
            total_expenses=total_exp,
            total_requests=len(records),
            average_cost_per_request=avg_cost,
            expenses_by_category=expenses_by_category,
            monthly_expenses=monthly_expenses,
            expenses_by_priority=expenses_by_priority,
            top_expensive_requests=sorted(items, key=lambda i: i.actual_cost, reverse=True)[:10],
        )

    # ------------------------------------------------------------------ #
    # Cost analysis
    # ------------------------------------------------------------------ #
    def get_cost_analysis(self, hostel_id: UUID, period: DateRangeFilter) -> CostAnalysis:
        report = self.get_expense_report(hostel_id, period)

        trend = "stable"
        trend_pct = Decimal("0")
        if len(report.monthly_expenses) >= 2:
            last = report.monthly_expenses[-1].total_expenses
            prev = report.monthly_expenses[-2].total_expenses
            if prev > 0:
                trend_pct = (last - prev) / prev * 100
                if trend_pct > 5:
                    trend = "increasing"
                elif trend_pct < -5:
                    trend = "decreasing"

        highest_cat = None
        most_freq_cat = None
        if report.expenses_by_category:
            highest_cat = max(report.expenses_by_category.items(), key=lambda kv: kv[1])[0]
            most_freq_cat = highest_cat  # for simplicity; could use count instead

        # For cost_per_student / cost_per_room we need additional data; set to 0 here,
        # can be enriched later by injecting hostel capacity/student count.
        return CostAnalysis(
            hostel_id=hostel_id,
            analysis_period=period,
            cost_trend=trend,
            trend_percentage=trend_pct,
            highest_cost_category=highest_cat or "",
            most_frequent_category=most_freq_cat or "",
            cost_per_student=Decimal("0"),
            cost_per_room=Decimal("0"),
            comparison_to_previous_period=Decimal("0"),
        )