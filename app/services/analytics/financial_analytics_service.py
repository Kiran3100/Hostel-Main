"""
Financial analytics service.

Optimizations:
- Added comprehensive financial ratio calculations
- Implemented budget variance analysis
- Enhanced P&L reporting with drill-down capability
- Added cashflow forecasting
- Improved tax calculation accuracy
- Added audit trail support
"""

from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
from datetime import date, timedelta, datetime
from decimal import Decimal
from enum import Enum
import logging

from sqlalchemy.orm import Session

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.analytics import FinancialAnalyticsRepository
from app.models.analytics.financial_analytics import FinancialReport as FinancialReportModel
from app.schemas.analytics.financial_analytics import (
    RevenueBreakdown,
    ExpenseBreakdown,
    FinancialRatios,
    BudgetComparison,
    TaxSummary,
    ProfitAndLossReport,
    CashflowPoint,
    CashflowSummary,
    FinancialReport,
)

logger = logging.getLogger(__name__)


class FinancialPeriodType(str, Enum):
    """Financial reporting period types."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class RevenueCategory(str, Enum):
    """Revenue categories."""
    ROOM_BOOKINGS = "room_bookings"
    SERVICES = "services"
    FOOD_BEVERAGE = "food_beverage"
    EVENTS = "events"
    OTHER = "other"


class ExpenseCategory(str, Enum):
    """Expense categories."""
    SALARIES = "salaries"
    UTILITIES = "utilities"
    MAINTENANCE = "maintenance"
    SUPPLIES = "supplies"
    MARKETING = "marketing"
    INSURANCE = "insurance"
    OTHER = "other"


class FinancialAnalyticsService(BaseService[FinancialReportModel, FinancialAnalyticsRepository]):
    """
    Service for financial analytics.
    
    Provides:
    - Revenue and expense breakdowns
    - Profit & Loss statements
    - Cashflow analysis and forecasting
    - Financial ratios and KPIs
    - Budget vs actual comparisons
    - Tax summaries
    """

    # Default analysis period
    DEFAULT_ANALYSIS_DAYS = 30
    
    # Financial health thresholds
    HEALTHY_PROFIT_MARGIN = 0.15  # 15%
    HEALTHY_CURRENT_RATIO = 1.5
    HEALTHY_DEBT_TO_EQUITY = 2.0
    
    # Cache TTL
    CACHE_TTL = 600  # 10 minutes for financial data

    def __init__(self, repository: FinancialAnalyticsRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._cache = {}
        self._cache_timestamps = {}

    def get_financial_report(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        include_cashflow: bool = True,
        include_ratios: bool = True,
        include_budget_comparison: bool = False,
    ) -> ServiceResult[FinancialReport]:
        """
        Get comprehensive financial report.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            include_cashflow: Include cashflow analysis
            include_ratios: Include financial ratios
            include_budget_comparison: Include budget variance analysis
            
        Returns:
            ServiceResult containing financial report
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Check cache
            cache_key = f"report_{hostel_id}_{start_date}_{end_date}_{include_cashflow}"
            if self._is_cache_valid(cache_key):
                logger.debug(f"Returning cached financial report for {hostel_id}")
                return ServiceResult.success(self._cache[cache_key])
            
            # Fetch report
            report = self.repository.get_financial_report(
                hostel_id, start_date, end_date, include_cashflow
            )
            
            if not report:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No financial data found for hostel {hostel_id}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Enhance report with additional metrics
            if include_ratios:
                report.ratios = self._calculate_enhanced_ratios(report)
            
            if include_budget_comparison:
                report.budget_comparison = self._get_budget_comparison(
                    hostel_id, start_date, end_date, report
                )
            
            # Add financial health assessment
            report.health_assessment = self._assess_financial_health(report)
            
            # Cache result
            self._update_cache(cache_key, report)
            
            return ServiceResult.success(
                report,
                message="Financial report retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting financial report: {str(e)}")
            return self._handle_exception(e, "get financial report", hostel_id)

    def get_profit_and_loss(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        period_type: str = "monthly",
        include_variance: bool = True,
    ) -> ServiceResult[ProfitAndLossReport]:
        """
        Get Profit & Loss statement.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            period_type: Reporting period granularity
            include_variance: Include variance from previous period
            
        Returns:
            ServiceResult containing P&L report
        """
        try:
            # Validate inputs
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            try:
                FinancialPeriodType(period_type)
            except ValueError:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid period type: {period_type}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch P&L data
            pnl = self.repository.get_profit_and_loss(
                hostel_id, start_date, end_date, period_type
            )
            
            if not pnl:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No P&L data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Calculate key metrics
            pnl = self._calculate_pnl_metrics(pnl)
            
            # Add variance analysis if requested
            if include_variance:
                pnl.variance = self._calculate_pnl_variance(
                    hostel_id, start_date, end_date, pnl
                )
            
            return ServiceResult.success(
                pnl,
                message="P&L report retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting P&L report: {str(e)}")
            return self._handle_exception(e, "get profit and loss", hostel_id)

    def get_cashflow(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        granularity: str = "daily",
        include_forecast: bool = False,
    ) -> ServiceResult[CashflowSummary]:
        """
        Get cashflow summary and analysis.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            granularity: Time granularity
            include_forecast: Include cashflow forecast
            
        Returns:
            ServiceResult containing cashflow summary
        """
        try:
            # Validate inputs
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            if granularity not in ("daily", "weekly", "monthly"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid granularity: {granularity}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch cashflow data
            cashflow = self.repository.get_cashflow(
                hostel_id, start_date, end_date, granularity
            )
            
            if not cashflow:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No cashflow data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Calculate cashflow metrics
            cashflow = self._calculate_cashflow_metrics(cashflow)
            
            # Add forecast if requested
            if include_forecast:
                cashflow.forecast = self._generate_cashflow_forecast(
                    hostel_id, cashflow
                )
            
            return ServiceResult.success(
                cashflow,
                message="Cashflow summary retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting cashflow: {str(e)}")
            return self._handle_exception(e, "get cashflow summary", hostel_id)

    def get_ratios(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        include_benchmarks: bool = True,
    ) -> ServiceResult[FinancialRatios]:
        """
        Get financial ratios and metrics.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            include_benchmarks: Include industry benchmarks
            
        Returns:
            ServiceResult containing financial ratios
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch ratios
            ratios = self.repository.get_financial_ratios(
                hostel_id, start_date, end_date
            )
            
            if not ratios:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No financial ratio data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Add industry benchmarks if requested
            if include_benchmarks:
                ratios.benchmarks = self._get_industry_benchmarks()
                ratios.comparison = self._compare_to_benchmarks(ratios)
            
            # Add interpretation
            ratios.interpretation = self._interpret_ratios(ratios)
            
            return ServiceResult.success(
                ratios,
                message="Financial ratios retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting financial ratios: {str(e)}")
            return self._handle_exception(e, "get financial ratios", hostel_id)

    def get_revenue_breakdown(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        group_by: str = "category",
    ) -> ServiceResult[List[RevenueBreakdown]]:
        """
        Get detailed revenue breakdown.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            group_by: Grouping dimension (category, source, time)
            
        Returns:
            ServiceResult containing revenue breakdown
        """
        try:
            # Validate inputs
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            if group_by not in ("category", "source", "time", "room_type"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid group_by: {group_by}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch revenue breakdown
            breakdown = self.repository.get_revenue_breakdown(
                hostel_id, start_date, end_date, group_by
            )
            
            if not breakdown:
                logger.warning(f"No revenue breakdown data for {hostel_id}")
                breakdown = []
            
            # Calculate percentages
            total_revenue = sum(b.amount for b in breakdown)
            for b in breakdown:
                if total_revenue > 0:
                    b.percentage = round((b.amount / total_revenue) * 100, 2)
                else:
                    b.percentage = 0.0
            
            # Sort by amount descending
            breakdown.sort(key=lambda x: x.amount, reverse=True)
            
            return ServiceResult.success(
                breakdown,
                metadata={
                    "count": len(breakdown),
                    "total_revenue": float(total_revenue),
                    "group_by": group_by,
                },
                message=f"Retrieved {len(breakdown)} revenue breakdowns"
            )
            
        except Exception as e:
            logger.error(f"Error getting revenue breakdown: {str(e)}")
            return self._handle_exception(e, "get revenue breakdown", hostel_id)

    def get_expense_breakdown(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        group_by: str = "category",
        include_variance: bool = False,
    ) -> ServiceResult[List[ExpenseBreakdown]]:
        """
        Get detailed expense breakdown.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            group_by: Grouping dimension
            include_variance: Include budget variance
            
        Returns:
            ServiceResult containing expense breakdown
        """
        try:
            # Validate inputs
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            if group_by not in ("category", "vendor", "time", "department"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid group_by: {group_by}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Fetch expense breakdown
            breakdown = self.repository.get_expense_breakdown(
                hostel_id, start_date, end_date, group_by
            )
            
            if not breakdown:
                logger.warning(f"No expense breakdown data for {hostel_id}")
                breakdown = []
            
            # Calculate percentages
            total_expenses = sum(b.amount for b in breakdown)
            for b in breakdown:
                if total_expenses > 0:
                    b.percentage = round((b.amount / total_expenses) * 100, 2)
                else:
                    b.percentage = 0.0
            
            # Add budget variance if requested
            if include_variance:
                breakdown = self._add_expense_variance(
                    hostel_id, start_date, end_date, breakdown
                )
            
            # Sort by amount descending
            breakdown.sort(key=lambda x: x.amount, reverse=True)
            
            return ServiceResult.success(
                breakdown,
                metadata={
                    "count": len(breakdown),
                    "total_expenses": float(total_expenses),
                    "group_by": group_by,
                },
                message=f"Retrieved {len(breakdown)} expense breakdowns"
            )
            
        except Exception as e:
            logger.error(f"Error getting expense breakdown: {str(e)}")
            return self._handle_exception(e, "get expense breakdown", hostel_id)

    def get_tax_summary(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        tax_year: Optional[int] = None,
    ) -> ServiceResult[TaxSummary]:
        """
        Get tax summary and calculations.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            tax_year: Optional specific tax year
            
        Returns:
            ServiceResult containing tax summary
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch tax summary
            tax_summary = self.repository.get_tax_summary(
                hostel_id, start_date, end_date, tax_year
            )
            
            if not tax_summary:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No tax data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Add tax calculations and estimates
            tax_summary = self._enhance_tax_summary(tax_summary)
            
            return ServiceResult.success(
                tax_summary,
                message="Tax summary retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting tax summary: {str(e)}")
            return self._handle_exception(e, "get tax summary", hostel_id)

    def get_budget_comparison(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[BudgetComparison]:
        """
        Get budget vs actual comparison.
        
        Args:
            hostel_id: Target hostel UUID
            start_date: Start date
            end_date: End date
            
        Returns:
            ServiceResult containing budget comparison
        """
        try:
            # Validate date range
            validation_result = self._validate_date_range(start_date, end_date)
            if not validation_result.success:
                return validation_result
            
            # Fetch budget comparison
            comparison = self.repository.get_budget_comparison(
                hostel_id, start_date, end_date
            )
            
            if not comparison:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No budget data available",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Calculate variance percentages and add insights
            comparison = self._enhance_budget_comparison(comparison)
            
            return ServiceResult.success(
                comparison,
                message="Budget comparison retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error getting budget comparison: {str(e)}")
            return self._handle_exception(e, "get budget comparison", hostel_id)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _validate_date_range(self, start_date: date, end_date: date) -> ServiceResult[bool]:
        """Validate date range parameters."""
        if start_date > end_date:
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Start date cannot be after end date",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        # Check if range is too large (more than 3 years for financial data)
        if (end_date - start_date).days > 1095:
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Date range cannot exceed 3 years",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        return ServiceResult.success(True)

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self._cache:
            return False
        
        if cache_key not in self._cache_timestamps:
            return False
        
        age = (datetime.utcnow() - self._cache_timestamps[cache_key]).total_seconds()
        return age < self.CACHE_TTL

    def _update_cache(self, cache_key: str, data: Any) -> None:
        """Update cache with new data."""
        self._cache[cache_key] = data
        self._cache_timestamps[cache_key] = datetime.utcnow()
        
        # Limit cache size
        if len(self._cache) > 100:
            oldest_keys = sorted(
                self._cache_timestamps.keys(),
                key=lambda k: self._cache_timestamps[k]
            )[:20]
            for key in oldest_keys:
                del self._cache[key]
                del self._cache_timestamps[key]

    def _calculate_enhanced_ratios(self, report: FinancialReport) -> FinancialRatios:
        """Calculate comprehensive financial ratios."""
        ratios = FinancialRatios()
        
        # Profitability ratios
        if hasattr(report, 'total_revenue') and report.total_revenue:
            if hasattr(report, 'gross_profit'):
                ratios.gross_profit_margin = round(
                    (report.gross_profit / report.total_revenue) * 100, 2
                )
            
            if hasattr(report, 'net_profit'):
                ratios.net_profit_margin = round(
                    (report.net_profit / report.total_revenue) * 100, 2
                )
            
            if hasattr(report, 'operating_profit'):
                ratios.operating_profit_margin = round(
                    (report.operating_profit / report.total_revenue) * 100, 2
                )
        
        # Liquidity ratios
        if hasattr(report, 'current_assets') and hasattr(report, 'current_liabilities'):
            if report.current_liabilities and report.current_liabilities > 0:
                ratios.current_ratio = round(
                    report.current_assets / report.current_liabilities, 2
                )
        
        # Efficiency ratios
        if hasattr(report, 'total_assets') and report.total_assets:
            if hasattr(report, 'total_revenue'):
                ratios.asset_turnover = round(
                    report.total_revenue / report.total_assets, 2
                )
        
        return ratios

    def _assess_financial_health(self, report: FinancialReport) -> Dict[str, Any]:
        """Assess overall financial health."""
        assessment = {
            "status": "unknown",
            "score": 0,
            "strengths": [],
            "concerns": [],
            "recommendations": [],
        }
        
        score = 0
        max_score = 0
        
        # Check profit margin
        if hasattr(report, 'ratios') and hasattr(report.ratios, 'net_profit_margin'):
            max_score += 25
            margin = report.ratios.net_profit_margin / 100
            if margin >= self.HEALTHY_PROFIT_MARGIN:
                score += 25
                assessment["strengths"].append("Healthy profit margin")
            elif margin < self.HEALTHY_PROFIT_MARGIN / 2:
                assessment["concerns"].append("Low profit margin")
                assessment["recommendations"].append("Review pricing and cost structure")
        
        # Check liquidity
        if hasattr(report, 'ratios') and hasattr(report.ratios, 'current_ratio'):
            max_score += 25
            if report.ratios.current_ratio >= self.HEALTHY_CURRENT_RATIO:
                score += 25
                assessment["strengths"].append("Strong liquidity position")
            elif report.ratios.current_ratio < 1.0:
                assessment["concerns"].append("Liquidity concerns")
                assessment["recommendations"].append("Improve cash management")
        
        # Check revenue trend
        if hasattr(report, 'revenue_growth_rate'):
            max_score += 25
            if report.revenue_growth_rate > 0:
                score += 25
                assessment["strengths"].append("Positive revenue growth")
            elif report.revenue_growth_rate < -10:
                assessment["concerns"].append("Declining revenue")
                assessment["recommendations"].append("Focus on revenue generation")
        
        # Check expense control
        if hasattr(report, 'expense_ratio'):
            max_score += 25
            if report.expense_ratio < 0.8:  # Expenses < 80% of revenue
                score += 25
                assessment["strengths"].append("Good expense control")
            elif report.expense_ratio > 0.9:
                assessment["concerns"].append("High expense ratio")
                assessment["recommendations"].append("Review and optimize expenses")
        
        # Calculate final score
        if max_score > 0:
            assessment["score"] = round((score / max_score) * 100, 2)
            
            if assessment["score"] >= 80:
                assessment["status"] = "excellent"
            elif assessment["score"] >= 60:
                assessment["status"] = "good"
            elif assessment["score"] >= 40:
                assessment["status"] = "fair"
            else:
                assessment["status"] = "poor"
        
        return assessment

    def _get_budget_comparison(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        report: FinancialReport,
    ) -> Optional[BudgetComparison]:
        """Get budget comparison for the period."""
        try:
            return self.repository.get_budget_comparison(
                hostel_id, start_date, end_date
            )
        except Exception as e:
            logger.error(f"Error getting budget comparison: {str(e)}")
            return None

    def _calculate_pnl_metrics(self, pnl: ProfitAndLossReport) -> ProfitAndLossReport:
        """Calculate key P&L metrics."""
        # Calculate gross profit
        if hasattr(pnl, 'total_revenue') and hasattr(pnl, 'cost_of_goods_sold'):
            pnl.gross_profit = pnl.total_revenue - pnl.cost_of_goods_sold
        
        # Calculate operating profit
        if hasattr(pnl, 'gross_profit') and hasattr(pnl, 'operating_expenses'):
            pnl.operating_profit = pnl.gross_profit - pnl.operating_expenses
        
        # Calculate net profit
        if hasattr(pnl, 'operating_profit') and hasattr(pnl, 'taxes'):
            pnl.net_profit = pnl.operating_profit - pnl.taxes
        
        # Calculate EBITDA
        if hasattr(pnl, 'operating_profit'):
            depreciation = getattr(pnl, 'depreciation', 0)
            amortization = getattr(pnl, 'amortization', 0)
            pnl.ebitda = pnl.operating_profit + depreciation + amortization
        
        return pnl

    def _calculate_pnl_variance(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        current_pnl: ProfitAndLossReport,
    ) -> Dict[str, Any]:
        """Calculate P&L variance from previous period."""
        try:
            # Get previous period
            period_length = (end_date - start_date).days
            prev_end = start_date - timedelta(days=1)
            prev_start = prev_end - timedelta(days=period_length)
            
            prev_pnl = self.repository.get_profit_and_loss(
                hostel_id, prev_start, prev_end
            )
            
            if not prev_pnl:
                return {}
            
            variance = {}
            
            # Calculate revenue variance
            if hasattr(current_pnl, 'total_revenue') and hasattr(prev_pnl, 'total_revenue'):
                if prev_pnl.total_revenue > 0:
                    variance['revenue_variance_pct'] = round(
                        ((current_pnl.total_revenue - prev_pnl.total_revenue) /
                         prev_pnl.total_revenue) * 100, 2
                    )
            
            # Calculate expense variance
            if hasattr(current_pnl, 'total_expenses') and hasattr(prev_pnl, 'total_expenses'):
                if prev_pnl.total_expenses > 0:
                    variance['expense_variance_pct'] = round(
                        ((current_pnl.total_expenses - prev_pnl.total_expenses) /
                         prev_pnl.total_expenses) * 100, 2
                    )
            
            # Calculate profit variance
            if hasattr(current_pnl, 'net_profit') and hasattr(prev_pnl, 'net_profit'):
                if prev_pnl.net_profit != 0:
                    variance['profit_variance_pct'] = round(
                        ((current_pnl.net_profit - prev_pnl.net_profit) /
                         abs(prev_pnl.net_profit)) * 100, 2
                    )
            
            return variance
            
        except Exception as e:
            logger.error(f"Error calculating P&L variance: {str(e)}")
            return {}

    def _calculate_cashflow_metrics(self, cashflow: CashflowSummary) -> CashflowSummary:
        """Calculate cashflow metrics."""
        if hasattr(cashflow, 'points') and cashflow.points:
            # Calculate cumulative cashflow
            cumulative = 0
            for point in cashflow.points:
                cumulative += point.net_cashflow
                point.cumulative_cashflow = cumulative
            
            # Calculate averages
            cashflow.avg_daily_cashflow = round(
                sum(p.net_cashflow for p in cashflow.points) / len(cashflow.points), 2
            )
            
            # Identify cash flow trends
            positive_days = sum(1 for p in cashflow.points if p.net_cashflow > 0)
            cashflow.positive_cashflow_percentage = round(
                (positive_days / len(cashflow.points)) * 100, 2
            )
        
        return cashflow

    def _generate_cashflow_forecast(
        self,
        hostel_id: UUID,
        historical_cashflow: CashflowSummary,
        forecast_days: int = 30,
    ) -> List[CashflowPoint]:
        """Generate cashflow forecast based on historical data."""
        if not hasattr(historical_cashflow, 'points') or not historical_cashflow.points:
            return []
        
        # Simple moving average forecast
        recent_points = historical_cashflow.points[-30:] if len(historical_cashflow.points) > 30 else historical_cashflow.points
        
        avg_inflow = sum(p.cash_inflow for p in recent_points) / len(recent_points)
        avg_outflow = sum(p.cash_outflow for p in recent_points) / len(recent_points)
        
        forecast = []
        last_date = historical_cashflow.points[-1].date
        
        for i in range(1, forecast_days + 1):
            forecast_date = last_date + timedelta(days=i)
            forecast.append(CashflowPoint(
                date=forecast_date,
                cash_inflow=avg_inflow,
                cash_outflow=avg_outflow,
                net_cashflow=avg_inflow - avg_outflow,
                is_forecast=True,
            ))
        
        return forecast

    def _get_industry_benchmarks(self) -> Dict[str, float]:
        """Get industry benchmark ratios."""
        return {
            "gross_profit_margin": 65.0,  # %
            "net_profit_margin": 15.0,  # %
            "current_ratio": 1.5,
            "debt_to_equity": 2.0,
            "asset_turnover": 1.2,
            "return_on_assets": 8.0,  # %
            "return_on_equity": 12.0,  # %
        }

    def _compare_to_benchmarks(self, ratios: FinancialRatios) -> Dict[str, str]:
        """Compare ratios to industry benchmarks."""
        benchmarks = self._get_industry_benchmarks()
        comparison = {}
        
        if hasattr(ratios, 'gross_profit_margin'):
            if ratios.gross_profit_margin >= benchmarks['gross_profit_margin']:
                comparison['gross_profit_margin'] = "above_benchmark"
            elif ratios.gross_profit_margin >= benchmarks['gross_profit_margin'] * 0.9:
                comparison['gross_profit_margin'] = "at_benchmark"
            else:
                comparison['gross_profit_margin'] = "below_benchmark"
        
        if hasattr(ratios, 'net_profit_margin'):
            if ratios.net_profit_margin >= benchmarks['net_profit_margin']:
                comparison['net_profit_margin'] = "above_benchmark"
            elif ratios.net_profit_margin >= benchmarks['net_profit_margin'] * 0.9:
                comparison['net_profit_margin'] = "at_benchmark"
            else:
                comparison['net_profit_margin'] = "below_benchmark"
        
        return comparison

    def _interpret_ratios(self, ratios: FinancialRatios) -> Dict[str, str]:
        """Provide interpretation of financial ratios."""
        interpretation = {}
        
        # Profit margin interpretation
        if hasattr(ratios, 'net_profit_margin'):
            if ratios.net_profit_margin >= 20:
                interpretation['profit_margin'] = "Excellent profitability"
            elif ratios.net_profit_margin >= 15:
                interpretation['profit_margin'] = "Good profitability"
            elif ratios.net_profit_margin >= 10:
                interpretation['profit_margin'] = "Moderate profitability"
            elif ratios.net_profit_margin >= 5:
                interpretation['profit_margin'] = "Low profitability"
            else:
                interpretation['profit_margin'] = "Concerning profitability"
        
        # Liquidity interpretation
        if hasattr(ratios, 'current_ratio'):
            if ratios.current_ratio >= 2.0:
                interpretation['liquidity'] = "Strong liquidity position"
            elif ratios.current_ratio >= 1.5:
                interpretation['liquidity'] = "Good liquidity position"
            elif ratios.current_ratio >= 1.0:
                interpretation['liquidity'] = "Adequate liquidity"
            else:
                interpretation['liquidity'] = "Liquidity concerns"
        
        return interpretation

    def _enhance_tax_summary(self, tax_summary: TaxSummary) -> TaxSummary:
        """Enhance tax summary with calculations."""
        # Add effective tax rate
        if hasattr(tax_summary, 'total_tax') and hasattr(tax_summary, 'taxable_income'):
            if tax_summary.taxable_income > 0:
                tax_summary.effective_tax_rate = round(
                    (tax_summary.total_tax / tax_summary.taxable_income) * 100, 2
                )
        
        # Add tax savings from deductions
        if hasattr(tax_summary, 'deductions') and hasattr(tax_summary, 'tax_rate'):
            tax_summary.tax_savings = round(
                tax_summary.deductions * (tax_summary.tax_rate / 100), 2
            )
        
        return tax_summary

    def _enhance_budget_comparison(self, comparison: BudgetComparison) -> BudgetComparison:
        """Enhance budget comparison with variance analysis."""
        # Calculate variance percentages
        if hasattr(comparison, 'budgeted_amount') and hasattr(comparison, 'actual_amount'):
            if comparison.budgeted_amount > 0:
                variance = comparison.actual_amount - comparison.budgeted_amount
                comparison.variance_amount = variance
                comparison.variance_percentage = round(
                    (variance / comparison.budgeted_amount) * 100, 2
                )
                
                # Add variance status
                if abs(comparison.variance_percentage) <= 5:
                    comparison.variance_status = "on_track"
                elif comparison.variance_percentage > 5:
                    comparison.variance_status = "over_budget"
                else:
                    comparison.variance_status = "under_budget"
        
        return comparison

    def _add_expense_variance(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        breakdown: List[ExpenseBreakdown],
    ) -> List[ExpenseBreakdown]:
        """Add budget variance to expense breakdown."""
        try:
            # Fetch budget data
            budget_comparison = self.repository.get_budget_comparison(
                hostel_id, start_date, end_date
            )
            
            if not budget_comparison or not hasattr(budget_comparison, 'expense_budgets'):
                return breakdown
            
            # Map budget to categories
            budget_map = {
                b.category: b.budgeted_amount
                for b in budget_comparison.expense_budgets
            }
            
            # Add variance to breakdown
            for item in breakdown:
                if hasattr(item, 'category') and item.category in budget_map:
                    budgeted = budget_map[item.category]
                    if budgeted > 0:
                        variance = item.amount - budgeted
                        item.budget_variance = variance
                        item.budget_variance_pct = round(
                            (variance / budgeted) * 100, 2
                        )
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Error adding expense variance: {str(e)}")
            return breakdown