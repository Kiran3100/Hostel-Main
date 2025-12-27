"""
Payment gateway webhook handlers.

Handles server-to-server notifications and browser callbacks from payment gateways.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request, BackgroundTasks, status, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

from app.services.payment.payment_gateway_service import PaymentGatewayService
from app.core.exceptions import PaymentGatewayError

router = APIRouter(tags=["Payments - Webhook"])


def get_gateway_service() -> PaymentGatewayService:
    """
    Factory for PaymentGatewayService dependency injection.
    Should be implemented by the DI container.
    """
    raise NotImplementedError(
        "Payment gateway service must be configured in dependency injection container"
    )


@router.post(
    "/webhook/{provider}",
    summary="Payment gateway webhook",
    status_code=status.HTTP_200_OK,
    description="Receive and process payment gateway webhook notifications.",
    responses={
        200: {"description": "Webhook received and queued for processing"},
        400: {"description": "Invalid webhook signature or data"},
        500: {"description": "Webhook processing error"},
    },
)
async def handle_payment_webhook(
    provider: str,
    request: Request,
    background_tasks: BackgroundTasks,
    gateway_service: PaymentGatewayService = Depends(get_gateway_service),
) -> JSONResponse:
    """
    Handle server-to-server webhook notifications from payment gateways.

    This endpoint receives asynchronous notifications from payment gateways
    about payment status changes. The webhook is verified and processed
    in the background to ensure quick response times.

    Args:
        provider: Payment gateway provider name (e.g., 'razorpay', 'stripe')
        request: FastAPI request object
        background_tasks: FastAPI background tasks manager
        gateway_service: Injected payment gateway service

    Returns:
        JSONResponse: Acknowledgment of webhook receipt

    Raises:
        HTTPException: 400 for invalid webhooks, 500 for processing errors
    """
    try:
        # Extract webhook data
        raw_body = await request.body()
        headers = dict(request.headers)
        query_params = dict(request.query_params)
        
        # Validate webhook signature synchronously for security
        validation_result = await gateway_service.validate_webhook_signature(
            provider=provider,
            raw_body=raw_body,
            headers=headers,
        )
        
        if validation_result.is_err():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature"
            )
        
        # Process webhook asynchronously
        background_tasks.add_task(
            _process_webhook_async,
            gateway_service=gateway_service,
            provider=provider,
            raw_body=raw_body,
            headers=headers,
            query_params=query_params,
        )
        
        # Return immediate acknowledgment
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "received", "message": "Webhook queued for processing"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Log error but return 200 to prevent gateway retries
        # logger.error(f"Webhook handling error: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "error", "message": "Webhook received but processing failed"}
        )


async def _process_webhook_async(
    gateway_service: PaymentGatewayService,
    provider: str,
    raw_body: bytes,
    headers: dict,
    query_params: dict,
) -> None:
    """
    Process webhook asynchronously in the background.

    Args:
        gateway_service: Payment gateway service instance
        provider: Payment gateway provider name
        raw_body: Raw webhook body
        headers: Request headers
        query_params: Query parameters
    """
    try:
        result = await gateway_service.handle_webhook(
            provider=provider,
            raw_body=raw_body,
            headers=headers,
            query_params=query_params,
        )
        
        if result.is_err():
            error = result.unwrap_err()
            # logger.error(f"Webhook processing failed: {str(error)}")
            # Optionally trigger alerts or retry mechanisms
            
    except Exception as e:
        # logger.critical(f"Critical error in webhook processing: {str(e)}", exc_info=True)
        pass


@router.get(
    "/callback/{provider}",
    summary="Payment gateway return callback",
    description="Handle browser redirects after payment completion.",
    responses={
        200: {"description": "Payment verification result"},
        302: {"description": "Redirect to success/failure page"},
        400: {"description": "Invalid callback data"},
    },
)
async def handle_payment_callback(
    provider: str,
    request: Request,
    gateway_service: PaymentGatewayService = Depends(get_gateway_service),
) -> Any:
    """
    Handle browser redirects (return URLs) from payment gateways.

    After a user completes payment on the gateway's hosted page, they are
    redirected back to this endpoint with payment status information.
    This endpoint verifies the payment and redirects the user to the
    appropriate success or failure page.

    Args:
        provider: Payment gateway provider name
        request: FastAPI request object
        gateway_service: Injected payment gateway service

    Returns:
        RedirectResponse or JSONResponse: Redirect to appropriate page or status JSON

    Raises:
        HTTPException: 400 for invalid callback data
    """
    try:
        query_params = dict(request.query_params)
        
        result = await gateway_service.handle_callback(
            provider=provider,
            params=query_params,
        )
        
        if result.is_err():
            error = result.unwrap_err()
            # Redirect to failure page with error message
            return RedirectResponse(
                url=f"/payment/failed?error={str(error)}",
                status_code=status.HTTP_302_FOUND
            )
        
        callback_data = result.unwrap()
        
        # Check payment status and redirect accordingly
        if callback_data.get("status") == "success":
            payment_id = callback_data.get("payment_id")
            return RedirectResponse(
                url=f"/payment/success?payment_id={payment_id}",
                status_code=status.HTTP_302_FOUND
            )
        else:
            return RedirectResponse(
                url=f"/payment/failed?reason={callback_data.get('reason', 'unknown')}",
                status_code=status.HTTP_302_FOUND
            )
            
    except Exception as e:
        # logger.error(f"Callback handling error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid callback data"
        )


@router.get(
    "/webhook/test/{provider}",
    summary="Test webhook endpoint",
    description="Test endpoint for webhook integration (development only).",
    include_in_schema=False,  # Hide from production docs
)
async def test_webhook(
    provider: str,
    gateway_service: PaymentGatewayService = Depends(get_gateway_service),
) -> dict:
    """
    Test webhook endpoint for development purposes.
    Should be disabled in production.

    Args:
        provider: Payment gateway provider name
        gateway_service: Injected payment gateway service

    Returns:
        dict: Test webhook response
    """
    # This should only be accessible in development environment
    return {
        "provider": provider,
        "status": "test_mode",
        "message": "This endpoint is for testing only"
    }