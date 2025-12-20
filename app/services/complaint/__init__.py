"""
Complaint services package.

Provides comprehensive business logic layer for complaint management
with orchestration, validation, and workflow coordination.

Services:
    Core Services:
    - ComplaintService: Core complaint lifecycle management
    - ComplaintSLAService: SLA monitoring and breach detection
    - ComplaintAssignmentService: Assignment and workload management
    - ComplaintCommentService: Comment and discussion management
    - ComplaintEscalationService: Escalation workflow management
    - ComplaintFeedbackService: Feedback collection and analysis
    - ComplaintResolutionService: Resolution workflow and quality control
    - ComplaintAnalyticsService: Analytics and reporting
    
    Utility Services:
    - ComplaintNotificationService: Multi-channel notifications
    - ComplaintWorkflowService: Workflow orchestration and automation
    - ComplaintExportService: Data export and report generation
    - ComplaintSearchService: Advanced search and filtering
    - ComplaintValidationService: Validation and business rules

Example:
    from app.services.complaint import (
        ComplaintService,
        ComplaintWorkflowService,
        ComplaintSearchService,
    )
    
    # Core operations
    complaint_service = ComplaintService(session)
    complaint = complaint_service.create_complaint(...)
    
    # Advanced search
    search_service = ComplaintSearchService(session)
    results = search_service.advanced_search(
        query="water leakage",
        priority=[Priority.HIGH, Priority.CRITICAL],
    )
    
    # Workflow automation
    workflow_service = ComplaintWorkflowService(session)
    result = workflow_service.execute_workflow(
        complaint_id=complaint.id,
        workflow_name="quick_resolve",
        user_id=staff_id,
    )
"""

from app.services.complaint.complaint_service import ComplaintService
from app.services.complaint.complaint_sla_service import ComplaintSLAService
from app.services.complaint.complaint_assignment_service import (
    ComplaintAssignmentService,
)
from app.services.complaint.complaint_comment_service import (
    ComplaintCommentService,
)
from app.services.complaint.complaint_escalation_service import (
    ComplaintEscalationService,
)
from app.services.complaint.complaint_feedback_service import (
    ComplaintFeedbackService,
)
from app.services.complaint.complaint_resolution_service import (
    ComplaintResolutionService,
)
from app.services.complaint.complaint_analytics_service import (
    ComplaintAnalyticsService,
)
from app.services.complaint.complaint_notification_service import (
    ComplaintNotificationService,
)
from app.services.complaint.complaint_workflow_service import (
    ComplaintWorkflowService,
)
from app.services.complaint.complaint_export_service import (
    ComplaintExportService,
)
from app.services.complaint.complaint_search_service import (
    ComplaintSearchService,
)
from app.services.complaint.complaint_validation_service import (
    ComplaintValidationService,
)

__all__ = [
    # Core services
    "ComplaintService",
    "ComplaintSLAService",
    "ComplaintAssignmentService",
    "ComplaintCommentService",
    "ComplaintEscalationService",
    "ComplaintFeedbackService",
    "ComplaintResolutionService",
    "ComplaintAnalyticsService",
    # Utility services
    "ComplaintNotificationService",
    "ComplaintWorkflowService",
    "ComplaintExportService",
    "ComplaintSearchService",
    "ComplaintValidationService",
]