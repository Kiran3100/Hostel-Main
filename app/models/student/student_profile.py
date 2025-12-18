# --- File: C:\Hostel-Main\app\models\student\student_profile.py ---
"""
Student profile model.

Extended student profile information beyond the core student entity.
Includes detailed personal, educational, and professional information.
"""

from datetime import date as Date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date as SQLDate,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin, AuditMixin

if TYPE_CHECKING:
    from app.models.student.student import Student


class StudentProfile(BaseModel, TimestampMixin, AuditMixin):
    """
    Extended student profile model.
    
    Stores additional student information that is not part of the
    core student entity. Provides comprehensive student details for
    better management and personalization.
    
    One-to-one relationship with Student.
    """

    __tablename__ = "student_profiles"

    # Foreign Key
    student_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
        comment="Reference to student",
    )

    # Personal Information
    date_of_birth: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Student date of birth",
    )
    
    age: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Calculated age",
    )
    
    blood_group: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Blood group (A+, B+, O+, etc.)",
    )
    
    height_cm: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Height in centimeters",
    )
    
    weight_kg: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Weight in kilograms",
    )
    
    nationality: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Nationality",
    )
    
    religion: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Religion",
    )
    
    caste_category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Caste category (General, OBC, SC, ST, etc.)",
    )
    
    marital_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Marital status",
    )
    
    languages_known: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Languages known (comma-separated)",
    )

    # Contact Preferences
    preferred_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        comment="Preferred language for communication",
    )
    
    preferred_contact_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="email",
        comment="Preferred contact method (email, phone, sms, whatsapp)",
    )
    
    alternate_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Alternate email address",
    )
    
    alternate_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Alternate phone number",
    )
    
    whatsapp_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="WhatsApp number",
    )

    # Permanent Address
    permanent_address_line1: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Permanent address line 1",
    )
    
    permanent_address_line2: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Permanent address line 2",
    )
    
    permanent_city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Permanent city",
    )
    
    permanent_state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Permanent state",
    )
    
    permanent_country: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="India",
        comment="Permanent country",
    )
    
    permanent_pincode: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Permanent pincode",
    )

    # Educational Details (Institutional Students)
    previous_institution: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Previous educational institution",
    )
    
    highest_qualification: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Highest educational qualification",
    )
    
    field_of_study: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Field of study/major",
    )
    
    academic_year: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Current academic year (2023-24, etc.)",
    )
    
    semester: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Current semester",
    )
    
    expected_graduation_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Expected graduation/completion date",
    )
    
    cgpa: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Current CGPA/percentage",
    )
    
    scholarship_holder: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether student has scholarship",
    )
    
    scholarship_details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Scholarship details",
    )

    # Employment Details (Working Professionals)
    employment_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Employment type (full-time, part-time, contract, intern)",
    )
    
    department: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Department/division",
    )
    
    years_of_experience: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total years of work experience",
    )
    
    joining_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Company joining date",
    )
    
    office_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Office address",
    )
    
    office_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Office phone number",
    )
    
    work_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Work email address",
    )
    
    reporting_manager_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Reporting manager name",
    )
    
    reporting_manager_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Reporting manager contact",
    )

    # Medical Information
    has_medical_conditions: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Has known medical conditions",
    )
    
    medical_conditions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Details of medical conditions",
    )
    
    medications: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Regular medications",
    )
    
    allergies: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Known allergies (medical)",
    )
    
    disabilities: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Physical or learning disabilities",
    )
    
    requires_special_accommodation: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Requires special accommodation",
    )
    
    special_accommodation_details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Details of special accommodation needed",
    )

    # Emergency Medical
    family_doctor_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Family doctor name",
    )
    
    family_doctor_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Family doctor contact",
    )
    
    health_insurance_provider: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Health insurance provider",
    )
    
    health_insurance_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Health insurance policy number",
    )

    # Hobbies and Interests
    hobbies: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Hobbies and interests",
    )
    
    sports_activities: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Sports and physical activities",
    )
    
    cultural_activities: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Cultural activities and participation",
    )
    
    clubs_memberships: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Club memberships and associations",
    )

    # Social Media (Optional)
    linkedin_profile: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="LinkedIn profile URL",
    )
    
    facebook_profile: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Facebook profile URL",
    )
    
    instagram_profile: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Instagram profile URL",
    )
    
    twitter_profile: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Twitter profile URL",
    )

    # Additional Information
    how_did_you_hear: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="How did you hear about the hostel",
    )
    
    referral_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Referral code used (if any)",
    )
    
    referred_by_student_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        comment="Student who referred (if any)",
    )
    
    bio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Short biography/introduction",
    )
    
    profile_completeness: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Profile completion percentage (0-100)",
    )

    # Preferences
    room_preference: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Room preferences",
    )
    
    roommate_preference: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Roommate preferences",
    )
    
    lifestyle_preferences: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Lifestyle preferences (early riser, night owl, etc.)",
    )

    # Relationship
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="profile",
        lazy="joined",
    )
    
    referred_by: Mapped["Student | None"] = relationship(
        "Student",
        foreign_keys=[referred_by_student_id],
        remote_side="Student.id",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<StudentProfile(id={self.id}, student_id={self.student_id})>"

    @property
    def full_permanent_address(self) -> str | None:
        """Get formatted permanent address."""
        parts = [
            self.permanent_address_line1,
            self.permanent_address_line2,
            self.permanent_city,
            self.permanent_state,
            self.permanent_country,
            self.permanent_pincode,
        ]
        
        address_parts = [part for part in parts if part]
        
        return ", ".join(address_parts) if address_parts else None

    @property
    def is_international_student(self) -> bool:
        """Check if student is from outside India."""
        return (
            self.permanent_country is not None
            and self.permanent_country.lower() != "india"
        )

    @property
    def has_complete_medical_info(self) -> bool:
        """Check if medical information is complete."""
        if self.has_medical_conditions:
            return bool(self.medical_conditions)
        return True
