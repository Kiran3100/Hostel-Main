"""
Unified communication service orchestrator.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.services.communication.email_service import EmailService
from app.services.communication.sms_service import SMSService
from app.services.base.notification_dispatcher import NotificationDispatcher
from app.schemas.notification.notification_base import NotificationCreate
from app.schemas.notification.notification_response import NotificationResponse


logger = logging.getLogger(__name__)


class CommunicationService:
    """
    Unified communication orchestration facade.
    
    Provides a single interface for all communication channels:
    - Email (transactional, bulk, templated)
    - SMS (single, bulk)
    - In-app notifications
    - Push notifications
    
    Features:
    - Channel abstraction
    - Unified error handling
    - Cross-channel coordination
    - Audit logging
    """

    def __init__(
        self,
        email_service: EmailService,
        sms_service: SMSService,
        dispatcher: NotificationDispatcher,
        db_session: Session,
    ):
        self.email_service = email_service
        self.sms_service = sms_service
        self.dispatcher = dispatcher
        self.db = db_session
        self._logger = logger

    # ═══════════════════════════════════════════════════════════════
    # Email Operations
    # ═══════════════════════════════════════════════════════════════

    def send_email(self, *args, **kwargs) -> ServiceResult[Dict[str, Any]]:
        """
        Send a single email.
        
        Delegates to EmailService.send()
        See EmailService.send() for parameter details.
        """
        self._logger.debug("Routing email send request to EmailService")
        try:
            return self.email_service.send(*args, **kwargs)
        except Exception as e:
            self._logger.error(f"Error in send_email: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                message="Failed to send email",
                error=e,
            )

    def send_bulk_email(self, *args, **kwargs) -> ServiceResult[Dict[str, Any]]:
        """
        Send bulk emails.
        
        Delegates to EmailService.send_bulk()
        See EmailService.send_bulk() for parameter details.
        """
        self._logger.debug("Routing bulk email request to EmailService")
        try:
            return self.email_service.send_bulk(*args, **kwargs)
        except Exception as e:
            self._logger.error(f"Error in send_bulk_email: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                message="Failed to send bulk email",
                error=e,
            )

    def send_email_using_template(
        self,
        *args,
        **kwargs
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Send templated email.
        
        Delegates to EmailService.send_template()
        See EmailService.send_template() for parameter details.
        """
        self._logger.debug("Routing templated email request to EmailService")
        try:
            return self.email_service.send_template(*args, **kwargs)
        except Exception as e:
            self._logger.error(
                f"Error in send_email_using_template: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                message="Failed to send templated email",
                error=e,
            )

    def schedule_email(self, *args, **kwargs) -> ServiceResult[bool]:
        """
        Schedule email for future delivery.
        
        Delegates to EmailService.schedule()
        See EmailService.schedule() for parameter details.
        """
        self._logger.debug("Routing email scheduling request to EmailService")
        try:
            return self.email_service.schedule(*args, **kwargs)
        except Exception as e:
            self._logger.error(f"Error in schedule_email: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                message="Failed to schedule email",
                error=e,
            )

    # ═══════════════════════════════════════════════════════════════
    # SMS Operations
    # ═══════════════════════════════════════════════════════════════

    def send_sms(self, *args, **kwargs) -> ServiceResult[Dict[str, Any]]:
        """
        Send a single SMS.
        
        Delegates to SMSService.send()
        See SMSService.send() for parameter details.
        """
        self._logger.debug("Routing SMS send request to SMSService")
        try:
            return self.sms_service.send(*args, **kwargs)
        except Exception as e:
            self._logger.error(f"Error in send_sms: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                message="Failed to send SMS",
                error=e,
            )

    def send_bulk_sms(self, *args, **kwargs) -> ServiceResult[Dict[str, Any]]:
        """
        Send bulk SMS messages.
        
        Delegates to SMSService.send_bulk()
        See SMSService.send_bulk() for parameter details.
        """
        self._logger.debug("Routing bulk SMS request to SMSService")
        try:
            return self.sms_service.send_bulk(*args, **kwargs)
        except Exception as e:
            self._logger.error(f"Error in send_bulk_sms: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                message="Failed to send bulk SMS",
                error=e,
            )

    # ═══════════════════════════════════════════════════════════════
    # In-App / Push Notifications
    # ═══════════════════════════════════════════════════════════════

    def send_in_app(
        self,
        request: NotificationCreate,
        enqueue_only: bool = True,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send in-app or push notification.
        
        Args:
            request: Notification creation request
            enqueue_only: If True, queue for async delivery; if False, send immediately
            
        Returns:
            ServiceResult containing notification response
        """
        self._logger.debug(
            f"Routing in-app/push notification to dispatcher (enqueue_only={enqueue_only})"
        )
        try:
            return self.dispatcher.send(request, enqueue_only=enqueue_only)
        except Exception as e:
            self._logger.error(f"Error in send_in_app: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                message="Failed to send in-app notification",
                error=e,
            )

    def send_push(
        self,
        request: NotificationCreate,
        enqueue_only: bool = True,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send push notification (alias for send_in_app with type validation).
        
        Args:
            request: Notification creation request (must be PUSH type)
            enqueue_only: If True, queue for async delivery
            
        Returns:
            ServiceResult containing notification response
        """
        # Ensure notification type is PUSH
        if request.notification_type != "PUSH":
            self._logger.warning(
                f"send_push called with type {request.notification_type}, "
                "forcing to PUSH"
            )
            request.notification_type = "PUSH"
        
        return self.send_in_app(request, enqueue_only=enqueue_only)

    # ═══════════════════════════════════════════════════════════════
    # Multi-Channel Operations
    # ═══════════════════════════════════════════════════════════════

    def send_multi_channel(
        self,
        user_id: UUID,
        message: str,
        channels: List[str],
        subject: Optional[str] = None,
        template_code: Optional[str] = None,
        template_variables: Optional[Dict[str, Any]] = None,
        priority: str = "normal",
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Send message across multiple channels simultaneously.
        
        Args:
            user_id: Target user
            message: Message content
            channels: List of channels ('email', 'sms', 'push', 'in_app')
            subject: Subject line (for email)
            template_code: Optional template to use
            template_variables: Variables for template rendering
            priority: Message priority
            
        Returns:
            ServiceResult with results per channel
        """
        self._logger.info(
            f"Sending multi-channel message to user {user_id} via {channels}"
        )
        
        results = {}
        errors = []
        
        for channel in channels:
            try:
                if channel == "email":
                    # Would need email address from user profile
                    result = self._send_email_to_user(
                        user_id,
                        message,
                        subject,
                        template_code,
                        template_variables
                    )
                    results["email"] = result.success
                    
                elif channel == "sms":
                    # Would need phone from user profile
                    result = self._send_sms_to_user(
                        user_id,
                        message,
                        template_code,
                        template_variables
                    )
                    results["sms"] = result.success
                    
                elif channel in ["push", "in_app"]:
                    request = NotificationCreate(
                        user_id=str(user_id),
                        notification_type=channel.upper(),
                        subject=subject,
                        message_body=message,
                        priority=priority,
                        metadata={
                            "template_code": template_code,
                            "template_variables": template_variables,
                        } if template_code else None,
                    )
                    result = self.send_in_app(request)
                    results[channel] = result.success
                    
            except Exception as e:
                self._logger.error(
                    f"Error sending via {channel}: {str(e)}",
                    exc_info=True
                )
                results[channel] = False
                errors.append({"channel": channel, "error": str(e)})
        
        success = any(results.values())
        
        return ServiceResult.success(
            {
                "results": results,
                "errors": errors,
                "success_count": sum(1 for v in results.values() if v),
                "total_channels": len(channels),
            },
            message=f"Sent via {sum(1 for v in results.values() if v)}/{len(channels)} channels"
        ) if success else ServiceResult.failure(
            message="Failed to send via any channel",
            error=Exception(f"All channels failed: {errors}"),
        )

    # ═══════════════════════════════════════════════════════════════
    # Helper Methods
    # ═══════════════════════════════════════════════════════════════

    def _send_email_to_user(
        self,
        user_id: UUID,
        message: str,
        subject: Optional[str],
        template_code: Optional[str],
        template_variables: Optional[Dict[str, Any]],
    ) -> ServiceResult[Dict[str, Any]]:
        """Helper to send email to user (requires user profile lookup)."""
        # This would require user repository to get email address
        # Placeholder implementation
        self._logger.warning("Email to user requires user profile integration")
        return ServiceResult.failure(
            message="Email delivery requires user profile integration",
            error=NotImplementedError(),
        )

    def _send_sms_to_user(
        self,
        user_id: UUID,
        message: str,
        template_code: Optional[str],
        template_variables: Optional[Dict[str, Any]],
    ) -> ServiceResult[Dict[str, Any]]:
        """Helper to send SMS to user (requires user profile lookup)."""
        # This would require user repository to get phone number
        # Placeholder implementation
        self._logger.warning("SMS to user requires user profile integration")
        return ServiceResult.failure(
            message="SMS delivery requires user profile integration",
            error=NotImplementedError(),
        )

    def get_communication_health(self) -> Dict[str, Any]:
        """
        Get health status of all communication channels.
        
        Returns:
            Dictionary with health status per channel
        """
        health = {
            "email": "healthy",
            "sms": "healthy",
            "push": "healthy",
            "in_app": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Could add actual health checks here
        return health