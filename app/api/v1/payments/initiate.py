"""
Payment initiation API endpoints.

Handles online payment gateway integration and payment flow initiation.
"""

from typing import Any

from fastapi import APIRouter, Depends, status, HTTPException

from app.core.dependencies import get_current_user
from app.services.payment.payment_gateway_service import PaymentGatewayService
from app.schemas.payment import (
    PaymentRequest,
    PaymentInitiation,
)
from app.core.exceptions import (
    PaymentGatewayError,
    InvalidPaymentDataError,
    UnauthorizedError,
)

router = APIRouter(tags=["Payments - Initiate"])


def get_gateway_service() -> PaymentGatewayService:
    """
    Factory for PaymentGatewayService dependency injection.
    Should be implemented by the DI container.
    """
    raise NotImplementedError(
        "Payment gateway service must be configured in dependency injection container"
    )


@router.post(
    "/initiate",
    response_model=PaymentInitiation,
    status_code=status.HTTP_200_OK,
    summary="Initiate online payment",
    description="Start an online payment flow with a configured payment gateway.",
    responses={
        200: {"description": "Payment initiated successfully, returns checkout URL or SDK parameters"},
        400: {"description": "Invalid payment request data"},
        401: {"description": "Authentication required"},
        403: {"description": "Payment initiation not allowed"},
        500: {"description": "Payment gateway error"},
    },
)
async def initiate_payment(
    payload: PaymentRequest,
    gateway_service: PaymentGatewayService = Depends(get_gateway_service),
    current_user: Any = Depends(get_current_user),
) -> PaymentInitiation:
    """
    Initiate an online payment transaction.

    This endpoint starts the payment flow with the configured payment gateway
    (e.g., Razorpay, Stripe, PayPal) and returns the necessary information
    for the client to complete the payment.

    Args:
        payload: Payment request containing amount, currency, gateway provider, etc.
        gateway_service: Injected payment gateway service
        current_user: Currently authenticated user

    Returns:
        PaymentInitiation: Contains checkout URL, payment ID, or SDK initialization data

    Raises:
        HTTPException: 400 for invalid data, 403 for unauthorized, 500 for gateway errors
    """
    try:
        result = await gateway_service.initiate_online_payment(
            user_id=current_user.id,
            data=payload,
        )
        
        if result.is_err():
            error = result.unwrap_err()
            
            if isinstance(error, InvalidPaymentDataError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(error)
                )
            elif isinstance(error, UnauthorizedError):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=str(error)
                )
            elif isinstance(error, PaymentGatewayError):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Payment gateway error: {str(error)}"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(error)
                )
        
        return result.unwrap()
        
    except Exception as e:
        # Log the exception for debugging
        # logger.error(f"Payment initiation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate payment. Please try again later."
        )


@router.post(
    "/verify",
    summary="Verify payment completion",
    description="Verify payment status after user completes payment on gateway.",
    responses={
        200: {"description": "Payment verification result"},
        400: {"description": "Invalid verification data"},
        401: {"description": "Authentication required"},
        404: {"description": "Payment not found"},
    },
)
async def verify_payment(
    payment_id: str,
    gateway_service: PaymentGatewayService = Depends(get_gateway_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Verify the completion status of a payment.

    This endpoint checks with the payment gateway to verify if a payment
    has been successfully completed.

    Args:
        payment_id: ID of the payment to verify
        gateway_service: Injected payment gateway service
        current_user: Currently authenticated user

    Returns:
        dict: Verification result with payment status

    Raises:
        HTTPException: For various verification errors
    """
    result = await gateway_service.verify_payment_completion(
        payment_id=payment_id,
        user_id=current_user.id
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, PaymentGatewayError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment {payment_id} not found"
            )
    
    return result.unwrap()