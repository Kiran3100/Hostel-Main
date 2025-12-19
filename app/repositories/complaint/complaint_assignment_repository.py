# --- File: complaint_assignment_repository.py ---
"""
Complaint assignment repository with workload management and performance tracking.

Handles assignment history, workload balancing, and assignment optimization
for efficient complaint resolution.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.models.complaint.complaint_assignment import ComplaintAssignment
from app.models.complaint.complaint import Complaint
from app.repositories.base.base_repository import BaseRepository


class ComplaintAssignmentRepository(BaseRepository[ComplaintAssignment]):
    """
    Complaint assignment repository with advanced workload management.
    
    Provides assignment tracking, workload optimization, and performance
    analytics for complaint resolution staff.
    """

    def __init__(self, session: Session):
        """
        Initialize complaint assignment repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(ComplaintAssignment, session)

    # ==================== CRUD Operations ====================

    def create_assignment(
        self,
        complaint_id: str,
        assigned_to: str,
        assigned_by: str,
        assignment_type: str = "INITIAL",
        assignment_reason: Optional[str] = None,
        assignment_notes: Optional[str] = None,
        estimated_resolution_time: Optional[datetime] = None,
        workload_score: int = 0,
    ) -> ComplaintAssignment:
        """
        Create a new complaint assignment.
        
        Args:
            complaint_id: Complaint identifier
            assigned_to: User ID of assignee
            assigned_by: User ID performing assignment
            assignment_type: Type (INITIAL, REASSIGNMENT, ESCALATION)
            assignment_reason: Reason for assignment
            assignment_notes: Additional context
            estimated_resolution_time: Expected resolution time
            workload_score: Calculated workload score
            
        Returns:
            Created assignment instance
        """
        # Mark previous assignment as not current if exists
        self._deactivate_previous_assignments(complaint_id)
        
        assignment = ComplaintAssignment(
            complaint_id=complaint_id,
            assigned_to=assigned_to,
            assigned_by=assigned_by,
            assigned_at=datetime.now(timezone.utc),
            assignment_type=assignment_type,
            assignment_reason=assignment_reason,
            assignment_notes=assignment_notes,
            estimated_resolution_time=estimated_resolution_time,
            workload_score=workload_score,
            is_current=True,
        )
        
        return self.create(assignment)

    def complete_assignment(
        self,
        assignment_id: str,
    ) -> Optional[ComplaintAssignment]:
        """
        Mark assignment as completed.
        
        Args:
            assignment_id: Assignment identifier
            
        Returns:
            Updated assignment or None
        """
        assignment = self.find_by_id(assignment_id)
        if not assignment:
            return None
        
        now = datetime.now(timezone.utc)
        
        # Calculate duration
        duration_delta = now - assignment.assigned_at
        duration_hours = int(duration_delta.total_seconds() / 3600)
        
        update_data = {
            "is_current": False,
            "unassigned_at": now,
            "duration_hours": duration_hours,
        }
        
        return self.update(assignment_id, update_data)

    # ==================== Query Operations ====================

    def find_by_complaint(
        self,
        complaint_id: str,
        include_inactive: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintAssignment]:
        """
        Find all assignments for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            include_inactive: Include completed assignments
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of assignments
        """
        query = select(ComplaintAssignment).where(
            ComplaintAssignment.complaint_id == complaint_id
        )
        
        if not include_inactive:
            query = query.where(ComplaintAssignment.is_current == True)
        
        query = query.order_by(desc(ComplaintAssignment.assigned_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_current_assignment(
        self,
        complaint_id: str,
    ) -> Optional[ComplaintAssignment]:
        """
        Find current active assignment for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            Current assignment or None
        """
        query = select(ComplaintAssignment).where(
            and_(
                ComplaintAssignment.complaint_id == complaint_id,
                ComplaintAssignment.is_current == True,
            )
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def find_by_assignee(
        self,
        user_id: str,
        current_only: bool = True,
        assignment_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintAssignment]:
        """
        Find assignments for a specific user.
        
        Args:
            user_id: User identifier
            current_only: Only active assignments
            assignment_type: Filter by assignment type
            date_from: Start date filter
            date_to: End date filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of assignments
        """
        query = select(ComplaintAssignment).where(
            ComplaintAssignment.assigned_to == user_id
        )
        
        if current_only:
            query = query.where(ComplaintAssignment.is_current == True)
        
        if assignment_type:
            query = query.where(ComplaintAssignment.assignment_type == assignment_type)
        
        if date_from:
            query = query.where(ComplaintAssignment.assigned_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintAssignment.assigned_at <= date_to)
        
        query = query.order_by(desc(ComplaintAssignment.assigned_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_by_assigner(
        self,
        user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintAssignment]:
        """
        Find assignments created by a specific user.
        
        Args:
            user_id: User identifier
            date_from: Start date filter
            date_to: End date filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of assignments
        """
        query = select(ComplaintAssignment).where(
            ComplaintAssignment.assigned_by == user_id
        )
        
        if date_from:
            query = query.where(ComplaintAssignment.assigned_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintAssignment.assigned_at <= date_to)
        
        query = query.order_by(desc(ComplaintAssignment.assigned_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Workload Management ====================

    def get_user_workload(
        self,
        user_id: str,
        hostel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate current workload for a user.
        
        Args:
            user_id: User identifier
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary with workload metrics
        """
        # Get active assignments
        query = (
            select(ComplaintAssignment)
            .join(Complaint)
            .where(
                and_(
                    ComplaintAssignment.assigned_to == user_id,
                    ComplaintAssignment.is_current == True,
                    Complaint.status.notin_(['RESOLVED', 'CLOSED']),
                )
            )
        )
        
        if hostel_id:
            query = query.where(Complaint.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        active_assignments = list(result.scalars().all())
        
        # Calculate metrics
        total_assignments = len(active_assignments)
        total_workload_score = sum(a.workload_score for a in active_assignments)
        
        # Count by priority
        priority_query = (
            select(
                Complaint.priority,
                func.count(ComplaintAssignment.id).label("count"),
            )
            .join(Complaint)
            .where(
                and_(
                    ComplaintAssignment.assigned_to == user_id,
                    ComplaintAssignment.is_current == True,
                    Complaint.status.notin_(['RESOLVED', 'CLOSED']),
                )
            )
            .group_by(Complaint.priority)
        )
        
        if hostel_id:
            priority_query = priority_query.where(Complaint.hostel_id == hostel_id)
        
        priority_result = self.session.execute(priority_query)
        priority_breakdown = {
            row.priority.value: row.count for row in priority_result
        }
        
        # Get overdue count
        now = datetime.now(timezone.utc)
        overdue_query = (
            select(func.count())
            .select_from(ComplaintAssignment)
            .join(Complaint)
            .where(
                and_(
                    ComplaintAssignment.assigned_to == user_id,
                    ComplaintAssignment.is_current == True,
                    Complaint.status.notin_(['RESOLVED', 'CLOSED']),
                    Complaint.sla_due_at.isnot(None),
                    Complaint.sla_due_at < now,
                )
            )
        )
        
        if hostel_id:
            overdue_query = overdue_query.where(Complaint.hostel_id == hostel_id)
        
        overdue_count = self.session.execute(overdue_query).scalar_one()
        
        return {
            "user_id": user_id,
            "total_assignments": total_assignments,
            "total_workload_score": total_workload_score,
            "priority_breakdown": priority_breakdown,
            "overdue_count": overdue_count,
            "average_workload_score": (
                total_workload_score / total_assignments
                if total_assignments > 0 else 0
            ),
        }

    def get_team_workload_distribution(
        self,
        user_ids: List[str],
        hostel_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get workload distribution across a team.
        
        Args:
            user_ids: List of user identifiers
            hostel_id: Optional hostel filter
            
        Returns:
            List of workload metrics per user
        """
        workload_data = []
        
        for user_id in user_ids:
            workload = self.get_user_workload(user_id, hostel_id)
            workload_data.append(workload)
        
        # Sort by total assignments descending
        workload_data.sort(key=lambda x: x["total_assignments"], reverse=True)
        
        return workload_data

    def find_least_loaded_user(
        self,
        user_ids: List[str],
        hostel_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Find user with least workload for assignment.
        
        Args:
            user_ids: List of candidate user identifiers
            hostel_id: Optional hostel filter
            
        Returns:
            User ID with least workload or None
        """
        if not user_ids:
            return None
        
        workload_data = self.get_team_workload_distribution(user_ids, hostel_id)
        
        if not workload_data:
            return user_ids[0]
        
        # Find user with minimum workload score
        min_workload_user = min(
            workload_data,
            key=lambda x: x["total_workload_score"]
        )
        
        return min_workload_user["user_id"]

    def calculate_workload_score(
        self,
        complaint_priority: str,
        complaint_category: str,
        estimated_hours: int = 4,
    ) -> int:
        """
        Calculate workload score for a complaint.
        
        Args:
            complaint_priority: Priority level
            complaint_category: Complaint category
            estimated_hours: Estimated resolution hours
            
        Returns:
            Calculated workload score
        """
        # Base score from priority
        priority_scores = {
            "CRITICAL": 100,
            "URGENT": 75,
            "HIGH": 50,
            "MEDIUM": 25,
            "LOW": 10,
        }
        
        base_score = priority_scores.get(complaint_priority, 25)
        
        # Category complexity multiplier
        category_multipliers = {
            "MAINTENANCE": 1.2,
            "FACILITIES": 1.0,
            "CLEANLINESS": 0.8,
            "SECURITY": 1.3,
            "FOOD": 0.9,
            "INTERNET": 1.1,
            "OTHER": 1.0,
        }
        
        multiplier = category_multipliers.get(complaint_category, 1.0)
        
        # Time factor (longer estimated time = higher score)
        time_factor = min(estimated_hours / 4, 2.0)  # Cap at 2x
        
        return int(base_score * multiplier * time_factor)

    # ==================== Performance Analytics ====================

    def get_assignment_performance(
        self,
        user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get assignment performance metrics for a user.
        
        Args:
            user_id: User identifier
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Dictionary with performance metrics
        """
        query = select(ComplaintAssignment).where(
            ComplaintAssignment.assigned_to == user_id
        )
        
        if date_from:
            query = query.where(ComplaintAssignment.assigned_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintAssignment.assigned_at <= date_to)
        
        result = self.session.execute(query)
        assignments = list(result.scalars().all())
        
        if not assignments:
            return {
                "user_id": user_id,
                "total_assignments": 0,
                "completed_assignments": 0,
                "active_assignments": 0,
                "average_duration_hours": None,
                "reassignment_rate": 0,
            }
        
        total = len(assignments)
        completed = len([a for a in assignments if not a.is_current])
        active = len([a for a in assignments if a.is_current])
        
        # Calculate average duration for completed assignments
        completed_with_duration = [
            a for a in assignments
            if a.duration_hours is not None
        ]
        
        avg_duration = (
            sum(a.duration_hours for a in completed_with_duration) / len(completed_with_duration)
            if completed_with_duration else None
        )
        
        # Count reassignments
        reassignments = len([
            a for a in assignments
            if a.assignment_type == "REASSIGNMENT"
        ])
        
        return {
            "user_id": user_id,
            "total_assignments": total,
            "completed_assignments": completed,
            "active_assignments": active,
            "average_duration_hours": avg_duration,
            "reassignment_count": reassignments,
            "reassignment_rate": (reassignments / total * 100) if total > 0 else 0,
        }

    def get_assignment_history_stats(
        self,
        complaint_id: str,
    ) -> Dict[str, Any]:
        """
        Get assignment history statistics for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            Dictionary with assignment statistics
        """
        query = select(ComplaintAssignment).where(
            ComplaintAssignment.complaint_id == complaint_id
        )
        
        result = self.session.execute(query)
        assignments = list(result.scalars().all())
        
        if not assignments:
            return {
                "complaint_id": complaint_id,
                "total_assignments": 0,
                "reassignment_count": 0,
                "unique_assignees": 0,
                "total_assignment_time_hours": None,
            }
        
        total = len(assignments)
        reassignments = total - 1  # First is initial, rest are reassignments
        
        # Count unique assignees
        unique_assignees = len(set(a.assigned_to for a in assignments))
        
        # Calculate total assignment time
        completed_assignments = [
            a for a in assignments
            if a.duration_hours is not None
        ]
        
        total_time = (
            sum(a.duration_hours for a in completed_assignments)
            if completed_assignments else None
        )
        
        return {
            "complaint_id": complaint_id,
            "total_assignments": total,
            "reassignment_count": reassignments,
            "unique_assignees": unique_assignees,
            "total_assignment_time_hours": total_time,
            "average_assignment_duration_hours": (
                total_time / len(completed_assignments)
                if completed_assignments else None
            ),
        }

    # ==================== Assignment Optimization ====================

    def suggest_optimal_assignee(
        self,
        complaint_id: str,
        candidate_user_ids: List[str],
        hostel_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Suggest optimal assignee based on workload and performance.
        
        Args:
            complaint_id: Complaint being assigned
            candidate_user_ids: List of potential assignees
            hostel_id: Optional hostel context
            
        Returns:
            Recommended user ID or None
        """
        if not candidate_user_ids:
            return None
        
        # Get complaint details
        complaint_query = select(Complaint).where(Complaint.id == complaint_id)
        complaint_result = self.session.execute(complaint_query)
        complaint = complaint_result.scalar_one_or_none()
        
        if not complaint:
            return None
        
        # Calculate scores for each candidate
        candidate_scores = []
        
        for user_id in candidate_user_ids:
            workload = self.get_user_workload(user_id, hostel_id)
            performance = self.get_assignment_performance(user_id)
            
            # Calculate composite score (lower is better)
            # Factors: workload (50%), reassignment rate (30%), response time (20%)
            workload_score = workload["total_workload_score"]
            reassignment_penalty = performance["reassignment_rate"] * 10
            
            composite_score = (
                workload_score * 0.5 +
                reassignment_penalty * 0.3
            )
            
            candidate_scores.append({
                "user_id": user_id,
                "score": composite_score,
                "workload": workload_score,
                "reassignment_rate": performance["reassignment_rate"],
            })
        
        # Sort by score (ascending - lower is better)
        candidate_scores.sort(key=lambda x: x["score"])
        
        return candidate_scores[0]["user_id"] if candidate_scores else None

    def balance_workload(
        self,
        user_ids: List[str],
        hostel_id: Optional[str] = None,
        threshold_percentage: float = 30.0,
    ) -> List[Dict[str, Any]]:
        """
        Identify workload imbalances and suggest reassignments.
        
        Args:
            user_ids: List of team member IDs
            hostel_id: Optional hostel filter
            threshold_percentage: Imbalance threshold
            
        Returns:
            List of suggested reassignments
        """
        workload_data = self.get_team_workload_distribution(user_ids, hostel_id)
        
        if not workload_data:
            return []
        
        # Calculate average workload
        avg_workload = sum(w["total_workload_score"] for w in workload_data) / len(workload_data)
        
        # Identify overloaded and underloaded users
        overloaded = []
        underloaded = []
        
        for workload in workload_data:
            deviation = (workload["total_workload_score"] - avg_workload) / avg_workload * 100
            
            if deviation > threshold_percentage:
                overloaded.append(workload)
            elif deviation < -threshold_percentage:
                underloaded.append(workload)
        
        suggestions = []
        
        # Suggest reassignments from overloaded to underloaded
        for overload in overloaded:
            for underload in underloaded:
                suggestions.append({
                    "from_user": overload["user_id"],
                    "to_user": underload["user_id"],
                    "from_workload": overload["total_workload_score"],
                    "to_workload": underload["total_workload_score"],
                    "reason": "Workload balancing",
                })
        
        return suggestions

    # ==================== Helper Methods ====================

    def _deactivate_previous_assignments(self, complaint_id: str) -> None:
        """
        Mark all previous assignments for a complaint as inactive.
        
        Args:
            complaint_id: Complaint identifier
        """
        now = datetime.now(timezone.utc)
        
        # Get current active assignment
        current = self.find_current_assignment(complaint_id)
        
        if current:
            # Calculate duration
            duration_delta = now - current.assigned_at
            duration_hours = int(duration_delta.total_seconds() / 3600)
            
            # Update current assignment
            self.update(current.id, {
                "is_current": False,
                "unassigned_at": now,
                "duration_hours": duration_hours,
            })


