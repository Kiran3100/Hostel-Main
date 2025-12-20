"""
Core complaint management service with lifecycle orchestration.

Handles complaint creation, updates, status transitions, and comprehensive
business logic for the complaint management workflow.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.base.enums import ComplaintCategory, ComplaintStatus, Priority
from app.models.complaint.complaint import Complaint
from app.repositories.complaint.complaint_repository import ComplaintRepository
from app.repositories.complaint.complaint_assignment_repository import (
    ComplaintAssignmentRepository,
)
from app.services.complaint.complaint_sla_service import ComplaintSLAService
from app.core.exceptions import (
    BusinessLogicError,
    NotFoundError,
    ValidationError,
)


class ComplaintService:
    """
    Core complaint management service.
    
    Orchestrates complaint lifecycle, validates business rules,
    and coordinates with other services for comprehensive management.
    """

    def __init__(self, session: Session):
        """
        Initialize complaint service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.complaint_repo = ComplaintRepository(session)
        self.assignment_repo = ComplaintAssignmentRepository(session)
        self.sla_service = ComplaintSLAService(session)

    # ==================== Creation ====================

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
        auto_assign: bool = True,
    ) -> Complaint:
        """
        Create a new complaint with validation and auto-assignment.
        
        Args:
            hostel_id: Hostel identifier
            raised_by: User raising the complaint
            title: Complaint title
            description: Detailed description
            category: Complaint category
            priority: Priority level
            student_id: Optional student identifier
            room_id: Optional room identifier
            location_details: Detailed location
            attachments: Attachment URLs
            metadata: Additional metadata
            auto_assign: Auto-assign to available staff
            
        Returns:
            Created complaint instance
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate inputs
        self._validate_complaint_data(
            title=title,
            description=description,
            hostel_id=hostel_id,
        )
        
        # Auto-adjust priority based on category if needed
        adjusted_priority = self._adjust_priority_by_category(category, priority)
        
        # Create complaint
        complaint = self.complaint_repo.create_complaint(
            hostel_id=hostel_id,
            raised_by=raised_by,
            title=title,
            description=description,
            category=category,
            priority=adjusted_priority,
            student_id=student_id,
            room_id=room_id,
            location_details=location_details,
            attachments=attachments,
            metadata=metadata,
        )
        
        # Auto-assign if requested
        if auto_assign:
            try:
                from app.services.complaint.complaint_assignment_service import (
                    ComplaintAssignmentService,
                )
                assignment_service = ComplaintAssignmentService(self.session)
                assignment_service.auto_assign_complaint(complaint.id, raised_by)
            except Exception as e:
                # Log but don't fail complaint creation
                print(f"Auto-assignment failed: {str(e)}")
        
        self.session.commit()
        self.session.refresh(complaint)
        
        return complaint

    def update_complaint(
        self,
        complaint_id: str,
        user_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[ComplaintCategory] = None,
        priority: Optional[Priority] = None,
        location_details: Optional[str] = None,
        attachments: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Complaint:
        """
        Update complaint details.
        
        Args:
            complaint_id: Complaint identifier
            user_id: User performing update
            title: Updated title
            description: Updated description
            category: Updated category
            priority: Updated priority
            location_details: Updated location
            attachments: Updated attachments
            metadata: Updated metadata
            
        Returns:
            Updated complaint instance
            
        Raises:
            NotFoundError: If complaint not found
            ValidationError: If update validation fails
            BusinessLogicError: If update not allowed
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        # Check if user can update
        self._check_update_permission(complaint, user_id)
        
        # Prepare update data
        update_data = {}
        
        if title is not None:
            if not title.strip():
                raise ValidationError("Title cannot be empty")
            update_data["title"] = title
        
        if description is not None:
            if not description.strip():
                raise ValidationError("Description cannot be empty")
            update_data["description"] = description
        
        if category is not None:
            update_data["category"] = category
        
        if priority is not None:
            update_data["priority"] = priority
            # Recalculate SLA if priority changes
            if complaint.priority != priority:
                self.sla_service.recalculate_sla(complaint_id, priority)
        
        if location_details is not None:
            update_data["location_details"] = location_details
        
        if attachments is not None:
            update_data["attachments"] = attachments
        
        if metadata is not None:
            current_metadata = complaint.metadata or {}
            current_metadata.update(metadata)
            update_data["metadata"] = current_metadata
        
        # Update complaint
        updated_complaint = self.complaint_repo.update(complaint_id, update_data)
        
        self.session.commit()
        self.session.refresh(updated_complaint)
        
        return updated_complaint

    # ==================== Status Management ====================

    def assign_complaint(
        self,
        complaint_id: str,
        assigned_to: str,
        assigned_by: str,
        notes: Optional[str] = None,
    ) -> Complaint:
        """
        Assign complaint to a user.
        
        Args:
            complaint_id: Complaint identifier
            assigned_to: User to assign to
            assigned_by: User performing assignment
            notes: Assignment notes
            
        Returns:
            Updated complaint
            
        Raises:
            NotFoundError: If complaint not found
            BusinessLogicError: If assignment not allowed
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        # Check if complaint can be assigned
        if complaint.status == ComplaintStatus.CLOSED:
            raise BusinessLogicError("Cannot assign closed complaint")
        
        # Check workload before assignment
        workload = self.assignment_repo.get_user_workload(assigned_to)
        if workload["total_assignments"] > 20:  # Configurable threshold
            print(f"Warning: User {assigned_to} has high workload ({workload['total_assignments']} assignments)")
        
        # Perform assignment
        updated_complaint = self.complaint_repo.assign_complaint(
            complaint_id=complaint_id,
            assigned_to=assigned_to,
            assigned_by=assigned_by,
            notes=notes,
        )
        
        # Create assignment record
        from app.services.complaint.complaint_assignment_service import (
            ComplaintAssignmentService,
        )
        assignment_service = ComplaintAssignmentService(self.session)
        assignment_service.create_assignment(
            complaint_id=complaint_id,
            assigned_to=assigned_to,
            assigned_by=assigned_by,
            assignment_type="MANUAL",
            assignment_reason=notes,
        )
        
        self.session.commit()
        self.session.refresh(updated_complaint)
        
        return updated_complaint

    def start_progress(
        self,
        complaint_id: str,
        user_id: str,
    ) -> Complaint:
        """
        Mark complaint as in progress.
        
        Args:
            complaint_id: Complaint identifier
            user_id: User starting work
            
        Returns:
            Updated complaint
            
        Raises:
            NotFoundError: If complaint not found
            BusinessLogicError: If status change not allowed
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        # Verify user is assigned
        if complaint.assigned_to != user_id:
            raise BusinessLogicError("Only assigned user can start progress")
        
        # Check current status
        if complaint.status not in [ComplaintStatus.OPEN, ComplaintStatus.ASSIGNED, ComplaintStatus.REOPENED]:
            raise BusinessLogicError(f"Cannot start progress from status: {complaint.status.value}")
        
        updated_complaint = self.complaint_repo.mark_in_progress(complaint_id, user_id)
        
        self.session.commit()
        self.session.refresh(updated_complaint)
        
        return updated_complaint

    def resolve_complaint(
        self,
        complaint_id: str,
        resolved_by: str,
        resolution_notes: str,
        resolution_attachments: Optional[List[str]] = None,
        actions_taken: Optional[List[str]] = None,
        materials_used: Optional[str] = None,
        follow_up_required: bool = False,
    ) -> Complaint:
        """
        Mark complaint as resolved.
        
        Args:
            complaint_id: Complaint identifier
            resolved_by: User resolving complaint
            resolution_notes: Resolution description
            resolution_attachments: Proof attachments
            actions_taken: Actions performed
            materials_used: Materials used
            follow_up_required: Follow-up flag
            
        Returns:
            Updated complaint
            
        Raises:
            NotFoundError: If complaint not found
            ValidationError: If resolution data invalid
            BusinessLogicError: If resolution not allowed
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        # Verify user is assigned
        if complaint.assigned_to != resolved_by:
            raise BusinessLogicError("Only assigned user can resolve complaint")
        
        # Validate resolution notes
        if not resolution_notes or not resolution_notes.strip():
            raise ValidationError("Resolution notes are required")
        
        # Mark as resolved
        updated_complaint = self.complaint_repo.mark_resolved(
            complaint_id=complaint_id,
            resolved_by=resolved_by,
            resolution_notes=resolution_notes,
            resolution_attachments=resolution_attachments,
        )
        
        # Create resolution record
        from app.services.complaint.complaint_resolution_service import (
            ComplaintResolutionService,
        )
        resolution_service = ComplaintResolutionService(self.session)
        resolution_service.create_resolution(
            complaint_id=complaint_id,
            resolved_by=resolved_by,
            resolution_notes=resolution_notes,
            resolution_attachments=resolution_attachments,
            actions_taken=actions_taken,
            materials_used=materials_used,
            follow_up_required=follow_up_required,
        )
        
        self.session.commit()
        self.session.refresh(updated_complaint)
        
        return updated_complaint

    def reopen_complaint(
        self,
        complaint_id: str,
        reopened_by: str,
        reopen_reason: str,
    ) -> Complaint:
        """
        Reopen a resolved complaint.
        
        Args:
            complaint_id: Complaint identifier
            reopened_by: User reopening complaint
            reopen_reason: Reason for reopening
            
        Returns:
            Updated complaint
            
        Raises:
            NotFoundError: If complaint not found
            ValidationError: If reason not provided
            BusinessLogicError: If reopen not allowed
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        # Check if complaint can be reopened
        if complaint.status not in [ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED]:
            raise BusinessLogicError("Only resolved or closed complaints can be reopened")
        
        if not reopen_reason or not reopen_reason.strip():
            raise ValidationError("Reopen reason is required")
        
        # Reopen complaint
        updated_complaint = self.complaint_repo.reopen_complaint(
            complaint_id=complaint_id,
            reopened_by=reopened_by,
            reopen_reason=reopen_reason,
        )
        
        # Mark resolution as reopened
        from app.services.complaint.complaint_resolution_service import (
            ComplaintResolutionService,
        )
        resolution_service = ComplaintResolutionService(self.session)
        resolution_service.mark_reopened(complaint_id, reopen_reason)
        
        # Recalculate SLA
        self.sla_service.recalculate_sla(complaint_id, complaint.priority)
        
        self.session.commit()
        self.session.refresh(updated_complaint)
        
        return updated_complaint

    def close_complaint(
        self,
        complaint_id: str,
        closed_by: str,
        verify_feedback: bool = True,
    ) -> Complaint:
        """
        Close a resolved complaint.
        
        Args:
            complaint_id: Complaint identifier
            closed_by: User closing complaint
            verify_feedback: Require feedback before closing
            
        Returns:
            Updated complaint
            
        Raises:
            NotFoundError: If complaint not found
            BusinessLogicError: If closure not allowed
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        # Check if complaint can be closed
        if complaint.status != ComplaintStatus.RESOLVED:
            raise BusinessLogicError("Only resolved complaints can be closed")
        
        # Optionally verify feedback exists
        if verify_feedback:
            from app.services.complaint.complaint_feedback_service import (
                ComplaintFeedbackService,
            )
            feedback_service = ComplaintFeedbackService(self.session)
            if not feedback_service.has_feedback(complaint_id):
                raise BusinessLogicError("Feedback required before closing complaint")
        
        # Close complaint
        updated_complaint = self.complaint_repo.close_complaint(
            complaint_id=complaint_id,
            closed_by=closed_by,
        )
        
        self.session.commit()
        self.session.refresh(updated_complaint)
        
        return updated_complaint

    # ==================== Escalation ====================

    def escalate_complaint(
        self,
        complaint_id: str,
        escalated_by: str,
        escalation_reason: str,
        escalated_to: Optional[str] = None,
        is_urgent: bool = False,
    ) -> Complaint:
        """
        Escalate a complaint.
        
        Args:
            complaint_id: Complaint identifier
            escalated_by: User escalating
            escalation_reason: Escalation reason
            escalated_to: Target user (auto-determined if None)
            is_urgent: Urgent escalation flag
            
        Returns:
            Updated complaint
            
        Raises:
            NotFoundError: If complaint not found
            ValidationError: If escalation data invalid
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        if not escalation_reason or not escalation_reason.strip():
            raise ValidationError("Escalation reason is required")
        
        # Determine escalation target if not provided
        if not escalated_to:
            from app.services.complaint.complaint_escalation_service import (
                ComplaintEscalationService,
            )
            escalation_service = ComplaintEscalationService(self.session)
            escalated_to = escalation_service.determine_escalation_target(
                complaint_id=complaint_id,
                hostel_id=complaint.hostel_id,
            )
        
        if not escalated_to:
            raise BusinessLogicError("No escalation target available")
        
        # Increase priority if urgent
        new_priority = complaint.priority
        if is_urgent and complaint.priority != Priority.CRITICAL:
            if complaint.priority == Priority.HIGH:
                new_priority = Priority.CRITICAL
            elif complaint.priority == Priority.MEDIUM:
                new_priority = Priority.HIGH
            elif complaint.priority == Priority.LOW:
                new_priority = Priority.MEDIUM
        
        # Escalate complaint
        updated_complaint = self.complaint_repo.escalate_complaint(
            complaint_id=complaint_id,
            escalated_to=escalated_to,
            escalated_by=escalated_by,
            escalation_reason=escalation_reason,
            new_priority=new_priority if new_priority != complaint.priority else None,
        )
        
        # Create escalation record
        from app.services.complaint.complaint_escalation_service import (
            ComplaintEscalationService,
        )
        escalation_service = ComplaintEscalationService(self.session)
        escalation_service.create_escalation(
            complaint_id=complaint_id,
            escalated_to=escalated_to,
            escalated_by=escalated_by,
            escalation_reason=escalation_reason,
            is_urgent=is_urgent,
        )
        
        self.session.commit()
        self.session.refresh(updated_complaint)
        
        return updated_complaint

    # ==================== Queries ====================

    def get_complaint(
        self,
        complaint_id: str,
        include_relations: bool = True,
    ) -> Optional[Complaint]:
        """
        Get complaint by ID with optional relations.
        
        Args:
            complaint_id: Complaint identifier
            include_relations: Load related entities
            
        Returns:
            Complaint instance or None
        """
        if include_relations:
            from app.repositories.complaint.complaint_aggregate_repository import (
                ComplaintAggregateRepository,
            )
            aggregate_repo = ComplaintAggregateRepository(self.session)
            details = aggregate_repo.get_complaint_details_with_relations(complaint_id)
            return details.get("complaint") if details else None
        
        return self.complaint_repo.find_by_id(complaint_id)

    def get_complaint_by_number(
        self,
        complaint_number: str,
    ) -> Optional[Complaint]:
        """
        Get complaint by unique complaint number.
        
        Args:
            complaint_number: Unique complaint reference
            
        Returns:
            Complaint instance or None
        """
        return self.complaint_repo.find_by_complaint_number(complaint_number)

    def list_hostel_complaints(
        self,
        hostel_id: str,
        status: Optional[ComplaintStatus] = None,
        category: Optional[ComplaintCategory] = None,
        priority: Optional[Priority] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Complaint]:
        """
        List complaints for a hostel with filters.
        
        Args:
            hostel_id: Hostel identifier
            status: Filter by status
            category: Filter by category
            priority: Filter by priority
            date_from: Start date filter
            date_to: End date filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of complaints
        """
        return self.complaint_repo.find_by_hostel(
            hostel_id=hostel_id,
            status=status,
            category=category,
            priority=priority,
            date_from=date_from,
            date_to=date_to,
            skip=skip,
            limit=limit,
        )

    def list_user_complaints(
        self,
        user_id: str,
        student_id: Optional[str] = None,
        status: Optional[ComplaintStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Complaint]:
        """
        List complaints for a user.
        
        Args:
            user_id: User identifier
            student_id: Optional student filter
            status: Optional status filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of complaints
        """
        if student_id:
            return self.complaint_repo.find_by_student(
                student_id=student_id,
                status=status,
                skip=skip,
                limit=limit,
            )
        
        return self.complaint_repo.find_assigned_to_user(
            user_id=user_id,
            status=status,
            skip=skip,
            limit=limit,
        )

    def search_complaints(
        self,
        search_term: Optional[str] = None,
        hostel_id: Optional[str] = None,
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
        Advanced complaint search.
        
        Args:
            search_term: Search in title/description
            hostel_id: Filter by hostel
            status: Filter by status list
            category: Filter by category list
            priority: Filter by priority list
            date_from: Start date filter
            date_to: End date filter
            assigned_to: Filter by assignee
            raised_by: Filter by raiser
            student_id: Filter by student
            room_id: Filter by room
            escalated_only: Show only escalated
            sla_breach_only: Show only SLA breached
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            Tuple of (complaints list, total count)
        """
        return self.complaint_repo.search_complaints(
            hostel_id=hostel_id,
            search_term=search_term,
            status=status,
            category=category,
            priority=priority,
            date_from=date_from,
            date_to=date_to,
            assigned_to=assigned_to,
            raised_by=raised_by,
            student_id=student_id,
            room_id=room_id,
            escalated_only=escalated_only,
            sla_breach_only=sla_breach_only,
            skip=skip,
            limit=limit,
        )

    def get_overdue_complaints(
        self,
        hostel_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Complaint]:
        """
        Get overdue complaints.
        
        Args:
            hostel_id: Optional hostel filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of overdue complaints
        """
        return self.complaint_repo.find_overdue_complaints(
            hostel_id=hostel_id,
            skip=skip,
            limit=limit,
        )

    def get_escalated_complaints(
        self,
        hostel_id: Optional[str] = None,
        escalated_to: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Complaint]:
        """
        Get escalated complaints.
        
        Args:
            hostel_id: Optional hostel filter
            escalated_to: Optional user filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of escalated complaints
        """
        return self.complaint_repo.find_escalated_complaints(
            hostel_id=hostel_id,
            escalated_to=escalated_to,
            skip=skip,
            limit=limit,
        )

    # ==================== Analytics ====================

    def get_complaint_statistics(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get complaint statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Dictionary with statistics
        """
        return self.complaint_repo.get_complaint_statistics(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )

    def get_dashboard_summary(
        self,
        hostel_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get dashboard summary.
        
        Args:
            hostel_id: Optional hostel filter
            user_id: Optional user filter
            
        Returns:
            Dashboard metrics
        """
        from app.repositories.complaint.complaint_aggregate_repository import (
            ComplaintAggregateRepository,
        )
        aggregate_repo = ComplaintAggregateRepository(self.session)
        return aggregate_repo.get_dashboard_summary(
            hostel_id=hostel_id,
            user_id=user_id,
        )

    # ==================== Bulk Operations ====================

    def bulk_assign_complaints(
        self,
        complaint_ids: List[str],
        assigned_to: str,
        assigned_by: str,
    ) -> int:
        """
        Bulk assign multiple complaints.
        
        Args:
            complaint_ids: List of complaint IDs
            assigned_to: User to assign to
            assigned_by: User performing assignment
            
        Returns:
            Number of complaints assigned
        """
        count = self.complaint_repo.bulk_assign(
            complaint_ids=complaint_ids,
            assigned_to=assigned_to,
            assigned_by=assigned_by,
        )
        
        self.session.commit()
        return count

    def bulk_update_priority(
        self,
        complaint_ids: List[str],
        priority: Priority,
    ) -> int:
        """
        Bulk update priority.
        
        Args:
            complaint_ids: List of complaint IDs
            priority: New priority level
            
        Returns:
            Number of complaints updated
        """
        count = self.complaint_repo.bulk_update_priority(
            complaint_ids=complaint_ids,
            priority=priority,
        )
        
        # Recalculate SLA for all updated complaints
        for complaint_id in complaint_ids:
            try:
                self.sla_service.recalculate_sla(complaint_id, priority)
            except Exception as e:
                print(f"SLA recalculation failed for {complaint_id}: {str(e)}")
        
        self.session.commit()
        return count

    # ==================== Validation & Helpers ====================

    def _validate_complaint_data(
        self,
        title: str,
        description: str,
        hostel_id: str,
    ) -> None:
        """
        Validate complaint creation data.
        
        Args:
            title: Complaint title
            description: Complaint description
            hostel_id: Hostel identifier
            
        Raises:
            ValidationError: If validation fails
        """
        if not title or not title.strip():
            raise ValidationError("Title is required")
        
        if len(title) < 5:
            raise ValidationError("Title must be at least 5 characters")
        
        if len(title) > 255:
            raise ValidationError("Title must not exceed 255 characters")
        
        if not description or not description.strip():
            raise ValidationError("Description is required")
        
        if len(description) < 10:
            raise ValidationError("Description must be at least 10 characters")
        
        if not hostel_id:
            raise ValidationError("Hostel ID is required")

    def _adjust_priority_by_category(
        self,
        category: ComplaintCategory,
        priority: Priority,
    ) -> Priority:
        """
        Auto-adjust priority based on category.
        
        Args:
            category: Complaint category
            priority: Requested priority
            
        Returns:
            Adjusted priority
        """
        # Critical categories that should have higher priority
        critical_categories = [
            ComplaintCategory.SECURITY,
            ComplaintCategory.SAFETY,
        ]
        
        if category in critical_categories and priority == Priority.LOW:
            return Priority.MEDIUM
        
        return priority

    def _check_update_permission(
        self,
        complaint: Complaint,
        user_id: str,
    ) -> None:
        """
        Check if user can update complaint.
        
        Args:
            complaint: Complaint instance
            user_id: User attempting update
            
        Raises:
            BusinessLogicError: If update not allowed
        """
        # Allow updates if:
        # 1. User raised the complaint and it's still open
        # 2. User is assigned to the complaint
        # 3. User is admin/manager (would need role check)
        
        if complaint.raised_by == user_id and complaint.status == ComplaintStatus.OPEN:
            return
        
        if complaint.assigned_to == user_id:
            return
        
        # If complaint is closed, prevent updates
        if complaint.status == ComplaintStatus.CLOSED:
            raise BusinessLogicError("Cannot update closed complaint")
        
        raise BusinessLogicError("User not authorized to update this complaint")

    def delete_complaint(
        self,
        complaint_id: str,
        user_id: str,
        hard_delete: bool = False,
    ) -> bool:
        """
        Delete a complaint (soft or hard).
        
        Args:
            complaint_id: Complaint identifier
            user_id: User performing deletion
            hard_delete: Permanent deletion flag
            
        Returns:
            True if deleted
            
        Raises:
            NotFoundError: If complaint not found
            BusinessLogicError: If deletion not allowed
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        # Only allow deletion of OPEN complaints by the raiser or admin
        if complaint.status != ComplaintStatus.OPEN:
            raise BusinessLogicError("Only open complaints can be deleted")
        
        if complaint.raised_by != user_id:
            # Would need admin role check here
            raise BusinessLogicError("Only complaint raiser can delete")
        
        if hard_delete:
            self.complaint_repo.hard_delete(complaint_id)
        else:
            self.complaint_repo.soft_delete(complaint_id)
        
        self.session.commit()
        return True