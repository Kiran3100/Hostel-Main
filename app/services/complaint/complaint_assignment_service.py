"""
Complaint assignment service with intelligent workload management.

Handles complaint assignment, reassignment, workload balancing,
and auto-assignment with optimization algorithms.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.complaint.complaint import Complaint
from app.models.complaint.complaint_assignment import ComplaintAssignment
from app.repositories.complaint.complaint_repository import ComplaintRepository
from app.repositories.complaint.complaint_assignment_repository import (
    ComplaintAssignmentRepository,
)
from app.core.exceptions import (
    BusinessLogicError,
    NotFoundError,
    ValidationError,
)


class ComplaintAssignmentService:
    """
    Complaint assignment service with intelligent workload management.
    
    Provides assignment optimization, workload balancing, and
    performance tracking for complaint resolution staff.
    """

    def __init__(self, session: Session):
        """
        Initialize assignment service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.complaint_repo = ComplaintRepository(session)
        self.assignment_repo = ComplaintAssignmentRepository(session)

    # ==================== Assignment Creation ====================

    def create_assignment(
        self,
        complaint_id: str,
        assigned_to: str,
        assigned_by: str,
        assignment_type: str = "MANUAL",
        assignment_reason: Optional[str] = None,
        assignment_notes: Optional[str] = None,
        estimated_resolution_hours: int = 4,
    ) -> ComplaintAssignment:
        """
        Create a new complaint assignment.
        
        Args:
            complaint_id: Complaint identifier
            assigned_to: User to assign to
            assigned_by: User performing assignment
            assignment_type: INITIAL, REASSIGNMENT, ESCALATION
            assignment_reason: Reason for assignment
            assignment_notes: Additional notes
            estimated_resolution_hours: Estimated hours to resolve
            
        Returns:
            Created assignment instance
            
        Raises:
            NotFoundError: If complaint not found
            ValidationError: If assignment data invalid
        """
        # Verify complaint exists
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        # Validate assignment type
        valid_types = ["INITIAL", "REASSIGNMENT", "ESCALATION"]
        if assignment_type not in valid_types:
            raise ValidationError(f"Invalid assignment type: {assignment_type}")
        
        # Calculate workload score
        workload_score = self.assignment_repo.calculate_workload_score(
            complaint_priority=complaint.priority.value,
            complaint_category=complaint.category.value,
            estimated_hours=estimated_resolution_hours,
        )
        
        # Calculate estimated resolution time
        estimated_resolution_time = datetime.now(timezone.utc)
        from datetime import timedelta
        estimated_resolution_time += timedelta(hours=estimated_resolution_hours)
        
        # Create assignment
        assignment = self.assignment_repo.create_assignment(
            complaint_id=complaint_id,
            assigned_to=assigned_to,
            assigned_by=assigned_by,
            assignment_type=assignment_type,
            assignment_reason=assignment_reason,
            assignment_notes=assignment_notes,
            estimated_resolution_time=estimated_resolution_time,
            workload_score=workload_score,
        )
        
        self.session.commit()
        self.session.refresh(assignment)
        
        return assignment

    def auto_assign_complaint(
        self,
        complaint_id: str,
        assigned_by: str,
        candidate_user_ids: Optional[List[str]] = None,
    ) -> ComplaintAssignment:
        """
        Auto-assign complaint using workload optimization.
        
        Args:
            complaint_id: Complaint identifier
            assigned_by: User initiating auto-assignment
            candidate_user_ids: Optional list of candidates
            
        Returns:
            Created assignment
            
        Raises:
            NotFoundError: If complaint not found
            BusinessLogicError: If no suitable assignee found
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        # If no candidates provided, would need to fetch from user service
        # For now, require candidates to be provided
        if not candidate_user_ids:
            raise BusinessLogicError("No candidate assignees available")
        
        # Find optimal assignee
        optimal_assignee = self.assignment_repo.suggest_optimal_assignee(
            complaint_id=complaint_id,
            candidate_user_ids=candidate_user_ids,
            hostel_id=complaint.hostel_id,
        )
        
        if not optimal_assignee:
            # Fallback to least loaded
            optimal_assignee = self.assignment_repo.find_least_loaded_user(
                user_ids=candidate_user_ids,
                hostel_id=complaint.hostel_id,
            )
        
        if not optimal_assignee:
            raise BusinessLogicError("Could not determine optimal assignee")
        
        # Create assignment
        assignment = self.create_assignment(
            complaint_id=complaint_id,
            assigned_to=optimal_assignee,
            assigned_by=assigned_by,
            assignment_type="INITIAL",
            assignment_reason="Auto-assigned based on workload optimization",
        )
        
        # Update complaint
        self.complaint_repo.assign_complaint(
            complaint_id=complaint_id,
            assigned_to=optimal_assignee,
            assigned_by=assigned_by,
            notes="Auto-assigned",
        )
        
        self.session.commit()
        
        return assignment

    def reassign_complaint(
        self,
        complaint_id: str,
        new_assignee: str,
        reassigned_by: str,
        reassignment_reason: str,
    ) -> ComplaintAssignment:
        """
        Reassign complaint to different user.
        
        Args:
            complaint_id: Complaint identifier
            new_assignee: New user to assign to
            reassigned_by: User performing reassignment
            reassignment_reason: Reason for reassignment
            
        Returns:
            New assignment instance
            
        Raises:
            NotFoundError: If complaint not found
            ValidationError: If reassignment data invalid
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        if not reassignment_reason or not reassignment_reason.strip():
            raise ValidationError("Reassignment reason is required")
        
        # Complete current assignment if exists
        current_assignment = self.assignment_repo.find_current_assignment(complaint_id)
        if current_assignment:
            self.assignment_repo.complete_assignment(current_assignment.id)
        
        # Create new assignment
        new_assignment = self.create_assignment(
            complaint_id=complaint_id,
            assigned_to=new_assignee,
            assigned_by=reassigned_by,
            assignment_type="REASSIGNMENT",
            assignment_reason=reassignment_reason,
        )
        
        # Update complaint
        self.complaint_repo.assign_complaint(
            complaint_id=complaint_id,
            assigned_to=new_assignee,
            assigned_by=reassigned_by,
            notes=reassignment_reason,
        )
        
        self.session.commit()
        
        return new_assignment

    # ==================== Query Operations ====================

    def get_assignment(
        self,
        assignment_id: str,
    ) -> Optional[ComplaintAssignment]:
        """
        Get assignment by ID.
        
        Args:
            assignment_id: Assignment identifier
            
        Returns:
            Assignment instance or None
        """
        return self.assignment_repo.find_by_id(assignment_id)

    def get_complaint_assignments(
        self,
        complaint_id: str,
        include_inactive: bool = True,
    ) -> List[ComplaintAssignment]:
        """
        Get all assignments for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            include_inactive: Include completed assignments
            
        Returns:
            List of assignments
        """
        return self.assignment_repo.find_by_complaint(
            complaint_id=complaint_id,
            include_inactive=include_inactive,
        )

    def get_current_assignment(
        self,
        complaint_id: str,
    ) -> Optional[ComplaintAssignment]:
        """
        Get current active assignment for complaint.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            Current assignment or None
        """
        return self.assignment_repo.find_current_assignment(complaint_id)

    def get_user_assignments(
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
        Get assignments for a user.
        
        Args:
            user_id: User identifier
            current_only: Only active assignments
            assignment_type: Filter by type
            date_from: Start date filter
            date_to: End date filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of assignments
        """
        return self.assignment_repo.find_by_assignee(
            user_id=user_id,
            current_only=current_only,
            assignment_type=assignment_type,
            date_from=date_from,
            date_to=date_to,
            skip=skip,
            limit=limit,
        )

    # ==================== Workload Management ====================

    def get_user_workload(
        self,
        user_id: str,
        hostel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get current workload for a user.
        
        Args:
            user_id: User identifier
            hostel_id: Optional hostel filter
            
        Returns:
            Workload metrics dictionary
        """
        return self.assignment_repo.get_user_workload(
            user_id=user_id,
            hostel_id=hostel_id,
        )

    def get_team_workload(
        self,
        user_ids: List[str],
        hostel_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get workload distribution for a team.
        
        Args:
            user_ids: List of user identifiers
            hostel_id: Optional hostel filter
            
        Returns:
            List of workload metrics per user
        """
        return self.assignment_repo.get_team_workload_distribution(
            user_ids=user_ids,
            hostel_id=hostel_id,
        )

    def balance_workload(
        self,
        user_ids: List[str],
        hostel_id: Optional[str] = None,
        threshold_percentage: float = 30.0,
        auto_apply: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Identify workload imbalances and suggest reassignments.
        
        Args:
            user_ids: List of team member IDs
            hostel_id: Optional hostel filter
            threshold_percentage: Imbalance threshold
            auto_apply: Automatically apply suggestions
            
        Returns:
            List of reassignment suggestions
        """
        suggestions = self.assignment_repo.balance_workload(
            user_ids=user_ids,
            hostel_id=hostel_id,
            threshold_percentage=threshold_percentage,
        )
        
        if auto_apply and suggestions:
            # Would implement auto-reassignment logic here
            # For now, just return suggestions
            pass
        
        return suggestions

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
            Performance metrics dictionary
        """
        return self.assignment_repo.get_assignment_performance(
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
        )

    def get_assignment_history_stats(
        self,
        complaint_id: str,
    ) -> Dict[str, Any]:
        """
        Get assignment history statistics for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            Assignment history statistics
        """
        return self.assignment_repo.get_assignment_history_stats(complaint_id)

    # ==================== Completion ====================

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
        updated = self.assignment_repo.complete_assignment(assignment_id)
        
        if updated:
            self.session.commit()
            self.session.refresh(updated)
        
        return updated

    def complete_current_assignment(
        self,
        complaint_id: str,
    ) -> Optional[ComplaintAssignment]:
        """
        Complete current active assignment for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            Completed assignment or None
        """
        current = self.assignment_repo.find_current_assignment(complaint_id)
        
        if current:
            return self.complete_assignment(current.id)
        
        return None