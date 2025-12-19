# app/repositories/maintenance/maintenance_assignment_repository.py
"""
Maintenance Assignment Repository.

Intelligent staff and vendor assignment with skill matching,
workload optimization, and performance tracking.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.maintenance import (
    MaintenanceAssignment,
    VendorAssignment,
    MaintenanceRequest,
    MaintenanceVendor,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.schemas.common.enums import MaintenanceCategory


class MaintenanceAssignmentRepository(BaseRepository[MaintenanceAssignment]):
    """
    Repository for maintenance assignment operations.
    
    Provides intelligent assignment management with skill matching,
    workload balancing, and performance analytics.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with session."""
        super().__init__(MaintenanceAssignment, session)
    
    # ============================================================================
    # CREATE OPERATIONS
    # ============================================================================
    
    def create_assignment(
        self,
        maintenance_request_id: UUID,
        assigned_to: UUID,
        assigned_by: UUID,
        deadline: Optional[datetime] = None,
        instructions: Optional[str] = None,
        estimated_hours: Optional[Decimal] = None,
        priority_level: Optional[str] = None,
        required_skills: Optional[List[str]] = None,
        tools_required: Optional[List[str]] = None,
        **kwargs
    ) -> MaintenanceAssignment:
        """
        Create new maintenance assignment.
        
        Args:
            maintenance_request_id: Request identifier
            assigned_to: Staff member to assign
            assigned_by: User making assignment
            deadline: Optional completion deadline
            instructions: Special instructions
            estimated_hours: Estimated hours to complete
            priority_level: Assignment priority
            required_skills: Required skills
            tools_required: Required tools/equipment
            **kwargs: Additional assignment attributes
            
        Returns:
            Created maintenance assignment
        """
        assignment_data = {
            "maintenance_request_id": maintenance_request_id,
            "assigned_to": assigned_to,
            "assigned_by": assigned_by,
            "deadline": deadline,
            "instructions": instructions,
            "estimated_hours": estimated_hours,
            "priority_level": priority_level,
            "required_skills": required_skills or [],
            "tools_required": tools_required or [],
            "is_active": True,
            "is_completed": False,
            **kwargs
        }
        
        return self.create(assignment_data)
    
    def create_vendor_assignment(
        self,
        maintenance_request_id: UUID,
        vendor_id: UUID,
        vendor_name: str,
        vendor_contact: str,
        quoted_amount: Decimal,
        estimated_completion_date: datetime,
        work_order_number: Optional[str] = None,
        contract_details: Optional[str] = None,
        payment_terms: Optional[str] = None,
        **kwargs
    ) -> VendorAssignment:
        """
        Create vendor assignment for maintenance work.
        
        Args:
            maintenance_request_id: Request identifier
            vendor_id: Vendor identifier
            vendor_name: Vendor company name
            vendor_contact: Contact number
            quoted_amount: Vendor quoted amount
            estimated_completion_date: Estimated completion
            work_order_number: Work order reference
            contract_details: Contract terms
            payment_terms: Payment terms
            **kwargs: Additional vendor assignment attributes
            
        Returns:
            Created vendor assignment
        """
        vendor_assignment_data = {
            "maintenance_request_id": maintenance_request_id,
            "vendor_id": vendor_id,
            "vendor_name": vendor_name,
            "vendor_contact": vendor_contact,
            "quoted_amount": quoted_amount,
            "estimated_completion_date": estimated_completion_date,
            "work_order_number": work_order_number or self._generate_work_order_number(),
            "contract_details": contract_details,
            "payment_terms": payment_terms,
            "is_active": True,
            "is_completed": False,
            **kwargs
        }
        
        vendor_assignment = VendorAssignment(**vendor_assignment_data)
        self.session.add(vendor_assignment)
        self.session.commit()
        self.session.refresh(vendor_assignment)
        
        return vendor_assignment
    
    # ============================================================================
    # READ OPERATIONS - STAFF ASSIGNMENTS
    # ============================================================================
    
    def find_by_assignee(
        self,
        assignee_id: UUID,
        is_active: Optional[bool] = True,
        is_completed: Optional[bool] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceAssignment]:
        """
        Find assignments for a specific staff member.
        
        Args:
            assignee_id: Staff member identifier
            is_active: Filter by active status
            is_completed: Filter by completion status
            pagination: Pagination parameters
            
        Returns:
            Paginated assignments
        """
        query = select(MaintenanceAssignment).where(
            MaintenanceAssignment.assigned_to == assignee_id,
            MaintenanceAssignment.deleted_at.is_(None)
        )
        
        if is_active is not None:
            query = query.where(MaintenanceAssignment.is_active == is_active)
        
        if is_completed is not None:
            query = query.where(MaintenanceAssignment.is_completed == is_completed)
        
        query = query.order_by(
            MaintenanceAssignment.deadline.asc().nullslast(),
            MaintenanceAssignment.assigned_at.desc()
        )
        
        return self.paginate(query, pagination)
    
    def find_by_request(
        self,
        request_id: UUID,
        include_inactive: bool = False
    ) -> List[MaintenanceAssignment]:
        """
        Find all assignments for a maintenance request.
        
        Args:
            request_id: Request identifier
            include_inactive: Include inactive assignments
            
        Returns:
            List of assignments
        """
        query = select(MaintenanceAssignment).where(
            MaintenanceAssignment.maintenance_request_id == request_id,
            MaintenanceAssignment.deleted_at.is_(None)
        )
        
        if not include_inactive:
            query = query.where(MaintenanceAssignment.is_active == True)
        
        query = query.order_by(MaintenanceAssignment.assigned_at.desc())
        
        return list(self.session.execute(query).scalars().all())
    
    def find_active_by_request(
        self,
        request_id: UUID
    ) -> Optional[MaintenanceAssignment]:
        """
        Find active assignment for a maintenance request.
        
        Args:
            request_id: Request identifier
            
        Returns:
            Active assignment if exists
        """
        query = select(MaintenanceAssignment).where(
            MaintenanceAssignment.maintenance_request_id == request_id,
            MaintenanceAssignment.is_active == True,
            MaintenanceAssignment.is_completed == False,
            MaintenanceAssignment.deleted_at.is_(None)
        )
        
        return self.session.execute(query).scalar_one_or_none()
    
    def find_overdue_assignments(
        self,
        assignee_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceAssignment]:
        """
        Find overdue assignments.
        
        Args:
            assignee_id: Optional assignee filter
            pagination: Pagination parameters
            
        Returns:
            Paginated overdue assignments
        """
        now = datetime.utcnow()
        
        query = select(MaintenanceAssignment).where(
            MaintenanceAssignment.is_completed == False,
            MaintenanceAssignment.is_active == True,
            MaintenanceAssignment.deadline.isnot(None),
            MaintenanceAssignment.deadline < now,
            MaintenanceAssignment.deleted_at.is_(None)
        )
        
        if assignee_id:
            query = query.where(MaintenanceAssignment.assigned_to == assignee_id)
        
        query = query.order_by(MaintenanceAssignment.deadline.asc())
        
        return self.paginate(query, pagination)
    
    def find_upcoming_deadlines(
        self,
        assignee_id: UUID,
        days: int = 3
    ) -> List[MaintenanceAssignment]:
        """
        Find assignments with upcoming deadlines.
        
        Args:
            assignee_id: Staff member identifier
            days: Number of days to look ahead
            
        Returns:
            List of assignments with upcoming deadlines
        """
        now = datetime.utcnow()
        future_date = now + timedelta(days=days)
        
        query = select(MaintenanceAssignment).where(
            MaintenanceAssignment.assigned_to == assignee_id,
            MaintenanceAssignment.is_completed == False,
            MaintenanceAssignment.is_active == True,
            MaintenanceAssignment.deadline.isnot(None),
            MaintenanceAssignment.deadline >= now,
            MaintenanceAssignment.deadline <= future_date,
            MaintenanceAssignment.deleted_at.is_(None)
        ).order_by(MaintenanceAssignment.deadline.asc())
        
        return list(self.session.execute(query).scalars().all())
    
    # ============================================================================
    # READ OPERATIONS - VENDOR ASSIGNMENTS
    # ============================================================================
    
    def find_vendor_assignments_by_vendor(
        self,
        vendor_id: UUID,
        is_active: Optional[bool] = True,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[VendorAssignment]:
        """
        Find vendor assignments for a specific vendor.
        
        Args:
            vendor_id: Vendor identifier
            is_active: Filter by active status
            pagination: Pagination parameters
            
        Returns:
            Paginated vendor assignments
        """
        query = select(VendorAssignment).where(
            VendorAssignment.vendor_id == vendor_id,
            VendorAssignment.deleted_at.is_(None)
        )
        
        if is_active is not None:
            query = query.where(VendorAssignment.is_active == is_active)
        
        query = query.order_by(
            VendorAssignment.estimated_completion_date.asc(),
            VendorAssignment.created_at.desc()
        )
        
        return self.paginate(query, pagination)
    
    def find_vendor_assignment_by_request(
        self,
        request_id: UUID
    ) -> Optional[VendorAssignment]:
        """
        Find vendor assignment for a maintenance request.
        
        Args:
            request_id: Request identifier
            
        Returns:
            Vendor assignment if exists
        """
        query = select(VendorAssignment).where(
            VendorAssignment.maintenance_request_id == request_id,
            VendorAssignment.is_active == True,
            VendorAssignment.deleted_at.is_(None)
        )
        
        return self.session.execute(query).scalar_one_or_none()
    
    def find_overdue_vendor_assignments(
        self,
        vendor_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[VendorAssignment]:
        """
        Find overdue vendor assignments.
        
        Args:
            vendor_id: Optional vendor filter
            pagination: Pagination parameters
            
        Returns:
            Paginated overdue vendor assignments
        """
        now = datetime.utcnow()
        
        query = select(VendorAssignment).where(
            VendorAssignment.is_completed == False,
            VendorAssignment.is_active == True,
            VendorAssignment.estimated_completion_date < now,
            VendorAssignment.deleted_at.is_(None)
        )
        
        if vendor_id:
            query = query.where(VendorAssignment.vendor_id == vendor_id)
        
        query = query.order_by(VendorAssignment.estimated_completion_date.asc())
        
        return self.paginate(query, pagination)
    
    # ============================================================================
    # UPDATE OPERATIONS
    # ============================================================================
    
    def mark_started(
        self,
        assignment_id: UUID,
        started_at: Optional[datetime] = None
    ) -> MaintenanceAssignment:
        """
        Mark assignment as started.
        
        Args:
            assignment_id: Assignment identifier
            started_at: Optional start timestamp
            
        Returns:
            Updated assignment
        """
        assignment = self.find_by_id(assignment_id)
        if not assignment:
            raise ValueError(f"Assignment {assignment_id} not found")
        
        assignment.started_at = started_at or datetime.utcnow()
        
        self.session.commit()
        self.session.refresh(assignment)
        
        return assignment
    
    def mark_completed(
        self,
        assignment_id: UUID,
        completion_notes: Optional[str] = None,
        actual_hours: Optional[Decimal] = None,
        quality_rating: Optional[int] = None
    ) -> MaintenanceAssignment:
        """
        Mark assignment as completed.
        
        Args:
            assignment_id: Assignment identifier
            completion_notes: Completion notes
            actual_hours: Actual hours spent
            quality_rating: Quality rating (1-5)
            
        Returns:
            Updated assignment
        """
        assignment = self.find_by_id(assignment_id)
        if not assignment:
            raise ValueError(f"Assignment {assignment_id} not found")
        
        assignment.mark_completed(
            completion_notes=completion_notes,
            actual_hours=actual_hours,
            quality_rating=quality_rating
        )
        
        self.session.commit()
        self.session.refresh(assignment)
        
        return assignment
    
    def reassign(
        self,
        assignment_id: UUID,
        new_assignee_id: UUID,
        reason: str,
        reassigned_by: UUID
    ) -> MaintenanceAssignment:
        """
        Reassign task to different staff member.
        
        Args:
            assignment_id: Current assignment identifier
            new_assignee_id: New assignee identifier
            reason: Reason for reassignment
            reassigned_by: User making reassignment
            
        Returns:
            New assignment record
        """
        old_assignment = self.find_by_id(assignment_id)
        if not old_assignment:
            raise ValueError(f"Assignment {assignment_id} not found")
        
        # Create new assignment using the model's reassign method
        new_assignment = old_assignment.reassign(
            new_assignee=new_assignee_id,
            reason=reason,
            reassigned_by=reassigned_by
        )
        
        self.session.add(new_assignment)
        self.session.commit()
        self.session.refresh(new_assignment)
        
        return new_assignment
    
    def update_vendor_assignment_status(
        self,
        assignment_id: UUID,
        is_completed: bool,
        actual_completion_date: Optional[datetime] = None,
        vendor_rating: Optional[int] = None,
        performance_notes: Optional[str] = None
    ) -> VendorAssignment:
        """
        Update vendor assignment completion status.
        
        Args:
            assignment_id: Vendor assignment identifier
            is_completed: Completion status
            actual_completion_date: Actual completion date
            vendor_rating: Vendor performance rating
            performance_notes: Performance notes
            
        Returns:
            Updated vendor assignment
        """
        query = select(VendorAssignment).where(
            VendorAssignment.id == assignment_id
        )
        vendor_assignment = self.session.execute(query).scalar_one_or_none()
        
        if not vendor_assignment:
            raise ValueError(f"Vendor assignment {assignment_id} not found")
        
        vendor_assignment.is_completed = is_completed
        
        if actual_completion_date:
            vendor_assignment.actual_completion_date = actual_completion_date
        
        if vendor_rating:
            vendor_assignment.vendor_rating = vendor_rating
        
        if performance_notes:
            vendor_assignment.performance_notes = performance_notes
        
        if is_completed:
            vendor_assignment.is_active = False
        
        self.session.commit()
        self.session.refresh(vendor_assignment)
        
        return vendor_assignment
    
    # ============================================================================
    # WORKLOAD OPTIMIZATION
    # ============================================================================
    
    def get_assignee_workload(
        self,
        assignee_id: UUID,
        include_completed: bool = False
    ) -> Dict[str, Any]:
        """
        Get current workload for a staff member.
        
        Args:
            assignee_id: Staff member identifier
            include_completed: Include completed assignments
            
        Returns:
            Workload statistics
        """
        query = select(
            func.count(MaintenanceAssignment.id).label("total_assignments"),
            func.sum(
                func.case(
                    (MaintenanceAssignment.is_completed == False, 1),
                    else_=0
                )
            ).label("active_assignments"),
            func.sum(
                func.case(
                    (MaintenanceAssignment.is_completed == True, 1),
                    else_=0
                )
            ).label("completed_assignments"),
            func.sum(MaintenanceAssignment.estimated_hours).label("estimated_hours"),
            func.sum(MaintenanceAssignment.actual_hours).label("actual_hours")
        ).where(
            MaintenanceAssignment.assigned_to == assignee_id,
            MaintenanceAssignment.deleted_at.is_(None)
        )
        
        if not include_completed:
            query = query.where(MaintenanceAssignment.is_completed == False)
        
        result = self.session.execute(query).first()
        
        return {
            "assignee_id": str(assignee_id),
            "total_assignments": result.total_assignments or 0,
            "active_assignments": result.active_assignments or 0,
            "completed_assignments": result.completed_assignments or 0,
            "estimated_hours": float(result.estimated_hours or 0),
            "actual_hours": float(result.actual_hours or 0)
        }
    
    def get_team_workload_distribution(
        self,
        assignee_ids: Optional[List[UUID]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get workload distribution across team members.
        
        Args:
            assignee_ids: Optional list of assignee IDs to analyze
            
        Returns:
            List of workload data per assignee
        """
        query = select(
            MaintenanceAssignment.assigned_to,
            func.count(MaintenanceAssignment.id).label("total_assignments"),
            func.sum(
                func.case(
                    (MaintenanceAssignment.is_completed == False, 1),
                    else_=0
                )
            ).label("active_assignments"),
            func.sum(MaintenanceAssignment.estimated_hours).label("estimated_hours")
        ).where(
            MaintenanceAssignment.is_active == True,
            MaintenanceAssignment.deleted_at.is_(None)
        )
        
        if assignee_ids:
            query = query.where(MaintenanceAssignment.assigned_to.in_(assignee_ids))
        
        query = query.group_by(
            MaintenanceAssignment.assigned_to
        ).order_by(
            desc("active_assignments")
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "assignee_id": str(row.assigned_to),
                "total_assignments": row.total_assignments,
                "active_assignments": row.active_assignments,
                "estimated_hours": float(row.estimated_hours or 0)
            }
            for row in results
        ]
    
    def suggest_optimal_assignee(
        self,
        required_skills: List[str],
        estimated_hours: Decimal,
        exclude_assignees: Optional[List[UUID]] = None
    ) -> Optional[UUID]:
        """
        Suggest optimal assignee based on workload and skills.
        
        Args:
            required_skills: Required skills for assignment
            estimated_hours: Estimated hours for task
            exclude_assignees: Assignees to exclude
            
        Returns:
            Suggested assignee ID, or None if no suitable assignee
        """
        # Get team workload
        workload_data = self.get_team_workload_distribution()
        
        if not workload_data:
            return None
        
        # Filter out excluded assignees
        if exclude_assignees:
            workload_data = [
                w for w in workload_data
                if UUID(w["assignee_id"]) not in exclude_assignees
            ]
        
        # Sort by active assignments (ascending) and estimated hours (ascending)
        workload_data.sort(
            key=lambda x: (x["active_assignments"], x["estimated_hours"])
        )
        
        # Return assignee with lowest workload
        if workload_data:
            return UUID(workload_data[0]["assignee_id"])
        
        return None
    
    # ============================================================================
    # PERFORMANCE ANALYTICS
    # ============================================================================
    
    def calculate_completion_rate(
        self,
        assignee_id: UUID,
        days: int = 30
    ) -> Decimal:
        """
        Calculate assignment completion rate for staff member.
        
        Args:
            assignee_id: Staff member identifier
            days: Time period in days
            
        Returns:
            Completion rate percentage
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            func.count(MaintenanceAssignment.id).label("total"),
            func.sum(
                func.case(
                    (MaintenanceAssignment.is_completed == True, 1),
                    else_=0
                )
            ).label("completed")
        ).where(
            MaintenanceAssignment.assigned_to == assignee_id,
            MaintenanceAssignment.assigned_at >= cutoff_date,
            MaintenanceAssignment.deleted_at.is_(None)
        )
        
        result = self.session.execute(query).first()
        
        if not result or result.total == 0:
            return Decimal("0.00")
        
        return round(
            Decimal(result.completed) / Decimal(result.total) * 100,
            2
        )
    
    def calculate_average_time_variance(
        self,
        assignee_id: UUID,
        days: int = 90
    ) -> Optional[Decimal]:
        """
        Calculate average time variance (actual vs estimated) for assignee.
        
        Args:
            assignee_id: Staff member identifier
            days: Time period in days
            
        Returns:
            Average variance in hours, or None if no data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            func.avg(
                MaintenanceAssignment.actual_hours - MaintenanceAssignment.estimated_hours
            ).label("avg_variance")
        ).where(
            MaintenanceAssignment.assigned_to == assignee_id,
            MaintenanceAssignment.is_completed == True,
            MaintenanceAssignment.actual_hours.isnot(None),
            MaintenanceAssignment.estimated_hours.isnot(None),
            MaintenanceAssignment.completed_at >= cutoff_date,
            MaintenanceAssignment.deleted_at.is_(None)
        )
        
        result = self.session.execute(query).scalar_one_or_none()
        
        return Decimal(str(result)) if result else None
    
    def get_quality_metrics(
        self,
        assignee_id: UUID,
        days: int = 90
    ) -> Dict[str, Any]:
        """
        Get quality metrics for staff member.
        
        Args:
            assignee_id: Staff member identifier
            days: Time period in days
            
        Returns:
            Quality metrics dictionary
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            func.count(MaintenanceAssignment.id).label("total_rated"),
            func.avg(MaintenanceAssignment.quality_rating).label("avg_rating"),
            func.min(MaintenanceAssignment.quality_rating).label("min_rating"),
            func.max(MaintenanceAssignment.quality_rating).label("max_rating")
        ).where(
            MaintenanceAssignment.assigned_to == assignee_id,
            MaintenanceAssignment.is_completed == True,
            MaintenanceAssignment.quality_rating.isnot(None),
            MaintenanceAssignment.completed_at >= cutoff_date,
            MaintenanceAssignment.deleted_at.is_(None)
        )
        
        result = self.session.execute(query).first()
        
        return {
            "total_rated": result.total_rated or 0,
            "average_rating": float(result.avg_rating) if result.avg_rating else 0.0,
            "min_rating": result.min_rating or 0,
            "max_rating": result.max_rating or 0
        }
    
    def calculate_on_time_completion_rate(
        self,
        assignee_id: UUID,
        days: int = 90
    ) -> Decimal:
        """
        Calculate on-time completion rate for staff member.
        
        Args:
            assignee_id: Staff member identifier
            days: Time period in days
            
        Returns:
            On-time completion rate percentage
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            func.count(MaintenanceAssignment.id).label("total"),
            func.sum(
                func.case(
                    (MaintenanceAssignment.met_deadline == True, 1),
                    else_=0
                )
            ).label("on_time")
        ).where(
            MaintenanceAssignment.assigned_to == assignee_id,
            MaintenanceAssignment.is_completed == True,
            MaintenanceAssignment.deadline.isnot(None),
            MaintenanceAssignment.completed_at >= cutoff_date,
            MaintenanceAssignment.deleted_at.is_(None)
        )
        
        result = self.session.execute(query).first()
        
        if not result or result.total == 0:
            return Decimal("0.00")
        
        return round(
            Decimal(result.on_time) / Decimal(result.total) * 100,
            2
        )
    
    def get_vendor_performance_summary(
        self,
        vendor_id: UUID,
        days: int = 180
    ) -> Dict[str, Any]:
        """
        Get performance summary for vendor.
        
        Args:
            vendor_id: Vendor identifier
            days: Time period in days
            
        Returns:
            Vendor performance summary
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            func.count(VendorAssignment.id).label("total_jobs"),
            func.sum(
                func.case(
                    (VendorAssignment.is_completed == True, 1),
                    else_=0
                )
            ).label("completed_jobs"),
            func.avg(VendorAssignment.vendor_rating).label("avg_rating"),
            func.sum(VendorAssignment.quoted_amount).label("total_quoted"),
            func.sum(VendorAssignment.payment_amount).label("total_paid"),
            func.avg(
                func.extract(
                    'epoch',
                    VendorAssignment.actual_completion_date - VendorAssignment.estimated_completion_date
                ) / 86400
            ).label("avg_delay_days")
        ).where(
            VendorAssignment.vendor_id == vendor_id,
            VendorAssignment.created_at >= cutoff_date,
            VendorAssignment.deleted_at.is_(None)
        )
        
        result = self.session.execute(query).first()
        
        completion_rate = Decimal("0.00")
        if result.total_jobs and result.total_jobs > 0:
            completion_rate = round(
                Decimal(result.completed_jobs or 0) / Decimal(result.total_jobs) * 100,
                2
            )
        
        return {
            "vendor_id": str(vendor_id),
            "total_jobs": result.total_jobs or 0,
            "completed_jobs": result.completed_jobs or 0,
            "completion_rate": float(completion_rate),
            "average_rating": float(result.avg_rating) if result.avg_rating else 0.0,
            "total_quoted": float(result.total_quoted or 0),
            "total_paid": float(result.total_paid or 0),
            "average_delay_days": float(result.avg_delay_days) if result.avg_delay_days else 0.0
        }
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _generate_work_order_number(self) -> str:
        """
        Generate unique work order number for vendor assignment.
        
        Returns:
            Unique work order number
        """
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        
        # Count vendor assignments this month
        count_query = select(
            func.count(VendorAssignment.id)
        ).where(
            func.extract('year', VendorAssignment.created_at) == now.year,
            func.extract('month', VendorAssignment.created_at) == now.month
        )
        
        count = self.session.execute(count_query).scalar_one() + 1
        
        # Format: WO-YYYY-MM-0001
        return f"WO-{year}-{month}-{count:04d}"


class VendorAssignmentRepository(BaseRepository[VendorAssignment]):
    """
    Dedicated repository for vendor assignment operations.
    
    Provides specialized vendor assignment management separate from
    staff assignments for clearer domain separation.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with session."""
        super().__init__(VendorAssignment, session)
    
    # Additional vendor-specific methods can be added here
    # This provides a clean separation of concerns