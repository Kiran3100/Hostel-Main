"""
Visitor Recommendation Service

Generates personalized hostel recommendations for visitors.
Implements rule-based and ML-ready recommendation engine.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any, Set
from uuid import UUID
from datetime import datetime, timedelta
from collections import Counter

from sqlalchemy.orm import Session

from app.repositories.visitor import (
    VisitorRepository,
    VisitorFavoriteRepository,
    VisitorAggregateRepository,
    RecommendedHostelRepository,
)
from app.schemas.visitor import RecommendedHostel
from app.core1.exceptions import (
    ValidationException,
    NotFoundException,
    ServiceException,
)
from app.core1.caching import cache_result

logger = logging.getLogger(__name__)


class VisitorRecommendationService:
    """
    High-level recommendation engine for personalized hostel suggestions.

    Recommendation Strategies:
    1. Collaborative Filtering (similar visitors' favorites)
    2. Content-Based Filtering (based on visitor preferences and behavior)
    3. Popularity-Based (trending hostels)
    4. Location-Based (nearby or in preferred cities)
    5. Hybrid approach combining multiple strategies

    The service is designed to be extensible for ML-based recommendations.
    """

    # Default recommendation settings
    DEFAULT_RECOMMENDATION_COUNT = 10
    MAX_RECOMMENDATION_COUNT = 50
    RECOMMENDATION_REFRESH_HOURS = 24

    # Scoring weights for hybrid recommendations
    WEIGHTS = {
        "behavioral": 0.4,      # Based on user behavior (views, searches)
        "preference": 0.3,      # Based on explicit preferences
        "popularity": 0.2,      # Based on overall popularity
        "novelty": 0.1,         # Introduce new/diverse options
    }

    def __init__(
        self,
        visitor_repo: VisitorRepository,
        favorite_repo: VisitorFavoriteRepository,
        aggregate_repo: VisitorAggregateRepository,
        recommended_repo: RecommendedHostelRepository,
    ) -> None:
        """
        Initialize the recommendation service.

        Args:
            visitor_repo: Repository for visitor operations
            favorite_repo: Repository for favorite operations
            aggregate_repo: Repository for aggregated visitor data
            recommended_repo: Repository for recommendation storage
        """
        self.visitor_repo = visitor_repo
        self.favorite_repo = favorite_repo
        self.aggregate_repo = aggregate_repo
        self.recommended_repo = recommended_repo

    # -------------------------------------------------------------------------
    # Main Recommendation Methods
    # -------------------------------------------------------------------------

    def generate_recommendations(
        self,
        db: Session,
        visitor_id: UUID,
        limit: int = DEFAULT_RECOMMENDATION_COUNT,
        force_refresh: bool = False,
        strategy: str = "hybrid",
    ) -> List[RecommendedHostel]:
        """
        Generate and persist personalized recommendations for a visitor.

        This method:
        1. Analyzes visitor behavior and preferences
        2. Applies recommendation algorithms
        3. Scores and ranks candidates
        4. Stores recommendations for future retrieval
        5. Returns top N recommendations

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            limit: Number of recommendations to generate (max 50)
            force_refresh: Force regeneration even if recent recommendations exist
            strategy: Recommendation strategy ("hybrid", "behavioral", "popular")

        Returns:
            List[RecommendedHostel]: Personalized recommendations

        Raises:
            NotFoundException: If visitor not found
            ValidationException: If parameters are invalid
            ServiceException: If generation fails
        """
        try:
            # Validate inputs
            if limit < 1 or limit > self.MAX_RECOMMENDATION_COUNT:
                raise ValidationException(
                    f"limit must be between 1 and {self.MAX_RECOMMENDATION_COUNT}"
                )

            valid_strategies = ["hybrid", "behavioral", "popular", "preference"]
            if strategy not in valid_strategies:
                raise ValidationException(
                    f"Invalid strategy. Must be one of: {valid_strategies}"
                )

            # Check visitor exists
            visitor = self.visitor_repo.get_by_id(db, visitor_id)
            if not visitor:
                raise NotFoundException(f"Visitor {visitor_id} not found")

            # Check for recent recommendations
            if not force_refresh:
                existing = self._get_recent_recommendations(db, visitor_id, limit)
                if existing:
                    logger.info(
                        f"Returning existing recommendations for visitor {visitor_id}"
                    )
                    return existing

            # Gather visitor context
            context = self._build_visitor_context(db, visitor_id)

            # Generate candidates based on strategy
            if strategy == "hybrid":
                candidates = self._generate_hybrid_recommendations(db, context, limit * 3)
            elif strategy == "behavioral":
                candidates = self._generate_behavioral_recommendations(db, context, limit * 3)
            elif strategy == "popular":
                candidates = self._generate_popular_recommendations(db, context, limit * 3)
            elif strategy == "preference":
                candidates = self._generate_preference_recommendations(db, context, limit * 3)
            else:
                candidates = self._generate_hybrid_recommendations(db, context, limit * 3)

            # Score and rank candidates
            scored_candidates = self._score_candidates(context, candidates)

            # Take top N
            top_candidates = scored_candidates[:limit]

            # Store recommendations
            recommendations = self.recommended_repo.store_recommendations_for_visitor(
                db=db,
                visitor_id=visitor_id,
                hostels=top_candidates,
                strategy=strategy,
            )

            logger.info(
                f"Generated {len(recommendations)} {strategy} recommendations "
                f"for visitor {visitor_id}"
            )

            return [RecommendedHostel.model_validate(r) for r in recommendations]

        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to generate recommendations for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to generate recommendations: {str(e)}")

    @cache_result(ttl=3600, key_prefix="visitor_recs")
    def get_recommendations(
        self,
        db: Session,
        visitor_id: UUID,
        limit: int = DEFAULT_RECOMMENDATION_COUNT,
        refresh_if_stale: bool = True,
    ) -> List[RecommendedHostel]:
        """
        Fetch existing recommendations for a visitor.

        If none found or stale, generate new ones.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            limit: Number of recommendations to return
            refresh_if_stale: Regenerate if recommendations are stale

        Returns:
            List[RecommendedHostel]: Recommendations

        Raises:
            NotFoundException: If visitor not found
            ServiceException: If retrieval fails
        """
        try:
            # Check for existing recommendations
            existing = self.recommended_repo.get_recommendations_for_visitor(
                db, visitor_id, limit=limit
            )

            if existing:
                # Check if stale
                if refresh_if_stale and self._are_recommendations_stale(existing):
                    logger.info(
                        f"Recommendations stale for visitor {visitor_id}, regenerating"
                    )
                    return self.generate_recommendations(
                        db, visitor_id, limit=limit, force_refresh=True
                    )

                return [RecommendedHostel.model_validate(r) for r in existing]

            # No existing recommendations, generate new ones
            logger.info(f"No recommendations found for visitor {visitor_id}, generating")
            return self.generate_recommendations(db, visitor_id, limit=limit)

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get recommendations for visitor {visitor_id}: {str(e)}",
                exc_info=True
            )
            raise ServiceException(f"Failed to retrieve recommendations: {str(e)}")

    def refresh_recommendations(
        self,
        db: Session,
        visitor_id: UUID,
        limit: int = DEFAULT_RECOMMENDATION_COUNT,
    ) -> List[RecommendedHostel]:
        """
        Force refresh recommendations for a visitor.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            limit: Number of recommendations to generate

        Returns:
            List[RecommendedHostel]: Fresh recommendations
        """
        return self.generate_recommendations(
            db, visitor_id, limit=limit, force_refresh=True
        )

    # -------------------------------------------------------------------------
    # Recommendation Strategies
    # -------------------------------------------------------------------------

    def _generate_hybrid_recommendations(
        self,
        db: Session,
        context: Dict[str, Any],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations using hybrid approach.

        Combines multiple signals:
        - Behavioral patterns
        - Explicit preferences
        - Popularity metrics
        - Diversity/novelty

        Args:
            db: Database session
            context: Visitor context data
            limit: Number of candidates to generate

        Returns:
            List of hostel candidates with metadata
        """
        visitor_id = context["visitor_id"]

        # Get candidates from different sources
        behavioral_hostels = self._get_behavioral_candidates(db, context)
        preference_hostels = self._get_preference_candidates(db, context)
        popular_hostels = self._get_popular_candidates(db, context)

        # Combine and deduplicate
        all_candidates = {}

        for hostel in behavioral_hostels:
            hostel_id = hostel["hostel_id"]
            all_candidates[hostel_id] = {
                **hostel,
                "behavioral_score": hostel.get("score", 0.5),
            }

        for hostel in preference_hostels:
            hostel_id = hostel["hostel_id"]
            if hostel_id in all_candidates:
                all_candidates[hostel_id]["preference_score"] = hostel.get("score", 0.5)
            else:
                all_candidates[hostel_id] = {
                    **hostel,
                    "preference_score": hostel.get("score", 0.5),
                }

        for hostel in popular_hostels:
            hostel_id = hostel["hostel_id"]
            if hostel_id in all_candidates:
                all_candidates[hostel_id]["popularity_score"] = hostel.get("score", 0.5)
            else:
                all_candidates[hostel_id] = {
                    **hostel,
                    "popularity_score": hostel.get("score", 0.5),
                }

        return list(all_candidates.values())[:limit]

    def _generate_behavioral_recommendations(
        self,
        db: Session,
        context: Dict[str, Any],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on visitor behavior.

        Args:
            db: Database session
            context: Visitor context data
            limit: Number of candidates to generate

        Returns:
            List of hostel candidates
        """
        return self._get_behavioral_candidates(db, context)[:limit]

    def _generate_popular_recommendations(
        self,
        db: Session,
        context: Dict[str, Any],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on popularity.

        Args:
            db: Database session
            context: Visitor context data
            limit: Number of candidates to generate

        Returns:
            List of hostel candidates
        """
        return self._get_popular_candidates(db, context)[:limit]

    def _generate_preference_recommendations(
        self,
        db: Session,
        context: Dict[str, Any],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on explicit preferences.

        Args:
            db: Database session
            context: Visitor context data
            limit: Number of candidates to generate

        Returns:
            List of hostel candidates
        """
        return self._get_preference_candidates(db, context)[:limit]

    # -------------------------------------------------------------------------
    # Candidate Generation Helpers
    # -------------------------------------------------------------------------

    def _get_behavioral_candidates(
        self,
        db: Session,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Get hostel candidates based on behavioral patterns.

        Analyzes:
        - Recently viewed hostels
        - Recent searches
        - Favorite patterns
        - Booking history

        Args:
            db: Database session
            context: Visitor context data

        Returns:
            List of hostel candidates with scores
        """
        visitor_id = context["visitor_id"]
        excluded_ids = context.get("excluded_hostel_ids", set())

        # Get behavioral summary
        behavioral_data = self.aggregate_repo.get_view_and_search_summary(
            db, visitor_id
        )

        preferred_cities = behavioral_data.get("top_cities", [])[:5]
        preferred_room_types = behavioral_data.get("top_room_types", [])[:3]
        preferred_amenities = behavioral_data.get("top_amenities", [])[:10]

        # Find candidates matching behavioral patterns
        candidates = self.recommended_repo.find_recommendation_candidates(
            db=db,
            excluded_hostel_ids=list(excluded_ids),
            preferred_cities=preferred_cities,
            preferred_room_types=preferred_room_types,
            preferred_amenities=preferred_amenities,
            limit=30,
        )

        # Add behavioral scores
        for candidate in candidates:
            candidate["score"] = self._calculate_behavioral_score(
                candidate, behavioral_data
            )

        return sorted(candidates, key=lambda x: x["score"], reverse=True)

    def _get_preference_candidates(
        self,
        db: Session,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Get hostel candidates based on explicit preferences.

        Args:
            db: Database session
            context: Visitor context data

        Returns:
            List of hostel candidates with scores
        """
        visitor_id = context["visitor_id"]
        excluded_ids = context.get("excluded_hostel_ids", set())
        preferences = context.get("preferences", {})

        # Extract preference criteria
        preferred_cities = preferences.get("preferred_cities", [])
        preferred_price_range = preferences.get("price_range", {})
        preferred_amenities = preferences.get("amenities", [])

        # Find candidates matching preferences
        candidates = self.recommended_repo.find_recommendation_candidates(
            db=db,
            excluded_hostel_ids=list(excluded_ids),
            preferred_cities=preferred_cities,
            price_range=preferred_price_range,
            required_amenities=preferred_amenities,
            limit=30,
        )

        # Add preference match scores
        for candidate in candidates:
            candidate["score"] = self._calculate_preference_score(
                candidate, preferences
            )

        return sorted(candidates, key=lambda x: x["score"], reverse=True)

    def _get_popular_candidates(
        self,
        db: Session,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Get popular hostel candidates.

        Args:
            db: Database session
            context: Visitor context data

        Returns:
            List of hostel candidates with popularity scores
        """
        excluded_ids = context.get("excluded_hostel_ids", set())

        # Get trending/popular hostels
        candidates = self.recommended_repo.find_popular_hostels(
            db=db,
            excluded_hostel_ids=list(excluded_ids),
            limit=30,
        )

        # Popularity score already included from repository
        return candidates

    # -------------------------------------------------------------------------
    # Scoring Helpers
    # -------------------------------------------------------------------------

    def _score_candidates(
        self,
        context: Dict[str, Any],
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Score and rank candidates using hybrid scoring.

        Args:
            context: Visitor context data
            candidates: List of hostel candidates

        Returns:
            Sorted list of candidates by final score
        """
        for candidate in candidates:
            # Normalize individual scores
            behavioral_score = candidate.get("behavioral_score", 0.0)
            preference_score = candidate.get("preference_score", 0.0)
            popularity_score = candidate.get("popularity_score", 0.0)

            # Calculate novelty score (inverse of familiarity)
            novelty_score = self._calculate_novelty_score(candidate, context)

            # Weighted combination
            final_score = (
                self.WEIGHTS["behavioral"] * behavioral_score +
                self.WEIGHTS["preference"] * preference_score +
                self.WEIGHTS["popularity"] * popularity_score +
                self.WEIGHTS["novelty"] * novelty_score
            )

            candidate["final_score"] = final_score
            candidate["score_breakdown"] = {
                "behavioral": behavioral_score,
                "preference": preference_score,
                "popularity": popularity_score,
                "novelty": novelty_score,
            }

        # Sort by final score
        return sorted(candidates, key=lambda x: x["final_score"], reverse=True)

    def _calculate_behavioral_score(
        self,
        candidate: Dict[str, Any],
        behavioral_data: Dict[str, Any],
    ) -> float:
        """
        Calculate behavioral match score for a candidate.

        Args:
            candidate: Hostel candidate data
            behavioral_data: Visitor behavioral data

        Returns:
            Score between 0 and 1
        """
        score = 0.0
        max_score = 3.0

        # City match
        top_cities = behavioral_data.get("top_cities", [])
        if candidate.get("city") in top_cities:
            score += 1.0

        # Room type match
        top_room_types = behavioral_data.get("top_room_types", [])
        if candidate.get("room_type") in top_room_types:
            score += 1.0

        # Amenity matches
        top_amenities = set(behavioral_data.get("top_amenities", []))
        candidate_amenities = set(candidate.get("amenities", []))
        amenity_overlap = len(top_amenities & candidate_amenities)
        if amenity_overlap > 0:
            score += min(1.0, amenity_overlap / 5)  # Max 1 point for amenities

        return min(1.0, score / max_score)

    def _calculate_preference_score(
        self,
        candidate: Dict[str, Any],
        preferences: Dict[str, Any],
    ) -> float:
        """
        Calculate preference match score for a candidate.

        Args:
            candidate: Hostel candidate data
            preferences: Visitor preferences

        Returns:
            Score between 0 and 1
        """
        score = 0.0
        max_score = 3.0

        # City preference match
        preferred_cities = preferences.get("preferred_cities", [])
        if candidate.get("city") in preferred_cities:
            score += 1.5

        # Price range match
        price_range = preferences.get("price_range", {})
        if price_range:
            candidate_price = candidate.get("price", 0)
            min_price = price_range.get("min", 0)
            max_price = price_range.get("max", float('inf'))
            if min_price <= candidate_price <= max_price:
                score += 1.0

        # Amenity preferences
        preferred_amenities = set(preferences.get("amenities", []))
        candidate_amenities = set(candidate.get("amenities", []))
        if preferred_amenities:
            match_ratio = len(preferred_amenities & candidate_amenities) / len(preferred_amenities)
            score += 0.5 * match_ratio

        return min(1.0, score / max_score)

    def _calculate_novelty_score(
        self,
        candidate: Dict[str, Any],
        context: Dict[str, Any],
    ) -> float:
        """
        Calculate novelty score (encourages diversity).

        Args:
            candidate: Hostel candidate data
            context: Visitor context data

        Returns:
            Score between 0 and 1
        """
        # Check if hostel is in a new city
        viewed_cities = set(context.get("viewed_cities", []))
        candidate_city = candidate.get("city")

        if candidate_city not in viewed_cities:
            return 1.0

        # Check if different room type
        viewed_room_types = set(context.get("viewed_room_types", []))
        candidate_room_type = candidate.get("room_type")

        if candidate_room_type not in viewed_room_types:
            return 0.7

        return 0.3  # Base novelty for familiar patterns

    # -------------------------------------------------------------------------
    # Context Building
    # -------------------------------------------------------------------------

    def _build_visitor_context(
        self,
        db: Session,
        visitor_id: UUID,
    ) -> Dict[str, Any]:
        """
        Build comprehensive context for recommendation generation.

        Args:
            db: Database session
            visitor_id: UUID of the visitor

        Returns:
            Dictionary with visitor context data
        """
        # Get favorites (to exclude)
        favorites = self.favorite_repo.get_favorites_by_visitor(db, visitor_id)
        excluded_ids = {f.hostel_id for f in favorites}

        # Get behavioral data
        behavioral_summary = self.aggregate_repo.get_view_and_search_summary(
            db, visitor_id
        )

        # Get preferences if available
        visitor = self.visitor_repo.get_full_profile(db, visitor_id)
        preferences = {}
        if hasattr(visitor, 'preferences') and visitor.preferences:
            preferences = visitor.preferences

        # Compile context
        context = {
            "visitor_id": visitor_id,
            "excluded_hostel_ids": excluded_ids,
            "preferences": preferences,
            "behavioral_summary": behavioral_summary,
            "viewed_cities": behavioral_summary.get("top_cities", []),
            "viewed_room_types": behavioral_summary.get("top_room_types", []),
            "engagement_level": getattr(visitor, 'engagement_score', 0),
        }

        return context

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def _get_recent_recommendations(
        self,
        db: Session,
        visitor_id: UUID,
        limit: int,
    ) -> Optional[List[RecommendedHostel]]:
        """
        Get recent recommendations if available and fresh.

        Args:
            db: Database session
            visitor_id: UUID of the visitor
            limit: Number of recommendations needed

        Returns:
            List of recommendations or None if stale/missing
        """
        existing = self.recommended_repo.get_recommendations_for_visitor(
            db, visitor_id, limit=limit
        )

        if not existing:
            return None

        if self._are_recommendations_stale(existing):
            return None

        return [RecommendedHostel.model_validate(r) for r in existing]

    def _are_recommendations_stale(
        self,
        recommendations: List[Any],
    ) -> bool:
        """
        Check if recommendations are stale.

        Args:
            recommendations: List of recommendation objects

        Returns:
            True if stale, False otherwise
        """
        if not recommendations:
            return True

        # Check first recommendation's timestamp
        first_rec = recommendations[0]
        created_at = getattr(first_rec, 'created_at', None)

        if not created_at:
            return True

        age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600

        return age_hours > self.RECOMMENDATION_REFRESH_HOURS