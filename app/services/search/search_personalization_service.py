"""
Search Personalization Service

Provides personalization utilities to adjust search behavior per user/visitor.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.search import AdvancedSearchRequest
from app.repositories.visitor import VisitorAggregateRepository
from app.core.exceptions import ValidationException


class SearchPersonalizationService:
    """
    High-level service for per-visitor personalization.

    Responsibilities:
    - Adjust search filters based on visitor behavior
    - Suggest boosted cities/room types/amenities based on history
    """

    def __init__(
        self,
        visitor_aggregate_repo: VisitorAggregateRepository,
    ) -> None:
        self.visitor_aggregate_repo = visitor_aggregate_repo

    def personalize_advanced_request(
        self,
        db: Session,
        visitor_id: UUID,
        request: AdvancedSearchRequest,
    ) -> AdvancedSearchRequest:
        """
        Return a modified copy of AdvancedSearchRequest with
        personalized hints applied.

        Personalization is non-destructive: it only sets defaults
        if they are not already specified by the caller.
        """
        summary = self.visitor_aggregate_repo.get_view_and_search_summary(
            db,
            visitor_id=visitor_id,
        )
        if not summary:
            # No behavior data – return original request
            return request

        data = request.model_dump()

        # Example heuristics:
        # - If no cities specified, use most searched/viewed city
        if not data.get("city") and summary.get("top_cities"):
            data["city"] = summary["top_cities"][0]

        # - If no room type specified, use most viewed room type
        if not data.get("room_types") and summary.get("top_room_types"):
            data["room_types"] = [summary["top_room_types"][0]]

        # - If budget not set but we have inferred budget
        if data.get("min_price") is None and summary.get("avg_budget_min") is not None:
            data["min_price"] = summary["avg_budget_min"]
        if data.get("max_price") is None and summary.get("avg_budget_max") is not None:
            data["max_price"] = summary["avg_budget_max"]

        return AdvancedSearchRequest(**data)