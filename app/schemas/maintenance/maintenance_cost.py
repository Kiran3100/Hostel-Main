# --- File: app/schemas/maintenance/maintenance_cost.py ---
"""
Maintenance cost tracking and budget management schemas.

Provides comprehensive cost tracking, budget allocation, expense reporting,
and vendor invoice management with detailed analytics.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Union

from pydantic import ConfigDict, Field, computed_field, field_validator, model_validator
from uuid import UUID

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "CostTracking",
    "BudgetAllocation",
    "CategoryBudget",
    "ExpenseReport",
    "MonthlyExpense",
    "ExpenseItem",
    "VendorInvoice",
    "InvoiceLineItem",
    "CostAnalysis",
]


class CostTracking(BaseSchema):
    """
    Cost tracking for maintenance request.
    
    Tracks estimated vs actual costs with variance analysis.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "request_number": "MNT-2024-001",
                "estimated_cost": "3000.00",
                "approved_cost": "3500.00",
                "actual_cost": "3200.00",
                "variance": "-300.00",
                "within_budget": True
            }
        }
    )

    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request unique identifier",
    )
    request_number: str = Field(
        ...,
        description="Request number",
    )
    # All cost fields using Annotated with decimal_places in v2
    estimated_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Original estimated cost",
    )
    approved_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Approved budget amount",
    )
    actual_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Actual cost incurred",
    )
    variance: Annotated[Decimal, Field(decimal_places=2)] = Field(
        ...,
        description="Cost variance (actual - approved)",
    )
    variance_percentage: Annotated[Decimal, Field(decimal_places=2)] = Field(
        ...,
        description="Variance as percentage of approved",
    )
    within_budget: bool = Field(
        ...,
        description="Whether actual cost is within approved budget",
    )
    materials_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Materials cost component",
    )
    labor_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Labor cost component",
    )
    vendor_charges: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="External vendor charges",
    )
    other_costs: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Other miscellaneous costs",
    )
    tax_amount: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Tax component",
    )

    @field_validator(
        "estimated_cost",
        "approved_cost",
        "actual_cost",
        "variance",
        "variance_percentage",
        "materials_cost",
        "labor_cost",
        "vendor_charges",
        "other_costs",
        "tax_amount",
    )
    @classmethod
    def round_amounts(cls, v: Decimal) -> Decimal:
        """Round monetary amounts to 2 decimal places."""
        return round(v, 2)

    @computed_field  # type: ignore[misc]
    @property
    def cost_breakdown_total(self) -> Decimal:
        """Calculate total from breakdown components."""
        return round(
            self.materials_cost
            + self.labor_cost
            + self.vendor_charges
            + self.other_costs
            + self.tax_amount,
            2,
        )


class CategoryBudget(BaseSchema):
    """
    Budget allocation for specific maintenance category.
    
    Tracks allocation, spending, and utilization per category.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "category": "Electrical",
                "category_code": "ELEC",
                "allocated": "500000.00",
                "spent": "350000.00",
                "remaining": "150000.00",
                "utilization_percentage": "70.00"
            }
        }
    )

    category: str = Field(
        ...,
        description="Maintenance category name",
    )
    category_code: Union[str, None] = Field(
        None,
        max_length=50,
        description="Category code",
    )
    allocated: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Allocated budget amount",
    )
    spent: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Amount spent",
    )
    committed: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Amount committed (approved but not paid)",
    )
    remaining: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Remaining budget",
    )
    utilization_percentage: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="Budget utilization percentage",
    )
    request_count: int = Field(
        default=0,
        ge=0,
        description="Number of maintenance requests",
    )
    average_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Average cost per request",
    )

    @field_validator(
        "allocated",
        "spent",
        "committed",
        "remaining",
        "utilization_percentage",
        "average_cost",
    )
    @classmethod
    def round_amounts(cls, v: Decimal) -> Decimal:
        """Round amounts to 2 decimal places."""
        return round(v, 2)

    @computed_field  # type: ignore[misc]
    @property
    def is_over_budget(self) -> bool:
        """Check if category is over budget."""
        return self.spent > self.allocated

    @computed_field  # type: ignore[misc]
    @property
    def available_for_commitment(self) -> Decimal:
        """Calculate amount available for new commitments."""
        return round(
            max(Decimal("0.00"), self.allocated - self.spent - self.committed),
            2,
        )


class BudgetAllocation(BaseSchema):
    """
    Overall budget allocation for hostel maintenance.
    
    Tracks fiscal year budget with category-wise breakdown
    and utilization metrics.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hostel_name": "North Campus Hostel A",
                "fiscal_year": "2024",
                "total_budget": "5000000.00",
                "spent_amount": "3500000.00",
                "remaining_budget": "1500000.00",
                "utilization_percentage": "70.00"
            }
        }
    )

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    fiscal_year: str = Field(
        ...,
        pattern=r"^\d{4}$",
        description="Fiscal year (YYYY format)",
    )
    fiscal_year_start: Date = Field(
        ...,
        description="Fiscal year start Date",
    )
    fiscal_year_end: Date = Field(
        ...,
        description="Fiscal year end Date",
    )
    total_budget: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total allocated budget",
    )
    allocated_budget: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Budget allocated to categories",
    )
    spent_amount: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total amount spent",
    )
    committed_amount: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Committed but not yet spent",
    )
    remaining_budget: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Remaining unallocated budget",
    )
    utilization_percentage: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="Overall budget utilization",
    )
    budget_by_category: Dict[str, CategoryBudget] = Field(
        ...,
        description="Budget breakdown by category",
    )
    reserve_fund: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Emergency reserve fund",
    )
    
    # Forecasting
    projected_annual_spend: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Projected annual spending",
    )
    burn_rate_monthly: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Average monthly spending rate",
    )

    @field_validator("fiscal_year_end")
    @classmethod
    def validate_fiscal_year(cls, v: Date, info) -> Date:
        """Validate fiscal year dates."""
        if "fiscal_year_start" in info.data:
            if v <= info.data["fiscal_year_start"]:
                raise ValueError("Fiscal year end must be after start")
        return v

    @computed_field  # type: ignore[misc]
    @property
    def is_over_budget(self) -> bool:
        """Check if overall budget is exceeded."""
        return self.spent_amount > self.total_budget

    @computed_field  # type: ignore[misc]
    @property
    def months_remaining(self) -> int:
        """Calculate months remaining in fiscal year."""
        today = Date.today()
        if today > self.fiscal_year_end:
            return 0
        
        months = (
            (self.fiscal_year_end.year - today.year) * 12
            + (self.fiscal_year_end.month - today.month)
        )
        return max(0, months)


class MonthlyExpense(BaseSchema):
    """
    Monthly expense summary.
    
    Aggregates maintenance expenses for a specific month.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "month": "2024-01",
                "month_name": "January",
                "year": 2024,
                "total_expenses": "450000.00",
                "request_count": 45,
                "average_cost": "10000.00"
            }
        }
    )

    month: str = Field(
        ...,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Month in YYYY-MM format",
    )
    month_name: str = Field(
        ...,
        description="Month name (January, February, etc.)",
    )
    year: int = Field(
        ...,
        ge=2000,
        le=2100,
        description="Year",
    )
    total_expenses: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total expenses for the month",
    )
    request_count: int = Field(
        ...,
        ge=0,
        description="Number of maintenance requests",
    )
    completed_count: int = Field(
        default=0,
        ge=0,
        description="Number of completed requests",
    )
    average_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average cost per request",
    )
    budget_allocated: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Budget allocated for the month",
    )
    variance_from_budget: Union[Annotated[Decimal, Field(decimal_places=2)], None] = Field(
        None,
        description="Variance from monthly budget",
    )

    @computed_field  # type: ignore[misc]
    @property
    def within_budget(self) -> Union[bool, None]:
        """Check if monthly expenses are within budget."""
        if self.budget_allocated is None:
            return None
        return self.total_expenses <= self.budget_allocated


class ExpenseItem(BaseSchema):
    """
    Individual expense item in reports.
    
    Represents single maintenance request in expense listings.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "request_number": "MNT-2024-001",
                "title": "Ceiling fan replacement",
                "category": "Electrical",
                "estimated_cost": "3000.00",
                "actual_cost": "3500.00",
                "cost_variance": "500.00"
            }
        }
    )

    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request unique identifier",
    )
    request_number: str = Field(
        ...,
        description="Request number",
    )
    title: str = Field(
        ...,
        description="Request title",
    )
    category: str = Field(
        ...,
        description="Maintenance category",
    )
    priority: str = Field(
        ...,
        description="Priority level",
    )
    estimated_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Estimated cost",
    )
    actual_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Actual cost incurred",
    )
    cost_variance: Annotated[Decimal, Field(decimal_places=2)] = Field(
        ...,
        description="Cost variance amount",
    )
    completion_date: Date = Field(
        ...,
        description="Completion Date",
    )
    vendor_name: Union[str, None] = Field(
        None,
        description="Vendor name (if applicable)",
    )

    @computed_field  # type: ignore[misc]
    @property
    def over_budget(self) -> bool:
        """Check if expense was over estimated cost."""
        return self.actual_cost > self.estimated_cost


class ExpenseReport(BaseSchema):
    """
    Comprehensive maintenance expense report.
    
    Provides detailed expense analysis with multiple dimensions
    and top expense listings.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hostel_name": "North Campus Hostel A",
                "total_expenses": "1500000.00",
                "total_requests": 150,
                "completed_requests": 142,
                "average_cost_per_request": "10000.00"
            }
        }
    )

    hostel_id: Union[UUID, None] = Field(
        None,
        description="Hostel ID (if hostel-specific)",
    )
    hostel_name: Union[str, None] = Field(
        None,
        description="Hostel name",
    )
    report_period: DateRangeFilter = Field(
        ...,
        description="Report period",
    )
    generated_at: datetime = Field(
        ...,
        description="Report generation timestamp",
    )
    generated_by: Union[UUID, None] = Field(
        None,
        description="User who generated report",
    )
    
    # Summary statistics
    total_expenses: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total expenses in period",
    )
    total_requests: int = Field(
        ...,
        ge=0,
        description="Total maintenance requests",
    )
    completed_requests: int = Field(
        ...,
        ge=0,
        description="Completed requests",
    )
    average_cost_per_request: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average cost per request",
    )
    
    # Budget comparison
    total_budget: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Total budget for period",
    )
    budget_utilization: Union[Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)], None] = Field(
        None,
        description="Budget utilization percentage",
    )
    
    # Breakdown by category - Decimal values in dict
    expenses_by_category: Dict[str, Decimal] = Field(
        ...,
        description="Expenses grouped by category",
    )
    requests_by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Request count by category",
    )
    
    # Monthly breakdown
    monthly_expenses: List[MonthlyExpense] = Field(
        ...,
        description="Month-by-month expenses",
    )
    
    # Priority-based breakdown
    expenses_by_priority: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Expenses grouped by priority",
    )
    
    # Top expenses
    top_expensive_requests: List[ExpenseItem] = Field(
        default_factory=list,
        max_length=50,
        description="Highest cost maintenance requests",
    )
    
    # Vendor analysis
    top_vendors_by_spending: Union[List[Dict[str, Any]], None] = Field(
        None,
        max_length=20,
        description="Top vendors by total spending",
    )

    @computed_field  # type: ignore[misc]
    @property
    def completion_rate(self) -> Decimal:
        """Calculate completion rate percentage."""
        if self.total_requests == 0:
            return Decimal("0.00")
        return round(
            Decimal(self.completed_requests) / Decimal(self.total_requests) * 100,
            2,
        )


class InvoiceLineItem(BaseSchema):
    """
    Line item in vendor invoice.
    
    Represents individual item/service in invoice.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "line_number": 1,
                "description": "Ceiling fan - 1200mm",
                "quantity": "2.000",
                "unit": "pcs",
                "unit_price": "1500.00",
                "total_price": "3000.00"
            }
        }
    )

    line_number: int = Field(
        ...,
        ge=1,
        description="Line item number",
    )
    description: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Item/service description",
    )
    item_code: Union[str, None] = Field(
        None,
        max_length=50,
        description="Item code/SKU",
    )
    quantity: Annotated[Decimal, Field(gt=0, decimal_places=3)] = Field(
        ...,
        description="Quantity",
    )
    unit: str = Field(
        ...,
        max_length=20,
        description="Unit of measurement",
    )
    unit_price: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Price per unit",
    )
    total_price: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total line price",
    )
    tax_rate: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Tax rate percentage",
    )
    tax_amount: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Tax amount",
    )

    @model_validator(mode="after")
    def validate_pricing(self) -> "InvoiceLineItem":
        """
        Validate pricing calculations.
        
        Ensures total_price = quantity × unit_price (pre-tax).
        """
        calculated_total = self.quantity * self.unit_price
        
        # Allow small rounding differences
        if abs(calculated_total - self.total_price) > Decimal("0.01"):
            raise ValueError(
                f"Total price ({self.total_price}) doesn't match "
                f"quantity ({self.quantity}) × unit price ({self.unit_price})"
            )
        
        # Validate tax calculation if tax_rate > 0
        if self.tax_rate > 0:
            calculated_tax = self.total_price * self.tax_rate / 100
            if abs(calculated_tax - self.tax_amount) > Decimal("0.01"):
                raise ValueError(
                    f"Tax amount ({self.tax_amount}) doesn't match "
                    f"total price ({self.total_price}) × tax rate ({self.tax_rate}%)"
                )
        
        return self


class VendorInvoice(BaseCreateSchema):
    """
    Vendor invoice for maintenance work.
    
    Comprehensive invoice tracking with line items, taxes,
    and payment terms.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "vendor_name": "ABC Electricals",
                "invoice_number": "INV-2024-001",
                "invoice_date": "2024-01-20",
                "subtotal": "3000.00",
                "tax_amount": "540.00",
                "total_amount": "3540.00",
                "payment_terms": "Net 30",
                "due_date": "2024-02-20"
            }
        }
    )

    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request unique identifier",
    )
    vendor_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Vendor company name",
    )
    vendor_id: Union[UUID, None] = Field(
        None,
        description="Vendor ID in system (if registered)",
    )
    vendor_address: Union[str, None] = Field(
        None,
        max_length=500,
        description="Vendor billing address",
    )
    vendor_tax_id: Union[str, None] = Field(
        None,
        max_length=50,
        description="Vendor tax ID/GST number",
    )
    invoice_number: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Vendor invoice number",
    )
    invoice_date: Date = Field(
        ...,
        description="Invoice issue Date",
    )
    purchase_order_number: Union[str, None] = Field(
        None,
        max_length=100,
        description="Our purchase order number",
    )
    line_items: List[InvoiceLineItem] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Invoice line items",
    )
    subtotal: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Subtotal (before tax)",
    )
    tax_amount: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total tax amount",
    )
    discount_amount: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        default=Decimal("0.00"),
        description="Discount amount",
    )
    total_amount: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Total invoice amount",
    )
    payment_terms: str = Field(
        ...,
        max_length=200,
        description="Payment terms (e.g., Net 30, Due on receipt)",
    )
    due_date: Date = Field(
        ...,
        description="Payment due Date",
    )
    currency: str = Field(
        default="INR",
        max_length=3,
        description="Currency code (ISO 4217)",
    )
    invoice_document_url: Union[str, None] = Field(
        None,
        description="URL to invoice document/PDF",
    )
    notes: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Additional notes",
    )

    @field_validator("invoice_date", "due_date")
    @classmethod
    def validate_dates(cls, v: Date) -> Date:
        """Validate invoice dates are reasonable."""
        # Invoice Date shouldn't be too far in past or future
        days_diff = abs((Date.today() - v).days)
        if days_diff > 365:
            raise ValueError(
                "Invoice Date cannot be more than 1 year from today"
            )
        return v

    @model_validator(mode="after")
    def validate_invoice_totals(self) -> "VendorInvoice":
        """
        Validate invoice calculations.
        
        Ensures subtotal matches line items and total is calculated correctly.
        """
        # Validate subtotal matches line items
        line_items_total = sum(item.total_price for item in self.line_items)
        
        if abs(line_items_total - self.subtotal) > Decimal("0.01"):
            raise ValueError(
                f"Subtotal ({self.subtotal}) doesn't match sum of line items ({line_items_total})"
            )
        
        # Validate total calculation
        calculated_total = self.subtotal + self.tax_amount - self.discount_amount
        
        if abs(calculated_total - self.total_amount) > Decimal("0.01"):
            raise ValueError(
                f"Total amount ({self.total_amount}) doesn't match "
                f"subtotal ({self.subtotal}) + tax ({self.tax_amount}) - discount ({self.discount_amount})"
            )
        
        # Due Date should be on or after invoice Date
        if self.due_date < self.invoice_date:
            raise ValueError("Due Date cannot be before invoice Date")
        
        return self


class CostAnalysis(BaseSchema):
    """
    Cost analysis and trends.
    
    Provides insights into cost patterns, trends, and efficiency metrics.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hostel_name": "North Campus Hostel A",
                "cost_trend": "decreasing",
                "trend_percentage": "-5.50",
                "highest_cost_category": "Electrical",
                "cost_per_student": "500.00",
                "cost_per_room": "2500.00"
            }
        }
    )

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    analysis_period: DateRangeFilter = Field(
        ...,
        description="Analysis period",
    )
    previous_period: Union[DateRangeFilter, None] = Field(
        None,
        description="Previous period for comparison",
    )
    
    # Cost trends
    cost_trend: str = Field(
        ...,
        pattern=r"^(increasing|decreasing|stable)$",
        description="Overall cost trend direction",
    )
    trend_percentage: Annotated[Decimal, Field(decimal_places=2)] = Field(
        ...,
        description="Trend change percentage",
    )
    
    # Cost drivers
    highest_cost_category: str = Field(
        ...,
        description="Category with highest total cost",
    )
    highest_cost_category_amount: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Amount spent in highest cost category",
    )
    most_frequent_category: str = Field(
        ...,
        description="Most frequently occurring category",
    )
    most_frequent_category_count: int = Field(
        ...,
        ge=0,
        description="Request count for most frequent category",
    )
    
    # Efficiency metrics
    cost_per_student: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average maintenance cost per student",
    )
    cost_per_room: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Average maintenance cost per room",
    )
    cost_per_sqft: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Cost per square foot",
    )
    
    # Performance benchmarks
    comparison_to_previous_period: Annotated[Decimal, Field(decimal_places=2)] = Field(
        ...,
        description="Percentage change from previous period",
    )
    comparison_to_budget: Union[Annotated[Decimal, Field(decimal_places=2)], None] = Field(
        None,
        description="Percentage variance from budget",
    )
    
    # Predictive insights
    projected_annual_cost: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        None,
        description="Projected annual cost based on trends",
    )
    seasonal_variation: Union[Annotated[Decimal, Field(decimal_places=2)], None] = Field(
        None,
        description="Seasonal variation coefficient",
    )
    
    # Recommendations
    cost_saving_opportunities: Union[List[str], None] = Field(
        None,
        max_length=10,
        description="Identified cost-saving opportunities",
    )
    risk_areas: Union[List[str], None] = Field(
        None,
        max_length=10,
        description="Areas of cost risk",
    )