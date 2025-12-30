"""
Hostel analytics repository for performance tracking and insights.
"""

from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, date, timedelta
from sqlalchemy import and_, or_, func, desc, asc, extract, text
from sqlalchemy.orm import selectinload

from app.models.hostel.hostel_analytics import HostelAnalytic, OccupancyTrend, RevenueTrend
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginatedResult


class HostelAnalyticsRepository(BaseRepository[HostelAnalytic]):
    """Repository for hostel analytics and performance tracking."""
    
    def __init__(self, session):
        super().__init__(session, HostelAnalytic)
    
    # ===== Analytics Generation =====
    
    async def generate_monthly_analytics(
        self,
        hostel_id: UUID,
        year: int,
        month: int
    ) -> HostelAnalytic:
        """Generate comprehensive monthly analytics for a hostel."""
        period_start = date(year, month, 1)
        if month == 12:
            period_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            period_end = date(year, month + 1, 1) - timedelta(days=1)
        
        # Check if analytics already exist
        existing = await self.find_one_by_criteria({
            "hostel_id": hostel_id,
            "period_start": period_start,
            "period_end": period_end,
            "period_type": "monthly"
        })
        
        if existing:
            return existing
        
        # Generate analytics data
        analytics_data = await self._calculate_analytics_data(hostel_id, period_start, period_end)
        analytics_data.update({
            "hostel_id": hostel_id,
            "period_start": period_start,
            "period_end": period_end,
            "period_type": "monthly",
            "generated_at": datetime.utcnow()
        })
        
        return await self.create(analytics_data)
    
    async def generate_yearly_analytics(
        self,
        hostel_id: UUID,
        year: int
    ) -> HostelAnalytic:
        """Generate yearly analytics summary."""
        period_start = date(year, 1, 1)
        period_end = date(year, 12, 31)
        
        # Aggregate monthly data
        monthly_analytics = await self.find_by_criteria({
            "hostel_id": hostel_id,
            "period_type": "monthly"
        }, custom_filter=and_(
            HostelAnalytic.period_start >= period_start,
            HostelAnalytic.period_end <= period_end
        ))
        
        if len(monthly_analytics) < 12:
            # Generate missing monthly analytics first
            for month in range(1, 13):
                await self.generate_monthly_analytics(hostel_id, year, month)
        
        # Calculate yearly aggregates
        analytics_data = await self._calculate_yearly_aggregates(hostel_id, year)
        analytics_data.update({
            "hostel_id": hostel_id,
            "period_start": period_start,
            "period_end": period_end,
            "period_type": "yearly",
            "generated_at": datetime.utcnow()
        })
        
        return await self.create(analytics_data)
    
    async def _calculate_analytics_data(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Calculate analytics data for a specific period."""
        # This would integrate with actual booking, payment, and operational data
        # For now, providing a template structure
        
        return {
            # Occupancy metrics
            "average_occupancy_rate": Decimal("75.50"),
            "peak_occupancy_rate": Decimal("95.00"),
            "lowest_occupancy_rate": Decimal("60.00"),
            "total_bed_nights": 2250,
            
            # Revenue metrics
            "total_revenue": Decimal("450000.00"),
            "rent_revenue": Decimal("350000.00"),
            "mess_revenue": Decimal("80000.00"),
            "other_revenue": Decimal("20000.00"),
            "total_collected": Decimal("420000.00"),
            "total_pending": Decimal("30000.00"),
            "collection_rate": Decimal("93.33"),
            "average_revenue_per_bed": Decimal("15000.00"),
            
            # Booking metrics
            "total_bookings": 45,
            "approved_bookings": 38,
            "rejected_bookings": 5,
            "cancelled_bookings": 2,
            "conversion_rate": Decimal("84.44"),
            "average_booking_value": Decimal("12000.00"),
            
            # Student metrics
            "new_students": 15,
            "departed_students": 8,
            "total_students_end": 85,
            "student_retention_rate": Decimal("90.59"),
            
            # Complaint metrics
            "total_complaints": 12,
            "resolved_complaints": 10,
            "average_resolution_time_hours": Decimal("24.50"),
            "complaint_resolution_rate": Decimal("83.33"),
            
            # Maintenance metrics
            "total_maintenance_requests": 18,
            "completed_maintenance": 16,
            "total_maintenance_cost": Decimal("25000.00"),
            "average_maintenance_time_hours": Decimal("8.75"),
            
            # Review metrics
            "new_reviews": 8,
            "average_rating": Decimal("4.20"),
            "rating_trend": "increasing"
        }
    
    async def _calculate_yearly_aggregates(
        self,
        hostel_id: UUID,
        year: int
    ) -> Dict[str, Any]:
        """Calculate yearly aggregate data from monthly analytics."""
        monthly_data = await self.session.query(HostelAnalytic).filter(
            and_(
                HostelAnalytic.hostel_id == hostel_id,
                HostelAnalytic.period_type == "monthly",
                extract('year', HostelAnalytic.period_start) == year
            )
        ).all()
        
        if not monthly_data:
            return {}
        
        # Aggregate calculations
        total_revenue = sum(analytics.total_revenue for analytics in monthly_data)
        total_bookings = sum(analytics.total_bookings for analytics in monthly_data)
        avg_occupancy = sum(analytics.average_occupancy_rate for analytics in monthly_data) / len(monthly_data)
        
        return {
            "average_occupancy_rate": avg_occupancy,
            "total_revenue": total_revenue,
            "total_bookings": total_bookings,
            # Add more aggregations as needed
        }
    
    # ===== Analytics Queries =====
    
    async def get_performance_trends(
        self,
        hostel_id: UUID,
        period_type: str = "monthly",
        limit: int = 12
    ) -> List[HostelAnalytic]:
        """Get performance trends for a hostel."""
        return await self.find_by_criteria(
            {
                "hostel_id": hostel_id,
                "period_type": period_type
            },
            order_by=[desc(HostelAnalytic.period_start)],
            limit=limit
        )
    
    async def get_comparative_analytics(
        self,
        hostel_ids: List[UUID],
        period_start: date,
        period_end: date
    ) -> List[HostelAnalytic]:
        """Get comparative analytics for multiple hostels."""
        return await self.find_by_criteria(
            custom_filter=and_(
                HostelAnalytic.hostel_id.in_(hostel_ids),
                HostelAnalytic.period_start >= period_start,
                HostelAnalytic.period_end <= period_end
            ),
            order_by=[
                HostelAnalytic.hostel_id,
                HostelAnalytic.period_start
            ]
        )
    
    async def get_top_performing_hostels(
        self,
        period_type: str = "monthly",
        metric: str = "overall_performance_score",
        limit: int = 10
    ) -> List[HostelAnalytic]:
        """Get top performing hostels by specified metric."""
        # Get latest analytics for each hostel
        subquery = self.session.query(
            HostelAnalytic.hostel_id,
            func.max(HostelAnalytic.period_start).label("latest_period")
        ).filter(
            HostelAnalytic.period_type == period_type
        ).group_by(HostelAnalytic.hostel_id).subquery()
        
        order_column = getattr(HostelAnalytic, metric)
        return await self.session.query(HostelAnalytic).join(
            subquery,
            and_(
                HostelAnalytic.hostel_id == subquery.c.hostel_id,
                HostelAnalytic.period_start == subquery.c.latest_period
            )
        ).order_by(desc(order_column)).limit(limit).all()
    
    async def calculate_performance_score(self, analytics_id: UUID) -> Decimal:
        """Calculate and update overall performance score."""
        analytics = await self.get_by_id(analytics_id)
        if not analytics:
            raise ValueError(f"Analytics {analytics_id} not found")
        
        score = analytics.calculate_performance_score()
        await self.session.commit()
        return score
    
    # ===== Insights Generation =====
    
    async def generate_insights(
        self,
        hostel_id: UUID,
        period_months: int = 6
    ) -> Dict[str, Any]:
        """Generate actionable insights based on analytics data."""
        end_date = date.today()
        start_date = end_date - timedelta(days=period_months * 30)
        
        analytics = await self.find_by_criteria(
            {
                "hostel_id": hostel_id,
                "period_type": "monthly"
            },
            custom_filter=and_(
                HostelAnalytic.period_start >= start_date,
                HostelAnalytic.period_end <= end_date
            ),
            order_by=[HostelAnalytic.period_start]
        )
        
        if not analytics:
            return {"insights": [], "recommendations": []}
        
        insights = []
        recommendations = []
        
        # Occupancy trend analysis
        occupancy_rates = [float(a.average_occupancy_rate) for a in analytics]
        if len(occupancy_rates) >= 3:
            recent_trend = occupancy_rates[-3:]
            if all(recent_trend[i] < recent_trend[i-1] for i in range(1, len(recent_trend))):
                insights.append({
                    "type": "warning",
                    "message": "Occupancy rate has been declining over the last 3 months",
                    "metric": "occupancy_rate",
                    "trend": "declining"
                })
                recommendations.append({
                    "priority": "high",
                    "action": "Review pricing strategy and marketing efforts",
                    "category": "occupancy"
                })
        
        # Revenue analysis
        revenue_data = [float(a.total_revenue) for a in analytics]
        avg_revenue = sum(revenue_data) / len(revenue_data)
        latest_revenue = revenue_data[-1] if revenue_data else 0
        
        if latest_revenue < avg_revenue * 0.9:
            insights.append({
                "type": "alert",
                "message": "Recent revenue is 10% below average",
                "metric": "revenue",
                "impact": "financial"
            })
        
        return {
            "insights": insights,
            "recommendations": recommendations,
            "summary": {
                "avg_occupancy": sum(occupancy_rates) / len(occupancy_rates) if occupancy_rates else 0,
                "avg_revenue": avg_revenue,
                "trend_analysis": "stable"  # This would be more sophisticated
            }
        }


class OccupancyTrendRepository(BaseRepository[OccupancyTrend]):
    """Repository for detailed occupancy trend tracking."""
    
    def __init__(self, session):
        super().__init__(session, OccupancyTrend)
    
    async def record_daily_occupancy(
        self,
        hostel_id: UUID,
        data_date: date,
        occupancy_data: Dict[str, Any]
    ) -> OccupancyTrend:
        """Record daily occupancy data."""
        # Check if data already exists
        existing = await self.find_one_by_criteria({
            "hostel_id": hostel_id,
            "data_date": data_date
        })
        
        if existing:
            # Update existing record
            for key, value in occupancy_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await self.session.commit()
            return existing
        
        # Create new record
        occupancy_data.update({
            "hostel_id": hostel_id,
            "data_date": data_date
        })
        
        return await self.create(occupancy_data)
    
    async def get_occupancy_trends(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date
    ) -> List[OccupancyTrend]:
        """Get occupancy trends for a date range."""
        return await self.find_by_criteria(
            {
                "hostel_id": hostel_id
            },
            custom_filter=and_(
                OccupancyTrend.data_date >= start_date,
                OccupancyTrend.data_date <= end_date
            ),
            order_by=[OccupancyTrend.data_date]
        )
    
    async def get_peak_occupancy_days(
        self,
        hostel_id: UUID,
        period_days: int = 30
    ) -> List[OccupancyTrend]:
        """Get days with highest occupancy in the last N days."""
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)
        
        return await self.find_by_criteria(
            {
                "hostel_id": hostel_id
            },
            custom_filter=and_(
                OccupancyTrend.data_date >= start_date,
                OccupancyTrend.data_date <= end_date
            ),
            order_by=[desc(OccupancyTrend.occupancy_rate)],
            limit=10
        )


class RevenueTrendRepository(BaseRepository[RevenueTrend]):
    """Repository for revenue trend tracking and analysis."""
    
    def __init__(self, session):
        super().__init__(session, RevenueTrend)
    
    async def record_daily_revenue(
        self,
        hostel_id: UUID,
        data_date: date,
        revenue_data: Dict[str, Any]
    ) -> RevenueTrend:
        """Record daily revenue data."""
        existing = await self.find_one_by_criteria({
            "hostel_id": hostel_id,
            "data_date": data_date,
            "period_type": "daily"
        })
        
        if existing:
            for key, value in revenue_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await self.session.commit()
            return existing
        
        revenue_data.update({
            "hostel_id": hostel_id,
            "data_date": data_date,
            "period_type": "daily"
        })
        
        return await self.create(revenue_data)
    
    async def get_revenue_trends(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        period_type: str = "daily"
    ) -> List[RevenueTrend]:
        """Get revenue trends for a period."""
        return await self.find_by_criteria(
            {
                "hostel_id": hostel_id,
                "period_type": period_type
            },
            custom_filter=and_(
                RevenueTrend.data_date >= start_date,
                RevenueTrend.data_date <= end_date
            ),
            order_by=[RevenueTrend.data_date]
        )
    
    async def calculate_revenue_growth(
        self,
        hostel_id: UUID,
        current_period: Tuple[date, date],
        comparison_period: Tuple[date, date]
    ) -> Dict[str, Any]:
        """Calculate revenue growth between two periods."""
        current_revenue = await self.session.query(
            func.sum(RevenueTrend.total_revenue)
        ).filter(
            and_(
                RevenueTrend.hostel_id == hostel_id,
                RevenueTrend.data_date >= current_period[0],
                RevenueTrend.data_date <= current_period[1]
            )
        ).scalar()
        
        comparison_revenue = await self.session.query(
            func.sum(RevenueTrend.total_revenue)
        ).filter(
            and_(
                RevenueTrend.hostel_id == hostel_id,
                RevenueTrend.data_date >= comparison_period[0],
                RevenueTrend.data_date <= comparison_period[1]
            )
        ).scalar()
        
        current_revenue = float(current_revenue or 0)
        comparison_revenue = float(comparison_revenue or 0)
        
        growth_rate = 0
        if comparison_revenue > 0:
            growth_rate = ((current_revenue - comparison_revenue) / comparison_revenue) * 100
        
        return {
            "current_revenue": current_revenue,
            "comparison_revenue": comparison_revenue,
            "growth_rate": growth_rate,
            "growth_amount": current_revenue - comparison_revenue
        }