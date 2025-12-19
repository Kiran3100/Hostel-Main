"""
Emergency Contact Repository - Emergency contact management with verification and prioritization.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.models.user import EmergencyContact
from app.repositories.base.base_repository import BaseRepository


class EmergencyContactRepository(BaseRepository[EmergencyContact]):
    """
    Repository for EmergencyContact entity with priority management,
    verification tracking, and communication logging.
    """

    def __init__(self, db: Session):
        super().__init__(EmergencyContact, db)

    # ==================== Basic Contact Operations ====================

    def find_by_user_id(
        self, 
        user_id: str, 
        active_only: bool = True
    ) -> List[EmergencyContact]:
        """
        Find all emergency contacts for a user.
        
        Args:
            user_id: User ID
            active_only: Filter only active contacts
            
        Returns:
            List of emergency contacts ordered by priority
        """
        query = self.db.query(EmergencyContact).filter(
            EmergencyContact.user_id == user_id
        )
        
        if active_only:
            query = query.filter(EmergencyContact.is_active == True)
        
        return query.order_by(
            EmergencyContact.priority.asc(),
            EmergencyContact.is_primary.desc()
        ).all()

    def find_primary_contact(self, user_id: str) -> Optional[EmergencyContact]:
        """
        Find primary emergency contact for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Primary EmergencyContact or None
        """
        return self.db.query(EmergencyContact).filter(
            EmergencyContact.user_id == user_id,
            EmergencyContact.is_primary == True,
            EmergencyContact.is_active == True
        ).first()

    def find_by_priority(
        self, 
        user_id: str, 
        priority: int
    ) -> Optional[EmergencyContact]:
        """
        Find emergency contact by priority level.
        
        Args:
            user_id: User ID
            priority: Priority level (1 = highest)
            
        Returns:
            EmergencyContact or None
        """
        return self.db.query(EmergencyContact).filter(
            EmergencyContact.user_id == user_id,
            EmergencyContact.priority == priority,
            EmergencyContact.is_active == True
        ).first()

    def set_primary_contact(
        self, 
        contact_id: str, 
        user_id: str
    ) -> EmergencyContact:
        """
        Set a contact as primary (unset others).
        
        Args:
            contact_id: Contact ID to set as primary
            user_id: User ID for validation
            
        Returns:
            Updated primary contact
        """
        # Unset all other primary contacts for this user
        self.db.query(EmergencyContact).filter(
            EmergencyContact.user_id == user_id,
            EmergencyContact.id != contact_id
        ).update({"is_primary": False})
        
        # Set the new primary
        contact = self.get_by_id(contact_id)
        contact.is_primary = True
        
        self.db.commit()
        self.db.refresh(contact)
        
        return contact

    # ==================== Priority Management ====================

    def reorder_priorities(
        self, 
        user_id: str, 
        contact_priority_map: Dict[str, int]
    ) -> List[EmergencyContact]:
        """
        Reorder contact priorities in bulk.
        
        Args:
            user_id: User ID
            contact_priority_map: Dictionary mapping contact_id to new priority
            
        Returns:
            List of updated contacts
        """
        updated_contacts = []
        
        for contact_id, new_priority in contact_priority_map.items():
            contact = self.get_by_id(contact_id)
            
            # Validate user_id matches
            if contact.user_id != user_id:
                continue
            
            contact.priority = new_priority
            updated_contacts.append(contact)
        
        self.db.commit()
        
        for contact in updated_contacts:
            self.db.refresh(contact)
        
        return updated_contacts

    def get_next_priority(self, user_id: str) -> int:
        """
        Get the next available priority number for a new contact.
        
        Args:
            user_id: User ID
            
        Returns:
            Next priority number
        """
        max_priority = self.db.query(
            func.max(EmergencyContact.priority)
        ).filter(
            EmergencyContact.user_id == user_id,
            EmergencyContact.is_active == True
        ).scalar()
        
        return (max_priority or 0) + 1

    # ==================== Verification ====================

    def verify_contact(
        self, 
        contact_id: str, 
        verification_method: str = "phone_call"
    ) -> EmergencyContact:
        """
        Mark contact as verified.
        
        Args:
            contact_id: Contact ID
            verification_method: Verification method (phone_call, document, manual)
            
        Returns:
            Verified contact
        """
        contact = self.get_by_id(contact_id)
        
        contact.is_verified = True
        contact.verified_at = datetime.now(timezone.utc)
        contact.verification_method = verification_method
        
        self.db.commit()
        self.db.refresh(contact)
        
        return contact

    def find_unverified_contacts(
        self, 
        user_id: Optional[str] = None,
        older_than_days: Optional[int] = None
    ) -> List[EmergencyContact]:
        """
        Find unverified emergency contacts.
        
        Args:
            user_id: Optional user ID filter
            older_than_days: Only contacts added more than X days ago
            
        Returns:
            List of unverified contacts
        """
        query = self.db.query(EmergencyContact).filter(
            EmergencyContact.is_verified == False,
            EmergencyContact.is_active == True
        )
        
        if user_id:
            query = query.filter(EmergencyContact.user_id == user_id)
        
        if older_than_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
            query = query.filter(EmergencyContact.created_at < cutoff)
        
        return query.all()

    def get_verification_statistics(self) -> Dict[str, Any]:
        """
        Get verification statistics for emergency contacts.
        
        Returns:
            Dictionary with verification metrics
        """
        total = self.db.query(func.count(EmergencyContact.id)).filter(
            EmergencyContact.is_active == True
        ).scalar()
        
        verified = self.db.query(func.count(EmergencyContact.id)).filter(
            EmergencyContact.is_verified == True,
            EmergencyContact.is_active == True
        ).scalar()
        
        by_method = self.db.query(
            EmergencyContact.verification_method,
            func.count(EmergencyContact.id).label('count')
        ).filter(
            EmergencyContact.is_verified == True,
            EmergencyContact.is_active == True
        ).group_by(EmergencyContact.verification_method).all()
        
        return {
            "total_contacts": total,
            "verified_contacts": verified,
            "unverified_contacts": total - verified,
            "verification_rate": (verified / total * 100) if total > 0 else 0,
            "by_method": {method: count for method, count in by_method if method}
        }

    # ==================== Consent Management ====================

    def record_consent(
        self, 
        contact_id: str, 
        consent_given: bool = True
    ) -> EmergencyContact:
        """
        Record consent for emergency contact.
        
        Args:
            contact_id: Contact ID
            consent_given: Consent status
            
        Returns:
            Updated contact
        """
        contact = self.get_by_id(contact_id)
        
        contact.consent_given = consent_given
        contact.consent_date = datetime.now(timezone.utc) if consent_given else None
        
        self.db.commit()
        self.db.refresh(contact)
        
        return contact

    def find_without_consent(self, user_id: Optional[str] = None) -> List[EmergencyContact]:
        """
        Find contacts without recorded consent.
        
        Args:
            user_id: Optional user ID filter
            
        Returns:
            List of contacts without consent
        """
        query = self.db.query(EmergencyContact).filter(
            EmergencyContact.consent_given == False,
            EmergencyContact.is_active == True
        )
        
        if user_id:
            query = query.filter(EmergencyContact.user_id == user_id)
        
        return query.all()

    def update_authorization(
        self, 
        contact_id: str,
        can_make_decisions: bool = False,
        can_access_medical_info: bool = False
    ) -> EmergencyContact:
        """
        Update contact authorization permissions.
        
        Args:
            contact_id: Contact ID
            can_make_decisions: Authorization to make decisions
            can_access_medical_info: Authorization to access medical info
            
        Returns:
            Updated contact
        """
        contact = self.get_by_id(contact_id)
        
        contact.can_make_decisions = can_make_decisions
        contact.can_access_medical_info = can_access_medical_info
        
        self.db.commit()
        self.db.refresh(contact)
        
        return contact

    # ==================== Communication Tracking ====================

    def log_contact_attempt(
        self, 
        contact_id: str,
        success: bool = True
    ) -> EmergencyContact:
        """
        Log an attempt to contact this emergency contact.
        
        Args:
            contact_id: Contact ID
            success: Whether contact was successful
            
        Returns:
            Updated contact
        """
        contact = self.get_by_id(contact_id)
        
        if success:
            contact.last_contacted_at = datetime.now(timezone.utc)
        
        contact.contact_count = (contact.contact_count or 0) + 1
        
        self.db.commit()
        self.db.refresh(contact)
        
        return contact

    def find_never_contacted(
        self, 
        user_id: Optional[str] = None
    ) -> List[EmergencyContact]:
        """
        Find contacts that have never been reached.
        
        Args:
            user_id: Optional user ID filter
            
        Returns:
            List of never-contacted contacts
        """
        query = self.db.query(EmergencyContact).filter(
            EmergencyContact.last_contacted_at.is_(None),
            EmergencyContact.is_active == True
        )
        
        if user_id:
            query = query.filter(EmergencyContact.user_id == user_id)
        
        return query.all()

    def find_frequently_contacted(
        self, 
        min_count: int = 3,
        limit: int = 50
    ) -> List[EmergencyContact]:
        """
        Find frequently contacted emergency contacts.
        
        Args:
            min_count: Minimum contact count threshold
            limit: Maximum results
            
        Returns:
            List of frequently contacted contacts
        """
        return self.db.query(EmergencyContact).filter(
            EmergencyContact.contact_count >= min_count,
            EmergencyContact.is_active == True
        ).order_by(
            EmergencyContact.contact_count.desc()
        ).limit(limit).all()

    # ==================== Relationship Analysis ====================

    def find_by_relationship(
        self, 
        relationship: str,
        user_id: Optional[str] = None
    ) -> List[EmergencyContact]:
        """
        Find contacts by relationship type.
        
        Args:
            relationship: Relationship type (Father, Mother, Spouse, etc.)
            user_id: Optional user ID filter
            
        Returns:
            List of contacts
        """
        query = self.db.query(EmergencyContact).filter(
            EmergencyContact.emergency_contact_relation.ilike(f"%{relationship}%"),
            EmergencyContact.is_active == True
        )
        
        if user_id:
            query = query.filter(EmergencyContact.user_id == user_id)
        
        return query.all()

    def get_relationship_distribution(self) -> Dict[str, int]:
        """
        Get distribution of relationship types.
        
        Returns:
            Dictionary mapping relationship to count
        """
        results = self.db.query(
            EmergencyContact.emergency_contact_relation,
            func.count(EmergencyContact.id).label('count')
        ).filter(
            EmergencyContact.is_active == True
        ).group_by(
            EmergencyContact.emergency_contact_relation
        ).order_by(
            func.count(EmergencyContact.id).desc()
        ).all()
        
        return {relation: count for relation, count in results}

    # ==================== Search & Validation ====================

    def search_contacts(
        self,
        user_id: str,
        search_term: Optional[str] = None
    ) -> List[EmergencyContact]:
        """
        Search emergency contacts by name, phone, or email.
        
        Args:
            user_id: User ID
            search_term: Search term
            
        Returns:
            List of matching contacts
        """
        query = self.db.query(EmergencyContact).filter(
            EmergencyContact.user_id == user_id,
            EmergencyContact.is_active == True
        )
        
        if search_term:
            search_pattern = f"%{search_term}%"
            query = query.filter(
                or_(
                    EmergencyContact.emergency_contact_name.ilike(search_pattern),
                    EmergencyContact.emergency_contact_phone.like(search_pattern),
                    EmergencyContact.emergency_contact_email.ilike(search_pattern)
                )
            )
        
        return query.order_by(EmergencyContact.priority).all()

    def validate_contact_uniqueness(
        self, 
        user_id: str,
        phone: str,
        exclude_contact_id: Optional[str] = None
    ) -> bool:
        """
        Check if phone number is already used for this user.
        
        Args:
            user_id: User ID
            phone: Phone number to check
            exclude_contact_id: Contact ID to exclude (for updates)
            
        Returns:
            True if phone is unique, False if duplicate
        """
        query = self.db.query(EmergencyContact.id).filter(
            EmergencyContact.user_id == user_id,
            EmergencyContact.emergency_contact_phone == phone,
            EmergencyContact.is_active == True
        )
        
        if exclude_contact_id:
            query = query.filter(EmergencyContact.id != exclude_contact_id)
        
        return query.first() is None

    # ==================== Statistics ====================

    def get_contact_statistics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive emergency contact statistics.
        
        Args:
            user_id: Optional user ID filter
            
        Returns:
            Dictionary with contact metrics
        """
        query_base = self.db.query(EmergencyContact).filter(
            EmergencyContact.is_active == True
        )
        
        if user_id:
            query_base = query_base.filter(EmergencyContact.user_id == user_id)
        
        total = query_base.count()
        verified = query_base.filter(EmergencyContact.is_verified == True).count()
        with_consent = query_base.filter(EmergencyContact.consent_given == True).count()
        
        can_decide = query_base.filter(
            EmergencyContact.can_make_decisions == True
        ).count()
        
        can_access_medical = query_base.filter(
            EmergencyContact.can_access_medical_info == True
        ).count()
        
        avg_contact_count = self.db.query(
            func.avg(EmergencyContact.contact_count)
        ).filter(
            EmergencyContact.is_active == True
        ).scalar()
        
        if user_id:
            avg_contact_count = self.db.query(
                func.avg(EmergencyContact.contact_count)
            ).filter(
                EmergencyContact.user_id == user_id,
                EmergencyContact.is_active == True
            ).scalar()
        
        return {
            "total_contacts": total,
            "verified_contacts": verified,
            "with_consent": with_consent,
            "can_make_decisions": can_decide,
            "can_access_medical": can_access_medical,
            "verification_rate": (verified / total * 100) if total > 0 else 0,
            "consent_rate": (with_consent / total * 100) if total > 0 else 0,
            "average_contact_count": float(avg_contact_count) if avg_contact_count else 0
        }

    def find_contacts_needing_update(
        self, 
        months_old: int = 12
    ) -> List[EmergencyContact]:
        """
        Find contacts that haven't been updated in specified months.
        
        Args:
            months_old: Age threshold in months
            
        Returns:
            List of potentially outdated contacts
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=months_old * 30)
        
        return self.db.query(EmergencyContact).filter(
            EmergencyContact.updated_at < cutoff,
            EmergencyContact.is_active == True
        ).order_by(EmergencyContact.updated_at.asc()).all()