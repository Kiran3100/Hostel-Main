# --- File: C:\Hostel-Main\app\services\analytics\financial_analytics_service.py ---
"""
Financial Analytics Service - P&L, cashflow, and financial health tracking.

Provides comprehensive financial analytics with:
- Revenue and expense analysis
- Profit & Loss statement generation
- Cashflow tracking and forecasting
- Budget variance analysis
- Financial health scoring
"""

from typing import List, Dict, Optional, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from uuid import UUID
import logging

from app.repositories.analytics.financial_analytics_repository import (
    FinancialAnalyticsRepository
)
from app.models.payments import Payment  # Assuming you have this model
from app.models.expenses import Expense  # Assuming you have this model


logger = logging.getLogger(__name__)


class FinancialAnalyticsService:
    """Service for financial analytics operations."""
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.repo = FinancialAnalyticsRepository(db)
    
    # ==================== Revenue Analysis ====================
    
    def generate_revenue_breakdown(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Any:
        """
        Generate comprehensive revenue breakdown for period.
        
        Analyzes revenue by type, source, and payment method.
        """
        logger.info(f"Generating revenue breakdown for hostel {hostel_id}")
        
        # Query payments for period
        payments = self.db.query(Payment).filter(
            and_(
                Payment.payment_date >= period_start,
                Payment.payment_date <= period_end,
                Payment.status == 'completed',
                Payment.hostel_id == hostel_id if hostel_id else True
            )
        ).all()
        
        # Calculate revenue by type
        booking_revenue = sum(
            float(p.amount) for p in payments
            if p.payment_type == 'booking'
        )
        
        rent_revenue = sum(
            float(p.amount) for p in payments
            if p.payment_type == 'rent'
        )
        
        mess_revenue = sum(
            float(p.amount) for p in payments
            if p.payment_type == 'mess'
        )
        
        utility_revenue = sum(
            float(p.amount) for p in payments
            if p.payment_type == 'utility'
        )
        
        late_fee_revenue = sum(
            float(p.amount) for p in payments
            if p.payment_type == 'late_fee'
        )
        
        other_revenue = sum(
            float(p.amount) for p in payments
            if p.payment_type not in ['booking', 'rent', 'mess', 'utility', 'late_fee']
        )
        
        total_revenue = sum(float(p.amount) for p in payments)
        
        # Billed vs collected
        all_invoices = self.db.query(Payment).filter(
            and_(
                Payment.payment_date >= period_start,
                Payment.payment_date <= period_end,
                Payment.hostel_id == hostel_id if hostel_id else True
            )
        ).all()
        
        billed_amount = sum(float(p.amount) for p in all_invoices)
        collected_amount = total_revenue
        pending_amount = billed_amount - collected_amount
        
        # Revenue by payment type
        revenue_by_payment_type = {}
        for payment in payments:
            method = payment.payment_method or 'cash'
            revenue_by_payment_type[method] = revenue_by_payment_type.get(method, 0) + float(payment.amount)
        
        revenue_data = {
            'total_revenue': Decimal(str(total_revenue)),
            'booking_revenue': Decimal(str(booking_revenue)),
            'rent_revenue': Decimal(str(rent_revenue)),
            'mess_revenue': Decimal(str(mess_revenue)),
            'utility_revenue': Decimal(str(utility_revenue)),
            'late_fee_revenue': Decimal(str(late_fee_revenue)),
            'other_revenue': Decimal(str(other_revenue)),
            'billed_amount': Decimal(str(billed_amount)),
            'collected_amount': Decimal(str(collected_amount)),
            'pending_amount': Decimal(str(pending_amount)),
            'revenue_by_payment_type': revenue_by_payment_type,
        }
        
        breakdown = self.repo.create_revenue_breakdown(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            revenue_data=revenue_data
        )
        
        return breakdown
    
    # ==================== Expense Analysis ====================
    
    def generate_expense_breakdown(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Any:
        """
        Generate comprehensive expense breakdown for period.
        
        Analyzes expenses by category and type.
        """
        logger.info(f"Generating expense breakdown for hostel {hostel_id}")
        
        # Query expenses for period
        expenses = self.db.query(Expense).filter(
            and_(
                Expense.expense_date >= period_start,
                Expense.expense_date <= period_end,
                Expense.hostel_id == hostel_id if hostel_id else True
            )
        ).all()
        
        # Calculate expenses by category
        maintenance_expenses = sum(
            float(e.amount) for e in expenses
            if e.category == 'maintenance'
        )
        
        staff_expenses = sum(
            float(e.amount) for e in expenses
            if e.category == 'staff'
        )
        
        utility_expenses = sum(
            float(e.amount) for e in expenses
            if e.category == 'utilities'
        )
        
        supply_expenses = sum(
            float(e.amount) for e in expenses
            if e.category == 'supplies'
        )
        
        marketing_expenses = sum(
            float(e.amount) for e in expenses
            if e.category == 'marketing'
        )
        
        administrative_expenses = sum(
            float(e.amount) for e in expenses
            if e.category == 'administrative'
        )
        
        other_expenses = sum(
            float(e.amount) for e in expenses
            if e.category not in ['maintenance', 'staff', 'utilities', 'supplies', 'marketing', 'administrative']
        )
        
        total_expenses = sum(float(e.amount) for e in expenses)
        
        # Fixed vs Variable
        fixed_expenses = sum(
            float(e.amount) for e in expenses
            if e.expense_type == 'fixed'
        )
        
        variable_expenses = sum(
            float(e.amount) for e in expenses
            if e.expense_type == 'variable'
        )
        
        # Expenses by category (detailed)
        expenses_by_category = {}
        for expense in expenses:
            category = expense.category or 'Uncategorized'
            expenses_by_category[category] = expenses_by_category.get(category, 0) + float(expense.amount)
        
        expense_data = {
            'total_expenses': Decimal(str(total_expenses)),
            'maintenance_expenses': Decimal(str(maintenance_expenses)),
            'staff_expenses': Decimal(str(staff_expenses)),
            'utility_expenses': Decimal(str(utility_expenses)),
            'supply_expenses': Decimal(str(supply_expenses)),
            'marketing_expenses': Decimal(str(marketing_expenses)),
            'administrative_expenses': Decimal(str(administrative_expenses)),
            'other_expenses': Decimal(str(other_expenses)),
            'fixed_expenses': Decimal(str(fixed_expenses)),
            'variable_expenses': Decimal(str(variable_expenses)),
            'expenses_by_category': expenses_by_category,
        }
        
        breakdown = self.repo.create_expense_breakdown(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            expense_data=expense_data
        )
        
        return breakdown
    
    # ==================== Financial Ratios ====================
    
    def calculate_financial_ratios(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        revenue_breakdown: Any,
        expense_breakdown: Any
    ) -> Any:
        """Calculate key financial ratios."""
        logger.info(f"Calculating financial ratios for hostel {hostel_id}")
        
        total_revenue = float(revenue_breakdown.total_revenue)
        total_expenses = float(expense_breakdown.total_expenses)
        
        # Profitability ratios
        gross_profit = total_revenue - total_expenses
        
        gross_profit_margin = (
            Decimal(str((gross_profit / total_revenue) * 100))
            if total_revenue > 0 else Decimal('0.0000')
        )
        
        net_profit_margin = gross_profit_margin  # Simplified
        
        return_on_revenue = (
            Decimal(str((gross_profit / total_revenue) * 100))
            if total_revenue > 0 else Decimal('0.0000')
        )
        
        # Efficiency ratios
        operating_expense_ratio = (
            Decimal(str((total_expenses / total_revenue) * 100))
            if total_revenue > 0 else Decimal('0.00')
        )
        
        # Get bed count and student count (would query from database)
        # Placeholder values
        total_beds = 100
        total_students = 80
        
        revenue_per_bed = (
            Decimal(str(total_revenue / total_beds))
            if total_beds > 0 else Decimal('0.00')
        )
        
        revenue_per_student = (
            Decimal(str(total_revenue / total_students))
            if total_students > 0 else Decimal('0.00')
        )
        
        # Collection efficiency
        collection_efficiency = float(revenue_breakdown.collection_rate)
        
        # Days sales outstanding (simplified)
        days_sales_outstanding = Decimal('30.00')  # Placeholder
        
        # Cost ratios
        variable_cost_ratio = (
            Decimal(str((float(expense_breakdown.variable_expenses) / total_revenue) * 100))
            if total_revenue > 0 else Decimal('0.00')
        )
        
        fixed_cost_ratio = (
            Decimal(str((float(expense_breakdown.fixed_expenses) / total_revenue) * 100))
            if total_revenue > 0 else Decimal('0.00')
        )
        
        ratios_data = {
            'gross_profit_margin': gross_profit_margin,
            'net_profit_margin': net_profit_margin,
            'return_on_revenue': return_on_revenue,
            'operating_expense_ratio': operating_expense_ratio,
            'revenue_per_bed': revenue_per_bed,
            'revenue_per_student': revenue_per_student,
            'collection_efficiency': Decimal(str(collection_efficiency)),
            'days_sales_outstanding': days_sales_outstanding,
            'variable_cost_ratio': variable_cost_ratio,
            'fixed_cost_ratio': fixed_cost_ratio,
        }
        
        ratios = self.repo.create_financial_ratios(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            ratios_data=ratios_data
        )
        
        return ratios
    
    # ==================== P&L Statement ====================
    
    def generate_pnl_statement(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Any:
        """
        Generate Profit & Loss statement for period.
        
        Combines revenue and expense data into comprehensive P&L.
        """
        logger.info(f"Generating P&L statement for hostel {hostel_id}")
        
        # Generate components
        revenue_breakdown = self.generate_revenue_breakdown(
            hostel_id, period_start, period_end
        )
        
        expense_breakdown = self.generate_expense_breakdown(
            hostel_id, period_start, period_end
        )
        
        ratios = self.calculate_financial_ratios(
            hostel_id, period_start, period_end,
            revenue_breakdown, expense_breakdown
        )
        
        # Create P&L statement
        pnl = self.repo.create_pnl_statement(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            revenue_breakdown_id=revenue_breakdown.id,
            expense_breakdown_id=expense_breakdown.id,
            financial_ratios_id=ratios.id
        )
        
        return {
            'pnl': pnl,
            'revenue_breakdown': revenue_breakdown,
            'expense_breakdown': expense_breakdown,
            'ratios': ratios,
        }
    
    # ==================== Cashflow Analysis ====================
    
    def generate_cashflow_summary(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Any:
        """
        Generate cashflow summary for period.
        
        Tracks cash inflows and outflows with daily granularity.
        """
        logger.info(f"Generating cashflow summary for hostel {hostel_id}")
        
        # Get opening balance (would query from previous period)
        opening_balance = Decimal('10000.00')  # Placeholder
        
        # Calculate inflows (payments received)
        payments = self.db.query(Payment).filter(
            and_(
                Payment.payment_date >= period_start,
                Payment.payment_date <= period_end,
                Payment.status == 'completed',
                Payment.hostel_id == hostel_id if hostel_id else True
            )
        ).all()
        
        total_inflows = sum(float(p.amount) for p in payments)
        
        # Calculate outflows (expenses paid)
        expenses = self.db.query(Expense).filter(
            and_(
                Expense.expense_date >= period_start,
                Expense.expense_date <= period_end,
                Expense.hostel_id == hostel_id if hostel_id else True
            )
        ).all()
        
        total_outflows = sum(float(e.amount) for e in expenses)
        
        # Net cashflow
        net_cashflow = Decimal(str(total_inflows - total_outflows))
        closing_balance = opening_balance + net_cashflow
        
        # Inflow breakdown
        inflow_breakdown = {}
        for payment in payments:
            payment_type = payment.payment_type or 'other'
            inflow_breakdown[payment_type] = inflow_breakdown.get(payment_type, 0) + float(payment.amount)
        
        # Outflow breakdown
        outflow_breakdown = {}
        for expense in expenses:
            category = expense.category or 'other'
            outflow_breakdown[category] = outflow_breakdown.get(category, 0) + float(expense.amount)
        
        cashflow_data = {
            'opening_balance': opening_balance,
            'closing_balance': closing_balance,
            'total_inflows': Decimal(str(total_inflows)),
            'total_outflows': Decimal(str(total_outflows)),
            'net_cashflow': net_cashflow,
            'inflow_breakdown': inflow_breakdown,
            'outflow_breakdown': outflow_breakdown,
        }
        
        summary = self.repo.create_cashflow_summary(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            cashflow_data=cashflow_data
        )
        
        # Generate daily cashflow points
        self._generate_cashflow_points(
            summary.id, period_start, period_end, hostel_id, opening_balance
        )
        
        return summary
    
    def _generate_cashflow_points(
        self,
        cashflow_summary_id: UUID,
        period_start: date,
        period_end: date,
        hostel_id: Optional[UUID],
        opening_balance: Decimal
    ) -> None:
        """Generate daily cashflow data points."""
        current_date = period_start
        running_balance = opening_balance
        points = []
        
        while current_date <= period_end:
            # Get daily inflows
            daily_payments = self.db.query(Payment).filter(
                and_(
                    Payment.payment_date == current_date,
                    Payment.status == 'completed',
                    Payment.hostel_id == hostel_id if hostel_id else True
                )
            ).all()
            
            inflow = sum(float(p.amount) for p in daily_payments)
            
            # Get daily outflows
            daily_expenses = self.db.query(Expense).filter(
                and_(
                    Expense.expense_date == current_date,
                    Expense.hostel_id == hostel_id if hostel_id else True
                )
            ).all()
            
            outflow = sum(float(e.amount) for e in daily_expenses)
            
            # Calculate net flow and balance
            net_flow = Decimal(str(inflow - outflow))
            running_balance += net_flow
            
            points.append({
                'cashflow_date': current_date,
                'inflow': Decimal(str(inflow)),
                'outflow': Decimal(str(outflow)),
                'net_flow': net_flow,
                'balance': running_balance,
                'is_positive_flow': net_flow > 0,
            })
            
            current_date += timedelta(days=1)
        
        if points:
            self.repo.add_cashflow_points(cashflow_summary_id, points)
    
    # ==================== Budget Comparison ====================
    
    def generate_budget_comparisons(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        budget_data: Dict[str, Decimal]
    ) -> List[Any]:
        """
        Generate budget vs actual comparisons.
        
        Args:
            budget_data: Dictionary of budgeted amounts by category
        """
        logger.info(f"Generating budget comparisons for hostel {hostel_id}")
        
        # Get actual data
        revenue_breakdown = self.generate_revenue_breakdown(
            hostel_id, period_start, period_end
        )
        expense_breakdown = self.generate_expense_breakdown(
            hostel_id, period_start, period_end
        )
        
        comparisons = []
        
        # Revenue comparisons
        for category, budgeted in budget_data.items():
            if category.startswith('revenue_'):
                actual_key = category.replace('revenue_', '') + '_revenue'
                actual = getattr(revenue_breakdown, actual_key, Decimal('0.00'))
            elif category.startswith('expense_'):
                actual_key = category.replace('expense_', '') + '_expenses'
                actual = getattr(expense_breakdown, actual_key, Decimal('0.00'))
            else:
                continue
            
            comparison = self.repo.create_budget_comparison(
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
                category=category,
                comparison_data={
                    'budgeted_amount': budgeted,
                    'actual_amount': actual,
                }
            )
            
            comparisons.append(comparison)
        
        return comparisons
    
    # ==================== Comprehensive Financial Report ====================
    
    def generate_financial_report(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Generate comprehensive financial report.
        
        Combines P&L, cashflow, and all financial metrics.
        """
        logger.info(f"Generating financial report for hostel {hostel_id}")
        
        # Generate all components
        pnl_data = self.generate_pnl_statement(hostel_id, period_start, period_end)
        cashflow = self.generate_cashflow_summary(hostel_id, period_start, period_end)
        
        # Get metrics for report
        # These would be calculated based on actual data
        report_data = {
            'collection_rate': Decimal('85.50'),
            'overdue_ratio': Decimal('12.30'),
            'avg_revenue_per_student': Decimal('5000.00'),
            'avg_revenue_per_bed': Decimal('4000.00'),
            'occupancy_rate': Decimal('80.00'),
        }
        
        # Create comprehensive report
        report = self.repo.create_financial_report(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            pnl_id=pnl_data['pnl'].id,
            cashflow_id=cashflow.id,
            tax_summary_id=None,
            report_data=report_data
        )
        
        return {
            'report': report,
            'pnl': pnl_data,
            'cashflow': cashflow,
        }


