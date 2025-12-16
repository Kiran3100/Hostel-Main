"""
Complaint resolution and closure schemas.

Handles complaint resolution workflow including marking as resolved,
reopening, and final closure with comprehensive validation.
"""

from datetime import datetime
from datetime import date as Date
from typing import List, Union

from pydantic import ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "ResolutionRequest",
    "ResolutionResponse",
    "ResolutionUpdate",
    "ReopenRequest",
    "CloseRequest",
]


class ResolutionRequest(BaseCreateSchema):
    """
    Request to mark complaint as resolved.
    
    Requires detailed resolution notes and supports
    optional proof attachments and follow-up scheduling.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(
        ...,
        description="Complaint identifier to resolve",
    )

    resolution_notes: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="Detailed resolution description",
    )

    resolution_attachments: List[HttpUrl] = Field(
        default_factory=list,
        max_length=10,
        description="Proof of resolution (photos/documents)",
    )

    actual_resolution_time: Union[datetime, None] = Field(
        default=None,
        description="Actual time resolution was completed",
    )

    # Follow-up tracking
    follow_up_required: bool = Field(
        default=False,
        description="Whether follow-up check is needed",
    )
    follow_up_date: Union[Date, None] = Field(
        default=None,
        description="Scheduled follow-up Date",
    )
    follow_up_notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Follow-up instructions",
    )

    @field_validator("resolution_notes")
    @classmethod
    def validate_resolution_notes(cls, v: str) -> str:
        """Validate resolution notes quality."""
        v = v.strip()
        if not v:
            raise ValueError("Resolution notes cannot be empty")
        
        word_count = len(v.split())
        if word_count < 10:
            raise ValueError(
                "Resolution notes must contain at least 10 words "
                "for proper documentation"
            )
        
        return v

    @field_validator("resolution_attachments")
    @classmethod
    def validate_attachments_limit(cls, v: List[HttpUrl]) -> List[HttpUrl]:
        """Ensure attachment count doesn't exceed limit."""
        if len(v) > 10:
            raise ValueError(
                "Maximum 10 resolution attachments allowed"
            )
        return v

    @field_validator("follow_up_date")
    @classmethod
    def validate_follow_up_date(cls, v: Union[Date, None]) -> Union[Date, None]:
        """Ensure follow-up Date is in the future."""
        if v is not None and v <= Date.today():
            raise ValueError(
                "Follow-up Date must be in the future"
            )
        return v

    @model_validator(mode="after")
    def validate_follow_up_consistency(self):
        """
        Validate follow-up fields are consistent.
        
        If follow_up_required is True, follow_up_date must be provided.
        """
        if self.follow_up_required and not self.follow_up_date:
            raise ValueError(
                "Follow-up Date is required when follow-up is marked as needed"
            )
        
        return self


class ResolutionResponse(BaseSchema):
    """
    Response after successful complaint resolution.
    
    Provides confirmation and resolution metrics.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(..., description="Resolved complaint ID")
    complaint_number: str = Field(..., description="Complaint reference number")

    resolved: bool = Field(..., description="Resolution confirmation flag")
    resolved_at: datetime = Field(..., description="Resolution timestamp")
    resolved_by: str = Field(..., description="Resolver user ID")
    resolved_by_name: str = Field(..., description="Resolver name")

    resolution_notes: str = Field(..., description="Resolution description")

    # Performance metrics
    time_to_resolve_hours: int = Field(
        ...,
        ge=0,
        description="Total resolution time in hours",
    )
    sla_met: bool = Field(
        ...,
        description="Whether SLA was met for this resolution",
    )

    message: str = Field(
        ...,
        description="Confirmation message",
        examples=["Complaint resolved successfully"],
    )


class ResolutionUpdate(BaseCreateSchema):
    """
    Update resolution details for already resolved complaint.
    
    Allows modification of resolution notes and attachments.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(
        ...,
        description="Complaint identifier",
    )

    resolution_notes: Union[str, None] = Field(
        default=None,
        min_length=20,
        max_length=2000,
        description="Updated resolution notes",
    )
    resolution_attachments: Union[List[HttpUrl], None] = Field(
        default=None,
        max_length=10,
        description="Updated resolution attachments",
    )
    follow_up_notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Updated follow-up notes",
    )

    @field_validator("resolution_notes")
    @classmethod
    def validate_resolution_notes(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate resolution notes if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Resolution notes cannot be empty")
            
            word_count = len(v.split())
            if word_count < 10:
                raise ValueError(
                    "Resolution notes must contain at least 10 words"
                )
        
        return v

    @field_validator("resolution_attachments")
    @classmethod
    def validate_attachments_limit(
        cls,
        v: Union[List[HttpUrl], None]
    ) -> Union[List[HttpUrl], None]:
        """Ensure attachment count doesn't exceed limit."""
        if v is not None and len(v) > 10:
            raise ValueError(
                "Maximum 10 resolution attachments allowed"
            )
        return v

    @model_validator(mode="after")
    def validate_has_updates(self):
        """Ensure at least one field is being updated."""
        update_fields = {
            k: v for k, v in self.model_dump(exclude_unset=True).items()
            if v is not None and k != "complaint_id"
        }
        
        if not update_fields:
            raise ValueError(
                "At least one field must be provided for update"
            )
        
        return self


class ReopenRequest(BaseCreateSchema):
    """
    Request to reopen a resolved/closed complaint.
    
    Requires detailed reason and supports additional information.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(
        ...,
        description="Complaint identifier to reopen",
    )

    reopen_reason: str = Field(
        ...,
        min_length=20,
        max_length=500,
        description="Detailed reason for reopening",
    )

    additional_issues: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Additional issues discovered",
    )
    new_attachments: List[HttpUrl] = Field(
        default_factory=list,
        max_length=10,
        description="New supporting attachments",
    )

    @field_validator("reopen_reason")
    @classmethod
    def validate_reopen_reason(cls, v: str) -> str:
        """Validate reopen reason quality."""
        v = v.strip()
        if not v:
            raise ValueError("Reopen reason cannot be empty")
        
        word_count = len(v.split())
        if word_count < 5:
            raise ValueError(
                "Reopen reason must contain at least 5 words "
                "for proper documentation"
            )
        
        return v

    @field_validator("additional_issues")
    @classmethod
    def validate_additional_issues(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize additional issues if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @field_validator("new_attachments")
    @classmethod
    def validate_attachments_limit(cls, v: List[HttpUrl]) -> List[HttpUrl]:
        """Ensure attachment count doesn't exceed limit."""
        if len(v) > 10:
            raise ValueError(
                "Maximum 10 new attachments allowed"
            )
        return v


class CloseRequest(BaseCreateSchema):
    """
    Request to close complaint (final state).
    
    Optional closure notes and student confirmation.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(
        ...,
        description="Complaint identifier to close",
    )

    closure_notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Final closure notes",
    )

    student_confirmed: bool = Field(
        default=False,
        description="Student confirmed resolution satisfaction",
    )

    @field_validator("closure_notes")
    @classmethod
    def validate_closure_notes(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize closure notes if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v