"""
Student profile management schemas with enhanced validation.

Provides schemas for student profile creation, updates, document management,
and preference settings.
"""

from datetime import datetime
from typing import List, Union, Annotated

from pydantic import Field, HttpUrl, field_validator, model_validator, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import DietaryPreference, IDProofType

__all__ = [
    "StudentProfileCreate",
    "StudentProfileUpdate",
    "StudentDocuments",
    "DocumentInfo",
    "DocumentUploadRequest",
    "DocumentVerificationRequest",
    "StudentPreferences",
    "StudentPrivacySettings",
    "StudentBulkImport",
]


class StudentProfileCreate(BaseCreateSchema):
    """
    Create student profile (extends user registration).
    
    Used during student onboarding to collect student-specific information.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Guardian information (required for students)
    guardian_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Guardian/parent full name",
    )
    guardian_phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Guardian contact phone",
    )
    guardian_email: Union[str, None] = Field(
        default=None,
        description="Guardian email address",
    )
    guardian_relation: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Relation to student",
        examples=["Father", "Mother", "Uncle", "Guardian"],
    )
    guardian_address: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Guardian residential address",
    )

    # Institutional information (for students)
    institution_name: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Educational institution name",
    )
    course: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Course/program name",
    )
    year_of_study: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Current year/semester",
    )
    student_id_number: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="College/University ID",
    )

    # Employment information (for working professionals)
    company_name: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Employer name",
    )
    designation: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Job designation",
    )

    # ID proof
    id_proof_type: Union[IDProofType, None] = Field(
        default=None,
        description="Type of ID proof",
    )
    id_proof_number: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="ID proof number",
    )

    # Preferences
    dietary_preference: Union[DietaryPreference, None] = Field(
        default=None,
        description="Dietary preference",
    )
    food_allergies: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Food allergies and restrictions",
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
        return " ".join(v.split())

    @field_validator("guardian_phone")
    @classmethod
    def normalize_guardian_phone(cls, v: str) -> str:
        """Normalize guardian phone number."""
        return v.replace(" ", "").replace("-", "").strip()

    @field_validator("guardian_email")
    @classmethod
    def normalize_guardian_email(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize guardian email."""
        if v is not None:
            return v.lower().strip()
        return v

    @field_validator(
        "institution_name",
        "course",
        "company_name",
        "designation",
    )
    @classmethod
    def normalize_text_fields(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            return " ".join(v.split())
        return v

    @field_validator("id_proof_number")
    @classmethod
    def normalize_id_proof(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize ID proof number."""
        if v is not None:
            v = v.strip().upper()
            if not v:
                return None
            return " ".join(v.split())
        return v

    @model_validator(mode="after")
    def validate_student_or_professional(self) -> "StudentProfileCreate":
        """
        Validate that either institutional or employment info is provided.
        
        Students should be either studying or working.
        """
        has_institution = any(
            [
                self.institution_name,
                self.course,
                self.student_id_number,
            ]
        )
        has_employment = any([self.company_name, self.designation])

        if not has_institution and not has_employment:
            raise ValueError(
                "Either institutional information (for students) or "
                "employment information (for working professionals) must be provided"
            )

        return self


class StudentProfileUpdate(BaseUpdateSchema):
    """
    Update student profile.
    
    All fields optional for partial updates.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Guardian updates
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
    guardian_relation: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Guardian relation",
    )
    guardian_address: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Guardian address",
    )

    # Institutional updates
    institution_name: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Institution name",
    )
    course: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Course",
    )
    year_of_study: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Year of study",
    )
    student_id_number: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Student ID",
    )

    # Employment updates
    company_name: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Company name",
    )
    designation: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Designation",
    )

    # ID proof updates
    id_proof_type: Union[IDProofType, None] = Field(
        default=None,
        description="ID proof type",
    )
    id_proof_number: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="ID proof number",
    )

    # Preferences
    dietary_preference: Union[DietaryPreference, None] = Field(
        default=None,
        description="Dietary preference",
    )
    food_allergies: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Food allergies",
    )

    # Apply validators
    @field_validator("guardian_name")
    @classmethod
    def validate_guardian_name(cls, v: Union[str, None]) -> Union[str, None]:
        if v is not None:
            return StudentProfileCreate.validate_guardian_name(v)
        return v

    @field_validator("guardian_phone")
    @classmethod
    def normalize_guardian_phone(cls, v: Union[str, None]) -> Union[str, None]:
        if v is not None:
            return StudentProfileCreate.normalize_guardian_phone(v)
        return v

    @field_validator("guardian_email")
    @classmethod
    def normalize_guardian_email(cls, v: Union[str, None]) -> Union[str, None]:
        return StudentProfileCreate.normalize_guardian_email(v)

    @field_validator(
        "institution_name",
        "course",
        "company_name",
        "designation",
    )
    @classmethod
    def normalize_text_fields(cls, v: Union[str, None]) -> Union[str, None]:
        return StudentProfileCreate.normalize_text_fields(v)

    @field_validator("id_proof_number")
    @classmethod
    def normalize_id_proof(cls, v: Union[str, None]) -> Union[str, None]:
        return StudentProfileCreate.normalize_id_proof(v)


class DocumentInfo(BaseSchema):
    """
    Individual document information.
    
    Represents a single uploaded document with metadata.
    """

    id: str = Field(..., description="Document ID")
    document_type: str = Field(
        ...,
        description="Document category/type",
        examples=[
            "id_proof",
            "address_proof",
            "photo",
            "institutional_id",
            "company_id",
            "other",
        ],
    )
    document_name: str = Field(
        ...,
        description="Document display name",
    )
    document_url: HttpUrl = Field(
        ...,
        description="Document storage URL",
    )
    file_size_bytes: Union[int, None] = Field(
        default=None,
        ge=0,
        description="File size in bytes",
    )
    mime_type: Union[str, None] = Field(
        default=None,
        description="MIME type",
        examples=["application/pdf", "image/jpeg", "image/png"],
    )
    uploaded_at: datetime = Field(
        ...,
        description="Upload timestamp",
    )
    uploaded_by: str = Field(
        ...,
        description="User ID who uploaded",
    )

    # Verification
    verified: bool = Field(
        default=False,
        description="Verification status",
    )
    verified_by: Union[str, None] = Field(
        default=None,
        description="Admin who verified",
    )
    verified_at: Union[datetime, None] = Field(
        default=None,
        description="Verification timestamp",
    )
    verification_notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Verification notes",
    )

    # Expiry (for documents like ID proofs)
    expiry_date: Union[datetime, None] = Field(
        default=None,
        description="Document expiry date",
    )
    is_expired: bool = Field(
        default=False,
        description="Whether document is expired",
    )


class StudentDocuments(BaseSchema):
    """
    Student document collection.
    
    All documents associated with a student.
    """

    student_id: str = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    documents: List[DocumentInfo] = Field(
        default_factory=list,
        description="List of uploaded documents",
    )
    total_documents: int = Field(
        default=0,
        ge=0,
        description="Total document count",
    )
    verified_documents: int = Field(
        default=0,
        ge=0,
        description="Verified document count",
    )
    pending_verification: int = Field(
        default=0,
        ge=0,
        description="Pending verification count",
    )


class DocumentUploadRequest(BaseCreateSchema):
    """
    Upload document request.
    
    Used after file upload to register document in system.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    student_id: str = Field(
        ...,
        description="Student ID",
    )
    document_type: str = Field(
        ...,
        pattern=r"^(id_proof|address_proof|photo|institutional_id|company_id|other)$",
        description="Document type/category",
    )
    document_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Document name",
    )
    document_url: HttpUrl = Field(
        ...,
        description="Document URL (after upload to storage)",
    )
    file_size_bytes: Union[int, None] = Field(
        default=None,
        ge=0,
        le=10485760,  # 10MB
        description="File size in bytes (max 10MB)",
    )
    mime_type: Union[str, None] = Field(
        default=None,
        description="MIME type",
    )
    expiry_date: Union[datetime, None] = Field(
        default=None,
        description="Document expiry date (for ID proofs)",
    )
    notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Additional notes",
    )

    @field_validator("document_type")
    @classmethod
    def normalize_document_type(cls, v: str) -> str:
        """Normalize document type to lowercase."""
        return v.lower().strip()

    @field_validator("document_name")
    @classmethod
    def validate_document_name(cls, v: str) -> str:
        """Validate and normalize document name."""
        v = v.strip()
        if not v:
            raise ValueError("Document name cannot be empty")
        return " ".join(v.split())

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate MIME type is allowed."""
        if v is not None:
            allowed_types = [
                "application/pdf",
                "image/jpeg",
                "image/jpg",
                "image/png",
                "image/webp",
            ]
            if v.lower() not in allowed_types:
                raise ValueError(
                    f"MIME type must be one of: {', '.join(allowed_types)}"
                )
        return v

    @field_validator("expiry_date")
    @classmethod
    def validate_expiry_date(cls, v: Union[datetime, None]) -> Union[datetime, None]:
        """Validate expiry date is in the future."""
        if v is not None:
            if v < datetime.now():
                raise ValueError("Document expiry date cannot be in the past")
        return v


class DocumentVerificationRequest(BaseCreateSchema):
    """
    Verify document request.
    
    Used by admins to verify or reject uploaded documents.
    """

    document_id: str = Field(
        ...,
        description="Document ID to verify",
    )
    verified: bool = Field(
        ...,
        description="Verification status (true=verified, false=rejected)",
    )
    verification_notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Verification notes/comments",
    )
    reject_reason: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Rejection reason (if not verified)",
    )

    @model_validator(mode="after")
    def validate_rejection_reason(self) -> "DocumentVerificationRequest":
        """Require rejection reason if document is rejected."""
        if not self.verified and not self.reject_reason:
            raise ValueError(
                "Rejection reason is required when rejecting a document"
            )
        return self


class StudentPreferences(BaseUpdateSchema):
    """
    Student preferences and settings.
    
    Manages student-specific preferences for meal, notifications, etc.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Meal preferences
    mess_subscribed: Union[bool, None] = Field(
        default=None,
        description="Mess subscription status",
    )
    dietary_preference: Union[DietaryPreference, None] = Field(
        default=None,
        description="Dietary preference",
    )
    food_allergies: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Food allergies and restrictions",
    )

    # Meal plan preferences
    meal_plan_type: Union[str, None] = Field(
        default=None,
        pattern=r"^(full|breakfast_only|lunch_dinner|custom)$",
        description="Meal plan type",
    )
    skip_breakfast: bool = Field(
        default=False,
        description="Skip breakfast in meal plan",
    )
    skip_lunch: bool = Field(
        default=False,
        description="Skip lunch in meal plan",
    )
    skip_dinner: bool = Field(
        default=False,
        description="Skip dinner in meal plan",
    )

    # Notification preferences
    email_notifications: bool = Field(
        default=True,
        description="Enable email notifications",
    )
    sms_notifications: bool = Field(
        default=True,
        description="Enable SMS notifications",
    )
    push_notifications: bool = Field(
        default=True,
        description="Enable push notifications",
    )

    # Notification types
    payment_reminders: bool = Field(
        default=True,
        description="Receive payment reminders",
    )
    attendance_alerts: bool = Field(
        default=True,
        description="Receive attendance alerts",
    )
    announcement_notifications: bool = Field(
        default=True,
        description="Receive announcements",
    )
    complaint_updates: bool = Field(
        default=True,
        description="Receive complaint status updates",
    )
    event_notifications: bool = Field(
        default=True,
        description="Receive event notifications",
    )

    # Communication preferences
    preferred_language: str = Field(
        default="en",
        pattern=r"^(en|hi|ta|te|bn|mr|gu)$",
        description="Preferred language for communications",
    )
    preferred_contact_method: str = Field(
        default="email",
        pattern=r"^(email|sms|phone|whatsapp)$",
        description="Preferred contact method",
    )

    @field_validator("preferred_language", "preferred_contact_method")
    @classmethod
    def normalize_preferences(cls, v: str) -> str:
        """Normalize preference values."""
        return v.lower().strip()


class StudentPrivacySettings(BaseUpdateSchema):
    """
    Student privacy settings.
    
    Controls visibility of student information to others.
    """

    # Profile visibility
    show_profile_to_others: bool = Field(
        default=True,
        description="Show profile to other students",
    )
    show_room_number: bool = Field(
        default=True,
        description="Show room number in profile",
    )
    show_phone_number: bool = Field(
        default=False,
        description="Show phone number to other students",
    )
    show_email: bool = Field(
        default=False,
        description="Show email to other students",
    )
    show_institutional_info: bool = Field(
        default=True,
        description="Show college/company information",
    )

    # Contact permissions
    allow_roommate_contact: bool = Field(
        default=True,
        description="Allow roommates to view contact info",
    )
    allow_floormate_contact: bool = Field(
        default=True,
        description="Allow floormates to view contact info",
    )
    allow_hostelmate_contact: bool = Field(
        default=False,
        description="Allow all hostel residents to view contact info",
    )

    # Search visibility
    searchable_by_name: bool = Field(
        default=True,
        description="Allow search by name",
    )
    searchable_by_institution: bool = Field(
        default=True,
        description="Allow search by institution",
    )

    # Activity visibility
    show_last_seen: bool = Field(
        default=True,
        description="Show last seen/activity status",
    )
    show_attendance_to_others: bool = Field(
        default=False,
        description="Show attendance status to other students",
    )


class StudentBulkImport(BaseCreateSchema):
    """
    Bulk import students from file.
    
    Used for initial data migration or batch student registration.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    hostel_id: str = Field(
        ...,
        description="Hostel ID for all students",
    )
    import_file_url: HttpUrl = Field(
        ...,
        description="URL of uploaded CSV/Excel file",
    )
    file_type: str = Field(
        ...,
        pattern=r"^(csv|excel)$",
        description="File format",
    )
    skip_duplicates: bool = Field(
        default=True,
        description="Skip duplicate email/phone entries",
    )
    send_welcome_email: bool = Field(
        default=True,
        description="Send welcome email to imported students",
    )
    auto_generate_passwords: bool = Field(
        default=True,
        description="Auto-generate passwords for new users",
    )

    # Field mapping (if custom columns)
    field_mapping: Union[dict, None] = Field(
        default=None,
        description="Custom field mapping for CSV columns",
        examples=[
            {
                "Name": "full_name",
                "Email": "email",
                "Phone": "phone",
                "Guardian Name": "guardian_name",
            }
        ],
    )