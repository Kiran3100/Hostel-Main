"""
Financial Analytics API Endpoints.

Provides comprehensive financial analytics including:
- Profit & Loss statements
- Cashflow analysis
- Financial ratios
- Revenue and expense breakdowns
- Tax summaries
- Budget comparisons
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from app.schemas.analytics.financial_analytics import (
    BudgetComparison,
    CashflowSummary,
    ExpenseBreakdown,
    FinancialRatios,
    FinancialReport,
    ProfitAndLossReport,
    RevenueBreakdown,
    TaxSummary,
)
from app.services.analytics.financial_analytics_service import FinancialAnalyticsService

from .dependencies import (
    AdminUser,
    HostelFilter,
    RequiredDateRange,
    get_financial_analytics_service,
    handle_analytics_error,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/financial", tags=["analytics:financial"])

# Type alias for service dependency
FinancialService = Annotated[
    FinancialAnalyticsService,
    Depends(get_financial_analytics_service),
]


@router.get(
    "/report",
    response_model=FinancialReport,
    summary="Get comprehensive financial report",
    description="""
    Retrieves a comprehensive financial report including:
    - Revenue summary
    - Expense summary
    - Profit metrics
    - Key financial indicators
    - Period-over-period comparison
    
    Date range is required for accurate financial reporting.
    """,
    responses={
        200: {"description": "Financial report retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        422: {"description": "Invalid date range"},
    },
)
def get_financial_report(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    _admin: AdminUser,
    service: FinancialService,
) -> FinancialReport:
    """
    Get comprehensive financial report.
    
    Aggregates all financial data into a complete report
    for the specified date range.
    """
    try:
        return service.get_financial_report(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching financial report: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/pnl",
    response_model=ProfitAndLossReport,
    summary="Get profit & loss statement",
    description="""
    Retrieves a detailed Profit & Loss statement:
    - Gross revenue by category
    - Operating expenses by category
    - Gross profit
    - Operating profit
    - Net profit
    - Profit margins
    """,
    responses={
        200: {"description": "P&L statement retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_profit_and_loss(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    _admin: AdminUser,
    service: FinancialService,
) -> ProfitAndLossReport:
    """
    Get profit and loss statement.
    
    Returns detailed P&L breakdown for financial
    analysis and reporting purposes.
    """
    try:
        return service.get_profit_and_loss(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching P&L report: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/cashflow",
    response_model=CashflowSummary,
    summary="Get cashflow summary",
    description="""
    Retrieves cashflow analysis including:
    - Operating cash flow
    - Cash inflows by source
    - Cash outflows by category
    - Net cash position
    - Cash flow trends
    """,
    responses={
        200: {"description": "Cashflow summary retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_cashflow(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    _admin: AdminUser,
    service: FinancialService,
) -> CashflowSummary:
    """
    Get cashflow summary.
    
    Provides cash movement analysis for liquidity
    management and financial planning.
    """
    try:
        return service.get_cashflow(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching cashflow: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/ratios",
    response_model=FinancialRatios,
    summary="Get financial ratios",
    description="""
    Retrieves key financial ratios:
    - Profitability ratios (gross margin, net margin, ROI)
    - Efficiency ratios (RevPAR, ADR, GOPPAR)
    - Liquidity ratios
    - Operating ratios
    """,
    responses={
        200: {"description": "Financial ratios retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_financial_ratios(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    _admin: AdminUser,
    service: FinancialService,
) -> FinancialRatios:
    """
    Get financial ratios.
    
    Returns industry-standard financial ratios
    for benchmarking and performance analysis.
    """
    try:
        return service.get_ratios(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching financial ratios: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/revenue",
    response_model=RevenueBreakdown,
    summary="Get revenue breakdown",
    description="""
    Retrieves detailed revenue breakdown:
    - Room revenue
    - Ancillary services
    - Food & beverage
    - Events and activities
    - Other revenue streams
    
    Includes trends and comparisons.
    """,
    responses={
        200: {"description": "Revenue breakdown retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_revenue_breakdown(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    _admin: AdminUser,
    service: FinancialService,
) -> RevenueBreakdown:
    """
    Get revenue breakdown by category.
    
    Provides detailed analysis of revenue streams
    for identifying growth opportunities.
    """
    try:
        return service.get_revenue_breakdown(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching revenue breakdown: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/expenses",
    response_model=ExpenseBreakdown,
    summary="Get expense breakdown",
    description="""
    Retrieves detailed expense breakdown:
    - Payroll and staffing
    - Utilities
    - Maintenance and repairs
    - Marketing and sales
    - Administrative costs
    - Other operating expenses
    """,
    responses={
        200: {"description": "Expense breakdown retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_expense_breakdown(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    _admin: AdminUser,
    service: FinancialService,
) -> ExpenseBreakdown:
    """
    Get expense breakdown by category.
    
    Provides detailed analysis of operating costs
    for cost control and optimization.
    """
    try:
        return service.get_expense_breakdown(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching expense breakdown: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/tax",
    response_model=TaxSummary,
    summary="Get tax summary",
    description="""
    Retrieves tax-related summary:
    - Tax collected (GST, VAT, etc.)
    - Tax payable
    - Tax credits
    - Filing deadlines
    - Compliance status
    """,
    responses={
        200: {"description": "Tax summary retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_tax_summary(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    _admin: AdminUser,
    service: FinancialService,
) -> TaxSummary:
    """
    Get tax summary.
    
    Provides tax-related metrics for compliance
    monitoring and financial planning.
    """
    try:
        return service.get_tax_summary(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching tax summary: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/budget",
    response_model=BudgetComparison,
    summary="Get budget vs actual comparison",
    description="""
    Retrieves budget vs actual comparison:
    - Budget targets by category
    - Actual performance
    - Variance analysis
    - Year-to-date tracking
    - Forecast adjustments
    """,
    responses={
        200: {"description": "Budget comparison retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_budget_comparison(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    _admin: AdminUser,
    service: FinancialService,
) -> BudgetComparison:
    """
    Get budget vs actual comparison.
    
    Enables monitoring of financial performance
    against budgeted targets.
    """
    try:
        return service.get_budget_comparison(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching budget comparison: {e}")
        raise handle_analytics_error(e)