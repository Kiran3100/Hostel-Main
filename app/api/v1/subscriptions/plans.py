# --- File: C:\Hostel-Main\app\api\v1\subscriptions\plans.py ---
"""
Subscription plan management endpoints.

This module handles operations related to subscription plans including
CRUD operations, feature comparisons, and plan recommendations.
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.subscription.subscription_plan_service import SubscriptionPlanService
from app.schemas.subscription import (
    PlanResponse,
    PlanSummary,
    PlanFeatures,
    PlanComparison,
    PlanCreate,
    PlanUpdate,
)
from .dependencies import get_plan_service, get_current_user

logger = get_logger(__name__)

router = APIRouter(
    prefix="/subscriptions/plans",
    tags=["Subscriptions - Plans"],
)


class PlanComparisonRequest(BaseModel):
    """Request body for plan comparison."""
    plan_ids: List[str] = Field(..., min_items=2, max_items=5, description="List of plan IDs to compare")


@router.post(
    "",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create subscription plan",
    description="Create a new subscription plan (admin only).",
    responses={
        201: {"description": "Plan created successfully"},
        400: {"description": "Invalid plan data"},
        403: {"description": "Admin access required"},
        409: {"description": "Plan already exists"},
    }
)
async def create_plan(
    payload: PlanCreate,
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
    current_user: Any = Depends(get_current_user),
) -> PlanResponse:
    """
    Create a new subscription plan.
    
    Args:
        payload: Plan creation data
        plan_service: Plan service dependency
        current_user: Current authenticated user
        
    Returns:
        Created plan details
        
    Raises:
        HTTPException: If user is not admin or creation fails
    """
    logger.info(f"User {current_user.id} creating new plan: {payload.name}")
    
    # Verify admin access
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to create plans"
        )
    
    result = plan_service.create_plan(data=payload)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to create plan: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    plan = result.unwrap()
    logger.info(f"Successfully created plan {plan.id}: {plan.name}")
    
    return plan


@router.get(
    "",
    response_model=List[PlanSummary],
    summary="List subscription plans",
    description="Retrieve all available subscription plans with optional filtering.",
    responses={
        200: {"description": "List of subscription plans"},
    }
)
async def list_plans(
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
    current_user: Any = Depends(get_current_user),
    active_only: bool = Query(True, description="Show only active plans"),
    public_only: bool = Query(False, description="Show only public plans"),
) -> List[PlanSummary]:
    """
    List all subscription plans.
    
    Args:
        plan_service: Plan service dependency
        current_user: Current authenticated user
        active_only: Filter for active plans only
        public_only: Filter for public plans only
        
    Returns:
        List of plan summaries
    """
    logger.info(f"User {current_user.id} listing plans (active={active_only}, public={public_only})")
    
    filters = {
        "active_only": active_only,
        "public_only": public_only,
    }
    
    result = plan_service.list_plans(filters=filters)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to list plans: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="Get plan details",
    description="Retrieve detailed information about a specific plan.",
    responses={
        200: {"description": "Plan details"},
        404: {"description": "Plan not found"},
    }
)
async def get_plan(
    plan_id: str,
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
    current_user: Any = Depends(get_current_user),
) -> PlanResponse:
    """
    Get detailed plan information.
    
    Args:
        plan_id: Plan identifier
        plan_service: Plan service dependency
        current_user: Current authenticated user
        
    Returns:
        Plan details
    """
    logger.info(f"User {current_user.id} retrieving plan {plan_id}")
    
    result = plan_service.get_plan(plan_id=plan_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get plan {plan_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found"
        )
    
    return result.unwrap()


@router.patch(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="Update plan",
    description="Update plan details (admin only).",
    responses={
        200: {"description": "Plan updated successfully"},
        400: {"description": "Invalid update data"},
        403: {"description": "Admin access required"},
        404: {"description": "Plan not found"},
    }
)
async def update_plan(
    plan_id: str,
    payload: PlanUpdate,
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
    current_user: Any = Depends(get_current_user),
) -> PlanResponse:
    """
    Update plan details.
    
    Args:
        plan_id: Plan identifier
        payload: Update data
        plan_service: Plan service dependency
        current_user: Current authenticated user
        
    Returns:
        Updated plan details
    """
    logger.info(f"User {current_user.id} updating plan {plan_id}")
    
    # Verify admin access
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to update plans"
        )
    
    result = plan_service.update_plan(plan_id=plan_id, data=payload)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to update plan {plan_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    updated = result.unwrap()
    logger.info(f"Successfully updated plan {plan_id}")
    
    return updated


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete plan",
    description="Delete a plan (admin only). Plans with active subscriptions cannot be deleted.",
    responses={
        204: {"description": "Plan deleted successfully"},
        400: {"description": "Cannot delete plan with active subscriptions"},
        403: {"description": "Admin access required"},
        404: {"description": "Plan not found"},
    }
)
async def delete_plan(
    plan_id: str,
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Delete a plan.
    
    Args:
        plan_id: Plan identifier
        plan_service: Plan service dependency
        current_user: Current authenticated user
    """
    logger.info(f"User {current_user.id} deleting plan {plan_id}")
    
    # Verify admin access
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to delete plans"
        )
    
    result = plan_service.delete_plan(plan_id=plan_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to delete plan {plan_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    logger.info(f"Successfully deleted plan {plan_id}")


@router.post(
    "/{plan_id}/archive",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive plan",
    description="Archive a plan (admin only). Archived plans are hidden but data is preserved.",
    responses={
        204: {"description": "Plan archived successfully"},
        403: {"description": "Admin access required"},
        404: {"description": "Plan not found"},
    }
)
async def archive_plan(
    plan_id: str,
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Archive a plan.
    
    Args:
        plan_id: Plan identifier
        plan_service: Plan service dependency
        current_user: Current authenticated user
    """
    logger.info(f"User {current_user.id} archiving plan {plan_id}")
    
    # Verify admin access
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to archive plans"
        )
    
    result = plan_service.archive_plan(plan_id=plan_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to archive plan {plan_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    logger.info(f"Successfully archived plan {plan_id}")


@router.get(
    "/by-name/{name}",
    response_model=PlanResponse,
    summary="Get plan by name",
    description="Retrieve a plan by its unique name.",
    responses={
        200: {"description": "Plan details"},
        404: {"description": "Plan not found"},
    }
)
async def get_plan_by_name(
    name: str,
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
    current_user: Any = Depends(get_current_user),
) -> PlanResponse:
    """
    Get plan by name.
    
    Args:
        name: Plan name
        plan_service: Plan service dependency
        current_user: Current authenticated user
        
    Returns:
        Plan details
    """
    logger.info(f"User {current_user.id} retrieving plan by name: {name}")
    
    result = plan_service.get_plan_by_name(name=name)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get plan by name {name}: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{name}' not found"
        )
    
    return result.unwrap()


@router.get(
    "/search",
    response_model=List[PlanSummary],
    summary="Search plans",
    description="Search plans by name, description, or features.",
    responses={
        200: {"description": "Search results"},
    }
)
async def search_plans(
    q: Optional[str] = Query(None, min_length=1, description="Search query"),
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
    current_user: Any = Depends(get_current_user),
) -> List[PlanSummary]:
    """
    Search plans.
    
    Args:
        q: Search query
        plan_service: Plan service dependency
        current_user: Current authenticated user
        
    Returns:
        List of matching plans
    """
    logger.info(f"User {current_user.id} searching plans with query: {q}")
    
    result = plan_service.search_plans(filters={"query": q})
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to search plans: {error}")
        return []
    
    return result.unwrap()


@router.get(
    "/recommended",
    response_model=List[PlanSummary],
    summary="Get recommended plans",
    description="Get plan recommendations based on hostel size and usage patterns.",
    responses={
        200: {"description": "Recommended plans"},
    }
)
async def get_recommended_plans(
    hostel_id: Optional[str] = Query(None, description="Hostel ID for personalized recommendations"),
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
    current_user: Any = Depends(get_current_user),
) -> List[PlanSummary]:
    """
    Get recommended plans.
    
    Args:
        hostel_id: Optional hostel ID for personalized recommendations
        plan_service: Plan service dependency
        current_user: Current authenticated user
        
    Returns:
        List of recommended plans
    """
    logger.info(f"User {current_user.id} getting recommended plans for hostel: {hostel_id}")
    
    context = {"hostel_id": hostel_id} if hostel_id else {}
    result = plan_service.get_recommended_plans(context=context)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get recommended plans: {error}")
        return []
    
    return result.unwrap()


@router.get(
    "/{plan_id}/features",
    response_model=PlanFeatures,
    summary="Get plan features",
    description="Retrieve detailed feature list for a plan.",
    responses={
        200: {"description": "Plan features"},
        404: {"description": "Plan not found"},
    }
)
async def get_plan_features(
    plan_id: str,
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
    current_user: Any = Depends(get_current_user),
) -> PlanFeatures:
    """
    Get plan features.
    
    Args:
        plan_id: Plan identifier
        plan_service: Plan service dependency
        current_user: Current authenticated user
        
    Returns:
        Plan features
    """
    logger.info(f"User {current_user.id} retrieving features for plan {plan_id}")
    
    result = plan_service.get_plan_features(plan_id=plan_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get plan features: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found"
        )
    
    return result.unwrap()


@router.post(
    "/compare",
    response_model=PlanComparison,
    summary="Compare plans",
    description="Compare features and pricing of multiple plans side by side.",
    responses={
        200: {"description": "Plan comparison"},
        400: {"description": "Invalid plan IDs or comparison request"},
    }
)
async def compare_plans(
    request: PlanComparisonRequest,
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
    current_user: Any = Depends(get_current_user),
) -> PlanComparison:
    """
    Compare multiple plans.
    
    Args:
        request: Comparison request with plan IDs
        plan_service: Plan service dependency
        current_user: Current authenticated user
        
    Returns:
        Plan comparison data
    """
    logger.info(f"User {current_user.id} comparing plans: {request.plan_ids}")
    
    result = plan_service.compare_plans(plan_ids=request.plan_ids)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to compare plans: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/by-feature/{feature_key}",
    response_model=List[PlanSummary],
    summary="Get plans with feature",
    description="Get all plans that include a specific feature.",
    responses={
        200: {"description": "Plans with the specified feature"},
    }
)
async def get_plans_with_feature(
    feature_key: str,
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
    current_user: Any = Depends(get_current_user),
) -> List[PlanSummary]:
    """
    Get plans that include a specific feature.
    
    Args:
        feature_key: Feature key to search for
        plan_service: Plan service dependency
        current_user: Current authenticated user
        
    Returns:
        List of plans with the feature
    """
    logger.info(f"User {current_user.id} searching plans with feature: {feature_key}")
    
    result = plan_service.get_plans_with_feature(feature_key=feature_key)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get plans with feature: {error}")
        return []
    
    return result.unwrap()


@router.get(
    "/popular",
    response_model=List[PlanSummary],
    summary="Get popular plans",
    description="Get the most popular plans based on subscription count.",
    responses={
        200: {"description": "Most popular plans"},
    }
)
async def get_most_popular_plans(
    limit: int = Query(5, ge=1, le=10, description="Number of plans to return"),
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
    current_user: Any = Depends(get_current_user),
) -> List[PlanSummary]:
    """
    Get most popular plans.
    
    Args:
        limit: Number of plans to return
        plan_service: Plan service dependency
        current_user: Current authenticated user
        
    Returns:
        List of popular plans
    """
    logger.info(f"User {current_user.id} retrieving top {limit} popular plans")
    
    result = plan_service.get_most_popular_plans(limit=limit)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get popular plans: {error}")
        return []
    
    return result.unwrap()


@router.get(
    "/{plan_id}/stats",
    summary="Get plan statistics",
    description="Get usage statistics and analytics for a plan (admin only).",
    responses={
        200: {"description": "Plan statistics"},
        403: {"description": "Admin access required"},
        404: {"description": "Plan not found"},
    }
)
async def get_plan_stats(
    plan_id: str,
    plan_service: SubscriptionPlanService = Depends(get_plan_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Get plan statistics.
    
    Args:
        plan_id: Plan identifier
        plan_service: Plan service dependency
        current_user: Current authenticated user
        
    Returns:
        Plan statistics and analytics
    """
    logger.info(f"User {current_user.id} retrieving stats for plan {plan_id}")
    
    # Verify admin access
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to view plan statistics"
        )
    
    result = plan_service.get_plan_statistics(plan_id=plan_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to get plan stats: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found"
        )
    
    return result.unwrap()