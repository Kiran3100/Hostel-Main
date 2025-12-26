"""
Maintenance Cost Service

Tracks and reports on maintenance costs:
- Per-request costs
- Budget allocations and category budgets
- Expense reports
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceCostRepository
from app.schemas.common import DateRangeFilter
from app.schemas.maintenance import (
    CostTracking,
    BudgetAllocation,
    CategoryBudget,
    ExpenseReport,
    MonthlyExpense,
    VendorInvoice,
    ExpenseItem,
    CostAnalysis,
)
from app.core.exceptions import ValidationException


class MaintenanceCostService:
    """
    High-level service for maintenance cost & budget tracking.
    """

    def __init__(self, cost_repo: MaintenanceCostRepository) -> None:
        self.cost_repo = cost_repo

    # -------------------------------------------------------------------------
    # Per-request cost
    # -------------------------------------------------------------------------

    def record_cost_for_request(
        self,
        db: Session,
        tracking: CostTracking,
    ) -> CostTracking:
        obj = self.cost_repo.create_cost_record(
            db=db,
            data=tracking.model_dump(exclude_none=True),
        )
        return CostTracking.model_validate(obj)

    # -------------------------------------------------------------------------
    # Budgets
    # -------------------------------------------------------------------------

    def get_budget_allocation_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        fiscal_year: str,
    ) -> BudgetAllocation:
        data = self.cost_repo.get_budget_allocation(db, hostel_id, fiscal_year)
        if not data:
            raise ValidationException("Budget allocation not found")
        return BudgetAllocation.model_validate(data)

    def list_category_budgets_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        fiscal_year: str,
    ) -> List[CategoryBudget]:
        objs = self.cost_repo.get_category_budgets(db, hostel_id, fiscal_year)
        return [CategoryBudget.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Expense reports
    # -------------------------------------------------------------------------

    def get_expense_report(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> ExpenseReport:
        data = self.cost_repo.build_expense_report(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No expense report available for this period")
        return ExpenseReport.model_validate(data)

    def get_monthly_expenses(
        self,
        db: Session,
        hostel_id: UUID,
        fiscal_year: str,
    ) -> List[MonthlyExpense]:
        objs = self.cost_repo.get_monthly_expenses(db, hostel_id, fiscal_year)
        return [MonthlyExpense.model_validate(o) for o in objs]

    def get_cost_analysis(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> CostAnalysis:
        data = self.cost_repo.build_cost_analysis(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not data:
            raise ValidationException("No cost analysis available")
        return CostAnalysis.model_validate(data)