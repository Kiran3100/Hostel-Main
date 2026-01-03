"""
Hostel policy and rules management schemas.
"""

from datetime import datetime
from enum import Enum
from typing import Union, List
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseUpdateSchema,
    BaseResponseSchema
)
from app.schemas.common.enums import Priority

__all__ = [
    "PolicyType",
    "PolicyCreate",
    "PolicyUpdate", 
    "PolicyResponse",
    "PolicyAcknowledgment",
]


class PolicyType(str, Enum):
    """Policy type enumeration."""
    GENERAL = "general"
    SAFETY = "safety"
    VISITOR = "visitor"
    NOISE = "noise"
    CLEANLINESS = "cleanliness"
    PAYMENT = "payment"
    CANCELLATION = "cancellation"
    CHECK_IN_OUT = "check_in_out"
    DISCIPLINARY = "disciplinary"
    AMENITY_USAGE = "amenity_usage"


class PolicyCreate(BaseCreateSchema):
    """Create policy schema."""
    model_config = ConfigDict(from_attributes=True)
    
    hostel_id: UUID = Field(..., description="Hostel ID")
    policy_type: PolicyType = Field(..., description="Type of policy")
    title: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="Policy title"
    )
    content: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Policy content/description"
    )
    is_mandatory: bool = Field(
        default=True,
        description="Whether students must acknowledge this policy"
    )
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Policy priority level"
    )
    effective_from: Union[datetime, None] = Field(
        default=None,
        description="When this policy becomes effective"
    )
    valid_until: Union[datetime, None] = Field(
        default=None,
        description="When this policy expires"
    )
    applies_to_new_students: bool = Field(
        default=True,
        description="Apply to new student registrations"
    )
    applies_to_existing_students: bool = Field(
        default=False,
        description="Apply to existing students"
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Clean and validate policy content."""
        v = v.strip()
        if len(v.split()) < 5:
            raise ValueError("Policy content must contain at least 5 words")
        return v


class PolicyUpdate(BaseUpdateSchema):
    """Update policy schema."""
    model_config = ConfigDict(from_attributes=True)
    
    title: Union[str, None] = Field(
        default=None,
        min_length=5,
        max_length=200,
        description="Policy title"
    )
    content: Union[str, None] = Field(
        default=None,
        min_length=10,
        max_length=5000,
        description="Policy content"
    )
    is_mandatory: Union[bool, None] = Field(
        default=None,
        description="Mandatory acknowledgment requirement"
    )
    priority: Union[Priority, None] = Field(
        default=None,
        description="Policy priority"
    )
    effective_from: Union[datetime, None] = Field(
        default=None,
        description="Effective date"
    )
    valid_until: Union[datetime, None] = Field(
        default=None,
        description="Expiry date"
    )
    is_active: Union[bool, None] = Field(
        default=None,
        description="Active status"
    )
    applies_to_new_students: Union[bool, None] = Field(
        default=None,
        description="Apply to new students"
    )
    applies_to_existing_students: Union[bool, None] = Field(
        default=None,
        description="Apply to existing students"
    )


class PolicyResponse(BaseResponseSchema):
    """Policy response schema."""
    model_config = ConfigDict(from_attributes=True)
    
    hostel_id: UUID = Field(..., description="Hostel ID")
    policy_type: PolicyType = Field(..., description="Policy type")
    title: str = Field(..., description="Policy title")
    content: str = Field(..., description="Policy content")
    is_mandatory: bool = Field(..., description="Mandatory acknowledgment")
    priority: Priority = Field(..., description="Priority level")
    is_active: bool = Field(..., description="Active status")
    
    # Date fields
    effective_from: Union[datetime, None] = Field(
        default=None,
        description="Effective date"
    )
    valid_until: Union[datetime, None] = Field(
        default=None,
        description="Expiry date"
    )
    
    # Application scope
    applies_to_new_students: bool = Field(..., description="Apply to new students")
    applies_to_existing_students: bool = Field(..., description="Apply to existing students")
    
    # Statistics
    total_acknowledgments: int = Field(
        default=0,
        ge=0,
        description="Total acknowledgments received"
    )
    pending_acknowledgments: int = Field(
        default=0,
        ge=0,
        description="Students who need to acknowledge"
    )
    
    # Metadata
    created_by: Union[UUID, None] = Field(default=None, description="Creator")
    last_modified_by: Union[UUID, None] = Field(default=None, description="Last modifier")
    version: int = Field(default=1, ge=1, description="Policy version")


class PolicyAcknowledgment(BaseResponseSchema):
    """Policy acknowledgment schema."""
    model_config = ConfigDict(from_attributes=True)
    
    policy_id: UUID = Field(..., description="Policy ID")
    user_id: UUID = Field(..., description="User who acknowledged")
    policy_title: str = Field(..., description="Policy title at time of acknowledgment")
    policy_version: int = Field(..., description="Policy version acknowledged")
    acknowledged_at: datetime = Field(..., description="Acknowledgment timestamp")
    ip_address: Union[str, None] = Field(default=None, description="User's IP address")
    user_agent: Union[str, None] = Field(default=None, description="User's browser info")
    
    # User info (for admin views)
    user_name: Union[str, None] = Field(default=None, description="User's name")
    user_email: Union[str, None] = Field(default=None, description="User's email")