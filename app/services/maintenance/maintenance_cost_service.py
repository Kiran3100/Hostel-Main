"""
Maintenance Cost Service

Comprehensive cost tracking and budget management for maintenance operations.

Features:
- Detailed cost tracking per request
- Budget allocation and monitoring
- Category-wise budget management
- Expense reporting and analytics
- Cost variance analysis
- Fiscal year management
- Invoice tracking
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceCostRepository
from app.schemas.common import DateRangeFilter
from app.schemas.maintenance import (
    CostTracking,
    BudgetAllocation,
    CategoryBudget,
    ExpenseReport,
    MonthlyExpense,
    VendorInvoice,
    ExpenseItem,
    CostAnalysis,
)
from app.core.exceptions import ValidationException, BusinessLogicException
from app.core.logging import logger


class MaintenanceCostService:
    """
    High-level service for maintenance cost tracking and budget management.

    Provides comprehensive financial oversight of maintenance operations.
    """

    def __init__(self, cost_repo: MaintenanceCostRepository) -> None:
        """
        Initialize the cost service.

        Args:
            cost_repo: Repository for cost data persistence
        """
        if not cost_repo:
            raise ValueError("MaintenanceCostRepository is required")
        self.cost_repo = cost_repo

    # -------------------------------------------------------------------------
    # Cost Tracking Operations
    # -------------------------------------------------------------------------

    def record_cost_for_request(
        self,
        db: Session,
        tracking: CostTracking,
    ) -> CostTracking:
        """
        Record cost information for a maintenance request.

        Tracks labor, materials, equipment, and other expenses.

        Args:
            db: Database session
            tracking: Cost tracking details

        Returns:
            Created CostTracking record

        Raises:
            ValidationException: If cost data is invalid
            BusinessLogicException: If budget is exceeded
        """
        # Validate cost data
        self._validate_cost_tracking(tracking)

        try:
            logger.info(
                f"Recording cost for maintenance request "
                f"{tracking.maintenance_request_id}"
            )

            # Check budget availability
            if tracking.total_cost:
                self._check_budget_availability(
                    db,
                    tracking.hostel_id,
                    tracking.category,
                    tracking.total_cost,
                )

            payload = tracking.model_dump(exclude_none=True)
            obj = self.cost_repo.create_cost_record(db=db, data=payload)

            logger.info(
                f"Cost recorded: Total ${obj.total_cost} "
                f"for request {tracking.maintenance_request_id}"
            )

            return CostTracking.model_validate(obj)

        except ValidationException:
            raise
        except BusinessLogicException:
            raise
        except Exception as e:
            logger.error(
                f"Error recording cost: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to record maintenance cost: {str(e)}"
            )

    def update_cost_record(
        self,
        db: Session,
        cost_id: UUID,
        updates: Dict[str, Any],
    ) -> CostTracking:
        """
        Update an existing cost record.

        Args:
            db: Database session
            cost_id: UUID of cost record
            updates: Fields to update

        Returns:
            Updated CostTracking

        Raises:
            ValidationException: If cost record not found
        """
        if not cost_id:
            raise ValidationException("Cost ID is required")

        try:
            cost_record = self.cost_repo.get_by_id(db, cost_id)
            if not cost_record:
                raise ValidationException(f"Cost record {cost_id} not found")

            # Validate updated costs
            if "total_cost" in updates:
                if updates["total_cost"] < 0:
                    raise ValidationException("Total cost cannot be negative")

            updated = self.cost_repo.update_cost_record(
                db=db,
                cost_record=cost_record,
                data=updates,
            )

            logger.info(f"Updated cost record {cost_id}")
            return CostTracking.model_validate(updated)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error updating cost record: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to update cost record: {str(e)}"
            )

    def get_cost_for_request(
        self,
        db: Session,
        request_id: UUID,
    ) -> Optional[CostTracking]:
        """
        Retrieve cost record for a maintenance request.

        Args:
            db: Database session
            request_id: UUID of maintenance request

        Returns:
            CostTracking if found, None otherwise
        """
        if not request_id:
            raise ValidationException("Request ID is required")

        try:
            cost = self.cost_repo.get_by_request_id(db, request_id)
            if not cost:
                return None

            return CostTracking.model_validate(cost)

        except Exception as e:
            logger.error(
                f"Error retrieving cost for request {request_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve cost record: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Budget Management Operations
    # -------------------------------------------------------------------------

    def get_budget_allocation_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        fiscal_year: str,
    ) -> BudgetAllocation:
        """
        Retrieve budget allocation for a hostel in a fiscal year.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            fiscal_year: Fiscal year (e.g., "2024")

        Returns:
            BudgetAllocation with budget details and utilization

        Raises:
            ValidationException: If budget not found
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")
        if not fiscal_year:
            raise ValidationException("Fiscal year is required")

        self._validate_fiscal_year(fiscal_year)

        try:
            data = self.cost_repo.get_budget_allocation(
                db,
                hostel_id,
                fiscal_year
            )
            
            if not data:
                raise ValidationException(
                    f"Budget allocation not found for hostel {hostel_id} "
                    f"in fiscal year {fiscal_year}"
                )
            
            return BudgetAllocation.model_validate(data)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving budget allocation: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve budget allocation: {str(e)}"
            )

    def create_budget_allocation(
        self,
        db: Session,
        allocation: BudgetAllocation,
    ) -> BudgetAllocation:
        """
        Create a new budget allocation for a hostel.

        Args:
            db: Database session
            allocation: Budget allocation details

        Returns:
            Created BudgetAllocation

        Raises:
            ValidationException: If allocation data is invalid
        """
        self._validate_budget_allocation(allocation)

        try:
            logger.info(
                f"Creating budget allocation for hostel {allocation.hostel_id} "
                f"in fiscal year {allocation.fiscal_year}"
            )

            payload = allocation.model_dump(exclude_none=True)
            obj = self.cost_repo.create_budget_allocation(db=db, data=payload)

            logger.info(
                f"Budget allocation created: ${obj.total_budget} "
                f"for {allocation.fiscal_year}"
            )

            return BudgetAllocation.model_validate(obj)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error creating budget allocation: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to create budget allocation: {str(e)}"
            )

    def update_budget_allocation(
        self,
        db: Session,
        allocation_id: UUID,
        updates: Dict[str, Any],
    ) -> BudgetAllocation:
        """
        Update an existing budget allocation.

        Args:
            db: Database session
            allocation_id: UUID of budget allocation
            updates: Fields to update

        Returns:
            Updated BudgetAllocation
        """
        if not allocation_id:
            raise ValidationException("Budget allocation ID is required")

        try:
            allocation = self.cost_repo.get_budget_by_id(db, allocation_id)
            if not allocation:
                raise ValidationException(
                    f"Budget allocation {allocation_id} not found"
                )

            updated = self.cost_repo.update_budget_allocation(
                db=db,
                allocation=allocation,
                data=updates,
            )

            logger.info(f"Updated budget allocation {allocation_id}")
            return BudgetAllocation.model_validate(updated)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error updating budget allocation: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to update budget allocation: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Category Budget Operations
    # -------------------------------------------------------------------------

    def list_category_budgets_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        fiscal_year: str,
    ) -> List[CategoryBudget]:
        """
        List all category budgets for a hostel in a fiscal year.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            fiscal_year: Fiscal year

        Returns:
            List of CategoryBudget records with utilization
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")
        if not fiscal_year:
            raise ValidationException("Fiscal year is required")

        self._validate_fiscal_year(fiscal_year)

        try:
            objs = self.cost_repo.get_category_budgets(
                db,
                hostel_id,
                fiscal_year
            )
            
            budgets = [CategoryBudget.model_validate(o) for o in objs]

            logger.debug(
                f"Retrieved {len(budgets)} category budgets for "
                f"hostel {hostel_id}"
            )

            return budgets

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error listing category budgets: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve category budgets: {str(e)}"
            )

    def create_category_budget(
        self,
        db: Session,
        budget: CategoryBudget,
    ) -> CategoryBudget:
        """
        Create a category-specific budget.

        Args:
            db: Database session
            budget: Category budget details

        Returns:
            Created CategoryBudget
        """
        self._validate_category_budget(budget)

        try:
            payload = budget.model_dump(exclude_none=True)
            obj = self.cost_repo.create_category_budget(db=db, data=payload)

            logger.info(
                f"Created category budget: {budget.category} - "
                f"${budget.allocated_amount}"
            )

            return CategoryBudget.model_validate(obj)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error creating category budget: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to create category budget: {str(e)}"
            )

    def get_category_budget_status(
        self,
        db: Session,
        hostel_id: UUID,
        category: str,
        fiscal_year: str,
    ) -> Dict[str, Any]:
        """
        Get detailed budget status for a specific category.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            category: Maintenance category
            fiscal_year: Fiscal year

        Returns:
            Dictionary with budget status and alerts
        """
        try:
            budget = self.cost_repo.get_category_budget(
                db,
                hostel_id,
                category,
                fiscal_year
            )

            if not budget:
                return {
                    "category": category,
                    "has_budget": False,
                    "status": "no_budget",
                }

            utilized = budget.get("utilized_amount", 0)
            allocated = budget.get("allocated_amount", 0)
            utilization_pct = (utilized / allocated * 100) if allocated > 0 else 0

            status = "healthy"
            alerts = []

            if utilization_pct >= 100:
                status = "exceeded"
                alerts.append("Budget exceeded")
            elif utilization_pct >= 90:
                status = "critical"
                alerts.append("Budget nearly exhausted (>90%)")
            elif utilization_pct >= 75:
                status = "warning"
                alerts.append("Budget utilization high (>75%)")

            return {
                "category": category,
                "fiscal_year": fiscal_year,
                "has_budget": True,
                "allocated_amount": allocated,
                "utilized_amount": utilized,
                "remaining_amount": allocated - utilized,
                "utilization_percentage": round(utilization_pct, 2),
                "status": status,
                "alerts": alerts,
            }

        except Exception as e:
            logger.error(
                f"Error getting category budget status: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve budget status: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Expense Reporting Operations
    # -------------------------------------------------------------------------

    def get_expense_report(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> ExpenseReport:
        """
        Generate comprehensive expense report for a date range.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            period: Date range for the report

        Returns:
            ExpenseReport with detailed breakdown

        Raises:
            ValidationException: If no data available
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        self._validate_date_range(period)

        try:
            logger.info(
                f"Generating expense report for hostel {hostel_id} "
                f"from {period.start_date} to {period.end_date}"
            )

            data = self.cost_repo.build_expense_report(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            
            if not data:
                raise ValidationException(
                    f"No expense data available for the period "
                    f"{period.start_date} to {period.end_date}"
                )
            
            report = ExpenseReport.model_validate(data)

            logger.info(
                f"Expense report generated: Total expenses ${report.total_expenses}"
            )

            return report

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error generating expense report: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to generate expense report: {str(e)}"
            )

    def get_monthly_expenses(
        self,
        db: Session,
        hostel_id: UUID,
        fiscal_year: str,
    ) -> List[MonthlyExpense]:
        """
        Get month-by-month expense breakdown for a fiscal year.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            fiscal_year: Fiscal year

        Returns:
            List of MonthlyExpense records
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")
        if not fiscal_year:
            raise ValidationException("Fiscal year is required")

        self._validate_fiscal_year(fiscal_year)

        try:
            objs = self.cost_repo.get_monthly_expenses(
                db,
                hostel_id,
                fiscal_year
            )
            
            expenses = [MonthlyExpense.model_validate(o) for o in objs]

            logger.debug(
                f"Retrieved {len(expenses)} monthly expense records "
                f"for fiscal year {fiscal_year}"
            )

            return expenses

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving monthly expenses: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve monthly expenses: {str(e)}"
            )

    def get_cost_analysis(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> CostAnalysis:
        """
        Generate detailed cost analysis with trends and insights.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            period: Date range for analysis

        Returns:
            CostAnalysis with insights and trends

        Raises:
            ValidationException: If no data available
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        self._validate_date_range(period)

        try:
            logger.info(
                f"Generating cost analysis for hostel {hostel_id}"
            )

            data = self.cost_repo.build_cost_analysis(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            
            if not data:
                raise ValidationException(
                    "No cost data available for analysis"
                )
            
            analysis = CostAnalysis.model_validate(data)

            logger.info("Cost analysis generated successfully")

            return analysis

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error generating cost analysis: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to generate cost analysis: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Invoice Management
    # -------------------------------------------------------------------------

    def record_vendor_invoice(
        self,
        db: Session,
        invoice: VendorInvoice,
    ) -> VendorInvoice:
        """
        Record a vendor invoice for maintenance work.

        Args:
            db: Database session
            invoice: Invoice details

        Returns:
            Created VendorInvoice
        """
        self._validate_vendor_invoice(invoice)

        try:
            payload = invoice.model_dump(exclude_none=True)
            obj = self.cost_repo.create_vendor_invoice(db=db, data=payload)

            logger.info(
                f"Vendor invoice recorded: {invoice.invoice_number} - "
                f"${invoice.invoice_amount}"
            )

            return VendorInvoice.model_validate(obj)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error recording vendor invoice: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to record vendor invoice: {str(e)}"
            )

    def get_vendor_invoices(
        self,
        db: Session,
        vendor_id: UUID,
        status_filter: Optional[str] = None,
    ) -> List[VendorInvoice]:
        """
        Retrieve all invoices for a vendor.

        Args:
            db: Database session
            vendor_id: UUID of vendor
            status_filter: Optional status filter

        Returns:
            List of VendorInvoice records
        """
        if not vendor_id:
            raise ValidationException("Vendor ID is required")

        try:
            invoices = self.cost_repo.get_vendor_invoices(
                db=db,
                vendor_id=vendor_id,
                status=status_filter,
            )

            return [VendorInvoice.model_validate(i) for i in invoices]

        except Exception as e:
            logger.error(
                f"Error retrieving vendor invoices: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve vendor invoices: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Private Validation and Helper Methods
    # -------------------------------------------------------------------------

    def _validate_cost_tracking(self, tracking: CostTracking) -> None:
        """Validate cost tracking data."""
        if not tracking.maintenance_request_id:
            raise ValidationException("Maintenance request ID is required")

        costs = [
            tracking.labor_cost,
            tracking.material_cost,
            tracking.equipment_cost,
            tracking.other_cost,
        ]

        if any(cost is not None and cost < 0 for cost in costs):
            raise ValidationException("Cost values cannot be negative")

        if tracking.total_cost is not None and tracking.total_cost < 0:
            raise ValidationException("Total cost cannot be negative")

    def _validate_budget_allocation(self, allocation: BudgetAllocation) -> None:
        """Validate budget allocation data."""
        if not allocation.hostel_id:
            raise ValidationException("Hostel ID is required")

        if not allocation.fiscal_year:
            raise ValidationException("Fiscal year is required")

        self._validate_fiscal_year(allocation.fiscal_year)

        if allocation.total_budget is None or allocation.total_budget <= 0:
            raise ValidationException("Total budget must be greater than zero")

    def _validate_category_budget(self, budget: CategoryBudget) -> None:
        """Validate category budget data."""
        if not budget.category:
            raise ValidationException("Category is required")

        if budget.allocated_amount is None or budget.allocated_amount <= 0:
            raise ValidationException("Allocated amount must be greater than zero")

    def _validate_vendor_invoice(self, invoice: VendorInvoice) -> None:
        """Validate vendor invoice data."""
        if not invoice.vendor_id:
            raise ValidationException("Vendor ID is required")

        if not invoice.invoice_number:
            raise ValidationException("Invoice number is required")

        if invoice.invoice_amount is None or invoice.invoice_amount <= 0:
            raise ValidationException("Invoice amount must be greater than zero")

    def _validate_fiscal_year(self, fiscal_year: str) -> None:
        """Validate fiscal year format."""
        try:
            year = int(fiscal_year)
            current_year = datetime.now().year
            if year < 2000 or year > current_year + 10:
                raise ValueError
        except (ValueError, TypeError):
            raise ValidationException(
                f"Invalid fiscal year format: {fiscal_year}. "
                "Must be a 4-digit year (e.g., '2024')"
            )

    def _validate_date_range(self, period: DateRangeFilter) -> None:
        """Validate date range."""
        if not period.start_date or not period.end_date:
            raise ValidationException("Both start_date and end_date are required")

        if period.start_date > period.end_date:
            raise ValidationException("start_date must be before or equal to end_date")

    def _check_budget_availability(
        self,
        db: Session,
        hostel_id: UUID,
        category: str,
        amount: float,
    ) -> None:
        """
        Check if budget is available for the expense.

        Logs warning if budget is exceeded but doesn't block the operation.
        """
        try:
            current_year = str(datetime.now().year)
            status = self.get_category_budget_status(
                db,
                hostel_id,
                category,
                current_year
            )

            if not status.get("has_budget"):
                logger.warning(
                    f"No budget defined for category {category} "
                    f"in hostel {hostel_id}"
                )
                return

            remaining = status.get("remaining_amount", 0)
            if amount > remaining:
                logger.warning(
                    f"Expense ${amount} exceeds remaining budget ${remaining} "
                    f"for category {category}"
                )
                # Note: Not raising exception, just logging warning
                # Business decision: allow over-budget expenses

        except Exception as e:
            logger.error(
                f"Error checking budget availability: {str(e)}",
                exc_info=True
            )
            # Don't block the operation if budget check fails