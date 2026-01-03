"""
Student Profile and Guardian Contact API Endpoints

Provides endpoints for managing student profiles and guardian information.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Path, status, Body

from app.core.dependencies import get_current_user
from app.services.student.student_profile_service import StudentProfileService
from app.services.student.guardian_contact_service import GuardianContactService
from app.schemas.student import (
    StudentProfile,
    StudentProfileUpdate,
    GuardianContact,
    GuardianContactCreate,
    GuardianContactUpdate,
)
from app.schemas.common.base import User

router = APIRouter(
    prefix="/students",
    tags=["Students - Profile"],
)


def get_profile_service() -> StudentProfileService:
    """
    Dependency injection for StudentProfileService.
    
    Returns:
        StudentProfileService: Instance of the profile service
        
    Raises:
        NotImplementedError: To be implemented with actual service instantiation
    """
    raise NotImplementedError("StudentProfileService dependency not configured")


def get_guardian_service() -> GuardianContactService:
    """
    Dependency injection for GuardianContactService.
    
    Returns:
        GuardianContactService: Instance of the guardian service
        
    Raises:
        NotImplementedError: To be implemented with actual service instantiation
    """
    raise NotImplementedError("GuardianContactService dependency not configured")


# ==================== Student Profile Endpoints ====================


@router.get(
    "/{student_id}/profile",
    response_model=StudentProfile,
    status_code=status.HTTP_200_OK,
    summary="Get extended student profile",
    description="Retrieve comprehensive student profile including personal details, academic info, and emergency contacts.",
    responses={
        200: {"description": "Profile retrieved successfully"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Student profile not found"},
    },
)
async def get_profile(
    student_id: UUID = Path(..., description="Unique student identifier"),
    profile_service: StudentProfileService = Depends(get_profile_service),
    current_user: User = Depends(get_current_user),
) -> StudentProfile:
    """
    Get extended student profile information.
    
    Includes:
    - Personal details (DOB, blood group, nationality, etc.)
    - Academic information
    - Contact details
    - Emergency contacts
    - Medical information
    - Parent/guardian details
    
    Args:
        student_id: UUID of the student
        profile_service: Injected profile service
        current_user: Authenticated user from dependency
        
    Returns:
        StudentProfile: Comprehensive profile data
    """
    result = profile_service.get_profile(student_id=str(student_id))
    return result.unwrap()


@router.put(
    "/{student_id}/profile",
    response_model=StudentProfile,
    status_code=status.HTTP_200_OK,
    summary="Update extended student profile",
    description="Create or update student profile information.",
)
async def upsert_profile(
    student_id: UUID = Path(..., description="Unique student identifier"),
    payload: StudentProfileUpdate = Body(..., description="Profile update data"),
    profile_service: StudentProfileService = Depends(get_profile_service),
    current_user: User = Depends(get_current_user),
) -> StudentProfile:
    """
    Create or update student profile.
    
    This is an upsert operation - it will create a new profile if one doesn't exist,
    or update the existing profile.
    
    Args:
        student_id: UUID of the student
        payload: Profile data to update
        profile_service: Injected profile service
        current_user: Authenticated user from dependency
        
    Returns:
        StudentProfile: Updated profile data
    """
    result = profile_service.upsert_profile(
        student_id=str(student_id),
        data=payload.dict(exclude_unset=True),
    )
    return result.unwrap()


@router.patch(
    "/{student_id}/profile",
    response_model=StudentProfile,
    status_code=status.HTTP_200_OK,
    summary="Partially update student profile",
    description="Update specific fields of the student profile.",
)
async def partial_update_profile(
    student_id: UUID = Path(..., description="Unique student identifier"),
    payload: StudentProfileUpdate = Body(..., description="Partial profile update data"),
    profile_service: StudentProfileService = Depends(get_profile_service),
    current_user: User = Depends(get_current_user),
) -> StudentProfile:
    """
    Partially update student profile.
    
    Only provided fields will be updated.
    
    Args:
        student_id: UUID of the student
        payload: Fields to update
        profile_service: Injected profile service
        current_user: Authenticated user from dependency
        
    Returns:
        StudentProfile: Updated profile data
    """
    result = profile_service.partial_update_profile(
        student_id=str(student_id),
        data=payload.dict(exclude_unset=True),
    )
    return result.unwrap()


# ==================== Guardian Contact Endpoints ====================


@router.get(
    "/{student_id}/guardians",
    response_model=List[GuardianContact],
    status_code=status.HTTP_200_OK,
    summary="List guardians",
    description="Retrieve all guardian contacts for a student.",
    responses={
        200: {"description": "Guardians retrieved successfully"},
        401: {"description": "Unauthorized"},
        404: {"description": "Student not found"},
    },
)
async def list_guardians(
    student_id: UUID = Path(..., description="Unique student identifier"),
    guardian_service: GuardianContactService = Depends(get_guardian_service),
    current_user: User = Depends(get_current_user),
) -> List[GuardianContact]:
    """
    List all guardian contacts for a student.
    
    Includes parents, legal guardians, and emergency contacts.
    
    Args:
        student_id: UUID of the student
        guardian_service: Injected guardian service
        current_user: Authenticated user from dependency
        
    Returns:
        List[GuardianContact]: List of guardian contacts
    """
    result = guardian_service.list_guardians(student_id=str(student_id))
    return result.unwrap()


@router.get(
    "/{student_id}/guardians/{guardian_id}",
    response_model=GuardianContact,
    status_code=status.HTTP_200_OK,
    summary="Get guardian details",
    description="Retrieve detailed information about a specific guardian.",
)
async def get_guardian_detail(
    student_id: UUID = Path(..., description="Unique student identifier"),
    guardian_id: UUID = Path(..., description="Unique guardian identifier"),
    guardian_service: GuardianContactService = Depends(get_guardian_service),
    current_user: User = Depends(get_current_user),
) -> GuardianContact:
    """
    Get detailed information about a specific guardian.
    
    Args:
        student_id: UUID of the student
        guardian_id: UUID of the guardian
        guardian_service: Injected guardian service
        current_user: Authenticated user from dependency
        
    Returns:
        GuardianContact: Guardian contact details
    """
    result = guardian_service.get_guardian_by_id(
        student_id=str(student_id),
        guardian_id=str(guardian_id),
    )
    return result.unwrap()


@router.post(
    "/{student_id}/guardians",
    response_model=GuardianContact,
    status_code=status.HTTP_201_CREATED,
    summary="Add guardian contact",
    description="Add a new guardian contact for a student.",
    responses={
        201: {"description": "Guardian added successfully"},
        400: {"description": "Invalid guardian data"},
        401: {"description": "Unauthorized"},
    },
)
async def add_guardian(
    student_id: UUID = Path(..., description="Unique student identifier"),
    payload: GuardianContactCreate = Body(..., description="Guardian contact data"),
    guardian_service: GuardianContactService = Depends(get_guardian_service),
    current_user: User = Depends(get_current_user),
) -> GuardianContact:
    """
    Add a new guardian contact for a student.
    
    Guardian types include:
    - Father
    - Mother
    - Legal Guardian
    - Emergency Contact
    
    Args:
        student_id: UUID of the student
        payload: Guardian contact data
        guardian_service: Injected guardian service
        current_user: Authenticated user from dependency
        
    Returns:
        GuardianContact: Created guardian contact
    """
    guardian_data = payload.dict()
    guardian_data["student_id"] = str(student_id)
    
    result = guardian_service.create_guardian(data=guardian_data)
    return result.unwrap()


@router.patch(
    "/{student_id}/guardians/{guardian_id}",
    response_model=GuardianContact,
    status_code=status.HTTP_200_OK,
    summary="Update guardian contact",
    description="Update guardian contact information.",
)
async def update_guardian(
    student_id: UUID = Path(..., description="Unique student identifier"),
    guardian_id: UUID = Path(..., description="Unique guardian identifier"),
    payload: GuardianContactUpdate = Body(..., description="Guardian update data"),
    guardian_service: GuardianContactService = Depends(get_guardian_service),
    current_user: User = Depends(get_current_user),
) -> GuardianContact:
    """
    Update guardian contact information.
    
    Args:
        student_id: UUID of the student
        guardian_id: UUID of the guardian
        payload: Updated guardian data
        guardian_service: Injected guardian service
        current_user: Authenticated user from dependency
        
    Returns:
        GuardianContact: Updated guardian contact
    """
    result = guardian_service.update_guardian(
        guardian_id=str(guardian_id),
        data=payload.dict(exclude_unset=True),
    )
    return result.unwrap()


@router.delete(
    "/{student_id}/guardians/{guardian_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove guardian contact",
    description="Delete a guardian contact from the student's profile.",
    responses={
        204: {"description": "Guardian removed successfully"},
        400: {"description": "Cannot remove primary guardian"},
        401: {"description": "Unauthorized"},
        404: {"description": "Guardian not found"},
    },
)
async def remove_guardian(
    student_id: UUID = Path(..., description="Unique student identifier"),
    guardian_id: UUID = Path(..., description="Unique guardian identifier"),
    guardian_service: GuardianContactService = Depends(get_guardian_service),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Remove a guardian contact.
    
    Note: Primary guardians cannot be removed if they are the only contact.
    
    Args:
        student_id: UUID of the student
        guardian_id: UUID of the guardian
        guardian_service: Injected guardian service
        current_user: Authenticated user from dependency
        
    Returns:
        None: 204 No Content on success
    """
    guardian_service.delete_guardian(
        guardian_id=str(guardian_id),
        student_id=str(student_id),
    ).unwrap()


@router.patch(
    "/{student_id}/guardians/{guardian_id}/set-primary",
    response_model=GuardianContact,
    status_code=status.HTTP_200_OK,
    summary="Set primary guardian",
    description="Mark a guardian as the primary contact.",
)
async def set_primary_guardian(
    student_id: UUID = Path(..., description="Unique student identifier"),
    guardian_id: UUID = Path(..., description="Unique guardian identifier"),
    guardian_service: GuardianContactService = Depends(get_guardian_service),
    current_user: User = Depends(get_current_user),
) -> GuardianContact:
    """
    Set a guardian as the primary contact.
    
    This will unset any existing primary guardian.
    
    Args:
        student_id: UUID of the student
        guardian_id: UUID of the guardian
        guardian_service: Injected guardian service
        current_user: Authenticated user from dependency
        
    Returns:
        GuardianContact: Updated guardian contact
    """
    result = guardian_service.set_primary_guardian(
        student_id=str(student_id),
        guardian_id=str(guardian_id),
    )
    return result.unwrap()