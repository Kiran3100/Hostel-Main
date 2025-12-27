"""
Enhanced announcement targeting with advanced audience segmentation capabilities.
"""
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger, log_endpoint_call
from app.core.security import require_permissions
from app.schemas.announcement import (
    TargetingConfig,
    AudienceSelection,
    TargetingSummary,
    BulkTargeting,
    TargetingPreview,
)
from app.services.announcement.announcement_targeting_service import AnnouncementTargetingService
from .deps import get_targeting_service

logger = get_logger(__name__)
router = APIRouter(
    prefix="/announcements/targeting",
    tags=["announcements:targeting"],
    responses={
        404: {"description": "Announcement not found"},
        422: {"description": "Invalid targeting configuration"},
        403: {"description": "Insufficient targeting permissions"}
    }
)


# ---------------------------------------------------------------------------
# Audience Targeting Configuration
# ---------------------------------------------------------------------------

@router.post(
    "/{announcement_id}/apply",
    response_model=TargetingSummary,
    summary="Apply targeting configuration to announcement",
    description="""
    Configure comprehensive audience targeting rules for an announcement.
    
    **Targeting dimensions:**
    - Demographic filters (age, gender, year of study)
    - Academic criteria (program, GPA, enrollment status)
    - Behavioral patterns (engagement history, preferences)
    - Geographic constraints (room blocks, floors, buildings)
    - Temporal factors (timezone, local time preferences)
    
    **Advanced features:**
    - Multi-criteria rule combinations (AND/OR logic)
    - Exclusion lists and negative targeting
    - Dynamic audience updates
    - A/B testing segment allocation
    - Compliance with privacy regulations
    
    **Validation checks:**
    - Minimum audience size requirements
    - Maximum targeting complexity limits
    - Privacy consent verification
    - Data availability confirmation
    """,
    response_description="Targeting summary with audience size and configuration details"
)
@require_permissions(["announcement:target"])
@log_endpoint_call
async def apply_targeting(
    announcement_id: UUID,
    payload: AudienceSelection,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTargetingService = Depends(get_targeting_service),
) -> TargetingSummary:
    """
    Apply sophisticated audience targeting with validation and preview capabilities.
    """
    try:
        logger.info(
            f"Applying targeting to announcement {announcement_id}",
            extra={
                "actor_id": current_user.id,
                "announcement_id": str(announcement_id),
                "targeting_rules_count": len(getattr(payload, 'targeting_rules', [])),
                "audience_type": getattr(payload, 'audience_type', 'unknown')
            }
        )
        
        result = await service.apply_targeting(
            announcement_id=str(announcement_id),
            payload=payload,
            actor_id=current_user.id,
        )
        
        logger.info(
            f"Successfully applied targeting to announcement {announcement_id}",
            extra={
                "actor_id": current_user.id,
                "announcement_id": str(announcement_id),
                "target_audience_size": result.estimated_audience_size,
                "targeting_complexity": result.complexity_score
            }
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid targeting configuration: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for targeting", extra={"actor_id": current_user.id, "announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient targeting permissions")
    except Exception as e:
        logger.error(f"Targeting application failed: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Targeting application failed")


@router.post(
    "/{announcement_id}/preview",
    response_model=TargetingPreview,
    summary="Preview targeting results",
    description="""
    Preview targeting configuration without applying changes.
    
    **Preview capabilities:**
    - Estimated audience size and demographics
    - Sample audience members (anonymized)
    - Targeting rule effectiveness analysis
    - Overlap detection with other announcements
    - Performance predictions based on history
    
    **Analysis features:**
    - Reach vs precision trade-off visualization
    - Historical engagement rate predictions
    - Optimal timing recommendations
    - Content personalization suggestions
    - Compliance and privacy impact assessment
    
    **Optimization suggestions:**
    - Rule simplification opportunities
    - Audience expansion recommendations
    - Performance improvement tips
    - Best practice compliance checks
    """,
    response_description="Detailed preview with audience analysis and optimization suggestions"
)
@require_permissions(["announcement:preview_targeting"])
@log_endpoint_call
async def preview_targeting(
    announcement_id: UUID,
    payload: AudienceSelection,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTargetingService = Depends(get_targeting_service),
) -> TargetingPreview:
    """
    Generate comprehensive targeting preview with analytics and recommendations.
    """
    try:
        logger.debug(
            f"Generating targeting preview for announcement {announcement_id}",
            extra={
                "actor_id": current_user.id,
                "announcement_id": str(announcement_id),
                "preview_mode": True
            }
        )
        
        result = await service.preview_targeting(
            announcement_id=str(announcement_id),
            payload=payload,
            actor_id=current_user.id,
        )
        
        logger.debug(
            f"Generated targeting preview for announcement {announcement_id}",
            extra={
                "actor_id": current_user.id,
                "announcement_id": str(announcement_id),
                "predicted_audience_size": result.estimated_audience_size,
                "confidence_score": result.confidence_score
            }
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid targeting preview request: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"Targeting preview failed: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Targeting preview failed")


# ---------------------------------------------------------------------------
# Targeting Information and Analytics
# ---------------------------------------------------------------------------

@router.get(
    "/{announcement_id}/summary",
    response_model=TargetingSummary,
    summary="Get targeting summary",
    description="""
    Retrieve comprehensive targeting configuration and performance summary.
    
    **Summary includes:**
    - Active targeting rules and criteria
    - Current audience size and composition
    - Historical performance metrics
    - Effectiveness benchmarks
    - Optimization opportunities
    
    **Performance metrics:**
    - Delivery success rates
    - Engagement quality scores
    - Audience satisfaction indicators
    - Cost-effectiveness analysis
    - Compliance adherence status
    
    **Insights and recommendations:**
    - Audience behavior patterns
    - Optimal targeting adjustments
    - Seasonal effectiveness variations
    - Comparative performance analysis
    """,
    response_description="Complete targeting analysis with performance insights"
)
@log_endpoint_call
async def get_targeting_summary(
    announcement_id: UUID,
    include_performance: bool = True,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTargetingService = Depends(get_targeting_service),
) -> TargetingSummary:
    """
    Get comprehensive targeting summary with optional performance analytics.
    """
    try:
        result = await service.compute_summary(
            announcement_id=str(announcement_id),
            actor_id=current_user.id,
            include_performance=include_performance,
        )
        
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Targeting configuration not found")
            
        logger.debug(
            f"Retrieved targeting summary for announcement {announcement_id}",
            extra={
                "actor_id": current_user.id,
                "announcement_id": str(announcement_id),
                "audience_size": result.estimated_audience_size
            }
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Targeting summary retrieval failed: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Summary retrieval failed")


# ---------------------------------------------------------------------------
# Targeting Management Operations
# ---------------------------------------------------------------------------

@router.delete(
    "/{announcement_id}",
    status_code=status.HTTP_200_OK,
    summary="Clear all targeting for announcement",
    description="""
    Remove all targeting configuration and restore default broad audience.
    
    **Clearing effects:**
    - Removes all custom targeting rules
    - Resets to hostel-wide default audience
    - Preserves historical targeting data for analytics
    - Updates audience size estimates immediately
    
    **Safety considerations:**
    - Cannot clear targeting for published announcements
    - Requires explicit confirmation for high-impact changes
    - Maintains audit trail of targeting modifications
    - Validates impact on scheduled deliveries
    
    **Recovery options:**
    - Previous targeting configurations are preserved
    - Quick restore from targeting history
    - Template-based targeting restoration
    - Guided targeting reconfiguration
    """,
    responses={
        200: {"description": "Targeting cleared successfully"},
        409: {"description": "Cannot clear targeting in current state"}
    }
)
@require_permissions(["announcement:clear_targeting"])
@log_endpoint_call
async def clear_targeting(
    announcement_id: UUID,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTargetingService = Depends(get_targeting_service),
) -> Dict[str, str]:
    """
    Clear targeting configuration with safety checks and audit logging.
    """
    try:
        logger.warning(
            f"Clearing targeting for announcement {announcement_id}",
            extra={"actor_id": current_user.id, "announcement_id": str(announcement_id)}
        )
        
        await service.clear_targeting(
            announcement_id=str(announcement_id),
            actor_id=current_user.id,
        )
        
        logger.warning(
            f"Successfully cleared targeting for announcement {announcement_id}",
            extra={"actor_id": current_user.id, "announcement_id": str(announcement_id)}
        )
        
        return {"detail": "Targeting cleared successfully"}
        
    except ValueError as e:
        logger.warning(f"Invalid targeting clear request: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for targeting clear", extra={"actor_id": current_user.id, "announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    except Exception as e:
        logger.error(f"Targeting clear failed: {str(e)}", extra={"announcement_id": str(announcement_id)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Targeting clear failed")


@router.post(
    "/bulk",
    response_model=TargetingSummary,
    summary="Apply bulk targeting rules",
    description="""
    Apply targeting configuration to multiple announcements simultaneously.
    
    **Bulk operations:**
    - Apply same targeting rules to multiple announcements
    - Template-based mass targeting application
    - Conditional targeting based on announcement properties
    - Batch optimization for large-scale campaigns
    
    **Efficiency features:**
    - Single transaction for consistency
    - Parallel processing for performance
    - Rollback capability on partial failures
    - Progress tracking for long operations
    
    **Validation and safety:**
    - Individual announcement state verification
    - Audience overlap analysis and warnings
    - Performance impact estimation
    - Resource usage optimization
    
    **Reporting and tracking:**
    - Detailed operation results per announcement
    - Aggregate performance metrics
    - Failure analysis and remediation guidance
    - Success rate tracking and optimization
    """,
    responses={
        200: {"description": "Bulk targeting applied successfully"},
        207: {"description": "Partial success with detailed results"},
        422: {"description": "Invalid bulk targeting configuration"}
    }
)
@require_permissions(["announcement:bulk_target"])
@log_endpoint_call
async def apply_bulk_targeting(
    payload: BulkTargeting,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTargetingService = Depends(get_targeting_service),
) -> TargetingSummary:
    """
    Apply bulk targeting with comprehensive validation and detailed result tracking.
    """
    try:
        announcement_ids = getattr(payload, 'announcement_ids', [])
        logger.info(
            f"Applying bulk targeting",
            extra={
                "actor_id": current_user.id,
                "announcement_count": len(announcement_ids),
                "targeting_template": getattr(payload, 'targeting_template_id', None)
            }
        )
        
        result = await service.apply_bulk_targeting(
            payload=payload,
            actor_id=current_user.id,
        )
        
        logger.info(
            f"Bulk targeting operation completed",
            extra={
                "actor_id": current_user.id,
                "processed_count": len(announcement_ids),
                "success_rate": result.success_rate if hasattr(result, 'success_rate') else None
            }
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid bulk targeting request: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"Bulk targeting failed: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Bulk targeting failed")