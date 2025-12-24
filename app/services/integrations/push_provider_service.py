"""
Push provider configuration & health service (Firebase/APNs).

Manages push notification provider integrations including FCM (Firebase Cloud Messaging)
and APNs (Apple Push Notification service) with device management and testing capabilities.
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


class PushProviderService(BaseService[APIIntegration, ThirdPartyRepository]):
    """
    Manage push provider configs (FCM/APNs), device validation, and health.
    
    Supported providers:
    - Firebase Cloud Messaging (FCM)
    - Apple Push Notification service (APNs)
    - OneSignal
    - Pusher
    """

    # Supported push providers
    SUPPORTED_PROVIDERS = {
        "fcm", "apns", "onesignal", "pusher"
    }
    
    # Device token validation patterns
    TOKEN_PATTERNS = {
        "fcm": re.compile(r'^[a-zA-Z0-9_-]{140,}$'),
        "apns": re.compile(r'^[a-fA-F0-9]{64}$'),
        "onesignal": re.compile(r'^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$'),
        "pusher": re.compile(r'^.+$')  # Generic pattern
    }

    def __init__(
        self, 
        repository: ThirdPartyRepository, 
        db_session: Session,
        max_retries: int = 3,
        retry_delay: int = 2,
    ):
        """
        Initialize push provider service.
        
        Args:
            repository: Third-party repository instance
            db_session: SQLAlchemy database session
            max_retries: Maximum retry attempts for failed sends
            retry_delay: Delay between retries in seconds
        """
        super().__init__(repository, db_session)
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._device_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("PushProviderService initialized")

    def _validate_provider(self, provider: str) -> ServiceResult[bool]:
        """
        Validate push provider identifier.
        
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
                    message=f"Unsupported push provider: {provider}",
                    severity=ErrorSeverity.MEDIUM,
                    context={
                        "provider": provider,
                        "supported": list(self.SUPPORTED_PROVIDERS)
                    }
                )
            )
            
        return ServiceResult.success(True)

    def _validate_device_token(
        self, 
        provider: str, 
        device_token: str
    ) -> ServiceResult[bool]:
        """
        Validate device token format for provider.
        
        Args:
            provider: Provider identifier
            device_token: Device token to validate
            
        Returns:
            ServiceResult indicating validation success
        """
        if not device_token or not isinstance(device_token, str):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Device token must be a non-empty string",
                    severity=ErrorSeverity.MEDIUM
                )
            )
        
        provider_lower = provider.lower()
        pattern = self.TOKEN_PATTERNS.get(provider_lower)
        
        if pattern and not pattern.match(device_token):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid device token format for {provider}",
                    severity=ErrorSeverity.MEDIUM,
                    context={
                        "provider": provider,
                        "token_length": len(device_token)
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
        if provider_lower == "fcm":
            required = ["project_id", "credentials"]
            # Check for either service account or API key
            if "service_account_json" not in config and "server_key" not in config.get("credentials", {}):
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="FCM requires either service_account_json or server_key",
                        severity=ErrorSeverity.MEDIUM,
                        context={"provider": provider}
                    )
                )
        elif provider_lower == "apns":
            required = ["team_id", "key_id", "bundle_id"]
            # Check for either auth key or certificate
            if "auth_key" not in config and "certificate" not in config:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="APNs requires either auth_key or certificate",
                        severity=ErrorSeverity.MEDIUM,
                        context={"provider": provider}
                    )
                )
        elif provider_lower == "onesignal":
            required = ["app_id", "api_key"]
        elif provider_lower == "pusher":
            required = ["app_id", "key", "secret", "cluster"]
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
        
        return ServiceResult.success(True)

    def upsert_config(
        self,
        provider: str,
        config: Dict[str, Any],
        updated_by: Optional[UUID] = None,
        validate_immediately: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Create or update push provider configuration.
        
        Args:
            provider: Provider identifier
            config: Provider configuration data
            updated_by: UUID of user making the change
            validate_immediately: Test configuration after saving
            
        Returns:
            ServiceResult containing saved configuration
        """
        logger.info(
            f"Upserting config for push provider: {provider}",
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
                "max_retries": config.get("max_retries", self._max_retries),
                "retry_delay": config.get("retry_delay", self._retry_delay),
                "batch_size": config.get("batch_size", 500),
                "priority": config.get("priority", "normal")
            }
            
            # Save configuration
            result = self.repository.push_upsert_config(provider, enhanced_config)
            
            # Clear cache
            cache_key = f"push_config_{provider}"
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
                f"Push provider config saved successfully: {provider}",
                extra={"provider": provider}
            )
            
            return ServiceResult.success(
                result or {},
                message=f"Push provider config saved for {provider}",
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
            return self._handle_exception(e, "upsert push provider config", provider)

    def get_config(
        self,
        provider: str,
        use_cache: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Retrieve push provider configuration.
        
        Args:
            provider: Provider identifier
            use_cache: Use cached configuration if available
            
        Returns:
            ServiceResult containing provider configuration
        """
        logger.debug(f"Retrieving config for push provider: {provider}")
        
        # Validate provider
        provider_validation = self._validate_provider(provider)
        if not provider_validation.success:
            return provider_validation
        
        try:
            cache_key = f"push_config_{provider}"
            
            # Check cache
            if use_cache and cache_key in self._config_cache:
                logger.debug(f"Returning cached config for {provider}")
                return ServiceResult.success(
                    self._config_cache[cache_key],
                    message=f"Retrieved cached config for {provider}",
                    metadata={"provider": provider, "cached": True}
                )
            
            # Fetch from repository
            config = self.repository.push_get_config(provider)
            
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
            return self._handle_exception(e, "get push provider config", provider)

    def health_check(
        self,
        provider: str,
        timeout: int = 10,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Perform health check for push provider.
        
        Validates credentials, connectivity, and service availability
        without actually sending push notifications.
        
        Args:
            provider: Provider identifier
            timeout: Health check timeout in seconds
            
        Returns:
            ServiceResult containing health status and metrics
        """
        logger.info(f"Performing health check for push provider: {provider}")
        
        # Validate provider
        provider_validation = self._validate_provider(provider)
        if not provider_validation.success:
            return provider_validation

        try:
            from datetime import datetime
            start_time = datetime.utcnow()
            
            # Execute health check
            health = self.repository.push_health_check(provider, timeout=timeout)
            
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
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        priority: str = "normal",
        badge: Optional[int] = None,
        sound: Optional[str] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Send test push notification through provider.
        
        Args:
            provider: Provider identifier
            device_token: Target device token
            title: Notification title
            body: Notification body text
            data: Additional data payload
            priority: Notification priority (normal, high)
            badge: Badge count (iOS)
            sound: Sound file name
            
        Returns:
            ServiceResult containing send status and message ID
        """
        logger.info(
            f"Sending test push via {provider}",
            extra={"provider": provider, "title": title}
        )
        
        # Validate provider
        provider_validation = self._validate_provider(provider)
        if not provider_validation.success:
            return provider_validation
        
        # Validate device token
        token_validation = self._validate_device_token(provider, device_token)
        if not token_validation.success:
            return token_validation
        
        # Validate inputs
        if not title or not isinstance(title, str):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Title must be a non-empty string",
                    severity=ErrorSeverity.MEDIUM
                )
            )
        
        if not body or not isinstance(body, str):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Body must be a non-empty string",
                    severity=ErrorSeverity.MEDIUM
                )
            )
        
        if priority not in ["normal", "high"]:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Priority must be 'normal' or 'high'",
                    severity=ErrorSeverity.MEDIUM,
                    context={"priority": priority}
                )
            )

        try:
            # Send test notification
            result = self.repository.push_send_test(
                provider=provider,
                device_token=device_token,
                title=title,
                body=body,
                data=data or {},
                priority=priority,
                badge=badge,
                sound=sound
            )
            
            # Commit transaction
            self.db.commit()
            
            success = result.get("success", False)
            
            if success:
                logger.info(
                    f"Test push sent successfully via {provider}",
                    extra={
                        "provider": provider,
                        "device_token": device_token[:20] + "...",
                        "message_id": result.get("message_id")
                    }
                )
                
                return ServiceResult.success(
                    result,
                    message=f"Test push sent via {provider}",
                    metadata={
                        "provider": provider,
                        "message_id": result.get("message_id")
                    }
                )
            else:
                logger.warning(
                    f"Test push failed for {provider}",
                    extra={"provider": provider, "error": result.get("error")}
                )
                
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        message=f"Failed to send test push via {provider}",
                        severity=ErrorSeverity.MEDIUM,
                        context={
                            "provider": provider,
                            "error": result.get("error")
                        }
                    )
                )
                
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error sending test push via {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to log test push for {provider}",
                    severity=ErrorSeverity.MEDIUM,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error sending test push via {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "send test push", device_token)

    def register_device(
        self,
        provider: str,
        device_token: str,
        user_id: UUID,
        platform: str,
        app_version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Register device for push notifications.
        
        Args:
            provider: Provider identifier
            device_token: Device token
            user_id: User ID associated with device
            platform: Device platform (ios, android, web)
            app_version: Application version
            metadata: Additional device metadata
            
        Returns:
            ServiceResult containing registration status
        """
        logger.info(
            f"Registering device for {provider}",
            extra={
                "provider": provider,
                "user_id": str(user_id),
                "platform": platform
            }
        )
        
        # Validate provider
        provider_validation = self._validate_provider(provider)
        if not provider_validation.success:
            return provider_validation
        
        # Validate device token
        token_validation = self._validate_device_token(provider, device_token)
        if not token_validation.success:
            return token_validation
        
        # Validate platform
        if platform not in ["ios", "android", "web"]:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Platform must be 'ios', 'android', or 'web'",
                    severity=ErrorSeverity.MEDIUM,
                    context={"platform": platform}
                )
            )
        
        try:
            from datetime import datetime
            
            device_data = {
                "provider": provider,
                "device_token": device_token,
                "user_id": str(user_id),
                "platform": platform,
                "app_version": app_version,
                "registered_at": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            }
            
            result = self.repository.push_register_device(device_data)
            
            # Update device cache
            cache_key = f"device_{device_token}"
            self._device_cache[cache_key] = device_data
            
            self.db.commit()
            
            logger.info(
                f"Device registered successfully for {provider}",
                extra={"provider": provider, "user_id": str(user_id)}
            )
            
            return ServiceResult.success(
                result or {},
                message=f"Device registered for {provider}",
                metadata={"provider": provider, "platform": platform}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error registering device: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message="Failed to register device",
                    severity=ErrorSeverity.HIGH,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error registering device: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "register device", device_token)

    def unregister_device(
        self,
        device_token: str,
        reason: Optional[str] = None,
    ) -> ServiceResult[bool]:
        """
        Unregister device from push notifications.
        
        Args:
            device_token: Device token to unregister
            reason: Reason for unregistration
            
        Returns:
            ServiceResult indicating unregistration success
        """
        logger.info(
            f"Unregistering device: {device_token[:20]}...",
            extra={"reason": reason}
        )
        
        try:
            success = self.repository.push_unregister_device(
                device_token, 
                reason=reason
            )
            
            # Clear device cache
            cache_key = f"device_{device_token}"
            if cache_key in self._device_cache:
                del self._device_cache[cache_key]
            
            self.db.commit()
            
            return ServiceResult.success(
                success,
                message="Device unregistered",
                metadata={"device_token": device_token[:20] + "..."}
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error unregistering device: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "unregister device", device_token)

    def get_send_statistics(
        self,
        provider: str,
        hours: int = 24,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Retrieve send statistics for push provider.
        
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
            stats = self.repository.push_get_statistics(provider, hours=hours)
            
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
            return self._handle_exception(e, "get push statistics", provider)

    def list_providers(
        self,
        include_config: bool = False,
        include_health: bool = False,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        List all configured push providers.
        
        Args:
            include_config: Include full configuration data
            include_health: Include health status
            
        Returns:
            ServiceResult containing list of providers
        """
        logger.info("Listing all push providers")
        
        try:
            providers = self.repository.push_list_providers(
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
                message=f"Retrieved {len(providers)} push providers",
                metadata={
                    "count": len(providers),
                    "include_config": include_config,
                    "include_health": include_health
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error listing push providers: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list push providers")