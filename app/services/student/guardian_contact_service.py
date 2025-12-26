# app/services/student/guardian_contact_service.py
"""
Guardian Contact Service

Manages guardian/parent contacts for students with validation and primary contact management.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.student import GuardianContactRepository
from app.models.student.guardian_contact import GuardianContact
from app.core.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)

logger = logging.getLogger(__name__)


class GuardianContactService:
    """
    High-level service for guardian/parent contact management.

    Responsibilities:
    - List guardian contacts for students
    - Create, update, and delete contacts
    - Manage primary guardian designation
    - Validate contact information
    - Handle emergency contact scenarios

    Business rules:
    - Each student can have multiple guardians
    - Only one guardian can be marked as primary
    - Primary guardian must have valid phone number
    - At least one guardian recommended for all students
    """

    def __init__(
        self,
        guardian_repo: GuardianContactRepository,
    ) -> None:
        """
        Initialize service with guardian repository.

        Args:
            guardian_repo: Repository for guardian operations
        """
        self.guardian_repo = guardian_repo

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def list_guardians(
        self,
        db: Session,
        student_id: UUID,
        primary_only: bool = False,
    ) -> List[GuardianContact]:
        """
        Return all guardian contacts for a student.

        Args:
            db: Database session
            student_id: UUID of student
            primary_only: If True, return only primary guardian

        Returns:
            List of GuardianContact ORM instances
        """
        try:
            if primary_only:
                primary = self.guardian_repo.get_primary_for_student(db, student_id)
                return [primary] if primary else []
            
            return self.guardian_repo.get_by_student_id(db, student_id)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error listing guardians for {student_id}: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to list guardians: {str(e)}"
            ) from e

    def get_guardian(
        self,
        db: Session,
        guardian_id: UUID,
    ) -> GuardianContact:
        """
        Get a guardian contact by ID.

        Args:
            db: Database session
            guardian_id: UUID of guardian

        Returns:
            GuardianContact ORM instance

        Raises:
            NotFoundException: If guardian not found
        """
        contact = self.guardian_repo.get_by_id(db, guardian_id)
        
        if not contact:
            raise NotFoundException(f"Guardian contact not found: {guardian_id}")
        
        return contact

    def get_primary_guardian(
        self,
        db: Session,
        student_id: UUID,
    ) -> Optional[GuardianContact]:
        """
        Get the primary guardian for a student.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            GuardianContact or None if no primary guardian set
        """
        try:
            return self.guardian_repo.get_primary_for_student(db, student_id)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error getting primary guardian for {student_id}: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to get primary guardian: {str(e)}"
            ) from e

    def create_guardian(
        self,
        db: Session,
        student_id: UUID,
        name: str,
        phone: str,
        relation: str,
        email: Optional[str] = None,
        is_primary: bool = False,
        **additional_fields,
    ) -> GuardianContact:
        """
        Create a new guardian contact for a student.

        Args:
            db: Database session
            student_id: UUID of student
            name: Guardian's full name
            phone: Contact phone number
            relation: Relationship to student (e.g., 'father', 'mother')
            email: Optional email address
            is_primary: Whether to set as primary guardian
            **additional_fields: Additional guardian data

        Returns:
            GuardianContact: Created guardian

        Raises:
            ValidationException: If validation fails
        """
        # Validate required fields
        self._validate_guardian_data(name, phone, relation, email)

        # If marking as primary, clear existing primary
        if is_primary:
            try:
                self.guardian_repo.clear_primary_for_student(db, student_id)
            except SQLAlchemyError as e:
                logger.error(f"Error clearing primary guardian: {str(e)}")
                raise BusinessLogicException(
                    f"Failed to update primary guardian: {str(e)}"
                ) from e

        try:
            contact = self.guardian_repo.create(
                db,
                data={
                    "student_id": student_id,
                    "name": name,
                    "phone": phone,
                    "relation": relation,
                    "email": email,
                    "is_primary": is_primary,
                    **additional_fields,
                },
            )
            
            logger.info(
                f"Guardian created: {contact.id} for student: {student_id}, "
                f"primary: {is_primary}"
            )
            
            return contact

        except SQLAlchemyError as e:
            logger.error(f"Database error creating guardian: {str(e)}")
            raise BusinessLogicException(
                f"Failed to create guardian: {str(e)}"
            ) from e

    def update_guardian(
        self,
        db: Session,
        guardian_id: UUID,
        name: str,
        phone: str,
        relation: str,
        email: Optional[str],
        is_primary: bool,
        **additional_updates,
    ) -> GuardianContact:
        """
        Update an existing guardian contact.

        Args:
            db: Database session
            guardian_id: UUID of guardian
            name: Guardian's full name
            phone: Contact phone number
            relation: Relationship to student
            email: Optional email address
            is_primary: Whether to set as primary guardian
            **additional_updates: Additional fields to update

        Returns:
            GuardianContact: Updated guardian

        Raises:
            NotFoundException: If guardian not found
            ValidationException: If validation fails
        """
        contact = self.get_guardian(db, guardian_id)

        # Validate updated data
        self._validate_guardian_data(name, phone, relation, email)

        # If marking as primary, clear existing primary for this student
        if is_primary and not contact.is_primary:
            try:
                self.guardian_repo.clear_primary_for_student(db, contact.student_id)
            except SQLAlchemyError as e:
                logger.error(f"Error clearing primary guardian: {str(e)}")
                raise BusinessLogicException(
                    f"Failed to update primary guardian: {str(e)}"
                ) from e

        try:
            updated = self.guardian_repo.update(
                db,
                obj=contact,
                data={
                    "name": name,
                    "phone": phone,
                    "relation": relation,
                    "email": email,
                    "is_primary": is_primary,
                    **additional_updates,
                },
            )
            
            logger.info(
                f"Guardian updated: {guardian_id}, primary: {is_primary}"
            )
            
            return updated

        except SQLAlchemyError as e:
            logger.error(f"Database error updating guardian: {str(e)}")
            raise BusinessLogicException(
                f"Failed to update guardian: {str(e)}"
            ) from e

    def delete_guardian(
        self,
        db: Session,
        guardian_id: UUID,
        allow_delete_primary: bool = False,
    ) -> None:
        """
        Delete a guardian contact.

        Args:
            db: Database session
            guardian_id: UUID of guardian
            allow_delete_primary: Allow deletion of primary guardian

        Raises:
            ValidationException: If trying to delete primary without permission
        """
        contact = self.guardian_repo.get_by_id(db, guardian_id)
        
        if not contact:
            logger.warning(f"Guardian not found for deletion: {guardian_id}")
            return

        # Check if primary guardian
        if contact.is_primary and not allow_delete_primary:
            raise ValidationException(
                "Cannot delete primary guardian. "
                "Please designate another guardian as primary first."
            )

        try:
            self.guardian_repo.delete(db, contact)
            logger.info(f"Guardian deleted: {guardian_id}")

        except SQLAlchemyError as e:
            logger.error(f"Database error deleting guardian: {str(e)}")
            raise BusinessLogicException(
                f"Failed to delete guardian: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Primary Guardian Management
    # -------------------------------------------------------------------------

    def set_primary_guardian(
        self,
        db: Session,
        guardian_id: UUID,
    ) -> GuardianContact:
        """
        Designate a guardian as the primary contact.

        Args:
            db: Database session
            guardian_id: UUID of guardian to set as primary

        Returns:
            GuardianContact: Updated guardian

        Raises:
            NotFoundException: If guardian not found
        """
        contact = self.get_guardian(db, guardian_id)

        # Validate that guardian has required information for primary contact
        if not contact.phone:
            raise ValidationException(
                "Primary guardian must have a valid phone number"
            )

        try:
            # Clear existing primary for this student
            self.guardian_repo.clear_primary_for_student(db, contact.student_id)

            # Set this guardian as primary
            updated = self.guardian_repo.update(
                db,
                obj=contact,
                data={"is_primary": True},
            )
            
            logger.info(
                f"Primary guardian set: {guardian_id} "
                f"for student: {contact.student_id}"
            )
            
            return updated

        except SQLAlchemyError as e:
            logger.error(f"Database error setting primary guardian: {str(e)}")
            raise BusinessLogicException(
                f"Failed to set primary guardian: {str(e)}"
            ) from e

    def ensure_primary_guardian(
        self,
        db: Session,
        student_id: UUID,
    ) -> Optional[GuardianContact]:
        """
        Ensure student has a primary guardian, auto-designating if needed.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            GuardianContact or None if no guardians exist
        """
        # Check if primary guardian exists
        primary = self.guardian_repo.get_primary_for_student(db, student_id)
        
        if primary:
            return primary

        # Get all guardians for student
        guardians = self.guardian_repo.get_by_student_id(db, student_id)
        
        if not guardians:
            logger.warning(f"No guardians found for student: {student_id}")
            return None

        # Set first guardian with phone as primary
        for guardian in guardians:
            if guardian.phone:
                try:
                    updated = self.guardian_repo.update(
                        db,
                        obj=guardian,
                        data={"is_primary": True},
                    )
                    logger.info(
                        f"Auto-designated primary guardian: {guardian.id} "
                        f"for student: {student_id}"
                    )
                    return updated
                except SQLAlchemyError as e:
                    logger.error(f"Error auto-designating primary: {str(e)}")
                    continue

        return None

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_guardian_data(
        self,
        name: str,
        phone: str,
        relation: str,
        email: Optional[str],
    ) -> None:
        """
        Validate guardian data.

        Args:
            name: Guardian name
            phone: Phone number
            relation: Relationship to student
            email: Email address

        Raises:
            ValidationException: If validation fails
        """
        # Validate name
        if not name or len(name.strip()) < 2:
            raise ValidationException("Guardian name must be at least 2 characters")

        # Validate phone
        if not phone or len(phone.strip()) < 10:
            raise ValidationException("Valid phone number is required")

        # Validate relation
        valid_relations = [
            "father",
            "mother",
            "guardian",
            "sibling",
            "uncle",
            "aunt",
            "grandparent",
            "other",
        ]
        if relation.lower() not in valid_relations:
            raise ValidationException(
                f"Invalid relation. Must be one of: {', '.join(valid_relations)}"
            )

        # Validate email format if provided
        if email and "@" not in email:
            raise ValidationException("Invalid email format")

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def import_guardians(
        self,
        db: Session,
        student_id: UUID,
        guardians_data: List[dict],
    ) -> List[GuardianContact]:
        """
        Import multiple guardians for a student.

        Args:
            db: Database session
            student_id: UUID of student
            guardians_data: List of guardian data dictionaries

        Returns:
            List of created GuardianContact instances
        """
        if not guardians_data:
            return []

        created = []
        primary_set = False

        for data in guardians_data:
            # Ensure only one primary
            is_primary = data.get("is_primary", False) and not primary_set
            
            try:
                guardian = self.create_guardian(
                    db=db,
                    student_id=student_id,
                    name=data["name"],
                    phone=data["phone"],
                    relation=data.get("relation", "guardian"),
                    email=data.get("email"),
                    is_primary=is_primary,
                )
                created.append(guardian)
                
                if is_primary:
                    primary_set = True

            except (ValidationException, KeyError) as e:
                logger.error(f"Error importing guardian: {str(e)}")
                continue

        logger.info(
            f"Imported {len(created)} guardians for student: {student_id}"
        )

        return created