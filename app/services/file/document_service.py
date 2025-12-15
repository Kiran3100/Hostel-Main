# app/services/file/document_service.py
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional, Protocol
from uuid import UUID

from app.schemas.file import (
    DocumentUploadInitRequest,
    DocumentUploadInitResponse,
    DocumentValidationResult,
)
from app.schemas.file.document_upload import DocumentInfo, DocumentList
from app.schemas.file.file_upload import FileUploadInitRequest
from app.services.common import errors
from app.services.file.file_service import FileService


class DocumentStore(Protocol):
    """
    Abstract storage for document metadata (beyond generic files).

    A typical record stored by this protocol might include:
    - id (UUID)
    - storage_key
    - document_type
    - description
    - uploaded_by_user_id
    - student_id / hostel_id
    - uploaded_at (date)
    - verified, verified_by, verified_at, verification_notes
    """

    def create_document(self, data: dict) -> dict: ...
    def get_document(self, doc_id: UUID) -> Optional[dict]: ...
    def list_documents_for_owner(self, owner_type: str, owner_id: UUID) -> List[dict]: ...
    def update_document(self, doc_id: UUID, data: dict) -> dict: ...


class DocumentService:
    """
    Document-specific file handling:

    - Initialize document uploads (PDF or image-as-document)
    - Validate basic properties of uploaded document
    - List documents for a student/hostel/system
    - Read single DocumentInfo
    """

    def __init__(self, file_service: FileService, store: DocumentStore) -> None:
        self._files = file_service
        self._store = store

    def _today(self) -> date:
        return datetime.now(timezone.utc).date()

    # ------------------------------------------------------------------ #
    # Upload init
    # ------------------------------------------------------------------ #
    def init_document_upload(
        self,
        req: DocumentUploadInitRequest,
        *,
        folder: Optional[str] = None,
        is_public: bool = False,
    ) -> DocumentUploadInitResponse:
        """
        Initialize a document upload and create a corresponding document record.

        The actual upload is still handled via FileService and object storage.
        """
        effective_folder = folder or "documents"
        if req.hostel_id:
            effective_folder = f"hostels/{req.hostel_id}/documents"
        elif req.student_id:
            effective_folder = f"students/{req.student_id}/documents"

        file_req = FileUploadInitRequest(
            filename=req.filename,
            content_type=req.content_type,
            size_bytes=req.size_bytes,
            folder=effective_folder,
            uploaded_by_user_id=req.uploaded_by_user_id,
            hostel_id=req.hostel_id,
            category="document",
            tags=[req.document_type],
            is_public=is_public,
        )
        file_resp = self._files.init_upload(file_req)

        # Pre-create document metadata in store
        doc_record = {
            "id": None,  # store may assign UUID
            "storage_key": file_resp.storage_key,
            "document_type": req.document_type,
            "description": req.description,
            "uploaded_by_user_id": req.uploaded_by_user_id,
            "student_id": str(req.student_id) if req.student_id else None,
            "hostel_id": str(req.hostel_id) if req.hostel_id else None,
            "uploaded_at": self._today(),
            "verified": False,
            "verified_by": None,
            "verified_at": None,
            "verification_notes": None,
        }
        self._store.create_document(doc_record)

        # Response is just the generic FileUploadInitResponse shape
        return DocumentUploadInitResponse.model_validate(file_resp.model_dump())

    # ------------------------------------------------------------------ #
    # Validation (simple stub)
    # ------------------------------------------------------------------ #
    def validate_document(
        self,
        storage_key: str,
    ) -> DocumentValidationResult:
        """
        Simple backend-side validation of a document:

        - Confirms the file exists
        - Optionally could check size/mime from FileInfo

        For now, we treat existence as "valid".
        """
        file_info = self._files.get_file(storage_key)

        # Add any additional validation logic here if needed
        is_valid = True
        reason = None

        return DocumentValidationResult(
            storage_key=storage_key,
            is_valid=is_valid,
            reason=reason,
            extracted_metadata=None,
        )

    # ------------------------------------------------------------------ #
    # Read operations
    # ------------------------------------------------------------------ #
    def get_document(self, doc_id: UUID) -> DocumentInfo:
        rec = self._store.get_document(doc_id)
        if not rec:
            raise errors.NotFoundError(f"Document {doc_id} not found")

        storage_key = rec["storage_key"]
        file_info = self._files.get_file(storage_key)

        # Choose URL (prefer public_url, else signed_url)
        url = file_info.public_url or file_info.signed_url
        if url is None:
            # As a fallback, generate a short-lived signed URL
            url_obj = self._files.get_file_url(storage_key, expires_in_seconds=3600)
            url = url_obj.url

        return DocumentInfo(
            id=doc_id,
            storage_key=storage_key,
            url=url,
            document_type=rec.get("document_type", "other"),
            description=rec.get("description"),
            uploaded_by_user_id=rec["uploaded_by_user_id"],
            uploaded_by_name=rec.get("uploaded_by_name"),
            uploaded_at=rec.get("uploaded_at", self._today()),
            verified=rec.get("verified", False),
            verified_by=rec.get("verified_by"),
            verified_at=rec.get("verified_at"),
            verification_notes=rec.get("verification_notes"),
        )

    def list_documents(
        self,
        *,
        owner_type: str,
        owner_id: UUID,
    ) -> DocumentList:
        """
        List documents for a given owner (student|hostel|system).
        """
        records = self._store.list_documents_for_owner(owner_type, owner_id)
        docs: List[DocumentInfo] = []

        for r in records:
            doc_id = r.get("id")
            if not doc_id:
                continue
            docs.append(self.get_document(doc_id))

        return DocumentList(
            owner_type=owner_type,
            owner_id=owner_id,
            documents=docs,
            total_documents=len(docs),
        )