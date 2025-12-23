"""
Third-party sync service: pull, push, reconcile (generic).

Provides generic synchronization capabilities for third-party integrations
with support for bidirectional sync, conflict resolution, and reconciliation.
"""

from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta
from uuid import UUID
import logging
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService, ServiceResult, ServiceError, 
    ErrorCode, ErrorSeverity
)
from app.repositories.integrations import (
    ThirdPartyRepository, 
    IntegrationAggregateRepository
)
from app.models.integrations.api_integration import APIIntegration

logger = logging.getLogger(__name__)


class SyncDirection(str, Enum):
    """Sync direction enumeration."""
    PULL = "pull"
    PUSH = "push"
    BIDIRECTIONAL = "bidirectional"


class ConflictResolution(str, Enum):
    """Conflict resolution strategy enumeration."""
    LOCAL_WINS = "local_wins"
    REMOTE_WINS = "remote_wins"
    LATEST_WINS = "latest_wins"
    MANUAL = "manual"


class ThirdPartySyncService(BaseService[APIIntegration, ThirdPartyRepository]):
    """
    Sync flows for third-party providers (non-payment).
    
    Features:
    - Pull updates from remote providers
    - Push local changes to providers
    - Bidirectional synchronization
    - Conflict detection and resolution
    - Reconciliation and drift detection
    - Incremental sync support
    """

    def __init__(
        self,
        repository: ThirdPartyRepository,
        aggregate_repo: IntegrationAggregateRepository,
        db_session: Session,
        default_sync_interval: int = 30,
        max_sync_batch_size: int = 500,
    ):
        """
        Initialize third-party sync service.
        
        Args:
            repository: Third-party repository instance
            aggregate_repo: Aggregate repository for analytics
            db_session: SQLAlchemy database session
            default_sync_interval: Default sync interval in minutes
            max_sync_batch_size: Maximum items per sync batch
        """
        super().__init__(repository, db_session)
        self.aggregate_repo = aggregate_repo
        self._default_sync_interval = default_sync_interval
        self._max_sync_batch_size = max_sync_batch_size
        self._active_syncs: Set[str] = set()  # Track active sync operations
        self._sync_locks: Dict[str, datetime] = {}  # Sync lock timestamps
        
        logger.info("ThirdPartySyncService initialized")

    def _validate_sync_params(
        self,
        provider: str,
        limit: int,
    ) -> ServiceResult[bool]:
        """
        Validate sync operation parameters.
        
        Args:
            provider: Provider identifier
            limit: Batch size limit
            
        Returns:
            ServiceResult indicating validation success
        """
        if not provider or not isinstance(provider, str):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Provider must be a non-empty string",
                    severity=ErrorSeverity.MEDIUM
                )
            )
        
        if limit <= 0 or limit > self._max_sync_batch_size:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Limit must be between 1 and {self._max_sync_batch_size}",
                    severity=ErrorSeverity.MEDIUM,
                    context={
                        "limit": limit,
                        "max_limit": self._max_sync_batch_size
                    }
                )
            )
        
        return ServiceResult.success(True)

    def _acquire_sync_lock(
        self, 
        provider: str, 
        direction: SyncDirection,
        timeout_minutes: int = 15
    ) -> ServiceResult[bool]:
        """
        Acquire lock for sync operation to prevent concurrent syncs.
        
        Args:
            provider: Provider identifier
            direction: Sync direction
            timeout_minutes: Lock timeout in minutes
            
        Returns:
            ServiceResult indicating lock acquisition success
        """
        lock_key = f"{provider}:{direction.value}"
        
        # Check if already locked
        if lock_key in self._sync_locks:
            lock_time = self._sync_locks[lock_key]
            age = (datetime.utcnow() - lock_time).total_seconds() / 60
            
            # Check if lock is stale
            if age < timeout_minutes:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.CONFLICT,
                        message=f"Sync already in progress for {provider}",
                        severity=ErrorSeverity.MEDIUM,
                        context={
                            "provider": provider,
                            "direction": direction.value,
                            "lock_age_minutes": round(age, 2),
                            "lock_expires_in": timeout_minutes - age
                        }
                    )
                )
            else:
                # Release stale lock
                logger.warning(
                    f"Releasing stale sync lock for {provider}",
                    extra={
                        "provider": provider,
                        "direction": direction.value,
                        "lock_age_minutes": round(age, 2)
                    }
                )
                del self._sync_locks[lock_key]
        
        # Acquire lock
        self._sync_locks[lock_key] = datetime.utcnow()
        self._active_syncs.add(lock_key)
        
        logger.debug(
            f"Acquired sync lock for {provider} ({direction.value})",
            extra={"provider": provider, "direction": direction.value}
        )
        
        return ServiceResult.success(True)

    def _release_sync_lock(
        self, 
        provider: str, 
        direction: SyncDirection
    ) -> None:
        """
        Release sync lock.
        
        Args:
            provider: Provider identifier
            direction: Sync direction
        """
        lock_key = f"{provider}:{direction.value}"
        
        if lock_key in self._sync_locks:
            del self._sync_locks[lock_key]
        
        self._active_syncs.discard(lock_key)
        
        logger.debug(
            f"Released sync lock for {provider} ({direction.value})",
            extra={"provider": provider, "direction": direction.value}
        )

    def pull(
        self,
        provider: str,
        since_minutes: Optional[int] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 500,
        incremental: bool = True,
        resource_types: Optional[List[str]] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Pull updates from third-party provider.
        
        Retrieves data from the provider and stores it locally,
        with support for incremental sync and filtering.
        
        Args:
            provider: Provider identifier
            since_minutes: Pull data from last N minutes (overrides since)
            since: Start datetime for data retrieval
            until: End datetime for data retrieval
            limit: Maximum number of items to retrieve
            incremental: Use incremental sync if available
            resource_types: List of resource types to sync (None for all)
            
        Returns:
            ServiceResult containing sync summary
        """
        logger.info(
            f"Pulling updates from provider: {provider}",
            extra={
                "provider": provider,
                "incremental": incremental,
                "limit": limit
            }
        )
        
        # Validate parameters
        validation = self._validate_sync_params(provider, limit)
        if not validation.success:
            return validation
        
        # Acquire sync lock
        lock_result = self._acquire_sync_lock(provider, SyncDirection.PULL)
        if not lock_result.success:
            return lock_result

        try:
            # Determine time range
            if since_minutes is not None:
                since = datetime.utcnow() - timedelta(minutes=since_minutes)
            elif since is None and incremental:
                # Get last successful sync time
                last_sync = self.repository.get_last_sync_time(
                    provider, 
                    direction=SyncDirection.PULL.value
                )
                since = last_sync or (
                    datetime.utcnow() - timedelta(minutes=self._default_sync_interval)
                )
            elif since is None:
                since = datetime.utcnow() - timedelta(minutes=self._default_sync_interval)
            
            if until is None:
                until = datetime.utcnow()
            
            # Validate time range
            if since >= until:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Start time must be before end time",
                        severity=ErrorSeverity.MEDIUM,
                        context={
                            "since": since.isoformat(),
                            "until": until.isoformat()
                        }
                    )
                )
            
            sync_start = datetime.utcnow()
            
            # Execute pull operation
            result = self.repository.pull(
                provider=provider,
                since=since,
                until=until,
                limit=limit,
                resource_types=resource_types
            )
            
            sync_duration = (datetime.utcnow() - sync_start).total_seconds()
            
            # Update last sync time
            self.repository.update_last_sync_time(
                provider=provider,
                direction=SyncDirection.PULL.value,
                timestamp=datetime.utcnow(),
                items_synced=result.get("count", 0),
                duration_seconds=sync_duration
            )
            
            # Commit transaction
            self.db.commit()
            
            sync_summary = {
                "provider": provider,
                "direction": SyncDirection.PULL.value,
                "items_pulled": result.get("count", 0),
                "items_created": result.get("created", 0),
                "items_updated": result.get("updated", 0),
                "items_failed": result.get("failed", 0),
                "duration_seconds": round(sync_duration, 2),
                "time_range": {
                    "since": since.isoformat(),
                    "until": until.isoformat()
                },
                "incremental": incremental,
                "resource_types": resource_types or ["all"],
                "synced_at": datetime.utcnow().isoformat()
            }
            
            logger.info(
                f"Successfully pulled {result.get('count', 0)} items from {provider}",
                extra=sync_summary
            )
            
            return ServiceResult.success(
                sync_summary,
                message=f"Pulled {result.get('count', 0)} items from {provider}",
                metadata=sync_summary
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error during pull from {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to persist data from {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error during pull from {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "pull third-party updates", provider)
        finally:
            self._release_sync_lock(provider, SyncDirection.PULL)

    def push(
        self,
        provider: str,
        limit: int = 500,
        resource_types: Optional[List[str]] = None,
        force: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Push local changes to third-party provider.
        
        Sends pending local changes to the provider with support
        for batching and failure recovery.
        
        Args:
            provider: Provider identifier
            limit: Maximum number of items to push
            resource_types: List of resource types to sync (None for all)
            force: Force push even if no changes detected
            
        Returns:
            ServiceResult containing sync summary
        """
        logger.info(
            f"Pushing updates to provider: {provider}",
            extra={
                "provider": provider,
                "limit": limit,
                "force": force
            }
        )
        
        # Validate parameters
        validation = self._validate_sync_params(provider, limit)
        if not validation.success:
            return validation
        
        # Acquire sync lock
        lock_result = self._acquire_sync_lock(provider, SyncDirection.PUSH)
        if not lock_result.success:
            return lock_result

        try:
            sync_start = datetime.utcnow()
            
            # Execute push operation
            result = self.repository.push(
                provider=provider,
                limit=limit,
                resource_types=resource_types,
                force=force
            )
            
            sync_duration = (datetime.utcnow() - sync_start).total_seconds()
            
            # Update last sync time
            self.repository.update_last_sync_time(
                provider=provider,
                direction=SyncDirection.PUSH.value,
                timestamp=datetime.utcnow(),
                items_synced=result.get("count", 0),
                duration_seconds=sync_duration
            )
            
            # Commit transaction
            self.db.commit()
            
            sync_summary = {
                "provider": provider,
                "direction": SyncDirection.PUSH.value,
                "items_pushed": result.get("count", 0),
                "items_created": result.get("created", 0),
                "items_updated": result.get("updated", 0),
                "items_failed": result.get("failed", 0),
                "duration_seconds": round(sync_duration, 2),
                "resource_types": resource_types or ["all"],
                "forced": force,
                "synced_at": datetime.utcnow().isoformat()
            }
            
            logger.info(
                f"Successfully pushed {result.get('count', 0)} items to {provider}",
                extra=sync_summary
            )
            
            return ServiceResult.success(
                sync_summary,
                message=f"Pushed {result.get('count', 0)} items to {provider}",
                metadata=sync_summary
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error during push to {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to update sync status for {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error during push to {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "push third-party updates", provider)
        finally:
            self._release_sync_lock(provider, SyncDirection.PUSH)

    def sync_bidirectional(
        self,
        provider: str,
        conflict_resolution: ConflictResolution = ConflictResolution.REMOTE_WINS,
        limit: int = 500,
        resource_types: Optional[List[str]] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Perform bidirectional sync with conflict resolution.
        
        Args:
            provider: Provider identifier
            conflict_resolution: Strategy for resolving conflicts
            limit: Maximum items per direction
            resource_types: Resource types to sync
            
        Returns:
            ServiceResult containing bidirectional sync summary
        """
        logger.info(
            f"Starting bidirectional sync for {provider}",
            extra={
                "provider": provider,
                "conflict_resolution": conflict_resolution.value
            }
        )
        
        # Acquire sync lock
        lock_result = self._acquire_sync_lock(provider, SyncDirection.BIDIRECTIONAL)
        if not lock_result.success:
            return lock_result

        try:
            sync_start = datetime.utcnow()
            
            # Phase 1: Pull remote changes
            pull_result = self.pull(
                provider=provider,
                limit=limit,
                resource_types=resource_types,
                incremental=True
            )
            
            if not pull_result.success:
                logger.error(
                    f"Pull phase failed for {provider}",
                    extra={"provider": provider}
                )
                return pull_result
            
            # Phase 2: Resolve conflicts
            conflicts = self._detect_conflicts(provider, resource_types)
            resolved_conflicts = self._resolve_conflicts(
                provider, 
                conflicts, 
                conflict_resolution
            )
            
            # Phase 3: Push local changes
            push_result = self.push(
                provider=provider,
                limit=limit,
                resource_types=resource_types,
                force=False
            )
            
            if not push_result.success:
                logger.error(
                    f"Push phase failed for {provider}",
                    extra={"provider": provider}
                )
                return push_result
            
            sync_duration = (datetime.utcnow() - sync_start).total_seconds()
            
            # Update last sync time
            self.repository.update_last_sync_time(
                provider=provider,
                direction=SyncDirection.BIDIRECTIONAL.value,
                timestamp=datetime.utcnow(),
                items_synced=(
                    pull_result.data.get("items_pulled", 0) +
                    push_result.data.get("items_pushed", 0)
                ),
                duration_seconds=sync_duration
            )
            
            self.db.commit()
            
            sync_summary = {
                "provider": provider,
                "direction": SyncDirection.BIDIRECTIONAL.value,
                "pull_summary": pull_result.data,
                "push_summary": push_result.data,
                "conflicts_detected": len(conflicts),
                "conflicts_resolved": len(resolved_conflicts),
                "conflict_resolution_strategy": conflict_resolution.value,
                "total_duration_seconds": round(sync_duration, 2),
                "synced_at": datetime.utcnow().isoformat()
            }
            
            logger.info(
                f"Bidirectional sync completed for {provider}",
                extra=sync_summary
            )
            
            return ServiceResult.success(
                sync_summary,
                message=f"Bidirectional sync completed for {provider}",
                metadata=sync_summary
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error during bidirectional sync for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "bidirectional sync", provider)
        finally:
            self._release_sync_lock(provider, SyncDirection.BIDIRECTIONAL)

    def _detect_conflicts(
        self,
        provider: str,
        resource_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect conflicts between local and remote data.
        
        Args:
            provider: Provider identifier
            resource_types: Resource types to check
            
        Returns:
            List of detected conflicts
        """
        try:
            conflicts = self.repository.detect_conflicts(
                provider=provider,
                resource_types=resource_types
            )
            
            if conflicts:
                logger.warning(
                    f"Detected {len(conflicts)} conflicts for {provider}",
                    extra={
                        "provider": provider,
                        "conflict_count": len(conflicts)
                    }
                )
            
            return conflicts or []
            
        except Exception as e:
            logger.error(
                f"Error detecting conflicts for {provider}: {str(e)}",
                exc_info=True
            )
            return []

    def _resolve_conflicts(
        self,
        provider: str,
        conflicts: List[Dict[str, Any]],
        strategy: ConflictResolution
    ) -> List[Dict[str, Any]]:
        """
        Resolve conflicts using specified strategy.
        
        Args:
            provider: Provider identifier
            conflicts: List of conflicts to resolve
            strategy: Resolution strategy
            
        Returns:
            List of resolved conflicts
        """
        if not conflicts:
            return []
        
        logger.info(
            f"Resolving {len(conflicts)} conflicts for {provider} "
            f"using strategy: {strategy.value}",
            extra={
                "provider": provider,
                "conflict_count": len(conflicts),
                "strategy": strategy.value
            }
        )
        
        try:
            resolved = self.repository.resolve_conflicts(
                provider=provider,
                conflicts=conflicts,
                strategy=strategy.value
            )
            
            logger.info(
                f"Resolved {len(resolved)} conflicts for {provider}",
                extra={
                    "provider": provider,
                    "resolved_count": len(resolved)
                }
            )
            
            return resolved or []
            
        except Exception as e:
            logger.error(
                f"Error resolving conflicts for {provider}: {str(e)}",
                exc_info=True
            )
            return []

    def reconcile(
        self,
        provider: str,
        resource_types: Optional[List[str]] = None,
        fix_drift: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Reconcile data between local and remote systems.
        
        Performs comprehensive comparison to detect drift, missing items,
        and inconsistencies between systems.
        
        Args:
            provider: Provider identifier
            resource_types: Resource types to reconcile
            fix_drift: Automatically fix detected drift
            
        Returns:
            ServiceResult containing reconciliation report
        """
        logger.info(
            f"Starting reconciliation for {provider}",
            extra={
                "provider": provider,
                "fix_drift": fix_drift,
                "resource_types": resource_types
            }
        )

        try:
            reconcile_start = datetime.utcnow()
            
            # Execute reconciliation
            report = self.aggregate_repo.reconcile_provider(
                provider=provider,
                resource_types=resource_types,
                fix_drift=fix_drift
            )
            
            reconcile_duration = (
                datetime.utcnow() - reconcile_start
            ).total_seconds()
            
            # Enhance report
            enhanced_report = {
                **(report or {}),
                "provider": provider,
                "resource_types": resource_types or ["all"],
                "fix_drift": fix_drift,
                "duration_seconds": round(reconcile_duration, 2),
                "reconciled_at": datetime.utcnow().isoformat()
            }
            
            # Log warnings for drift
            drift_count = enhanced_report.get("drift_detected", 0)
            if drift_count > 0:
                logger.warning(
                    f"Detected {drift_count} items with drift for {provider}",
                    extra={
                        "provider": provider,
                        "drift_count": drift_count,
                        "fixed": fix_drift
                    }
                )
            
            logger.info(
                f"Reconciliation completed for {provider}",
                extra=enhanced_report
            )
            
            return ServiceResult.success(
                enhanced_report,
                message=f"Reconciliation completed for {provider}",
                metadata={
                    "provider": provider,
                    "drift_detected": drift_count,
                    "fixed": fix_drift
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error during reconciliation for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "reconcile third-party provider", provider)

    def get_sync_status(
        self,
        provider: str,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get current sync status for a provider.
        
        Args:
            provider: Provider identifier
            
        Returns:
            ServiceResult containing sync status
        """
        logger.debug(f"Retrieving sync status for {provider}")
        
        try:
            status = self.repository.get_sync_status(provider)
            
            # Add active sync information
            active_syncs = [
                key.split(":")[1] for key in self._active_syncs 
                if key.startswith(f"{provider}:")
            ]
            
            enhanced_status = {
                **(status or {}),
                "active_syncs": active_syncs,
                "is_syncing": len(active_syncs) > 0
            }
            
            return ServiceResult.success(
                enhanced_status,
                message=f"Retrieved sync status for {provider}",
                metadata={"provider": provider}
            )
            
        except Exception as e:
            logger.error(
                f"Error retrieving sync status for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get sync status", provider)

    def cancel_sync(
        self,
        provider: str,
        direction: Optional[SyncDirection] = None,
    ) -> ServiceResult[bool]:
        """
        Cancel an active sync operation.
        
        Args:
            provider: Provider identifier
            direction: Sync direction to cancel (None for all)
            
        Returns:
            ServiceResult indicating cancellation success
        """
        logger.info(
            f"Cancelling sync for {provider}",
            extra={"provider": provider, "direction": direction}
        )
        
        try:
            cancelled = False
            
            if direction:
                lock_key = f"{provider}:{direction.value}"
                if lock_key in self._sync_locks:
                    self._release_sync_lock(provider, direction)
                    cancelled = True
            else:
                # Cancel all syncs for provider
                for sync_direction in SyncDirection:
                    lock_key = f"{provider}:{sync_direction.value}"
                    if lock_key in self._sync_locks:
                        self._release_sync_lock(provider, sync_direction)
                        cancelled = True
            
            if cancelled:
                # Notify repository to cancel operation
                self.repository.cancel_sync(provider, direction.value if direction else None)
                
                logger.info(
                    f"Sync cancelled for {provider}",
                    extra={"provider": provider, "direction": direction}
                )
            else:
                logger.warning(
                    f"No active sync found for {provider}",
                    extra={"provider": provider}
                )
            
            return ServiceResult.success(
                cancelled,
                message=f"Sync {'cancelled' if cancelled else 'not active'} for {provider}",
                metadata={"provider": provider, "cancelled": cancelled}
            )
            
        except Exception as e:
            logger.error(
                f"Error cancelling sync for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "cancel sync", provider)

    def get_sync_history(
        self,
        provider: str,
        direction: Optional[SyncDirection] = None,
        limit: int = 50,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get sync history for a provider.
        
        Args:
            provider: Provider identifier
            direction: Filter by sync direction
            limit: Maximum number of history entries
            
        Returns:
            ServiceResult containing sync history
        """
        logger.debug(
            f"Retrieving sync history for {provider}",
            extra={"provider": provider, "direction": direction, "limit": limit}
        )
        
        try:
            history = self.repository.get_sync_history(
                provider=provider,
                direction=direction.value if direction else None,
                limit=limit
            )
            
            return ServiceResult.success(
                history or [],
                message=f"Retrieved {len(history or [])} history entries",
                metadata={
                    "provider": provider,
                    "count": len(history or []),
                    "direction": direction.value if direction else "all"
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error retrieving sync history for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get sync history", provider)