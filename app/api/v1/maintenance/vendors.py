"""
Maintenance Vendors API Endpoints
Handles vendor management, performance tracking, and vendor assignments.
"""

from typing import Any, List, Optional
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Path,
    Body,
    status,
)
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.maintenance.maintenance_vendor import (
    MaintenanceVendor,
    VendorCreate,
    VendorUpdate,
    VendorPerformanceReview,
    VendorPerformanceCreate,
    VendorMetrics,
    VendorContract,
    VendorContractCreate,
)
from app.services.maintenance.maintenance_vendor_service import (
    MaintenanceVendorService,
)

# Initialize router with prefix and tags
router = APIRouter(prefix="/vendors", tags=["maintenance:vendors"])


def get_vendor_service(
    db: Session = Depends(deps.get_db),
) -> MaintenanceVendorService:
    """
    Dependency to get maintenance vendor service instance.
    
    Args:
        db: Database session dependency
        
    Returns:
        MaintenanceVendorService: Service instance for vendor operations
    """
    return MaintenanceVendorService(db=db)


@router.post(
    "",
    response_model=MaintenanceVendor,
    status_code=status.HTTP_201_CREATED,
    summary="Create vendor",
    description="Register a new maintenance vendor with contact and service details",
    response_description="Created vendor details",
)
def create_vendor(
    payload: VendorCreate = Body(..., description="Vendor creation details"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceVendorService = Depends(get_vendor_service),
) -> Any:
    """
    Create a new maintenance vendor.
    
    Registers vendor with contact information, service categories,
    and initial performance metrics.
    
    Args:
        payload: Vendor creation details including contact and services
        admin: Authenticated admin user creating the vendor
        service: Maintenance vendor service instance
        
    Returns:
        MaintenanceVendor: Created vendor details
        
    Raises:
        HTTPException: If vendor creation fails or duplicate vendor exists
    """
    try:
        return service.create_vendor(payload, creator_id=admin.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create vendor",
        )


@router.get(
    "",
    response_model=List[MaintenanceVendor],
    summary="List vendors",
    description="Retrieve all registered maintenance vendors for a hostel",
    response_description="List of vendors",
)
def list_vendors(
    hostel_id: str = Query(..., description="Hostel ID to filter vendors"),
    service_category: Optional[str] = Query(
        None,
        description="Filter by service category (plumbing, electrical, etc.)",
    ),
    active_only: bool = Query(
        True,
        description="Show only active vendors",
    ),
    min_rating: Optional[float] = Query(
        None,
        ge=0.0,
        le=5.0,
        description="Minimum performance rating filter",
    ),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceVendorService = Depends(get_vendor_service),
) -> Any:
    """
    List all maintenance vendors.
    
    Supports filtering by service category, active status, and performance rating.
    
    Args:
        hostel_id: Hostel ID to filter vendors
        service_category: Optional service category filter
        active_only: Whether to show only active vendors
        min_rating: Minimum performance rating filter
        admin: Authenticated admin user
        service: Maintenance vendor service instance
        
    Returns:
        List[MaintenanceVendor]: List of vendors matching filters
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        return service.list_vendors_for_hostel(
            hostel_id,
            service_category=service_category,
            active_only=active_only,
            min_rating=min_rating,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve vendors",
        )


@router.get(
    "/{vendor_id}",
    response_model=MaintenanceVendor,
    summary="Get vendor details",
    description="Retrieve detailed information about a specific vendor",
    response_description="Vendor details",
)
def get_vendor(
    vendor_id: str = Path(..., description="Unique identifier of the vendor"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceVendorService = Depends(get_vendor_service),
) -> Any:
    """
    Get detailed information about a vendor.
    
    Args:
        vendor_id: Unique identifier of the vendor
        admin: Authenticated admin user
        service: Maintenance vendor service instance
        
    Returns:
        MaintenanceVendor: Vendor details
        
    Raises:
        HTTPException: If vendor not found
    """
    try:
        vendor = service.get_vendor(vendor_id)
        if not vendor:
            raise LookupError(f"Vendor with ID {vendor_id} not found")
        return vendor
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve vendor details",
        )


@router.put(
    "/{vendor_id}",
    response_model=MaintenanceVendor,
    summary="Update vendor details",
    description="Update vendor information including contact details and service categories",
    response_description="Updated vendor details",
)
def update_vendor(
    vendor_id: str = Path(..., description="Unique identifier of the vendor"),
    payload: VendorUpdate = Body(..., description="Vendor update details"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceVendorService = Depends(get_vendor_service),
) -> Any:
    """
    Update vendor details.
    
    Allows updating contact information, service categories, and status.
    
    Args:
        vendor_id: Unique identifier of the vendor
        payload: Update details
        admin: Authenticated admin user
        service: Maintenance vendor service instance
        
    Returns:
        MaintenanceVendor: Updated vendor details
        
    Raises:
        HTTPException: If update fails or vendor not found
    """
    try:
        return service.update_vendor(vendor_id, payload, actor_id=admin.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update vendor",
        )


@router.delete(
    "/{vendor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate vendor",
    description="Deactivate a vendor (soft delete)",
)
def deactivate_vendor(
    vendor_id: str = Path(..., description="Unique identifier of the vendor"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceVendorService = Depends(get_vendor_service),
) -> None:
    """
    Deactivate a vendor.
    
    Vendors are soft-deleted to maintain historical records and contract information.
    
    Args:
        vendor_id: Unique identifier of the vendor
        admin: Authenticated admin user
        service: Maintenance vendor service instance
        
    Raises:
        HTTPException: If deactivation fails or vendor not found
    """
    try:
        service.deactivate_vendor(vendor_id, actor_id=admin.id)
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate vendor",
        )


@router.post(
    "/{vendor_id}/review",
    response_model=VendorPerformanceReview,
    status_code=status.HTTP_201_CREATED,
    summary="Submit vendor performance review",
    description="Submit a performance review for a vendor after task completion",
    response_description="Created performance review",
)
def review_vendor(
    vendor_id: str = Path(..., description="Unique identifier of the vendor"),
    payload: VendorPerformanceCreate = Body(..., description="Performance review details"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceVendorService = Depends(get_vendor_service),
) -> Any:
    """
    Submit a performance review for a vendor.
    
    Reviews are submitted after task completion and impact vendor ratings.
    
    Args:
        vendor_id: Unique identifier of the vendor
        payload: Performance review details including ratings and feedback
        admin: Authenticated admin user submitting review
        service: Maintenance vendor service instance
        
    Returns:
        VendorPerformanceReview: Created review record
        
    Raises:
        HTTPException: If review submission fails or vendor not found
    """
    try:
        return service.create_performance_review(
            vendor_id,
            payload,
            reviewer_id=admin.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit vendor review",
        )


@router.get(
    "/{vendor_id}/reviews",
    response_model=List[VendorPerformanceReview],
    summary="Get vendor reviews",
    description="Retrieve all performance reviews for a vendor",
    response_description="List of performance reviews",
)
def get_vendor_reviews(
    vendor_id: str = Path(..., description="Unique identifier of the vendor"),
    start_date: Optional[date] = Query(
        None,
        description="Filter reviews from this date",
    ),
    end_date: Optional[date] = Query(
        None,
        description="Filter reviews up to this date",
    ),
    min_rating: Optional[float] = Query(
        None,
        ge=0.0,
        le=5.0,
        description="Minimum rating filter",
    ),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceVendorService = Depends(get_vendor_service),
) -> Any:
    """
    Get all performance reviews for a vendor.
    
    Helps track vendor performance over time and identify trends.
    
    Args:
        vendor_id: Unique identifier of the vendor
        start_date: Optional start date filter
        end_date: Optional end date filter
        min_rating: Minimum rating filter
        admin: Authenticated admin user
        service: Maintenance vendor service instance
        
    Returns:
        List[VendorPerformanceReview]: List of reviews
        
    Raises:
        HTTPException: If retrieval fails or vendor not found
    """
    try:
        return service.get_vendor_reviews(
            vendor_id,
            start_date=start_date,
            end_date=end_date,
            min_rating=min_rating,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve vendor reviews",
        )


@router.get(
    "/{vendor_id}/metrics",
    response_model=VendorMetrics,
    summary="Get vendor performance metrics",
    description="Retrieve comprehensive performance metrics and statistics for a vendor",
    response_description="Vendor performance metrics",
)
def get_vendor_metrics(
    vendor_id: str = Path(..., description="Unique identifier of the vendor"),
    period_months: int = Query(
        12,
        ge=1,
        le=36,
        description="Period in months for metrics calculation",
    ),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceVendorService = Depends(get_vendor_service),
) -> Any:
    """
    Get comprehensive performance metrics for a vendor.
    
    Includes average ratings, completion rates, response times, and cost analysis.
    
    Args:
        vendor_id: Unique identifier of the vendor
        period_months: Period for metrics calculation (1-36 months)
        admin: Authenticated admin user
        service: Maintenance vendor service instance
        
    Returns:
        VendorMetrics: Comprehensive performance metrics
        
    Raises:
        HTTPException: If retrieval fails or vendor not found
    """
    try:
        return service.get_vendor_metrics(vendor_id, period_months=period_months)
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve vendor metrics",
        )


@router.post(
    "/{vendor_id}/contracts",
    response_model=VendorContract,
    status_code=status.HTTP_201_CREATED,
    summary="Create vendor contract",
    description="Create a new contract with a vendor",
    response_description="Created contract details",
)
def create_vendor_contract(
    vendor_id: str = Path(..., description="Unique identifier of the vendor"),
    payload: VendorContractCreate = Body(..., description="Contract details"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceVendorService = Depends(get_vendor_service),
) -> Any:
    """
    Create a contract with a vendor.
    
    Contracts define terms, rates, and service level agreements.
    
    Args:
        vendor_id: Unique identifier of the vendor
        payload: Contract details including terms and rates
        admin: Authenticated admin user
        service: Maintenance vendor service instance
        
    Returns:
        VendorContract: Created contract details
        
    Raises:
        HTTPException: If contract creation fails
    """
    try:
        return service.create_vendor_contract(
            vendor_id,
            payload,
            creator_id=admin.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create vendor contract",
        )


@router.get(
    "/{vendor_id}/contracts",
    response_model=List[VendorContract],
    summary="Get vendor contracts",
    description="Retrieve all contracts for a vendor",
    response_description="List of vendor contracts",
)
def get_vendor_contracts(
    vendor_id: str = Path(..., description="Unique identifier of the vendor"),
    active_only: bool = Query(
        True,
        description="Show only active contracts",
    ),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceVendorService = Depends(get_vendor_service),
) -> Any:
    """
    Get all contracts for a vendor.
    
    Args:
        vendor_id: Unique identifier of the vendor
        active_only: Whether to show only active contracts
        admin: Authenticated admin user
        service: Maintenance vendor service instance
        
    Returns:
        List[VendorContract]: List of contracts
        
    Raises:
        HTTPException: If retrieval fails or vendor not found
    """
    try:
        return service.get_vendor_contracts(
            vendor_id,
            active_only=active_only,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve vendor contracts",
        )


@router.get(
    "/recommendations",
    response_model=List[MaintenanceVendor],
    summary="Get vendor recommendations",
    description="Get recommended vendors for a specific service category based on performance",
    response_description="List of recommended vendors",
)
def get_vendor_recommendations(
    hostel_id: str = Query(..., description="Hostel ID"),
    service_category: str = Query(..., description="Service category"),
    limit: int = Query(5, ge=1, le=20, description="Maximum number of recommendations"),
    admin=Depends(deps.get_admin_user),
    service: MaintenanceVendorService = Depends(get_vendor_service),
) -> Any:
    """
    Get vendor recommendations based on performance metrics.
    
    Recommends vendors with best ratings and track record for specific service categories.
    
    Args:
        hostel_id: Hostel ID
        service_category: Required service category
        limit: Maximum number of recommendations
        admin: Authenticated admin user
        service: Maintenance vendor service instance
        
    Returns:
        List[MaintenanceVendor]: Recommended vendors sorted by performance
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        return service.get_vendor_recommendations(
            hostel_id=hostel_id,
            service_category=service_category,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get vendor recommendations",
        )