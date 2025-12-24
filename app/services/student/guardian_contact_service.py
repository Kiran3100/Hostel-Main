# app/services/student/guardian_contact_service.py
"""
Guardian Contact Service

Manages guardian/parent contacts for students.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.student import GuardianContactRepository
from app.models.student.guardian_contact import GuardianContact
from app.core.exceptions import ValidationException


class GuardianContactService:
    """
    High-level service for guardian contacts attached to a student.

    Responsibilities:
    - List guardian contacts for a student
    - Create/update/delete guardian contacts
    - Set primary guardian contact
    """

    def __init__(
        self,
        guardian_repo: GuardianContactRepository,
    ) -> None:
        self.guardian_repo = guardian_repo

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def list_guardians(
        self,
        db: Session,
        student_id: UUID,
    ) -> List[GuardianContact]:
        """
        Return all guardian contacts for a student (ORM instances).
        """
        return self.guardian_repo.get_by_student_id(db, student_id)

    def get_guardian(
        self,
        db: Session,
        guardian_id: UUID,
    ) -> GuardianContact:
        """
        Get a guardian contact by id.
        """
        contact = self.guardian_repo.get_by_id(db, guardian_id)
        if not contact:
            raise ValidationException("Guardian contact not found")
        return contact

    def create_guardian(
        self,
        db: Session,
        student_id: UUID,
        name: str,
        phone: str,
        relation: str,
        email: str | None = None,
        is_primary: bool = False,
    ) -> GuardianContact:
        """
        Create a new guardian contact for a student.
        """
        if is_primary:
            self.guardian_repo.clear_primary_for_student(db, student_id)

        contact = self.guardian_repo.create(
            db,
            data={
                "student_id": student_id,
                "name": name,
                "phone": phone,
                "relation": relation,
                "email": email,
                "is_primary": is_primary,
            },
        )
        return contact

    def update_guardian(
        self,
        db: Session,
        guardian_id: UUID,
        name: str,
        phone: str,
        relation: str,
        email: str | None,
        is_primary: bool,
    ) -> GuardianContact:
        """
        Update an existing guardian contact.
        """
        contact = self.get_guardian(db, guardian_id)

        if is_primary:
            self.guardian_repo.clear_primary_for_student(db, contact.student_id)

        updated = self.guardian_repo.update(
            db,
            obj=contact,
            data={
                "name": name,
                "phone": phone,
                "relation": relation,
                "email": email,
                "is_primary": is_primary,
            },
        )
        return updated

    def delete_guardian(
        self,
        db: Session,
        guardian_id: UUID,
    ) -> None:
        """
        Delete a guardian contact.
        """
        contact = self.guardian_repo.get_by_id(db, guardian_id)
        if not contact:
            return
        self.guardian_repo.delete(db, contact)

    # -------------------------------------------------------------------------
    # Primary guardian
    # -------------------------------------------------------------------------

    def set_primary_guardian(
        self,
        db: Session,
        guardian_id: UUID,
    ) -> GuardianContact:
        """
        Mark a guardian as the primary contact.
        """
        contact = self.get_guardian(db, guardian_id)

        self.guardian_repo.clear_primary_for_student(db, contact.student_id)
        updated = self.guardian_repo.update(
            db,
            obj=contact,
            data={"is_primary": True},
        )
        return updated