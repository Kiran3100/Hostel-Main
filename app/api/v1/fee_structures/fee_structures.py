"""
Fee Structure Management Endpoints

This module provides comprehensive CRUD operations for:
- Fee structure management
- Charge component configuration
- Discount rule administration
"""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.fee_structure import (
    FeeStructureCreate,
    FeeStructureUpdate,
    FeeStructureResponse,
    FeeStructureList,
    FeeDetail,
    ChargeComponent,
    ChargeComponentCreate,
    DiscountConfiguration,
    DiscountCreate,
)
from app.services.fee_structure.fee_structure_service import FeeStructureService
from app.services.fee_structure.charge_component_service import ChargeComponentService

# Router configuration
router = APIRouter(
    prefix="/fee-structures",
    tags=["fee-structures"]
)


# Dependency injection for services
def get_fee_service(
    db: Session = Depends(deps.get_db)
) -> FeeStructureService:
    """
    Dependency provider for FeeStructureService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        FeeStructureService: Initialized service instance
    """
    return FeeStructureService(db=db)


def get_charge_service(
    db: Session = Depends(deps.get_db)
) -> ChargeComponentService:
    """
    Dependency provider for ChargeComponentService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        ChargeComponentService: Initialized service instance
    """
    return ChargeComponentService(db=db)


# ===========================================================================
# Fee Structure CRUD Operations
# ===========================================================================


@router.post(
    "",
    response_model=FeeStructureResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new fee structure",
    description="""
    Create a new fee structure for a hostel.
    
    **Required Fields:**
    - Hostel ID
    - Structure name
    - Base pricing configuration
    
    **Optional Fields:**
    - Seasonal adjustments
    - Custom charge components
    - Discount rules
    """,
    responses={
        201: {
            "description": "Fee structure created successfully",
            "model": FeeStructureResponse
        },
        400: {
            "description": "Invalid request data"
        },
        401: {
            "description": "Unauthorized - Admin access required"
        },
        409: {
            "description": "Conflict - Fee structure already exists"
        },
        422: {
            "description": "Validation error"
        }
    }
)
def create_fee_structure(
    payload: FeeStructureCreate,
    _admin=Depends(deps.get_admin_user),
    service: FeeStructureService = Depends(get_fee_service),
) -> Any:
    """
    Create a new fee structure with admin authorization.
    
    Args:
        payload: Fee structure creation data
        _admin: Authenticated admin user
        service: Fee structure service instance
        
    Returns:
        FeeStructureResponse: Created fee structure details
        
    Raises:
        HTTPException: If creation fails or validation errors occur
    """
    try:
        return service.create_structure(
            payload=payload,
            creator_id=_admin.id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create fee structure"
        )


@router.get(
    "/{structure_id}",
    response_model=FeeDetail,
    status_code=status.HTTP_200_OK,
    summary="Retrieve fee structure details",
    description="""
    Fetch complete details of a specific fee structure including:
    - Base configuration
    - Charge components
    - Discount rules
    - Historical changes
    """,
    responses={
        200: {
            "description": "Fee structure retrieved successfully",
            "model": FeeDetail
        },
        401: {
            "description": "Unauthorized - Admin access required"
        },
        404: {
            "description": "Fee structure not found"
        }
    }
)
def get_fee_structure(
    structure_id: str,
    _admin=Depends(deps.get_admin_user),
    service: FeeStructureService = Depends(get_fee_service),
) -> Any:
    """
    Retrieve detailed information about a specific fee structure.
    
    Args:
        structure_id: Unique identifier of the fee structure
        _admin: Authenticated admin user
        service: Fee structure service instance
        
    Returns:
        FeeDetail: Complete fee structure details
        
    Raises:
        HTTPException: If structure not found
    """
    structure = service.get_structure_by_id(structure_id)
    
    if not structure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fee structure not found: {structure_id}"
        )
    
    return structure


@router.put(
    "/{structure_id}",
    response_model=FeeStructureResponse,
    status_code=status.HTTP_200_OK,
    summary="Update existing fee structure",
    description="""
    Update an existing fee structure. All changes are audited.
    
    **Updatable Fields:**
    - Structure name
    - Pricing configuration
    - Active status
    - Effective dates
    
    **Note:** Historical records are preserved for audit purposes.
    """,
    responses={
        200: {
            "description": "Fee structure updated successfully",
            "model": FeeStructureResponse
        },
        400: {
            "description": "Invalid update data"
        },
        401: {
            "description": "Unauthorized - Admin access required"
        },
        404: {
            "description": "Fee structure not found"
        },
        422: {
            "description": "Validation error"
        }
    }
)
def update_fee_structure(
    structure_id: str,
    payload: FeeStructureUpdate,
    _admin=Depends(deps.get_admin_user),
    service: FeeStructureService = Depends(get_fee_service),
) -> Any:
    """
    Update an existing fee structure with admin authorization.
    
    Args:
        structure_id: Unique identifier of the fee structure
        payload: Update data
        _admin: Authenticated admin user
        service: Fee structure service instance
        
    Returns:
        FeeStructureResponse: Updated fee structure
        
    Raises:
        HTTPException: If update fails or structure not found
    """
    try:
        updated_structure = service.update_structure(
            structure_id=structure_id,
            payload=payload,
            updater_id=_admin.id
        )
        
        if not updated_structure:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fee structure not found: {structure_id}"
            )
        
        return updated_structure
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update fee structure"
        )


@router.delete(
    "/{structure_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete fee structure",
    description="""
    Soft delete a fee structure. The structure is marked as inactive
    but retained for historical reference and audit purposes.
    
    **Important:** Active bookings using this structure are not affected.
    """,
    responses={
        204: {
            "description": "Fee structure deleted successfully"
        },
        401: {
            "description": "Unauthorized - Admin access required"
        },
        404: {
            "description": "Fee structure not found"
        },
        409: {
            "description": "Conflict - Cannot delete structure with active bookings"
        }
    }
)
def delete_fee_structure(
    structure_id: str,
    force: bool = Query(
        default=False,
        description="Force deletion even with active references"
    ),
    _admin=Depends(deps.get_admin_user),
    service: FeeStructureService = Depends(get_fee_service),
) -> None:
    """
    Soft delete a fee structure.
    
    Args:
        structure_id: Unique identifier of the fee structure
        force: Whether to force deletion with active references
        _admin: Authenticated admin user
        service: Fee structure service instance
        
    Returns:
        None
        
    Raises:
        HTTPException: If deletion fails or structure not found
    """
    try:
        deleted = service.delete_structure(
            structure_id=structure_id,
            force=force,
            deleter_id=_admin.id
        )
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fee structure not found: {structure_id}"
            )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete fee structure"
        )


@router.get(
    "",
    response_model=FeeStructureList,
    status_code=status.HTTP_200_OK,
    summary="List fee structures",
    description="""
    Retrieve a paginated list of fee structures for a specific hostel.
    
    **Filtering Options:**
    - Active/inactive status
    - Date range
    - Structure type
    
    **Sorting Options:**
    - Creation date
    - Name
    - Last modified
    """,
    responses={
        200: {
            "description": "Fee structures retrieved successfully",
            "model": FeeStructureList
        },
        401: {
            "description": "Unauthorized - Admin access required"
        },
        422: {
            "description": "Invalid query parameters"
        }
    }
)
def list_fee_structures(
    hostel_id: str = Query(
        ...,
        description="Hostel ID to filter structures",
        min_length=1,
        max_length=100
    ),
    active_only: bool = Query(
        default=True,
        description="Return only active structures"
    ),
    pagination=Depends(deps.get_pagination_params),
    _admin=Depends(deps.get_admin_user),
    service: FeeStructureService = Depends(get_fee_service),
) -> Any:
    """
    List all fee structures for a hostel with pagination.
    
    Args:
        hostel_id: Unique identifier of the hostel
        active_only: Filter for active structures only
        pagination: Pagination parameters
        _admin: Authenticated admin user
        service: Fee structure service instance
        
    Returns:
        FeeStructureList: Paginated list of fee structures
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        return service.list_structures(
            hostel_id=hostel_id,
            active_only=active_only,
            pagination=pagination
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve fee structures"
        )


# ===========================================================================
# Charge Component Management
# ===========================================================================


@router.get(
    "/{structure_id}/components",
    response_model=List[ChargeComponent],
    status_code=status.HTTP_200_OK,
    summary="List charge components",
    description="""
    Retrieve all charge components associated with a fee structure.
    
    **Component Types:**
    - Base rent
    - Utilities
    - Maintenance fees
    - Security deposits
    - Additional services
    """,
    responses={
        200: {
            "description": "Components retrieved successfully",
            "model": List[ChargeComponent]
        },
        401: {
            "description": "Unauthorized - Admin access required"
        },
        404: {
            "description": "Fee structure not found"
        }
    }
)
def list_components(
    structure_id: str,
    component_type: str = Query(
        None,
        description="Filter by component type"
    ),
    active_only: bool = Query(
        default=True,
        description="Return only active components"
    ),
    _admin=Depends(deps.get_admin_user),
    service: ChargeComponentService = Depends(get_charge_service),
) -> Any:
    """
    List all charge components for a fee structure.
    
    Args:
        structure_id: Unique identifier of the fee structure
        component_type: Optional filter by component type
        active_only: Filter for active components only
        _admin: Authenticated admin user
        service: Charge component service instance
        
    Returns:
        List[ChargeComponent]: List of charge components
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        components = service.list_components(
            structure_id=structure_id,
            component_type=component_type,
            active_only=active_only
        )
        return components
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve charge components"
        )


@router.post(
    "/{structure_id}/components",
    response_model=ChargeComponent,
    status_code=status.HTTP_201_CREATED,
    summary="Add charge component",
    description="""
    Add a new charge component to a fee structure.
    
    **Required Fields:**
    - Component name
    - Charge type
    - Amount or calculation method
    
    **Optional Fields:**
    - Description
    - Tax applicability
    - Conditional rules
    """,
    responses={
        201: {
            "description": "Component created successfully",
            "model": ChargeComponent
        },
        400: {
            "description": "Invalid component data"
        },
        401: {
            "description": "Unauthorized - Admin access required"
        },
        404: {
            "description": "Fee structure not found"
        },
        422: {
            "description": "Validation error"
        }
    }
)
def add_component(
    structure_id: str,
    payload: ChargeComponentCreate,
    _admin=Depends(deps.get_admin_user),
    service: ChargeComponentService = Depends(get_charge_service),
) -> Any:
    """
    Add a new charge component to a fee structure.
    
    Args:
        structure_id: Unique identifier of the fee structure
        payload: Component creation data
        _admin: Authenticated admin user
        service: Charge component service instance
        
    Returns:
        ChargeComponent: Created charge component
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        component = service.create_component(
            structure_id=structure_id,
            payload=payload,
            creator_id=_admin.id
        )
        return component
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create charge component"
        )


@router.put(
    "/{structure_id}/components/{component_id}",
    response_model=ChargeComponent,
    status_code=status.HTTP_200_OK,
    summary="Update charge component",
    description="Update an existing charge component within a fee structure.",
    responses={
        200: {
            "description": "Component updated successfully",
            "model": ChargeComponent
        },
        400: {
            "description": "Invalid update data"
        },
        401: {
            "description": "Unauthorized - Admin access required"
        },
        404: {
            "description": "Component not found"
        }
    }
)
def update_component(
    structure_id: str,
    component_id: str,
    payload: ChargeComponentCreate,
    _admin=Depends(deps.get_admin_user),
    service: ChargeComponentService = Depends(get_charge_service),
) -> Any:
    """
    Update an existing charge component.
    
    Args:
        structure_id: Unique identifier of the fee structure
        component_id: Unique identifier of the component
        payload: Update data
        _admin: Authenticated admin user
        service: Charge component service instance
        
    Returns:
        ChargeComponent: Updated charge component
        
    Raises:
        HTTPException: If update fails
    """
    try:
        component = service.update_component(
            structure_id=structure_id,
            component_id=component_id,
            payload=payload,
            updater_id=_admin.id
        )
        
        if not component:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Component not found: {component_id}"
            )
        
        return component
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update charge component"
        )


@router.delete(
    "/{structure_id}/components/{component_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete charge component",
    description="Remove a charge component from a fee structure.",
    responses={
        204: {
            "description": "Component deleted successfully"
        },
        401: {
            "description": "Unauthorized - Admin access required"
        },
        404: {
            "description": "Component not found"
        }
    }
)
def delete_component(
    structure_id: str,
    component_id: str,
    _admin=Depends(deps.get_admin_user),
    service: ChargeComponentService = Depends(get_charge_service),
) -> None:
    """
    Delete a charge component from a fee structure.
    
    Args:
        structure_id: Unique identifier of the fee structure
        component_id: Unique identifier of the component
        _admin: Authenticated admin user
        service: Charge component service instance
        
    Returns:
        None
        
    Raises:
        HTTPException: If deletion fails
    """
    try:
        deleted = service.delete_component(
            structure_id=structure_id,
            component_id=component_id,
            deleter_id=_admin.id
        )
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Component not found: {component_id}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete charge component"
        )


# ===========================================================================
# Discount Configuration Management
# ===========================================================================


@router.get(
    "/discounts",
    response_model=List[DiscountConfiguration],
    status_code=status.HTTP_200_OK,
    summary="List discount configurations",
    description="""
    Retrieve all discount configurations for a hostel.
    
    **Discount Types:**
    - Early bird discounts
    - Long-stay discounts
    - Seasonal promotions
    - Referral discounts
    - Custom promotional codes
    """,
    responses={
        200: {
            "description": "Discounts retrieved successfully",
            "model": List[DiscountConfiguration]
        },
        401: {
            "description": "Unauthorized - Admin access required"
        },
        422: {
            "description": "Invalid query parameters"
        }
    }
)
def list_discounts(
    hostel_id: str = Query(
        ...,
        description="Hostel ID to filter discounts",
        min_length=1,
        max_length=100
    ),
    active_only: bool = Query(
        default=True,
        description="Return only active discounts"
    ),
    discount_type: str = Query(
        None,
        description="Filter by discount type"
    ),
    _admin=Depends(deps.get_admin_user),
    service: ChargeComponentService = Depends(get_charge_service),
) -> Any:
    """
    List all discount configurations for a hostel.
    
    Args:
        hostel_id: Unique identifier of the hostel
        active_only: Filter for active discounts only
        discount_type: Optional filter by discount type
        _admin: Authenticated admin user
        service: Charge component service instance
        
    Returns:
        List[DiscountConfiguration]: List of discount configurations
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        discounts = service.list_discounts(
            hostel_id=hostel_id,
            active_only=active_only,
            discount_type=discount_type
        )
        return discounts
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve discounts"
        )


@router.post(
    "/discounts",
    response_model=DiscountConfiguration,
    status_code=status.HTTP_201_CREATED,
    summary="Create discount configuration",
    description="""
    Create a new discount configuration.
    
    **Configuration Options:**
    - Percentage or fixed amount
    - Validity period
    - Usage limits
    - Applicable fee structures
    - Stacking rules
    """,
    responses={
        201: {
            "description": "Discount created successfully",
            "model": DiscountConfiguration
        },
        400: {
            "description": "Invalid discount data"
        },
        401: {
            "description": "Unauthorized - Admin access required"
        },
        422: {
            "description": "Validation error"
        }
    }
)
def create_discount(
    payload: DiscountCreate,
    _admin=Depends(deps.get_admin_user),
    service: ChargeComponentService = Depends(get_charge_service),
) -> Any:
    """
    Create a new discount configuration.
    
    Args:
        payload: Discount creation data
        _admin: Authenticated admin user
        service: Charge component service instance
        
    Returns:
        DiscountConfiguration: Created discount configuration
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        discount = service.create_discount(
            payload=payload,
            creator_id=_admin.id
        )
        return discount
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create discount"
        )


@router.put(
    "/discounts/{discount_id}",
    response_model=DiscountConfiguration,
    status_code=status.HTTP_200_OK,
    summary="Update discount configuration",
    description="Update an existing discount configuration.",
    responses={
        200: {
            "description": "Discount updated successfully",
            "model": DiscountConfiguration
        },
        400: {
            "description": "Invalid update data"
        },
        401: {
            "description": "Unauthorized - Admin access required"
        },
        404: {
            "description": "Discount not found"
        }
    }
)
def update_discount(
    discount_id: str,
    payload: DiscountCreate,
    _admin=Depends(deps.get_admin_user),
    service: ChargeComponentService = Depends(get_charge_service),
) -> Any:
    """
    Update an existing discount configuration.
    
    Args:
        discount_id: Unique identifier of the discount
        payload: Update data
        _admin: Authenticated admin user
        service: Charge component service instance
        
    Returns:
        DiscountConfiguration: Updated discount configuration
        
    Raises:
        HTTPException: If update fails
    """
    try:
        discount = service.update_discount(
            discount_id=discount_id,
            payload=payload,
            updater_id=_admin.id
        )
        
        if not discount:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Discount not found: {discount_id}"
            )
        
        return discount
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update discount"
        )


@router.delete(
    "/discounts/{discount_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete discount configuration",
    description="Remove a discount configuration.",
    responses={
        204: {
            "description": "Discount deleted successfully"
        },
        401: {
            "description": "Unauthorized - Admin access required"
        },
        404: {
            "description": "Discount not found"
        }
    }
)
def delete_discount(
    discount_id: str,
    _admin=Depends(deps.get_admin_user),
    service: ChargeComponentService = Depends(get_charge_service),
) -> None:
    """
    Delete a discount configuration.
    
    Args:
        discount_id: Unique identifier of the discount
        _admin: Authenticated admin user
        service: Charge component service instance
        
    Returns:
        None
        
    Raises:
        HTTPException: If deletion fails
    """
    try:
        deleted = service.delete_discount(
            discount_id=discount_id,
            deleter_id=_admin.id
        )
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Discount not found: {discount_id}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete discount"
        )