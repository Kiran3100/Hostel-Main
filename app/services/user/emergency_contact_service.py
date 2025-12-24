"""
Emergency Contact Service

Manages user-level emergency contacts (separate from student-specific contacts).
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.user import EmergencyContactRepository
from app.core.exceptions import ValidationException
from app.models.user.emergency_contact import EmergencyContact


class EmergencyContactService:
    """
    High-level service for user emergency contacts.

    Responsibilities:
    - List emergency contacts for a user
    - Create/update/delete emergency contacts
    - Set primary emergency contact
    """

    def __init__(
        self,
        emergency_contact_repo: EmergencyContactRepository,
    ) -> None:
        self.emergency_contact_repo = emergency_contact_repo

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def list_contacts(
        self,
        db: Session,
        user_id: UUID,
    ) -> List[EmergencyContact]:
        """
        Return all emergency contacts for a user (ORM instances).
        """
        return self.emergency_contact_repo.get_by_user_id(db, user_id)

    def get_contact(
        self,
        db: Session,
        contact_id: UUID,
    ) -> EmergencyContact:
        """
        Get an emergency contact by id.
        """
        contact = self.emergency_contact_repo.get_by_id(db, contact_id)
        if not contact:
            raise ValidationException("Emergency contact not found")
        return contact

    def create_contact(
        self,
        db: Session,
        user_id: UUID,
        name: str,
        phone: str,
        relation: str,
        is_primary: bool = False,
    ) -> EmergencyContact:
        """
        Create a new emergency contact for a user.
        """
        if is_primary:
            self.emergency_contact_repo.clear_primary_for_user(db, user_id)

        contact = self.emergency_contact_repo.create(
            db,
            data={
                "user_id": user_id,
                "name": name,
                "phone": phone,
                "relation": relation,
                "is_primary": is_primary,
            },
        )
        return contact

    def update_contact(
        self,
        db: Session,
        contact_id: UUID,
        name: str,
        phone: str,
        relation: str,
        is_primary: bool,
    ) -> EmergencyContact:
        """
        Update an existing emergency contact.
        """
        contact = self.get_contact(db, contact_id)

        if is_primary:
            self.emergency_contact_repo.clear_primary_for_user(db, contact.user_id)

        updated = self.emergency_contact_repo.update(
            db,
            obj=contact,
            data={
                "name": name,
                "phone": phone,
                "relation": relation,
                "is_primary": is_primary,
            },
        )
        return updated

    def delete_contact(
        self,
        db: Session,
        contact_id: UUID,
    ) -> None:
        """
        Delete an emergency contact.
        """
        contact = self.emergency_contact_repo.get_by_id(db, contact_id)
        if not contact:
            return
        self.emergency_contact_repo.delete(db, contact)

    # -------------------------------------------------------------------------
    # Primary contact
    # -------------------------------------------------------------------------

    def set_primary_contact(
        self,
        db: Session,
        contact_id: UUID,
    ) -> EmergencyContact:
        """
        Mark a contact as primary and clear previous primary.
        """
        contact = self.get_contact(db, contact_id)

        self.emergency_contact_repo.clear_primary_for_user(db, contact.user_id)
        updated = self.emergency_contact_repo.update(
            db,
            obj=contact,
            data={"is_primary": True},
        )
        return updated