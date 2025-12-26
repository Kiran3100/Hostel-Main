"""
Search Service

Core search orchestration for:
- Basic search
- Advanced search
- Nearby search

This service does NOT implement the search algorithm itself. Instead it
delegates to a pluggable backend (e.g. SQL, Elasticsearch) and handles:

- Execution timing
- Logging search queries and results
- Returning standardized response schemas
- Error handling and validation
"""

from __future__ import annotations

from typing import Callable, Optional, Any, Dict
from uuid import UUID
from time import perf_counter
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.schemas.search import (
    BasicSearchRequest,
    AdvancedSearchRequest,
    NearbySearchRequest,
    FacetedSearchResponse,
)
from app.repositories.search import SearchQueryLogRepository
from app.core.exceptions import ValidationException
from app.core.logging import LoggingContext, logger


# Type aliases for search backend functions
BasicSearchExecutor = Callable[[Session, BasicSearchRequest], FacetedSearchResponse]
AdvancedSearchExecutor = Callable[[Session, AdvancedSearchRequest], FacetedSearchResponse]
NearbySearchExecutor = Callable[[Session, NearbySearchRequest], FacetedSearchResponse]


class SearchService:
    """
    High-level orchestration for search operations.

    The actual search execution is performed by injected backend functions
    (SQL/Elasticsearch/etc.) making this service implementation-agnostic.

    Responsibilities:
    - Validate search requests
    - Execute search via pluggable backends
    - Track execution time and performance metrics
    - Log search queries for analytics
    - Handle errors gracefully
    """

    __slots__ = ('query_log_repo',)

    def __init__(
        self,
        query_log_repo: SearchQueryLogRepository,
    ) -> None:
        """
        Initialize SearchService.

        Args:
            query_log_repo: Repository for logging search queries
        """
        self.query_log_repo = query_log_repo

    # -------------------------------------------------------------------------
    # Basic search
    # -------------------------------------------------------------------------

    def search_basic(
        self,
        db: Session,
        request: BasicSearchRequest,
        executor: BasicSearchExecutor,
        user_id: Optional[UUID] = None,
    ) -> FacetedSearchResponse:
        """
        Execute a basic keyword search.

        Args:
            db: SQLAlchemy session
            request: BasicSearchRequest containing query and limit
            executor: Callable that performs the actual search
            user_id: Optional ID of the logged-in user/visitor

        Returns:
            FacetedSearchResponse with results and metadata

        Raises:
            ValidationException: If request validation fails
        """
        self._validate_basic_request(request)

        with LoggingContext(search_type="basic", query=request.query):
            return self._execute_search(
                db=db,
                request=request,
                executor=lambda: executor(db, request),
                user_id=user_id,
                search_kind="basic",
            )

    # -------------------------------------------------------------------------
    # Advanced search
    # -------------------------------------------------------------------------

    def search_advanced(
        self,
        db: Session,
        request: AdvancedSearchRequest,
        executor: AdvancedSearchExecutor,
        user_id: Optional[UUID] = None,
    ) -> FacetedSearchResponse:
        """
        Execute an advanced search with filters, sorting, and pagination.

        Args:
            db: SQLAlchemy session
            request: AdvancedSearchRequest with comprehensive filters
            executor: Callable that performs the actual search
            user_id: Optional ID of the logged-in user/visitor

        Returns:
            FacetedSearchResponse with filtered results and facets

        Raises:
            ValidationException: If request validation fails
        """
        self._validate_advanced_request(request)

        with LoggingContext(search_type="advanced", query=request.query or ""):
            return self._execute_search(
                db=db,
                request=request,
                executor=lambda: executor(db, request),
                user_id=user_id,
                search_kind="advanced",
            )

    # -------------------------------------------------------------------------
    # Nearby search
    # -------------------------------------------------------------------------

    def search_nearby(
        self,
        db: Session,
        request: NearbySearchRequest,
        executor: NearbySearchExecutor,
        user_id: Optional[UUID] = None,
    ) -> FacetedSearchResponse:
        """
        Execute a nearby search based on latitude/longitude and radius.

        Args:
            db: SQLAlchemy session
            request: NearbySearchRequest with geolocation parameters
            executor: Callable that performs the actual search
            user_id: Optional ID of the logged-in user/visitor

        Returns:
            FacetedSearchResponse with nearby results sorted by distance

        Raises:
            ValidationException: If geolocation parameters are invalid
        """
        self._validate_nearby_request(request)

        with LoggingContext(
            search_type="nearby",
            query=request.query or "",
            lat=request.latitude,
            lon=request.longitude,
        ):
            return self._execute_search(
                db=db,
                request=request,
                executor=lambda: executor(db, request),
                user_id=user_id,
                search_kind="nearby",
            )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _execute_search(
        self,
        db: Session,
        request: Any,
        executor: Callable[[], FacetedSearchResponse],
        user_id: Optional[UUID],
        search_kind: str,
    ) -> FacetedSearchResponse:
        """
        Generic search execution wrapper with timing and logging.

        Args:
            db: SQLAlchemy session
            request: Search request object
            executor: Callable that executes the search
            user_id: Optional user identifier
            search_kind: Type of search (basic/advanced/nearby)

        Returns:
            FacetedSearchResponse from the executor
        """
        start_time = perf_counter()
        
        try:
            response = executor()
            execution_time_ms = self._calculate_execution_time(start_time)
            
            # Attach execution time to response metadata
            if hasattr(response, 'metadata') and hasattr(response.metadata, '__dict__'):
                response.metadata.__dict__['execution_time_ms'] = execution_time_ms
            
            # Log search query asynchronously (non-blocking)
            self._log_search_async(
                db=db,
                user_id=user_id,
                request_data=request.model_dump(exclude_none=True),
                response=response,
                execution_time_ms=execution_time_ms,
                search_kind=search_kind,
            )
            
            return response
            
        except Exception as e:
            execution_time_ms = self._calculate_execution_time(start_time)
            logger.error(
                f"Search execution failed: {search_kind}",
                extra={
                    "search_kind": search_kind,
                    "execution_time_ms": execution_time_ms,
                    "error": str(e),
                    "user_id": str(user_id) if user_id else None,
                }
            )
            raise

    def _log_search_async(
        self,
        db: Session,
        user_id: Optional[UUID],
        request_data: Dict[str, Any],
        response: FacetedSearchResponse,
        execution_time_ms: int,
        search_kind: str,
    ) -> None:
        """
        Persist a search query log entry via repository.

        The repository is responsible for mapping fields to the underlying
        models (SearchQueryLog, SearchSession, etc.).

        This method catches all exceptions to ensure logging failures
        don't impact the search flow.

        Args:
            db: SQLAlchemy session
            user_id: Optional user identifier
            request_data: Serialized request parameters
            response: Search response
            execution_time_ms: Execution time in milliseconds
            search_kind: Type of search performed
        """
        try:
            self.query_log_repo.log_search(
                db=db,
                user_id=user_id,
                search_kind=search_kind,
                query=request_data.get("query"),
                parameters=request_data,
                results_count=len(response.results),
                execution_time_ms=execution_time_ms,
                metadata={
                    "total_results": response.metadata.total_results,
                    "current_page": response.metadata.current_page,
                    "page_size": response.metadata.page_size,
                    "total_pages": response.metadata.total_pages,
                    "has_next": response.metadata.has_next,
                    "has_previous": response.metadata.has_previous,
                },
            )
            db.commit()
        except Exception as e:
            # Logging should not break the main search flow
            logger.warning(
                f"Failed to log search query: {str(e)}",
                extra={
                    "search_kind": search_kind,
                    "user_id": str(user_id) if user_id else None,
                }
            )
            db.rollback()

    @staticmethod
    def _calculate_execution_time(start_time: float) -> int:
        """
        Calculate execution time in milliseconds.

        Args:
            start_time: Start time from perf_counter()

        Returns:
            Execution time in milliseconds
        """
        return int((perf_counter() - start_time) * 1000)

    # -------------------------------------------------------------------------
    # Validation methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_basic_request(request: BasicSearchRequest) -> None:
        """
        Validate basic search request.

        Args:
            request: BasicSearchRequest to validate

        Raises:
            ValidationException: If validation fails
        """
        if not request.query or not request.query.strip():
            raise ValidationException("Search query cannot be empty")
        
        if request.limit is not None and request.limit <= 0:
            raise ValidationException("Search limit must be positive")
        
        if request.limit is not None and request.limit > 1000:
            raise ValidationException("Search limit cannot exceed 1000")

    @staticmethod
    def _validate_advanced_request(request: AdvancedSearchRequest) -> None:
        """
        Validate advanced search request.

        Args:
            request: AdvancedSearchRequest to validate

        Raises:
            ValidationException: If validation fails
        """
        # Validate pagination
        if request.page is not None and request.page < 1:
            raise ValidationException("Page number must be >= 1")
        
        if request.page_size is not None and request.page_size <= 0:
            raise ValidationException("Page size must be positive")
        
        if request.page_size is not None and request.page_size > 100:
            raise ValidationException("Page size cannot exceed 100")
        
        # Validate price range
        if (request.min_price is not None and request.max_price is not None and
            request.min_price > request.max_price):
            raise ValidationException("Min price cannot exceed max price")
        
        if request.min_price is not None and request.min_price < 0:
            raise ValidationException("Min price cannot be negative")
        
        # Validate rating
        if request.min_rating is not None and (request.min_rating < 0 or request.min_rating > 5):
            raise ValidationException("Min rating must be between 0 and 5")

    @staticmethod
    def _validate_nearby_request(request: NearbySearchRequest) -> None:
        """
        Validate nearby search request.

        Args:
            request: NearbySearchRequest to validate

        Raises:
            ValidationException: If validation fails
        """
        if request.latitude is None or request.longitude is None:
            raise ValidationException("Nearby search requires latitude and longitude")
        
        # Validate latitude range
        if not -90 <= request.latitude <= 90:
            raise ValidationException("Latitude must be between -90 and 90")
        
        # Validate longitude range
        if not -180 <= request.longitude <= 180:
            raise ValidationException("Longitude must be between -180 and 180")
        
        # Validate radius
        if request.radius_km is not None and request.radius_km <= 0:
            raise ValidationException("Radius must be positive")
        
        if request.radius_km is not None and request.radius_km > 500:
            raise ValidationException("Radius cannot exceed 500 km")