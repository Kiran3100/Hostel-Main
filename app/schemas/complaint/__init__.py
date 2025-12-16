"""
Complaint schemas package.

Comprehensive complaint management schemas including creation, updates,
assignments, resolution, escalation, feedback, and analytics.

Example:
    from app.schemas.complaint import ComplaintCreate, ComplaintDetail
"""

from app.schemas.complaint.complaint_analytics import (
    CategoryAnalysis,
    CategoryMetrics,
    ComplaintAnalytics,
    ComplaintHeatmap,
    ComplaintTrendPoint,
    ResolutionMetrics,
    RoomComplaintCount,
    StaffPerformance,
)
from app.schemas.complaint.complaint_assignment import (
    AssignmentHistory,
    AssignmentRequest,
    AssignmentResponse,
    BulkAssignment,
    ReassignmentRequest,
    UnassignRequest,
)
from app.schemas.complaint.complaint_base import (
    ComplaintBase,
    ComplaintCreate,
    ComplaintStatusUpdate,
    ComplaintUpdate,
)
from app.schemas.complaint.complaint_comments import (
    CommentCreate,
    CommentDelete,
    CommentList,
    CommentResponse,
    CommentUpdate,
    MentionNotification,
)
from app.schemas.complaint.complaint_escalation import (
    AutoEscalationRule,
    EscalationEntry,
    EscalationHistory,
    EscalationRequest,
    EscalationResponse,
)
from app.schemas.complaint.complaint_feedback import (
    FeedbackAnalysis,
    FeedbackRequest,
    FeedbackResponse,
    FeedbackSummary,
    RatingTrendPoint,
)
from app.schemas.complaint.complaint_filters import (
    ComplaintExportRequest,
    ComplaintFilterParams,
    ComplaintSearchRequest,
    ComplaintSortOptions,
)
from app.schemas.complaint.complaint_resolution import (
    CloseRequest,
    ReopenRequest,
    ResolutionRequest,
    ResolutionResponse,
    ResolutionUpdate,
)
from app.schemas.complaint.complaint_response import (
    ComplaintDetail,
    ComplaintListItem,
    ComplaintResponse,
    ComplaintStats,
    ComplaintSummary,
)

__all__ = [
    # Base schemas
    "ComplaintBase",
    "ComplaintCreate",
    "ComplaintUpdate",
    "ComplaintStatusUpdate",
    # Response schemas
    "ComplaintResponse",
    "ComplaintDetail",
    "ComplaintListItem",
    "ComplaintSummary",
    "ComplaintStats",
    # Assignment schemas
    "AssignmentRequest",
    "AssignmentResponse",
    "ReassignmentRequest",
    "BulkAssignment",
    "UnassignRequest",
    "AssignmentHistory",
    # Resolution schemas
    "ResolutionRequest",
    "ResolutionResponse",
    "ResolutionUpdate",
    "ReopenRequest",
    "CloseRequest",
    # Escalation schemas
    "EscalationRequest",
    "EscalationResponse",
    "EscalationHistory",
    "EscalationEntry",
    "AutoEscalationRule",
    # Feedback schemas
    "FeedbackRequest",
    "FeedbackResponse",
    "FeedbackSummary",
    "FeedbackAnalysis",
    "RatingTrendPoint",
    # Comment schemas
    "CommentCreate",
    "CommentResponse",
    "CommentList",
    "CommentUpdate",
    "CommentDelete",
    "MentionNotification",
    # Filter schemas
    "ComplaintFilterParams",
    "ComplaintSearchRequest",
    "ComplaintSortOptions",
    "ComplaintExportRequest",
    # Analytics schemas
    "ComplaintAnalytics",
    "ResolutionMetrics",
    "CategoryAnalysis",
    "CategoryMetrics",
    "ComplaintTrendPoint",
    "StaffPerformance",
    "ComplaintHeatmap",
    "RoomComplaintCount",
]