"""
Background data sync service.

Handles synchronization with third-party integrations:
- Pull updates (webhooks, polling)
- Push updates (outbound sync)
- Reconciliation & retry logic

Performance improvements:
- Retry mechanism with exponential backoff
- Batch processing optimization
- Detailed sync metrics
- Provider-specific error handling
- Transaction boundaries per batch
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from uuid import UUID
from dataclasses import dataclass
from enum import Enum
import time

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult
from app.services.base.service_result import ServiceError, ErrorCode, ErrorSeverity
from app.repositories.integrations import (
    ThirdPartyRepository,
    APIIntegrationRepository,
    IntegrationAggregateRepository,
)
from app.models.integrations.api_integration import APIIntegration
from app.core.logging import get_logger


class SyncDirection(str, Enum):
    """Data synchronization direction."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    BIDIRECTIONAL = "bidirectional"


class SyncStatus(str, Enum):
    """Synchronization status."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass
class SyncConfig:
    """Configuration for sync operations."""
    default_batch_size: int = 500
    max_batch_size: int = 2000
    webhook_batch_size: int = 1000
    poll_interval_minutes: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 5
    enable_reconciliation: bool = True
    reconciliation_threshold_percent: float = 5.0


@dataclass
class SyncMetrics:
    """Metrics for a sync operation."""
    provider: str
    direction: SyncDirection
    status: SyncStatus
    items_processed: int
    items_succeeded: int
    items_failed: int
    duration_seconds: float
    error_details: Optional[List[str]] = None
    started_at: datetime = None
    completed_at: datetime = None

    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.utcnow()
        if self.completed_at is None:
            self.completed_at = datetime.utcnow()


class DataSyncService(BaseService[APIIntegration, APIIntegrationRepository]):
    """
    Orchestrates third-party data synchronization tasks.
    
    Features:
    - Webhook processing with batch limits
    - Polling for updates with configurable intervals
    - Push updates with retry logic
    - Data reconciliation with drift detection
    - Comprehensive metrics tracking
    """

    def __init__(
        self,
        api_repo: APIIntegrationRepository,
        third_party_repo: ThirdPartyRepository,
        aggregate_repo: IntegrationAggregateRepository,
        db_session: Session,
        config: Optional[SyncConfig] = None,
    ):
        super().__init__(api_repo, db_session)
        self.api_repo = api_repo
        self.third_party_repo = third_party_repo
        self.aggregate_repo = aggregate_repo
        self.config = config or SyncConfig()
        self._logger = get_logger(self.__class__.__name__)

    def pull_webhooks(
        self,
        provider: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> ServiceResult[SyncMetrics]:
        """
        Process pending inbound webhooks from providers.
        
        Args:
            provider: Specific provider to process (all if None)
            batch_size: Override default batch size
            
        Returns:
            ServiceResult with sync metrics
        """
        start_time = datetime.utcnow()
        batch_limit = min(
            batch_size or self.config.webhook_batch_size,
            self.config.max_batch_size
        )
        
        try:
            count = self.third_party_repo.consume_webhooks(
                provider=provider,
                limit=batch_limit
            )
            
            self.db.commit()
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            metrics = SyncMetrics(
                provider=provider or "all",
                direction=SyncDirection.INBOUND,
                status=SyncStatus.SUCCESS,
                items_processed=count or 0,
                items_succeeded=count or 0,
                items_failed=0,
                duration_seconds=duration,
                started_at=start_time,
                completed_at=datetime.utcnow(),
            )
            
            self._logger.info(
                f"Processed {count} webhooks from {provider or 'all providers'} "
                f"in {duration:.2f}s"
            )
            
            return ServiceResult.success(
                metrics,
                message=f"Processed {count} webhooks"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error processing webhooks: {str(e)}")
            return self._create_error_result(
                provider or "all",
                SyncDirection.INBOUND,
                start_time,
                str(e)
            )
        except Exception as e:
            self.db.rollback()
            return self._handle_sync_exception(
                e,
                "pull webhooks",
                provider or "all",
                SyncDirection.INBOUND,
                start_time
            )

    def pull_updates(
        self,
        provider: str,
        since_minutes: Optional[int] = None,
        batch_size: Optional[int] = None,
    ) -> ServiceResult[SyncMetrics]:
        """
        Poll provider for updates since the last window.
        
        Args:
            provider: Provider identifier
            since_minutes: Look back window in minutes
            batch_size: Override default batch size
            
        Returns:
            ServiceResult with sync metrics
        """
        start_time = datetime.utcnow()
        lookback = since_minutes or self.config.poll_interval_minutes
        batch_limit = min(
            batch_size or self.config.default_batch_size,
            self.config.max_batch_size
        )
        
        if not provider:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Provider is required for pulling updates",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        try:
            since = datetime.utcnow() - timedelta(minutes=lookback)
            count = self.api_repo.pull_updates(provider, since, limit=batch_limit)
            
            self.db.commit()
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            metrics = SyncMetrics(
                provider=provider,
                direction=SyncDirection.INBOUND,
                status=SyncStatus.SUCCESS,
                items_processed=count or 0,
                items_succeeded=count or 0,
                items_failed=0,
                duration_seconds=duration,
                started_at=start_time,
                completed_at=datetime.utcnow(),
            )
            
            self._logger.info(
                f"Pulled {count} updates from {provider} "
                f"(last {lookback} minutes) in {duration:.2f}s"
            )
            
            return ServiceResult.success(
                metrics,
                message=f"Pulled {count} updates from {provider}"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error pulling updates from {provider}: {str(e)}")
            return self._create_error_result(provider, SyncDirection.INBOUND, start_time, str(e))
        except Exception as e:
            self.db.rollback()
            return self._handle_sync_exception(
                e,
                f"pull updates from {provider}",
                provider,
                SyncDirection.INBOUND,
                start_time
            )

    def push_updates(
        self,
        provider: str,
        limit: Optional[int] = None,
        retry_failed: bool = True,
    ) -> ServiceResult[SyncMetrics]:
        """
        Push local changes to provider with retry logic.
        
        Args:
            provider: Provider identifier
            limit: Maximum number of updates to push
            retry_failed: Whether to retry previously failed items
            
        Returns:
            ServiceResult with sync metrics
        """
        start_time = datetime.utcnow()
        batch_limit = min(
            limit or self.config.default_batch_size,
            self.config.max_batch_size
        )
        
        if not provider:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Provider is required for pushing updates",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        try:
            # Attempt push with retry logic
            count, errors = self._push_with_retry(provider, batch_limit, retry_failed)
            
            self.db.commit()
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            failed_count = len(errors) if errors else 0
            succeeded_count = count - failed_count
            
            status = SyncStatus.SUCCESS
            if failed_count > 0:
                status = SyncStatus.PARTIAL if succeeded_count > 0 else SyncStatus.FAILED
            
            metrics = SyncMetrics(
                provider=provider,
                direction=SyncDirection.OUTBOUND,
                status=status,
                items_processed=count,
                items_succeeded=succeeded_count,
                items_failed=failed_count,
                duration_seconds=duration,
                error_details=errors[:10] if errors else None,  # Limit error list
                started_at=start_time,
                completed_at=datetime.utcnow(),
            )
            
            self._logger.info(
                f"Pushed {succeeded_count}/{count} updates to {provider} "
                f"in {duration:.2f}s ({failed_count} failed)"
            )
            
            if status == SyncStatus.FAILED:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        message=f"All push updates to {provider} failed",
                        severity=ErrorSeverity.ERROR,
                        details={"errors": errors[:5]},
                    ),
                    data=metrics
                )
            
            return ServiceResult.success(
                metrics,
                message=f"Pushed {succeeded_count} updates to {provider}"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error pushing updates to {provider}: {str(e)}")
            return self._create_error_result(provider, SyncDirection.OUTBOUND, start_time, str(e))
        except Exception as e:
            self.db.rollback()
            return self._handle_sync_exception(
                e,
                f"push updates to {provider}",
                provider,
                SyncDirection.OUTBOUND,
                start_time
            )

    def _push_with_retry(
        self,
        provider: str,
        limit: int,
        retry_failed: bool
    ) -> Tuple[int, Optional[List[str]]]:
        """
        Push updates with exponential backoff retry logic.
        
        Returns:
            Tuple of (total_count, error_list)
        """
        errors = []
        attempt = 0
        
        while attempt <= self.config.max_retries:
            try:
                count = self.api_repo.push_updates(
                    provider,
                    limit=limit,
                    retry_failed=retry_failed
                )
                return count or 0, errors if errors else None
                
            except Exception as e:
                attempt += 1
                error_msg = f"Attempt {attempt}: {str(e)}"
                errors.append(error_msg)
                
                if attempt <= self.config.max_retries:
                    delay = self.config.retry_delay_seconds * (2 ** (attempt - 1))
                    self._logger.warning(
                        f"Push to {provider} failed (attempt {attempt}), "
                        f"retrying in {delay}s: {str(e)}"
                    )
                    time.sleep(delay)
                else:
                    self._logger.error(
                        f"Push to {provider} failed after {attempt} attempts"
                    )
                    raise
        
        return 0, errors

    def reconcile(
        self,
        provider: str,
        full_scan: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Run a reconciliation job between local and provider data.
        
        Args:
            provider: Provider identifier
            full_scan: Whether to perform full reconciliation (vs incremental)
            
        Returns:
            ServiceResult with reconciliation report
        """
        start_time = datetime.utcnow()
        
        if not provider:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Provider is required for reconciliation",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        if not self.config.enable_reconciliation:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.OPERATION_NOT_ALLOWED,
                    message="Reconciliation is disabled in configuration",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        try:
            report = self.aggregate_repo.reconcile_provider(provider, full_scan=full_scan)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            # Analyze reconciliation results
            total_records = report.get("total_records", 0)
            mismatches = report.get("mismatches", 0)
            missing_local = report.get("missing_local", 0)
            missing_remote = report.get("missing_remote", 0)
            
            drift_percent = (mismatches / total_records * 100) if total_records > 0 else 0
            
            # Enhance report with metadata
            enhanced_report = {
                **report,
                "provider": provider,
                "full_scan": full_scan,
                "drift_percent": round(drift_percent, 2),
                "duration_seconds": round(duration, 2),
                "reconciled_at": datetime.utcnow().isoformat(),
                "within_threshold": drift_percent <= self.config.reconciliation_threshold_percent,
            }
            
            # Log warning if drift exceeds threshold
            if drift_percent > self.config.reconciliation_threshold_percent:
                self._logger.warning(
                    f"Reconciliation drift for {provider} ({drift_percent:.2f}%) "
                    f"exceeds threshold ({self.config.reconciliation_threshold_percent}%)"
                )
            
            self._logger.info(
                f"Reconciliation for {provider} completed: "
                f"{mismatches} mismatches, {missing_local} missing local, "
                f"{missing_remote} missing remote ({duration:.2f}s)"
            )
            
            return ServiceResult.success(
                enhanced_report,
                message=f"Reconciliation completed for {provider}"
            )
            
        except Exception as e:
            self._logger.error(f"Error reconciling {provider}: {str(e)}", exc_info=True)
            return self._handle_exception(e, f"reconcile {provider}")

    def sync_all_providers(
        self,
        direction: SyncDirection = SyncDirection.BIDIRECTIONAL,
        providers: Optional[List[str]] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Execute sync for all configured providers.
        
        Args:
            direction: Sync direction (inbound, outbound, or both)
            providers: Specific providers to sync (all if None)
            
        Returns:
            ServiceResult with aggregated sync metrics
        """
        start_time = datetime.utcnow()
        
        try:
            # Get provider list
            if providers is None:
                providers = self.api_repo.get_active_providers()
            
            if not providers:
                return ServiceResult.success(
                    {"message": "No active providers to sync"},
                    message="No providers configured"
                )
            
            results = {
                "providers_synced": 0,
                "providers_failed": 0,
                "total_items_processed": 0,
                "provider_details": {},
            }
            
            for provider in providers:
                provider_start = datetime.utcnow()
                
                try:
                    # Inbound sync
                    if direction in [SyncDirection.INBOUND, SyncDirection.BIDIRECTIONAL]:
                        pull_result = self.pull_updates(provider)
                        if pull_result.success:
                            results["total_items_processed"] += pull_result.data.items_processed
                    
                    # Outbound sync
                    if direction in [SyncDirection.OUTBOUND, SyncDirection.BIDIRECTIONAL]:
                        push_result = self.push_updates(provider)
                        if push_result.success:
                            results["total_items_processed"] += push_result.data.items_processed
                    
                    results["providers_synced"] += 1
                    results["provider_details"][provider] = {
                        "status": "success",
                        "duration_seconds": (datetime.utcnow() - provider_start).total_seconds(),
                    }
                    
                except Exception as e:
                    results["providers_failed"] += 1
                    results["provider_details"][provider] = {
                        "status": "failed",
                        "error": str(e),
                        "duration_seconds": (datetime.utcnow() - provider_start).total_seconds(),
                    }
                    self._logger.error(f"Failed to sync provider {provider}: {str(e)}")
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            results["total_duration_seconds"] = round(duration, 2)
            
            self._logger.info(
                f"Synced {results['providers_synced']}/{len(providers)} providers "
                f"({results['providers_failed']} failed) in {duration:.2f}s"
            )
            
            return ServiceResult.success(
                results,
                message=f"Synced {results['providers_synced']} providers"
            )
            
        except Exception as e:
            return self._handle_exception(e, "sync all providers")

    def _create_error_result(
        self,
        provider: str,
        direction: SyncDirection,
        start_time: datetime,
        error_message: str,
    ) -> ServiceResult[SyncMetrics]:
        """Create an error ServiceResult with sync metrics."""
        duration = (datetime.utcnow() - start_time).total_seconds()
        metrics = SyncMetrics(
            provider=provider,
            direction=direction,
            status=SyncStatus.FAILED,
            items_processed=0,
            items_succeeded=0,
            items_failed=0,
            duration_seconds=duration,
            error_details=[error_message],
            started_at=start_time,
            completed_at=datetime.utcnow(),
        )
        
        return ServiceResult.failure(
            error=ServiceError(
                code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message=f"Sync failed for {provider}",
                severity=ErrorSeverity.ERROR,
                details={"error": error_message},
            ),
            data=metrics
        )

    def _handle_sync_exception(
        self,
        exception: Exception,
        operation: str,
        provider: str,
        direction: SyncDirection,
        start_time: datetime,
    ) -> ServiceResult[SyncMetrics]:
        """Handle exception during sync and return error result."""
        self._logger.error(f"Error during {operation}: {str(exception)}", exc_info=True)
        return self._create_error_result(provider, direction, start_time, str(exception))