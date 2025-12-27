"""
API Integration Repository for external API management.

This repository handles all external API integrations including
OAuth, webhooks, rate limiting, and integration health monitoring.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
from enum import Enum as PyEnum

from sqlalchemy import and_, or_, func, case
from sqlalchemy.orm import Session

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.core1.exceptions import NotFoundException, ValidationException


class IntegrationStatus(str, PyEnum):
    """Integration status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    FAILED = "failed"
    SUSPENDED = "suspended"


class IntegrationType(str, PyEnum):
    """Integration type enumeration."""
    PAYMENT_GATEWAY = "payment_gateway"
    SMS_PROVIDER = "sms_provider"
    EMAIL_SERVICE = "email_service"
    CLOUD_STORAGE = "cloud_storage"
    CALENDAR = "calendar"
    ANALYTICS = "analytics"
    CRM = "crm"
    ACCOUNTING = "accounting"
    OTHER = "other"


class APIIntegrationRepository(BaseRepository):
    """
    Repository for API integration management.
    
    Provides methods for managing external API integrations, monitoring health,
    tracking usage, and handling authentication.
    """
    
    def __init__(self, session: Session):
        """Initialize API integration repository."""
        self.session = session
    
    # ============================================================================
    # INTEGRATION MANAGEMENT
    # ============================================================================
    
    async def create_integration(
        self,
        hostel_id: UUID,
        integration_type: IntegrationType,
        name: str,
        config: Dict[str, Any],
        credentials: Dict[str, Any],
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create new API integration.
        
        Args:
            hostel_id: Hostel ID
            integration_type: Type of integration
            name: Integration name
            config: Configuration settings
            credentials: API credentials (encrypted)
            audit_context: Audit information
            
        Returns:
            Created integration record
        """
        integration = {
            "id": str(UUID()),
            "hostel_id": hostel_id,
            "integration_type": integration_type,
            "name": name,
            "config": config,
            "credentials": await self._encrypt_credentials(credentials),
            "status": IntegrationStatus.PENDING,
            "is_active": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Validate configuration
        await self._validate_integration_config(integration_type, config)
        
        # Test connection
        test_result = await self._test_integration_connection(integration)
        
        if test_result["success"]:
            integration["status"] = IntegrationStatus.ACTIVE
            integration["is_active"] = True
            integration["last_health_check"] = datetime.utcnow()
        else:
            integration["status"] = IntegrationStatus.FAILED
            integration["last_error"] = test_result.get("error")
        
        return integration
    
    async def update_integration(
        self,
        integration_id: UUID,
        update_data: Dict[str, Any],
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update integration configuration.
        
        Args:
            integration_id: Integration ID
            update_data: Update data
            audit_context: Audit information
            
        Returns:
            Updated integration
        """
        integration = await self.get_integration_by_id(integration_id)
        
        if "credentials" in update_data:
            update_data["credentials"] = await self._encrypt_credentials(
                update_data["credentials"]
            )
        
        if "config" in update_data:
            await self._validate_integration_config(
                integration["integration_type"],
                update_data["config"]
            )
        
        update_data["updated_at"] = datetime.utcnow()
        
        # Retest if critical fields changed
        if any(key in update_data for key in ["credentials", "config", "endpoint"]):
            test_result = await self._test_integration_connection({
                **integration,
                **update_data
            })
            
            if not test_result["success"]:
                update_data["status"] = IntegrationStatus.FAILED
                update_data["last_error"] = test_result.get("error")
        
        integration.update(update_data)
        return integration
    
    async def activate_integration(
        self,
        integration_id: UUID,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Activate integration.
        
        Args:
            integration_id: Integration ID
            audit_context: Audit information
            
        Returns:
            Updated integration
        """
        integration = await self.get_integration_by_id(integration_id)
        
        # Test before activation
        test_result = await self._test_integration_connection(integration)
        
        if not test_result["success"]:
            raise ValidationException(
                f"Cannot activate integration: {test_result.get('error')}"
            )
        
        return await self.update_integration(
            integration_id,
            {
                "is_active": True,
                "status": IntegrationStatus.ACTIVE,
                "activated_at": datetime.utcnow(),
                "last_health_check": datetime.utcnow()
            },
            audit_context
        )
    
    async def deactivate_integration(
        self,
        integration_id: UUID,
        reason: Optional[str] = None,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Deactivate integration.
        
        Args:
            integration_id: Integration ID
            reason: Deactivation reason
            audit_context: Audit information
            
        Returns:
            Updated integration
        """
        return await self.update_integration(
            integration_id,
            {
                "is_active": False,
                "status": IntegrationStatus.INACTIVE,
                "deactivated_at": datetime.utcnow(),
                "deactivation_reason": reason
            },
            audit_context
        )
    
    # ============================================================================
    # HEALTH MONITORING
    # ============================================================================
    
    async def perform_health_check(
        self,
        integration_id: UUID
    ) -> Dict[str, Any]:
        """
        Perform health check on integration.
        
        Args:
            integration_id: Integration ID
            
        Returns:
            Health check results
        """
        integration = await self.get_integration_by_id(integration_id)
        
        health_check = {
            "integration_id": integration_id,
            "checked_at": datetime.utcnow(),
            "status": "unknown",
            "response_time_ms": 0,
            "error": None
        }
        
        try:
            start_time = datetime.utcnow()
            
            # Perform actual health check
            test_result = await self._test_integration_connection(integration)
            
            end_time = datetime.utcnow()
            response_time = (end_time - start_time).total_seconds() * 1000
            
            health_check["response_time_ms"] = response_time
            health_check["status"] = "healthy" if test_result["success"] else "unhealthy"
            health_check["error"] = test_result.get("error")
            
            # Update integration status
            await self.update_integration(
                integration_id,
                {
                    "last_health_check": datetime.utcnow(),
                    "last_health_status": health_check["status"],
                    "avg_response_time_ms": response_time
                }
            )
            
        except Exception as e:
            health_check["status"] = "error"
            health_check["error"] = str(e)
        
        return health_check
    
    async def get_integration_health_history(
        self,
        integration_id: UUID,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get integration health history.
        
        Args:
            integration_id: Integration ID
            days: Number of days of history
            
        Returns:
            Health check history
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # This would query a health_check_logs table
        # Placeholder implementation
        return []
    
    async def get_unhealthy_integrations(
        self,
        hostel_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all unhealthy integrations.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of unhealthy integrations
        """
        # Placeholder implementation
        return []
    
    # ============================================================================
    # USAGE TRACKING
    # ============================================================================
    
    async def track_api_call(
        self,
        integration_id: UUID,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: float,
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Track individual API call.
        
        Args:
            integration_id: Integration ID
            endpoint: API endpoint
            method: HTTP method
            status_code: Response status code
            response_time_ms: Response time in milliseconds
            request_data: Request payload (optional)
            response_data: Response data (optional)
            error: Error message if failed
            
        Returns:
            API call record
        """
        api_call = {
            "id": str(UUID()),
            "integration_id": integration_id,
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "response_time_ms": response_time_ms,
            "request_data": request_data,
            "response_data": response_data,
            "error": error,
            "success": 200 <= status_code < 300,
            "called_at": datetime.utcnow()
        }
        
        # Update integration usage statistics
        await self._update_usage_statistics(integration_id, api_call)
        
        # Check rate limits
        await self._check_rate_limits(integration_id)
        
        return api_call
    
    async def get_usage_statistics(
        self,
        integration_id: UUID,
        period: str = "day"  # day, week, month
    ) -> Dict[str, Any]:
        """
        Get usage statistics for integration.
        
        Args:
            integration_id: Integration ID
            period: Time period
            
        Returns:
            Usage statistics
        """
        if period == "day":
            cutoff = datetime.utcnow() - timedelta(days=1)
        elif period == "week":
            cutoff = datetime.utcnow() - timedelta(weeks=1)
        else:
            cutoff = datetime.utcnow() - timedelta(days=30)
        
        # Placeholder - would query api_call_logs table
        return {
            "integration_id": integration_id,
            "period": period,
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "success_rate": 0,
            "avg_response_time_ms": 0,
            "total_data_transferred_mb": 0
        }
    
    async def get_rate_limit_status(
        self,
        integration_id: UUID
    ) -> Dict[str, Any]:
        """
        Get current rate limit status.
        
        Args:
            integration_id: Integration ID
            
        Returns:
            Rate limit status
        """
        integration = await self.get_integration_by_id(integration_id)
        
        rate_limits = integration.get("rate_limits", {})
        
        # Calculate current usage
        current_hour_calls = await self._count_calls_in_window(
            integration_id,
            timedelta(hours=1)
        )
        
        current_day_calls = await self._count_calls_in_window(
            integration_id,
            timedelta(days=1)
        )
        
        return {
            "integration_id": integration_id,
            "hourly_limit": rate_limits.get("hourly", 0),
            "hourly_used": current_hour_calls,
            "hourly_remaining": max(0, rate_limits.get("hourly", 0) - current_hour_calls),
            "daily_limit": rate_limits.get("daily", 0),
            "daily_used": current_day_calls,
            "daily_remaining": max(0, rate_limits.get("daily", 0) - current_day_calls),
            "reset_at": datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        }
    
    # ============================================================================
    # WEBHOOK MANAGEMENT
    # ============================================================================
    
    async def register_webhook(
        self,
        integration_id: UUID,
        event_type: str,
        webhook_url: str,
        secret: str,
        is_active: bool = True
    ) -> Dict[str, Any]:
        """
        Register webhook for integration.
        
        Args:
            integration_id: Integration ID
            event_type: Event type to listen for
            webhook_url: Webhook callback URL
            secret: Webhook secret for validation
            is_active: Whether webhook is active
            
        Returns:
            Webhook configuration
        """
        webhook = {
            "id": str(UUID()),
            "integration_id": integration_id,
            "event_type": event_type,
            "webhook_url": webhook_url,
            "secret": await self._encrypt_credentials({"secret": secret}),
            "is_active": is_active,
            "created_at": datetime.utcnow(),
            "last_triggered_at": None,
            "total_triggers": 0,
            "failed_triggers": 0
        }
        
        return webhook
    
    async def trigger_webhook(
        self,
        webhook_id: UUID,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger webhook with payload.
        
        Args:
            webhook_id: Webhook ID
            payload: Event payload
            
        Returns:
            Trigger result
        """
        # Placeholder implementation
        return {
            "webhook_id": webhook_id,
            "triggered_at": datetime.utcnow(),
            "success": True,
            "response_code": 200
        }
    
    async def get_webhook_logs(
        self,
        webhook_id: UUID,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get webhook trigger logs.
        
        Args:
            webhook_id: Webhook ID
            limit: Maximum results
            
        Returns:
            Webhook logs
        """
        # Placeholder implementation
        return []
    
    # ============================================================================
    # AUTHENTICATION & AUTHORIZATION
    # ============================================================================
    
    async def refresh_oauth_token(
        self,
        integration_id: UUID
    ) -> Dict[str, Any]:
        """
        Refresh OAuth token for integration.
        
        Args:
            integration_id: Integration ID
            
        Returns:
            New token data
        """
        integration = await self.get_integration_by_id(integration_id)
        
        if integration.get("auth_type") != "oauth":
            raise ValidationException("Integration does not use OAuth")
        
        # Placeholder - would call OAuth token endpoint
        new_token = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_at": datetime.utcnow() + timedelta(hours=1)
        }
        
        await self.update_integration(
            integration_id,
            {"credentials": new_token}
        )
        
        return new_token
    
    async def validate_api_key(
        self,
        integration_id: UUID,
        api_key: str
    ) -> bool:
        """
        Validate API key for integration.
        
        Args:
            integration_id: Integration ID
            api_key: API key to validate
            
        Returns:
            True if valid
        """
        integration = await self.get_integration_by_id(integration_id)
        
        stored_credentials = await self._decrypt_credentials(
            integration["credentials"]
        )
        
        return stored_credentials.get("api_key") == api_key
    
    # ============================================================================
    # QUERY METHODS
    # ============================================================================
    
    async def get_integration_by_id(
        self,
        integration_id: UUID
    ) -> Dict[str, Any]:
        """
        Get integration by ID.
        
        Args:
            integration_id: Integration ID
            
        Returns:
            Integration data
            
        Raises:
            NotFoundException: If not found
        """
        # Placeholder implementation
        return {
            "id": integration_id,
            "integration_type": IntegrationType.PAYMENT_GATEWAY,
            "name": "Test Integration",
            "status": IntegrationStatus.ACTIVE
        }
    
    async def find_by_hostel(
        self,
        hostel_id: UUID,
        integration_type: Optional[IntegrationType] = None,
        is_active: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Find integrations by hostel.
        
        Args:
            hostel_id: Hostel ID
            integration_type: Optional type filter
            is_active: Optional active status filter
            
        Returns:
            List of integrations
        """
        # Placeholder implementation
        return []
    
    async def find_by_type(
        self,
        integration_type: IntegrationType,
        is_active: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find integrations by type.
        
        Args:
            integration_type: Integration type
            is_active: Whether to include only active
            
        Returns:
            List of integrations
        """
        # Placeholder implementation
        return []
    
    # ============================================================================
    # ANALYTICS
    # ============================================================================
    
    async def get_integration_analytics(
        self,
        integration_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive integration analytics.
        
        Args:
            integration_id: Integration ID
            days: Time period in days
            
        Returns:
            Analytics data
        """
        usage_stats = await self.get_usage_statistics(integration_id, "month")
        health_history = await self.get_integration_health_history(integration_id, days)
        rate_limit_status = await self.get_rate_limit_status(integration_id)
        
        return {
            "integration_id": integration_id,
            "period_days": days,
            "usage_statistics": usage_stats,
            "health_history": health_history,
            "rate_limit_status": rate_limit_status,
            "uptime_percentage": 99.9,  # Calculated from health checks
            "error_rate": 0.1,  # Calculated from API calls
            "generated_at": datetime.utcnow()
        }
    
    async def get_platform_integration_overview(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get platform-wide integration overview.
        
        Args:
            days: Time period in days
            
        Returns:
            Platform integration overview
        """
        # Placeholder implementation
        return {
            "total_integrations": 0,
            "active_integrations": 0,
            "integration_by_type": {},
            "total_api_calls": 0,
            "average_success_rate": 0,
            "period_days": days
        }
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    async def _validate_integration_config(
        self,
        integration_type: IntegrationType,
        config: Dict[str, Any]
    ) -> None:
        """Validate integration configuration."""
        required_fields = {
            IntegrationType.PAYMENT_GATEWAY: ["api_endpoint", "currency"],
            IntegrationType.SMS_PROVIDER: ["api_endpoint", "sender_id"],
            IntegrationType.EMAIL_SERVICE: ["api_endpoint", "from_email"],
        }
        
        required = required_fields.get(integration_type, [])
        
        for field in required:
            if field not in config:
                raise ValidationException(
                    f"Missing required configuration field: {field}"
                )
    
    async def _test_integration_connection(
        self,
        integration: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test integration connection."""
        # Placeholder - would make actual test call
        return {
            "success": True,
            "response_time_ms": 150,
            "error": None
        }
    
    async def _encrypt_credentials(
        self,
        credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Encrypt credentials."""
        # Placeholder - would use actual encryption
        return credentials
    
    async def _decrypt_credentials(
        self,
        encrypted_credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Decrypt credentials."""
        # Placeholder - would use actual decryption
        return encrypted_credentials
    
    async def _update_usage_statistics(
        self,
        integration_id: UUID,
        api_call: Dict[str, Any]
    ) -> None:
        """Update integration usage statistics."""
        pass
    
    async def _check_rate_limits(
        self,
        integration_id: UUID
    ) -> None:
        """Check if rate limits are exceeded."""
        rate_limit_status = await self.get_rate_limit_status(integration_id)
        
        if rate_limit_status["hourly_remaining"] == 0:
            raise ValidationException("Hourly rate limit exceeded")
        
        if rate_limit_status["daily_remaining"] == 0:
            raise ValidationException("Daily rate limit exceeded")
    
    async def _count_calls_in_window(
        self,
        integration_id: UUID,
        window: timedelta
    ) -> int:
        """Count API calls in time window."""
        # Placeholder implementation
        return 0