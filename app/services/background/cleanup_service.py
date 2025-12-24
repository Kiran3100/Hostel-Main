"""
Background cleanup service.

Performs periodic cleanup of expired/obsolete data:
- OTP tokens
- User sessions
- Blacklisted tokens (past retention)
- Temporary/incomplete uploads
- Stale queues/batches
- Old audit logs (per retention policy)

Performance improvements:
- Batch processing with configurable limits
- Parallel task execution support
- Detailed metrics collection
- Graceful error handling per task
- Transaction optimization
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult
from app.services.base.service_result import ServiceError, ErrorCode, ErrorSeverity
from app.repositories.auth import (
    OTPTokenRepository,
    UserSessionRepository,
    BlacklistedTokenRepository,
)
from app.repositories.file_management import FileUploadRepository
from app.repositories.announcement import (
    AnnouncementSchedulingRepository,
    AnnouncementDeliveryRepository,
)
from app.repositories.audit import AuditLogRepository
from app.models.auth.otp_token import OTPToken
from app.core.logging import get_logger


class CleanupTask(str, Enum):
    """Enumeration of available cleanup tasks."""
    OTP_TOKENS = "otp_tokens"
    USER_SESSIONS = "user_sessions"
    BLACKLISTED_TOKENS = "blacklisted_tokens"
    TEMP_UPLOADS = "temp_uploads"
    STALE_QUEUES = "stale_queues"
    AUDIT_LOGS = "audit_logs"


@dataclass
class CleanupConfig:
    """Configuration for cleanup operations."""
    blacklist_retention_days: int = 90
    temp_upload_retention_hours: int = 24
    stale_queue_retention_days: int = 7
    audit_log_retention_days: int = 365
    batch_size: int = 1000
    enable_parallel: bool = False
    max_workers: int = 3


@dataclass
class CleanupResult:
    """Result of a single cleanup task."""
    task: CleanupTask
    count: int
    success: bool
    duration_ms: float
    error: Optional[str] = None


class CleanupService(BaseService[OTPToken, OTPTokenRepository]):
    """
    Orchestrates cleanup tasks by delegating to specialized repositories.
    
    Features:
    - Individual and batch cleanup execution
    - Configurable retention policies
    - Performance metrics tracking
    - Optional parallel execution
    - Comprehensive error handling
    """

    def __init__(
        self,
        otp_repo: OTPTokenRepository,
        session_repo: UserSessionRepository,
        blacklist_repo: BlacklistedTokenRepository,
        file_upload_repo: FileUploadRepository,
        ann_sched_repo: AnnouncementSchedulingRepository,
        ann_delivery_repo: AnnouncementDeliveryRepository,
        audit_repo: AuditLogRepository,
        db_session: Session,
        config: Optional[CleanupConfig] = None,
    ):
        super().__init__(otp_repo, db_session)
        self.otp_repo = otp_repo
        self.session_repo = session_repo
        self.blacklist_repo = blacklist_repo
        self.file_upload_repo = file_upload_repo
        self.ann_sched_repo = ann_sched_repo
        self.ann_delivery_repo = ann_delivery_repo
        self.audit_repo = audit_repo
        self.config = config or CleanupConfig()
        self._logger = get_logger(self.__class__.__name__)

    def run_daily_cleanup(
        self,
        tasks: Optional[List[CleanupTask]] = None,
        parallel: Optional[bool] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Execute daily cleanup tasks with enhanced metrics and error handling.
        
        Args:
            tasks: Specific tasks to run (all tasks if None)
            parallel: Override config parallel setting
            
        Returns:
            ServiceResult with detailed cleanup metrics
        """
        start_time = datetime.utcnow()
        use_parallel = parallel if parallel is not None else self.config.enable_parallel
        
        # Default to all tasks if none specified
        if tasks is None:
            tasks = list(CleanupTask)
        
        try:
            if use_parallel and len(tasks) > 1:
                cleanup_results = self._run_parallel_cleanup(tasks)
            else:
                cleanup_results = self._run_sequential_cleanup(tasks)
            
            # Aggregate results
            total_cleaned = sum(r.count for r in cleanup_results if r.success)
            failed_tasks = [r.task.value for r in cleanup_results if not r.success]
            
            # Commit if all tasks succeeded
            if not failed_tasks:
                self.db.commit()
                self._logger.info(
                    f"Daily cleanup completed successfully. "
                    f"Total items cleaned: {total_cleaned}"
                )
            else:
                self.db.rollback()
                self._logger.warning(
                    f"Daily cleanup completed with failures: {failed_tasks}"
                )
            
            # Build detailed response
            duration = (datetime.utcnow() - start_time).total_seconds()
            response = {
                "total_cleaned": total_cleaned,
                "duration_seconds": round(duration, 2),
                "tasks_executed": len(cleanup_results),
                "tasks_succeeded": len([r for r in cleanup_results if r.success]),
                "tasks_failed": len(failed_tasks),
                "failed_tasks": failed_tasks,
                "details": {
                    r.task.value: {
                        "count": r.count,
                        "success": r.success,
                        "duration_ms": round(r.duration_ms, 2),
                        "error": r.error,
                    }
                    for r in cleanup_results
                },
            }
            
            if failed_tasks:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message=f"Cleanup completed with {len(failed_tasks)} failed task(s)",
                        severity=ErrorSeverity.WARNING,
                        details={"failed_tasks": failed_tasks},
                    ),
                    data=response,
                )
            
            return ServiceResult.success(
                response,
                message=f"Daily cleanup completed: {total_cleaned} items cleaned"
            )
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Critical error in daily cleanup: {str(e)}", exc_info=True)
            return self._handle_exception(e, "daily cleanup")

    def _run_sequential_cleanup(self, tasks: List[CleanupTask]) -> List[CleanupResult]:
        """Execute cleanup tasks sequentially."""
        results = []
        
        for task in tasks:
            result = self._execute_cleanup_task(task)
            results.append(result)
            
            # Log individual task result
            if result.success:
                self._logger.debug(
                    f"Cleanup task {task.value} completed: "
                    f"{result.count} items in {result.duration_ms:.2f}ms"
                )
            else:
                self._logger.error(
                    f"Cleanup task {task.value} failed: {result.error}"
                )
        
        return results

    def _run_parallel_cleanup(self, tasks: List[CleanupTask]) -> List[CleanupResult]:
        """Execute cleanup tasks in parallel using thread pool."""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_task = {
                executor.submit(self._execute_cleanup_task, task): task
                for task in tasks
            }
            
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result.success:
                        self._logger.debug(
                            f"Parallel cleanup task {task.value} completed: "
                            f"{result.count} items"
                        )
                    else:
                        self._logger.error(
                            f"Parallel cleanup task {task.value} failed: {result.error}"
                        )
                except Exception as e:
                    self._logger.error(
                        f"Exception in parallel cleanup task {task.value}: {str(e)}",
                        exc_info=True
                    )
                    results.append(CleanupResult(
                        task=task,
                        count=0,
                        success=False,
                        duration_ms=0.0,
                        error=str(e),
                    ))
        
        return results

    def _execute_cleanup_task(self, task: CleanupTask) -> CleanupResult:
        """Execute a single cleanup task and return its result."""
        start_time = datetime.utcnow()
        
        try:
            # Map task to method
            task_map = {
                CleanupTask.OTP_TOKENS: self.cleanup_otps,
                CleanupTask.USER_SESSIONS: self.cleanup_sessions,
                CleanupTask.BLACKLISTED_TOKENS: lambda: self.cleanup_blacklist(
                    self.config.blacklist_retention_days
                ),
                CleanupTask.TEMP_UPLOADS: lambda: self.cleanup_temp_uploads(
                    self.config.temp_upload_retention_hours
                ),
                CleanupTask.STALE_QUEUES: lambda: self.cleanup_queues(
                    self.config.stale_queue_retention_days
                ),
                CleanupTask.AUDIT_LOGS: lambda: self.cleanup_audit_logs(
                    self.config.audit_log_retention_days
                ),
            }
            
            cleanup_method = task_map.get(task)
            if not cleanup_method:
                raise ValueError(f"Unknown cleanup task: {task}")
            
            result = cleanup_method()
            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            if result.success:
                return CleanupResult(
                    task=task,
                    count=result.data or 0,
                    success=True,
                    duration_ms=duration,
                )
            else:
                return CleanupResult(
                    task=task,
                    count=0,
                    success=False,
                    duration_ms=duration,
                    error=result.error.message if result.error else "Unknown error",
                )
                
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            error_msg = f"{type(e).__name__}: {str(e)}"
            self._logger.error(f"Error executing cleanup task {task.value}: {error_msg}")
            
            return CleanupResult(
                task=task,
                count=0,
                success=False,
                duration_ms=duration,
                error=error_msg,
            )

    # ---------------------------------------------------------------------
    # Individual cleanup tasks
    # ---------------------------------------------------------------------

    def cleanup_otps(self) -> ServiceResult[int]:
        """
        Purge expired OTP tokens.
        
        Returns:
            ServiceResult with count of purged tokens
        """
        try:
            count = self.otp_repo.purge_expired()
            self.db.flush()
            
            self._logger.info(f"Purged {count} expired OTP tokens")
            return ServiceResult.success(
                count,
                message=f"Purged {count} expired OTP tokens"
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error purging OTPs: {str(e)}")
            return self._handle_exception(e, "cleanup OTPs")
        except Exception as e:
            return self._handle_exception(e, "cleanup OTPs")

    def cleanup_sessions(self) -> ServiceResult[int]:
        """
        Purge expired user sessions.
        
        Returns:
            ServiceResult with count of purged sessions
        """
        try:
            count = self.session_repo.purge_expired()
            self.db.flush()
            
            self._logger.info(f"Purged {count} expired user sessions")
            return ServiceResult.success(
                count,
                message=f"Purged {count} expired sessions"
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error purging sessions: {str(e)}")
            return self._handle_exception(e, "cleanup sessions")
        except Exception as e:
            return self._handle_exception(e, "cleanup sessions")

    def cleanup_blacklist(self, retention_days: int = 90) -> ServiceResult[int]:
        """
        Purge old blacklisted tokens beyond retention period.
        
        Args:
            retention_days: Number of days to retain blacklisted tokens
            
        Returns:
            ServiceResult with count of purged tokens
        """
        try:
            if retention_days < 1:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Retention days must be at least 1",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            before = datetime.utcnow() - timedelta(days=retention_days)
            count = self.blacklist_repo.purge_before(before)
            self.db.flush()
            
            self._logger.info(
                f"Purged {count} blacklisted tokens older than {retention_days} days"
            )
            return ServiceResult.success(
                count,
                message=f"Purged {count} old blacklisted tokens"
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error purging blacklist: {str(e)}")
            return self._handle_exception(e, "cleanup blacklisted tokens")
        except Exception as e:
            return self._handle_exception(e, "cleanup blacklisted tokens")

    def cleanup_temp_uploads(self, older_than_hours: int = 24) -> ServiceResult[int]:
        """
        Remove incomplete or temporary file uploads.
        
        Args:
            older_than_hours: Remove uploads older than this many hours
            
        Returns:
            ServiceResult with count of removed uploads
        """
        try:
            if older_than_hours < 1:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Retention hours must be at least 1",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            before = datetime.utcnow() - timedelta(hours=older_than_hours)
            count = self.file_upload_repo.cleanup_incomplete_before(before)
            self.db.flush()
            
            self._logger.info(
                f"Cleaned {count} temporary uploads older than {older_than_hours} hours"
            )
            return ServiceResult.success(
                count,
                message=f"Cleaned {count} temporary uploads"
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error cleaning temp uploads: {str(e)}")
            return self._handle_exception(e, "cleanup temporary uploads")
        except Exception as e:
            return self._handle_exception(e, "cleanup temporary uploads")

    def cleanup_queues(self, older_than_days: int = 7) -> ServiceResult[int]:
        """
        Clean stale announcement scheduling and delivery queues.
        
        Args:
            older_than_days: Remove queue items older than this many days
            
        Returns:
            ServiceResult with total count of cleaned queue items
        """
        try:
            if older_than_days < 1:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Retention days must be at least 1",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            before = datetime.utcnow() - timedelta(days=older_than_days)
            
            sched_count = self.ann_sched_repo.cleanup_stale(before) or 0
            delivery_count = self.ann_delivery_repo.cleanup_stale(before) or 0
            total_count = sched_count + delivery_count
            
            self.db.flush()
            
            self._logger.info(
                f"Cleaned {total_count} stale queue items "
                f"(scheduling: {sched_count}, delivery: {delivery_count})"
            )
            return ServiceResult.success(
                total_count,
                message=f"Cleaned {total_count} stale queue items"
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error cleaning queues: {str(e)}")
            return self._handle_exception(e, "cleanup queues")
        except Exception as e:
            return self._handle_exception(e, "cleanup queues")

    def cleanup_audit_logs(self, retention_days: int = 365) -> ServiceResult[int]:
        """
        Purge old audit logs according to retention policy.
        
        Args:
            retention_days: Number of days to retain audit logs
            
        Returns:
            ServiceResult with count of purged logs
        """
        try:
            if retention_days < 30:
                self._logger.warning(
                    f"Audit log retention of {retention_days} days is below "
                    f"recommended minimum of 30 days"
                )
            
            before = datetime.utcnow() - timedelta(days=retention_days)
            count = self.audit_repo.purge_before(before)
            self.db.flush()
            
            self._logger.info(
                f"Purged {count} audit logs older than {retention_days} days"
            )
            return ServiceResult.success(
                count,
                message=f"Purged {count} old audit logs"
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error purging audit logs: {str(e)}")
            return self._handle_exception(e, "cleanup audit logs")
        except Exception as e:
            return self._handle_exception(e, "cleanup audit logs")

    def get_cleanup_stats(self) -> ServiceResult[Dict[str, Any]]:
        """
        Get statistics about data eligible for cleanup without performing cleanup.
        
        Returns:
            ServiceResult with cleanup statistics
        """
        try:
            stats = {
                "expired_otps": self.otp_repo.count_expired(),
                "expired_sessions": self.session_repo.count_expired(),
                "old_blacklisted_tokens": self.blacklist_repo.count_before(
                    datetime.utcnow() - timedelta(days=self.config.blacklist_retention_days)
                ),
                "temp_uploads": self.file_upload_repo.count_incomplete_before(
                    datetime.utcnow() - timedelta(hours=self.config.temp_upload_retention_hours)
                ),
                "stale_queue_items": (
                    self.ann_sched_repo.count_stale(
                        datetime.utcnow() - timedelta(days=self.config.stale_queue_retention_days)
                    ) or 0
                ) + (
                    self.ann_delivery_repo.count_stale(
                        datetime.utcnow() - timedelta(days=self.config.stale_queue_retention_days)
                    ) or 0
                ),
                "old_audit_logs": self.audit_repo.count_before(
                    datetime.utcnow() - timedelta(days=self.config.audit_log_retention_days)
                ),
            }
            
            stats["total_eligible"] = sum(stats.values())
            
            return ServiceResult.success(
                stats,
                message="Cleanup statistics retrieved"
            )
            
        except Exception as e:
            return self._handle_exception(e, "get cleanup stats")