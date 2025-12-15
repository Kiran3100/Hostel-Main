# --- File: app/schemas/analytics/financial_analytics.py ---
"""
Financial analytics schemas with comprehensive P&L and cashflow tracking.

Provides detailed financial analytics including:
- Revenue and expense breakdowns
- Profit & Loss statements
- Cashflow analysis and forecasting
- Financial ratios and metrics
- Budget vs. actual comparisons
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any, Annotated
from enum import Enum

from pydantic import BaseModel, Field, field_validator, computed_field, model_validator, AfterValidator
from uuid import UUID

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import PaymentType
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "RevenueCategory",
    "ExpenseCategory",
    "RevenueBreakdown",
    "ExpenseBreakdown",
    "ProfitAndLossReport",
    "CashflowPoint",
    "CashflowSummary",
    "FinancialRatios",
    "BudgetComparison",
    "FinancialReport",
    "TaxSummary",
]


# Custom validators for decimal places
def round_to_2_places(v: Decimal) -> Decimal:
    """Round decimal to 2 places."""
    if isinstance(v, (int, float)):
        v = Decimal(str(v))
    return round(v, 2)


# Type aliases for common decimal fields
DecimalCurrency = Annotated[Decimal, Field(ge=0), AfterValidator(round_to_2_places)]
DecimalPercentage = Annotated[Decimal, Field(ge=0, le=100), AfterValidator(round_to_2_places)]
DecimalAmount = Annotated[Decimal, AfterValidator(round_to_2_places)]


class RevenueCategory(str, Enum):
    """Revenue categories for financial reporting."""
    
    BOOKING = "booking"
    RENT = "rent"
    MESS = "mess"
    UTILITIES = "utilities"
    LATE_FEES = "late_fees"
    SECURITY_DEPOSIT = "security_deposit"
    OTHER = "other"


class ExpenseCategory(str, Enum):
    """Expense categories for financial reporting."""
    
    MAINTENANCE = "maintenance"
    STAFF_SALARIES = "staff_salaries"
    UTILITIES = "utilities"
    SUPPLIES = "supplies"
    MARKETING = "marketing"
    ADMINISTRATIVE = "administrative"
    DEPRECIATION = "depreciation"
    INSURANCE = "insurance"
    TAXES = "taxes"
    OTHER = "other"


class RevenueBreakdown(BaseSchema):
    """
    Detailed breakdown of revenue by source and type.
    
    Provides granular visibility into revenue streams
    for financial analysis and planning.
    """
    
    # Total revenue
    total_revenue: DecimalCurrency = Field(
        ...,
        description="Total revenue for the period"
    )
    
    # Revenue by type
    booking_revenue: DecimalCurrency = Field(
        ...,
        description="Revenue from new bookings"
    )
    rent_revenue: DecimalCurrency = Field(
        ...,
        description="Monthly/periodic rent revenue"
    )
    mess_revenue: DecimalCurrency = Field(
        ...,
        description="Mess/food service revenue"
    )
    utility_revenue: DecimalCurrency = Field(
        0,
        description="Utility charges collected"
    )
    late_fee_revenue: DecimalCurrency = Field(
        0,
        description="Late payment fees"
    )
    other_revenue: DecimalCurrency = Field(
        0,
        description="Other miscellaneous revenue"
    )
    
    # Breakdown by hostel
    revenue_by_hostel: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Revenue mapped by hostel ID"
    )
    
    # Breakdown by payment type
    revenue_by_payment_type: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Revenue by PaymentType category"
    )
    
    # Collection metrics
    billed_amount: DecimalCurrency = Field(
        0,
        description="Total amount billed in period"
    )
    collected_amount: DecimalCurrency = Field(
        0,
        description="Amount actually collected"
    )
    pending_amount: DecimalCurrency = Field(
        0,
        description="Amount pending collection"
    )
    
    @model_validator(mode="after")
    def validate_revenue_totals(self) -> "RevenueBreakdown":
        """Validate that component revenues sum to total."""
        component_sum = (
            self.booking_revenue +
            self.rent_revenue +
            self.mess_revenue +
            self.utility_revenue +
            self.late_fee_revenue +
            self.other_revenue
        )
        
        # Allow 0.01 tolerance for rounding
        if abs(component_sum - self.total_revenue) > Decimal("0.01"):
            raise ValueError(
                f"Component revenues ({component_sum}) must sum to "
                f"total_revenue ({self.total_revenue})"
            )
        
        return self
    
    @computed_field  # type: ignore[misc]
    @property
    def collection_rate(self) -> Decimal:
        """Calculate collection rate percentage."""
        if self.billed_amount == 0:
            return Decimal("100.00")
        return round(
            (self.collected_amount / self.billed_amount) * 100,
            2
        )
    
    @computed_field  # type: ignore[misc]
    @property
    def primary_revenue_source(self) -> str:
        """Identify the largest revenue source."""
        sources = {
            "booking": self.booking_revenue,
            "rent": self.rent_revenue,
            "mess": self.mess_revenue,
            "utilities": self.utility_revenue,
            "late_fees": self.late_fee_revenue,
            "other": self.other_revenue,
        }
        return max(sources, key=sources.get)  # type: ignore[arg-type]
    
    @computed_field  # type: ignore[misc]
    @property
    def revenue_concentration_risk(self) -> str:
        """
        Assess revenue concentration risk.
        
        Returns:
            'low', 'medium', or 'high' based on revenue diversification
        """
        if self.total_revenue == 0:
            return "unknown"
        
        # Calculate percentage from largest source
        largest_source_pct = (
            float(max(
                self.booking_revenue,
                self.rent_revenue,
                self.mess_revenue
            )) / float(self.total_revenue) * 100
        )
        
        if largest_source_pct >= 70:
            return "high"
        elif largest_source_pct >= 50:
            return "medium"
        else:
            return "low"


class ExpenseBreakdown(BaseSchema):
    """
    Detailed breakdown of expenses by category.
    
    Provides granular visibility into cost structure
    for financial control and optimization.
    """
    
    # Total expenses
    total_expenses: DecimalCurrency = Field(
        ...,
        description="Total expenses for the period"
    )
    
    # Expense by category
    maintenance_expenses: DecimalCurrency = Field(
        ...,
        description="Maintenance and repair expenses"
    )
    staff_expenses: DecimalCurrency = Field(
        ...,
        description="Staff salaries and benefits"
    )
    utility_expenses: DecimalCurrency = Field(
        ...,
        description="Utility expenses (electricity, water, etc.)"
    )
    supply_expenses: DecimalCurrency = Field(
        0,
        description="Supplies and consumables"
    )
    marketing_expenses: DecimalCurrency = Field(
        0,
        description="Marketing and advertising expenses"
    )
    administrative_expenses: DecimalCurrency = Field(
        0,
        description="Administrative and overhead expenses"
    )
    other_expenses: DecimalCurrency = Field(
        0,
        description="Other miscellaneous expenses"
    )
    
    # Breakdown by hostel
    expenses_by_hostel: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Expenses mapped by hostel ID"
    )
    
    # Breakdown by category (detailed)
    expenses_by_category: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Expenses by ExpenseCategory"
    )
    
    # Fixed vs. Variable
    fixed_expenses: DecimalCurrency = Field(
        0,
        description="Fixed expenses (rent, salaries, etc.)"
    )
    variable_expenses: DecimalCurrency = Field(
        0,
        description="Variable expenses (utilities, supplies, etc.)"
    )
    
    @model_validator(mode="after")
    def validate_expense_totals(self) -> "ExpenseBreakdown":
        """Validate that component expenses sum to total."""
        component_sum = (
            self.maintenance_expenses +
            self.staff_expenses +
            self.utility_expenses +
            self.supply_expenses +
            self.marketing_expenses +
            self.administrative_expenses +
            self.other_expenses
        )
        
        # Allow 0.01 tolerance for rounding
        if abs(component_sum - self.total_expenses) > Decimal("0.01"):
            raise ValueError(
                f"Component expenses ({component_sum}) must sum to "
                f"total_expenses ({self.total_expenses})"
            )
        
        return self
    
    @computed_field  # type: ignore[misc]
    @property
    def largest_expense_category(self) -> str:
        """Identify the largest expense category."""
        categories = {
            "maintenance": self.maintenance_expenses,
            "staff": self.staff_expenses,
            "utilities": self.utility_expenses,
            "supplies": self.supply_expenses,
            "marketing": self.marketing_expenses,
            "administrative": self.administrative_expenses,
            "other": self.other_expenses,
        }
        return max(categories, key=categories.get)  # type: ignore[arg-type]
    
    @computed_field  # type: ignore[misc]
    @property
    def expense_ratio_staff(self) -> Decimal:
        """Calculate staff expense as percentage of total."""
        if self.total_expenses == 0:
            return Decimal("0.00")
        return round(
            (self.staff_expenses / self.total_expenses) * 100,
            2
        )


class FinancialRatios(BaseSchema):
    """
    Key financial ratios and metrics.
    
    Provides analytical ratios for financial health assessment
    and performance benchmarking.
    """
    
    # Profitability ratios
    gross_profit_margin: DecimalAmount = Field(
        ...,
        description="Gross profit margin percentage"
    )
    net_profit_margin: DecimalAmount = Field(
        ...,
        description="Net profit margin percentage"
    )
    return_on_revenue: DecimalAmount = Field(
        ...,
        description="Return on revenue percentage"
    )
    
    # Efficiency ratios
    operating_expense_ratio: DecimalCurrency = Field(
        ...,
        description="Operating expenses as % of revenue"
    )
    revenue_per_bed: DecimalCurrency = Field(
        ...,
        description="Average revenue per bed"
    )
    revenue_per_student: DecimalCurrency = Field(
        ...,
        description="Average revenue per student"
    )
    
    # Collection ratios
    collection_efficiency: DecimalPercentage = Field(
        ...,
        description="Collection efficiency percentage"
    )
    days_sales_outstanding: Optional[DecimalCurrency] = Field(
        None,
        description="Average days to collect payment"
    )
    
    # Cost control
    variable_cost_ratio: DecimalPercentage = Field(
        0,
        description="Variable costs as % of revenue"
    )
    fixed_cost_ratio: DecimalPercentage = Field(
        0,
        description="Fixed costs as % of revenue"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def profitability_status(self) -> str:
        """Assess overall profitability status."""
        if self.net_profit_margin >= 20:
            return "excellent"
        elif self.net_profit_margin >= 10:
            return "good"
        elif self.net_profit_margin >= 0:
            return "moderate"
        else:
            return "loss"


class BudgetComparison(BaseSchema):
    """
    Budget vs. actual comparison.
    
    Compares actual financial performance against
    budgeted targets for variance analysis.
    """
    
    category: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Budget category (revenue/expense type)"
    )
    budgeted_amount: DecimalAmount = Field(
        ...,
        description="Budgeted amount for the period"
    )
    actual_amount: DecimalAmount = Field(
        ...,
        description="Actual amount for the period"
    )
    variance_amount: DecimalAmount = Field(
        ...,
        description="Variance (actual - budgeted)"
    )
    variance_percentage: DecimalAmount = Field(
        ...,
        description="Variance as percentage of budget"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def is_favorable(self) -> bool:
        """
        Determine if variance is favorable.
        
        For revenue: actual > budgeted is favorable
        For expenses: actual < budgeted is favorable
        """
        # Assume revenue categories have positive variance when favorable
        # This should be contextualized by the caller
        return self.variance_amount >= 0
    
    @computed_field  # type: ignore[misc]
    @property
    def variance_severity(self) -> str:
        """Assess severity of budget variance."""
        abs_variance_pct = abs(float(self.variance_percentage))
        
        if abs_variance_pct <= 5:
            return "minor"
        elif abs_variance_pct <= 15:
            return "moderate"
        elif abs_variance_pct <= 30:
            return "significant"
        else:
            return "critical"


class TaxSummary(BaseSchema):
    """
    Tax-related summary for financial reporting.
    
    Provides tax liability and compliance information.
    """
    
    taxable_revenue: DecimalCurrency = Field(
        ...,
        description="Revenue subject to taxation"
    )
    tax_exempt_revenue: DecimalCurrency = Field(
        0,
        description="Tax-exempt revenue"
    )
    
    # Tax liabilities
    gst_collected: DecimalCurrency = Field(
        0,
        description="GST collected from customers"
    )
    gst_paid: DecimalCurrency = Field(
        0,
        description="GST paid on expenses"
    )
    gst_payable: DecimalAmount = Field(
        0,
        description="Net GST payable (collected - paid)"
    )
    
    tds_deducted: DecimalCurrency = Field(
        0,
        description="TDS deducted at source"
    )
    
    estimated_income_tax: DecimalCurrency = Field(
        0,
        description="Estimated income tax liability"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def effective_tax_rate(self) -> Decimal:
        """Calculate effective tax rate."""
        if self.taxable_revenue == 0:
            return Decimal("0.00")
        
        total_tax = self.gst_payable + self.estimated_income_tax
        return round(
            (total_tax / self.taxable_revenue) * 100,
            2
        )


class ProfitAndLossReport(BaseSchema):
    """
    Profit & Loss (P&L) statement.
    
    Comprehensive income statement showing revenue,
    expenses, and profitability for a period.
    """
    
    scope_type: str = Field(
        ...,
        pattern="^(hostel|platform)$",
        description="Scope of the P&L report"
    )
    scope_id: Optional[UUID] = Field(
        None,
        description="Hostel ID if scope is hostel"
    )
    scope_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Display name for the scope"
    )
    
    period: DateRangeFilter = Field(
        ...,
        description="Reporting period"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp"
    )
    
    # Revenue and expenses
    revenue: RevenueBreakdown = Field(
        ...,
        description="Revenue breakdown"
    )
    expenses: ExpenseBreakdown = Field(
        ...,
        description="Expense breakdown"
    )
    
    # Calculated values
    gross_profit: DecimalAmount = Field(
        ...,
        description="Gross profit (revenue - direct costs)"
    )
    operating_profit: DecimalAmount = Field(
        ...,
        description="Operating profit (gross profit - operating expenses)"
    )
    net_profit: DecimalAmount = Field(
        ...,
        description="Net profit after all expenses"
    )
    
    # Margins
    gross_profit_margin: DecimalAmount = Field(
        ...,
        description="Gross profit margin percentage"
    )
    operating_profit_margin: DecimalAmount = Field(
        ...,
        description="Operating profit margin percentage"
    )
    net_profit_margin: DecimalAmount = Field(
        ...,
        description="Net profit margin percentage"
    )
    
    # Legacy field
    profit_margin_percentage: DecimalAmount = Field(
        ...,
        description="Profit margin percentage (deprecated: use net_profit_margin)"
    )
    
    # Financial ratios
    ratios: Optional[FinancialRatios] = Field(
        None,
        description="Key financial ratios"
    )
    
    # Tax information
    tax_summary: Optional[TaxSummary] = Field(
        None,
        description="Tax-related summary"
    )
    
    # Budget comparison
    budget_comparisons: List[BudgetComparison] = Field(
        default_factory=list,
        description="Budget vs. actual comparisons"
    )
    
    @model_validator(mode="after")
    def validate_profit_calculations(self) -> "ProfitAndLossReport":
        """Validate profit calculations are consistent."""
        
        # Net profit should be revenue - total expenses
        expected_net = self.revenue.total_revenue - self.expenses.total_expenses
        if abs(self.net_profit - expected_net) > Decimal("0.01"):
            raise ValueError(
                f"Net profit ({self.net_profit}) should equal "
                f"revenue ({self.revenue.total_revenue}) - "
                f"expenses ({self.expenses.total_expenses})"
            )
        
        return self
    
    @computed_field  # type: ignore[misc]
    @property
    def is_profitable(self) -> bool:
        """Check if the period was profitable."""
        return self.net_profit > 0
    
    @computed_field  # type: ignore[misc]
    @property
    def break_even_revenue(self) -> Decimal:
        """
        Calculate break-even revenue.
        
        Revenue needed to cover all expenses.
        """
        return self.expenses.total_expenses
    
    @computed_field  # type: ignore[misc]
    @property
    def revenue_above_break_even(self) -> Decimal:
        """Calculate revenue above break-even point."""
        return max(
            Decimal("0.00"),
            self.revenue.total_revenue - self.break_even_revenue
        )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Generate performance summary.
        
        Returns:
            Dictionary with key performance insights
        """
        return {
            "is_profitable": self.is_profitable,
            "profitability_status": self.ratios.profitability_status if self.ratios else "unknown",
            "net_profit": float(self.net_profit),
            "net_profit_margin": float(self.net_profit_margin),
            "revenue_growth_needed": (
                0 if self.is_profitable
                else float(self.break_even_revenue - self.revenue.total_revenue)
            ),
            "largest_revenue_source": self.revenue.primary_revenue_source,
            "largest_expense_category": self.expenses.largest_expense_category,
            "collection_rate": float(self.revenue.collection_rate),
        }


class CashflowPoint(BaseSchema):
    """
    Single data point in cashflow time series.
    
    Represents cash movements for a specific date.
    """
    
    cashflow_date: Date = Field(
        ...,
        description="Date of cashflow point"
    )
    inflow: DecimalCurrency = Field(
        ...,
        description="Cash inflow for the day"
    )
    outflow: DecimalCurrency = Field(
        ...,
        description="Cash outflow for the day"
    )
    net_flow: DecimalAmount = Field(
        ...,
        description="Net cashflow (inflow - outflow)"
    )
    balance: DecimalAmount = Field(
        ...,
        description="Cumulative balance after this transaction"
    )
    
    @model_validator(mode="after")
    def validate_net_flow(self) -> "CashflowPoint":
        """Validate net flow calculation."""
        expected_net = self.inflow - self.outflow
        if abs(self.net_flow - expected_net) > Decimal("0.01"):
            raise ValueError(
                f"Net flow ({self.net_flow}) should equal "
                f"inflow ({self.inflow}) - outflow ({self.outflow})"
            )
        return self
    
    @computed_field  # type: ignore[misc]
    @property
    def is_positive_flow(self) -> bool:
        """Check if net flow is positive."""
        return self.net_flow > 0


class CashflowSummary(BaseSchema):
    """
    Cashflow summary and analysis.
    
    Provides comprehensive view of cash movements,
    working capital, and liquidity position.
    """
    
    scope_type: str = Field(
        ...,
        pattern="^(hostel|platform)$",
        description="Scope of cashflow analysis"
    )
    scope_id: Optional[UUID] = Field(
        None,
        description="Hostel ID if scope is hostel"
    )
    scope_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Display name"
    )
    
    period: DateRangeFilter = Field(
        ...,
        description="Analysis period"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp"
    )
    
    # Balances
    opening_balance: DecimalAmount = Field(
        ...,
        description="Cash balance at start of period"
    )
    closing_balance: DecimalAmount = Field(
        ...,
        description="Cash balance at end of period"
    )
    
    # Totals
    total_inflows: DecimalCurrency = Field(
        ...,
        description="Total cash inflows during period"
    )
    total_outflows: DecimalCurrency = Field(
        ...,
        description="Total cash outflows during period"
    )
    net_cashflow: DecimalAmount = Field(
        ...,
        description="Net cashflow for the period"
    )
    
    # Legacy fields
    inflows: DecimalCurrency = Field(
        ...,
        description="Total inflows (deprecated: use total_inflows)"
    )
    outflows: DecimalCurrency = Field(
        ...,
        description="Total outflows (deprecated: use total_outflows)"
    )
    
    # Breakdowns
    inflow_breakdown: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Inflows by category"
    )
    outflow_breakdown: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Outflows by category"
    )
    
    # Time series
    cashflow_timeseries: List[CashflowPoint] = Field(
        default_factory=list,
        description="Daily cashflow data points"
    )
    
    # Liquidity metrics
    average_daily_balance: DecimalAmount = Field(
        0,
        description="Average daily cash balance"
    )
    minimum_balance: DecimalAmount = Field(
        0,
        description="Minimum balance during period"
    )
    maximum_balance: DecimalAmount = Field(
        0,
        description="Maximum balance during period"
    )
    
    @model_validator(mode="after")
    def validate_cashflow_consistency(self) -> "CashflowSummary":
        """Validate cashflow calculations are consistent."""
        
        # Net cashflow should equal closing - opening
        expected_net = self.closing_balance - self.opening_balance
        if abs(self.net_cashflow - expected_net) > Decimal("0.01"):
            raise ValueError(
                f"Net cashflow ({self.net_cashflow}) should equal "
                f"closing ({self.closing_balance}) - opening ({self.opening_balance})"
            )
        
        # Net cashflow should also equal inflows - outflows
        expected_net_2 = self.total_inflows - self.total_outflows
        if abs(self.net_cashflow - expected_net_2) > Decimal("0.01"):
            raise ValueError(
                f"Net cashflow ({self.net_cashflow}) should equal "
                f"inflows ({self.total_inflows}) - outflows ({self.total_outflows})"
            )
        
        return self
    
    @field_validator("cashflow_timeseries")
    @classmethod
    def validate_chronological_order(
        cls,
        v: List[CashflowPoint]
    ) -> List[CashflowPoint]:
        """Ensure cashflow points are chronological."""
        if len(v) > 1:
            dates = [point.cashflow_date for point in v]
            if dates != sorted(dates):
                raise ValueError("Cashflow points must be in chronological order")
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def cashflow_health(self) -> str:
        """Assess overall cashflow health."""
        if self.closing_balance < 0:
            return "critical"
        elif self.net_cashflow < 0:
            return "warning"
        elif self.net_cashflow > self.total_outflows * Decimal("0.2"):
            return "excellent"
        else:
            return "good"
    
    @computed_field  # type: ignore[misc]
    @property
    def burn_rate_days(self) -> Optional[int]:
        """
        Calculate runway in days based on current burn rate.
        
        Returns:
            Number of days until cash runs out at current rate,
            or None if cashflow is positive
        """
        if self.net_cashflow >= 0:
            return None
        
        if len(self.cashflow_timeseries) == 0:
            return None
        
        # Calculate average daily burn
        days = len(self.cashflow_timeseries)
        daily_burn = abs(self.net_cashflow / Decimal(days))
        
        if daily_burn == 0:
            return None
        
        return int(self.closing_balance / daily_burn)
    
    @computed_field  # type: ignore[misc]
    @property
    def operating_cash_ratio(self) -> Decimal:
        """Calculate operating cash flow ratio."""
        if self.total_outflows == 0:
            return Decimal("0.00")
        return round(
            (self.total_inflows / self.total_outflows) * 100,
            2
        )


class FinancialReport(BaseSchema):
    """
    Comprehensive financial report.
    
    Consolidates P&L, cashflow, and key financial metrics
    into a single comprehensive financial statement.
    """
    
    scope_type: str = Field(
        ...,
        pattern="^(hostel|platform)$",
        description="Report scope"
    )
    scope_id: Optional[UUID] = Field(
        None,
        description="Hostel ID if applicable"
    )
    scope_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Display name"
    )
    
    period: DateRangeFilter = Field(
        ...,
        description="Reporting period"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp"
    )
    
    # Core financial statements
    pnl_report: ProfitAndLossReport = Field(
        ...,
        description="Profit & Loss statement"
    )
    cashflow: CashflowSummary = Field(
        ...,
        description="Cashflow analysis"
    )
    
    # Key metrics
    collection_rate: DecimalPercentage = Field(
        ...,
        description="Percentage of billed amount collected"
    )
    overdue_ratio: DecimalPercentage = Field(
        ...,
        description="Percentage of amount that is overdue"
    )
    avg_revenue_per_student: DecimalCurrency = Field(
        ...,
        description="Average revenue per student"
    )
    avg_revenue_per_bed: DecimalCurrency = Field(
        ...,
        description="Average revenue per bed"
    )
    
    # Operational metrics
    occupancy_rate: Optional[DecimalPercentage] = Field(
        None,
        description="Average occupancy rate during period"
    )
    average_daily_rate: Optional[DecimalCurrency] = Field(
        None,
        description="Average daily rate (ADR) charged"
    )
    
    # Year-over-year comparison
    revenue_growth_yoy: Optional[DecimalAmount] = Field(
        None,
        description="Year-over-year revenue growth percentage"
    )
    profit_growth_yoy: Optional[DecimalAmount] = Field(
        None,
        description="Year-over-year profit growth percentage"
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def financial_health_score(self) -> Decimal:
        """
        Calculate overall financial health score (0-100).
        
        Based on profitability, cashflow, and collection metrics.
        """
        score = Decimal("0.00")
        
        # Profitability (40 points)
        if self.pnl_report.is_profitable:
            profit_margin = self.pnl_report.net_profit_margin
            if profit_margin >= 20:
                score += Decimal("40")
            elif profit_margin >= 10:
                score += Decimal("30")
            elif profit_margin >= 5:
                score += Decimal("20")
            else:
                score += Decimal("10")
        
        # Cashflow (30 points)
        if self.cashflow.cashflow_health == "excellent":
            score += Decimal("30")
        elif self.cashflow.cashflow_health == "good":
            score += Decimal("20")
        elif self.cashflow.cashflow_health == "warning":
            score += Decimal("10")
        
        # Collections (30 points)
        if self.collection_rate >= 95:
            score += Decimal("30")
        elif self.collection_rate >= 85:
            score += Decimal("20")
        elif self.collection_rate >= 75:
            score += Decimal("10")
        
        return round(score, 2)
    
    @computed_field  # type: ignore[misc]
    @property
    def performance_grade(self) -> str:
        """Get letter grade for financial performance."""
        score = float(self.financial_health_score)
        
        if score >= 90:
            return "A+"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 50:
            return "D"
        else:
            return "F"
    
    def get_executive_summary(self) -> Dict[str, Any]:
        """
        Generate executive summary of financial performance.
        
        Returns:
            Dictionary with key insights for executive review
        """
        return {
            "period": {
                "start": self.period.start_date,
                "end": self.period.end_date,
            },
            "revenue": {
                "total": float(self.pnl_report.revenue.total_revenue),
                "growth_yoy": float(self.revenue_growth_yoy) if self.revenue_growth_yoy else None,
                "per_student": float(self.avg_revenue_per_student),
                "collection_rate": float(self.collection_rate),
            },
            "profitability": {
                "net_profit": float(self.pnl_report.net_profit),
                "margin": float(self.pnl_report.net_profit_margin),
                "status": self.pnl_report.ratios.profitability_status if self.pnl_report.ratios else "unknown",
            },
            "cashflow": {
                "closing_balance": float(self.cashflow.closing_balance),
                "net_flow": float(self.cashflow.net_cashflow),
                "health": self.cashflow.cashflow_health,
            },
            "overall": {
                "health_score": float(self.financial_health_score),
                "grade": self.performance_grade,
            },
        }