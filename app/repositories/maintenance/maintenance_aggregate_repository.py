# app/repositories/maintenance/maintenance_aggregate_repository.py
"""
Maintenance Aggregate Repository.

Cross-cutting aggregate operations combining multiple maintenance entities
for complex business operations and reporting.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.maintenance import (
    MaintenanceRequest,
    MaintenanceAssignment,
    MaintenanceCompletion,
    MaintenanceCost,
    MaintenanceApproval,
    MaintenanceSchedule,
    VendorAssignment,
    MaintenanceVendor,
    BudgetAllocation,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.schemas.common.enums import MaintenanceCategory, MaintenanceStatus


class MaintenanceAggregateRepository:
    """
    Aggregate repository for cross-cutting maintenance operations.
    
    Provides complex queries and operations that span multiple
    maintenance entities and domains.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with session."""
        self.session = session
    
    # ============================================================================
    # DASHBOARD OPERATIONS
    # ============================================================================
    
    def get_dashboard_summary(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Get comprehensive dashboard summary for hostel.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Dashboard summary with key metrics
        """
        today = date.today()
        month_start = date(today.year, today.month, 1)
        
        # Current status counts
        status_query = select(
            func.count(MaintenanceRequest.id).label("total"),
            func.sum(
                func.case(
                    (MaintenanceRequest.status == MaintenanceStatus.PENDING, 1),
                    else_=0
                )
            ).label("pending"),
            func.sum(
                func.case(
                    (MaintenanceRequest.status == MaintenanceStatus.IN_PROGRESS, 1),
                    else_=0
                )
            ).label("in_progress"),
            func.sum(
                func.case(
                    (MaintenanceRequest.status == MaintenanceStatus.COMPLETED, 1),
                    else_=0
                )
            ).label("completed_today")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        status_result = self.session.execute(status_query).first()
        
        # Overdue requests
        overdue_query = select(
            func.count(MaintenanceRequest.id)
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.status != MaintenanceStatus.COMPLETED,
            MaintenanceRequest.deadline < datetime.now(),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        overdue_count = self.session.execute(overdue_query).scalar_one()
        
        # Pending approvals
        approval_query = select(
            func.count(MaintenanceApproval.id)
        ).join(
            MaintenanceRequest,
            MaintenanceApproval.maintenance_request_id == MaintenanceRequest.id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceApproval.approved.is_(None),
            MaintenanceApproval.deleted_at.is_(None)
        )
        
        pending_approvals = self.session.execute(approval_query).scalar_one()
        
        # Monthly spending
        cost_query = select(
            func.sum(MaintenanceCost.actual_cost)
        ).join(
            MaintenanceRequest,
            MaintenanceCost.maintenance_request_id == MaintenanceRequest.id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceCost.actual_cost.isnot(None),
            MaintenanceRequest.created_at >= datetime.combine(month_start, datetime.min.time()),
            MaintenanceCost.deleted_at.is_(None)
        )
        
        monthly_spending = self.session.execute(cost_query).scalar_one_or_none()
        
        # Active schedules due this week
        week_end = today + timedelta(days=7)
        
        schedule_query = select(
            func.count(MaintenanceSchedule.id)
        ).where(
            MaintenanceSchedule.hostel_id == hostel_id,
            MaintenanceSchedule.is_active == True,
            MaintenanceSchedule.next_due_date >= today,
            MaintenanceSchedule.next_due_date <= week_end,
            MaintenanceSchedule.deleted_at.is_(None)
        )
        
        upcoming_schedules = self.session.execute(schedule_query).scalar_one()
        
        return {
            "total_active_requests": status_result.total or 0,
            "pending_requests": status_result.pending or 0,
            "in_progress_requests": status_result.in_progress or 0,
            "completed_today": status_result.completed_today or 0,
            "overdue_requests": overdue_count,
            "pending_approvals": pending_approvals,
            "monthly_spending": float(monthly_spending or 0),
            "upcoming_scheduled_maintenance": upcoming_schedules
        }
    
    def get_hostel_overview(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive hostel maintenance overview.
        
        Args:
            hostel_id: Hostel identifier
            days: Number of days for trend analysis
            
        Returns:
            Comprehensive overview
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Request statistics
        request_stats = self._get_request_statistics(hostel_id, start_date, end_date)
        
        # Cost statistics
        cost_stats = self._get_cost_statistics(hostel_id, start_date, end_date)
        
        # Performance metrics
        performance = self._get_performance_metrics(hostel_id, start_date, end_date)
        
        # Budget status
        budget_status = self._get_budget_status(hostel_id)
        
        # Top issues
        top_issues = self._get_top_issues(hostel_id, days)
        
        return {
            "period_days": days,
            "request_statistics": request_stats,
            "cost_statistics": cost_stats,
            "performance_metrics": performance,
            "budget_status": budget_status,
            "top_issues": top_issues
        }
    
    # ============================================================================
    # RESOURCE OPTIMIZATION
    # ============================================================================
    
    def get_workload_distribution(
        self,
        hostel_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get workload distribution across all resources.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Workload distribution data
        """
        # Staff workload
        staff_query = select(
            MaintenanceAssignment.assigned_to,
            func.count(MaintenanceAssignment.id).label("active_assignments"),
            func.sum(MaintenanceAssignment.estimated_hours).label("estimated_hours"),
            func.sum(MaintenanceAssignment.actual_hours).label("actual_hours")
        ).join(
            MaintenanceRequest,
            MaintenanceAssignment.maintenance_request_id == MaintenanceRequest.id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceAssignment.is_active == True,
            MaintenanceAssignment.is_completed == False,
            MaintenanceAssignment.deleted_at.is_(None)
        ).group_by(
            MaintenanceAssignment.assigned_to
        )
        
        staff_results = self.session.execute(staff_query).all()
        
        # Vendor workload
        vendor_query = select(
            VendorAssignment.vendor_id,
            func.count(VendorAssignment.id).label("active_assignments"),
            func.sum(VendorAssignment.quoted_amount).label("total_value")
        ).join(
            MaintenanceRequest,
            VendorAssignment.maintenance_request_id == MaintenanceRequest.id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            VendorAssignment.is_active == True,
            VendorAssignment.is_completed == False,
            VendorAssignment.deleted_at.is_(None)
        ).group_by(
            VendorAssignment.vendor_id
        )
        
        vendor_results = self.session.execute(vendor_query).all()
        
        return {
            "staff_workload": [
                {
                    "assignee_id": str(row.assigned_to),
                    "active_assignments": row.active_assignments,
                    "estimated_hours": float(row.estimated_hours or 0),
                    "actual_hours": float(row.actual_hours or 0)
                }
                for row in staff_results
            ],
            "vendor_workload": [
                {
                    "vendor_id": str(row.vendor_id),
                    "active_assignments": row.active_assignments,
                    "total_value": float(row.total_value or 0)
                }
                for row in vendor_results
            ]
        }
    
    def optimize_resource_allocation(
        self,
        hostel_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Provide resource allocation optimization recommendations.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Optimization recommendations
        """
        recommendations = []
        
        # Check for overloaded staff
        workload = self.get_workload_distribution(hostel_id)
        
        staff_workload = workload["staff_workload"]
        if staff_workload:
            avg_assignments = sum(s["active_assignments"] for s in staff_workload) / len(staff_workload)
            
            for staff in staff_workload:
                if staff["active_assignments"] > avg_assignments * 1.5:
                    recommendations.append({
                        "type": "staff_overload",
                        "resource_id": staff["assignee_id"],
                        "severity": "high",
                        "current_load": staff["active_assignments"],
                        "recommended_action": "redistribute_assignments",
                        "details": f"Staff member has {staff['active_assignments']} assignments, {int((staff['active_assignments']/avg_assignments - 1) * 100)}% above average"
                    })
        
        # Check for unassigned high-priority requests
        unassigned_query = select(
            func.count(MaintenanceRequest.id)
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.assigned_to.is_(None),
            MaintenanceRequest.priority.in_(['HIGH', 'URGENT', 'CRITICAL']),
            MaintenanceRequest.status == MaintenanceStatus.PENDING,
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        unassigned_count = self.session.execute(unassigned_query).scalar_one()
        
        if unassigned_count > 0:
            recommendations.append({
                "type": "unassigned_high_priority",
                "severity": "critical",
                "count": unassigned_count,
                "recommended_action": "immediate_assignment",
                "details": f"{unassigned_count} high-priority requests need immediate assignment"
            })
        
        return recommendations
    
    # ============================================================================
    # FINANCIAL CONSOLIDATION
    # ============================================================================
    
    def get_financial_summary(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        Get consolidated financial summary.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Period start date
            end_date: Period end date
            
        Returns:
            Financial summary
        """
        # Total spending by component
        component_query = select(
            func.sum(MaintenanceCost.materials_cost).label("materials"),
            func.sum(MaintenanceCost.labor_cost).label("labor"),
            func.sum(MaintenanceCost.vendor_charges).label("vendor"),
            func.sum(MaintenanceCost.other_costs).label("other"),
            func.sum(MaintenanceCost.tax_amount).label("tax"),
            func.sum(MaintenanceCost.actual_cost).label("total")
        ).join(
            MaintenanceRequest,
            MaintenanceCost.maintenance_request_id == MaintenanceRequest.id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceCost.actual_cost.isnot(None),
            MaintenanceRequest.created_at >= datetime.combine(start_date, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(end_date, datetime.max.time()),
            MaintenanceCost.deleted_at.is_(None)
        )
        
        component_result = self.session.execute(component_query).first()
        
        # Budget comparison
        budget = self._get_budget_status(hostel_id)
        
        # Category breakdown
        category_query = select(
            MaintenanceRequest.category,
            func.sum(MaintenanceCost.actual_cost).label("cost")
        ).join(
            MaintenanceCost,
            MaintenanceRequest.id == MaintenanceCost.maintenance_request_id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceCost.actual_cost.isnot(None),
            MaintenanceRequest.created_at >= datetime.combine(start_date, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(end_date, datetime.max.time()),
            MaintenanceCost.deleted_at.is_(None)
        ).group_by(
            MaintenanceRequest.category
        )
        
        category_results = self.session.execute(category_query).all()
        
        return {
            "total_spending": float(component_result.total or 0),
            "breakdown": {
                "materials": float(component_result.materials or 0),
                "labor": float(component_result.labor or 0),
                "vendor": float(component_result.vendor or 0),
                "other": float(component_result.other or 0),
                "tax": float(component_result.tax or 0)
            },
            "budget_status": budget,
            "by_category": {
                str(row.category.value): float(row.cost)
                for row in category_results
            }
        }
    
    # ============================================================================
    # PERFORMANCE COMPARISON
    # ============================================================================
    
    def compare_periods(
        self,
        hostel_id: UUID,
        current_start: date,
        current_end: date,
        previous_start: date,
        previous_end: date
    ) -> Dict[str, Any]:
        """
        Compare performance between two periods.
        
        Args:
            hostel_id: Hostel identifier
            current_start: Current period start
            current_end: Current period end
            previous_start: Previous period start
            previous_end: Previous period end
            
        Returns:
            Period comparison analysis
        """
        current_stats = self._get_request_statistics(hostel_id, current_start, current_end)
        previous_stats = self._get_request_statistics(hostel_id, previous_start, previous_end)
        
        current_costs = self._get_cost_statistics(hostel_id, current_start, current_end)
        previous_costs = self._get_cost_statistics(hostel_id, previous_start, previous_end)
        
        def calculate_change(current: float, previous: float) -> Dict[str, Any]:
            if previous == 0:
                return {"value": current, "change": 0, "percentage": 0}
            
            change = current - previous
            percentage = (change / previous) * 100
            
            return {
                "value": current,
                "change": change,
                "percentage": round(percentage, 2),
                "trend": "up" if change > 0 else "down" if change < 0 else "stable"
            }
        
        return {
            "request_volume": calculate_change(
                current_stats["total_requests"],
                previous_stats["total_requests"]
            ),
            "completion_rate": calculate_change(
                current_stats["completion_rate"],
                previous_stats["completion_rate"]
            ),
            "total_spending": calculate_change(
                current_costs["total_cost"],
                previous_costs["total_cost"]
            ),
            "average_cost": calculate_change(
                current_costs["average_cost"],
                previous_costs["average_cost"]
            )
        }
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _get_request_statistics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get request statistics for period."""
        query = select(
            func.count(MaintenanceRequest.id).label("total"),
            func.sum(
                func.case(
                    (MaintenanceRequest.status == MaintenanceStatus.COMPLETED, 1),
                    else_=0
                )
            ).label("completed"),
            func.sum(
                func.case(
                    (MaintenanceRequest.status == MaintenanceStatus.PENDING, 1),
                    else_=0
                )
            ).label("pending")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.created_at >= datetime.combine(start_date, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(end_date, datetime.max.time()),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        result = self.session.execute(query).first()
        
        completion_rate = 0.0
        if result.total and result.total > 0:
            completion_rate = (result.completed / result.total) * 100
        
        return {
            "total_requests": result.total or 0,
            "completed_requests": result.completed or 0,
            "pending_requests": result.pending or 0,
            "completion_rate": round(completion_rate, 2)
        }
    
    def _get_cost_statistics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get cost statistics for period."""
        query = select(
            func.sum(MaintenanceCost.actual_cost).label("total"),
            func.avg(MaintenanceCost.actual_cost).label("average")
        ).join(
            MaintenanceRequest,
            MaintenanceCost.maintenance_request_id == MaintenanceRequest.id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceCost.actual_cost.isnot(None),
            MaintenanceRequest.created_at >= datetime.combine(start_date, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(end_date, datetime.max.time()),
            MaintenanceCost.deleted_at.is_(None)
        )
        
        result = self.session.execute(query).first()
        
        return {
            "total_cost": float(result.total or 0),
            "average_cost": float(result.average or 0)
        }
    
    def _get_performance_metrics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get performance metrics for period."""
        query = select(
            func.avg(
                extract('epoch', MaintenanceRequest.completed_at - MaintenanceRequest.created_at) / 3600
            ).label("avg_completion_hours"),
            func.sum(
                func.case(
                    (
                        and_(
                            MaintenanceRequest.completed_at.isnot(None),
                            MaintenanceRequest.deadline.isnot(None),
                            MaintenanceRequest.completed_at <= MaintenanceRequest.deadline
                        ),
                        1
                    ),
                    else_=0
                )
            ).label("on_time"),
            func.count(MaintenanceRequest.id).label("total_completed")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.status == MaintenanceStatus.COMPLETED,
            MaintenanceRequest.completed_at.isnot(None),
            MaintenanceRequest.created_at >= datetime.combine(start_date, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(end_date, datetime.max.time()),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        result = self.session.execute(query).first()
        
        on_time_rate = 0.0
        if result.total_completed and result.total_completed > 0:
            on_time_rate = (result.on_time / result.total_completed) * 100
        
        return {
            "average_completion_hours": float(result.avg_completion_hours or 0),
            "on_time_completion_rate": round(on_time_rate, 2),
            "total_completed": result.total_completed or 0
        }
    
    def _get_budget_status(self, hostel_id: UUID) -> Dict[str, Any]:
        """Get current budget status."""
        budget_query = select(BudgetAllocation).where(
            BudgetAllocation.hostel_id == hostel_id,
            BudgetAllocation.is_active == True
        ).order_by(
            BudgetAllocation.fiscal_year_start.desc()
        )
        
        budget = self.session.execute(budget_query).scalars().first()
        
        if not budget:
            return {
                "has_budget": False
            }
        
        return {
            "has_budget": True,
            "fiscal_year": budget.fiscal_year,
            "total_budget": float(budget.total_budget),
            "spent": float(budget.spent_amount),
            "remaining": float(budget.remaining_budget),
            "utilization": float(budget.utilization_percentage)
        }
    
    def _get_top_issues(
        self,
        hostel_id: UUID,
        days: int
    ) -> List[Dict[str, Any]]:
        """Get top recurring issues."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        query = select(
            MaintenanceRequest.category,
            MaintenanceRequest.title,
            func.count(MaintenanceRequest.id).label("occurrence_count")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.created_at >= datetime.combine(start_date, datetime.min.time()),
            MaintenanceRequest.deleted_at.is_(None)
        ).group_by(
            MaintenanceRequest.category,
            MaintenanceRequest.title
        ).order_by(
            desc("occurrence_count")
        ).limit(5)
        
        results = self.session.execute(query).all()
        
        return [
            {
                "category": str(row.category.value),
                "title": row.title,
                "occurrences": row.occurrence_count
            }
            for row in results
        ]


# Export repository class
__all__ = ["MaintenanceAggregateRepository"]