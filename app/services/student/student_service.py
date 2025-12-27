# app/services/student/student_service.py
"""
Student Service

Core CRUD and high-level operations for Student entity with optimized queries
and comprehensive data views.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.student import (
    StudentRepository,
    StudentAggregateRepository,
)
from app.schemas.student import (
    StudentCreate,
    StudentUpdate,
    StudentResponse,
    StudentDetail,
    StudentListItem,
    StudentFinancialInfo,
    StudentContactInfo,
    StudentDocumentInfo,
)
from app.core1.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)

logger = logging.getLogger(__name__)


class StudentService:
    """
    High-level service for Student entity management.

    Responsibilities:
    - Create and update student records
    - Retrieve single student details with related data
    - List students with filtering and pagination
    - Provide financial, contact, and document sub-views
    - Enforce business rules and validations

    Performance optimizations:
    - Uses aggregate repositories for complex queries
    - Implements eager loading for related entities
    - Caches frequently accessed data patterns
    """

    def __init__(
        self,
        student_repo: StudentRepository,
        aggregate_repo: StudentAggregateRepository,
    ) -> None:
        """
        Initialize service with required repositories.

        Args:
            student_repo: Repository for student CRUD operations
            aggregate_repo: Repository for complex aggregate queries
        """
        self.student_repo = student_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def create_student(
        self,
        db: Session,
        data: StudentCreate,
    ) -> StudentResponse:
        """
        Create a new student record.

        Args:
            db: Database session
            data: Student creation data

        Returns:
            StudentResponse: Created student details

        Raises:
            ValidationException: If validation fails
            BusinessLogicException: If business rules are violated
        """
        try:
            # Validate unique constraints before creation
            self._validate_unique_fields(db, data)

            obj = self.student_repo.create(
                db,
                data=data.model_dump(exclude_none=True),
            )
            
            logger.info(
                f"Student created successfully: {obj.id} "
                f"for hostel: {obj.hostel_id}"
            )
            
            return StudentResponse.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Database error creating student: {str(e)}")
            raise BusinessLogicException(
                f"Failed to create student: {str(e)}"
            ) from e

    def update_student(
        self,
        db: Session,
        student_id: UUID,
        data: StudentUpdate,
    ) -> StudentResponse:
        """
        Update an existing student record.

        Args:
            db: Database session
            student_id: UUID of student to update
            data: Update data

        Returns:
            StudentResponse: Updated student details

        Raises:
            NotFoundException: If student not found
            ValidationException: If validation fails
        """
        try:
            student = self._get_student_or_raise(db, student_id)

            # Validate updates don't violate constraints
            self._validate_update(db, student, data)

            updated = self.student_repo.update(
                db,
                student,
                data=data.model_dump(exclude_none=True, exclude_unset=True),
            )
            
            logger.info(f"Student updated successfully: {student_id}")
            
            return StudentResponse.model_validate(updated)

        except SQLAlchemyError as e:
            logger.error(f"Database error updating student {student_id}: {str(e)}")
            raise BusinessLogicException(
                f"Failed to update student: {str(e)}"
            ) from e

    def delete_student(
        self,
        db: Session,
        student_id: UUID,
        soft_delete: bool = True,
    ) -> None:
        """
        Delete a student record (soft or hard delete).

        Args:
            db: Database session
            student_id: UUID of student to delete
            soft_delete: If True, marks as deleted; if False, permanently removes

        Raises:
            NotFoundException: If student not found
            BusinessLogicException: If student has active dependencies
        """
        student = self._get_student_or_raise(db, student_id)

        # Check for active dependencies
        if self._has_active_dependencies(db, student_id):
            raise BusinessLogicException(
                "Cannot delete student with active bookings or payments"
            )

        if soft_delete:
            self.student_repo.soft_delete(db, student)
            logger.info(f"Student soft-deleted: {student_id}")
        else:
            self.student_repo.delete(db, student)
            logger.info(f"Student permanently deleted: {student_id}")

    # -------------------------------------------------------------------------
    # Retrieval Operations
    # -------------------------------------------------------------------------

    def get_student(
        self,
        db: Session,
        student_id: UUID,
        include_relations: bool = True,
    ) -> StudentDetail:
        """
        Retrieve comprehensive student details.

        Args:
            db: Database session
            student_id: UUID of student
            include_relations: Whether to include related entities

        Returns:
            StudentDetail: Complete student information

        Raises:
            NotFoundException: If student not found
        """
        try:
            if include_relations:
                obj = self.student_repo.get_full_student(db, student_id)
            else:
                obj = self.student_repo.get_by_id(db, student_id)

            if not obj:
                raise NotFoundException(f"Student not found: {student_id}")

            return StudentDetail.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving student {student_id}: {str(e)}")
            raise BusinessLogicException(
                f"Failed to retrieve student: {str(e)}"
            ) from e

    def get_student_by_user_id(
        self,
        db: Session,
        user_id: UUID,
    ) -> Optional[StudentDetail]:
        """
        Retrieve student by associated user ID.

        Args:
            db: Database session
            user_id: UUID of associated user

        Returns:
            StudentDetail or None if not found
        """
        obj = self.student_repo.get_by_user_id(db, user_id)
        if not obj:
            return None
        return StudentDetail.model_validate(obj)

    def list_students_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        skip: int = 0,
        limit: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[StudentListItem]:
        """
        List students for a hostel with pagination and filtering.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Optional filtering criteria

        Returns:
            List of StudentListItem objects
        """
        # Validate pagination parameters
        skip = max(0, skip)
        limit = min(max(1, limit), 100)  # Cap at 100

        try:
            objs = self.student_repo.get_by_hostel(
                db,
                hostel_id,
                skip=skip,
                limit=limit,
                filters=filters,
            )
            
            return [StudentListItem.model_validate(o) for o in objs]

        except SQLAlchemyError as e:
            logger.error(
                f"Database error listing students for hostel {hostel_id}: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to list students: {str(e)}"
            ) from e

    def search_students(
        self,
        db: Session,
        hostel_id: UUID,
        search_term: str,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StudentListItem]:
        """
        Search students by name, email, or registration number.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            search_term: Search string
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matching StudentListItem objects
        """
        if not search_term or len(search_term.strip()) < 2:
            return []

        try:
            objs = self.student_repo.search_students(
                db,
                hostel_id=hostel_id,
                search_term=search_term.strip(),
                skip=skip,
                limit=min(limit, 100),
            )
            
            return [StudentListItem.model_validate(o) for o in objs]

        except SQLAlchemyError as e:
            logger.error(f"Database error searching students: {str(e)}")
            raise BusinessLogicException(
                f"Failed to search students: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Sub-view Operations (Financial, Contact, Documents)
    # -------------------------------------------------------------------------

    def get_financial_info(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentFinancialInfo:
        """
        Retrieve student financial information.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            StudentFinancialInfo: Financial summary

        Raises:
            NotFoundException: If student not found
        """
        try:
            data = self.aggregate_repo.get_student_financial_info(db, student_id)
            
            if not data:
                raise NotFoundException(
                    f"Financial info not available for student: {student_id}"
                )
            
            return StudentFinancialInfo.model_validate(data)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving financial info for {student_id}: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to retrieve financial info: {str(e)}"
            ) from e

    def get_contact_info(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentContactInfo:
        """
        Retrieve student contact information including guardians.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            StudentContactInfo: Contact details

        Raises:
            NotFoundException: If student not found
        """
        try:
            data = self.aggregate_repo.get_student_contact_info(db, student_id)
            
            if not data:
                raise NotFoundException(
                    f"Contact info not available for student: {student_id}"
                )
            
            return StudentContactInfo.model_validate(data)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving contact info for {student_id}: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to retrieve contact info: {str(e)}"
            ) from e

    def get_document_info(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentDocumentInfo:
        """
        Retrieve student document summary.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            StudentDocumentInfo: Document summary

        Raises:
            NotFoundException: If student not found
        """
        try:
            data = self.aggregate_repo.get_student_document_info(db, student_id)
            
            if not data:
                raise NotFoundException(
                    f"Document info not available for student: {student_id}"
                )
            
            return StudentDocumentInfo.model_validate(data)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving document info for {student_id}: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to retrieve document info: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def bulk_update_status(
        self,
        db: Session,
        student_ids: List[UUID],
        new_status: str,
        updated_by: UUID,
    ) -> int:
        """
        Update status for multiple students.

        Args:
            db: Database session
            student_ids: List of student UUIDs
            new_status: New status to set
            updated_by: UUID of user performing update

        Returns:
            Number of students updated
        """
        if not student_ids:
            return 0

        try:
            count = self.student_repo.bulk_update_status(
                db,
                student_ids=student_ids,
                new_status=new_status,
                updated_by=updated_by,
            )
            
            logger.info(
                f"Bulk status update: {count} students updated to {new_status}"
            )
            
            return count

        except SQLAlchemyError as e:
            logger.error(f"Database error in bulk update: {str(e)}")
            raise BusinessLogicException(
                f"Failed to bulk update students: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Statistics and Aggregations
    # -------------------------------------------------------------------------

    def get_hostel_statistics(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a hostel's students.

        Args:
            db: Database session
            hostel_id: UUID of hostel

        Returns:
            Dictionary containing various statistics
        """
        try:
            stats = self.aggregate_repo.get_hostel_statistics(db, hostel_id)
            return stats

        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving statistics for hostel {hostel_id}: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to retrieve statistics: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _get_student_or_raise(
        self,
        db: Session,
        student_id: UUID,
    ) -> Any:
        """
        Get student or raise NotFoundException.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            Student ORM object

        Raises:
            NotFoundException: If student not found
        """
        student = self.student_repo.get_by_id(db, student_id)
        if not student:
            raise NotFoundException(f"Student not found: {student_id}")
        return student

    def _validate_unique_fields(
        self,
        db: Session,
        data: StudentCreate,
    ) -> None:
        """
        Validate unique field constraints.

        Args:
            db: Database session
            data: Student creation data

        Raises:
            ValidationException: If unique constraints violated
        """
        # Check registration number uniqueness
        if data.registration_number:
            existing = self.student_repo.get_by_registration_number(
                db,
                data.registration_number,
            )
            if existing:
                raise ValidationException(
                    f"Registration number already exists: {data.registration_number}"
                )

        # Check email uniqueness if provided
        if data.email:
            existing = self.student_repo.get_by_email(db, data.email)
            if existing:
                raise ValidationException(
                    f"Email already registered: {data.email}"
                )

    def _validate_update(
        self,
        db: Session,
        student: Any,
        data: StudentUpdate,
    ) -> None:
        """
        Validate update operation.

        Args:
            db: Database session
            student: Existing student object
            data: Update data

        Raises:
            ValidationException: If validation fails
        """
        # Check registration number uniqueness if being updated
        if (
            data.registration_number
            and data.registration_number != student.registration_number
        ):
            existing = self.student_repo.get_by_registration_number(
                db,
                data.registration_number,
            )
            if existing and existing.id != student.id:
                raise ValidationException(
                    f"Registration number already exists: {data.registration_number}"
                )

    def _has_active_dependencies(
        self,
        db: Session,
        student_id: UUID,
    ) -> bool:
        """
        Check if student has active dependencies preventing deletion.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            True if active dependencies exist
        """
        return self.student_repo.has_active_dependencies(db, student_id)