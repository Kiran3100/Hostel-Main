"""
Hostel aggregate repository for complex cross-model operations.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy import (
    and_, or_, select, update, delete, func, case, 
    text, distinct, exists, join
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload, contains_eager
from sqlalchemy.sql import Select

from app.models.hostel.hostel import Hostel
from app.models.hostel.hostel_settings import HostelSettings
from app.models.hostel.hostel_amenity import HostelAmenity, AmenityCategory
from app.models.hostel.hostel_analytics import HostelAnalytic, OccupancyTrend, RevenueTrend
from app.models.hostel.hostel_media import HostelMedia
from app.models.hostel.hostel_policy import HostelPolicy
from app.models.room.room import Room
from app.models.student.student import Student
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.specifications import Specification
from app.core1.exceptions import HostelNotFoundError, ValidationError


class HostelAggregateRepository(BaseRepository[Hostel]):
    """
    Hostel aggregate repository for complex operations across multiple models.
    
    Provides comprehensive hostel management with cross-model operations,
    analytics, reporting, and business intelligence features.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(Hostel, session)

    async def get_hostel_with_complete_details(self, hostel_id: UUID) -> Optional[Hostel]:
        """
        Get hostel with all related data loaded.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Hostel with all related data or None
        """
        query = (
            select(Hostel)
            .where(Hostel.id == hostel_id)
            .options(
                selectinload(Hostel.rooms),
                selectinload(Hostel.students),
                selectinload(Hostel.amenity_details),
                selectinload(Hostel.media_items),
                selectinload(Hostel.policies),
                selectinload(Hostel.settings)
            )
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_hostel_dashboard_data(self, hostel_id: UUID) -> Dict:
        """
        Get comprehensive dashboard data for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Dictionary with dashboard metrics and data
        """
        hostel = await self.get_hostel_with_complete_details(hostel_id)
        if not hostel:
            raise HostelNotFoundError(f"Hostel {hostel_id} not found")

        # Get current metrics
        total_rooms = await self._get_total_rooms(hostel_id)
        occupied_rooms = await self._get_occupied_rooms(hostel_id)
        total_students = await self._get_total_students(hostel_id)
        pending_requests = await self._get_pending_requests(hostel_id)
        monthly_revenue = await self._get_monthly_revenue(hostel_id)
        occupancy_rate = await self._calculate_occupancy_rate(hostel_id)
        
        # Get trends
        occupancy_trend = await self._get_occupancy_trend(hostel_id, days=30)
        revenue_trend = await self._get_revenue_trend(hostel_id, days=30)
        
        return {
            'hostel_info': {
                'id': hostel.id,
                'name': hostel.name,
                'type': hostel.hostel_type,
                'status': hostel.status,
                'total_capacity': hostel.total_beds,
                'current_occupancy': hostel.occupied_beds,
                'occupancy_percentage': hostel.occupancy_percentage,
                'average_rating': hostel.average_rating,
                'total_reviews': hostel.total_reviews
            },
            'capacity_metrics': {
                'total_rooms': total_rooms,
                'occupied_rooms': occupied_rooms,
                'available_rooms': total_rooms - occupied_rooms,
                'total_students': total_students,
                'occupancy_rate': occupancy_rate
            },
            'financial_metrics': {
                'monthly_revenue': monthly_revenue,
                'outstanding_payments': hostel.outstanding_payments,
                'starting_price': hostel.starting_price_monthly,
                'currency': hostel.currency
            },
            'operational_metrics': {
                'pending_bookings': pending_requests.get('bookings', 0),
                'pending_complaints': pending_requests.get('complaints', 0),
                'pending_maintenance': pending_requests.get('maintenance', 0),
                'active_policies': len([p for p in hostel.policies if p.is_active])
            },
            'trends': {
                'occupancy_trend': occupancy_trend,
                'revenue_trend': revenue_trend
            },
            'amenities_summary': await self._get_amenities_summary(hostel_id),
            'recent_activities': await self._get_recent_activities(hostel_id, limit=10)
        }

    async def search_hostels(
        self,
        criteria: Dict,
        pagination: Optional[Dict] = None,
        include_analytics: bool = False
    ) -> Dict:
        """
        Advanced hostel search with multiple criteria and analytics.
        
        Args:
            criteria: Search criteria dictionary
            pagination: Pagination parameters
            include_analytics: Whether to include analytics data
            
        Returns:
            Search results with metadata
        """
        query = self._build_search_query(criteria)
        
        # Apply pagination
        if pagination:
            offset = (pagination.get('page', 1) - 1) * pagination.get('size', 20)
            query = query.offset(offset).limit(pagination.get('size', 20))

        # Execute query
        result = await self.session.execute(query)
        hostels = result.scalars().all()

        # Get total count for pagination
        count_query = self._build_search_query(criteria, count_only=True)
        count_result = await self.session.execute(count_query)
        total_count = count_result.scalar()

        # Prepare response
        response = {
            'hostels': [await self._serialize_hostel_summary(h) for h in hostels],
            'total_count': total_count,
            'page': pagination.get('page', 1) if pagination else 1,
            'size': len(hostels),
            'total_pages': (total_count + pagination.get('size', 20) - 1) // pagination.get('size', 20) if pagination else 1
        }

        # Add analytics if requested
        if include_analytics:
            response['analytics'] = await self._get_search_analytics(criteria, hostels)

        return response

    async def get_hostels_by_location(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Get hostels within a geographic radius with distance calculation.
        
        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_km: Search radius in kilometers
            filters: Additional filters
            
        Returns:
            List of hostels with distance information
        """
        # Haversine formula for distance calculation
        distance_formula = func.acos(
            func.sin(func.radians(latitude)) * func.sin(func.radians(Hostel.latitude)) +
            func.cos(func.radians(latitude)) * func.cos(func.radians(Hostel.latitude)) *
            func.cos(func.radians(longitude) - func.radians(Hostel.longitude))
        ) * 6371  # Earth's radius in km

        query = (
            select(
                Hostel,
                distance_formula.label('distance_km')
            )
            .where(
                and_(
                    Hostel.latitude.isnot(None),
                    Hostel.longitude.isnot(None),
                    Hostel.is_active == True,
                    distance_formula <= radius_km
                )
            )
            .order_by(distance_formula.asc())
        )

        # Apply additional filters
        if filters:
            query = self._apply_filters(query, filters)

        result = await self.session.execute(query)
        rows = result.fetchall()

        return [
            {
                **await self._serialize_hostel_summary(row.Hostel),
                'distance_km': float(row.distance_km),
                'distance_formatted': f"{row.distance_km:.1f} km"
            }
            for row in rows
        ]

    async def get_hostel_comparison_data(self, hostel_ids: List[UUID]) -> Dict:
        """
        Get comparison data for multiple hostels.
        
        Args:
            hostel_ids: List of hostel UUIDs to compare
            
        Returns:
            Comparison data structure
        """
        # Get basic hostel data
        query = select(Hostel).where(Hostel.id.in_(hostel_ids))
        result = await self.session.execute(query)
        hostels = result.scalars().all()

        if not hostels:
            return {'hostels': [], 'comparison_metrics': {}}

        # Get analytics for each hostel
        analytics_data = await self._get_bulk_analytics_data(hostel_ids)
        
        # Get amenities comparison
        amenities_comparison = await self._get_amenities_comparison(hostel_ids)
        
        # Calculate comparison metrics
        comparison_metrics = {
            'price_range': {
                'min': min(h.starting_price_monthly for h in hostels if h.starting_price_monthly),
                'max': max(h.starting_price_monthly for h in hostels if h.starting_price_monthly),
                'average': sum(h.starting_price_monthly for h in hostels if h.starting_price_monthly) / len([h for h in hostels if h.starting_price_monthly])
            },
            'occupancy_comparison': {
                h.id: {
                    'current': float(h.occupancy_percentage),
                    'capacity': h.total_beds,
                    'occupied': h.occupied_beds
                }
                for h in hostels
            },
            'rating_comparison': {
                h.id: {
                    'rating': float(h.average_rating),
                    'reviews': h.total_reviews
                }
                for h in hostels
            },
            'amenities_comparison': amenities_comparison
        }

        return {
            'hostels': [await self._serialize_hostel_summary(h) for h in hostels],
            'comparison_metrics': comparison_metrics,
            'analytics_data': analytics_data
        }

    async def update_hostel_metrics(self, hostel_id: UUID) -> Dict:
        """
        Recalculate and update all hostel metrics.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Updated metrics summary
        """
        hostel = await self.get_by_id(hostel_id)
        if not hostel:
            raise HostelNotFoundError(f"Hostel {hostel_id} not found")

        # Recalculate capacity metrics
        room_stats = await self._calculate_room_statistics(hostel_id)
        student_stats = await self._calculate_student_statistics(hostel_id)
        financial_stats = await self._calculate_financial_statistics(hostel_id)
        
        # Update hostel record
        update_data = {
            'total_rooms': room_stats['total_rooms'],
            'total_beds': room_stats['total_beds'],
            'occupied_beds': room_stats['occupied_beds'],
            'available_beds': room_stats['available_beds'],
            'total_students': student_stats['total_students'],
            'active_students': student_stats['active_students'],
            'total_revenue_this_month': financial_stats['monthly_revenue'],
            'outstanding_payments': financial_stats['outstanding_payments'],
            'occupancy_percentage': room_stats['occupancy_percentage']
        }

        await self.update(hostel_id, update_data)
        
        return {
            'hostel_id': hostel_id,
            'updated_metrics': update_data,
            'updated_at': datetime.utcnow()
        }

    async def bulk_update_metrics(self, hostel_ids: Optional[List[UUID]] = None) -> Dict:
        """
        Bulk update metrics for multiple hostels.
        
        Args:
            hostel_ids: List of hostel UUIDs (if None, updates all active hostels)
            
        Returns:
            Bulk update summary
        """
        if hostel_ids is None:
            # Get all active hostels
            query = select(Hostel.id).where(Hostel.is_active == True)
            result = await self.session.execute(query)
            hostel_ids = [row[0] for row in result.fetchall()]

        updated_count = 0
        failed_updates = []

        for hostel_id in hostel_ids:
            try:
                await self.update_hostel_metrics(hostel_id)
                updated_count += 1
            except Exception as e:
                failed_updates.append({'hostel_id': hostel_id, 'error': str(e)})

        return {
            'total_requested': len(hostel_ids),
            'successfully_updated': updated_count,
            'failed_updates': failed_updates,
            'update_timestamp': datetime.utcnow()
        }

    async def get_hostel_performance_summary(
        self,
        hostel_id: UUID,
        period_days: int = 30
    ) -> Dict:
        """
        Get comprehensive performance summary for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            period_days: Analysis period in days
            
        Returns:
            Performance summary data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)

        # Get analytics data for the period
        analytics_query = (
            select(HostelAnalytic)
            .where(
                and_(
                    HostelAnalytic.hostel_id == hostel_id,
                    HostelAnalytic.period_start >= start_date,
                    HostelAnalytic.period_end <= end_date
                )
            )
            .order_by(HostelAnalytic.period_start.desc())
        )
        
        analytics_result = await self.session.execute(analytics_query)
        analytics_records = analytics_result.scalars().all()

        if not analytics_records:
            return {'hostel_id': hostel_id, 'message': 'No analytics data available for the specified period'}

        # Calculate performance metrics
        avg_occupancy = sum(a.average_occupancy_rate for a in analytics_records) / len(analytics_records)
        total_revenue = sum(a.total_revenue for a in analytics_records)
        avg_rating = sum(a.average_rating for a in analytics_records) / len(analytics_records)
        conversion_rate = sum(a.conversion_rate for a in analytics_records) / len(analytics_records)

        # Get trend analysis
        occupancy_trend = [float(a.average_occupancy_rate) for a in analytics_records[-7:]]  # Last 7 records
        revenue_trend = [float(a.total_revenue) for a in analytics_records[-7:]]

        return {
            'hostel_id': hostel_id,
            'analysis_period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': period_days
            },
            'performance_metrics': {
                'average_occupancy_rate': float(avg_occupancy),
                'total_revenue': float(total_revenue),
                'average_rating': float(avg_rating),
                'conversion_rate': float(conversion_rate),
                'records_analyzed': len(analytics_records)
            },
            'trends': {
                'occupancy_trend': occupancy_trend,
                'revenue_trend': revenue_trend,
                'trend_direction': {
                    'occupancy': self._calculate_trend_direction(occupancy_trend),
                    'revenue': self._calculate_trend_direction(revenue_trend)
                }
            },
            'performance_score': await self._calculate_performance_score(analytics_records)
        }

    # Private helper methods

    def _build_search_query(self, criteria: Dict, count_only: bool = False) -> Select:
        """Build search query based on criteria."""
        if count_only:
            query = select(func.count(Hostel.id))
        else:
            query = select(Hostel)

        # Base filters
        conditions = [Hostel.is_active == True]

        # Apply search criteria
        if criteria.get('city'):
            conditions.append(Hostel.city.ilike(f"%{criteria['city']}%"))
        
        if criteria.get('hostel_type'):
            conditions.append(Hostel.hostel_type == criteria['hostel_type'])
        
        if criteria.get('min_price'):
            conditions.append(Hostel.starting_price_monthly >= criteria['min_price'])
        
        if criteria.get('max_price'):
            conditions.append(Hostel.starting_price_monthly <= criteria['max_price'])
        
        if criteria.get('min_rating'):
            conditions.append(Hostel.average_rating >= criteria['min_rating'])
        
        if criteria.get('amenities'):
            for amenity in criteria['amenities']:
                conditions.append(Hostel.amenities.contains([amenity]))

        query = query.where(and_(*conditions))

        if not count_only:
            # Default ordering
            if criteria.get('sort_by') == 'price_low':
                query = query.order_by(Hostel.starting_price_monthly.asc())
            elif criteria.get('sort_by') == 'price_high':
                query = query.order_by(Hostel.starting_price_monthly.desc())
            elif criteria.get('sort_by') == 'rating':
                query = query.order_by(Hostel.average_rating.desc())
            else:
                query = query.order_by(Hostel.created_at.desc())

        return query

    async def _get_total_rooms(self, hostel_id: UUID) -> int:
        """Get total rooms count for a hostel."""
        query = select(func.count(Room.id)).where(Room.hostel_id == hostel_id)
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def _get_occupied_rooms(self, hostel_id: UUID) -> int:
        """Get occupied rooms count for a hostel."""
        query = (
            select(func.count(distinct(Room.id)))
            .select_from(Room)
            .join(Student, Room.id == Student.room_id)
            .where(
                and_(
                    Room.hostel_id == hostel_id,
                    Student.status == 'ACTIVE'
                )
            )
        )
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def _get_total_students(self, hostel_id: UUID) -> int:
        """Get total students count for a hostel."""
        query = (
            select(func.count(Student.id))
            .where(
                and_(
                    Student.hostel_id == hostel_id,
                    Student.status == 'ACTIVE'
                )
            )
        )
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def _calculate_trend_direction(self, values: List[float]) -> str:
        """Calculate trend direction from a list of values."""
        if len(values) < 2:
            return 'stable'
        
        # Simple linear trend calculation
        increases = decreases = 0
        for i in range(1, len(values)):
            if values[i] > values[i-1]:
                increases += 1
            elif values[i] < values[i-1]:
                decreases += 1
        
        if increases > decreases:
            return 'increasing'
        elif decreases > increases:
            return 'decreasing'
        else:
            return 'stable'

    async def _serialize_hostel_summary(self, hostel: Hostel) -> Dict:
        """Serialize hostel for summary display."""
        return {
            'id': hostel.id,
            'name': hostel.name,
            'slug': hostel.slug,
            'type': hostel.hostel_type,
            'city': hostel.city,
            'state': hostel.state,
            'starting_price': float(hostel.starting_price_monthly) if hostel.starting_price_monthly else None,
            'currency': hostel.currency,
            'rating': float(hostel.average_rating),
            'reviews': hostel.total_reviews,
            'occupancy_percentage': float(hostel.occupancy_percentage),
            'total_beds': hostel.total_beds,
            'available_beds': hostel.available_beds,
            'cover_image': hostel.cover_image_url,
            'amenities': hostel.amenities[:5],  # Show first 5 amenities
            'is_featured': hostel.is_featured,
            'is_verified': hostel.is_verified
        }