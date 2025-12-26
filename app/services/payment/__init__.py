# app/services/payment/__init__.py
"""
Payment services package.

Provides comprehensive payment management services:

Core Services:
- PaymentService: Core payment operations and CRUD
- PaymentGatewayService: Gateway integration for online payments
- PaymentLedgerService: Financial ledger and account statements
- PaymentRefundService: Refund lifecycle management
- PaymentScheduleService: Recurring payment schedules
- PaymentReminderService: Payment reminder configuration and delivery

Support Services:
- PaymentReconciliationService: Payment reconciliation with gateway
- PaymentFraudService: Fraud detection and risk assessment
- PaymentReportingService: Analytics and reporting

All services follow consistent patterns:
- Dependency injection via repositories
- Comprehensive validation
- Logging and error handling
- Transaction safety
- Business rule enforcement
"""

from .payment_service import PaymentService
from .payment_gateway_service import PaymentGatewayService, GatewayClient
from .payment_ledger_service import PaymentLedgerService
from .payment_refund_service import PaymentRefundService
from .payment_reminder_service import PaymentReminderService
from .payment_schedule_service import PaymentScheduleService
from .payment_reconciliation_service import PaymentReconciliationService
from .payment_fraud_service import PaymentFraudService
from .payment_reporting_service import PaymentReportingService

__all__ = [
    # Core services
    "PaymentService",
    "PaymentGatewayService",
    "GatewayClient",
    "PaymentLedgerService",
    "PaymentRefundService",
    "PaymentScheduleService",
    "PaymentReminderService",
    # Support services
    "PaymentReconciliationService",
    "PaymentFraudService",
    "PaymentReportingService",
]

# Version
__version__ = "1.0.0"