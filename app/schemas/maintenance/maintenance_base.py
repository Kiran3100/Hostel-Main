# --- File: app/schemas/maintenance/maintenance_base.py ---
"""
Base maintenance schemas with comprehensive validation and type safety.

This module provides foundational schemas for maintenance request management
including creation, updates, and core validation logic.
"""

from __future__ import annotations

from datetime import date as Date
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import ConfigDict, Field, HttpUrl, field_validator, model_validator

from uuid import UUID

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import (
    MaintenanceCategory,
    MaintenanceIssueType,
    MaintenanceStatus,
    Priority,
)

__all__ = [
    "MaintenanceBase",
    "MaintenanceCreate",
    "MaintenanceUpdate",
    "MaintenanceStatusUpdate",
]


class MaintenanceBase(BaseSchema):
    """
    Base maintenance request schema with core fields.
    
    Provides common maintenance attributes and validation logic
    used across create/update operations.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hostel_id": "123e4567-e89b-12d3-a456-426614174000",
                "requested_by": "123e4567-e89b-12d3-a456-426614174111",
                "title": "Broken ceiling fan in room 101",
                "description": "The ceiling fan is not working and making unusual noise",
                "category": "electrical",
                "priority": "medium"
            }
        }
    )

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    requested_by: UUID = Field(
        ...,
        description="User ID who requested maintenance",
    )
    room_id: Optional[UUID] = Field(
        None,
        description="Room where issue exists (if applicable)",
    )

    # Request details
    title: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Brief issue summary",
    )
    description: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="Detailed issue description",
    )

    # Classification
    category: MaintenanceCategory = Field(
        ...,
        description="Maintenance category",
    )
    priority: Priority = Field(
        Priority.MEDIUM,
        description="Issue priority level",
    )
    issue_type: MaintenanceIssueType = Field(
        MaintenanceIssueType.ROUTINE,
        description="Type of maintenance issue",
    )

    # Location details
    location: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional location details",
    )
    floor: Optional[int] = Field(
        None,
        ge=0,
        le=50,
        description="Floor number (if applicable)",
    )
    specific_area: Optional[str] = Field(
        None,
        max_length=255,
        description="Specific area within location (e.g., bathroom, kitchen)",
    )

    # Attachments
    issue_photos: List[HttpUrl] = Field(
        default_factory=list,
        max_length=10,
        description="URLs to issue photographs",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """
        Validate and normalize title.
        
        Ensures title is meaningful and properly formatted.
        """
        v = v.strip()
        
        if len(v) < 5:
            raise ValueError("Title must be at least 5 characters")
        
        # Basic meaningfulness check
        if len(set(v.lower().replace(" ", ""))) < 3:
            raise ValueError("Title must be meaningful and descriptive")
        
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """
        Validate and normalize description.
        
        Ensures description provides adequate detail.
        """
        v = v.strip()
        
        if len(v) < 20:
            raise ValueError("Description must be at least 20 characters")
        
        # Check for meaningful content
        if len(set(v.lower().replace(" ", ""))) < 10:
            raise ValueError("Description must provide detailed information")
        
        return v

    @field_validator("location", "specific_area")
    @classmethod
    def normalize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Normalize text fields by stripping whitespace."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @field_validator("issue_photos")
    @classmethod
    def validate_photos(cls, v: List[HttpUrl]) -> List[HttpUrl]:
        """Validate photo URLs list."""
        if len(v) > 10:
            raise ValueError("Maximum 10 photos allowed per request")
        return v

    @model_validator(mode="after")
    def validate_priority_consistency(self) -> "MaintenanceBase":
        """
        Validate priority consistency with issue type.
        
        Emergency issues should have high/urgent priority.
        """
        if self.issue_type == MaintenanceIssueType.EMERGENCY:
            if self.priority not in [Priority.HIGH, Priority.URGENT, Priority.CRITICAL]:
                raise ValueError(
                    "Emergency issues must have HIGH, URGENT, or CRITICAL priority"
                )
        
        return self


class MaintenanceCreate(MaintenanceBase, BaseCreateSchema):
    """
    Create maintenance request with additional context.
    
    Extends base schema with creation-specific fields and validation.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hostel_id": "123e4567-e89b-12d3-a456-426614174000",
                "requested_by": "123e4567-e89b-12d3-a456-426614174111",
                "title": "Broken ceiling fan in room 101",
                "description": "The ceiling fan is not working and making unusual noise when switched on",
                "category": "electrical",
                "priority": "medium",
                "preferred_completion_date": "2024-12-31",
                "notify_on_completion": True
            }
        }
    )

    # Additional creation context
    preferred_completion_date: Optional[Date] = Field(
        None,
        description="Preferred completion Date (if any)",
    )
    notify_on_completion: bool = Field(
        default=True,
        description="Send notification when completed",
    )
    allow_cost_estimation: bool = Field(
        default=True,
        description="Allow supervisor to estimate costs",
    )

    @field_validator("preferred_completion_date")
    @classmethod
    def validate_completion_date(cls, v: Optional[Date]) -> Optional[Date]:
        """
        Validate preferred completion Date.
        
        Ensures Date is in the future and within reasonable range.
        """
        if v is not None:
            today = Date.today()
            
            # Can't be in the past
            if v < today:
                raise ValueError(
                    "Preferred completion Date cannot be in the past"
                )
            
            # Should be within reasonable timeframe (1 year)
            days_ahead = (v - today).days
            if days_ahead > 365:
                raise ValueError(
                    "Preferred completion Date cannot be more than 1 year ahead"
                )
        
        return v

    @model_validator(mode="after")
    def validate_emergency_urgency(self) -> "MaintenanceCreate":
        """
        Validate emergency requests have appropriate urgency.
        
        Emergency issues should have immediate preferred completion.
        """
        if self.issue_type == MaintenanceIssueType.EMERGENCY:
            if self.preferred_completion_date:
                days_ahead = (
                    self.preferred_completion_date - Date.today()
                ).days
                
                if days_ahead > 3:
                    raise ValueError(
                        "Emergency requests should have completion Date within 3 days"
                    )
        
        return self


class MaintenanceUpdate(BaseUpdateSchema):
    """
    Update maintenance request with partial fields.
    
    All fields are optional for flexible updates. Typically used
    to modify pending requests or add information during processing.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Updated: Broken ceiling fan in room 101",
                "priority": "high",
                "estimated_cost": "2500.00",
                "status": "in_progress"
            }
        }
    )

    title: Optional[str] = Field(
        None,
        min_length=5,
        max_length=255,
        description="Updated title",
    )
    description: Optional[str] = Field(
        None,
        min_length=20,
        max_length=2000,
        description="Updated description",
    )
    category: Optional[MaintenanceCategory] = Field(
        None,
        description="Updated category",
    )
    priority: Optional[Priority] = Field(
        None,
        description="Updated priority",
    )
    location: Optional[str] = Field(
        None,
        max_length=500,
        description="Updated location",
    )
    floor: Optional[int] = Field(
        None,
        ge=0,
        le=50,
        description="Updated floor",
    )
    specific_area: Optional[str] = Field(
        None,
        max_length=255,
        description="Updated specific area",
    )

    # Status
    status: Optional[MaintenanceStatus] = Field(
        None,
        description="Updated status (restricted to certain roles)",
    )

    # Cost information - Using Annotated for Decimal constraints in Pydantic v2
    estimated_cost: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Estimated repair cost",
    )
    actual_cost: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        None,
        description="Actual cost incurred",
    )

    # Timeline
    estimated_completion_date: Optional[Date] = Field(
        None,
        description="Estimated completion Date",
    )

    @field_validator("title", "description", "location", "specific_area")
    @classmethod
    def normalize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            if isinstance(v, str):
                # Different validation for different fields
                return v if v else None
        return None

    @field_validator("estimated_cost", "actual_cost")
    @classmethod
    def round_costs(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Round costs to 2 decimal places."""
        return round(v, 2) if v is not None else None

    @model_validator(mode="after")
    def validate_cost_consistency(self) -> "MaintenanceUpdate":
        """
        Validate cost fields consistency.
        
        Actual cost should not exceed estimated cost by too much.
        """
        if self.estimated_cost is not None and self.actual_cost is not None:
            # Allow 50% variance
            max_allowed = self.estimated_cost * Decimal("1.5")
            
            if self.actual_cost > max_allowed:
                raise ValueError(
                    f"Actual cost ({self.actual_cost}) exceeds estimated cost "
                    f"({self.estimated_cost}) by more than 50%"
                )
        
        return self


class MaintenanceStatusUpdate(BaseUpdateSchema):
    """
    Update maintenance status with tracking notes.
    
    Simplified schema for status transitions with audit trail.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "completed",
                "notes": "Work completed successfully, fan replaced",
                "notify_requester": True,
                "updated_by": "123e4567-e89b-12d3-a456-426614174111"
            }
        }
    )

    status: MaintenanceStatus = Field(
        ...,
        description="New maintenance status",
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Status change notes/reason",
    )
    notify_requester: bool = Field(
        default=True,
        description="Send notification to requester",
    )
    updated_by: UUID = Field(
        ...,
        description="User ID making the status change",
    )

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        """Normalize status notes."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_status_notes_requirement(self) -> "MaintenanceStatusUpdate":
        """
        Validate notes requirement for certain status changes.
        
        Rejection, cancellation require mandatory notes.
        """
        statuses_requiring_notes = {
            MaintenanceStatus.REJECTED,
            MaintenanceStatus.CANCELLED,
            MaintenanceStatus.ON_HOLD,
        }
        
        if self.status in statuses_requiring_notes:
            if not self.notes:
                raise ValueError(
                    f"Notes are required when changing status to {self.status.value}"
                )
            
            if len(self.notes.strip()) < 10:
                raise ValueError(
                    "Notes must be at least 10 characters for this status change"
                )
        
        return self