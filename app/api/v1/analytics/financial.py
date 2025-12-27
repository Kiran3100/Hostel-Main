from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.analytics.financial_analytics import (
    BudgetComparison,
    CashflowSummary,
    FinancialRatios,
    FinancialReport,
    ProfitAndLossReport,
    RevenueBreakdown,
    ExpenseBreakdown,
    TaxSummary,
)
from app.services.analytics.financial_analytics_service import FinancialAnalyticsService

router = APIRouter(prefix="/financial", tags=["analytics:financial"])


def get_financial_analytics_service(
    db: Session = Depends(deps.get_db),
) -> FinancialAnalyticsService:
    return FinancialAnalyticsService(db=db)


@router.get(
    "/report",
    response_model=FinancialReport,
    summary="Get comprehensive financial report",
)
def get_financial_report(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: FinancialAnalyticsService = Depends(get_financial_analytics_service),
) -> Any:
    return service.get_financial_report(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/pnl",
    response_model=ProfitAndLossReport,
    summary="Get profit & loss statement",
)
def get_profit_and_loss(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: FinancialAnalyticsService = Depends(get_financial_analytics_service),
) -> Any:
    return service.get_profit_and_loss(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/cashflow",
    response_model=CashflowSummary,
    summary="Get cashflow summary",
)
def get_cashflow(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: FinancialAnalyticsService = Depends(get_financial_analytics_service),
) -> Any:
    return service.get_cashflow(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/ratios",
    response_model=FinancialRatios,
    summary="Get financial ratios",
)
def get_financial_ratios(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: FinancialAnalyticsService = Depends(get_financial_analytics_service),
) -> Any:
    return service.get_ratios(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/revenue",
    response_model=RevenueBreakdown,
    summary="Get revenue breakdown",
)
def get_revenue_breakdown(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: FinancialAnalyticsService = Depends(get_financial_analytics_service),
) -> Any:
    return service.get_revenue_breakdown(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/expenses",
    response_model=ExpenseBreakdown,
    summary="Get expense breakdown",
)
def get_expense_breakdown(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: FinancialAnalyticsService = Depends(get_financial_analytics_service),
) -> Any:
    return service.get_expense_breakdown(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/tax",
    response_model=TaxSummary,
    summary="Get tax summary",
)
def get_tax_summary(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: FinancialAnalyticsService = Depends(get_financial_analytics_service),
) -> Any:
    return service.get_tax_summary(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/budget",
    response_model=BudgetComparison,
    summary="Get budget vs actual comparison",
)
def get_budget_comparison(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: FinancialAnalyticsService = Depends(get_financial_analytics_service),
) -> Any:
    return service.get_budget_comparison(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )