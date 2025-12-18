"""
Booking guest information models.

This module defines guest-specific information associated with bookings,
including contact details, identification, emergency contacts, and preferences.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.booking.booking import Booking

__all__ = [
    "BookingGuest",
    "GuestDocument",
]


class BookingGuest(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Guest information for bookings.
    
    Stores comprehensive guest details including personal information,
    contact details, identification, emergency contacts, and institutional
    or employment information.
    
    Attributes:
        booking_id: Reference to the booking (one-to-one)
        guest_name: Full name of the guest
        guest_email: Email address
        guest_phone: Contact phone number
        guest_id_proof_type: Type of ID proof
        guest_id_proof_number: ID proof number
        emergency_contact_name: Emergency contact person name
        emergency_contact_phone: Emergency contact phone
        emergency_contact_relation: Relationship to emergency contact
        institution_or_company: Educational institution or employer
        designation_or_course: Job designation or course
        permanent_address: Permanent residential address
        current_address: Current residential address
        date_of_birth: Guest date of birth
        gender: Guest gender
        nationality: Guest nationality
        guardian_name: Parent/guardian name (for minors)
        guardian_phone: Parent/guardian phone
        guardian_email: Parent/guardian email
        guardian_relation: Relationship to guardian
    """

    __tablename__ = "booking_guests"

    # Foreign Key (One-to-One with Booking)
    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to booking (one-to-one)",
    )

    # Basic Information
    guest_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Full name of the guest",
    )

    guest_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Guest email address",
    )

    guest_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Guest contact phone number",
    )

    # ID Proof Information
    guest_id_proof_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Type of ID proof (aadhaar, passport, driving_license, etc.)",
    )

    guest_id_proof_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="ID proof number",
    )

    id_proof_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether ID proof has been verified",
    )

    id_proof_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When ID proof was verified",
    )

    id_proof_verified_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who verified ID proof",
    )

    # Emergency Contact
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Emergency contact person name",
    )

    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Emergency contact phone number",
    )

    emergency_contact_relation: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Relationship to emergency contact",
    )

    # Institutional/Employment Details
    institution_or_company: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Educational institution or employer name",
    )

    designation_or_course: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Job designation or course/program",
    )

    # Address Information
    permanent_address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Permanent residential address",
    )

    current_address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Current residential address",
    )

    # Additional Personal Details
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Guest date of birth",
    )

    gender: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Guest gender",
    )

    nationality: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Guest nationality",
    )

    # Guardian Information (for minors or students)
    guardian_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Parent/guardian name",
    )

    guardian_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Parent/guardian phone",
    )

    guardian_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Parent/guardian email",
    )

    guardian_relation: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Relationship to guardian (father, mother, etc.)",
    )

    # Communication Preferences
    preferred_contact_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="email",
        comment="Preferred contact method (email, phone, sms)",
    )

    alternate_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Alternate contact phone number",
    )

    alternate_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Alternate email address",
    )

    # Privacy and Consent
    consent_for_communication: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Consent for promotional communication",
    )

    consent_for_data_sharing: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Consent for data sharing with third parties",
    )

    consent_given_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When consent was given",
    )

    # Additional Notes
    additional_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes about guest",
    )

    # Relationships
    booking: Mapped["Booking"] = relationship(
        "Booking",
        back_populates="guest_info",
    )

    documents: Mapped[list["GuestDocument"]] = relationship(
        "GuestDocument",
        back_populates="guest",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        Index("ix_guest_name", "guest_name"),
        Index("ix_guest_email", "guest_email"),
        Index("ix_guest_phone", "guest_phone"),
        Index("ix_guest_booking", "booking_id"),
        {"comment": "Guest information for bookings"},
    )

    # Validators
    @validates("guest_email", "alternate_email", "guardian_email")
    def validate_email(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate email format."""
        if value:
            value = value.strip().lower()
            if "@" not in value or "." not in value:
                raise ValueError(f"Invalid email format for {key}")
        return value

    @validates("guest_phone", "emergency_contact_phone", "guardian_phone", "alternate_phone")
    def validate_phone(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate and normalize phone number."""
        if value:
            # Remove common formatting characters
            value = value.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            if len(value) < 10:
                raise ValueError(f"Phone number too short for {key}")
        return value

    @validates("preferred_contact_method")
    def validate_contact_method(self, key: str, value: str) -> str:
        """Validate contact method."""
        valid_methods = {"email", "phone", "sms", "whatsapp"}
        if value.lower() not in valid_methods:
            raise ValueError(f"Invalid contact method. Must be one of {valid_methods}")
        return value.lower()

    # Properties
    @property
    def is_minor(self) -> bool:
        """Check if guest is a minor (under 18)."""
        if not self.date_of_birth:
            return False
        from datetime import datetime
        age = (datetime.utcnow() - self.date_of_birth).days // 365
        return age < 18

    @property
    def has_complete_profile(self) -> bool:
        """Check if guest profile is complete."""
        required_fields = [
            self.guest_name,
            self.guest_email,
            self.guest_phone,
            self.emergency_contact_name,
            self.emergency_contact_phone,
        ]
        return all(required_fields)

    @property
    def has_verified_id(self) -> bool:
        """Check if ID proof is verified."""
        return self.id_proof_verified

    # Methods
    def verify_id_proof(self, verified_by: UUID) -> None:
        """
        Mark ID proof as verified.
        
        Args:
            verified_by: ID of admin verifying the proof
        """
        self.id_proof_verified = True
        self.id_proof_verified_at = datetime.utcnow()
        self.id_proof_verified_by = verified_by

    def update_consent(self, communication: bool, data_sharing: bool) -> None:
        """
        Update consent preferences.
        
        Args:
            communication: Consent for communication
            data_sharing: Consent for data sharing
        """
        self.consent_for_communication = communication
        self.consent_for_data_sharing = data_sharing
        self.consent_given_at = datetime.utcnow()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<BookingGuest(booking_id={self.booking_id}, "
            f"name={self.guest_name}, email={self.guest_email})>"
        )


class GuestDocument(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Document storage for guest verification.
    
    Stores references to uploaded documents such as ID proofs,
    photos, and other verification documents.
    
    Attributes:
        guest_id: Reference to booking guest
        document_type: Type of document
        document_name: Original file name
        file_path: Storage path/URL
        file_size: File size in bytes
        mime_type: File MIME type
        is_verified: Whether document is verified
        verified_at: When document was verified
        verified_by: Admin who verified document
        expiry_date: Document expiry date (if applicable)
        notes: Additional notes about document
    """

    __tablename__ = "guest_documents"

    # Foreign Key
    guest_id: Mapped[UUID] = mapped_column(
        ForeignKey("booking_guests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to booking guest",
    )

    # Document Details
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of document (id_proof, photo, address_proof, etc.)",
    )

    document_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original file name",
    )

    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Storage path or URL",
    )

    file_size: Mapped[int] = mapped_column(
        nullable=False,
        comment="File size in bytes",
    )

    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="File MIME type",
    )

    # Verification
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether document is verified",
    )

    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When document was verified",
    )

    verified_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who verified document",
    )

    verification_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Verification notes",
    )

    # Expiry (for documents like ID proofs)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Document expiry date",
    )

    # Additional Information
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes about document",
    )

    # Relationships
    guest: Mapped["BookingGuest"] = relationship(
        "BookingGuest",
        back_populates="documents",
    )

    # Table Configuration
    __table_args__ = (
        Index("ix_document_guest_type", "guest_id", "document_type"),
        Index("ix_document_verified", "is_verified"),
        {"comment": "Guest document storage and verification"},
    )

    # Properties
    @property
    def is_expired(self) -> bool:
        """Check if document has expired."""
        if not self.expiry_date:
            return False
        return datetime.utcnow() > self.expiry_date

    @property
    def is_expiring_soon(self) -> bool:
        """Check if document is expiring within 30 days."""
        if not self.expiry_date:
            return False
        from datetime import timedelta
        return (self.expiry_date - datetime.utcnow()) < timedelta(days=30)

    # Methods
    def verify(self, verified_by: UUID, notes: Optional[str] = None) -> None:
        """
        Mark document as verified.
        
        Args:
            verified_by: ID of admin verifying the document
            notes: Optional verification notes
        """
        self.is_verified = True
        self.verified_at = datetime.utcnow()
        self.verified_by = verified_by
        if notes:
            self.verification_notes = notes

    def reject(self, verified_by: UUID, reason: str) -> None:
        """
        Reject document verification.
        
        Args:
            verified_by: ID of admin rejecting the document
            reason: Reason for rejection
        """
        self.is_verified = False
        self.verified_at = datetime.utcnow()
        self.verified_by = verified_by
        self.verification_notes = f"REJECTED: {reason}"

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<GuestDocument(id={self.id}, type={self.document_type}, "
            f"verified={self.is_verified})>"
        )