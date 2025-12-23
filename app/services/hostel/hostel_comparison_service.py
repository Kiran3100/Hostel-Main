# --- File: C:\Hostel-Main\app\services\hostel\hostel_comparison_service.py ---
"""
Cross-hostel comparison service.

Provides comprehensive comparison capabilities for multiple hostels across
various metrics including pricing, amenities, reviews, and performance indicators.
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
import logging
from statistics import mean, median

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity
)
from app.repositories.hostel import HostelComparisonRepository
from app.models.hostel.hostel_comparison import HostelComparison as HostelComparisonModel
from app.schemas.hostel.hostel_comparison import (
    HostelComparisonRequest,
    ComparisonResult,
)
from app.services.hostel.constants import (
    MIN_COMPARISON_HOSTELS,
    MAX_COMPARISON_HOSTELS,
    ERROR_INSUFFICIENT_HOSTELS,
    ERROR_TOO_MANY_HOSTELS,
    SUCCESS_COMPARISON_GENERATED,
)

logger = logging.getLogger(__name__)


class HostelComparisonService(BaseService[HostelComparisonModel, HostelComparisonRepository]):
    """
    Compare multiple hostels across key metrics and features.
    
    Provides functionality for:
    - Multi-dimensional hostel comparison
    - Pricing analysis
    - Feature and amenity comparison
    - Performance benchmarking
    - Competitive analysis
    - Recommendation scoring
    """

    # Comparison dimensions
    COMPARISON_DIMENSIONS = {
        'pricing',
        'amenities',
        'location',
        'reviews',
        'capacity',
        'features',
        'policies',
        'performance'
    }

    # Scoring weights for recommendations
    SCORING_WEIGHTS = {
        'price': 0.25,
        'rating': 0.30,
        'amenities': 0.20,
        'location': 0.15,
        'capacity': 0.10,
    }

    def __init__(self, repository: HostelComparisonRepository, db_session: Session):
        """
        Initialize hostel comparison service.
        
        Args:
            repository: Hostel comparison repository instance
            db_session: Database session
        """
        super().__init__(repository, db_session)
        self._comparison_cache: Dict[str, ComparisonResult] = {}

    # =========================================================================
    # Main Comparison Operations
    # =========================================================================

    def compare(
        self,
        request: HostelComparisonRequest,
        include_recommendations: bool = True,
        use_cache: bool = True,
    ) -> ServiceResult[ComparisonResult]:
        """
        Perform comprehensive hostel comparison.
        
        Args:
            request: Comparison request with hostel IDs and options
            include_recommendations: Whether to include recommendation scores
            use_cache: Whether to use cached comparison results
            
        Returns:
            ServiceResult containing comparison results or error
        """
        try:
            logger.info(
                f"Comparing {len(request.hostel_ids)} hostels: {request.hostel_ids}"
            )
            
            # Validate request
            validation_error = self._validate_comparison_request(request)
            if validation_error:
                return validation_error
            
            # Check cache
            cache_key = self._get_comparison_cache_key(request)
            if use_cache and cache_key in self._comparison_cache:
                logger.debug(f"Cache hit for comparison: {cache_key}")
                return ServiceResult.success(self._comparison_cache[cache_key])
            
            # Perform comparison
            comparison = self.repository.compare(request)
            
            # Enrich with additional analysis
            enriched_comparison = self._enrich_comparison(
                comparison,
                request,
                include_recommendations
            )
            
            # Cache result
            if use_cache:
                self._comparison_cache[cache_key] = enriched_comparison
            
            logger.info("Hostel comparison completed successfully")
            return ServiceResult.success(
                enriched_comparison,
                message=SUCCESS_COMPARISON_GENERATED
            )
            
        except Exception as e:
            return self._handle_exception(e, "compare hostels")

    def compare_by_criteria(
        self,
        hostel_ids: List[UUID],
        criteria: List[str],
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Compare hostels by specific criteria only.
        
        Args:
            hostel_ids: List of hostel UUIDs to compare
            criteria: List of comparison criteria
            
        Returns:
            ServiceResult containing focused comparison
        """
        try:
            # Validate criteria
            invalid_criteria = set(criteria) - self.COMPARISON_DIMENSIONS
            if invalid_criteria:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid comparison criteria: {invalid_criteria}",
                        severity=ErrorSeverity.ERROR,
                        details={"valid_criteria": list(self.COMPARISON_DIMENSIONS)}
                    )
                )
            
            # Create focused request
            request = HostelComparisonRequest(
                hostel_ids=hostel_ids,
                comparison_dimensions=criteria
            )
            
            # Perform comparison
            result = self.compare(request, include_recommendations=False)
            
            if not result.success:
                return result
            
            # Filter to requested criteria only
            filtered_comparison = self._filter_comparison_by_criteria(
                result.data,
                criteria
            )
            
            return ServiceResult.success(filtered_comparison)
            
        except Exception as e:
            return self._handle_exception(e, "compare by criteria")

    # =========================================================================
    # Specialized Comparisons
    # =========================================================================

    def compare_pricing(
        self,
        hostel_ids: List[UUID],
        room_type: Optional[str] = None,
        date_range: Optional[tuple] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Perform detailed pricing comparison.
        
        Args:
            hostel_ids: List of hostel UUIDs
            room_type: Specific room type to compare
            date_range: Optional date range for pricing
            
        Returns:
            ServiceResult containing pricing analysis
        """
        try:
            logger.info(f"Comparing pricing for {len(hostel_ids)} hostels")
            
            pricing_data = self.repository.compare_pricing(
                hostel_ids,
                room_type=room_type,
                date_range=date_range
            )
            
            # Calculate pricing statistics
            analysis = self._analyze_pricing(pricing_data)
            
            return ServiceResult.success(analysis)
            
        except Exception as e:
            return self._handle_exception(e, "compare pricing")

    def compare_amenities(
        self,
        hostel_ids: List[UUID],
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Compare amenities and features across hostels.
        
        Args:
            hostel_ids: List of hostel UUIDs
            
        Returns:
            ServiceResult containing amenity comparison
        """
        try:
            logger.info(f"Comparing amenities for {len(hostel_ids)} hostels")
            
            amenities_data = self.repository.compare_amenities(hostel_ids)
            
            # Analyze amenity coverage and uniqueness
            analysis = self._analyze_amenities(amenities_data)
            
            return ServiceResult.success(analysis)
            
        except Exception as e:
            return self._handle_exception(e, "compare amenities")

    def compare_performance(
        self,
        hostel_ids: List[UUID],
        metrics: Optional[List[str]] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Compare operational performance metrics.
        
        Args:
            hostel_ids: List of hostel UUIDs
            metrics: Specific metrics to compare
            
        Returns:
            ServiceResult containing performance comparison
        """
        try:
            logger.info(f"Comparing performance for {len(hostel_ids)} hostels")
            
            performance_data = self.repository.compare_performance(
                hostel_ids,
                metrics=metrics
            )
            
            # Calculate performance rankings and insights
            analysis = self._analyze_performance(performance_data)
            
            return ServiceResult.success(analysis)
            
        except Exception as e:
            return self._handle_exception(e, "compare performance")

    # =========================================================================
    # Recommendation & Ranking
    # =========================================================================

    def get_recommendations(
        self,
        hostel_ids: List[UUID],
        user_preferences: Optional[Dict[str, Any]] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Generate hostel recommendations with scoring.
        
        Args:
            hostel_ids: List of hostel UUIDs to evaluate
            user_preferences: User preference criteria
            weights: Custom scoring weights
            
        Returns:
            ServiceResult containing ranked recommendations
        """
        try:
            logger.info(
                f"Generating recommendations for {len(hostel_ids)} hostels"
            )
            
            # Use custom weights or defaults
            scoring_weights = weights or self.SCORING_WEIGHTS
            
            # Get comparison data
            request = HostelComparisonRequest(hostel_ids=hostel_ids)
            comparison_result = self.compare(request)
            
            if not comparison_result.success:
                return comparison_result
            
            # Calculate recommendation scores
            recommendations = self._calculate_recommendations(
                comparison_result.data,
                user_preferences,
                scoring_weights
            )
            
            # Sort by score
            recommendations.sort(key=lambda x: x['score'], reverse=True)
            
            return ServiceResult.success(recommendations)
            
        except Exception as e:
            return self._handle_exception(e, "get recommendations")

    def rank_hostels(
        self,
        hostel_ids: List[UUID],
        ranking_criteria: str = 'overall',
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Rank hostels by specific criteria.
        
        Args:
            hostel_ids: List of hostel UUIDs
            ranking_criteria: Criteria for ranking
            
        Returns:
            ServiceResult containing ranked list
        """
        try:
            logger.info(f"Ranking {len(hostel_ids)} hostels by {ranking_criteria}")
            
            # Get comparison data
            request = HostelComparisonRequest(hostel_ids=hostel_ids)
            comparison_result = self.compare(request)
            
            if not comparison_result.success:
                return comparison_result
            
            # Rank by criteria
            rankings = self._rank_by_criteria(
                comparison_result.data,
                ranking_criteria
            )
            
            return ServiceResult.success(rankings)
            
        except Exception as e:
            return self._handle_exception(e, "rank hostels")

    # =========================================================================
    # Analysis & Insights
    # =========================================================================

    def get_competitive_insights(
        self,
        hostel_id: UUID,
        competitor_ids: List[UUID],
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Generate competitive analysis insights for a hostel.
        
        Args:
            hostel_id: UUID of the subject hostel
            competitor_ids: List of competitor hostel UUIDs
            
        Returns:
            ServiceResult containing competitive insights
        """
        try:
            logger.info(
                f"Generating competitive insights for {hostel_id} "
                f"vs {len(competitor_ids)} competitors"
            )
            
            # Compare subject hostel with competitors
            all_hostels = [hostel_id] + competitor_ids
            request = HostelComparisonRequest(hostel_ids=all_hostels)
            
            comparison_result = self.compare(request)
            if not comparison_result.success:
                return comparison_result
            
            # Generate insights
            insights = self._generate_competitive_insights(
                hostel_id,
                comparison_result.data
            )
            
            return ServiceResult.success(insights)
            
        except Exception as e:
            return self._handle_exception(e, "get competitive insights", hostel_id)

    def get_market_position(
        self,
        hostel_id: UUID,
        market_hostels: List[UUID],
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Determine market position of a hostel.
        
        Args:
            hostel_id: UUID of the hostel
            market_hostels: List of hostels in the same market
            
        Returns:
            ServiceResult containing market position analysis
        """
        try:
            logger.info(f"Analyzing market position for {hostel_id}")
            
            all_hostels = list(set([hostel_id] + market_hostels))
            request = HostelComparisonRequest(hostel_ids=all_hostels)
            
            comparison_result = self.compare(request)
            if not comparison_result.success:
                return comparison_result
            
            # Calculate market position
            position = self._calculate_market_position(
                hostel_id,
                comparison_result.data
            )
            
            return ServiceResult.success(position)
            
        except Exception as e:
            return self._handle_exception(e, "get market position", hostel_id)

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _validate_comparison_request(
        self,
        request: HostelComparisonRequest
    ) -> Optional[ServiceResult[ComparisonResult]]:
        """Validate comparison request."""
        if not request.hostel_ids:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=ERROR_INSUFFICIENT_HOSTELS,
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        unique_ids = list(set(request.hostel_ids))
        
        if len(unique_ids) < MIN_COMPARISON_HOSTELS:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=ERROR_INSUFFICIENT_HOSTELS,
                    severity=ErrorSeverity.WARNING,
                    details={
                        "provided": len(unique_ids),
                        "minimum": MIN_COMPARISON_HOSTELS
                    }
                )
            )
        
        if len(unique_ids) > MAX_COMPARISON_HOSTELS:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=ERROR_TOO_MANY_HOSTELS,
                    severity=ErrorSeverity.WARNING,
                    details={
                        "provided": len(unique_ids),
                        "maximum": MAX_COMPARISON_HOSTELS
                    }
                )
            )
        
        return None

    def _get_comparison_cache_key(
        self,
        request: HostelComparisonRequest
    ) -> str:
        """Generate cache key for comparison."""
        sorted_ids = sorted([str(id) for id in request.hostel_ids])
        dimensions = sorted(request.comparison_dimensions or [])
        return f"compare_{'_'.join(sorted_ids)}_{'_'.join(dimensions)}"

    def _enrich_comparison(
        self,
        comparison: ComparisonResult,
        request: HostelComparisonRequest,
        include_recommendations: bool
    ) -> ComparisonResult:
        """Enrich comparison with additional analysis."""
        # Add statistical analysis
        if hasattr(comparison, 'metrics_matrix'):
            comparison.statistics = self._calculate_statistics(
                comparison.metrics_matrix
            )
        
        # Add recommendations if requested
        if include_recommendations:
            comparison.recommendations = self._calculate_recommendations(
                comparison,
                user_preferences=None,
                weights=self.SCORING_WEIGHTS
            )
        
        return comparison

    def _filter_comparison_by_criteria(
        self,
        comparison: ComparisonResult,
        criteria: List[str]
    ) -> Dict[str, Any]:
        """Filter comparison to specific criteria."""
        filtered = {
            "hostels": comparison.hostels if hasattr(comparison, 'hostels') else [],
            "criteria": criteria,
            "comparisons": {}
        }
        
        for criterion in criteria:
            if hasattr(comparison, criterion):
                filtered["comparisons"][criterion] = getattr(comparison, criterion)
        
        return filtered

    def _analyze_pricing(
        self,
        pricing_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze pricing data and generate insights."""
        prices = [p['price'] for p in pricing_data.values() if 'price' in p]
        
        if not prices:
            return {"error": "No pricing data available"}
        
        return {
            "average_price": mean(prices),
            "median_price": median(prices),
            "min_price": min(prices),
            "max_price": max(prices),
            "price_range": max(prices) - min(prices),
            "hostels": pricing_data,
        }

    def _analyze_amenities(
        self,
        amenities_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze amenity coverage and uniqueness."""
        all_amenities = set()
        hostel_amenities = {}
        
        for hostel_id, amenities in amenities_data.items():
            amenity_list = amenities if isinstance(amenities, list) else []
            hostel_amenities[hostel_id] = amenity_list
            all_amenities.update(amenity_list)
        
        # Calculate coverage
        coverage = {}
        for amenity in all_amenities:
            count = sum(1 for ams in hostel_amenities.values() if amenity in ams)
            coverage[amenity] = {
                "count": count,
                "percentage": (count / len(hostel_amenities)) * 100
            }
        
        return {
            "total_unique_amenities": len(all_amenities),
            "coverage": coverage,
            "hostel_amenities": hostel_amenities,
        }

    def _analyze_performance(
        self,
        performance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze performance metrics."""
        return {
            "hostels": performance_data,
            "rankings": self._calculate_performance_rankings(performance_data),
        }

    def _calculate_recommendations(
        self,
        comparison: ComparisonResult,
        user_preferences: Optional[Dict[str, Any]],
        weights: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Calculate recommendation scores for hostels."""
        recommendations = []
        
        # This is a placeholder - implement actual scoring algorithm
        # based on comparison data and weights
        
        return recommendations

    def _rank_by_criteria(
        self,
        comparison: ComparisonResult,
        criteria: str
    ) -> List[Dict[str, Any]]:
        """Rank hostels by specific criteria."""
        # Implement ranking logic based on criteria
        return []

    def _calculate_statistics(
        self,
        metrics_matrix: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate statistical summary of comparison metrics."""
        return {
            "mean": {},
            "median": {},
            "std_dev": {},
        }

    def _generate_competitive_insights(
        self,
        hostel_id: UUID,
        comparison: ComparisonResult
    ) -> Dict[str, Any]:
        """Generate competitive insights for a hostel."""
        return {
            "hostel_id": str(hostel_id),
            "strengths": [],
            "weaknesses": [],
            "opportunities": [],
            "threats": [],
        }

    def _calculate_market_position(
        self,
        hostel_id: UUID,
        comparison: ComparisonResult
    ) -> Dict[str, Any]:
        """Calculate market position for a hostel."""
        return {
            "hostel_id": str(hostel_id),
            "market_segment": "mid-range",
            "percentile_ranking": 0,
            "competitive_advantages": [],
        }

    def _calculate_performance_rankings(
        self,
        performance_data: Dict[str, Any]
    ) -> Dict[str, List]:
        """Calculate performance rankings."""
        return {
            "overall": [],
            "by_metric": {},
        }

    def clear_cache(self) -> None:
        """Clear comparison cache."""
        self._comparison_cache.clear()
        logger.info("Comparison cache cleared")