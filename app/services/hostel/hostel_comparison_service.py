# --- File: C:\Hostel-Main\app\services\hostel\hostel_comparison_service.py ---
"""
Hostel comparison service for competitive analysis and benchmarking.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hostel.hostel_comparison import HostelComparison, BenchmarkData, CompetitorAnalysis
from app.repositories.hostel.hostel_comparison_repository import (
    HostelComparisonRepository,
    BenchmarkDataRepository,
    CompetitorAnalysisRepository
)
from app.core.exceptions import ValidationError, ResourceNotFoundError
from app.services.base.base_service import BaseService


class HostelComparisonService(BaseService):
    """
    Hostel comparison service for competitive analysis.
    
    Handles hostel comparisons, competitive analysis, benchmarking,
    and market intelligence.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.comparison_repo = HostelComparisonRepository(session)
        self.benchmark_repo = BenchmarkDataRepository(session)
        self.competitor_repo = CompetitorAnalysisRepository(session)

    # ===== Comparison Operations =====

    async def create_competitive_comparison(
        self,
        hostel_id: UUID,
        competitor_ids: List[UUID],
        comparison_name: str,
        description: Optional[str] = None
    ) -> HostelComparison:
        """
        Create a competitive comparison analysis.
        
        Args:
            hostel_id: Primary hostel UUID
            competitor_ids: List of competitor hostel UUIDs
            comparison_name: Name for this comparison
            description: Optional description
            
        Returns:
            Created HostelComparison instance
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate inputs
        if not competitor_ids:
            raise ValidationError("At least one competitor is required")
        
        if len(competitor_ids) > 20:
            raise ValidationError("Maximum 20 competitors allowed per comparison")
        
        if hostel_id in competitor_ids:
            raise ValidationError("Cannot compare hostel with itself")
        
        # Create comparison
        comparison = await self.comparison_repo.create_competitive_comparison(
            hostel_id,
            competitor_ids,
            comparison_name,
            description
        )
        
        # Log event
        await self._log_event('comparison_created', {
            'comparison_id': comparison.id,
            'hostel_id': hostel_id,
            'competitor_count': len(competitor_ids)
        })
        
        return comparison

    async def create_regional_comparison(
        self,
        hostel_id: UUID,
        city: str,
        state: str,
        radius_km: float = 20.0
    ) -> HostelComparison:
        """
        Create regional comparison with nearby hostels.
        
        Args:
            hostel_id: Primary hostel UUID
            city: City name
            state: State name
            radius_km: Search radius in kilometers
            
        Returns:
            Created HostelComparison instance
        """
        return await self.comparison_repo.create_regional_comparison(
            hostel_id,
            city,
            state,
            radius_km
        )

    async def get_comparison_by_id(
        self,
        comparison_id: UUID
    ) -> HostelComparison:
        """
        Get comparison by ID.
        
        Args:
            comparison_id: Comparison UUID
            
        Returns:
            HostelComparison instance
            
        Raises:
            ResourceNotFoundError: If comparison not found
        """
        comparison = await self.comparison_repo.get_by_id(comparison_id)
        if not comparison:
            raise ResourceNotFoundError(f"Comparison {comparison_id} not found")
        
        return comparison

    async def get_active_comparisons(
        self,
        hostel_id: UUID
    ) -> List[HostelComparison]:
        """
        Get active comparisons for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            List of active comparisons
        """
        return await self.comparison_repo.find_active_comparisons(hostel_id)

    async def refresh_comparison(
        self,
        comparison_id: UUID
    ) -> HostelComparison:
        """
        Refresh comparison data with latest metrics.
        
        Args:
            comparison_id: Comparison UUID
            
        Returns:
            Updated HostelComparison instance
        """
        comparison = await self.get_comparison_by_id(comparison_id)
        
        # Re-create comparison with same parameters
        competitor_ids = [
            UUID(cid) for cid in comparison.compared_hostel_ids.get('hostels', [])
        ]
        
        new_comparison = await self.comparison_repo.create_competitive_comparison(
            comparison.hostel_id,
            competitor_ids,
            comparison.comparison_name,
            comparison.description
        )
        
        # Deactivate old comparison
        await self.comparison_repo.update(comparison_id, {
            'is_active': False,
            'valid_until': datetime.utcnow()
        })
        
        return new_comparison

    # ===== Analysis Insights =====

    async def get_competitive_position(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Get competitive position summary for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Competitive position analysis
        """
        comparisons = await self.comparison_repo.find_active_comparisons(hostel_id)
        
        if not comparisons:
            return {
                'hostel_id': hostel_id,
                'status': 'no_comparisons',
                'message': 'No active comparisons available'
            }
        
        # Get latest comparison
        latest = comparisons[0]
        
        # Calculate average position
        rankings = []
        if latest.price_ranking:
            rankings.append(('price', latest.price_ranking))
        if latest.rating_ranking:
            rankings.append(('rating', latest.rating_ranking))
        if latest.occupancy_ranking:
            rankings.append(('occupancy', latest.occupancy_ranking))
        
        avg_ranking = sum(r[1] for r in rankings) / len(rankings) if rankings else None
        
        # Determine position category
        if avg_ranking:
            if avg_ranking <= 3:
                position = 'leader'
            elif avg_ranking <= 7:
                position = 'competitive'
            else:
                position = 'challenger'
        else:
            position = 'unknown'
        
        return {
            'hostel_id': hostel_id,
            'position': position,
            'overall_ranking': latest.overall_ranking,
            'performance_score': float(latest.performance_score) if latest.performance_score else 0,
            'rankings': {
                'price': latest.price_ranking,
                'rating': latest.rating_ranking,
                'occupancy': latest.occupancy_ranking
            },
            'percentiles': {
                'price': float(latest.price_percentile) if latest.price_percentile else None,
                'rating': float(latest.rating_percentile) if latest.rating_percentile else None,
                'occupancy': float(latest.occupancy_percentile) if latest.occupancy_percentile else None
            },
            'advantages_count': len(latest.competitive_advantages.get('advantages', [])) if latest.competitive_advantages else 0,
            'disadvantages_count': len(latest.competitive_disadvantages.get('disadvantages', [])) if latest.competitive_disadvantages else 0,
            'last_updated': latest.generated_at
        }

    async def get_strengths_and_weaknesses(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Get competitive strengths and weaknesses.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Strengths and weaknesses analysis
        """
        comparisons = await self.comparison_repo.find_active_comparisons(hostel_id)
        
        if not comparisons:
            return {
                'strengths': [],
                'weaknesses': [],
                'message': 'No comparison data available'
            }
        
        latest = comparisons[0]
        
        strengths = []
        weaknesses = []
        
        # Analyze advantages
        if latest.competitive_advantages:
            advantages = latest.competitive_advantages.get('advantages', [])
            for adv in advantages:
                strengths.append({
                    'category': adv.get('category'),
                    'description': adv.get('description'),
                    'impact': adv.get('impact', 'medium')
                })
        
        # Analyze disadvantages
        if latest.competitive_disadvantages:
            disadvantages = latest.competitive_disadvantages.get('disadvantages', [])
            for disadv in disadvantages:
                weaknesses.append({
                    'category': disadv.get('category'),
                    'description': disadv.get('description'),
                    'impact': disadv.get('impact', 'medium')
                })
        
        return {
            'hostel_id': hostel_id,
            'strengths': strengths,
            'weaknesses': weaknesses,
            'strength_areas': list(set(s['category'] for s in strengths)),
            'improvement_areas': list(set(w['category'] for w in weaknesses))
        }

    async def get_recommendations(
        self,
        hostel_id: UUID,
        priority_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get strategic recommendations based on comparison.
        
        Args:
            hostel_id: Hostel UUID
            priority_filter: Filter by priority (low, medium, high, urgent)
            
        Returns:
            List of recommendations
        """
        comparisons = await self.comparison_repo.find_active_comparisons(hostel_id)
        
        if not comparisons:
            return []
        
        latest = comparisons[0]
        
        if not latest.recommendations:
            return []
        
        recommendations = latest.recommendations.get('recommendations', [])
        
        # Filter by priority if specified
        if priority_filter:
            recommendations = [
                r for r in recommendations 
                if r.get('priority') == priority_filter
            ]
        
        # Sort by priority
        priority_order = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
        recommendations.sort(
            key=lambda x: priority_order.get(x.get('priority', 'low'), 3)
        )
        
        return recommendations

    # ===== Benchmarking =====

    async def create_industry_benchmark(
        self,
        category: str,
        region: Optional[str] = None
    ) -> BenchmarkData:
        """
        Create industry benchmark data.
        
        Args:
            category: Hostel category
            region: Optional region filter
            
        Returns:
            Created BenchmarkData instance
        """
        return await self.benchmark_repo.create_industry_benchmark(
            category,
            region
        )

    async def get_latest_benchmark(
        self,
        benchmark_type: str,
        category: str,
        region: Optional[str] = None
    ) -> Optional[BenchmarkData]:
        """
        Get latest benchmark data.
        
        Args:
            benchmark_type: Type of benchmark (industry, regional)
            category: Hostel category
            region: Optional region
            
        Returns:
            Latest BenchmarkData if found
        """
        return await self.benchmark_repo.find_latest_benchmark(
            benchmark_type,
            category,
            region
        )

    async def compare_to_benchmark(
        self,
        hostel_id: UUID,
        benchmark_id: UUID
    ) -> Dict[str, Any]:
        """
        Compare hostel metrics against benchmark.
        
        Args:
            hostel_id: Hostel UUID
            benchmark_id: Benchmark UUID
            
        Returns:
            Comparison against benchmark
        """
        benchmark = await self.benchmark_repo.get_by_id(benchmark_id)
        if not benchmark:
            raise ResourceNotFoundError(f"Benchmark {benchmark_id} not found")
        
        # Get hostel from comparison (simplified - would integrate with hostel service)
        comparisons = await self.comparison_repo.find_active_comparisons(hostel_id)
        
        if not comparisons:
            return {
                'error': 'No comparison data available for hostel',
                'hostel_id': hostel_id
            }
        
        latest = comparisons[0]
        hostel_metrics = latest.metrics.get('hostels', {}).get(str(hostel_id), {})
        
        # Compare metrics
        comparison = {
            'hostel_id': hostel_id,
            'benchmark_id': benchmark_id,
            'benchmark_type': benchmark.benchmark_type,
            'category': benchmark.category,
            'region': benchmark.region,
            'comparisons': {}
        }
        
        # Price comparison
        if hostel_metrics.get('price'):
            price_diff = hostel_metrics['price'] - float(benchmark.avg_pricing)
            price_diff_pct = (price_diff / float(benchmark.avg_pricing)) * 100 if benchmark.avg_pricing > 0 else 0
            
            comparison['comparisons']['pricing'] = {
                'hostel_value': hostel_metrics['price'],
                'benchmark_value': float(benchmark.avg_pricing),
                'difference': price_diff,
                'difference_percentage': round(price_diff_pct, 2),
                'status': 'above' if price_diff > 0 else 'below' if price_diff < 0 else 'at_benchmark'
            }
        
        # Occupancy comparison
        if hostel_metrics.get('occupancy'):
            occ_diff = hostel_metrics['occupancy'] - float(benchmark.avg_occupancy_rate)
            occ_diff_pct = (occ_diff / float(benchmark.avg_occupancy_rate)) * 100 if benchmark.avg_occupancy_rate > 0 else 0
            
            comparison['comparisons']['occupancy'] = {
                'hostel_value': hostel_metrics['occupancy'],
                'benchmark_value': float(benchmark.avg_occupancy_rate),
                'difference': occ_diff,
                'difference_percentage': round(occ_diff_pct, 2),
                'status': 'above' if occ_diff > 0 else 'below' if occ_diff < 0 else 'at_benchmark'
            }
        
        # Rating comparison
        if hostel_metrics.get('rating'):
            rating_diff = hostel_metrics['rating'] - float(benchmark.avg_rating)
            
            comparison['comparisons']['rating'] = {
                'hostel_value': hostel_metrics['rating'],
                'benchmark_value': float(benchmark.avg_rating),
                'difference': rating_diff,
                'status': 'above' if rating_diff > 0 else 'below' if rating_diff < 0 else 'at_benchmark'
            }
        
        return comparison

    # ===== Competitor Analysis =====

    async def analyze_competitor(
        self,
        hostel_id: UUID,
        competitor_hostel_id: UUID
    ) -> CompetitorAnalysis:
        """
        Create detailed competitor analysis.
        
        Args:
            hostel_id: Primary hostel UUID
            competitor_hostel_id: Competitor hostel UUID
            
        Returns:
            Created CompetitorAnalysis instance
        """
        if hostel_id == competitor_hostel_id:
            raise ValidationError("Cannot analyze hostel against itself")
        
        return await self.competitor_repo.create_competitor_analysis(
            hostel_id,
            competitor_hostel_id
        )

    async def get_competitor_analyses(
        self,
        hostel_id: UUID,
        days_back: int = 30
    ) -> List[CompetitorAnalysis]:
        """
        Get recent competitor analyses.
        
        Args:
            hostel_id: Hostel UUID
            days_back: Number of days to look back
            
        Returns:
            List of competitor analyses
        """
        return await self.competitor_repo.find_competitor_analyses(
            hostel_id,
            days_back
        )

    async def get_competitive_landscape(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Get comprehensive competitive landscape.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Competitive landscape analysis
        """
        return await self.competitor_repo.get_competitive_landscape(hostel_id)

    # ===== Market Intelligence =====

    async def get_market_position_summary(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Get comprehensive market position summary.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Market position summary
        """
        # Get competitive position
        position = await self.get_competitive_position(hostel_id)
        
        # Get strengths and weaknesses
        swot = await self.get_strengths_and_weaknesses(hostel_id)
        
        # Get recommendations
        recommendations = await self.get_recommendations(hostel_id)
        
        # Get competitive landscape
        landscape = await self.get_competitive_landscape(hostel_id)
        
        return {
            'hostel_id': hostel_id,
            'competitive_position': position,
            'swot_analysis': swot,
            'top_recommendations': recommendations[:5],
            'competitive_landscape': landscape,
            'generated_at': datetime.utcnow()
        }

    async def identify_market_opportunities(
        self,
        hostel_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Identify market opportunities based on analysis.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            List of identified opportunities
        """
        landscape = await self.get_competitive_landscape(hostel_id)
        
        opportunities = []
        
        # Check for pricing opportunities
        if landscape.get('competitive_position', {}).get('avg_price_difference', 0) < -500:
            opportunities.append({
                'type': 'pricing',
                'opportunity': 'Pricing below market average',
                'action': 'Consider strategic price increase to improve revenue',
                'potential_impact': 'high',
                'risk': 'low'
            })
        
        # Check for service improvement opportunities
        if landscape.get('competitive_position', {}).get('avg_rating_difference', 0) > 0.5:
            opportunities.append({
                'type': 'service_excellence',
                'opportunity': 'Superior service quality vs competitors',
                'action': 'Leverage high ratings in marketing campaigns',
                'potential_impact': 'medium',
                'risk': 'low'
            })
        
        # Check for occupancy opportunities
        if landscape.get('competitive_position', {}).get('avg_occupancy_difference', 0) < -15:
            opportunities.append({
                'type': 'demand_generation',
                'opportunity': 'Lower occupancy than market average',
                'action': 'Implement targeted marketing and promotional offers',
                'potential_impact': 'high',
                'risk': 'medium'
            })
        
        return opportunities

    # ===== Helper Methods =====

    async def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log service events for audit and analytics."""
        pass