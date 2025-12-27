"""
Search Optimization Service

Uses analytics data to suggest ranking tweaks, synonym additions,
and filter defaults to improve search quality.
"""

from __future__ import annotations

from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict

from sqlalchemy.orm import Session

from app.schemas.search import SearchAnalyticsRequest, SearchAnalytics
from app.repositories.search import SearchAnalyticsRepository
from app.core1.exceptions import ValidationException
from app.core1.logging import logger, LoggingContext


class SearchOptimizationService:
    """
    High-level service for search optimization hints.

    Responsibilities:
    - Analyze analytics and generate optimization suggestions
    - Suggest synonyms based on search patterns
    - Recommend field boost values
    - Propose default filters based on user behavior
    - Identify problematic search terms
    """

    __slots__ = (
        'analytics_repo',
        'min_ctr_threshold',
        'min_synonym_frequency',
        'boost_multiplier',
    )

    def __init__(
        self,
        analytics_repo: SearchAnalyticsRepository,
        min_ctr_threshold: float = 0.2,
        min_synonym_frequency: int = 10,
        boost_multiplier: float = 1.5,
    ) -> None:
        """
        Initialize SearchOptimizationService.

        Args:
            analytics_repo: Repository for search analytics data
            min_ctr_threshold: Minimum CTR to trigger field boosting
            min_synonym_frequency: Minimum frequency to suggest synonyms
            boost_multiplier: Base multiplier for field boosting
        """
        self.analytics_repo = analytics_repo
        self.min_ctr_threshold = min_ctr_threshold
        self.min_synonym_frequency = min_synonym_frequency
        self.boost_multiplier = boost_multiplier

    def analyze_and_suggest_optimizations(
        self,
        db: Session,
        request: SearchAnalyticsRequest,
    ) -> Dict[str, Any]:
        """
        Generate a set of recommendations for improving search.

        Returns a dict with suggestions like:
        - synonyms_to_add: Dict of base terms to synonym lists
        - fields_to_boost: Dict of field names to boost values
        - default_filters: Dict of recommended default filter values
        - problematic_terms: List of zero-result terms needing attention
        - quality_score: Overall search quality score (0-100)

        Args:
            db: SQLAlchemy session
            request: SearchAnalyticsRequest with analysis parameters

        Returns:
            Dictionary containing optimization suggestions

        Raises:
            ValidationException: If no analytics data is available
        """
        with LoggingContext(
            action="analyze_optimizations",
            start_date=str(request.start_date),
            end_date=str(request.end_date),
        ):
            data = self._fetch_analytics_data(db, request)
            
            if not data:
                logger.warning("No search analytics data available for optimization")
                raise ValidationException(
                    "No search analytics data available for the specified period"
                )

            analytics = SearchAnalytics.model_validate(data)

            # Generate optimization suggestions
            synonyms_to_add = self._suggest_synonyms(analytics)
            fields_to_boost = self._suggest_field_boosts(analytics)
            default_filters = self._suggest_default_filters(analytics)
            problematic_terms = self._identify_problematic_terms(
                analytics,
                request.min_searches_threshold,
            )
            quality_score = self._calculate_quality_score(analytics)

            optimization_report = {
                "synonyms_to_add": synonyms_to_add,
                "fields_to_boost": fields_to_boost,
                "default_filters": default_filters,
                "problematic_terms": problematic_terms,
                "quality_score": quality_score,
                "metrics_summary": {
                    "avg_ctr": analytics.metrics.click_through_rate,
                    "avg_results": analytics.metrics.avg_results_count,
                    "zero_result_rate": self._calculate_zero_result_rate(analytics),
                    "top_term_count": len(analytics.top_terms),
                    "trending_term_count": len(analytics.trending_terms),
                },
            }

            logger.info(
                "Optimization analysis completed",
                extra={
                    "quality_score": quality_score,
                    "synonym_count": len(synonyms_to_add),
                    "problematic_term_count": len(problematic_terms),
                }
            )

            return optimization_report

    # -------------------------------------------------------------------------
    # Internal analytics fetching
    # -------------------------------------------------------------------------

    def _fetch_analytics_data(
        self,
        db: Session,
        request: SearchAnalyticsRequest,
    ) -> Dict[str, Any]:
        """
        Fetch analytics data from repository.

        Args:
            db: SQLAlchemy session
            request: SearchAnalyticsRequest

        Returns:
            Analytics data dictionary
        """
        return self.analytics_repo.get_analytics(
            db=db,
            start_date=request.start_date,
            end_date=request.end_date,
            top_terms_limit=request.top_terms_limit,
            trending_terms_limit=request.trending_terms_limit,
            zero_result_terms_limit=request.zero_result_terms_limit,
            min_searches_threshold=request.min_searches_threshold,
        )

    # -------------------------------------------------------------------------
    # Optimization heuristics
    # -------------------------------------------------------------------------

    def _suggest_synonyms(self, analytics: SearchAnalytics) -> Dict[str, List[str]]:
        """
        Heuristic: derive potential synonyms from popular/trending terms.

        Analyzes term patterns to identify:
        - Common abbreviations (PG -> Paying Guest)
        - Gender-specific terms (boys/girls)
        - Location variants (near/around)
        - Type variations (hostel/accommodation/pg)

        Args:
            analytics: SearchAnalytics data

        Returns:
            Dictionary mapping base terms to their synonym lists
        """
        synonyms: Dict[str, Set[str]] = defaultdict(set)
        
        # Combine top and trending terms for analysis
        all_terms = [t.term for t in analytics.top_terms] + [
            t.term for t in analytics.trending_terms
        ]

        for term in all_terms:
            normalized_term = term.lower().strip()
            
            # Skip very short terms
            if len(normalized_term) < 3:
                continue

            # PG variations
            if "pg " in normalized_term or normalized_term.startswith("pg"):
                base = normalized_term.replace("pg ", "").replace("pg", "").strip()
                if base:
                    synonyms["paying guest"].add(normalized_term)
                    synonyms[base].add("pg " + base)
                    synonyms[base].add("paying guest " + base)

            # Gender-specific variations
            if "boys " in normalized_term or normalized_term.endswith(" boys"):
                base = normalized_term.replace("boys", "").strip()
                if base:
                    synonyms[base].update([
                        f"{base} boys",
                        f"{base} male",
                        f"{base} men",
                    ])

            if "girls " in normalized_term or normalized_term.endswith(" girls"):
                base = normalized_term.replace("girls", "").strip()
                if base:
                    synonyms[base].update([
                        f"{base} girls",
                        f"{base} female",
                        f"{base} women",
                    ])

            # Location proximity variations
            if "near " in normalized_term:
                base = normalized_term.replace("near ", "").strip()
                if base:
                    synonyms[base].update([
                        f"near {base}",
                        f"around {base}",
                        f"close to {base}",
                        f"nearby {base}",
                    ])

            # Accommodation type variations
            if "hostel" in normalized_term:
                base = normalized_term.replace("hostel", "").strip()
                if base:
                    synonyms[base].update([
                        f"{base} hostel",
                        f"{base} accommodation",
                        f"{base} pg",
                        f"{base} room",
                    ])

        # Filter synonyms by frequency and convert to lists
        result: Dict[str, List[str]] = {}
        for base, syns in synonyms.items():
            if len(syns) >= 2:  # Only include if we have at least 2 synonyms
                result[base] = sorted(list(syns))

        return result

    def _suggest_field_boosts(self, analytics: SearchAnalytics) -> Dict[str, float]:
        """
        Heuristic: decide which fields to boost based on engagement metrics.

        Analyzes CTR and result patterns to determine optimal field weights:
        - High CTR with many results -> boost descriptive fields
        - High CTR with few results -> boost exact match fields
        - Location-heavy searches -> boost location fields
        - Amenity-focused searches -> boost amenity fields

        Args:
            analytics: SearchAnalytics data

        Returns:
            Dictionary mapping field names to boost multipliers
        """
        boosts: Dict[str, float] = {}
        
        ctr = analytics.metrics.click_through_rate
        avg_results = analytics.metrics.avg_results_count

        # Base boost recommendations
        if ctr > self.min_ctr_threshold:
            if avg_results > 10:
                # High results, high CTR -> users finding what they need
                # Boost descriptive fields
                boosts["name"] = self.boost_multiplier * 1.2
                boosts["description"] = self.boost_multiplier
                boosts["amenities"] = self.boost_multiplier * 1.1
            else:
                # Low results, high CTR -> exact matches working well
                # Boost exact match fields
                boosts["name"] = self.boost_multiplier * 1.5
                boosts["city"] = self.boost_multiplier * 1.3
                boosts["area"] = self.boost_multiplier * 1.2
        else:
            # Low CTR -> need to improve relevance
            boosts["name"] = self.boost_multiplier * 1.3
            boosts["location"] = self.boost_multiplier * 1.2

        # Analyze top terms for pattern-specific boosts
        location_terms = 0
        amenity_terms = 0
        
        location_keywords = {"near", "in", "at", "around", "city", "area"}
        amenity_keywords = {"wifi", "ac", "parking", "food", "laundry", "gym"}

        for term_stat in analytics.top_terms[:20]:  # Check top 20 terms
            term_lower = term_stat.term.lower()
            
            if any(kw in term_lower for kw in location_keywords):
                location_terms += 1
            
            if any(kw in term_lower for kw in amenity_keywords):
                amenity_terms += 1

        # Adjust boosts based on term patterns
        if location_terms > amenity_terms:
            boosts["city"] = boosts.get("city", self.boost_multiplier) * 1.2
            boosts["area"] = boosts.get("area", self.boost_multiplier) * 1.2
            boosts["location"] = boosts.get("location", self.boost_multiplier) * 1.3
        elif amenity_terms > location_terms:
            boosts["amenities"] = boosts.get("amenities", self.boost_multiplier) * 1.3
            boosts["description"] = boosts.get("description", self.boost_multiplier) * 1.1

        return boosts

    def _suggest_default_filters(self, analytics: SearchAnalytics) -> Dict[str, Any]:
        """
        Heuristic: propose default filters based on popular behavior.

        Analyzes search patterns to suggest sensible defaults:
        - Price ranges based on budget distribution
        - Popular room types
        - Commonly searched amenities
        - Typical search radius

        Args:
            analytics: SearchAnalytics data

        Returns:
            Dictionary of recommended default filter values
        """
        defaults: Dict[str, Any] = {}

        # Price defaults based on analytics metrics
        if analytics.metrics.avg_price_low is not None:
            defaults["suggested_min_price"] = int(analytics.metrics.avg_price_low)
        
        if analytics.metrics.avg_price_high is not None:
            defaults["suggested_max_price"] = int(analytics.metrics.avg_price_high)

        # Suggest popular room types from top search terms
        room_type_keywords = {
            "single": "single",
            "double": "double",
            "shared": "shared",
            "triple": "triple",
            "dormitory": "dormitory",
            "private": "private",
        }
        
        popular_room_types: List[str] = []
        for term_stat in analytics.top_terms[:30]:
            term_lower = term_stat.term.lower()
            for keyword, room_type in room_type_keywords.items():
                if keyword in term_lower and room_type not in popular_room_types:
                    popular_room_types.append(room_type)
        
        if popular_room_types:
            defaults["popular_room_types"] = popular_room_types[:3]

        # Suggest radius based on search patterns
        if analytics.metrics.avg_results_count < 5:
            defaults["suggested_radius_km"] = 10  # Expand search radius
        elif analytics.metrics.avg_results_count > 50:
            defaults["suggested_radius_km"] = 3  # Narrow search radius
        else:
            defaults["suggested_radius_km"] = 5  # Default radius

        # Suggest sorting based on CTR
        if analytics.metrics.click_through_rate > 0.3:
            defaults["suggested_sort"] = "relevance"
        else:
            defaults["suggested_sort"] = "price_low_high"

        return defaults

    def _identify_problematic_terms(
        self,
        analytics: SearchAnalytics,
        min_threshold: int,
    ) -> List[Dict[str, Any]]:
        """
        Identify zero-result search terms that need attention.

        Args:
            analytics: SearchAnalytics data
            min_threshold: Minimum search count to be considered problematic

        Returns:
            List of problematic terms with metadata
        """
        problematic_terms: List[Dict[str, Any]] = []

        for zero_result in analytics.zero_result_terms:
            if zero_result.search_count >= min_threshold:
                problematic_terms.append({
                    "term": zero_result.term,
                    "search_count": zero_result.search_count,
                    "severity": self._calculate_term_severity(
                        zero_result.search_count,
                        min_threshold,
                    ),
                    "suggestions": self._generate_term_suggestions(zero_result.term),
                })

        # Sort by severity (descending)
        problematic_terms.sort(key=lambda x: x["severity"], reverse=True)

        return problematic_terms

    @staticmethod
    def _calculate_term_severity(search_count: int, threshold: int) -> str:
        """
        Calculate severity level for problematic terms.

        Args:
            search_count: Number of searches for the term
            threshold: Minimum threshold

        Returns:
            Severity level: "high", "medium", or "low"
        """
        if search_count >= threshold * 5:
            return "high"
        elif search_count >= threshold * 2:
            return "medium"
        else:
            return "low"

    @staticmethod
    def _generate_term_suggestions(term: str) -> List[str]:
        """
        Generate suggestions for problematic search terms.

        Args:
            term: The problematic search term

        Returns:
            List of suggestions to improve the term
        """
        suggestions = []
        
        # Check for common misspellings or variations
        if "pg" in term.lower():
            suggestions.append("Add 'paying guest' as synonym")
        
        if any(word in term.lower() for word in ["boy", "girl", "male", "female"]):
            suggestions.append("Ensure gender filters are properly indexed")
        
        if len(term.split()) == 1:
            suggestions.append("Term might be too broad - suggest autocomplete")
        
        if not suggestions:
            suggestions.append("Review content for matching keywords")
        
        return suggestions

    # -------------------------------------------------------------------------
    # Quality scoring
    # -------------------------------------------------------------------------

    def _calculate_quality_score(self, analytics: SearchAnalytics) -> float:
        """
        Calculate an overall search quality score (0-100).

        Factors:
        - Click-through rate (40% weight)
        - Zero-result rate (30% weight)
        - Average results count (20% weight)
        - Trending term diversity (10% weight)

        Args:
            analytics: SearchAnalytics data

        Returns:
            Quality score from 0 to 100
        """
        # CTR score (0-40 points)
        ctr_score = min(analytics.metrics.click_through_rate * 100, 40)

        # Zero-result score (0-30 points)
        zero_result_rate = self._calculate_zero_result_rate(analytics)
        zero_result_score = max(0, 30 - (zero_result_rate * 30))

        # Results count score (0-20 points)
        avg_results = analytics.metrics.avg_results_count
        if 5 <= avg_results <= 20:
            results_score = 20  # Ideal range
        elif avg_results < 5:
            results_score = (avg_results / 5) * 20
        else:
            results_score = max(0, 20 - ((avg_results - 20) / 10))

        # Diversity score (0-10 points)
        trending_count = len(analytics.trending_terms)
        diversity_score = min(trending_count / 2, 10)  # Max at 20+ trending terms

        total_score = ctr_score + zero_result_score + results_score + diversity_score

        return round(min(total_score, 100), 2)

    @staticmethod
    def _calculate_zero_result_rate(analytics: SearchAnalytics) -> float:
        """
        Calculate the rate of zero-result searches.

        Args:
            analytics: SearchAnalytics data

        Returns:
            Zero-result rate (0.0 to 1.0)
        """
        total_searches = sum(t.search_count for t in analytics.top_terms)
        zero_result_searches = sum(z.search_count for z in analytics.zero_result_terms)
        
        if total_searches == 0:
            return 0.0
        
        return zero_result_searches / (total_searches + zero_result_searches)