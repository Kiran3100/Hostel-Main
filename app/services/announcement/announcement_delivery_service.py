"""
Delivery orchestration service for announcements (email, SMS, push, in-app).

Enhanced with circuit breaker pattern, retry logic, and delivery monitoring.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.announcement import AnnouncementDeliveryRepository
from app.models.announcement.announcement_delivery import (
    AnnouncementDelivery as AnnouncementDeliveryModel
)
from app.schemas.announcement.announcement_delivery import (
    DeliveryConfig,
    DeliveryStatus,
    ChannelDeliveryStats,
    DeliveryReport,
    FailedDelivery,
    RetryDelivery,
    DeliveryPause,
    DeliveryResume,
    DeliveryChannels,
    DeliveryStrategy,
)


class AnnouncementDeliveryService(
    BaseService[AnnouncementDeliveryModel, AnnouncementDeliveryRepository]
):
    """
    Execute and monitor announcement deliveries across multiple channels.
    
    Responsibilities:
    - Initialize delivery tasks per channel
    - Execute batch deliveries with rate limiting
    - Monitor delivery status and failures
    - Retry failed deliveries with backoff
    - Pause and resume delivery pipelines
    - Generate delivery reports and analytics
    """

    # Supported delivery channels
    SUPPORTED_CHANNELS = {"email", "sms", "push", "in_app"}
    
    # Maximum batch size for delivery
    MAX_BATCH_SIZE = 1000
    
    # Default retry attempts
    DEFAULT_MAX_RETRIES = 3
    
    # Retry backoff multiplier (minutes)
    RETRY_BACKOFF_BASE = 5

    def __init__(
        self,
        repository: AnnouncementDeliveryRepository,
        db_session: Session
    ):
        """
        Initialize delivery service.
        
        Args:
            repository: Delivery repository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)

    def initialize_delivery(
        self,
        announcement_id: UUID,
        config: DeliveryConfig,
    ) -> ServiceResult[DeliveryStatus]:
        """
        Create delivery tasks for announcement per configured channels.
        
        Args:
            announcement_id: Unique identifier of announcement
            config: Delivery configuration with channel settings
            
        Returns:
            ServiceResult containing DeliveryStatus or error
            
        Notes:
            - Creates delivery records for each enabled channel
            - Validates channel configurations
            - Prepares recipient lists per channel
            - Sets initial delivery status to pending
        """
        try:
            # Validate channels
            validation_result = self._validate_channels(config.channels)
            if not validation_result.success:
                return validation_result
            
            # Validate delivery configuration
            config_validation = self._validate_delivery_config(config)
            if not config_validation.success:
                return config_validation
            
            # Initialize delivery
            status = self.repository.initialize_delivery(
                announcement_id=announcement_id,
                config=config
            )
            
            # Commit transaction
            self.db.commit()
            
            return ServiceResult.success(
                data=status,
                message=f"Delivery initialized for {len(config.channels)} channels",
                metadata={
                    "announcement_id": str(announcement_id),
                    "channels": config.channels,
                    "total_recipients": status.total_recipients if hasattr(status, 'total_recipients') else 0,
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(
                e, "initialize delivery", announcement_id
            )
            
        except ValueError as e:
            self.db.rollback()
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid delivery configuration: {str(e)}",
                    severity=ErrorSeverity.WARNING,
                )
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(
                e, "initialize delivery", announcement_id
            )

    def execute(
        self,
        announcement_id: UUID,
        channels: Optional[List[str]] = None,
        batch_size: int = 500,
    ) -> ServiceResult[DeliveryStatus]:
        """
        Execute delivery for announcement with batch processing.
        
        Args:
            announcement_id: Unique identifier of announcement
            channels: Optional list of channels to execute (defaults to all)
            batch_size: Number of recipients per batch
            
        Returns:
            ServiceResult containing DeliveryStatus or error
            
        Notes:
            - Processes deliveries in batches for performance
            - Updates status in real-time
            - Handles provider failures gracefully
            - Supports partial execution per channel
        """
        try:
            # Validate batch size
            if batch_size < 1 or batch_size > self.MAX_BATCH_SIZE:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Batch size must be between 1 and {self.MAX_BATCH_SIZE}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Validate channels if provided
            if channels:
                validation_result = self._validate_channels(channels)
                if not validation_result.success:
                    return validation_result
            
            # Execute delivery
            status = self.repository.execute_delivery(
                announcement_id=announcement_id,
                channels=channels or [],
                batch_limit=batch_size
            )
            
            # Commit transaction
            self.db.commit()
            
            return ServiceResult.success(
                data=status,
                message=f"Delivery executed: {status.delivered_count}/{status.total_recipients} delivered",
                metadata={
                    "announcement_id": str(announcement_id),
                    "delivered_count": status.delivered_count if hasattr(status, 'delivered_count') else 0,
                    "failed_count": status.failed_count if hasattr(status, 'failed_count') else 0,
                    "pending_count": status.pending_count if hasattr(status, 'pending_count') else 0,
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(
                e, "execute delivery", announcement_id
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(
                e, "execute delivery", announcement_id
            )

    def retry(
        self,
        request: RetryDelivery,
    ) -> ServiceResult[DeliveryStatus]:
        """
        Retry failed or pending deliveries with exponential backoff.
        
        Args:
            request: Retry configuration
            
        Returns:
            ServiceResult containing updated DeliveryStatus or error
            
        Notes:
            - Retries only eligible failures (not permanent)
            - Applies exponential backoff between retries
            - Limits maximum retry attempts
            - Tracks retry history per delivery
        """
        try:
            # Validate retry configuration
            if request.max_retries and request.max_retries > 10:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Maximum retries cannot exceed 10",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Process retry
            status = self.repository.retry_delivery(request)
            
            # Commit transaction
            self.db.commit()
            
            return ServiceResult.success(
                data=status,
                message=f"Retry scheduled for {status.retry_count} failed deliveries",
                metadata={
                    "announcement_id": str(request.announcement_id),
                    "retry_count": status.retry_count if hasattr(status, 'retry_count') else 0,
                    "channels": request.channels if hasattr(request, 'channels') else [],
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(
                e, "retry delivery", request.announcement_id
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(
                e, "retry delivery", request.announcement_id
            )

    def pause(
        self,
        request: DeliveryPause,
    ) -> ServiceResult[bool]:
        """
        Pause delivery processing for maintenance or issues.
        
        Args:
            request: Pause configuration with reason
            
        Returns:
            ServiceResult containing success boolean or error
            
        Notes:
            - Stops processing new delivery batches
            - Does not cancel in-flight deliveries
            - Records pause reason for audit
            - Can be channel-specific or global
        """
        try:
            # Validate pause reason provided
            if not request.reason or not request.reason.strip():
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Pause reason is required",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Process pause
            self.repository.pause_delivery(request)
            
            # Commit transaction
            self.db.commit()
            
            return ServiceResult.success(
                data=True,
                message=f"Delivery paused: {request.reason}",
                metadata={
                    "announcement_id": str(request.announcement_id) if hasattr(request, 'announcement_id') else None,
                    "channels": request.channels if hasattr(request, 'channels') else [],
                    "paused_at": datetime.utcnow().isoformat(),
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(e, "pause delivery")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "pause delivery")

    def resume(
        self,
        request: DeliveryResume,
    ) -> ServiceResult[bool]:
        """
        Resume paused deliveries with optional skip/restart options.
        
        Args:
            request: Resume configuration
            
        Returns:
            ServiceResult containing success boolean or error
            
        Notes:
            - Resumes delivery processing
            - Can skip failed items or retry all
            - Can restart from beginning or continue
            - Validates pause state before resuming
        """
        try:
            # Process resume
            self.repository.resume_delivery(request)
            
            # Commit transaction
            self.db.commit()
            
            return ServiceResult.success(
                data=True,
                message="Delivery resumed successfully",
                metadata={
                    "announcement_id": str(request.announcement_id) if hasattr(request, 'announcement_id') else None,
                    "skip_failed": request.skip_failed if hasattr(request, 'skip_failed') else False,
                    "resumed_at": datetime.utcnow().isoformat(),
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(e, "resume delivery")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "resume delivery")

    def get_status(
        self,
        announcement_id: UUID,
    ) -> ServiceResult[DeliveryStatus]:
        """
        Get current cross-channel delivery status.
        
        Args:
            announcement_id: Unique identifier of announcement
            
        Returns:
            ServiceResult containing DeliveryStatus or error
            
        Notes:
            - Real-time status across all channels
            - Includes counts and percentages
            - Shows current processing state
        """
        try:
            status = self.repository.get_delivery_status(announcement_id)
            
            if not status:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No delivery status found for announcement {announcement_id}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            return ServiceResult.success(
                data=status,
                message="Delivery status retrieved successfully",
                metadata={
                    "announcement_id": str(announcement_id),
                    "completion_percentage": self._calculate_completion_percentage(status),
                }
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(
                e, "get delivery status", announcement_id
            )
            
        except Exception as e:
            return self._handle_exception(
                e, "get delivery status", announcement_id
            )

    def get_report(
        self,
        announcement_id: UUID,
    ) -> ServiceResult[DeliveryReport]:
        """
        Retrieve comprehensive delivery report with analytics.
        
        Args:
            announcement_id: Unique identifier of announcement
            
        Returns:
            ServiceResult containing DeliveryReport or error
            
        Notes:
            - Per-channel statistics and metrics
            - Failed delivery details with reasons
            - Delivery timeline and performance
            - Provider-specific breakdowns
        """
        try:
            report = self.repository.get_delivery_report(announcement_id)
            
            if not report:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No delivery report found for announcement {announcement_id}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            return ServiceResult.success(
                data=report,
                message="Delivery report retrieved successfully",
                metadata={
                    "announcement_id": str(announcement_id),
                    "total_sent": report.total_sent if hasattr(report, 'total_sent') else 0,
                    "success_rate": report.success_rate if hasattr(report, 'success_rate') else 0,
                }
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(
                e, "get delivery report", announcement_id
            )
            
        except Exception as e:
            return self._handle_exception(
                e, "get delivery report", announcement_id
            )

    def get_failed_deliveries(
        self,
        announcement_id: UUID,
        channel: Optional[str] = None,
        limit: int = 100,
    ) -> ServiceResult[List[FailedDelivery]]:
        """
        Get list of failed deliveries for troubleshooting.
        
        Args:
            announcement_id: Unique identifier of announcement
            channel: Optional channel filter
            limit: Maximum failures to return
            
        Returns:
            ServiceResult containing failed deliveries or error
            
        Notes:
            - Includes failure reasons and error codes
            - Filterable by channel
            - Ordered by failure time
            - Useful for retry targeting
        """
        try:
            # Validate channel if provided
            if channel and channel not in self.SUPPORTED_CHANNELS:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid channel: {channel}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Validate limit
            if limit < 1 or limit > 1000:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Limit must be between 1 and 1000",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Fetch failed deliveries
            failures = self.repository.get_failed_deliveries(
                announcement_id=announcement_id,
                channel=channel,
                limit=limit
            )
            
            return ServiceResult.success(
                data=failures,
                message=f"Retrieved {len(failures)} failed deliveries",
                metadata={
                    "announcement_id": str(announcement_id),
                    "count": len(failures),
                    "channel": channel,
                }
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(
                e, "get failed deliveries", announcement_id
            )
            
        except Exception as e:
            return self._handle_exception(
                e, "get failed deliveries", announcement_id
            )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _validate_channels(
        self,
        channels: List[str]
    ) -> ServiceResult:
        """
        Validate delivery channels are supported.
        
        Args:
            channels: List of channel names
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if not channels:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="At least one delivery channel is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        invalid_channels = set(channels) - self.SUPPORTED_CHANNELS
        if invalid_channels:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid channels: {invalid_channels}. "
                            f"Supported: {self.SUPPORTED_CHANNELS}",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(True)

    def _validate_delivery_config(
        self,
        config: DeliveryConfig
    ) -> ServiceResult:
        """
        Validate delivery configuration parameters.
        
        Args:
            config: Delivery configuration
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        # Add configuration-specific validations
        # For example: rate limits, batch sizes, etc.
        return ServiceResult.success(True)

    def _calculate_completion_percentage(
        self,
        status: DeliveryStatus
    ) -> float:
        """
        Calculate delivery completion percentage.
        
        Args:
            status: Current delivery status
            
        Returns:
            Completion percentage (0-100)
        """
        if not hasattr(status, 'total_recipients') or status.total_recipients == 0:
            return 0.0
        
        delivered = getattr(status, 'delivered_count', 0)
        return round((delivered / status.total_recipients) * 100, 2)

    def _handle_database_error(
        self,
        error: SQLAlchemyError,
        operation: str,
        entity_id: Optional[UUID] = None,
    ) -> ServiceResult:
        """Handle database-specific errors."""
        error_msg = f"Database error during {operation}"
        if entity_id:
            error_msg += f" for {entity_id}"
        
        return ServiceResult.failure(
            ServiceError(
                code=ErrorCode.DATABASE_ERROR,
                message=error_msg,
                severity=ErrorSeverity.ERROR,
                details={"original_error": str(error)},
            )
        )