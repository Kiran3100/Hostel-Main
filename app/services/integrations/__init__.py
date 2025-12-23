"""
Integrations service layer.

Provides comprehensive business logic for all integration operations:
- API integrations (providers, credentials, health, requests)
- Third-party sync jobs (pull/push/reconcile)
- Email/SMS/Push provider configuration and health
- Payment gateway initiation/verification/refunds
- Calendar synchronization
- Webhooks (inbound/outbound) orchestration

All services implement:
- Comprehensive validation
- Error handling with detailed context
- Logging and monitoring hooks
- Transaction management
- Caching where appropriate
- Rate limiting and circuit breakers
- Retry logic for external calls
- Idempotency support
"""

from app.services.integrations.integration_service import IntegrationService
from app.services.integrations.api_integration_service import APIIntegrationService
from app.services.integrations.third_party_sync_service import (
    ThirdPartySyncService,
    SyncDirection,
    ConflictResolution,
)
from app.services.integrations.calendar_sync_service import CalendarSyncService
from app.services.integrations.webhook_service import WebhookService
from app.services.integrations.email_provider_service import EmailProviderService
from app.services.integrations.sms_provider_service import SMSProviderService
from app.services.integrations.push_provider_service import PushProviderService
from app.services.integrations.payment_gateway_integration import (
    PaymentGatewayIntegrationService
)

__all__ = [
    # Main orchestrator
    "IntegrationService", 
    
    # Core integration services
    "APIIntegrationService",
    "ThirdPartySyncService",
    
    # Communication providers
    "EmailProviderService",
    "SMSProviderService",
    "PushProviderService",
    
    # Specialized integrations
    "CalendarSyncService",
    "PaymentGatewayIntegrationService",
    "WebhookService",
    
    # Enumerations
    "SyncDirection",
    "ConflictResolution",
]

__version__ = "2.0.0"
__author__ = "Hostel Management System Team"
__description__ = "Enhanced integration services with comprehensive error handling and monitoring"