"""
Complaint assignment and reassignment schemas.

Handles complaint assignment to staff members, reassignments,
bulk operations, and unassignment flows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "AssignmentRequest",
    "AssignmentResponse",
    "ReassignmentRequest",
    "BulkAssignment",
    "UnassignRequest",
    "AssignmentHistory",
]


class AssignmentRequest(BaseCreateSchema):
    """
    Request to assign complaint to a staff member.
    
    Supports optional estimated resolution time and notes
    for assignment context.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(
        ...,
        description="Complaint identifier to assign",
    )
    assigned_to: str = Field(
        ...,
        description="User ID of assignee (supervisor/staff)",
    )

    estimated_resolution_time: Optional[datetime] = Field(
        default=None,
        description="Estimated resolution timestamp",
    )

    assignment_notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Assignment context or instructions",
    )

    @field_validator("assignment_notes")
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        """Normalize assignment notes."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @field_validator("estimated_resolution_time")
    @classmethod
    def validate_estimated_time(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure estimated resolution time is in the future."""
        if v is not None:
            now = datetime.now(timezone.utc)
            # Handle timezone-naive datetime
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            if v <= now:
                raise ValueError(
                    "Estimated resolution time must be in the future"
                )
        return v


class AssignmentResponse(BaseSchema):
    """
    Response after successful complaint assignment.
    
    Provides confirmation details and assignment metadata.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(..., description="Assigned complaint ID")
    complaint_number: str = Field(..., description="Complaint reference number")

    assigned_to: str = Field(..., description="Assignee user ID")
    assigned_to_name: str = Field(..., description="Assignee name")
    assigned_by: str = Field(..., description="User who performed assignment")
    assigned_by_name: str = Field(..., description="Assigner name")

    assigned_at: datetime = Field(..., description="Assignment timestamp")

    message: str = Field(
        ...,
        description="Confirmation message",
        examples=["Complaint assigned successfully"],
    )


class ReassignmentRequest(BaseCreateSchema):
    """
    Request to reassign complaint to different staff member.
    
    Requires reason for reassignment to maintain audit trail.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(
        ...,
        description="Complaint identifier to reassign",
    )
    new_assigned_to: str = Field(
        ...,
        description="New assignee user ID",
    )

    reassignment_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for reassignment (mandatory)",
    )

    notify_previous_assignee: bool = Field(
        default=True,
        description="Send notification to previous assignee",
    )

    @field_validator("reassignment_reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate reassignment reason."""
        v = v.strip()
        if not v:
            raise ValueError("Reassignment reason cannot be empty")
        
        word_count = len(v.split())
        if word_count < 3:
            raise ValueError(
                "Reassignment reason must be at least 3 words"
            )
        
        return v


class BulkAssignment(BaseCreateSchema):
    """
    Bulk assignment of multiple complaints to one assignee.
    
    Useful for distributing workload efficiently.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of complaint IDs to assign (max 50)",
    )
    assigned_to: str = Field(
        ...,
        description="User ID of assignee for all complaints",
    )

    assignment_notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Common assignment notes",
    )

    @field_validator("complaint_ids")
    @classmethod
    def validate_complaint_ids_unique(cls, v: List[str]) -> List[str]:
        """Ensure complaint IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Complaint IDs must be unique")
        
        if len(v) > 50:
            raise ValueError("Cannot assign more than 50 complaints at once")
        
        return v

    @field_validator("assignment_notes")
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        """Normalize assignment notes."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class UnassignRequest(BaseCreateSchema):
    """
    Request to unassign complaint from current assignee.
    
    Requires reason for accountability.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(
        ...,
        description="Complaint identifier to unassign",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for unassignment",
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate unassignment reason."""
        v = v.strip()
        if not v:
            raise ValueError("Unassignment reason cannot be empty")
        
        word_count = len(v.split())
        if word_count < 3:
            raise ValueError(
                "Unassignment reason must be at least 3 words"
            )
        
        return v


class AssignmentHistory(BaseSchema):
    """
    Assignment history entry for audit trail.
    
    Tracks all assignment changes for a complaint.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(..., description="Complaint ID")
    
    assigned_to: str = Field(..., description="Assignee user ID")
    assigned_to_name: str = Field(..., description="Assignee name")
    
    assigned_by: str = Field(..., description="Assigner user ID")
    assigned_by_name: str = Field(..., description="Assigner name")
    
    assigned_at: datetime = Field(..., description="Assignment timestamp")
    unassigned_at: Optional[datetime] = Field(
        default=None,
        description="Unassignment timestamp",
    )
    
    reason: Optional[str] = Field(
        default=None,
        description="Assignment/reassignment reason",
    )
    
    duration_hours: Optional[int] = Field(
        default=None,
        ge=0,
        description="Duration assigned (hours)",
    )