# --- File: app/schemas/maintenance/maintenance_approval.py ---
"""
Maintenance approval workflow schemas.

Provides schemas for approval requests, responses, threshold configuration,
and rejection handling with comprehensive validation.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Optional

from pydantic import ConfigDict, Field, field_validator, model_validator
from uuid import UUID

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "ApprovalRequest",
    "ApprovalResponse",
    "ThresholdConfig",
    "ApprovalWorkflow",
    "RejectionRequest",
]


class ApprovalRequest(BaseCreateSchema):
    """
    Request approval for maintenance work.
    
    Submitted by supervisor to admin when cost exceeds threshold
    or approval is required for other reasons.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "request_number": "MNT-2024-001",
                "estimated_cost": "7500.00",
                "cost_justification": "Replacement of entire electrical panel required due to safety concerns",
                "approval_reason": "Cost exceeds supervisor approval limit of ₹5000",
                "urgent": False
            }
        }
    )

    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request unique identifier",
    )
    request_number: str = Field(
        ...,
        description="Maintenance request number",
    )
    
    # Cost details - Using Annotated for Decimal constraints
    estimated_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Estimated total cost",
    )
    cost_breakdown: Optional[Dict[str, Decimal]] = Field(
        None,
        description="Detailed cost breakdown by category",
    )
    cost_justification: str = Field(
        ...,
        min_length=20,
        max_length=1000,
        description="Detailed justification for cost estimate",
    )
    
    # Approval justification
    approval_reason: str = Field(
        ...,
        min_length=20,
        max_length=500,
        description="Reason why approval is needed",
    )
    business_impact: Optional[str] = Field(
        None,
        max_length=500,
        description="Impact on business/operations if not approved",
    )
    
    # Urgency
    urgent: bool = Field(
        False,
        description="Whether approval is urgent",
    )
    urgency_reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for urgency (if urgent)",
    )
    
    # Vendor information
    preferred_vendor: Optional[str] = Field(
        None,
        max_length=255,
        description="Preferred vendor/contractor",
    )
    vendor_quote: Optional[str] = Field(
        None,
        description="Vendor quote reference or URL",
    )
    alternative_quotes: Optional[int] = Field(
        None,
        ge=0,
        le=10,
        description="Number of alternative quotes obtained",
    )
    
    # Timeline
    requested_completion_date: Optional[Date] = Field(
        None,
        description="Requested completion Date",
    )
    
    # Requester
    requested_by: UUID = Field(
        ...,
        description="Supervisor requesting approval",
    )

    @field_validator("estimated_cost")
    @classmethod
    def round_cost(cls, v: Decimal) -> Decimal:
        """Round cost to 2 decimal places."""
        return round(v, 2)

    @field_validator("cost_breakdown")
    @classmethod
    def validate_cost_breakdown(
        cls,
        v: Optional[Dict[str, Decimal]],
    ) -> Optional[Dict[str, Decimal]]:
        """
        Validate cost breakdown values.
        
        Ensures all breakdown amounts are positive and reasonable.
        """
        if v is not None:
            for category, amount in v.items():
                if amount < 0:
                    raise ValueError(
                        f"Cost breakdown amount for '{category}' cannot be negative"
                    )
                
                # Round to 2 decimal places
                v[category] = round(amount, 2)
        
        return v

    @field_validator(
        "cost_justification",
        "approval_reason",
        "business_impact",
        "urgency_reason",
    )
    @classmethod
    def validate_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize text fields."""
        if v is not None:
            v = v.strip()
            
            # For required fields (cost_justification, approval_reason)
            if isinstance(v, str) and len(v) > 0:
                return v
            
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_urgency_requirements(self) -> "ApprovalRequest":
        """
        Validate urgency flag consistency.
        
        Urgent requests should have urgency reason.
        """
        if self.urgent and not self.urgency_reason:
            raise ValueError(
                "Urgency reason is required when approval is marked urgent"
            )
        
        return self

    @model_validator(mode="after")
    def validate_cost_breakdown_total(self) -> "ApprovalRequest":
        """
        Validate cost breakdown matches estimated cost.
        
        Sum of breakdown should match total estimate.
        """
        if self.cost_breakdown:
            breakdown_total = sum(self.cost_breakdown.values())
            
            # Allow 1% variance for rounding
            variance = abs(breakdown_total - self.estimated_cost)
            max_variance = self.estimated_cost * Decimal("0.01")
            
            if variance > max_variance and variance > Decimal("10.00"):
                raise ValueError(
                    f"Cost breakdown total ({breakdown_total}) doesn't match "
                    f"estimated cost ({self.estimated_cost})"
                )
        
        return self


class ApprovalResponse(BaseSchema):
    """
    Approval decision response.
    
    Provides complete information about approval or rejection
    with justification and conditions.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "request_number": "MNT-2024-001",
                "approved": True,
                "decision_maker_name": "John Admin",
                "decision_maker_role": "Admin",
                "approved_amount": "7500.00",
                "message": "Approval granted for electrical panel replacement"
            }
        }
    )

    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request unique identifier",
    )
    request_number: str = Field(
        ...,
        description="Request number",
    )
    
    # Decision
    approved: bool = Field(
        ...,
        description="Whether request was approved",
    )
    decision_maker: UUID = Field(
        ...,
        description="User ID who made decision",
    )
    decision_maker_name: str = Field(
        ...,
        description="Name of decision maker",
    )
    decision_maker_role: str = Field(
        ...,
        description="Role of decision maker",
    )
    decided_at: datetime = Field(
        ...,
        description="Decision timestamp",
    )
    
    # Approved details (if approved)
    approved_amount: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Approved amount (may differ from requested)",
    )
    approval_conditions: Optional[str] = Field(
        None,
        max_length=1000,
        description="Conditions or requirements for approval",
    )
    approval_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional approval notes",
    )
    
    # Rejection details (if rejected)
    rejection_reason: Optional[str] = Field(
        None,
        max_length=1000,
        description="Detailed rejection reason",
    )
    suggested_alternative: Optional[str] = Field(
        None,
        max_length=500,
        description="Suggested alternative approach",
    )
    resubmission_allowed: bool = Field(
        default=True,
        description="Whether request can be resubmitted",
    )
    
    # Response message
    message: str = Field(
        ...,
        description="Human-readable response message",
    )
    
    # Notification tracking
    notifications_sent: bool = Field(
        default=False,
        description="Whether notifications were sent",
    )

    @field_validator("approved_amount")
    @classmethod
    def round_amount(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Round approved amount to 2 decimal places."""
        return round(v, 2) if v is not None else None

    @model_validator(mode="after")
    def validate_response_consistency(self) -> "ApprovalResponse":
        """
        Validate approval response consistency.
        
        Ensures approval/rejection fields are consistent with decision.
        """
        if self.approved:
            # Approved requests should have approved amount
            if self.approved_amount is None:
                raise ValueError(
                    "Approved amount is required for approved requests"
                )
            
            # Shouldn't have rejection details
            if self.rejection_reason:
                raise ValueError(
                    "Rejection reason should not be present for approved requests"
                )
        else:
            # Rejected requests must have rejection reason
            if not self.rejection_reason:
                raise ValueError(
                    "Rejection reason is required for rejected requests"
                )
            
            if len(self.rejection_reason.strip()) < 20:
                raise ValueError(
                    "Rejection reason must be at least 20 characters"
                )
            
            # Shouldn't have approval details
            if self.approval_conditions or self.approved_amount:
                raise ValueError(
                    "Approval details should not be present for rejected requests"
                )
        
        return self


class ThresholdConfig(BaseSchema):
    """
    Approval threshold configuration for hostel.
    
    Defines cost limits and approval requirements for
    different authorization levels.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hostel_name": "North Campus Hostel A",
                "supervisor_approval_limit": "5000.00",
                "admin_approval_required_above": "5000.00",
                "auto_approve_below": "1000.00",
                "auto_approve_enabled": True,
                "emergency_bypass_threshold": True
            }
        }
    )

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    
    # Supervisor approval threshold
    supervisor_approval_limit: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        Decimal("5000.00"),
        description="Maximum amount supervisor can approve independently",
    )
    
    # Admin approval required above
    admin_approval_required_above: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        Decimal("5000.00"),
        description="Amount above which admin approval is required",
    )
    
    # Auto-approve threshold
    auto_approve_below: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        Decimal("1000.00"),
        description="Amount below which requests are auto-approved",
    )
    auto_approve_enabled: bool = Field(
        default=True,
        description="Whether auto-approval is enabled",
    )
    
    # Senior management threshold
    senior_management_required_above: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Amount requiring senior management approval",
    )
    
    # Emergency handling
    emergency_bypass_threshold: bool = Field(
        True,
        description="Allow emergency requests to bypass normal thresholds",
    )
    emergency_approval_limit: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Special limit for emergency approvals",
    )
    
    # Category-specific thresholds
    category_specific_limits: Optional[Dict[str, Decimal]] = Field(
        None,
        description="Custom limits per maintenance category",
    )
    
    # Approval workflow
    require_multiple_quotes_above: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Amount above which multiple quotes required",
    )
    minimum_quotes_required: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Minimum number of quotes for high-value work",
    )
    
    # Configuration metadata
    last_updated: datetime = Field(
        ...,
        description="Last configuration update",
    )
    updated_by: UUID = Field(
        ...,
        description="User who last updated configuration",
    )

    @field_validator(
        "supervisor_approval_limit",
        "admin_approval_required_above",
        "auto_approve_below",
        "senior_management_required_above",
        "emergency_approval_limit",
        "require_multiple_quotes_above",
    )
    @classmethod
    def round_amounts(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Round threshold amounts to 2 decimal places."""
        return round(v, 2) if v is not None else None

    @model_validator(mode="after")
    def validate_threshold_hierarchy(self) -> "ThresholdConfig":
        """
        Validate threshold amounts are in logical hierarchy.
        
        Auto-approve < Supervisor < Admin < Senior Management
        """
        # Auto-approve should be less than supervisor limit
        if self.auto_approve_below > self.supervisor_approval_limit:
            raise ValueError(
                "Auto-approve limit must be less than supervisor approval limit"
            )
        
        # Supervisor limit should equal admin threshold
        if self.supervisor_approval_limit != self.admin_approval_required_above:
            raise ValueError(
                "Supervisor approval limit should match admin required threshold"
            )
        
        # Senior management should be higher than admin
        if self.senior_management_required_above:
            if self.senior_management_required_above <= self.admin_approval_required_above:
                raise ValueError(
                    "Senior management threshold must be higher than admin threshold"
                )
        
        return self


class ApprovalWorkflow(BaseSchema):
    """
    Current approval workflow status.
    
    Tracks approval process state and pending actions.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "request_number": "MNT-2024-001",
                "estimated_cost": "7500.00",
                "threshold_exceeded": True,
                "requires_approval": True,
                "approval_pending": True,
                "approval_level_required": "admin"
            }
        }
    )

    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request unique identifier",
    )
    request_number: str = Field(
        ...,
        description="Request number",
    )
    
    # Cost information
    estimated_cost: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Estimated cost",
    )
    threshold_exceeded: bool = Field(
        ...,
        description="Whether cost exceeds threshold",
    )
    exceeded_threshold_type: Optional[str] = Field(
        None,
        pattern=r"^(supervisor|admin|senior_management)$",
        description="Which threshold was exceeded",
    )
    
    # Approval status
    requires_approval: bool = Field(
        ...,
        description="Whether approval is required",
    )
    approval_pending: bool = Field(
        ...,
        description="Whether approval is currently pending",
    )
    approval_level_required: Optional[str] = Field(
        None,
        pattern=r"^(supervisor|admin|senior_management)$",
        description="Required approval level",
    )
    
    # Current approver
    pending_with: Optional[UUID] = Field(
        None,
        description="User ID of current pending approver",
    )
    pending_with_name: Optional[str] = Field(
        None,
        description="Name of current pending approver",
    )
    pending_with_role: Optional[str] = Field(
        None,
        description="Role of pending approver",
    )
    
    # Timeline
    submitted_for_approval_at: Optional[datetime] = Field(
        None,
        description="When request was submitted for approval",
    )
    approval_deadline: Optional[datetime] = Field(
        None,
        description="Deadline for approval decision",
    )
    is_overdue: bool = Field(
        default=False,
        description="Whether approval is overdue",
    )
    
    # Previous approvals (for multi-level)
    previous_approvals: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Previous approval steps (for multi-level workflows)",
    )
    
    # Escalation
    escalation_count: int = Field(
        default=0,
        ge=0,
        description="Number of times escalated",
    )
    last_escalated_at: Optional[datetime] = Field(
        None,
        description="Last escalation timestamp",
    )

    @field_validator("estimated_cost")
    @classmethod
    def round_cost(cls, v: Decimal) -> Decimal:
        """Round cost to 2 decimal places."""
        return round(v, 2)


class RejectionRequest(BaseCreateSchema):
    """
    Reject maintenance approval request.
    
    Provides detailed rejection with alternatives and guidance.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "maintenance_id": "123e4567-e89b-12d3-a456-426614174000",
                "rejected_by": "123e4567-e89b-12d3-a456-426614174111",
                "rejection_reason": "Cost estimate is significantly higher than market rates. Please obtain additional quotes.",
                "rejection_category": "cost_too_high",
                "suggested_cost_reduction": "5000.00",
                "resubmission_allowed": True
            }
        }
    )

    maintenance_id: UUID = Field(
        ...,
        description="Maintenance request unique identifier",
    )
    rejected_by: UUID = Field(
        ...,
        description="User ID rejecting the request",
    )
    rejection_reason: str = Field(
        ...,
        min_length=20,
        max_length=1000,
        description="Detailed rejection reason",
    )
    rejection_category: Optional[str] = Field(
        None,
        pattern=r"^(cost_too_high|insufficient_justification|alternative_available|budget_constraints|not_urgent|other)$",
        description="Rejection category",
    )
    
    # Alternatives and suggestions
    suggested_alternative: Optional[str] = Field(
        None,
        max_length=500,
        description="Suggested alternative approach",
    )
    suggested_cost_reduction: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Suggested reduced cost amount",
    )
    suggested_vendor: Optional[str] = Field(
        None,
        max_length=255,
        description="Suggested alternative vendor",
    )
    
    # Resubmission guidance
    resubmission_allowed: bool = Field(
        default=True,
        description="Whether request can be resubmitted",
    )
    resubmission_requirements: Optional[str] = Field(
        None,
        max_length=1000,
        description="Requirements for resubmission",
    )
    
    # Notification
    notify_requester: bool = Field(
        default=True,
        description="Send rejection notification",
    )
    notify_supervisor: bool = Field(
        default=True,
        description="Notify supervisor",
    )

    @field_validator("rejection_reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate rejection reason is comprehensive."""
        v = v.strip()
        
        if len(v) < 20:
            raise ValueError(
                "Rejection reason must be at least 20 characters"
            )
        
        # Check for meaningful content
        if len(set(v.lower().replace(" ", ""))) < 10:
            raise ValueError(
                "Please provide a detailed and specific rejection reason"
            )
        
        return v

    @field_validator("suggested_cost_reduction")
    @classmethod
    def round_cost(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Round suggested cost to 2 decimal places."""
        return round(v, 2) if v is not None else None

    @model_validator(mode="after")
    def validate_resubmission_guidance(self) -> "RejectionRequest":
        """
        Validate resubmission guidance.
        
        If resubmission allowed, provide requirements.
        """
        if self.resubmission_allowed:
            # Should provide guidance on what needs to change
            if not any([
                self.suggested_alternative,
                self.suggested_cost_reduction,
                self.resubmission_requirements,
            ]):
                raise ValueError(
                    "Please provide guidance for resubmission (suggested alternative, "
                    "cost reduction, or specific requirements)"
                )
        
        return self