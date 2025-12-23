"""
Integration orchestrator service (registry, health, rate-limits, provider status).

This is the main orchestration layer for all integration services, providing
a unified interface for managing multiple integration types.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import UUID
import logging
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.integrations import (
    IntegrationAggregateRepository,
    APIIntegrationRepository,
    ThirdPartyRepository,
)
from app.models.integrations.api_integration import APIIntegration

logger = logging.getLogger(__name__)


class IntegrationService(BaseService[APIIntegration, APIIntegrationRepository]):
    """
    Top-level orchestrator for integrations: provider registry, health, rate-limits.
    
    This service coordinates between different integration types and provides
    centralized management, monitoring, and diagnostics capabilities.
    """

    def __init__(
        self,
        api_repo: APIIntegrationRepository,
        third_party_repo: ThirdPartyRepository,
        aggregate_repo: IntegrationAggregateRepository,
        db_session: Session,
        default_rate_limit: int = 1000,
        rate_limit_window_seconds: int = 3600,
    ):
        """
        Initialize integration orchestration service.
        
        Args:
            api_repo: API integration repository
            third_party_repo: Third-party integration repository
            aggregate_repo: Aggregate/analytics repository
            db_session: SQLAlchemy database session
            default_rate_limit: Default rate limit for providers
            rate_limit_window_seconds: Rate limit time window
        """
        super().__init__(api_repo, db_session)
        self.api_repo = api_repo
        self.third_party_repo = third_party_repo
        self.aggregate_repo = aggregate_repo
        self._default_rate_limit = default_rate_limit
        self._rate_limit_window = rate_limit_window_seconds
        self._rate_limit_buckets: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "reset_at": datetime.utcnow()}
        )
        
        logger.info("IntegrationService initialized")

    # ==================================================================
    # Provider Registry & Configuration
    # ==================================================================

    def _validate_provider_config(
        self, 
        provider: str, 
        config: Dict[str, Any]
    ) -> ServiceResult[bool]:
        """
        Validate provider configuration structure.
        
        Args:
            provider: Provider identifier
            config: Configuration dictionary
            
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
            
        if not config or not isinstance(config, dict):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Config must be a non-empty dictionary",
                    severity=ErrorSeverity.MEDIUM,
                    context={"provider": provider}
                )
            )
        
        # Check for required base fields
        required_fields = ["type", "enabled"]
        missing = [f for f in required_fields if f not in config]
        
        if missing:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Missing required config fields: {missing}",
                    severity=ErrorSeverity.MEDIUM,
                    context={
                        "provider": provider,
                        "missing_fields": missing
                    }
                )
            )
        
        # Validate provider type
        valid_types = [
            "api", "payment", "email", "sms", "push", 
            "calendar", "analytics", "storage", "other"
        ]
        if config.get("type") not in valid_types:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid provider type: {config.get('type')}",
                    severity=ErrorSeverity.MEDIUM,
                    context={
                        "provider": provider,
                        "type": config.get("type"),
                        "valid_types": valid_types
                    }
                )
            )
        
        return ServiceResult.success(True)

    def register_provider(
        self,
        provider: str,
        config: Dict[str, Any],
        created_by: Optional[UUID] = None,
        auto_enable: bool = False,
        validate_credentials: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Register a provider with credentials and defaults.
        
        Creates a new provider integration with the specified configuration,
        optionally validating credentials before activation.
        
        Args:
            provider: Provider identifier (unique)
            config: Provider configuration including credentials
            created_by: UUID of user registering the provider
            auto_enable: Enable provider immediately after registration
            validate_credentials: Validate credentials before saving
            
        Returns:
            ServiceResult containing registered provider details
        """
        logger.info(
            f"Registering new provider: {provider}",
            extra={"provider": provider, "auto_enable": auto_enable}
        )
        
        # Validate configuration
        validation = self._validate_provider_config(provider, config)
        if not validation.success:
            return validation

        try:
            # Check if provider already exists
            existing = self.api_repo.get_provider_config(provider)
            if existing:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.CONFLICT,
                        message=f"Provider {provider} already registered",
                        severity=ErrorSeverity.MEDIUM,
                        context={
                            "provider": provider,
                            "existing_config": existing
                        }
                    )
                )
            
            # Enhance config with metadata
            enhanced_config = {
                **config,
                "enabled": auto_enable if auto_enable else config.get("enabled", False),
                "created_by": str(created_by) if created_by else None,
                "created_at": datetime.utcnow().isoformat(),
                "rate_limit": config.get("rate_limit", self._default_rate_limit),
                "rate_limit_window": config.get(
                    "rate_limit_window", 
                    self._rate_limit_window
                ),
                "health_check_interval": config.get("health_check_interval", 300),
                "retry_config": config.get("retry_config", {
                    "max_retries": 3,
                    "backoff_factor": 2,
                    "initial_delay": 1
                })
            }
            
            # Validate credentials if requested
            if validate_credentials and enhanced_config.get("enabled"):
                validation_result = self._validate_provider_credentials(
                    provider, 
                    enhanced_config
                )
                if not validation_result.success:
                    logger.warning(
                        f"Credential validation failed for {provider}, "
                        "disabling provider",
                        extra={"provider": provider}
                    )
                    enhanced_config["enabled"] = False
                    enhanced_config["validation_error"] = str(validation_result.error)
            
            # Register provider
            result = self.api_repo.register_provider(
                provider, 
                enhanced_config, 
                created_by=created_by
            )
            
            # Commit transaction
            self.db.commit()
            
            logger.info(
                f"Provider registered successfully: {provider}",
                extra={
                    "provider": provider,
                    "enabled": enhanced_config["enabled"]
                }
            )
            
            return ServiceResult.success(
                result or {},
                message=f"Provider {provider} registered successfully",
                metadata={
                    "provider": provider,
                    "enabled": enhanced_config["enabled"],
                    "type": enhanced_config["type"]
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error registering provider {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to register provider {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error registering provider {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "register provider", provider)

    def _validate_provider_credentials(
        self,
        provider: str,
        config: Dict[str, Any]
    ) -> ServiceResult[bool]:
        """
        Validate provider credentials by attempting a test connection.
        
        Args:
            provider: Provider identifier
            config: Provider configuration
            
        Returns:
            ServiceResult indicating validation success
        """
        try:
            # Delegate to repository for actual validation
            valid = self.api_repo.validate_provider_credentials(provider, config)
            
            if valid:
                return ServiceResult.success(True)
            else:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.AUTHENTICATION_ERROR,
                        message=f"Invalid credentials for {provider}",
                        severity=ErrorSeverity.HIGH,
                        context={"provider": provider}
                    )
                )
                
        except Exception as e:
            logger.error(
                f"Error validating credentials for {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                    message=f"Credential validation failed for {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={"provider": provider, "error": str(e)}
                )
            )

    def update_provider_config(
        self,
        provider: str,
        config_update: Dict[str, Any],
        updated_by: Optional[UUID] = None,
        partial_update: bool = True,
        validate_after_update: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Update provider configuration.
        
        Args:
            provider: Provider identifier
            config_update: Configuration fields to update
            updated_by: UUID of user making the update
            partial_update: Apply partial update (merge) vs full replace
            validate_after_update: Validate configuration after update
            
        Returns:
            ServiceResult containing updated configuration
        """
        logger.info(
            f"Updating config for provider: {provider}",
            extra={"provider": provider, "partial": partial_update}
        )
        
        if not config_update or not isinstance(config_update, dict):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Config update must be a non-empty dictionary",
                    severity=ErrorSeverity.MEDIUM
                )
            )

        try:
            # Get existing config
            existing = self.api_repo.get_provider_config(provider)
            if not existing:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Provider {provider} not found",
                        severity=ErrorSeverity.MEDIUM,
                        context={"provider": provider}
                    )
                )
            
            # Prepare update
            if partial_update:
                updated_config = {**existing, **config_update}
            else:
                updated_config = config_update
            
            # Add metadata
            updated_config["updated_by"] = str(updated_by) if updated_by else None
            updated_config["updated_at"] = datetime.utcnow().isoformat()
            
            # Validate updated config
            validation = self._validate_provider_config(provider, updated_config)
            if not validation.success:
                return validation
            
            # If credentials changed and provider is enabled, validate them
            if (validate_after_update and 
                updated_config.get("enabled") and 
                self._credentials_changed(existing, updated_config)):
                
                cred_validation = self._validate_provider_credentials(
                    provider, 
                    updated_config
                )
                if not cred_validation.success:
                    logger.warning(
                        f"New credentials invalid for {provider}, disabling",
                        extra={"provider": provider}
                    )
                    updated_config["enabled"] = False
                    updated_config["credential_validation_error"] = str(
                        cred_validation.error
                    )
            
            # Update config
            result = self.api_repo.update_provider_config(
                provider, 
                updated_config, 
                updated_by=updated_by
            )
            
            # Commit transaction
            self.db.commit()
            
            logger.info(
                f"Provider config updated successfully: {provider}",
                extra={"provider": provider}
            )
            
            return ServiceResult.success(
                result or {},
                message=f"Provider {provider} config updated",
                metadata={
                    "provider": provider,
                    "partial_update": partial_update
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error updating config for {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to update config for {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error updating config for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update provider config", provider)

    def _credentials_changed(
        self, 
        old_config: Dict[str, Any], 
        new_config: Dict[str, Any]
    ) -> bool:
        """
        Check if credentials fields have changed.
        
        Args:
            old_config: Previous configuration
            new_config: New configuration
            
        Returns:
            True if credentials changed, False otherwise
        """
        credential_fields = [
            "api_key", "secret_key", "access_token", "refresh_token",
            "password", "client_id", "client_secret", "private_key"
        ]
        
        for field in credential_fields:
            if old_config.get(field) != new_config.get(field):
                return True
        
        return False

    def get_provider_config(
        self,
        provider: str,
        include_sensitive: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Retrieve provider configuration.
        
        Args:
            provider: Provider identifier
            include_sensitive: Include sensitive fields (credentials)
            
        Returns:
            ServiceResult containing provider configuration
        """
        logger.debug(f"Retrieving config for provider: {provider}")
        
        try:
            config = self.api_repo.get_provider_config(provider)
            
            if not config:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Provider {provider} not found",
                        severity=ErrorSeverity.MEDIUM,
                        context={"provider": provider}
                    )
                )
            
            # Redact sensitive fields if not requested
            if not include_sensitive:
                config = self._redact_sensitive_fields(config)
            
            return ServiceResult.success(
                config,
                message=f"Retrieved config for {provider}",
                metadata={
                    "provider": provider,
                    "include_sensitive": include_sensitive
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error retrieving config for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get provider config", provider)

    def _redact_sensitive_fields(
        self, 
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Redact sensitive credential fields from configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Configuration with redacted sensitive fields
        """
        sensitive_fields = [
            "api_key", "secret_key", "access_token", "refresh_token",
            "password", "client_secret", "private_key", "secret_access_key"
        ]
        
        redacted = config.copy()
        
        for field in sensitive_fields:
            if field in redacted and redacted[field]:
                # Show first 4 and last 4 characters
                value = str(redacted[field])
                if len(value) > 8:
                    redacted[field] = f"{value[:4]}...{value[-4:]}"
                else:
                    redacted[field] = "***REDACTED***"
        
        return redacted

    def list_providers(
        self,
        provider_type: Optional[str] = None,
        enabled_only: bool = False,
        include_config: bool = False,
        include_health: bool = False,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        List all registered providers with optional filters.
        
        Args:
            provider_type: Filter by provider type
            enabled_only: Only return enabled providers
            include_config: Include full configuration
            include_health: Include health status
            
        Returns:
            ServiceResult containing list of providers
        """
        logger.info(
            f"Listing providers (type={provider_type}, enabled_only={enabled_only})"
        )
        
        try:
            providers = self.api_repo.list_providers(
                provider_type=provider_type,
                enabled_only=enabled_only,
                include_config=include_config
            )
            
            # Add health status if requested
            if include_health:
                for provider_data in providers:
                    provider = provider_data.get("provider")
                    if provider:
                        health = self.get_provider_health(provider)
                        provider_data["health"] = (
                            health.data if health.success 
                            else {"status": "unknown"}
                        )
            
            # Redact sensitive fields if config included
            if include_config:
                for provider_data in providers:
                    if "config" in provider_data:
                        provider_data["config"] = self._redact_sensitive_fields(
                            provider_data["config"]
                        )
            
            return ServiceResult.success(
                providers,
                message=f"Retrieved {len(providers)} providers",
                metadata={
                    "count": len(providers),
                    "provider_type": provider_type,
                    "enabled_only": enabled_only
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error listing providers: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list providers")

    def enable_provider(
        self,
        provider: str,
        enabled_by: Optional[UUID] = None,
        validate_before_enable: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Enable a provider.
        
        Args:
            provider: Provider identifier
            enabled_by: UUID of user enabling the provider
            validate_before_enable: Validate credentials before enabling
            
        Returns:
            ServiceResult containing updated provider status
        """
        logger.info(f"Enabling provider: {provider}")
        
        try:
            # Get current config
            config_result = self.get_provider_config(provider, include_sensitive=True)
            if not config_result.success:
                return config_result
            
            config = config_result.data
            
            # Validate credentials if requested
            if validate_before_enable:
                validation = self._validate_provider_credentials(provider, config)
                if not validation.success:
                    return ServiceResult.failure(
                        error=ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Cannot enable {provider}: invalid credentials",
                            severity=ErrorSeverity.HIGH,
                            context={
                                "provider": provider,
                                "validation_error": str(validation.error)
                            }
                        )
                    )
            
            # Update config
            update_result = self.update_provider_config(
                provider,
                {
                    "enabled": True,
                    "enabled_by": str(enabled_by) if enabled_by else None,
                    "enabled_at": datetime.utcnow().isoformat()
                },
                updated_by=enabled_by,
                validate_after_update=False
            )
            
            return update_result
            
        except Exception as e:
            logger.error(
                f"Error enabling provider {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "enable provider", provider)

    def disable_provider(
        self,
        provider: str,
        disabled_by: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Disable a provider.
        
        Args:
            provider: Provider identifier
            disabled_by: UUID of user disabling the provider
            reason: Reason for disabling
            
        Returns:
            ServiceResult containing updated provider status
        """
        logger.info(
            f"Disabling provider: {provider}",
            extra={"provider": provider, "reason": reason}
        )
        
        try:
            update_result = self.update_provider_config(
                provider,
                {
                    "enabled": False,
                    "disabled_by": str(disabled_by) if disabled_by else None,
                    "disabled_at": datetime.utcnow().isoformat(),
                    "disabled_reason": reason
                },
                updated_by=disabled_by,
                validate_after_update=False
            )
            
            return update_result
            
        except Exception as e:
            logger.error(
                f"Error disabling provider {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "disable provider", provider)

    # ==================================================================
    # Health & Monitoring
    # ==================================================================

    def get_provider_health(
        self,
        provider: str,
        use_cache: bool = True,
        cache_ttl: int = 60,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Return last health check results and provider metrics.
        
        Args:
            provider: Provider identifier
            use_cache: Use cached health data if available
            cache_ttl: Cache time-to-live in seconds
            
        Returns:
            ServiceResult containing health status and metrics
        """
        logger.debug(f"Retrieving health for provider: {provider}")
        
        try:
            health = self.aggregate_repo.get_provider_health(
                provider,
                use_cache=use_cache,
                cache_ttl=cache_ttl
            )
            
            if not health:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No health data found for {provider}",
                        severity=ErrorSeverity.LOW,
                        context={"provider": provider}
                    )
                )
            
            # Enhance with status classification
            health["status_classification"] = self._classify_health_status(health)
            
            return ServiceResult.success(
                health,
                message=f"Retrieved health for {provider}",
                metadata={
                    "provider": provider,
                    "cached": use_cache,
                    "status": health.get("status")
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error retrieving health for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get provider health", provider)

    def _classify_health_status(
        self, 
        health: Dict[str, Any]
    ) -> str:
        """
        Classify health status into categories.
        
        Args:
            health: Health data dictionary
            
        Returns:
            Health classification (healthy, degraded, unhealthy, unknown)
        """
        status = health.get("status", "").lower()
        uptime = health.get("uptime_percentage", 100)
        error_rate = health.get("error_rate", 0)
        avg_latency = health.get("avg_latency_ms", 0)
        
        if status == "healthy" and uptime > 99 and error_rate < 1:
            return "healthy"
        elif status in ["healthy", "degraded"] and uptime > 95 and error_rate < 5:
            return "degraded"
        elif status == "unhealthy" or uptime < 95 or error_rate > 10:
            return "unhealthy"
        else:
            return "unknown"

    # ==================================================================
    # Rate Limiting
    # ==================================================================

    def check_and_consume_rate_limit(
        self,
        provider: str,
        key: Optional[str] = None,
        cost: int = 1,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Verify rate limit budget and consume it if allowed.
        
        Implements token bucket algorithm with configurable rates per provider.
        
        Args:
            provider: Provider identifier
            key: Optional sub-key for granular rate limiting
            cost: Number of tokens to consume (default: 1)
            
        Returns:
            ServiceResult with allowed status and remaining quota
        """
        logger.debug(
            f"Checking rate limit for {provider} (key={key}, cost={cost})"
        )
        
        if cost <= 0:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Cost must be greater than 0",
                    severity=ErrorSeverity.LOW,
                    context={"cost": cost}
                )
            )

        try:
            # Get provider config for rate limits
            config_result = self.get_provider_config(provider)
            if not config_result.success:
                return config_result
            
            config = config_result.data
            rate_limit = config.get("rate_limit", self._default_rate_limit)
            window = config.get("rate_limit_window", self._rate_limit_window)
            
            # Check and consume rate limit
            result = self.api_repo.check_and_consume_rate_limit(
                provider=provider,
                key=key,
                cost=cost,
                limit=rate_limit,
                window=window
            )
            
            allowed = result.get("allowed", False)
            
            if allowed:
                self.db.commit()
                
                return ServiceResult.success(
                    result,
                    message=f"Rate limit consumed for {provider}",
                    metadata={
                        "provider": provider,
                        "cost": cost,
                        "remaining": result.get("remaining", 0)
                    }
                )
            else:
                logger.warning(
                    f"Rate limit exceeded for {provider}",
                    extra={
                        "provider": provider,
                        "key": key,
                        "cost": cost,
                        "reset_at": result.get("reset_at")
                    }
                )
                
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.RATE_LIMIT_EXCEEDED,
                        message=f"Rate limit exceeded for {provider}",
                        severity=ErrorSeverity.MEDIUM,
                        context={
                            "provider": provider,
                            "key": key,
                            "reset_at": result.get("reset_at"),
                            "limit": rate_limit
                        }
                    )
                )
                
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error checking rate limit for {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to check rate limit for {provider}",
                    severity=ErrorSeverity.MEDIUM,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error checking rate limit for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "consume rate limit", provider)

    def get_rate_limit_status(
        self,
        provider: str,
        key: Optional[str] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get current rate limit status without consuming quota.
        
        Args:
            provider: Provider identifier
            key: Optional sub-key
            
        Returns:
            ServiceResult containing rate limit status
        """
        logger.debug(f"Getting rate limit status for {provider} (key={key})")
        
        try:
            status = self.api_repo.get_rate_limit_status(provider, key=key)
            
            return ServiceResult.success(
                status or {},
                message=f"Retrieved rate limit status for {provider}",
                metadata={"provider": provider, "key": key}
            )
            
        except Exception as e:
            logger.error(
                f"Error getting rate limit status for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get rate limit status", provider)

    def reset_rate_limit(
        self,
        provider: str,
        key: Optional[str] = None,
        reset_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Reset rate limit counters for a provider.
        
        Args:
            provider: Provider identifier
            key: Optional sub-key
            reset_by: UUID of user resetting limits
            
        Returns:
            ServiceResult indicating reset success
        """
        logger.info(
            f"Resetting rate limit for {provider} (key={key})",
            extra={"provider": provider, "key": key, "reset_by": str(reset_by)}
        )
        
        try:
            success = self.api_repo.reset_rate_limit(
                provider, 
                key=key,
                reset_by=reset_by
            )
            
            self.db.commit()
            
            return ServiceResult.success(
                success,
                message=f"Rate limit reset for {provider}",
                metadata={"provider": provider, "key": key}
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error resetting rate limit for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "reset rate limit", provider)

    # ==================================================================
    # Diagnostics & Analytics
    # ==================================================================

    def get_integration_overview(
        self,
        include_metrics: bool = True,
        include_health: bool = True,
        time_range_hours: int = 24,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Return summary of all providers, health, recent errors, and usage.
        
        Provides a comprehensive dashboard view of all integrations.
        
        Args:
            include_metrics: Include usage metrics
            include_health: Include health status
            time_range_hours: Hours of historical data to include
            
        Returns:
            ServiceResult containing integration overview
        """
        logger.info(
            f"Generating integration overview (hours={time_range_hours})"
        )
        
        try:
            overview = self.aggregate_repo.get_integration_overview(
                include_metrics=include_metrics,
                include_health=include_health,
                hours=time_range_hours
            )
            
            # Enhance with summary statistics
            if overview:
                overview["summary"] = self._generate_summary_stats(overview)
                overview["generated_at"] = datetime.utcnow().isoformat()
                overview["time_range_hours"] = time_range_hours
            
            return ServiceResult.success(
                overview or {},
                message="Integration overview generated",
                metadata={
                    "provider_count": len(overview.get("providers", [])),
                    "time_range_hours": time_range_hours
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error generating integration overview: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get integration overview")

    def _generate_summary_stats(
        self, 
        overview: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate summary statistics from overview data.
        
        Args:
            overview: Overview data dictionary
            
        Returns:
            Summary statistics
        """
        providers = overview.get("providers", [])
        
        total_providers = len(providers)
        enabled_providers = sum(
            1 for p in providers if p.get("enabled", False)
        )
        healthy_providers = sum(
            1 for p in providers 
            if p.get("health", {}).get("status") == "healthy"
        )
        
        total_requests = sum(
            p.get("metrics", {}).get("total_requests", 0)
            for p in providers
        )
        total_errors = sum(
            p.get("metrics", {}).get("total_errors", 0)
            for p in providers
        )
        
        overall_error_rate = (
            (total_errors / total_requests * 100) 
            if total_requests > 0 else 0
        )
        
        return {
            "total_providers": total_providers,
            "enabled_providers": enabled_providers,
            "healthy_providers": healthy_providers,
            "unhealthy_providers": enabled_providers - healthy_providers,
            "health_percentage": (
                (healthy_providers / enabled_providers * 100)
                if enabled_providers > 0 else 0
            ),
            "total_requests": total_requests,
            "total_errors": total_errors,
            "overall_error_rate": round(overall_error_rate, 2),
            "average_latency_ms": sum(
                p.get("metrics", {}).get("avg_latency_ms", 0)
                for p in providers
            ) / total_providers if total_providers > 0 else 0
        }

    def get_provider_analytics(
        self,
        provider: str,
        hours: int = 24,
        granularity: str = "hour",
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get detailed analytics for a specific provider.
        
        Args:
            provider: Provider identifier
            hours: Hours of historical data
            granularity: Data granularity (minute, hour, day)
            
        Returns:
            ServiceResult containing analytics data
        """
        logger.info(
            f"Retrieving analytics for {provider} "
            f"(hours={hours}, granularity={granularity})"
        )
        
        if granularity not in ["minute", "hour", "day"]:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid granularity: {granularity}",
                    severity=ErrorSeverity.LOW,
                    context={
                        "granularity": granularity,
                        "valid_values": ["minute", "hour", "day"]
                    }
                )
            )
        
        try:
            analytics = self.aggregate_repo.get_provider_analytics(
                provider=provider,
                hours=hours,
                granularity=granularity
            )
            
            return ServiceResult.success(
                analytics or {},
                message=f"Retrieved analytics for {provider}",
                metadata={
                    "provider": provider,
                    "hours": hours,
                    "granularity": granularity
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error retrieving analytics for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get provider analytics", provider)

    def get_error_log(
        self,
        provider: Optional[str] = None,
        severity: Optional[str] = None,
        hours: int = 24,
        limit: int = 100,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Retrieve integration error logs.
        
        Args:
            provider: Filter by provider (None for all)
            severity: Filter by severity (low, medium, high, critical)
            hours: Hours of historical data
            limit: Maximum number of errors to return
            
        Returns:
            ServiceResult containing error logs
        """
        logger.info(
            f"Retrieving error logs (provider={provider}, "
            f"severity={severity}, hours={hours})"
        )
        
        try:
            errors = self.aggregate_repo.get_error_log(
                provider=provider,
                severity=severity,
                hours=hours,
                limit=limit
            )
            
            return ServiceResult.success(
                errors or [],
                message=f"Retrieved {len(errors or [])} error logs",
                metadata={
                    "count": len(errors or []),
                    "provider": provider,
                    "severity": severity,
                    "hours": hours
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error retrieving error logs: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get error log")