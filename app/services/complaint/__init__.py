# app/services/complaint/__init__.py
"""
Complaint-related services.

- ComplaintService: core CRUD, listing, status updates, summaries.
- ComplaintAssignmentService: assign/reassign/unassign complaints.
- ComplaintEscalationService: escalation metadata & rules (store-agnostic).
- ComplaintFeedbackService: feedback capture & basic analytics (store-agnostic).
- ComplaintWorkflowService: wrapper over wf_complaint.
- ComplaintAnalyticsService: basic hostel-level complaint analytics.
"""

from .complaint_service import ComplaintService
from .complaint_assignment_service import ComplaintAssignmentService
from .complaint_escalation_service import ComplaintEscalationService
from .complaint_feedback_service import ComplaintFeedbackService
from .complaint_workflow_service import ComplaintWorkflowService
from .complaint_analytics_service import ComplaintAnalyticsService

__all__ = [
    "ComplaintService",
    "ComplaintAssignmentService",
    "ComplaintEscalationService",
    "ComplaintFeedbackService",
    "ComplaintWorkflowService",
    "ComplaintAnalyticsService",
]