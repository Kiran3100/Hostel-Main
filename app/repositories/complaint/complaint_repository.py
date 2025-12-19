# --- File: complaint_repository.py ---
"""
Core complaint repository with advanced querying, lifecycle management, and analytics.

Handles all complaint-related data operations including creation, updates, 
status transitions, assignments, and complex search queries.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, desc, func, or_, select, text
from sqlalchemy.orm import joinedload, selectinload, Session

from app.models.complaint.complaint import Complaint
from app.models.base.enums import ComplaintCategory, ComplaintStatus, Priority
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.specifications import Specification


class ComplaintRepository(BaseRepository[Complaint]):
    """
    Core complaint repository with comprehensive data access operations.
    
    Provides advanced querying, filtering, aggregation, and lifecycle
    management for complaints with performance optimization.
    """

    def __init__(self, session: Session):
        """
        Initialize complaint repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(Complaint, session)

    # ==================== CRUD Operations ====================

    def create_complaint(
        self,
        hostel_id: str,
        raised_by: str,
        title: str,
        description: str,
        category: ComplaintCategory,
        priority: Priority = Priority.MEDIUM,
        student_id: Optional[str] = None,
        room_id: Optional[str] = None,
        location_details: Optional[str] = None,
        attachments: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Complaint:
        """
        Create a new complaint with auto-generated complaint number.
        
        Args:
            hostel_id: Associated hostel identifier
            raised_by: User ID who raised the complaint
            title: Brief complaint summary
            description: Detailed complaint description
            category: Complaint category
            priority: Priority level
            student_id: Optional student identifier
            room_id: Optional room identifier
            location_details: Detailed location information
            attachments: List of attachment URLs
            metadata: Additional metadata
            
        Returns:
            Created complaint instance
        """
        # Generate unique complaint number
        complaint_number = self._generate_complaint_number(hostel_id)
        
        # Calculate SLA due date based on priority
        sla_due_at = self._calculate_sla_due_date(priority)
        
        complaint = Complaint(
            complaint_number=complaint_number,
            hostel_id=hostel_id,
            raised_by=raised_by,
            student_id=student_id,
            title=title,
            description=description,
            category=category,
            priority=priority,
            room_id=room_id,
            location_details=location_details,
            attachments=attachments or [],
            status=ComplaintStatus.OPEN,
            sla_due_at=sla_due_at,
            opened_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        
        return self.create(complaint)

    def update_complaint(
        self,
        complaint_id: str,
        **update_data: Any,
    ) -> Optional[Complaint]:
        """
        Update complaint with validation and audit tracking.
        
        Args:
            complaint_id: Complaint identifier
            **update_data: Fields to update
            
        Returns:
            Updated complaint or None if not found
        """
        complaint = self.find_by_id(complaint_id)
        if not complaint:
            return None
        
        # Track specific updates
        if "status" in update_data:
            self._handle_status_change(complaint, update_data["status"])
        
        if "priority" in update_data:
            self._handle_priority_change(complaint, update_data["priority"])
        
        return self.update(complaint_id, update_data)

    # ==================== Query Operations ====================

    def find_by_complaint_number(
        self,
        complaint_number: str,
        include_deleted: bool = False,
    ) -> Optional[Complaint]:
        """
        Find complaint by unique complaint number.
        
        Args:
            complaint_number: Unique complaint reference number
            include_deleted: Include soft-deleted records
            
        Returns:
            Complaint instance or None
        """
        query = select(Complaint).where(
            Complaint.complaint_number == complaint_number
        )
        
        if not include_deleted:
            query = query.where(Complaint.deleted_at.is_(None))
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def find_by_hostel(
        self,
        hostel_id: str,
        status: Optional[ComplaintStatus] = None,
        category: Optional[ComplaintCategory] = None,
        priority: Optional[Priority] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        include_deleted: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Complaint]:
        """
        Find complaints by hostel with optional filters.
        
        Args:
            hostel_id: Hostel identifier
            status: Filter by status
            category: Filter by category
            priority: Filter by priority
            date_from: Start date filter
            date_to: End date filter
            include_deleted: Include soft-deleted records
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of matching complaints
        """
        query = select(Complaint).where(Complaint.hostel_id == hostel_id)
        
        if not include_deleted:
            query = query.where(Complaint.deleted_at.is_(None))
        
        if status:
            query = query.where(Complaint.status == status)
        
        if category:
            query = query.where(Complaint.category == category)
        
        if priority:
            query = query.where(Complaint.priority == priority)
        
        if date_from:
            query = query.where(Complaint.opened_at >= date_from)
        
        if date_to:
            query = query.where(Complaint.opened_at <= date_to)
        
        query = query.order_by(desc(Complaint.opened_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_by_student(
        self,
        student_id: str,
        status: Optional[ComplaintStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Complaint]:
        """
        Find all complaints raised by a student.
        
        Args:
            student_id: Student identifier
            status: Optional status filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of student's complaints
        """
        query = select(Complaint).where(
            and_(
                Complaint.student_id == student_id,
                Complaint.deleted_at.is_(None),
            )
        )
        
        if status:
            query = query.where(Complaint.status == status)
        
        query = query.order_by(desc(Complaint.opened_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_assigned_to_user(
        self,
        user_id: str,
        status: Optional[ComplaintStatus] = None,
        priority: Optional[Priority] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Complaint]:
        """
        Find complaints assigned to a specific user.
        
        Args:
            user_id: User identifier
            status: Optional status filter
            priority: Optional priority filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of assigned complaints
        """
        query = select(Complaint).where(
            and_(
                Complaint.assigned_to == user_id,
                Complaint.deleted_at.is_(None),
            )
        )
        
        if status:
            query = query.where(Complaint.status == status)
        
        if priority:
            query = query.where(Complaint.priority == priority)
        
        query = query.order_by(
            desc(Complaint.priority),
            Complaint.sla_due_at.asc(),
        )
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_overdue_complaints(
        self,
        hostel_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Complaint]:
        """
        Find complaints that are overdue based on SLA.
        
        Args:
            hostel_id: Optional hostel filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of overdue complaints
        """
        now = datetime.now(timezone.utc)
        
        query = select(Complaint).where(
            and_(
                Complaint.deleted_at.is_(None),
                Complaint.status.in_([
                    ComplaintStatus.OPEN,
                    ComplaintStatus.ASSIGNED,
                    ComplaintStatus.IN_PROGRESS,
                    ComplaintStatus.REOPENED,
                ]),
                Complaint.sla_due_at.isnot(None),
                Complaint.sla_due_at < now,
            )
        )
        
        if hostel_id:
            query = query.where(Complaint.hostel_id == hostel_id)
        
        query = query.order_by(Complaint.sla_due_at.asc())
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_escalated_complaints(
        self,
        hostel_id: Optional[str] = None,
        escalated_to: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Complaint]:
        """
        Find escalated complaints.
        
        Args:
            hostel_id: Optional hostel filter
            escalated_to: Optional user filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of escalated complaints
        """
        query = select(Complaint).where(
            and_(
                Complaint.deleted_at.is_(None),
                Complaint.escalated == True,
                Complaint.status.in_([
                    ComplaintStatus.OPEN,
                    ComplaintStatus.ASSIGNED,
                    ComplaintStatus.IN_PROGRESS,
                    ComplaintStatus.REOPENED,
                ]),
            )
        )
        
        if hostel_id:
            query = query.where(Complaint.hostel_id == hostel_id)
        
        if escalated_to:
            query = query.where(Complaint.escalated_to == escalated_to)
        
        query = query.order_by(desc(Complaint.escalated_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_by_room(
        self,
        room_id: str,
        status: Optional[ComplaintStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Complaint]:
        """
        Find complaints related to a specific room.
        
        Args:
            room_id: Room identifier
            status: Optional status filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of room-related complaints
        """
        query = select(Complaint).where(
            and_(
                Complaint.room_id == room_id,
                Complaint.deleted_at.is_(None),
            )
        )
        
        if status:
            query = query.where(Complaint.status == status)
        
        query = query.order_by(desc(Complaint.opened_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def search_complaints(
        self,
        hostel_id: Optional[str] = None,
        search_term: Optional[str] = None,
        status: Optional[List[ComplaintStatus]] = None,
        category: Optional[List[ComplaintCategory]] = None,
        priority: Optional[List[Priority]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        assigned_to: Optional[str] = None,
        raised_by: Optional[str] = None,
        student_id: Optional[str] = None,
        room_id: Optional[str] = None,
        escalated_only: bool = False,
        sla_breach_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[Complaint], int]:
        """
        Advanced complaint search with multiple filters.
        
        Args:
            hostel_id: Filter by hostel
            search_term: Search in title and description
            status: Filter by status list
            category: Filter by category list
            priority: Filter by priority list
            date_from: Start date filter
            date_to: End date filter
            assigned_to: Filter by assignee
            raised_by: Filter by raiser
            student_id: Filter by student
            room_id: Filter by room
            escalated_only: Show only escalated complaints
            sla_breach_only: Show only SLA breached complaints
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            Tuple of (complaints list, total count)
        """
        # Build base query
        query = select(Complaint).where(Complaint.deleted_at.is_(None))
        
        # Apply filters
        if hostel_id:
            query = query.where(Complaint.hostel_id == hostel_id)
        
        if search_term:
            search_pattern = f"%{search_term}%"
            query = query.where(
                or_(
                    Complaint.title.ilike(search_pattern),
                    Complaint.description.ilike(search_pattern),
                    Complaint.complaint_number.ilike(search_pattern),
                )
            )
        
        if status:
            query = query.where(Complaint.status.in_(status))
        
        if category:
            query = query.where(Complaint.category.in_(category))
        
        if priority:
            query = query.where(Complaint.priority.in_(priority))
        
        if date_from:
            query = query.where(Complaint.opened_at >= date_from)
        
        if date_to:
            query = query.where(Complaint.opened_at <= date_to)
        
        if assigned_to:
            query = query.where(Complaint.assigned_to == assigned_to)
        
        if raised_by:
            query = query.where(Complaint.raised_by == raised_by)
        
        if student_id:
            query = query.where(Complaint.student_id == student_id)
        
        if room_id:
            query = query.where(Complaint.room_id == room_id)
        
        if escalated_only:
            query = query.where(Complaint.escalated == True)
        
        if sla_breach_only:
            query = query.where(Complaint.sla_breach == True)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_count = self.session.execute(count_query).scalar_one()
        
        # Apply ordering and pagination
        query = query.order_by(
            desc(Complaint.priority),
            Complaint.sla_due_at.asc(),
            desc(Complaint.opened_at),
        )
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        complaints = list(result.scalars().all())
        
        return complaints, total_count

    # ==================== Status Management ====================

    def assign_complaint(
        self,
        complaint_id: str,
        assigned_to: str,
        assigned_by: str,
        notes: Optional[str] = None,
    ) -> Optional[Complaint]:
        """
        Assign complaint to a user.
        
        Args:
            complaint_id: Complaint identifier
            assigned_to: User ID to assign to
            assigned_by: User ID performing assignment
            notes: Optional assignment notes
            
        Returns:
            Updated complaint or None
        """
        complaint = self.find_by_id(complaint_id)
        if not complaint:
            return None
        
        # Update assignment count if reassigning
        if complaint.assigned_to and complaint.assigned_to != assigned_to:
            complaint.reassigned_count += 1
        
        update_data = {
            "assigned_to": assigned_to,
            "assigned_by": assigned_by,
            "assigned_at": datetime.now(timezone.utc),
            "status": ComplaintStatus.ASSIGNED,
            "reassigned_count": complaint.reassigned_count,
        }
        
        return self.update(complaint_id, update_data)

    def mark_in_progress(
        self,
        complaint_id: str,
        user_id: str,
    ) -> Optional[Complaint]:
        """
        Mark complaint as in progress.
        
        Args:
            complaint_id: Complaint identifier
            user_id: User marking as in progress
            
        Returns:
            Updated complaint or None
        """
        complaint = self.find_by_id(complaint_id)
        if not complaint:
            return None
        
        update_data = {
            "status": ComplaintStatus.IN_PROGRESS,
            "in_progress_at": datetime.now(timezone.utc),
        }
        
        return self.update(complaint_id, update_data)

    def mark_resolved(
        self,
        complaint_id: str,
        resolved_by: str,
        resolution_notes: str,
        resolution_attachments: Optional[List[str]] = None,
    ) -> Optional[Complaint]:
        """
        Mark complaint as resolved.
        
        Args:
            complaint_id: Complaint identifier
            resolved_by: User resolving the complaint
            resolution_notes: Resolution description
            resolution_attachments: Optional proof attachments
            
        Returns:
            Updated complaint or None
        """
        complaint = self.find_by_id(complaint_id)
        if not complaint:
            return None
        
        now = datetime.now(timezone.utc)
        
        update_data = {
            "status": ComplaintStatus.RESOLVED,
            "resolved_at": now,
            "resolution_notes": resolution_notes,
            "resolution_attachments": resolution_attachments or [],
            "actual_resolution_time": now,
        }
        
        return self.update(complaint_id, update_data)

    def reopen_complaint(
        self,
        complaint_id: str,
        reopened_by: str,
        reopen_reason: str,
    ) -> Optional[Complaint]:
        """
        Reopen a resolved complaint.
        
        Args:
            complaint_id: Complaint identifier
            reopened_by: User reopening the complaint
            reopen_reason: Reason for reopening
            
        Returns:
            Updated complaint or None
        """
        complaint = self.find_by_id(complaint_id)
        if not complaint:
            return None
        
        update_data = {
            "status": ComplaintStatus.REOPENED,
            "reopened_count": complaint.reopened_count + 1,
            "resolved_at": None,
            "resolution_notes": None,
        }
        
        return self.update(complaint_id, update_data)

    def close_complaint(
        self,
        complaint_id: str,
        closed_by: str,
    ) -> Optional[Complaint]:
        """
        Close a resolved complaint.
        
        Args:
            complaint_id: Complaint identifier
            closed_by: User closing the complaint
            
        Returns:
            Updated complaint or None
        """
        complaint = self.find_by_id(complaint_id)
        if not complaint:
            return None
        
        if complaint.status != ComplaintStatus.RESOLVED:
            return None
        
        update_data = {
            "status": ComplaintStatus.CLOSED,
            "closed_at": datetime.now(timezone.utc),
            "closed_by": closed_by,
        }
        
        return self.update(complaint_id, update_data)

    # ==================== Escalation Management ====================

    def escalate_complaint(
        self,
        complaint_id: str,
        escalated_to: str,
        escalated_by: str,
        escalation_reason: str,
        new_priority: Optional[Priority] = None,
    ) -> Optional[Complaint]:
        """
        Escalate a complaint.
        
        Args:
            complaint_id: Complaint identifier
            escalated_to: User to escalate to
            escalated_by: User performing escalation
            escalation_reason: Reason for escalation
            new_priority: Optional new priority level
            
        Returns:
            Updated complaint or None
        """
        complaint = self.find_by_id(complaint_id)
        if not complaint:
            return None
        
        update_data = {
            "escalated": True,
            "escalated_to": escalated_to,
            "escalated_at": datetime.now(timezone.utc),
            "escalation_reason": escalation_reason,
        }
        
        if new_priority:
            update_data["priority"] = new_priority
        
        return self.update(complaint_id, update_data)

    # ==================== SLA Management ====================

    def mark_sla_breach(
        self,
        complaint_id: str,
        breach_reason: str,
    ) -> Optional[Complaint]:
        """
        Mark complaint as SLA breached.
        
        Args:
            complaint_id: Complaint identifier
            breach_reason: Reason for SLA breach
            
        Returns:
            Updated complaint or None
        """
        update_data = {
            "sla_breach": True,
            "sla_breach_reason": breach_reason,
        }
        
        return self.update(complaint_id, update_data)

    def find_sla_at_risk(
        self,
        hostel_id: Optional[str] = None,
        hours_threshold: int = 2,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Complaint]:
        """
        Find complaints at risk of SLA breach.
        
        Args:
            hostel_id: Optional hostel filter
            hours_threshold: Hours before SLA breach
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of at-risk complaints
        """
        threshold_time = datetime.now(timezone.utc) + timedelta(hours=hours_threshold)
        
        query = select(Complaint).where(
            and_(
                Complaint.deleted_at.is_(None),
                Complaint.sla_breach == False,
                Complaint.status.in_([
                    ComplaintStatus.OPEN,
                    ComplaintStatus.ASSIGNED,
                    ComplaintStatus.IN_PROGRESS,
                    ComplaintStatus.REOPENED,
                ]),
                Complaint.sla_due_at.isnot(None),
                Complaint.sla_due_at <= threshold_time,
            )
        )
        
        if hostel_id:
            query = query.where(Complaint.hostel_id == hostel_id)
        
        query = query.order_by(Complaint.sla_due_at.asc())
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Analytics & Reporting ====================

    def get_complaint_statistics(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive complaint statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Dictionary with complaint statistics
        """
        query = select(Complaint).where(Complaint.deleted_at.is_(None))
        
        if hostel_id:
            query = query.where(Complaint.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(Complaint.opened_at >= date_from)
        
        if date_to:
            query = query.where(Complaint.opened_at <= date_to)
        
        # Status breakdown
        status_query = (
            select(
                Complaint.status,
                func.count(Complaint.id).label("count"),
            )
            .where(Complaint.deleted_at.is_(None))
            .group_by(Complaint.status)
        )
        
        if hostel_id:
            status_query = status_query.where(Complaint.hostel_id == hostel_id)
        
        status_result = self.session.execute(status_query)
        status_breakdown = {
            row.status.value: row.count for row in status_result
        }
        
        # Category breakdown
        category_query = (
            select(
                Complaint.category,
                func.count(Complaint.id).label("count"),
            )
            .where(Complaint.deleted_at.is_(None))
            .group_by(Complaint.category)
        )
        
        if hostel_id:
            category_query = category_query.where(Complaint.hostel_id == hostel_id)
        
        category_result = self.session.execute(category_query)
        category_breakdown = {
            row.category.value: row.count for row in category_result
        }
        
        # Priority breakdown
        priority_query = (
            select(
                Complaint.priority,
                func.count(Complaint.id).label("count"),
            )
            .where(Complaint.deleted_at.is_(None))
            .group_by(Complaint.priority)
        )
        
        if hostel_id:
            priority_query = priority_query.where(Complaint.hostel_id == hostel_id)
        
        priority_result = self.session.execute(priority_query)
        priority_breakdown = {
            row.priority.value: row.count for row in priority_result
        }
        
        # Total count
        count_query = select(func.count()).select_from(query.subquery())
        total_count = self.session.execute(count_query).scalar_one()
        
        # SLA metrics
        sla_breach_query = query.where(Complaint.sla_breach == True)
        sla_breach_count_query = select(func.count()).select_from(sla_breach_query.subquery())
        sla_breach_count = self.session.execute(sla_breach_count_query).scalar_one()
        
        # Escalation metrics
        escalated_query = query.where(Complaint.escalated == True)
        escalated_count_query = select(func.count()).select_from(escalated_query.subquery())
        escalated_count = self.session.execute(escalated_count_query).scalar_one()
        
        return {
            "total_complaints": total_count,
            "status_breakdown": status_breakdown,
            "category_breakdown": category_breakdown,
            "priority_breakdown": priority_breakdown,
            "sla_breach_count": sla_breach_count,
            "sla_compliance_rate": (
                ((total_count - sla_breach_count) / total_count * 100)
                if total_count > 0 else 0
            ),
            "escalated_count": escalated_count,
            "escalation_rate": (
                (escalated_count / total_count * 100)
                if total_count > 0 else 0
            ),
        }

    def get_average_resolution_time(
        self,
        hostel_id: Optional[str] = None,
        category: Optional[ComplaintCategory] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Optional[float]:
        """
        Calculate average resolution time in hours.
        
        Args:
            hostel_id: Optional hostel filter
            category: Optional category filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Average resolution time in hours or None
        """
        query = select(
            func.avg(
                func.extract(
                    "epoch",
                    Complaint.resolved_at - Complaint.opened_at
                ) / 3600
            )
        ).where(
            and_(
                Complaint.deleted_at.is_(None),
                Complaint.resolved_at.isnot(None),
            )
        )
        
        if hostel_id:
            query = query.where(Complaint.hostel_id == hostel_id)
        
        if category:
            query = query.where(Complaint.category == category)
        
        if date_from:
            query = query.where(Complaint.resolved_at >= date_from)
        
        if date_to:
            query = query.where(Complaint.resolved_at <= date_to)
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def get_top_categories(
        self,
        hostel_id: Optional[str] = None,
        limit: int = 10,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get top complaint categories by count.
        
        Args:
            hostel_id: Optional hostel filter
            limit: Maximum categories to return
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            List of categories with counts
        """
        query = (
            select(
                Complaint.category,
                func.count(Complaint.id).label("count"),
            )
            .where(Complaint.deleted_at.is_(None))
            .group_by(Complaint.category)
            .order_by(desc("count"))
            .limit(limit)
        )
        
        if hostel_id:
            query = query.where(Complaint.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(Complaint.opened_at >= date_from)
        
        if date_to:
            query = query.where(Complaint.opened_at <= date_to)
        
        result = self.session.execute(query)
        return [
            {"category": row.category.value, "count": row.count}
            for row in result
        ]

    # ==================== Bulk Operations ====================

    def bulk_assign(
        self,
        complaint_ids: List[str],
        assigned_to: str,
        assigned_by: str,
    ) -> int:
        """
        Bulk assign multiple complaints.
        
        Args:
            complaint_ids: List of complaint identifiers
            assigned_to: User ID to assign to
            assigned_by: User ID performing assignment
            
        Returns:
            Number of complaints updated
        """
        now = datetime.now(timezone.utc)
        
        stmt = (
            self.model.__table__.update()
            .where(
                and_(
                    self.model.id.in_(complaint_ids),
                    self.model.deleted_at.is_(None),
                )
            )
            .values(
                assigned_to=assigned_to,
                assigned_by=assigned_by,
                assigned_at=now,
                status=ComplaintStatus.ASSIGNED,
                updated_at=now,
            )
        )
        
        result = self.session.execute(stmt)
        self.session.commit()
        
        return result.rowcount

    def bulk_update_priority(
        self,
        complaint_ids: List[str],
        priority: Priority,
    ) -> int:
        """
        Bulk update priority for multiple complaints.
        
        Args:
            complaint_ids: List of complaint identifiers
            priority: New priority level
            
        Returns:
            Number of complaints updated
        """
        now = datetime.now(timezone.utc)
        
        stmt = (
            self.model.__table__.update()
            .where(
                and_(
                    self.model.id.in_(complaint_ids),
                    self.model.deleted_at.is_(None),
                )
            )
            .values(
                priority=priority,
                updated_at=now,
            )
        )
        
        result = self.session.execute(stmt)
        self.session.commit()
        
        return result.rowcount

    # ==================== Helper Methods ====================

    def _generate_complaint_number(self, hostel_id: str) -> str:
        """
        Generate unique complaint number.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Unique complaint number (e.g., CMP-2024-001)
        """
        year = datetime.now().year
        
        # Get count of complaints this year for this hostel
        query = select(func.count()).where(
            and_(
                Complaint.hostel_id == hostel_id,
                func.extract("year", Complaint.created_at) == year,
            )
        )
        
        count = self.session.execute(query).scalar_one()
        sequence = count + 1
        
        return f"CMP-{year}-{sequence:05d}"

    def _calculate_sla_due_date(self, priority: Priority) -> datetime:
        """
        Calculate SLA due date based on priority.
        
        Args:
            priority: Complaint priority
            
        Returns:
            SLA due datetime
        """
        now = datetime.now(timezone.utc)
        
        # SLA hours based on priority
        sla_hours = {
            Priority.CRITICAL: 4,
            Priority.URGENT: 8,
            Priority.HIGH: 24,
            Priority.MEDIUM: 48,
            Priority.LOW: 72,
        }
        
        hours = sla_hours.get(priority, 48)
        return now + timedelta(hours=hours)

    def _handle_status_change(
        self,
        complaint: Complaint,
        new_status: ComplaintStatus,
    ) -> None:
        """
        Handle status-specific updates.
        
        Args:
            complaint: Complaint instance
            new_status: New status
        """
        now = datetime.now(timezone.utc)
        
        if new_status == ComplaintStatus.IN_PROGRESS and not complaint.in_progress_at:
            complaint.in_progress_at = now
        
        elif new_status == ComplaintStatus.RESOLVED and not complaint.resolved_at:
            complaint.resolved_at = now
        
        elif new_status == ComplaintStatus.CLOSED and not complaint.closed_at:
            complaint.closed_at = now

    def _handle_priority_change(
        self,
        complaint: Complaint,
        new_priority: Priority,
    ) -> None:
        """
        Handle priority change and recalculate SLA.
        
        Args:
            complaint: Complaint instance
            new_priority: New priority level
        """
        if complaint.priority != new_priority:
            # Recalculate SLA due date if not breached
            if not complaint.sla_breach and complaint.status in [
                ComplaintStatus.OPEN,
                ComplaintStatus.ASSIGNED,
                ComplaintStatus.IN_PROGRESS,
            ]:
                complaint.sla_due_at = self._calculate_sla_due_date(new_priority)