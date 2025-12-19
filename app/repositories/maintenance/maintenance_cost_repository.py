# app/repositories/maintenance/maintenance_cost_repository.py
"""
Maintenance Cost Repository.

Cost tracking, budget management, and financial analytics
for maintenance operations.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.maintenance import (
    MaintenanceCost,
    BudgetAllocation,
    CategoryBudget,
    VendorInvoice,
    ExpenseReport,
    MaintenanceRequest,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.schemas.common.enums import MaintenanceCategory


class MaintenanceCostRepository(BaseRepository[MaintenanceCost]):
    """
    Repository for maintenance cost operations.
    
    Manages cost tracking, variance analysis, and budget compliance
    with comprehensive financial reporting.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with session."""
        super().__init__(MaintenanceCost, session)
    
    # ============================================================================
    # CREATE OPERATIONS
    # ============================================================================
    
    def create_cost_record(
        self,
        maintenance_request_id: UUID,
        estimated_cost: Decimal,
        approved_cost: Decimal,
        actual_cost: Optional[Decimal] = None,
        materials_cost: Decimal = Decimal("0.00"),
        labor_cost: Decimal = Decimal("0.00"),
        vendor_charges: Decimal = Decimal("0.00"),
        other_costs: Decimal = Decimal("0.00"),
        tax_amount: Decimal = Decimal("0.00"),
        cost_breakdown: Optional[Dict[str, Any]] = None,
        budget_source: Optional[str] = None,
        cost_center: Optional[str] = None,
        **kwargs
    ) -> MaintenanceCost:
        """
        Create cost tracking record.
        
        Args:
            maintenance_request_id: Request identifier
            estimated_cost: Original estimate
            approved_cost: Approved budget
            actual_cost: Actual cost incurred
            materials_cost: Materials component
            labor_cost: Labor component
            vendor_charges: Vendor charges
            other_costs: Other costs
            tax_amount: Tax component
            cost_breakdown: Detailed breakdown
            budget_source: Budget source
            cost_center: Cost center code
            **kwargs: Additional cost attributes
            
        Returns:
            Created cost record
        """
        cost_data = {
            "maintenance_request_id": maintenance_request_id,
            "estimated_cost": estimated_cost,
            "approved_cost": approved_cost,
            "actual_cost": actual_cost,
            "materials_cost": materials_cost,
            "labor_cost": labor_cost,
            "vendor_charges": vendor_charges,
            "other_costs": other_costs,
            "tax_amount": tax_amount,
            "cost_breakdown": cost_breakdown or {},
            "budget_source": budget_source,
            "cost_center": cost_center,
            **kwargs
        }
        
        cost_record = self.create(cost_data)
        
        # Calculate variance if actual cost is provided
        if actual_cost is not None:
            cost_record.calculate_variance()
            self.session.commit()
            self.session.refresh(cost_record)
        
        return cost_record
    
    def create_budget_allocation(
        self,
        hostel_id: UUID,
        fiscal_year: str,
        fiscal_year_start: datetime,
        fiscal_year_end: datetime,
        total_budget: Decimal,
        budget_by_category: Dict[str, Decimal],
        reserve_fund: Decimal = Decimal("0.00"),
        **kwargs
    ) -> BudgetAllocation:
        """
        Create budget allocation for hostel.
        
        Args:
            hostel_id: Hostel identifier
            fiscal_year: Fiscal year (YYYY)
            fiscal_year_start: FY start date
            fiscal_year_end: FY end date
            total_budget: Total allocated budget
            budget_by_category: Category-wise budget
            reserve_fund: Reserve fund amount
            **kwargs: Additional budget attributes
            
        Returns:
            Created budget allocation
        """
        # Calculate allocated budget
        allocated_budget = sum(budget_by_category.values())
        remaining_budget = total_budget - allocated_budget - reserve_fund
        
        budget_data = {
            "hostel_id": hostel_id,
            "fiscal_year": fiscal_year,
            "fiscal_year_start": fiscal_year_start.date() if isinstance(fiscal_year_start, datetime) else fiscal_year_start,
            "fiscal_year_end": fiscal_year_end.date() if isinstance(fiscal_year_end, datetime) else fiscal_year_end,
            "total_budget": total_budget,
            "allocated_budget": allocated_budget,
            "remaining_budget": remaining_budget,
            "reserve_fund": reserve_fund,
            "budget_by_category": budget_by_category,
            "is_active": True,
            **kwargs
        }
        
        budget_allocation = BudgetAllocation(**budget_data)
        self.session.add(budget_allocation)
        self.session.commit()
        self.session.refresh(budget_allocation)
        
        # Create category budgets
        for category, amount in budget_by_category.items():
            self._create_category_budget(
                budget_allocation.id,
                category,
                amount
            )
        
        return budget_allocation
    
    def create_vendor_invoice(
        self,
        maintenance_request_id: UUID,
        vendor_id: UUID,
        vendor_name: str,
        invoice_number: str,
        invoice_date: datetime,
        subtotal: Decimal,
        tax_amount: Decimal,
        total_amount: Decimal,
        payment_terms: str,
        due_date: datetime,
        line_items: List[Dict[str, Any]],
        discount_amount: Decimal = Decimal("0.00"),
        purchase_order_number: Optional[str] = None,
        **kwargs
    ) -> VendorInvoice:
        """
        Create vendor invoice record.
        
        Args:
            maintenance_request_id: Request identifier
            vendor_id: Vendor identifier
            vendor_name: Vendor name
            invoice_number: Invoice number
            invoice_date: Invoice date
            subtotal: Subtotal amount
            tax_amount: Tax amount
            total_amount: Total amount
            payment_terms: Payment terms
            due_date: Payment due date
            line_items: Invoice line items
            discount_amount: Discount amount
            purchase_order_number: PO number
            **kwargs: Additional invoice attributes
            
        Returns:
            Created vendor invoice
        """
        invoice_data = {
            "maintenance_request_id": maintenance_request_id,
            "vendor_id": vendor_id,
            "vendor_name": vendor_name,
            "invoice_number": invoice_number,
            "invoice_date": invoice_date.date() if isinstance(invoice_date, datetime) else invoice_date,
            "purchase_order_number": purchase_order_number,
            "line_items": line_items,
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "discount_amount": discount_amount,
            "total_amount": total_amount,
            "payment_terms": payment_terms,
            "due_date": due_date.date() if isinstance(due_date, datetime) else due_date,
            "payment_status": "pending",
            **kwargs
        }
        
        invoice = VendorInvoice(**invoice_data)
        self.session.add(invoice)
        self.session.commit()
        self.session.refresh(invoice)
        
        return invoice
    
    # ============================================================================
    # READ OPERATIONS - COST TRACKING
    # ============================================================================
    
    def find_cost_by_request(
        self,
        request_id: UUID
    ) -> Optional[MaintenanceCost]:
        """
        Find cost record by request.
        
        Args:
            request_id: Request identifier
            
        Returns:
            Cost record if exists
        """
        query = select(MaintenanceCost).where(
            MaintenanceCost.maintenance_request_id == request_id,
            MaintenanceCost.deleted_at.is_(None)
        )
        
        return self.session.execute(query).scalar_one_or_none()
    
    def find_over_budget_requests(
        self,
        hostel_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceCost]:
        """
        Find requests that exceeded budget.
        
        Args:
            hostel_id: Optional hostel filter
            pagination: Pagination parameters
            
        Returns:
            Paginated over-budget cost records
        """
        query = select(MaintenanceCost).where(
            MaintenanceCost.within_budget == False,
            MaintenanceCost.actual_cost.isnot(None),
            MaintenanceCost.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.join(
                MaintenanceRequest,
                MaintenanceCost.maintenance_request_id == MaintenanceRequest.id
            ).where(
                MaintenanceRequest.hostel_id == hostel_id
            )
        
        query = query.order_by(
            MaintenanceCost.variance.desc()
        )
        
        return self.paginate(query, pagination)
    
    def find_costs_by_budget_source(
        self,
        budget_source: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceCost]:
        """
        Find costs by budget source.
        
        Args:
            budget_source: Budget source
            start_date: Optional start date
            end_date: Optional end date
            pagination: Pagination parameters
            
        Returns:
            Paginated cost records
        """
        query = select(MaintenanceCost).where(
            MaintenanceCost.budget_source == budget_source,
            MaintenanceCost.deleted_at.is_(None)
        )
        
        if start_date:
            query = query.where(MaintenanceCost.created_at >= start_date)
        if end_date:
            query = query.where(MaintenanceCost.created_at <= end_date)
        
        query = query.order_by(MaintenanceCost.created_at.desc())
        
        return self.paginate(query, pagination)
    
    # ============================================================================
    # READ OPERATIONS - BUDGET MANAGEMENT
    # ============================================================================
    
    def get_active_budget(
        self,
        hostel_id: UUID
    ) -> Optional[BudgetAllocation]:
        """
        Get active budget allocation for hostel.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Active budget allocation
        """
        query = select(BudgetAllocation).where(
            BudgetAllocation.hostel_id == hostel_id,
            BudgetAllocation.is_active == True
        ).order_by(
            BudgetAllocation.fiscal_year_start.desc()
        )
        
        return self.session.execute(query).scalar_one_or_none()
    
    def get_budget_for_fiscal_year(
        self,
        hostel_id: UUID,
        fiscal_year: str
    ) -> Optional[BudgetAllocation]:
        """
        Get budget allocation for specific fiscal year.
        
        Args:
            hostel_id: Hostel identifier
            fiscal_year: Fiscal year (YYYY)
            
        Returns:
            Budget allocation for fiscal year
        """
        query = select(BudgetAllocation).where(
            BudgetAllocation.hostel_id == hostel_id,
            BudgetAllocation.fiscal_year == fiscal_year
        )
        
        return self.session.execute(query).scalar_one_or_none()
    
    def get_category_budget(
        self,
        budget_allocation_id: UUID,
        category: str
    ) -> Optional[CategoryBudget]:
        """
        Get category budget details.
        
        Args:
            budget_allocation_id: Budget allocation identifier
            category: Category name
            
        Returns:
            Category budget details
        """
        query = select(CategoryBudget).where(
            CategoryBudget.budget_allocation_id == budget_allocation_id,
            CategoryBudget.category == category
        )
        
        return self.session.execute(query).scalar_one_or_none()
    
    def get_all_category_budgets(
        self,
        budget_allocation_id: UUID
    ) -> List[CategoryBudget]:
        """
        Get all category budgets for allocation.
        
        Args:
            budget_allocation_id: Budget allocation identifier
            
        Returns:
            List of category budgets
        """
        query = select(CategoryBudget).where(
            CategoryBudget.budget_allocation_id == budget_allocation_id
        ).order_by(
            CategoryBudget.spent.desc()
        )
        
        return list(self.session.execute(query).scalars().all())
    
    # ============================================================================
    # READ OPERATIONS - VENDOR INVOICES
    # ============================================================================
    
    def find_invoice_by_number(
        self,
        invoice_number: str
    ) -> Optional[VendorInvoice]:
        """
        Find invoice by invoice number.
        
        Args:
            invoice_number: Invoice number
            
        Returns:
            Invoice if found
        """
        query = select(VendorInvoice).where(
            VendorInvoice.invoice_number == invoice_number,
            VendorInvoice.deleted_at.is_(None)
        )
        
        return self.session.execute(query).scalar_one_or_none()
    
    def find_invoices_by_vendor(
        self,
        vendor_id: UUID,
        payment_status: Optional[str] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[VendorInvoice]:
        """
        Find invoices for vendor.
        
        Args:
            vendor_id: Vendor identifier
            payment_status: Optional payment status filter
            pagination: Pagination parameters
            
        Returns:
            Paginated vendor invoices
        """
        query = select(VendorInvoice).where(
            VendorInvoice.vendor_id == vendor_id,
            VendorInvoice.deleted_at.is_(None)
        )
        
        if payment_status:
            query = query.where(VendorInvoice.payment_status == payment_status)
        
        query = query.order_by(VendorInvoice.invoice_date.desc())
        
        return self.paginate(query, pagination)
    
    def find_overdue_invoices(
        self,
        vendor_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[VendorInvoice]:
        """
        Find overdue unpaid invoices.
        
        Args:
            vendor_id: Optional vendor filter
            pagination: Pagination parameters
            
        Returns:
            Paginated overdue invoices
        """
        today = datetime.utcnow().date()
        
        query = select(VendorInvoice).where(
            VendorInvoice.payment_status != "paid",
            VendorInvoice.due_date < today,
            VendorInvoice.deleted_at.is_(None)
        )
        
        if vendor_id:
            query = query.where(VendorInvoice.vendor_id == vendor_id)
        
        query = query.order_by(VendorInvoice.due_date.asc())
        
        return self.paginate(query, pagination)
    
    def find_pending_invoices(
        self,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[VendorInvoice]:
        """
        Find pending payment invoices.
        
        Args:
            pagination: Pagination parameters
            
        Returns:
            Paginated pending invoices
        """
        query = select(VendorInvoice).where(
            VendorInvoice.payment_status == "pending",
            VendorInvoice.deleted_at.is_(None)
        ).order_by(VendorInvoice.due_date.asc())
        
        return self.paginate(query, pagination)
    
    # ============================================================================
    # UPDATE OPERATIONS
    # ============================================================================
    
    def update_actual_cost(
        self,
        cost_id: UUID,
        actual_cost: Decimal,
        materials_cost: Optional[Decimal] = None,
        labor_cost: Optional[Decimal] = None,
        vendor_charges: Optional[Decimal] = None,
        other_costs: Optional[Decimal] = None,
        tax_amount: Optional[Decimal] = None
    ) -> MaintenanceCost:
        """
        Update actual costs for maintenance.
        
        Args:
            cost_id: Cost record identifier
            actual_cost: Total actual cost
            materials_cost: Materials component
            labor_cost: Labor component
            vendor_charges: Vendor charges
            other_costs: Other costs
            tax_amount: Tax amount
            
        Returns:
            Updated cost record
        """
        cost_record = self.find_by_id(cost_id)
        if not cost_record:
            raise ValueError(f"Cost record {cost_id} not found")
        
        cost_record.actual_cost = actual_cost
        
        if materials_cost is not None:
            cost_record.materials_cost = materials_cost
        if labor_cost is not None:
            cost_record.labor_cost = labor_cost
        if vendor_charges is not None:
            cost_record.vendor_charges = vendor_charges
        if other_costs is not None:
            cost_record.other_costs = other_costs
        if tax_amount is not None:
            cost_record.tax_amount = tax_amount
        
        # Calculate variance
        cost_record.calculate_variance()
        
        self.session.commit()
        self.session.refresh(cost_record)
        
        return cost_record
    
    def update_budget_utilization(
        self,
        budget_allocation_id: UUID
    ) -> BudgetAllocation:
        """
        Update budget utilization based on actual spending.
        
        Args:
            budget_allocation_id: Budget allocation identifier
            
        Returns:
            Updated budget allocation
        """
        budget = self.session.get(BudgetAllocation, budget_allocation_id)
        if not budget:
            raise ValueError(f"Budget {budget_allocation_id} not found")
        
        # Update category budgets first
        category_budgets = self.get_all_category_budgets(budget_allocation_id)
        for cat_budget in category_budgets:
            cat_budget.update_utilization()
        
        # Calculate total spent and committed
        spent_query = select(
            func.sum(CategoryBudget.spent).label("total_spent"),
            func.sum(CategoryBudget.committed).label("total_committed")
        ).where(
            CategoryBudget.budget_allocation_id == budget_allocation_id
        )
        
        result = self.session.execute(spent_query).first()
        
        budget.spent_amount = result.total_spent or Decimal("0.00")
        budget.committed_amount = result.total_committed or Decimal("0.00")
        budget.remaining_budget = (
            budget.total_budget - budget.spent_amount - budget.committed_amount
        )
        
        # Update utilization percentage
        budget.update_utilization()
        
        self.session.commit()
        self.session.refresh(budget)
        
        return budget
    
    def mark_invoice_paid(
        self,
        invoice_id: UUID,
        paid_amount: Decimal,
        paid_date: Optional[datetime] = None
    ) -> VendorInvoice:
        """
        Mark vendor invoice as paid.
        
        Args:
            invoice_id: Invoice identifier
            paid_amount: Amount paid
            paid_date: Payment date
            
        Returns:
            Updated invoice
        """
        invoice = self.session.get(VendorInvoice, invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        invoice.mark_paid(
            paid_amount=paid_amount,
            paid_date=paid_date
        )
        
        self.session.commit()
        self.session.refresh(invoice)
        
        return invoice
    
    # ============================================================================
    # ANALYTICS AND REPORTING
    # ============================================================================
    
    def calculate_cost_variance_summary(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Calculate cost variance summary.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Period start date
            end_date: Period end date
            
        Returns:
            Cost variance summary
        """
        query = select(
            func.count(MaintenanceCost.id).label("total_requests"),
            func.sum(MaintenanceCost.estimated_cost).label("total_estimated"),
            func.sum(MaintenanceCost.approved_cost).label("total_approved"),
            func.sum(MaintenanceCost.actual_cost).label("total_actual"),
            func.avg(MaintenanceCost.variance_percentage).label("avg_variance_pct"),
            func.sum(
                func.case(
                    (MaintenanceCost.within_budget == True, 1),
                    else_=0
                )
            ).label("within_budget_count")
        ).join(
            MaintenanceRequest,
            MaintenanceCost.maintenance_request_id == MaintenanceRequest.id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceCost.actual_cost.isnot(None),
            MaintenanceCost.created_at >= start_date,
            MaintenanceCost.created_at <= end_date,
            MaintenanceCost.deleted_at.is_(None)
        )
        
        result = self.session.execute(query).first()
        
        within_budget_rate = Decimal("0.00")
        if result.total_requests and result.total_requests > 0:
            within_budget_rate = round(
                Decimal(result.within_budget_count or 0) / 
                Decimal(result.total_requests) * 100,
                2
            )
        
        return {
            "total_requests": result.total_requests or 0,
            "total_estimated": float(result.total_estimated or 0),
            "total_approved": float(result.total_approved or 0),
            "total_actual": float(result.total_actual or 0),
            "average_variance_percentage": float(result.avg_variance_pct or 0),
            "within_budget_count": result.within_budget_count or 0,
            "within_budget_rate": float(within_budget_rate)
        }
    
    def get_cost_breakdown_by_category(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get cost breakdown by maintenance category.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Period start date
            end_date: Period end date
            
        Returns:
            Cost breakdown by category
        """
        query = select(
            MaintenanceRequest.category,
            func.count(MaintenanceCost.id).label("request_count"),
            func.sum(MaintenanceCost.actual_cost).label("total_cost"),
            func.avg(MaintenanceCost.actual_cost).label("avg_cost"),
            func.sum(MaintenanceCost.materials_cost).label("total_materials"),
            func.sum(MaintenanceCost.labor_cost).label("total_labor"),
            func.sum(MaintenanceCost.vendor_charges).label("total_vendor")
        ).join(
            MaintenanceRequest,
            MaintenanceCost.maintenance_request_id == MaintenanceRequest.id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceCost.actual_cost.isnot(None),
            MaintenanceCost.created_at >= start_date,
            MaintenanceCost.created_at <= end_date,
            MaintenanceCost.deleted_at.is_(None)
        ).group_by(
            MaintenanceRequest.category
        ).order_by(
            desc("total_cost")
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "category": str(row.category.value),
                "request_count": row.request_count,
                "total_cost": float(row.total_cost),
                "average_cost": float(row.avg_cost),
                "materials_cost": float(row.total_materials or 0),
                "labor_cost": float(row.total_labor or 0),
                "vendor_charges": float(row.total_vendor or 0)
            }
            for row in results
        ]
    
    def get_budget_utilization_by_category(
        self,
        budget_allocation_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get budget utilization breakdown by category.
        
        Args:
            budget_allocation_id: Budget allocation identifier
            
        Returns:
            Utilization by category
        """
        query = select(
            CategoryBudget
        ).where(
            CategoryBudget.budget_allocation_id == budget_allocation_id
        ).order_by(
            CategoryBudget.utilization_percentage.desc()
        )
        
        category_budgets = list(self.session.execute(query).scalars().all())
        
        return [
            {
                "category": cb.category,
                "allocated": float(cb.allocated),
                "spent": float(cb.spent),
                "committed": float(cb.committed),
                "remaining": float(cb.remaining),
                "utilization_percentage": float(cb.utilization_percentage),
                "request_count": cb.request_count,
                "average_cost": float(cb.average_cost),
                "is_over_budget": cb.is_over_budget
            }
            for cb in category_budgets
        ]
    
    def calculate_monthly_spending_trend(
        self,
        hostel_id: UUID,
        months: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Calculate monthly spending trends.
        
        Args:
            hostel_id: Hostel identifier
            months: Number of months to analyze
            
        Returns:
            Monthly spending data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=months * 30)
        
        query = select(
            func.date_trunc('month', MaintenanceCost.created_at).label('month'),
            func.count(MaintenanceCost.id).label("request_count"),
            func.sum(MaintenanceCost.actual_cost).label("total_spent"),
            func.avg(MaintenanceCost.actual_cost).label("avg_cost")
        ).join(
            MaintenanceRequest,
            MaintenanceCost.maintenance_request_id == MaintenanceRequest.id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceCost.actual_cost.isnot(None),
            MaintenanceCost.created_at >= cutoff_date,
            MaintenanceCost.deleted_at.is_(None)
        ).group_by(
            'month'
        ).order_by(
            'month'
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "month": row.month.strftime("%Y-%m"),
                "request_count": row.request_count,
                "total_spent": float(row.total_spent or 0),
                "average_cost": float(row.avg_cost or 0)
            }
            for row in results
        ]
    
    def get_vendor_payment_summary(
        self,
        vendor_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get payment summary for vendor.
        
        Args:
            vendor_id: Vendor identifier
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Vendor payment summary
        """
        query = select(
            func.count(VendorInvoice.id).label("total_invoices"),
            func.sum(VendorInvoice.total_amount).label("total_invoiced"),
            func.sum(VendorInvoice.paid_amount).label("total_paid"),
            func.sum(
                func.case(
                    (VendorInvoice.payment_status == "paid", 1),
                    else_=0
                )
            ).label("paid_count"),
            func.sum(
                func.case(
                    (VendorInvoice.payment_status == "pending", 1),
                    else_=0
                )
            ).label("pending_count")
        ).where(
            VendorInvoice.vendor_id == vendor_id,
            VendorInvoice.deleted_at.is_(None)
        )
        
        if start_date:
            query = query.where(VendorInvoice.invoice_date >= start_date.date())
        if end_date:
            query = query.where(VendorInvoice.invoice_date <= end_date.date())
        
        result = self.session.execute(query).first()
        
        outstanding = (
            (result.total_invoiced or Decimal("0.00")) - 
            (result.total_paid or Decimal("0.00"))
        )
        
        return {
            "vendor_id": str(vendor_id),
            "total_invoices": result.total_invoices or 0,
            "total_invoiced": float(result.total_invoiced or 0),
            "total_paid": float(result.total_paid or 0),
            "outstanding_amount": float(outstanding),
            "paid_invoices": result.paid_count or 0,
            "pending_invoices": result.pending_count or 0
        }
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _create_category_budget(
        self,
        budget_allocation_id: UUID,
        category: str,
        allocated: Decimal
    ) -> CategoryBudget:
        """
        Create category budget entry.
        
        Args:
            budget_allocation_id: Budget allocation identifier
            category: Category name
            allocated: Allocated amount
            
        Returns:
            Created category budget
        """
        category_budget = CategoryBudget(
            budget_allocation_id=budget_allocation_id,
            category=category,
            allocated=allocated,
            remaining=allocated
        )
        
        self.session.add(category_budget)
        self.session.commit()
        self.session.refresh(category_budget)
        
        return category_budget