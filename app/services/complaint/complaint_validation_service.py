"""
Complaint data validation and business rules service.

Provides centralized validation logic, business rules enforcement,
and data integrity checks for complaint management.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.base.enums import ComplaintCategory, ComplaintStatus, Priority
from app.models.complaint.complaint import Complaint
from app.repositories.complaint.complaint_repository import ComplaintRepository
from app.core.exceptions import ValidationError, BusinessLogicError


class ComplaintValidationService:
    """
    Complaint validation service.
    
    Centralizes validation logic and business rules enforcement
    for complaint management operations.
    """

    def __init__(self, session: Session):
        """
        Initialize validation service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.complaint_repo = ComplaintRepository(session)

    # ==================== Input Validation ====================

    def validate_complaint_creation(
        self,
        title: str,
        description: str,
        category: ComplaintCategory,
        priority: Priority,
        hostel_id: str,
        raised_by: str,
        student_id: Optional[str] = None,
        room_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate complaint creation data.
        
        Args:
            title: Complaint title
            description: Complaint description
            category: Complaint category
            priority: Priority level
            hostel_id: Hostel identifier
            raised_by: User raising complaint
            student_id: Optional student ID
            room_id: Optional room ID
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Title validation
        if not title or not title.strip():
            return False, "Title is required"
        
        if len(title) < 5:
            return False, "Title must be at least 5 characters"
        
        if len(title) > 255:
            return False, "Title must not exceed 255 characters"
        
        # Description validation
        if not description or not description.strip():
            return False, "Description is required"
        
        if len(description) < 10:
            return False, "Description must be at least 10 characters"
        
        if len(description) > 5000:
            return False, "Description must not exceed 5000 characters"
        
        # Check for spam/duplicate
        if self._is_duplicate_complaint(title, description, raised_by, hostel_id):
            return False, "A similar complaint was recently submitted"
        
        return True, None

    def validate_assignment(
        self,
        complaint_id: str,
        assigned_to: str,
        assigned_by: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate complaint assignment.
        
        Args:
            complaint_id: Complaint identifier
            assigned_to: User to assign to
            assigned_by: User performing assignment
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            return False, "Complaint not found"
        
        # Check if complaint can be assigned
        if complaint.status == ComplaintStatus.CLOSED:
            return False, "Cannot assign closed complaint"
        
        if complaint.status == ComplaintStatus.CANCELLED:
            return False, "Cannot assign cancelled complaint"
        
        # Check if assigning to same person
        if complaint.assigned_to == assigned_to:
            return False, "Complaint already assigned to this user"
        
        # Check workload (would check user capacity)
        # Placeholder for workload check
        
        return True, None

    def validate_resolution(
        self,
        complaint_id: str,
        resolved_by: str,
        resolution_notes: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate complaint resolution.
        
        Args:
            complaint_id: Complaint identifier
            resolved_by: User resolving complaint
            resolution_notes: Resolution description
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            return False, "Complaint not found"
        
        # Check status
        if complaint.status == ComplaintStatus.CLOSED:
            return False, "Complaint already closed"
        
        if complaint.status == ComplaintStatus.CANCELLED:
            return False, "Cannot resolve cancelled complaint"
        
        # Check if user is assigned
        if complaint.assigned_to != resolved_by:
            return False, "Only assigned user can resolve complaint"
        
        # Validate resolution notes
        if not resolution_notes or not resolution_notes.strip():
            return False, "Resolution notes are required"
        
        if len(resolution_notes) < 10:
            return False, "Resolution notes must be at least 10 characters"
        
        return True, None

    def validate_feedback(
        self,
        complaint_id: str,
        submitted_by: str,
        rating: int,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate feedback submission.
        
        Args:
            complaint_id: Complaint identifier
            submitted_by: User submitting feedback
            rating: Overall rating
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            return False, "Complaint not found"
        
        # Check if complaint is resolved
        if complaint.status not in [ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED]:
            return False, "Feedback can only be submitted for resolved complaints"
        
        # Check if user raised the complaint
        if complaint.raised_by != submitted_by:
            return False, "Only complaint raiser can submit feedback"
        
        # Validate rating
        if not (1 <= rating <= 5):
            return False, "Rating must be between 1 and 5"
        
        # Check if feedback already exists
        from app.services.complaint import ComplaintFeedbackService
        feedback_service = ComplaintFeedbackService(self.session)
        
        if feedback_service.has_feedback(complaint_id):
            return False, "Feedback already submitted for this complaint"
        
        return True, None

    # ==================== Business Rules ====================

    def check_priority_escalation_rules(
        self,
        complaint: Complaint,
        new_priority: Priority,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if priority escalation follows business rules.
        
        Args:
            complaint: Complaint instance
            new_priority: New priority level
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Can only escalate priority, not decrease
        priority_order = [
            Priority.LOW,
            Priority.MEDIUM,
            Priority.HIGH,
            Priority.URGENT,
            Priority.CRITICAL,
        ]
        
        current_index = priority_order.index(complaint.priority)
        new_index = priority_order.index(new_priority)
        
        if new_index < current_index:
            return False, "Cannot decrease complaint priority"
        
        # Check if escalation is justified
        if new_index - current_index > 2:
            return False, "Priority can only be increased by 2 levels at a time"
        
        return True, None

    def check_sla_compliance(
        self,
        complaint: Complaint,
    ) -> Dict[str, Any]:
        """
        Check SLA compliance for complaint.
        
        Args:
            complaint: Complaint instance
            
        Returns:
            SLA compliance status
        """
        from app.services.complaint import ComplaintSLAService
        sla_service = ComplaintSLAService(self.session)
        
        return sla_service.get_sla_status(complaint)

    def validate_status_transition(
        self,
        complaint: Complaint,
        new_status: ComplaintStatus,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate status transition.
        
        Args:
            complaint: Complaint instance
            new_status: Target status
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Define valid transitions
        valid_transitions = {
            ComplaintStatus.OPEN: [
                ComplaintStatus.ASSIGNED,
                ComplaintStatus.IN_PROGRESS,
                ComplaintStatus.CANCELLED,
            ],
            ComplaintStatus.ASSIGNED: [
                ComplaintStatus.IN_PROGRESS,
                ComplaintStatus.OPEN,
                ComplaintStatus.CANCELLED,
            ],
            ComplaintStatus.IN_PROGRESS: [
                ComplaintStatus.RESOLVED,
                ComplaintStatus.ASSIGNED,
                ComplaintStatus.ESCALATED,
            ],
            ComplaintStatus.ESCALATED: [
                ComplaintStatus.ASSIGNED,
                ComplaintStatus.IN_PROGRESS,
                ComplaintStatus.RESOLVED,
            ],
            ComplaintStatus.RESOLVED: [
                ComplaintStatus.CLOSED,
                ComplaintStatus.REOPENED,
            ],
            ComplaintStatus.REOPENED: [
                ComplaintStatus.ASSIGNED,
                ComplaintStatus.IN_PROGRESS,
            ],
            ComplaintStatus.CLOSED: [],
            ComplaintStatus.CANCELLED: [],
        }
        
        allowed = valid_transitions.get(complaint.status, [])
        
        if new_status not in allowed:
            return False, f"Invalid status transition from {complaint.status.value} to {new_status.value}"
        
        return True, None

    # ==================== Data Integrity ====================

    def _is_duplicate_complaint(
        self,
        title: str,
        description: str,
        raised_by: str,
        hostel_id: str,
        hours_threshold: int = 24,
    ) -> bool:
        """
        Check for duplicate complaints.
        
        Args:
            title: Complaint title
            description: Complaint description
            raised_by: User ID
            hostel_id: Hostel ID
            hours_threshold: Time window in hours
            
        Returns:
            True if duplicate found
        """
        from datetime import timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)
        
        # Search for similar complaints
        recent_complaints, _ = self.complaint_repo.search_complaints(
            hostel_id=hostel_id,
            raised_by=raised_by,
            date_from=cutoff,
            limit=100,
        )
        
        # Simple similarity check (would use better algorithm in production)
        for complaint in recent_complaints:
            # Check title similarity
            if self._calculate_similarity(title, complaint.title) > 0.8:
                return True
            
            # Check description similarity
            if self._calculate_similarity(description, complaint.description) > 0.8:
                return True
        
        return False

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity (placeholder).
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0-1)
        """
        # Placeholder - would use proper text similarity algorithm
        # (e.g., Levenshtein distance, cosine similarity)
        
        text1_lower = text1.lower()
        text2_lower = text2.lower()
        
        if text1_lower == text2_lower:
            return 1.0
        
        # Simple word overlap
        words1 = set(text1_lower.split())
        words2 = set(text2_lower.split())
        
        if not words1 or not words2:
            return 0.0
        
        overlap = len(words1.intersection(words2))
        total = len(words1.union(words2))
        
        return overlap / total if total > 0 else 0.0

    def validate_batch_operation(
        self,
        complaint_ids: List[str],
        operation: str,
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate batch operation on complaints.
        
        Args:
            complaint_ids: List of complaint IDs
            operation: Operation name (assign, close, etc.)
            
        Returns:
            Tuple of (is_valid, valid_ids, invalid_ids)
        """
        valid_ids = []
        invalid_ids = []
        
        for complaint_id in complaint_ids:
            complaint = self.complaint_repo.find_by_id(complaint_id)
            
            if not complaint:
                invalid_ids.append(complaint_id)
                continue
            
            # Operation-specific validation
            if operation == "close":
                if complaint.status != ComplaintStatus.RESOLVED:
                    invalid_ids.append(complaint_id)
                    continue
            
            elif operation == "assign":
                if complaint.status in [ComplaintStatus.CLOSED, ComplaintStatus.CANCELLED]:
                    invalid_ids.append(complaint_id)
                    continue
            
            valid_ids.append(complaint_id)
        
        return len(valid_ids) > 0, valid_ids, invalid_ids