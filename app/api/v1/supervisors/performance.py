"""
Supervisor Performance Management

Handles performance metrics, reviews, reports, and analytics for supervisors.
Includes trend analysis, ratings, and export functionality.
"""

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, Field, validator

from app.core.dependencies import AuthenticationDependency
from app.services.supervisor.supervisor_performance_service import SupervisorPerformanceService
from app.schemas.supervisor import (
    PerformanceReviewCreate,
    PerformanceReviewUpdate,
    SupervisorPerformanceMetrics,
    SupervisorPerformanceReport,
    SupervisorPerformanceTrends,
    PerformanceReview,
    PerformanceRating,
)

# Router configuration
router = APIRouter(
    prefix="",
    tags=["Supervisors - Performance"],
)


# ============================================================================
# Dependency Injection
# ============================================================================

def get_performance_service() -> SupervisorPerformanceService:
    """
    Dependency provider for SupervisorPerformanceService.
    
    Wire this to your DI container or service factory.
    """
    raise NotImplementedError(
        "SupervisorPerformanceService dependency must be implemented."
    )


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """Extract and validate current authenticated user."""
    user = auth.get_current_user()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user


# ============================================================================
# Request/Response Models
# ============================================================================

class PerformancePeriod(BaseModel):
    """Performance evaluation period"""
    start_date: datetime = Field(..., description="Period start date")
    end_date: datetime = Field(..., description="Period end date")
    
    @validator('end_date')
    def end_after_start(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v
    
    @validator('start_date', 'end_date')
    def not_future(cls, v):
        if v > datetime.utcnow():
            raise ValueError('Date cannot be in the future')
        return v


class PerformanceReviewListResponse(BaseModel):
    """Response for performance review listing"""
    total: int = Field(..., description="Total number of reviews")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")
    reviews: List[PerformanceReview] = Field(..., description="Review items")


# ============================================================================
# API Endpoints
# ============================================================================

@router.get(
    "/{supervisor_id}/performance/metrics",
    response_model=SupervisorPerformanceMetrics,
    summary="Get performance metrics",
    description="""
    Get detailed performance metrics for a supervisor over a specified period.
    
    **Metrics Include**:
    - **Activity Metrics**: Check-in rates, task completion, response times
    - **Quality Metrics**: Incident resolution, student satisfaction, compliance
    - **Efficiency Metrics**: Average task duration, productivity score
    - **Engagement Metrics**: Student interactions, communication frequency
    - **Attendance Metrics**: On-time percentage, shift coverage
    
    **Calculation**:
    - Real-time calculation from activity logs
    - Weighted scoring based on importance
    - Benchmarked against peers and standards
    
    **Use Cases**:
    - Performance dashboards
    - Review preparation
    - Trend analysis
    - Comparative analytics
    """,
    responses={
        200: {"description": "Metrics retrieved successfully"},
        400: {"description": "Invalid date range"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_performance_metrics(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    period: PerformancePeriod = Depends(),
    performance_service: SupervisorPerformanceService = Depends(get_performance_service),
    current_user: Any = Depends(get_current_user),
    include_benchmarks: bool = Query(True, description="Include peer benchmarks"),
) -> SupervisorPerformanceMetrics:
    """Get comprehensive performance metrics for specified period."""
    result = performance_service.get_performance_metrics(
        supervisor_id=supervisor_id,
        period_start=period.start_date.isoformat(),
        period_end=period.end_date.isoformat(),
        include_benchmarks=include_benchmarks,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{supervisor_id}/performance/report",
    response_model=SupervisorPerformanceReport,
    summary="Get performance report",
    description="""
    Generate comprehensive performance report for a supervisor.
    
    **Report Sections**:
    - Executive summary
    - Detailed metrics breakdown
    - Strengths and achievements
    - Areas for improvement
    - Comparative analysis
    - Historical trends
    - Recommendations
    
    **Report Formats**:
    - Structured JSON (default)
    - PDF export (via export endpoint)
    - Excel export (via export endpoint)
    
    **Use Cases**:
    - Formal performance reviews
    - Annual evaluations
    - Promotion considerations
    - Performance improvement plans
    """,
    responses={
        200: {"description": "Report generated successfully"},
        400: {"description": "Invalid date range"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_performance_report(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    period: PerformancePeriod = Depends(),
    performance_service: SupervisorPerformanceService = Depends(get_performance_service),
    current_user: Any = Depends(get_current_user),
    include_recommendations: bool = Query(True, description="Include AI-generated recommendations"),
) -> SupervisorPerformanceReport:
    """Generate comprehensive performance report."""
    result = performance_service.get_performance_report(
        supervisor_id=supervisor_id,
        period_start=period.start_date.isoformat(),
        period_end=period.end_date.isoformat(),
        include_recommendations=include_recommendations,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{supervisor_id}/performance/report/export",
    summary="Export performance report",
    description="""
    Export performance report in various formats.
    
    **Supported Formats**:
    - **PDF**: Professional formatted report with charts
    - **Excel**: Detailed data with multiple sheets
    - **CSV**: Raw metrics data for analysis
    - **JSON**: Structured data for integration
    
    **Export Features**:
    - Company branding and logo
    - Charts and visualizations
    - Comparative tables
    - Historical data
    - Digital signatures (PDF)
    
    **Response**:
    - Direct file download
    - Pre-signed S3 URL for larger files
    - Metadata for async generation
    
    **Processing**:
    - Small reports: Synchronous
    - Large reports: Async with notification
    """,
    responses={
        200: {
            "description": "Report exported successfully",
            "content": {
                "application/pdf": {},
                "application/vnd.ms-excel": {},
                "text/csv": {},
                "application/json": {},
            }
        },
        202: {"description": "Export queued (async processing)"},
        400: {"description": "Invalid format or date range"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def export_performance_report(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    period: PerformancePeriod = Depends(),
    format: str = Query("pdf", regex="^(pdf|excel|csv|json)$", description="Export format"),
    performance_service: SupervisorPerformanceService = Depends(get_performance_service),
    current_user: Any = Depends(get_current_user),
    async_export: bool = Query(False, description="Process export asynchronously"),
) -> Response:
    """Export performance report in specified format."""
    result = performance_service.export_performance_report(
        supervisor_id=supervisor_id,
        period_start=period.start_date.isoformat(),
        period_end=period.end_date.isoformat(),
        format=format,
        async_export=async_export,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    export_data = result.unwrap()
    
    # Handle async export
    if async_export:
        return Response(
            content=export_data.get("message", "Export queued"),
            status_code=status.HTTP_202_ACCEPTED,
            media_type="application/json"
        )
    
    # Return file for sync export
    content_types = {
        "pdf": "application/pdf",
        "excel": "application/vnd.ms-excel",
        "csv": "text/csv",
        "json": "application/json",
    }
    
    return Response(
        content=export_data.get("content", b""),
        media_type=content_types.get(format, "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="performance_report_{supervisor_id}.{format}"'
        }
    )


@router.post(
    "/{supervisor_id}/performance/reviews",
    response_model=PerformanceReview,
    status_code=status.HTTP_201_CREATED,
    summary="Create performance review",
    description="""
    Create a new formal performance review for a supervisor.
    
    **Review Components**:
    - Review period and type
    - Overall rating
    - Category-specific ratings
    - Strengths and achievements
    - Areas for improvement
    - Goals and objectives
    - Reviewer comments
    - Development plan
    
    **Review Types**:
    - Annual review
    - Probation review
    - Mid-year review
    - Promotion review
    - Improvement plan review
    
    **Workflow**:
    - Draft → Pending Approval → Approved → Completed
    - Notifications to supervisor and reviewers
    - Document generation
    - Signature collection
    
    **Permissions**: Requires manager or HR role
    """,
    responses={
        201: {"description": "Review created successfully"},
        400: {"description": "Invalid review data"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Supervisor not found"},
    }
)
async def create_performance_review(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    payload: PerformanceReviewCreate = ...,
    performance_service: SupervisorPerformanceService = Depends(get_performance_service),
    current_user: Any = Depends(get_current_user),
) -> PerformanceReview:
    """Create a new performance review."""
    result = performance_service.create_performance_review(
        supervisor_id=supervisor_id,
        data=payload.dict(exclude_unset=True),
        reviewer_id=current_user.id if hasattr(current_user, 'id') else None,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        error_msg = str(error).lower()
        
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        if "permission" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to create performance review"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.patch(
    "/{supervisor_id}/performance/reviews/{review_id}",
    response_model=PerformanceReview,
    summary="Update performance review",
    description="""
    Update an existing performance review.
    
    **Updatable Fields**:
    - Ratings and scores
    - Comments and feedback
    - Goals and objectives
    - Status and workflow state
    - Attachments and documents
    
    **Restrictions**:
    - Cannot update completed/signed reviews
    - Some fields locked after approval
    - Audit trail maintained for all changes
    
    **Permissions**: Requires review owner or HR role
    """,
    responses={
        200: {"description": "Review updated successfully"},
        400: {"description": "Invalid update data"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Review not found"},
        409: {"description": "Review is locked or completed"},
    }
)
async def update_performance_review(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    review_id: str = Path(..., description="Unique review identifier"),
    payload: PerformanceReviewUpdate = ...,
    performance_service: SupervisorPerformanceService = Depends(get_performance_service),
    current_user: Any = Depends(get_current_user),
) -> PerformanceReview:
    """Update performance review."""
    result = performance_service.update_performance_review(
        supervisor_id=supervisor_id,
        review_id=review_id,
        data=payload.dict(exclude_unset=True),
        updated_by=current_user.id if hasattr(current_user, 'id') else None,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        error_msg = str(error).lower()
        
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Review with ID '{review_id}' not found"
            )
        if "locked" in error_msg or "completed" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot update locked or completed review"
            )
        if "permission" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update review"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{supervisor_id}/performance/reviews",
    response_model=PerformanceReviewListResponse,
    summary="List performance reviews",
    description="""
    List all performance reviews for a supervisor.
    
    **Ordering**: Most recent first
    
    **Filtering**:
    - By review type
    - By status
    - By date range
    - By reviewer
    
    **Includes**:
    - Review summary
    - Overall ratings
    - Review dates
    - Status information
    """,
    responses={
        200: {"description": "Reviews retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def list_performance_reviews(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    performance_service: SupervisorPerformanceService = Depends(get_performance_service),
    current_user: Any = Depends(get_current_user),
    review_type: Optional[str] = Query(None, description="Filter by review type"),
    status: Optional[str] = Query(None, description="Filter by review status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> PerformanceReviewListResponse:
    """List performance reviews with filtering and pagination."""
    result = performance_service.list_performance_reviews(
        supervisor_id=supervisor_id,
        filters={
            "review_type": review_type,
            "status": status,
            "page": page,
            "page_size": page_size,
        },
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return PerformanceReviewListResponse(**result.unwrap())


@router.get(
    "/{supervisor_id}/performance/trends",
    response_model=SupervisorPerformanceTrends,
    summary="Get performance trends",
    description="""
    Get performance trends and historical analysis.
    
    **Trend Analysis**:
    - Performance score over time
    - Category-specific trends
    - Improvement/decline patterns
    - Seasonal variations
    - Peer comparison trends
    
    **Visualization Data**:
    - Time series data points
    - Trend lines and projections
    - Moving averages
    - Anomaly detection
    
    **Time Periods**:
    - Last 6 months (default)
    - Last year
    - Last 2 years
    - Custom range
    
    **Use Cases**:
    - Performance charts
    - Trend analysis
    - Predictive insights
    - Long-term planning
    """,
    responses={
        200: {"description": "Trends retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_performance_trends(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    performance_service: SupervisorPerformanceService = Depends(get_performance_service),
    current_user: Any = Depends(get_current_user),
    period: str = Query("6months", regex="^(3months|6months|1year|2years|custom)$", description="Trend period"),
    granularity: str = Query("month", regex="^(week|month|quarter)$", description="Data granularity"),
) -> SupervisorPerformanceTrends:
    """Get performance trends and historical analysis."""
    result = performance_service.get_performance_trends(
        supervisor_id=supervisor_id,
        period=period,
        granularity=granularity,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{supervisor_id}/performance/rating",
    response_model=PerformanceRating,
    summary="Get overall performance rating",
    description="""
    Calculate and retrieve overall performance rating.
    
    **Rating Calculation**:
    - Weighted average of all metrics
    - Recent performance emphasis
    - Peer benchmarking adjustment
    - Outlier handling
    
    **Rating Scale**:
    - Excellent: 90-100
    - Good: 75-89
    - Satisfactory: 60-74
    - Needs Improvement: 40-59
    - Unsatisfactory: 0-39
    
    **Components**:
    - Overall score (0-100)
    - Rating category
    - Percentile rank
    - Confidence interval
    - Contributing factors
    
    **Use Cases**:
    - Quick performance check
    - Dashboard widgets
    - Comparison metrics
    - Promotion eligibility
    """,
    responses={
        200: {"description": "Rating calculated successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_overall_rating(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    performance_service: SupervisorPerformanceService = Depends(get_performance_service),
    current_user: Any = Depends(get_current_user),
    as_of_date: Optional[datetime] = Query(None, description="Calculate rating as of this date"),
) -> PerformanceRating:
    """Calculate overall performance rating."""
    result = performance_service.calculate_overall_rating(
        supervisor_id=supervisor_id,
        as_of_date=as_of_date.isoformat() if as_of_date else None,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()