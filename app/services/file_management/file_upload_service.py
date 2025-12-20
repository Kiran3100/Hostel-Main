"""
File Upload Service

Orchestrates file upload workflow with session management, quota enforcement,
and processing triggers.
"""

import hashlib
import mimetypes
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, BinaryIO
from uuid import uuid4
import logging

from sqlalchemy.orm import Session

from app.repositories.file_management.file_upload_repository import (
    FileUploadRepository,
    QuotaExceededException,
)
from app.repositories.file_management.image_upload_repository import (
    ImageUploadRepository,
)
from app.repositories.file_management.document_upload_repository import (
    DocumentUploadRepository,
)
from app.services.file_management.file_storage_service import FileStorageService
from app.services.file_management.file_validation_service import FileValidationService
from app.core.exceptions import (
    ValidationException,
    StorageException,
    NotFoundException,
)

logger = logging.getLogger(__name__)


class FileUploadService:
    """
    Service for managing file uploads with comprehensive workflow orchestration.
    """

    def __init__(
        self,
        db_session: Session,
        storage_service: FileStorageService,
        validation_service: FileValidationService,
    ):
        self.db = db_session
        self.file_repo = FileUploadRepository(db_session)
        self.image_repo = ImageUploadRepository(db_session)
        self.document_repo = DocumentUploadRepository(db_session)
        self.storage = storage_service
        self.validator = validation_service

    # ============================================================================
    # DIRECT UPLOAD WORKFLOW
    # ============================================================================

    async def upload_file(
        self,
        file_stream: BinaryIO,
        filename: str,
        uploaded_by_user_id: str,
        content_type: Optional[str] = None,
        category: Optional[str] = None,
        folder: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_public: bool = False,
        hostel_id: Optional[str] = None,
        student_id: Optional[str] = None,
        check_duplicates: bool = True,
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Upload file with full validation and processing pipeline.

        Args:
            file_stream: File binary stream
            filename: Original filename
            uploaded_by_user_id: User uploading the file
            content_type: MIME type (auto-detected if None)
            category: File category
            folder: Logical folder path
            tags: File tags
            metadata: Custom metadata
            is_public: Whether file is publicly accessible
            hostel_id: Associated hostel
            student_id: Associated student
            check_duplicates: Whether to check for duplicates
            audit_context: Audit context

        Returns:
            Upload result with file details

        Raises:
            ValidationException: If validation fails
            QuotaExceededException: If quota exceeded
            StorageException: If storage operation fails
        """
        try:
            logger.info(f"Starting file upload: {filename} by user {uploaded_by_user_id}")

            # Step 1: Read file content
            file_content = file_stream.read()
            file_size = len(file_content)
            file_stream.seek(0)  # Reset stream

            # Step 2: Detect content type if not provided
            if not content_type:
                content_type = self._detect_content_type(filename, file_content)

            # Step 3: Generate file identifiers
            file_id = str(uuid4())
            extension = self._extract_extension(filename)
            storage_key = self._generate_storage_key(
                user_id=uploaded_by_user_id,
                filename=filename,
                file_id=file_id,
                folder=folder,
            )

            # Step 4: Calculate checksum
            checksum = self._calculate_checksum(file_content)

            # Step 5: Check for duplicates
            if check_duplicates:
                duplicate = await self._check_duplicate(
                    checksum=checksum,
                    uploaded_by_user_id=uploaded_by_user_id,
                )
                if duplicate:
                    logger.info(f"Duplicate file detected: {duplicate.file_id}")
                    return {
                        "status": "duplicate",
                        "file_id": duplicate.file_id,
                        "message": "File already exists",
                        "existing_file": self._serialize_file(duplicate),
                    }

            # Step 6: Validate file
            validation_result = await self.validator.validate_file(
                file_content=file_content,
                filename=filename,
                content_type=content_type,
                size_bytes=file_size,
                category=category,
                uploaded_by_user_id=uploaded_by_user_id,
            )

            if not validation_result["is_valid"]:
                raise ValidationException(
                    f"File validation failed: {', '.join(validation_result['errors'])}"
                )

            # Step 7: Check quota
            await self._check_quota(
                uploaded_by_user_id=uploaded_by_user_id,
                file_size=file_size,
            )

            # Step 8: Upload to storage
            upload_result = await self.storage.upload_file(
                file_content=file_content,
                storage_key=storage_key,
                content_type=content_type,
                metadata=metadata or {},
                is_public=is_public,
            )

            # Step 9: Create file record
            file_data = {
                "file_id": file_id,
                "storage_key": storage_key,
                "filename": filename,
                "content_type": content_type,
                "size_bytes": file_size,
                "extension": extension,
                "checksum": checksum,
                "etag": upload_result.get("etag"),
                "url": upload_result["url"],
                "public_url": upload_result.get("public_url") if is_public else None,
                "hostel_id": hostel_id,
                "student_id": student_id,
                "folder": folder,
                "category": category,
                "tags": tags or [],
                "metadata": metadata or {},
                "is_public": is_public,
            }

            file_upload = await self.file_repo.create_file_upload(
                file_data=file_data,
                uploaded_by_user_id=uploaded_by_user_id,
                audit_context=audit_context,
            )

            # Step 10: Store validation results
            if validation_result.get("validation_details"):
                await self.file_repo.create_validation_result(
                    file_id=file_upload.file_id,
                    validation_data=validation_result["validation_details"],
                )

            # Step 11: Trigger post-upload processing
            await self._trigger_post_upload_processing(
                file_upload=file_upload,
                content_type=content_type,
            )

            logger.info(f"File upload completed: {file_id}")

            return {
                "status": "success",
                "file_id": file_upload.file_id,
                "file": self._serialize_file(file_upload),
                "validation": validation_result,
            }

        except QuotaExceededException as e:
            logger.warning(f"Quota exceeded for user {uploaded_by_user_id}: {str(e)}")
            raise
        except ValidationException as e:
            logger.warning(f"File validation failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"File upload failed: {str(e)}", exc_info=True)
            # Cleanup storage if file was uploaded
            if 'storage_key' in locals():
                try:
                    await self.storage.delete_file(storage_key)
                except Exception as cleanup_error:
                    logger.error(f"Cleanup failed: {str(cleanup_error)}")
            raise StorageException(f"File upload failed: {str(e)}")

    # ============================================================================
    # MULTIPART UPLOAD WORKFLOW
    # ============================================================================

    async def initiate_multipart_upload(
        self,
        filename: str,
        content_type: str,
        file_size: int,
        uploaded_by_user_id: str,
        category: Optional[str] = None,
        folder: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        hostel_id: Optional[str] = None,
        student_id: Optional[str] = None,
        part_size_mb: int = 5,
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Initiate multipart upload for large files.

        Args:
            filename: Original filename
            content_type: MIME type
            file_size: Total file size in bytes
            uploaded_by_user_id: User uploading
            category: File category
            folder: Logical folder
            metadata: Custom metadata
            hostel_id: Associated hostel
            student_id: Associated student
            part_size_mb: Part size in MB
            audit_context: Audit context

        Returns:
            Multipart upload session details

        Raises:
            ValidationException: If validation fails
            QuotaExceededException: If quota exceeded
        """
        try:
            logger.info(f"Initiating multipart upload: {filename} ({file_size} bytes)")

            # Validate file size
            if file_size < 5 * 1024 * 1024:  # 5 MB minimum
                raise ValidationException(
                    "File too small for multipart upload. Use direct upload instead."
                )

            # Check quota
            await self._check_quota(
                uploaded_by_user_id=uploaded_by_user_id,
                file_size=file_size,
            )

            # Generate identifiers
            upload_id = str(uuid4())
            file_id = str(uuid4())
            storage_key = self._generate_storage_key(
                user_id=uploaded_by_user_id,
                filename=filename,
                file_id=file_id,
                folder=folder,
            )

            # Calculate parts
            part_size_bytes = part_size_mb * 1024 * 1024
            total_parts = (file_size + part_size_bytes - 1) // part_size_bytes

            # Initiate multipart upload in storage
            multipart_result = await self.storage.initiate_multipart_upload(
                storage_key=storage_key,
                content_type=content_type,
                metadata=metadata or {},
            )

            # Create upload session
            session_data = {
                "upload_id": upload_id,
                "session_type": "multipart",
                "storage_key": storage_key,
                "filename": filename,
                "content_type": content_type,
                "expected_size_bytes": file_size,
                "expires_at": datetime.utcnow() + timedelta(hours=24),
                "metadata": {
                    "file_id": file_id,
                    "hostel_id": hostel_id,
                    "student_id": student_id,
                    "category": category,
                    "folder": folder,
                    "multipart_upload_id": multipart_result["upload_id"],
                },
            }

            upload_session = await self.file_repo.create_upload_session(
                session_data=session_data,
                uploaded_by_user_id=uploaded_by_user_id,
                audit_context=audit_context,
            )

            # Create multipart upload tracking
            multipart_data = {
                "multipart_upload_id": multipart_result["upload_id"],
                "total_size_bytes": file_size,
                "part_size_bytes": part_size_bytes,
                "total_parts": total_parts,
            }

            multipart_upload = await self.file_repo.create_multipart_upload(
                session_id=upload_session.id,
                multipart_data=multipart_data,
            )

            # Create part upload URLs
            parts = []
            for part_number in range(1, total_parts + 1):
                part_start = (part_number - 1) * part_size_bytes
                part_end = min(part_start + part_size_bytes, file_size)
                part_size = part_end - part_start

                # Get pre-signed URL for part
                part_url = await self.storage.get_multipart_upload_url(
                    storage_key=storage_key,
                    upload_id=multipart_result["upload_id"],
                    part_number=part_number,
                )

                # Create part record
                part_data = {
                    "part_number": part_number,
                    "size_bytes": part_size,
                    "upload_url": part_url,
                    "url_expires_at": datetime.utcnow() + timedelta(hours=1),
                }

                part_record = await self.file_repo.create_multipart_part(
                    multipart_upload_id=multipart_upload.id,
                    part_data=part_data,
                )

                parts.append({
                    "part_number": part_number,
                    "upload_url": part_url,
                    "size_bytes": part_size,
                    "byte_range": f"{part_start}-{part_end - 1}",
                })

            logger.info(f"Multipart upload initiated: {upload_id} with {total_parts} parts")

            return {
                "upload_id": upload_id,
                "file_id": file_id,
                "storage_key": storage_key,
                "total_parts": total_parts,
                "part_size_bytes": part_size_bytes,
                "expires_at": session_data["expires_at"].isoformat(),
                "parts": parts,
            }

        except Exception as e:
            logger.error(f"Multipart upload initiation failed: {str(e)}", exc_info=True)
            raise

    async def complete_multipart_upload(
        self,
        upload_id: str,
        parts: List[Dict[str, Any]],
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Complete multipart upload and create file record.

        Args:
            upload_id: Upload session ID
            parts: List of completed parts with ETags
            audit_context: Audit context

        Returns:
            Completed file details

        Raises:
            NotFoundException: If upload session not found
            ValidationException: If parts validation fails
            StorageException: If completion fails
        """
        try:
            logger.info(f"Completing multipart upload: {upload_id}")

            # Get upload session
            upload_session = await self.file_repo.find_upload_session(upload_id)
            if not upload_session:
                raise NotFoundException(f"Upload session not found: {upload_id}")

            # Get multipart upload
            multipart_upload = upload_session.multipart_upload
            if not multipart_upload:
                raise NotFoundException(f"Multipart upload not found for session: {upload_id}")

            # Validate all parts uploaded
            if len(parts) != multipart_upload.total_parts:
                raise ValidationException(
                    f"Missing parts: expected {multipart_upload.total_parts}, got {len(parts)}"
                )

            # Update part statuses
            for part in parts:
                await self.file_repo.update_multipart_part_status(
                    multipart_upload_id=multipart_upload.id,
                    part_number=part["part_number"],
                    status="completed",
                    etag=part["etag"],
                )

            # Complete multipart upload in storage
            storage_result = await self.storage.complete_multipart_upload(
                storage_key=upload_session.storage_key,
                upload_id=multipart_upload.multipart_upload_id,
                parts=parts,
            )

            # Generate file ID
            file_id = upload_session.session_metadata.get("file_id", str(uuid4()))

            # Create file record
            file_data = {
                "file_id": file_id,
                "storage_key": upload_session.storage_key,
                "filename": upload_session.filename,
                "content_type": upload_session.content_type,
                "size_bytes": upload_session.expected_size_bytes,
                "extension": self._extract_extension(upload_session.filename),
                "etag": storage_result.get("etag"),
                "url": storage_result["url"],
                "hostel_id": upload_session.session_metadata.get("hostel_id"),
                "student_id": upload_session.session_metadata.get("student_id"),
                "folder": upload_session.session_metadata.get("folder"),
                "category": upload_session.session_metadata.get("category"),
                "metadata": upload_session.session_metadata,
            }

            file_upload = await self.file_repo.create_file_upload(
                file_data=file_data,
                uploaded_by_user_id=upload_session.uploaded_by_user_id,
                audit_context=audit_context,
            )

            # Mark multipart upload as completed
            await self.file_repo.complete_multipart_upload(
                multipart_upload_id=multipart_upload.id,
                file_id=file_upload.file_id,
            )

            # Trigger post-upload processing
            await self._trigger_post_upload_processing(
                file_upload=file_upload,
                content_type=upload_session.content_type,
            )

            logger.info(f"Multipart upload completed: {file_id}")

            return {
                "status": "success",
                "file_id": file_upload.file_id,
                "file": self._serialize_file(file_upload),
            }

        except Exception as e:
            logger.error(f"Multipart upload completion failed: {str(e)}", exc_info=True)
            raise

    # ============================================================================
    # FILE RETRIEVAL
    # ============================================================================

    async def get_file(
        self,
        file_id: str,
        accessed_by_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get file details with access tracking.

        Args:
            file_id: File identifier
            accessed_by_user_id: User accessing the file

        Returns:
            File details

        Raises:
            NotFoundException: If file not found
        """
        file_upload = await self.file_repo.find_by_file_id(
            file_id=file_id,
            load_relationships=True,
        )

        if not file_upload:
            raise NotFoundException(f"File not found: {file_id}")

        # Track access
        if accessed_by_user_id:
            await self.file_repo.track_file_access(
                file_id=file_id,
                accessed_by_user_id=accessed_by_user_id,
            )

        return self._serialize_file(file_upload)

    async def get_download_url(
        self,
        file_id: str,
        accessed_by_user_id: str,
        expires_in_seconds: int = 3600,
    ) -> str:
        """
        Get temporary download URL for file.

        Args:
            file_id: File identifier
            accessed_by_user_id: User requesting download
            expires_in_seconds: URL expiration time

        Returns:
            Pre-signed download URL

        Raises:
            NotFoundException: If file not found
        """
        file_upload = await self.file_repo.find_by_file_id(file_id)
        if not file_upload:
            raise NotFoundException(f"File not found: {file_id}")

        # Track access
        await self.file_repo.track_file_access(
            file_id=file_id,
            accessed_by_user_id=accessed_by_user_id,
        )

        # Generate download URL
        download_url = await self.storage.generate_download_url(
            storage_key=file_upload.storage_key,
            expires_in=expires_in_seconds,
            filename=file_upload.filename,
        )

        return download_url

    # ============================================================================
    # FILE DELETION
    # ============================================================================

    async def delete_file(
        self,
        file_id: str,
        deleted_by_user_id: str,
        permanent: bool = False,
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Delete file (soft or permanent).

        Args:
            file_id: File identifier
            deleted_by_user_id: User deleting the file
            permanent: Whether to permanently delete
            audit_context: Audit context

        Returns:
            Deletion result

        Raises:
            NotFoundException: If file not found
        """
        file_upload = await self.file_repo.find_by_file_id(file_id)
        if not file_upload:
            raise NotFoundException(f"File not found: {file_id}")

        if permanent:
            # Delete from storage
            await self.storage.delete_file(file_upload.storage_key)

            # Delete variants if image
            if file_upload.image_upload:
                for variant in file_upload.image_upload.variants:
                    await self.storage.delete_file(variant.storage_key)

            # Hard delete from database
            await self.file_repo.delete(file_upload.id, audit_context)

            # Update quota
            await self.file_repo._update_quota_usage(
                owner_type="user",
                owner_id=deleted_by_user_id,
                size_delta=-file_upload.size_bytes,
                file_count_delta=-1,
            )

            return {
                "status": "permanently_deleted",
                "file_id": file_id,
            }
        else:
            # Soft delete
            await self.file_repo.soft_delete(file_upload.id, audit_context)

            return {
                "status": "soft_deleted",
                "file_id": file_id,
                "can_restore": True,
            }

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _detect_content_type(self, filename: str, content: bytes) -> str:
        """Detect MIME type from filename and content."""
        # Try from filename
        content_type, _ = mimetypes.guess_type(filename)
        
        if content_type:
            return content_type

        # Detect from magic bytes
        if content.startswith(b'\xFF\xD8\xFF'):
            return 'image/jpeg'
        elif content.startswith(b'\x89PNG'):
            return 'image/png'
        elif content.startswith(b'GIF8'):
            return 'image/gif'
        elif content.startswith(b'%PDF'):
            return 'application/pdf'
        elif content.startswith(b'PK\x03\x04'):
            return 'application/zip'

        return 'application/octet-stream'

    def _extract_extension(self, filename: str) -> Optional[str]:
        """Extract file extension without dot."""
        parts = filename.rsplit('.', 1)
        if len(parts) > 1:
            return parts[1].lower()
        return None

    def _generate_storage_key(
        self,
        user_id: str,
        filename: str,
        file_id: str,
        folder: Optional[str] = None,
    ) -> str:
        """Generate storage key/path for file."""
        # Structure: uploads/{year}/{month}/{user_id}/{folder}/{file_id}_{filename}
        now = datetime.utcnow()
        year = now.strftime('%Y')
        month = now.strftime('%m')
        
        parts = ['uploads', year, month, user_id]
        
        if folder:
            parts.append(folder)
        
        # Sanitize filename
        safe_filename = filename.replace(' ', '_').replace('/', '_')
        parts.append(f"{file_id}_{safe_filename}")
        
        return '/'.join(parts)

    def _calculate_checksum(self, content: bytes) -> str:
        """Calculate SHA-256 checksum."""
        return hashlib.sha256(content).hexdigest()

    async def _check_duplicate(
        self,
        checksum: str,
        uploaded_by_user_id: str,
    ) -> Optional[Any]:
        """Check for duplicate files by checksum."""
        duplicates = await self.file_repo.find_by_checksum(
            checksum=checksum,
            uploaded_by_user_id=uploaded_by_user_id,
        )
        return duplicates[0] if duplicates else None

    async def _check_quota(
        self,
        uploaded_by_user_id: str,
        file_size: int,
    ) -> None:
        """Check if upload would exceed quota."""
        # This is already handled in repository, but we can add service-level checks
        quota_stats = await self.file_repo.get_quota_statistics(
            owner_type="user",
            owner_id=uploaded_by_user_id,
        )

        if quota_stats["is_exceeded"]:
            raise QuotaExceededException(
                f"Storage quota exceeded. Used: {quota_stats['used_bytes']} / {quota_stats['quota_bytes']} bytes"
            )

        available = quota_stats["available_bytes"]
        if file_size > available:
            raise QuotaExceededException(
                f"Insufficient storage. File size: {file_size}, Available: {available} bytes"
            )

    async def _trigger_post_upload_processing(
        self,
        file_upload: Any,
        content_type: str,
    ) -> None:
        """Trigger post-upload processing based on file type."""
        # Trigger virus scan
        await self.file_repo.update_virus_scan_status(
            file_id=file_upload.file_id,
            status="pending",
        )

        # Queue type-specific processing
        if content_type.startswith('image/'):
            # Will be handled by ImageProcessingService
            logger.info(f"Image processing queued for: {file_upload.file_id}")
        elif content_type == 'application/pdf' or content_type.startswith('application/vnd'):
            # Will be handled by DocumentProcessingService
            logger.info(f"Document processing queued for: {file_upload.file_id}")

    def _serialize_file(self, file_upload: Any) -> Dict[str, Any]:
        """Serialize file upload to dictionary."""
        return {
            "id": file_upload.id,
            "file_id": file_upload.file_id,
            "filename": file_upload.filename,
            "content_type": file_upload.content_type,
            "size_bytes": file_upload.size_bytes,
            "extension": file_upload.extension,
            "url": file_upload.url,
            "public_url": file_upload.public_url,
            "checksum": file_upload.checksum,
            "folder": file_upload.folder,
            "category": file_upload.category,
            "tags": file_upload.tags,
            "is_public": file_upload.is_public,
            "processing_status": file_upload.processing_status,
            "virus_scan_status": file_upload.virus_scan_status,
            "uploaded_by_user_id": file_upload.uploaded_by_user_id,
            "created_at": file_upload.created_at.isoformat(),
            "metadata": file_upload.metadata,
        }