"""
Search autocomplete endpoint for typeahead suggestions.

Provides real-time search suggestions as users type, supporting:
- Multi-type suggestions (hostels, cities, amenities, etc.)
- Optional user-specific personalization
- Configurable result limits and filtering
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.core.dependencies import AuthenticationDependency
from app.schemas.search import AutocompleteResponse
from app.services.search.search_autocomplete_service import SearchAutocompleteService

# Router configuration
router = APIRouter(
    prefix="/search/autocomplete",
    tags=["Search - Autocomplete"],
)


# ============================================================================
# Dependencies
# ============================================================================


def get_autocomplete_service() -> SearchAutocompleteService:
    """
    Dependency injection for autocomplete service.
    
    Override this in your dependency configuration to provide
    the actual implementation.
    
    Raises:
        NotImplementedError: When not properly configured in DI container
    """
    raise NotImplementedError(
        "Autocomplete service dependency not configured. "
        "Please override this in your dependency injection setup."
    )


def get_current_user_optional(
    auth: AuthenticationDependency = Depends(),
) -> Optional[Any]:
    """
    Optional authentication dependency.
    
    Returns the current user if authenticated, None otherwise.
    Allows both authenticated and anonymous users to access autocomplete.
    
    Args:
        auth: Authentication dependency
        
    Returns:
        User object if authenticated, None otherwise
    """
    return auth.get_current_user_optional()


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "",
    response_model=AutocompleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Get search autocomplete suggestions",
    description="""
    Returns typeahead suggestions for the search bar based on query prefix.
    
    Features:
    - Real-time suggestions as user types
    - Multiple suggestion types (hostels, cities, amenities, etc.)
    - Optional filtering by suggestion types
    - User-aware personalization for authenticated users
    - Configurable result limits
    
    Examples:
    - `/search/autocomplete?q=par` → Paris, Park Hotel, Parking amenity
    - `/search/autocomplete?q=lond&types=city,hostel&limit=5`
    """,
    responses={
        200: {
            "description": "Successful autocomplete suggestions",
            "content": {
                "application/json": {
                    "example": {
                        "suggestions": [
                            {
                                "text": "Paris",
                                "type": "city",
                                "score": 0.95,
                                "metadata": {"country": "France"}
                            },
                            {
                                "text": "Park Hotel Hostel",
                                "type": "hostel",
                                "score": 0.87,
                                "metadata": {"city": "Paris", "rating": 4.5}
                            }
                        ],
                        "grouped": {
                            "city": [...],
                            "hostel": [...]
                        },
                        "total": 2
                    }
                }
            }
        },
        400: {"description": "Invalid query parameters"},
        500: {"description": "Internal server error"}
    }
)
async def get_autocomplete_suggestions(
    q: str = Query(
        ...,
        min_length=1,
        max_length=100,
        description="Search query prefix (minimum 1 character)",
        example="par"
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of suggestions to return"
    ),
    types: Optional[list[str]] = Query(
        default=None,
        description="Filter by suggestion types (e.g., hostel, city, amenity)",
        example=["hostel", "city"]
    ),
    autocomplete_service: SearchAutocompleteService = Depends(get_autocomplete_service),
    current_user: Optional[Any] = Depends(get_current_user_optional),
) -> AutocompleteResponse:
    """
    Get autocomplete suggestions based on query prefix.
    
    Args:
        q: Query prefix string
        limit: Maximum number of suggestions (1-50)
        types: Optional list of suggestion types to filter by
        autocomplete_service: Injected autocomplete service
        current_user: Optional authenticated user
        
    Returns:
        AutocompleteResponse with suggestions and metadata
        
    Raises:
        HTTPException: On service errors (handled by FastAPI)
    """
    # Extract user ID for personalization
    user_id: Optional[int] = getattr(current_user, "id", None) if current_user else None
    
    # Get suggestions from service
    result = autocomplete_service.get_suggestions(
        prefix=q.strip(),  # Remove leading/trailing whitespace
        limit=limit,
        types=types,
        user_id=user_id,
    )
    
    # Unwrap Result type (assumes Result pattern from service layer)
    return result.unwrap()