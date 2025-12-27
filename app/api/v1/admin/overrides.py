from typing import Any, List, Optional, Dict
from functools import lru_cache
from datetime import datetime, timedelta
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator

from app.api import deps
from app.core.exceptions import OverrideNotFoundError, InvalidOverrideError
from app.core.logging import get_logger
from app.core.cache import cache_result, invalidate_cache
from app.core.notifications import send_override_notification
from app.schemas.admin import (
    AdminOverrideRequest,
    OverrideLog,
    OverrideReason,
    OverrideSummary,
    SupervisorOverrideStats,
)
from app.services.admin.admin_override_service import AdminOverrideService

logger = get_logger(__name__)
router = APIRouter(prefix="/overrides", tags=["admin:overrides"])


class OverrideStatus(str, Enum):
    """Enhanced override status enumeration"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class OverrideUrgency(str, Enum):
    """Override urgency levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OverrideFilterParams(BaseModel):
    """Enhanced filtering parameters for overrides"""
    status: Optional[List[OverrideStatus]] = None
    urgency: Optional[List[OverrideUrgency]] = None
    hostel_ids: Optional[List[str]] = None
    admin_ids: Optional[List[str]] = None
    date_range: Optional[str] = Field(None, regex="^(1d|7d|30d|90d|custom)$")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    categories: Optional[List[str]] = None


class EnhancedOverrideRequest(BaseModel):
    """Enhanced override request schema"""
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20, max_length=2000)
    category: str = Field(..., min_length=1, max_length=100)
    urgency: OverrideUrgency = Field(default=OverrideUrgency.MEDIUM)
    hostel_id: str = Field(..., min_length=1)
    target_entity_type: str = Field(..., regex="^(booking|payment|guest|room|policy)$")
    target_entity_id: str = Field(..., min_length=1)
    requested_change: Dict[str, Any] = Field(...)
    business_justification: str = Field(..., min_length=50, max_length=1000)
    risk_assessment: Optional[str] = Field(None, max_length=500)
    expected_impact: Optional[str] = Field(None, max_length=500)
    expiry_hours: int = Field(default=24, ge=1, le=168)  # 1 hour to 7 days
    notify_stakeholders: bool = Field(default=True)
    
    @validator('requested_change')
    def validate_requested_change(cls, v):
        """Validate the requested change structure"""
        if not isinstance(v, dict) or not v:
            raise ValueError("Requested change must be a non-empty dictionary")
        required_fields = ['field', 'current_value', 'new_value']
        if not all(field in v for field in required_fields):
            raise ValueError(f"Requested change must contain: {', '.join(required_fields)}")
        return v


class OverrideApprovalRequest(BaseModel):
    """Schema for override approval"""
    approval_comments: str = Field(..., min_length=10, max_length=1000)
    conditions: Optional[List[str]] = Field(None, max_items=10)
    expiry_override: Optional[datetime] = None
    notify_requestor: bool = Field(default=True)
    auto_apply: bool = Field(default=False)


class OverrideRejectionRequest(BaseModel):
    """Schema for override rejection"""
    rejection_reason: str = Field(..., min_length=10, max_length=1000)
    alternative_suggestions: Optional[str] = Field(None, max_length=500)
    allow_resubmission: bool = Field(default=True)
    notify_requestor: bool = Field(default=True)


# Enhanced dependency injection
@lru_cache()
def get_override_service(
    db: Session = Depends(deps.get_db),
) -> AdminOverrideService:
    """Optimized override service dependency with caching."""
    return AdminOverrideService(db=db)


@router.post(
    "",
    response_model=OverrideLog,
    status_code=status.HTTP_201_CREATED,
    summary="Create comprehensive admin override request",
    description="Create detailed override request with enhanced validation and workflow",
)
async def create_override(
    payload: EnhancedOverrideRequest,
    background_tasks: BackgroundTasks,
    auto_escalate: bool = Query(False, description="Auto-escalate if urgency is high/critical"),
    validate_business_rules: bool = Query(True, description="Validate against business rules"),
    current_admin=Depends(deps.get_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> OverrideLog:
    """
    Create comprehensive override request with enhanced validation and workflow automation.
    """
    try:
        # Validate admin has permission to create overrides for this hostel
        can_override = await service.validate_override_permission(
            admin_id=current_admin.id,
            hostel_id=payload.hostel_id,
            category=payload.category
        )
        if not can_override:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin does not have permission to create overrides for this hostel/category"
            )
        
        # Validate business rules if requested
        if validate_business_rules:
            rule_violations = await service.validate_business_rules(payload)
            if rule_violations:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Business rule violations: {', '.join(rule_violations)}"
                )
        
        override = await service.create_override(
            payload=payload,
            created_by=current_admin.id,
            auto_escalate=auto_escalate
        )
        
        # Schedule notifications
        if payload.notify_stakeholders:
            background_tasks.add_task(
                send_override_notification,
                override_id=override.id,
                notification_type="created"
            )
        
        # Auto-escalate for high urgency
        if auto_escalate and payload.urgency in [OverrideUrgency.HIGH, OverrideUrgency.CRITICAL]:
            background_tasks.add_task(
                service.escalate_override,
                override_id=override.id,
                urgency=payload.urgency
            )
        
        logger.info(f"Override {override.id} created by admin {current_admin.id} for hostel {payload.hostel_id}")
        return override
        
    except HTTPException:
        raise
    except InvalidOverrideError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid override request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to create override: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create override request"
        )


@router.get(
    "",
    response_model=List[OverrideLog],
    summary="List overrides with advanced filtering",
    description="Retrieve overrides with comprehensive filtering and pagination",
)
@cache_result(expire_time=180)  # Cache for 3 minutes
async def list_overrides(
    status_filter: Optional[str] = Query(None, regex="^(pending|approved|rejected|expired|cancelled)$"),
    urgency_filter: Optional[str] = Query(None, regex="^(low|medium|high|critical)$"),
    hostel_id: Optional[str] = Query(None, description="Filter by hostel ID"),
    category: Optional[str] = Query(None, description="Filter by override category"),
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    include_metadata: bool = Query(True, description="Include detailed metadata"),
    current_admin=Depends(deps.get_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> List[OverrideLog]:
    """
    List overrides with advanced filtering, pagination, and sorting.
    """
    try:
        filters = OverrideFilterParams(
            status=[OverrideStatus(status_filter)] if status_filter else None,
            urgency=[OverrideUrgency(urgency_filter)] if urgency_filter else None,
            hostel_ids=[hostel_id] if hostel_id else None,
            categories=[category] if category else None,
            date_range=f"{days}d"
        )
        
        overrides = await service.list_overrides_with_filters(
            filters=filters,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            include_metadata=include_metadata,
            requesting_admin_id=current_admin.id
        )
        
        return overrides
        
    except Exception as e:
        logger.error(f"Failed to list overrides: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve overrides"
        )


@router.get(
    "/{override_id}",
    response_model=OverrideLog,
    summary="Get detailed override information",
    description="Retrieve comprehensive override details with audit trail",
)
async def get_override_detail(
    override_id: str,
    include_audit_trail: bool = Query(True, description="Include detailed audit trail"),
    include_related_overrides: bool = Query(False, description="Include related/similar overrides"),
    current_admin=Depends(deps.get_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> OverrideLog:
    """
    Get comprehensive override details with enhanced information.
    """
    try:
        override = await service.get_override_by_id(
            override_id=override_id,
            include_audit_trail=include_audit_trail,
            include_related_overrides=include_related_overrides,
            requesting_admin_id=current_admin.id
        )
        
        if not override:
            raise OverrideNotFoundError(f"Override {override_id} not found")
        
        # Verify admin has permission to view this override
        can_view = await service.validate_view_permission(
            admin_id=current_admin.id,
            override=override
        )
        if not can_view:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin does not have permission to view this override"
            )
        
        return override
        
    except OverrideNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Override {override_id} not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get override {override_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve override details"
        )


@router.post(
    "/{override_id}/approve",
    response_model=OverrideLog,
    summary="Approve override with conditions",
    description="Approve override request with optional conditions and automatic application",
)
async def approve_override(
    override_id: str,
    approval: OverrideApprovalRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> OverrideLog:
    """
    Approve override with comprehensive validation and optional automatic application.
    """
    try:
        # Verify override exists and is in pending state
        override = await service.get_override_by_id(override_id)
        if not override:
            raise OverrideNotFoundError(f"Override {override_id} not found")
        
        if override.status != OverrideStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Override is not in pending state (current: {override.status})"
            )
        
        approved_override = await service.approve_override(
            override_id=override_id,
            approval=approval,
            approved_by=current_admin.id
        )
        
        # Invalidate caches
        await invalidate_cache(f"overrides:pending")
        await invalidate_cache(f"overrides:hostel:{override.hostel_id}")
        
        # Schedule notifications and automatic application
        if approval.notify_requestor:
            background_tasks.add_task(
                send_override_notification,
                override_id=override_id,
                notification_type="approved"
            )
        
        if approval.auto_apply:
            background_tasks.add_task(
                service.apply_override,
                override_id=override_id,
                applied_by=current_admin.id
            )
        
        logger.info(f"Override {override_id} approved by {current_admin.id}")
        return approved_override
        
    except (OverrideNotFoundError, HTTPException):
        raise
    except Exception as e:
        logger.error(f"Failed to approve override {override_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve override"
        )


@router.post(
    "/{override_id}/reject",
    response_model=OverrideLog,
    summary="Reject override with detailed reasoning",
    description="Reject override request with comprehensive feedback and alternative suggestions",
)
async def reject_override(
    override_id: str,
    rejection: OverrideRejectionRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> OverrideLog:
    """
    Reject override with comprehensive feedback and alternative suggestions.
    """
    try:
        # Verify override exists and is in pending state
        override = await service.get_override_by_id(override_id)
        if not override:
            raise OverrideNotFoundError(f"Override {override_id} not found")
        
        if override.status != OverrideStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Override is not in pending state (current: {override.status})"
            )
        
        rejected_override = await service.reject_override(
            override_id=override_id,
            rejection=rejection,
            rejected_by=current_admin.id
        )
        
        # Invalidate caches
        await invalidate_cache(f"overrides:pending")
        await invalidate_cache(f"overrides:hostel:{override.hostel_id}")
        
        # Schedule notifications
        if rejection.notify_requestor:
            background_tasks.add_task(
                send_override_notification,
                override_id=override_id,
                notification_type="rejected",
                extra_data={
                    "rejection_reason": rejection.rejection_reason,
                    "alternative_suggestions": rejection.alternative_suggestions,
                    "allow_resubmission": rejection.allow_resubmission
                }
            )
        
        logger.warning(f"Override {override_id} rejected by {current_admin.id}. Reason: {rejection.rejection_reason}")
        return rejected_override
        
    except (OverrideNotFoundError, HTTPException):
        raise
    except Exception as e:
        logger.error(f"Failed to reject override {override_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject override"
        )


@router.get(
    "/pending",
    response_model=List[OverrideLog],
    summary="List pending overrides with prioritization",
    description="Retrieve pending overrides sorted by urgency and priority",
)
@cache_result(expire_time=60)  # Cache for 1 minute (more frequent updates for pending)
async def list_pending_overrides(
    urgency_filter: Optional[str] = Query(None, regex="^(low|medium|high|critical)$"),
    hostel_id: Optional[str] = Query(None, description="Filter by hostel ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sort_by_priority: bool = Query(True, description="Sort by priority (urgency + age)"),
    include_expired: bool = Query(False, description="Include expired pending overrides"),
    limit: int = Query(100, ge=1, le=200, description="Maximum results"),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> List[OverrideLog]:
    """
    Get pending overrides with intelligent prioritization and filtering.
    """
    try:
        pending_overrides = await service.get_pending_overrides(
            urgency_filter=OverrideUrgency(urgency_filter) if urgency_filter else None,
            hostel_id=hostel_id,
            category=category,
            sort_by_priority=sort_by_priority,
            include_expired=include_expired,
            limit=limit
        )
        
        return pending_overrides
        
    except Exception as e:
        logger.error(f"Failed to get pending overrides: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pending overrides"
        )


@router.get(
    "/summary",
    response_model=OverrideSummary,
    summary="Get comprehensive override summary",
    description="Retrieve detailed override summary with trends and analytics",
)
@cache_result(expire_time=600)  # Cache for 10 minutes
async def get_override_summary(
    hostel_id: Optional[str] = Query(None, description="Filter by hostel ID"),
    days: int = Query(30, ge=1, le=365, description="Summary period in days"),
    breakdown_by: str = Query("category", regex="^(category|urgency|status|admin)$", description="Breakdown dimension"),
    include_trends: bool = Query(True, description="Include trend analysis"),
    include_comparisons: bool = Query(True, description="Include period comparisons"),
    current_admin=Depends(deps.get_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> OverrideSummary:
    """
    Get comprehensive override summary with trends and analytics.
    """
    try:
        summary = await service.get_override_summary(
            hostel_id=hostel_id,
            days=days,
            breakdown_by=breakdown_by,
            include_trends=include_trends,
            include_comparisons=include_comparisons,
            requesting_admin_id=current_admin.id
        )
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get override summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve override summary"
        )


@router.get(
    "/supervisors/{supervisor_id}/stats",
    response_model=SupervisorOverrideStats,
    summary="Get supervisor override statistics",
    description="Retrieve detailed override statistics for specific supervisor",
)
@cache_result(expire_time=300)  # Cache for 5 minutes
async def get_supervisor_override_stats(
    supervisor_id: str,
    period_days: int = Query(90, ge=1, le=365, description="Statistics period in days"),
    include_team_stats: bool = Query(True, description="Include team member statistics"),
    include_trends: bool = Query(True, description="Include approval trends"),
    current_admin=Depends(deps.get_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> SupervisorOverrideStats:
    """
    Get comprehensive supervisor override statistics with team analytics.
    """
    try:
        # Verify admin has permission to view supervisor stats
        can_view = await service.validate_supervisor_view_permission(
            admin_id=current_admin.id,
            supervisor_id=supervisor_id
        )
        if not can_view:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin does not have permission to view this supervisor's statistics"
            )
        
        stats = await service.get_supervisor_override_stats(
            supervisor_id=supervisor_id,
            period_days=period_days,
            include_team_stats=include_team_stats,
            include_trends=include_trends
        )
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get supervisor stats for {supervisor_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve supervisor override statistics"
        )


@router.get(
    "/reasons",
    response_model=List[OverrideReason],
    summary="List standard override reasons",
    description="Retrieve standard override reasons with usage statistics",
)
@cache_result(expire_time=3600)  # Cache for 1 hour
async def list_override_reasons(
    category: Optional[str] = Query(None, description="Filter by category"),
    include_usage_stats: bool = Query(True, description="Include usage statistics"),
    include_inactive: bool = Query(False, description="Include inactive reasons"),
    current_admin=Depends(deps.get_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> List[OverrideReason]:
    """
    Get standard override reasons with usage statistics and categorization.
    """
    try:
        reasons = await service.get_standard_reasons(
            category=category,
            include_usage_stats=include_usage_stats,
            include_inactive=include_inactive
        )
        
        return reasons
        
    except Exception as e:
        logger.error(f"Failed to get override reasons: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve override reasons"
        )


@router.post(
    "/{override_id}/cancel",
    response_model=OverrideLog,
    summary="Cancel pending override",
    description="Cancel a pending override request with reason",
)
async def cancel_override(
    override_id: str,
    cancellation_reason: str = Query(..., min_length=10, max_length=500),
    notify_stakeholders: bool = Query(True, description="Notify relevant stakeholders"),
    background_tasks: BackgroundTasks,
    current_admin=Depends(deps.get_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> OverrideLog:
    """
    Cancel pending override with proper validation and notifications.
    """
    try:
        # Verify override exists and admin can cancel it
        override = await service.get_override_by_id(override_id)
        if not override:
            raise OverrideNotFoundError(f"Override {override_id} not found")
        
        can_cancel = await service.validate_cancel_permission(
            admin_id=current_admin.id,
            override=override
        )
        if not can_cancel:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin does not have permission to cancel this override"
            )
        
        cancelled_override = await service.cancel_override(
            override_id=override_id,
            cancellation_reason=cancellation_reason,
            cancelled_by=current_admin.id
        )
        
        # Invalidate caches
        await invalidate_cache(f"overrides:pending")
        await invalidate_cache(f"overrides:hostel:{override.hostel_id}")
        
        # Schedule notifications
        if notify_stakeholders:
            background_tasks.add_task(
                send_override_notification,
                override_id=override_id,
                notification_type="cancelled",
                extra_data={"cancellation_reason": cancellation_reason}
            )
        
        logger.info(f"Override {override_id} cancelled by {current_admin.id}")
        return cancelled_override
        
    except (OverrideNotFoundError, HTTPException):
        raise
    except Exception as e:
        logger.error(f"Failed to cancel override {override_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel override"
        )


@router.get(
    "/analytics/trends",
    summary="Get override trend analytics",
    description="Retrieve advanced analytics and trends for overrides",
)
@cache_result(expire_time=1800)  # Cache for 30 minutes
async def get_override_trends(
    period_days: int = Query(90, ge=7, le=365, description="Analysis period in days"),
    granularity: str = Query("daily", regex="^(hourly|daily|weekly|monthly)$", description="Data granularity"),
    metrics: str = Query("count,approval_rate,avg_resolution_time", description="Comma-separated metrics"),
    hostel_ids: Optional[str] = Query(None, description="Comma-separated hostel IDs"),
    categories: Optional[str] = Query(None, description="Comma-separated categories"),
    current_admin=Depends(deps.get_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> Dict[str, Any]:
    """
    Get advanced override trend analytics with customizable metrics and granularity.
    """
    try:
        # Parse parameters
        metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
        hostel_id_list = None
        category_list = None
        
        if hostel_ids:
            hostel_id_list = [h.strip() for h in hostel_ids.split(",") if h.strip()]
        if categories:
            category_list = [c.strip() for c in categories.split(",") if c.strip()]
        
        trends = await service.get_override_trends(
            period_days=period_days,
            granularity=granularity,
            metrics=metric_list,
            hostel_ids=hostel_id_list,
            categories=category_list,
            requesting_admin_id=current_admin.id
        )
        
        return trends
        
    except Exception as e:
        logger.error(f"Failed to get override trends: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve override trends"
        )