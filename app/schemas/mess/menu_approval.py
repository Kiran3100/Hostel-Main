# --- File: app/schemas/mess/menu_approval.py ---
"""
Menu approval workflow schemas.

Provides schemas for menu approval requests, responses,
and workflow tracking with comprehensive validation.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import Field, field_validator, model_validator, computed_field
from uuid import UUID

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "MenuApprovalRequest",
    "MenuApprovalResponse",
    "ApprovalWorkflow",
    "BulkApproval",
    "ApprovalHistory",
    "ApprovalAttempt",
]


class MenuApprovalRequest(BaseCreateSchema):
    """
    Request menu approval from supervisor to admin.
    
    Submits menu for review with cost estimates and justification.
    """

    menu_id: UUID = Field(
        ...,
        description="Menu unique identifier",
    )
    requested_by: UUID = Field(
        ...,
        description="Supervisor requesting approval",
    )
    
    # Submission details
    submission_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Notes for approver",
    )
    urgency: str = Field(
        default="normal",
        pattern=r"^(low|normal|high|urgent)$",
        description="Approval urgency level",
    )
    
    # Budget information
    # Pydantic v2: Decimal fields with precision handled via field_validator
    estimated_cost_per_person: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Estimated cost per person",
    )
    total_estimated_cost: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Total estimated cost",
    )
    expected_students: Optional[int] = Field(
        None,
        ge=1,
        le=10000,
        description="Expected number of students",
    )
    
    # Special requirements
    requires_special_procurement: bool = Field(
        default=False,
        description="Requires special ingredient procurement",
    )
    special_items: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Special items requiring approval",
    )
    
    # Justification
    reason_for_special_menu: Optional[str] = Field(
        None,
        max_length=1000,
        description="Justification for special/expensive menu",
    )

    @field_validator("submission_notes", "reason_for_special_menu", mode="before")
    @classmethod
    def normalize_text(cls, v: Optional[str]) -> Optional[str]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @field_validator("estimated_cost_per_person", "total_estimated_cost", mode="after")
    @classmethod
    def round_cost_decimals(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Round cost values to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @model_validator(mode="after")
    def validate_cost_information(self) -> "MenuApprovalRequest":
        """
        Validate cost information consistency.
        
        If per-person cost is high, justification should be provided.
        """
        if self.estimated_cost_per_person:
            # If cost is above threshold (e.g., ₹100), require justification
            if self.estimated_cost_per_person > Decimal("100.00"):
                if not self.reason_for_special_menu:
                    raise ValueError(
                        "Justification required for high per-person cost"
                    )
        
        # Validate total cost calculation
        if (
            self.estimated_cost_per_person
            and self.expected_students
            and self.total_estimated_cost
        ):
            calculated_total = (
                self.estimated_cost_per_person * Decimal(self.expected_students)
            )
            
            # Allow 10% variance
            variance = abs(calculated_total - self.total_estimated_cost)
            max_variance = calculated_total * Decimal("0.1")
            
            if variance > max_variance:
                raise ValueError(
                    "Total estimated cost doesn't match per-person cost calculation"
                )
        
        return self


class MenuApprovalResponse(BaseSchema):
    """
    Menu approval decision response.
    
    Provides complete information about approval or rejection decision.
    """

    menu_id: UUID = Field(
        ...,
        description="Menu unique identifier",
    )
    menu_date: Date = Field(
        ...,
        description="Menu Date",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    
    # Decision
    approved: bool = Field(
        ...,
        description="Whether menu was approved",
    )
    approval_status: str = Field(
        ...,
        pattern=r"^(approved|rejected|approved_with_conditions|pending_revision)$",
        description="Approval status",
    )
    
    # Approver details
    approved_by: UUID = Field(
        ...,
        description="Approver user ID",
    )
    approved_by_name: str = Field(
        ...,
        description="Approver full name",
    )
    approved_by_role: str = Field(
        ...,
        description="Approver role",
    )
    approved_at: datetime = Field(
        ...,
        description="Approval timestamp",
    )
    
    # Feedback and conditions
    approval_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Approver's notes",
    )
    conditions: Optional[str] = Field(
        None,
        max_length=500,
        description="Conditions for approval (if any)",
    )
    rejection_reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for rejection",
    )
    suggested_changes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Suggested modifications",
    )
    
    # Cost approval
    approved_budget: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Approved budget amount",
    )
    budget_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Notes about budget approval",
    )
    
    # Response message
    message: str = Field(
        ...,
        description="Human-readable response message",
    )
    
    # Next steps
    requires_resubmission: bool = Field(
        default=False,
        description="Whether resubmission is required",
    )
    can_publish: bool = Field(
        ...,
        description="Whether menu can be published",
    )

    @field_validator("approved_budget", mode="after")
    @classmethod
    def round_budget(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Round budget to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @model_validator(mode="after")
    def validate_response_consistency(self) -> "MenuApprovalResponse":
        """Validate approval response consistency."""
        if self.approved:
            # Approved menus shouldn't have rejection reason
            if self.rejection_reason:
                raise ValueError(
                    "Rejection reason should not be present for approved menus"
                )
        else:
            # Rejected menus must have rejection reason
            if not self.rejection_reason:
                raise ValueError(
                    "Rejection reason is required for rejected menus"
                )
        
        return self


class ApprovalWorkflow(BaseSchema):
    """
    Menu approval workflow status tracking.
    
    Tracks current state of approval process with timeline.
    """

    menu_id: UUID = Field(
        ...,
        description="Menu unique identifier",
    )
    menu_date: Date = Field(
        ...,
        description="Menu Date",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    
    # Workflow status
    requires_approval: bool = Field(
        ...,
        description="Whether approval is required",
    )
    approval_status: str = Field(
        ...,
        pattern=r"^(pending|approved|rejected|not_required|revision_requested)$",
        description="Current approval status",
    )
    
    # Workflow stage
    current_stage: str = Field(
        ...,
        pattern=r"^(draft|submitted|under_review|approved|rejected|published)$",
        description="Current workflow stage",
    )
    
    # Timeline
    created_at: datetime = Field(
        ...,
        description="Menu creation timestamp",
    )
    submitted_for_approval_at: Optional[datetime] = Field(
        None,
        description="Submission timestamp",
    )
    approved_at: Optional[datetime] = Field(
        None,
        description="Approval timestamp",
    )
    rejected_at: Optional[datetime] = Field(
        None,
        description="Rejection timestamp",
    )
    published_at: Optional[datetime] = Field(
        None,
        description="Publication timestamp",
    )
    
    # Current approver
    pending_with: Optional[UUID] = Field(
        None,
        description="User ID of current approver",
    )
    pending_with_name: Optional[str] = Field(
        None,
        description="Name of current approver",
    )
    pending_with_role: Optional[str] = Field(
        None,
        description="Role of current approver",
    )
    
    # Deadlines
    approval_deadline: Optional[datetime] = Field(
        None,
        description="Approval deadline",
    )
    is_overdue: bool = Field(
        default=False,
        description="Whether approval is overdue",
    )
    
    # Revision tracking
    revision_count: int = Field(
        default=0,
        ge=0,
        description="Number of revisions made",
    )
    last_revision_at: Optional[datetime] = Field(
        None,
        description="Last revision timestamp",
    )

    @computed_field
    @property
    def days_pending(self) -> Optional[int]:
        """Calculate days approval has been pending."""
        if self.submitted_for_approval_at and self.approval_status == "pending":
            return (datetime.now() - self.submitted_for_approval_at).days
        return None

    @computed_field
    @property
    def time_to_approval_hours(self) -> Optional[Decimal]:
        """Calculate hours taken for approval."""
        if self.submitted_for_approval_at and self.approved_at:
            hours = (self.approved_at - self.submitted_for_approval_at).total_seconds() / 3600
            return round(Decimal(str(hours)), 2)
        return None


class BulkApproval(BaseCreateSchema):
    """
    Approve or reject multiple menus in bulk.
    
    Efficient bulk approval for routine or similar menus.
    """

    menu_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of menu IDs to approve/reject",
    )
    approved: bool = Field(
        ...,
        description="True to approve all, False to reject all",
    )
    approver_id: UUID = Field(
        ...,
        description="Approver user ID",
    )
    approval_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Common notes for all menus",
    )
    rejection_reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Common rejection reason (if rejecting)",
    )
    apply_conditions: Optional[str] = Field(
        None,
        max_length=500,
        description="Common conditions to apply",
    )
    
    # Budget approval
    approved_budget_per_menu: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Approved budget for each menu",
    )

    @field_validator("approved_budget_per_menu", mode="after")
    @classmethod
    def round_budget(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Round budget to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @model_validator(mode="after")
    def validate_bulk_approval(self) -> "BulkApproval":
        """Validate bulk approval request."""
        # Rejection requires reason
        if not self.approved and not self.rejection_reason:
            raise ValueError(
                "Rejection reason is required for bulk rejection"
            )
        
        # Can't have both approval notes and rejection reason
        if self.approved and self.rejection_reason:
            raise ValueError(
                "Rejection reason should not be provided when approving"
            )
        
        return self


class ApprovalAttempt(BaseSchema):
    """
    Individual approval attempt record.
    
    Represents single submission in approval workflow.
    """

    attempt_number: int = Field(
        ...,
        ge=1,
        description="Attempt sequence number",
    )
    submitted_by: UUID = Field(
        ...,
        description="Submitter user ID",
    )
    submitted_by_name: str = Field(
        ...,
        description="Submitter name",
    )
    submitted_at: datetime = Field(
        ...,
        description="Submission timestamp",
    )
    reviewed_by: Optional[UUID] = Field(
        None,
        description="Reviewer user ID",
    )
    reviewed_by_name: Optional[str] = Field(
        None,
        description="Reviewer name",
    )
    reviewed_at: Optional[datetime] = Field(
        None,
        description="Review timestamp",
    )
    decision: Optional[str] = Field(
        None,
        pattern=r"^(approved|rejected|revision_requested|pending)$",
        description="Approval decision",
    )
    feedback: Optional[str] = Field(
        None,
        description="Reviewer feedback",
    )
    changes_made: Optional[str] = Field(
        None,
        description="Changes made in this revision",
    )


class ApprovalHistory(BaseSchema):
    """
    Complete approval history for menu.
    
    Tracks all approval attempts and decisions for audit trail.
    """

    menu_id: UUID = Field(
        ...,
        description="Menu unique identifier",
    )
    menu_date: Date = Field(
        ...,
        description="Menu Date",
    )
    total_submissions: int = Field(
        ...,
        ge=0,
        description="Total approval submissions",
    )
    approval_attempts: List[ApprovalAttempt] = Field(
        ...,
        description="Chronological list of approval attempts",
    )
    current_status: str = Field(
        ...,
        description="Current approval status",
    )
    final_approver: Optional[str] = Field(
        None,
        description="Final approver name",
    )