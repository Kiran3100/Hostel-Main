# --- File: C:\Hostel-Main\app\api\v1\subscriptions\dependencies.py ---
"""
Shared dependencies for subscription API endpoints.
"""
from typing import Any, Optional
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthenticationDependency, get_db_session
from app.services.subscription.subscription_service import SubscriptionService
from app.services.subscription.subscription_plan_service import SubscriptionPlanService
from app.services.subscription.subscription_billing_service import SubscriptionBillingService
from app.services.subscription.subscription_invoice_service import SubscriptionInvoiceService
from app.services.subscription.subscription_upgrade_service import SubscriptionUpgradeService
from app.core.logging import get_logger

logger = get_logger(__name__)


async def get_current_user(
    auth: AuthenticationDependency = Depends()
) -> Any:
    """
    Extract and validate current authenticated user.
    
    Args:
        auth: Authentication dependency
        
    Returns:
        Current authenticated user object
        
    Raises:
        HTTPException: If user is not authenticated
    """
    try:
        user = auth.get_current_user()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        return user
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


async def get_subscription_service(
    db: AsyncSession = Depends(get_db_session)
) -> SubscriptionService:
    """
    Get subscription service instance with database session.
    
    Args:
        db: Database session
        
    Returns:
        SubscriptionService instance
    """
    return SubscriptionService(db=db)


async def get_plan_service(
    db: AsyncSession = Depends(get_db_session)
) -> SubscriptionPlanService:
    """
    Get subscription plan service instance.
    
    Args:
        db: Database session
        
    Returns:
        SubscriptionPlanService instance
    """
    return SubscriptionPlanService(db=db)


async def get_billing_service(
    db: AsyncSession = Depends(get_db_session)
) -> SubscriptionBillingService:
    """
    Get billing service instance.
    
    Args:
        db: Database session
        
    Returns:
        SubscriptionBillingService instance
    """
    return SubscriptionBillingService(db=db)


async def get_invoice_service(
    db: AsyncSession = Depends(get_db_session)
) -> SubscriptionInvoiceService:
    """
    Get invoice service instance.
    
    Args:
        db: Database session
        
    Returns:
        SubscriptionInvoiceService instance
    """
    return SubscriptionInvoiceService(db=db)


async def get_upgrade_service(
    db: AsyncSession = Depends(get_db_session)
) -> SubscriptionUpgradeService:
    """
    Get upgrade service instance.
    
    Args:
        db: Database session
        
    Returns:
        SubscriptionUpgradeService instance
    """
    return SubscriptionUpgradeService(db=db)


async def verify_subscription_access(
    subscription_id: str,
    current_user: Any,
    subscription_service: SubscriptionService,
    require_admin: bool = False
) -> Any:
    """
    Verify user has access to specific subscription.
    
    Args:
        subscription_id: Subscription identifier
        current_user: Current authenticated user
        subscription_service: Subscription service instance
        require_admin: Whether admin access is required
        
    Returns:
        Subscription object if access is granted
        
    Raises:
        HTTPException: If access is denied or subscription not found
    """
    result = subscription_service.get_subscription(subscription_id=subscription_id)
    
    if result.is_err():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription {subscription_id} not found"
        )
    
    subscription = result.unwrap()
    
    # Check if user has access to this subscription
    is_admin = getattr(current_user, 'is_admin', False)
    is_owner = getattr(subscription, 'hostel_owner_id', None) == getattr(current_user, 'id', None)
    
    if require_admin and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    if not (is_admin or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this subscription"
        )
    
    return subscription


async def verify_hostel_access(
    hostel_id: str,
    current_user: Any,
    require_admin: bool = False
) -> bool:
    """
    Verify user has access to specific hostel.
    
    Args:
        hostel_id: Hostel identifier
        current_user: Current authenticated user
        require_admin: Whether admin access is required
        
    Returns:
        True if access is granted
        
    Raises:
        HTTPException: If access is denied
    """
    is_admin = getattr(current_user, 'is_admin', False)
    user_hostels = getattr(current_user, 'hostel_ids', [])
    
    if require_admin and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    if not (is_admin or hostel_id in user_hostels):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this hostel"
        )
    
    return True