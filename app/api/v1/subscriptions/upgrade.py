# --- File: C:\Hostel-Main\app\api\v1\subscriptions\upgrade.py ---
"""
Subscription plan upgrade/downgrade endpoints.

This module handles plan changes including previews, upgrades,
downgrades, and plan change history.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.subscription.subscription_upgrade_service import SubscriptionUpgradeService
from app.schemas.subscription import (
    PlanChangePreview,
    PlanChangeConfirmation,
)
from .dependencies import (
    get_upgrade_service,
    get_current_user,
    get_subscription_service,
    verify_subscription_access,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscriptions - Upgrades"],
)


class PlanChangeRequest(BaseModel):
    """Request body for plan change."""
    new_plan_id: str = Field(..., description="Target plan ID")
    effective_date: Optional[str] = Field(None, description="Effective date (ISO format)")
    proration: bool = Field(True, description="Apply proration")
    notes: Optional[str] = Field(None, max_length=500, description="Change notes")


@router.post(
    "/{subscription_id}/plan-change/preview",
    response_model=PlanChangePreview,
    summary="Preview plan change",
    description="Preview the impact of changing to a different plan.",
    responses={
        200: {"description": "Plan change preview"},
        400: {"description": "Invalid request"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription or plan not found"},
    }
)
async def preview_plan_change(
    subscription_id: str,
    payload: PlanChangeRequest,
    upgrade_service: SubscriptionUpgradeService = Depends(get_upgrade_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> PlanChangePreview:
    """
    Preview plan change impact.
    
    Args:
        subscription_id: Subscription identifier
        payload: Plan change request
        upgrade_service: Upgrade service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Plan change preview with cost calculations
    """
    logger.info(f"User {current_user.id} previewing plan change for subscription {subscription_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = upgrade_service.preview_plan_change(
        subscription_id=subscription_id,
        data=payload.dict(),
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to preview plan change: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.post(
    "/{subscription_id}/upgrade/preview",
    response_model=PlanChangePreview,
    summary="Preview upgrade",
    description="Preview the impact of upgrading to a higher-tier plan.",
    responses={
        200: {"description": "Upgrade preview"},
        400: {"description": "Invalid upgrade request"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription or plan not found"},
    }
)
async def preview_upgrade(
    subscription_id: str,
    new_plan_id: str,
    upgrade_service: SubscriptionUpgradeService = Depends(get_upgrade_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> PlanChangePreview:
    """
    Preview subscription upgrade.
    
    Args:
        subscription_id: Subscription identifier
        new_plan_id: Target plan ID
        upgrade_service: Upgrade service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Upgrade preview
    """
    logger.info(f"User {current_user.id} previewing upgrade to plan {new_plan_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = upgrade_service.preview_upgrade(
        subscription_id=subscription_id,
        new_plan_id=new_plan_id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to preview upgrade: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.post(
    "/{subscription_id}/downgrade/preview",
    response_model=PlanChangePreview,
    summary="Preview downgrade",
    description="Preview the impact of downgrading to a lower-tier plan.",
    responses={
        200: {"description": "Downgrade preview"},
        400: {"description": "Invalid downgrade request"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription or plan not found"},
    }
)
async def preview_downgrade(
    subscription_id: str,
    new_plan_id: str,
    upgrade_service: SubscriptionUpgradeService = Depends(get_upgrade_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> PlanChangePreview:
    """
    Preview subscription downgrade.
    
    Args:
        subscription_id: Subscription identifier
        new_plan_id: Target plan ID
        upgrade_service: Upgrade service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Downgrade preview
    """
    logger.info(f"User {current_user.id} previewing downgrade to plan {new_plan_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = upgrade_service.preview_downgrade(
        subscription_id=subscription_id,
        new_plan_id=new_plan_id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to preview downgrade: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.post(
    "/{subscription_id}/plan-change/apply",
    response_model=PlanChangeConfirmation,
    summary="Apply plan change",
    description="Execute a previewed plan change.",
    responses={
        200: {"description": "Plan change applied successfully"},
        400: {"description": "Invalid request or plan change failed"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def apply_plan_change(
    subscription_id: str,
    payload: PlanChangeRequest,
    upgrade_service: SubscriptionUpgradeService = Depends(get_upgrade_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> PlanChangeConfirmation:
    """
    Apply plan change.
    
    Args:
        subscription_id: Subscription identifier
        payload: Plan change request
        upgrade_service: Upgrade service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Plan change confirmation
    """
    logger.info(f"User {current_user.id} applying plan change for subscription {subscription_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = upgrade_service.apply_plan_change(
        subscription_id=subscription_id,
        data=payload.dict(),
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to apply plan change: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    confirmation = result.unwrap()
    logger.info(f"Successfully applied plan change for subscription {subscription_id}")
    
    return confirmation


@router.post(
    "/{subscription_id}/upgrade",
    response_model=PlanChangeConfirmation,
    summary="Upgrade subscription",
    description="Upgrade subscription to a higher-tier plan.",
    responses={
        200: {"description": "Subscription upgraded successfully"},
        400: {"description": "Invalid upgrade request"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def upgrade_subscription(
    subscription_id: str,
    payload: PlanChangeRequest,
    upgrade_service: SubscriptionUpgradeService = Depends(get_upgrade_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> PlanChangeConfirmation:
    """
    Upgrade subscription.
    
    Args:
        subscription_id: Subscription identifier
        payload: Upgrade request
        upgrade_service: Upgrade service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Upgrade confirmation
    """
    logger.info(f"User {current_user.id} upgrading subscription {subscription_id} to plan {payload.new_plan_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = upgrade_service.upgrade_subscription(
        subscription_id=subscription_id,
        data=payload.dict(),
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to upgrade subscription: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    confirmation = result.unwrap()
    logger.info(f"Successfully upgraded subscription {subscription_id}")
    
    return confirmation


@router.post(
    "/{subscription_id}/downgrade",
    response_model=PlanChangeConfirmation,
    summary="Downgrade subscription",
    description="Downgrade subscription to a lower-tier plan.",
    responses={
        200: {"description": "Subscription downgraded successfully"},
        400: {"description": "Invalid downgrade request"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def downgrade_subscription(
    subscription_id: str,
    payload: PlanChangeRequest,
    upgrade_service: SubscriptionUpgradeService = Depends(get_upgrade_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> PlanChangeConfirmation:
    """
    Downgrade subscription.
    
    Args:
        subscription_id: Subscription identifier
        payload: Downgrade request
        upgrade_service: Upgrade service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Downgrade confirmation
    """
    logger.info(f"User {current_user.id} downgrading subscription {subscription_id} to plan {payload.new_plan_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = upgrade_service.downgrade_subscription(
        subscription_id=subscription_id,
        data=payload.dict(),
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to downgrade subscription: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    confirmation = result.unwrap()
    logger.info(f"Successfully downgraded subscription {subscription_id}")
    
    return confirmation


@router.post(
    "/{subscription_id}/plan-change/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel pending plan change",
    description="Cancel a scheduled plan change before it takes effect.",
    responses={
        204: {"description": "Pending plan change cancelled"},
        400: {"description": "No pending plan change or cannot cancel"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def cancel_pending_plan_change(
    subscription_id: str,
    upgrade_service: SubscriptionUpgradeService = Depends(get_upgrade_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Cancel pending plan change.
    
    Args:
        subscription_id: Subscription identifier
        upgrade_service: Upgrade service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
    """
    logger.info(f"User {current_user.id} cancelling pending plan change for subscription {subscription_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = upgrade_service.cancel_pending_plan_change(subscription_id=subscription_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to cancel pending plan change: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    logger.info(f"Successfully cancelled pending plan change for subscription {subscription_id}")


@router.get(
    "/{subscription_id}/plan-change/history",
    summary="Get plan change history",
    description="Retrieve the history of all plan changes for a subscription.",
    responses={
        200: {"description": "Plan change history"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def get_plan_change_history(
    subscription_id: str,
    upgrade_service: SubscriptionUpgradeService = Depends(get_upgrade_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Get plan change history.
    
    Args:
        subscription_id: Subscription identifier
        upgrade_service: Upgrade service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Plan change history
    """
    logger.info(f"User {current_user.id} retrieving plan change history for subscription {subscription_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = upgrade_service.get_plan_change_history(subscription_id=subscription_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get plan change history: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{subscription_id}/upgrade/recommendations",
    summary="Get upgrade recommendations",
    description="Get personalized plan upgrade recommendations based on usage.",
    responses={
        200: {"description": "Upgrade recommendations"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def get_upgrade_recommendations(
    subscription_id: str,
    upgrade_service: SubscriptionUpgradeService = Depends(get_upgrade_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Get upgrade recommendations.
    
    Args:
        subscription_id: Subscription identifier
        upgrade_service: Upgrade service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Upgrade recommendations
    """
    logger.info(f"User {current_user.id} retrieving upgrade recommendations for subscription {subscription_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = upgrade_service.get_upgrade_recommendations(subscription_id=subscription_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get upgrade recommendations: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{subscription_id}/plan-change/savings",
    summary="Calculate plan change savings",
    description="Calculate potential savings or additional cost for plan changes.",
    responses={
        200: {"description": "Savings calculation"},
        403: {"description": "Access forbidden"},
        404: {"description": "Subscription not found"},
    }
)
async def calculate_plan_change_savings(
    subscription_id: str,
    new_plan_id: str = Query(..., description="Target plan ID for comparison"),
    upgrade_service: SubscriptionUpgradeService = Depends(get_upgrade_service),
    subscription_service = Depends(get_subscription_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Calculate plan change savings.
    
    Args:
        subscription_id: Subscription identifier
        new_plan_id: Target plan ID
        upgrade_service: Upgrade service dependency
        subscription_service: Subscription service dependency
        current_user: Current authenticated user
        
    Returns:
        Savings calculation
    """
    logger.info(f"User {current_user.id} calculating savings for plan change to {new_plan_id}")
    
    # Verify access
    await verify_subscription_access(subscription_id, current_user, subscription_service)
    
    result = upgrade_service.calculate_plan_change_savings(
        subscription_id=subscription_id,
        new_plan_id=new_plan_id
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to calculate savings: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()