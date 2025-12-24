"""
Webhook service: inbound (verify/process) and outbound (deliver/retry) webhooks.

Manages webhook lifecycle including registration, verification, delivery,
retry logic, and event tracking across all integration providers.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import UUID
import logging
import hashlib
import hmac

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService, ServiceResult, ServiceError, 
    ErrorCode, ErrorSeverity
)
from app.repositories.integrations import APIIntegrationRepository
from app.models.integrations.api_integration import APIIntegration

logger = logging.getLogger(__name__)


class WebhookService(BaseService[APIIntegration, APIIntegrationRepository]):
    """
    Webhook handling across providers.
    
    Features:
    - Webhook registration and management
    - Signature verification for security
    - Inbound webhook processing
    - Outbound webhook delivery with retry
    - Event filtering and routing
    - Delivery tracking and analytics
    """

    # Webhook delivery states
    DELIVERY_PENDING = "pending"
    DELIVERY_PROCESSING = "processing"
    DELIVERY_SUCCESS = "success"
    DELIVERY_FAILED = "failed"
    DELIVERY_RETRYING = "retrying"

    def __init__(
        self, 
        repository: APIIntegrationRepository, 
        db_session: Session,
        max_retries: int = 5,
        retry_backoff_base: int = 2,
        initial_retry_delay: int = 60,
    ):
        """
        Initialize webhook service.
        
        Args:
            repository: API integration repository
            db_session: SQLAlchemy database session
            max_retries: Maximum retry attempts for failed deliveries
            retry_backoff_base: Exponential backoff base multiplier
            initial_retry_delay: Initial retry delay in seconds
        """
        super().__init__(repository, db_session)
        self._max_retries = max_retries
        self._retry_backoff_base = retry_backoff_base
        self._initial_retry_delay = initial_retry_delay
        
        logger.info("WebhookService initialized")

    def _validate_webhook_config(
        self,
        provider: str,
        callback_url: str,
        events: List[str],
    ) -> ServiceResult[bool]:
        """
        Validate webhook configuration.
        
        Args:
            provider: Provider identifier
            callback_url: Webhook callback URL
            events: List of event types
            
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
        
        if not callback_url or not isinstance(callback_url, str):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Callback URL must be a non-empty string",
                    severity=ErrorSeverity.MEDIUM
                )
            )
        
        # Validate URL format
        if not callback_url.startswith(("http://", "https://")):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Callback URL must start with http:// or https://",
                    severity=ErrorSeverity.MEDIUM,
                    context={"callback_url": callback_url}
                )
            )
        
        # Validate events list
        if not events or not isinstance(events, list) or len(events) == 0:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Events must be a non-empty list",
                    severity=ErrorSeverity.MEDIUM
                )
            )
        
        # Check for invalid event names
        invalid_events = [e for e in events if not isinstance(e, str) or not e]
        if invalid_events:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="All events must be non-empty strings",
                    severity=ErrorSeverity.MEDIUM,
                    context={"invalid_events": invalid_events}
                )
            )
        
        return ServiceResult.success(True)

    def _generate_webhook_secret(self) -> str:
        """
        Generate a secure webhook secret.
        
        Returns:
            Randomly generated webhook secret
        """
        import secrets
        return secrets.token_urlsafe(32)

    def _verify_signature(
        self,
        payload: Dict[str, Any],
        signature: str,
        secret: str,
        algorithm: str = "sha256"
    ) -> bool:
        """
        Verify webhook signature.
        
        Args:
            payload: Webhook payload
            signature: Provided signature
            secret: Webhook secret
            algorithm: Hash algorithm
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            import json
            
            # Serialize payload
            payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
            
            # Compute expected signature
            if algorithm == "sha256":
                expected = hmac.new(
                    secret.encode(),
                    payload_str.encode(),
                    hashlib.sha256
                ).hexdigest()
            elif algorithm == "sha1":
                expected = hmac.new(
                    secret.encode(),
                    payload_str.encode(),
                    hashlib.sha1
                ).hexdigest()
            else:
                logger.error(f"Unsupported signature algorithm: {algorithm}")
                return False
            
            # Compare signatures (constant-time comparison)
            return hmac.compare_digest(expected, signature)
            
        except Exception as e:
            logger.error(
                f"Error verifying webhook signature: {str(e)}",
                exc_info=True
            )
            return False

    def register_webhook(
        self,
        provider: str,
        callback_url: str,
        events: List[str],
        secret: Optional[str] = None,
        description: Optional[str] = None,
        enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Register a webhook endpoint.
        
        Args:
            provider: Provider identifier
            callback_url: URL to receive webhook notifications
            events: List of event types to subscribe to
            secret: Webhook secret for signature verification (auto-generated if None)
            description: Human-readable description
            enabled: Whether webhook is active
            metadata: Additional metadata
            
        Returns:
            ServiceResult containing webhook registration details
        """
        logger.info(
            f"Registering webhook for {provider}",
            extra={
                "provider": provider,
                "callback_url": callback_url,
                "events": events
            }
        )
        
        # Validate configuration
        validation = self._validate_webhook_config(provider, callback_url, events)
        if not validation.success:
            return validation

        try:
            # Generate secret if not provided
            if not secret:
                secret = self._generate_webhook_secret()
            
            # Prepare webhook data
            webhook_data = {
                "provider": provider,
                "callback_url": callback_url,
                "events": events,
                "secret": secret,
                "description": description,
                "enabled": enabled,
                "metadata": metadata or {},
                "registered_at": datetime.utcnow().isoformat()
            }
            
            # Register webhook
            webhook = self.repository.register_webhook(
                provider=provider,
                callback_url=callback_url,
                events=events,
                secret=secret,
                description=description,
                enabled=enabled,
                metadata=metadata
            )
            
            # Commit transaction
            self.db.commit()
            
            logger.info(
                f"Webhook registered successfully for {provider}",
                extra={
                    "provider": provider,
                    "webhook_id": webhook.get("id"),
                    "events": events
                }
            )
            
            return ServiceResult.success(
                webhook or {},
                message=f"Webhook registered for {provider}",
                metadata={
                    "provider": provider,
                    "webhook_id": webhook.get("id"),
                    "event_count": len(events)
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error registering webhook for {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to register webhook for {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error registering webhook for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "register webhook", provider)

    def process_inbound(
        self,
        provider: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        verify_signature: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Verify and process inbound webhook.
        
        Args:
            provider: Provider identifier
            headers: HTTP headers from webhook request
            payload: Webhook payload
            verify_signature: Whether to verify signature
            
        Returns:
            ServiceResult containing processing status
        """
        logger.info(
            f"Processing inbound webhook from {provider}",
            extra={
                "provider": provider,
                "event_type": payload.get("event_type") or payload.get("type")
            }
        )

        try:
            # Get webhook configuration
            webhook_config = self.repository.get_webhook_config(provider)
            
            if not webhook_config:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No webhook configured for {provider}",
                        severity=ErrorSeverity.MEDIUM,
                        context={"provider": provider}
                    )
                )
            
            # Check if webhook is enabled
            if not webhook_config.get("enabled", False):
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.BUSINESS_RULE_VIOLATION,
                        message=f"Webhook disabled for {provider}",
                        severity=ErrorSeverity.MEDIUM,
                        context={"provider": provider}
                    )
                )
            
            # Verify signature if requested
            if verify_signature:
                signature_header = headers.get("X-Webhook-Signature") or headers.get("X-Signature")
                secret = webhook_config.get("secret")
                
                if not signature_header or not secret:
                    logger.warning(
                        f"Missing signature or secret for {provider}",
                        extra={"provider": provider}
                    )
                    return ServiceResult.failure(
                        error=ServiceError(
                            code=ErrorCode.AUTHENTICATION_ERROR,
                            message="Missing signature or webhook secret",
                            severity=ErrorSeverity.HIGH,
                            context={"provider": provider}
                        )
                    )
                
                # Verify signature
                if not self._verify_signature(payload, signature_header, secret):
                    logger.error(
                        f"Invalid webhook signature from {provider}",
                        extra={"provider": provider}
                    )
                    return ServiceResult.failure(
                        error=ServiceError(
                            code=ErrorCode.AUTHENTICATION_ERROR,
                            message=f"Invalid webhook signature from {provider}",
                            severity=ErrorSeverity.CRITICAL,
                            context={"provider": provider}
                        )
                    )
            
            # Process webhook
            result = self.repository.process_inbound_webhook(
                provider=provider,
                headers=headers,
                payload=payload
            )
            
            # Commit transaction
            self.db.commit()
            
            logger.info(
                f"Inbound webhook processed successfully from {provider}",
                extra={
                    "provider": provider,
                    "event_id": result.get("event_id")
                }
            )
            
            return ServiceResult.success(
                result or {},
                message=f"Webhook processed from {provider}",
                metadata={
                    "provider": provider,
                    "event_id": result.get("event_id")
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error processing webhook from {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to process webhook from {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error processing webhook from {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "process inbound webhook", provider)

    def deliver_outbound(
        self,
        provider: str,
        webhook_id: UUID,
        payload: Dict[str, Any],
        event_type: str,
        idempotency_key: Optional[str] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Deliver outbound webhook to provider.
        
        Args:
            provider: Provider identifier
            webhook_id: Webhook configuration ID
            payload: Data to send
            event_type: Type of event
            idempotency_key: Optional idempotency key
            
        Returns:
            ServiceResult containing delivery status
        """
        logger.info(
            f"Delivering outbound webhook to {provider}",
            extra={
                "provider": provider,
                "webhook_id": str(webhook_id),
                "event_type": event_type
            }
        )

        try:
            # Prepare delivery metadata
            delivery_metadata = {
                "event_type": event_type,
                "idempotency_key": idempotency_key,
                "attempted_at": datetime.utcnow().isoformat()
            }
            
            # Deliver webhook
            result = self.repository.deliver_outbound_webhook(
                provider=provider,
                webhook_id=webhook_id,
                payload=payload,
                metadata=delivery_metadata
            )
            
            # Commit transaction
            self.db.commit()
            
            success = result.get("success", False)
            
            if success:
                logger.info(
                    f"Outbound webhook delivered successfully to {provider}",
                    extra={
                        "provider": provider,
                        "delivery_id": result.get("delivery_id"),
                        "status_code": result.get("status_code")
                    }
                )
            else:
                logger.warning(
                    f"Outbound webhook delivery failed for {provider}",
                    extra={
                        "provider": provider,
                        "error": result.get("error"),
                        "status_code": result.get("status_code")
                    }
                )
            
            return ServiceResult.success(
                result or {},
                message=f"Webhook {'delivered' if success else 'delivery failed'}",
                metadata={
                    "provider": provider,
                    "success": success,
                    "delivery_id": result.get("delivery_id")
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error delivering webhook to {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to log webhook delivery to {provider}",
                    severity=ErrorSeverity.MEDIUM,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error delivering webhook to {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "deliver outbound webhook", webhook_id)

    def retry(
        self,
        webhook_delivery_id: UUID,
        manual: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Retry failed webhook delivery.
        
        Args:
            webhook_delivery_id: Delivery record ID
            manual: Whether this is a manual retry
            
        Returns:
            ServiceResult containing retry status
        """
        logger.info(
            f"Retrying webhook delivery: {webhook_delivery_id}",
            extra={"delivery_id": str(webhook_delivery_id), "manual": manual}
        )

        try:
            # Get delivery record
            delivery = self.repository.get_webhook_delivery(webhook_delivery_id)
            
            if not delivery:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Webhook delivery not found: {webhook_delivery_id}",
                        severity=ErrorSeverity.MEDIUM,
                        context={"delivery_id": str(webhook_delivery_id)}
                    )
                )
            
            # Check retry limit
            retry_count = delivery.get("retry_count", 0)
            if not manual and retry_count >= self._max_retries:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.BUSINESS_RULE_VIOLATION,
                        message="Maximum retry attempts exceeded",
                        severity=ErrorSeverity.MEDIUM,
                        context={
                            "delivery_id": str(webhook_delivery_id),
                            "retry_count": retry_count,
                            "max_retries": self._max_retries
                        }
                    )
                )
            
            # Calculate backoff delay
            if not manual:
                delay_seconds = self._initial_retry_delay * (
                    self._retry_backoff_base ** retry_count
                )
                next_retry = datetime.utcnow() + timedelta(seconds=delay_seconds)
            else:
                next_retry = datetime.utcnow()
            
            # Retry delivery
            result = self.repository.retry_webhook(
                webhook_delivery_id=webhook_delivery_id,
                manual=manual,
                next_retry=next_retry
            )
            
            # Commit transaction
            self.db.commit()
            
            success = result.get("success", False)
            
            logger.info(
                f"Webhook retry {'succeeded' if success else 'failed'}: {webhook_delivery_id}",
                extra={
                    "delivery_id": str(webhook_delivery_id),
                    "success": success,
                    "retry_count": retry_count + 1
                }
            )
            
            return ServiceResult.success(
                result or {},
                message=f"Webhook retry {'succeeded' if success else 'failed'}",
                metadata={
                    "delivery_id": str(webhook_delivery_id),
                    "success": success,
                    "retry_count": retry_count + 1
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error retrying webhook: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message="Failed to retry webhook delivery",
                    severity=ErrorSeverity.HIGH,
                    context={
                        "delivery_id": str(webhook_delivery_id),
                        "error": str(e)
                    }
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error retrying webhook: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "retry webhook", webhook_delivery_id)

    def list_webhooks(
        self,
        provider: Optional[str] = None,
        enabled_only: bool = False,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        List registered webhooks.
        
        Args:
            provider: Filter by provider (None for all)
            enabled_only: Only return enabled webhooks
            
        Returns:
            ServiceResult containing list of webhooks
        """
        logger.debug(
            f"Listing webhooks (provider={provider}, enabled_only={enabled_only})"
        )

        try:
            webhooks = self.repository.list_webhooks(
                provider=provider,
                enabled_only=enabled_only
            )
            
            return ServiceResult.success(
                webhooks or [],
                message=f"Retrieved {len(webhooks or [])} webhooks",
                metadata={
                    "count": len(webhooks or []),
                    "provider": provider,
                    "enabled_only": enabled_only
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error listing webhooks: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list webhooks")

    def update_webhook(
        self,
        webhook_id: UUID,
        updates: Dict[str, Any],
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Update webhook configuration.
        
        Args:
            webhook_id: Webhook ID
            updates: Fields to update
            
        Returns:
            ServiceResult containing updated webhook
        """
        logger.info(
            f"Updating webhook: {webhook_id}",
            extra={"webhook_id": str(webhook_id)}
        )

        try:
            # Add update timestamp
            updates["updated_at"] = datetime.utcnow().isoformat()
            
            # Update webhook
            webhook = self.repository.update_webhook(webhook_id, updates)
            
            self.db.commit()
            
            return ServiceResult.success(
                webhook or {},
                message="Webhook updated successfully",
                metadata={"webhook_id": str(webhook_id)}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error updating webhook: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message="Failed to update webhook",
                    severity=ErrorSeverity.HIGH,
                    context={"webhook_id": str(webhook_id), "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error updating webhook: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update webhook", webhook_id)

    def delete_webhook(
        self,
        webhook_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Delete webhook registration.
        
        Args:
            webhook_id: Webhook ID
            
        Returns:
            ServiceResult indicating deletion success
        """
        logger.info(
            f"Deleting webhook: {webhook_id}",
            extra={"webhook_id": str(webhook_id)}
        )

        try:
            success = self.repository.delete_webhook(webhook_id)
            
            self.db.commit()
            
            return ServiceResult.success(
                success,
                message="Webhook deleted successfully",
                metadata={"webhook_id": str(webhook_id)}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error deleting webhook: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message="Failed to delete webhook",
                    severity=ErrorSeverity.HIGH,
                    context={"webhook_id": str(webhook_id), "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error deleting webhook: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "delete webhook", webhook_id)

    def get_delivery_history(
        self,
        webhook_id: Optional[UUID] = None,
        provider: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get webhook delivery history.
        
        Args:
            webhook_id: Filter by webhook ID
            provider: Filter by provider
            status: Filter by delivery status
            limit: Maximum number of results
            
        Returns:
            ServiceResult containing delivery history
        """
        logger.debug(
            f"Retrieving webhook delivery history "
            f"(webhook_id={webhook_id}, provider={provider}, status={status})"
        )

        try:
            history = self.repository.get_delivery_history(
                webhook_id=webhook_id,
                provider=provider,
                status=status,
                limit=limit
            )
            
            return ServiceResult.success(
                history or [],
                message=f"Retrieved {len(history or [])} delivery records",
                metadata={
                    "count": len(history or []),
                    "webhook_id": str(webhook_id) if webhook_id else None,
                    "provider": provider,
                    "status": status
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error retrieving delivery history: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get delivery history")