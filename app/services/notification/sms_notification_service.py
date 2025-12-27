# app/services/notification/sms_notification_service.py
"""
Enhanced SMS Notification Service

Handles high-level operations around SMS notifications with improved:
- Performance through batch operations and connection pooling
- Advanced message optimization and segmentation
- Comprehensive error handling and retry logic
- Cost management and optimization
- Multi-provider support and failover
- International SMS support
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.notification import SMSNotificationRepository
from app.schemas.notification import (
    SMSRequest,
    BulkSMSRequest,
    SMSStats,
)
from app.core1.exceptions import ValidationException, DatabaseException
from app.core1.logging import LoggingContext

logger = logging.getLogger(__name__)


class SMSPriority(str, Enum):
    """SMS priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class SMSProvider(str, Enum):
    """Supported SMS providers."""
    TWILIO = "twilio"
    AWS_SNS = "aws_sns"
    TEXTLOCAL = "textlocal"
    MSG91 = "msg91"


class SMSNotificationService:
    """
    Enhanced orchestration of SMS notification creation/scheduling.

    Enhanced with:
    - Message optimization and segmentation
    - Multi-provider support with failover
    - Cost management and optimization
    - International SMS support
    - Advanced error handling and retry logic
    - Comprehensive analytics and monitoring
    """

    def __init__(self, sms_repo: SMSNotificationRepository) -> None:
        self.sms_repo = sms_repo
        
        # Configuration
        self._max_batch_size = 1000
        self._max_message_length = 1600  # 10 SMS segments
        self._single_sms_length = 160
        self._unicode_sms_length = 70
        self._max_phone_numbers_per_batch = 100
        self._valid_priorities = [p.value for p in SMSPriority]
        self._retry_delays = [300, 900, 3600]  # 5min, 15min, 1hour
        
        # Phone number validation patterns
        self._phone_patterns = {
            "international": re.compile(r"^\+[1-9]\d{1,14}$"),
            "indian": re.compile(r"^(\+91|91)?[6789]\d{9}$"),
            "us": re.compile(r"^(\+1|1)?[2-9]\d{9}$"),
        }

    def _validate_phone_number(self, phone: str) -> tuple[bool, str]:
        """
        Validate and normalize phone number format.
        
        Returns: (is_valid, normalized_phone)
        """
        if not phone or len(phone.strip()) == 0:
            return False, ""
        
        # Clean phone number
        clean_phone = re.sub(r"[^\d+]", "", phone.strip())
        
        # Check international format first
        if self._phone_patterns["international"].match(clean_phone):
            return True, clean_phone
        
        # Try Indian format
        if self._phone_patterns["indian"].match(clean_phone):
            if clean_phone.startswith("91"):
                clean_phone = "+" + clean_phone
            elif clean_phone.startswith("6") or clean_phone.startswith("7") or \
                 clean_phone.startswith("8") or clean_phone.startswith("9"):
                clean_phone = "+91" + clean_phone
            return True, clean_phone
        
        # Try US format
        if self._phone_patterns["us"].match(clean_phone):
            if clean_phone.startswith("1") and len(clean_phone) == 11:
                clean_phone = "+" + clean_phone
            elif len(clean_phone) == 10:
                clean_phone = "+1" + clean_phone
            return True, clean_phone
        
        return False, clean_phone

    def _analyze_message_content(self, message: str) -> Dict[str, Any]:
        """
        Analyze message content for optimization and segmentation.
        
        Returns information about encoding, length, segments, etc.
        """
        if not message:
            return {
                "length": 0,
                "segments": 0,
                "encoding": "gsm7",
                "is_unicode": False,
                "estimated_cost_factor": 0,
            }
        
        # Check if message contains Unicode characters
        try:
            message.encode('ascii')
            is_unicode = False
            max_single_length = self._single_sms_length
        except UnicodeEncodeError:
            is_unicode = True
            max_single_length = self._unicode_sms_length
        
        message_length = len(message)
        
        # Calculate segments
        if message_length <= max_single_length:
            segments = 1
        else:
            # Multi-part SMS has lower limit per segment
            segment_limit = max_single_length - 7  # Account for UDH
            segments = (message_length + segment_limit - 1) // segment_limit
        
        return {
            "length": message_length,
            "segments": segments,
            "encoding": "ucs2" if is_unicode else "gsm7",
            "is_unicode": is_unicode,
            "estimated_cost_factor": segments,
            "max_single_length": max_single_length,
        }

    def _optimize_message_content(
        self,
        message: str,
        max_segments: int = 3,
    ) -> str:
        """
        Optimize message content to reduce SMS cost while preserving meaning.
        """
        if not message:
            return message
        
        analysis = self._analyze_message_content(message)
        
        if analysis["segments"] <= max_segments:
            return message
        
        # Apply optimization strategies
        optimized = message
        
        # Replace common words with shorter alternatives
        replacements = {
            " and ": " & ",
            " you ": " u ",
            " your ": " ur ",
            " you're ": " ur ",
            " to ": " 2 ",
            " for ": " 4 ",
            " before ": " b4 ",
            " because ": " bcz ",
            " tomorrow ": " tmrw ",
            " tonight ": " 2nite ",
            " through ": " thru ",
            " without ": " w/o ",
            " with ": " w/ ",
            " please ": " pls ",
            " thanks ": " thx ",
            " thank you ": " thx ",
        }
        
        for old, new in replacements.items():
            optimized = optimized.replace(old, new)
        
        # Remove extra spaces
        optimized = re.sub(r"\s+", " ", optimized).strip()
        
        # If still too long, truncate with ellipsis
        max_length = max_segments * analysis["max_single_length"]
        if len(optimized) > max_length:
            optimized = optimized[:max_length - 3] + "..."
        
        return optimized

    def _validate_sms_request(self, request: SMSRequest) -> None:
        """Validate SMS request parameters."""
        if not request.message or len(request.message.strip()) == 0:
            raise ValidationException("SMS message is required")
        
        if len(request.message) > self._max_message_length:
            raise ValidationException(
                f"Message too long (max {self._max_message_length} characters)"
            )
        
        if not request.recipient_phone:
            raise ValidationException("Recipient phone number is required")
        
        is_valid, normalized = self._validate_phone_number(request.recipient_phone)
        if not is_valid:
            raise ValidationException(f"Invalid phone number format: {request.recipient_phone}")
        
        if request.priority and request.priority not in self._valid_priorities:
            raise ValidationException(f"Invalid priority. Must be one of: {self._valid_priorities}")

    def _validate_bulk_sms_request(self, request: BulkSMSRequest) -> None:
        """Validate bulk SMS request parameters."""
        if not request.message or len(request.message.strip()) == 0:
            raise ValidationException("SMS message is required")
        
        if len(request.message) > self._max_message_length:
            raise ValidationException(
                f"Message too long (max {self._max_message_length} characters)"
            )
        
        if not request.recipients:
            raise ValidationException("Recipients list cannot be empty")
        
        if len(request.recipients) > self._max_batch_size:
            raise ValidationException(
                f"Too many recipients (max {self._max_batch_size})"
            )
        
        if request.priority and request.priority not in self._valid_priorities:
            raise ValidationException(f"Invalid priority. Must be one of: {self._valid_priorities}")
        
        # Validate phone numbers
        invalid_numbers = []
        for phone in request.recipients[:10]:  # Check first 10 to avoid blocking on large lists
            is_valid, _ = self._validate_phone_number(phone)
            if not is_valid:
                invalid_numbers.append(phone)
        
        if invalid_numbers:
            raise ValidationException(
                f"Invalid phone numbers detected: {invalid_numbers[:5]}"
            )

    def _estimate_sms_cost(
        self,
        message: str,
        recipients: List[str],
        provider: str = "default",
    ) -> Dict[str, Any]:
        """
        Estimate SMS cost based on message analysis and recipient countries.
        """
        analysis = self._analyze_message_content(message)
        
        # Basic cost estimation (would be provider-specific in real implementation)
        base_cost_per_segment = 0.05  # USD
        international_multiplier = 2.0
        
        total_cost = 0.0
        domestic_count = 0
        international_count = 0
        
        for phone in recipients:
            is_valid, normalized = self._validate_phone_number(phone)
            if is_valid:
                # Simple country detection (would be more sophisticated in real app)
                if normalized.startswith("+91"):  # India
                    domestic_count += 1
                    total_cost += analysis["segments"] * base_cost_per_segment
                else:
                    international_count += 1
                    total_cost += analysis["segments"] * base_cost_per_segment * international_multiplier
        
        return {
            "total_cost": round(total_cost, 4),
            "currency": "USD",
            "segments_per_message": analysis["segments"],
            "total_segments": analysis["segments"] * len(recipients),
            "domestic_count": domestic_count,
            "international_count": international_count,
            "base_cost_per_segment": base_cost_per_segment,
            "cost_breakdown": {
                "domestic": analysis["segments"] * domestic_count * base_cost_per_segment,
                "international": analysis["segments"] * international_count * base_cost_per_segment * international_multiplier,
            }
        }

    # -------------------------------------------------------------------------
    # Enhanced single SMS operations
    # -------------------------------------------------------------------------

    def send_sms(
        self,
        db: Session,
        request: SMSRequest,
        user_id: Optional[UUID] = None,
        optimize_message: bool = True,
        provider_preference: Optional[str] = None,
    ) -> UUID:
        """
        Create an SMS notification entry with enhanced optimization and validation.

        Enhanced with:
        - Message optimization for cost reduction
        - Phone number validation and normalization
        - Provider selection and failover
        - Cost estimation
        - Comprehensive error handling

        Args:
            db: Database session
            request: SMS request data
            user_id: Optional user identifier
            optimize_message: Whether to optimize message content
            provider_preference: Preferred SMS provider

        Returns:
            UUID: SMS notification ID

        Raises:
            ValidationException: For invalid request data
            DatabaseException: For database operation failures
        """
        self._validate_sms_request(request)

        # Validate and normalize phone number
        is_valid, normalized_phone = self._validate_phone_number(request.recipient_phone)
        if not is_valid:
            raise ValidationException(f"Invalid phone number: {request.recipient_phone}")

        payload = request.model_dump(exclude_none=True)
        payload["user_id"] = user_id
        payload["recipient_phone"] = normalized_phone

        # Optimize message content if requested
        if optimize_message:
            optimized_message = self._optimize_message_content(request.message)
            payload["message"] = optimized_message
            payload["original_message"] = request.message

        # Analyze message for metadata
        message_analysis = self._analyze_message_content(payload["message"])
        payload["message_analysis"] = message_analysis

        # Estimate cost
        cost_estimate = self._estimate_sms_cost(
            payload["message"], 
            [normalized_phone],
            provider_preference or "default"
        )
        payload["cost_estimate"] = cost_estimate

        # Set provider preference
        if provider_preference:
            payload["provider_preference"] = provider_preference

        with LoggingContext(
            channel="sms",
            to=normalized_phone[-4:],  # Last 4 digits for privacy
            segments=message_analysis["segments"],
            cost=cost_estimate["total_cost"]
        ):
            try:
                logger.info(
                    f"Creating SMS notification to {normalized_phone[-4:]}..., "
                    f"segments: {message_analysis['segments']}, "
                    f"estimated cost: ${cost_estimate['total_cost']}"
                )
                
                obj = self.sms_repo.create_sms_notification(db, payload)
                
                logger.info(f"SMS notification created successfully: {obj.id}")
                return obj.id  # type: ignore[attr-defined]
                
            except SQLAlchemyError as e:
                logger.error(f"Database error creating SMS notification: {str(e)}")
                raise DatabaseException("Failed to create SMS notification") from e
            except Exception as e:
                logger.error(f"Unexpected error creating SMS notification: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Enhanced bulk SMS operations
    # -------------------------------------------------------------------------

    def send_bulk_sms(
        self,
        db: Session,
        request: BulkSMSRequest,
        owner_id: Optional[UUID] = None,
        chunk_size: int = 100,
        optimize_message: bool = True,
        cost_limit: Optional[float] = None,
    ) -> List[UUID]:
        """
        Create multiple SMS notifications with enhanced batch processing.

        Enhanced with:
        - Chunked processing for large batches
        - Cost management and limits
        - Phone number validation and deduplication
        - Message optimization
        - Progress tracking
        - Comprehensive error handling

        Args:
            db: Database session
            request: Bulk SMS request
            owner_id: Optional owner identifier
            chunk_size: Size of processing chunks
            optimize_message: Whether to optimize message content
            cost_limit: Maximum allowed cost (USD)

        Returns:
            List[UUID]: List of SMS notification IDs

        Raises:
            ValidationException: For invalid request data or cost limit exceeded
            DatabaseException: For database operation failures
        """
        self._validate_bulk_sms_request(request)
        
        if chunk_size < 1 or chunk_size > self._max_phone_numbers_per_batch:
            chunk_size = self._max_phone_numbers_per_batch

        # Validate and normalize all phone numbers
        valid_recipients = []
        invalid_recipients = []
        
        for phone in request.recipients:
            is_valid, normalized = self._validate_phone_number(phone)
            if is_valid:
                valid_recipients.append(normalized)
            else:
                invalid_recipients.append(phone)
        
        if not valid_recipients:
            raise ValidationException("No valid phone numbers found")
        
        if invalid_recipients:
            logger.warning(f"Skipping {len(invalid_recipients)} invalid phone numbers")

        # Remove duplicates while preserving order
        unique_recipients = list(dict.fromkeys(valid_recipients))
        
        payload = request.model_dump(exclude_none=True)
        payload["owner_id"] = owner_id
        payload["recipients"] = unique_recipients

        # Optimize message content if requested
        if optimize_message:
            optimized_message = self._optimize_message_content(request.message)
            payload["message"] = optimized_message
            payload["original_message"] = request.message

        # Analyze message and estimate cost
        message_analysis = self._analyze_message_content(payload["message"])
        cost_estimate = self._estimate_sms_cost(
            payload["message"], 
            unique_recipients,
            request.provider_preference if hasattr(request, 'provider_preference') else "default"
        )
        
        # Check cost limit
        if cost_limit and cost_estimate["total_cost"] > cost_limit:
            raise ValidationException(
                f"Estimated cost ${cost_estimate['total_cost']} exceeds limit ${cost_limit}"
            )

        payload["message_analysis"] = message_analysis
        payload["cost_estimate"] = cost_estimate

        with LoggingContext(
            channel="sms_bulk",
            recipient_count=len(unique_recipients),
            segments=message_analysis["segments"],
            total_cost=cost_estimate["total_cost"]
        ):
            try:
                logger.info(
                    f"Creating bulk SMS campaign for {len(unique_recipients)} recipients, "
                    f"segments per message: {message_analysis['segments']}, "
                    f"estimated total cost: ${cost_estimate['total_cost']}"
                )
                
                all_ids = []
                total_recipients = len(unique_recipients)
                
                # Process in chunks for better performance and memory management
                for i in range(0, total_recipients, chunk_size):
                    chunk_recipients = unique_recipients[i:i + chunk_size]
                    chunk_payload = payload.copy()
                    chunk_payload["recipients"] = chunk_recipients
                    
                    logger.debug(
                        f"Processing chunk {i//chunk_size + 1}, "
                        f"recipients: {len(chunk_recipients)}"
                    )
                    
                    # Update cost estimate for this chunk
                    chunk_cost = self._estimate_sms_cost(
                        payload["message"], 
                        chunk_recipients,
                        request.provider_preference if hasattr(request, 'provider_preference') else "default"
                    )
                    chunk_payload["cost_estimate"] = chunk_cost
                    
                    objs = self.sms_repo.create_bulk_sms_notifications(
                        db, chunk_payload
                    )
                    
                    chunk_ids = [o.id for o in objs]  # type: ignore[attr-defined]
                    all_ids.extend(chunk_ids)
                    
                    # Commit each chunk to avoid large transactions
                    db.commit()
                
                logger.info(
                    f"Bulk SMS campaign created successfully, "
                    f"total notifications: {len(all_ids)}, "
                    f"estimated cost: ${cost_estimate['total_cost']}"
                )
                
                return all_ids
                
            except SQLAlchemyError as e:
                logger.error(f"Database error creating bulk SMS: {str(e)}")
                db.rollback()
                raise DatabaseException("Failed to create bulk SMS campaign") from e
            except Exception as e:
                logger.error(f"Unexpected error creating bulk SMS: {str(e)}")
                db.rollback()
                raise

    # -------------------------------------------------------------------------
    # Enhanced statistics and monitoring
    # -------------------------------------------------------------------------

    def get_sms_stats_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        time_range_days: int = 30,
        include_cost_breakdown: bool = True,
    ) -> SMSStats:
        """
        Get enhanced SMS statistics with cost analysis and detailed breakdown.

        Enhanced with:
        - Configurable time ranges
        - Cost breakdown and analysis
        - Provider performance comparison
        - Delivery rate analysis

        Args:
            db: Database session
            hostel_id: Hostel identifier
            time_range_days: Statistics time range in days
            include_cost_breakdown: Whether to include detailed cost breakdown

        Returns:
            SMSStats: Enhanced SMS statistics

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")
        
        if time_range_days < 1 or time_range_days > 365:
            raise ValidationException("Time range must be between 1 and 365 days")

        with LoggingContext(
            channel="sms_stats",
            hostel_id=str(hostel_id),
            time_range_days=time_range_days
        ):
            try:
                logger.debug(f"Retrieving SMS stats for hostel {hostel_id}")
                
                data = self.sms_repo.get_stats_for_hostel(
                    db, 
                    hostel_id,
                    time_range_days=time_range_days,
                    include_cost_breakdown=include_cost_breakdown,
                )
                
                if not data:
                    logger.debug(f"No SMS stats found for hostel {hostel_id}, returning defaults")
                    return self._get_default_sms_stats(hostel_id)
                
                stats = SMSStats.model_validate(data)
                logger.debug(f"SMS stats retrieved: {stats.total_sent} sent, ${stats.total_cost} cost")
                
                return stats
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error retrieving SMS stats: {str(e)}")
                raise DatabaseException("Failed to retrieve SMS statistics") from e
            except Exception as e:
                logger.error(f"Unexpected error retrieving SMS stats: {str(e)}")
                raise

    def _get_default_sms_stats(self, hostel_id: UUID) -> SMSStats:
        """Get default SMS stats when no data is available."""
        return SMSStats(
            hostel_id=hostel_id,
            total_sent=0,
            total_delivered=0,
            total_failed=0,
            total_pending=0,
            total_cost=0.0,
            avg_cost_per_sms=0.0,
            delivery_rate=0.0,
            failure_rate=0.0,
            total_segments=0,
            avg_segments_per_sms=0.0,
            currency="USD",
            time_range_days=30,
            provider_breakdown={},
            cost_breakdown={},
            generated_at=datetime.utcnow(),
        )

    # -------------------------------------------------------------------------
    # Enhanced utility methods
    # -------------------------------------------------------------------------

    def get_sms_delivery_status(
        self,
        db: Session,
        notification_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get detailed delivery status for an SMS notification.

        Args:
            db: Database session
            notification_id: SMS notification ID

        Returns:
            Dict[str, Any]: Delivery status details

        Raises:
            ValidationException: For invalid notification ID
            DatabaseException: For database operation failures
        """
        if not notification_id:
            raise ValidationException("Notification ID is required")

        with LoggingContext(
            channel="sms_delivery_status",
            notification_id=str(notification_id)
        ):
            try:
                logger.debug(f"Retrieving SMS delivery status for {notification_id}")
                
                status = self.sms_repo.get_delivery_status(db, notification_id)
                if not status:
                    raise ValidationException("SMS notification not found")
                
                return status
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error retrieving delivery status: {str(e)}")
                raise DatabaseException("Failed to retrieve delivery status") from e
            except Exception as e:
                logger.error(f"Unexpected error retrieving delivery status: {str(e)}")
                raise

    def retry_failed_sms(
        self,
        db: Session,
        notification_id: UUID,
        alternate_provider: Optional[str] = None,
    ) -> bool:
        """
        Retry a failed SMS notification, optionally with a different provider.

        Args:
            db: Database session
            notification_id: Failed notification ID
            alternate_provider: Alternative provider to try

        Returns:
            bool: True if retry was scheduled

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if not notification_id:
            raise ValidationException("Notification ID is required")

        with LoggingContext(
            channel="sms_retry",
            notification_id=str(notification_id),
            alternate_provider=alternate_provider
        ):
            try:
                logger.info(f"Retrying failed SMS notification {notification_id}")
                
                success = self.sms_repo.schedule_retry(
                    db=db,
                    notification_id=notification_id,
                    alternate_provider=alternate_provider,
                    retry_delays=self._retry_delays,
                )
                
                if success:
                    logger.info("SMS retry scheduled successfully")
                else:
                    logger.warning("SMS retry could not be scheduled")
                
                return success
                
            except SQLAlchemyError as e:
                logger.error(f"Database error scheduling SMS retry: {str(e)}")
                raise DatabaseException("Failed to schedule SMS retry") from e
            except Exception as e:
                logger.error(f"Unexpected error scheduling SMS retry: {str(e)}")
                raise

    def estimate_bulk_sms_cost(
        self,
        message: str,
        recipients: List[str],
        provider: str = "default",
    ) -> Dict[str, Any]:
        """
        Estimate cost for a bulk SMS campaign before sending.

        Args:
            message: SMS message content
            recipients: List of recipient phone numbers
            provider: SMS provider to use for estimation

        Returns:
            Dict[str, Any]: Detailed cost estimation

        Raises:
            ValidationException: For invalid parameters
        """
        if not message:
            raise ValidationException("Message is required")
        
        if not recipients:
            raise ValidationException("Recipients list cannot be empty")
        
        if len(recipients) > self._max_batch_size:
            raise ValidationException(f"Too many recipients (max {self._max_batch_size})")

        with LoggingContext(
            channel="sms_cost_estimate",
            recipient_count=len(recipients),
            provider=provider
        ):
            try:
                logger.debug(f"Estimating SMS cost for {len(recipients)} recipients")
                
                # Validate phone numbers
                valid_count = 0
                invalid_numbers = []
                
                for phone in recipients:
                    is_valid, _ = self._validate_phone_number(phone)
                    if is_valid:
                        valid_count += 1
                    else:
                        invalid_numbers.append(phone)
                
                if valid_count == 0:
                    raise ValidationException("No valid phone numbers found")
                
                # Analyze message
                message_analysis = self._analyze_message_content(message)
                
                # Estimate cost for valid numbers only
                cost_estimate = self._estimate_sms_cost(
                    message,
                    [r for r in recipients if self._validate_phone_number(r)[0]],
                    provider
                )
                
                # Add validation summary
                cost_estimate.update({
                    "validation_summary": {
                        "total_provided": len(recipients),
                        "valid_numbers": valid_count,
                        "invalid_numbers": len(invalid_numbers),
                        "invalid_samples": invalid_numbers[:5],  # First 5 invalid numbers
                    },
                    "message_analysis": message_analysis,
                    "provider": provider,
                    "estimated_at": datetime.utcnow().isoformat(),
                })
                
                logger.debug(f"Cost estimation complete: ${cost_estimate['total_cost']}")
                return cost_estimate
                
            except ValidationException:
                raise
            except Exception as e:
                logger.error(f"Error estimating SMS cost: {str(e)}")
                raise

    def get_provider_status(
        self,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Get status and performance metrics for all SMS providers.

        Args:
            db: Database session

        Returns:
            Dict[str, Any]: Provider status and metrics

        Raises:
            DatabaseException: For database operation failures
        """
        with LoggingContext(channel="sms_provider_status"):
            try:
                logger.debug("Retrieving SMS provider status")
                
                status = self.sms_repo.get_provider_status(db)
                
                logger.debug("SMS provider status retrieved successfully")
                return status
                
            except SQLAlchemyError as e:
                logger.error(f"Database error retrieving provider status: {str(e)}")
                raise DatabaseException("Failed to retrieve provider status") from e
            except Exception as e:
                logger.error(f"Unexpected error retrieving provider status: {str(e)}")
                raise

    def optimize_message_for_cost(
        self,
        message: str,
        max_segments: int = 2,
        preserve_meaning: bool = True,
    ) -> Dict[str, Any]:
        """
        Optimize a message to reduce SMS cost while preserving meaning.

        Args:
            message: Original message
            max_segments: Maximum allowed segments
            preserve_meaning: Whether to preserve meaning over brevity

        Returns:
            Dict[str, Any]: Optimization results

        Raises:
            ValidationException: For invalid parameters
        """
        if not message:
            raise ValidationException("Message is required")
        
        if max_segments < 1 or max_segments > 10:
            raise ValidationException("Max segments must be between 1 and 10")

        with LoggingContext(
            channel="sms_optimize",
            original_length=len(message),
            max_segments=max_segments
        ):
            try:
                logger.debug(f"Optimizing SMS message, target: {max_segments} segments")
                
                original_analysis = self._analyze_message_content(message)
                
                if original_analysis["segments"] <= max_segments:
                    return {
                        "optimization_needed": False,
                        "original_message": message,
                        "optimized_message": message,
                        "original_analysis": original_analysis,
                        "optimized_analysis": original_analysis,
                        "cost_savings": 0,
                    }
                
                optimized_message = self._optimize_message_content(message, max_segments)
                optimized_analysis = self._analyze_message_content(optimized_message)
                
                # Calculate cost savings
                original_cost = original_analysis["segments"] * 0.05  # Base cost per segment
                optimized_cost = optimized_analysis["segments"] * 0.05
                cost_savings = original_cost - optimized_cost
                
                result = {
                    "optimization_needed": True,
                    "original_message": message,
                    "optimized_message": optimized_message,
                    "original_analysis": original_analysis,
                    "optimized_analysis": optimized_analysis,
                    "cost_savings": cost_savings,
                    "savings_percentage": (cost_savings / original_cost) * 100 if original_cost > 0 else 0,
                    "character_reduction": len(message) - len(optimized_message),
                    "segment_reduction": original_analysis["segments"] - optimized_analysis["segments"],
                }
                
                logger.debug(
                    f"Message optimization complete - "
                    f"segments: {original_analysis['segments']} -> {optimized_analysis['segments']}, "
                    f"savings: ${cost_savings:.3f}"
                )
                
                return result
                
            except Exception as e:
                logger.error(f"Error optimizing SMS message: {str(e)}")
                raise