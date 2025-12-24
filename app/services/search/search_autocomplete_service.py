"""
Search Autocomplete Service

Provides typeahead/autocomplete suggestions using stored suggestion data
and/or aggregated search analytics.
"""

from __future__ import annotations

from typing import List
from time import perf_counter

from sqlalchemy.orm import Session

from app.schemas.search import (
    AutocompleteRequest,
    AutocompleteResponse,
    Suggestion,
)
from app.repositories.search import AutocompleteSuggestionRepository
from app.core.logging import LoggingContext


class SearchAutocompleteService:
    """
    High-level service for search autocomplete.

    Responsibilities:
    - Retrieve suggestions from AutocompleteSuggestionRepository
    - Wrap results into AutocompleteResponse with timing
    - Optionally log autocomplete performance (via repo)
    """

    def __init__(
        self,
        suggestion_repo: AutocompleteSuggestionRepository,
    ) -> None:
        self.suggestion_repo = suggestion_repo

    def get_suggestions(
        self,
        db: Session,
        request: AutocompleteRequest,
    ) -> AutocompleteResponse:
        """
        Generate autocomplete suggestions for a given prefix.

        Args:
            db: SQLAlchemy session
            request: AutocompleteRequest

        Returns:
            AutocompleteResponse
        """
        with LoggingContext(autocomplete_prefix=request.prefix):
            start = perf_counter()

            raw_suggestions = self.suggestion_repo.get_suggestions(
                db=db,
                prefix=request.prefix,
                suggestion_types=request.types,
                limit=request.limit,
                latitude=request.latitude,
                longitude=request.longitude,
            )

            suggestions: List[Suggestion] = [
                Suggestion.model_validate(s) for s in raw_suggestions
            ]

            elapsed_ms = int((perf_counter() - start) * 1000)

            # Optional: log autocomplete query performance
            try:
                self.suggestion_repo.log_autocomplete_query(
                    db=db,
                    prefix=request.prefix,
                    suggestion_types=request.types,
                    result_count=len(suggestions),
                    execution_time_ms=elapsed_ms,
                )
            except Exception:
                db.rollback()

            return AutocompleteResponse(
                prefix=request.prefix,
                suggestions=suggestions,
                total_count=len(suggestions),
                execution_time_ms=elapsed_ms,
            )