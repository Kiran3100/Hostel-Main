# --- File: app/schemas/announcement/announcement_base.py ---
"""
Base announcement schemas for creation and updates.

This module defines foundational schemas for announcements with
comprehensive validation and targeting capabilities.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import (
    Field,
    HttpUrl,
    field_validator,
    model_validator,
    ConfigDict,
)

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseSchema,
    BaseUpdateSchema,
)
from app.schemas.common.enums import (
    AnnouncementCategory,
    Priority,
    TargetAudience,
)

__all__ = [
    "AnnouncementBase",
    "AnnouncementCreate",
    "AnnouncementUpdate",
    "AnnouncementPublish",
    "AnnouncementUnpublish",
]


class AnnouncementBase(BaseSchema):
    """
    Base announcement schema with common fields.
    
    Contains all shared fields for announcement operations
    with comprehensive validation rules.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    hostel_id: UUID = Field(
        ...,
        description="UUID of the hostel this announcement belongs to",
    )
    
    # Content
    title: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Announcement title (5-255 characters)",
        examples=["Important: Maintenance Schedule Update"],
    )
    content: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Announcement content/body (10-5000 characters)",
    )
    
    # Classification
    category: AnnouncementCategory = Field(
        ...,
        description="Announcement category for organization",
    )
    priority: Priority = Field(
        Priority.MEDIUM,
        description="Priority level affecting display order",
    )
    
    # Visibility flags
    is_urgent: bool = Field(
        False,
        description="Mark as urgent for highlighted display",
    )
    is_pinned: bool = Field(
        False,
        description="Pin to top of announcement list",
    )
    
    # Target audience configuration
    target_audience: TargetAudience = Field(
        TargetAudience.ALL,
        description="Target audience type",
    )
    target_room_ids: list[UUID] = Field(
        default_factory=list,
        description="Specific room UUIDs when targeting specific rooms",
    )
    target_student_ids: list[UUID] = Field(
        default_factory=list,
        description="Specific student UUIDs for individual targeting",
    )
    target_floor_numbers: list[int] = Field(
        default_factory=list,
        description="Specific floor numbers when targeting floors",
    )
    
    # Attachments
    attachments: list[HttpUrl] = Field(
        default_factory=list,
        max_length=10,
        description="Attachment URLs (max 10)",
    )
    
    # Expiry
    expires_at: Optional[datetime] = Field(
        None,
        description="When the announcement expires and becomes inactive",
    )
    
    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Normalize and validate title."""
        # Strip and normalize whitespace
        normalized = " ".join(v.split())
        if len(normalized) < 5:
            raise ValueError("Title must be at least 5 characters after normalization")
        return normalized
    
    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate and clean content."""
        stripped = v.strip()
        if len(stripped) < 10:
            raise ValueError("Content must be at least 10 characters")
        return stripped
    
    @field_validator("target_floor_numbers")
    @classmethod
    def validate_floor_numbers(cls, v: list[int]) -> list[int]:
        """Validate floor numbers are positive and unique."""
        if v:
            if any(f < 0 for f in v):
                raise ValueError("Floor numbers must be non-negative")
            if len(v) != len(set(v)):
                raise ValueError("Duplicate floor numbers not allowed")
        return sorted(v)
    
    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure expiry is in the future."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("Expiry date must be in the future")
        return v
    
    @model_validator(mode="after")
    def validate_targeting(self) -> "AnnouncementBase":
        """Validate targeting configuration is consistent."""
        audience = self.target_audience
        
        if audience == TargetAudience.SPECIFIC_ROOMS and not self.target_room_ids:
            raise ValueError(
                "target_room_ids required when target_audience is SPECIFIC_ROOMS"
            )
        
        if audience == TargetAudience.SPECIFIC_FLOORS and not self.target_floor_numbers:
            raise ValueError(
                "target_floor_numbers required when target_audience is SPECIFIC_FLOORS"
            )
        
        if audience == TargetAudience.INDIVIDUAL and not self.target_student_ids:
            raise ValueError(
                "target_student_ids required when target_audience is INDIVIDUAL"
            )
        
        # Clear irrelevant targeting when audience is ALL
        if audience == TargetAudience.ALL:
            self.target_room_ids = []
            self.target_student_ids = []
            self.target_floor_numbers = []
        
        return self


class AnnouncementCreate(AnnouncementBase, BaseCreateSchema):
    """
    Schema for creating a new announcement.
    
    Includes creator information and delivery settings.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    created_by: UUID = Field(
        ...,
        description="UUID of the user creating the announcement (admin/supervisor)",
    )
    
    # Delivery channel settings
    send_email: bool = Field(
        False,
        description="Send email notification to recipients",
    )
    send_sms: bool = Field(
        False,
        description="Send SMS notification to recipients",
    )
    send_push: bool = Field(
        True,
        description="Send push notification to recipients",
    )
    
    # Scheduling
    scheduled_publish_at: Optional[datetime] = Field(
        None,
        description="Schedule for future publication (None = immediate)",
    )
    
    # Acknowledgment settings
    requires_acknowledgment: bool = Field(
        False,
        description="Whether recipients must acknowledge reading",
    )
    acknowledgment_deadline: Optional[datetime] = Field(
        None,
        description="Deadline for acknowledgment if required",
    )
    
    @field_validator("scheduled_publish_at")
    @classmethod
    def validate_schedule(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure scheduled time is in the future."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("Scheduled publish time must be in the future")
        return v
    
    @model_validator(mode="after")
    def validate_acknowledgment(self) -> "AnnouncementCreate":
        """Validate acknowledgment settings."""
        if self.requires_acknowledgment:
            if self.acknowledgment_deadline is None:
                raise ValueError(
                    "acknowledgment_deadline required when requires_acknowledgment is True"
                )
            if self.acknowledgment_deadline <= datetime.utcnow():
                raise ValueError("Acknowledgment deadline must be in the future")
            if self.expires_at and self.acknowledgment_deadline > self.expires_at:
                raise ValueError(
                    "Acknowledgment deadline cannot be after announcement expiry"
                )
        return self
    
    @model_validator(mode="after")
    def validate_at_least_one_channel(self) -> "AnnouncementCreate":
        """Ensure at least one delivery channel is enabled."""
        if not any([self.send_email, self.send_sms, self.send_push]):
            raise ValueError("At least one delivery channel must be enabled")
        return self


class AnnouncementUpdate(BaseUpdateSchema):
    """
    Schema for updating an existing announcement.
    
    All fields are optional for partial updates.
    Published announcements have restricted update capabilities.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    title: Optional[str] = Field(
        None,
        min_length=5,
        max_length=255,
        description="Updated announcement title",
    )
    content: Optional[str] = Field(
        None,
        min_length=10,
        max_length=5000,
        description="Updated announcement content",
    )
    category: Optional[AnnouncementCategory] = Field(
        None,
        description="Updated category",
    )
    priority: Optional[Priority] = Field(
        None,
        description="Updated priority level",
    )
    
    # Visibility
    is_urgent: Optional[bool] = Field(
        None,
        description="Update urgent flag",
    )
    is_pinned: Optional[bool] = Field(
        None,
        description="Update pinned flag",
    )
    
    # Expiry
    expires_at: Optional[datetime] = Field(
        None,
        description="Updated expiry datetime",
    )
    
    # Attachments
    attachments: Optional[list[HttpUrl]] = Field(
        None,
        max_length=10,
        description="Updated attachment list",
    )
    
    # Note: Targeting cannot be updated after creation
    # Note: Delivery channels cannot be changed after creation
    
    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        """Normalize title if provided."""
        if v is not None:
            normalized = " ".join(v.split())
            if len(normalized) < 5:
                raise ValueError("Title must be at least 5 characters")
            return normalized
        return v
    
    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure expiry is in the future."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("Expiry date must be in the future")
        return v
    
    @model_validator(mode="after")
    def validate_has_updates(self) -> "AnnouncementUpdate":
        """Ensure at least one field is being updated."""
        update_fields = [
            "title", "content", "category", "priority",
            "is_urgent", "is_pinned", "expires_at", "attachments"
        ]
        if not any(getattr(self, field) is not None for field in update_fields):
            raise ValueError("At least one field must be provided for update")
        return self


class AnnouncementPublish(BaseCreateSchema):
    """
    Schema for publishing a draft announcement.
    
    Allows immediate or scheduled publication.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="UUID of the announcement to publish",
    )
    published_by: UUID = Field(
        ...,
        description="UUID of the user publishing",
    )
    publish_immediately: bool = Field(
        True,
        description="Publish now or schedule for later",
    )
    scheduled_publish_at: Optional[datetime] = Field(
        None,
        description="Scheduled publication time if not immediate",
    )
    
    @model_validator(mode="after")
    def validate_publish_time(self) -> "AnnouncementPublish":
        """Validate publication timing."""
        if not self.publish_immediately and not self.scheduled_publish_at:
            raise ValueError(
                "scheduled_publish_at required when publish_immediately is False"
            )
        if self.scheduled_publish_at and self.scheduled_publish_at <= datetime.utcnow():
            raise ValueError("Scheduled publish time must be in the future")
        return self


class AnnouncementUnpublish(BaseCreateSchema):
    """
    Schema for unpublishing an announcement.
    
    Makes the announcement invisible but preserves it.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    announcement_id: UUID = Field(
        ...,
        description="UUID of the announcement to unpublish",
    )
    unpublished_by: UUID = Field(
        ...,
        description="UUID of the user unpublishing",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for unpublishing",
    )
    notify_recipients: bool = Field(
        False,
        description="Notify recipients about the unpublishing",
    )