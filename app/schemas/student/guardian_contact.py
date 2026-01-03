"""
Guardian contact schemas for API compatibility.

Provides schemas for managing guardian information as separate entities
while maintaining compatibility with the embedded guardian design in
the main student schemas.
"""

from typing import Union
from enum import Enum

from pydantic import Field, field_validator, model_validator, ConfigDict

from app.schemas.common.base import (
    BaseSchema,
    BaseCreateSchema,
    BaseUpdateSchema,
    BaseResponseSchema,
)

__all__ = [
    "GuardianRelationType",
    "GuardianContact",
    "GuardianContactCreate",
    "GuardianContactUpdate",
    "GuardianContactList",
]


class GuardianRelationType(str, Enum):
    """
    Guardian relation types.
    
    Defines the relationship between guardian and student.
    """
    
    FATHER = "father"
    MOTHER = "mother"
    LEGAL_GUARDIAN = "legal_guardian"
    UNCLE = "uncle"
    AUNT = "aunt"
    GRANDFATHER = "grandfather"
    GRANDMOTHER = "grandmother"
    BROTHER = "brother"
    SISTER = "sister"
    COUSIN = "cousin"
    FAMILY_FRIEND = "family_friend"
    OTHER = "other"


class GuardianContact(BaseResponseSchema):
    """
    Guardian contact response schema.
    
    Represents guardian information extracted from student records.
    Note: In the actual schema design, guardian info is embedded in student records,
    but this provides an API interface for guardian-specific operations.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
    )

    id: str = Field(..., description="Guardian contact ID (derived)")
    student_id: str = Field(..., description="Associated student ID")
    student_name: Union[str, None] = Field(
        default=None,
        description="Student name for reference",
    )

    # Guardian details
    guardian_name: str = Field(..., description="Guardian full name")
    guardian_phone: str = Field(..., description="Guardian contact phone")
    guardian_email: Union[str, None] = Field(
        default=None,
        description="Guardian email address",
    )
    guardian_relation: Union[GuardianRelationType, None] = Field(
        default=None,
        description="Relationship to student",
    )
    guardian_address: Union[str, None] = Field(
        default=None,
        description="Guardian residential address",
    )

    # Contact preferences
    is_primary: bool = Field(
        default=True,
        description="Whether this is the primary guardian contact",
    )
    is_emergency_contact: bool = Field(
        default=True,
        description="Whether to contact in emergencies",
    )
    preferred_contact_method: str = Field(
        default="phone",
        pattern=r"^(phone|email|sms|whatsapp)$",
        description="Preferred contact method",
    )

    # Alternative contact
    alternate_phone: Union[str, None] = Field(
        default=None,
        description="Alternative phone number",
    )
    work_phone: Union[str, None] = Field(
        default=None,
        description="Work phone number",
    )

    # Additional information
    occupation: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Guardian's occupation",
    )
    workplace_name: Union[str, None] = Field(
        default=None,
        max_length=200,
        description="Guardian's workplace",
    )
    workplace_address: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Workplace address",
    )

    # Verification status
    contact_verified: bool = Field(
        default=False,
        description="Whether contact details are verified",
    )
    last_contacted: Union[str, None] = Field(
        default=None,
        description="Last contact date",
    )

    # Notes
    notes: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Additional notes about guardian",
    )

    @property
    def formatted_address(self) -> str:
        """Get formatted address string."""
        if not self.guardian_address:
            return "Address not provided"
        return self.guardian_address.strip()

    @property
    def contact_methods(self) -> list[str]:
        """Get available contact methods."""
        methods = []
        if self.guardian_phone:
            methods.append("phone")
        if self.guardian_email:
            methods.append("email")
        if self.alternate_phone:
            methods.append("alternate_phone")
        if self.work_phone:
            methods.append("work_phone")
        return methods


class GuardianContactCreate(BaseCreateSchema):
    """
    Create guardian contact request.
    
    Used to add guardian information to a student record.
    This maps to updating the embedded guardian fields in the student schema.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Required fields
    guardian_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Guardian full name",
    )
    guardian_phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Guardian contact phone (E.164 format)",
    )

    # Optional contact details
    guardian_email: Union[str, None] = Field(
        default=None,
        description="Guardian email address",
    )
    guardian_relation: Union[GuardianRelationType, None] = Field(
        default=None,
        description="Relationship to student",
    )
    guardian_address: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Guardian residential address",
    )

    # Contact preferences
    is_primary: bool = Field(
        default=True,
        description="Set as primary guardian",
    )
    is_emergency_contact: bool = Field(
        default=True,
        description="Use as emergency contact",
    )
    preferred_contact_method: str = Field(
        default="phone",
        pattern=r"^(phone|email|sms|whatsapp)$",
        description="Preferred contact method",
    )

    # Additional contact numbers
    alternate_phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Alternative phone number",
    )
    work_phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Work phone number",
    )

    # Professional details
    occupation: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Guardian's occupation",
    )
    workplace_name: Union[str, None] = Field(
        default=None,
        max_length=200,
        description="Guardian's workplace",
    )
    workplace_address: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Workplace address",
    )

    # Notes
    notes: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Additional notes",
    )

    @field_validator("guardian_name")
    @classmethod
    def validate_guardian_name(cls, v: str) -> str:
        """Validate and normalize guardian name."""
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Guardian name must be at least 2 characters")
        if v.isdigit():
            raise ValueError("Guardian name cannot be only numbers")
        # Remove excessive whitespace
        v = " ".join(v.split())
        return v

    @field_validator("guardian_phone", "alternate_phone", "work_phone")
    @classmethod
    def normalize_phone_number(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize phone numbers."""
        if v is not None:
            return v.replace(" ", "").replace("-", "").strip()
        return v

    @field_validator("guardian_email")
    @classmethod
    def normalize_email(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize email address."""
        if v is not None:
            return v.lower().strip()
        return v

    @field_validator(
        "occupation",
        "workplace_name",
    )
    @classmethod
    def normalize_text_fields(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            # Remove excessive whitespace
            v = " ".join(v.split())
        return v


class GuardianContactUpdate(BaseUpdateSchema):
    """
    Update guardian contact information.
    
    All fields are optional for partial updates.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Contact details
    guardian_name: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=255,
        description="Guardian name",
    )
    guardian_phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Guardian phone",
    )
    guardian_email: Union[str, None] = Field(
        default=None,
        description="Guardian email",
    )
    guardian_relation: Union[GuardianRelationType, None] = Field(
        default=None,
        description="Guardian relation",
    )
    guardian_address: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Guardian address",
    )

    # Preferences
    is_primary: Union[bool, None] = Field(
        default=None,
        description="Primary guardian status",
    )
    is_emergency_contact: Union[bool, None] = Field(
        default=None,
        description="Emergency contact status",
    )
    preferred_contact_method: Union[str, None] = Field(
        default=None,
        pattern=r"^(phone|email|sms|whatsapp)$",
        description="Preferred contact method",
    )

    # Additional contacts
    alternate_phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Alternative phone",
    )
    work_phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Work phone",
    )

    # Professional details
    occupation: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Occupation",
    )
    workplace_name: Union[str, None] = Field(
        default=None,
        max_length=200,
        description="Workplace name",
    )
    workplace_address: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Workplace address",
    )

    # Notes
    notes: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Additional notes",
    )

    # Apply same validators as create schema
    @field_validator("guardian_name")
    @classmethod
    def validate_guardian_name(cls, v: Union[str, None]) -> Union[str, None]:
        if v is not None:
            return GuardianContactCreate.validate_guardian_name(v)
        return v

    @field_validator("guardian_phone", "alternate_phone", "work_phone")
    @classmethod
    def normalize_phone_number(cls, v: Union[str, None]) -> Union[str, None]:
        return GuardianContactCreate.normalize_phone_number(v)

    @field_validator("guardian_email")
    @classmethod
    def normalize_email(cls, v: Union[str, None]) -> Union[str, None]:
        return GuardianContactCreate.normalize_email(v)

    @field_validator("occupation", "workplace_name")
    @classmethod
    def normalize_text_fields(cls, v: Union[str, None]) -> Union[str, None]:
        return GuardianContactCreate.normalize_text_fields(v)


class GuardianContactList(BaseSchema):
    """
    Guardian contacts list response.
    
    Provides list of all guardian contacts for a student.
    """

    student_id: str = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    
    guardians: list[GuardianContact] = Field(
        default_factory=list,
        description="List of guardian contacts",
    )
    
    # Summary
    total_guardians: int = Field(
        default=0,
        ge=0,
        description="Total number of guardians",
    )
    primary_guardian_id: Union[str, None] = Field(
        default=None,
        description="ID of primary guardian",
    )
    verified_contacts: int = Field(
        default=0,
        ge=0,
        description="Number of verified contacts",
    )

    @property
    def has_primary_guardian(self) -> bool:
        """Check if student has a primary guardian."""
        return self.primary_guardian_id is not None

    @property
    def emergency_contacts(self) -> list[GuardianContact]:
        """Get list of emergency contacts."""
        return [g for g in self.guardians if g.is_emergency_contact]

    @property
    def verified_guardians(self) -> list[GuardianContact]:
        """Get list of verified guardians."""
        return [g for g in self.guardians if g.contact_verified]