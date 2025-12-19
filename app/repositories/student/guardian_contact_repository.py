# --- File: guardian_contact_repository.py ---

"""
Guardian contact repository.

Guardian/parent contact management with emergency contact handling,
verification, and communication tracking.
"""

from datetime import datetime
from typing import Any, Optional
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session, joinedload

from app.models.student.guardian_contact import GuardianContact
from app.models.student.student import Student


class GuardianContactRepository:
    """
    Guardian contact repository for comprehensive guardian management.
    
    Handles:
        - Multiple guardian contacts per student
        - Emergency contact prioritization
        - Contact verification workflows
        - Communication preferences
        - Authorization and consent management
        - Privacy and security controls
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ============================================================================
    # CORE CRUD OPERATIONS
    # ============================================================================

    def create(
        self,
        contact_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> GuardianContact:
        """
        Create guardian contact with audit logging.
        
        Args:
            contact_data: Guardian contact information
            audit_context: Audit context
            
        Returns:
            Created guardian contact instance
        """
        if audit_context:
            contact_data['created_by'] = audit_context.get('user_id')
            contact_data['updated_by'] = audit_context.get('user_id')

        contact = GuardianContact(**contact_data)
        self.db.add(contact)
        self.db.flush()
        
        # If this is primary contact, unset other primary contacts for same student
        if contact.is_primary:
            self._ensure_single_primary_contact(
                contact.student_id, 
                contact.id
            )
        
        return contact

    def find_by_id(
        self,
        contact_id: str,
        include_deleted: bool = False,
        eager_load: bool = False
    ) -> Optional[GuardianContact]:
        """
        Find guardian contact by ID with optional eager loading.
        
        Args:
            contact_id: Guardian contact UUID
            include_deleted: Include soft-deleted records
            eager_load: Load related entities
            
        Returns:
            Guardian contact instance or None
        """
        query = self.db.query(GuardianContact)
        
        if eager_load:
            query = query.options(joinedload(GuardianContact.student))
        
        query = query.filter(GuardianContact.id == contact_id)
        
        if not include_deleted:
            query = query.filter(GuardianContact.deleted_at.is_(None))
        
        return query.first()

    def find_by_student_id(
        self,
        student_id: str,
        include_deleted: bool = False,
        verified_only: bool = False
    ) -> list[GuardianContact]:
        """
        Find all guardian contacts for a student.
        
        Args:
            student_id: Student UUID
            include_deleted: Include soft-deleted records
            verified_only: Return only verified contacts
            
        Returns:
            List of guardian contacts
        """
        query = self.db.query(GuardianContact).filter(
            GuardianContact.student_id == student_id
        )
        
        if not include_deleted:
            query = query.filter(GuardianContact.deleted_at.is_(None))
        
        if verified_only:
            query = query.filter(GuardianContact.phone_verified == True)
        
        return query.order_by(GuardianContact.priority.asc()).all()

    def update(
        self,
        contact_id: str,
        update_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[GuardianContact]:
        """
        Update guardian contact with audit logging.
        
        Args:
            contact_id: Guardian contact UUID
            update_data: Fields to update
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance or None
        """
        contact = self.find_by_id(contact_id)
        if not contact:
            return None
        
        if audit_context:
            update_data['updated_by'] = audit_context.get('user_id')
        update_data['updated_at'] = datetime.utcnow()
        
        for key, value in update_data.items():
            if hasattr(contact, key):
                setattr(contact, key, value)
        
        self.db.flush()
        
        # Handle primary contact constraint
        if update_data.get('is_primary') and contact.is_primary:
            self._ensure_single_primary_contact(
                contact.student_id, 
                contact.id
            )
        
        return contact

    def soft_delete(
        self,
        contact_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> bool:
        """
        Soft delete guardian contact with audit logging.
        
        Args:
            contact_id: Guardian contact UUID
            audit_context: Audit context
            
        Returns:
            Success status
        """
        contact = self.find_by_id(contact_id)
        if not contact:
            return False
        
        contact.deleted_at = datetime.utcnow()
        if audit_context:
            contact.deleted_by = audit_context.get('user_id')
        
        self.db.flush()
        return True

    # ============================================================================
    # PRIMARY CONTACT MANAGEMENT
    # ============================================================================

    def get_primary_contact(
        self,
        student_id: str
    ) -> Optional[GuardianContact]:
        """
        Get primary guardian contact for student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Primary guardian contact or None
        """
        return self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.student_id == student_id,
                GuardianContact.is_primary == True,
                GuardianContact.deleted_at.is_(None)
            )
        ).first()

    def set_primary_contact(
        self,
        contact_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[GuardianContact]:
        """
        Set guardian contact as primary.
        
        Args:
            contact_id: Guardian contact UUID
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance or None
        """
        update_data = {'is_primary': True}
        return self.update(contact_id, update_data, audit_context)

    def _ensure_single_primary_contact(
        self,
        student_id: str,
        exclude_contact_id: str
    ) -> None:
        """
        Ensure only one primary contact exists for student.
        
        Args:
            student_id: Student UUID
            exclude_contact_id: Contact ID to exclude from update
        """
        self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.student_id == student_id,
                GuardianContact.id != exclude_contact_id,
                GuardianContact.is_primary == True,
                GuardianContact.deleted_at.is_(None)
            )
        ).update(
            {'is_primary': False},
            synchronize_session=False
        )
        
        self.db.flush()

    # ============================================================================
    # EMERGENCY CONTACT MANAGEMENT
    # ============================================================================

    def get_emergency_contacts(
        self,
        student_id: str,
        available_24x7_only: bool = False
    ) -> list[GuardianContact]:
        """
        Get emergency contacts for student ordered by priority.
        
        Args:
            student_id: Student UUID
            available_24x7_only: Return only 24x7 available contacts
            
        Returns:
            List of emergency contacts
        """
        query = self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.student_id == student_id,
                GuardianContact.is_emergency_contact == True,
                GuardianContact.deleted_at.is_(None)
            )
        )
        
        if available_24x7_only:
            query = query.filter(GuardianContact.available_24x7 == True)
        
        return query.order_by(GuardianContact.emergency_priority.asc()).all()

    def get_first_emergency_contact(
        self,
        student_id: str
    ) -> Optional[GuardianContact]:
        """
        Get first priority emergency contact for student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            First emergency contact or None
        """
        return self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.student_id == student_id,
                GuardianContact.is_emergency_contact == True,
                GuardianContact.deleted_at.is_(None)
            )
        ).order_by(GuardianContact.emergency_priority.asc()).first()

    def update_emergency_priority(
        self,
        contact_id: str,
        priority: int,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[GuardianContact]:
        """
        Update emergency contact priority.
        
        Args:
            contact_id: Guardian contact UUID
            priority: Emergency priority (1=highest)
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance or None
        """
        update_data = {
            'emergency_priority': priority,
            'is_emergency_contact': True
        }
        
        return self.update(contact_id, update_data, audit_context)

    def find_24x7_available_contacts(
        self,
        hostel_id: Optional[str] = None
    ) -> list[GuardianContact]:
        """
        Find all 24x7 available emergency contacts.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of 24x7 available contacts
        """
        query = self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.available_24x7 == True,
                GuardianContact.is_emergency_contact == True,
                GuardianContact.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    # ============================================================================
    # VERIFICATION MANAGEMENT
    # ============================================================================

    def verify_phone(
        self,
        contact_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[GuardianContact]:
        """
        Mark phone number as verified.
        
        Args:
            contact_id: Guardian contact UUID
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance or None
        """
        update_data = {'phone_verified': True}
        return self.update(contact_id, update_data, audit_context)

    def verify_email(
        self,
        contact_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[GuardianContact]:
        """
        Mark email as verified.
        
        Args:
            contact_id: Guardian contact UUID
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance or None
        """
        update_data = {'email_verified': True}
        return self.update(contact_id, update_data, audit_context)

    def verify_id_proof(
        self,
        contact_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[GuardianContact]:
        """
        Mark ID proof as verified.
        
        Args:
            contact_id: Guardian contact UUID
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance or None
        """
        update_data = {'id_verified': True}
        return self.update(contact_id, update_data, audit_context)

    def find_unverified_contacts(
        self,
        verification_type: str,
        hostel_id: Optional[str] = None
    ) -> list[GuardianContact]:
        """
        Find contacts with pending verification.
        
        Args:
            verification_type: Type of verification (phone, email, id)
            hostel_id: Optional hostel filter
            
        Returns:
            List of unverified contacts
        """
        query = self.db.query(GuardianContact).filter(
            GuardianContact.deleted_at.is_(None)
        )
        
        if verification_type == 'phone':
            query = query.filter(GuardianContact.phone_verified == False)
        elif verification_type == 'email':
            query = query.filter(
                and_(
                    GuardianContact.email.isnot(None),
                    GuardianContact.email_verified == False
                )
            )
        elif verification_type == 'id':
            query = query.filter(
                and_(
                    GuardianContact.id_proof_number.isnot(None),
                    GuardianContact.id_verified == False
                )
            )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def get_fully_verified_contacts(
        self,
        student_id: str
    ) -> list[GuardianContact]:
        """
        Get fully verified contacts for student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            List of fully verified contacts
        """
        return self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.student_id == student_id,
                GuardianContact.phone_verified == True,
                GuardianContact.email_verified == True,
                GuardianContact.id_verified == True,
                GuardianContact.deleted_at.is_(None)
            )
        ).all()

    # ============================================================================
    # AUTHORIZATION MANAGEMENT
    # ============================================================================

    def get_authorized_for_pickup(
        self,
        student_id: str
    ) -> list[GuardianContact]:
        """
        Get contacts authorized for student pickup.
        
        Args:
            student_id: Student UUID
            
        Returns:
            List of authorized contacts
        """
        return self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.student_id == student_id,
                GuardianContact.authorized_for_pickup == True,
                GuardianContact.deleted_at.is_(None)
            )
        ).all()

    def get_authorized_for_leave_approval(
        self,
        student_id: str
    ) -> list[GuardianContact]:
        """
        Get contacts authorized to approve leaves.
        
        Args:
            student_id: Student UUID
            
        Returns:
            List of authorized contacts
        """
        return self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.student_id == student_id,
                GuardianContact.can_approve_leaves == True,
                GuardianContact.deleted_at.is_(None)
            )
        ).all()

    def get_financial_guardians(
        self,
        student_id: str
    ) -> list[GuardianContact]:
        """
        Get financial guardians for student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            List of financial guardians
        """
        return self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.student_id == student_id,
                GuardianContact.financial_guardian == True,
                GuardianContact.deleted_at.is_(None)
            )
        ).all()

    def update_authorizations(
        self,
        contact_id: str,
        authorizations: dict[str, bool],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[GuardianContact]:
        """
        Update guardian authorizations.
        
        Args:
            contact_id: Guardian contact UUID
            authorizations: Dictionary of authorization settings
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance or None
        """
        valid_authorizations = [
            'authorized_to_receive_updates',
            'authorized_for_pickup',
            'can_approve_leaves',
            'financial_guardian'
        ]
        
        update_data = {
            key: value for key, value in authorizations.items()
            if key in valid_authorizations
        }
        
        return self.update(contact_id, update_data, audit_context)

    # ============================================================================
    # COMMUNICATION PREFERENCES
    # ============================================================================

    def update_communication_preferences(
        self,
        contact_id: str,
        preferences: dict[str, bool],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[GuardianContact]:
        """
        Update communication preferences.
        
        Args:
            contact_id: Guardian contact UUID
            preferences: Dictionary of communication preferences
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance or None
        """
        valid_preferences = [
            'send_monthly_reports',
            'send_payment_reminders',
            'send_attendance_alerts'
        ]
        
        update_data = {
            key: value for key, value in preferences.items()
            if key in valid_preferences
        }
        
        if 'preferred_language' in preferences:
            update_data['preferred_language'] = preferences['preferred_language']
        
        return self.update(contact_id, update_data, audit_context)

    def find_subscribed_to_monthly_reports(
        self,
        hostel_id: Optional[str] = None
    ) -> list[GuardianContact]:
        """
        Find guardians subscribed to monthly reports.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of subscribed contacts
        """
        query = self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.send_monthly_reports == True,
                GuardianContact.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def find_subscribed_to_payment_reminders(
        self,
        hostel_id: Optional[str] = None
    ) -> list[GuardianContact]:
        """
        Find guardians subscribed to payment reminders.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of subscribed contacts
        """
        query = self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.send_payment_reminders == True,
                GuardianContact.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def find_by_language_preference(
        self,
        language: str,
        hostel_id: Optional[str] = None
    ) -> list[GuardianContact]:
        """
        Find guardians by language preference.
        
        Args:
            language: Language code
            hostel_id: Optional hostel filter
            
        Returns:
            List of contacts with specified language
        """
        query = self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.preferred_language == language,
                GuardianContact.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    # ============================================================================
    # SEARCH AND FILTERING
    # ============================================================================

    def search_guardians(
        self,
        search_term: str,
        hostel_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[GuardianContact]:
        """
        Search guardian contacts by multiple criteria.
        
        Args:
            search_term: Search term (name, phone, email)
            hostel_id: Optional hostel filter
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of matching guardian contacts
        """
        query = self.db.query(GuardianContact).filter(
            and_(
                or_(
                    GuardianContact.guardian_name.ilike(f"%{search_term}%"),
                    GuardianContact.phone.ilike(f"%{search_term}%"),
                    GuardianContact.email.ilike(f"%{search_term}%")
                ),
                GuardianContact.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.offset(offset).limit(limit).all()

    def find_by_relation(
        self,
        relation: str,
        hostel_id: Optional[str] = None
    ) -> list[GuardianContact]:
        """
        Find guardians by relation type.
        
        Args:
            relation: Relation to student (Father, Mother, etc.)
            hostel_id: Optional hostel filter
            
        Returns:
            List of guardian contacts
        """
        query = self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.relation.ilike(f"%{relation}%"),
                GuardianContact.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def find_by_phone(
        self,
        phone: str,
        exact_match: bool = True
    ) -> list[GuardianContact]:
        """
        Find guardians by phone number.
        
        Args:
            phone: Phone number
            exact_match: Use exact match (default) or partial match
            
        Returns:
            List of guardian contacts
        """
        query = self.db.query(GuardianContact).filter(
            GuardianContact.deleted_at.is_(None)
        )
        
        if exact_match:
            query = query.filter(GuardianContact.phone == phone)
        else:
            query = query.filter(GuardianContact.phone.ilike(f"%{phone}%"))
        
        return query.all()

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_verification_statistics(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Get guardian contact verification statistics.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary with verification statistics
        """
        query = self.db.query(GuardianContact).filter(
            GuardianContact.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        total = query.count()
        
        phone_verified = query.filter(
            GuardianContact.phone_verified == True
        ).count()
        
        email_verified = query.filter(
            and_(
                GuardianContact.email.isnot(None),
                GuardianContact.email_verified == True
            )
        ).count()
        
        id_verified = query.filter(
            and_(
                GuardianContact.id_proof_number.isnot(None),
                GuardianContact.id_verified == True
            )
        ).count()
        
        fully_verified = query.filter(
            and_(
                GuardianContact.phone_verified == True,
                GuardianContact.email_verified == True,
                GuardianContact.id_verified == True
            )
        ).count()
        
        return {
            'total_contacts': total,
            'phone_verified': phone_verified,
            'email_verified': email_verified,
            'id_verified': id_verified,
            'fully_verified': fully_verified,
            'verification_rate': round((fully_verified / total * 100), 2) if total > 0 else 0
        }

    def get_relation_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get distribution of guardian relations.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary mapping relations to counts
        """
        query = self.db.query(
            GuardianContact.relation,
            func.count(GuardianContact.id).label('count')
        ).filter(GuardianContact.deleted_at.is_(None))
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        query = query.group_by(GuardianContact.relation)
        
        results = query.all()
        
        return {relation: count for relation, count in results}

    def count_by_student(self, student_id: str) -> int:
        """
        Count guardian contacts for a student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Count of guardian contacts
        """
        return self.db.query(func.count(GuardianContact.id)).filter(
            and_(
                GuardianContact.student_id == student_id,
                GuardianContact.deleted_at.is_(None)
            )
        ).scalar()

    # ============================================================================
    # BULK OPERATIONS
    # ============================================================================

    def bulk_update_communication_preference(
        self,
        contact_ids: list[str],
        preference: str,
        enabled: bool,
        audit_context: Optional[dict[str, Any]] = None
    ) -> int:
        """
        Bulk update communication preference.
        
        Args:
            contact_ids: List of guardian contact UUIDs
            preference: Preference name
            enabled: Enable or disable
            audit_context: Audit context
            
        Returns:
            Number of contacts updated
        """
        valid_preferences = [
            'send_monthly_reports',
            'send_payment_reminders',
            'send_attendance_alerts'
        ]
        
        if preference not in valid_preferences:
            return 0
        
        updated = self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.id.in_(contact_ids),
                GuardianContact.deleted_at.is_(None)
            )
        ).update(
            {
                preference: enabled,
                'updated_at': datetime.utcnow(),
                'updated_by': audit_context.get('user_id') if audit_context else None
            },
            synchronize_session=False
        )
        
        self.db.flush()
        return updated

    # ============================================================================
    # VALIDATION
    # ============================================================================

    def exists_for_student(
        self,
        student_id: str,
        phone: Optional[str] = None
    ) -> bool:
        """
        Check if guardian contact exists for student.
        
        Args:
            student_id: Student UUID
            phone: Optional phone number to check
            
        Returns:
            Existence status
        """
        query = self.db.query(GuardianContact).filter(
            and_(
                GuardianContact.student_id == student_id,
                GuardianContact.deleted_at.is_(None)
            )
        )
        
        if phone:
            query = query.filter(GuardianContact.phone == phone)
        
        return self.db.query(query.exists()).scalar()