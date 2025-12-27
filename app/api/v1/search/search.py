"""
Main search endpoints for hostel discovery.

Provides comprehensive search functionality including:
- Basic keyword search across hostel data
- Advanced search with complex filters and facets
- Geospatial nearby search with radius filtering
- Optional personalization for authenticated users
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.core.dependencies import AuthenticationDependency
from app.schemas.search import (
    AdvancedSearchRequest,
    FacetedSearchResponse,
    SearchMetadata,
    SearchResultItem,
)
from app.services.search.search_personalization_service import SearchPersonalizationService
from app.services.search.search_service import SearchService

# Router configuration
router = APIRouter(
    prefix="/search",
    tags=["Search"],
)


# ============================================================================
# Constants
# ============================================================================

DEFAULT_PAGE = 1
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MIN_LIMIT = 1

DEFAULT_RADIUS_KM = 10.0
MIN_RADIUS_KM = 0.1
MAX_RADIUS_KM = 500.0

MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0


# ============================================================================
# Dependencies
# ============================================================================


def get_search_service() -> SearchService:
    """
    Dependency injection for search service.
    
    Override this in your dependency configuration to provide
    the actual implementation.
    
    Raises:
        NotImplementedError: When not properly configured in DI container
    """
    raise NotImplementedError(
        "Search service dependency not configured. "
        "Please override this in your dependency injection setup."
    )


def get_personalization_service() -> SearchPersonalizationService:
    """
    Dependency injection for personalization service.
    
    Override this in your dependency configuration to provide
    the actual implementation.
    
    Raises:
        NotImplementedError: When not properly configured in DI container
    """
    raise NotImplementedError(
        "Personalization service dependency not configured. "
        "Please override this in your dependency injection setup."
    )


def get_current_user_optional(
    auth: AuthenticationDependency = Depends(),
) -> Optional[Any]:
    """
    Optional authentication dependency.
    
    Returns the current user if authenticated, None otherwise.
    Allows both authenticated and anonymous users to access search.
    
    Args:
        auth: Authentication dependency
        
    Returns:
        User object if authenticated, None otherwise
    """
    return auth.get_current_user_optional()


# ============================================================================
# Helper Functions
# ============================================================================


def extract_user_id(user: Optional[Any]) -> Optional[int]:
    """
    Safely extract user ID from user object.
    
    Args:
        user: Optional user object
        
    Returns:
        User ID if available, None otherwise
    """
    if user is None:
        return None
    return getattr(user, "id", None)


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/basic",
    response_model=FacetedSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Basic keyword search",
    description="""
    Simple keyword search across hostel data.
    
    Searches across:
    - Hostel names
    - Descriptions
    - City/location names
    - Amenities
    - Tags
    
    Features:
    - Full-text search with relevance scoring
    - Pagination support
    - Optional user-based ranking adjustments
    - Faceted results with aggregations
    """,
    responses={
        200: {
            "description": "Search results with metadata and facets",
            "content": {
                "application/json": {
                    "example": {
                        "results": [
                            {
                                "id": 123,
                                "name": "Central Hostel Paris",
                                "score": 0.92,
                                "type": "hostel"
                            }
                        ],
                        "metadata": {
                            "total": 45,
                            "page": 1,
                            "limit": 20,
                            "pages": 3
                        },
                        "facets": {
                            "city": {"Paris": 12, "Lyon": 8},
                            "price_range": {"0-20": 15, "20-50": 20}
                        }
                    }
                }
            }
        },
        400: {"description": "Invalid query parameters"},
        500: {"description": "Internal server error"}
    }
)
async def search_basic(
    q: str = Query(
        ...,
        min_length=1,
        max_length=200,
        description="Search query string",
        example="hostel paris wifi"
    ),
    page: int = Query(
        default=DEFAULT_PAGE,
        ge=1,
        description="Page number for pagination"
    ),
    limit: int = Query(
        default=DEFAULT_LIMIT,
        ge=MIN_LIMIT,
        le=MAX_LIMIT,
        description="Number of results per page"
    ),
    search_service: SearchService = Depends(get_search_service),
    current_user: Optional[Any] = Depends(get_current_user_optional),
) -> FacetedSearchResponse:
    """
    Execute basic keyword search across hostels.
    
    Args:
        q: Search query string
        page: Page number (1-indexed)
        limit: Results per page (1-100)
        search_service: Injected search service
        current_user: Optional authenticated user
        
    Returns:
        FacetedSearchResponse with results, metadata, and facets
        
    Raises:
        HTTPException: On service errors (handled by FastAPI)
    """
    user_id = extract_user_id(current_user)
    
    # Execute basic search
    result = search_service.search_basic(
        query=q.strip(),
        page=page,
        limit=limit,
        user_id=user_id,
    )
    
    return result.unwrap()


@router.post(
    "/advanced",
    response_model=FacetedSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Advanced search with filters",
    description="""
    Complex search with multiple filters and facets.
    
    Supports filtering by:
    - Price range (min/max)
    - Location (city, country, coordinates)
    - Amenities (WiFi, breakfast, parking, etc.)
    - Rating (minimum rating)
    - Availability (date ranges)
    - Property type (hostel, hotel, guesthouse)
    - Room types (dorm, private)
    
    Features:
    - Optional personalization based on user preferences
    - Multi-criteria filtering
    - Faceted search results
    - Sorting options (price, rating, distance, relevance)
    """,
    responses={
        200: {"description": "Filtered search results with facets"},
        400: {"description": "Invalid request parameters"},
        422: {"description": "Validation error in request body"},
        500: {"description": "Internal server error"}
    }
)
async def search_advanced(
    payload: AdvancedSearchRequest,
    search_service: SearchService = Depends(get_search_service),
    personalization_service: SearchPersonalizationService = Depends(get_personalization_service),
    current_user: Optional[Any] = Depends(get_current_user_optional),
) -> FacetedSearchResponse:
    """
    Execute advanced search with complex filters.
    
    Optionally applies personalization if user is authenticated and
    personalization is enabled in the request.
    
    Args:
        payload: Advanced search request with filters
        search_service: Injected search service
        personalization_service: Injected personalization service
        current_user: Optional authenticated user
        
    Returns:
        FacetedSearchResponse with filtered results and facets
        
    Raises:
        HTTPException: On service errors (handled by FastAPI)
    """
    user_id = extract_user_id(current_user)
    
    # Apply personalization if user is authenticated and requested
    if user_id and getattr(payload, "use_personalization", False):
        personalization_result = personalization_service.personalize_advanced_request(
            user_id=user_id,
            request=payload,
        )
        payload = personalization_result.unwrap()
    
    # Execute advanced search
    result = search_service.search_advanced(
        request=payload,
        user_id=user_id
    )
    
    return result.unwrap()


@router.get(
    "/nearby",
    response_model=FacetedSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search nearby hostels",
    description="""
    Geospatial search for hostels near a specific coordinate.
    
    Features:
    - Radius-based proximity search
    - Distance sorting (closest first)
    - Optional keyword filtering
    - Distance calculation in results
    - Pagination support
    
    Use cases:
    - "Find hostels near me"
    - "Show hostels within 5km of Eiffel Tower"
    - "Nearby hostels with WiFi"
    """,
    responses={
        200: {
            "description": "Nearby hostels with distance information",
            "content": {
                "application/json": {
                    "example": {
                        "results": [
                            {
                                "id": 123,
                                "name": "Central Hostel",
                                "distance_km": 0.8,
                                "latitude": 48.8566,
                                "longitude": 2.3522
                            }
                        ],
                        "metadata": {
                            "total": 12,
                            "page": 1,
                            "limit": 20,
                            "center": {"lat": 48.8584, "lon": 2.2945},
                            "radius_km": 10.0
                        }
                    }
                }
            }
        },
        400: {"description": "Invalid coordinates or parameters"},
        500: {"description": "Internal server error"}
    }
)
async def search_nearby(
    lat: float = Query(
        ...,
        ge=MIN_LATITUDE,
        le=MAX_LATITUDE,
        description="Latitude of search center (-90 to 90)",
        example=48.8566
    ),
    lon: float = Query(
        ...,
        ge=MIN_LONGITUDE,
        le=MAX_LONGITUDE,
        description="Longitude of search center (-180 to 180)",
        example=2.3522
    ),
    radius_km: float = Query(
        default=DEFAULT_RADIUS_KM,
        gt=MIN_RADIUS_KM,
        le=MAX_RADIUS_KM,
        description="Search radius in kilometers",
        example=5.0
    ),
    q: Optional[str] = Query(
        default=None,
        max_length=200,
        description="Optional keyword filter",
        example="wifi breakfast"
    ),
    page: int = Query(
        default=DEFAULT_PAGE,
        ge=1,
        description="Page number for pagination"
    ),
    limit: int = Query(
        default=DEFAULT_LIMIT,
        ge=MIN_LIMIT,
        le=MAX_LIMIT,
        description="Number of results per page"
    ),
    search_service: SearchService = Depends(get_search_service),
    current_user: Optional[Any] = Depends(get_current_user_optional),
) -> FacetedSearchResponse:
    """
    Search for hostels within a radius of given coordinates.
    
    Results are sorted by distance (closest first) unless otherwise specified.
    
    Args:
        lat: Latitude of search center
        lon: Longitude of search center
        radius_km: Search radius in kilometers
        q: Optional keyword filter
        page: Page number (1-indexed)
        limit: Results per page (1-100)
        search_service: Injected search service
        current_user: Optional authenticated user
        
    Returns:
        FacetedSearchResponse with nearby results and distance metadata
        
    Raises:
        HTTPException: On service errors (handled by FastAPI)
    """
    user_id = extract_user_id(current_user)
    
    # Prepare optional query (strip whitespace if provided)
    query = q.strip() if q else None
    
    # Execute nearby search
    result = search_service.search_nearby(
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        query=query,
        page=page,
        limit=limit,
        user_id=user_id,
    )
    
    return result.unwrap()