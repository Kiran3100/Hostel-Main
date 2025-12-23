"""
SMS provider configuration & health service (Twilio/SNS/Msg91/etc.).

Manages SMS provider integrations with support for multiple carriers,
delivery tracking, and comprehensive error handling.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
import logging
import re

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService, ServiceResult, ServiceError, 
    ErrorCode, ErrorSeverity
)
from app.repositories.integrations import ThirdPartyRepository
from app.models.integrations.api_integration import APIIntegration

logger = logging.getLogger(__name__)


class SMSProviderService(BaseService[APIIntegration, ThirdPartyRepository]):
    """
    Manage SMS provider configs, test send, and health checks.
    
    Supported providers:
    - Twilio
    - AWS SNS
    - Msg91
    - Nexmo/Vonage
    - Plivo
    """

    # Supported SMS providers
    SUPPORTED_PROVIDERS = {
        "twilio", "sns", "msg91", "nexmo", "vonage", "plivo"
    }
    
    # Phone number validation regex (E.164 format)
    PHONE_REGEX = re.compile(r'^\+[1-9]\d{1,14}$')

    def __init__(
        self, 
        repository: ThirdPartyRepository, 
        db_session: Session,
        default_sender_id: Optional[str] = None,
        max_message_length: int = 160,
    ):
        """
        Initialize SMS provider service.
        
        Args:
            repository: Third-party repository instance
            db_session: SQLAlchemy database session
            default_sender_id: Default sender ID for SMS
            max_message_length: Maximum SMS message length
        """
        super().__init__(repository, db_session)
        self._default_sender_id = default_sender_id
        self._max_message_length = max_message_length
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("SMSProviderService initialized")

    def _validate_provider(self, provider: str) -> ServiceResult[bool]:
        """
        Validate SMS provider identifier.
        
        Args:
            provider: Provider identifier
            
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
            
        provider_lower = provider.lower()
        if provider_lower not in self.SUPPORTED_PROVIDERS:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Unsupported SMS provider: {provider}",
                    severity=ErrorSeverity.MEDIUM,
                    context={
                        "provider": provider,
                        "supported": list(self.SUPPORTED_PROVIDERS)
                    }
                )
            )
            
        return ServiceResult.success(True)

    def _validate_phone_number(self, phone: str) -> ServiceResult[bool]:
        """
        Validate phone number format (E.164).
        
        Args:
            phone: Phone number to validate
            
        Returns:
            ServiceResult indicating validation success
        """
        if not phone or not isinstance(phone, str):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Phone number must be a non-empty string",
                    severity=ErrorSeverity.MEDIUM
                )
            )
        
        # Remove whitespace and common separators
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        
        if not self.PHONE_REGEX.match(cleaned):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid phone number format (E.164 required): {phone}",
                    severity=ErrorSeverity.MEDIUM,
                    context={
                        "phone": phone,
                        "format": "E.164 (+[country code][number])"
                    }
                )
            )
        
        return ServiceResult.success(True)

    def _validate_config(
        self, 
        provider: str, 
        config: Dict[str, Any]
    ) -> ServiceResult[bool]:
        """
        Validate provider-specific configuration.
        
        Args:
            provider: Provider identifier
            config: Configuration dictionary
            
        Returns:
            ServiceResult indicating validation success
        """
        if not config or not isinstance(config, dict):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Config must be a non-empty dictionary",
                    severity=ErrorSeverity.MEDIUM
                )
            )
        
        provider_lower = provider.lower()
        
        # Provider-specific required fields
        if provider_lower == "twilio":
            required = ["account_sid", "auth_token", "from_number"]
        elif provider_lower == "sns":
            required = ["region", "access_key_id", "secret_access_key"]
        elif provider_lower == "msg91":
            required = ["auth_key", "sender_id"]
        elif provider_lower in ["nexmo", "vonage"]:
            required = ["api_key", "api_secret", "from_number"]
        elif provider_lower == "plivo":
            required = ["auth_id", "auth_token", "from_number"]
        else:
            required = []
        
        # Check required fields
        missing = [field for field in required if field not in config]
        if missing:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Missing required config fields for {provider}",
                    severity=ErrorSeverity.MEDIUM,
                    context={
                        "provider": provider,
                        "missing_fields": missing,
                        "required_fields": required
                    }
                )
            )
        
        # Validate from_number if present
        if "from_number" in config:
            phone_validation = self._validate_phone_number(config["from_number"])
            if not phone_validation.success:
                return phone_validation
        
        return ServiceResult.success(True)

    def upsert_config(
        self,
        provider: str,
        config: Dict[str, Any],
        updated_by: Optional[UUID] = None,
        validate_immediately: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Create or update SMS provider configuration.
        
        Args:
            provider: Provider identifier
            config: Provider configuration data
            updated_by: UUID of user making the change
            validate_immediately: Test configuration after saving
            
        Returns:
            ServiceResult containing saved configuration
        """
        logger.info(
            f"Upserting config for SMS provider: {provider}",
            extra={"provider": provider}
        )
        
        # Validate provider
        provider_validation = self._validate_provider(provider)
        if not provider_validation.success:
            return provider_validation
        
        # Validate configuration
        config_validation = self._validate_config(provider, config)
        if not config_validation.success:
            return config_validation

        try:
            # Enhance config with metadata
            from datetime import datetime
            enhanced_config = {
                **config,
                "updated_by": str(updated_by) if updated_by else None,
                "updated_at": datetime.utcnow().isoformat(),
                "max_message_length": config.get(
                    "max_message_length", 
                    self._max_message_length
                ),
                "supports_unicode": config.get("supports_unicode", True),
                "delivery_reports": config.get("delivery_reports", True),
                "rate_limit_per_minute": config.get("rate_limit_per_minute", 100)
            }
            
            # Save configuration
            result = self.repository.sms_upsert_config(provider, enhanced_config)
            
            # Clear cache
            cache_key = f"sms_config_{provider}"
            if cache_key in self._config_cache:
                del self._config_cache[cache_key]
            
            # Validate configuration if requested
            if validate_immediately:
                validation_result = self.health_check(provider)
                if not validation_result.success:
                    logger.warning(
                        f"Configuration saved but validation failed for {provider}",
                        extra={"provider": provider}
                    )
                    result["validation_warning"] = (
                        "Configuration saved but health check failed"
                    )
                    result["validation_details"] = str(validation_result.error)
            
            # Commit transaction
            self.db.commit()
            
            logger.info(
                f"SMS provider config saved successfully: {provider}",
                extra={"provider": provider}
            )
            
            return ServiceResult.success(
                result or {},
                message=f"SMS provider config saved for {provider}",
                metadata={
                    "provider": provider,
                    "validated": validate_immediately
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error upserting config for {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to save config for {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error upserting config for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "upsert sms provider config", provider)

    def get_config(
        self,
        provider: str,
        use_cache: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Retrieve SMS provider configuration.
        
        Args:
            provider: Provider identifier
            use_cache: Use cached configuration if available
            
        Returns:
            ServiceResult containing provider configuration
        """
        logger.debug(f"Retrieving config for SMS provider: {provider}")
        
        # Validate provider
        provider_validation = self._validate_provider(provider)
        if not provider_validation.success:
            return provider_validation
        
        try:
            cache_key = f"sms_config_{provider}"
            
            # Check cache
            if use_cache and cache_key in self._config_cache:
                logger.debug(f"Returning cached config for {provider}")
                return ServiceResult.success(
                    self._config_cache[cache_key],
                    message=f"Retrieved cached config for {provider}",
                    metadata={"provider": provider, "cached": True}
                )
            
            # Fetch from repository
            config = self.repository.sms_get_config(provider)
            
            if not config:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No configuration found for {provider}",
                        severity=ErrorSeverity.MEDIUM,
                        context={"provider": provider}
                    )
                )
            
            # Update cache
            if use_cache:
                self._config_cache[cache_key] = config
            
            return ServiceResult.success(
                config,
                message=f"Retrieved config for {provider}",
                metadata={"provider": provider, "cached": False}
            )
            
        except Exception as e:
            logger.error(
                f"Error retrieving config for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get sms provider config", provider)

    def health_check(
        self,
        provider: str,
        timeout: int = 10,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Perform health check for SMS provider.
        
        Validates credentials, connectivity, and account balance
        without actually sending SMS messages.
        
        Args:
            provider: Provider identifier
            timeout: Health check timeout in seconds
            
        Returns:
            ServiceResult containing health status and metrics
        """
        logger.info(f"Performing health check for SMS provider: {provider}")
        
        # Validate provider
        provider_validation = self._validate_provider(provider)
        if not provider_validation.success:
            return provider_validation

        try:
            from datetime import datetime
            start_time = datetime.utcnow()
            
            # Execute health check
            health = self.repository.sms_health_check(provider, timeout=timeout)
            
            # Calculate response time
            response_time_ms = (
                datetime.utcnow() - start_time
            ).total_seconds() * 1000
            
            # Enhance health data
            enhanced_health = {
                **(health or {}),
                "provider": provider,
                "response_time_ms": round(response_time_ms, 2),
                "checked_at": datetime.utcnow().isoformat(),
                "timeout": timeout
            }
            
            status = enhanced_health.get("status", "unknown")
            
            # Log warning if balance is low
            balance = enhanced_health.get("balance")
            if balance and isinstance(balance, (int, float)) and balance < 100:
                logger.warning(
                    f"Low balance for SMS provider {provider}: {balance}",
                    extra={"provider": provider, "balance": balance}
                )
            
            logger.info(
                f"Health check completed for {provider}: {status}",
                extra={
                    "provider": provider,
                    "status": status,
                    "response_time_ms": response_time_ms
                }
            )
            
            return ServiceResult.success(
                enhanced_health,
                message=f"Health check completed for {provider}",
                metadata={
                    "provider": provider,
                    "status": status,
                    "response_time_ms": response_time_ms
                }
            )
            
        except Exception as e:
            logger.error(
                f"Health check failed for {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                    message=f"Health check failed for {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={"provider": provider, "error": str(e)}
                )
            )

    def send_test(
        self,
        provider: str,
        to_phone: str,
        message: str,
        from_phone: Optional[str] = None,
        sender_id: Optional[str] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Send test SMS through provider.
        
        Args:
            provider: Provider identifier
            to_phone: Recipient phone number (E.164 format)
            message: SMS message text
            from_phone: Sender phone number (overrides config)
            sender_id: Sender ID (for providers that support it)
            
        Returns:
            ServiceResult containing send status and message ID
        """
        logger.info(
            f"Sending test SMS via {provider} to {to_phone}",
            extra={"provider": provider, "to_phone": to_phone}
        )
        
        # Validate provider
        provider_validation = self._validate_provider(provider)
        if not provider_validation.success:
            return provider_validation
        
        # Validate recipient phone
        phone_validation = self._validate_phone_number(to_phone)
        if not phone_validation.success:
            return phone_validation
        
        # Validate sender phone if provided
        if from_phone:
            sender_validation = self._validate_phone_number(from_phone)
            if not sender_validation.success:
                return sender_validation
        
        # Validate message
        if not message or not isinstance(message, str):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Message must be a non-empty string",
                    severity=ErrorSeverity.MEDIUM
                )
            )
        
        if len(message) > self._max_message_length:
            logger.warning(
                f"Message exceeds max length ({self._max_message_length}), "
                "will be split into multiple parts",
                extra={
                    "provider": provider,
                    "message_length": len(message),
                    "max_length": self._max_message_length
                }
            )

        try:
            # Send test SMS
            result = self.repository.sms_send_test(
                provider=provider,
                to_phone=to_phone,
                message=message,
                from_phone=from_phone or self._default_sender_id,
                sender_id=sender_id
            )
            
            # Commit transaction
            self.db.commit()
            
            success = result.get("success", False)
            
            if success:
                logger.info(
                    f"Test SMS sent successfully via {provider}",
                    extra={
                        "provider": provider,
                        "to_phone": to_phone,
                        "message_id": result.get("message_id"),
                        "parts": result.get("parts", 1)
                    }
                )
                
                return ServiceResult.success(
                    result,
                    message=f"Test SMS sent via {provider}",
                    metadata={
                        "provider": provider,
                        "to_phone": to_phone,
                        "message_id": result.get("message_id"),
                        "parts": result.get("parts", 1)
                    }
                )
            else:
                logger.warning(
                    f"Test SMS failed for {provider}",
                    extra={"provider": provider, "error": result.get("error")}
                )
                
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        message=f"Failed to send test SMS via {provider}",
                        severity=ErrorSeverity.MEDIUM,
                        context={
                            "provider": provider,
                            "to_phone": to_phone,
                            "error": result.get("error")
                        }
                    )
                )
                
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error sending test SMS via {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to log test SMS for {provider}",
                    severity=ErrorSeverity.MEDIUM,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error sending test SMS via {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "send test sms", to_phone)

    def get_delivery_status(
        self,
        provider: str,
        message_id: str,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get delivery status for a sent SMS.
        
        Args:
            provider: Provider identifier
            message_id: Message ID from send operation
            
        Returns:
            ServiceResult containing delivery status
        """
        logger.info(
            f"Retrieving delivery status for message: {message_id}",
            extra={"provider": provider, "message_id": message_id}
        )
        
        # Validate provider
        provider_validation = self._validate_provider(provider)
        if not provider_validation.success:
            return provider_validation
        
        try:
            status = self.repository.sms_get_delivery_status(provider, message_id)
            
            if not status:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Message not found: {message_id}",
                        severity=ErrorSeverity.MEDIUM,
                        context={
                            "provider": provider,
                            "message_id": message_id
                        }
                    )
                )
            
            return ServiceResult.success(
                status,
                message="Delivery status retrieved",
                metadata={
                    "provider": provider,
                    "message_id": message_id,
                    "status": status.get("status")
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error retrieving delivery status: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get delivery status", message_id)

    def get_send_statistics(
        self,
        provider: str,
        hours: int = 24,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Retrieve send statistics for SMS provider.
        
        Args:
            provider: Provider identifier
            hours: Number of hours of historical data
            
        Returns:
            ServiceResult containing send statistics
        """
        logger.info(
            f"Retrieving send statistics for {provider} (last {hours} hours)"
        )
        
        # Validate provider
        provider_validation = self._validate_provider(provider)
        if not provider_validation.success:
            return provider_validation
        
        try:
            stats = self.repository.sms_get_statistics(provider, hours=hours)
            
            return ServiceResult.success(
                stats or {},
                message=f"Retrieved statistics for {provider}",
                metadata={
                    "provider": provider,
                    "hours": hours
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error retrieving statistics for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get sms statistics", provider)

    def list_providers(
        self,
        include_config: bool = False,
        include_health: bool = False,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        List all configured SMS providers.
        
        Args:
            include_config: Include full configuration data
            include_health: Include health status
            
        Returns:
            ServiceResult containing list of providers
        """
        logger.info("Listing all SMS providers")
        
        try:
            providers = self.repository.sms_list_providers(
                include_config=include_config
            )
            
            # Add health status if requested
            if include_health:
                for provider_data in providers:
                    provider = provider_data.get("provider")
                    if provider:
                        health_result = self.health_check(provider)
                        provider_data["health"] = (
                            health_result.data if health_result.success 
                            else {"status": "error"}
                        )
            
            return ServiceResult.success(
                providers,
                message=f"Retrieved {len(providers)} SMS providers",
                metadata={
                    "count": len(providers),
                    "include_config": include_config,
                    "include_health": include_health
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error listing SMS providers: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list sms providers")