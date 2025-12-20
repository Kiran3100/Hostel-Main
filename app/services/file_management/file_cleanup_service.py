"""
File Cleanup Service

Automated cleanup tasks for expired sessions, orphaned records,
temporary files, and storage optimization.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session

from app.repositories.file_management.file_upload_repository import FileUploadRepository
from app.repositories.file_management.file_aggregate_repository import FileAggregateRepository
from app.repositories.file_management.file_metadata_repository import FileMetadataRepository
from app.repositories.file_management.image_upload_repository import ImageUploadRepository
from app.repositories.file_management.document_upload_repository import DocumentUploadRepository
from app.services.file_management.file_storage_service import FileStorageService

logger = logging.getLogger(__name__)


class FileCleanupService:
    """
    Service for automated file cleanup and maintenance tasks.
    """

    def __init__(
        self,
        db_session: Session,
        storage_service: FileStorageService,
    ):
        self.db = db_session
        self.file_repo = FileUploadRepository(db_session)
        self.aggregate_repo = FileAggregateRepository(db_session)
        self.metadata_repo = FileMetadataRepository(db_session)
        self.image_repo = ImageUploadRepository(db_session)
        self.document_repo = DocumentUploadRepository(db_session)
        self.storage = storage_service

    # ============================================================================
    # SESSION CLEANUP
    # ============================================================================

    async def cleanup_expired_upload_sessions(
        self,
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Clean up expired upload sessions and release reserved quota.

        Args:
            batch_size: Number of sessions to clean per batch

        Returns:
            Cleanup results
        """
        try:
            logger.info("Starting expired upload sessions cleanup")

            cleaned_count = await self.file_repo.cleanup_expired_sessions(
                batch_size=batch_size
            )

            logger.info(f"Expired sessions cleaned: {cleaned_count}")

            return {
                "task": "cleanup_expired_sessions",
                "sessions_cleaned": cleaned_count,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Session cleanup failed: {str(e)}", exc_info=True)
            return {
                "task": "cleanup_expired_sessions",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    # ============================================================================
    # ORPHANED RECORDS CLEANUP
    # ============================================================================

    async def cleanup_orphaned_records(
        self,
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Clean up orphaned records across all file management tables.

        Args:
            batch_size: Number of records to process per batch

        Returns:
            Cleanup results
        """
        try:
            logger.info("Starting orphaned records cleanup")

            cleaned = await self.aggregate_repo.cleanup_orphaned_records(
                batch_size=batch_size
            )

            total_cleaned = sum(cleaned.values())

            logger.info(f"Orphaned records cleaned: {total_cleaned}")

            return {
                "task": "cleanup_orphaned_records",
                "records_cleaned": cleaned,
                "total_cleaned": total_cleaned,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Orphaned records cleanup failed: {str(e)}", exc_info=True)
            return {
                "task": "cleanup_orphaned_records",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    # ============================================================================
    # SOFT-DELETED FILES CLEANUP
    # ============================================================================

    async def cleanup_soft_deleted_files(
        self,
        days_old: int = 30,
        batch_size: int = 50,
        permanent_delete: bool = True,
    ) -> Dict[str, Any]:
        """
        Clean up soft-deleted files older than specified days.

        Args:
            days_old: Age threshold in days
            batch_size: Number of files to process
            permanent_delete: Whether to permanently delete from storage

        Returns:
            Cleanup results
        """
        try:
            logger.info(f"Starting soft-deleted files cleanup (older than {days_old} days)")

            threshold_date = datetime.utcnow() - timedelta(days=days_old)

            # Find soft-deleted files
            deleted_files = (
                self.db.query(self.file_repo.model)
                .filter(
                    self.file_repo.model.deleted_at.isnot(None),
                    self.file_repo.model.deleted_at < threshold_date,
                )
                .limit(batch_size)
                .all()
            )

            cleaned_count = 0
            storage_freed = 0
            errors = []

            for file_upload in deleted_files:
                try:
                    if permanent_delete:
                        # Delete from storage
                        await self.storage.delete_file(file_upload.storage_key)

                        # Delete variants if image
                        if hasattr(file_upload, 'image_upload') and file_upload.image_upload:
                            image_upload = file_upload.image_upload
                            if image_upload.variants:
                                for variant in image_upload.variants:
                                    try:
                                        await self.storage.delete_file(variant.storage_key)
                                    except Exception as e:
                                        logger.warning(f"Failed to delete variant: {str(e)}")

                        # Hard delete from database
                        self.db.delete(file_upload)
                        storage_freed += file_upload.size_bytes
                        cleaned_count += 1

                except Exception as e:
                    logger.error(f"Failed to delete file {file_upload.file_id}: {str(e)}")
                    errors.append({
                        "file_id": file_upload.file_id,
                        "error": str(e),
                    })

            self.db.commit()

            logger.info(f"Soft-deleted files cleaned: {cleaned_count}, storage freed: {storage_freed} bytes")

            return {
                "task": "cleanup_soft_deleted_files",
                "files_cleaned": cleaned_count,
                "storage_freed_bytes": storage_freed,
                "errors": errors,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Soft-deleted files cleanup failed: {str(e)}", exc_info=True)
            self.db.rollback()
            return {
                "task": "cleanup_soft_deleted_files",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    # ============================================================================
    # TEMPORARY FILES CLEANUP
    # ============================================================================

    async def cleanup_temporary_files(
        self,
        days_old: int = 1,
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Clean up temporary files and incomplete uploads.

        Args:
            days_old: Age threshold in days
            batch_size: Number of files to process

        Returns:
            Cleanup results
        """
        try:
            logger.info(f"Starting temporary files cleanup (older than {days_old} days)")

            threshold_date = datetime.utcnow() - timedelta(days=days_old)

            # Find incomplete uploads
            incomplete_uploads = (
                self.db.query(self.file_repo.model)
                .filter(
                    self.file_repo.model.processing_status.in_(["pending", "processing"]),
                    self.file_repo.model.created_at < threshold_date,
                    self.file_repo.model.deleted_at.is_(None),
                )
                .limit(batch_size)
                .all()
            )

            cleaned_count = 0
            errors = []

            for file_upload in incomplete_uploads:
                try:
                    # Delete from storage
                    await self.storage.delete_file(file_upload.storage_key)

                    # Soft delete
                    file_upload.deleted_at = datetime.utcnow()
                    file_upload.processing_status = "failed"
                    file_upload.processing_error = "Cleanup: Incomplete upload timeout"

                    cleaned_count += 1

                except Exception as e:
                    logger.error(f"Failed to cleanup temp file {file_upload.file_id}: {str(e)}")
                    errors.append({
                        "file_id": file_upload.file_id,
                        "error": str(e),
                    })

            self.db.commit()

            logger.info(f"Temporary files cleaned: {cleaned_count}")

            return {
                "task": "cleanup_temporary_files",
                "files_cleaned": cleaned_count,
                "errors": errors,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Temporary files cleanup failed: {str(e)}", exc_info=True)
            self.db.rollback()
            return {
                "task": "cleanup_temporary_files",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    # ============================================================================
    # ACCESS LOGS ARCHIVAL
    # ============================================================================

    async def archive_old_access_logs(
        self,
        days_old: int = 365,
        batch_size: int = 1000,
    ) -> Dict[str, Any]:
        """
        Archive old access logs to reduce database size.

        Args:
            days_old: Age threshold in days
            batch_size: Number of logs to archive

        Returns:
            Archival results
        """
        try:
            logger.info(f"Starting access logs archival (older than {days_old} days)")

            archived_count = await self.aggregate_repo.archive_old_access_logs(
                days_old=days_old,
                batch_size=batch_size,
            )

            logger.info(f"Access logs archived: {archived_count}")

            return {
                "task": "archive_access_logs",
                "logs_archived": archived_count,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Access logs archival failed: {str(e)}", exc_info=True)
            return {
                "task": "archive_access_logs",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    # ============================================================================
    # EXPIRED ACCESS CLEANUP
    # ============================================================================

    async def cleanup_expired_access(
        self,
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Mark expired file access records.

        Args:
            batch_size: Number of records to process

        Returns:
            Cleanup results
        """
        try:
            logger.info("Starting expired access cleanup")

            marked_count = await self.metadata_repo.cleanup_expired_access(
                batch_size=batch_size
            )

            logger.info(f"Expired access records marked: {marked_count}")

            return {
                "task": "cleanup_expired_access",
                "records_marked": marked_count,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Expired access cleanup failed: {str(e)}", exc_info=True)
            return {
                "task": "cleanup_expired_access",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    # ============================================================================
    # UNUSED FILES CLEANUP
    # ============================================================================

    async def cleanup_unused_files(
        self,
        days_unused: int = 180,
        notify_owners: bool = True,
        auto_delete: bool = False,
        batch_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Identify and optionally delete unused files.

        Args:
            days_unused: Days of inactivity threshold
            notify_owners: Whether to notify file owners
            auto_delete: Whether to automatically delete
            batch_size: Number of files to process

        Returns:
            Cleanup results
        """
        try:
            logger.info(f"Starting unused files cleanup (unused for {days_unused} days)")

            # Find unused files
            unused_files = await self.file_repo.find_unused_files(
                days_unused=days_unused,
                limit=batch_size,
            )

            notified_count = 0
            deleted_count = 0
            storage_freed = 0

            for file_upload in unused_files:
                try:
                    if notify_owners:
                        # TODO: Send notification to file owner
                        # await self.notification_service.send_unused_file_notification(...)
                        notified_count += 1

                    if auto_delete:
                        # Soft delete
                        file_upload.deleted_at = datetime.utcnow()
                        storage_freed += file_upload.size_bytes
                        deleted_count += 1

                except Exception as e:
                    logger.error(f"Failed to process unused file {file_upload.file_id}: {str(e)}")

            self.db.commit()

            logger.info(f"Unused files processed: {len(unused_files)}, deleted: {deleted_count}")

            return {
                "task": "cleanup_unused_files",
                "files_identified": len(unused_files),
                "owners_notified": notified_count,
                "files_deleted": deleted_count,
                "storage_freed_bytes": storage_freed,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Unused files cleanup failed: {str(e)}", exc_info=True)
            self.db.rollback()
            return {
                "task": "cleanup_unused_files",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    # ============================================================================
    # FAILED PROCESSING CLEANUP
    # ============================================================================

    async def cleanup_failed_processing(
        self,
        days_old: int = 7,
        retry_failed: bool = False,
        batch_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Clean up files with failed processing.

        Args:
            days_old: Age threshold for failed items
            retry_failed: Whether to retry failed processing
            batch_size: Number of files to process

        Returns:
            Cleanup results
        """
        try:
            logger.info("Starting failed processing cleanup")

            threshold_date = datetime.utcnow() - timedelta(days=days_old)

            # Find files with failed processing
            failed_files = (
                self.db.query(self.file_repo.model)
                .filter(
                    self.file_repo.model.processing_status == "failed",
                    self.file_repo.model.processing_completed_at < threshold_date,
                    self.file_repo.model.deleted_at.is_(None),
                )
                .limit(batch_size)
                .all()
            )

            retried_count = 0
            deleted_count = 0

            for file_upload in failed_files:
                try:
                    if retry_failed:
                        # Reset processing status for retry
                        file_upload.processing_status = "pending"
                        file_upload.processing_error = None
                        file_upload.processing_started_at = None
                        file_upload.processing_completed_at = None
                        retried_count += 1
                    else:
                        # Soft delete
                        file_upload.deleted_at = datetime.utcnow()
                        deleted_count += 1

                except Exception as e:
                    logger.error(f"Failed to process failed file {file_upload.file_id}: {str(e)}")

            self.db.commit()

            logger.info(f"Failed processing cleanup: retried={retried_count}, deleted={deleted_count}")

            return {
                "task": "cleanup_failed_processing",
                "files_processed": len(failed_files),
                "files_retried": retried_count,
                "files_deleted": deleted_count,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed processing cleanup failed: {str(e)}", exc_info=True)
            self.db.rollback()
            return {
                "task": "cleanup_failed_processing",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    # ============================================================================
    # STORAGE OPTIMIZATION
    # ============================================================================

    async def optimize_storage(
        self,
        batch_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Identify and optimize storage usage.

        Args:
            batch_size: Number of files to process

        Returns:
            Optimization results
        """
        try:
            logger.info("Starting storage optimization")

            # Find large unoptimized images
            opportunities = await self.aggregate_repo.identify_optimization_opportunities(
                limit=batch_size
            )

            # Queue images for optimization
            queued_for_optimization = 0
            
            large_images = opportunities.get("large_unoptimized_images", {}).get("files", [])
            for image_info in large_images:
                try:
                    # Find image upload
                    file_upload = await self.file_repo.find_by_file_id(image_info["file_id"])
                    if file_upload and hasattr(file_upload, 'image_upload'):
                        image = file_upload.image_upload
                        if image and not image.optimization_completed:
                            # Queue for optimization
                            await self.image_repo.queue_for_processing(
                                image_id=image.id,
                                priority=3,
                            )
                            queued_for_optimization += 1

                except Exception as e:
                    logger.error(f"Failed to queue image for optimization: {str(e)}")

            logger.info(f"Storage optimization: queued {queued_for_optimization} images")

            return {
                "task": "optimize_storage",
                "optimization_opportunities": opportunities,
                "queued_for_optimization": queued_for_optimization,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Storage optimization failed: {str(e)}", exc_info=True)
            return {
                "task": "optimize_storage",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    # ============================================================================
    # QUOTA RECALCULATION
    # ============================================================================

    async def recalculate_quotas(
        self,
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Recalculate storage quotas for accuracy.

        Args:
            batch_size: Number of quotas to recalculate

        Returns:
            Recalculation results
        """
        try:
            logger.info("Starting quota recalculation")

            from app.models.file_management.file_upload import FileQuota

            # Get quotas to recalculate
            quotas = (
                self.db.query(FileQuota)
                .order_by(FileQuota.last_usage_update_at.asc())
                .limit(batch_size)
                .all()
            )

            recalculated_count = 0

            for quota in quotas:
                try:
                    # Calculate actual usage
                    actual_usage = (
                        self.db.query(func.sum(self.file_repo.model.size_bytes))
                        .filter(
                            self.file_repo.model.uploaded_by_user_id == quota.owner_id,
                            self.file_repo.model.deleted_at.is_(None),
                        )
                        .scalar() or 0
                    )

                    # Count files
                    file_count = (
                        self.db.query(func.count(self.file_repo.model.id))
                        .filter(
                            self.file_repo.model.uploaded_by_user_id == quota.owner_id,
                            self.file_repo.model.deleted_at.is_(None),
                        )
                        .scalar() or 0
                    )

                    # Update quota
                    quota.used_bytes = actual_usage
                    quota.current_file_count = file_count
                    quota.last_usage_update_at = datetime.utcnow()
                    quota.is_exceeded = (quota.used_bytes + quota.reserved_bytes) > quota.quota_bytes

                    recalculated_count += 1

                except Exception as e:
                    logger.error(f"Failed to recalculate quota for {quota.owner_id}: {str(e)}")

            self.db.commit()

            logger.info(f"Quotas recalculated: {recalculated_count}")

            return {
                "task": "recalculate_quotas",
                "quotas_recalculated": recalculated_count,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Quota recalculation failed: {str(e)}", exc_info=True)
            self.db.rollback()
            return {
                "task": "recalculate_quotas",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    # ============================================================================
    # COMPREHENSIVE CLEANUP
    # ============================================================================

    async def run_all_cleanup_tasks(
        self,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run all cleanup tasks in sequence.

        Args:
            config: Optional configuration for cleanup tasks

        Returns:
            Combined results from all tasks
        """
        logger.info("Starting comprehensive cleanup tasks")

        config = config or {}
        results = {
            "started_at": datetime.utcnow().isoformat(),
            "tasks": {},
        }

        # 1. Cleanup expired sessions
        results["tasks"]["expired_sessions"] = await self.cleanup_expired_upload_sessions(
            batch_size=config.get("session_batch_size", 100)
        )

        # 2. Cleanup orphaned records
        results["tasks"]["orphaned_records"] = await self.cleanup_orphaned_records(
            batch_size=config.get("orphan_batch_size", 100)
        )

        # 3. Cleanup soft-deleted files
        results["tasks"]["soft_deleted"] = await self.cleanup_soft_deleted_files(
            days_old=config.get("soft_delete_days", 30),
            batch_size=config.get("soft_delete_batch_size", 50),
        )

        # 4. Cleanup temporary files
        results["tasks"]["temporary_files"] = await self.cleanup_temporary_files(
            days_old=config.get("temp_days", 1),
            batch_size=config.get("temp_batch_size", 100),
        )

        # 5. Cleanup expired access
        results["tasks"]["expired_access"] = await self.cleanup_expired_access(
            batch_size=config.get("access_batch_size", 100)
        )

        # 6. Archive old logs
        if config.get("archive_logs", True):
            results["tasks"]["archive_logs"] = await self.archive_old_access_logs(
                days_old=config.get("log_archive_days", 365),
                batch_size=config.get("log_batch_size", 1000),
            )

        # 7. Recalculate quotas
        results["tasks"]["quota_recalculation"] = await self.recalculate_quotas(
            batch_size=config.get("quota_batch_size", 100)
        )

        # 8. Storage optimization
        if config.get("optimize_storage", False):
            results["tasks"]["storage_optimization"] = await self.optimize_storage(
                batch_size=config.get("optimize_batch_size", 50)
            )

        results["completed_at"] = datetime.utcnow().isoformat()
        
        # Calculate summary
        total_errors = sum(
            1 for task in results["tasks"].values()
            if task.get("status") == "failed"
        )
        
        results["summary"] = {
            "total_tasks": len(results["tasks"]),
            "successful_tasks": len(results["tasks"]) - total_errors,
            "failed_tasks": total_errors,
            "overall_status": "completed" if total_errors == 0 else "completed_with_errors",
        }

        logger.info(f"Comprehensive cleanup completed: {results['summary']}")

        return results

    # ============================================================================
    # HEALTH CHECK
    # ============================================================================

    async def get_cleanup_health_status(self) -> Dict[str, Any]:
        """
        Get health status of cleanup operations.

        Returns:
            Health status information
        """
        try:
            from app.models.file_management.file_upload import UploadSession
            from sqlalchemy import func

            # Count items needing cleanup
            expired_sessions = (
                self.db.query(func.count(UploadSession.id))
                .filter(
                    UploadSession.expires_at < datetime.utcnow(),
                    UploadSession.status.in_(["initialized", "uploading"]),
                )
                .scalar() or 0
            )

            soft_deleted_files = (
                self.db.query(func.count(self.file_repo.model.id))
                .filter(
                    self.file_repo.model.deleted_at.isnot(None),
                    self.file_repo.model.deleted_at < datetime.utcnow() - timedelta(days=30),
                )
                .scalar() or 0
            )

            failed_processing = (
                self.db.query(func.count(self.file_repo.model.id))
                .filter(
                    self.file_repo.model.processing_status == "failed",
                    self.file_repo.model.deleted_at.is_(None),
                )
                .scalar() or 0
            )

            # Determine health status
            issues = []
            if expired_sessions > 100:
                issues.append(f"{expired_sessions} expired sessions need cleanup")
            if soft_deleted_files > 500:
                issues.append(f"{soft_deleted_files} soft-deleted files pending permanent deletion")
            if failed_processing > 50:
                issues.append(f"{failed_processing} files with failed processing")

            health_status = "healthy" if len(issues) == 0 else "needs_attention"

            return {
                "status": health_status,
                "checks": {
                    "expired_sessions": expired_sessions,
                    "soft_deleted_files": soft_deleted_files,
                    "failed_processing": failed_processing,
                },
                "issues": issues,
                "last_checked": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Health check failed: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "last_checked": datetime.utcnow().isoformat(),
            }