"""
Guardian contact service.

Guardian/parent contact management with emergency contact handling,
verification, and communication tracking.
"""

from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.student.guardian_contact_repository import GuardianContactRepository
from app.repositories.student.student_repository import StudentRepository
from app.models.student.guardian_contact import GuardianContact
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    BusinessRuleViolationError
)


class GuardianContactService:
    """
    Guardian contact service for comprehensive guardian management.
    
    Handles:
        - Guardian contact CRUD
        - Multiple guardians per student
        - Emergency contact management
        - Verification workflows
        - Authorization management
        - Communication preferences
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.guardian_repo = GuardianContactRepository(db)
        self.student_repo = StudentRepository(db)

    # ============================================================================
    # GUARDIAN CRUD OPERATIONS
    # ============================================================================

    def create_guardian_contact(
        self,
        student_id: str,
        guardian_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> GuardianContact:
        """
        Create guardian contact for student.
        
        Args:
            student_id: Student UUID
            guardian_data: Guardian information
            audit_context: Audit context
            
        Returns:
            Created guardian contact instance
            
        Raises:
            NotFoundError: If student not found
            ValidationError: If validation fails
        """
        try:
            # Validate student exists
            student = self.student_repo.find_by_id(student_id)
            if not student:
                raise NotFoundError(f"Student {student_id} not found")
            
            # Validate required fields
            self._validate_guardian_data(guardian_data)
            
            guardian_data['student_id'] = student_id
            
            # Set default priority if not provided
            if 'priority' not in guardian_data:
                # Get next priority number
                existing_count = self.guardian_repo.count_by_student(student_id)
                guardian_data['priority'] = existing_count + 1
            
            guardian = self.guardian_repo.create(guardian_data, audit_context)
            
            self.db.commit()
            
            return guardian
            
        except (NotFoundError, ValidationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def _validate_guardian_data(self, guardian_data: dict[str, Any]) -> None:
        """
        Validate guardian data.
        
        Args:
            guardian_data: Guardian information
            
        Raises:
            ValidationError: If validation fails
        """
        required_fields = ['guardian_name', 'relation', 'phone']
        
        for field in required_fields:
            if field not in guardian_data or not guardian_data[field]:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate phone number format (basic validation)
        phone = guardian_data['phone']
        if not phone.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise ValidationError(f"Invalid phone number format: {phone}")
        
        # Validate relation
        valid_relations = [
            'Father', 'Mother', 'Guardian', 'Uncle', 'Aunt',
            'Brother', 'Sister', 'Grandfather', 'Grandmother', 'Other'
        ]
        
        relation = guardian_data.get('relation', '')
        if relation not in valid_relations:
            raise ValidationError(
                f"Invalid relation: {relation}. Must be one of {valid_relations}"
            )

    def get_guardian_by_id(
        self,
        guardian_id: str,
        include_student: bool = False
    ) -> GuardianContact:
        """
        Get guardian contact by ID.
        
        Args:
            guardian_id: Guardian contact UUID
            include_student: Load student entity
            
        Returns:
            Guardian contact instance
            
        Raises:
            NotFoundError: If guardian not found
        """
        guardian = self.guardian_repo.find_by_id(
            guardian_id,
            eager_load=include_student
        )
        
        if not guardian:
            raise NotFoundError(f"Guardian contact {guardian_id} not found")
        
        return guardian

    def get_student_guardians(
        self,
        student_id: str,
        verified_only: bool = False
    ) -> list[GuardianContact]:
        """
        Get all guardian contacts for a student.
        
        Args:
            student_id: Student UUID
            verified_only: Return only verified contacts
            
        Returns:
            List of guardian contacts
        """
        return self.guardian_repo.find_by_student_id(
            student_id,
            verified_only=verified_only
        )

    def update_guardian_contact(
        self,
        guardian_id: str,
        update_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> GuardianContact:
        """
        Update guardian contact.
        
        Args:
            guardian_id: Guardian contact UUID
            update_data: Fields to update
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance
            
        Raises:
            NotFoundError: If guardian not found
        """
        try:
            guardian = self.guardian_repo.update(
                guardian_id,
                update_data,
                audit_context
            )
            
            if not guardian:
                raise NotFoundError(f"Guardian contact {guardian_id} not found")
            
            self.db.commit()
            
            return guardian
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # PRIMARY CONTACT MANAGEMENT
    # ============================================================================

    def get_primary_contact(self, student_id: str) -> Optional[GuardianContact]:
        """
        Get primary guardian contact for student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Primary guardian contact or None
        """
        return self.guardian_repo.get_primary_contact(student_id)

    def set_primary_contact(
        self,
        guardian_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> GuardianContact:
        """
        Set guardian contact as primary.
        
        Args:
            guardian_id: Guardian contact UUID
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance
        """
        try:
            guardian = self.guardian_repo.set_primary_contact(
                guardian_id,
                audit_context
            )
            
            if not guardian:
                raise NotFoundError(f"Guardian contact {guardian_id} not found")
            
            self.db.commit()
            
            return guardian
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # EMERGENCY CONTACT MANAGEMENT
    # ============================================================================

    def get_emergency_contacts(
        self,
        student_id: str,
        available_24x7_only: bool = False
    ) -> list[GuardianContact]:
        """
        Get emergency contacts for student.
        
        Args:
            student_id: Student UUID
            available_24x7_only: Return only 24x7 available contacts
            
        Returns:
            List of emergency contacts ordered by priority
        """
        return self.guardian_repo.get_emergency_contacts(
            student_id,
            available_24x7_only
        )

    def get_first_emergency_contact(
        self,
        student_id: str
    ) -> Optional[GuardianContact]:
        """
        Get first priority emergency contact.
        
        Args:
            student_id: Student UUID
            
        Returns:
            First emergency contact or None
        """
        return self.guardian_repo.get_first_emergency_contact(student_id)

    def update_emergency_priority(
        self,
        guardian_id: str,
        priority: int,
        audit_context: Optional[dict[str, Any]] = None
    ) -> GuardianContact:
        """
        Update emergency contact priority.
        
        Args:
            guardian_id: Guardian contact UUID
            priority: Emergency priority (1=highest)
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance
        """
        try:
            if priority < 1:
                raise ValidationError("Priority must be at least 1")
            
            guardian = self.guardian_repo.update_emergency_priority(
                guardian_id,
                priority,
                audit_context
            )
            
            if not guardian:
                raise NotFoundError(f"Guardian contact {guardian_id} not found")
            
            self.db.commit()
            
            return guardian
            
        except (NotFoundError, ValidationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # VERIFICATION MANAGEMENT
    # ============================================================================

    def verify_phone(
        self,
        guardian_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> GuardianContact:
        """
        Mark phone number as verified.
        
        Args:
            guardian_id: Guardian contact UUID
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance
        """
        try:
            guardian = self.guardian_repo.verify_phone(
                guardian_id,
                audit_context
            )
            
            if not guardian:
                raise NotFoundError(f"Guardian contact {guardian_id} not found")
            
            self.db.commit()
            
            return guardian
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def verify_email(
        self,
        guardian_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> GuardianContact:
        """
        Mark email as verified.
        
        Args:
            guardian_id: Guardian contact UUID
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance
        """
        try:
            guardian = self.guardian_repo.verify_email(
                guardian_id,
                audit_context
            )
            
            if not guardian:
                raise NotFoundError(f"Guardian contact {guardian_id} not found")
            
            self.db.commit()
            
            return guardian
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def verify_id_proof(
        self,
        guardian_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> GuardianContact:
        """
        Mark ID proof as verified.
        
        Args:
            guardian_id: Guardian contact UUID
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance
        """
        try:
            guardian = self.guardian_repo.verify_id_proof(
                guardian_id,
                audit_context
            )
            
            if not guardian:
                raise NotFoundError(f"Guardian contact {guardian_id} not found")
            
            self.db.commit()
            
            return guardian
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def get_unverified_contacts(
        self,
        verification_type: str,
        hostel_id: Optional[str] = None
    ) -> list[GuardianContact]:
        """
        Get contacts with pending verification.
        
        Args:
            verification_type: Type of verification (phone, email, id)
            hostel_id: Optional hostel filter
            
        Returns:
            List of unverified contacts
        """
        return self.guardian_repo.find_unverified_contacts(
            verification_type,
            hostel_id
        )

    # ============================================================================
    # AUTHORIZATION MANAGEMENT
    # ============================================================================

    def update_authorizations(
        self,
        guardian_id: str,
        authorizations: dict[str, bool],
        audit_context: Optional[dict[str, Any]] = None
    ) -> GuardianContact:
        """
        Update guardian authorizations.
        
        Args:
            guardian_id: Guardian contact UUID
            authorizations: Dictionary of authorization settings
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance
        """
        try:
            guardian = self.guardian_repo.update_authorizations(
                guardian_id,
                authorizations,
                audit_context
            )
            
            if not guardian:
                raise NotFoundError(f"Guardian contact {guardian_id} not found")
            
            self.db.commit()
            
            return guardian
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

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
        return self.guardian_repo.get_authorized_for_pickup(student_id)

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
        return self.guardian_repo.get_financial_guardians(student_id)

    # ============================================================================
    # COMMUNICATION PREFERENCES
    # ============================================================================

    def update_communication_preferences(
        self,
        guardian_id: str,
        preferences: dict[str, bool],
        audit_context: Optional[dict[str, Any]] = None
    ) -> GuardianContact:
        """
        Update communication preferences.
        
        Args:
            guardian_id: Guardian contact UUID
            preferences: Dictionary of communication preferences
            audit_context: Audit context
            
        Returns:
            Updated guardian contact instance
        """
        try:
            guardian = self.guardian_repo.update_communication_preferences(
                guardian_id,
                preferences,
                audit_context
            )
            
            if not guardian:
                raise NotFoundError(f"Guardian contact {guardian_id} not found")
            
            self.db.commit()
            
            return guardian
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # SEARCH AND STATISTICS
    # ============================================================================

    def search_guardians(
        self,
        search_term: str,
        hostel_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[GuardianContact]:
        """
        Search guardian contacts.
        
        Args:
            search_term: Search term
            hostel_id: Optional hostel filter
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of matching guardian contacts
        """
        return self.guardian_repo.search_guardians(
            search_term,
            hostel_id,
            offset,
            limit
        )

    def get_verification_statistics(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Get verification statistics.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Verification statistics
        """
        return self.guardian_repo.get_verification_statistics(hostel_id)

    def get_relation_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get distribution of guardian relations.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Relation distribution
        """
        return self.guardian_repo.get_relation_distribution(hostel_id)

    # ============================================================================
    # DELETE OPERATIONS
    # ============================================================================

    def soft_delete_guardian(
        self,
        guardian_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> bool:
        """
        Soft delete guardian contact.
        
        Args:
            guardian_id: Guardian contact UUID
            audit_context: Audit context
            
        Returns:
            Success status
            
        Raises:
            BusinessRuleViolationError: If guardian is primary or only contact
        """
        try:
            guardian = self.get_guardian_by_id(guardian_id)
            
            # Check if this is the only guardian
            all_guardians = self.get_student_guardians(guardian.student_id)
            if len(all_guardians) == 1:
                raise BusinessRuleViolationError(
                    "Cannot delete the only guardian contact. "
                    "Add another guardian first."
                )
            
            # Check if this is the primary guardian
            if guardian.is_primary:
                raise BusinessRuleViolationError(
                    "Cannot delete primary guardian. "
                    "Set another guardian as primary first."
                )
            
            success = self.guardian_repo.soft_delete(guardian_id, audit_context)
            
            self.db.commit()
            
            return success
            
        except BusinessRuleViolationError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")