"""
Complaint escalation schemas with comprehensive tracking.

Handles complaint escalation workflow, auto-escalation rules,
and escalation history management.
"""

from datetime import datetime
from typing import List, Union

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema

__all__ = [
    "EscalationRequest",
    "EscalationResponse",
    "EscalationHistory",
    "EscalationEntry",
    "AutoEscalationRule",
]


class EscalationRequest(BaseCreateSchema):
    """
    Request to escalate complaint to higher authority.
    
    Requires detailed reason and supports priority increase
    and urgency flags.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(
        ...,
        description="Complaint identifier to escalate",
    )
    escalate_to: str = Field(
        ...,
        description="User ID to escalate to (admin/supervisor)",
    )

    escalation_reason: str = Field(
        ...,
        min_length=20,
        max_length=500,
        description="Detailed escalation reason",
    )

    increase_priority: bool = Field(
        default=True,
        description="Automatically increase priority level",
    )

    is_urgent: bool = Field(
        default=False,
        description="Mark as urgent escalation",
    )

    @field_validator("escalation_reason")
    @classmethod
    def validate_escalation_reason(cls, v: str) -> str:
        """Validate escalation reason quality."""
        v = v.strip()
        if not v:
            raise ValueError("Escalation reason cannot be empty")
        
        word_count = len(v.split())
        if word_count < 5:
            raise ValueError(
                "Escalation reason must contain at least 5 words "
                "for proper documentation"
            )
        
        return v


class EscalationResponse(BaseSchema):
    """
    Response after successful escalation.
    
    Provides confirmation and updated complaint details.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(..., description="Escalated complaint ID")
    complaint_number: str = Field(..., description="Complaint reference number")

    escalated: bool = Field(..., description="Escalation confirmation flag")
    escalated_to: str = Field(..., description="Escalated to user ID")
    escalated_to_name: str = Field(..., description="Escalated to name")
    escalated_by: str = Field(..., description="Escalator user ID")
    escalated_by_name: str = Field(..., description="Escalator name")
    escalated_at: datetime = Field(..., description="Escalation timestamp")

    new_priority: str = Field(
        ...,
        description="Updated priority level after escalation",
    )

    message: str = Field(
        ...,
        description="Confirmation message",
        examples=["Complaint escalated successfully"],
    )


class EscalationEntry(BaseResponseSchema):
    """
    Individual escalation entry in history.
    
    Tracks single escalation event with complete metadata.
    """
    model_config = ConfigDict(from_attributes=True)

    escalated_to: str = Field(..., description="Escalated to user ID")
    escalated_to_name: str = Field(..., description="Escalated to name")
    escalated_by: str = Field(..., description="Escalator user ID")
    escalated_by_name: str = Field(..., description="Escalator name")
    escalated_at: datetime = Field(..., description="Escalation timestamp")

    reason: str = Field(..., description="Escalation reason")

    # State before/after
    status_before: str = Field(..., description="Status before escalation")
    priority_before: str = Field(..., description="Priority before escalation")
    priority_after: str = Field(..., description="Priority after escalation")

    # Response tracking
    response_time_hours: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Time taken to respond (hours)",
    )
    resolved_after_escalation: bool = Field(
        ...,
        description="Whether resolved after this escalation",
    )


class EscalationHistory(BaseSchema):
    """
    Complete escalation history for a complaint.
    
    Provides audit trail of all escalations.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(..., description="Complaint ID")
    complaint_number: str = Field(..., description="Complaint reference number")

    escalations: List[EscalationEntry] = Field(
        default_factory=list,
        description="List of escalation entries",
    )
    total_escalations: int = Field(
        ...,
        ge=0,
        description="Total escalation count",
    )


class AutoEscalationRule(BaseSchema):
    """
    Auto-escalation rule configuration.
    
    Defines automatic escalation triggers based on time
    and SLA conditions.
    """
    model_config = ConfigDict(from_attributes=True)

    hostel_id: str = Field(
        ...,
        description="Hostel identifier for rule scope",
    )

    # Trigger conditions
    escalate_after_hours: int = Field(
        default=24,
        ge=1,
        le=168,  # Max 1 week
        description="Hours before auto-escalation (default 24)",
    )
    escalate_on_sla_breach: bool = Field(
        default=True,
        description="Auto-escalate on SLA breach",
    )

    # Priority-specific rules
    urgent_escalation_hours: int = Field(
        default=4,
        ge=1,
        le=24,
        description="Escalation threshold for urgent complaints (hours)",
    )
    high_escalation_hours: int = Field(
        default=12,
        ge=1,
        le=48,
        description="Escalation threshold for high priority (hours)",
    )
    medium_escalation_hours: int = Field(
        default=24,
        ge=1,
        le=72,
        description="Escalation threshold for medium priority (hours)",
    )

    # Escalation chain
    first_escalation_to: str = Field(
        ...,
        description="First level escalation target user ID",
    )
    second_escalation_to: Union[str, None] = Field(
        default=None,
        description="Second level escalation target (if first unresolved)",
    )

    is_active: bool = Field(
        default=True,
        description="Rule active status",
    )

    @model_validator(mode="after")
    def validate_escalation_thresholds(self):
        """
        Validate escalation time thresholds are logical.
        
        Ensures urgent < high < medium.
        """
        if not (
            self.urgent_escalation_hours
            < self.high_escalation_hours
            < self.medium_escalation_hours
        ):
            raise ValueError(
                "Escalation thresholds must follow: "
                "urgent < high < medium"
            )
        
        return self