"""
Complaint service layer.

Provides comprehensive business logic for complaint management including:

- **Core Operations**: Complaint creation, updates, status management
- **Assignment Management**: Assignment, reassignment, bulk operations, history
- **Collaboration**: Comments, mentions, and team communication
- **Escalation**: Manual and automatic rule-based escalations
- **Resolution**: Resolution workflows, reopening, and closure
- **Feedback**: User feedback collection and analysis
- **SLA Monitoring**: SLA compliance tracking and breach detection
- **Analytics**: Dashboards, KPIs, trends, and data breakdowns

All services follow consistent patterns with:
- Comprehensive validation
- Transaction management
- Error handling and logging
- Audit trail support
- Metadata tracking

Version: 1.0.0
"""

from app.services.complaint.complaint_service import ComplaintService
from app.services.complaint.complaint_assignment_service import ComplaintAssignmentService
from app.services.complaint.complaint_comment_service import ComplaintCommentService
from app.services.complaint.complaint_escalation_service import ComplaintEscalationService
from app.services.complaint.complaint_resolution_service import ComplaintResolutionService
from app.services.complaint.complaint_feedback_service import ComplaintFeedbackService
from app.services.complaint.complaint_sla_service import ComplaintSLAService
from app.services.complaint.complaint_analytics_service import ComplaintAnalyticsService

__all__ = [
    "ComplaintService",
    "ComplaintAssignmentService",
    "ComplaintCommentService",
    "ComplaintEscalationService",
    "ComplaintResolutionService",
    "ComplaintFeedbackService",
    "ComplaintSLAService",
    "ComplaintAnalyticsService",
]

__version__ = "1.0.0"
__author__ = "Hostel Management System"
__description__ = "Comprehensive complaint management service layer"

# Service registry for dependency injection or factory patterns
SERVICE_REGISTRY = {
    "complaint": ComplaintService,
    "assignment": ComplaintAssignmentService,
    "comment": ComplaintCommentService,
    "escalation": ComplaintEscalationService,
    "resolution": ComplaintResolutionService,
    "feedback": ComplaintFeedbackService,
    "sla": ComplaintSLAService,
    "analytics": ComplaintAnalyticsService,
}


def get_service(service_name: str):
    """
    Get service class by name.
    
    Args:
        service_name: Name of the service
        
    Returns:
        Service class
        
    Raises:
        KeyError: If service name is not found
    """
    return SERVICE_REGISTRY[service_name]