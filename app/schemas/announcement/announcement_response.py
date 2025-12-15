# --- File: app/schemas/announcement/announcement_response.py ---
"""
Announcement response schemas for API responses.

This module defines response schemas with varying levels of detail
for different use cases (list views, detail views, student views).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from pydantic import Field, computed_field, ConfigDict

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import (
    AnnouncementCategory,
    Priority,
    TargetAudience,
)

__all__ = [
    "AnnouncementResponse",
    "AnnouncementDetail",
    "AnnouncementList",
    "AnnouncementListItem",
    "StudentAnnouncementView",
    "AnnouncementSummary",
]


class AnnouncementResponse(BaseResponseSchema):
    """
    Standard announcement response schema.
    
    Used for basic announcement information after creation
    or simple fetch operations.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    # Hostel reference
    hostel_id: UUID = Field(
        ...,
        description="Associated hostel UUID",
    )
    hostel_name: str = Field(
        ...,
        description="Associated hostel name",
    )
    
    # Content
    title: str = Field(
        ...,
        description="Announcement title",
    )
    content: str = Field(
        ...,
        description="Announcement content/body",
    )
    
    # Classification
    category: AnnouncementCategory = Field(
        ...,
        description="Announcement category",
    )
    priority: Priority = Field(
        ...,
        description="Priority level",
    )
    
    # Visibility
    is_urgent: bool = Field(
        ...,
        description="Urgent flag",
    )
    is_pinned: bool = Field(
        ...,
        description="Pinned flag",
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
    
    # Publication status
    is_published: bool = Field(
        ...,
        description="Publication status",
    )
    published_at: Optional[datetime] = Field(
        None,
        description="Publication timestamp",
    )
    
    # Basic metrics
    total_recipients: int = Field(
        ...,
        ge=0,
        description="Total number of recipients",
    )
    read_count: int = Field(
        ...,
        ge=0,
        description="Number of recipients who read",
    )
    
    @computed_field
    @property
    def read_percentage(self) -> float:
        """Calculate read percentage."""
        if self.total_recipients == 0:
            return 0.0
        return round((self.read_count / self.total_recipients) * 100, 2)
    
    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if announcement is currently active."""
        if not self.is_published:
            return False
        # Check expiry from parent class if available
        return True


class AnnouncementDetail(BaseResponseSchema):
    """
    Detailed announcement view with complete information.
    
    Used for individual announcement detail pages with full
    metadata, delivery, and engagement information.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    # Hostel reference
    hostel_id: UUID = Field(
        ...,
        description="Associated hostel UUID",
    )
    hostel_name: str = Field(
        ...,
        description="Associated hostel name",
    )
    
    # Content
    title: str = Field(
        ...,
        description="Announcement title",
    )
    content: str = Field(
        ...,
        description="Announcement content/body",
    )
    category: AnnouncementCategory = Field(
        ...,
        description="Announcement category",
    )
    priority: Priority = Field(
        ...,
        description="Priority level",
    )
    
    # Visibility
    is_urgent: bool = Field(
        ...,
        description="Urgent flag",
    )
    is_pinned: bool = Field(
        ...,
        description="Pinned flag",
    )
    
    # Target audience
    target_audience: TargetAudience = Field(
        ...,
        description="Target audience type",
    )
    target_room_ids: list[UUID] = Field(
        default_factory=list,
        description="Targeted room UUIDs",
    )
    target_student_ids: list[UUID] = Field(
        default_factory=list,
        description="Targeted student UUIDs",
    )
    target_floor_numbers: list[int] = Field(
        default_factory=list,
        description="Targeted floor numbers",
    )
    
    # Attachments
    attachments: list[str] = Field(
        default_factory=list,
        description="Attachment URLs",
    )
    
    # Scheduling and expiry
    scheduled_publish_at: Optional[datetime] = Field(
        None,
        description="Scheduled publication time",
    )
    published_at: Optional[datetime] = Field(
        None,
        description="Actual publication time",
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Expiry timestamp",
    )
    is_published: bool = Field(
        ...,
        description="Publication status",
    )
    
    # Creator information
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
        description="Creator role (admin/supervisor)",
    )
    
    # Approval information
    requires_approval: bool = Field(
        ...,
        description="Whether approval was required",
    )
    approved_by: Optional[UUID] = Field(
        None,
        description="Approver UUID",
    )
    approved_by_name: Optional[str] = Field(
        None,
        description="Approver name",
    )
    approved_at: Optional[datetime] = Field(
        None,
        description="Approval timestamp",
    )
    
    # Delivery settings
    send_email: bool = Field(
        ...,
        description="Email notification enabled",
    )
    send_sms: bool = Field(
        ...,
        description="SMS notification enabled",
    )
    send_push: bool = Field(
        ...,
        description="Push notification enabled",
    )
    
    # Delivery timestamps
    email_sent_at: Optional[datetime] = Field(
        None,
        description="Email delivery timestamp",
    )
    sms_sent_at: Optional[datetime] = Field(
        None,
        description="SMS delivery timestamp",
    )
    push_sent_at: Optional[datetime] = Field(
        None,
        description="Push notification timestamp",
    )
    
    # Acknowledgment
    requires_acknowledgment: bool = Field(
        False,
        description="Whether acknowledgment is required",
    )
    acknowledgment_deadline: Optional[datetime] = Field(
        None,
        description="Acknowledgment deadline",
    )
    
    # Engagement metrics
    total_recipients: int = Field(
        ...,
        ge=0,
        description="Total recipients",
    )
    read_count: int = Field(
        ...,
        ge=0,
        description="Read count",
    )
    acknowledged_count: int = Field(
        0,
        ge=0,
        description="Acknowledgment count",
    )
    
    # Engagement rate - Using Annotated for Decimal constraints
    engagement_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Engagement rate percentage",
    )
    
    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if announcement has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    @computed_field
    @property
    def is_scheduled(self) -> bool:
        """Check if announcement is scheduled for future."""
        if self.scheduled_publish_at is None:
            return False
        return not self.is_published and self.scheduled_publish_at > datetime.utcnow()
    
    @computed_field
    @property
    def acknowledgment_rate(self) -> float:
        """Calculate acknowledgment rate."""
        if not self.requires_acknowledgment or self.total_recipients == 0:
            return 0.0
        return round((self.acknowledged_count / self.total_recipients) * 100, 2)
    
    @computed_field
    @property
    def pending_acknowledgments(self) -> int:
        """Calculate pending acknowledgments."""
        if not self.requires_acknowledgment:
            return 0
        return self.total_recipients - self.acknowledged_count
    
    @computed_field
    @property
    def days_until_expiry(self) -> Optional[int]:
        """Calculate days until expiry."""
        if self.expires_at is None:
            return None
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)


class AnnouncementListItem(BaseSchema):
    """
    Lightweight announcement schema for list views.
    
    Optimized for displaying announcements in tables and
    lists with minimal data transfer.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    hostel_id: UUID = Field(
        ...,
        description="Associated hostel UUID",
    )
    hostel_name: str = Field(
        ...,
        description="Associated hostel name",
    )
    
    # Content summary
    title: str = Field(
        ...,
        description="Announcement title",
    )
    category: AnnouncementCategory = Field(
        ...,
        description="Category",
    )
    priority: Priority = Field(
        ...,
        description="Priority",
    )
    
    # Visibility
    is_urgent: bool = Field(
        ...,
        description="Urgent flag",
    )
    is_pinned: bool = Field(
        ...,
        description="Pinned flag",
    )
    
    # Creator
    created_by_name: str = Field(
        ...,
        description="Creator name",
    )
    
    # Status
    is_published: bool = Field(
        ...,
        description="Publication status",
    )
    published_at: Optional[datetime] = Field(
        None,
        description="Publication timestamp",
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Expiry timestamp",
    )
    
    # Metrics
    read_count: int = Field(
        ...,
        ge=0,
        description="Read count",
    )
    total_recipients: int = Field(
        ...,
        ge=0,
        description="Total recipients",
    )
    
    # Timestamps
    created_at: datetime = Field(
        ...,
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
    )
    
    # For student view
    is_read: bool = Field(
        False,
        description="Whether current user has read (student view)",
    )
    
    @computed_field
    @property
    def read_percentage(self) -> float:
        """Calculate read percentage."""
        if self.total_recipients == 0:
            return 0.0
        return round((self.read_count / self.total_recipients) * 100, 2)
    
    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if announcement is active."""
        if not self.is_published:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True
    
    @computed_field
    @property
    def display_priority(self) -> int:
        """
        Calculate display priority score for sorting.
        
        Higher score = higher display priority.
        """
        score = 0
        
        # Pinned announcements at top
        if self.is_pinned:
            score += 1000
        
        # Urgent announcements next
        if self.is_urgent:
            score += 500
        
        # Priority scoring
        priority_scores = {
            Priority.CRITICAL: 100,
            Priority.URGENT: 80,
            Priority.HIGH: 60,
            Priority.MEDIUM: 40,
            Priority.LOW: 20,
        }
        score += priority_scores.get(self.priority, 0)
        
        return score


class AnnouncementList(BaseSchema):
    """
    Paginated list of announcements with summary statistics.
    
    Used for announcement listing endpoints with aggregated
    metadata for the current filter context.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    hostel_id: Optional[UUID] = Field(
        None,
        description="Hostel UUID if filtered by hostel",
    )
    hostel_name: Optional[str] = Field(
        None,
        description="Hostel name if filtered by hostel",
    )
    
    # Counts
    total_announcements: int = Field(
        ...,
        ge=0,
        description="Total announcements matching filter",
    )
    active_announcements: int = Field(
        ...,
        ge=0,
        description="Currently active announcements",
    )
    pinned_announcements: int = Field(
        ...,
        ge=0,
        description="Pinned announcements count",
    )
    urgent_announcements: int = Field(
        ...,
        ge=0,
        description="Urgent announcements count",
    )
    
    # Pending actions
    pending_approval: int = Field(
        0,
        ge=0,
        description="Announcements pending approval",
    )
    scheduled_count: int = Field(
        0,
        ge=0,
        description="Scheduled for future publication",
    )
    
    # Items
    announcements: list[AnnouncementListItem] = Field(
        default_factory=list,
        description="List of announcements",
    )
    
    @computed_field
    @property
    def has_urgent(self) -> bool:
        """Check if there are any urgent announcements."""
        return self.urgent_announcements > 0


class StudentAnnouncementView(BaseSchema):
    """
    Student-optimized announcement view.
    
    Simplified view for student-facing interfaces with
    read status and acknowledgment information.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    title: str = Field(
        ...,
        description="Announcement title",
    )
    content: str = Field(
        ...,
        description="Announcement content",
    )
    category: AnnouncementCategory = Field(
        ...,
        description="Category",
    )
    priority: Priority = Field(
        ...,
        description="Priority",
    )
    
    # Visibility
    is_urgent: bool = Field(
        ...,
        description="Urgent flag",
    )
    is_pinned: bool = Field(
        ...,
        description="Pinned flag",
    )
    
    # Attachments
    attachments: list[str] = Field(
        default_factory=list,
        description="Attachment URLs",
    )
    
    # Creator
    created_by_name: str = Field(
        ...,
        description="Creator name",
    )
    
    # Timestamps
    published_at: datetime = Field(
        ...,
        description="Publication timestamp",
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Expiry timestamp",
    )
    
    # Student-specific fields
    is_read: bool = Field(
        False,
        description="Whether student has read",
    )
    read_at: Optional[datetime] = Field(
        None,
        description="When student read the announcement",
    )
    
    # Acknowledgment
    requires_acknowledgment: bool = Field(
        False,
        description="Whether acknowledgment is required",
    )
    is_acknowledged: bool = Field(
        False,
        description="Whether student has acknowledged",
    )
    acknowledged_at: Optional[datetime] = Field(
        None,
        description="Acknowledgment timestamp",
    )
    acknowledgment_deadline: Optional[datetime] = Field(
        None,
        description="Acknowledgment deadline",
    )
    
    @computed_field
    @property
    def acknowledgment_overdue(self) -> bool:
        """Check if acknowledgment is overdue."""
        if not self.requires_acknowledgment:
            return False
        if self.is_acknowledged:
            return False
        if self.acknowledgment_deadline is None:
            return False
        return datetime.utcnow() > self.acknowledgment_deadline
    
    @computed_field
    @property
    def requires_action(self) -> bool:
        """Check if student action is required."""
        if self.requires_acknowledgment and not self.is_acknowledged:
            return True
        return False


class AnnouncementSummary(BaseSchema):
    """
    Minimal announcement summary for notifications and previews.
    
    Contains just enough information for notification display.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(
        ...,
        description="Announcement UUID",
    )
    title: str = Field(
        ...,
        description="Announcement title",
    )
    category: AnnouncementCategory = Field(
        ...,
        description="Category",
    )
    priority: Priority = Field(
        ...,
        description="Priority",
    )
    is_urgent: bool = Field(
        ...,
        description="Urgent flag",
    )
    content_preview: str = Field(
        ...,
        max_length=200,
        description="First 200 characters of content",
    )
    published_at: datetime = Field(
        ...,
        description="Publication timestamp",
    )
    created_by_name: str = Field(
        ...,
        description="Creator name",
    )