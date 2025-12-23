"""
File Cleanup Service

Manages automated cleanup tasks:
- Purge incomplete uploads
- Remove old file versions
- Clean up failed processing artifacts
- Archive expired documents
- Storage optimization
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.file_management.file_upload_repository import FileUploadRepository
from app.repositories.file_management.file_metadata_repository import FileMetadataRepository
from app.repositories.file_management.document_upload_repository import DocumentUploadRepository
from app.repositories.file_management.image_upload_repository import ImageUploadRepository
from app.models.file_management.file_upload import FileUpload as FileUploadModel

logger = logging.getLogger(__name__)


class FileCleanupService(BaseService[FileUploadModel, FileUploadRepository]):
    """
    Automated cleanup and maintenance of file artifacts.
    
    Features:
    - Scheduled cleanup of stale uploads
    - Version history pruning
    - Failed processing cleanup
    - Archive management
    - Storage quota enforcement
    """

    def __init__(
        self,
        file_repo: FileUploadRepository,
        meta_repo: FileMetadataRepository,
        doc_repo: DocumentUploadRepository,
        img_repo: ImageUploadRepository,
        db_session: Session,
    ):
        """
        Initialize the file cleanup service.
        
        Args:
            file_repo: File upload repository
            meta_repo: File metadata repository
            doc_repo: Document upload repository
            img_repo: Image upload repository
            db_session: SQLAlchemy database session
        """
        super().__init__(file_repo, db_session)
        self.file_repo = file_repo
        self.meta_repo = meta_repo
        self.doc_repo = doc_repo
        self.img_repo = img_repo
        self._cleanup_stats = {
            "incomplete_uploads": 0,
            "old_versions": 0,
            "failed_images": 0,
            "archived_documents": 0,
            "total_bytes_freed": 0
        }
        logger.info("FileCleanupService initialized with all repositories")

    def purge_incomplete_uploads(
        self,
        older_than_hours: int = 24,
        dry_run: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Purge incomplete uploads older than specified hours.
        
        Args:
            older_than_hours: Age threshold in hours
            dry_run: If True, return count without deleting
            
        Returns:
            ServiceResult with cleanup statistics
        """
        try:
            if older_than_hours < 1:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="older_than_hours must be at least 1",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            before = datetime.utcnow() - timedelta(hours=older_than_hours)

            logger.info(
                f"{'[DRY RUN] ' if dry_run else ''}Purging incomplete uploads "
                f"older than {older_than_hours} hours (before {before})"
            )

            count = self.file_repo.cleanup_incomplete_before(before, dry_run=dry_run)

            if not dry_run:
                self.db.commit()
                self._cleanup_stats["incomplete_uploads"] += count

            logger.info(
                f"{'[DRY RUN] ' if dry_run else ''}Purged {count} incomplete uploads"
            )

            return ServiceResult.success(
                {
                    "count": count or 0,
                    "dry_run": dry_run,
                    "threshold_hours": older_than_hours,
                    "before_date": before.isoformat()
                },
                message=f"{'Would purge' if dry_run else 'Purged'} {count or 0} incomplete uploads"
            )

        except Exception as e:
            if not dry_run:
                self.db.rollback()
            logger.error(f"Failed to purge incomplete uploads: {str(e)}", exc_info=True)
            return self._handle_exception(e, "purge incomplete uploads")

    def purge_old_versions(
        self,
        keep_last: int = 5,
        dry_run: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Purge old file versions, keeping only the most recent ones.
        
        Args:
            keep_last: Number of versions to keep per file
            dry_run: If True, return count without deleting
            
        Returns:
            ServiceResult with cleanup statistics
        """
        try:
            if keep_last < 1:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="keep_last must be at least 1",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            logger.info(
                f"{'[DRY RUN] ' if dry_run else ''}Purging old versions, "
                f"keeping last {keep_last} per file"
            )

            count = self.meta_repo.cleanup_old_versions(keep_last=keep_last, dry_run=dry_run)

            if not dry_run:
                self.db.commit()
                self._cleanup_stats["old_versions"] += count

            logger.info(
                f"{'[DRY RUN] ' if dry_run else ''}Purged {count} old versions"
            )

            return ServiceResult.success(
                {
                    "count": count or 0,
                    "dry_run": dry_run,
                    "keep_last": keep_last
                },
                message=f"{'Would purge' if dry_run else 'Purged'} {count or 0} old versions"
            )

        except Exception as e:
            if not dry_run:
                self.db.rollback()
            logger.error(f"Failed to purge old versions: {str(e)}", exc_info=True)
            return self._handle_exception(e, "purge old versions")

    def purge_failed_images(
        self,
        older_than_days: int = 7,
        dry_run: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Purge failed image processing records.
        
        Args:
            older_than_days: Age threshold in days
            dry_run: If True, return count without deleting
            
        Returns:
            ServiceResult with cleanup statistics
        """
        try:
            if older_than_days < 1:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="older_than_days must be at least 1",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            before = datetime.utcnow() - timedelta(days=older_than_days)

            logger.info(
                f"{'[DRY RUN] ' if dry_run else ''}Purging failed images "
                f"older than {older_than_days} days (before {before})"
            )

            count = self.img_repo.cleanup_failed_before(before, dry_run=dry_run)

            if not dry_run:
                self.db.commit()
                self._cleanup_stats["failed_images"] += count

            logger.info(
                f"{'[DRY RUN] ' if dry_run else ''}Purged {count} failed images"
            )

            return ServiceResult.success(
                {
                    "count": count or 0,
                    "dry_run": dry_run,
                    "threshold_days": older_than_days,
                    "before_date": before.isoformat()
                },
                message=f"{'Would purge' if dry_run else 'Purged'} {count or 0} failed images"
            )

        except Exception as e:
            if not dry_run:
                self.db.rollback()
            logger.error(f"Failed to purge failed images: {str(e)}", exc_info=True)
            return self._handle_exception(e, "purge failed images")

    def purge_archived_documents(
        self,
        older_than_days: int = 180,
        dry_run: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Purge archived documents older than retention period.
        
        Args:
            older_than_days: Retention period in days
            dry_run: If True, return count without deleting
            
        Returns:
            ServiceResult with cleanup statistics
        """
        try:
            if older_than_days < 30:  # Minimum 30 days retention
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="older_than_days must be at least 30 for archived documents",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            before = datetime.utcnow() - timedelta(days=older_than_days)

            logger.info(
                f"{'[DRY RUN] ' if dry_run else ''}Purging archived documents "
                f"older than {older_than_days} days (before {before})"
            )

            count = self.doc_repo.cleanup_archived_before(before, dry_run=dry_run)

            if not dry_run:
                self.db.commit()
                self._cleanup_stats["archived_documents"] += count

            logger.info(
                f"{'[DRY RUN] ' if dry_run else ''}Purged {count} archived documents"
            )

            return ServiceResult.success(
                {
                    "count": count or 0,
                    "dry_run": dry_run,
                    "threshold_days": older_than_days,
                    "before_date": before.isoformat()
                },
                message=f"{'Would purge' if dry_run else 'Purged'} {count or 0} archived documents"
            )

        except Exception as e:
            if not dry_run:
                self.db.rollback()
            logger.error(f"Failed to purge archived documents: {str(e)}", exc_info=True)
            return self._handle_exception(e, "purge archived documents")

    def run_full_cleanup(
        self,
        config: Optional[Dict[str, int]] = None,
        dry_run: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Run all cleanup tasks with configurable thresholds.
        
        Args:
            config: Configuration dict with thresholds (e.g., {"incomplete_hours": 24, ...})
            dry_run: If True, simulate without deleting
            
        Returns:
            ServiceResult with comprehensive cleanup statistics
        """
        try:
            # Default configuration
            default_config = {
                "incomplete_hours": 24,
                "version_keep_last": 5,
                "failed_images_days": 7,
                "archived_documents_days": 180
            }

            # Merge with provided config
            cleanup_config = {**default_config, **(config or {})}

            logger.info(
                f"{'[DRY RUN] ' if dry_run else ''}Running full cleanup with config: "
                f"{cleanup_config}"
            )

            results = {
                "incomplete_uploads": {},
                "old_versions": {},
                "failed_images": {},
                "archived_documents": {},
                "total_items_cleaned": 0,
                "dry_run": dry_run
            }

            # 1. Purge incomplete uploads
            incomplete_result = self.purge_incomplete_uploads(
                older_than_hours=cleanup_config["incomplete_hours"],
                dry_run=dry_run
            )
            if incomplete_result.success:
                results["incomplete_uploads"] = incomplete_result.data
                results["total_items_cleaned"] += incomplete_result.data.get("count", 0)

            # 2. Purge old versions
            versions_result = self.purge_old_versions(
                keep_last=cleanup_config["version_keep_last"],
                dry_run=dry_run
            )
            if versions_result.success:
                results["old_versions"] = versions_result.data
                results["total_items_cleaned"] += versions_result.data.get("count", 0)

            # 3. Purge failed images
            images_result = self.purge_failed_images(
                older_than_days=cleanup_config["failed_images_days"],
                dry_run=dry_run
            )
            if images_result.success:
                results["failed_images"] = images_result.data
                results["total_items_cleaned"] += images_result.data.get("count", 0)

            # 4. Purge archived documents
            documents_result = self.purge_archived_documents(
                older_than_days=cleanup_config["archived_documents_days"],
                dry_run=dry_run
            )
            if documents_result.success:
                results["archived_documents"] = documents_result.data
                results["total_items_cleaned"] += documents_result.data.get("count", 0)

            logger.info(
                f"{'[DRY RUN] ' if dry_run else ''}Full cleanup completed, "
                f"total items: {results['total_items_cleaned']}"
            )

            return ServiceResult.success(
                results,
                message=f"{'Would clean' if dry_run else 'Cleaned'} {results['total_items_cleaned']} items"
            )

        except Exception as e:
            if not dry_run:
                self.db.rollback()
            logger.error(f"Full cleanup failed: {str(e)}", exc_info=True)
            return self._handle_exception(e, "run full cleanup")

    def get_cleanup_stats(self) -> ServiceResult[Dict[str, Any]]:
        """
        Get cumulative cleanup statistics.
        
        Returns:
            ServiceResult containing cleanup statistics
        """
        try:
            logger.debug("Retrieving cleanup statistics")

            return ServiceResult.success(
                self._cleanup_stats.copy(),
                message="Cleanup statistics retrieved"
            )

        except Exception as e:
            logger.error(f"Failed to get cleanup stats: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get cleanup stats")

    def reset_cleanup_stats(self) -> ServiceResult[bool]:
        """
        Reset cleanup statistics.
        
        Returns:
            ServiceResult indicating success
        """
        try:
            logger.info("Resetting cleanup statistics")

            self._cleanup_stats = {
                "incomplete_uploads": 0,
                "old_versions": 0,
                "failed_images": 0,
                "archived_documents": 0,
                "total_bytes_freed": 0
            }

            return ServiceResult.success(True, message="Cleanup statistics reset")

        except Exception as e:
            logger.error(f"Failed to reset cleanup stats: {str(e)}", exc_info=True)
            return self._handle_exception(e, "reset cleanup stats")

    def estimate_storage_savings(
        self,
        config: Optional[Dict[str, int]] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Estimate potential storage savings from cleanup.
        
        Args:
            config: Cleanup configuration
            
        Returns:
            ServiceResult with storage savings estimate
        """
        try:
            logger.info("Estimating storage savings from cleanup")

            # Run dry run of full cleanup
            dry_run_result = self.run_full_cleanup(config=config, dry_run=True)

            if not dry_run_result.success:
                return dry_run_result

            estimate = {
                "total_items": dry_run_result.data.get("total_items_cleaned", 0),
                "estimated_bytes_freed": 0,  # Would need to calculate from actual file sizes
                "breakdown": dry_run_result.data
            }

            return ServiceResult.success(
                estimate,
                message="Storage savings estimated"
            )

        except Exception as e:
            logger.error(f"Failed to estimate storage savings: {str(e)}", exc_info=True)
            return self._handle_exception(e, "estimate storage savings")