"""
Search Optimization Service

Uses analytics data to suggest ranking tweaks, synonym additions,
and filter defaults to improve search quality.
"""

from __future__ import annotations

from typing import Dict, Any

from sqlalchemy.orm import Session

from app.schemas.search import SearchAnalyticsRequest, SearchAnalytics
from app.repositories.search import SearchAnalyticsRepository
from app.core.exceptions import ValidationException


class SearchOptimizationService:
    """
    High-level service for search optimization hints.

    Responsibilities:
    - Analyze analytics and generate optimization suggestions
      (popular filters, synonyms, boosted fields, etc.)
    """

    def __init__(
        self,
        analytics_repo: SearchAnalyticsRepository,
    ) -> None:
        self.analytics_repo = analytics_repo

    def analyze_and_suggest_optimizations(
        self,
        db: Session,
        request: SearchAnalyticsRequest,
    ) -> Dict[str, Any]:
        """
        Generate a set of recommendations for improving search.

        Returns a dict with suggestions like:
        - synonyms_to_add
        - fields_to_boost
        - default_filters
        - problematic_terms (zero-result)
        """
        data = self.analytics_repo.get_analytics(
            db=db,
            start_date=request.start_date,
            end_date=request.end_date,
            top_terms_limit=request.top_terms_limit,
            trending_terms_limit=request.trending_terms_limit,
            zero_result_terms_limit=request.zero_result_terms_limit,
            min_searches_threshold=request.min_searches_threshold,
        )
        if not data:
            raise ValidationException("No search analytics data available")

        analytics = SearchAnalytics.model_validate(data)

        synonyms_to_add = self._suggest_synonyms(analytics)
        fields_to_boost = self._suggest_field_boosts(analytics)
        default_filters = self._suggest_default_filters(analytics)
        problematic_terms = [
            z.term for z in analytics.zero_result_terms if z.search_count >= request.min_searches_threshold
        ]

        return {
            "synonyms_to_add": synonyms_to_add,
            "fields_to_boost": fields_to_boost,
            "default_filters": default_filters,
            "problematic_terms": problematic_terms,
        }

    # -------------------------------------------------------------------------
    # Internal heuristics
    # -------------------------------------------------------------------------

    def _suggest_synonyms(self, analytics: SearchAnalytics) -> Dict[str, list[str]]:
        """
        Heuristic: derive potential synonyms from popular/trending terms.

        Implementation is intentionally minimal and can be extended.
        """
        synonyms: Dict[str, list[str]] = {}

        for term_stats in analytics.top_terms:
            term = term_stats.term.lower()
            # Example: treat common multi-word phrases as candidates
            if "pg " in term or "boys " in term or "girls " in term:
                base = term.replace("pg ", "").strip()
                synonyms.setdefault(base, []).append(term)

        return synonyms

    def _suggest_field_boosts(self, analytics: SearchAnalytics) -> Dict[str, float]:
        """
        Heuristic: decide which fields to boost based on engagement metrics.
        """
        # Example: if click-through for location-based terms is high,
        # we might boost 'city', 'area' fields.
        boosts: Dict[str, float] = {}

        if analytics.metrics.avg_results_count > 0 and analytics.metrics.click_through_rate > 0.2:
            boosts["location"] = 1.5
            boosts["amenities"] = 1.2

        return boosts

    def _suggest_default_filters(self, analytics: SearchAnalytics) -> Dict[str, Any]:
        """
        Heuristic: propose default filters based on popular behaviour.
        """
        defaults: Dict[str, Any] = {}

        # Example: if budget distribution is skewed low, suggest a default max_price
        if analytics.metrics.avg_results_count > 0:
            defaults["max_price"] = analytics.metrics.avg_price_high or None

        return defaults