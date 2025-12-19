# app/repositories/maintenance/maintenance_request_repository.py
"""
Maintenance Request Repository.

Comprehensive maintenance request management with predictive scheduling,
resource optimization, and performance tracking.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.maintenance import (
    MaintenanceRequest,
    MaintenanceStatusHistory,
    MaintenanceIssueType,
    MaintenanceAssignment,
    MaintenanceCompletion,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.repositories.base.specifications import Specification
from app.schemas.common.enums import (
    MaintenanceCategory,
    MaintenanceStatus,
    Priority,
    MaintenanceIssueType as IssueTypeEnum,
)


class MaintenanceRequestRepository(BaseRepository[MaintenanceRequest]):
    """
    Repository for maintenance request operations.
    
    Provides comprehensive CRUD operations, advanced querying,
    predictive analytics, and performance tracking for maintenance requests.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with session."""
        super().__init__(MaintenanceRequest, session)
    
    # ============================================================================
    # CREATE OPERATIONS
    # ============================================================================
    
    def create_request(
        self,
        hostel_id: UUID,
        requested_by: UUID,
        title: str,
        description: str,
        category: MaintenanceCategory,
        priority: Priority,
        issue_type: IssueTypeEnum,
        room_id: Optional[UUID] = None,
        floor: Optional[int] = None,
        specific_area: Optional[str] = None,
        estimated_cost: Optional[Decimal] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> MaintenanceRequest:
        """
        Create new maintenance request with automatic categorization.
        
        Args:
            hostel_id: Hostel identifier
            requested_by: User who requested maintenance
            title: Brief issue summary
            description: Detailed description
            category: Maintenance category
            priority: Priority level
            issue_type: Type of issue
            room_id: Optional room identifier
            floor: Optional floor number
            specific_area: Optional specific location
            estimated_cost: Optional cost estimate
            metadata: Additional metadata
            **kwargs: Additional request attributes
            
        Returns:
            Created maintenance request
        """
        # Generate unique request number
        request_number = self._generate_request_number(hostel_id)
        
        # Determine if approval required based on cost
        requires_approval = self._check_approval_requirement(
            estimated_cost,
            hostel_id
        )
        
        request_data = {
            "request_number": request_number,
            "hostel_id": hostel_id,
            "requested_by": requested_by,
            "title": title,
            "description": description,
            "category": category,
            "priority": priority,
            "issue_type": issue_type,
            "room_id": room_id,
            "floor": floor,
            "specific_area": specific_area,
            "estimated_cost": estimated_cost,
            "requires_approval": requires_approval,
            "status": MaintenanceStatus.PENDING,
            "metadata": metadata or {},
            **kwargs
        }
        
        request = self.create(request_data)
        
        # Create initial status history
        self._create_status_history(
            request.id,
            None,
            MaintenanceStatus.PENDING,
            requested_by,
            "Request created"
        )
        
        return request
    
    def create_emergency_request(
        self,
        hostel_id: UUID,
        requested_by: UUID,
        title: str,
        description: str,
        category: MaintenanceCategory,
        **kwargs
    ) -> MaintenanceRequest:
        """
        Create emergency maintenance request with high priority.
        
        Args:
            hostel_id: Hostel identifier
            requested_by: User requesting
            title: Issue title
            description: Issue description
            category: Maintenance category
            **kwargs: Additional attributes
            
        Returns:
            Created emergency request
        """
        return self.create_request(
            hostel_id=hostel_id,
            requested_by=requested_by,
            title=title,
            description=description,
            category=category,
            priority=Priority.CRITICAL,
            issue_type=IssueTypeEnum.EMERGENCY,
            **kwargs
        )
    
    def create_preventive_request(
        self,
        schedule_id: UUID,
        hostel_id: UUID,
        title: str,
        description: str,
        category: MaintenanceCategory,
        **kwargs
    ) -> MaintenanceRequest:
        """
        Create preventive maintenance request from schedule.
        
        Args:
            schedule_id: Related schedule identifier
            hostel_id: Hostel identifier
            title: Maintenance title
            description: Detailed description
            category: Maintenance category
            **kwargs: Additional attributes
            
        Returns:
            Created preventive maintenance request
        """
        return self.create_request(
            hostel_id=hostel_id,
            requested_by=kwargs.pop("requested_by", None),
            title=title,
            description=description,
            category=category,
            priority=Priority.MEDIUM,
            issue_type=IssueTypeEnum.ROUTINE,
            is_preventive=True,
            preventive_schedule_id=schedule_id,
            **kwargs
        )
    
    # ============================================================================
    # READ OPERATIONS - BASIC
    # ============================================================================
    
    def find_by_request_number(
        self,
        request_number: str,
        include_deleted: bool = False
    ) -> Optional[MaintenanceRequest]:
        """
        Find maintenance request by request number.
        
        Args:
            request_number: Request number to find
            include_deleted: Include soft-deleted records
            
        Returns:
            Maintenance request if found, None otherwise
        """
        query = select(MaintenanceRequest).where(
            MaintenanceRequest.request_number == request_number
        )
        
        if not include_deleted:
            query = query.where(MaintenanceRequest.deleted_at.is_(None))
        
        return self.session.execute(query).scalar_one_or_none()
    
    def find_by_hostel(
        self,
        hostel_id: UUID,
        status: Optional[MaintenanceStatus] = None,
        category: Optional[MaintenanceCategory] = None,
        priority: Optional[Priority] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceRequest]:
        """
        Find maintenance requests for a hostel with filtering.
        
        Args:
            hostel_id: Hostel identifier
            status: Optional status filter
            category: Optional category filter
            priority: Optional priority filter
            pagination: Pagination parameters
            
        Returns:
            Paginated maintenance requests
        """
        query = select(MaintenanceRequest).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        # Apply filters
        if status:
            query = query.where(MaintenanceRequest.status == status)
        if category:
            query = query.where(MaintenanceRequest.category == category)
        if priority:
            query = query.where(MaintenanceRequest.priority == priority)
        
        # Order by priority and created date
        query = query.order_by(
            MaintenanceRequest.priority.desc(),
            MaintenanceRequest.created_at.desc()
        )
        
        return self.paginate(query, pagination)
    
    def find_by_assignee(
        self,
        assignee_id: UUID,
        status: Optional[MaintenanceStatus] = None,
        include_completed: bool = False,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceRequest]:
        """
        Find maintenance requests assigned to a user.
        
        Args:
            assignee_id: Assignee user identifier
            status: Optional status filter
            include_completed: Include completed requests
            pagination: Pagination parameters
            
        Returns:
            Paginated assigned requests
        """
        query = select(MaintenanceRequest).where(
            MaintenanceRequest.assigned_to == assignee_id,
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if status:
            query = query.where(MaintenanceRequest.status == status)
        elif not include_completed:
            query = query.where(
                MaintenanceRequest.status != MaintenanceStatus.COMPLETED
            )
        
        query = query.order_by(
            MaintenanceRequest.priority.desc(),
            MaintenanceRequest.deadline.asc().nullslast()
        )
        
        return self.paginate(query, pagination)
    
    def find_by_room(
        self,
        room_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceRequest]:
        """
        Find maintenance requests for a specific room.
        
        Args:
            room_id: Room identifier
            start_date: Optional start date filter
            end_date: Optional end date filter
            pagination: Pagination parameters
            
        Returns:
            Paginated room maintenance requests
        """
        query = select(MaintenanceRequest).where(
            MaintenanceRequest.room_id == room_id,
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if start_date:
            query = query.where(MaintenanceRequest.created_at >= start_date)
        if end_date:
            query = query.where(MaintenanceRequest.created_at <= end_date)
        
        query = query.order_by(MaintenanceRequest.created_at.desc())
        
        return self.paginate(query, pagination)
    
    # ============================================================================
    # READ OPERATIONS - ADVANCED QUERIES
    # ============================================================================
    
    def find_pending_requests(
        self,
        hostel_id: Optional[UUID] = None,
        age_days: Optional[int] = None,
        priority: Optional[Priority] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceRequest]:
        """
        Find pending maintenance requests with optional filters.
        
        Args:
            hostel_id: Optional hostel filter
            age_days: Optional minimum age in days
            priority: Optional priority filter
            pagination: Pagination parameters
            
        Returns:
            Paginated pending requests
        """
        query = select(MaintenanceRequest).where(
            MaintenanceRequest.status == MaintenanceStatus.PENDING,
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(MaintenanceRequest.hostel_id == hostel_id)
        
        if age_days:
            cutoff_date = datetime.utcnow() - timedelta(days=age_days)
            query = query.where(MaintenanceRequest.created_at <= cutoff_date)
        
        if priority:
            query = query.where(MaintenanceRequest.priority == priority)
        
        query = query.order_by(
            MaintenanceRequest.priority.desc(),
            MaintenanceRequest.created_at.asc()
        )
        
        return self.paginate(query, pagination)
    
    def find_overdue_requests(
        self,
        hostel_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceRequest]:
        """
        Find overdue maintenance requests.
        
        Args:
            hostel_id: Optional hostel filter
            pagination: Pagination parameters
            
        Returns:
            Paginated overdue requests
        """
        now = datetime.utcnow()
        
        query = select(MaintenanceRequest).where(
            MaintenanceRequest.status != MaintenanceStatus.COMPLETED,
            MaintenanceRequest.deleted_at.is_(None),
            or_(
                and_(
                    MaintenanceRequest.deadline.isnot(None),
                    MaintenanceRequest.deadline < now
                ),
                and_(
                    MaintenanceRequest.estimated_completion_date.isnot(None),
                    MaintenanceRequest.estimated_completion_date < now
                )
            )
        )
        
        if hostel_id:
            query = query.where(MaintenanceRequest.hostel_id == hostel_id)
        
        query = query.order_by(
            MaintenanceRequest.priority.desc(),
            MaintenanceRequest.deadline.asc().nullslast()
        )
        
        return self.paginate(query, pagination)
    
    def find_high_priority_unassigned(
        self,
        hostel_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceRequest]:
        """
        Find high priority requests that are unassigned.
        
        Args:
            hostel_id: Optional hostel filter
            pagination: Pagination parameters
            
        Returns:
            Paginated high priority unassigned requests
        """
        query = select(MaintenanceRequest).where(
            MaintenanceRequest.assigned_to.is_(None),
            MaintenanceRequest.priority.in_([
                Priority.HIGH,
                Priority.URGENT,
                Priority.CRITICAL
            ]),
            MaintenanceRequest.status.in_([
                MaintenanceStatus.PENDING,
                MaintenanceStatus.APPROVED
            ]),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(MaintenanceRequest.hostel_id == hostel_id)
        
        query = query.order_by(
            MaintenanceRequest.priority.desc(),
            MaintenanceRequest.created_at.asc()
        )
        
        return self.paginate(query, pagination)
    
    def find_awaiting_approval(
        self,
        hostel_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceRequest]:
        """
        Find requests awaiting approval.
        
        Args:
            hostel_id: Optional hostel filter
            pagination: Pagination parameters
            
        Returns:
            Paginated requests awaiting approval
        """
        query = select(MaintenanceRequest).where(
            MaintenanceRequest.requires_approval == True,
            MaintenanceRequest.approval_pending == True,
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(MaintenanceRequest.hostel_id == hostel_id)
        
        query = query.order_by(
            MaintenanceRequest.priority.desc(),
            MaintenanceRequest.created_at.asc()
        )
        
        return self.paginate(query, pagination)
    
    def find_in_progress(
        self,
        hostel_id: Optional[UUID] = None,
        assignee_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceRequest]:
        """
        Find maintenance requests currently in progress.
        
        Args:
            hostel_id: Optional hostel filter
            assignee_id: Optional assignee filter
            pagination: Pagination parameters
            
        Returns:
            Paginated in-progress requests
        """
        query = select(MaintenanceRequest).where(
            MaintenanceRequest.status == MaintenanceStatus.IN_PROGRESS,
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(MaintenanceRequest.hostel_id == hostel_id)
        if assignee_id:
            query = query.where(MaintenanceRequest.assigned_to == assignee_id)
        
        query = query.order_by(
            MaintenanceRequest.priority.desc(),
            MaintenanceRequest.actual_start_date.asc().nullslast()
        )
        
        return self.paginate(query, pagination)
    
    def find_completed_in_period(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None,
        category: Optional[MaintenanceCategory] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceRequest]:
        """
        Find completed requests within a date range.
        
        Args:
            start_date: Period start date
            end_date: Period end date
            hostel_id: Optional hostel filter
            category: Optional category filter
            pagination: Pagination parameters
            
        Returns:
            Paginated completed requests
        """
        query = select(MaintenanceRequest).where(
            MaintenanceRequest.status == MaintenanceStatus.COMPLETED,
            MaintenanceRequest.completed_at >= start_date,
            MaintenanceRequest.completed_at <= end_date,
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(MaintenanceRequest.hostel_id == hostel_id)
        if category:
            query = query.where(MaintenanceRequest.category == category)
        
        query = query.order_by(MaintenanceRequest.completed_at.desc())
        
        return self.paginate(query, pagination)
    
    def find_recurring_issues(
        self,
        hostel_id: UUID,
        category: MaintenanceCategory,
        room_id: Optional[UUID] = None,
        days: int = 90,
        min_occurrences: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Identify recurring maintenance issues.
        
        Args:
            hostel_id: Hostel identifier
            category: Maintenance category
            room_id: Optional room filter
            days: Time period in days
            min_occurrences: Minimum occurrences to be considered recurring
            
        Returns:
            List of recurring issue patterns
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            MaintenanceRequest.room_id,
            MaintenanceRequest.category,
            MaintenanceRequest.specific_area,
            func.count(MaintenanceRequest.id).label("occurrence_count"),
            func.avg(MaintenanceRequest.actual_cost).label("avg_cost")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.category == category,
            MaintenanceRequest.created_at >= cutoff_date,
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if room_id:
            query = query.where(MaintenanceRequest.room_id == room_id)
        
        query = query.group_by(
            MaintenanceRequest.room_id,
            MaintenanceRequest.category,
            MaintenanceRequest.specific_area
        ).having(
            func.count(MaintenanceRequest.id) >= min_occurrences
        ).order_by(
            desc("occurrence_count")
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "room_id": row.room_id,
                "category": row.category,
                "specific_area": row.specific_area,
                "occurrence_count": row.occurrence_count,
                "average_cost": float(row.avg_cost) if row.avg_cost else 0.0
            }
            for row in results
        ]
    
    # ============================================================================
    # UPDATE OPERATIONS
    # ============================================================================
    
    def update_status(
        self,
        request_id: UUID,
        new_status: MaintenanceStatus,
        changed_by: UUID,
        notes: Optional[str] = None
    ) -> MaintenanceRequest:
        """
        Update maintenance request status with audit trail.
        
        Args:
            request_id: Request identifier
            new_status: New status
            changed_by: User making the change
            notes: Optional status change notes
            
        Returns:
            Updated maintenance request
            
        Raises:
            ValueError: If request not found or invalid status transition
        """
        request = self.find_by_id(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        old_status = request.status
        
        # Validate status transition
        if not self._is_valid_status_transition(old_status, new_status):
            raise ValueError(
                f"Invalid status transition from {old_status} to {new_status}"
            )
        
        # Update request
        request.status = new_status
        request.status_changed_at = datetime.utcnow()
        request.status_changed_by = changed_by
        
        # Create status history
        self._create_status_history(
            request_id,
            old_status,
            new_status,
            changed_by,
            notes
        )
        
        self.session.commit()
        self.session.refresh(request)
        
        return request
    
    def assign_request(
        self,
        request_id: UUID,
        assignee_id: UUID,
        assigned_by: UUID,
        deadline: Optional[datetime] = None,
        notes: Optional[str] = None
    ) -> MaintenanceRequest:
        """
        Assign maintenance request to a user.
        
        Args:
            request_id: Request identifier
            assignee_id: User to assign to
            assigned_by: User making assignment
            deadline: Optional deadline
            notes: Optional assignment notes
            
        Returns:
            Updated maintenance request
        """
        request = self.find_by_id(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        request.assigned_to = assignee_id
        request.assigned_by = assigned_by
        request.assigned_at = datetime.utcnow()
        
        if deadline:
            request.deadline = deadline
        
        # Update status if pending
        if request.status == MaintenanceStatus.PENDING:
            request.update_status(
                MaintenanceStatus.ASSIGNED,
                assigned_by,
                notes or f"Assigned to user {assignee_id}"
            )
        
        self.session.commit()
        self.session.refresh(request)
        
        return request
    
    def update_cost_estimate(
        self,
        request_id: UUID,
        estimated_cost: Decimal,
        updated_by: UUID
    ) -> MaintenanceRequest:
        """
        Update cost estimate for maintenance request.
        
        Args:
            request_id: Request identifier
            estimated_cost: New cost estimate
            updated_by: User making update
            
        Returns:
            Updated maintenance request
        """
        request = self.find_by_id(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        request.estimated_cost = estimated_cost
        
        # Check if approval needed based on new cost
        request.requires_approval = self._check_approval_requirement(
            estimated_cost,
            request.hostel_id
        )
        
        self.session.commit()
        self.session.refresh(request)
        
        return request
    
    def mark_started(
        self,
        request_id: UUID,
        started_by: UUID,
        actual_start_date: Optional[datetime] = None
    ) -> MaintenanceRequest:
        """
        Mark maintenance request as started.
        
        Args:
            request_id: Request identifier
            started_by: User starting work
            actual_start_date: Optional start date (defaults to now)
            
        Returns:
            Updated maintenance request
        """
        request = self.find_by_id(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        request.actual_start_date = actual_start_date or datetime.utcnow()
        request.update_status(
            MaintenanceStatus.IN_PROGRESS,
            started_by,
            "Work started"
        )
        
        self.session.commit()
        self.session.refresh(request)
        
        return request
    
    def mark_completed(
        self,
        request_id: UUID,
        completed_by: UUID,
        work_notes: str,
        actual_cost: Optional[Decimal] = None,
        actual_completion_date: Optional[datetime] = None
    ) -> MaintenanceRequest:
        """
        Mark maintenance request as completed.
        
        Args:
            request_id: Request identifier
            completed_by: User completing work
            work_notes: Work completion notes
            actual_cost: Optional actual cost
            actual_completion_date: Optional completion date
            
        Returns:
            Updated maintenance request
        """
        request = self.find_by_id(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        request.completed_by = completed_by
        request.completed_at = actual_completion_date or datetime.utcnow()
        request.actual_completion_date = actual_completion_date or datetime.utcnow()
        request.work_notes = work_notes
        
        if actual_cost:
            request.actual_cost = actual_cost
        
        request.update_status(
            MaintenanceStatus.COMPLETED,
            completed_by,
            "Work completed"
        )
        
        self.session.commit()
        self.session.refresh(request)
        
        return request
    
    # ============================================================================
    # ANALYTICS AND REPORTING
    # ============================================================================
    
    def get_status_summary(
        self,
        hostel_id: Optional[UUID] = None,
        category: Optional[MaintenanceCategory] = None
    ) -> Dict[str, int]:
        """
        Get summary of requests by status.
        
        Args:
            hostel_id: Optional hostel filter
            category: Optional category filter
            
        Returns:
            Dictionary of status counts
        """
        query = select(
            MaintenanceRequest.status,
            func.count(MaintenanceRequest.id).label("count")
        ).where(
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(MaintenanceRequest.hostel_id == hostel_id)
        if category:
            query = query.where(MaintenanceRequest.category == category)
        
        query = query.group_by(MaintenanceRequest.status)
        
        results = self.session.execute(query).all()
        
        return {
            str(row.status.value): row.count
            for row in results
        }
    
    def get_category_distribution(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Get distribution of requests by category.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Dictionary of category counts
        """
        query = select(
            MaintenanceRequest.category,
            func.count(MaintenanceRequest.id).label("count")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if start_date:
            query = query.where(MaintenanceRequest.created_at >= start_date)
        if end_date:
            query = query.where(MaintenanceRequest.created_at <= end_date)
        
        query = query.group_by(MaintenanceRequest.category)
        
        results = self.session.execute(query).all()
        
        return {
            str(row.category.value): row.count
            for row in results
        }
    
    def get_priority_distribution(
        self,
        hostel_id: UUID,
        status: Optional[MaintenanceStatus] = None
    ) -> Dict[str, int]:
        """
        Get distribution of requests by priority.
        
        Args:
            hostel_id: Hostel identifier
            status: Optional status filter
            
        Returns:
            Dictionary of priority counts
        """
        query = select(
            MaintenanceRequest.priority,
            func.count(MaintenanceRequest.id).label("count")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if status:
            query = query.where(MaintenanceRequest.status == status)
        
        query = query.group_by(MaintenanceRequest.priority)
        
        results = self.session.execute(query).all()
        
        return {
            str(row.priority.value): row.count
            for row in results
        }
    
    def calculate_average_completion_time(
        self,
        hostel_id: UUID,
        category: Optional[MaintenanceCategory] = None,
        priority: Optional[Priority] = None,
        days: int = 90
    ) -> Optional[float]:
        """
        Calculate average completion time in hours.
        
        Args:
            hostel_id: Hostel identifier
            category: Optional category filter
            priority: Optional priority filter
            days: Time period in days
            
        Returns:
            Average completion time in hours, or None if no data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            func.avg(
                func.extract(
                    'epoch',
                    MaintenanceRequest.completed_at - MaintenanceRequest.created_at
                ) / 3600
            ).label("avg_hours")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.status == MaintenanceStatus.COMPLETED,
            MaintenanceRequest.completed_at >= cutoff_date,
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if category:
            query = query.where(MaintenanceRequest.category == category)
        if priority:
            query = query.where(MaintenanceRequest.priority == priority)
        
        result = self.session.execute(query).scalar_one_or_none()
        
        return float(result) if result else None
    
    def calculate_cost_metrics(
        self,
        hostel_id: UUID,
        start_date: datetime,
        end_date: datetime,
        category: Optional[MaintenanceCategory] = None
    ) -> Dict[str, Any]:
        """
        Calculate cost-related metrics for completed requests.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Period start date
            end_date: Period end date
            category: Optional category filter
            
        Returns:
            Dictionary of cost metrics
        """
        query = select(
            func.count(MaintenanceRequest.id).label("total_requests"),
            func.sum(MaintenanceRequest.actual_cost).label("total_cost"),
            func.avg(MaintenanceRequest.actual_cost).label("avg_cost"),
            func.min(MaintenanceRequest.actual_cost).label("min_cost"),
            func.max(MaintenanceRequest.actual_cost).label("max_cost")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.status == MaintenanceStatus.COMPLETED,
            MaintenanceRequest.completed_at >= start_date,
            MaintenanceRequest.completed_at <= end_date,
            MaintenanceRequest.actual_cost.isnot(None),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if category:
            query = query.where(MaintenanceRequest.category == category)
        
        result = self.session.execute(query).first()
        
        if not result or result.total_requests == 0:
            return {
                "total_requests": 0,
                "total_cost": 0.0,
                "average_cost": 0.0,
                "min_cost": 0.0,
                "max_cost": 0.0
            }
        
        return {
            "total_requests": result.total_requests,
            "total_cost": float(result.total_cost or 0),
            "average_cost": float(result.avg_cost or 0),
            "min_cost": float(result.min_cost or 0),
            "max_cost": float(result.max_cost or 0)
        }
    
    def get_assignee_workload(
        self,
        hostel_id: UUID,
        include_completed: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get workload distribution across assignees.
        
        Args:
            hostel_id: Hostel identifier
            include_completed: Include completed requests
            
        Returns:
            List of assignee workload data
        """
        query = select(
            MaintenanceRequest.assigned_to,
            func.count(MaintenanceRequest.id).label("total_assigned"),
            func.count(
                func.nullif(
                    MaintenanceRequest.status == MaintenanceStatus.COMPLETED,
                    False
                )
            ).label("completed"),
            func.count(
                func.nullif(
                    MaintenanceRequest.status == MaintenanceStatus.IN_PROGRESS,
                    False
                )
            ).label("in_progress")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.assigned_to.isnot(None),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if not include_completed:
            query = query.where(
                MaintenanceRequest.status != MaintenanceStatus.COMPLETED
            )
        
        query = query.group_by(
            MaintenanceRequest.assigned_to
        ).order_by(
            desc("total_assigned")
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "assignee_id": str(row.assigned_to),
                "total_assigned": row.total_assigned,
                "completed": row.completed,
                "in_progress": row.in_progress
            }
            for row in results
        ]
    
    # ============================================================================
    # PREDICTIVE ANALYTICS
    # ============================================================================
    
    def predict_completion_date(
        self,
        request_id: UUID
    ) -> Optional[datetime]:
        """
        Predict completion date based on historical data.
        
        Args:
            request_id: Request identifier
            
        Returns:
            Predicted completion date, or None if insufficient data
        """
        request = self.find_by_id(request_id)
        if not request:
            return None
        
        # Get average completion time for similar requests
        avg_hours = self.calculate_average_completion_time(
            hostel_id=request.hostel_id,
            category=request.category,
            priority=request.priority
        )
        
        if not avg_hours:
            # Fallback to category average
            avg_hours = self.calculate_average_completion_time(
                hostel_id=request.hostel_id,
                category=request.category
            )
        
        if not avg_hours:
            return None
        
        # Calculate prediction from created date or start date
        base_date = request.actual_start_date or request.created_at
        predicted_date = base_date + timedelta(hours=avg_hours)
        
        return predicted_date
    
    def identify_bottlenecks(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Identify maintenance bottlenecks and delays.
        
        Args:
            hostel_id: Hostel identifier
            days: Time period for analysis
            
        Returns:
            List of identified bottlenecks
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        bottlenecks = []
        
        # Check for unassigned high-priority requests
        unassigned_query = select(
            func.count(MaintenanceRequest.id).label("count")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.assigned_to.is_(None),
            MaintenanceRequest.priority.in_([Priority.HIGH, Priority.URGENT, Priority.CRITICAL]),
            MaintenanceRequest.created_at >= cutoff_date,
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        unassigned_count = self.session.execute(unassigned_query).scalar_one()
        
        if unassigned_count > 0:
            bottlenecks.append({
                "type": "unassigned_high_priority",
                "count": unassigned_count,
                "severity": "high",
                "description": f"{unassigned_count} high-priority requests unassigned"
            })
        
        # Check for overdue requests
        overdue_query = select(
            func.count(MaintenanceRequest.id).label("count")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.status != MaintenanceStatus.COMPLETED,
            MaintenanceRequest.deadline < datetime.utcnow(),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        overdue_count = self.session.execute(overdue_query).scalar_one()
        
        if overdue_count > 0:
            bottlenecks.append({
                "type": "overdue_requests",
                "count": overdue_count,
                "severity": "critical",
                "description": f"{overdue_count} requests past deadline"
            })
        
        # Check for long-pending approvals
        approval_query = select(
            func.count(MaintenanceRequest.id).label("count")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.approval_pending == True,
            MaintenanceRequest.created_at < datetime.utcnow() - timedelta(days=3),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        approval_count = self.session.execute(approval_query).scalar_one()
        
        if approval_count > 0:
            bottlenecks.append({
                "type": "pending_approvals",
                "count": approval_count,
                "severity": "medium",
                "description": f"{approval_count} requests awaiting approval >3 days"
            })
        
        return bottlenecks
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _generate_request_number(self, hostel_id: UUID) -> str:
        """
        Generate unique request number.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Unique request number
        """
        # Get current year and month
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        
        # Count requests this month
        count_query = select(
            func.count(MaintenanceRequest.id)
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            func.extract('year', MaintenanceRequest.created_at) == now.year,
            func.extract('month', MaintenanceRequest.created_at) == now.month
        )
        
        count = self.session.execute(count_query).scalar_one() + 1
        
        # Format: MNT-YYYY-MM-0001
        return f"MNT-{year}-{month}-{count:04d}"
    
    def _check_approval_requirement(
        self,
        estimated_cost: Optional[Decimal],
        hostel_id: UUID
    ) -> bool:
        """
        Check if approval is required based on cost.
        
        Args:
            estimated_cost: Estimated cost
            hostel_id: Hostel identifier
            
        Returns:
            True if approval required
        """
        if not estimated_cost:
            return False
        
        # This would typically check against hostel-specific thresholds
        # For now, use a simple threshold
        APPROVAL_THRESHOLD = Decimal("5000.00")
        
        return estimated_cost > APPROVAL_THRESHOLD
    
    def _is_valid_status_transition(
        self,
        old_status: MaintenanceStatus,
        new_status: MaintenanceStatus
    ) -> bool:
        """
        Validate status transition.
        
        Args:
            old_status: Current status
            new_status: Desired new status
            
        Returns:
            True if transition is valid
        """
        valid_transitions = {
            MaintenanceStatus.PENDING: [
                MaintenanceStatus.ASSIGNED,
                MaintenanceStatus.APPROVED,
                MaintenanceStatus.REJECTED,
                MaintenanceStatus.CANCELLED
            ],
            MaintenanceStatus.APPROVED: [
                MaintenanceStatus.ASSIGNED,
                MaintenanceStatus.CANCELLED
            ],
            MaintenanceStatus.ASSIGNED: [
                MaintenanceStatus.IN_PROGRESS,
                MaintenanceStatus.ON_HOLD,
                MaintenanceStatus.CANCELLED
            ],
            MaintenanceStatus.IN_PROGRESS: [
                MaintenanceStatus.COMPLETED,
                MaintenanceStatus.ON_HOLD,
                MaintenanceStatus.CANCELLED
            ],
            MaintenanceStatus.ON_HOLD: [
                MaintenanceStatus.IN_PROGRESS,
                MaintenanceStatus.CANCELLED
            ],
            MaintenanceStatus.COMPLETED: [],
            MaintenanceStatus.CANCELLED: [],
            MaintenanceStatus.REJECTED: []
        }
        
        return new_status in valid_transitions.get(old_status, [])
    
    def _create_status_history(
        self,
        request_id: UUID,
        old_status: Optional[MaintenanceStatus],
        new_status: MaintenanceStatus,
        changed_by: UUID,
        notes: Optional[str] = None
    ) -> None:
        """
        Create status history entry.
        
        Args:
            request_id: Request identifier
            old_status: Previous status
            new_status: New status
            changed_by: User making change
            notes: Optional notes
        """
        history = MaintenanceStatusHistory(
            maintenance_request_id=request_id,
            old_status=old_status or MaintenanceStatus.PENDING,
            new_status=new_status,
            changed_by=changed_by,
            notes=notes,
            automated=False
        )
        
        self.session.add(history)