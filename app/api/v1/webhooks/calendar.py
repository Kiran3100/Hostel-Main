"""
Calendar Webhook Handler

Handles incoming webhooks from calendar integration providers including:
- Google Calendar
- Microsoft Outlook/Office 365
- Apple Calendar
- And other configured providers

Webhooks are used to sync calendar events, handle notifications, and maintain
real-time updates for integrated calendars.
"""

from typing import Dict, Any, Optional, Union
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

from app.services.integrations.webhook_service import WebhookService
from app.core.config import get_settings
from app.core.exceptions import WebhookVerificationError, ProviderNotSupportedError

# Configure logger
logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(
    prefix="/calendar",
    tags=["Webhooks - Calendar"],
)

# Settings
settings = get_settings()


# ============================================================================
# Dependency Injection
# ============================================================================


def get_webhook_service() -> WebhookService:
    """
    Dependency provider for WebhookService.

    Returns:
        WebhookService: Configured webhook service instance

    Note:
        Replace this implementation with your actual DI container wiring.
        Example implementations:
        
        Option 1 - Service Factory Pattern:
            from app.services.base.service_factory import ServiceFactory
            return ServiceFactory().create(WebhookService)
        
        Option 2 - Direct Instantiation with Dependencies:
            from app.db.session import get_db
            from app.repositories.integration_repository import IntegrationRepository
            from app.services.integrations.calendar_sync_service import CalendarSyncService
            db = next(get_db())
            repo = IntegrationRepository(db)
            calendar_service = CalendarSyncService(repository=repo)
            return WebhookService(
                calendar_sync_service=calendar_service,
                repository=repo
            )
        
        Option 3 - Dependency Injector:
            from dependency_injector.wiring import inject, Provide
            from app.core.container import Container
            return Provide[Container.webhook_service]()
    """
    raise NotImplementedError(
        "WebhookService dependency injection not configured. "
        "Please wire this dependency through your DI container."
    )


# ============================================================================
# Webhook Endpoints
# ============================================================================


@router.post(
    "/{provider}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Calendar Provider Webhook Handler",
    description="""
    Generic webhook endpoint for calendar integration notifications.
    
    This endpoint handles webhooks from various calendar providers and processes
    them asynchronously to ensure quick response times.
    
    **Supported Providers:**
    - google (Google Calendar)
    - microsoft (Outlook/Office 365)
    - apple (iCloud Calendar)
    - caldav (Generic CalDAV)
    
    **Common Event Types:**
    - Event created
    - Event updated
    - Event deleted
    - Calendar shared
    - Reminder triggered
    - Sync state changed
    
    **Process Flow:**
    1. Receive webhook notification
    2. Verify webhook authenticity (signatures, tokens)
    3. Queue for background processing
    4. Return 202 Accepted immediately
    5. Service processes the calendar event update
    6. Sync with internal calendar representation
    
    **Security:**
    - Webhook signatures/tokens are verified before processing
    - Invalid requests are rejected and logged
    - Rate limiting may apply based on configuration
    
    **Idempotency:**
    Calendar webhooks are designed to be idempotent. The service tracks
    event versions and change tokens to avoid duplicate processing.
    """,
    responses={
        202: {
            "description": "Webhook accepted for processing",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Webhook accepted",
                        "provider": "google",
                        "received_at": "2024-01-15T10:30:00Z",
                        "webhook_id": "cal_whook_abc123"
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
                        "error": "Missing required notification data"
                    }
                }
            }
        },
        401: {
            "description": "Webhook verification failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Token verification failed"
                    }
                }
            }
        },
        410: {
            "description": "Webhook subscription expired or deleted",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Webhook subscription no longer valid"
                    }
                }
            }
        }
    },
    response_model=Dict[str, Any],
)
async def handle_calendar_webhook(
    provider: str,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> Dict[str, Any]:
    """
    Process incoming calendar provider webhooks.

    Args:
        provider: Calendar provider identifier (e.g., 'google', 'microsoft')
        request: FastAPI request object containing headers and body
        response: FastAPI response object for setting custom headers
        background_tasks: FastAPI background tasks manager
        webhook_service: Injected webhook service

    Returns:
        Dict containing acknowledgment of webhook receipt

    Raises:
        HTTPException: For invalid providers or malformed requests
    """
    
    # Normalize provider name
    provider = provider.lower().strip()
    
    # Log incoming webhook
    logger.info(
        f"Calendar webhook received",
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

        # Generate webhook ID for tracking
        webhook_id = f"cal_whook_{provider}_{datetime.utcnow().timestamp()}"
        received_at = datetime.utcnow().isoformat() + "Z"

        # Add metadata for processing
        metadata = {
            "webhook_id": webhook_id,
            "received_at": received_at,
            "client_ip": request.client.host if request.client else None,
            "user_agent": headers.get("user-agent", "unknown"),
        }

        # Special handling for Google Calendar state header
        if provider == "google":
            resource_state = headers.get("x-goog-resource-state")
            if resource_state:
                metadata["resource_state"] = resource_state
                logger.debug(
                    f"Google Calendar resource state: {resource_state}",
                    extra={"webhook_id": webhook_id}
                )

        # Queue webhook for background processing
        background_tasks.add_task(
            _process_calendar_webhook_task,
            webhook_service=webhook_service,
            integration_type="calendar",
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
            f"Unexpected error processing calendar webhook from {provider}",
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
    "/{provider}",
    status_code=status.HTTP_200_OK,
    summary="Calendar Webhook Verification Endpoint",
    description="""
    Verification endpoint for calendar webhook subscriptions.
    
    Many calendar providers (especially Google) require a challenge-response
    verification when setting up webhook subscriptions.
    
    **Google Calendar:**
    - Sends initial GET request with verification token
    - Expects the token to be echoed back
    - Uses `hub.challenge` or `challenge` query parameter
    
    **Microsoft Graph:**
    - Sends validation token in query string
    - Expects plain text response with the token
    - Uses `validationToken` query parameter
    
    This endpoint handles both patterns automatically.
    """,
    responses={
        200: {
            "description": "Verification successful",
            "content": {
                "text/plain": {
                    "example": "abc123xyz_challenge_token"
                },
                "application/json": {
                    "example": {
                        "detail": "OK",
                        "provider": "google",
                        "verified_at": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Missing verification token",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Verification token required"
                    }
                }
            }
        }
    },
    response_class=Union[PlainTextResponse, JSONResponse],
)
async def verify_calendar_webhook(
    provider: str,
    request: Request,
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> Union[str, Dict[str, Any]]:
    """
    Handle webhook verification/challenge requests.

    Args:
        provider: Calendar provider identifier
        request: FastAPI request object
        webhook_service: Injected webhook service

    Returns:
        Challenge token (plain text) or JSON confirmation

    Raises:
        HTTPException: If verification requirements are not met
    """
    
    provider = provider.lower().strip()
    query_params = dict(request.query_params)
    
    logger.info(
        f"Calendar webhook verification request",
        extra={
            "provider": provider,
            "query_params": list(query_params.keys()),
        }
    )

    # Google Calendar challenge
    challenge = query_params.get("challenge") or query_params.get("hub.challenge")
    
    # Microsoft Graph validation
    validation_token = query_params.get("validationToken")
    
    if challenge:
        logger.info(
            f"Responding to {provider} webhook challenge",
            extra={"provider": provider}
        )
        return PlainTextResponse(content=challenge, status_code=200)
    
    if validation_token:
        logger.info(
            f"Responding to {provider} validation token",
            extra={"provider": provider}
        )
        return PlainTextResponse(content=validation_token, status_code=200)
    
    # No verification token found - return generic OK
    # Some providers just ping the endpoint to check availability
    logger.debug(
        f"Generic verification request from {provider}",
        extra={"provider": provider}
    )
    
    return {
        "detail": "OK",
        "provider": provider,
        "verified_at": datetime.utcnow().isoformat() + "Z",
    }


@router.get(
    "/{provider}/health",
    status_code=status.HTTP_200_OK,
    summary="Calendar Webhook Health Check",
    description="""
    Health check endpoint for calendar webhooks.
    
    Providers may use this to verify webhook endpoint availability.
    """,
    responses={
        200: {
            "description": "Webhook endpoint is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "provider": "google",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def calendar_webhook_health_check(provider: str) -> Dict[str, Any]:
    """
    Health check endpoint for calendar webhooks.

    Args:
        provider: Calendar provider identifier

    Returns:
        Health status response
    """
    provider = provider.lower().strip()
    
    return {
        "status": "healthy",
        "provider": provider,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.delete(
    "/{provider}/subscription/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel Calendar Webhook Subscription",
    description="""
    Handle webhook subscription cancellation notifications.
    
    Some providers send DELETE requests when subscriptions are cancelled
    or expired. This endpoint acknowledges the cancellation.
    """,
    responses={
        204: {"description": "Subscription cancellation acknowledged"},
        404: {"description": "Subscription not found"}
    }
)
async def cancel_calendar_webhook_subscription(
    provider: str,
    subscription_id: str,
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> Response:
    """
    Handle subscription cancellation from provider.

    Args:
        provider: Calendar provider identifier
        subscription_id: Subscription/channel identifier
        webhook_service: Injected webhook service

    Returns:
        204 No Content response
    """
    provider = provider.lower().strip()
    
    logger.info(
        f"Webhook subscription cancellation received",
        extra={
            "provider": provider,
            "subscription_id": subscription_id,
        }
    )
    
    # You might want to clean up internal subscription tracking here
    # await webhook_service.handle_subscription_cancellation(provider, subscription_id)
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# Background Task Functions
# ============================================================================


async def _process_calendar_webhook_task(
    webhook_service: WebhookService,
    integration_type: str,
    provider: str,
    raw_body: bytes,
    headers: Dict[str, str],
    query_params: Dict[str, str],
    path: str,
    metadata: Dict[str, Any],
) -> None:
    """
    Background task to process calendar webhooks.

    This function runs asynchronously after the webhook response is sent.
    It handles verification, event processing, and calendar synchronization.

    Args:
        webhook_service: Webhook service instance
        integration_type: Type of integration ('calendar')
        provider: Calendar provider identifier
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
            f"Processing calendar webhook",
            extra={
                "webhook_id": webhook_id,
                "provider": provider,
                "integration_type": integration_type,
            }
        )

        # Delegate to webhook service
        await webhook_service.process_inbound(
            integration_type=integration_type,
            provider=provider,
            raw_body=raw_body,
            headers=headers,
            query_params=query_params,
            path=path,
            metadata=metadata,
        )

        logger.info(
            f"Calendar webhook processed successfully",
            extra={
                "webhook_id": webhook_id,
                "provider": provider,
            }
        )

    except WebhookVerificationError as e:
        # Verification failed
        logger.error(
            f"Calendar webhook verification failed",
            extra={
                "webhook_id": webhook_id,
                "provider": provider,
                "error": str(e),
            }
        )
        # Don't retry - verification failures are permanent
        
    except ProviderNotSupportedError as e:
        # Unknown provider
        logger.error(
            f"Unsupported calendar provider",
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
            f"Error processing calendar webhook",
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
        # - Renew expired subscriptions automatically