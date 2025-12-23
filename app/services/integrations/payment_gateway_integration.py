"""
Payment gateway integration service (initiate/verify/refund).

Handles all payment gateway operations with support for multiple providers
(Razorpay, Stripe, PayPal, etc.) including webhooks, verification, and refunds.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from decimal import Decimal
import logging
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService, ServiceResult, ServiceError, 
    ErrorCode, ErrorSeverity
)
from app.repositories.payment.gateway_transaction_repository import (
    GatewayTransactionRepository
)
from app.models.payment.gateway_transaction import GatewayTransaction
from app.schemas.payment.payment_gateway import (
    GatewayRequest,
    GatewayResponse,
    GatewayWebhook,
    GatewayCallback,
    GatewayRefundRequest,
    GatewayRefundResponse,
    GatewayVerification,
)

logger = logging.getLogger(__name__)


class PaymentGatewayIntegrationService(
    BaseService[GatewayTransaction, GatewayTransactionRepository]
):
    """
    Gateway operations against providers: initiate, callbacks, verify, refund.
    
    Supported gateways:
    - Razorpay
    - Stripe
    - PayPal
    - Square
    - Braintree
    """

    # Supported payment gateways
    SUPPORTED_GATEWAYS = {
        "razorpay", "stripe", "paypal", "square", "braintree"
    }
    
    # Transaction states
    PENDING_STATES = {"created", "pending", "processing"}
    SUCCESS_STATES = {"success", "completed", "captured"}
    FAILURE_STATES = {"failed", "cancelled", "expired"}

    def __init__(
        self, 
        repository: GatewayTransactionRepository, 
        db_session: Session,
        webhook_verify_enabled: bool = True,
        auto_capture: bool = False,
    ):
        """
        Initialize payment gateway integration service.
        
        Args:
            repository: Gateway transaction repository
            db_session: SQLAlchemy database session
            webhook_verify_enabled: Verify webhook signatures
            auto_capture: Auto-capture authorized payments
        """
        super().__init__(repository, db_session)
        self._webhook_verify_enabled = webhook_verify_enabled
        self._auto_capture = auto_capture
        self._idempotency_cache: Dict[str, Any] = {}
        
        logger.info("PaymentGatewayIntegrationService initialized")

    def _validate_gateway_request(
        self, 
        request: GatewayRequest
    ) -> ServiceResult[bool]:
        """
        Validate gateway payment request.
        
        Args:
            request: Gateway request object
            
        Returns:
            ServiceResult indicating validation success
        """
        # Validate provider
        if not request.provider or request.provider.lower() not in self.SUPPORTED_GATEWAYS:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Unsupported gateway: {request.provider}",
                    severity=ErrorSeverity.HIGH,
                    context={
                        "provider": request.provider,
                        "supported": list(self.SUPPORTED_GATEWAYS)
                    }
                )
            )
        
        # Validate amount
        if not request.amount or request.amount <= 0:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Amount must be greater than 0",
                    severity=ErrorSeverity.HIGH,
                    context={"amount": request.amount}
                )
            )
        
        # Validate currency
        if not request.currency or len(request.currency) != 3:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Currency must be a 3-letter ISO code",
                    severity=ErrorSeverity.MEDIUM,
                    context={"currency": request.currency}
                )
            )
        
        # Validate internal payment ID
        if not request.internal_payment_id:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Internal payment ID is required",
                    severity=ErrorSeverity.HIGH
                )
            )
        
        return ServiceResult.success(True)

    def _check_idempotency(
        self, 
        idempotency_key: str
    ) -> Optional[GatewayResponse]:
        """
        Check if request was already processed (idempotency).
        
        Args:
            idempotency_key: Unique request identifier
            
        Returns:
            Previous response if found, None otherwise
        """
        if idempotency_key in self._idempotency_cache:
            logger.info(
                f"Idempotent request detected: {idempotency_key}",
                extra={"idempotency_key": idempotency_key}
            )
            return self._idempotency_cache[idempotency_key]
        
        # Check database for previous transaction
        existing = self.repository.get_by_idempotency_key(idempotency_key)
        if existing:
            response = GatewayResponse(
                success=existing.status in self.SUCCESS_STATES,
                gateway_order_id=existing.gateway_order_id,
                gateway_payment_id=existing.gateway_payment_id,
                status=existing.status,
                message="Idempotent request - returning cached response",
                metadata=existing.metadata or {}
            )
            self._idempotency_cache[idempotency_key] = response
            return response
        
        return None

    def initiate(
        self,
        request: GatewayRequest,
        idempotency_key: Optional[str] = None,
        user_id: Optional[UUID] = None,
    ) -> ServiceResult[GatewayResponse]:
        """
        Initiate payment with gateway provider.
        
        Creates a payment order/session with the gateway and returns
        necessary information for client-side completion.
        
        Args:
            request: Gateway payment request
            idempotency_key: Optional key for idempotent requests
            user_id: User initiating the payment
            
        Returns:
            ServiceResult containing gateway response
        """
        logger.info(
            f"Initiating payment via {request.provider}",
            extra={
                "provider": request.provider,
                "amount": float(request.amount),
                "currency": request.currency,
                "internal_payment_id": str(request.internal_payment_id)
            }
        )
        
        # Validate request
        validation = self._validate_gateway_request(request)
        if not validation.success:
            return validation
        
        # Check idempotency
        if idempotency_key:
            cached_response = self._check_idempotency(idempotency_key)
            if cached_response:
                return ServiceResult.success(
                    cached_response,
                    message="Idempotent request - cached response returned",
                    metadata={"idempotent": True}
                )

        try:
            # Enhance request with metadata
            enhanced_request = GatewayRequest(
                **request.dict(),
                metadata={
                    **(request.metadata or {}),
                    "initiated_at": datetime.utcnow().isoformat(),
                    "initiated_by": str(user_id) if user_id else None,
                    "idempotency_key": idempotency_key
                }
            )
            
            # Initiate payment with gateway
            response = self.repository.initiate(enhanced_request)
            
            # Cache response for idempotency
            if idempotency_key:
                self._idempotency_cache[idempotency_key] = response
            
            # Commit transaction
            self.db.commit()
            
            logger.info(
                f"Payment initiated successfully via {request.provider}",
                extra={
                    "provider": request.provider,
                    "gateway_order_id": response.gateway_order_id,
                    "status": response.status
                }
            )
            
            return ServiceResult.success(
                response,
                message=f"Payment initiated via {request.provider}",
                metadata={
                    "provider": request.provider,
                    "gateway_order_id": response.gateway_order_id,
                    "amount": float(request.amount),
                    "currency": request.currency
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error initiating payment via {request.provider}: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Failed to initiate payment via {request.provider}",
                    severity=ErrorSeverity.CRITICAL,
                    context={
                        "provider": request.provider,
                        "error": str(e),
                        "internal_payment_id": str(request.internal_payment_id)
                    }
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error initiating payment via {request.provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(
                e, 
                "initiate payment gateway", 
                request.internal_payment_id
            )

    def handle_webhook(
        self,
        provider: str,
        request: GatewayWebhook,
        verify_signature: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Handle incoming webhook from payment gateway.
        
        Processes webhook notifications for payment status updates,
        with signature verification for security.
        
        Args:
            provider: Gateway provider identifier
            request: Webhook request data
            verify_signature: Verify webhook signature
            
        Returns:
            ServiceResult containing webhook processing status
        """
        logger.info(
            f"Processing webhook from {provider}",
            extra={
                "provider": provider,
                "event_type": request.event_type
            }
        )
        
        # Validate provider
        if provider.lower() not in self.SUPPORTED_GATEWAYS:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Unsupported gateway: {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={"provider": provider}
                )
            )

        try:
            # Verify signature if enabled
            if verify_signature and self._webhook_verify_enabled:
                signature_valid = self.repository.verify_webhook_signature(
                    provider, 
                    request
                )
                
                if not signature_valid:
                    logger.warning(
                        f"Invalid webhook signature from {provider}",
                        extra={"provider": provider}
                    )
                    return ServiceResult.failure(
                        error=ServiceError(
                            code=ErrorCode.AUTHENTICATION_ERROR,
                            message=f"Invalid webhook signature from {provider}",
                            severity=ErrorSeverity.CRITICAL,
                            context={
                                "provider": provider,
                                "event_type": request.event_type
                            }
                        )
                    )
            
            # Process webhook
            result = self.repository.handle_webhook(provider, request)
            
            # Commit transaction
            self.db.commit()
            
            logger.info(
                f"Webhook processed successfully from {provider}",
                extra={
                    "provider": provider,
                    "event_type": request.event_type,
                    "processed": result.get("processed", False)
                }
            )
            
            return ServiceResult.success(
                result or {},
                message=f"Webhook processed from {provider}",
                metadata={
                    "provider": provider,
                    "event_type": request.event_type
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
            return self._handle_exception(e, "handle gateway webhook", provider)

    def handle_callback(
        self,
        request: GatewayCallback,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Handle return callback from payment gateway.
        
        Processes user return after completing payment flow,
        typically used for redirect-based payment methods.
        
        Args:
            request: Callback request data
            
        Returns:
            ServiceResult containing callback processing status
        """
        logger.info(
            f"Processing callback for order: {request.gateway_order_id}",
            extra={
                "gateway_order_id": request.gateway_order_id,
                "status": request.status
            }
        )

        try:
            # Process callback
            result = self.repository.handle_callback(request)
            
            # Commit transaction
            self.db.commit()
            
            success = result.get("success", False)
            
            logger.info(
                f"Callback processed: {request.gateway_order_id} - "
                f"{'success' if success else 'failure'}",
                extra={
                    "gateway_order_id": request.gateway_order_id,
                    "success": success
                }
            )
            
            return ServiceResult.success(
                result or {},
                message="Callback processed",
                metadata={
                    "gateway_order_id": request.gateway_order_id,
                    "success": success
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error processing callback: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message="Failed to process gateway callback",
                    severity=ErrorSeverity.HIGH,
                    context={
                        "gateway_order_id": request.gateway_order_id,
                        "error": str(e)
                    }
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error processing callback: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "handle gateway callback")

    def verify(
        self,
        provider: str,
        order_id: str,
        payment_id: Optional[str] = None,
        signature: Optional[str] = None,
    ) -> ServiceResult[GatewayVerification]:
        """
        Verify payment status with gateway.
        
        Confirms payment completion by querying the gateway directly,
        useful for additional verification beyond webhooks.
        
        Args:
            provider: Gateway provider identifier
            order_id: Gateway order/transaction ID
            payment_id: Gateway payment ID (if available)
            signature: Payment signature for verification
            
        Returns:
            ServiceResult containing verification results
        """
        logger.info(
            f"Verifying payment with {provider}",
            extra={
                "provider": provider,
                "order_id": order_id,
                "payment_id": payment_id
            }
        )
        
        # Validate provider
        if provider.lower() not in self.SUPPORTED_GATEWAYS:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Unsupported gateway: {provider}",
                    severity=ErrorSeverity.HIGH,
                    context={"provider": provider}
                )
            )

        try:
            # Verify payment
            verification = self.repository.verify(
                provider=provider,
                order_id=order_id,
                payment_id=payment_id,
                signature=signature
            )
            
            verified = verification.verified
            status = verification.status
            
            logger.info(
                f"Payment verification completed for {provider}: "
                f"{'verified' if verified else 'not verified'}",
                extra={
                    "provider": provider,
                    "order_id": order_id,
                    "verified": verified,
                    "status": status
                }
            )
            
            return ServiceResult.success(
                verification,
                message=f"Payment {'verified' if verified else 'not verified'}",
                metadata={
                    "provider": provider,
                    "order_id": order_id,
                    "verified": verified,
                    "status": status
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error verifying payment with {provider}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "verify gateway payment", order_id)

    def refund(
        self,
        request: GatewayRefundRequest,
        initiated_by: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> ServiceResult[GatewayRefundResponse]:
        """
        Initiate refund with payment gateway.
        
        Processes full or partial refunds through the gateway,
        with proper authorization and audit trail.
        
        Args:
            request: Refund request data
            initiated_by: User initiating the refund
            reason: Reason for refund
            
        Returns:
            ServiceResult containing refund response
        """
        logger.info(
            f"Initiating refund for payment: {request.gateway_payment_id}",
            extra={
                "gateway_payment_id": request.gateway_payment_id,
                "amount": float(request.amount) if request.amount else None,
                "reason": reason
            }
        )
        
        # Validate refund amount
        if request.amount and request.amount <= 0:
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Refund amount must be greater than 0",
                    severity=ErrorSeverity.MEDIUM,
                    context={"amount": float(request.amount)}
                )
            )

        try:
            # Enhance request with metadata
            enhanced_request = GatewayRefundRequest(
                **request.dict(),
                metadata={
                    **(request.metadata or {}),
                    "initiated_at": datetime.utcnow().isoformat(),
                    "initiated_by": str(initiated_by) if initiated_by else None,
                    "reason": reason
                }
            )
            
            # Check if payment is refundable
            payment_status = self.repository.get_payment_status(
                request.gateway_payment_id
            )
            
            if payment_status not in self.SUCCESS_STATES:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.BUSINESS_RULE_VIOLATION,
                        message="Payment is not in a refundable state",
                        severity=ErrorSeverity.MEDIUM,
                        context={
                            "gateway_payment_id": request.gateway_payment_id,
                            "current_status": payment_status
                        }
                    )
                )
            
            # Process refund
            response = self.repository.refund(enhanced_request)
            
            # Commit transaction
            self.db.commit()
            
            success = response.success
            
            logger.info(
                f"Refund {'initiated successfully' if success else 'failed'} "
                f"for payment: {request.gateway_payment_id}",
                extra={
                    "gateway_payment_id": request.gateway_payment_id,
                    "refund_id": response.refund_id,
                    "success": success
                }
            )
            
            return ServiceResult.success(
                response,
                message=f"Refund {'initiated' if success else 'failed'}",
                metadata={
                    "gateway_payment_id": request.gateway_payment_id,
                    "refund_id": response.refund_id,
                    "amount": float(request.amount) if request.amount else None
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error processing refund: {str(e)}",
                exc_info=True
            )
            return ServiceResult.failure(
                error=ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message="Failed to process gateway refund",
                    severity=ErrorSeverity.HIGH,
                    context={
                        "gateway_payment_id": request.gateway_payment_id,
                        "error": str(e)
                    }
                )
            )
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Error processing refund: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(
                e, 
                "gateway refund", 
                request.gateway_payment_id
            )

    def get_transaction_status(
        self,
        transaction_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get current status of a gateway transaction.
        
        Args:
            transaction_id: Internal transaction ID
            
        Returns:
            ServiceResult containing transaction status
        """
        logger.debug(f"Retrieving transaction status: {transaction_id}")
        
        try:
            status = self.repository.get_transaction_by_id(transaction_id)
            
            if not status:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Transaction not found: {transaction_id}",
                        severity=ErrorSeverity.MEDIUM,
                        context={"transaction_id": str(transaction_id)}
                    )
                )
            
            return ServiceResult.success(
                status,
                message="Transaction status retrieved",
                metadata={"transaction_id": str(transaction_id)}
            )
            
        except Exception as e:
            logger.error(
                f"Error retrieving transaction status: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(
                e, 
                "get transaction status", 
                transaction_id
            )

    def list_transactions(
        self,
        provider: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        List gateway transactions with filters.
        
        Args:
            provider: Filter by provider
            status: Filter by status
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            ServiceResult containing list of transactions
        """
        logger.info(
            f"Listing transactions (provider={provider}, status={status})"
        )
        
        try:
            transactions = self.repository.list_transactions(
                provider=provider,
                status=status,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset
            )
            
            return ServiceResult.success(
                transactions or [],
                message=f"Retrieved {len(transactions or [])} transactions",
                metadata={
                    "count": len(transactions or []),
                    "provider": provider,
                    "status": status,
                    "limit": limit,
                    "offset": offset
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error listing transactions: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list transactions")