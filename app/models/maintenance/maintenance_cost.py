# app/models/maintenance/maintenance_cost.py
"""
Maintenance cost tracking and budget management models.

Comprehensive cost tracking, budget allocation, expense reporting,
and financial analytics for maintenance operations.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin, AuditMixin


class MaintenanceCost(UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin, BaseModel):
    """
    Cost tracking for maintenance requests.
    
    Tracks estimated vs actual costs with variance analysis
    and budget compliance monitoring.
    """
    
    __tablename__ = "maintenance_costs"
    
    maintenance_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related maintenance request",
    )
    
    # Cost tracking
    estimated_cost = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Original estimated cost",
    )
    
    approved_cost = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Approved budget amount",
    )
    
    actual_cost = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Actual cost incurred",
    )
    
    # Variance analysis
    variance = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Cost variance (actual - approved)",
    )
    
    variance_percentage = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Variance as percentage of approved",
    )
    
    within_budget = Column(
        Boolean,
        nullable=True,
        index=True,
        comment="Whether actual cost is within approved budget",
    )
    
    # Cost components
    materials_cost = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Materials cost component",
    )
    
    labor_cost = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Labor cost component",
    )
    
    vendor_charges = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="External vendor charges",
    )
    
    other_costs = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Other miscellaneous costs",
    )
    
    tax_amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Tax component",
    )
    
    # Detailed breakdown
    cost_breakdown = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Detailed cost breakdown",
    )
    
    # Budget allocation
    budget_source = Column(
        String(100),
        nullable=True,
        comment="Budget source/allocation",
    )
    
    cost_center = Column(
        String(100),
        nullable=True,
        comment="Cost center code",
    )
    
    # Metadata - renamed from 'metadata' to avoid conflict
    additional_data = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional cost metadata",
    )
    
    # Relationships
    maintenance_request = relationship(
        "MaintenanceRequest",
        back_populates="cost_records"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "estimated_cost >= 0",
            name="ck_cost_estimated_positive"
        ),
        CheckConstraint(
            "approved_cost >= 0",
            name="ck_cost_approved_positive"
        ),
        CheckConstraint(
            "actual_cost >= 0",
            name="ck_cost_actual_positive"
        ),
        CheckConstraint(
            "materials_cost >= 0",
            name="ck_cost_materials_positive"
        ),
        CheckConstraint(
            "labor_cost >= 0",
            name="ck_cost_labor_positive"
        ),
        CheckConstraint(
            "vendor_charges >= 0",
            name="ck_cost_vendor_positive"
        ),
        CheckConstraint(
            "other_costs >= 0",
            name="ck_cost_other_positive"
        ),
        CheckConstraint(
            "tax_amount >= 0",
            name="ck_cost_tax_positive"
        ),
        Index("idx_cost_request", "maintenance_request_id"),
        Index("idx_cost_within_budget", "within_budget"),
        {"comment": "Cost tracking for maintenance requests"}
    )
    
    def __repr__(self) -> str:
        return f"<MaintenanceCost request={self.maintenance_request_id} actual={self.actual_cost}>"
    
    @validates("estimated_cost", "approved_cost", "actual_cost", "materials_cost", "labor_cost", "vendor_charges", "other_costs", "tax_amount")
    def validate_positive_amounts(self, key: str, value: Optional[Decimal]) -> Optional[Decimal]:
        """Validate amounts are positive."""
        if value is not None and value < 0:
            raise ValueError(f"{key} must be positive")
        return value
    
    @hybrid_property
    def cost_breakdown_total(self) -> Decimal:
        """Calculate total from breakdown components."""
        return (
            self.materials_cost +
            self.labor_cost +
            self.vendor_charges +
            self.other_costs +
            self.tax_amount
        )
    
    def calculate_variance(self) -> None:
        """Calculate cost variance and percentage."""
        if self.actual_cost is not None:
            self.variance = self.actual_cost - self.approved_cost
            if self.approved_cost > 0:
                self.variance_percentage = (self.variance / self.approved_cost) * 100
            else:
                self.variance_percentage = Decimal("0.00")
            self.within_budget = self.actual_cost <= self.approved_cost


class BudgetAllocation(UUIDMixin, TimestampModel, BaseModel):
    """
    Budget allocation for hostel maintenance.
    
    Tracks fiscal year budget with category-wise breakdown
    and utilization metrics.
    """
    
    __tablename__ = "budget_allocations"
    
    hostel_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel unique identifier",
    )
    
    # Fiscal year
    fiscal_year = Column(
        String(4),
        nullable=False,
        comment="Fiscal year (YYYY format)",
    )
    
    fiscal_year_start = Column(
        Date,
        nullable=False,
        comment="Fiscal year start date",
    )
    
    fiscal_year_end = Column(
        Date,
        nullable=False,
        comment="Fiscal year end date",
    )
    
    # Budget amounts
    total_budget = Column(
        Numeric(12, 2),
        nullable=False,
        comment="Total allocated budget",
    )
    
    allocated_budget = Column(
        Numeric(12, 2),
        nullable=False,
        comment="Budget allocated to categories",
    )
    
    spent_amount = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total amount spent",
    )
    
    committed_amount = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Committed but not yet spent",
    )
    
    remaining_budget = Column(
        Numeric(12, 2),
        nullable=False,
        comment="Remaining unallocated budget",
    )
    
    # Utilization
    utilization_percentage = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Overall budget utilization",
    )
    
    # Category breakdown
    budget_by_category = Column(
        JSONB,
        nullable=False,
        default={},
        comment="Budget breakdown by category",
    )
    
    # Reserve fund
    reserve_fund = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Emergency reserve fund",
    )
    
    # Forecasting
    projected_annual_spend = Column(
        Numeric(12, 2),
        nullable=True,
        comment="Projected annual spending",
    )
    
    burn_rate_monthly = Column(
        Numeric(12, 2),
        nullable=True,
        comment="Average monthly spending rate",
    )
    
    # Status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether this budget is active",
    )
    
    # Metadata - renamed from 'metadata' to avoid conflict
    additional_data = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional budget metadata",
    )
    
    # Relationships
    hostel = relationship("Hostel", back_populates="budget_allocations")
    category_budgets = relationship(
        "CategoryBudget",
        back_populates="budget_allocation",
        cascade="all, delete-orphan"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "total_budget >= 0",
            name="ck_budget_total_positive"
        ),
        CheckConstraint(
            "allocated_budget >= 0",
            name="ck_budget_allocated_positive"
        ),
        CheckConstraint(
            "spent_amount >= 0",
            name="ck_budget_spent_positive"
        ),
        CheckConstraint(
            "committed_amount >= 0",
            name="ck_budget_committed_positive"
        ),
        CheckConstraint(
            "reserve_fund >= 0",
            name="ck_budget_reserve_positive"
        ),
        CheckConstraint(
            "utilization_percentage >= 0 AND utilization_percentage <= 100",
            name="ck_budget_utilization_range"
        ),
        Index("idx_budget_hostel_year", "hostel_id", "fiscal_year"),
        Index("idx_budget_active", "is_active"),
        {"comment": "Budget allocation for hostel maintenance"}
    )
    
    def __repr__(self) -> str:
        return f"<BudgetAllocation hostel={self.hostel_id} FY={self.fiscal_year}>"
    
    @hybrid_property
    def is_over_budget(self) -> bool:
        """Check if overall budget is exceeded."""
        return self.spent_amount > self.total_budget
    
    @hybrid_property
    def available_budget(self) -> Decimal:
        """Calculate available budget (total - spent - committed)."""
        return self.total_budget - self.spent_amount - self.committed_amount
    
    def update_utilization(self) -> None:
        """Update budget utilization percentage."""
        if self.total_budget > 0:
            self.utilization_percentage = (self.spent_amount / self.total_budget) * 100
        else:
            self.utilization_percentage = Decimal("0.00")


class CategoryBudget(UUIDMixin, TimestampModel, BaseModel):
    """
    Budget allocation for specific maintenance category.
    
    Tracks allocation, spending, and utilization per category.
    """
    
    __tablename__ = "category_budgets"
    
    budget_allocation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("budget_allocations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related budget allocation",
    )
    
    # Category
    category = Column(
        String(100),
        nullable=False,
        comment="Maintenance category name",
    )
    
    category_code = Column(
        String(50),
        nullable=True,
        comment="Category code",
    )
    
    # Budget amounts
    allocated = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Allocated budget amount",
    )
    
    spent = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Amount spent",
    )
    
    committed = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Amount committed (approved but not paid)",
    )
    
    remaining = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Remaining budget",
    )
    
    utilization_percentage = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Budget utilization percentage",
    )
    
    # Request tracking
    request_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of maintenance requests",
    )
    
    average_cost = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average cost per request",
    )
    
    # Metadata - renamed from 'metadata' to avoid conflict
    additional_data = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional category budget metadata",
    )
    
    # Relationships
    budget_allocation = relationship(
        "BudgetAllocation",
        back_populates="category_budgets"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "allocated >= 0",
            name="ck_category_budget_allocated_positive"
        ),
        CheckConstraint(
            "spent >= 0",
            name="ck_category_budget_spent_positive"
        ),
        CheckConstraint(
            "committed >= 0",
            name="ck_category_budget_committed_positive"
        ),
        CheckConstraint(
            "remaining >= 0",
            name="ck_category_budget_remaining_positive"
        ),
        CheckConstraint(
            "utilization_percentage >= 0 AND utilization_percentage <= 100",
            name="ck_category_budget_utilization_range"
        ),
        CheckConstraint(
            "request_count >= 0",
            name="ck_category_budget_request_count_positive"
        ),
        CheckConstraint(
            "average_cost >= 0",
            name="ck_category_budget_average_cost_positive"
        ),
        Index("idx_category_budget_allocation", "budget_allocation_id", "category"),
        {"comment": "Budget allocation per maintenance category"}
    )
    
    def __repr__(self) -> str:
        return f"<CategoryBudget {self.category} allocated={self.allocated}>"
    
    @hybrid_property
    def is_over_budget(self) -> bool:
        """Check if category is over budget."""
        return self.spent > self.allocated
    
    @hybrid_property
    def available_for_commitment(self) -> Decimal:
        """Calculate amount available for new commitments."""
        return max(Decimal("0.00"), self.allocated - self.spent - self.committed)
    
    def update_utilization(self) -> None:
        """Update budget utilization percentage."""
        if self.allocated > 0:
            self.utilization_percentage = (self.spent / self.allocated) * 100
        else:
            self.utilization_percentage = Decimal("0.00")
        
        self.remaining = self.allocated - self.spent
        
        if self.request_count > 0:
            self.average_cost = self.spent / self.request_count
        else:
            self.average_cost = Decimal("0.00")


class VendorInvoice(UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin, BaseModel):
    """
    Vendor invoice for maintenance work.
    
    Comprehensive invoice tracking with line items, taxes,
    and payment terms.
    """
    
    __tablename__ = "vendor_invoices"
    
    maintenance_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related maintenance request",
    )
    
    vendor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_vendors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Vendor ID in system",
    )
    
    # Vendor details (denormalized)
    vendor_name = Column(
        String(255),
        nullable=False,
        comment="Vendor company name",
    )
    
    vendor_address = Column(
        Text,
        nullable=True,
        comment="Vendor billing address",
    )
    
    vendor_tax_id = Column(
        String(50),
        nullable=True,
        comment="Vendor tax ID/GST number",
    )
    
    # Invoice details
    invoice_number = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Vendor invoice number",
    )
    
    invoice_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Invoice issue date",
    )
    
    purchase_order_number = Column(
        String(100),
        nullable=True,
        comment="Our purchase order number",
    )
    
    # Line items
    line_items = Column(
        JSONB,
        nullable=False,
        default=[],
        comment="Invoice line items",
    )
    
    # Amounts
    subtotal = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Subtotal (before tax)",
    )
    
    tax_amount = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Total tax amount",
    )
    
    discount_amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Discount amount",
    )
    
    total_amount = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Total invoice amount",
    )
    
    # Payment terms
    payment_terms = Column(
        String(200),
        nullable=False,
        comment="Payment terms",
    )
    
    due_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Payment due date",
    )
    
    currency = Column(
        String(3),
        nullable=False,
        default="INR",
        comment="Currency code (ISO 4217)",
    )
    
    # Payment tracking
    payment_status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Payment status (pending, partial, paid, overdue)",
    )
    
    paid_amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Amount paid",
    )
    
    paid_date = Column(
        Date,
        nullable=True,
        comment="Payment date",
    )
    
    # Documents
    invoice_document_url = Column(
        String(500),
        nullable=True,
        comment="URL to invoice document/PDF",
    )
    
    notes = Column(
        Text,
        nullable=True,
        comment="Additional notes",
    )
    
    # Metadata - renamed from 'metadata' to avoid conflict
    additional_data = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional invoice metadata",
    )
    
    # Relationships
    maintenance_request = relationship(
        "MaintenanceRequest",
        back_populates="vendor_invoices"
    )
    vendor = relationship(
        "MaintenanceVendor",
        back_populates="invoices"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "subtotal >= 0",
            name="ck_invoice_subtotal_positive"
        ),
        CheckConstraint(
            "tax_amount >= 0",
            name="ck_invoice_tax_positive"
        ),
        CheckConstraint(
            "discount_amount >= 0",
            name="ck_invoice_discount_positive"
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="ck_invoice_total_positive"
        ),
        CheckConstraint(
            "paid_amount >= 0",
            name="ck_invoice_paid_positive"
        ),
        Index("idx_invoice_vendor", "vendor_id", "invoice_date"),
        Index("idx_invoice_payment_status", "payment_status", "due_date"),
        {"comment": "Vendor invoices for maintenance work"}
    )
    
    def __repr__(self) -> str:
        return f"<VendorInvoice {self.invoice_number} - {self.vendor_name}>"
    
    @validates("subtotal", "tax_amount", "discount_amount", "total_amount", "paid_amount")
    def validate_positive_amounts(self, key: str, value: Decimal) -> Decimal:
        """Validate amounts are positive."""
        if value < 0:
            raise ValueError(f"{key} must be positive")
        return value
    
    @hybrid_property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue."""
        if self.payment_status == "paid":
            return False
        return date.today() > self.due_date
    
    @hybrid_property
    def balance_due(self) -> Decimal:
        """Calculate balance due."""
        return self.total_amount - self.paid_amount
    
    def mark_paid(self, paid_amount: Decimal, paid_date: Optional[date] = None) -> None:
        """
        Mark invoice as paid.
        
        Args:
            paid_amount: Amount paid
            paid_date: Payment date (defaults to today)
        """
        self.paid_amount = paid_amount
        self.paid_date = paid_date or date.today()
        
        if self.paid_amount >= self.total_amount:
            self.payment_status = "paid"
        elif self.paid_amount > 0:
            self.payment_status = "partial"
        
        # Check if overdue
        if self.is_overdue and self.payment_status != "paid":
            self.payment_status = "overdue"


class ExpenseReport(UUIDMixin, TimestampModel, BaseModel):
    """
    Maintenance expense report.
    
    Aggregated expense data for reporting and analytics.
    """
    
    __tablename__ = "expense_reports"
    
    hostel_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Hostel ID (NULL for system-wide)",
    )
    
    # Report period
    report_period_start = Column(
        Date,
        nullable=False,
        comment="Report period start date",
    )
    
    report_period_end = Column(
        Date,
        nullable=False,
        comment="Report period end date",
    )
    
    report_type = Column(
        String(50),
        nullable=False,
        comment="Report type (monthly, quarterly, annual)",
    )
    
    # Generation details
    generated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who generated report",
    )
    
    # Summary statistics
    total_expenses = Column(
        Numeric(12, 2),
        nullable=False,
        comment="Total expenses in period",
    )
    
    total_requests = Column(
        Integer,
        nullable=False,
        comment="Total maintenance requests",
    )
    
    completed_requests = Column(
        Integer,
        nullable=False,
        comment="Completed requests",
    )
    
    average_cost_per_request = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Average cost per request",
    )
    
    # Budget comparison
    total_budget = Column(
        Numeric(12, 2),
        nullable=True,
        comment="Total budget for period",
    )
    
    budget_utilization = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Budget utilization percentage",
    )
    
    # Breakdowns
    expenses_by_category = Column(
        JSONB,
        nullable=False,
        default={},
        comment="Expenses grouped by category",
    )
    
    requests_by_category = Column(
        JSONB,
        nullable=False,
        default={},
        comment="Request count by category",
    )
    
    expenses_by_priority = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Expenses grouped by priority",
    )
    
    # Monthly breakdown
    monthly_expenses = Column(
        JSONB,
        nullable=True,
        default=[],
        comment="Month-by-month expenses",
    )
    
    # Top expenses
    top_expensive_requests = Column(
        JSONB,
        nullable=True,
        default=[],
        comment="Highest cost maintenance requests",
    )
    
    # Vendor analysis
    top_vendors_by_spending = Column(
        JSONB,
        nullable=True,
        default=[],
        comment="Top vendors by total spending",
    )
    
    # Report data
    report_data = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Complete report data",
    )
    
    # Metadata - renamed from 'metadata' to avoid conflict
    additional_data = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional report metadata",
    )
    
    # Relationships
    hostel = relationship("Hostel", back_populates="expense_reports")
    generator = relationship("User")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "total_expenses >= 0",
            name="ck_expense_report_total_positive"
        ),
        CheckConstraint(
            "total_requests >= 0",
            name="ck_expense_report_requests_positive"
        ),
        CheckConstraint(
            "completed_requests >= 0",
            name="ck_expense_report_completed_positive"
        ),
        CheckConstraint(
            "average_cost_per_request >= 0",
            name="ck_expense_report_average_positive"
        ),
        Index("idx_expense_report_hostel_period", "hostel_id", "report_period_start"),
        Index("idx_expense_report_type", "report_type"),
        {"comment": "Maintenance expense reports"}
    )
    
    def __repr__(self) -> str:
        return f"<ExpenseReport {self.report_type} {self.report_period_start} to {self.report_period_end}>"
    
    @hybrid_property
    def completion_rate(self) -> Decimal:
        """Calculate completion rate percentage."""
        if self.total_requests == 0:
            return Decimal("0.00")
        return round(
            Decimal(self.completed_requests) / Decimal(self.total_requests) * 100,
            2
        )