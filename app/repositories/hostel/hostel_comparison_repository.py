"""
Hostel comparison repository for competitive analysis and benchmarking.
"""

from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from sqlalchemy import and_, or_, func, desc, asc, text

from app.models.hostel.hostel_comparison import HostelComparison, BenchmarkData, CompetitorAnalysis
from app.models.hostel.hostel import Hostel
from app.repositories.base.base_repository import BaseRepository


class HostelComparisonRepository(BaseRepository[HostelComparison]):
    """Repository for hostel comparison and competitive analysis."""
    
    def __init__(self, session):
        super().__init__(session, HostelComparison)
    
    # ===== Comparison Creation =====
    
    async def create_competitive_comparison(
        self,
        hostel_id: UUID,
        competitor_ids: List[UUID],
        comparison_name: str,
        description: Optional[str] = None
    ) -> HostelComparison:
        """Create a competitive comparison analysis."""
        # Gather comparison metrics
        metrics = await self._gather_comparison_metrics(hostel_id, competitor_ids)
        
        # Calculate rankings and percentiles
        rankings = await self._calculate_rankings(hostel_id, competitor_ids, metrics)
        
        comparison_data = {
            "hostel_id": hostel_id,
            "comparison_name": comparison_name,
            "comparison_type": "competitive",
            "description": description,
            "compared_hostel_ids": {"hostels": [str(hid) for hid in competitor_ids]},
            "metrics": metrics,
            "price_ranking": rankings.get("price_ranking"),
            "price_percentile": rankings.get("price_percentile"),
            "rating_ranking": rankings.get("rating_ranking"),
            "rating_percentile": rankings.get("rating_percentile"),
            "occupancy_ranking": rankings.get("occupancy_ranking"),
            "occupancy_percentile": rankings.get("occupancy_percentile"),
            "overall_ranking": rankings.get("overall_ranking"),
            "performance_score": rankings.get("performance_score"),
            "valid_from": datetime.utcnow(),
            "valid_until": datetime.utcnow() + timedelta(days=30),
            "is_active": True,
            "generated_by": "system"
        }
        
        # Generate competitive insights
        insights = await self._generate_competitive_insights(hostel_id, competitor_ids, metrics)
        comparison_data.update(insights)
        
        return await self.create(comparison_data)
    
    async def create_regional_comparison(
        self,
        hostel_id: UUID,
        city: str,
        state: str,
        radius_km: float = 20.0
    ) -> HostelComparison:
        """Create regional comparison with nearby hostels."""
        # Find nearby hostels
        hostel = await self.session.query(Hostel).filter(Hostel.id == hostel_id).first()
        if not hostel:
            raise ValueError(f"Hostel {hostel_id} not found")
        
        # Find hostels in the same region
        nearby_hostels = await self.session.query(Hostel).filter(
            and_(
                Hostel.id != hostel_id,
                Hostel.is_active == True,
                or_(
                    and_(Hostel.city == city, Hostel.state == state),
                    # Add distance calculation if lat/lng available
                    and_(
                        Hostel.latitude.isnot(None),
                        Hostel.longitude.isnot(None),
                        func.acos(
                            func.cos(func.radians(hostel.latitude)) *
                            func.cos(func.radians(Hostel.latitude)) *
                            func.cos(func.radians(Hostel.longitude) - func.radians(hostel.longitude)) +
                            func.sin(func.radians(hostel.latitude)) *
                            func.sin(func.radians(Hostel.latitude))
                        ) * 6371 <= radius_km
                    ) if hostel.latitude and hostel.longitude else text("1=0")
                )
            )
        ).limit(20).all()
        
        competitor_ids = [h.id for h in nearby_hostels]
        
        return await self.create_competitive_comparison(
            hostel_id,
            competitor_ids,
            f"Regional Comparison - {city}, {state}",
            f"Comparison with hostels in {city}, {state} within {radius_km}km radius"
        )
    
    async def _gather_comparison_metrics(
        self,
        hostel_id: UUID,
        competitor_ids: List[UUID]
    ) -> Dict[str, Any]:
        """Gather comprehensive metrics for comparison."""
        all_hostel_ids = [hostel_id] + competitor_ids
        
        hostels = await self.session.query(Hostel).filter(
            Hostel.id.in_(all_hostel_ids)
        ).all()
        
        hostel_dict = {str(h.id): h for h in hostels}
        
        metrics = {
            "hostels": {},
            "summary": {
                "total_hostels": len(hostels),
                "avg_price": 0,
                "avg_rating": 0,
                "avg_occupancy": 0
            }
        }
        
        total_price = 0
        total_rating = 0
        total_occupancy = 0
        count = 0
        
        for hostel in hostels:
            hostel_metrics = {
                "id": str(hostel.id),
                "name": hostel.name,
                "price": float(hostel.starting_price_monthly or 0),
                "rating": float(hostel.average_rating),
                "occupancy": float(hostel.occupancy_percentage),
                "total_beds": hostel.total_beds,
                "available_beds": hostel.available_beds,
                "reviews_count": hostel.total_reviews,
                "amenities_count": len(hostel.amenities or []),
                "is_featured": hostel.is_featured,
                "is_verified": hostel.is_verified
            }
            
            metrics["hostels"][str(hostel.id)] = hostel_metrics
            
            if hostel.starting_price_monthly:
                total_price += float(hostel.starting_price_monthly)
                count += 1
            total_rating += float(hostel.average_rating)
            total_occupancy += float(hostel.occupancy_percentage)
        
        if count > 0:
            metrics["summary"]["avg_price"] = total_price / count
        metrics["summary"]["avg_rating"] = total_rating / len(hostels)
        metrics["summary"]["avg_occupancy"] = total_occupancy / len(hostels)
        
        return metrics
    
    async def _calculate_rankings(
        self,
        hostel_id: UUID,
        competitor_ids: List[UUID],
        metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate rankings and percentiles."""
        all_hostels = metrics["hostels"]
        target_hostel = all_hostels[str(hostel_id)]
        
        # Price ranking (1 = cheapest)
        prices = sorted([h["price"] for h in all_hostels.values() if h["price"] > 0])
        price_ranking = prices.index(target_hostel["price"]) + 1 if target_hostel["price"] > 0 else None
        price_percentile = (price_ranking / len(prices)) * 100 if price_ranking else None
        
        # Rating ranking (1 = highest)
        ratings = sorted([h["rating"] for h in all_hostels.values()], reverse=True)
        rating_ranking = ratings.index(target_hostel["rating"]) + 1
        rating_percentile = (1 - (rating_ranking - 1) / len(ratings)) * 100
        
        # Occupancy ranking (1 = highest)
        occupancies = sorted([h["occupancy"] for h in all_hostels.values()], reverse=True)
        occupancy_ranking = occupancies.index(target_hostel["occupancy"]) + 1
        occupancy_percentile = (1 - (occupancy_ranking - 1) / len(occupancies)) * 100
        
        # Calculate overall performance score
        performance_score = (
            (rating_percentile * 0.4) +
            (occupancy_percentile * 0.3) +
            ((100 - price_percentile) * 0.2 if price_percentile else 0) +
            (10 if target_hostel["is_verified"] else 0) +
            (5 if target_hostel["is_featured"] else 0)
        )
        
        # Overall ranking based on performance score
        scores = []
        for hid, hostel in all_hostels.items():
            h_rating_rank = ratings.index(hostel["rating"]) + 1
            h_rating_pct = (1 - (h_rating_rank - 1) / len(ratings)) * 100
            
            h_occ_rank = occupancies.index(hostel["occupancy"]) + 1
            h_occ_pct = (1 - (h_occ_rank - 1) / len(occupancies)) * 100
            
            h_price_pct = 50  # Default if no price
            if hostel["price"] > 0 and hostel["price"] in prices:
                h_price_rank = prices.index(hostel["price"]) + 1
                h_price_pct = (h_price_rank / len(prices)) * 100
            
            h_score = (
                (h_rating_pct * 0.4) +
                (h_occ_pct * 0.3) +
                ((100 - h_price_pct) * 0.2) +
                (10 if hostel["is_verified"] else 0) +
                (5 if hostel["is_featured"] else 0)
            )
            scores.append((hid, h_score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        overall_ranking = next(i + 1 for i, (hid, _) in enumerate(scores) if hid == str(hostel_id))
        
        return {
            "price_ranking": price_ranking,
            "price_percentile": Decimal(str(round(price_percentile, 2))) if price_percentile else None,
            "rating_ranking": rating_ranking,
            "rating_percentile": Decimal(str(round(rating_percentile, 2))),
            "occupancy_ranking": occupancy_ranking,
            "occupancy_percentile": Decimal(str(round(occupancy_percentile, 2))),
            "overall_ranking": overall_ranking,
            "performance_score": Decimal(str(round(performance_score, 2)))
        }
    
    async def _generate_competitive_insights(
        self,
        hostel_id: UUID,
        competitor_ids: List[UUID],
        metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate competitive advantages, disadvantages, and recommendations."""
        target_metrics = metrics["hostels"][str(hostel_id)]
        competitor_metrics = [metrics["hostels"][str(cid)] for cid in competitor_ids]
        
        advantages = []
        disadvantages = []
        recommendations = []
        
        # Price analysis
        competitor_prices = [c["price"] for c in competitor_metrics if c["price"] > 0]
        if competitor_prices and target_metrics["price"] > 0:
            avg_competitor_price = sum(competitor_prices) / len(competitor_prices)
            if target_metrics["price"] < avg_competitor_price * 0.9:
                advantages.append({
                    "category": "pricing",
                    "description": f"Price is {((avg_competitor_price - target_metrics['price']) / avg_competitor_price) * 100:.1f}% below market average",
                    "impact": "high"
                })
            elif target_metrics["price"] > avg_competitor_price * 1.1:
                disadvantages.append({
                    "category": "pricing",
                    "description": f"Price is {((target_metrics['price'] - avg_competitor_price) / avg_competitor_price) * 100:.1f}% above market average",
                    "impact": "medium"
                })
                recommendations.append({
                    "category": "pricing",
                    "action": "Consider reviewing pricing strategy to be more competitive",
                    "priority": "medium"
                })
        
        # Rating analysis
        competitor_ratings = [c["rating"] for c in competitor_metrics]
        avg_competitor_rating = sum(competitor_ratings) / len(competitor_ratings)
        if target_metrics["rating"] > avg_competitor_rating + 0.3:
            advantages.append({
                "category": "service_quality",
                "description": f"Rating is {target_metrics['rating'] - avg_competitor_rating:.1f} points above average",
                "impact": "high"
            })
        elif target_metrics["rating"] < avg_competitor_rating - 0.3:
            disadvantages.append({
                "category": "service_quality",
                "description": f"Rating is {avg_competitor_rating - target_metrics['rating']:.1f} points below average",
                "impact": "high"
            })
            recommendations.append({
                "category": "service_quality",
                "action": "Focus on improving guest satisfaction and service quality",
                "priority": "high"
            })
        
        # Occupancy analysis
        competitor_occupancies = [c["occupancy"] for c in competitor_metrics]
        avg_competitor_occupancy = sum(competitor_occupancies) / len(competitor_occupancies)
        if target_metrics["occupancy"] > avg_competitor_occupancy + 10:
            advantages.append({
                "category": "demand",
                "description": f"Occupancy is {target_metrics['occupancy'] - avg_competitor_occupancy:.1f}% above market average",
                "impact": "medium"
            })
        elif target_metrics["occupancy"] < avg_competitor_occupancy - 10:
            disadvantages.append({
                "category": "demand",
                "description": f"Occupancy is {avg_competitor_occupancy - target_metrics['occupancy']:.1f}% below market average",
                "impact": "high"
            })
            recommendations.append({
                "category": "marketing",
                "action": "Increase marketing efforts and improve online presence",
                "priority": "high"
            })
        
        return {
            "competitive_advantages": {"advantages": advantages},
            "competitive_disadvantages": {"disadvantages": disadvantages},
            "recommendations": {"recommendations": recommendations}
        }
    
    # ===== Query Operations =====
    
    async def find_active_comparisons(self, hostel_id: UUID) -> List[HostelComparison]:
        """Find active comparisons for a hostel."""
        return await self.find_by_criteria(
            {
                "hostel_id": hostel_id,
                "is_active": True
            },
            custom_filter=or_(
                HostelComparison.valid_until.is_(None),
                HostelComparison.valid_until > datetime.utcnow()
            ),
            order_by=[desc(HostelComparison.generated_at)]
        )
    
    async def find_comparisons_by_type(
        self,
        comparison_type: str,
        limit: int = 10
    ) -> List[HostelComparison]:
        """Find comparisons by type."""
        return await self.find_by_criteria(
            {
                "comparison_type": comparison_type,
                "is_active": True
            },
            order_by=[desc(HostelComparison.generated_at)],
            limit=limit
        )


class BenchmarkDataRepository(BaseRepository[BenchmarkData]):
    """Repository for industry and regional benchmark data."""
    
    def __init__(self, session):
        super().__init__(session, BenchmarkData)
    
    async def create_industry_benchmark(
        self,
        category: str,
        region: Optional[str] = None,
        period_start: datetime = None,
        period_end: datetime = None
    ) -> BenchmarkData:
        """Create industry benchmark data."""
        if not period_start:
            period_end = datetime.utcnow()
            period_start = period_end - timedelta(days=90)  # Last 3 months
        
        # Gather industry data
        metrics = await self._gather_industry_metrics(category, region, period_start, period_end)
        sample_hostels = await self._get_sample_hostels(category, region)
        
        benchmark_data = {
            "benchmark_type": "industry",
            "category": category,
            "region": region,
            "period_start": period_start,
            "period_end": period_end,
            "metrics": metrics,
            "sample_size": len(sample_hostels),
            "confidence_level": Decimal("95.0"),
            "avg_occupancy_rate": metrics.get("avg_occupancy", Decimal("0")),
            "avg_pricing": metrics.get("avg_pricing", Decimal("0")),
            "avg_rating": metrics.get("avg_rating", Decimal("0")),
            "data_source": "platform_data",
            "verified": True
        }
        
        return await self.create(benchmark_data)
    
    async def _gather_industry_metrics(
        self,
        category: str,
        region: Optional[str],
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """Gather industry metrics for benchmarking."""
        # Build query based on criteria
        query = self.session.query(Hostel).filter(Hostel.is_active == True)
        
        if region:
            query = query.filter(Hostel.state == region)
        
        hostels = await query.all()
        
        if not hostels:
            return {}
        
        # Calculate aggregate metrics
        metrics = {
            "total_hostels": len(hostels),
            "avg_occupancy": Decimal(str(sum(float(h.occupancy_percentage) for h in hostels) / len(hostels))),
            "avg_pricing": Decimal(str(sum(float(h.starting_price_monthly or 0) for h in hostels if h.starting_price_monthly) / max(1, len([h for h in hostels if h.starting_price_monthly])))),
            "avg_rating": Decimal(str(sum(float(h.average_rating) for h in hostels) / len(hostels))),
            "avg_beds": sum(h.total_beds for h in hostels) / len(hostels),
            "pricing_distribution": {
                "min": float(min(h.starting_price_monthly or 0 for h in hostels)),
                "max": float(max(h.starting_price_monthly or 0 for h in hostels)),
                "median": 0  # Calculate median
            }
        }
        
        return metrics
    
    async def _get_sample_hostels(self, category: str, region: Optional[str]) -> List[Hostel]:
        """Get sample hostels for benchmark calculation."""
        query = self.session.query(Hostel).filter(Hostel.is_active == True)
        
        if region:
            query = query.filter(Hostel.state == region)
        
        return await query.all()
    
    async def find_latest_benchmark(
        self,
        benchmark_type: str,
        category: str,
        region: Optional[str] = None
    ) -> Optional[BenchmarkData]:
        """Find the latest benchmark data."""
        criteria = {
            "benchmark_type": benchmark_type,
            "category": category
        }
        if region:
            criteria["region"] = region
        
        return await self.find_one_by_criteria(
            criteria,
            order_by=[desc(BenchmarkData.period_end)]
        )


class CompetitorAnalysisRepository(BaseRepository[CompetitorAnalysis]):
    """Repository for detailed competitor analysis."""
    
    def __init__(self, session):
        super().__init__(session, CompetitorAnalysis)
    
    async def create_competitor_analysis(
        self,
        hostel_id: UUID,
        competitor_hostel_id: UUID
    ) -> CompetitorAnalysis:
        """Create detailed competitor analysis."""
        # Get both hostels
        hostel = await self.session.query(Hostel).filter(Hostel.id == hostel_id).first()
        competitor = await self.session.query(Hostel).filter(Hostel.id == competitor_hostel_id).first()
        
        if not hostel or not competitor:
            raise ValueError("One or both hostels not found")
        
        # Calculate metrics comparison
        competitor_metrics = {
            "name": competitor.name,
            "price": float(competitor.starting_price_monthly or 0),
            "rating": float(competitor.average_rating),
            "occupancy": float(competitor.occupancy_percentage),
            "beds": competitor.total_beds,
            "reviews": competitor.total_reviews,
            "amenities": len(competitor.amenities or [])
        }
        
        # Calculate differences
        price_diff = float(hostel.starting_price_monthly or 0) - float(competitor.starting_price_monthly or 0)
        rating_diff = float(hostel.average_rating) - float(competitor.average_rating)
        occupancy_diff = float(hostel.occupancy_percentage) - float(competitor.occupancy_percentage)
        
        # Generate insights
        threats = []
        opportunities = []
        actions = []
        
        if rating_diff < -0.5:
            threats.append({
                "type": "service_quality",
                "description": f"Competitor has significantly higher rating ({competitor.average_rating:.1f} vs {hostel.average_rating:.1f})",
                "severity": "high"
            })
            actions.append({
                "category": "service_improvement",
                "action": "Analyze competitor's service standards and implement improvements",
                "timeline": "immediate"
            })
        
        if price_diff > competitor.starting_price_monthly * 0.15:
            threats.append({
                "type": "pricing",
                "description": f"Our pricing is {(price_diff / competitor.starting_price_monthly * 100):.1f}% higher",
                "severity": "medium"
            })
        
        if occupancy_diff < -15:
            opportunities.append({
                "type": "demand",
                "description": "Low occupancy indicates potential for improved marketing and pricing strategy",
                "potential": "high"
            })
        
        analysis_data = {
            "hostel_id": hostel_id,
            "competitor_hostel_id": competitor_hostel_id,
            "analysis_date": datetime.utcnow(),
            "competitor_metrics": competitor_metrics,
            "price_difference": Decimal(str(price_diff)),
            "rating_difference": Decimal(str(rating_diff)),
            "occupancy_difference": Decimal(str(occupancy_diff)),
            "competitive_threats": {"threats": threats},
            "opportunities": {"opportunities": opportunities},
            "recommended_actions": {"actions": actions},
            "action_priority": "medium" if threats or opportunities else "low"
        }
        
        return await self.create(analysis_data)
    
    async def find_competitor_analyses(
        self,
        hostel_id: UUID,
        days_back: int = 30
    ) -> List[CompetitorAnalysis]:
        """Find recent competitor analyses for a hostel."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        return await self.find_by_criteria(
            {"hostel_id": hostel_id},
            custom_filter=CompetitorAnalysis.analysis_date >= cutoff_date,
            order_by=[desc(CompetitorAnalysis.analysis_date)]
        )
    
    async def get_competitive_landscape(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """Get comprehensive competitive landscape analysis."""
        analyses = await self.find_competitor_analyses(hostel_id, days_back=90)
        
        if not analyses:
            return {"message": "No competitor analysis available"}
        
        # Aggregate insights
        total_threats = sum(len(a.competitive_threats.get("threats", [])) for a in analyses)
        total_opportunities = sum(len(a.opportunities.get("opportunities", [])) for a in analyses)
        
        avg_price_diff = sum(float(a.price_difference) for a in analyses) / len(analyses)
        avg_rating_diff = sum(float(a.rating_difference) for a in analyses) / len(analyses)
        avg_occupancy_diff = sum(float(a.occupancy_difference) for a in analyses) / len(analyses)
        
        return {
            "analyses_count": len(analyses),
            "competitive_position": {
                "avg_price_difference": avg_price_diff,
                "avg_rating_difference": avg_rating_diff,
                "avg_occupancy_difference": avg_occupancy_diff
            },
            "threats_count": total_threats,
            "opportunities_count": total_opportunities,
            "last_analysis_date": analyses[0].analysis_date if analyses else None,
            "competitive_strength": "strong" if avg_rating_diff > 0 and avg_occupancy_diff > 0 else "needs_improvement"
        }