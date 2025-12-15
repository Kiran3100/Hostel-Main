# app/services/analytics/financial_analytics_service.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import PaymentRepository
from app.repositories.services import MaintenanceRepository
from app.schemas.analytics.financial_analytics import (
    FinancialReport,
    RevenueBreakdown,
    ExpenseBreakdown,
    ProfitAndLossReport,
    CashflowSummary,
    CashflowPoint,
)
from app.schemas.common.enums import PaymentStatus, PaymentType
from app.schemas.common.filters import DateRangeFilter
from app.services.common import UnitOfWork


class FinancialAnalyticsService:
    """
    Basic financial analytics using txn_payment and svc_maintenance:

    - Revenue breakdown by type/payment_type
    - Maintenance expenses as primary expense category
    - Simple P&L and cashflow summary
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_payment_repo(self, uow: UnitOfWork) -> PaymentRepository:
        return uow.get_repo(PaymentRepository)

    def _get_maintenance_repo(self, uow: UnitOfWork) -> MaintenanceRepository:
        return uow.get_repo(MaintenanceRepository)

    def _today(self) -> date:
        return date.today()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_financial_report(
        self,
        *,
        scope_type: str,          # 'hostel' or 'platform'
        scope_id: Optional[UUID],
        period: DateRangeFilter,
    ) -> FinancialReport:
        """
        Compute a FinancialReport for a hostel or platform over a period.

        For 'platform' scope, aggregates across all hostels.
        """
        with UnitOfWork(self._session_factory) as uow:
            pay_repo = self._get_payment_repo(uow)
            maint_repo = self._get_maintenance_repo(uow)

            pay_filters: Dict[str, object] = {}
            maint_filters: Dict[str, object] = {}
            if scope_type == "hostel" and scope_id:
                pay_filters["hostel_id"] = scope_id
                maint_filters["hostel_id"] = scope_id

            payments = pay_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=pay_filters or None,
            )
            maints = maint_repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=maint_filters or None,
            )

        start = period.start_date or date.min
        end = period.end_date or date.max

        # Revenue: COMPLETED payments with paid_at in [start,end]
        payments_in_period = []
        for p in payments:
            if p.payment_status != PaymentStatus.COMPLETED or not p.paid_at:
                continue
            d = p.paid_at.date()
            if d < start or d > end:
                continue
            payments_in_period.append(p)

        # Revenue breakdown by PaymentType
        booking_revenue = rent_revenue = mess_revenue = other_revenue = Decimal("0")
        revenue_by_type: Dict[str, Decimal] = {}

        for p in payments_in_period:
            if p.payment_type == PaymentType.BOOKING_ADVANCE:
                booking_revenue += p.amount
            elif p.payment_type == PaymentType.RENT:
                rent_revenue += p.amount
            elif p.payment_type == PaymentType.MESS_CHARGES:
                mess_revenue += p.amount
            else:
                other_revenue += p.amount

            key = p.payment_type.value if hasattr(p.payment_type, "value") else str(p.payment_type)
            revenue_by_type[key] = revenue_by_type.get(key, Decimal("0")) + p.amount

        total_revenue = booking_revenue + rent_revenue + mess_revenue + other_revenue

        revenue_breakdown = RevenueBreakdown(
            total_revenue=total_revenue,
            booking_revenue=booking_revenue,
            rent_revenue=rent_revenue,
            mess_revenue=mess_revenue,
            other_revenue=other_revenue,
            revenue_by_hostel={},  # not broken down here
            revenue_by_payment_type={k: v for k, v in revenue_by_type.items()},
        )

        # Expenses from Maintenance.actual_cost
        expenses_in_period = []
        for m in maints:
            if not m.actual_completion_date or not m.actual_cost:
                continue
            d = m.actual_completion_date
            if d < start or d > end:
                continue
            expenses_in_period.append(m)

        maintenance_expenses = Decimal("0")
        expenses_by_category: Dict[str, Decimal] = {}
        for m in expenses_in_period:
            maintenance_expenses += m.actual_cost or Decimal("0")
            cat = m.category.value if hasattr(m.category, "value") else str(m.category)
            expenses_by_category[cat] = expenses_by_category.get(cat, Decimal("0")) + (m.actual_cost or Decimal("0"))

        total_expenses = maintenance_expenses  # others set to 0 here

        expense_breakdown = ExpenseBreakdown(
            total_expenses=total_expenses,
            maintenance_expenses=maintenance_expenses,
            staff_expenses=Decimal("0"),
            utility_expenses=Decimal("0"),
            other_expenses=Decimal("0"),
            expenses_by_hostel={},     # not broken down
            expenses_by_category=expenses_by_category,
        )

        gross_profit = total_revenue - total_expenses
        net_profit = gross_profit  # no tax/other adjustments modeled
        profit_margin = (
            (net_profit / total_revenue * 100) if total_revenue > 0 else Decimal("0")
        )

        pnl = ProfitAndLossReport(
            scope_type=scope_type,
            scope_id=scope_id,
            period=period,
            generated_at=datetime.utcnow(),
            revenue=revenue_breakdown,
            expenses=expense_breakdown,
            gross_profit=gross_profit,
            net_profit=net_profit,
            profit_margin_percentage=profit_margin,
        )

        # Cashflow summary: simple inflow(outflow) per day
        inflows = total_revenue
        outflows = total_expenses
        opening_balance = Decimal("0")
        closing_balance = opening_balance + inflows - outflows

        # Daily timeseries
        daily_in: Dict[date, Decimal] = {}
        daily_out: Dict[date, Decimal] = {}

        for p in payments_in_period:
            d = p.paid_at.date()
            daily_in[d] = daily_in.get(d, Decimal("0")) + p.amount

        for m in expenses_in_period:
            d = m.actual_completion_date
            daily_out[d] = daily_out.get(d, Decimal("0")) + (m.actual_cost or Decimal("0"))

        cashflow_points: List[CashflowPoint] = []
        cur = start
        while cur <= end:
            inflow = daily_in.get(cur, Decimal("0"))
            outflow = daily_out.get(cur, Decimal("0"))
            cashflow_points.append(
                CashflowPoint(
                    date=cur,
                    inflow=inflow,
                    outflow=outflow,
                    net_flow=inflow - outflow,
                )
            )
            cur += timedelta(days=1)

        cashflow = CashflowSummary(
            scope_type=scope_type,
            scope_id=scope_id,
            period=period,
            generated_at=datetime.utcnow(),
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            inflows=inflows,
            outflows=outflows,
            inflow_breakdown={"payments": inflows},
            outflow_breakdown={"maintenance": outflows},
            cashflow_timeseries=cashflow_points,
        )

        # Ratios (very basic)
        # For collection_rate we compare completed vs all payments in period (created_at)
        # Re-load payments for the period on created_at
        total_billed = Decimal("0")
        total_billed_completed = Decimal("0")
        for p in payments:
            d = p.created_at.date()
            if d < start or d > end:
                continue
            total_billed += p.amount
            if p.payment_status == PaymentStatus.COMPLETED:
                total_billed_completed += p.amount

        collection_rate = (
            (total_billed_completed / total_billed * 100) if total_billed > 0 else Decimal("0")
        )
        overdue_ratio = Decimal("0")  # could be computed from pending+due_date < today

        financial_report = FinancialReport(
            scope_type=scope_type,
            scope_id=scope_id,
            period=period,
            generated_at=datetime.utcnow(),
            pnl_report=pnl,
            cashflow=cashflow,
            collection_rate=collection_rate,
            overdue_ratio=overdue_ratio,
            avg_revenue_per_student=Decimal("0"),
            avg_revenue_per_bed=Decimal("0"),
        )
        return financial_report