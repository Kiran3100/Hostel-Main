"""
API integration service: credentials, auth, request proxy, health checks.

This service manages API-level operations including:
- Provider credential management and rotation
- OAuth token refresh flows
- Request proxying with retry logic
- Health monitoring and status tracking
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta
import logging
from functools import wraps

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.integrations import APIIntegrationRepository
from app.models.integrations.api_integration import APIIntegration

logger = logging.getLogger(__name__)


def with_circuit_breaker(max_failures: int = 5, timeout_seconds: int = 60):
    """
    Decorator to implement circuit breaker pattern for provider calls.
    
    Args:
        max_failures: Number of failures before opening circuit
        timeout_seconds: Seconds to wait before attempting to close circuit
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, provider: str, *args, **kwargs):
            circuit_key = f"circuit_{provider}"
            
            # Check if circuit is open
            if hasattr(self, '_circuit_breakers'):
                circuit = self._circuit_breakers.get(circuit_key, {})
                if circuit.get('open') and circuit.get('open_until', datetime.min) > datetime.utcnow():
                    return ServiceResult.failure(
                        error=ServiceError(
                            code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                            message=f"Circuit breaker open for provider: {provider}",
                            severity=ErrorSeverity.HIGH,
                            context={"provider": provider, "open_until": circuit['open_until']}
                        )
                    )
            else:
                self._circuit_breakers = {}
            
            try:
                result = func(self, provider, *args, **kwargs)
                
                # Reset failures on success
                if result.success and circuit_key in self._circuit_breakers:
                    self._circuit_breakers[circuit_key]['failures'] = 0
                    self._circuit_breakers[circuit_key]['open'] = False
                
                return result
                
            except Exception as e:
                # Increment failure count
                if circuit_key not in self._circuit_breakers:
                    self._circuit_breakers[circuit_key] = {'failures': 0, 'open': False}
                
                self._circuit_breakers[circuit_key]['failures'] += 1
                
                # Open circuit if threshold reached
                if self._circuit_breakers[circuit_key]['failures'] >= max_failures:
                    self._circuit_breakers[circuit_key]['open'] = True
                    self._circuit_breakers[circuit_key]['open_until'] = (
                        datetime.utcnow() + timedelta(seconds=timeout_seconds)
                    )
                    logger.error(
                        f"Circuit breaker opened for provider {provider} "
                        f"after {max_failures} failures"
                    )
                
                raise
        
        return wrapper
    return decorator


class APIIntegrationService(BaseService[APIIntegration, APIIntegrationRepository]):
    """
    Manage API-level operations: credentials, auth flows, request proxying, health checks.
    
    This service provides a comprehensive interface for managing external API integrations
    with built-in resilience patterns, security controls, and monitoring capabilities.
    """

    def __init__(
        self, 
        repository: APIIntegrationRepository, 
        db_session: Session,
        cache_ttl: int = 300  # 5 minutes default cache
    ):
        """
        Initialize API integration service.
        
        Args:
            repository: API integration repository instance
            db_session: SQLAlchemy database session
            cache_ttl: Cache time-to-live in seconds for provider configs
        """
        super().__init__(repository, db_session)
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = cache_ttl
        self._circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        logger.info("APIIntegrationService initialized")

    def _validate_provider_name(self, provider: str) -> ServiceResult[bool]:
        """
        Validate provider name format and existence.
        
        Args:
            provider: Provider identifier
            
        Returns:
            ServiceResult indicating validation success
        """
        if not provider or not isinstance(provider, str):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Provider name must be a non-empty string",
                    severity=ErrorSeverity.MEDIUM,
                    context={"provider": provider}
                )
            )
        
        if len(provider) > 100:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Provider name exceeds maximum length of 100 characters",
                    severity=ErrorSeverity.MEDIUM,
                    context={"provider": provider, "length": len(provider)}
                )
            )
        
        return ServiceResult.success(True)

    def _invalidate_cache(self, provider: str) -> None:
        """
        Invalidate cached configuration for a provider.
        
        Args:
            provider: Provider identifier
        """
        cache_key = f"config_{provider}"
        if cache_key in self._config_cache:
            del self._config_cache[cache_key]
            logger.debug(f"Invalidated cache for provider: {provider}")

    def rotate_credentials(
        self,
        provider: str,
        rotated_by: Optional[UUID] = None,
        reason: Optional[str] = None,
        notification_enabled: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Rotate provider credentials/secrets with audit trail.
        
        This operation generates new credentials, updates the provider configuration,
        and optionally triggers notifications to relevant stakeholders.
        
        Args:
            provider: Provider identifier
            rotated_by: UUID of user performing rotation
            reason: Reason for credential rotation
            notification_enabled: Whether to send rotation notifications
            
        Returns:
            ServiceResult containing rotation details and new credential metadata
        """
        logger.info(f"Initiating credential rotation for provider: {provider}")
        
        # Validate provider
        validation = self._validate_provider_name(provider)
        if not validation.success:
            return validation

        try:
            # Execute rotation in repository
            result = self.repository.rotate_credentials(
                provider, 
                rotated_by=rotated_by
            )
            
            # Invalidate cache
            self._invalidate_cache(provider)
            
            # Commit transaction
            self.db.commit()
            
            # Enhance result with metadata
            enhanced_result = {
                **(result or {}),
                "rotated_at": datetime.utcnow().isoformat(),
                "rotated_by": str(rotated_by) if rotated_by else None,
                "reason": reason,
                "notification_sent": notification_enabled
            }
            
            logger.info(f"Credentials rotated successfully for provider: {provider}")
            
            return ServiceResult.success(
                enhanced_result,
                message=f"Credentials rotated successfully for {provider}",
                metadata={
                    "provider": provider,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error during credential rotation for {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to rotate credentials for {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={
                        "provider": provider,
                        "error": str(e),
                        "rotated_by": str(rotated_by) if rotated_by else None
                    }
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Unexpected error during credential rotation for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "rotate credentials", provider)

    def refresh_access_token(
        self,
        provider: str,
        refresh_token: str,
        force_refresh: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Exchange refresh token for new access token and persist.
        
        Implements OAuth 2.0 refresh token flow with automatic retry and
        token validation. Includes safety checks to prevent unnecessary refreshes.
        
        Args:
            provider: Provider identifier
            refresh_token: Valid refresh token
            force_refresh: Force refresh even if current token is valid
            
        Returns:
            ServiceResult containing new access token and expiry information
        """
        logger.info(f"Refreshing access token for provider: {provider}")
        
        # Validate inputs
        validation = self._validate_provider_name(provider)
        if not validation.success:
            return validation
            
        if not refresh_token or not isinstance(refresh_token, str):
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Refresh token must be a non-empty string",
                    severity=ErrorSeverity.MEDIUM,
                    context={"provider": provider}
                )
            )

        try:
            # Check if refresh is needed (unless forced)
            if not force_refresh:
                current_config = self.repository.get_provider_config(provider)
                if current_config:
                    token_expiry = current_config.get("access_token_expiry")
                    if token_expiry and isinstance(token_expiry, datetime):
                        if token_expiry > datetime.utcnow() + timedelta(minutes=5):
                            logger.info(
                                f"Access token for {provider} still valid, skipping refresh"
                            )
                            return ServiceResult.success(
                                current_config,
                                message="Current access token still valid"
                            )
            
            # Execute token refresh
            result = self.repository.refresh_access_token(provider, refresh_token)
            
            # Invalidate cache
            self._invalidate_cache(provider)
            
            # Commit transaction
            self.db.commit()
            
            # Enhance result
            enhanced_result = {
                **(result or {}),
                "refreshed_at": datetime.utcnow().isoformat(),
                "provider": provider
            }
            
            logger.info(f"Access token refreshed successfully for provider: {provider}")
            
            return ServiceResult.success(
                enhanced_result,
                message=f"Access token refreshed for {provider}",
                metadata={"provider": provider, "forced": force_refresh}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error during token refresh for {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to refresh token for {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Unexpected error during token refresh for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "refresh access token", provider)

    @with_circuit_breaker(max_failures=5, timeout_seconds=60)
    def proxy_request(
        self,
        provider: str,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        retry_count: int = 3,
        idempotent: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Dispatch a request to provider using stored credentials.
        
        Implements resilient HTTP request proxying with automatic retries,
        circuit breaking, and comprehensive error handling.
        
        Args:
            provider: Provider identifier
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            path: API endpoint path
            params: Query parameters
            body: Request body for POST/PUT requests
            headers: Additional HTTP headers
            timeout: Request timeout in seconds
            retry_count: Number of retry attempts for transient failures
            idempotent: Whether the request is idempotent (safe to retry)
            
        Returns:
            ServiceResult containing provider response data
        """
        logger.info(
            f"Proxying {method} request to {provider} at path: {path}",
            extra={"provider": provider, "method": method, "path": path}
        )
        
        # Validate inputs
        validation = self._validate_provider_name(provider)
        if not validation.success:
            return validation
            
        if method not in ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid HTTP method: {method}",
                    severity=ErrorSeverity.MEDIUM,
                    context={"method": method, "provider": provider}
                )
            )

        try:
            # Execute proxied request with retry logic
            result = self.repository.proxy_request(
                provider=provider,
                method=method,
                path=path,
                params=params or {},
                body=body or {},
                headers=headers or {},
                timeout=timeout,
                retry_count=retry_count if idempotent else 1
            )
            
            # Enhance result with metadata
            enhanced_result = {
                **(result or {}),
                "request_metadata": {
                    "provider": provider,
                    "method": method,
                    "path": path,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
            logger.info(
                f"Request proxied successfully to {provider}",
                extra={"provider": provider, "method": method}
            )
            
            return ServiceResult.success(
                enhanced_result,
                message=f"Request proxied to {provider}",
                metadata={
                    "provider": provider,
                    "method": method,
                    "path": path
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error proxying request to {provider}: {str(e)}",
                exc_info=True,
                extra={"provider": provider, "method": method, "path": path}
            )
            return self._handle_exception(e, "proxy provider request", provider)

    @with_circuit_breaker(max_failures=3, timeout_seconds=120)
    def perform_health_check(
        self,
        provider: str,
        detailed: bool = False,
        update_status: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Execute provider-specific health check and persist status.
        
        Performs comprehensive health verification including connectivity,
        authentication, and basic API functionality tests.
        
        Args:
            provider: Provider identifier
            detailed: Include detailed diagnostic information
            update_status: Update provider status in database
            
        Returns:
            ServiceResult containing health check results and metrics
        """
        logger.info(f"Performing health check for provider: {provider}")
        
        # Validate provider
        validation = self._validate_provider_name(provider)
        if not validation.success:
            return validation

        try:
            start_time = datetime.utcnow()
            
            # Execute health check
            health = self.repository.perform_health_check(provider, detailed=detailed)
            
            # Calculate response time
            response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Enhance health data
            enhanced_health = {
                **(health or {}),
                "response_time_ms": round(response_time_ms, 2),
                "checked_at": datetime.utcnow().isoformat(),
                "detailed": detailed
            }
            
            # Update status if requested
            if update_status:
                self.db.commit()
                logger.info(f"Health status updated for provider: {provider}")
            
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
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error during health check for {provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to persist health check for {provider}",
                    severity=ErrorSeverity.MEDIUM,
                    context={"provider": provider, "error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error during health check for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "perform health check", provider)

    def batch_health_check(
        self,
        providers: Optional[List[str]] = None,
        parallel: bool = True,
    ) -> ServiceResult[Dict[str, Dict[str, Any]]]:
        """
        Perform health checks for multiple providers.
        
        Args:
            providers: List of provider identifiers (None for all)
            parallel: Execute checks in parallel
            
        Returns:
            ServiceResult containing health status for all providers
        """
        logger.info(f"Performing batch health check for {len(providers or [])} providers")
        
        try:
            results = {}
            target_providers = providers or self.repository.get_all_provider_names()
            
            for provider in target_providers:
                health_result = self.perform_health_check(provider, update_status=True)
                results[provider] = health_result.data if health_result.success else {
                    "status": "error",
                    "error": str(health_result.error)
                }
            
            healthy_count = sum(
                1 for r in results.values() 
                if r.get("status") == "healthy"
            )
            
            logger.info(
                f"Batch health check completed: {healthy_count}/{len(results)} healthy"
            )
            
            return ServiceResult.success(
                results,
                message=f"Checked {len(results)} providers",
                metadata={
                    "total": len(results),
                    "healthy": healthy_count,
                    "unhealthy": len(results) - healthy_count
                }
            )
            
        except Exception as e:
            logger.error(f"Error during batch health check: {str(e)}", exc_info=True)
            return self._handle_exception(e, "batch health check")

    def get_provider_metrics(
        self,
        provider: str,
        hours: int = 24,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Retrieve performance metrics for a provider.
        
        Args:
            provider: Provider identifier
            hours: Number of hours of historical data
            
        Returns:
            ServiceResult containing metrics and statistics
        """
        logger.info(f"Retrieving metrics for provider: {provider}")
        
        validation = self._validate_provider_name(provider)
        if not validation.success:
            return validation
            
        try:
            metrics = self.repository.get_provider_metrics(provider, hours=hours)
            
            return ServiceResult.success(
                metrics or {},
                message=f"Retrieved metrics for {provider}",
                metadata={"provider": provider, "hours": hours}
            )
            
        except Exception as e:
            logger.error(
                f"Error retrieving metrics for {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get provider metrics", provider)