"""
Owner response endpoints for hostel managers to reply to reviews.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query, status, HTTPException

from app.core.dependencies import get_current_user_dependency, require_role
from app.core.exceptions import NotFoundError, PermissionError, ValidationError
from app.services.review.review_response_service import ReviewResponseService
from app.schemas.review import (
    OwnerResponse,
    ResponseCreate,
    ResponseUpdate,
    ResponseTemplate,
    ResponseTemplateCreate,
)

router = APIRouter(
    prefix="/reviews/responses",
    tags=["Reviews - Responses"],
)


# ========== Dependency Injection ========== #

def get_response_service() -> ReviewResponseService:
    """Provide ReviewResponseService instance."""
    from app.core.container import get_container
    container = get_container()
    return container.review_response_service()


# ========== Response CRUD Endpoints ========== #

@router.post(
    "/{review_id}",
    response_model=OwnerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create owner response",
    description="Hostel owner or manager responds to a review.",
    responses={
        201: {"description": "Response created successfully"},
        400: {"description": "Invalid response data"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to respond"},
        404: {"description": "Review not found"},
        409: {"description": "Response already exists"},
    },
)
async def create_response(
    review_id: str = Path(
        ...,
        description="Review ID to respond to"
    ),
    payload: ResponseCreate = ...,
    response_service: ReviewResponseService = Depends(get_response_service),
    current_user = Depends(get_current_user_dependency),
) -> OwnerResponse:
    """
    Create a response to a review.
    
    **Authorization:**
    - Must be hostel owner/manager or admin
    - Can only respond to reviews of owned hostels
    - One response per review
    
    **Request Body:**
    - content: Response text (10-1000 chars) - Required
    
    **Best Practices:**
    - Respond professionally and courteously
    - Address specific points raised in review
    - Thank reviewer for feedback
    - Offer solutions if issues mentioned
    
    **Side Effects:**
    - Sends notification to reviewer
    - Updates review response status
    - May improve owner response rate metrics
    """
    result = response_service.create_response(
        review_id=review_id,
        user_id=current_user.id,
        content=payload.content,
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        elif isinstance(error, PermissionError):
            raise HTTPException(status_code=403, detail=str(error))
        elif isinstance(error, ValidationError):
            raise HTTPException(status_code=400, detail=str(error))
        elif "already exists" in str(error).lower():
            raise HTTPException(status_code=409, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.patch(
    "/{response_id}",
    response_model=OwnerResponse,
    summary="Update owner response",
    description="Update an existing response to a review.",
    responses={
        200: {"description": "Response updated successfully"},
        400: {"description": "Invalid update data"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to update this response"},
        404: {"description": "Response not found"},
    },
)
async def update_response(
    response_id: str = Path(
        ...,
        description="Response ID to update"
    ),
    payload: ResponseUpdate = ...,
    response_service: ReviewResponseService = Depends(get_response_service),
    current_user = Depends(get_current_user_dependency),
) -> OwnerResponse:
    """
    Update an existing owner response.
    
    **Authorization:**
    - Must be original responder or admin
    - Response must not be locked
    
    **Request Body:**
    - content: Updated response text (10-1000 chars)
    
    **Note:**
    - Updates are logged for transparency
    - Edited responses are marked as such
    """
    result = response_service.update_response(
        response_id=response_id,
        user_id=current_user.id,
        content=payload.content,
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        elif isinstance(error, PermissionError):
            raise HTTPException(status_code=403, detail=str(error))
        elif isinstance(error, ValidationError):
            raise HTTPException(status_code=400, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.delete(
    "/{response_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete owner response",
    description="Remove a response to a review.",
    responses={
        204: {"description": "Response deleted successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized to delete this response"},
        404: {"description": "Response not found"},
    },
)
async def delete_response(
    response_id: str = Path(
        ...,
        description="Response ID to delete"
    ),
    response_service: ReviewResponseService = Depends(get_response_service),
    current_user = Depends(get_current_user_dependency),
) -> None:
    """
    Delete an owner response.
    
    **Authorization:**
    - Must be original responder or admin
    
    **Behavior:**
    - Response is soft-deleted
    - Can be restored by admin if needed
    - Review response status updated
    """
    result = response_service.delete_response(
        response_id=response_id,
        user_id=current_user.id
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        elif isinstance(error, PermissionError):
            raise HTTPException(status_code=403, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/review/{review_id}",
    response_model=Optional[OwnerResponse],
    summary="Get response for review",
    description="Retrieve the owner response for a specific review.",
    responses={
        200: {"description": "Response retrieved or null if no response"},
        404: {"description": "Review not found"},
    },
)
async def get_response_by_review(
    review_id: str = Path(
        ...,
        description="Review ID"
    ),
    response_service: ReviewResponseService = Depends(get_response_service),
) -> Optional[OwnerResponse]:
    """
    Get the owner response for a specific review.
    
    **Returns:**
    - OwnerResponse if exists
    - null if no response has been created
    """
    result = response_service.get_response_by_review(review_id=review_id)
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            return None
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


# ========== Response Templates ========== #

@router.get(
    "/templates",
    response_model=List[ResponseTemplate],
    summary="List response templates",
    description="Retrieve available response templates for quick replies.",
    dependencies=[Depends(require_role(["owner", "manager", "admin"]))],
    responses={
        200: {"description": "Templates retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
async def list_templates(
    category: Optional[str] = Query(
        None,
        description="Filter by template category"
    ),
    is_active: bool = Query(
        True,
        description="Filter by active status"
    ),
    response_service: ReviewResponseService = Depends(get_response_service),
    current_user = Depends(get_current_user_dependency),
) -> List[ResponseTemplate]:
    """
    List available response templates.
    
    **Access:** Hostel owners/managers and admins
    
    **Templates help:**
    - Respond quickly to common review types
    - Maintain consistent tone and messaging
    - Include customizable variables
    
    **Query Parameters:**
    - category: Filter by category (e.g., "positive", "negative", "neutral")
    - is_active: Show only active templates
    """
    filters = {
        "category": category,
        "is_active": is_active,
    }
    
    result = response_service.list_templates(filters=filters)
    
    if result.is_err():
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.post(
    "/templates",
    response_model=ResponseTemplate,
    status_code=status.HTTP_201_CREATED,
    summary="Create response template",
    description="Create a new response template. Admin only.",
    dependencies=[Depends(require_role(["admin"]))],
    responses={
        201: {"description": "Template created successfully"},
        400: {"description": "Invalid template data"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
async def create_template(
    payload: ResponseTemplateCreate = ...,
    response_service: ReviewResponseService = Depends(get_response_service),
    current_user = Depends(get_current_user_dependency),
) -> ResponseTemplate:
    """
    Create a new response template.
    
    **Access:** Admin only
    
    **Request Body:**
    - name: Template name (3-100 chars)
    - category: Template category (e.g., "positive", "negative")
    - content: Template text with optional variables
    - variables: List of variable names used in template (e.g., ["guest_name", "issue"])
    
    **Variables:**
    Use {{variable_name}} syntax in content
    Example: "Thank you {{guest_name}} for your feedback!"
    """
    result = response_service.create_template(data=payload)
    
    if result.is_err():
        error = result.err()
        if isinstance(error, ValidationError):
            raise HTTPException(status_code=400, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.get(
    "/templates/{template_id}",
    response_model=ResponseTemplate,
    summary="Get template details",
    description="Retrieve a specific template.",
    dependencies=[Depends(require_role(["owner", "manager", "admin"]))],
    responses={
        200: {"description": "Template retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Template not found"},
    },
)
async def get_template(
    template_id: str = Path(
        ...,
        description="Template ID"
    ),
    response_service: ReviewResponseService = Depends(get_response_service),
    current_user = Depends(get_current_user_dependency),
) -> ResponseTemplate:
    """Get detailed information about a specific template."""
    result = response_service.get_template(template_id=template_id)
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.patch(
    "/templates/{template_id}",
    response_model=ResponseTemplate,
    summary="Update template",
    description="Update an existing template. Admin only.",
    dependencies=[Depends(require_role(["admin"]))],
    responses={
        200: {"description": "Template updated successfully"},
        400: {"description": "Invalid update data"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Template not found"},
    },
)
async def update_template(
    template_id: str = Path(
        ...,
        description="Template ID to update"
    ),
    payload: dict = ...,
    response_service: ReviewResponseService = Depends(get_response_service),
    current_user = Depends(get_current_user_dependency),
) -> ResponseTemplate:
    """Update an existing response template."""
    result = response_service.update_template(
        template_id=template_id,
        data=payload
    )
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        elif isinstance(error, ValidationError):
            raise HTTPException(status_code=400, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete template",
    description="Delete a response template. Admin only.",
    dependencies=[Depends(require_role(["admin"]))],
    responses={
        204: {"description": "Template deleted successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Template not found"},
    },
)
async def delete_template(
    template_id: str = Path(
        ...,
        description="Template ID to delete"
    ),
    response_service: ReviewResponseService = Depends(get_response_service),
    current_user = Depends(get_current_user_dependency),
) -> None:
    """Delete a response template."""
    result = response_service.delete_template(template_id=template_id)
    
    if result.is_err():
        error = result.err()
        if isinstance(error, NotFoundError):
            raise HTTPException(status_code=404, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/stats/response-rate",
    summary="Get response rate statistics",
    description="Get statistics about owner response rates.",
    dependencies=[Depends(require_role(["owner", "manager", "admin"]))],
    responses={
        200: {"description": "Statistics retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
async def get_response_rate_stats(
    hostel_id: Optional[str] = Query(
        None,
        description="Filter by hostel ID"
    ),
    time_range: str = Query(
        "30d",
        regex="^(7d|30d|90d|all)$",
        description="Time range for statistics"
    ),
    response_service: ReviewResponseService = Depends(get_response_service),
    current_user = Depends(get_current_user_dependency),
) -> dict:
    """
    Get response rate statistics.
    
    **Returns:**
    - total_reviews: Total number of reviews
    - responded_reviews: Number with owner responses
    - response_rate: Percentage of reviews with responses
    - avg_response_time: Average time to respond
    - response_rate_trend: Trend over time
    """
    result = response_service.get_response_stats(
        hostel_id=hostel_id,
        time_range=time_range,
        user_id=current_user.id
    )
    
    if result.is_err():
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result.unwrap()