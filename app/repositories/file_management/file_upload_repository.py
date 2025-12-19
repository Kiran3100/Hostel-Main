"""
File Upload Repository

Core file upload operations with session management, validation,
multipart uploads, and quota enforcement.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import and_, or_, func, case, desc, asc
from sqlalchemy.orm import Session, joinedload, selectinload

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationManager, PaginatedResult
from app.models.file_management.file_upload import (
    FileUpload,
    UploadSession,
    FileValidation,
    UploadProgress,
    FileQuota,
    MultipartUpload,
    MultipartUploadPart,
)
from app.models.user.user import User
from app.models.hostel.hostel import Hostel


class FileUploadRepository(BaseRepository[FileUpload]):
    """
    Repository for file upload operations with advanced querying,
    validation, and quota management.
    """

    def __init__(self, db_session: Session):
        super().__init__(FileUpload, db_session)

    # ============================================================================
    # CORE FILE OPERATIONS
    # ============================================================================

    async def create_file_upload(
        self,
        file_data: Dict[str, Any],
        uploaded_by_user_id: str,
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> FileUpload:
        """
        Create new file upload with validation and quota checking.

        Args:
            file_data: File metadata and storage information
            uploaded_by_user_id: User ID who uploaded the file
            audit_context: Audit trail context

        Returns:
            Created FileUpload instance

        Raises:
            QuotaExceededException: If quota is exceeded
            ValidationException: If file data is invalid
        """
        # Check quota before upload
        await self._check_quota(
            owner_type=file_data.get("owner_type", "user"),
            owner_id=uploaded_by_user_id,
            file_size=file_data.get("size_bytes", 0),
        )

        # Create file upload
        file_upload = FileUpload(
            file_id=file_data["file_id"],
            storage_key=file_data["storage_key"],
            filename=file_data["filename"],
            content_type=file_data["content_type"],
            size_bytes=file_data["size_bytes"],
            extension=file_data.get("extension"),
            checksum=file_data.get("checksum"),
            etag=file_data.get("etag"),
            uploaded_by_user_id=uploaded_by_user_id,
            hostel_id=file_data.get("hostel_id"),
            student_id=file_data.get("student_id"),
            folder=file_data.get("folder"),
            category=file_data.get("category"),
            tags=file_data.get("tags", []),
            is_public=file_data.get("is_public", False),
            public_url=file_data.get("public_url"),
            url=file_data["url"],
            metadata=file_data.get("metadata", {}),
            processing_status="pending",
            virus_scan_status="pending",
        )

        created_file = await self.create(file_upload, audit_context)

        # Update quota usage
        await self._update_quota_usage(
            owner_type=file_data.get("owner_type", "user"),
            owner_id=uploaded_by_user_id,
            size_delta=file_data["size_bytes"],
            file_count_delta=1,
        )

        return created_file

    async def find_by_file_id(
        self,
        file_id: str,
        include_deleted: bool = False,
        load_relationships: bool = False,
    ) -> Optional[FileUpload]:
        """
        Find file by unique file ID.

        Args:
            file_id: Unique file identifier
            include_deleted: Whether to include soft-deleted files
            load_relationships: Whether to eager load relationships

        Returns:
            FileUpload if found, None otherwise
        """
        query = self.db_session.query(FileUpload).filter(
            FileUpload.file_id == file_id
        )

        if not include_deleted:
            query = query.filter(FileUpload.deleted_at.is_(None))

        if load_relationships:
            query = query.options(
                joinedload(FileUpload.uploaded_by),
                joinedload(FileUpload.hostel),
                joinedload(FileUpload.student),
                selectinload(FileUpload.validations),
            )

        return query.first()

    async def find_by_storage_key(
        self, storage_key: str
    ) -> Optional[FileUpload]:
        """Find file by storage key."""
        return self.db_session.query(FileUpload).filter(
            FileUpload.storage_key == storage_key,
            FileUpload.deleted_at.is_(None),
        ).first()

    async def find_by_checksum(
        self,
        checksum: str,
        uploaded_by_user_id: Optional[str] = None,
    ) -> List[FileUpload]:
        """
        Find files by checksum for duplicate detection.

        Args:
            checksum: File checksum
            uploaded_by_user_id: Optional user ID filter

        Returns:
            List of files with matching checksum
        """
        query = self.db_session.query(FileUpload).filter(
            FileUpload.checksum == checksum,
            FileUpload.deleted_at.is_(None),
        )

        if uploaded_by_user_id:
            query = query.filter(
                FileUpload.uploaded_by_user_id == uploaded_by_user_id
            )

        return query.all()

    async def search_files(
        self,
        criteria: Dict[str, Any],
        pagination: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedResult[FileUpload]:
        """
        Search files with flexible criteria and pagination.

        Args:
            criteria: Search criteria dictionary
            pagination: Pagination parameters
            sort_by: Field to sort by
            sort_order: Sort order ('asc' or 'desc')

        Returns:
            Paginated search results

        Criteria Options:
            - uploaded_by_user_id: Filter by uploader
            - hostel_id: Filter by hostel
            - student_id: Filter by student
            - category: Filter by category
            - content_type: Filter by MIME type
            - folder: Filter by folder path
            - tags: Filter by tags (list)
            - is_public: Filter by public status
            - processing_status: Filter by processing status
            - virus_scan_status: Filter by scan status
            - min_size_bytes: Minimum file size
            - max_size_bytes: Maximum file size
            - filename_search: Search in filename
            - created_after: Files created after date
            - created_before: Files created before date
        """
        query = QueryBuilder(FileUpload, self.db_session)

        # Apply filters
        if "uploaded_by_user_id" in criteria:
            query = query.where(
                FileUpload.uploaded_by_user_id == criteria["uploaded_by_user_id"]
            )

        if "hostel_id" in criteria:
            query = query.where(FileUpload.hostel_id == criteria["hostel_id"])

        if "student_id" in criteria:
            query = query.where(FileUpload.student_id == criteria["student_id"])

        if "category" in criteria:
            query = query.where(FileUpload.category == criteria["category"])

        if "content_type" in criteria:
            query = query.where(
                FileUpload.content_type == criteria["content_type"]
            )

        if "folder" in criteria:
            query = query.where(FileUpload.folder.like(f"{criteria['folder']}%"))

        if "tags" in criteria and criteria["tags"]:
            # JSON array contains any of the specified tags
            for tag in criteria["tags"]:
                query = query.where(
                    FileUpload.tags.contains([tag])
                )

        if "is_public" in criteria:
            query = query.where(FileUpload.is_public == criteria["is_public"])

        if "processing_status" in criteria:
            query = query.where(
                FileUpload.processing_status == criteria["processing_status"]
            )

        if "virus_scan_status" in criteria:
            query = query.where(
                FileUpload.virus_scan_status == criteria["virus_scan_status"]
            )

        if "min_size_bytes" in criteria:
            query = query.where(
                FileUpload.size_bytes >= criteria["min_size_bytes"]
            )

        if "max_size_bytes" in criteria:
            query = query.where(
                FileUpload.size_bytes <= criteria["max_size_bytes"]
            )

        if "filename_search" in criteria:
            search_term = f"%{criteria['filename_search']}%"
            query = query.where(FileUpload.filename.ilike(search_term))

        if "created_after" in criteria:
            query = query.where(
                FileUpload.created_at >= criteria["created_after"]
            )

        if "created_before" in criteria:
            query = query.where(
                FileUpload.created_at <= criteria["created_before"]
            )

        # Exclude soft-deleted
        query = query.where(FileUpload.deleted_at.is_(None))

        # Apply sorting
        sort_field = getattr(FileUpload, sort_by, FileUpload.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_field))
        else:
            query = query.order_by(asc(sort_field))

        # Apply pagination
        return await PaginationManager.paginate(
            query.build(),
            pagination or {"page": 1, "page_size": 50}
        )

    async def update_processing_status(
        self,
        file_id: str,
        status: str,
        error_message: Optional[str] = None,
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> FileUpload:
        """
        Update file processing status.

        Args:
            file_id: File identifier
            status: New processing status
            error_message: Error message if failed
            audit_context: Audit context

        Returns:
            Updated FileUpload
        """
        file_upload = await self.find_by_file_id(file_id)
        if not file_upload:
            raise ValueError(f"File not found: {file_id}")

        update_data = {
            "processing_status": status,
            "is_processed": status == "completed",
        }

        if status == "processing" and not file_upload.processing_started_at:
            update_data["processing_started_at"] = datetime.utcnow()
        elif status in ["completed", "failed"]:
            update_data["processing_completed_at"] = datetime.utcnow()

        if error_message:
            update_data["processing_error"] = error_message

        return await self.update(
            file_upload.id,
            update_data,
            audit_context=audit_context
        )

    async def update_virus_scan_status(
        self,
        file_id: str,
        status: str,
        scan_result: Optional[Dict[str, Any]] = None,
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> FileUpload:
        """
        Update virus scan status and results.

        Args:
            file_id: File identifier
            status: Scan status
            scan_result: Detailed scan results
            audit_context: Audit context

        Returns:
            Updated FileUpload
        """
        file_upload = await self.find_by_file_id(file_id)
        if not file_upload:
            raise ValueError(f"File not found: {file_id}")

        update_data = {
            "virus_scan_status": status,
            "virus_scan_timestamp": datetime.utcnow(),
        }

        if scan_result:
            update_data["virus_scan_result"] = scan_result

        return await self.update(
            file_upload.id,
            update_data,
            audit_context=audit_context
        )

    async def track_file_access(
        self,
        file_id: str,
        accessed_by_user_id: str,
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> FileUpload:
        """
        Track file access and update access metrics.

        Args:
            file_id: File identifier
            accessed_by_user_id: User accessing the file
            audit_context: Audit context

        Returns:
            Updated FileUpload
        """
        file_upload = await self.find_by_file_id(file_id)
        if not file_upload:
            raise ValueError(f"File not found: {file_id}")

        update_data = {
            "access_count": file_upload.access_count + 1,
            "last_accessed_at": datetime.utcnow(),
            "last_accessed_by_user_id": accessed_by_user_id,
        }

        return await self.update(
            file_upload.id,
            update_data,
            audit_context=audit_context
        )

    # ============================================================================
    # UPLOAD SESSION OPERATIONS
    # ============================================================================

    async def create_upload_session(
        self,
        session_data: Dict[str, Any],
        uploaded_by_user_id: str,
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> UploadSession:
        """
        Create upload session for direct or multipart upload.

        Args:
            session_data: Session configuration
            uploaded_by_user_id: User initiating upload
            audit_context: Audit context

        Returns:
            Created UploadSession
        """
        # Check quota before creating session
        await self._check_quota(
            owner_type=session_data.get("owner_type", "user"),
            owner_id=uploaded_by_user_id,
            file_size=session_data["expected_size_bytes"],
        )

        # Reserve quota
        await self._update_quota_usage(
            owner_type=session_data.get("owner_type", "user"),
            owner_id=uploaded_by_user_id,
            reserved_delta=session_data["expected_size_bytes"],
        )

        session = UploadSession(
            upload_id=session_data["upload_id"],
            session_type=session_data["session_type"],
            storage_key=session_data["storage_key"],
            filename=session_data["filename"],
            content_type=session_data["content_type"],
            expected_size_bytes=session_data["expected_size_bytes"],
            uploaded_by_user_id=uploaded_by_user_id,
            status="initialized",
            upload_url=session_data.get("upload_url"),
            upload_method=session_data.get("upload_method", "PUT"),
            upload_headers=session_data.get("upload_headers"),
            expires_at=session_data["expires_at"],
            session_metadata=session_data.get("metadata", {}),
        )

        return self.db_session.add(session)
        self.db_session.commit()
        return session

    async def find_upload_session(
        self,
        upload_id: str,
        include_expired: bool = False,
    ) -> Optional[UploadSession]:
        """
        Find upload session by ID.

        Args:
            upload_id: Upload session identifier
            include_expired: Whether to include expired sessions

        Returns:
            UploadSession if found
        """
        query = self.db_session.query(UploadSession).filter(
            UploadSession.upload_id == upload_id
        )

        if not include_expired:
            query = query.filter(UploadSession.expires_at > datetime.utcnow())

        return query.first()

    async def update_upload_session_status(
        self,
        upload_id: str,
        status: str,
        error_message: Optional[str] = None,
        actual_size_bytes: Optional[int] = None,
        checksum: Optional[str] = None,
        etag: Optional[str] = None,
    ) -> UploadSession:
        """
        Update upload session status.

        Args:
            upload_id: Session identifier
            status: New status
            error_message: Error if failed
            actual_size_bytes: Actual uploaded size
            checksum: File checksum
            etag: Storage provider ETag

        Returns:
            Updated UploadSession
        """
        session = await self.find_upload_session(upload_id, include_expired=True)
        if not session:
            raise ValueError(f"Upload session not found: {upload_id}")

        session.status = status

        if status == "uploading" and not session.upload_started_at:
            session.upload_started_at = datetime.utcnow()
        elif status in ["completed", "failed", "expired"]:
            session.upload_completed_at = datetime.utcnow()

        if error_message:
            session.error_message = error_message
            session.retry_count += 1

        if actual_size_bytes is not None:
            session.actual_size_bytes = actual_size_bytes

        if checksum:
            session.checksum = checksum

        if etag:
            session.etag = etag

        self.db_session.commit()
        return session

    async def cleanup_expired_sessions(
        self, batch_size: int = 100
    ) -> int:
        """
        Clean up expired upload sessions and release reserved quota.

        Args:
            batch_size: Number of sessions to clean per batch

        Returns:
            Number of sessions cleaned up
        """
        expired_sessions = (
            self.db_session.query(UploadSession)
            .filter(
                UploadSession.expires_at < datetime.utcnow(),
                UploadSession.status.in_(["initialized", "uploading"]),
            )
            .limit(batch_size)
            .all()
        )

        cleaned_count = 0
        for session in expired_sessions:
            # Release reserved quota
            await self._update_quota_usage(
                owner_type="user",  # Should be stored in session metadata
                owner_id=session.uploaded_by_user_id,
                reserved_delta=-session.expected_size_bytes,
            )

            session.status = "expired"
            cleaned_count += 1

        self.db_session.commit()
        return cleaned_count

    # ============================================================================
    # FILE VALIDATION OPERATIONS
    # ============================================================================

    async def create_validation_result(
        self,
        file_id: str,
        validation_data: Dict[str, Any],
    ) -> FileValidation:
        """
        Store file validation results.

        Args:
            file_id: File identifier
            validation_data: Validation results

        Returns:
            Created FileValidation record
        """
        file_upload = await self.find_by_file_id(file_id)
        if not file_upload:
            raise ValueError(f"File not found: {file_id}")

        validation = FileValidation(
            file_id=file_upload.id,
            validation_type=validation_data["validation_type"],
            is_valid=validation_data["is_valid"],
            validation_score=validation_data.get("validation_score"),
            checks_passed=validation_data.get("checks_passed", []),
            checks_failed=validation_data.get("checks_failed", []),
            warnings=validation_data.get("warnings", []),
            reason=validation_data.get("reason"),
            error_details=validation_data.get("error_details"),
            extracted_metadata=validation_data.get("extracted_metadata"),
            detected_type=validation_data.get("detected_type"),
            confidence_level=validation_data.get("confidence_level"),
            validated_at=datetime.utcnow(),
            validation_duration_ms=validation_data.get("validation_duration_ms"),
            validator_name=validation_data.get("validator_name"),
            validator_version=validation_data.get("validator_version"),
        )

        self.db_session.add(validation)
        self.db_session.commit()
        return validation

    async def get_validation_results(
        self,
        file_id: str,
        validation_type: Optional[str] = None,
    ) -> List[FileValidation]:
        """
        Get validation results for a file.

        Args:
            file_id: File identifier
            validation_type: Optional filter by validation type

        Returns:
            List of validation results
        """
        file_upload = await self.find_by_file_id(file_id)
        if not file_upload:
            return []

        query = self.db_session.query(FileValidation).filter(
            FileValidation.file_id == file_upload.id
        )

        if validation_type:
            query = query.filter(FileValidation.validation_type == validation_type)

        return query.order_by(desc(FileValidation.validated_at)).all()

    # ============================================================================
    # MULTIPART UPLOAD OPERATIONS
    # ============================================================================

    async def create_multipart_upload(
        self,
        session_id: str,
        multipart_data: Dict[str, Any],
    ) -> MultipartUpload:
        """
        Create multipart upload tracking.

        Args:
            session_id: Upload session ID
            multipart_data: Multipart upload configuration

        Returns:
            Created MultipartUpload
        """
        multipart = MultipartUpload(
            session_id=session_id,
            multipart_upload_id=multipart_data["multipart_upload_id"],
            total_size_bytes=multipart_data["total_size_bytes"],
            part_size_bytes=multipart_data["part_size_bytes"],
            total_parts=multipart_data["total_parts"],
            status="in_progress",
        )

        self.db_session.add(multipart)
        self.db_session.commit()
        return multipart

    async def create_multipart_part(
        self,
        multipart_upload_id: str,
        part_data: Dict[str, Any],
    ) -> MultipartUploadPart:
        """
        Create multipart upload part.

        Args:
            multipart_upload_id: Multipart upload ID
            part_data: Part configuration

        Returns:
            Created MultipartUploadPart
        """
        multipart = (
            self.db_session.query(MultipartUpload)
            .filter(MultipartUpload.id == multipart_upload_id)
            .first()
        )

        if not multipart:
            raise ValueError(f"Multipart upload not found: {multipart_upload_id}")

        part = MultipartUploadPart(
            multipart_upload_id=multipart_upload_id,
            part_number=part_data["part_number"],
            size_bytes=part_data["size_bytes"],
            upload_url=part_data["upload_url"],
            url_expires_at=part_data["url_expires_at"],
            status="pending",
        )

        self.db_session.add(part)
        self.db_session.commit()
        return part

    async def update_multipart_part_status(
        self,
        multipart_upload_id: str,
        part_number: int,
        status: str,
        etag: Optional[str] = None,
        checksum: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> MultipartUploadPart:
        """
        Update multipart part upload status.

        Args:
            multipart_upload_id: Multipart upload ID
            part_number: Part number
            status: New status
            etag: Part ETag from storage
            checksum: Part checksum
            error_message: Error if failed

        Returns:
            Updated MultipartUploadPart
        """
        part = (
            self.db_session.query(MultipartUploadPart)
            .filter(
                MultipartUploadPart.multipart_upload_id == multipart_upload_id,
                MultipartUploadPart.part_number == part_number,
            )
            .first()
        )

        if not part:
            raise ValueError(
                f"Part {part_number} not found for multipart upload {multipart_upload_id}"
            )

        part.status = status

        if status == "completed":
            part.uploaded_at = datetime.utcnow()
            if etag:
                part.etag = etag
            if checksum:
                part.checksum = checksum

            # Update multipart upload progress
            multipart = part.multipart_upload
            multipart.uploaded_parts += 1
            multipart.uploaded_bytes += part.size_bytes

            if multipart.uploaded_parts >= multipart.total_parts:
                multipart.status = "assembling"
                multipart.assembly_started_at = datetime.utcnow()

        elif status == "failed":
            part.error_message = error_message
            part.retry_count += 1

        self.db_session.commit()
        return part

    async def complete_multipart_upload(
        self,
        multipart_upload_id: str,
        file_id: Optional[str] = None,
    ) -> MultipartUpload:
        """
        Mark multipart upload as completed.

        Args:
            multipart_upload_id: Multipart upload ID
            file_id: Final file ID after assembly

        Returns:
            Updated MultipartUpload
        """
        multipart = (
            self.db_session.query(MultipartUpload)
            .filter(MultipartUpload.id == multipart_upload_id)
            .first()
        )

        if not multipart:
            raise ValueError(f"Multipart upload not found: {multipart_upload_id}")

        multipart.status = "completed"
        multipart.assembly_completed_at = datetime.utcnow()

        # Update session
        session = multipart.session
        session.status = "completed"
        session.upload_completed_at = datetime.utcnow()
        session.actual_size_bytes = multipart.total_size_bytes

        if file_id:
            session.file_id = file_id

        # Release reserved quota and add actual usage
        await self._update_quota_usage(
            owner_type="user",
            owner_id=session.uploaded_by_user_id,
            reserved_delta=-session.expected_size_bytes,
            size_delta=multipart.total_size_bytes,
        )

        self.db_session.commit()
        return multipart

    # ============================================================================
    # QUOTA MANAGEMENT OPERATIONS
    # ============================================================================

    async def get_quota(
        self,
        owner_type: str,
        owner_id: str,
    ) -> Optional[FileQuota]:
        """
        Get quota for owner.

        Args:
            owner_type: Owner type (user, hostel, tenant)
            owner_id: Owner identifier

        Returns:
            FileQuota if exists
        """
        return (
            self.db_session.query(FileQuota)
            .filter(
                FileQuota.owner_type == owner_type,
                FileQuota.owner_id == owner_id,
            )
            .first()
        )

    async def create_or_update_quota(
        self,
        owner_type: str,
        owner_id: str,
        quota_bytes: int,
        max_files: Optional[int] = None,
        max_file_size_bytes: Optional[int] = None,
    ) -> FileQuota:
        """
        Create or update quota settings.

        Args:
            owner_type: Owner type
            owner_id: Owner identifier
            quota_bytes: Total quota in bytes
            max_files: Maximum number of files
            max_file_size_bytes: Maximum size per file

        Returns:
            FileQuota record
        """
        quota = await self.get_quota(owner_type, owner_id)

        if quota:
            quota.quota_bytes = quota_bytes
            if max_files is not None:
                quota.max_files = max_files
            if max_file_size_bytes is not None:
                quota.max_file_size_bytes = max_file_size_bytes
        else:
            quota = FileQuota(
                owner_type=owner_type,
                owner_id=owner_id,
                quota_bytes=quota_bytes,
                max_files=max_files,
                max_file_size_bytes=max_file_size_bytes,
                used_bytes=0,
                reserved_bytes=0,
                current_file_count=0,
                is_enforced=True,
            )
            self.db_session.add(quota)

        self.db_session.commit()
        return quota

    async def _check_quota(
        self,
        owner_type: str,
        owner_id: str,
        file_size: int,
    ) -> None:
        """
        Check if upload would exceed quota.

        Args:
            owner_type: Owner type
            owner_id: Owner identifier
            file_size: File size to check

        Raises:
            QuotaExceededException: If quota would be exceeded
        """
        quota = await self.get_quota(owner_type, owner_id)

        if not quota or not quota.is_enforced:
            return

        # Check total size quota
        total_used = quota.used_bytes + quota.reserved_bytes + file_size
        if total_used > quota.quota_bytes:
            raise QuotaExceededException(
                f"Quota exceeded: {total_used} bytes would exceed limit of {quota.quota_bytes} bytes"
            )

        # Check file count quota
        if quota.max_files and quota.current_file_count >= quota.max_files:
            raise QuotaExceededException(
                f"File count limit reached: {quota.max_files} files"
            )

        # Check per-file size quota
        if quota.max_file_size_bytes and file_size > quota.max_file_size_bytes:
            raise QuotaExceededException(
                f"File too large: {file_size} bytes exceeds limit of {quota.max_file_size_bytes} bytes"
            )

    async def _update_quota_usage(
        self,
        owner_type: str,
        owner_id: str,
        size_delta: int = 0,
        reserved_delta: int = 0,
        file_count_delta: int = 0,
    ) -> None:
        """
        Update quota usage.

        Args:
            owner_type: Owner type
            owner_id: Owner identifier
            size_delta: Change in used bytes
            reserved_delta: Change in reserved bytes
            file_count_delta: Change in file count
        """
        quota = await self.get_quota(owner_type, owner_id)

        if not quota:
            # Create default quota if doesn't exist
            quota = await self.create_or_update_quota(
                owner_type=owner_type,
                owner_id=owner_id,
                quota_bytes=10 * 1024 * 1024 * 1024,  # 10 GB default
            )

        quota.used_bytes += size_delta
        quota.reserved_bytes += reserved_delta
        quota.current_file_count += file_count_delta
        quota.last_usage_update_at = datetime.utcnow()

        # Check if quota exceeded
        total_used = quota.used_bytes + quota.reserved_bytes
        quota.is_exceeded = total_used > quota.quota_bytes

        # Send alert if needed
        usage_percentage = (total_used / quota.quota_bytes * 100) if quota.quota_bytes > 0 else 0
        if (
            usage_percentage >= quota.alert_threshold_percentage
            and not quota.alert_sent_at
        ):
            quota.alert_sent_at = datetime.utcnow()
            # TODO: Trigger quota alert notification

        self.db_session.commit()

    async def get_quota_statistics(
        self,
        owner_type: str,
        owner_id: str,
    ) -> Dict[str, Any]:
        """
        Get detailed quota statistics.

        Args:
            owner_type: Owner type
            owner_id: Owner identifier

        Returns:
            Quota statistics dictionary
        """
        quota = await self.get_quota(owner_type, owner_id)

        if not quota:
            return {
                "quota_bytes": 0,
                "used_bytes": 0,
                "reserved_bytes": 0,
                "available_bytes": 0,
                "usage_percentage": 0,
                "file_count": 0,
                "is_exceeded": False,
            }

        total_used = quota.used_bytes + quota.reserved_bytes
        available = max(0, quota.quota_bytes - total_used)
        usage_percentage = (total_used / quota.quota_bytes * 100) if quota.quota_bytes > 0 else 0

        return {
            "quota_bytes": quota.quota_bytes,
            "used_bytes": quota.used_bytes,
            "reserved_bytes": quota.reserved_bytes,
            "available_bytes": available,
            "usage_percentage": round(usage_percentage, 2),
            "file_count": quota.current_file_count,
            "max_files": quota.max_files,
            "max_file_size_bytes": quota.max_file_size_bytes,
            "is_exceeded": quota.is_exceeded,
            "alert_threshold_percentage": quota.alert_threshold_percentage,
        }

    # ============================================================================
    # ANALYTICS AND REPORTING
    # ============================================================================

    async def get_upload_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        uploaded_by_user_id: Optional[str] = None,
        hostel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get upload statistics for specified period.

        Args:
            start_date: Start date for statistics
            end_date: End date for statistics
            uploaded_by_user_id: Filter by uploader
            hostel_id: Filter by hostel

        Returns:
            Statistics dictionary
        """
        query = self.db_session.query(
            func.count(FileUpload.id).label("total_uploads"),
            func.sum(FileUpload.size_bytes).label("total_size"),
            func.avg(FileUpload.size_bytes).label("average_size"),
            func.count(
                case([(FileUpload.processing_status == "completed", 1)])
            ).label("processed_count"),
            func.count(
                case([(FileUpload.virus_scan_status == "clean", 1)])
            ).label("clean_files"),
            func.count(
                case([(FileUpload.virus_scan_status == "infected", 1)])
            ).label("infected_files"),
        ).filter(FileUpload.deleted_at.is_(None))

        if start_date:
            query = query.filter(FileUpload.created_at >= start_date)

        if end_date:
            query = query.filter(FileUpload.created_at <= end_date)

        if uploaded_by_user_id:
            query = query.filter(
                FileUpload.uploaded_by_user_id == uploaded_by_user_id
            )

        if hostel_id:
            query = query.filter(FileUpload.hostel_id == hostel_id)

        result = query.first()

        return {
            "total_uploads": result.total_uploads or 0,
            "total_size_bytes": result.total_size or 0,
            "average_size_bytes": round(result.average_size or 0, 2),
            "processed_count": result.processed_count or 0,
            "clean_files": result.clean_files or 0,
            "infected_files": result.infected_files or 0,
        }

    async def get_storage_breakdown_by_category(
        self,
        uploaded_by_user_id: Optional[str] = None,
        hostel_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get storage usage breakdown by category.

        Args:
            uploaded_by_user_id: Filter by uploader
            hostel_id: Filter by hostel

        Returns:
            List of category breakdowns
        """
        query = self.db_session.query(
            FileUpload.category,
            func.count(FileUpload.id).label("file_count"),
            func.sum(FileUpload.size_bytes).label("total_size"),
        ).filter(FileUpload.deleted_at.is_(None))

        if uploaded_by_user_id:
            query = query.filter(
                FileUpload.uploaded_by_user_id == uploaded_by_user_id
            )

        if hostel_id:
            query = query.filter(FileUpload.hostel_id == hostel_id)

        results = query.group_by(FileUpload.category).all()

        return [
            {
                "category": row.category or "uncategorized",
                "file_count": row.file_count,
                "total_size_bytes": row.total_size or 0,
            }
            for row in results
        ]

    async def find_large_files(
        self,
        min_size_bytes: int,
        limit: int = 100,
        uploaded_by_user_id: Optional[str] = None,
    ) -> List[FileUpload]:
        """
        Find files larger than specified size.

        Args:
            min_size_bytes: Minimum file size
            limit: Maximum results
            uploaded_by_user_id: Filter by uploader

        Returns:
            List of large files
        """
        query = (
            self.db_session.query(FileUpload)
            .filter(
                FileUpload.size_bytes >= min_size_bytes,
                FileUpload.deleted_at.is_(None),
            )
            .order_by(desc(FileUpload.size_bytes))
            .limit(limit)
        )

        if uploaded_by_user_id:
            query = query.filter(
                FileUpload.uploaded_by_user_id == uploaded_by_user_id
            )

        return query.all()

    async def find_unused_files(
        self,
        days_unused: int = 90,
        limit: int = 100,
    ) -> List[FileUpload]:
        """
        Find files not accessed for specified days.

        Args:
            days_unused: Days of inactivity
            limit: Maximum results

        Returns:
            List of unused files
        """
        threshold_date = datetime.utcnow() - timedelta(days=days_unused)

        return (
            self.db_session.query(FileUpload)
            .filter(
                FileUpload.deleted_at.is_(None),
                or_(
                    FileUpload.last_accessed_at.is_(None),
                    FileUpload.last_accessed_at < threshold_date,
                ),
                FileUpload.created_at < threshold_date,
            )
            .order_by(asc(FileUpload.last_accessed_at))
            .limit(limit)
            .all()
        )


class QuotaExceededException(Exception):
    """Exception raised when file quota is exceeded."""
    pass