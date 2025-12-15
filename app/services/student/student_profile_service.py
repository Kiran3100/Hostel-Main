# app/services/student/student_profile_service.py
from __future__ import annotations

from datetime import datetime
from typing import Callable, List, Optional, Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.repositories.core import StudentRepository, UserRepository
from app.schemas.student.student_profile import (
    StudentProfileCreate,
    StudentProfileUpdate,
    StudentDocuments,
    DocumentInfo,
    DocumentUploadRequest,
    DocumentVerificationRequest,
    StudentPreferences,
)
from app.schemas.student.student_response import StudentDetail
from app.services.common import UnitOfWork, errors
from .student_service import StudentService


class StudentDocumentStore(Protocol):
    """
    Storage abstraction for student documents.

    Expected record fields (example):
        {
            "id": UUID,
            "student_id": UUID,
            "document_type": str,
            "document_name": str,
            "document_url": str,
            "uploaded_at": datetime,
            "verified": bool,
            "verified_by": UUID | None,
            "verified_at": datetime | None,
            "notes": str | None,
        }
    """

    def list_documents(self, student_id: UUID) -> List[dict]: ...
    def save_document(self, record: dict) -> dict: ...
    def get_document(self, document_id: UUID) -> Optional[dict]: ...
    def update_document(self, document_id: UUID, data: dict) -> dict: ...


class StudentProfileService:
    """
    Student profile & documents:

    - Get/update student "profile" fields (guardian, institution, employment, preferences).
    - Manage uploaded documents via a DocumentStore.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        document_store: StudentDocumentStore,
    ) -> None:
        self._session_factory = session_factory
        self._documents = document_store
        self._student_service = StudentService(session_factory)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Profile (uses Student + User)
    # ------------------------------------------------------------------ #
    def update_profile(
        self,
        student_id: UUID,
        data: StudentProfileUpdate,
    ) -> StudentDetail:
        """
        Merge StudentProfileUpdate fields into Student.
        """
        with UnitOfWork(self._session_factory) as uow:
            student_repo = self._get_student_repo(uow)

            s = student_repo.get(student_id)
            if s is None:
                raise errors.NotFoundError(f"Student {student_id} not found")

            mapping = data.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(s, field) and field != "id":
                    setattr(s, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return self._student_service.get_student(student_id)

    # ------------------------------------------------------------------ #
    # Documents
    # ------------------------------------------------------------------ #
    def list_documents(self, student_id: UUID) -> StudentDocuments:
        records = self._documents.list_documents(student_id)
        docs = [DocumentInfo.model_validate(r) for r in records]
        return StudentDocuments(student_id=student_id, documents=docs)

    def upload_document(self, data: DocumentUploadRequest) -> DocumentInfo:
        now = self._now()
        record = {
            "id": uuid4(),
            "student_id": data.student_id,
            "document_type": data.document_type,
            "document_name": data.document_name,
            "document_url": str(data.document_url),
            "uploaded_at": now,
            "verified": False,
            "verified_by": None,
            "verified_at": None,
            "notes": None,
        }
        saved = self._documents.save_document(record)
        return DocumentInfo.model_validate(saved)

    def verify_document(self, data: DocumentVerificationRequest, *, verifier_id: UUID) -> DocumentInfo:
        record = self._documents.get_document(data.document_id)
        if not record:
            raise errors.NotFoundError(f"Document {data.document_id} not found")

        record["verified"] = data.verified
        record["verified_by"] = verifier_id
        record["verified_at"] = self._now()
        record["notes"] = data.notes

        updated = self._documents.update_document(data.document_id, record)
        return DocumentInfo.model_validate(updated)

    # ------------------------------------------------------------------ #
    # Preferences
    # ------------------------------------------------------------------ #
    def update_preferences(self, student_id: UUID, prefs: StudentPreferences) -> StudentDetail:
        """
        Update student-level preferences that live on Student.
        """
        with UnitOfWork(self._session_factory) as uow:
            student_repo = self._get_student_repo(uow)

            s = student_repo.get(student_id)
            if s is None:
                raise errors.NotFoundError(f"Student {student_id} not found")

            mapping = prefs.model_dump(exclude_unset=True)
            for field, value in mapping.items():
                if hasattr(s, field) and field != "id":
                    setattr(s, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

        return self._student_service.get_student(student_id)