"""
Inquiry status management schemas.

This module defines schemas for managing inquiry status changes,
assignments, timeline tracking, and follow-ups.
"""

from datetime import datetime
from typing import Dict, List, Union
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import InquiryStatus

__all__ = [
    "InquiryStatusUpdate",
    "InquiryAssignment",
    "InquiryFollowUp",
    "InquiryTimelineEntry",
    "InquiryConversion",
    "BulkInquiryStatusUpdate",
]


class InquiryStatusUpdate(BaseCreateSchema):
    """
    Update inquiry status with notes.
    
    Used to track status changes throughout the inquiry lifecycle.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "inquiry_id": "123e4567-e89b-12d3-a456-426614174000",
                "new_status": "contacted",
                "notes": "Spoke with visitor, they are interested in a single room",
                "updated_by": "123e4567-e89b-12d3-a456-426614174001"
            }
        }
    )

    inquiry_id: UUID = Field(
        ...,
        description="Inquiry ID to update",
    )
    new_status: InquiryStatus = Field(
        ...,
        description="New status to set",
    )
    notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Notes about status change",
    )

    # Metadata
    updated_by: Union[UUID, None] = Field(
        default=None,
        description="Admin updating the status",
    )

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, v: Union[str, None]) -> Union[str, None]:
        """Clean notes field."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v

    @model_validator(mode="after")
    def validate_status_transition(self) -> "InquiryStatusUpdate":
        """
        Validate status transition is logical.
        
        Note: This is a soft validation - enforces best practices
        but doesn't block unusual transitions (admin override).
        """
        # Define logical status transitions
        valid_transitions = {
            InquiryStatus.NEW: [
                InquiryStatus.CONTACTED,
                InquiryStatus.NOT_INTERESTED,
            ],
            InquiryStatus.CONTACTED: [
                InquiryStatus.INTERESTED,
                InquiryStatus.NOT_INTERESTED,
                InquiryStatus.CONVERTED,
            ],
            InquiryStatus.INTERESTED: [
                InquiryStatus.CONVERTED,
                InquiryStatus.NOT_INTERESTED,
            ],
            InquiryStatus.NOT_INTERESTED: [],  # Terminal state
            InquiryStatus.CONVERTED: [],  # Terminal state
        }
        
        # This validation would need access to current status
        # In practice, this would be validated at the service layer
        # where we have access to the current inquiry data
        
        return self


class InquiryAssignment(BaseCreateSchema):
    """
    Assign inquiry to an admin/staff member.
    
    Used for distributing inquiries among team members
    for follow-up.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "inquiry_id": "123e4567-e89b-12d3-a456-426614174000",
                "assigned_to": "123e4567-e89b-12d3-a456-426614174001",
                "assigned_by": "123e4567-e89b-12d3-a456-426614174002",
                "assignment_notes": "Please follow up with this visitor by end of day",
                "follow_up_due": "2024-01-16T17:00:00Z"
            }
        }
    )

    inquiry_id: UUID = Field(
        ...,
        description="Inquiry ID to assign",
    )
    assigned_to: UUID = Field(
        ...,
        description="Admin/staff member to assign to",
    )
    assigned_by: UUID = Field(
        ...,
        description="Admin making the assignment",
    )

    assignment_notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Notes about the assignment",
    )

    # Due Date for Follow-up
    follow_up_due: Union[datetime, None] = Field(
        default=None,
        description="When follow-up should be completed by",
    )

    @field_validator("assignment_notes")
    @classmethod
    def clean_notes(cls, v: Union[str, None]) -> Union[str, None]:
        """Clean assignment notes."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v

    @field_validator("follow_up_due")
    @classmethod
    def validate_follow_up_due(cls, v: Union[datetime, None]) -> Union[datetime, None]:
        """Validate follow-up due date."""
        if v is not None:
            if v < datetime.utcnow():
                raise ValueError("Follow-up due date cannot be in the past")
        return v


class InquiryFollowUp(BaseCreateSchema):
    """
    Record a follow-up action on an inquiry.
    
    Used to track all interactions with the visitor.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "inquiry_id": "123e4567-e89b-12d3-a456-426614174000",
                "followed_up_by": "123e4567-e89b-12d3-a456-426614174001",
                "contact_method": "phone",
                "contact_outcome": "connected",
                "notes": "Visitor confirmed interest in single room, will visit on Saturday",
                "next_follow_up_date": "2024-01-20T10:00:00Z"
            }
        }
    )

    inquiry_id: UUID = Field(
        ...,
        description="Inquiry ID",
    )
    followed_up_by: UUID = Field(
        ...,
        description="Admin who performed follow-up",
    )

    # Follow-up Details
    contact_method: str = Field(
        ...,
        pattern=r"^(phone|email|sms|whatsapp|in_person|other)$",
        description="Method of contact",
    )
    contact_outcome: str = Field(
        ...,
        pattern=r"^(connected|no_answer|voicemail|email_sent|interested|not_interested|callback_requested)$",
        description="Outcome of the follow-up attempt",
    )

    # Notes
    notes: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Detailed notes about the follow-up",
    )

    # Next Steps
    next_follow_up_date: Union[datetime, None] = Field(
        default=None,
        description="When next follow-up should occur",
    )

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: str) -> str:
        """Validate notes are meaningful."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Follow-up notes must be at least 10 characters")
        return v

    @field_validator("next_follow_up_date")
    @classmethod
    def validate_next_follow_up(cls, v: Union[datetime, None]) -> Union[datetime, None]:
        """Validate next follow-up date."""
        if v is not None:
            if v < datetime.utcnow():
                raise ValueError("Next follow-up date cannot be in the past")
        return v


class InquiryTimelineEntry(BaseSchema):
    """
    Timeline entry for inquiry lifecycle.
    
    Represents a single event in the inquiry's history.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "event_type": "status_change",
                "status": "contacted",
                "timestamp": "2024-01-15T14:30:00Z",
                "changed_by": "123e4567-e89b-12d3-a456-426614174001",
                "changed_by_name": "Admin User",
                "notes": "Made initial phone call to visitor"
            }
        }
    )

    event_type: str = Field(
        ...,
        pattern=r"^(status_change|assignment|follow_up|note_added|conversion)$",
        description="Type of timeline event",
    )
    status: Union[InquiryStatus, None] = Field(
        default=None,
        description="Status at this point (for status_change events)",
    )
    timestamp: datetime = Field(
        ...,
        description="When this event occurred",
    )
    changed_by: Union[UUID, None] = Field(
        default=None,
        description="Admin who triggered this event",
    )
    changed_by_name: Union[str, None] = Field(
        default=None,
        description="Name of admin who triggered event",
    )
    notes: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Notes about this event",
    )

    # Additional Context
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional event metadata",
    )


class InquiryConversion(BaseCreateSchema):
    """
    Record inquiry conversion to booking.
    
    Links inquiry to the resulting booking.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "inquiry_id": "123e4567-e89b-12d3-a456-426614174000",
                "booking_id": "123e4567-e89b-12d3-a456-426614174001",
                "converted_by": "123e4567-e89b-12d3-a456-426614174002",
                "conversion_notes": "Visitor booked a single room for 6 months starting March 1"
            }
        }
    )

    inquiry_id: UUID = Field(
        ...,
        description="Inquiry ID that converted",
    )
    booking_id: UUID = Field(
        ...,
        description="Resulting booking ID",
    )
    converted_by: UUID = Field(
        ...,
        description="Admin who facilitated conversion",
    )

    conversion_notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Notes about the conversion",
    )

    @field_validator("conversion_notes")
    @classmethod
    def clean_notes(cls, v: Union[str, None]) -> Union[str, None]:
        """Clean conversion notes."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class BulkInquiryStatusUpdate(BaseCreateSchema):
    """
    Update status of multiple inquiries.
    
    Used for batch operations on inquiries.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "inquiry_ids": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "123e4567-e89b-12d3-a456-426614174001"
                ],
                "new_status": "not_interested",
                "notes": "No response after multiple follow-up attempts",
                "updated_by": "123e4567-e89b-12d3-a456-426614174002"
            }
        }
    )

    inquiry_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of inquiry IDs to update (max 100)",
    )
    new_status: InquiryStatus = Field(
        ...,
        description="New status for all inquiries",
    )
    notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Common notes for all updates",
    )

    updated_by: UUID = Field(
        ...,
        description="Admin performing bulk update",
    )

    @field_validator("inquiry_ids")
    @classmethod
    def validate_inquiry_ids(cls, v: List[UUID]) -> List[UUID]:
        """Validate inquiry IDs list."""
        if len(v) == 0:
            raise ValueError("At least one inquiry ID is required")
        
        if len(v) > 100:
            raise ValueError("Maximum 100 inquiries can be updated at once")
        
        # Remove duplicates
        unique_ids = list(dict.fromkeys(v))
        
        return unique_ids

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, v: Union[str, None]) -> Union[str, None]:
        """Clean notes."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v