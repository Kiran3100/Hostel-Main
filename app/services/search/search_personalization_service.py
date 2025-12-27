"""
Search Personalization Service

Provides personalization utilities to adjust search behavior per user/visitor.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.search import AdvancedSearchRequest
from app.repositories.visitor import VisitorAggregateRepository
from app.core1.exceptions import ValidationException
from app.core1.logging import logger, LoggingContext


class SearchPersonalizationService:
    """
    High-level service for per-visitor personalization.

    Responsibilities:
    - Adjust search filters based on visitor behavior
    - Suggest boosted cities/room types/amenities based on history
    - Apply personalization non-destructively (preserve user preferences)
    - Handle missing visitor data gracefully
    """

    __slots__ = (
        'visitor_aggregate_repo',
        'personalization_weight',
        'min_history_threshold',
    )

    def __init__(
        self,
        visitor_aggregate_repo: VisitorAggregateRepository,
        personalization_weight: float = 0.7,
        min_history_threshold: int = 3,
    ) -> None:
        """
        Initialize SearchPersonalizationService.

        Args:
            visitor_aggregate_repo: Repository for visitor behavior data
            personalization_weight: Weight for personalization (0.0-1.0)
            min_history_threshold: Minimum interactions needed for personalization
        """
        self.visitor_aggregate_repo = visitor_aggregate_repo
        self.personalization_weight = max(0.0, min(1.0, personalization_weight))
        self.min_history_threshold = min_history_threshold

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

        Args:
            db: SQLAlchemy session
            visitor_id: UUID of the visitor
            request: Original AdvancedSearchRequest

        Returns:
            Personalized AdvancedSearchRequest

        Raises:
            ValidationException: If visitor_id is invalid
        """
        if visitor_id is None:
            raise ValidationException("Visitor ID cannot be None")

        with LoggingContext(
            action="personalize_search",
            visitor_id=str(visitor_id),
        ):
            try:
                # Fetch visitor behavior summary
                summary = self._fetch_visitor_summary(db, visitor_id)
                
                if not summary or not self._has_sufficient_history(summary):
                    logger.debug(
                        f"Insufficient history for visitor: {visitor_id}",
                        extra={"visitor_id": str(visitor_id)}
                    )
                    return request

                # Apply personalization
                personalized_data = self._apply_personalization(
                    request.model_dump(),
                    summary,
                )

                personalized_request = AdvancedSearchRequest(**personalized_data)
                
                logger.info(
                    f"Applied personalization for visitor: {visitor_id}",
                    extra={
                        "visitor_id": str(visitor_id),
                        "personalizations_applied": self._count_personalizations(
                            request,
                            personalized_request,
                        ),
                    }
                )

                return personalized_request

            except Exception as e:
                logger.warning(
                    f"Personalization failed for visitor: {visitor_id}",
                    extra={
                        "visitor_id": str(visitor_id),
                        "error": str(e),
                    }
                )
                # Return original request if personalization fails
                return request

    def get_personalization_insights(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get personalization insights for a visitor.

        Returns information about visitor preferences without
        applying them to a search request.

        Args:
            db: SQLAlchemy session
            visitor_id: UUID of the visitor

        Returns:
            Dictionary containing personalization insights
        """
        with LoggingContext(
            action="get_personalization_insights",
            visitor_id=str(visitor_id),
        ):
            summary = self._fetch_visitor_summary(db, visitor_id)
            
            if not summary:
                return {
                    "visitor_id": str(visitor_id),
                    "has_history": False,
                    "preferences": {},
                }

            return {
                "visitor_id": str(visitor_id),
                "has_history": self._has_sufficient_history(summary),
                "preferences": {
                    "preferred_cities": summary.get("top_cities", []),
                    "preferred_room_types": summary.get("top_room_types", []),
                    "preferred_amenities": summary.get("top_amenities", []),
                    "budget_range": {
                        "min": summary.get("avg_budget_min"),
                        "max": summary.get("avg_budget_max"),
                    },
                    "interaction_count": summary.get("total_interactions", 0),
                    "search_count": summary.get("search_count", 0),
                    "view_count": summary.get("view_count", 0),
                },
            }

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _fetch_visitor_summary(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch visitor behavior summary from repository.

        Args:
            db: SQLAlchemy session
            visitor_id: UUID of the visitor

        Returns:
            Visitor summary dictionary or None
        """
        try:
            return self.visitor_aggregate_repo.get_view_and_search_summary(
                db,
                visitor_id=visitor_id,
            )
        except Exception as e:
            logger.error(
                f"Failed to fetch visitor summary: {str(e)}",
                extra={"visitor_id": str(visitor_id)}
            )
            return None

    def _has_sufficient_history(self, summary: Dict[str, Any]) -> bool:
        """
        Check if visitor has sufficient interaction history.

        Args:
            summary: Visitor behavior summary

        Returns:
            True if sufficient history exists
        """
        total_interactions = summary.get("total_interactions", 0)
        return total_interactions >= self.min_history_threshold

    def _apply_personalization(
        self,
        request_data: Dict[str, Any],
        summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply personalization to request data based on visitor summary.

        Personalization rules:
        1. Only apply if user hasn't specified the field
        2. Use most frequent values from history
        3. Apply with confidence weighting

        Args:
            request_data: Original request data
            summary: Visitor behavior summary

        Returns:
            Personalized request data
        """
        # City personalization
        if not request_data.get("city") and summary.get("top_cities"):
            request_data["city"] = summary["top_cities"][0]

        # Room type personalization
        if not request_data.get("room_types") and summary.get("top_room_types"):
            # Suggest top 2 room types
            request_data["room_types"] = summary["top_room_types"][:2]

        # Amenity personalization
        if not request_data.get("amenities") and summary.get("top_amenities"):
            # Suggest top 3 amenities
            request_data["amenities"] = summary["top_amenities"][:3]

        # Budget personalization (with weight adjustment)
        if request_data.get("min_price") is None and summary.get("avg_budget_min"):
            avg_min = summary["avg_budget_min"]
            # Apply with weight to avoid being too restrictive
            request_data["min_price"] = int(avg_min * self.personalization_weight)

        if request_data.get("max_price") is None and summary.get("avg_budget_max"):
            avg_max = summary["avg_budget_max"]
            # Apply with inverse weight to be more lenient
            request_data["max_price"] = int(avg_max / self.personalization_weight)

        # Gender preference personalization
        if not request_data.get("gender_type") and summary.get("preferred_gender"):
            request_data["gender_type"] = summary["preferred_gender"]

        # Sorting preference personalization
        if not request_data.get("sort_by") and summary.get("preferred_sort"):
            request_data["sort_by"] = summary["preferred_sort"]

        return request_data

    @staticmethod
    def _count_personalizations(
        original: AdvancedSearchRequest,
        personalized: AdvancedSearchRequest,
    ) -> int:
        """
        Count how many fields were personalized.

        Args:
            original: Original request
            personalized: Personalized request

        Returns:
            Number of fields that were modified
        """
        count = 0
        original_dict = original.model_dump()
        personalized_dict = personalized.model_dump()

        for key, value in personalized_dict.items():
            if value != original_dict.get(key):
                count += 1

        return count