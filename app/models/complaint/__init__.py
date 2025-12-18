"""
Complaint models package.

Comprehensive complaint management models including core complaint tracking,
assignments, escalation, resolution, feedback, comments, and analytics.

Models:
    - Complaint: Core complaint entity with lifecycle management
    - ComplaintAssignment: Assignment history and tracking
    - ComplaintComment: Comments and internal notes
    - ComplaintEscalation: Escalation tracking and auto-escalation rules
    - ComplaintFeedback: Student feedback and satisfaction
    - ComplaintResolution: Resolution tracking and documentation
    - ComplaintAnalyticSnapshot: Pre-computed analytics
    - ComplaintCategoryMetric: Category-wise performance metrics
    - ComplaintStaffPerformance: Staff performance tracking

Example:
    from app.models.complaint import Complaint, ComplaintAssignment
    
    # Create new complaint
    complaint = Complaint(
        hostel_id=hostel.id,
        raised_by=user.id,
        title="Water leakage in bathroom",
        description="Severe water leakage...",
        category=ComplaintCategory.MAINTENANCE,
        priority=Priority.HIGH
    )
    
    # Assign complaint
    assignment = ComplaintAssignment(
        complaint_id=complaint.id,
        assigned_to=staff.id,
        assigned_by=admin.id
    )
"""

from app.models.complaint.complaint import Complaint
from app.models.complaint.complaint_analytics import (
    ComplaintAnalyticSnapshot,
    ComplaintCategoryMetric,
    ComplaintStaffPerformance,
)
from app.models.complaint.complaint_assignment import ComplaintAssignment
from app.models.complaint.complaint_comment import ComplaintComment
from app.models.complaint.complaint_escalation import (
    AutoEscalationRule,
    ComplaintEscalation,
)
from app.models.complaint.complaint_feedback import ComplaintFeedback
from app.models.complaint.complaint_resolution import ComplaintResolution

__all__ = [
    # Core models
    "Complaint",
    "ComplaintAssignment",
    "ComplaintComment",
    "ComplaintEscalation",
    "ComplaintFeedback",
    "ComplaintResolution",
    # Analytics models
    "ComplaintAnalyticSnapshot",
    "ComplaintCategoryMetric",
    "ComplaintStaffPerformance",
    # Rules and configuration
    "AutoEscalationRule",
]