"""
Email provider configuration & health service (SES/SendGrid/Postmark/SMTP).

Manages email provider integrations including configuration, testing,
monitoring, and health checks.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
import logging
import re

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.integrations import ThirdPartyRepository
from app.models.integrations.api_integration import APIIntegration

logger = logging.getLogger(__name__)


class EmailProviderService(BaseService[APIIntegration, ThirdPartyRepository]):
    """
    Manage email provider configs, test send, and health checks.
    
    Supported providers:
    - AWS SES
    - SendGrid
    - Postmark
    - SMTP (generic)
    - Mailgun
    """

    # Email validation regex
    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )

    # Supported providers
    SUPPORTED_PROVIDERS = {
        "ses", "sendgrid", "postmark", "smtp", "mailgun"
    }

    def __init__(
        self, 
        repository: ThirdPartyRepository, 
        db_session: Session,
        rate_limit_per_hour: int = 1000
    ):
        """
        Initialize email provider service.
        
        Args:
            repository: Third-party repository instance
            db_session: SQLAlchemy database session
            rate_limit_per_hour: Default hourly rate limit for providers
        """
        super().__init__(repository, db_session)
        self._rate_limit_per_hour = rate_limit_per_hour
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("EmailProviderService initialized")

    def _validate_provider(self, provider: str) -> ServiceResult[bool]:
        """
        Validate email provider identifier.
        
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
                    message=f"Unsupported email provider: {provider}",
                    severity=ErrorSeverity.MEDIUM,
                    context={
                        "provider": provider,
                        "supported": list(self.SUPPORTED_PROVIDERS)
                    }
                )
            )
            
        return ServiceResult.success(True)

    def _validate_email(self, email: str) -> ServiceResult[bool]:
        """
        Validate email address format.
        
        Args:
            email: Email address to validate
            
        Returns:
            ServiceResult indicating validation success
        """
        if not email or not isinstance(email, str):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Email must be a non-empty string",
                    severity=ErrorSeverity.MEDIUM
                )
            )
            
        if not self.EMAIL_REGEX.match(email):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid email format: {email}",
                    severity=ErrorSeverity.MEDIUM,
                    context={"email": email}
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
        
        # Provider-specific validation
        if provider_lower == "ses":
            required = ["region", "access_key_id", "secret_access_key"]
        elif provider_lower == "sendgrid":
            required = ["api_key"]
        elif provider_lower == "postmark":
            required = ["server_token"]
        elif provider_lower == "smtp":
            required = ["host", "port", "username", "password"]
        elif provider_lower == "mailgun":
            required = ["api_key", "domain"]
        else:
            required = []
        
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
        Create or update email provider configuration.
        
        Args:
            provider: Provider identifier
            config: Provider configuration data
            updated_by: UUID of user making the change
            validate_immediately: Test configuration after saving
            
        Returns:
            ServiceResult containing saved configuration
        """
        logger.info(
            f"Upserting config for email provider: {provider}",
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
            enhanced_config = {
                **config,
                "updated_by": str(updated_by) if updated_by else None,
                "updated_at": datetime.utcnow().isoformat(),
                "rate_limit_per_hour": config.get(
                    "rate_limit_per_hour", 
                    self._rate_limit_per_hour
                )
            }
            
            # Save configuration
            result = self.repository.email_upsert_config(provider, enhanced_config)
            
            # Clear cache
            cache_key = f"email_config_{provider}"
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
                    result["validation_details"] = validation_result.error
            
            # Commit transaction
            self.db.commit()
            
            logger.info(
                f"Email provider config saved successfully: {provider}",
                extra={"provider": provider}
            )
            
            return ServiceResult.success(
                result or {},
                message=f"Email provider config saved for {provider}",
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
            return self._handle_exception(e, "upsert email provider config", provider)

    def get_config(
        self,
        provider: str,
        use_cache: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Retrieve email provider configuration.
        
        Args:
            provider: Provider identifier
            use_cache: Use cached configuration if available
            
        Returns:
            ServiceResult containing provider configuration
        """
        logger.debug(f"Retrieving config for email provider: {provider}")
        
        # Validate provider
        provider_validation = self._validate_provider(provider)
        if not provider_validation.success:
            return provider_validation
        
        try:
            cache_key = f"email_config_{provider}"
            
            # Check cache
            if use_cache and cache_key in self._config_cache:
                logger.debug(f"Returning cached config for {provider}")
                return ServiceResult.success(
                    self._config_cache[cache_key],
                    message=f"Retrieved cached config for {provider}",
                    metadata={"provider": provider, "cached": True}
                )
            
            # Fetch from repository
            config = self.repository.email_get_config(provider)
            
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
            return self._handle_exception(e, "get email provider config", provider)

    def health_check(
        self,
        provider: str,
        timeout: int = 10,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Perform health check for email provider.
        
        Validates credentials, connectivity, and basic functionality
        without actually sending emails.
        
        Args:
            provider: Provider identifier
            timeout: Health check timeout in seconds
            
        Returns:
            ServiceResult containing health status and metrics
        """
        logger.info(f"Performing health check for email provider: {provider}")
        
        # Validate provider
        provider_validation = self._validate_provider(provider)
        if not provider_validation.success:
            return provider_validation

        try:
            from datetime import datetime
            start_time = datetime.utcnow()
            
            # Execute health check
            health = self.repository.email_health_check(provider, timeout=timeout)
            
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
        to_email: str,
        subject: str = "Test Email",
        html_body: Optional[str] = None,
        text_body: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Send test email through provider.
        
        Args:
            provider: Provider identifier
            to_email: Recipient email address
            subject: Email subject line
            html_body: HTML email body
            text_body: Plain text email body
            from_email: Sender email address
            from_name: Sender display name
            
        Returns:
            ServiceResult containing send status and message ID
        """
        logger.info(
            f"Sending test email via {provider} to {to_email}",
            extra={"provider": provider, "to_email": to_email}
        )
        
        # Validate provider
        provider_validation = self._validate_provider(provider)
        if not provider_validation.success:
            return provider_validation
        
        # Validate recipient email
        email_validation = self._validate_email(to_email)
        if not email_validation.success:
            return email_validation
        
        # Validate sender email if provided
        if from_email:
            sender_validation = self._validate_email(from_email)
            if not sender_validation.success:
                return sender_validation
        
        # Ensure at least one body type is provided
        if not html_body and not text_body:
            text_body = f"This is a test email from {provider} email provider."
            html_body = f"<p>This is a test email from <strong>{provider}</strong> email provider.</p>"

        try:
            # Send test email
            result = self.repository.email_send_test(
                provider=provider,
                to_email=to_email,
                subject=subject,
                html_body=html_body or "",
                text_body=text_body or "",
                from_email=from_email,
                from_name=from_name
            )
            
            # Commit transaction
            self.db.commit()
            
            success = result.get("success", False)
            
            if success:
                logger.info(
                    f"Test email sent successfully via {provider}",
                    extra={
                        "provider": provider,
                        "to_email": to_email,
                        "message_id": result.get("message_id")
                    }
                )
                
                return ServiceResult.success(
                    result,
                    message=f"Test email sent via {provider}",
                    metadata={
                        "provider": provider,
                        "to_email": to_email,
                        "message_id": result.get("message_id")
                    }
                )
            else:
                logger.warning(
                    f"Test email failed for {provider}",
                    extra={"provider": provider, "error": result.get("error")}
                )
                
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        message=f"Failed to send test email via {provider}",
                        severity=ErrorSeverity.MEDIUM,
                        context={
                            "provider": provider,
                            "to_email": to_email,
                            "error": result.get("error")
                        }
                    )
                )
                
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error sending test email via {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to log test email for {provider}",
                    severity=ErrorSeverity.MEDIUM,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error sending test email via {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "send test email", to_email)

    def get_send_statistics(
        self,
        provider: str,
        hours: int = 24,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Retrieve send statistics for email provider.
        
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
            stats = self.repository.email_get_statistics(provider, hours=hours)
            
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
            return self._handle_exception(e, "get email statistics", provider)

    def list_providers(
        self,
        include_config: bool = False,
        include_health: bool = False,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        List all configured email providers.
        
        Args:
            include_config: Include full configuration data
            include_health: Include health status
            
        Returns:
            ServiceResult containing list of providers
        """
        logger.info("Listing all email providers")
        
        try:
            providers = self.repository.email_list_providers(
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
                message=f"Retrieved {len(providers)} email providers",
                metadata={
                    "count": len(providers),
                    "include_config": include_config,
                    "include_health": include_health
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error listing email providers: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list email providers")