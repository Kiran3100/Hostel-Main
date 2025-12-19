"""
Financial Analytics Repository for P&L and cashflow tracking.

Provides comprehensive financial analytics with:
- Revenue and expense breakdown management
- Profit & Loss statement generation
- Cashflow analysis and tracking
- Budget vs actual comparison
- Tax summary management
- Financial health scoring
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import and_, or_, func, select, case, desc
from sqlalchemy.orm import Session, joinedload
from uuid import UUID

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.models.analytics.financial_analytics import (
    RevenueBreakdown,
    ExpenseBreakdown,
    FinancialRatios,
    ProfitAndLossStatement,
    CashflowPoint,
    CashflowSummary,
    BudgetComparison,
    TaxSummary,
    FinancialReport,
)


class FinancialAnalyticsRepository(BaseRepository):
    """Repository for financial analytics operations."""
    
    def __init__(self, db: Session):
        super().__init__(db)
    
    # ==================== Revenue Breakdown ====================
    
    def create_revenue_breakdown(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        revenue_data: Dict[str, Any]
    ) -> RevenueBreakdown:
        """Create or update revenue breakdown."""
        # Calculate derived fields
        collection_rate = self._calculate_collection_rate(
            revenue_data.get('billed_amount', 0),
            revenue_data.get('collected_amount', 0)
        )
        revenue_data['collection_rate'] = collection_rate
        
        primary_source = self._identify_primary_revenue_source(revenue_data)
        revenue_data['primary_revenue_source'] = primary_source
        
        concentration_risk = self._assess_revenue_concentration_risk(revenue_data)
        revenue_data['revenue_concentration_risk'] = concentration_risk
        
        existing = self.db.query(RevenueBreakdown).filter(
            and_(
                RevenueBreakdown.hostel_id == hostel_id if hostel_id else RevenueBreakdown.hostel_id.is_(None),
                RevenueBreakdown.period_start == period_start,
                RevenueBreakdown.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in revenue_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        breakdown = RevenueBreakdown(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **revenue_data
        )
        
        self.db.add(breakdown)
        self.db.commit()
        self.db.refresh(breakdown)
        
        return breakdown
    
    def get_revenue_breakdown(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Optional[RevenueBreakdown]:
        """Get revenue breakdown for period."""
        return self.db.query(RevenueBreakdown).filter(
            and_(
                RevenueBreakdown.hostel_id == hostel_id if hostel_id else RevenueBreakdown.hostel_id.is_(None),
                RevenueBreakdown.period_start == period_start,
                RevenueBreakdown.period_end == period_end
            )
        ).first()
    
    def get_revenue_trend(
        self,
        hostel_id: Optional[UUID],
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """Get revenue trend over time."""
        breakdowns = self.db.query(RevenueBreakdown).filter(
            and_(
                RevenueBreakdown.hostel_id == hostel_id if hostel_id else RevenueBreakdown.hostel_id.is_(None),
                RevenueBreakdown.period_start >= start_date,
                RevenueBreakdown.period_end <= end_date
            )
        ).order_by(RevenueBreakdown.period_start.asc()).all()
        
        return [
            {
                'period_start': b.period_start,
                'period_end': b.period_end,
                'total_revenue': float(b.total_revenue),
                'collection_rate': float(b.collection_rate),
                'primary_source': b.primary_revenue_source,
            }
            for b in breakdowns
        ]
    
    def _calculate_collection_rate(
        self,
        billed: Decimal,
        collected: Decimal
    ) -> Decimal:
        """Calculate collection efficiency rate."""
        if billed == 0:
            return Decimal('0.00')
        
        rate = (collected / billed) * 100
        return Decimal(str(round(rate, 2)))
    
    def _identify_primary_revenue_source(
        self,
        revenue_data: Dict[str, Any]
    ) -> str:
        """Identify the largest revenue source."""
        sources = {
            'booking': revenue_data.get('booking_revenue', 0),
            'rent': revenue_data.get('rent_revenue', 0),
            'mess': revenue_data.get('mess_revenue', 0),
            'utility': revenue_data.get('utility_revenue', 0),
            'late_fee': revenue_data.get('late_fee_revenue', 0),
            'other': revenue_data.get('other_revenue', 0),
        }
        
        if not any(sources.values()):
            return 'none'
        
        return max(sources.items(), key=lambda x: x[1])[0]
    
    def _assess_revenue_concentration_risk(
        self,
        revenue_data: Dict[str, Any]
    ) -> str:
        """Assess revenue concentration risk level."""
        total = float(revenue_data.get('total_revenue', 0))
        
        if total == 0:
            return 'unknown'
        
        sources = {
            'booking': float(revenue_data.get('booking_revenue', 0)),
            'rent': float(revenue_data.get('rent_revenue', 0)),
            'mess': float(revenue_data.get('mess_revenue', 0)),
            'utility': float(revenue_data.get('utility_revenue', 0)),
            'late_fee': float(revenue_data.get('late_fee_revenue', 0)),
            'other': float(revenue_data.get('other_revenue', 0)),
        }
        
        # Calculate percentage of largest source
        max_source_pct = (max(sources.values()) / total) * 100
        
        if max_source_pct > 70:
            return 'high'
        elif max_source_pct > 50:
            return 'moderate'
        else:
            return 'low'
    
    # ==================== Expense Breakdown ====================
    
    def create_expense_breakdown(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        expense_data: Dict[str, Any]
    ) -> ExpenseBreakdown:
        """Create or update expense breakdown."""
        # Identify largest expense
        largest_category = self._identify_largest_expense_category(expense_data)
        expense_data['largest_expense_category'] = largest_category
        
        # Calculate staff expense ratio
        staff_ratio = self._calculate_expense_ratio(
            expense_data.get('staff_expenses', 0),
            expense_data.get('total_expenses', 0)
        )
        expense_data['expense_ratio_staff'] = staff_ratio
        
        existing = self.db.query(ExpenseBreakdown).filter(
            and_(
                ExpenseBreakdown.hostel_id == hostel_id if hostel_id else ExpenseBreakdown.hostel_id.is_(None),
                ExpenseBreakdown.period_start == period_start,
                ExpenseBreakdown.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in expense_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        breakdown = ExpenseBreakdown(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **expense_data
        )
        
        self.db.add(breakdown)
        self.db.commit()
        self.db.refresh(breakdown)
        
        return breakdown
    
    def get_expense_breakdown(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Optional[ExpenseBreakdown]:
        """Get expense breakdown for period."""
        return self.db.query(ExpenseBreakdown).filter(
            and_(
                ExpenseBreakdown.hostel_id == hostel_id if hostel_id else ExpenseBreakdown.hostel_id.is_(None),
                ExpenseBreakdown.period_start == period_start,
                ExpenseBreakdown.period_end == period_end
            )
        ).first()
    
    def _identify_largest_expense_category(
        self,
        expense_data: Dict[str, Any]
    ) -> str:
        """Identify the largest expense category."""
        categories = {
            'maintenance': expense_data.get('maintenance_expenses', 0),
            'staff': expense_data.get('staff_expenses', 0),
            'utility': expense_data.get('utility_expenses', 0),
            'supply': expense_data.get('supply_expenses', 0),
            'marketing': expense_data.get('marketing_expenses', 0),
            'administrative': expense_data.get('administrative_expenses', 0),
            'other': expense_data.get('other_expenses', 0),
        }
        
        if not any(categories.values()):
            return 'none'
        
        return max(categories.items(), key=lambda x: x[1])[0]
    
    def _calculate_expense_ratio(
        self,
        category_expense: Decimal,
        total_expense: Decimal
    ) -> Decimal:
        """Calculate expense ratio as percentage."""
        if total_expense == 0:
            return Decimal('0.00')
        
        ratio = (category_expense / total_expense) * 100
        return Decimal(str(round(ratio, 2)))
    
    # ==================== Financial Ratios ====================
    
    def create_financial_ratios(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        ratios_data: Dict[str, Any]
    ) -> FinancialRatios:
        """Create or update financial ratios."""
        # Calculate profitability status
        profitability_status = self._assess_profitability_status(ratios_data)
        ratios_data['profitability_status'] = profitability_status
        
        existing = self.db.query(FinancialRatios).filter(
            and_(
                FinancialRatios.hostel_id == hostel_id if hostel_id else FinancialRatios.hostel_id.is_(None),
                FinancialRatios.period_start == period_start,
                FinancialRatios.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in ratios_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        ratios = FinancialRatios(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **ratios_data
        )
        
        self.db.add(ratios)
        self.db.commit()
        self.db.refresh(ratios)
        
        return ratios
    
    def _assess_profitability_status(
        self,
        ratios_data: Dict[str, Any]
    ) -> str:
        """Assess overall profitability status."""
        net_margin = float(ratios_data.get('net_profit_margin', 0))
        
        if net_margin >= 20:
            return 'excellent'
        elif net_margin >= 15:
            return 'good'
        elif net_margin >= 10:
            return 'satisfactory'
        elif net_margin >= 5:
            return 'marginal'
        elif net_margin > 0:
            return 'break_even'
        else:
            return 'loss'
    
    # ==================== Profit & Loss Statement ====================
    
    def create_pnl_statement(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        revenue_breakdown_id: Optional[UUID],
        expense_breakdown_id: Optional[UUID],
        financial_ratios_id: Optional[UUID]
    ) -> ProfitAndLossStatement:
        """Create or update P&L statement."""
        # Get related data
        revenue = self.db.query(RevenueBreakdown).filter(
            RevenueBreakdown.id == revenue_breakdown_id
        ).first() if revenue_breakdown_id else None
        
        expense = self.db.query(ExpenseBreakdown).filter(
            ExpenseBreakdown.id == expense_breakdown_id
        ).first() if expense_breakdown_id else None
        
        # Calculate P&L metrics
        total_revenue = float(revenue.total_revenue) if revenue else 0
        total_expenses = float(expense.total_expenses) if expense else 0
        
        gross_profit = Decimal(str(total_revenue - total_expenses))
        operating_profit = gross_profit  # Simplified
        net_profit = operating_profit  # Simplified
        
        # Calculate margins
        gross_margin = self._calculate_margin(gross_profit, total_revenue)
        operating_margin = self._calculate_margin(operating_profit, total_revenue)
        net_margin = self._calculate_margin(net_profit, total_revenue)
        
        # Profitability flag
        is_profitable = float(net_profit) > 0
        
        # Break-even analysis
        break_even_revenue = Decimal(str(total_expenses))
        revenue_above_break_even = Decimal(str(max(0, total_revenue - total_expenses)))
        
        # Performance summary
        performance_summary = {
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'net_profit': float(net_profit),
            'is_profitable': is_profitable,
            'profit_margin': float(net_margin),
        }
        
        existing = self.db.query(ProfitAndLossStatement).filter(
            and_(
                ProfitAndLossStatement.hostel_id == hostel_id if hostel_id else ProfitAndLossStatement.hostel_id.is_(None),
                ProfitAndLossStatement.period_start == period_start,
                ProfitAndLossStatement.period_end == period_end
            )
        ).first()
        
        pnl_data = {
            'revenue_breakdown_id': revenue_breakdown_id,
            'expense_breakdown_id': expense_breakdown_id,
            'financial_ratios_id': financial_ratios_id,
            'gross_profit': gross_profit,
            'operating_profit': operating_profit,
            'net_profit': net_profit,
            'gross_profit_margin': gross_margin,
            'operating_profit_margin': operating_margin,
            'net_profit_margin': net_margin,
            'is_profitable': is_profitable,
            'break_even_revenue': break_even_revenue,
            'revenue_above_break_even': revenue_above_break_even,
            'performance_summary': performance_summary,
            'calculated_at': datetime.utcnow(),
        }
        
        if existing:
            for key, value in pnl_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        pnl = ProfitAndLossStatement(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **pnl_data
        )
        
        self.db.add(pnl)
        self.db.commit()
        self.db.refresh(pnl)
        
        return pnl
    
    def get_pnl_statement(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Optional[ProfitAndLossStatement]:
        """Get P&L statement for period."""
        return self.db.query(ProfitAndLossStatement).filter(
            and_(
                ProfitAndLossStatement.hostel_id == hostel_id if hostel_id else ProfitAndLossStatement.hostel_id.is_(None),
                ProfitAndLossStatement.period_start == period_start,
                ProfitAndLossStatement.period_end == period_end
            )
        ).first()
    
    def _calculate_margin(
        self,
        profit: Decimal,
        revenue: float
    ) -> Decimal:
        """Calculate profit margin percentage."""
        if revenue == 0:
            return Decimal('0.0000')
        
        margin = (float(profit) / revenue) * 100
        return Decimal(str(round(margin, 4)))
    
    # ==================== Cashflow Analysis ====================
    
    def create_cashflow_summary(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        cashflow_data: Dict[str, Any]
    ) -> CashflowSummary:
        """Create or update cashflow summary."""
        # Calculate cashflow health
        cashflow_health = self._assess_cashflow_health(cashflow_data)
        cashflow_data['cashflow_health'] = cashflow_health
        
        # Calculate burn rate
        burn_rate_days = self._calculate_burn_rate(cashflow_data)
        cashflow_data['burn_rate_days'] = burn_rate_days
        
        existing = self.db.query(CashflowSummary).filter(
            and_(
                CashflowSummary.hostel_id == hostel_id if hostel_id else CashflowSummary.hostel_id.is_(None),
                CashflowSummary.period_start == period_start,
                CashflowSummary.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in cashflow_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        summary = CashflowSummary(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **cashflow_data
        )
        
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)
        
        return summary
    
    def add_cashflow_points(
        self,
        cashflow_summary_id: UUID,
        points: List[Dict[str, Any]]
    ) -> List[CashflowPoint]:
        """Add cashflow data points to summary."""
        created_points = []
        
        for point_data in points:
            existing = self.db.query(CashflowPoint).filter(
                and_(
                    CashflowPoint.cashflow_summary_id == cashflow_summary_id,
                    CashflowPoint.cashflow_date == point_data['cashflow_date']
                )
            ).first()
            
            if existing:
                for key, value in point_data.items():
                    if key != 'cashflow_date':
                        setattr(existing, key, value)
                created_points.append(existing)
            else:
                point = CashflowPoint(
                    cashflow_summary_id=cashflow_summary_id,
                    **point_data
                )
                self.db.add(point)
                created_points.append(point)
        
        self.db.commit()
        for point in created_points:
            self.db.refresh(point)
        
        return created_points
    
    def get_cashflow_points(
        self,
        cashflow_summary_id: UUID
    ) -> List[CashflowPoint]:
        """Get all cashflow points for a summary."""
        return self.db.query(CashflowPoint).filter(
            CashflowPoint.cashflow_summary_id == cashflow_summary_id
        ).order_by(CashflowPoint.cashflow_date.asc()).all()
    
    def _assess_cashflow_health(
        self,
        cashflow_data: Dict[str, Any]
    ) -> str:
        """Assess cashflow health status."""
        net_cashflow = float(cashflow_data.get('net_cashflow', 0))
        closing_balance = float(cashflow_data.get('closing_balance', 0))
        
        if net_cashflow > 0 and closing_balance > 0:
            return 'healthy'
        elif net_cashflow >= 0:
            return 'stable'
        elif closing_balance > 0:
            return 'concerning'
        else:
            return 'critical'
    
    def _calculate_burn_rate(
        self,
        cashflow_data: Dict[str, Any]
    ) -> Optional[int]:
        """Calculate cash burn rate in days."""
        net_cashflow = float(cashflow_data.get('net_cashflow', 0))
        closing_balance = float(cashflow_data.get('closing_balance', 0))
        
        if net_cashflow >= 0:
            return None  # Not burning cash
        
        if closing_balance <= 0:
            return 0  # Already out of cash
        
        # Calculate daily burn rate
        period_days = (
            cashflow_data.get('period_end') - 
            cashflow_data.get('period_start')
        ).days
        
        if period_days == 0:
            return None
        
        daily_burn = abs(net_cashflow) / period_days
        
        if daily_burn == 0:
            return None
        
        days_remaining = int(closing_balance / daily_burn)
        
        return days_remaining
    
    # ==================== Budget Comparison ====================
    
    def create_budget_comparison(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        category: str,
        comparison_data: Dict[str, Any]
    ) -> BudgetComparison:
        """Create or update budget comparison."""
        # Calculate variance
        budgeted = float(comparison_data.get('budgeted_amount', 0))
        actual = float(comparison_data.get('actual_amount', 0))
        
        variance_amount = Decimal(str(actual - budgeted))
        
        if budgeted != 0:
            variance_pct = Decimal(str(((actual - budgeted) / budgeted) * 100))
        else:
            variance_pct = Decimal('0.0000')
        
        comparison_data['variance_amount'] = variance_amount
        comparison_data['variance_percentage'] = variance_pct
        
        # Determine if favorable (context-dependent)
        is_favorable = self._is_variance_favorable(category, variance_amount)
        comparison_data['is_favorable'] = is_favorable
        
        # Assess severity
        severity = self._assess_variance_severity(variance_pct)
        comparison_data['variance_severity'] = severity
        
        existing = self.db.query(BudgetComparison).filter(
            and_(
                BudgetComparison.hostel_id == hostel_id if hostel_id else BudgetComparison.hostel_id.is_(None),
                BudgetComparison.period_start == period_start,
                BudgetComparison.period_end == period_end,
                BudgetComparison.category == category
            )
        ).first()
        
        if existing:
            for key, value in comparison_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        comparison = BudgetComparison(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            category=category,
            **comparison_data
        )
        
        self.db.add(comparison)
        self.db.commit()
        self.db.refresh(comparison)
        
        return comparison
    
    def get_budget_comparisons(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> List[BudgetComparison]:
        """Get all budget comparisons for period."""
        return self.db.query(BudgetComparison).filter(
            and_(
                BudgetComparison.hostel_id == hostel_id if hostel_id else BudgetComparison.hostel_id.is_(None),
                BudgetComparison.period_start == period_start,
                BudgetComparison.period_end == period_end
            )
        ).all()
    
    def _is_variance_favorable(
        self,
        category: str,
        variance: Decimal
    ) -> bool:
        """Determine if variance is favorable."""
        # For revenue categories, higher is better
        revenue_categories = ['revenue', 'income', 'sales']
        
        if any(cat in category.lower() for cat in revenue_categories):
            return float(variance) > 0
        
        # For expense categories, lower is better
        return float(variance) < 0
    
    def _assess_variance_severity(
        self,
        variance_pct: Decimal
    ) -> str:
        """Assess variance severity level."""
        abs_variance = abs(float(variance_pct))
        
        if abs_variance < 5:
            return 'minor'
        elif abs_variance < 10:
            return 'moderate'
        elif abs_variance < 20:
            return 'significant'
        else:
            return 'critical'
    
    # ==================== Tax Summary ====================
    
    def create_tax_summary(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        tax_data: Dict[str, Any]
    ) -> TaxSummary:
        """Create or update tax summary."""
        # Calculate effective tax rate
        taxable_revenue = float(tax_data.get('taxable_revenue', 0))
        total_tax = (
            float(tax_data.get('estimated_income_tax', 0)) +
            float(tax_data.get('gst_payable', 0))
        )
        
        if taxable_revenue > 0:
            effective_rate = Decimal(str((total_tax / taxable_revenue) * 100))
        else:
            effective_rate = Decimal('0.00')
        
        tax_data['effective_tax_rate'] = effective_rate
        
        existing = self.db.query(TaxSummary).filter(
            and_(
                TaxSummary.hostel_id == hostel_id if hostel_id else TaxSummary.hostel_id.is_(None),
                TaxSummary.period_start == period_start,
                TaxSummary.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in tax_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        summary = TaxSummary(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **tax_data
        )
        
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)
        
        return summary
    
    # ==================== Comprehensive Financial Report ====================
    
    def create_financial_report(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        pnl_id: Optional[UUID],
        cashflow_id: Optional[UUID],
        tax_summary_id: Optional[UUID],
        report_data: Dict[str, Any]
    ) -> FinancialReport:
        """Create or update comprehensive financial report."""
        # Calculate financial health score
        health_score = self._calculate_financial_health_score(report_data)
        report_data['financial_health_score'] = health_score
        
        # Assign performance grade
        performance_grade = self._assign_performance_grade(health_score)
        report_data['performance_grade'] = performance_grade
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary(report_data)
        report_data['executive_summary'] = executive_summary
        
        existing = self.db.query(FinancialReport).filter(
            and_(
                FinancialReport.hostel_id == hostel_id if hostel_id else FinancialReport.hostel_id.is_(None),
                FinancialReport.period_start == period_start,
                FinancialReport.period_end == period_end
            )
        ).first()
        
        report_data.update({
            'pnl_id': pnl_id,
            'cashflow_id': cashflow_id,
            'tax_summary_id': tax_summary_id,
            'calculated_at': datetime.utcnow(),
        })
        
        if existing:
            for key, value in report_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        report = FinancialReport(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **report_data
        )
        
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        
        return report
    
    def get_financial_report(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Optional[FinancialReport]:
        """Get comprehensive financial report."""
        return self.db.query(FinancialReport).filter(
            and_(
                FinancialReport.hostel_id == hostel_id if hostel_id else FinancialReport.hostel_id.is_(None),
                FinancialReport.period_start == period_start,
                FinancialReport.period_end == period_end
            )
        ).first()
    
    def _calculate_financial_health_score(
        self,
        report_data: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate overall financial health score (0-100).
        
        Weighted factors:
        - Profitability: 30%
        - Liquidity: 25%
        - Collection efficiency: 20%
        - Revenue growth: 15%
        - Expense control: 10%
        """
        # Profitability (based on net margin)
        net_margin = float(report_data.get('avg_revenue_per_student', 0))
        profitability_score = min(max(net_margin, 0), 100) * 0.30
        
        # Liquidity (based on collection rate)
        collection_rate = float(report_data.get('collection_rate', 0))
        liquidity_score = collection_rate * 0.25
        
        # Collection efficiency
        overdue_ratio = float(report_data.get('overdue_ratio', 0))
        collection_efficiency = max(0, 100 - overdue_ratio) * 0.20
        
        # Revenue growth (YoY)
        revenue_growth = float(report_data.get('revenue_growth_yoy', 0))
        growth_score = min(max(revenue_growth, 0), 100) * 0.15
        
        # Expense control (based on occupancy)
        occupancy_rate = float(report_data.get('occupancy_rate', 0))
        expense_score = occupancy_rate * 0.10
        
        total_score = (
            profitability_score +
            liquidity_score +
            collection_efficiency +
            growth_score +
            expense_score
        )
        
        return Decimal(str(round(total_score, 2)))
    
    def _assign_performance_grade(
        self,
        health_score: Decimal
    ) -> str:
        """Assign letter grade based on health score."""
        score = float(health_score)
        
        if score >= 90:
            return 'A+'
        elif score >= 85:
            return 'A'
        elif score >= 80:
            return 'A-'
        elif score >= 75:
            return 'B+'
        elif score >= 70:
            return 'B'
        elif score >= 65:
            return 'B-'
        elif score >= 60:
            return 'C+'
        elif score >= 55:
            return 'C'
        elif score >= 50:
            return 'C-'
        else:
            return 'D'
    
    def _generate_executive_summary(
        self,
        report_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate executive summary with key insights."""
        return {
            'key_highlights': [
                f"Collection rate: {report_data.get('collection_rate', 0)}%",
                f"Average revenue per student: ₹{report_data.get('avg_revenue_per_student', 0):,.2f}",
                f"Occupancy rate: {report_data.get('occupancy_rate', 0)}%",
            ],
            'areas_of_concern': self._identify_concerns(report_data),
            'recommendations': self._generate_recommendations(report_data),
        }
    
    def _identify_concerns(
        self,
        report_data: Dict[str, Any]
    ) -> List[str]:
        """Identify financial concerns."""
        concerns = []
        
        if float(report_data.get('collection_rate', 100)) < 80:
            concerns.append('Low collection efficiency')
        
        if float(report_data.get('overdue_ratio', 0)) > 20:
            concerns.append('High overdue ratio')
        
        if float(report_data.get('occupancy_rate', 100)) < 70:
            concerns.append('Below-target occupancy')
        
        return concerns
    
    def _generate_recommendations(
        self,
        report_data: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        if float(report_data.get('collection_rate', 100)) < 85:
            recommendations.append('Implement stricter payment collection policies')
        
        if float(report_data.get('occupancy_rate', 100)) < 75:
            recommendations.append('Increase marketing efforts to boost occupancy')
        
        if float(report_data.get('overdue_ratio', 0)) > 15:
            recommendations.append('Review and enforce payment terms more rigorously')
        
        return recommendations