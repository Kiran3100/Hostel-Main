# app/services/booking/booking_guest_service.py
"""
Booking guest service for guest information management.

Handles guest profile management, document verification, contact tracking,
and consent management.
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError, ValidationError
from app.repositories.booking.booking_guest_repository import (
    BookingGuestRepository,
    GuestDocumentRepository,
)
from app.repositories.base.base_repository import AuditContext


class BookingGuestService:
    """
    Service for booking guest information management.
    
    Responsibilities:
    - Manage guest profiles
    - Handle document uploads and verification
    - Track contact information
    - Manage consent preferences
    - Search and retrieve guest data
    """
    
    def __init__(
        self,
        session: Session,
        guest_repo: Optional[BookingGuestRepository] = None,
        document_repo: Optional[GuestDocumentRepository] = None,
    ):
        """Initialize guest service."""
        self.session = session
        self.guest_repo = guest_repo or BookingGuestRepository(session)
        self.document_repo = document_repo or GuestDocumentRepository(session)
    
    # ==================== GUEST PROFILE OPERATIONS ====================
    
    def create_guest_profile(
        self,
        booking_id: UUID,
        guest_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Create guest profile for a booking.
        
        Args:
            booking_id: Booking UUID
            guest_data: Guest information
            audit_context: Audit context
            
        Returns:
            Created guest profile dictionary
        """
        guest_data["booking_id"] = booking_id
        
        guest = self.guest_repo.create_guest_info(guest_data, audit_context)
        
        return self._guest_to_dict(guest)
    
    def update_guest_profile(
        self,
        guest_id: UUID,
        updates: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Update guest profile information.
        
        Args:
            guest_id: Guest UUID
            updates: Fields to update
            audit_context: Audit context
            
        Returns:
            Updated guest profile dictionary
        """
        guest = self.guest_repo.update(guest_id, updates, audit_context)
        
        return self._guest_to_dict(guest)
    
    def get_guest_by_booking(
        self,
        booking_id: UUID,
    ) -> Optional[Dict]:
        """
        Get guest information for a booking.
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            Guest profile dictionary or None
        """
        guest = self.guest_repo.find_by_booking(booking_id)
        if not guest:
            return None
        
        return self._guest_to_dict(guest, include_documents=True)
    
    def search_guests(
        self,
        search_term: str,
        hostel_id: Optional[UUID] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Search guests by name, email, or phone.
        
        Args:
            search_term: Search term
            hostel_id: Optional hostel filter
            limit: Result limit
            
        Returns:
            List of matching guest dictionaries
        """
        guests = self.guest_repo.search_guests(search_term, hostel_id, limit)
        return [self._guest_to_dict(g) for g in guests]
    
    def find_guests_by_email(
        self,
        email: str,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """Find guests by email address."""
        guests = self.guest_repo.find_by_email(email, limit)
        return [self._guest_to_dict(g) for g in guests]
    
    def find_guests_by_phone(
        self,
        phone: str,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """Find guests by phone number."""
        guests = self.guest_repo.find_by_phone(phone, limit)
        return [self._guest_to_dict(g) for g in guests]
    
    # ==================== ID VERIFICATION ====================
    
    def verify_guest_id(
        self,
        guest_id: UUID,
        verified_by_id: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Mark guest ID proof as verified.
        
        Args:
            guest_id: Guest UUID
            verified_by_id: Admin UUID
            audit_context: Audit context
            
        Returns:
            Updated guest profile dictionary
        """
        guest = self.guest_repo.verify_id_proof(guest_id, verified_by_id, audit_context)
        
        return self._guest_to_dict(guest)
    
    def get_unverified_ids(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """
        Get guests with unverified ID proofs.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of guest dictionaries
        """
        guests = self.guest_repo.find_unverified_ids(hostel_id)
        return [self._guest_to_dict(g) for g in guests]
    
    def get_incomplete_profiles(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Get guests with incomplete profiles."""
        guests = self.guest_repo.find_incomplete_profiles(hostel_id)
        return [self._guest_to_dict(g) for g in guests]
    
    def get_minors(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Get guests who are minors (under 18)."""
        guests = self.guest_repo.find_minors(hostel_id)
        return [self._guest_to_dict(g) for g in guests]
    
    # ==================== DOCUMENT MANAGEMENT ====================
    
    def add_guest_document(
        self,
        guest_id: UUID,
        document_type: str,
        document_name: str,
        file_path: str,
        file_size: int,
        mime_type: str,
        expiry_date: Optional[datetime] = None,
        notes: Optional[str] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Add document for a guest.
        
        Args:
            guest_id: Guest UUID
            document_type: Type of document
            document_name: Document filename
            file_path: Storage path
            file_size: File size in bytes
            mime_type: File MIME type
            expiry_date: Document expiry date
            notes: Additional notes
            audit_context: Audit context
            
        Returns:
            Created document dictionary
        """
        document_data = {
            "document_type": document_type,
            "document_name": document_name,
            "file_path": file_path,
            "file_size": file_size,
            "mime_type": mime_type,
            "expiry_date": expiry_date,
            "notes": notes,
        }
        
        document = self.document_repo.add_document(
            guest_id, document_data, audit_context
        )
        
        return self._document_to_dict(document)
    
    def verify_guest_document(
        self,
        document_id: UUID,
        verified_by_id: UUID,
        verification_notes: Optional[str] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Verify a guest document.
        
        Args:
            document_id: Document UUID
            verified_by_id: Admin UUID
            verification_notes: Verification notes
            audit_context: Audit context
            
        Returns:
            Updated document dictionary
        """
        document = self.document_repo.verify_document(
            document_id, verified_by_id, verification_notes, audit_context
        )
        
        return self._document_to_dict(document)
    
    def reject_guest_document(
        self,
        document_id: UUID,
        rejected_by_id: UUID,
        rejection_reason: str,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Reject a guest document.
        
        Args:
            document_id: Document UUID
            rejected_by_id: Admin UUID
            rejection_reason: Rejection reason
            audit_context: Audit context
            
        Returns:
            Updated document dictionary
        """
        document = self.document_repo.reject_document(
            document_id, rejected_by_id, rejection_reason, audit_context
        )
        
        return self._document_to_dict(document)
    
    def get_guest_documents(
        self,
        guest_id: UUID,
        document_type: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get all documents for a guest.
        
        Args:
            guest_id: Guest UUID
            document_type: Optional document type filter
            
        Returns:
            List of document dictionaries
        """
        documents = self.document_repo.find_by_guest(guest_id, document_type)
        return [self._document_to_dict(d) for d in documents]
    
    def get_unverified_documents(
        self,
        hostel_id: Optional[UUID] = None,
        document_type: Optional[str] = None,
    ) -> List[Dict]:
        """Get unverified guest documents."""
        documents = self.document_repo.find_unverified_documents(
            hostel_id, document_type
        )
        return [self._document_to_dict(d) for d in documents]
    
    def get_expiring_documents(
        self,
        days_ahead: int = 30,
        hostel_id: Optional[UUID] = None,
    ) -> List[Dict]:
        """Get documents expiring soon."""
        documents = self.document_repo.find_expiring_documents(days_ahead, hostel_id)
        return [self._document_to_dict(d) for d in documents]
    
    # ==================== CONSENT MANAGEMENT ====================
    
    def update_guest_consent(
        self,
        guest_id: UUID,
        communication_consent: bool,
        data_sharing_consent: bool,
        audit_context: Optional[AuditContext] = None,
    ) -> Dict:
        """
        Update guest consent preferences.
        
        Args:
            guest_id: Guest UUID
            communication_consent: Consent for communication
            data_sharing_consent: Consent for data sharing
            audit_context: Audit context
            
        Returns:
            Updated guest profile dictionary
        """
        guest = self.guest_repo.update_consent(
            guest_id, communication_consent, data_sharing_consent, audit_context
        )
        
        return self._guest_to_dict(guest)
    
    # ==================== HELPER METHODS ====================
    
    def _guest_to_dict(
        self,
        guest,
        include_documents: bool = False,
    ) -> Dict:
        """Convert guest model to dictionary."""
        result = {
            "id": str(guest.id),
            "booking_id": str(guest.booking_id),
            "guest_name": guest.guest_name,
            "guest_email": guest.guest_email,
            "guest_phone": guest.guest_phone,
            "guest_id_proof_type": guest.guest_id_proof_type,
            "guest_id_proof_number": guest.guest_id_proof_number,
            "id_proof_verified": guest.id_proof_verified,
            "id_proof_verified_at": (
                guest.id_proof_verified_at.isoformat()
                if guest.id_proof_verified_at
                else None
            ),
            "emergency_contact_name": guest.emergency_contact_name,
            "emergency_contact_phone": guest.emergency_contact_phone,
            "emergency_contact_relation": guest.emergency_contact_relation,
            "institution_or_company": guest.institution_or_company,
            "designation_or_course": guest.designation_or_course,
            "permanent_address": guest.permanent_address,
            "current_address": guest.current_address,
            "date_of_birth": (
                guest.date_of_birth.isoformat() if guest.date_of_birth else None
            ),
            "gender": guest.gender,
            "nationality": guest.nationality,
            "guardian_name": guest.guardian_name,
            "guardian_phone": guest.guardian_phone,
            "guardian_email": guest.guardian_email,
            "guardian_relation": guest.guardian_relation,
            "preferred_contact_method": guest.preferred_contact_method,
            "alternate_phone": guest.alternate_phone,
            "alternate_email": guest.alternate_email,
            "consent_for_communication": guest.consent_for_communication,
            "consent_for_data_sharing": guest.consent_for_data_sharing,
            "consent_given_at": (
                guest.consent_given_at.isoformat() if guest.consent_given_at else None
            ),
            "additional_notes": guest.additional_notes,
            # Computed properties
            "is_minor": guest.is_minor,
            "has_complete_profile": guest.has_complete_profile,
            "has_verified_id": guest.has_verified_id,
        }
        
        if include_documents:
            result["documents"] = [
                self._document_to_dict(doc) for doc in guest.documents
            ]
        
        return result
    
    def _document_to_dict(self, document) -> Dict:
        """Convert document model to dictionary."""
        return {
            "id": str(document.id),
            "guest_id": str(document.guest_id),
            "document_type": document.document_type,
            "document_name": document.document_name,
            "file_path": document.file_path,
            "file_size": document.file_size,
            "mime_type": document.mime_type,
            "is_verified": document.is_verified,
            "verified_at": (
                document.verified_at.isoformat() if document.verified_at else None
            ),
            "verified_by": str(document.verified_by) if document.verified_by else None,
            "verification_notes": document.verification_notes,
            "expiry_date": (
                document.expiry_date.isoformat() if document.expiry_date else None
            ),
            "notes": document.notes,
            "created_at": document.created_at.isoformat(),
            # Computed properties
            "is_expired": document.is_expired,
            "is_expiring_soon": document.is_expiring_soon,
        }