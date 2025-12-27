# app/services/notification/push_notification_service.py
"""
Enhanced Push Notification Service

Handles push notifications via stored device tokens with improved:
- Performance through batch operations and connection pooling
- Advanced device management and token validation
- Comprehensive error handling and retry logic
- Platform-specific optimizations (iOS/Android/Web)
- Analytics and delivery tracking
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.notification import (
    PushNotificationRepository,
    DeviceTokenRepository,
)
from app.schemas.notification import (
    PushRequest,
    BulkPushRequest,
    PushStats,
    DeviceToken,
)
from app.core1.logging import LoggingContext
from app.core1.exceptions import ValidationException, DatabaseException

logger = logging.getLogger(__name__)


class PushPriority(str, Enum):
    """Push notification priority levels."""
    LOW = "low"
    NORMAL = "normal" 
    HIGH = "high"
    CRITICAL = "critical"


class DeviceType(str, Enum):
    """Supported device types."""
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class PushNotificationService:
    """
    Enhanced orchestration of push notifications.

    Enhanced with:
    - Advanced device token management
    - Platform-specific optimizations
    - Batch processing capabilities
    - Comprehensive error handling
    - Analytics and monitoring
    - Retry logic with exponential backoff
    """

    def __init__(
        self,
        push_repo: PushNotificationRepository,
        device_repo: DeviceTokenRepository,
    ) -> None:
        self.push_repo = push_repo
        self.device_repo = device_repo
        
        # Configuration
        self._max_batch_size = 1000
        self._max_payload_size = 4096  # 4KB limit for most platforms
        self._max_title_length = 100
        self._max_body_length = 500
        self._valid_priorities = [p.value for p in PushPriority]
        self._valid_device_types = [d.value for d in DeviceType]
        self._default_ttl = 3600  # 1 hour TTL
        self._retry_delays = [60, 300, 900]  # 1min, 5min, 15min

    def _validate_push_request(self, request: PushRequest) -> None:
        """Validate push notification request."""
        if not request.title or len(request.title.strip()) == 0:
            raise ValidationException("Push notification title is required")
        
        if len(request.title) > self._max_title_length:
            raise ValidationException(f"Title too long (max {self._max_title_length} characters)")
        
        if request.body and len(request.body) > self._max_body_length:
            raise ValidationException(f"Body too long (max {self._max_body_length} characters)")
        
        if not request.user_id and not request.device_token:
            raise ValidationException("Either user_id or device_token is required")
        
        if request.priority and request.priority not in self._valid_priorities:
            raise ValidationException(f"Invalid priority. Must be one of: {self._valid_priorities}")
        
        # Validate payload size
        total_size = len(str(request.model_dump()))
        if total_size > self._max_payload_size:
            raise ValidationException(f"Push payload too large (max {self._max_payload_size} bytes)")

    def _validate_bulk_push_request(self, request: BulkPushRequest) -> None:
        """Validate bulk push notification request."""
        if not request.title or len(request.title.strip()) == 0:
            raise ValidationException("Push notification title is required")
        
        if len(request.title) > self._max_title_length:
            raise ValidationException(f"Title too long (max {self._max_title_length} characters)")
        
        if request.body and len(request.body) > self._max_body_length:
            raise ValidationException(f"Body too long (max {self._max_body_length} characters)")
        
        if not request.user_ids and not request.device_tokens:
            raise ValidationException("Either user_ids or device_tokens is required")
        
        total_recipients = len(request.user_ids or []) + len(request.device_tokens or [])
        if total_recipients == 0:
            raise ValidationException("At least one recipient is required")
        
        if total_recipients > self._max_batch_size:
            raise ValidationException(f"Too many recipients (max {self._max_batch_size})")
        
        if request.priority and request.priority not in self._valid_priorities:
            raise ValidationException(f"Invalid priority. Must be one of: {self._valid_priorities}")

    def _optimize_payload_for_platform(
        self,
        payload: Dict[str, Any],
        device_type: str,
    ) -> Dict[str, Any]:
        """
        Optimize push payload for specific platform requirements.
        
        Different platforms have different requirements and limits.
        """
        optimized = payload.copy()
        
        if device_type == DeviceType.IOS:
            # iOS specific optimizations
            if "data" in optimized:
                # iOS prefers data in "aps" custom payload
                optimized["custom_data"] = optimized.pop("data", {})
            
            # Add iOS specific fields
            optimized["sound"] = optimized.get("sound", "default")
            optimized["badge"] = optimized.get("badge", 1)
            
        elif device_type == DeviceType.ANDROID:
            # Android specific optimizations
            if "data" not in optimized:
                optimized["data"] = {}
            
            # Android can handle larger payloads
            optimized["android_channel_id"] = optimized.get("android_channel_id", "default")
            optimized["click_action"] = optimized.get("click_action", "FLUTTER_NOTIFICATION_CLICK")
            
        elif device_type == DeviceType.WEB:
            # Web push specific optimizations
            optimized["icon"] = optimized.get("icon", "/default-notification-icon.png")
            optimized["requireInteraction"] = optimized.get("requireInteraction", False)
            
            # Web push has stricter size limits
            if len(str(optimized)) > 3072:  # 3KB limit for web push
                # Truncate body if needed
                if "body" in optimized and len(optimized["body"]) > 200:
                    optimized["body"] = optimized["body"][:197] + "..."
        
        return optimized

    def _get_active_device_tokens_for_users(
        self,
        db: Session,
        user_ids: List[UUID],
    ) -> Dict[UUID, List[DeviceToken]]:
        """
        Get active device tokens for multiple users efficiently.
        
        Returns a mapping of user_id -> list of device tokens.
        """
        with LoggingContext(channel="device_tokens_batch", user_count=len(user_ids)):
            try:
                logger.debug(f"Retrieving device tokens for {len(user_ids)} users")
                
                user_devices = {}
                for user_id in user_ids:
                    devices = self.device_repo.get_by_user_id(
                        db, user_id, include_inactive=False
                    )
                    if devices:
                        user_devices[user_id] = [
                            DeviceToken.model_validate(device) for device in devices
                        ]
                
                total_devices = sum(len(devices) for devices in user_devices.values())
                logger.debug(f"Found {total_devices} active devices for {len(user_devices)} users")
                
                return user_devices
                
            except Exception as e:
                logger.error(f"Error retrieving device tokens: {str(e)}")
                raise DatabaseException("Failed to retrieve device tokens") from e

    def _validate_device_tokens(
        self,
        db: Session,
        device_tokens: List[str],
    ) -> List[str]:
        """
        Validate device tokens and filter out inactive/invalid ones.
        
        Returns list of valid, active device tokens.
        """
        valid_tokens = []
        
        for token in device_tokens:
            try:
                device = self.device_repo.get_by_token(db, token)
                if device and device.is_active:
                    # Check if token is not expired
                    if hasattr(device, 'last_used_at'):
                        if device.last_used_at:
                            days_since_use = (datetime.utcnow() - device.last_used_at).days
                            if days_since_use > 90:  # Token unused for 90 days
                                logger.debug(f"Skipping stale device token: {token[:10]}...")
                                continue
                    
                    valid_tokens.append(token)
                else:
                    logger.debug(f"Skipping inactive device token: {token[:10]}...")
                    
            except Exception as e:
                logger.warning(f"Error validating device token {token[:10]}...: {str(e)}")
                continue
        
        return valid_tokens

    # -------------------------------------------------------------------------
    # Enhanced single push operations
    # -------------------------------------------------------------------------

    def send_push(
        self,
        db: Session,
        request: PushRequest,
        platform_optimizations: bool = True,
        validate_device: bool = True,
    ) -> UUID:
        """
        Create a push notification entry with enhanced validation and optimization.

        Enhanced with:
        - Platform-specific payload optimization
        - Device token validation
        - Enhanced error handling
        - Performance monitoring

        Args:
            db: Database session
            request: Push notification request
            platform_optimizations: Whether to apply platform-specific optimizations
            validate_device: Whether to validate device token

        Returns:
            UUID: Push notification ID

        Raises:
            ValidationException: For invalid request data
            DatabaseException: For database operation failures
        """
        self._validate_push_request(request)

        payload = request.model_dump(exclude_none=True)
        
        # Resolve device tokens if user_id provided
        if request.user_id and not request.device_token:
            user_devices = self._get_active_device_tokens_for_users(db, [request.user_id])
            if not user_devices.get(request.user_id):
                raise ValidationException(f"No active devices found for user {request.user_id}")
            
            # Use the first active device (or implement device selection logic)
            device_token = user_devices[request.user_id][0].device_token
            payload["device_token"] = device_token
            payload["device_type"] = user_devices[request.user_id][0].device_type

        # Validate device token if requested
        if validate_device and payload.get("device_token"):
            valid_tokens = self._validate_device_tokens(db, [payload["device_token"]])
            if not valid_tokens:
                raise ValidationException("Device token is invalid or inactive")

        # Apply platform optimizations
        if platform_optimizations and payload.get("device_type"):
            payload = self._optimize_payload_for_platform(
                payload, payload["device_type"]
            )

        with LoggingContext(
            channel="push",
            title=payload.get("title"),
            user_id=str(request.user_id) if request.user_id else None,
            device_type=payload.get("device_type")
        ):
            try:
                logger.info(
                    f"Creating push notification for user {request.user_id}, "
                    f"title: {request.title}, device_type: {payload.get('device_type')}"
                )
                
                obj = self.push_repo.create_push_notification(db, payload)
                
                # Update device last_used_at
                if payload.get("device_token"):
                    self._update_device_usage(db, payload["device_token"])
                
                logger.info(f"Push notification created successfully: {obj.id}")
                return obj.id  # type: ignore[attr-defined]
                
            except SQLAlchemyError as e:
                logger.error(f"Database error creating push notification: {str(e)}")
                raise DatabaseException("Failed to create push notification") from e
            except Exception as e:
                logger.error(f"Unexpected error creating push notification: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Enhanced bulk push operations
    # -------------------------------------------------------------------------

    def send_bulk_push(
        self,
        db: Session,
        request: BulkPushRequest,
        chunk_size: int = 100,
        platform_optimizations: bool = True,
    ) -> List[UUID]:
        """
        Create multiple push notifications with enhanced batch processing.

        Enhanced with:
        - Chunked processing for large batches
        - Platform-specific optimizations
        - Device validation and filtering
        - Progress tracking
        - Comprehensive error handling

        Args:
            db: Database session
            request: Bulk push request
            chunk_size: Size of processing chunks
            platform_optimizations: Whether to apply platform optimizations

        Returns:
            List[UUID]: List of push notification IDs

        Raises:
            ValidationException: For invalid request data
            DatabaseException: For database operation failures
        """
        self._validate_bulk_push_request(request)
        
        if chunk_size < 1 or chunk_size > 500:
            chunk_size = 100

        payload = request.model_dump(exclude_none=True)

        # Resolve device tokens from user_ids if provided
        all_device_data = []
        
        if request.user_ids:
            user_devices = self._get_active_device_tokens_for_users(db, request.user_ids)
            for user_id, devices in user_devices.items():
                for device in devices:
                    all_device_data.append({
                        "user_id": user_id,
                        "device_token": device.device_token,
                        "device_type": device.device_type,
                    })

        # Add explicitly provided device tokens
        if request.device_tokens:
            # Validate provided device tokens
            valid_tokens = self._validate_device_tokens(db, request.device_tokens)
            for token in valid_tokens:
                device = self.device_repo.get_by_token(db, token)
                if device:
                    all_device_data.append({
                        "user_id": device.user_id,
                        "device_token": token,
                        "device_type": device.device_type,
                    })

        if not all_device_data:
            raise ValidationException("No valid devices found for push notification")

        with LoggingContext(
            channel="push_bulk",
            title=request.title,
            device_count=len(all_device_data)
        ):
            try:
                logger.info(
                    f"Creating bulk push notification '{request.title}' "
                    f"for {len(all_device_data)} devices"
                )
                
                all_ids = []
                total_devices = len(all_device_data)
                
                # Process in chunks for better performance and memory management
                for i in range(0, total_devices, chunk_size):
                    chunk_devices = all_device_data[i:i + chunk_size]
                    
                    logger.debug(
                        f"Processing chunk {i//chunk_size + 1}, "
                        f"devices: {len(chunk_devices)}"
                    )
                    
                    chunk_payloads = []
                    for device_info in chunk_devices:
                        chunk_payload = payload.copy()
                        chunk_payload.update(device_info)
                        
                        # Apply platform optimizations
                        if platform_optimizations and device_info.get("device_type"):
                            chunk_payload = self._optimize_payload_for_platform(
                                chunk_payload, device_info["device_type"]
                            )
                        
                        chunk_payloads.append(chunk_payload)
                    
                    # Create notifications in batch
                    objs = self.push_repo.create_bulk_push_notifications(
                        db, {"notifications": chunk_payloads}
                    )
                    
                    chunk_ids = [o.id for o in objs]  # type: ignore[attr-defined]
                    all_ids.extend(chunk_ids)
                    
                    # Update device usage for this chunk
                    device_tokens = [d["device_token"] for d in chunk_devices]
                    self._update_devices_usage_batch(db, device_tokens)
                    
                    # Commit each chunk to avoid large transactions
                    db.commit()
                
                logger.info(
                    f"Bulk push notification created successfully, "
                    f"total notifications: {len(all_ids)}"
                )
                
                return all_ids
                
            except SQLAlchemyError as e:
                logger.error(f"Database error creating bulk push: {str(e)}")
                db.rollback()
                raise DatabaseException("Failed to create bulk push notifications") from e
            except Exception as e:
                logger.error(f"Unexpected error creating bulk push: {str(e)}")
                db.rollback()
                raise

    # -------------------------------------------------------------------------
    # Enhanced device management
    # -------------------------------------------------------------------------

    def list_devices_for_user(
        self,
        db: Session,
        user_id: UUID,
        include_inactive: bool = False,
        device_type_filter: Optional[str] = None,
    ) -> List[DeviceToken]:
        """
        List devices for a user with enhanced filtering.

        Enhanced with:
        - Device type filtering
        - Inactive device inclusion option
        - Performance optimization
        - Comprehensive validation

        Args:
            db: Database session
            user_id: User identifier
            include_inactive: Whether to include inactive devices
            device_type_filter: Filter by device type

        Returns:
            List[DeviceToken]: User's devices

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if not user_id:
            raise ValidationException("User ID is required")
        
        if device_type_filter and device_type_filter not in self._valid_device_types:
            raise ValidationException(
                f"Invalid device type filter. Must be one of: {self._valid_device_types}"
            )

        with LoggingContext(
            channel="device_list_user",
            user_id=str(user_id),
            device_type_filter=device_type_filter
        ):
            try:
                logger.debug(f"Listing devices for user {user_id}")
                
                objs = self.device_repo.get_by_user_id(
                    db, 
                    user_id, 
                    include_inactive=include_inactive,
                    device_type_filter=device_type_filter,
                )
                
                devices = [DeviceToken.model_validate(o) for o in objs]
                logger.debug(f"Found {len(devices)} devices for user {user_id}")
                
                return devices
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error listing devices: {str(e)}")
                raise DatabaseException("Failed to retrieve user devices") from e
            except Exception as e:
                logger.error(f"Unexpected error listing devices: {str(e)}")
                raise

    def cleanup_inactive_devices(
        self,
        db: Session,
        days_inactive: int = 90,
        batch_size: int = 1000,
    ) -> int:
        """
        Clean up inactive device tokens to maintain performance.

        Args:
            db: Database session
            days_inactive: Remove devices inactive for this many days
            batch_size: Process in batches of this size

        Returns:
            int: Number of devices cleaned up

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if days_inactive < 7:
            raise ValidationException("Days inactive must be at least 7")
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)

        with LoggingContext(
            channel="device_cleanup",
            days_inactive=days_inactive,
            cutoff_date=cutoff_date.isoformat()
        ):
            try:
                logger.info(f"Cleaning up devices inactive for {days_inactive} days")
                
                cleaned_count = self.device_repo.cleanup_inactive_devices(
                    db=db,
                    cutoff_date=cutoff_date,
                    batch_size=batch_size,
                )
                
                logger.info(f"Cleaned up {cleaned_count} inactive devices")
                return cleaned_count
                
            except SQLAlchemyError as e:
                logger.error(f"Database error during device cleanup: {str(e)}")
                raise DatabaseException("Failed to cleanup inactive devices") from e
            except Exception as e:
                logger.error(f"Unexpected error during device cleanup: {str(e)}")
                raise

    def _update_device_usage(
        self,
        db: Session,
        device_token: str,
    ) -> None:
        """Update device last used timestamp."""
        try:
            self.device_repo.update_device_usage(
                db=db,
                device_token=device_token,
                last_used_at=datetime.utcnow(),
            )
        except Exception as e:
            logger.warning(f"Failed to update device usage: {str(e)}")
            # Don't fail the main operation

    def _update_devices_usage_batch(
        self,
        db: Session,
        device_tokens: List[str],
    ) -> None:
        """Update device usage for multiple devices efficiently."""
        try:
            self.device_repo.update_devices_usage_batch(
                db=db,
                device_tokens=device_tokens,
                last_used_at=datetime.utcnow(),
            )
        except Exception as e:
            logger.warning(f"Failed to update devices usage batch: {str(e)}")
            # Don't fail the main operation

    # -------------------------------------------------------------------------
    # Enhanced statistics and monitoring
    # -------------------------------------------------------------------------

    def get_push_stats_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        time_range_days: int = 30,
        include_device_breakdown: bool = False,
    ) -> PushStats:
        """
        Get enhanced push notification statistics with detailed breakdown.

        Enhanced with:
        - Configurable time ranges
        - Device type breakdown
        - Performance metrics
        - Trend analysis

        Args:
            db: Database session
            hostel_id: Hostel identifier
            time_range_days: Statistics time range in days
            include_device_breakdown: Whether to include device type breakdown

        Returns:
            PushStats: Enhanced push statistics

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")
        
        if time_range_days < 1 or time_range_days > 365:
            raise ValidationException("Time range must be between 1 and 365 days")

        with LoggingContext(
            channel="push_stats",
            hostel_id=str(hostel_id),
            time_range_days=time_range_days
        ):
            try:
                logger.debug(f"Retrieving push stats for hostel {hostel_id}")
                
                data = self.push_repo.get_stats_for_hostel(
                    db, 
                    hostel_id,
                    time_range_days=time_range_days,
                    include_device_breakdown=include_device_breakdown,
                )
                
                if not data:
                    logger.debug(f"No push stats found for hostel {hostel_id}, returning defaults")
                    return self._get_default_push_stats(hostel_id)
                
                stats = PushStats.model_validate(data)
                logger.debug(f"Push stats retrieved: {stats.total_sent} sent")
                
                return stats
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error retrieving push stats: {str(e)}")
                raise DatabaseException("Failed to retrieve push statistics") from e
            except Exception as e:
                logger.error(f"Unexpected error retrieving push stats: {str(e)}")
                raise

    def _get_default_push_stats(self, hostel_id: UUID) -> PushStats:
        """Get default push stats when no data is available."""
        return PushStats(
            hostel_id=hostel_id,
            total_sent=0,
            total_delivered=0,
            total_failed=0,
            total_opened=0,
            total_clicked=0,
            delivery_rate=0.0,
            open_rate=0.0,
            click_rate=0.0,
            device_breakdown={},
            platform_breakdown={},
            time_range_days=30,
            generated_at=datetime.utcnow(),
        )

    def get_push_delivery_status(
        self,
        db: Session,
        notification_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get detailed delivery status for a push notification.

        Args:
            db: Database session
            notification_id: Push notification ID

        Returns:
            Dict[str, Any]: Delivery status details

        Raises:
            ValidationException: For invalid notification ID
            DatabaseException: For database operation failures
        """
        if not notification_id:
            raise ValidationException("Notification ID is required")

        with LoggingContext(
            channel="push_delivery_status",
            notification_id=str(notification_id)
        ):
            try:
                logger.debug(f"Retrieving push delivery status for {notification_id}")
                
                status = self.push_repo.get_delivery_status(db, notification_id)
                if not status:
                    raise ValidationException("Push notification not found")
                
                return status
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error retrieving delivery status: {str(e)}")
                raise DatabaseException("Failed to retrieve delivery status") from e
            except Exception as e:
                logger.error(f"Unexpected error retrieving delivery status: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Enhanced utility methods
    # -------------------------------------------------------------------------

    def retry_failed_push(
        self,
        db: Session,
        notification_id: UUID,
        max_retries: int = 3,
    ) -> bool:
        """
        Retry a failed push notification with exponential backoff.

        Args:
            db: Database session
            notification_id: Failed notification ID
            max_retries: Maximum retry attempts

        Returns:
            bool: True if retry was scheduled

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if not notification_id:
            raise ValidationException("Notification ID is required")
        
        if max_retries < 1 or max_retries > 5:
            max_retries = 3

        with LoggingContext(
            channel="push_retry",
            notification_id=str(notification_id)
        ):
            try:
                logger.info(f"Retrying failed push notification {notification_id}")
                
                success = self.push_repo.schedule_retry(
                    db=db,
                    notification_id=notification_id,
                    max_retries=max_retries,
                    retry_delays=self._retry_delays,
                )
                
                if success:
                    logger.info("Push retry scheduled successfully")
                else:
                    logger.warning("Push retry could not be scheduled")
                
                return success
                
            except SQLAlchemyError as e:
                logger.error(f"Database error scheduling retry: {str(e)}")
                raise DatabaseException("Failed to schedule push retry") from e
            except Exception as e:
                logger.error(f"Unexpected error scheduling retry: {str(e)}")
                raise

    def test_device_connectivity(
        self,
        db: Session,
        device_token: str,
    ) -> Dict[str, Any]:
        """
        Test connectivity to a specific device token.

        Args:
            db: Database session
            device_token: Device token to test

        Returns:
            Dict[str, Any]: Connectivity test results

        Raises:
            ValidationException: For invalid device token
        """
        if not device_token:
            raise ValidationException("Device token is required")

        with LoggingContext(channel="device_connectivity_test", device_token=device_token[:10]):
            try:
                logger.info(f"Testing connectivity for device {device_token[:10]}...")
                
                # Validate device exists and is active
                device = self.device_repo.get_by_token(db, device_token)
                if not device:
                    return {
                        "status": "failed",
                        "reason": "device_not_found",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                
                if not device.is_active:
                    return {
                        "status": "failed",
                        "reason": "device_inactive",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                
                # Send test notification
                test_request = PushRequest(
                    device_token=device_token,
                    title="Test Notification",
                    body="This is a connectivity test",
                    data={"test": True},
                    priority="normal",
                )
                
                notification_id = self.send_push(
                    db=db,
                    request=test_request,
                    platform_optimizations=True,
                    validate_device=False,  # Already validated above
                )
                
                return {
                    "status": "sent",
                    "notification_id": str(notification_id),
                    "device_type": device.device_type,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                
            except Exception as e:
                logger.error(f"Error testing device connectivity: {str(e)}")
                return {
                    "status": "failed",
                    "reason": "test_error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }

    def get_push_analytics(
        self,
        db: Session,
        hostel_id: UUID,
        days_back: int = 7,
    ) -> Dict[str, Any]:
        """
        Get comprehensive push notification analytics.

        Args:
            db: Database session
            hostel_id: Hostel identifier
            days_back: Number of days to analyze

        Returns:
            Dict[str, Any]: Comprehensive analytics

        Raises:
            ValidationException: For invalid parameters
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")
        
        if days_back < 1 or days_back > 90:
            raise ValidationException("Days back must be between 1 and 90")

        with LoggingContext(
            channel="push_analytics",
            hostel_id=str(hostel_id),
            days_back=days_back
        ):
            try:
                logger.info(f"Generating push analytics for hostel {hostel_id}")
                
                analytics = self.push_repo.get_push_analytics(
                    db=db,
                    hostel_id=hostel_id,
                    days_back=days_back,
                )
                
                # Enhance with device statistics
                device_stats = self.device_repo.get_device_statistics(
                    db=db,
                    hostel_id=hostel_id,
                )
                
                analytics["device_statistics"] = device_stats
                analytics["generated_at"] = datetime.utcnow().isoformat()
                
                logger.info("Push analytics generated successfully")
                return analytics
                
            except Exception as e:
                logger.error(f"Error generating push analytics: {str(e)}")
                raise