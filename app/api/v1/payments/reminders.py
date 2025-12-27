"""
Payment reminder management API endpoints.

Handles reminder configuration, manual sending, and history tracking.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query, Path, status, HTTPException

from app.core.dependencies import get_current_user
from app.services.payment.payment_reminder_service import PaymentReminderService
from app.schemas.payment import (
    ReminderConfig,
    ReminderConfigUpdate,
    ReminderSendRequest,
    ReminderHistoryItem,
    ReminderSendResponse,
)
from app.core.exceptions import UnauthorizedError, ReminderConfigNotFoundError

router = APIRouter(tags=["Payments - Reminders"])


def get_reminder_service() -> PaymentReminderService:
    """
    Factory for PaymentReminderService dependency injection.
    Should be implemented by the DI container.
    """
    raise NotImplementedError(
        "Reminder service must be configured in dependency injection container"
    )


@router.post(
    "/reminders/config",
    response_model=ReminderConfig,
    summary="Configure payment reminders",
    description="Set up or update payment reminder configuration for a hostel.",
    responses={
        200: {"description": "Reminder configuration updated successfully"},
        201: {"description": "Reminder configuration created successfully"},
        400: {"description": "Invalid configuration data"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
    },
)
async def configure_reminders(
    hostel_id: str = Query(..., description="Hostel ID"),
    config: ReminderConfigUpdate = ...,
    reminder_service: PaymentReminderService = Depends(get_reminder_service),
    current_user: Any = Depends(get_current_user),
) -> ReminderConfig:
    """
    Configure payment reminder settings for a hostel.

    Args:
        hostel_id: ID of the hostel
        config: Reminder configuration including frequency, templates, etc.
        reminder_service: Injected reminder service
        current_user: Currently authenticated user (must be admin)

    Returns:
        ReminderConfig: Updated configuration

    Raises:
        HTTPException: 403 if unauthorized, 400 for invalid config
    """
    result = await reminder_service.set_reminder_config(
        hostel_id=hostel_id,
        config=config,
        set_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.get(
    "/reminders/config",
    response_model=ReminderConfig,
    summary="Get reminder configuration",
    description="Retrieve payment reminder configuration for a hostel.",
    responses={
        200: {"description": "Configuration retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Configuration not found"},
    },
)
async def get_reminder_config(
    hostel_id: str = Query(..., description="Hostel ID"),
    reminder_service: PaymentReminderService = Depends(get_reminder_service),
    current_user: Any = Depends(get_current_user),
) -> ReminderConfig:
    """
    Get payment reminder configuration for a hostel.

    Args:
        hostel_id: ID of the hostel
        reminder_service: Injected reminder service
        current_user: Currently authenticated user

    Returns:
        ReminderConfig: Current reminder configuration

    Raises:
        HTTPException: 404 if configuration not found
    """
    result = await reminder_service.get_reminder_config(
        hostel_id=hostel_id,
        requesting_user_id=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, ReminderConfigNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.post(
    "/reminders/send",
    response_model=ReminderSendResponse,
    summary="Manually send reminders",
    description="Trigger manual sending of payment reminders based on criteria.",
    responses={
        200: {"description": "Reminders sent successfully"},
        400: {"description": "Invalid send criteria"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
    },
)
async def send_reminders(
    payload: ReminderSendRequest,
    reminder_service: PaymentReminderService = Depends(get_reminder_service),
    current_user: Any = Depends(get_current_user),
) -> ReminderSendResponse:
    """
    Manually trigger sending of payment reminders.

    Args:
        payload: Criteria for sending reminders (e.g., specific payments, overdue only)
        reminder_service: Injected reminder service
        current_user: Currently authenticated user (must be admin)

    Returns:
        ReminderSendResponse: Summary of reminders sent

    Raises:
        HTTPException: 403 if unauthorized, 400 for invalid criteria
    """
    result = await reminder_service.send_reminders(
        criteria=payload,
        triggered_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.get(
    "/reminders/{payment_id}/history",
    response_model=List[ReminderHistoryItem],
    summary="Get reminder history for payment",
    description="Retrieve history of all reminders sent for a specific payment.",
    responses={
        200: {"description": "Reminder history retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Payment not found"},
    },
)
async def get_reminder_history(
    payment_id: str = Path(..., description="Payment ID"),
    reminder_service: PaymentReminderService = Depends(get_reminder_service),
    current_user: Any = Depends(get_current_user),
) -> List[ReminderHistoryItem]:
    """
    Get reminder history for a specific payment.

    Args:
        payment_id: ID of the payment
        reminder_service: Injected reminder service
        current_user: Currently authenticated user

    Returns:
        List[ReminderHistoryItem]: List of reminders sent for this payment

    Raises:
        HTTPException: 404 if payment not found
    """
    result = await reminder_service.get_reminders_for_payment(
        payment_id=payment_id,
        requesting_user_id=current_user.id,
    )
    
    if result.is_err():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found or no reminders sent"
        )
    
    return result.unwrap()


@router.delete(
    "/reminders/config",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete reminder configuration",
    description="Remove payment reminder configuration for a hostel.",
    responses={
        204: {"description": "Configuration deleted successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Configuration not found"},
    },
)
async def delete_reminder_config(
    hostel_id: str = Query(..., description="Hostel ID"),
    reminder_service: PaymentReminderService = Depends(get_reminder_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Delete reminder configuration for a hostel.

    Args:
        hostel_id: ID of the hostel
        reminder_service: Injected reminder service
        current_user: Currently authenticated user (must be admin)

    Raises:
        HTTPException: 403 if unauthorized, 404 if config not found
    """
    result = await reminder_service.delete_reminder_config(
        hostel_id=hostel_id,
        deleted_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error)
            )
        elif isinstance(error, ReminderConfigNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )