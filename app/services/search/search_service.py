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
"""

from __future__ import annotations

from typing import Callable, Optional
from uuid import UUID
from time import perf_counter

from sqlalchemy.orm import Session

from app.schemas.search import (
    BasicSearchRequest,
    AdvancedSearchRequest,
    NearbySearchRequest,
    FacetedSearchResponse,
)
from app.repositories.search import SearchQueryLogRepository
from app.core.exceptions import ValidationException
from app.core.logging import LoggingContext


# Type alias for a search backend function
BasicSearchExecutor = Callable[[BasicSearchRequest], FacetedSearchResponse]
AdvancedSearchExecutor = Callable[[AdvancedSearchRequest], FacetedSearchResponse]
NearbySearchExecutor = Callable[[NearbySearchRequest], FacetedSearchResponse]


class SearchService:
    """
    High-level orchestration for search.

    The actual search execution is performed by injected backend functions
    (SQL/Elasticsearch/etc.) so this service is agnostic of implementation.
    """

    def __init__(
        self,
        query_log_repo: SearchQueryLogRepository,
    ) -> None:
        self.query_log_repo = query_log_repo

    # -------------------------------------------------------------------------
    # Basic search
    # -------------------------------------------------------------------------

    def search_basic(
        self,
        db: Session,
        request: BasicSearchRequest,
        user_id: Optional[UUID],
        executor: BasicSearchExecutor,
    ) -> FacetedSearchResponse:
        """
        Execute a basic keyword search.

        Args:
            db: SQLAlchemy session
            request: BasicSearchRequest (query + limit)
            user_id: Optional ID of the logged-in user/visitor
            executor: Callable that actually performs the search

        Returns:
            FacetedSearchResponse
        """
        with LoggingContext(search_type="basic", query=request.query):
            start = perf_counter()
            response = executor(request)
            elapsed_ms = int((perf_counter() - start) * 1000)

            # Log search query
            self._log_search(
                db=db,
                user_id=user_id,
                request_data=request.model_dump(exclude_none=True),
                response=response,
                execution_time_ms=elapsed_ms,
                search_kind="basic",
            )

        return response

    # -------------------------------------------------------------------------
    # Advanced search
    # -------------------------------------------------------------------------

    def search_advanced(
        self,
        db: Session,
        request: AdvancedSearchRequest,
        user_id: Optional[UUID],
        executor: AdvancedSearchExecutor,
    ) -> FacetedSearchResponse:
        """
        Execute an advanced search with filters, sorting, and pagination.
        """
        with LoggingContext(search_type="advanced", query=request.query):
            start = perf_counter()
            response = executor(request)
            elapsed_ms = int((perf_counter() - start) * 1000)

            self._log_search(
                db=db,
                user_id=user_id,
                request_data=request.model_dump(exclude_none=True),
                response=response,
                execution_time_ms=elapsed_ms,
                search_kind="advanced",
            )

        return response

    # -------------------------------------------------------------------------
    # Nearby search
    # -------------------------------------------------------------------------

    def search_nearby(
        self,
        db: Session,
        request: NearbySearchRequest,
        user_id: Optional[UUID],
        executor: NearbySearchExecutor,
    ) -> FacetedSearchResponse:
        """
        Execute a nearby search based on latitude/longitude and radius.
        """
        if request.latitude is None or request.longitude is None:
            raise ValidationException("Nearby search requires latitude and longitude")

        with LoggingContext(search_type="nearby", query=request.query or ""):
            start = perf_counter()
            response = executor(request)
            elapsed_ms = int((perf_counter() - start) * 1000)

            self._log_search(
                db=db,
                user_id=user_id,
                request_data=request.model_dump(exclude_none=True),
                response=response,
                execution_time_ms=elapsed_ms,
                search_kind="nearby",
            )

        return response

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _log_search(
        self,
        db: Session,
        user_id: Optional[UUID],
        request_data: dict,
        response: FacetedSearchResponse,
        execution_time_ms: int,
        search_kind: str,
    ) -> None:
        """
        Persist a search query log entry via repository.

        The repository is responsible for mapping fields to the underlying
        models (SearchQueryLog, SearchSession, etc.).
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
                    "page": response.metadata.current_page,
                    "page_size": response.metadata.page_size,
                },
            )
        except Exception:
            # Logging should not break the main search flow
            db.rollback()