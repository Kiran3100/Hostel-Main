# app/services/student/student_service.py
"""
Student Service

Core CRUD and high-level operations for Student entity.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

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
from app.core.exceptions import ValidationException


class StudentService:
    """
    High-level service for Student entity.

    Responsibilities:
    - Create/update students
    - Get single student detail
    - List students by hostel / status
    - Fetch financial/contact/document sub-views
    """

    def __init__(
        self,
        student_repo: StudentRepository,
        aggregate_repo: StudentAggregateRepository,
    ) -> None:
        self.student_repo = student_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_student(
        self,
        db: Session,
        data: StudentCreate,
    ) -> StudentResponse:
        obj = self.student_repo.create(
            db,
            data=data.model_dump(exclude_none=True),
        )
        return StudentResponse.model_validate(obj)

    def update_student(
        self,
        db: Session,
        student_id: UUID,
        data: StudentUpdate,
    ) -> StudentResponse:
        student = self.student_repo.get_by_id(db, student_id)
        if not student:
            raise ValidationException("Student not found")

        updated = self.student_repo.update(
            db,
            student,
            data=data.model_dump(exclude_none=True),
        )
        return StudentResponse.model_validate(updated)

    # -------------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------------

    def get_student(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentDetail:
        obj = self.student_repo.get_full_student(db, student_id)
        if not obj:
            raise ValidationException("Student not found")
        return StudentDetail.model_validate(obj)

    def list_students_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StudentListItem]:
        objs = self.student_repo.get_by_hostel(db, hostel_id, skip, limit)
        return [StudentListItem.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Sub-views (financial, contact, documents)
    # -------------------------------------------------------------------------

    def get_financial_info(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentFinancialInfo:
        data = self.aggregate_repo.get_student_financial_info(db, student_id)
        if not data:
            raise ValidationException("Financial info not available")
        return StudentFinancialInfo.model_validate(data)

    def get_contact_info(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentContactInfo:
        data = self.aggregate_repo.get_student_contact_info(db, student_id)
        if not data:
            raise ValidationException("Contact info not available")
        return StudentContactInfo.model_validate(data)

    def get_document_info(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentDocumentInfo:
        data = self.aggregate_repo.get_student_document_info(db, student_id)
        if not data:
            raise ValidationException("Document info not available")
        return StudentDocumentInfo.model_validate(data)