"""
Visitor Recommendation Service

Generates personalized hostel recommendations for visitors.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.visitor import (
    VisitorRepository,
    VisitorFavoriteRepository,
    VisitorAggregateRepository,
    RecommendedHostelRepository,
)
from app.schemas.visitor import RecommendedHostel
from app.core.exceptions import ValidationException


class VisitorRecommendationService:
    """
    High-level recommendation engine (rule-based placeholder).

    This can later be replaced/augmented by ML-based recommendations.
    """

    def __init__(
        self,
        visitor_repo: VisitorRepository,
        favorite_repo: VisitorFavoriteRepository,
        aggregate_repo: VisitorAggregateRepository,
        recommended_repo: RecommendedHostelRepository,
    ) -> None:
        self.visitor_repo = visitor_repo
        self.favorite_repo = favorite_repo
        self.aggregate_repo = aggregate_repo
        self.recommended_repo = recommended_repo

    def generate_recommendations(
        self,
        db: Session,
        visitor_id: UUID,
        limit: int = 10,
    ) -> List[RecommendedHostel]:
        """
        Generate and persist recommendations for a visitor.

        Simple rule-based example:
        - Look at favorites and recent views
        - Recommend hostels in same cities/room types that the visitor has not favorited yet
        """
        visitor = self.visitor_repo.get_by_id(db, visitor_id)
        if not visitor:
            raise ValidationException("Visitor not found")

        # Get behavioral data
        favorites = self.favorite_repo.get_favorites_by_visitor(db, visitor_id)
        recent_summary = self.aggregate_repo.get_view_and_search_summary(db, visitor_id)

        # Compute preferred cities / room types from behavior
        preferred_cities = recent_summary.get("top_cities", [])
        preferred_room_types = recent_summary.get("top_room_types", [])

        # Get recommendations (repository encapsulates query logic)
        candidates = self.recommended_repo.find_recommendation_candidates(
            db=db,
            excluded_hostel_ids=[f.hostel_id for f in favorites],
            preferred_cities=preferred_cities,
            preferred_room_types=preferred_room_types,
            limit=limit,
        )

        # Store recommendations
        recs = self.recommended_repo.store_recommendations_for_visitor(
            db=db,
            visitor_id=visitor_id,
            hostels=candidates,
        )

        return [RecommendedHostel.model_validate(r) for r in recs]

    def get_recommendations(
        self,
        db: Session,
        visitor_id: UUID,
        limit: int = 10,
    ) -> List[RecommendedHostel]:
        """
        Fetch existing recommendations for a visitor.

        If none found, generate new ones.
        """
        existing = self.recommended_repo.get_recommendations_for_visitor(
            db, visitor_id, limit=limit
        )

        if not existing:
            return self.generate_recommendations(db, visitor_id, limit=limit)

        return [RecommendedHostel.model_validate(r) for r in existing]