"""
Mess Menu Planning API Endpoints

This module handles menu planning, templates, and AI-powered suggestions.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.dependencies import AuthenticationDependency
from app.services.mess.menu_planning_service import MenuPlanningService
from app.schemas.mess import (
    MenuTemplate,
    MenuTemplateCreate,
    MenuTemplateUpdate,
    WeeklyPlan,
    WeeklyPlanCreate,
    MonthlyPlan,
    MonthlyPlanCreate,
    MenuSuggestion,
    SuggestionCriteria,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/mess/planning",
    tags=["Mess - Planning"],
)


async def get_planning_service() -> MenuPlanningService:
    """
    Dependency injection for MenuPlanningService.
    
    Raises:
        NotImplementedError: When DI container is not configured
    """
    raise NotImplementedError(
        "MenuPlanningService dependency injection not configured. "
        "Please implement this in your DI container."
    )


async def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Get the currently authenticated user.
    
    Args:
        auth: Authentication dependency
        
    Returns:
        Current authenticated user object
    """
    return auth.get_current_user()


@router.post(
    "/templates",
    response_model=MenuTemplate,
    status_code=status.HTTP_201_CREATED,
    summary="Create menu template",
    description="Create a reusable menu template. Requires admin permissions.",
    responses={
        201: {"description": "Template created successfully"},
        400: {"description": "Invalid template data"},
        403: {"description": "User not authorized to create templates"},
    },
)
async def create_template(
    payload: MenuTemplateCreate,
    planning_service: MenuPlanningService = Depends(get_planning_service),
    current_user: Any = Depends(get_current_user),
) -> MenuTemplate:
    """
    Create a menu template.
    
    Args:
        payload: Template creation data
        planning_service: Menu planning service instance
        current_user: Currently authenticated user (must have admin rights)
        
    Returns:
        MenuTemplate: Created template
        
    Raises:
        HTTPException: If creation fails or user lacks permission
    """
    logger.info(
        f"User {current_user.id} creating menu template: {payload.name}"
    )
    
    result = planning_service.create_template(data=payload)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to create template: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    template = result.unwrap()
    logger.info(f"Template {template.id} created successfully")
    return template


@router.get(
    "/templates",
    response_model=List[MenuTemplate],
    status_code=status.HTTP_200_OK,
    summary="List menu templates",
    description="Retrieve all menu templates for a hostel.",
    responses={
        200: {"description": "Templates retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
async def list_templates(
    hostel_id: str = Query(..., description="Unique hostel identifier"),
    category: Optional[str] = Query(
        None,
        description="Filter by template category",
    ),
    is_active: Optional[bool] = Query(
        None,
        description="Filter by active status",
    ),
    planning_service: MenuPlanningService = Depends(get_planning_service),
    current_user: Any = Depends(get_current_user),
) -> List[MenuTemplate]:
    """
    List menu templates for a hostel.
    
    Args:
        hostel_id: Unique identifier of the hostel
        category: Optional category filter
        is_active: Optional active status filter
        planning_service: Menu planning service instance
        current_user: Currently authenticated user
        
    Returns:
        List[MenuTemplate]: List of menu templates
        
    Raises:
        HTTPException: If hostel not found
    """
    filters = {
        "category": category,
        "is_active": is_active,
    }
    filters = {k: v for k, v in filters.items() if v is not None}
    
    logger.debug(f"Listing templates for hostel {hostel_id} with filters: {filters}")
    
    result = planning_service.list_templates_for_hostel(
        hostel_id=hostel_id,
        filters=filters,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to list templates: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hostel with ID {hostel_id} not found",
        )
    
    templates = result.unwrap()
    logger.debug(f"Retrieved {len(templates)} templates")
    return templates


@router.get(
    "/templates/{template_id}",
    response_model=MenuTemplate,
    status_code=status.HTTP_200_OK,
    summary="Get template detail",
    description="Retrieve detailed information about a specific template.",
    responses={
        200: {"description": "Template retrieved successfully"},
        404: {"description": "Template not found"},
    },
)
async def get_template(
    template_id: str = Path(..., description="Unique template identifier"),
    planning_service: MenuPlanningService = Depends(get_planning_service),
    current_user: Any = Depends(get_current_user),
) -> MenuTemplate:
    """
    Get template details.
    
    Args:
        template_id: Unique identifier of the template
        planning_service: Menu planning service instance
        current_user: Currently authenticated user
        
    Returns:
        MenuTemplate: Template details
        
    Raises:
        HTTPException: If template not found
    """
    logger.debug(f"Fetching template {template_id}")
    
    result = planning_service.get_template(template_id=template_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch template {template_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with ID {template_id} not found",
        )
    
    return result.unwrap()


@router.patch(
    "/templates/{template_id}",
    response_model=MenuTemplate,
    status_code=status.HTTP_200_OK,
    summary="Update template",
    description="Update an existing menu template.",
    responses={
        200: {"description": "Template updated successfully"},
        400: {"description": "Invalid update data"},
        404: {"description": "Template not found"},
        403: {"description": "User not authorized"},
    },
)
async def update_template(
    template_id: str = Path(..., description="Unique template identifier"),
    payload: MenuTemplateUpdate = ...,
    planning_service: MenuPlanningService = Depends(get_planning_service),
    current_user: Any = Depends(get_current_user),
) -> MenuTemplate:
    """
    Update a menu template.
    
    Args:
        template_id: Unique identifier of the template
        payload: Updated template data
        planning_service: Menu planning service instance
        current_user: Currently authenticated user
        
    Returns:
        MenuTemplate: Updated template
        
    Raises:
        HTTPException: If update fails or template not found
    """
    logger.info(f"User {current_user.id} updating template {template_id}")
    
    result = planning_service.update_template(
        template_id=template_id,
        data=payload,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to update template {template_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    template = result.unwrap()
    logger.info(f"Template {template_id} updated successfully")
    return template


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete template",
    description="Delete a menu template.",
    responses={
        204: {"description": "Template deleted successfully"},
        404: {"description": "Template not found"},
        403: {"description": "User not authorized"},
    },
)
async def delete_template(
    template_id: str = Path(..., description="Unique template identifier"),
    planning_service: MenuPlanningService = Depends(get_planning_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Delete a menu template.
    
    Args:
        template_id: Unique identifier of the template
        planning_service: Menu planning service instance
        current_user: Currently authenticated user
        
    Raises:
        HTTPException: If deletion fails or template not found
    """
    logger.info(f"User {current_user.id} deleting template {template_id}")
    
    result = planning_service.delete_template(template_id=template_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to delete template {template_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    logger.info(f"Template {template_id} deleted successfully")


@router.post(
    "/weekly-plan",
    response_model=WeeklyPlan,
    status_code=status.HTTP_201_CREATED,
    summary="Create weekly plan",
    description="Create a weekly menu plan. Requires admin permissions.",
    responses={
        201: {"description": "Weekly plan created successfully"},
        400: {"description": "Invalid plan data"},
        403: {"description": "User not authorized to create plans"},
    },
)
async def create_weekly_plan(
    payload: WeeklyPlanCreate,
    planning_service: MenuPlanningService = Depends(get_planning_service),
    current_user: Any = Depends(get_current_user),
) -> WeeklyPlan:
    """
    Create a weekly menu plan.
    
    Args:
        payload: Weekly plan creation data
        planning_service: Menu planning service instance
        current_user: Currently authenticated user (must have admin rights)
        
    Returns:
        WeeklyPlan: Created weekly plan
        
    Raises:
        HTTPException: If creation fails or user lacks permission
    """
    logger.info(
        f"User {current_user.id} creating weekly plan for week starting {payload.start_date}"
    )
    
    result = planning_service.create_weekly_plan(data=payload)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to create weekly plan: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    plan = result.unwrap()
    logger.info(f"Weekly plan {plan.id} created successfully")
    return plan


@router.post(
    "/monthly-plan",
    response_model=MonthlyPlan,
    status_code=status.HTTP_201_CREATED,
    summary="Create monthly plan",
    description="Create a monthly menu plan. Requires admin permissions.",
    responses={
        201: {"description": "Monthly plan created successfully"},
        400: {"description": "Invalid plan data"},
        403: {"description": "User not authorized to create plans"},
    },
)
async def create_monthly_plan(
    payload: MonthlyPlanCreate,
    planning_service: MenuPlanningService = Depends(get_planning_service),
    current_user: Any = Depends(get_current_user),
) -> MonthlyPlan:
    """
    Create a monthly menu plan.
    
    Args:
        payload: Monthly plan creation data
        planning_service: Menu planning service instance
        current_user: Currently authenticated user (must have admin rights)
        
    Returns:
        MonthlyPlan: Created monthly plan
        
    Raises:
        HTTPException: If creation fails or user lacks permission
    """
    logger.info(
        f"User {current_user.id} creating monthly plan for {payload.month}"
    )
    
    result = planning_service.create_monthly_plan(data=payload)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to create monthly plan: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    plan = result.unwrap()
    logger.info(f"Monthly plan {plan.id} created successfully")
    return plan


@router.get(
    "/suggestions",
    response_model=List[MenuSuggestion],
    status_code=status.HTTP_200_OK,
    summary="Get AI menu suggestions",
    description="Get AI-powered menu suggestions based on various factors.",
    responses={
        200: {"description": "Suggestions retrieved successfully"},
        400: {"description": "Invalid parameters"},
    },
)
async def get_suggestions(
    hostel_id: str = Query(..., description="Unique hostel identifier"),
    date_range: Optional[str] = Query(
        None,
        description="Date range for suggestions (e.g., '2024-01-01:2024-01-07')",
    ),
    meal_type: Optional[str] = Query(
        None,
        description="Filter by meal type (breakfast, lunch, dinner)",
    ),
    dietary_preference: Optional[str] = Query(
        None,
        description="Consider dietary preferences",
    ),
    limit: int = Query(
        10,
        ge=1,
        le=50,
        description="Maximum number of suggestions",
    ),
    planning_service: MenuPlanningService = Depends(get_planning_service),
    current_user: Any = Depends(get_current_user),
) -> List[MenuSuggestion]:
    """
    Get AI-powered menu suggestions.
    
    Args:
        hostel_id: Unique identifier of the hostel
        date_range: Optional date range for suggestions
        meal_type: Optional meal type filter
        dietary_preference: Optional dietary preference consideration
        limit: Maximum number of suggestions
        planning_service: Menu planning service instance
        current_user: Currently authenticated user
        
    Returns:
        List[MenuSuggestion]: AI-generated menu suggestions
        
    Raises:
        HTTPException: If suggestion generation fails
    """
    logger.info(
        f"Generating menu suggestions for hostel {hostel_id}, "
        f"date_range: {date_range}, meal_type: {meal_type}"
    )
    
    result = planning_service.get_menu_suggestions(
        hostel_id=hostel_id,
        date_range=date_range,
        meal_type=meal_type,
        dietary_preference=dietary_preference,
        limit=limit,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to generate suggestions: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    suggestions = result.unwrap()
    logger.info(f"Generated {len(suggestions)} menu suggestions")
    return suggestions


@router.post(
    "/suggestions/generate",
    response_model=List[MenuSuggestion],
    status_code=status.HTTP_200_OK,
    summary="Generate menu suggestions",
    description="Generate menu suggestions based on specific criteria.",
    responses={
        200: {"description": "Suggestions generated successfully"},
        400: {"description": "Invalid criteria"},
    },
)
async def generate_suggestions(
    payload: SuggestionCriteria,
    planning_service: MenuPlanningService = Depends(get_planning_service),
    current_user: Any = Depends(get_current_user),
) -> List[MenuSuggestion]:
    """
    Generate menu suggestions with custom criteria.
    
    Args:
        payload: Suggestion generation criteria
        planning_service: Menu planning service instance
        current_user: Currently authenticated user
        
    Returns:
        List[MenuSuggestion]: Generated menu suggestions
        
    Raises:
        HTTPException: If generation fails
    """
    logger.info(
        f"User {current_user.id} generating menu suggestions with custom criteria"
    )
    
    result = planning_service.generate_suggestions(data=payload)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to generate suggestions: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    suggestions = result.unwrap()
    logger.info(f"Generated {len(suggestions)} custom suggestions")
    return suggestions


@router.post(
    "/templates/{template_id}/apply",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Apply template to date",
    description="Apply a menu template to create menu for a specific date.",
    responses={
        200: {"description": "Template applied successfully"},
        400: {"description": "Cannot apply template to date"},
        404: {"description": "Template not found"},
    },
)
async def apply_template(
    template_id: str = Path(..., description="Unique template identifier"),
    target_date: str = Query(
        ...,
        regex=r"^\d{4}-\d{2}-\d{2}$",
        description="Target date to apply template (YYYY-MM-DD)",
    ),
    planning_service: MenuPlanningService = Depends(get_planning_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Apply a template to create a menu for a specific date.
    
    Args:
        template_id: Unique identifier of the template
        target_date: Date to apply template to
        planning_service: Menu planning service instance
        current_user: Currently authenticated user
        
    Returns:
        dict: Application result with created menu ID
        
    Raises:
        HTTPException: If application fails or template not found
    """
    logger.info(
        f"User {current_user.id} applying template {template_id} to {target_date}"
    )
    
    result = planning_service.apply_template_to_date(
        template_id=template_id,
        target_date=target_date,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to apply template: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    application_result = result.unwrap()
    logger.info(f"Template {template_id} applied successfully to {target_date}")
    return application_result