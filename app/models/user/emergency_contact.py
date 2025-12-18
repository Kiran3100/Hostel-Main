"""
Emergency Contact model configuration.
"""
from sqlalchemy import Boolean, Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.common.mixins import TimestampMixin, UUIDMixin

class EmergencyContact(BaseModel, UUIDMixin, TimestampMixin):
    """
    User emergency contact information.
    
    Manages emergency contact details with relationship tracking,
    verification, and priority ordering.
    """
    __tablename__ = "user_emergency_contacts"
    __table_args__ = (
        {"comment": "Emergency contact information for users"}
    )

    user_id = Column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False,
        index=True,
        comment="Foreign key to users table"
    )
    
    # Contact Information
    emergency_contact_name = Column(
        String(255), 
        nullable=False,
        comment="Full name of emergency contact"
    )
    emergency_contact_phone = Column(
        String(20), 
        nullable=False,
        comment="Primary phone number (E.164 format)"
    )
    emergency_contact_alternate_phone = Column(
        String(20), 
        nullable=True,
        comment="Alternate/secondary phone number"
    )
    emergency_contact_email = Column(
        String(255), 
        nullable=True,
        comment="Email address of emergency contact"
    )
    
    # Relationship Details
    emergency_contact_relation = Column(
        String(100), 
        nullable=False,
        comment="Relationship to user (Father, Mother, Spouse, etc.)"
    )
    
    # Priority & Ordering
    priority = Column(
        Integer, 
        default=1, 
        nullable=False,
        comment="Contact priority order (1 = highest)"
    )
    is_primary = Column(
        Boolean, 
        default=True, 
        nullable=False,
        comment="Primary emergency contact flag"
    )
    
    # Address (optional)
    contact_address = Column(
        Text, 
        nullable=True,
        comment="Physical address of emergency contact"
    )
    
    # Verification
    is_verified = Column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="Contact verification status"
    )
    verified_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Verification timestamp"
    )
    verification_method = Column(
        String(50), 
        nullable=True,
        comment="Verification method: phone_call, document, manual"
    )
    
    # Consent & Authorization
    consent_given = Column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="Consent to be contacted in emergencies"
    )
    consent_date = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Date consent was given"
    )
    
    # Authorization for specific actions
    can_make_decisions = Column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="Authorized to make decisions on behalf of user"
    )
    can_access_medical_info = Column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="Authorized to access medical information"
    )
    
    # Additional Information
    notes = Column(
        Text, 
        nullable=True,
        comment="Additional notes about emergency contact"
    )
    
    # Status
    is_active = Column(
        Boolean, 
        default=True, 
        nullable=False,
        comment="Active status flag"
    )
    
    # Communication Log
    last_contacted_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Last time this contact was reached"
    )
    contact_count = Column(
        Integer, 
        default=0, 
        nullable=False,
        comment="Number of times contacted in emergencies"
    )

    # Relationships
    user = relationship("User", back_populates="emergency_contact")

    def __repr__(self):
        return f"<EmergencyContact user_id={self.user_id} name={self.emergency_contact_name} relation={self.emergency_contact_relation}>"