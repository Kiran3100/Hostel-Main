# --- File: C:\Hostel-Main\app\services\user\emergency_contact_service.py ---
"""
Emergency Contact Service - Emergency contact management with verification.
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.user import EmergencyContact
from app.repositories.user import EmergencyContactRepository, UserRepository
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError


class EmergencyContactService:
    """
    Service for emergency contact operations including verification,
    prioritization, and consent management.
    """

    def __init__(self, db: Session):
        self.db = db
        self.contact_repo = EmergencyContactRepository(db)
        self.user_repo = UserRepository(db)

    # ==================== Contact Management ====================

    def create_emergency_contact(
        self,
        user_id: str,
        contact_data: Dict[str, Any],
        set_as_primary: bool = False
    ) -> EmergencyContact:
        """
        Create emergency contact.
        
        Args:
            user_id: User ID
            contact_data: Contact data dictionary
            set_as_primary: Set as primary contact
            
        Returns:
            Created EmergencyContact
            
        Raises:
            EntityNotFoundError: If user not found
            BusinessRuleViolationError: If validation fails
        """
        # Validate user exists
        user = self.user_repo.get_by_id(user_id)
        
        # Validate phone uniqueness for this user
        phone = contact_data.get('emergency_contact_phone')
        if phone and not self.contact_repo.validate_contact_uniqueness(
            user_id, phone
        ):
            raise BusinessRuleViolationError(
                f"Emergency contact with phone {phone} already exists"
            )
        
        # Add user_id to contact data
        contact_data['user_id'] = user_id
        
        # Set priority if not provided
        if 'priority' not in contact_data:
            contact_data['priority'] = self.contact_repo.get_next_priority(user_id)
        
        # Set primary flag
        if 'is_primary' not in contact_data:
            contact_data['is_primary'] = set_as_primary
        
        # Create contact
        contact = self.contact_repo.create(contact_data)
        
        # If set as primary, unset others
        if set_as_primary:
            self.contact_repo.set_primary_contact(contact.id, user_id)
        
        return contact

    def update_emergency_contact(
        self,
        contact_id: str,
        contact_data: Dict[str, Any]
    ) -> EmergencyContact:
        """
        Update emergency contact.
        
        Args:
            contact_id: Contact ID
            contact_data: Contact data dictionary
            
        Returns:
            Updated EmergencyContact
        """
        contact = self.contact_repo.get_by_id(contact_id)
        
        # Validate phone uniqueness if phone is being updated
        if 'emergency_contact_phone' in contact_data:
            phone = contact_data['emergency_contact_phone']
            if not self.contact_repo.validate_contact_uniqueness(
                contact.user_id, phone, exclude_contact_id=contact_id
            ):
                raise BusinessRuleViolationError(
                    f"Emergency contact with phone {phone} already exists"
                )
        
        return self.contact_repo.update(contact_id, contact_data)

    def delete_emergency_contact(self, contact_id: str) -> None:
        """
        Delete emergency contact.
        
        Args:
            contact_id: Contact ID
        """
        contact = self.contact_repo.get_by_id(contact_id)
        
        # Don't allow deleting primary contact if others exist
        if contact.is_primary:
            user_contacts = self.contact_repo.find_by_user_id(contact.user_id)
            if len(user_contacts) > 1:
                raise BusinessRuleViolationError(
                    "Cannot delete primary contact. Set another contact as primary first."
                )
        
        self.contact_repo.delete(contact_id)

    def get_user_emergency_contacts(
        self,
        user_id: str,
        active_only: bool = True
    ) -> List[EmergencyContact]:
        """
        Get all emergency contacts for a user.
        
        Args:
            user_id: User ID
            active_only: Filter only active contacts
            
        Returns:
            List of emergency contacts ordered by priority
        """
        return self.contact_repo.find_by_user_id(user_id, active_only)

    def get_primary_contact(self, user_id: str) -> Optional[EmergencyContact]:
        """
        Get primary emergency contact for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Primary EmergencyContact or None
        """
        return self.contact_repo.find_primary_contact(user_id)

    def set_primary_contact(
        self,
        contact_id: str,
        user_id: str
    ) -> EmergencyContact:
        """
        Set a contact as primary.
        
        Args:
            contact_id: Contact ID
            user_id: User ID for validation
            
        Returns:
            Updated primary contact
        """
        return self.contact_repo.set_primary_contact(contact_id, user_id)

    # ==================== Priority Management ====================

    def reorder_contacts(
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
        return self.contact_repo.reorder_priorities(
            user_id,
            contact_priority_map
        )

    def move_contact_up(
        self,
        contact_id: str,
        user_id: str
    ) -> EmergencyContact:
        """
        Move contact up in priority (decrease priority number).
        
        Args:
            contact_id: Contact ID
            user_id: User ID
            
        Returns:
            Updated contact
        """
        contact = self.contact_repo.get_by_id(contact_id)
        
        if contact.priority <= 1:
            raise BusinessRuleViolationError(
                "Contact is already at highest priority"
            )
        
        new_priority = contact.priority - 1
        
        # Swap with contact at new priority
        other_contact = self.contact_repo.find_by_priority(user_id, new_priority)
        if other_contact:
            self.contact_repo.update(other_contact.id, {
                'priority': contact.priority
            })
        
        return self.contact_repo.update(contact_id, {
            'priority': new_priority
        })

    def move_contact_down(
        self,
        contact_id: str,
        user_id: str
    ) -> EmergencyContact:
        """
        Move contact down in priority (increase priority number).
        
        Args:
            contact_id: Contact ID
            user_id: User ID
            
        Returns:
            Updated contact
        """
        contact = self.contact_repo.get_by_id(contact_id)
        
        new_priority = contact.priority + 1
        
        # Swap with contact at new priority
        other_contact = self.contact_repo.find_by_priority(user_id, new_priority)
        if other_contact:
            self.contact_repo.update(other_contact.id, {
                'priority': contact.priority
            })
        
        return self.contact_repo.update(contact_id, {
            'priority': new_priority
        })

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
        return self.contact_repo.verify_contact(contact_id, verification_method)

    def unverify_contact(self, contact_id: str) -> EmergencyContact:
        """
        Remove contact verification.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Updated contact
        """
        contact = self.contact_repo.get_by_id(contact_id)
        return self.contact_repo.update(contact.id, {
            'is_verified': False,
            'verified_at': None,
            'verification_method': None
        })

    def get_unverified_contacts(
        self,
        user_id: Optional[str] = None,
        older_than_days: Optional[int] = None
    ) -> List[EmergencyContact]:
        """
        Get unverified emergency contacts.
        
        Args:
            user_id: Optional user ID filter
            older_than_days: Only contacts added more than X days ago
            
        Returns:
            List of unverified contacts
        """
        return self.contact_repo.find_unverified_contacts(
            user_id,
            older_than_days
        )

    def initiate_verification(
        self,
        contact_id: str,
        method: str = "phone_call"
    ) -> Dict[str, Any]:
        """
        Initiate contact verification process.
        
        Args:
            contact_id: Contact ID
            method: Verification method
            
        Returns:
            Verification details
        """
        contact = self.contact_repo.get_by_id(contact_id)
        
        # TODO: Implement actual verification process
        # - Send SMS/email verification
        # - Schedule phone call
        # - Request document upload
        
        return {
            'contact_id': contact.id,
            'method': method,
            'phone': contact.emergency_contact_phone,
            'email': contact.emergency_contact_email,
            'status': 'initiated'
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
        return self.contact_repo.record_consent(contact_id, consent_given)

    def get_contacts_without_consent(
        self,
        user_id: Optional[str] = None
    ) -> List[EmergencyContact]:
        """
        Get contacts without recorded consent.
        
        Args:
            user_id: Optional user ID filter
            
        Returns:
            List of contacts without consent
        """
        return self.contact_repo.find_without_consent(user_id)

    def request_consent(self, contact_id: str) -> Dict[str, Any]:
        """
        Request consent from emergency contact.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Request details
        """
        contact = self.contact_repo.get_by_id(contact_id)
        
        # TODO: Implement consent request
        # - Send consent form via email/SMS
        # - Generate consent tracking link
        
        return {
            'contact_id': contact.id,
            'status': 'consent_requested',
            'contact_method': 'email' if contact.emergency_contact_email else 'phone'
        }

    # ==================== Authorization Management ====================

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
        return self.contact_repo.update_authorization(
            contact_id,
            can_make_decisions,
            can_access_medical_info
        )

    def grant_full_authorization(self, contact_id: str) -> EmergencyContact:
        """
        Grant full authorization to contact.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Updated contact
        """
        return self.update_authorization(
            contact_id,
            can_make_decisions=True,
            can_access_medical_info=True
        )

    def revoke_all_authorization(self, contact_id: str) -> EmergencyContact:
        """
        Revoke all authorization from contact.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Updated contact
        """
        return self.update_authorization(
            contact_id,
            can_make_decisions=False,
            can_access_medical_info=False
        )

    # ==================== Communication Tracking ====================

    def log_contact_attempt(
        self,
        contact_id: str,
        success: bool = True,
        notes: Optional[str] = None
    ) -> EmergencyContact:
        """
        Log an attempt to contact this emergency contact.
        
        Args:
            contact_id: Contact ID
            success: Whether contact was successful
            notes: Optional notes about the attempt
            
        Returns:
            Updated contact
        """
        contact = self.contact_repo.log_contact_attempt(contact_id, success)
        
        if notes:
            current_notes = contact.notes or ""
            timestamp = datetime.now(timezone.utc).isoformat()
            new_note = f"\n[{timestamp}] {notes}"
            
            self.contact_repo.update(contact.id, {
                'notes': current_notes + new_note
            })
        
        return contact

    def get_contact_history(self, contact_id: str) -> Dict[str, Any]:
        """
        Get contact attempt history.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Contact history details
        """
        contact = self.contact_repo.get_by_id(contact_id)
        
        return {
            'contact_id': contact.id,
            'total_attempts': contact.contact_count or 0,
            'last_contacted': contact.last_contacted_at,
            'is_verified': contact.is_verified,
            'has_consent': contact.consent_given
        }

    # ==================== Search & Analytics ====================

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
        return self.contact_repo.search_contacts(user_id, search_term)

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
        return self.contact_repo.find_by_relationship(relationship, user_id)

    def get_contact_statistics(
        self,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive emergency contact statistics.
        
        Args:
            user_id: Optional user ID filter
            
        Returns:
            Dictionary with contact metrics
        """
        return self.contact_repo.get_contact_statistics(user_id)

    def get_verification_statistics(self) -> Dict[str, Any]:
        """
        Get verification statistics for emergency contacts.
        
        Returns:
            Dictionary with verification metrics
        """
        return self.contact_repo.get_verification_statistics()

    def get_relationship_distribution(self) -> Dict[str, int]:
        """
        Get distribution of relationship types.
        
        Returns:
            Dictionary mapping relationship to count
        """
        return self.contact_repo.get_relationship_distribution()

    # ==================== Bulk Operations ====================

    def bulk_verify_contacts(
        self,
        contact_ids: List[str],
        verification_method: str = "manual"
    ) -> int:
        """
        Bulk verify multiple contacts.
        
        Args:
            contact_ids: List of contact IDs
            verification_method: Verification method
            
        Returns:
            Count of verified contacts
        """
        count = 0
        for contact_id in contact_ids:
            try:
                self.verify_contact(contact_id, verification_method)
                count += 1
            except Exception:
                continue
        
        return count

    def bulk_request_consent(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Request consent from all contacts without consent.
        
        Args:
            user_id: User ID
            
        Returns:
            Request summary
        """
        contacts = self.get_contacts_without_consent(user_id)
        
        requested = 0
        for contact in contacts:
            try:
                self.request_consent(contact.id)
                requested += 1
            except Exception:
                continue
        
        return {
            'total_contacts': len(contacts),
            'consent_requested': requested,
            'failed': len(contacts) - requested
        }

    # ==================== Utility Methods ====================

    def validate_contact_completeness(
        self,
        contact_data: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate if contact data is complete.
        
        Args:
            contact_data: Contact data dictionary
            
        Returns:
            Tuple of (is_complete, missing_fields)
        """
        required_fields = [
            'emergency_contact_name',
            'emergency_contact_phone',
            'emergency_contact_relation'
        ]
        
        missing = [
            field for field in required_fields 
            if field not in contact_data or not contact_data[field]
        ]
        
        return len(missing) == 0, missing

    def suggest_improvements(
        self,
        contact_id: str
    ) -> List[Dict[str, str]]:
        """
        Get suggestions for improving contact information.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            List of suggestions
        """
        contact = self.contact_repo.get_by_id(contact_id)
        suggestions = []
        
        if not contact.is_verified:
            suggestions.append({
                'field': 'verification',
                'message': 'Verify this emergency contact'
            })
        
        if not contact.consent_given:
            suggestions.append({
                'field': 'consent',
                'message': 'Obtain consent from this contact'
            })
        
        if not contact.emergency_contact_email:
            suggestions.append({
                'field': 'email',
                'message': 'Add email address for better communication'
            })
        
        if not contact.emergency_contact_alternate_phone:
            suggestions.append({
                'field': 'alternate_phone',
                'message': 'Add alternate phone number for redundancy'
            })
        
        if not contact.contact_address:
            suggestions.append({
                'field': 'address',
                'message': 'Add physical address'
            })
        
        return suggestions


