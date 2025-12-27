"""
Search Autocomplete Service

Provides typeahead/autocomplete suggestions using stored suggestion data
and/or aggregated search analytics.
"""

from __future__ import annotations

from typing import List, Optional
from time import perf_counter

from sqlalchemy.orm import Session

from app.schemas.search import (
    AutocompleteRequest,
    AutocompleteResponse,
    Suggestion,
)
from app.repositories.search import AutocompleteSuggestionRepository
from app.core1.logging import LoggingContext, logger
from app.core1.exceptions import ValidationException


class SearchAutocompleteService:
    """
    High-level service for search autocomplete.

    Responsibilities:
    - Retrieve suggestions from AutocompleteSuggestionRepository
    - Wrap results into AutocompleteResponse with timing
    - Log autocomplete performance
    - Handle errors gracefully
    - Validate requests
    """

    __slots__ = ('suggestion_repo', 'max_prefix_length', 'min_prefix_length')

    def __init__(
        self,
        suggestion_repo: AutocompleteSuggestionRepository,
        min_prefix_length: int = 1,
        max_prefix_length: int = 100,
    ) -> None:
        """
        Initialize SearchAutocompleteService.

        Args:
            suggestion_repo: Repository for autocomplete suggestions
            min_prefix_length: Minimum prefix length to trigger suggestions
            max_prefix_length: Maximum prefix length to accept
        """
        self.suggestion_repo = suggestion_repo
        self.min_prefix_length = min_prefix_length
        self.max_prefix_length = max_prefix_length

    def get_suggestions(
        self,
        db: Session,
        request: AutocompleteRequest,
    ) -> AutocompleteResponse:
        """
        Generate autocomplete suggestions for a given prefix.

        Args:
            db: SQLAlchemy session
            request: AutocompleteRequest containing prefix and filters

        Returns:
            AutocompleteResponse with suggestions and metadata

        Raises:
            ValidationException: If request validation fails
        """
        self._validate_request(request)

        with LoggingContext(
            autocomplete_prefix=request.prefix,
            suggestion_types=request.types,
        ):
            start_time = perf_counter()

            try:
                raw_suggestions = self._fetch_suggestions(db, request)
                suggestions = self._parse_suggestions(raw_suggestions)
                execution_time_ms = self._calculate_execution_time(start_time)

                # Log autocomplete query performance asynchronously
                self._log_autocomplete_async(
                    db=db,
                    request=request,
                    result_count=len(suggestions),
                    execution_time_ms=execution_time_ms,
                )

                return AutocompleteResponse(
                    prefix=request.prefix,
                    suggestions=suggestions,
                    total_count=len(suggestions),
                    execution_time_ms=execution_time_ms,
                )

            except Exception as e:
                execution_time_ms = self._calculate_execution_time(start_time)
                logger.error(
                    f"Autocomplete failed for prefix: {request.prefix}",
                    extra={
                        "prefix": request.prefix,
                        "execution_time_ms": execution_time_ms,
                        "error": str(e),
                    }
                )
                # Return empty response instead of raising
                return AutocompleteResponse(
                    prefix=request.prefix,
                    suggestions=[],
                    total_count=0,
                    execution_time_ms=execution_time_ms,
                )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _fetch_suggestions(
        self,
        db: Session,
        request: AutocompleteRequest,
    ) -> List[dict]:
        """
        Fetch raw suggestions from repository.

        Args:
            db: SQLAlchemy session
            request: AutocompleteRequest

        Returns:
            List of raw suggestion dictionaries
        """
        return self.suggestion_repo.get_suggestions(
            db=db,
            prefix=request.prefix,
            suggestion_types=request.types,
            limit=request.limit,
            latitude=request.latitude,
            longitude=request.longitude,
        )

    @staticmethod
    def _parse_suggestions(raw_suggestions: List[dict]) -> List[Suggestion]:
        """
        Parse raw suggestions into Suggestion schema objects.

        Args:
            raw_suggestions: List of raw suggestion dictionaries

        Returns:
            List of validated Suggestion objects
        """
        suggestions: List[Suggestion] = []
        
        for raw_suggestion in raw_suggestions:
            try:
                suggestion = Suggestion.model_validate(raw_suggestion)
                suggestions.append(suggestion)
            except Exception as e:
                logger.warning(
                    f"Failed to parse suggestion: {str(e)}",
                    extra={"raw_suggestion": raw_suggestion}
                )
                continue
        
        return suggestions

    def _log_autocomplete_async(
        self,
        db: Session,
        request: AutocompleteRequest,
        result_count: int,
        execution_time_ms: int,
    ) -> None:
        """
        Log autocomplete query performance asynchronously.

        Args:
            db: SQLAlchemy session
            request: AutocompleteRequest
            result_count: Number of suggestions returned
            execution_time_ms: Execution time in milliseconds
        """
        try:
            self.suggestion_repo.log_autocomplete_query(
                db=db,
                prefix=request.prefix,
                suggestion_types=request.types,
                result_count=result_count,
                execution_time_ms=execution_time_ms,
            )
            db.commit()
        except Exception as e:
            logger.warning(
                f"Failed to log autocomplete query: {str(e)}",
                extra={
                    "prefix": request.prefix,
                    "result_count": result_count,
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
    # Validation
    # -------------------------------------------------------------------------

    def _validate_request(self, request: AutocompleteRequest) -> None:
        """
        Validate autocomplete request.

        Args:
            request: AutocompleteRequest to validate

        Raises:
            ValidationException: If validation fails
        """
        if not request.prefix or not request.prefix.strip():
            raise ValidationException("Autocomplete prefix cannot be empty")
        
        prefix_length = len(request.prefix.strip())
        
        if prefix_length < self.min_prefix_length:
            raise ValidationException(
                f"Prefix must be at least {self.min_prefix_length} characters"
            )
        
        if prefix_length > self.max_prefix_length:
            raise ValidationException(
                f"Prefix cannot exceed {self.max_prefix_length} characters"
            )
        
        if request.limit is not None and request.limit <= 0:
            raise ValidationException("Limit must be positive")
        
        if request.limit is not None and request.limit > 50:
            raise ValidationException("Limit cannot exceed 50")
        
        # Validate geolocation if provided
        if request.latitude is not None or request.longitude is not None:
            if request.latitude is None or request.longitude is None:
                raise ValidationException(
                    "Both latitude and longitude must be provided together"
                )
            
            if not -90 <= request.latitude <= 90:
                raise ValidationException("Latitude must be between -90 and 90")
            
            if not -180 <= request.longitude <= 180:
                raise ValidationException("Longitude must be between -180 and 180")