# app/services/notification/notification_service.py
"""
Enhanced Notification Service (Facade)

Provides a unified high-level API over all notification channels with improved:
- Performance through intelligent routing and batching
- Error handling with comprehensive fallbacks
- Transaction management and consistency
- Real-time delivery coordination
- Analytics and monitoring integration
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List, Union
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.notification import (
    NotificationCreate,
    NotificationResponse,
    NotificationDetail,
    EmailRequest,
    SMSRequest,
    PushRequest,
    NotificationRoute,
)
from app.services.notification.in_app_notification_service import InAppNotificationService
from app.services.notification.email_notification_service import EmailNotificationService
from app.services.notification.sms_notification_service import SMSNotificationService
from app.services.notification.push_notification_service import PushNotificationService
from app.services.notification.notification_routing_service import NotificationRoutingService
from app.services.notification.notification_queue_service import NotificationQueueService
from app.core1.exceptions import ValidationException, DatabaseException
from app.core1.logging import LoggingContext

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Enhanced facade over all notification services.

    Enhanced with:
    - Intelligent routing and channel selection
    - Transaction management and rollback
    - Performance optimization
    - Real-time delivery coordination
    - Comprehensive error handling
    - Analytics integration
    """

    def __init__(
        self,
        in_app_service: InAppNotificationService,
        email_service: EmailNotificationService,
        sms_service: SMSNotificationService,
        push_service: PushNotificationService,
        routing_service: NotificationRoutingService,
        queue_service: NotificationQueueService,
    ) -> None:
        self.in_app_service = in_app_service
        self.email_service = email_service
        self.sms_service = sms_service
        self.push_service = push_service
        self.routing_service = routing_service
        self.queue_service = queue_service
        
        # Configuration
        self._max_recipients_per_batch = 100
        self._default_priority = "normal"
        self._valid_priorities = ["low", "normal", "high", "urgent"]
        self._retry_failed_channels = True

    def _validate_event_parameters(
        self,
        event_type: str,
        hostel_id: UUID,
        base_request: NotificationCreate
    ) -> None:
        """Validate notification event parameters."""
        if not event_type or len(event_type.strip()) == 0:
            raise ValidationException("Event type is required")
        
        if not hostel_id:
            raise ValidationException("Hostel ID is required")
        
        if not base_request.title or len(base_request.title.strip()) == 0:
            raise ValidationException("Notification title is required")
        
        if not base_request.user_id:
            raise ValidationException("User ID is required in notification")

    def _normalize_priority(self, priority: Optional[str]) -> str:
        """Normalize and validate priority."""
        if not priority:
            return self._default_priority
        
        if priority not in self._valid_priorities:
            logger.warning(f"Invalid priority '{priority}', using default")
            return self._default_priority
        
        return priority

    def _determine_delivery_strategy(
        self,
        route: NotificationRoute,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Determine optimal delivery strategy based on routing and context.
        
        Returns strategy configuration including:
        - Channel priorities
        - Batch sizes
        - Delivery timing
        - Fallback options
        """
        strategy = {
            "channels": [],
            "batch_size": self._max_recipients_per_batch,
            "immediate_delivery": [],
            "queued_delivery": [],
            "realtime_channels": ["in_app", "push"],
            "async_channels": ["email", "sms"],
        }
        
        priority = context.get("priority", "normal")
        
        # Determine channel processing order
        for channel in route.primary_channels:
            channel_config = {
                "name": channel,
                "priority": priority,
                "recipients": route.primary_recipients,
                "immediate": channel in strategy["realtime_channels"] or priority in ["high", "urgent"],
            }
            
            if channel_config["immediate"]:
                strategy["immediate_delivery"].append(channel_config)
            else:
                strategy["queued_delivery"].append(channel_config)
            
            strategy["channels"].append(channel_config)
        
        # Adjust batch size based on priority
        if priority == "urgent":
            strategy["batch_size"] = min(50, self._max_recipients_per_batch)
        elif priority == "high":
            strategy["batch_size"] = min(75, self._max_recipients_per_batch)
        
        return strategy

    # -------------------------------------------------------------------------
    # Enhanced unified notification sending
    # -------------------------------------------------------------------------

    def send_notification(
        self,
        db: Session,
        base_request: NotificationCreate,
        event_type: str,
        hostel_id: UUID,
        context: Optional[Dict[str, Any]] = None,
        priority: Optional[str] = None,
        template_code: Optional[str] = None,
        template_variables: Optional[Dict[str, Any]] = None,
    ) -> NotificationResponse:
        """
        Enhanced high-level notification entrypoint with intelligent routing.

        Enhanced with:
        - Intelligent channel selection
        - Transaction management
        - Performance optimization
        - Error recovery
        - Real-time coordination

        Args:
            db: Database session
            base_request: Base notification data
            event_type: Type of event triggering notification
            hostel_id: Hostel identifier
            context: Additional context for routing
            priority: Notification priority override
            template_code: Template for content generation
            template_variables: Variables for template rendering

        Returns:
            NotificationResponse: Primary notification response

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        # Validate parameters
        self._validate_event_parameters(event_type, hostel_id, base_request)
        
        priority = self._normalize_priority(priority or base_request.priority)
        context = context or {}
        context.update({
            "priority": priority,
            "template_code": template_code,
            "template_variables": template_variables or {},
            "timestamp": datetime.utcnow().isoformat(),
        })

        with LoggingContext(
            channel="notification_send",
            event_type=event_type,
            hostel_id=str(hostel_id),
            user_id=str(base_request.user_id),
            priority=priority
        ):
            try:
                logger.info(
                    f"Sending notification for event '{event_type}', "
                    f"user: {base_request.user_id}, priority: {priority}"
                )
                
                # Step 1: Route notification to determine channels and recipients
                route = self.routing_service.route_notification(
                    db=db,
                    event_type=event_type,
                    hostel_id=hostel_id,
                    payload=context,
                    priority=priority,
                )
                
                # Step 2: Determine delivery strategy
                strategy = self._determine_delivery_strategy(route, context)
                
                # Step 3: Create primary in-app notification
                in_app_notification = self._create_in_app_notification(
                    db=db,
                    base_request=base_request,
                    route=route,
                    context=context,
                )
                
                # Step 4: Process immediate delivery channels
                immediate_results = self._process_immediate_channels(
                    db=db,
                    strategy=strategy,
                    route=route,
                    base_request=base_request,
                    context=context,
                )
                
                # Step 5: Queue asynchronous delivery channels
                queued_results = self._process_queued_channels(
                    db=db,
                    strategy=strategy,
                    route=route,
                    base_request=base_request,
                    context=context,
                )
                
                # Step 6: Set up escalation if configured
                if route.escalation_path:
                    self._schedule_escalation(
                        db=db,
                        notification_id=in_app_notification.id,
                        escalation_path=route.escalation_path,
                        context=context,
                    )
                
                # Update notification with delivery metadata
                self._update_notification_metadata(
                    db=db,
                    notification_id=in_app_notification.id,
                    delivery_results={
                        "immediate_channels": immediate_results,
                        "queued_channels": queued_results,
                        "routing_metadata": route.routing_metadata,
                        "strategy": strategy,
                    }
                )
                
                logger.info(
                    f"Notification sent successfully - "
                    f"immediate: {len(immediate_results)}, "
                    f"queued: {len(queued_results)} channels"
                )
                
                return in_app_notification
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error sending notification: {str(e)}")
                db.rollback()
                raise DatabaseException("Failed to send notification") from e
            except Exception as e:
                logger.error(f"Unexpected error sending notification: {str(e)}")
                db.rollback()
                raise

    def _create_in_app_notification(
        self,
        db: Session,
        base_request: NotificationCreate,
        route: NotificationRoute,
        context: Dict[str, Any],
    ) -> NotificationResponse:
        """Create the primary in-app notification."""
        # Enhance notification payload
        notif_payload = base_request.model_dump(exclude_none=True)
        notif_payload.update({
            "hostel_id": route.hostel_id,
            "priority": context["priority"],
            "category": context.get("event_type", "general"),
            "metadata": {
                "event_type": route.event_type,
                "routing_info": route.routing_metadata,
                "delivery_channels": route.primary_channels,
            }
        })

        return self.in_app_service.create_notification(
            db=db,
            request=NotificationCreate(**notif_payload),
            send_realtime=True,
        )

    def _process_immediate_channels(
        self,
        db: Session,
        strategy: Dict[str, Any],
        route: NotificationRoute,
        base_request: NotificationCreate,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Process channels that require immediate delivery."""
        results = []
        
        for channel_config in strategy["immediate_delivery"]:
            try:
                channel_name = channel_config["name"]
                logger.debug(f"Processing immediate channel: {channel_name}")
                
                if channel_name == "push":
                    result = self._send_push_notification(
                        db=db,
                        recipients=channel_config["recipients"],
                        base_request=base_request,
                        context=context,
                    )
                elif channel_name == "email" and context.get("priority") == "urgent":
                    # Urgent emails are sent immediately
                    result = self._send_email_notification(
                        db=db,
                        recipients=channel_config["recipients"],
                        base_request=base_request,
                        context=context,
                        immediate=True,
                    )
                else:
                    # Skip non-immediate channels
                    continue
                
                results.append({
                    "channel": channel_name,
                    "status": "sent",
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                
            except Exception as e:
                logger.error(f"Error processing immediate channel {channel_name}: {str(e)}")
                results.append({
                    "channel": channel_name,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                })
                
                # Continue with other channels
                continue
        
        return results

    def _process_queued_channels(
        self,
        db: Session,
        strategy: Dict[str, Any],
        route: NotificationRoute,
        base_request: NotificationCreate,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Process channels that will be delivered asynchronously."""
        results = []
        
        for channel_config in strategy["queued_delivery"]:
            try:
                channel_name = channel_config["name"]
                logger.debug(f"Queueing channel: {channel_name}")
                
                if channel_name == "email":
                    result = self._send_email_notification(
                        db=db,
                        recipients=channel_config["recipients"],
                        base_request=base_request,
                        context=context,
                        immediate=False,
                    )
                elif channel_name == "sms":
                    result = self._send_sms_notification(
                        db=db,
                        recipients=channel_config["recipients"],
                        base_request=base_request,
                        context=context,
                    )
                elif channel_name == "webhook":
                    result = self._send_webhook_notification(
                        db=db,
                        recipients=channel_config["recipients"],
                        base_request=base_request,
                        context=context,
                    )
                else:
                    # Unknown channel
                    logger.warning(f"Unknown channel: {channel_name}")
                    continue
                
                results.append({
                    "channel": channel_name,
                    "status": "queued",
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                
            except Exception as e:
                logger.error(f"Error queueing channel {channel_name}: {str(e)}")
                results.append({
                    "channel": channel_name,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                })
                
                # Continue with other channels
                continue
        
        return results

    def _send_email_notification(
        self,
        db: Session,
        recipients: List[str],
        base_request: NotificationCreate,
        context: Dict[str, Any],
        immediate: bool = False,
    ) -> Union[UUID, List[UUID]]:
        """Send email notification to recipients."""
        template_code = context.get("template_code")
        template_vars = context.get("template_variables", {})
        
        if len(recipients) == 1:
            # Single email
            email_request = EmailRequest(
                recipient_email=recipients[0],  # Assume first recipient is email
                subject=base_request.title,
                content=base_request.content,
                template_code=template_code,
                template_variables=template_vars,
                priority=context["priority"],
            )
            
            return self.email_service.send_email(
                db=db,
                request=email_request,
                user_id=base_request.user_id,
                priority=context["priority"],
            )
        else:
            # Bulk email
            from app.schemas.notification import BulkEmailRequest
            
            bulk_request = BulkEmailRequest(
                recipients=recipients,
                subject=base_request.title,
                content=base_request.content,
                template_code=template_code,
                template_variables=template_vars,
                priority=context["priority"],
            )
            
            return self.email_service.send_bulk_email(
                db=db,
                request=bulk_request,
                owner_id=base_request.user_id,
            )

    def _send_sms_notification(
        self,
        db: Session,
        recipients: List[str],
        base_request: NotificationCreate,
        context: Dict[str, Any],
    ) -> Union[UUID, List[UUID]]:
        """Send SMS notification to recipients."""
        if len(recipients) == 1:
            # Single SMS
            sms_request = SMSRequest(
                recipient_phone=recipients[0],  # Assume recipient is phone number
                message=f"{base_request.title}\n{base_request.content}"[:160],  # SMS limit
                template_code=context.get("template_code"),
                template_variables=context.get("template_variables", {}),
            )
            
            return self.sms_service.send_sms(
                db=db,
                request=sms_request,
                user_id=base_request.user_id,
            )
        else:
            # Bulk SMS
            from app.schemas.notification import BulkSMSRequest
            
            bulk_request = BulkSMSRequest(
                recipients=recipients,
                message=f"{base_request.title}\n{base_request.content}"[:160],
                template_code=context.get("template_code"),
                template_variables=context.get("template_variables", {}),
            )
            
            return self.sms_service.send_bulk_sms(
                db=db,
                request=bulk_request,
                owner_id=base_request.user_id,
            )

    def _send_push_notification(
        self,
        db: Session,
        recipients: List[str],
        base_request: NotificationCreate,
        context: Dict[str, Any],
    ) -> Union[UUID, List[UUID]]:
        """Send push notification to recipients."""
        # Convert role-based recipients to user IDs (simplified)
        user_ids = [base_request.user_id]  # In real implementation, resolve roles to user IDs
        
        if len(user_ids) == 1:
            # Single push
            push_request = PushRequest(
                user_id=user_ids[0],
                title=base_request.title,
                body=base_request.content,
                data=context.get("template_variables", {}),
                priority=context["priority"],
            )
            
            return self.push_service.send_push(
                db=db,
                request=push_request,
            )
        else:
            # Bulk push
            from app.schemas.notification import BulkPushRequest
            
            bulk_request = BulkPushRequest(
                user_ids=user_ids,
                title=base_request.title,
                body=base_request.content,
                data=context.get("template_variables", {}),
                priority=context["priority"],
            )
            
            return self.push_service.send_bulk_push(
                db=db,
                request=bulk_request,
            )

    def _send_webhook_notification(
        self,
        db: Session,
        recipients: List[str],
        base_request: NotificationCreate,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send webhook notification (placeholder)."""
        # This would integrate with a webhook service
        return {
            "webhook_ids": [],
            "status": "queued",
            "recipients": recipients,
        }

    def _schedule_escalation(
        self,
        db: Session,
        notification_id: UUID,
        escalation_path: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> None:
        """Schedule escalation notifications."""
        try:
            logger.info(f"Scheduling {len(escalation_path)} escalation levels")
            
            for level_config in escalation_path:
                # Queue escalation for future processing
                self.queue_service.enqueue_notification(
                    db=db,
                    notification_id=notification_id,
                    priority="escalation",
                    scheduled_for=datetime.utcnow().replace(
                        hour=datetime.utcnow().hour + int(level_config["trigger_after_hours"])
                    ),
                )
            
            logger.info("Escalation scheduled successfully")
            
        except Exception as e:
            logger.error(f"Error scheduling escalation: {str(e)}")
            # Don't fail the main notification for escalation errors

    def _update_notification_metadata(
        self,
        db: Session,
        notification_id: UUID,
        delivery_results: Dict[str, Any],
    ) -> None:
        """Update notification with delivery metadata."""
        try:
            from app.schemas.notification import NotificationUpdate
            
            update_request = NotificationUpdate(
                metadata=delivery_results
            )
            
            self.in_app_service.update_notification(
                db=db,
                notification_id=notification_id,
                request=update_request,
            )
            
        except Exception as e:
            logger.warning(f"Failed to update notification metadata: {str(e)}")
            # Don't fail for metadata update errors

    # -------------------------------------------------------------------------
    # Enhanced retrieval and management
    # -------------------------------------------------------------------------

    def get_notification_detail(
        self,
        db: Session,
        notification_id: UUID,
        user_id: Optional[UUID] = None,
        include_delivery_status: bool = True,
    ) -> NotificationDetail:
        """
        Get comprehensive notification details with delivery status.

        Enhanced with:
        - Delivery status aggregation
        - Performance optimization
        - Access validation

        Args:
            db: Database session
            notification_id: Notification identifier
            user_id: User identifier for access validation
            include_delivery_status: Whether to include delivery status

        Returns:
            NotificationDetail: Comprehensive notification details

        Raises:
            ValidationException: For invalid parameters or access denied
            DatabaseException: For database operation failures
        """
        with LoggingContext(
            channel="notification_detail",
            notification_id=str(notification_id),
            user_id=str(user_id) if user_id else None
        ):
            try:
                logger.debug(f"Retrieving notification detail {notification_id}")
                
                detail = self.in_app_service.get_notification(
                    db=db,
                    notification_id=notification_id,
                    user_id=user_id,
                    mark_as_read=True,  # Auto-mark as read when viewing details
                )
                
                # Enhance with delivery status if requested
                if include_delivery_status:
                    detail = self._enhance_with_delivery_status(db, detail)
                
                logger.debug("Notification detail retrieved successfully")
                return detail
                
            except ValidationException:
                raise
            except Exception as e:
                logger.error(f"Error retrieving notification detail: {str(e)}")
                raise

    def _enhance_with_delivery_status(
        self,
        db: Session,
        detail: NotificationDetail,
    ) -> NotificationDetail:
        """Enhance notification detail with delivery status from all channels."""
        try:
            # Get delivery status from all channels
            delivery_status = {
                "email": self._get_email_delivery_status(db, detail.id),
                "sms": self._get_sms_delivery_status(db, detail.id),
                "push": self._get_push_delivery_status(db, detail.id),
                "summary": {
                    "total_channels": 0,
                    "successful_deliveries": 0,
                    "failed_deliveries": 0,
                    "pending_deliveries": 0,
                }
            }
            
            # Calculate summary
            for channel, status in delivery_status.items():
                if channel != "summary" and status:
                    delivery_status["summary"]["total_channels"] += 1
                    if status.get("status") == "delivered":
                        delivery_status["summary"]["successful_deliveries"] += 1
                    elif status.get("status") == "failed":
                        delivery_status["summary"]["failed_deliveries"] += 1
                    else:
                        delivery_status["summary"]["pending_deliveries"] += 1
            
            # Add to metadata
            if not detail.metadata:
                detail.metadata = {}
            detail.metadata["delivery_status"] = delivery_status
            
        except Exception as e:
            logger.warning(f"Failed to enhance with delivery status: {str(e)}")
        
        return detail

    def _get_email_delivery_status(self, db: Session, notification_id: UUID) -> Optional[Dict[str, Any]]:
        """Get email delivery status for notification."""
        try:
            return self.email_service.get_email_status(db, notification_id)
        except Exception:
            return None

    def _get_sms_delivery_status(self, db: Session, notification_id: UUID) -> Optional[Dict[str, Any]]:
        """Get SMS delivery status for notification."""
        try:
            # Would be implemented in SMS service
            return None
        except Exception:
            return None

    def _get_push_delivery_status(self, db: Session, notification_id: UUID) -> Optional[Dict[str, Any]]:
        """Get push delivery status for notification."""
        try:
            # Would be implemented in push service
            return None
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # Batch operations for performance
    # -------------------------------------------------------------------------

    def send_bulk_notifications(
        self,
        db: Session,
        notifications: List[Dict[str, Any]],
        batch_size: int = 50,
    ) -> List[NotificationResponse]:
        """
        Send multiple notifications efficiently in batches.

        Args:
            db: Database session
            notifications: List of notification data
            batch_size: Size of processing batches

        Returns:
            List[NotificationResponse]: List of sent notifications

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if not notifications:
            return []
        
        if len(notifications) > 1000:
            raise ValidationException("Cannot send more than 1000 notifications at once")
        
        if batch_size < 1 or batch_size > 100:
            batch_size = 50

        with LoggingContext(
            channel="bulk_notifications",
            count=len(notifications),
            batch_size=batch_size
        ):
            try:
                logger.info(f"Sending {len(notifications)} notifications in batches of {batch_size}")
                
                results = []
                for i in range(0, len(notifications), batch_size):
                    batch = notifications[i:i + batch_size]
                    logger.debug(f"Processing batch {i//batch_size + 1}, size: {len(batch)}")
                    
                    batch_results = []
                    for notif_data in batch:
                        try:
                            result = self.send_notification(
                                db=db,
                                base_request=NotificationCreate(**notif_data["base_request"]),
                                event_type=notif_data["event_type"],
                                hostel_id=notif_data["hostel_id"],
                                context=notif_data.get("context"),
                                priority=notif_data.get("priority"),
                            )
                            batch_results.append(result)
                            
                        except Exception as e:
                            logger.error(f"Failed to send notification in batch: {str(e)}")
                            # Continue with other notifications
                            continue
                    
                    results.extend(batch_results)
                    
                    # Commit each batch
                    db.commit()
                
                logger.info(f"Bulk notifications complete - sent: {len(results)}")
                return results
                
            except Exception as e:
                logger.error(f"Error in bulk notifications: {str(e)}")
                db.rollback()
                raise

    # -------------------------------------------------------------------------
    # Analytics and monitoring
    # -------------------------------------------------------------------------

    def get_notification_analytics(
        self,
        db: Session,
        hostel_id: UUID,
        days_back: int = 7,
    ) -> Dict[str, Any]:
        """
        Get comprehensive notification analytics.

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
            channel="notification_analytics",
            hostel_id=str(hostel_id),
            days_back=days_back
        ):
            try:
                logger.info(f"Generating notification analytics for hostel {hostel_id}")
                
                analytics = {
                    "hostel_id": str(hostel_id),
                    "period_days": days_back,
                    "generated_at": datetime.utcnow().isoformat(),
                    "email_stats": self.email_service.get_email_stats_for_hostel(db, hostel_id),
                    "sms_stats": self.sms_service.get_sms_stats_for_hostel(db, hostel_id),
                    "push_stats": self.push_service.get_push_stats_for_hostel(db, hostel_id),
                    "queue_stats": self.queue_service.get_queue_stats(db, days_back * 24),
                    "routing_analytics": self.routing_service.get_routing_analytics(db, hostel_id, days_back),
                }
                
                # Add summary calculations
                analytics["summary"] = self._calculate_analytics_summary(analytics)
                
                logger.info("Notification analytics generated successfully")
                return analytics
                
            except Exception as e:
                logger.error(f"Error generating analytics: {str(e)}")
                raise

    def _calculate_analytics_summary(self, analytics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate summary metrics from detailed analytics."""
        try:
            email_stats = analytics["email_stats"]
            sms_stats = analytics["sms_stats"]
            push_stats = analytics["push_stats"]
            
            return {
                "total_notifications_sent": (
                    email_stats.total_sent +
                    sms_stats.total_sent +
                    push_stats.total_sent
                ),
                "overall_delivery_rate": self._calculate_weighted_average([
                    (email_stats.delivery_rate, email_stats.total_sent),
                    (sms_stats.delivery_rate, sms_stats.total_sent),
                    (push_stats.delivery_rate, push_stats.total_sent),
                ]),
                "channel_performance": {
                    "email": {
                        "sent": email_stats.total_sent,
                        "delivery_rate": email_stats.delivery_rate,
                        "open_rate": email_stats.open_rate,
                    },
                    "sms": {
                        "sent": sms_stats.total_sent,
                        "delivery_rate": sms_stats.delivery_rate,
                        "cost": sms_stats.total_cost,
                    },
                    "push": {
                        "sent": push_stats.total_sent,
                        "delivery_rate": push_stats.delivery_rate,
                        "open_rate": push_stats.open_rate,
                    },
                },
            }
            
        except Exception as e:
            logger.warning(f"Error calculating analytics summary: {str(e)}")
            return {"error": "Failed to calculate summary"}

    def _calculate_weighted_average(self, values_and_weights: List[tuple[float, int]]) -> float:
        """Calculate weighted average of values."""
        total_weighted_value = sum(value * weight for value, weight in values_and_weights)
        total_weight = sum(weight for _, weight in values_and_weights)
        
        return total_weighted_value / total_weight if total_weight > 0 else 0.0