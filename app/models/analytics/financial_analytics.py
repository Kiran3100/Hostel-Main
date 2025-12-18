"""
Financial analytics models for P&L and cashflow tracking.

Provides persistent storage for:
- Revenue and expense breakdowns
- Profit & Loss statements
- Cashflow analysis
- Financial ratios and metrics
- Budget vs actual comparisons
- Tax summaries
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, String, Integer, Numeric, DateTime, Date, Boolean,
    ForeignKey, Text, Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.models.analytics.base_analytics import (
    BaseAnalyticsModel,
    AnalyticsMixin,
    MetricMixin,
    HostelScopedMixin,
    CachedAnalyticsMixin,
    ComparisonMixin
)


class RevenueBreakdown(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Detailed revenue breakdown by source and type.
    
    Tracks revenue streams for financial analysis
    and planning.
    """
    
    __tablename__ = 'revenue_breakdowns'
    
    # Total revenue
    total_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Total revenue for period"
    )
    
    # Revenue by type
    booking_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    rent_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    mess_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    utility_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    late_fee_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    other_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    # Breakdown by hostel (for platform-wide)
    revenue_by_hostel = Column(
        JSONB,
        nullable=True,
        comment="Revenue by hostel ID"
    )
    
    # Breakdown by payment type
    revenue_by_payment_type = Column(
        JSONB,
        nullable=True,
        comment="Revenue by payment type"
    )
    
    # Collection metrics
    billed_amount = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Total amount billed"
    )
    
    collected_amount = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Amount collected"
    )
    
    pending_amount = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Pending collection"
    )
    
    # Calculated fields
    collection_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Collection rate percentage"
    )
    
    primary_revenue_source = Column(
        String(50),
        nullable=True,
        comment="Largest revenue source"
    )
    
    revenue_concentration_risk = Column(
        String(20),
        nullable=True,
        comment="Revenue concentration risk level"
    )
    
    __table_args__ = (
        Index(
            'ix_revenue_breakdown_hostel_period',
            'hostel_id',
            'period_start',
            'period_end'
        ),
        UniqueConstraint(
            'hostel_id',
            'period_start',
            'period_end',
            name='uq_revenue_breakdown_unique'
        ),
    )


class ExpenseBreakdown(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Detailed expense breakdown by category.
    
    Tracks expense structure for cost control
    and optimization.
    """
    
    __tablename__ = 'expense_breakdowns'
    
    # Total expenses
    total_expenses = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Total expenses for period"
    )
    
    # Expense by category
    maintenance_expenses = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    staff_expenses = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    utility_expenses = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    supply_expenses = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    marketing_expenses = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    administrative_expenses = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    other_expenses = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    # Breakdown by hostel
    expenses_by_hostel = Column(
        JSONB,
        nullable=True,
        comment="Expenses by hostel ID"
    )
    
    # Breakdown by category (detailed)
    expenses_by_category = Column(
        JSONB,
        nullable=True,
        comment="Detailed category breakdown"
    )
    
    # Fixed vs Variable
    fixed_expenses = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    variable_expenses = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    # Calculated fields
    largest_expense_category = Column(
        String(50),
        nullable=True,
        comment="Largest expense category"
    )
    
    expense_ratio_staff = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Staff expense as percentage"
    )
    
    __table_args__ = (
        Index(
            'ix_expense_breakdown_hostel_period',
            'hostel_id',
            'period_start',
            'period_end'
        ),
        UniqueConstraint(
            'hostel_id',
            'period_start',
            'period_end',
            name='uq_expense_breakdown_unique'
        ),
    )


class FinancialRatios(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Key financial ratios and metrics.
    
    Analytical ratios for financial health assessment
    and performance benchmarking.
    """
    
    __tablename__ = 'financial_ratios'
    
    # Profitability ratios
    gross_profit_margin = Column(
        Numeric(precision=10, scale=4),
        nullable=False,
        comment="Gross profit margin %"
    )
    
    net_profit_margin = Column(
        Numeric(precision=10, scale=4),
        nullable=False,
        comment="Net profit margin %"
    )
    
    return_on_revenue = Column(
        Numeric(precision=10, scale=4),
        nullable=False,
        comment="Return on revenue %"
    )
    
    # Efficiency ratios
    operating_expense_ratio = Column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Operating expenses as % of revenue"
    )
    
    revenue_per_bed = Column(
        Numeric(precision=12, scale=2),
        nullable=False,
        comment="Average revenue per bed"
    )
    
    revenue_per_student = Column(
        Numeric(precision=12, scale=2),
        nullable=False,
        comment="Average revenue per student"
    )
    
    # Collection ratios
    collection_efficiency = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Collection efficiency %"
    )
    
    days_sales_outstanding = Column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Average days to collect payment"
    )
    
    # Cost control
    variable_cost_ratio = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        default=0,
        comment="Variable costs as % of revenue"
    )
    
    fixed_cost_ratio = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        default=0,
        comment="Fixed costs as % of revenue"
    )
    
    # Status
    profitability_status = Column(
        String(20),
        nullable=True,
        comment="Overall profitability status"
    )
    
    __table_args__ = (
        Index(
            'ix_financial_ratios_hostel_period',
            'hostel_id',
            'period_start',
            'period_end'
        ),
    )


class ProfitAndLossStatement(
    BaseAnalyticsModel,
    AnalyticsMixin,
    HostelScopedMixin,
    CachedAnalyticsMixin
):
    """
    Profit & Loss (P&L) statement.
    
    Comprehensive income statement with revenue,
    expenses, and profitability.
    """
    
    __tablename__ = 'profit_loss_statements'
    
    revenue_breakdown_id = Column(
        UUID(as_uuid=True),
        ForeignKey('revenue_breakdowns.id', ondelete='SET NULL'),
        nullable=True
    )
    
    expense_breakdown_id = Column(
        UUID(as_uuid=True),
        ForeignKey('expense_breakdowns.id', ondelete='SET NULL'),
        nullable=True
    )
    
    financial_ratios_id = Column(
        UUID(as_uuid=True),
        ForeignKey('financial_ratios.id', ondelete='SET NULL'),
        nullable=True
    )
    
    # Calculated values
    gross_profit = Column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Gross profit"
    )
    
    operating_profit = Column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Operating profit"
    )
    
    net_profit = Column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Net profit after all expenses"
    )
    
    # Margins
    gross_profit_margin = Column(
        Numeric(precision=10, scale=4),
        nullable=False,
        comment="Gross profit margin %"
    )
    
    operating_profit_margin = Column(
        Numeric(precision=10, scale=4),
        nullable=False,
        comment="Operating profit margin %"
    )
    
    net_profit_margin = Column(
        Numeric(precision=10, scale=4),
        nullable=False,
        comment="Net profit margin %"
    )
    
    # Status flags
    is_profitable = Column(
        Boolean,
        nullable=False,
        comment="Whether period was profitable"
    )
    
    break_even_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=True,
        comment="Revenue needed to break even"
    )
    
    revenue_above_break_even = Column(
        Numeric(precision=15, scale=2),
        nullable=True,
        comment="Revenue above break-even"
    )
    
    # Performance summary
    performance_summary = Column(
        JSONB,
        nullable=True,
        comment="Executive performance summary"
    )
    
    __table_args__ = (
        Index(
            'ix_pnl_hostel_period',
            'hostel_id',
            'period_start',
            'period_end'
        ),
        UniqueConstraint(
            'hostel_id',
            'period_start',
            'period_end',
            name='uq_pnl_unique'
        ),
    )
    
    # Relationships
    revenue_breakdown = relationship('RevenueBreakdown', foreign_keys=[revenue_breakdown_id])
    expense_breakdown = relationship('ExpenseBreakdown', foreign_keys=[expense_breakdown_id])
    financial_ratios = relationship('FinancialRatios', foreign_keys=[financial_ratios_id])


class CashflowPoint(BaseAnalyticsModel):
    """
    Single cashflow data point for time-series analysis.
    
    Represents cash movements for a specific date.
    """
    
    __tablename__ = 'cashflow_points'
    
    cashflow_summary_id = Column(
        UUID(as_uuid=True),
        ForeignKey('cashflow_summaries.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    cashflow_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Date of cashflow point"
    )
    
    inflow = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Cash inflow"
    )
    
    outflow = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Cash outflow"
    )
    
    net_flow = Column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Net cashflow"
    )
    
    balance = Column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Cumulative balance"
    )
    
    is_positive_flow = Column(
        Boolean,
        nullable=True,
        comment="Whether net flow is positive"
    )
    
    __table_args__ = (
        Index('ix_cashflow_point_date', 'cashflow_date'),
        UniqueConstraint(
            'cashflow_summary_id',
            'cashflow_date',
            name='uq_cashflow_point_unique'
        ),
    )
    
    # Relationships
    cashflow_summary = relationship('CashflowSummary', back_populates='timeseries')


class CashflowSummary(
    BaseAnalyticsModel,
    AnalyticsMixin,
    HostelScopedMixin,
    CachedAnalyticsMixin
):
    """
    Cashflow summary and analysis.
    
    Comprehensive view of cash movements and
    liquidity position.
    """
    
    __tablename__ = 'cashflow_summaries'
    
    # Balances
    opening_balance = Column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Cash balance at period start"
    )
    
    closing_balance = Column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Cash balance at period end"
    )
    
    # Totals
    total_inflows = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    total_outflows = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0
    )
    
    net_cashflow = Column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Net cashflow"
    )
    
    # Breakdowns
    inflow_breakdown = Column(
        JSONB,
        nullable=True,
        comment="Inflows by category"
    )
    
    outflow_breakdown = Column(
        JSONB,
        nullable=True,
        comment="Outflows by category"
    )
    
    # Liquidity metrics
    average_daily_balance = Column(
        Numeric(precision=15, scale=4),
        nullable=True,
        comment="Average daily balance"
    )
    
    minimum_balance = Column(
        Numeric(precision=15, scale=4),
        nullable=True,
        comment="Minimum balance in period"
    )
    
    maximum_balance = Column(
        Numeric(precision=15, scale=4),
        nullable=True,
        comment="Maximum balance in period"
    )
    
    # Health indicators
    cashflow_health = Column(
        String(20),
        nullable=True,
        comment="Cashflow health status"
    )
    
    burn_rate_days = Column(
        Integer,
        nullable=True,
        comment="Days until cash runs out at current rate"
    )
    
    operating_cash_ratio = Column(
        Numeric(precision=10, scale=2),
        nullable=True,
        comment="Operating cash flow ratio"
    )
    
    __table_args__ = (
        Index(
            'ix_cashflow_summary_hostel_period',
            'hostel_id',
            'period_start',
            'period_end'
        ),
        UniqueConstraint(
            'hostel_id',
            'period_start',
            'period_end',
            name='uq_cashflow_summary_unique'
        ),
    )
    
    # Relationships
    timeseries = relationship(
        'CashflowPoint',
        back_populates='cashflow_summary',
        cascade='all, delete-orphan'
    )


class BudgetComparison(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Budget vs actual comparison.
    
    Tracks variance from budgeted targets for
    financial planning and control.
    """
    
    __tablename__ = 'budget_comparisons'
    
    category = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Budget category"
    )
    
    budgeted_amount = Column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Budgeted amount"
    )
    
    actual_amount = Column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Actual amount"
    )
    
    variance_amount = Column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Variance (actual - budgeted)"
    )
    
    variance_percentage = Column(
        Numeric(precision=10, scale=4),
        nullable=False,
        comment="Variance as percentage"
    )
    
    is_favorable = Column(
        Boolean,
        nullable=True,
        comment="Whether variance is favorable"
    )
    
    variance_severity = Column(
        String(20),
        nullable=True,
        comment="Variance severity (minor, moderate, significant, critical)"
    )
    
    __table_args__ = (
        Index(
            'ix_budget_comparison_hostel_period_category',
            'hostel_id',
            'period_start',
            'period_end',
            'category'
        ),
    )


class TaxSummary(BaseAnalyticsModel, AnalyticsMixin, HostelScopedMixin):
    """
    Tax-related summary for financial reporting.
    
    Tracks tax liabilities and compliance.
    """
    
    __tablename__ = 'tax_summaries'
    
    taxable_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Revenue subject to taxation"
    )
    
    tax_exempt_revenue = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Tax-exempt revenue"
    )
    
    # GST
    gst_collected = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="GST collected from customers"
    )
    
    gst_paid = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="GST paid on expenses"
    )
    
    gst_payable = Column(
        Numeric(precision=15, scale=4),
        nullable=False,
        default=0,
        comment="Net GST payable"
    )
    
    # TDS
    tds_deducted = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="TDS deducted at source"
    )
    
    # Income tax
    estimated_income_tax = Column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0,
        comment="Estimated income tax liability"
    )
    
    effective_tax_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Effective tax rate %"
    )
    
    __table_args__ = (
        Index(
            'ix_tax_summary_hostel_period',
            'hostel_id',
            'period_start',
            'period_end'
        ),
    )


class FinancialReport(
    BaseAnalyticsModel,
    AnalyticsMixin,
    HostelScopedMixin,
    CachedAnalyticsMixin,
    ComparisonMixin
):
    """
    Comprehensive financial report.
    
    Consolidates P&L, cashflow, and key metrics
    into complete financial statement.
    """
    
    __tablename__ = 'financial_reports'
    
    pnl_id = Column(
        UUID(as_uuid=True),
        ForeignKey('profit_loss_statements.id', ondelete='SET NULL'),
        nullable=True
    )
    
    cashflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey('cashflow_summaries.id', ondelete='SET NULL'),
        nullable=True
    )
    
    tax_summary_id = Column(
        UUID(as_uuid=True),
        ForeignKey('tax_summaries.id', ondelete='SET NULL'),
        nullable=True
    )
    
    # Key metrics
    collection_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Collection rate %"
    )
    
    overdue_ratio = Column(
        Numeric(precision=5, scale=2),
        nullable=False,
        comment="Overdue ratio %"
    )
    
    avg_revenue_per_student = Column(
        Numeric(precision=12, scale=2),
        nullable=False,
        comment="Average revenue per student"
    )
    
    avg_revenue_per_bed = Column(
        Numeric(precision=12, scale=2),
        nullable=False,
        comment="Average revenue per bed"
    )
    
    # Operational metrics
    occupancy_rate = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Average occupancy rate"
    )
    
    average_daily_rate = Column(
        Numeric(precision=12, scale=2),
        nullable=True,
        comment="Average daily rate (ADR)"
    )
    
    # Year-over-year comparison
    revenue_growth_yoy = Column(
        Numeric(precision=10, scale=4),
        nullable=True,
        comment="YoY revenue growth %"
    )
    
    profit_growth_yoy = Column(
        Numeric(precision=10, scale=4),
        nullable=True,
        comment="YoY profit growth %"
    )
    
    # Health scores
    financial_health_score = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Overall financial health score (0-100)"
    )
    
    performance_grade = Column(
        String(5),
        nullable=True,
        comment="Letter grade for performance"
    )
    
    # Executive summary
    executive_summary = Column(
        JSONB,
        nullable=True,
        comment="Executive summary insights"
    )
    
    __table_args__ = (
        Index(
            'ix_financial_report_hostel_period',
            'hostel_id',
            'period_start',
            'period_end'
        ),
        UniqueConstraint(
            'hostel_id',
            'period_start',
            'period_end',
            name='uq_financial_report_unique'
        ),
    )
    
    # Relationships
    pnl = relationship('ProfitAndLossStatement', foreign_keys=[pnl_id])
    cashflow = relationship('CashflowSummary', foreign_keys=[cashflow_id])
    tax_summary = relationship('TaxSummary', foreign_keys=[tax_summary_id])