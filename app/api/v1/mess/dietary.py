"""
Mess Dietary Options and Preferences API Endpoints

This module manages dietary options, student preferences, and meal customizations.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import AuthenticationDependency
from app.services.mess.dietary_option_service import DietaryOptionService
from app.schemas.mess import (
    DietaryOption,
    DietaryOptionUpdate,
    StudentDietaryPreference,
    StudentPreferenceUpdate,
    MealCustomization,
    CustomizationCreate,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/mess/dietary",
    tags=["Mess - Dietary"],
)


async def get_dietary_service() -> DietaryOptionService:
    """
    Dependency injection for DietaryOptionService.
    
    Raises:
        NotImplementedError: When DI container is not configured
    """
    raise NotImplementedError(
        "DietaryOptionService dependency injection not configured. "
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


@router.get(
    "/options",
    response_model=DietaryOption,
    status_code=status.HTTP_200_OK,
    summary="Get hostel dietary options",
    description="Retrieve available dietary options for a specific hostel.",
    responses={
        200: {"description": "Dietary options retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
async def get_dietary_options(
    hostel_id: str = Query(..., description="Unique hostel identifier"),
    dietary_service: DietaryOptionService = Depends(get_dietary_service),
    current_user: Any = Depends(get_current_user),
) -> DietaryOption:
    """
    Get dietary options configured for a hostel.
    
    Args:
        hostel_id: Unique identifier of the hostel
        dietary_service: Dietary option service instance
        current_user: Currently authenticated user
        
    Returns:
        DietaryOption: Available dietary options for the hostel
        
    Raises:
        HTTPException: If hostel not found
    """
    logger.debug(f"Fetching dietary options for hostel {hostel_id}")
    
    result = dietary_service.get_hostel_dietary_options(hostel_id=hostel_id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch dietary options for hostel {hostel_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hostel with ID {hostel_id} not found",
        )
    
    return result.unwrap()


@router.post(
    "/options",
    response_model=DietaryOption,
    status_code=status.HTTP_201_CREATED,
    summary="Configure hostel dietary options",
    description="Create or update dietary options for a hostel. Requires admin permissions.",
    responses={
        201: {"description": "Dietary options configured successfully"},
        400: {"description": "Invalid dietary option configuration"},
        403: {"description": "User not authorized to configure dietary options"},
    },
)
async def set_dietary_options(
    payload: DietaryOptionUpdate,
    dietary_service: DietaryOptionService = Depends(get_dietary_service),
    current_user: Any = Depends(get_current_user),
) -> DietaryOption:
    """
    Configure dietary options for a hostel.
    
    Args:
        payload: Dietary option configuration data
        dietary_service: Dietary option service instance
        current_user: Currently authenticated user (must have admin rights)
        
    Returns:
        DietaryOption: Updated dietary options
        
    Raises:
        HTTPException: If configuration fails or user lacks permission
    """
    logger.info(
        f"User {current_user.id} configuring dietary options for hostel {payload.hostel_id}"
    )
    
    result = dietary_service.set_hostel_dietary_options(
        hostel_id=payload.hostel_id,
        data=payload,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to configure dietary options: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    logger.info(f"Dietary options successfully configured for hostel {payload.hostel_id}")
    return result.unwrap()


@router.get(
    "/preferences/me",
    response_model=StudentDietaryPreference,
    status_code=status.HTTP_200_OK,
    summary="Get my dietary preferences",
    description="Retrieve dietary preferences for the currently authenticated student.",
    responses={
        200: {"description": "Preferences retrieved successfully"},
        404: {"description": "Student preferences not found"},
    },
)
async def get_my_preferences(
    dietary_service: DietaryOptionService = Depends(get_dietary_service),
    current_user: Any = Depends(get_current_user),
) -> StudentDietaryPreference:
    """
    Get dietary preferences for the current student.
    
    Args:
        dietary_service: Dietary option service instance
        current_user: Currently authenticated student
        
    Returns:
        StudentDietaryPreference: Student's dietary preferences
        
    Raises:
        HTTPException: If preferences not found
    """
    logger.debug(f"Fetching dietary preferences for student {current_user.id}")
    
    result = dietary_service.get_student_preferences(student_id=current_user.id)
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch preferences for student {current_user.id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student dietary preferences not found",
        )
    
    return result.unwrap()


@router.put(
    "/preferences/me",
    response_model=StudentDietaryPreference,
    status_code=status.HTTP_200_OK,
    summary="Update my dietary preferences",
    description="Update dietary preferences for the currently authenticated student.",
    responses={
        200: {"description": "Preferences updated successfully"},
        400: {"description": "Invalid preference data"},
    },
)
async def update_my_preferences(
    payload: StudentPreferenceUpdate,
    dietary_service: DietaryOptionService = Depends(get_dietary_service),
    current_user: Any = Depends(get_current_user),
) -> StudentDietaryPreference:
    """
    Update dietary preferences for the current student.
    
    Args:
        payload: Updated preference data
        dietary_service: Dietary option service instance
        current_user: Currently authenticated student
        
    Returns:
        StudentDietaryPreference: Updated preferences
        
    Raises:
        HTTPException: If update fails
    """
    logger.info(f"Student {current_user.id} updating dietary preferences")
    
    result = dietary_service.set_student_preferences(
        student_id=current_user.id,
        data=payload,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to update preferences for student {current_user.id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    logger.info(f"Preferences successfully updated for student {current_user.id}")
    return result.unwrap()


@router.get(
    "/customizations",
    response_model=List[MealCustomization],
    status_code=status.HTTP_200_OK,
    summary="Get meal customizations",
    description="Retrieve all meal customization requests for the current student.",
    responses={
        200: {"description": "Customizations retrieved successfully"},
    },
)
async def list_customizations(
    status_filter: Optional[str] = Query(
        None,
        description="Filter by customization status (pending, approved, rejected)",
    ),
    dietary_service: DietaryOptionService = Depends(get_dietary_service),
    current_user: Any = Depends(get_current_user),
) -> List[MealCustomization]:
    """
    List meal customizations for the current student.
    
    Args:
        status_filter: Optional status filter
        dietary_service: Dietary option service instance
        current_user: Currently authenticated student
        
    Returns:
        List[MealCustomization]: List of customization requests
    """
    logger.debug(
        f"Fetching customizations for student {current_user.id}, status: {status_filter}"
    )
    
    result = dietary_service.list_customizations_for_student(
        student_id=current_user.id,
        status_filter=status_filter,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to fetch customizations: {error}")
        # Return empty list instead of error for better UX
        return []
    
    customizations = result.unwrap()
    logger.debug(f"Retrieved {len(customizations)} customizations")
    return customizations


@router.post(
    "/customizations",
    response_model=MealCustomization,
    status_code=status.HTTP_201_CREATED,
    summary="Request meal customization",
    description="Create a new meal customization request.",
    responses={
        201: {"description": "Customization request created successfully"},
        400: {"description": "Invalid customization request"},
    },
)
async def create_customization(
    payload: CustomizationCreate,
    dietary_service: DietaryOptionService = Depends(get_dietary_service),
    current_user: Any = Depends(get_current_user),
) -> MealCustomization:
    """
    Create a meal customization request.
    
    Args:
        payload: Customization request data
        dietary_service: Dietary option service instance
        current_user: Currently authenticated student
        
    Returns:
        MealCustomization: Created customization request
        
    Raises:
        HTTPException: If creation fails
    """
    logger.info(
        f"Student {current_user.id} creating customization request"
    )
    
    result = dietary_service.create_customization(
        student_id=current_user.id,
        data=payload,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        logger.error(f"Failed to create customization: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    
    customization = result.unwrap()
    logger.info(f"Customization request {customization.id} created successfully")
    return customization