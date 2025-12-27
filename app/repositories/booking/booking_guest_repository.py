# app/repositories/booking/booking_guest_repository.py
"""
Booking guest repository for guest information management.

Provides guest profile management, document handling, verification,
and contact information tracking.
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core1.exceptions import EntityNotFoundError, ValidationError
from app.models.booking.booking_guest import BookingGuest, GuestDocument
from app.models.booking.booking import Booking
from app.repositories.base.base_repository import (
    AuditContext,
    BaseRepository,
    QueryOptions,
)


class BookingGuestRepository(BaseRepository[BookingGuest]):
    """
    Repository for booking guest operations.
    
    Provides:
    - Guest profile management
    - Contact information tracking
    - ID verification
    - Consent management
    - Guest analytics
    """
    
    def __init__(self, session: Session):
        """Initialize guest repository."""
        super().__init__(session, BookingGuest)
    
    # ==================== GUEST OPERATIONS ====================
    
    def create_guest_info(
        self,
        guest_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingGuest:
        """
        Create guest information for a booking.
        
        Args:
            guest_data: Guest information
            audit_context: Audit context
            
        Returns:
            Created guest record
        """
        guest = BookingGuest(**guest_data)
        return self.create(guest, audit_context)
    
    def find_by_booking(self, booking_id: UUID) -> Optional[BookingGuest]:
        """
        Find guest information for a booking.
        
        Args:
            booking_id: Booking UUID
            
        Returns:
            Guest information if found
        """
        query = select(BookingGuest).where(
            BookingGuest.booking_id == booking_id
        ).where(
            BookingGuest.deleted_at.is_(None)
        ).options(
            joinedload(BookingGuest.booking),
            selectinload(BookingGuest.documents),
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()
    
    def find_by_email(
        self,
        email: str,
        limit: Optional[int] = None,
    ) -> List[BookingGuest]:
        """
        Find guests by email address.
        
        Args:
            email: Email address
            limit: Optional result limit
            
        Returns:
            List of matching guests
        """
        query = select(BookingGuest).where(
            BookingGuest.guest_email == email.lower()
        ).where(
            BookingGuest.deleted_at.is_(None)
        ).options(
            joinedload(BookingGuest.booking),
        ).order_by(
            BookingGuest.created_at.desc()
        )
        
        if limit:
            query = query.limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_by_phone(
        self,
        phone: str,
        limit: Optional[int] = None,
    ) -> List[BookingGuest]:
        """
        Find guests by phone number.
        
        Args:
            phone: Phone number
            limit: Optional result limit
            
        Returns:
            List of matching guests
        """
        # Normalize phone number
        normalized_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        query = select(BookingGuest).where(
            BookingGuest.guest_phone.like(f"%{normalized_phone}%")
        ).where(
            BookingGuest.deleted_at.is_(None)
        ).options(
            joinedload(BookingGuest.booking),
        ).order_by(
            BookingGuest.created_at.desc()
        )
        
        if limit:
            query = query.limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def search_guests(
        self,
        search_term: str,
        hostel_id: Optional[UUID] = None,
        limit: int = 50,
    ) -> List[BookingGuest]:
        """
        Search guests by name, email, or phone.
        
        Args:
            search_term: Search term
            hostel_id: Optional hostel filter
            limit: Result limit
            
        Returns:
            List of matching guests
        """
        query = select(BookingGuest).join(
            Booking,
            BookingGuest.booking_id == Booking.id
        ).where(
            and_(
                or_(
                    BookingGuest.guest_name.ilike(f"%{search_term}%"),
                    BookingGuest.guest_email.ilike(f"%{search_term}%"),
                    BookingGuest.guest_phone.like(f"%{search_term}%"),
                ),
                BookingGuest.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        query = query.options(
            joinedload(BookingGuest.booking),
        ).order_by(
            BookingGuest.created_at.desc()
        ).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def verify_id_proof(
        self,
        guest_id: UUID,
        verified_by: UUID,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingGuest:
        """
        Mark guest ID proof as verified.
        
        Args:
            guest_id: Guest UUID
            verified_by: Admin UUID verifying the ID
            audit_context: Audit context
            
        Returns:
            Updated guest
        """
        guest = self.find_by_id(guest_id)
        if not guest:
            raise EntityNotFoundError(f"Guest {guest_id} not found")
        
        guest.verify_id_proof(verified_by)
        
        self.session.flush()
        self.session.refresh(guest)
        
        return guest
    
    def update_consent(
        self,
        guest_id: UUID,
        communication: bool,
        data_sharing: bool,
        audit_context: Optional[AuditContext] = None,
    ) -> BookingGuest:
        """
        Update guest consent preferences.
        
        Args:
            guest_id: Guest UUID
            communication: Consent for communication
            data_sharing: Consent for data sharing
            audit_context: Audit context
            
        Returns:
            Updated guest
        """
        guest = self.find_by_id(guest_id)
        if not guest:
            raise EntityNotFoundError(f"Guest {guest_id} not found")
        
        guest.update_consent(communication, data_sharing)
        
        self.session.flush()
        self.session.refresh(guest)
        
        return guest
    
    def find_incomplete_profiles(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingGuest]:
        """
        Find guests with incomplete profiles.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of guests with incomplete profiles
        """
        query = select(BookingGuest).join(
            Booking,
            BookingGuest.booking_id == Booking.id
        ).where(
            BookingGuest.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        guests = self.session.execute(query).scalars().all()
        
        # Filter for incomplete profiles
        incomplete = [g for g in guests if not g.has_complete_profile]
        
        return incomplete
    
    def find_unverified_ids(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingGuest]:
        """
        Find guests with unverified ID proofs.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of guests with unverified IDs
        """
        query = select(BookingGuest).join(
            Booking,
            BookingGuest.booking_id == Booking.id
        ).where(
            and_(
                BookingGuest.id_proof_verified == False,
                BookingGuest.guest_id_proof_number.isnot(None),
                BookingGuest.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        query = query.options(
            joinedload(BookingGuest.booking),
        ).order_by(
            BookingGuest.created_at.asc()
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_minors(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[BookingGuest]:
        """
        Find guests who are minors (under 18).
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of minor guests
        """
        query = select(BookingGuest).join(
            Booking,
            BookingGuest.booking_id == Booking.id
        ).where(
            and_(
                BookingGuest.date_of_birth.isnot(None),
                BookingGuest.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        guests = self.session.execute(query).scalars().all()
        
        # Filter for minors
        minors = [g for g in guests if g.is_minor]
        
        return minors


class GuestDocumentRepository(BaseRepository[GuestDocument]):
    """Repository for guest document management."""
    
    def __init__(self, session: Session):
        """Initialize document repository."""
        super().__init__(session, GuestDocument)
    
    def add_document(
        self,
        guest_id: UUID,
        document_data: Dict,
        audit_context: Optional[AuditContext] = None,
    ) -> GuestDocument:
        """
        Add document for a guest.
        
        Args:
            guest_id: Guest UUID
            document_data: Document information
            audit_context: Audit context
            
        Returns:
            Created document
        """
        document = GuestDocument(
            guest_id=guest_id,
            **document_data,
        )
        
        return self.create(document, audit_context)
    
    def find_by_guest(
        self,
        guest_id: UUID,
        document_type: Optional[str] = None,
    ) -> List[GuestDocument]:
        """
        Find documents for a guest.
        
        Args:
            guest_id: Guest UUID
            document_type: Optional document type filter
            
        Returns:
            List of documents
        """
        query = select(GuestDocument).where(
            and_(
                GuestDocument.guest_id == guest_id,
                GuestDocument.deleted_at.is_(None),
            )
        )
        
        if document_type:
            query = query.where(GuestDocument.document_type == document_type)
        
        query = query.order_by(GuestDocument.created_at.desc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def verify_document(
        self,
        document_id: UUID,
        verified_by: UUID,
        notes: Optional[str] = None,
        audit_context: Optional[AuditContext] = None,
    ) -> GuestDocument:
        """
        Verify a document.
        
        Args:
            document_id: Document UUID
            verified_by: Admin UUID verifying the document
            notes: Optional verification notes
            audit_context: Audit context
            
        Returns:
            Updated document
        """
        document = self.find_by_id(document_id)
        if not document:
            raise EntityNotFoundError(f"Document {document_id} not found")
        
        document.verify(verified_by, notes)
        
        self.session.flush()
        self.session.refresh(document)
        
        return document
    
    def reject_document(
        self,
        document_id: UUID,
        rejected_by: UUID,
        reason: str,
        audit_context: Optional[AuditContext] = None,
    ) -> GuestDocument:
        """
        Reject a document.
        
        Args:
            document_id: Document UUID
            rejected_by: Admin UUID rejecting the document
            reason: Rejection reason
            audit_context: Audit context
            
        Returns:
            Updated document
        """
        document = self.find_by_id(document_id)
        if not document:
            raise EntityNotFoundError(f"Document {document_id} not found")
        
        document.reject(rejected_by, reason)
        
        self.session.flush()
        self.session.refresh(document)
        
        return document
    
    def find_unverified_documents(
        self,
        hostel_id: Optional[UUID] = None,
        document_type: Optional[str] = None,
    ) -> List[GuestDocument]:
        """
        Find unverified documents.
        
        Args:
            hostel_id: Optional hostel filter
            document_type: Optional document type filter
            
        Returns:
            List of unverified documents
        """
        query = select(GuestDocument).join(
            BookingGuest,
            GuestDocument.guest_id == BookingGuest.id
        ).join(
            Booking,
            BookingGuest.booking_id == Booking.id
        ).where(
            and_(
                GuestDocument.is_verified == False,
                GuestDocument.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        if document_type:
            query = query.where(GuestDocument.document_type == document_type)
        
        query = query.options(
            joinedload(GuestDocument.guest),
        ).order_by(
            GuestDocument.created_at.asc()
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def find_expiring_documents(
        self,
        days_ahead: int = 30,
        hostel_id: Optional[UUID] = None,
    ) -> List[GuestDocument]:
        """
        Find documents expiring soon.
        
        Args:
            days_ahead: Days to look ahead
            hostel_id: Optional hostel filter
            
        Returns:
            List of expiring documents
        """
        from datetime import timedelta
        
        expiry_threshold = datetime.utcnow() + timedelta(days=days_ahead)
        
        query = select(GuestDocument).join(
            BookingGuest,
            GuestDocument.guest_id == BookingGuest.id
        ).join(
            Booking,
            BookingGuest.booking_id == Booking.id
        ).where(
            and_(
                GuestDocument.expiry_date.isnot(None),
                GuestDocument.expiry_date <= expiry_threshold,
                GuestDocument.expiry_date > datetime.utcnow(),
                GuestDocument.deleted_at.is_(None),
            )
        )
        
        if hostel_id:
            query = query.where(Booking.hostel_id == hostel_id)
        
        query = query.options(
            joinedload(GuestDocument.guest),
        ).order_by(
            GuestDocument.expiry_date.asc()
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())