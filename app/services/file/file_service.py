# app/services/file/file_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Protocol, Tuple
from uuid import UUID

from app.schemas.file import (
    FileUploadInitRequest,
    FileUploadInitResponse,
    FileUploadCompleteRequest,
    FileInfo,
    FileListResponse,
    FileURL,
)
from app.services.common import errors


class FileStore(Protocol):
    """
    Abstract storage for file metadata and URL generation.

    A typical implementation will:
    - Persist file records in a DB table
    - Generate storage_keys
    - Optionally generate pre-signed upload URLs & signed download URLs
    """

    def init_upload(self, payload: dict) -> dict:
        """
        Initialize upload and persist a pending file record.

        Expected to return a dict compatible with FileUploadInitResponse
        (plus any internal fields).
        """
        ...

    def complete_upload(
        self,
        *,
        storage_key: str,
        uploaded_by_user_id: UUID,
        checksum: Optional[str],
    ) -> dict:
        """
        Mark the file as uploaded and finalize metadata.

        Expected to return a dict compatible with FileInfo.
        """
        ...

    def get_file(self, storage_key: str) -> Optional[dict]:
        """Fetch file metadata by storage_key."""
        ...

    def list_files(
        self,
        *,
        hostel_id: Optional[UUID],
        offset: int,
        limit: int,
    ) -> Tuple[List[dict], int]:
        """
        List files for a hostel (or platform-wide if hostel_id is None).

        Returns (items, total_items).
        Each item should be compatible with FileInfo.
        """
        ...

    def get_file_url(
        self,
        storage_key: str,
        *,
        expires_in_seconds: Optional[int] = None,
    ) -> dict:
        """
        Generate a URL (public or signed) for the given storage_key.

        Should return a dict compatible with FileURL.
        """
        ...


class FileService:
    """
    Generic file service for:

    - Initializing uploads (pre-signed URL style or API upload)
    - Completing uploads (marking as stored)
    - Retrieving file metadata
    - Listing files
    - Generating a single file URL (FileURL)
    """

    def __init__(self, store: FileStore) -> None:
        self._store = store

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Upload lifecycle
    # ------------------------------------------------------------------ #
    def init_upload(self, req: FileUploadInitRequest) -> FileUploadInitResponse:
        """
        Initialize a file upload.

        Delegates to FileStore.init_upload(), which should:
        - Generate a storage_key
        - Optionally generate upload_url and public_url
        - Persist a pending file record
        """
        payload = req.model_dump()
        record = self._store.init_upload(payload)
        return FileUploadInitResponse.model_validate(record)

    def complete_upload(self, req: FileUploadCompleteRequest) -> FileInfo:
        """
        Mark an upload as completed and return final FileInfo.
        """
        record = self._store.complete_upload(
            storage_key=req.storage_key,
            uploaded_by_user_id=req.uploaded_by_user_id,
            checksum=req.checksum,
        )
        return FileInfo.model_validate(record)

    # ------------------------------------------------------------------ #
    # Read operations
    # ------------------------------------------------------------------ #
    def get_file(self, storage_key: str) -> FileInfo:
        record = self._store.get_file(storage_key)
        if not record:
            raise errors.NotFoundError(f"File with storage_key {storage_key!r} not found")
        return FileInfo.model_validate(record)

    def list_files(
        self,
        *,
        hostel_id: Optional[UUID],
        page: int,
        page_size: int,
    ) -> FileListResponse:
        """
        List files (optionally scoped to a hostel), using simple page/page_size.
        """
        if page < 1 or page_size <= 0:
            raise errors.ValidationError("Invalid pagination parameters")

        offset = (page - 1) * page_size
        items_raw, total = self._store.list_files(
            hostel_id=hostel_id,
            offset=offset,
            limit=page_size,
        )
        items = [FileInfo.model_validate(r) for r in items_raw]
        return FileListResponse(
            items=items,
            total_items=total,
            page=page,
            page_size=page_size,
        )

    def get_file_url(
        self,
        storage_key: str,
        *,
        expires_in_seconds: Optional[int] = None,
    ) -> FileURL:
        """
        Return a FileURL for a given storage_key.

        For public files, the store may ignore expires_in_seconds
        and just return a stable public URL.
        """
        record = self._store.get_file_url(
            storage_key,
            expires_in_seconds=expires_in_seconds,
        )
        return FileURL.model_validate(record)