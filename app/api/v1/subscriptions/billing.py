# --- File: C:\Hostel-Main\app\api\v1\subscriptions\billing.py ---
"""
Subscription billing cycle management endpoints.

This module handles billing cycle operations including retrieval,
calculation, and management of billing periods.
"""
from typing import Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, validator

from app.core.logging import get_logger
from app.services.subscription.subscription_billing_service import SubscriptionBillingService
from app.schemas.subscription import BillingCycleInfo
from .dependencies import (
    get_billing_service,
    get_current_user,
    get_subscription_service,
    verify_subscription_access,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscriptions - Billing"],
)


class BillingCycleCreate(BaseModel):
    """Request body for manual billing cycle creation."""
    start_date: str = Field(..., description="Start date (ISO format)")
    end_date: str = Field(..., description="End date (ISO format)")
    amount: float = Field(..., gt=0, description="Billing amount")
    
    @validator('start_date', 'end_date')
    def validate_date_format(cls, v):
        """Validate ISO date format."""
        try:
            datetime.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError("Date must be in ISO format (YYYY-MM-DD)")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        """Validate end date is after start date."""
        if 'start_date' in values:
            start = datetime.fromisoformat(values['start_date'])
            end = datetime.fromisoformat(v)
            if end <= start:
                raise ValueError("End date must be after start date")
        return v


@router.get(
    "/{subscription_id}/billing-cycles/current",
    response_model=BillingCycleInfo,
    summary="Get current billing cycle",
    description="Retrieve the current active billing cycle for a subscription.",
    responses={
        200: {"description": "Current billing cycle"},
        403: {"description": "Access forbidden"},
        404: {"description": "No current billing cycle found"},
    }
)
async def get_current_billing_cycle(
    subscription_id: str = Path(..., description="Subscription ID"),
    billing_service: SubscriptionBillingService = Depends(get_billing_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> BillingCycleInfo:
    """
    Get current billing cycle.
    
    Args:
        subscription_id: Subscription identifier
        billing_service: Billing service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Current billing cycle information
    """
    logger.info(f"User {current_user.id} retrieving current billing cycle for subscription {subscription_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = billing_service.get_billing_cycle_info(subscription_id=subscription_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get current billing cycle: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current billing cycle found"
        )
    
    return result.unwrap()


@router.get(
    "/{subscription_id}/billing-cycles",
    response_model=List[BillingCycleInfo],
    summary="List billing cycles",
    description="List all billing cycles for a subscription with optional filtering.",
    responses={
        200: {"description": "List of billing cycles"},
        403: {"description": "Access forbidden"},
    }
)
async def list_billing_cycles(
    subscription_id: str,
    billing_service: SubscriptionBillingService = Depends(get_billing_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
    include_past: bool = Query(True, description="Include past billing cycles"),
    include_future: bool = Query(True, description="Include future billing cycles"),
) -> List[BillingCycleInfo]:
    """
    List billing cycles for subscription.
    
    Args:
        subscription_id: Subscription identifier
        billing_service: Billing service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        include_past: Include past cycles
        include_future: Include future cycles
        
    Returns:
        List of billing cycles
    """
    logger.info(f"User {current_user.id} listing billing cycles for subscription {subscription_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = billing_service.list_billing_cycles(
        subscription_id=subscription_id,
        filters={
            "include_past": include_past,
            "include_future": include_future,
        },
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to list billing cycles: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{subscription_id}/billing-cycles/by-date",
    response_model=BillingCycleInfo,
    summary="Get billing cycle by date",
    description="Retrieve the billing cycle that contains a specific date.",
    responses={
        200: {"description": "Billing cycle containing the date"},
        400: {"description": "Invalid date format"},
        403: {"description": "Access forbidden"},
        404: {"description": "No billing cycle found for date"},
    }
)
async def get_billing_cycle_by_date(
    subscription_id: str,
    date: str = Query(..., description="ISO date within billing cycle (YYYY-MM-DD)"),
    billing_service: SubscriptionBillingService = Depends(get_billing_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> BillingCycleInfo:
    """
    Get billing cycle containing a specific date.
    
    Args:
        subscription_id: Subscription identifier
        date: Target date
        billing_service: Billing service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Billing cycle information
    """
    logger.info(f"User {current_user.id} retrieving billing cycle for date {date}")
    
    # Validate date format
    try:
        datetime.fromisoformat(date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use ISO format (YYYY-MM-DD)"
        )
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = billing_service.get_billing_cycle_by_date(
        subscription_id=subscription_id,
        date=date,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get billing cycle by date: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No billing cycle found for date {date}"
        )
    
    return result.unwrap()


@router.get(
    "/{subscription_id}/billing-cycles/upcoming",
    response_model=List[BillingCycleInfo],
    summary="Get upcoming billing cycles",
    description="Retrieve upcoming billing cycles for planning purposes.",
    responses={
        200: {"description": "List of upcoming billing cycles"},
        403: {"description": "Access forbidden"},
    }
)
async def get_upcoming_billing_cycles(
    subscription_id: str,
    months_ahead: int = Query(3, ge=1, le=24, description="Number of months to look ahead"),
    billing_service: SubscriptionBillingService = Depends(get_billing_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> List[BillingCycleInfo]:
    """
    Get upcoming billing cycles.
    
    Args:
        subscription_id: Subscription identifier
        months_ahead: Number of months to look ahead
        billing_service: Billing service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        List of upcoming billing cycles
    """
    logger.info(f"User {current_user.id} retrieving {months_ahead} months of upcoming billing cycles")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = billing_service.get_upcoming_billing_cycles(
        subscription_id=subscription_id,
        months_ahead=months_ahead,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get upcoming billing cycles: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{subscription_id}/billing-cycles/past",
    response_model=List[BillingCycleInfo],
    summary="Get past billing cycles",
    description="Retrieve historical billing cycles.",
    responses={
        200: {"description": "List of past billing cycles"},
        403: {"description": "Access forbidden"},
    }
)
async def get_past_billing_cycles(
    subscription_id: str,
    billing_service: SubscriptionBillingService = Depends(get_billing_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
    limit: int = Query(12, ge=1, le=100, description="Maximum number of cycles to return"),
) -> List[BillingCycleInfo]:
    """
    Get past billing cycles.
    
    Args:
        subscription_id: Subscription identifier
        billing_service: Billing service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        limit: Maximum number of cycles to return
        
    Returns:
        List of past billing cycles
    """
    logger.info(f"User {current_user.id} retrieving past billing cycles (limit={limit})")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = billing_service.get_past_billing_cycles(
        subscription_id=subscription_id,
        limit=limit
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get past billing cycles: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.post(
    "/{subscription_id}/billing-cycles/recalculate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Recalculate billing cycles",
    description="Trigger recalculation of billing cycles (admin only).",
    responses={
        202: {"description": "Recalculation initiated"},
        403: {"description": "Admin access required"},
    }
)
async def recalculate_billing_cycles(
    subscription_id: str,
    billing_service: SubscriptionBillingService = Depends(get_billing_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Recalculate billing cycles.
    
    Args:
        subscription_id: Subscription identifier
        billing_service: Billing service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Recalculation status
    """
    logger.info(f"User {current_user.id} recalculating billing cycles for subscription {subscription_id}")
    
    # Verify admin access
    await verify_subscription_access(
        subscription_id, current_user, subscription_service, require_admin=True
    )
    
    result = billing_service.recalculate_billing_cycles(subscription_id=subscription_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to recalculate billing cycles: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.post(
    "/{subscription_id}/billing-cycles",
    response_model=BillingCycleInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Create billing cycle manually",
    description="Manually create a billing cycle (admin only).",
    responses={
        201: {"description": "Billing cycle created"},
        400: {"description": "Invalid billing cycle data"},
        403: {"description": "Admin access required"},
    }
)
async def create_billing_cycle(
    subscription_id: str,
    payload: BillingCycleCreate,
    billing_service: SubscriptionBillingService = Depends(get_billing_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> BillingCycleInfo:
    """
    Create billing cycle manually.
    
    Args:
        subscription_id: Subscription identifier
        payload: Billing cycle creation data
        billing_service: Billing service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Created billing cycle
    """
    logger.info(f"User {current_user.id} creating manual billing cycle for subscription {subscription_id}")
    
    # Verify admin access
    await verify_subscription_access(
        subscription_id, current_user, subscription_service, require_admin=True
    )
    
    result = billing_service.create_billing_cycle(
        subscription_id=subscription_id,
        data=payload.dict(),
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to create billing cycle: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    cycle = result.unwrap()
    logger.info(f"Successfully created billing cycle {cycle.id}")
    
    return cycle


@router.get(
    "/{subscription_id}/billing-cycles/total-billed",
    summary="Get total billed amount",
    description="Calculate total billed amount for a period.",
    responses={
        200: {"description": "Total billed amount"},
        403: {"description": "Access forbidden"},
    }
)
async def get_total_billed_amount(
    subscription_id: str,
    start_date: Optional[str] = Query(None, description="Period start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Period end date (ISO format)"),
    billing_service: SubscriptionBillingService = Depends(get_billing_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Get total billed amount for period.
    
    Args:
        subscription_id: Subscription identifier
        start_date: Optional period start
        end_date: Optional period end
        billing_service: Billing service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Total billed amount and breakdown
    """
    logger.info(f"User {current_user.id} calculating total billed amount")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = billing_service.get_total_billed_amount(
        subscription_id=subscription_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to calculate total billed amount: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{subscription_id}/billing-cycles/next-billing-date",
    summary="Get next billing date",
    description="Get the next billing date for a subscription.",
    responses={
        200: {"description": "Next billing date"},
        403: {"description": "Access forbidden"},
    }
)
async def get_next_billing_date(
    subscription_id: str,
    billing_service: SubscriptionBillingService = Depends(get_billing_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Get next billing date.
    
    Args:
        subscription_id: Subscription identifier
        billing_service: Billing service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Next billing date and related information
    """
    logger.info(f"User {current_user.id} retrieving next billing date for subscription {subscription_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = billing_service.get_next_billing_date(subscription_id=subscription_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get next billing date: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()