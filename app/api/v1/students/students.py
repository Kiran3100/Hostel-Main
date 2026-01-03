"""
Core Student Management API Endpoints

Provides CRUD operations and lifecycle management for students.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status, Body

from app.core.dependencies import get_current_user
from app.services.student.student_service import StudentService
from app.services.student.student_onboarding_service import StudentOnboardingService
from app.services.student.student_checkout_service import StudentCheckoutService
from app.schemas.student import (
    StudentResponse,
    StudentDetail,
    StudentListItem,
    StudentStats,
    StudentCreate,
    StudentUpdate,
    StudentStatus,
    OnboardingRequest,
    CheckoutRequest,
    BulkStatusUpdate,
)
from app.schemas.common.base import User, PaginatedResponse

router = APIRouter(
    prefix="/students",
    tags=["Students"],
)


def get_student_service() -> StudentService:
    """
    Dependency injection for StudentService.
    
    Returns:
        StudentService: Instance of the student service
        
    Raises:
        NotImplementedError: To be implemented with actual service instantiation
    """
    raise NotImplementedError("StudentService dependency not configured")


def get_onboarding_service() -> StudentOnboardingService:
    """
    Dependency injection for StudentOnboardingService.
    
    Returns:
        StudentOnboardingService: Instance of the onboarding service
        
    Raises:
        NotImplementedError: To be implemented with actual service instantiation
    """
    raise NotImplementedError("StudentOnboardingService dependency not configured")


def get_checkout_service() -> StudentCheckoutService:
    """
    Dependency injection for StudentCheckoutService.
    
    Returns:
        StudentCheckoutService: Instance of the checkout service
        
    Raises:
        NotImplementedError: To be implemented with actual service instantiation
    """
    raise NotImplementedError("StudentCheckoutService dependency not configured")


# ==================== Student CRUD Endpoints ====================


@router.post(
    "",
    response_model=StudentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create student record",
    description="Create a new student record in the system.",
    responses={
        201: {"description": "Student created successfully"},
        400: {"description": "Invalid student data or duplicate record"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - Insufficient permissions"},
    },
)
async def create_student(
    payload: StudentCreate = Body(..., description="Student creation data"),
    student_service: StudentService = Depends(get_student_service),
    current_user: User = Depends(get_current_user),
) -> StudentDetail:
    """
    Create a new student record.
    
    Validates:
    - Required fields are provided
    - Email and student ID are unique
    - Academic year and course information are valid
    
    Args:
        payload: Student creation data
        student_service: Injected student service
        current_user: Authenticated user from dependency
        
    Returns:
        StudentDetail: Created student details
    """
    result = student_service.create_student(
        data=payload.dict(),
        created_by=current_user.id,
    )
    return result.unwrap()


@router.get(
    "",
    response_model=PaginatedResponse[StudentListItem],
    status_code=status.HTTP_200_OK,
    summary="List students",
    description="Retrieve a paginated list of students with optional filtering.",
    responses={
        200: {"description": "Students retrieved successfully"},
        401: {"description": "Unauthorized"},
    },
)
async def list_students(
    hostel_id: Optional[UUID] = Query(None, description="Filter by hostel"),
    room_id: Optional[UUID] = Query(None, description="Filter by room"),
    search: Optional[str] = Query(
        None,
        description="Search by name, email, or student ID",
        min_length=2,
    ),
    status_filter: Optional[StudentStatus] = Query(
        None,
        alias="status",
        description="Filter by student status",
    ),
    academic_year: Optional[str] = Query(
        None,
        description="Filter by academic year",
    ),
    course: Optional[str] = Query(None, description="Filter by course"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query(
        "desc",
        regex="^(asc|desc)$",
        description="Sort order (asc/desc)",
    ),
    student_service: StudentService = Depends(get_student_service),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[StudentListItem]:
    """
    List students with advanced filtering and pagination.
    
    Supports filtering by:
    - Hostel assignment
    - Room assignment
    - Student status
    - Academic year and course
    - Text search across name, email, and ID
    
    Args:
        hostel_id: Optional hostel filter
        room_id: Optional room filter
        search: Optional search query
        status_filter: Optional status filter
        academic_year: Optional academic year filter
        course: Optional course filter
        page: Page number for pagination
        page_size: Number of items per page
        sort_by: Field to sort by
        sort_order: Sort direction (asc/desc)
        student_service: Injected student service
        current_user: Authenticated user from dependency
        
    Returns:
        PaginatedResponse[StudentListItem]: Paginated list of students
    """
    filters = {
        "hostel_id": str(hostel_id) if hostel_id else None,
        "room_id": str(room_id) if room_id else None,
        "search": search,
        "status": status_filter.value if status_filter else None,
        "academic_year": academic_year,
        "course": course,
        "page": page,
        "page_size": page_size,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }
    
    result = student_service.list_students_with_filters(filters=filters)
    return result.unwrap()


@router.get(
    "/stats",
    response_model=StudentStats,
    status_code=status.HTTP_200_OK,
    summary="Get student statistics",
    description="Retrieve aggregated statistics about students.",
)
async def get_student_stats(
    hostel_id: Optional[UUID] = Query(None, description="Filter by hostel"),
    student_service: StudentService = Depends(get_student_service),
    current_user: User = Depends(get_current_user),
) -> StudentStats:
    """
    Get aggregated student statistics.
    
    Includes:
    - Total student count
    - Status breakdown (active, inactive, graduated, etc.)
    - Gender distribution
    - Occupancy statistics
    - Academic year distribution
    
    Args:
        hostel_id: Optional hostel filter
        student_service: Injected student service
        current_user: Authenticated user from dependency
        
    Returns:
        StudentStats: Aggregated statistics
    """
    result = student_service.get_student_statistics(
        hostel_id=str(hostel_id) if hostel_id else None
    )
    return result.unwrap()


@router.get(
    "/{student_id}",
    response_model=StudentDetail,
    status_code=status.HTTP_200_OK,
    summary="Get student details",
    description="Retrieve detailed information about a specific student.",
    responses={
        200: {"description": "Student details retrieved successfully"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Student not found"},
    },
)
async def get_student(
    student_id: UUID = Path(..., description="Unique student identifier"),
    student_service: StudentService = Depends(get_student_service),
    current_user: User = Depends(get_current_user),
) -> StudentDetail:
    """
    Get comprehensive details about a specific student.
    
    Includes:
    - Basic information
    - Current hostel and room assignment
    - Academic details
    - Contact information
    - Status and enrollment dates
    
    Args:
        student_id: UUID of the student
        student_service: Injected student service
        current_user: Authenticated user from dependency
        
    Returns:
        StudentDetail: Comprehensive student information
    """
    result = student_service.get_student(student_id=str(student_id))
    return result.unwrap()


@router.patch(
    "/{student_id}",
    response_model=StudentDetail,
    status_code=status.HTTP_200_OK,
    summary="Update student record",
    description="Update specific fields of a student record.",
    responses={
        200: {"description": "Student updated successfully"},
        400: {"description": "Invalid update data"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Student not found"},
    },
)
async def update_student(
    student_id: UUID = Path(..., description="Unique student identifier"),
    payload: StudentUpdate = Body(..., description="Student update data"),
    student_service: StudentService = Depends(get_student_service),
    current_user: User = Depends(get_current_user),
) -> StudentDetail:
    """
    Update student information.
    
    Only provided fields will be updated.
    
    Args:
        student_id: UUID of the student
        payload: Fields to update
        student_service: Injected student service
        current_user: Authenticated user from dependency
        
    Returns:
        StudentDetail: Updated student details
    """
    result = student_service.update_student(
        student_id=str(student_id),
        data=payload.dict(exclude_unset=True),
        updated_by=current_user.id,
    )
    return result.unwrap()


@router.delete(
    "/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete student record",
    description="Soft delete a student record (marks as inactive).",
    responses={
        204: {"description": "Student deleted successfully"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Student not found"},
        409: {"description": "Conflict - Student has active bookings or dues"},
    },
)
async def delete_student(
    student_id: UUID = Path(..., description="Unique student identifier"),
    hard_delete: bool = Query(
        False,
        description="Permanently delete (requires admin)",
    ),
    student_service: StudentService = Depends(get_student_service),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Delete a student record.
    
    By default, performs soft delete (marks as inactive).
    Hard delete permanently removes the record (admin only).
    
    Validates:
    - No active bookings exist
    - No pending payments or dues
    - No active complaints
    
    Args:
        student_id: UUID of the student
        hard_delete: Whether to permanently delete
        student_service: Injected student service
        current_user: Authenticated user from dependency
        
    Returns:
        None: 204 No Content on success
    """
    student_service.delete_student(
        student_id=str(student_id),
        hard_delete=hard_delete,
        deleted_by=current_user.id,
    ).unwrap()


# ==================== Student Lifecycle Endpoints ====================


@router.post(
    "/{student_id}/onboard",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Onboard student from booking",
    description="Complete student onboarding process from an approved booking.",
    responses={
        200: {"description": "Student onboarded successfully"},
        400: {"description": "Invalid booking or student already onboarded"},
        404: {"description": "Student or booking not found"},
    },
)
async def onboard_student(
    student_id: UUID = Path(..., description="Unique student identifier"),
    payload: OnboardingRequest = Body(..., description="Onboarding details"),
    onboarding_service: StudentOnboardingService = Depends(get_onboarding_service),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Onboard a student from an approved booking.
    
    This process:
    1. Validates the booking
    2. Assigns room to student
    3. Generates payment schedule
    4. Creates initial attendance record
    5. Sends welcome notifications
    
    Args:
        student_id: UUID of the student
        payload: Onboarding details including booking ID
        onboarding_service: Injected onboarding service
        current_user: Authenticated user from dependency
        
    Returns:
        dict: Onboarding result with assigned room and next steps
    """
    result = onboarding_service.onboard_from_booking(
        student_id=str(student_id),
        booking_id=payload.booking_id,
        onboarding_date=payload.onboarding_date,
        documents_verified=payload.documents_verified,
        initiated_by=current_user.id,
    )
    return result.unwrap()


@router.post(
    "/{student_id}/checkout",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Initiate student checkout",
    description="Process student checkout and room vacation.",
    responses={
        200: {"description": "Checkout initiated successfully"},
        400: {"description": "Pending dues or incomplete clearance"},
        404: {"description": "Student not found"},
    },
)
async def checkout_student(
    student_id: UUID = Path(..., description="Unique student identifier"),
    payload: CheckoutRequest = Body(..., description="Checkout details"),
    checkout_service: StudentCheckoutService = Depends(get_checkout_service),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Initiate student checkout process.
    
    This process:
    1. Validates no pending dues exist
    2. Checks clearance status (library, mess, etc.)
    3. Schedules room inspection
    4. Vacates room assignment
    5. Updates student status
    6. Generates clearance certificate
    
    Args:
        student_id: UUID of the student
        payload: Checkout details including reason and dates
        checkout_service: Injected checkout service
        current_user: Authenticated user from dependency
        
    Returns:
        dict: Checkout result with clearance status
    """
    result = checkout_service.checkout_student(
        student_id=str(student_id),
        checkout_date=payload.checkout_date,
        reason=payload.reason,
        forwarding_address=payload.forwarding_address,
        initiated_by=current_user.id,
    )
    return result.unwrap()


@router.post(
    "/{student_id}/reactivate",
    response_model=StudentDetail,
    status_code=status.HTTP_200_OK,
    summary="Reactivate student",
    description="Reactivate an inactive or graduated student.",
)
async def reactivate_student(
    student_id: UUID = Path(..., description="Unique student identifier"),
    reason: str = Body(..., embed=True, description="Reason for reactivation"),
    student_service: StudentService = Depends(get_student_service),
    current_user: User = Depends(get_current_user),
) -> StudentDetail:
    """
    Reactivate an inactive student.
    
    Args:
        student_id: UUID of the student
        reason: Reason for reactivation
        student_service: Injected student service
        current_user: Authenticated user from dependency
        
    Returns:
        StudentDetail: Updated student details
    """
    result = student_service.reactivate_student(
        student_id=str(student_id),
        reason=reason,
        reactivated_by=current_user.id,
    )
    return result.unwrap()


# ==================== Bulk Operations ====================


@router.post(
    "/bulk-update-status",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Bulk update student status",
    description="Update status for multiple students at once.",
    responses={
        200: {"description": "Bulk update completed"},
        400: {"description": "Invalid student IDs or status"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - Insufficient permissions"},
    },
)
async def bulk_update_status(
    payload: BulkStatusUpdate = Body(..., description="Bulk update data"),
    student_service: StudentService = Depends(get_student_service),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Update status for multiple students in a single operation.
    
    Useful for:
    - Batch graduation processing
    - Semester transitions
    - Mass status updates
    
    Args:
        payload: List of student IDs and new status
        student_service: Injected student service
        current_user: Authenticated user from dependency
        
    Returns:
        dict: Update results with success/failure counts
    """
    result = student_service.bulk_update_status(
        student_ids=[str(sid) for sid in payload.student_ids],
        new_status=payload.new_status,
        reason=payload.reason,
        updated_by=current_user.id,
    )
    return result.unwrap()


@router.post(
    "/bulk-assign-room",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Bulk assign students to rooms",
    description="Assign multiple students to rooms in batch.",
)
async def bulk_assign_room(
    assignments: List[dict] = Body(
        ...,
        description="List of student-room assignments",
    ),
    student_service: StudentService = Depends(get_student_service),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Assign multiple students to rooms in batch.
    
    Each assignment should contain:
    - student_id: UUID of the student
    - room_id: UUID of the target room
    
    Args:
        assignments: List of student-room mappings
        student_service: Injected student service
        current_user: Authenticated user from dependency
        
    Returns:
        dict: Assignment results with success/failure details
    """
    result = student_service.bulk_assign_rooms(
        assignments=assignments,
        assigned_by=current_user.id,
    )
    return result.unwrap()


@router.get(
    "/export",
    status_code=status.HTTP_200_OK,
    summary="Export student data",
    description="Export student data in various formats (CSV, Excel, PDF).",
)
async def export_students(
    format: str = Query("csv", regex="^(csv|xlsx|pdf)$"),
    hostel_id: Optional[UUID] = Query(None),
    status_filter: Optional[StudentStatus] = Query(None),
    student_service: StudentService = Depends(get_student_service),
    current_user: User = Depends(get_current_user),
):
    """
    Export student data for reporting.
    
    Supports multiple formats:
    - CSV: Comma-separated values
    - XLSX: Excel spreadsheet
    - PDF: Formatted report
    
    Args:
        format: Export format (csv/xlsx/pdf)
        hostel_id: Optional hostel filter
        status_filter: Optional status filter
        student_service: Injected student service
        current_user: Authenticated user from dependency
        
    Returns:
        FileResponse: Exported file
    """
    result = student_service.export_students(
        export_format=format,
        filters={
            "hostel_id": str(hostel_id) if hostel_id else None,
            "status": status_filter.value if status_filter else None,
        },
    )
    return result.unwrap()