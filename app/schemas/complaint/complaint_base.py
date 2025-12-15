"""
Core complaint schemas with enhanced validation and type safety.

This module provides base schemas for complaint creation, updates, and status management
with comprehensive field validation and business rule enforcement.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import ComplaintCategory, ComplaintStatus, Priority

__all__ = [
    "ComplaintBase",
    "ComplaintCreate",
    "ComplaintUpdate",
    "ComplaintStatusUpdate",
]


class ComplaintBase(BaseSchema):
    """
    Base complaint schema with core fields and validation.
    
    This schema defines the fundamental structure of a complaint including
    identification, categorization, priority, and location details.
    """
    model_config = ConfigDict(from_attributes=True)

    hostel_id: str = Field(
        ...,
        description="Hostel identifier where complaint originated",
    )
    raised_by: str = Field(
        ...,
        description="User ID who raised the complaint",
    )
    student_id: Optional[str] = Field(
        default=None,
        description="Student ID if complaint raised by a student",
    )

    # Complaint content
    title: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Brief complaint title/summary",
    )
    description: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="Detailed complaint description",
    )

    # Classification
    category: ComplaintCategory = Field(
        ...,
        description="Primary complaint category",
    )
    sub_category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional sub-category for finer classification",
    )

    # Priority
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Complaint priority level (defaults to medium)",
    )

    # Location details
    room_id: Optional[str] = Field(
        default=None,
        description="Room identifier if complaint is room-specific",
    )
    location_details: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Detailed location information within hostel",
    )

    # Attachments
    attachments: List[HttpUrl] = Field(
        default_factory=list,
        max_length=10,
        description="URLs of supporting documents/photos (max 10)",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """
        Validate and normalize complaint title.
        
        Ensures title is meaningful and properly formatted.
        """
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty or whitespace only")
        if v.isdigit():
            raise ValueError("Title cannot consist of only numbers")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """
        Validate and normalize complaint description.
        
        Ensures description provides sufficient detail.
        """
        v = v.strip()
        if not v:
            raise ValueError("Description cannot be empty or whitespace only")
        
        # Check for minimum word count (at least 5 words)
        word_count = len(v.split())
        if word_count < 5:
            raise ValueError(
                "Description must contain at least 5 words for clarity"
            )
        
        return v

    @field_validator("sub_category")
    @classmethod
    def validate_sub_category(cls, v: Optional[str]) -> Optional[str]:
        """Normalize sub-category if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @field_validator("location_details")
    @classmethod
    def validate_location_details(cls, v: Optional[str]) -> Optional[str]:
        """Normalize location details if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @field_validator("attachments")
    @classmethod
    def validate_attachments_limit(cls, v: List[HttpUrl]) -> List[HttpUrl]:
        """Ensure attachment count doesn't exceed limit."""
        if len(v) > 10:
            raise ValueError("Maximum 10 attachments allowed per complaint")
        return v

    @model_validator(mode="after")
    def validate_location_consistency(self) -> "ComplaintBase":
        """
        Validate location-related fields are consistent.
        
        If room_id is provided, location_details should also be provided
        for better context.
        """
        if self.room_id and not self.location_details:
            # This is a soft validation - log warning but don't fail
            pass
        
        return self


class ComplaintCreate(ComplaintBase, BaseCreateSchema):
    """
    Schema for creating a new complaint.
    
    Inherits all validation from ComplaintBase and adds any
    create-specific validation if needed.
    """
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_create_specific_rules(self) -> "ComplaintCreate":
        """
        Enforce creation-specific business rules.
        
        Additional validation that only applies during complaint creation.
        """
        # Ensure high/urgent priority complaints have location details
        if self.priority in [Priority.HIGH, Priority.URGENT, Priority.CRITICAL]:
            if not self.location_details and not self.room_id:
                raise ValueError(
                    f"High priority complaints ({self.priority.value}) "
                    "must include location details or room ID"
                )
        
        return self


class ComplaintUpdate(BaseUpdateSchema):
    """
    Schema for updating existing complaint.
    
    All fields are optional to support partial updates.
    Includes validation to ensure meaningful updates.
    """
    model_config = ConfigDict(from_attributes=True)

    title: Optional[str] = Field(
        default=None,
        min_length=5,
        max_length=255,
        description="Updated complaint title",
    )
    description: Optional[str] = Field(
        default=None,
        min_length=20,
        max_length=2000,
        description="Updated complaint description",
    )
    category: Optional[ComplaintCategory] = Field(
        default=None,
        description="Updated complaint category",
    )
    sub_category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Updated sub-category",
    )
    priority: Optional[Priority] = Field(
        default=None,
        description="Updated priority level",
    )
    location_details: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Updated location details",
    )
    attachments: Optional[List[HttpUrl]] = Field(
        default=None,
        max_length=10,
        description="Updated attachments list",
    )
    status: Optional[ComplaintStatus] = Field(
        default=None,
        description="Updated complaint status",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        """Validate title if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Title cannot be empty or whitespace only")
            if v.isdigit():
                raise ValueError("Title cannot consist of only numbers")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        """Validate description if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Description cannot be empty or whitespace only")
            
            word_count = len(v.split())
            if word_count < 5:
                raise ValueError(
                    "Description must contain at least 5 words for clarity"
                )
        return v

    @field_validator("attachments")
    @classmethod
    def validate_attachments_limit(cls, v: Optional[List[HttpUrl]]) -> Optional[List[HttpUrl]]:
        """Ensure attachment count doesn't exceed limit."""
        if v is not None and len(v) > 10:
            raise ValueError("Maximum 10 attachments allowed per complaint")
        return v

    @model_validator(mode="after")
    def validate_has_updates(self) -> "ComplaintUpdate":
        """
        Ensure at least one field is being updated.
        
        Prevents empty update requests.
        """
        update_fields = {
            k: v for k, v in self.model_dump(exclude_unset=True).items()
            if v is not None
        }
        
        if not update_fields:
            raise ValueError("At least one field must be provided for update")
        
        return self


class ComplaintStatusUpdate(BaseUpdateSchema):
    """
    Dedicated schema for complaint status updates.
    
    Provides focused status change functionality with
    mandatory change notes for audit trail.
    """
    model_config = ConfigDict(from_attributes=True)

    status: ComplaintStatus = Field(
        ...,
        description="New complaint status",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason or notes for status change",
    )

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        """Normalize status change notes."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @model_validator(mode="after")
    def validate_status_change_requirements(self) -> "ComplaintStatusUpdate":
        """
        Enforce business rules for status changes.
        
        Certain status transitions require mandatory notes.
        """
        # Statuses that require explanatory notes
        statuses_requiring_notes = {
            ComplaintStatus.REJECTED,
            ComplaintStatus.ON_HOLD,
            ComplaintStatus.CLOSED,
            ComplaintStatus.REOPENED,
        }
        
        if self.status in statuses_requiring_notes and not self.notes:
            raise ValueError(
                f"Status change to '{self.status.value}' requires explanatory notes"
            )
        
        return self