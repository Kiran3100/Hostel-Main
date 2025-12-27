# --- File: C:\Hostel-Main\app\api\v1\subscriptions\subscriptions.py ---
"""
Core subscription management endpoints.

This module handles CRUD operations and lifecycle management for subscriptions
including creation, retrieval, updates, activation, suspension, renewal, and cancellation.
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator

from app.core.logging import get_logger
from app.services.subscription.subscription_service import SubscriptionService
from app.schemas.subscription import (
    SubscriptionResponse,
    SubscriptionDetail,
    SubscriptionMetrics,
    SubscriptionCreate,
    SubscriptionUpdate,
)
from .dependencies import (
    get_subscription_service,
    get_current_user,
    verify_subscription_access,
    verify_hostel_access,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscriptions"],
)


# Query parameter models for better validation
class SubscriptionListFilters(BaseModel):
    """Query parameters for listing subscriptions."""
    hostel_id: Optional[str] = Field(None, description="Filter by hostel ID")
    status: Optional[str] = Field(None, description="Filter by status", alias="status_filter")
    plan_id: Optional[str] = Field(None, description="Filter by plan ID")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    
    class Config:
        populate_by_name = True


class CancellationRequest(BaseModel):
    """Request body for subscription cancellation."""
    reason: str = Field(..., min_length=3, max_length=500, description="Cancellation reason")
    effective_date: Optional[str] = Field(None, description="Effective date (ISO format)")
    feedback: Optional[str] = Field(None, max_length=1000, description="Additional feedback")


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.post(
    "",
    response_model=SubscriptionDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create new subscription",
    description="Create a new subscription for a hostel with specified plan and billing details.",
    responses={
        201: {"description": "Subscription created successfully"},
        400: {"description": "Invalid request data"},
        403: {"description": "Access forbidden"},
        409: {"description": "Subscription already exists"},
    }
)
async def create_subscription(
    payload: SubscriptionCreate,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> SubscriptionDetail:
    """
    Create a new subscription.
    
    Args:
        payload: Subscription creation data
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Created subscription details
        
    Raises:
        HTTPException: On validation or creation failure
    """
    logger.info(f"User {current_user.id} creating subscription for hostel {payload.hostel_id}")
    
    # Verify user has access to create subscription for this hostel
    await verify_hostel_access(payload.hostel_id, current_user)
    
    result = subscription_service.create_subscription(data=payload)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to create subscription: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    subscription = result.unwrap()
    logger.info(f"Successfully created subscription {subscription.id}")
    
    return subscription


@router.get(
    "",
    response_model=List[SubscriptionResponse],
    summary="List subscriptions",
    description="Retrieve a paginated list of subscriptions with optional filtering.",
    responses={
        200: {"description": "List of subscriptions"},
        400: {"description": "Invalid query parameters"},
    }
)
async def list_subscriptions(
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
    hostel_id: Optional[str] = Query(None, description="Filter by hostel ID"),
    status_filter: Optional[str] = Query(None, description="Filter by status (active, suspended, expired, cancelled)"),
    plan_id: Optional[str] = Query(None, description="Filter by plan ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> List[SubscriptionResponse]:
    """
    List subscriptions with filtering and pagination.
    
    Args:
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        hostel_id: Optional hostel filter
        status_filter: Optional status filter
        plan_id: Optional plan filter
        page: Page number
        page_size: Items per page
        
    Returns:
        List of subscriptions matching criteria
    """
    logger.info(f"User {current_user.id} listing subscriptions with filters: hostel={hostel_id}, status={status_filter}")
    
    filters = {
        "hostel_id": hostel_id,
        "status": status_filter,
        "plan_id": plan_id,
        "page": page,
        "page_size": page_size,
    }
    
    # If not admin, limit to user's hostels
    if not getattr(current_user, 'is_admin', False):
        user_hostels = getattr(current_user, 'hostel_ids', [])
        if hostel_id and hostel_id not in user_hostels:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to specified hostel"
            )
        filters["user_hostels"] = user_hostels
    
    result = subscription_service.list_subscriptions(filters=filters)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to list subscriptions: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionDetail,
    summary="Get subscription details",
    description="Retrieve detailed information about a specific subscription.",
    responses={
        200: {"description": "Subscription details"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def get_subscription(
    subscription_id: str,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> SubscriptionDetail:
    """
    Get detailed subscription information.
    
    Args:
        subscription_id: Subscription identifier
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Detailed subscription information
    """
    logger.info(f"User {current_user.id} retrieving subscription {subscription_id}")
    
    # Verify access and get subscription
    subscription = await verify_subscription_access(
        subscription_id, current_user, subscription_service
    )
    
    return subscription


@router.patch(
    "/{subscription_id}",
    response_model=SubscriptionDetail,
    summary="Update subscription",
    description="Update subscription details like billing information, notes, or metadata.",
    responses={
        200: {"description": "Subscription updated successfully"},
        400: {"description": "Invalid update data"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def update_subscription(
    subscription_id: str,
    payload: SubscriptionUpdate,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> SubscriptionDetail:
    """
    Update subscription details.
    
    Args:
        subscription_id: Subscription identifier
        payload: Update data
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Updated subscription details
    """
    logger.info(f"User {current_user.id} updating subscription {subscription_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = subscription_service.update_subscription(
        subscription_id=subscription_id,
        data=payload,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to update subscription {subscription_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    updated = result.unwrap()
    logger.info(f"Successfully updated subscription {subscription_id}")
    
    return updated


@router.get(
    "/hostels/{hostel_id}",
    response_model=List[SubscriptionResponse],
    summary="List subscriptions for hostel",
    description="Get all subscriptions associated with a specific hostel.",
    responses={
        200: {"description": "List of hostel subscriptions"},
        403: {"description": "Access forbidden"},
    }
)
async def list_subscriptions_for_hostel(
    hostel_id: str,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> List[SubscriptionResponse]:
    """
    List all subscriptions for a specific hostel.
    
    Args:
        hostel_id: Hostel identifier
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        List of subscriptions for the hostel
    """
    logger.info(f"User {current_user.id} listing subscriptions for hostel {hostel_id}")
    
    # Verify access
    await verify_hostel_access(hostel_id, current_user)
    
    result = subscription_service.list_subscriptions_for_hostel(hostel_id=hostel_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to list subscriptions for hostel {hostel_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/hostels/{hostel_id}/active",
    response_model=Optional[SubscriptionDetail],
    summary="Get active subscription for hostel",
    description="Retrieve the currently active subscription for a hostel.",
    responses={
        200: {"description": "Active subscription or null if none"},
        403: {"description": "Access forbidden"},
    }
)
async def get_active_subscription_for_hostel(
    hostel_id: str,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> Optional[SubscriptionDetail]:
    """
    Get the active subscription for a hostel.
    
    Args:
        hostel_id: Hostel identifier
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Active subscription details or None
    """
    logger.info(f"User {current_user.id} retrieving active subscription for hostel {hostel_id}")
    
    # Verify access
    await verify_hostel_access(hostel_id, current_user)
    
    result = subscription_service.get_active_subscription_for_hostel(hostel_id=hostel_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.warning(f"No active subscription for hostel {hostel_id}: {error}")
        return None
    
    return result.unwrap()


@router.get(
    "/expiring",
    response_model=List[SubscriptionResponse],
    summary="Get expiring subscriptions",
    description="Retrieve subscriptions that are expiring within specified days.",
    responses={
        200: {"description": "List of expiring subscriptions"},
    }
)
async def get_expiring_subscriptions(
    days: int = Query(30, ge=1, le=365, description="Number of days to look ahead"),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> List[SubscriptionResponse]:
    """
    Get subscriptions expiring within specified days.
    
    Args:
        days: Number of days to look ahead
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        List of expiring subscriptions
    """
    logger.info(f"User {current_user.id} retrieving subscriptions expiring in {days} days")
    
    result = subscription_service.get_expiring_subscriptions(days=days)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get expiring subscriptions: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    subscriptions = result.unwrap()
    
    # Filter by user's hostels if not admin
    if not getattr(current_user, 'is_admin', False):
        user_hostels = set(getattr(current_user, 'hostel_ids', []))
        subscriptions = [s for s in subscriptions if s.hostel_id in user_hostels]
    
    return subscriptions


@router.get(
    "/{subscription_id}/billing-history",
    summary="Get billing history",
    description="Retrieve complete billing history for a subscription.",
    responses={
        200: {"description": "Billing history"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def get_billing_history(
    subscription_id: str,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Get billing history for a subscription.
    
    Args:
        subscription_id: Subscription identifier
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Billing history data
    """
    logger.info(f"User {current_user.id} retrieving billing history for subscription {subscription_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = subscription_service.get_billing_history(subscription_id=subscription_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get billing history: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.post(
    "/{subscription_id}/activate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Activate subscription",
    description="Activate a suspended or pending subscription.",
    responses={
        204: {"description": "Subscription activated successfully"},
        400: {"description": "Cannot activate subscription in current state"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def activate_subscription(
    subscription_id: str,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Activate a subscription.
    
    Args:
        subscription_id: Subscription identifier
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
    """
    logger.info(f"User {current_user.id} activating subscription {subscription_id}")
    
    # Verify access (require admin for activation)
    await verify_subscription_access(
        subscription_id, current_user, subscription_service, require_admin=True
    )
    
    result = subscription_service.activate_subscription(subscription_id=subscription_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to activate subscription {subscription_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    logger.info(f"Successfully activated subscription {subscription_id}")


@router.post(
    "/{subscription_id}/suspend",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Suspend subscription",
    description="Suspend an active subscription (admin only).",
    responses={
        204: {"description": "Subscription suspended successfully"},
        400: {"description": "Cannot suspend subscription in current state"},
        403: {"description": "Admin access required"},
        404: {"description": "Subscription not found"},
    }
)
async def suspend_subscription(
    subscription_id: str,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Suspend a subscription.
    
    Args:
        subscription_id: Subscription identifier
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
    """
    logger.info(f"User {current_user.id} suspending subscription {subscription_id}")
    
    # Verify admin access
    await verify_subscription_access(
        subscription_id, current_user, subscription_service, require_admin=True
    )
    
    result = subscription_service.suspend_subscription(subscription_id=subscription_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to suspend subscription {subscription_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    logger.info(f"Successfully suspended subscription {subscription_id}")


@router.post(
    "/{subscription_id}/renew",
    response_model=SubscriptionDetail,
    summary="Renew subscription",
    description="Renew an expiring or expired subscription.",
    responses={
        200: {"description": "Subscription renewed successfully"},
        400: {"description": "Cannot renew subscription"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def renew_subscription(
    subscription_id: str,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> SubscriptionDetail:
    """
    Renew a subscription.
    
    Args:
        subscription_id: Subscription identifier
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Renewed subscription details
    """
    logger.info(f"User {current_user.id} renewing subscription {subscription_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = subscription_service.renew_subscription(subscription_id=subscription_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to renew subscription {subscription_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    renewed = result.unwrap()
    logger.info(f"Successfully renewed subscription {subscription_id}")
    
    return renewed


@router.post(
    "/{subscription_id}/preview-cancellation",
    summary="Preview subscription cancellation",
    description="Preview the impact of canceling a subscription (prorated refunds, etc.).",
    responses={
        200: {"description": "Cancellation preview"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def preview_cancellation(
    subscription_id: str,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Preview subscription cancellation impact.
    
    Args:
        subscription_id: Subscription identifier
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Cancellation preview data including refund amounts
    """
    logger.info(f"User {current_user.id} previewing cancellation for subscription {subscription_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = subscription_service.preview_cancellation(subscription_id=subscription_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to preview cancellation: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.post(
    "/{subscription_id}/cancel",
    response_model=SubscriptionDetail,
    summary="Cancel subscription",
    description="Cancel a subscription with optional reason and effective date.",
    responses={
        200: {"description": "Subscription cancelled successfully"},
        400: {"description": "Cannot cancel subscription"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def cancel_subscription(
    subscription_id: str,
    payload: CancellationRequest,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> SubscriptionDetail:
    """
    Cancel a subscription.
    
    Args:
        subscription_id: Subscription identifier
        payload: Cancellation request data
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Cancelled subscription details
    """
    logger.info(f"User {current_user.id} cancelling subscription {subscription_id}, reason: {payload.reason}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = subscription_service.cancel_subscription(
        subscription_id=subscription_id,
        data=payload.dict(),
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to cancel subscription {subscription_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    cancelled = result.unwrap()
    logger.info(f"Successfully cancelled subscription {subscription_id}")
    
    return cancelled


@router.get(
    "/{subscription_id}/metrics",
    response_model=SubscriptionMetrics,
    summary="Get subscription metrics",
    description="Retrieve usage metrics, billing statistics, and analytics for a subscription.",
    responses={
        200: {"description": "Subscription metrics"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def get_subscription_metrics(
    subscription_id: str,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> SubscriptionMetrics:
    """
    Get subscription metrics and analytics.
    
    Args:
        subscription_id: Subscription identifier
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Subscription metrics data
    """
    logger.info(f"User {current_user.id} retrieving metrics for subscription {subscription_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = subscription_service.get_subscription_metrics(subscription_id=subscription_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get metrics: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()