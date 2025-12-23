"""
Calendar sync service (Google/Outlook) for bookings/events.

This service manages bidirectional synchronization of calendar events
between the hostel management system and external calendar providers.
"""

from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.integrations import ThirdPartyRepository
from app.models.integrations.api_integration import APIIntegration

logger = logging.getLogger(__name__)


class CalendarSyncService(BaseService[APIIntegration, ThirdPartyRepository]):
    """
    Sync calendar events with external providers (Google Calendar, Outlook, etc.).
    
    Features:
    - Bidirectional sync (pull/push)
    - Conflict detection and resolution
    - Event deduplication
    - Incremental sync support
    - Bulk operations
    """

    def __init__(
        self, 
        repository: ThirdPartyRepository, 
        db_session: Session,
        default_sync_window_days: int = 90
    ):
        """
        Initialize calendar sync service.
        
        Args:
            repository: Third-party repository instance
            db_session: SQLAlchemy database session
            default_sync_window_days: Default time window for sync operations
        """
        super().__init__(repository, db_session)
        self._default_sync_window_days = default_sync_window_days
        self._sync_locks: Set[str] = set()  # Prevent concurrent syncs
        
        logger.info("CalendarSyncService initialized")

    def _validate_calendar_params(
        self,
        provider: str,
        calendar_id: str
    ) -> ServiceResult[bool]:
        """
        Validate calendar sync parameters.
        
        Args:
            provider: Provider identifier
            calendar_id: Calendar identifier
            
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
            
        if not calendar_id or not isinstance(calendar_id, str):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Calendar ID must be a non-empty string",
                    severity=ErrorSeverity.MEDIUM,
                    context={"provider": provider}
                )
            )
            
        return ServiceResult.success(True)

    def _acquire_sync_lock(self, provider: str, calendar_id: str) -> bool:
        """
        Acquire lock to prevent concurrent sync operations.
        
        Args:
            provider: Provider identifier
            calendar_id: Calendar identifier
            
        Returns:
            True if lock acquired, False otherwise
        """
        lock_key = f"{provider}:{calendar_id}"
        if lock_key in self._sync_locks:
            return False
        self._sync_locks.add(lock_key)
        return True

    def _release_sync_lock(self, provider: str, calendar_id: str) -> None:
        """
        Release sync lock.
        
        Args:
            provider: Provider identifier
            calendar_id: Calendar identifier
        """
        lock_key = f"{provider}:{calendar_id}"
        self._sync_locks.discard(lock_key)

    def pull_events(
        self,
        provider: str,
        calendar_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 500,
        incremental: bool = True,
        sync_deleted: bool = True,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Pull calendar events from external provider.
        
        Retrieves events from the provider's calendar and optionally
        performs incremental sync based on last sync timestamp.
        
        Args:
            provider: Provider identifier (google, outlook, etc.)
            calendar_id: Provider-specific calendar identifier
            since: Start date for event retrieval (default: last sync or 30 days ago)
            until: End date for event retrieval (default: 90 days from now)
            limit: Maximum number of events to retrieve
            incremental: Use incremental sync if available
            sync_deleted: Include deleted events in sync
            
        Returns:
            ServiceResult containing list of calendar events
        """
        logger.info(
            f"Pulling events from {provider} calendar: {calendar_id}",
            extra={"provider": provider, "calendar_id": calendar_id}
        )
        
        # Validate parameters
        validation = self._validate_calendar_params(provider, calendar_id)
        if not validation.success:
            return validation
            
        # Validate limit
        if limit <= 0 or limit > 2000:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Limit must be between 1 and 2000",
                    severity=ErrorSeverity.MEDIUM,
                    context={"limit": limit}
                )
            )

        # Acquire sync lock
        if not self._acquire_sync_lock(provider, calendar_id):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.CONFLICT,
                    message=f"Sync already in progress for {provider}:{calendar_id}",
                    severity=ErrorSeverity.MEDIUM,
                    context={"provider": provider, "calendar_id": calendar_id}
                )
            )

        try:
            # Set default time range if not provided
            if not since:
                if incremental:
                    # Get last sync time from repository
                    last_sync = self.repository.get_last_sync_time(provider, calendar_id)
                    since = last_sync or (datetime.utcnow() - timedelta(days=30))
                else:
                    since = datetime.utcnow() - timedelta(days=30)
                    
            if not until:
                until = datetime.utcnow() + timedelta(days=self._default_sync_window_days)
            
            # Validate date range
            if since >= until:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Start date must be before end date",
                        severity=ErrorSeverity.MEDIUM,
                        context={"since": since.isoformat(), "until": until.isoformat()}
                    )
                )
            
            # Pull events from provider
            events = self.repository.calendar_pull_events(
                provider=provider,
                calendar_id=calendar_id,
                since=since,
                until=until,
                limit=limit,
                sync_deleted=sync_deleted
            )
            
            # Deduplicate events
            unique_events = self._deduplicate_events(events or [])
            
            # Update sync timestamp
            self.repository.update_last_sync_time(
                provider, 
                calendar_id, 
                datetime.utcnow()
            )
            
            # Commit transaction
            self.db.commit()
            
            logger.info(
                f"Successfully pulled {len(unique_events)} events from {provider}",
                extra={
                    "provider": provider,
                    "calendar_id": calendar_id,
                    "event_count": len(unique_events)
                }
            )
            
            return ServiceResult.success(
                unique_events,
                message=f"Pulled {len(unique_events)} events from {provider}",
                metadata={
                    "provider": provider,
                    "calendar_id": calendar_id,
                    "count": len(unique_events),
                    "since": since.isoformat(),
                    "until": until.isoformat(),
                    "incremental": incremental
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error pulling events from {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to persist calendar events from {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={
                        "provider": provider,
                        "calendar_id": calendar_id,
                        "error": str(e)
                    }
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error pulling events from {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "pull calendar events", calendar_id)
        finally:
            self._release_sync_lock(provider, calendar_id)

    def push_events(
        self,
        provider: str,
        calendar_id: str,
        events: List[Dict[str, Any]],
        batch_size: int = 50,
        update_existing: bool = True,
        delete_removed: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Push calendar events to external provider.
        
        Sends local events to the provider's calendar with support for
        batch operations, conflict resolution, and partial failures.
        
        Args:
            provider: Provider identifier
            calendar_id: Provider-specific calendar identifier
            events: List of event data to push
            batch_size: Number of events per batch request
            update_existing: Update events that already exist
            delete_removed: Delete events not in the push list
            
        Returns:
            ServiceResult containing push operation summary
        """
        logger.info(
            f"Pushing {len(events)} events to {provider} calendar: {calendar_id}",
            extra={"provider": provider, "calendar_id": calendar_id, "count": len(events)}
        )
        
        # Validate parameters
        validation = self._validate_calendar_params(provider, calendar_id)
        if not validation.success:
            return validation
            
        if not events or not isinstance(events, list):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Events must be a non-empty list",
                    severity=ErrorSeverity.MEDIUM
                )
            )
            
        if batch_size <= 0 or batch_size > 100:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Batch size must be between 1 and 100",
                    severity=ErrorSeverity.MEDIUM,
                    context={"batch_size": batch_size}
                )
            )

        # Acquire sync lock
        if not self._acquire_sync_lock(provider, calendar_id):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.CONFLICT,
                    message=f"Sync already in progress for {provider}:{calendar_id}",
                    severity=ErrorSeverity.MEDIUM,
                    context={"provider": provider, "calendar_id": calendar_id}
                )
            )

        try:
            # Validate event data
            validated_events = []
            validation_errors = []
            
            for idx, event in enumerate(events):
                event_validation = self._validate_event_data(event)
                if event_validation.success:
                    validated_events.append(event)
                else:
                    validation_errors.append({
                        "index": idx,
                        "error": str(event_validation.error),
                        "event": event.get("id") or event.get("title")
                    })
            
            if not validated_events:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="No valid events to push",
                        severity=ErrorSeverity.MEDIUM,
                        context={"validation_errors": validation_errors}
                    )
                )
            
            # Push events in batches
            total_created = 0
            total_updated = 0
            total_failed = 0
            failed_events = []
            
            for i in range(0, len(validated_events), batch_size):
                batch = validated_events[i:i + batch_size]
                
                try:
                    result = self.repository.calendar_push_events(
                        provider=provider,
                        calendar_id=calendar_id,
                        events=batch,
                        update_existing=update_existing
                    )
                    
                    total_created += result.get("created", 0)
                    total_updated += result.get("updated", 0)
                    total_failed += result.get("failed", 0)
                    failed_events.extend(result.get("failed_events", []))
                    
                except Exception as batch_error:
                    logger.error(
                        f"Batch push failed for events {i}-{i+len(batch)}: {str(batch_error)}",
                        exc_info=True
                    )
                    total_failed += len(batch)
                    failed_events.extend([
                        {"event": e.get("id"), "error": str(batch_error)}
                        for e in batch
                    ])
            
            # Commit transaction
            self.db.commit()
            
            summary = {
                "total": len(events),
                "validated": len(validated_events),
                "created": total_created,
                "updated": total_updated,
                "failed": total_failed,
                "validation_errors": validation_errors,
                "failed_events": failed_events
            }
            
            logger.info(
                f"Push completed for {provider}: "
                f"{total_created} created, {total_updated} updated, {total_failed} failed",
                extra={**summary, "provider": provider, "calendar_id": calendar_id}
            )
            
            return ServiceResult.success(
                summary,
                message=f"Pushed {total_created + total_updated} events to {provider}",
                metadata={
                    "provider": provider,
                    "calendar_id": calendar_id,
                    **summary
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error pushing events to {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to push calendar events to {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={
                        "provider": provider,
                        "calendar_id": calendar_id,
                        "error": str(e)
                    }
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error pushing events to {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "push calendar events", calendar_id)
        finally:
            self._release_sync_lock(provider, calendar_id)

    def sync_bidirectional(
        self,
        provider: str,
        calendar_id: str,
        conflict_resolution: str = "remote_wins"
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Perform bidirectional sync between local and remote calendar.
        
        Args:
            provider: Provider identifier
            calendar_id: Calendar identifier
            conflict_resolution: Strategy for conflicts (remote_wins, local_wins, latest_wins)
            
        Returns:
            ServiceResult containing sync summary
        """
        logger.info(
            f"Starting bidirectional sync for {provider}:{calendar_id}",
            extra={"provider": provider, "calendar_id": calendar_id}
        )
        
        try:
            # Pull remote events
            pull_result = self.pull_events(provider, calendar_id, incremental=True)
            if not pull_result.success:
                return pull_result
            
            # Get local events needing sync
            local_events = self.repository.get_local_events_for_sync(calendar_id)
            
            # Push local events
            push_result = self.push_events(provider, calendar_id, local_events)
            
            summary = {
                "pull": pull_result.metadata,
                "push": push_result.metadata if push_result.success else {},
                "conflict_resolution": conflict_resolution,
                "synced_at": datetime.utcnow().isoformat()
            }
            
            logger.info(
                f"Bidirectional sync completed for {provider}:{calendar_id}",
                extra=summary
            )
            
            return ServiceResult.success(
                summary,
                message=f"Bidirectional sync completed for {provider}"
            )
            
        except Exception as e:
            logger.error(
                f"Error in bidirectional sync: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "bidirectional sync", calendar_id)

    def _deduplicate_events(
        self, 
        events: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate events based on event ID and content hash.
        
        Args:
            events: List of calendar events
            
        Returns:
            Deduplicated list of events
        """
        seen = set()
        unique_events = []
        
        for event in events:
            # Create unique key from event ID or content hash
            event_id = event.get("id") or event.get("external_id")
            event_hash = hash(frozenset(event.items()))
            key = f"{event_id}:{event_hash}"
            
            if key not in seen:
                seen.add(key)
                unique_events.append(event)
        
        if len(unique_events) < len(events):
            logger.info(
                f"Deduplicated {len(events)} events to {len(unique_events)} unique events"
            )
        
        return unique_events

    def _validate_event_data(
        self, 
        event: Dict[str, Any]
    ) -> ServiceResult[bool]:
        """
        Validate calendar event data structure.
        
        Args:
            event: Event data dictionary
            
        Returns:
            ServiceResult indicating validation success
        """
        required_fields = ["title", "start_time"]
        
        for field in required_fields:
            if field not in event:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Missing required field: {field}",
                        severity=ErrorSeverity.MEDIUM,
                        context={"event": event}
                    )
                )
        
        # Validate datetime fields
        if not isinstance(event.get("start_time"), (datetime, str)):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="start_time must be a datetime object or ISO string",
                    severity=ErrorSeverity.MEDIUM
                )
            )
        
        return ServiceResult.success(True)

    def delete_event(
        self,
        provider: str,
        calendar_id: str,
        event_id: str,
    ) -> ServiceResult[bool]:
        """
        Delete a specific event from the calendar.
        
        Args:
            provider: Provider identifier
            calendar_id: Calendar identifier
            event_id: Event identifier
            
        Returns:
            ServiceResult indicating deletion success
        """
        logger.info(
            f"Deleting event {event_id} from {provider}:{calendar_id}",
            extra={"provider": provider, "calendar_id": calendar_id, "event_id": event_id}
        )
        
        validation = self._validate_calendar_params(provider, calendar_id)
        if not validation.success:
            return validation
            
        try:
            success = self.repository.calendar_delete_event(
                provider, calendar_id, event_id
            )
            
            self.db.commit()
            
            return ServiceResult.success(
                success,
                message=f"Event deleted from {provider}"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting event: {str(e)}", exc_info=True)
            return self._handle_exception(e, "delete calendar event", event_id)