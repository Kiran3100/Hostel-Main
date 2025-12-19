# --- File: __init__.py ---
"""
Complaint repositories package.

Provides comprehensive data access layer for complaint management
with advanced querying, analytics, and aggregation capabilities.

Repositories:
    - ComplaintRepository: Core complaint CRUD and queries
    - ComplaintAssignmentRepository: Assignment management
    - ComplaintCommentRepository: Comment and discussion management
    - ComplaintEscalationRepository: Escalation tracking
    - ComplaintFeedbackRepository: Feedback and satisfaction tracking
    - ComplaintResolutionRepository: Resolution management
    - ComplaintAnalyticSnapshotRepository: Pre-computed analytics
    - ComplaintCategoryMetricRepository: Category performance metrics
    - ComplaintStaffPerformanceRepository: Staff performance tracking
    - ComplaintAggregateRepository: Complex multi-entity queries

Example:
    from app.repositories.complaint import ComplaintRepository
    
    repo = ComplaintRepository(session)
    
    # Create complaint
    complaint = repo.create_complaint(
        hostel_id=hostel_id,
        raised_by=user_id,
        title="Water leakage",
        description="...",
        category=ComplaintCategory.MAINTENANCE,
        priority=Priority.HIGH,
    )
    
    # Search complaints
    complaints, total = repo.search_complaints(
        hostel_id=hostel_id,
        status=[ComplaintStatus.OPEN, ComplaintStatus.IN_PROGRESS],
        priority=[Priority.HIGH, Priority.CRITICAL],
        skip=0,
        limit=20,
    )
"""

from app.repositories.complaint.complaint_repository import ComplaintRepository
from app.repositories.complaint.complaint_assignment_repository import (
    ComplaintAssignmentRepository,
)
from app.repositories.complaint.complaint_comment_repository import (
    ComplaintCommentRepository,
)
from app.repositories.complaint.complaint_escalation_repository import (
    ComplaintEscalationRepository,
    AutoEscalationRuleRepository,
)
from app.repositories.complaint.complaint_feedback_repository import (
    ComplaintFeedbackRepository,
)
from app.repositories.complaint.complaint_resolution_repository import (
    ComplaintResolutionRepository,
)
from app.repositories.complaint.complaint_analytics_repository import (
    ComplaintAnalyticSnapshotRepository,
    ComplaintCategoryMetricRepository,
    ComplaintStaffPerformanceRepository,
)
from app.repositories.complaint.complaint_aggregate_repository import (
    ComplaintAggregateRepository,
)

__all__ = [
    # Core repositories
    "ComplaintRepository",
    "ComplaintAssignmentRepository",
    "ComplaintCommentRepository",
    "ComplaintEscalationRepository",
    "ComplaintFeedbackRepository",
    "ComplaintResolutionRepository",
    # Analytics repositories
    "ComplaintAnalyticSnapshotRepository",
    "ComplaintCategoryMetricRepository",
    "ComplaintStaffPerformanceRepository",
    # Specialized repositories
    "AutoEscalationRuleRepository",
    "ComplaintAggregateRepository",
]