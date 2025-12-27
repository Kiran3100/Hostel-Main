"""
Payment Webhook Handler

Handles incoming webhooks from various payment gateway providers including:
- Razorpay
- Stripe
- PayTM
- PhonePe
- And other configured providers

All webhooks are verified for authenticity and processed asynchronously.
"""

from typing import Dict, Any, Optional
import logging
from datetime import datetime

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Request,
    Response,
    status,
    HTTPException,
)
from fastapi.responses import JSONResponse, PlainTextResponse

from app.services.payment.payment_gateway_service import PaymentGatewayService
from app.core.config import get_settings
from app.core.exceptions import WebhookVerificationError, ProviderNotSupportedError

# Configure logger
logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(
    prefix="/payment",
    tags=["Webhooks - Payment"],
)

# Settings
settings = get_settings()


# ============================================================================
# Dependency Injection
# ============================================================================


def get_payment_gateway_service() -> PaymentGatewayService:
    """
    Dependency provider for PaymentGatewayService.

    Returns:
        PaymentGatewayService: Configured payment gateway service instance

    Note:
        Replace this implementation with your actual DI container wiring.
        Example implementations:
        
        Option 1 - Service Factory Pattern:
            from app.services.base.service_factory import ServiceFactory
            return ServiceFactory().create(PaymentGatewayService)
        
        Option 2 - Direct Instantiation with Dependencies:
            from app.db.session import get_db
            from app.repositories.payment_repository import PaymentRepository
            db = next(get_db())
            repo = PaymentRepository(db)
            return PaymentGatewayService(repository=repo)
        
        Option 3 - Dependency Injector:
            from dependency_injector.wiring import inject, Provide
            from app.core.container import Container
            return Provide[Container.payment_gateway_service]()
    """
    raise NotImplementedError(
        "PaymentGatewayService dependency injection not configured. "
        "Please wire this dependency through your DI container."
    )


# ============================================================================
# Webhook Endpoints
# ============================================================================


@router.post(
    "/{provider}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Payment Gateway Webhook Handler",
    description="""
    Generic webhook endpoint for payment gateway notifications.
    
    This endpoint handles webhooks from various payment providers and processes
    them asynchronously to ensure quick response times.
    
    **Supported Providers:**
    - razorpay
    - stripe
    - paytm
    - phonepe
    - cashfree
    - instamojo
    
    **Process Flow:**
    1. Receive webhook payload
    2. Extract raw body and headers for signature verification
    3. Queue for background processing
    4. Return 202 Accepted immediately
    5. Service verifies signature and processes event
    
    **Security:**
    - Webhook signatures are verified before processing
    - Invalid signatures are rejected and logged
    - Rate limiting may apply based on configuration
    
    **Idempotency:**
    Webhooks are designed to be idempotent. Duplicate webhook deliveries
    will be detected and handled appropriately.
    """,
    responses={
        202: {
            "description": "Webhook accepted for processing",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Webhook accepted",
                        "provider": "razorpay",
                        "received_at": "2024-01-15T10:30:00Z",
                        "webhook_id": "whook_abc123"
                    }
                }
            }
        },
        400: {
            "description": "Invalid webhook payload or provider",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid webhook payload",
                        "error": "Missing required fields"
                    }
                }
            }
        },
        401: {
            "description": "Webhook signature verification failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Signature verification failed"
                    }
                }
            }
        },
        503: {
            "description": "Service temporarily unavailable",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Service temporarily unavailable, please retry"
                    }
                }
            }
        }
    },
    response_model=Dict[str, Any],
)
async def handle_payment_webhook(
    provider: str,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payment_gateway_service: PaymentGatewayService = Depends(get_payment_gateway_service),
) -> Dict[str, Any]:
    """
    Process incoming payment gateway webhooks.

    Args:
        provider: Payment gateway provider identifier (e.g., 'razorpay', 'stripe')
        request: FastAPI request object containing headers and body
        response: FastAPI response object for setting custom headers
        background_tasks: FastAPI background tasks manager
        payment_gateway_service: Injected payment gateway service

    Returns:
        Dict containing acknowledgment of webhook receipt

    Raises:
        HTTPException: For invalid providers or malformed requests
    """
    
    # Normalize provider name
    provider = provider.lower().strip()
    
    # Log incoming webhook
    logger.info(
        f"Payment webhook received",
        extra={
            "provider": provider,
            "path": str(request.url.path),
            "method": request.method,
            "client_host": request.client.host if request.client else "unknown",
        }
    )

    try:
        # Extract request data
        raw_body: bytes = await request.body()
        headers: Dict[str, str] = dict(request.headers)
        query_params: Dict[str, str] = dict(request.query_params)
        
        # Validate that we have a body
        if not raw_body:
            logger.warning(
                f"Empty webhook body received from {provider}",
                extra={"provider": provider}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook body cannot be empty"
            )

        # Generate webhook ID for tracking
        webhook_id = f"whook_{provider}_{datetime.utcnow().timestamp()}"
        received_at = datetime.utcnow().isoformat() + "Z"

        # Add metadata for processing
        metadata = {
            "webhook_id": webhook_id,
            "received_at": received_at,
            "client_ip": request.client.host if request.client else None,
            "user_agent": headers.get("user-agent", "unknown"),
        }

        # Queue webhook for background processing
        background_tasks.add_task(
            _process_payment_webhook_task,
            payment_gateway_service=payment_gateway_service,
            provider=provider,
            raw_body=raw_body,
            headers=headers,
            query_params=query_params,
            path=str(request.url.path),
            metadata=metadata,
        )

        # Set response headers for better tracking
        response.headers["X-Webhook-ID"] = webhook_id
        response.headers["X-Webhook-Received-At"] = received_at

        # Return success response
        return {
            "detail": "Webhook accepted",
            "provider": provider,
            "received_at": received_at,
            "webhook_id": webhook_id,
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        # Log unexpected errors
        logger.error(
            f"Unexpected error processing webhook from {provider}",
            extra={
                "provider": provider,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        
        # Return 500 to trigger retry from provider
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing webhook"
        )


@router.get(
    "/{provider}/health",
    status_code=status.HTTP_200_OK,
    summary="Payment Webhook Health Check",
    description="""
    Health check endpoint for payment webhooks.
    
    Some payment providers may ping this endpoint to verify webhook availability.
    """,
    responses={
        200: {
            "description": "Webhook endpoint is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "provider": "razorpay",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def payment_webhook_health_check(provider: str) -> Dict[str, Any]:
    """
    Health check endpoint for payment webhooks.

    Args:
        provider: Payment gateway provider identifier

    Returns:
        Health status response
    """
    provider = provider.lower().strip()
    
    return {
        "status": "healthy",
        "provider": provider,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ============================================================================
# Background Task Functions
# ============================================================================


async def _process_payment_webhook_task(
    payment_gateway_service: PaymentGatewayService,
    provider: str,
    raw_body: bytes,
    headers: Dict[str, str],
    query_params: Dict[str, str],
    path: str,
    metadata: Dict[str, Any],
) -> None:
    """
    Background task to process payment webhooks.

    This function runs asynchronously after the webhook response is sent.
    It handles verification, processing, and error handling.

    Args:
        payment_gateway_service: Payment gateway service instance
        provider: Payment provider identifier
        raw_body: Raw webhook payload bytes
        headers: Request headers dictionary
        query_params: Query parameters dictionary
        path: Request path
        metadata: Additional metadata for tracking

    Returns:
        None
    """
    webhook_id = metadata.get("webhook_id", "unknown")
    
    try:
        logger.info(
            f"Processing payment webhook",
            extra={
                "webhook_id": webhook_id,
                "provider": provider,
            }
        )

        # Delegate to payment gateway service
        await payment_gateway_service.handle_webhook(
            provider=provider,
            raw_body=raw_body,
            headers=headers,
            query_params=query_params,
            path=path,
            metadata=metadata,
        )

        logger.info(
            f"Payment webhook processed successfully",
            extra={
                "webhook_id": webhook_id,
                "provider": provider,
            }
        )

    except WebhookVerificationError as e:
        # Signature verification failed
        logger.error(
            f"Webhook signature verification failed",
            extra={
                "webhook_id": webhook_id,
                "provider": provider,
                "error": str(e),
            }
        )
        # Don't retry - signature failures are permanent
        
    except ProviderNotSupportedError as e:
        # Unknown provider
        logger.error(
            f"Unsupported payment provider",
            extra={
                "webhook_id": webhook_id,
                "provider": provider,
                "error": str(e),
            }
        )
        # Don't retry - provider not supported
        
    except Exception as e:
        # Unexpected error during processing
        logger.error(
            f"Error processing payment webhook",
            extra={
                "webhook_id": webhook_id,
                "provider": provider,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        # In production, you might want to:
        # - Store failed webhooks for manual review
        # - Trigger alerts for operations team
        # - Implement retry logic with exponential backoff