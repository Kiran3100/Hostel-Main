"""
Emergency Contact Service

Manages user-level emergency contacts (separate from student-specific contacts).
Enhanced with validation, bulk operations, and improved error handling.
"""

import logging
from typing import List, Union, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.user import EmergencyContactRepository
from app.core.exceptions import (
    ValidationError,
    BusinessLogicError,
    NotFoundError,
)
from app.models.user.emergency_contact import EmergencyContact
from app.utils.string_utils import StringHelper

logger = logging.getLogger(__name__)


class EmergencyContactService:
    """
    High-level service for user emergency contacts.

    Responsibilities:
    - List emergency contacts for a user
    - Create/update/delete emergency contacts
    - Set primary emergency contact
    - Validate contact information
    - Bulk operations support
    """

    # Business rules
    MAX_CONTACTS_PER_USER = 5
    MIN_PHONE_LENGTH = 10
    MAX_PHONE_LENGTH = 15

    def __init__(
        self,
        emergency_contact_repo: EmergencyContactRepository,
    ) -> None:
        self.emergency_contact_repo = emergency_contact_repo

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def list_contacts(
        self,
        db: Session,
        user_id: UUID,
        include_inactive: bool = False,
    ) -> List[EmergencyContact]:
        """
        Return all emergency contacts for a user.

        Args:
            db: Database session
            user_id: User identifier
            include_inactive: Whether to include soft-deleted contacts

        Returns:
            List of EmergencyContact instances ordered by is_primary DESC, created_at DESC
        """
        try:
            contacts = self.emergency_contact_repo.get_by_user_id(db, user_id)
            
            # Sort: primary first, then by creation date
            contacts.sort(key=lambda x: (not x.is_primary, x.created_at), reverse=True)
            
            return contacts
        except SQLAlchemyError as e:
            logger.error(f"Database error listing contacts for user {user_id}: {str(e)}")
            raise BusinessLogicError("Failed to retrieve emergency contacts")

    def get_contact(
        self,
        db: Session,
        contact_id: UUID,
        user_id: Union[UUID, None] = None,
    ) -> EmergencyContact:
        """
        Get an emergency contact by ID with optional user ownership verification.

        Args:
            db: Database session
            contact_id: Contact identifier
            user_id: Optional user ID for ownership verification

        Returns:
            EmergencyContact instance

        Raises:
            NotFoundError: If contact doesn't exist
            ValidationError: If user_id provided and doesn't match
        """
        contact = self.emergency_contact_repo.get_by_id(db, contact_id)
        if not contact:
            raise NotFoundError(f"Emergency contact {contact_id} not found")

        # Verify ownership if user_id provided
        if user_id and contact.user_id != user_id:
            raise ValidationError("Contact does not belong to the specified user")

        return contact

    def get_primary_contact(
        self,
        db: Session,
        user_id: UUID,
    ) -> Union[EmergencyContact, None]:
        """
        Get the primary emergency contact for a user.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            Primary EmergencyContact or None
        """
        contacts = self.list_contacts(db, user_id)
        return next((c for c in contacts if c.is_primary), None)

    def create_contact(
        self,
        db: Session,
        user_id: UUID,
        name: str,
        phone: str,
        relation: str,
        is_primary: bool = False,
        email: Union[str, None] = None,
        address: Union[str, None] = None,
    ) -> EmergencyContact:
        """
        Create a new emergency contact for a user.

        Args:
            db: Database session
            user_id: User identifier
            name: Contact name
            phone: Contact phone number
            relation: Relationship to user
            is_primary: Whether this is the primary contact
            email: Optional contact email
            address: Optional contact address

        Returns:
            Created EmergencyContact instance

        Raises:
            ValidationError: If validation fails
            BusinessLogicError: If business rules violated
        """
        # Validate inputs
        self._validate_contact_data(name, phone, relation, email)

        # Check contact limit
        existing_contacts = self.list_contacts(db, user_id)
        if len(existing_contacts) >= self.MAX_CONTACTS_PER_USER:
            raise BusinessLogicError(
                f"Maximum {self.MAX_CONTACTS_PER_USER} emergency contacts allowed per user"
            )

        try:
            # If setting as primary, clear existing primary
            if is_primary:
                self._clear_primary_for_user(db, user_id)
            # If no contacts exist, force this to be primary
            elif not existing_contacts:
                is_primary = True

            # Normalize phone number
            normalized_phone = StringHelper.normalize_phone(phone)

            # Check for duplicate phone numbers for this user
            if self._is_duplicate_phone(db, user_id, normalized_phone):
                raise ValidationError(
                    "A contact with this phone number already exists for this user"
                )

            contact_data = {
                "user_id": user_id,
                "name": name.strip(),
                "phone": normalized_phone,
                "relation": relation.strip(),
                "is_primary": is_primary,
                "email": email.strip().lower() if email else None,
                "address": address.strip() if address else None,
            }

            contact = self.emergency_contact_repo.create(db, data=contact_data)
            
            logger.info(
                f"Created emergency contact {contact.id} for user {user_id} "
                f"(primary={is_primary})"
            )
            
            return contact

        except SQLAlchemyError as e:
            logger.error(f"Database error creating contact for user {user_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicError("Failed to create emergency contact")

    def update_contact(
        self,
        db: Session,
        contact_id: UUID,
        user_id: UUID,
        name: Union[str, None] = None,
        phone: Union[str, None] = None,
        relation: Union[str, None] = None,
        is_primary: Union[bool, None] = None,
        email: Union[str, None] = None,
        address: Union[str, None] = None,
    ) -> EmergencyContact:
        """
        Update an existing emergency contact.

        Args:
            db: Database session
            contact_id: Contact identifier
            user_id: User identifier (for ownership verification)
            name: Optional new name
            phone: Optional new phone
            relation: Optional new relation
            is_primary: Optional primary status
            email: Optional new email
            address: Optional new address

        Returns:
            Updated EmergencyContact instance

        Raises:
            NotFoundError: If contact doesn't exist
            ValidationError: If validation fails
        """
        # Verify contact exists and belongs to user
        contact = self.get_contact(db, contact_id, user_id)

        # Build update payload
        update_data: Dict[str, Any] = {}

        if name is not None:
            if not name.strip():
                raise ValidationError("Contact name cannot be empty")
            update_data["name"] = name.strip()

        if phone is not None:
            normalized_phone = StringHelper.normalize_phone(phone)
            self._validate_phone(normalized_phone)
            
            # Check for duplicates (excluding current contact)
            if self._is_duplicate_phone(db, user_id, normalized_phone, exclude_id=contact_id):
                raise ValidationError(
                    "A contact with this phone number already exists for this user"
                )
            
            update_data["phone"] = normalized_phone

        if relation is not None:
            if not relation.strip():
                raise ValidationError("Relation cannot be empty")
            update_data["relation"] = relation.strip()

        if email is not None:
            if email.strip():
                self._validate_email(email)
                update_data["email"] = email.strip().lower()
            else:
                update_data["email"] = None

        if address is not None:
            update_data["address"] = address.strip() if address.strip() else None

        if is_primary is not None:
            if is_primary and not contact.is_primary:
                self._clear_primary_for_user(db, user_id)
            update_data["is_primary"] = is_primary

        try:
            updated = self.emergency_contact_repo.update(
                db,
                obj=contact,
                data=update_data,
            )
            
            logger.info(f"Updated emergency contact {contact_id} for user {user_id}")
            
            return updated

        except SQLAlchemyError as e:
            logger.error(f"Database error updating contact {contact_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicError("Failed to update emergency contact")

    def delete_contact(
        self,
        db: Session,
        contact_id: UUID,
        user_id: UUID,
    ) -> None:
        """
        Delete an emergency contact.

        If deleting the primary contact and other contacts exist,
        automatically promotes the next contact to primary.

        Args:
            db: Database session
            contact_id: Contact identifier
            user_id: User identifier (for ownership verification)

        Raises:
            NotFoundError: If contact doesn't exist
            BusinessLogicError: If trying to delete the last contact
        """
        # Verify contact exists and belongs to user
        contact = self.get_contact(db, contact_id, user_id)

        try:
            was_primary = contact.is_primary
            
            # Delete the contact
            self.emergency_contact_repo.delete(db, contact)

            # If deleted contact was primary, promote another
            if was_primary:
                remaining = self.list_contacts(db, user_id)
                if remaining:
                    # Promote the first remaining contact to primary
                    self.emergency_contact_repo.update(
                        db,
                        obj=remaining[0],
                        data={"is_primary": True},
                    )
                    logger.info(
                        f"Promoted contact {remaining[0].id} to primary after deleting {contact_id}"
                    )

            logger.info(f"Deleted emergency contact {contact_id} for user {user_id}")

        except SQLAlchemyError as e:
            logger.error(f"Database error deleting contact {contact_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicError("Failed to delete emergency contact")

    # -------------------------------------------------------------------------
    # Primary Contact Management
    # -------------------------------------------------------------------------

    def set_primary_contact(
        self,
        db: Session,
        contact_id: UUID,
        user_id: UUID,
    ) -> EmergencyContact:
        """
        Mark a contact as primary and clear previous primary.

        Args:
            db: Database session
            contact_id: Contact identifier
            user_id: User identifier (for ownership verification)

        Returns:
            Updated EmergencyContact instance

        Raises:
            NotFoundError: If contact doesn't exist
        """
        # Verify contact exists and belongs to user
        contact = self.get_contact(db, contact_id, user_id)

        if contact.is_primary:
            # Already primary, no action needed
            return contact

        try:
            # Clear existing primary
            self._clear_primary_for_user(db, user_id)

            # Set new primary
            updated = self.emergency_contact_repo.update(
                db,
                obj=contact,
                data={"is_primary": True},
            )

            logger.info(f"Set contact {contact_id} as primary for user {user_id}")

            return updated

        except SQLAlchemyError as e:
            logger.error(f"Database error setting primary contact {contact_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicError("Failed to set primary contact")

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def bulk_create_contacts(
        self,
        db: Session,
        user_id: UUID,
        contacts_data: List[Dict[str, Any]],
    ) -> List[EmergencyContact]:
        """
        Create multiple emergency contacts in a single transaction.

        Args:
            db: Database session
            user_id: User identifier
            contacts_data: List of contact data dictionaries

        Returns:
            List of created EmergencyContact instances

        Raises:
            ValidationError: If validation fails
            BusinessLogicError: If business rules violated
        """
        if not contacts_data:
            return []

        # Check total limit
        existing_count = len(self.list_contacts(db, user_id))
        if existing_count + len(contacts_data) > self.MAX_CONTACTS_PER_USER:
            raise BusinessLogicError(
                f"Cannot create {len(contacts_data)} contacts. "
                f"Maximum {self.MAX_CONTACTS_PER_USER} contacts allowed per user"
            )

        created_contacts = []
        
        try:
            for idx, data in enumerate(contacts_data):
                # Set first as primary if no existing contacts and not explicitly set
                is_primary = data.get("is_primary", False)
                if idx == 0 and existing_count == 0 and not any(
                    c.get("is_primary") for c in contacts_data
                ):
                    is_primary = True

                contact = self.create_contact(
                    db=db,
                    user_id=user_id,
                    name=data["name"],
                    phone=data["phone"],
                    relation=data["relation"],
                    is_primary=is_primary,
                    email=data.get("email"),
                    address=data.get("address"),
                )
                created_contacts.append(contact)

            logger.info(
                f"Bulk created {len(created_contacts)} emergency contacts for user {user_id}"
            )

            return created_contacts

        except Exception as e:
            logger.error(f"Error in bulk create contacts for user {user_id}: {str(e)}")
            db.rollback()
            raise

    def delete_all_contacts(
        self,
        db: Session,
        user_id: UUID,
    ) -> int:
        """
        Delete all emergency contacts for a user.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            Number of contacts deleted
        """
        contacts = self.list_contacts(db, user_id)
        
        try:
            for contact in contacts:
                self.emergency_contact_repo.delete(db, contact)

            count = len(contacts)
            logger.info(f"Deleted all {count} emergency contacts for user {user_id}")
            
            return count

        except SQLAlchemyError as e:
            logger.error(f"Database error deleting all contacts for user {user_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicError("Failed to delete emergency contacts")

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_contact_data(
        self,
        name: str,
        phone: str,
        relation: str,
        email: Union[str, None] = None,
    ) -> None:
        """Validate contact data before creation/update."""
        if not name or not name.strip():
            raise ValidationError("Contact name is required")

        if len(name.strip()) < 2:
            raise ValidationError("Contact name must be at least 2 characters")

        if len(name.strip()) > 100:
            raise ValidationError("Contact name must not exceed 100 characters")

        self._validate_phone(phone)

        if not relation or not relation.strip():
            raise ValidationError("Relation is required")

        if len(relation.strip()) > 50:
            raise ValidationError("Relation must not exceed 50 characters")

        if email:
            self._validate_email(email)

    def _validate_phone(self, phone: str) -> None:
        """Validate phone number format."""
        if not phone or not phone.strip():
            raise ValidationError("Phone number is required")

        normalized = StringHelper.normalize_phone(phone)
        
        if len(normalized) < self.MIN_PHONE_LENGTH:
            raise ValidationError(
                f"Phone number must be at least {self.MIN_PHONE_LENGTH} digits"
            )

        if len(normalized) > self.MAX_PHONE_LENGTH:
            raise ValidationError(
                f"Phone number must not exceed {self.MAX_PHONE_LENGTH} digits"
            )

        if not normalized.isdigit():
            raise ValidationError("Phone number must contain only digits")

    def _validate_email(self, email: str) -> None:
        """Validate email format."""
        if not StringHelper.is_valid_email(email):
            raise ValidationError("Invalid email format")

    def _is_duplicate_phone(
        self,
        db: Session,
        user_id: UUID,
        phone: str,
        exclude_id: Union[UUID, None] = None,
    ) -> bool:
        """Check if phone number already exists for user."""
        contacts = self.list_contacts(db, user_id)
        
        for contact in contacts:
            if exclude_id and contact.id == exclude_id:
                continue
            if contact.phone == phone:
                return True
        
        return False

    def _clear_primary_for_user(self, db: Session, user_id: UUID) -> None:
        """Clear primary status for all contacts of a user."""
        self.emergency_contact_repo.clear_primary_for_user(db, user_id)