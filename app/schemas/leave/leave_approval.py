"""
Leave approval and workflow schemas.

Provides schemas for supervisor/admin leave approval decisions
with comprehensive tracking and validation.
"""

from datetime import datetime
from typing import List, Union

from pydantic import ConfigDict, Field, field_validator, model_validator
from uuid import UUID

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import LeaveStatus, LeaveType

__all__ = [
    "LeaveApprovalRequest",
    "LeaveApprovalResponse",
    "LeaveApprovalAction",
    "PendingApprovalItem",
    "LeaveApprovalHistoryResponse",
    "LeaveApprovalHistoryItem",
]


class LeaveApprovalRequest(BaseCreateSchema):
    """
    Supervisor/admin leave approval or rejection request.
    
    Handles the approval workflow with proper validation and
    audit trail requirements.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "leave_id": "123e4567-e89b-12d3-a456-426614174000",
                "approver_id": "123e4567-e89b-12d3-a456-426614174001",
                "approve": True,
                "approval_notes": "Approved as requested",
                "notify_student": True
            }
        }
    )

    leave_id: UUID = Field(
        ...,
        description="Leave application unique identifier",
    )
    approver_id: UUID = Field(
        ...,
        description="User ID of approver (supervisor/admin)",
    )
    approve: bool = Field(
        ...,
        description="True to approve, False to reject",
    )
    approval_notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Additional notes or comments from approver",
    )
    rejection_reason: Union[str, None] = Field(
        None,
        min_length=10,
        max_length=500,
        description="Detailed reason for rejection (required if rejecting)",
    )
    conditions: Union[str, None] = Field(
        None,
        max_length=500,
        description="Conditions or requirements for approved leave",
    )
    notify_student: bool = Field(
        default=True,
        description="Send notification to student about decision",
    )
    notify_guardian: bool = Field(
        default=False,
        description="Send notification to guardian about decision",
    )

    @field_validator("approval_notes", "rejection_reason", "conditions")
    @classmethod
    def validate_text_fields(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_approval_decision(self):
        """
        Validate approval decision consistency.
        
        Ensures:
        - Rejection reason is provided when rejecting
        - Conditions are only set when approving
        """
        # Rejection requires reason
        if not self.approve:
            if not self.rejection_reason:
                raise ValueError(
                    "rejection_reason is required when rejecting leave"
                )
            
            if len(self.rejection_reason.strip()) < 10:
                raise ValueError(
                    "Rejection reason must be at least 10 characters"
                )
            
            # Conditions shouldn't be set for rejection
            if self.conditions:
                raise ValueError(
                    "conditions should not be set when rejecting leave"
                )
        else:
            # Approval shouldn't have rejection reason
            if self.rejection_reason:
                raise ValueError(
                    "rejection_reason should not be set when approving leave"
                )
        
        return self


class LeaveApprovalAction(BaseCreateSchema):
    """
    Alternative approval action schema with explicit status.
    
    Provides more flexibility for complex approval workflows.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "leave_id": "123e4567-e89b-12d3-a456-426614174000",
                "approver_id": "123e4567-e89b-12d3-a456-426614174001",
                "action": "approve",
                "comments": "Leave approved as per hostel policy",
                "notify_student": True
            }
        }
    )

    leave_id: UUID = Field(
        ...,
        description="Leave application unique identifier",
    )
    approver_id: UUID = Field(
        ...,
        description="Approver user ID",
    )
    action: str = Field(
        ...,
        pattern=r"^(approve|reject|request_changes|escalate)$",
        description="Approval action to take",
    )
    comments: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Comments explaining the action",
    )
    requested_changes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Specific changes requested (if action is 'request_changes')",
    )
    escalate_to: Union[UUID, None] = Field(
        None,
        description="User ID to escalate to (if action is 'escalate')",
    )
    conditions: Union[str, None] = Field(
        None,
        max_length=500,
        description="Approval conditions",
    )
    notify_student: bool = Field(
        default=True,
        description="Notify student of decision",
    )

    @field_validator("comments")
    @classmethod
    def validate_comments(cls, v: str) -> str:
        """Validate comments are meaningful."""
        v = v.strip()
        
        if len(v) < 10:
            raise ValueError("Comments must be at least 10 characters")
        
        return v

    @model_validator(mode="after")
    def validate_action_requirements(self):
        """
        Validate action-specific requirements.
        
        Ensures required fields are provided for each action type.
        """
        if self.action == "request_changes":
            if not self.requested_changes:
                raise ValueError(
                    "requested_changes is required for 'request_changes' action"
                )
        
        if self.action == "escalate":
            if not self.escalate_to:
                raise ValueError(
                    "escalate_to is required for 'escalate' action"
                )
        
        if self.action == "approve":
            # Conditions only make sense for approval
            pass
        else:
            # Other actions shouldn't have conditions
            if self.conditions:
                raise ValueError(
                    f"conditions should not be set for '{self.action}' action"
                )
        
        return self


class LeaveApprovalResponse(BaseSchema):
    """
    Leave approval decision response.
    
    Provides complete information about the approval decision
    with timestamps and responsible parties.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "leave_id": "123e4567-e89b-12d3-a456-426614174000",
                "student_id": "123e4567-e89b-12d3-a456-426614174001",
                "student_name": "John Student",
                "status": "approved",
                "approved_by_name": "Supervisor Smith",
                "message": "Leave application has been approved"
            }
        }
    )

    leave_id: UUID = Field(
        ...,
        description="Leave application unique identifier",
    )
    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    student_name: str = Field(
        ...,
        description="Student full name",
    )
    status: LeaveStatus = Field(
        ...,
        description="Updated leave status after decision",
    )
    previous_status: Union[LeaveStatus, None] = Field(
        None,
        description="Previous leave status",
    )

    # Approval details
    approved_by: Union[UUID, None] = Field(
        None,
        description="Approver user ID (if approved)",
    )
    approved_by_name: Union[str, None] = Field(
        None,
        description="Approver full name",
    )
    approved_at: Union[datetime, None] = Field(
        None,
        description="Approval timestamp",
    )
    approval_notes: Union[str, None] = Field(
        None,
        description="Approval notes",
    )
    conditions: Union[str, None] = Field(
        None,
        description="Approval conditions",
    )

    # Rejection details
    rejected_by: Union[UUID, None] = Field(
        None,
        description="Rejector user ID (if rejected)",
    )
    rejected_by_name: Union[str, None] = Field(
        None,
        description="Rejector full name",
    )
    rejected_at: Union[datetime, None] = Field(
        None,
        description="Rejection timestamp",
    )
    rejection_reason: Union[str, None] = Field(
        None,
        description="Rejection reason",
    )

    # Response metadata
    message: str = Field(
        ...,
        description="Human-readable response message",
    )
    notifications_sent: bool = Field(
        default=False,
        description="Whether notifications were sent",
    )
    notification_recipients: Union[List[str], None] = Field(
        None,
        description="List of notification recipients",
    )

    @model_validator(mode="after")
    def validate_response_consistency(self):
        """
        Validate response data consistency.
        
        Ensures approval/rejection fields match the status.
        """
        # Approved status should have approval details
        if self.status == LeaveStatus.APPROVED:
            if not self.approved_by or not self.approved_at:
                raise ValueError(
                    "Approval details required for APPROVED status"
                )
            
            # Shouldn't have rejection details
            if self.rejected_by or self.rejected_at or self.rejection_reason:
                raise ValueError(
                    "Rejection details should not be present for APPROVED status"
                )
        
        # Rejected status should have rejection details
        elif self.status == LeaveStatus.REJECTED:
            if not self.rejected_by or not self.rejected_at:
                raise ValueError(
                    "Rejection details required for REJECTED status"
                )
            
            if not self.rejection_reason:
                raise ValueError(
                    "Rejection reason required for REJECTED status"
                )
            
            # Shouldn't have approval details
            if self.approved_by or self.approved_at:
                raise ValueError(
                    "Approval details should not be present for REJECTED status"
                )
        
        return self


class PendingApprovalItem(BaseSchema):
    """
    Pending approval item for dashboard/queue display.
    
    Compact view of leave applications awaiting approval.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "leave_id": "123e4567-e89b-12d3-a456-426614174000",
                "student_id": "123e4567-e89b-12d3-a456-426614174001",
                "student_name": "John Student",
                "room_number": "101",
                "leave_type": "casual",
                "from_date": "2024-02-01",
                "to_date": "2024-02-05",
                "total_days": 5,
                "applied_at": "2024-01-25T10:30:00Z",
                "priority": "normal",
                "reason_summary": "Family function"
            }
        }
    )

    leave_id: UUID = Field(..., description="Leave application ID")
    student_id: UUID = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    hostel_name: str = Field(..., description="Hostel name")
    room_number: Union[str, None] = Field(None, description="Room number")
    leave_type: LeaveType = Field(..., description="Leave type")
    from_date: datetime = Field(..., description="Leave start date")
    to_date: datetime = Field(..., description="Leave end date")
    total_days: int = Field(..., description="Total days")
    applied_at: datetime = Field(..., description="Application timestamp")
    reason_summary: str = Field(..., max_length=100, description="Truncated reason")
    priority: str = Field(default="normal", description="Priority level")
    urgency_score: int = Field(default=0, description="Urgency score for sorting")


class LeaveApprovalHistoryItem(BaseSchema):
    """Individual approval history entry."""
    
    action: str = Field(..., description="Action taken")
    actor_id: UUID = Field(..., description="User who performed action")
    actor_name: str = Field(..., description="User name")
    timestamp: datetime = Field(..., description="Action timestamp")
    comments: Union[str, None] = Field(None, description="Action comments")
    from_status: Union[LeaveStatus, None] = Field(None, description="Previous status")
    to_status: LeaveStatus = Field(..., description="New status")


class LeaveApprovalHistoryResponse(BaseSchema):
    """
    Complete approval history with audit trail.
    
    Comprehensive view of all actions taken on a leave application.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "leave_id": "123e4567-e89b-12d3-a456-426614174000",
                "student_name": "John Student",
                "current_status": "approved",
                "history": []
            }
        }
    )

    leave_id: UUID = Field(..., description="Leave application ID")
    student_id: UUID = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    current_status: LeaveStatus = Field(..., description="Current status")
    history: List[LeaveApprovalHistoryItem] = Field(..., description="Approval history")
    total_actions: int = Field(..., description="Total number of actions")
    days_since_application: int = Field(..., description="Days since application")