"""
Payment services package.

Exports all payment-related services for dependency injection and usage.
"""

from app.services.payment.payment_fraud_service import PaymentFraudService
from app.services.payment.payment_gateway_service import PaymentGatewayService
from app.services.payment.payment_ledger_service import PaymentLedgerService
from app.services.payment.payment_reconciliation_service import (
    PaymentReconciliationService,
)
from app.services.payment.payment_refund_service import PaymentRefundService
from app.services.payment.payment_reminder_service import PaymentReminderService
from app.services.payment.payment_reporting_service import PaymentReportingService
from app.services.payment.payment_schedule_service import PaymentScheduleService
from app.services.payment.payment_service import PaymentService

__all__ = [
    "PaymentService",
    "PaymentGatewayService",
    "PaymentFraudService",
    "PaymentLedgerService",
    "PaymentReconciliationService",
    "PaymentRefundService",
    "PaymentReminderService",
    "PaymentReportingService",
    "PaymentScheduleService",
]


# ==================== Service Factory ====================

class PaymentServiceFactory:
    """
    Factory for creating payment services with proper dependencies.
    
    This handles dependency injection in a clean way.
    """
    
    @staticmethod
    def create_payment_service(session) -> PaymentService:
        """Create payment service with all dependencies."""
        from app.repositories.payment.payment_repository import PaymentRepository
        from app.repositories.payment.payment_ledger_repository import PaymentLedgerRepository
        from app.repositories.payment.payment_schedule_repository import PaymentScheduleRepository
        from app.repositories.payment.payment_reminder_repository import PaymentReminderRepository
        
        # Create repositories
        payment_repo = PaymentRepository(session)
        ledger_repo = PaymentLedgerRepository(session)
        schedule_repo = PaymentScheduleRepository(session)
        reminder_repo = PaymentReminderRepository(session)
        
        # Create services
        gateway_service = PaymentServiceFactory.create_gateway_service(session)
        fraud_service = PaymentServiceFactory.create_fraud_service(session)
        ledger_service = PaymentServiceFactory.create_ledger_service(session)
        reminder_service = PaymentServiceFactory.create_reminder_service(session)
        
        # Create payment service
        return PaymentService(
            session=session,
            payment_repo=payment_repo,
            ledger_repo=ledger_repo,
            schedule_repo=schedule_repo,
            reminder_repo=reminder_repo,
            gateway_service=gateway_service,
            fraud_service=fraud_service,
            ledger_service=ledger_service,
            reminder_service=reminder_service,
        )
    
    @staticmethod
    def create_gateway_service(session) -> PaymentGatewayService:
        """Create gateway service."""
        from app.repositories.payment.gateway_transaction_repository import GatewayTransactionRepository
        from app.repositories.payment.payment_repository import PaymentRepository
        
        gateway_repo = GatewayTransactionRepository(session)
        payment_repo = PaymentRepository(session)
        
        return PaymentGatewayService(
            session=session,
            gateway_repo=gateway_repo,
            payment_repo=payment_repo,
        )
    
    @staticmethod
    def create_fraud_service(session) -> PaymentFraudService:
        """Create fraud detection service."""
        from app.repositories.payment.payment_repository import PaymentRepository
        
        payment_repo = PaymentRepository(session)
        
        return PaymentFraudService(
            session=session,
            payment_repo=payment_repo,
        )
    
    @staticmethod
    def create_ledger_service(session) -> PaymentLedgerService:
        """Create ledger service."""
        from app.repositories.payment.payment_ledger_repository import PaymentLedgerRepository
        
        ledger_repo = PaymentLedgerRepository(session)
        
        return PaymentLedgerService(
            session=session,
            ledger_repo=ledger_repo,
        )
    
    @staticmethod
    def create_reminder_service(session) -> PaymentReminderService:
        """Create reminder service."""
        from app.repositories.payment.payment_reminder_repository import PaymentReminderRepository
        from app.repositories.payment.payment_repository import PaymentRepository
        
        reminder_repo = PaymentReminderRepository(session)
        payment_repo = PaymentRepository(session)
        
        return PaymentReminderService(
            session=session,
            reminder_repo=reminder_repo,
            payment_repo=payment_repo,
        )
    
    @staticmethod
    def create_refund_service(session) -> PaymentRefundService:
        """Create refund service."""
        from app.repositories.payment.payment_refund_repository import PaymentRefundRepository
        from app.repositories.payment.payment_repository import PaymentRepository
        
        refund_repo = PaymentRefundRepository(session)
        payment_repo = PaymentRepository(session)
        gateway_service = PaymentServiceFactory.create_gateway_service(session)
        ledger_service = PaymentServiceFactory.create_ledger_service(session)
        
        return PaymentRefundService(
            session=session,
            refund_repo=refund_repo,
            payment_repo=payment_repo,
            gateway_service=gateway_service,
            ledger_service=ledger_service,
        )
    
    @staticmethod
    def create_schedule_service(session) -> PaymentScheduleService:
        """Create schedule service."""
        from app.repositories.payment.payment_schedule_repository import PaymentScheduleRepository
        
        schedule_repo = PaymentScheduleRepository(session)
        payment_service = PaymentServiceFactory.create_payment_service(session)
        
        return PaymentScheduleService(
            session=session,
            schedule_repo=schedule_repo,
            payment_service=payment_service,
        )
    
    @staticmethod
    def create_reconciliation_service(session) -> PaymentReconciliationService:
        """Create reconciliation service."""
        from app.repositories.payment.payment_repository import PaymentRepository
        from app.repositories.payment.gateway_transaction_repository import GatewayTransactionRepository
        from app.repositories.payment.payment_ledger_repository import PaymentLedgerRepository
        
        payment_repo = PaymentRepository(session)
        gateway_repo = GatewayTransactionRepository(session)
        ledger_repo = PaymentLedgerRepository(session)
        
        return PaymentReconciliationService(
            session=session,
            payment_repo=payment_repo,
            gateway_repo=gateway_repo,
            ledger_repo=ledger_repo,
        )
    
    @staticmethod
    def create_reporting_service(session) -> PaymentReportingService:
        """Create reporting service."""
        from app.repositories.payment.payment_repository import PaymentRepository
        from app.repositories.payment.payment_ledger_repository import PaymentLedgerRepository
        from app.repositories.payment.gateway_transaction_repository import GatewayTransactionRepository
        from app.repositories.payment.payment_aggregate_repository import PaymentAggregateRepository
        
        payment_repo = PaymentRepository(session)
        ledger_repo = PaymentLedgerRepository(session)
        gateway_repo = GatewayTransactionRepository(session)
        aggregate_repo = PaymentAggregateRepository(session)
        
        return PaymentReportingService(
            session=session,
            payment_repo=payment_repo,
            ledger_repo=ledger_repo,
            gateway_repo=gateway_repo,
            aggregate_repo=aggregate_repo,
        )