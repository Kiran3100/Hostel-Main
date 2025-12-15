# --- File: app/schemas/leave/leave_application.py ---
"""
Leave application and cancellation request schemas.

Provides schemas for student-initiated leave requests and cancellations
with comprehensive validation.
"""

from __future__ import annotations

from datetime import date as Date 
from typing import Optional

from pydantic import ConfigDict, Field, HttpUrl, field_validator, model_validator
from uuid import UUID

from app.schemas.common.base import BaseCreateSchema
from app.schemas.common.enums import LeaveType

__all__ = [
    "LeaveApplicationRequest",
    "LeaveCancellationRequest",
]


class LeaveApplicationRequest(BaseCreateSchema):
    """
    Student-initiated leave application request.
    
    Streamlined schema for students to apply for leave with
    automatic calculation and validation.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "hostel_id": "123e4567-e89b-12d3-a456-426614174001",
                "leave_type": "casual",
                "from_date": "2024-02-01",
                "to_date": "2024-02-05",
                "reason": "Family function - attending cousin's wedding ceremony",
                "contact_during_leave": "+919876543210",
                "destination_address": "123 Main Street, Mumbai, Maharashtra"
            }
        }
    )

    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    leave_type: LeaveType = Field(
        ...,
        description="Type of leave being requested",
    )
    from_date: Date = Field(
        ...,
        description="Leave start Date",
    )
    to_date: Date = Field(
        ...,
        description="Leave end Date",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Detailed reason for leave",
    )
    contact_during_leave: Optional[str] = Field(
        None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Contact phone number during leave",
    )
    emergency_contact: Optional[str] = Field(
        None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Emergency contact phone number",
    )
    emergency_contact_relation: Optional[str] = Field(
        None,
        max_length=50,
        description="Relation with emergency contact person",
    )
    supporting_document_url: Optional[HttpUrl] = Field(
        None,
        description="URL to supporting document",
    )
    destination_address: Optional[str] = Field(
        None,
        max_length=500,
        description="Destination address during leave",
    )
    expected_return_date: Optional[Date] = Field(
        None,
        description="Expected return Date (may differ from to_date)",
    )

    @field_validator("from_date")
    @classmethod
    def validate_from_date(cls, v: Date) -> Date:
        """
        Validate leave start Date.
        
        Students can apply for leave up to 30 days in advance
        or up to 7 days in the past (for backdated applications).
        """
        today = Date.today()
        
        # Allow backdated applications up to 7 days
        days_past = (today - v).days
        if days_past > 7:
            raise ValueError(
                "Cannot apply for leave starting more than 7 days in the past"
            )
        
        # Allow advance applications up to 30 days
        days_future = (v - today).days
        if days_future > 30:
            raise ValueError(
                "Cannot apply for leave more than 30 days in advance"
            )
        
        return v

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate leave reason is meaningful."""
        v = v.strip()
        
        if len(v) < 10:
            raise ValueError("Leave reason must be at least 10 characters")
        
        # Basic meaningfulness check
        if len(set(v.lower().replace(" ", ""))) < 5:
            raise ValueError("Please provide a detailed and meaningful reason")
        
        # Check for common placeholder/test text
        placeholder_patterns = [
            "test", "testing", "asdf", "qwerty", "aaaa", "bbbb",
            "xxxx", "leave", "urgent", "personal"
        ]
        
        reason_lower = v.lower()
        if any(
            pattern == reason_lower or reason_lower.startswith(pattern + " ")
            for pattern in placeholder_patterns
        ):
            if len(v) < 20:
                raise ValueError("Please provide a more detailed reason")
        
        return v

    @field_validator("contact_during_leave", "emergency_contact")
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone numbers."""
        if v is not None:
            return v.replace(" ", "").replace("-", "").strip()
        return None

    @field_validator("destination_address")
    @classmethod
    def validate_destination(cls, v: Optional[str]) -> Optional[str]:
        """Normalize destination address."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_leave_application(self) -> "LeaveApplicationRequest":
        """
        Validate complete leave application.
        
        Ensures:
        - Date range is valid
        - Duration meets requirements
        - Required documents are provided
        - Contact information is sufficient
        """
        # Validate Date range
        if self.to_date < self.from_date:
            raise ValueError("End Date must be after or equal to start Date")
        
        # Calculate duration
        total_days = (self.to_date - self.from_date).days + 1
        
        # Validate duration limits by leave type
        max_days_by_type = {
            LeaveType.CASUAL: 30,
            LeaveType.SICK: 60,
            LeaveType.EMERGENCY: 15,
            LeaveType.VACATION: 90,
            LeaveType.OTHER: 30,
        }
        
        max_allowed = max_days_by_type.get(self.leave_type, 30)
        if total_days > max_allowed:
            raise ValueError(
                f"{self.leave_type.value} leave cannot exceed {max_allowed} days"
            )
        
        # Document requirements
        if self.leave_type == LeaveType.SICK and total_days > 3:
            if not self.supporting_document_url:
                raise ValueError(
                    "Medical certificate required for sick leave exceeding 3 days"
                )
        
        if total_days > 15:
            if not self.supporting_document_url:
                raise ValueError(
                    "Supporting documentation required for leave exceeding 15 days"
                )
        
        # Contact information requirements
        if total_days > 7:
            if not self.contact_during_leave and not self.emergency_contact:
                raise ValueError(
                    "Contact information required for leave exceeding 7 days"
                )
        
        # Emergency contact for long leaves
        if total_days > 15 and not self.emergency_contact:
            raise ValueError(
                "Emergency contact required for leave exceeding 15 days"
            )
        
        # Validate expected return Date if provided
        if self.expected_return_date:
            if self.expected_return_date < self.to_date:
                raise ValueError(
                    "Expected return Date cannot be before leave end Date"
                )
            
            # Reasonable buffer (max 7 days after scheduled end)
            days_after = (self.expected_return_date - self.to_date).days
            if days_after > 7:
                raise ValueError(
                    "Expected return Date cannot be more than 7 days after leave end Date"
                )
        
        return self


class LeaveCancellationRequest(BaseCreateSchema):
    """
    Student request to cancel leave application.
    
    Allows students to cancel pending or approved leaves with
    proper justification.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "leave_id": "123e4567-e89b-12d3-a456-426614174000",
                "student_id": "123e4567-e89b-12d3-a456-426614174001",
                "cancellation_reason": "Family event has been postponed to next month",
                "immediate_return": False
            }
        }
    )

    leave_id: UUID = Field(
        ...,
        description="Leave application unique identifier",
    )
    student_id: UUID = Field(
        ...,
        description="Student unique identifier (for verification)",
    )
    cancellation_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for cancellation",
    )
    immediate_return: bool = Field(
        default=False,
        description="Whether student is returning immediately (for ongoing leaves)",
    )
    actual_return_date: Optional[Date] = Field(
        None,
        description="Actual return Date (for early return from ongoing leave)",
    )

    @field_validator("cancellation_reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate cancellation reason is meaningful."""
        v = v.strip()
        
        if len(v) < 10:
            raise ValueError(
                "Cancellation reason must be at least 10 characters"
            )
        
        # Basic meaningfulness check
        if len(set(v.lower().replace(" ", ""))) < 5:
            raise ValueError(
                "Please provide a detailed reason for cancellation"
            )
        
        return v

    @model_validator(mode="after")
    def validate_cancellation(self) -> "LeaveCancellationRequest":
        """
        Validate cancellation request consistency.
        
        Ensures immediate return and actual return Date are consistent.
        """
        # If immediate return, actual_return_date should be today or not provided
        if self.immediate_return:
            if self.actual_return_date:
                if self.actual_return_date > Date.today():
                    raise ValueError(
                        "immediate_return is True but actual_return_date is in future"
                    )
        
        # If actual_return_date provided, validate it's reasonable
        if self.actual_return_date:
            today = Date.today()
            
            # Can't be in future for cancellation
            if self.actual_return_date > today:
                raise ValueError(
                    "Actual return Date cannot be in the future"
                )
            
            # Shouldn't be too far in the past
            days_past = (today - self.actual_return_date).days
            if days_past > 30:
                raise ValueError(
                    "Actual return Date cannot be more than 30 days in the past"
                )
        
        return self