# --- File: app/schemas/announcement/announcement_approval.py ---
"""
Announcement approval workflow schemas.

This module defines schemas for the approval process
when supervisors create announcements requiring admin approval.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "ApprovalStatus",
    "ApprovalRequest",
    "ApprovalResponse",
    "RejectionRequest",
    "ApprovalWorkflow",
    "SupervisorApprovalQueue",
    "PendingApprovalItem",
    "BulkApproval",
    "ApprovalHistory",
]


class ApprovalStatus(str, Enum):
    """Approval status enumeration."""
    
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NOT_REQUIRED = "not_required"


class ApprovalRequest(BaseCreateSchema):
    """
    Request approval for an announcement.
    
    Submitted by supervisors when creating announcements
    that require admin approval.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID requiring approval",
    )
    requested_by: UUID = Field(
        ...,
        description="User requesting approval (supervisor)",
    )
    
    # Justification
    approval_reason: Union[str, None] = Field(
        None,
        max_length=500,
        description="Justification for why approval is needed",
    )
    
    # Urgency
    is_urgent_request: bool = Field(
        False,
        description="Mark as urgent for prioritized review",
    )
    
    # Preferred approver (optional)
    preferred_approver_id: Union[UUID, None] = Field(
        None,
        description="Preferred admin to review (optional)",
    )
    
    # Expected action
    auto_publish_on_approval: bool = Field(
        True,
        description="Automatically publish when approved",
    )


class ApprovalResponse(BaseSchema):
    """
    Response after approval/rejection decision.
    
    Contains the decision details and next steps.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    
    # Decision
    approved: bool = Field(
        ...,
        description="Whether the announcement was approved",
    )
    
    # Approver info
    approved_by: UUID = Field(
        ...,
        description="UUID of the approving/rejecting admin",
    )
    approved_by_name: str = Field(
        ...,
        description="Name of the admin",
    )
    approved_at: datetime = Field(
        ...,
        description="Decision timestamp",
    )
    
    # Feedback
    approval_notes: Union[str, None] = Field(
        None,
        description="Notes from the approver",
    )
    
    # Publication status
    auto_published: bool = Field(
        ...,
        description="Whether announcement was auto-published",
    )
    published_at: Union[datetime, None] = Field(
        None,
        description="Publication timestamp if published",
    )
    
    # Response message
    message: str = Field(
        ...,
        description="Human-readable response message",
    )


class RejectionRequest(BaseCreateSchema):
    """
    Reject an announcement with feedback.
    
    Provides reason and suggestions for improvement.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID to reject",
    )
    rejected_by: UUID = Field(
        ...,
        description="Admin rejecting the announcement",
    )
    
    rejection_reason: str = Field(
        ...,
        min_length=20,
        max_length=500,
        description="Detailed reason for rejection (20-500 chars)",
    )
    
    # Constructive feedback
    suggested_modifications: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Suggestions for improving the announcement",
    )
    
    # Allow resubmission
    allow_resubmission: bool = Field(
        True,
        description="Whether creator can resubmit after modifications",
    )


class ApprovalWorkflow(BaseSchema):
    """
    Complete approval workflow status.
    
    Shows the current state of an announcement's approval process.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    title: str = Field(
        ...,
        description="Announcement title",
    )
    
    # Approval requirement
    requires_approval: bool = Field(
        ...,
        description="Whether approval is required",
    )
    approval_status: ApprovalStatus = Field(
        ...,
        description="Current approval status",
    )
    
    # Creator info
    created_by: UUID = Field(
        ...,
        description="Creator UUID",
    )
    created_by_name: str = Field(
        ...,
        description="Creator name",
    )
    created_by_role: str = Field(
        ...,
        description="Creator role (supervisor/admin)",
    )
    
    # Timeline
    submitted_for_approval_at: Union[datetime, None] = Field(
        None,
        description="When submitted for approval",
    )
    approved_rejected_at: Union[datetime, None] = Field(
        None,
        description="When decision was made",
    )
    
    # Current approver (if pending)
    pending_with: Union[UUID, None] = Field(
        None,
        description="Admin currently reviewing (if assigned)",
    )
    pending_with_name: Union[str, None] = Field(
        None,
        description="Reviewing admin's name",
    )
    
    # Decision details
    decision_by: Union[UUID, None] = Field(
        None,
        description="Admin who made the decision",
    )
    decision_by_name: Union[str, None] = Field(
        None,
        description="Decision maker's name",
    )
    
    # Rejection details (if rejected)
    rejection_reason: Union[str, None] = Field(
        None,
        description="Rejection reason if rejected",
    )
    suggested_modifications: Union[str, None] = Field(
        None,
        description="Suggested changes if rejected",
    )
    can_resubmit: bool = Field(
        True,
        description="Whether resubmission is allowed",
    )
    
    # Timing metrics
    time_pending_hours: Union[float, None] = Field(
        None,
        ge=0,
        description="Hours in pending state",
    )


class PendingApprovalItem(BaseSchema):
    """
    Pending approval item for queue display.
    
    Lightweight schema for approval queue lists.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    title: str = Field(
        ...,
        description="Announcement title",
    )
    category: str = Field(
        ...,
        description="Announcement category",
    )
    
    # Creator
    created_by: UUID = Field(
        ...,
        description="Creator UUID",
    )
    created_by_name: str = Field(
        ...,
        description="Creator name",
    )
    
    # Timing
    submitted_at: datetime = Field(
        ...,
        description="Submission timestamp",
    )
    is_urgent: bool = Field(
        ...,
        description="Urgent flag",
    )
    
    # Preview
    content_preview: str = Field(
        ...,
        max_length=200,
        description="First 200 characters of content",
    )
    
    # Targeting
    target_audience: str = Field(
        ...,
        description="Target audience type",
    )
    estimated_recipients: int = Field(
        ...,
        ge=0,
        description="Estimated recipient count",
    )
    
    # Age
    hours_pending: float = Field(
        ...,
        ge=0,
        description="Hours in pending state",
    )


class SupervisorApprovalQueue(BaseSchema):
    """
    Supervisor's view of their pending approvals.
    
    Shows all announcements submitted by a supervisor
    and their current approval status.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    supervisor_id: UUID = Field(
        ...,
        description="Supervisor UUID",
    )
    supervisor_name: str = Field(
        ...,
        description="Supervisor name",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel UUID",
    )
    
    # Counts
    total_pending: int = Field(
        ...,
        ge=0,
        description="Total pending approvals",
    )
    urgent_pending: int = Field(
        ...,
        ge=0,
        description="Urgent items pending",
    )
    approved_today: int = Field(
        0,
        ge=0,
        description="Items approved today",
    )
    rejected_today: int = Field(
        0,
        ge=0,
        description="Items rejected today",
    )
    
    # Items
    pending_announcements: list[PendingApprovalItem] = Field(
        default_factory=list,
        description="Pending approval items",
    )
    
    # Average response time
    avg_approval_time_hours: Union[float, None] = Field(
        None,
        ge=0,
        description="Average approval response time",
    )


class BulkApproval(BaseCreateSchema):
    """
    Approve or reject multiple announcements at once.
    
    Used for batch operations in admin interfaces.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Announcement UUIDs to process (1-50)",
    )
    
    # Decision
    approved: bool = Field(
        ...,
        description="Approve (True) or reject (False)",
    )
    decided_by: UUID = Field(
        ...,
        description="Admin making the decision",
    )
    
    # Notes
    approval_notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Notes for the decision",
    )
    
    # For rejections
    rejection_reason: Union[str, None] = Field(
        None,
        max_length=500,
        description="Rejection reason (required if rejecting)",
    )
    
    # Publication
    publish_immediately: bool = Field(
        True,
        description="Publish approved announcements immediately",
    )
    
    @field_validator("announcement_ids")
    @classmethod
    def validate_unique_ids(cls, v: list[UUID]) -> list[UUID]:
        """Ensure no duplicate IDs."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate announcement IDs not allowed")
        return v
    
    @model_validator(mode="after")
    def validate_rejection_reason(self) -> "BulkApproval":
        """Require rejection reason when rejecting."""
        if not self.approved and not self.rejection_reason:
            raise ValueError("rejection_reason required when rejecting")
        return self


class ApprovalHistory(BaseSchema):
    """
    Approval history entry for audit trail.
    
    Records each action in the approval workflow.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(
        ...,
        description="History entry UUID",
    )
    announcement_id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    
    # Action
    action: str = Field(
        ...,
        description="Action taken (submitted/approved/rejected/resubmitted)",
    )
    previous_status: Union[ApprovalStatus, None] = Field(
        None,
        description="Status before action",
    )
    new_status: ApprovalStatus = Field(
        ...,
        description="Status after action",
    )
    
    # Actor
    performed_by: UUID = Field(
        ...,
        description="User who performed the action",
    )
    performed_by_name: str = Field(
        ...,
        description="Actor's name",
    )
    performed_by_role: str = Field(
        ...,
        description="Actor's role",
    )
    
    # Details
    notes: Union[str, None] = Field(
        None,
        description="Additional notes",
    )
    
    # Timestamp
    performed_at: datetime = Field(
        ...,
        description="When action was performed",
    )