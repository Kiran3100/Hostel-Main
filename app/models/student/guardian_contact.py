# --- File: C:\Hostel-Main\app\models\student\guardian_contact.py ---
"""
Guardian contact model.

Manages guardian/parent contact information for students.
Supports multiple guardian contacts with priority and relationship tracking.
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.student.student import Student


class GuardianContact(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Guardian contact model.
    
    Stores detailed information about student guardians/parents.
    Students can have multiple guardians (father, mother, legal guardian, etc.)
    with different contact priorities for emergencies.
    
    Many-to-one relationship with Student.
    """

    __tablename__ = "guardian_contacts"

    # Foreign Key
    student_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to student",
    )

    # Guardian Information
    guardian_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Guardian full name",
    )
    
    relation: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Relation to student (Father, Mother, Uncle, Guardian, etc.)",
    )
    
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Primary guardian contact",
    )
    
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Contact priority (1=highest)",
    )

    # Contact Details
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Primary phone number",
    )
    
    alternate_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Alternate phone number",
    )
    
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Email address",
    )
    
    whatsapp_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="WhatsApp number",
    )

    # Address Information
    address_line1: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Address line 1",
    )
    
    address_line2: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Address line 2",
    )
    
    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="City",
    )
    
    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="State",
    )
    
    country: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="India",
        comment="Country",
    )
    
    pincode: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Postal/ZIP code",
    )

    # Occupation and Income (for scholarship/financial aid)
    occupation: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Occupation/profession",
    )
    
    employer_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Employer/company name",
    )
    
    annual_income: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Annual income range",
    )
    
    office_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Office phone number",
    )
    
    office_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Office address",
    )

    # Identification
    id_proof_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="ID proof type (Aadhaar, Passport, etc.)",
    )
    
    id_proof_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="ID proof number",
    )
    
    id_proof_document_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Uploaded ID proof document URL",
    )

    # Emergency Contact
    is_emergency_contact: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Can be contacted in emergency",
    )
    
    emergency_priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Emergency contact priority (1=first to contact)",
    )
    
    available_24x7: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Available 24x7 for emergency",
    )
    
    preferred_contact_time: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Preferred contact time (for non-emergency)",
    )

    # Authorization and Consent
    authorized_to_receive_updates: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Authorized to receive student updates",
    )
    
    authorized_for_pickup: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Authorized to pickup student",
    )
    
    can_approve_leaves: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Can approve leave applications",
    )
    
    financial_guardian: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Responsible for financial matters",
    )

    # Verification
    phone_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Phone number verified",
    )
    
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Email verified",
    )
    
    id_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="ID proof verified",
    )

    # Communication Preferences
    preferred_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        comment="Preferred communication language",
    )
    
    send_monthly_reports: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Send monthly progress reports",
    )
    
    send_payment_reminders: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Send payment reminders",
    )
    
    send_attendance_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Send attendance alerts",
    )

    # Additional Information
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes about guardian",
    )
    
    special_instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Special instructions for contacting",
    )

    # Photo
    photo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Guardian photo URL (for identification)",
    )

    # Relationship
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="guardian_contacts",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<GuardianContact(id={self.id}, student_id={self.student_id}, "
            f"name={self.guardian_name}, relation={self.relation})>"
        )

    @property
    def full_address(self) -> str | None:
        """Get formatted full address."""
        parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.state,
            self.country,
            self.pincode,
        ]
        
        address_parts = [part for part in parts if part]
        
        return ", ".join(address_parts) if address_parts else None

    @property
    def is_verified(self) -> bool:
        """Check if guardian is fully verified."""
        return (
            self.phone_verified
            and self.email_verified
            and self.id_verified
        )

    @property
    def contact_numbers(self) -> list[str]:
        """Get all contact numbers."""
        numbers = [self.phone]
        
        if self.alternate_phone:
            numbers.append(self.alternate_phone)
        
        if self.whatsapp_number and self.whatsapp_number not in numbers:
            numbers.append(self.whatsapp_number)
        
        if self.office_phone:
            numbers.append(self.office_phone)
        
        return numbers
