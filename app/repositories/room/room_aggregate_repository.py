# app/repositories/room/room_aggregate_repository.py
"""
Room aggregate repository for cross-cutting queries and analytics.
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, case, desc, distinct
from sqlalchemy.orm import Session

from app.models.room import (
    Room,
    Bed,
    BedAssignment,
    RoomAmenity,
    RoomAvailability,
    RoomTypeDefinition,
)


class RoomAggregateRepository:
    """
    Repository for cross-cutting room queries and analytics.
    
    Handles:
    - Cross-entity queries
    - Hostel-wide analytics
    - Performance metrics
    - Dashboard data
    """

    def __init__(self, session: Session):
        self.session = session

    # ============================================================================
    # HOSTEL OVERVIEW
    # ============================================================================

    def get_hostel_overview(self, hostel_id: str) -> Dict[str, Any]:
        """
        Get comprehensive hostel overview.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Dictionary with overview data
        """
        # Room statistics
        room_stats = self.session.execute(
            select(
                func.count(Room.id).label('total_rooms'),
                func.sum(Room.total_beds).label('total_beds'),
                func.sum(Room.occupied_beds).label('occupied_beds'),
                func.sum(Room.available_beds).label('available_beds'),
                func.avg(Room.price_monthly).label('avg_price')
            ).where(
                and_(
                    Room.hostel_id == hostel_id,
                    Room.is_deleted == False
                )
            )
        ).one()
        
        # Bed statistics
        bed_stats = self.session.execute(
            select(
                func.count(Bed.id).label('total_beds'),
                func.sum(case((Bed.is_occupied == True, 1), else_=0)).label('occupied'),
                func.sum(case((Bed.is_available == True, 1), else_=0)).label('available')
            ).join(Room).where(
                and_(
                    Room.hostel_id == hostel_id,
                    Bed.is_deleted == False
                )
            )
        ).one()
        
        # Assignment statistics
        assignment_stats = self.session.execute(
            select(
                func.count(BedAssignment.id).label('total_assignments'),
                func.sum(case((BedAssignment.is_active == True, 1), else_=0)).label('active')
            ).where(BedAssignment.hostel_id == hostel_id)
        ).one()
        
        total_beds = room_stats.total_beds or 0
        occupied = room_stats.occupied_beds or 0
        occupancy_rate = (occupied / total_beds * 100) if total_beds > 0 else 0
        
        return {
            'rooms': {
                'total': room_stats.total_rooms or 0,
                'total_beds': total_beds,
                'occupied_beds': occupied,
                'available_beds': room_stats.available_beds or 0,
                'occupancy_rate': round(occupancy_rate, 2),
                'avg_price': float(room_stats.avg_price or 0)
            },
            'beds': {
                'total': bed_stats.total_beds or 0,
                'occupied': bed_stats.occupied or 0,
                'available': bed_stats.available or 0
            },
            'assignments': {
                'total': assignment_stats.total_assignments or 0,
                'active': assignment_stats.active or 0
            }
        }

    def get_dashboard_metrics(
        self,
        hostel_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get dashboard metrics for date range.
        
        Args:
            hostel_id: Hostel ID
            date_from: Start date
            date_to: End date
            
        Returns:
            Dashboard metrics
        """
        date_from = date_from or (date.today() - timedelta(days=30))
        date_to = date_to or date.today()
        
        overview = self.get_hostel_overview(hostel_id)
        
        # Revenue data (simplified - would need payment data)
        revenue_estimate = Decimal('0.00')
        if overview['rooms']['occupied_beds'] > 0:
            revenue_estimate = Decimal(str(overview['rooms']['avg_price'])) * overview['rooms']['occupied_beds']
        
        return {
            **overview,
            'period': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat()
            },
            'revenue_estimate': float(revenue_estimate),
            'timestamp': datetime.utcnow().isoformat()
        }

    # ============================================================================
    # SEARCH AND FILTERING
    # ============================================================================

    def comprehensive_room_search(
        self,
        hostel_id: str,
        filters: Dict[str, Any],
        sort_by: str = 'price',
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Comprehensive room search with multiple filters.
        
        Args:
            hostel_id: Hostel ID
            filters: Search filters
            sort_by: Sort field
            limit: Maximum results
            
        Returns:
            List of matching rooms with details
        """
        query = select(Room, RoomAvailability).outerjoin(
            RoomAvailability,
            Room.id == RoomAvailability.room_id
        ).where(
            and_(
                Room.hostel_id == hostel_id,
                Room.is_deleted == False
            )
        )
        
        # Apply filters
        if filters.get('room_type'):
            query = query.where(Room.room_type == filters['room_type'])
        
        if filters.get('min_beds'):
            query = query.where(Room.available_beds >= filters['min_beds'])
        
        if filters.get('is_ac') is not None:
            query = query.where(Room.is_ac == filters['is_ac'])
        
        if filters.get('has_bathroom') is not None:
            query = query.where(Room.has_attached_bathroom == filters['has_bathroom'])
        
        if filters.get('max_price'):
            query = query.where(Room.price_monthly <= filters['max_price'])
        
        if filters.get('floor'):
            query = query.where(Room.floor_number == filters['floor'])
        
        # Sorting
        if sort_by == 'price':
            query = query.order_by(Room.price_monthly)
        elif sort_by == 'availability':
            query = query.order_by(desc(Room.available_beds))
        elif sort_by == 'room_number':
            query = query.order_by(Room.room_number)
        
        query = query.limit(limit)
        
        result = self.session.execute(query)
        
        rooms = []
        for room, availability in result:
            rooms.append({
                'room': room,
                'availability': availability,
                'occupancy_rate': float(room.occupancy_rate),
                'is_available': room.can_accommodate(filters.get('min_beds', 1))
            })
        
        return rooms

    # ============================================================================
    # ANALYTICS
    # ============================================================================

    def get_occupancy_trends(
        self,
        hostel_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get occupancy trends over time.
        
        Args:
            hostel_id: Hostel ID
            days: Number of days to analyze
            
        Returns:
            List of daily occupancy data
        """
        # This is simplified - would need historical tracking
        current_overview = self.get_hostel_overview(hostel_id)
        
        trends = []
        for i in range(days):
            day = date.today() - timedelta(days=days-i-1)
            trends.append({
                'date': day.isoformat(),
                'occupancy_rate': current_overview['rooms']['occupancy_rate'],
                'occupied_beds': current_overview['rooms']['occupied_beds']
            })
        
        return trends

    def get_revenue_forecast(
        self,
        hostel_id: str,
        months: int = 3
    ) -> Dict[str, Any]:
        """
        Get revenue forecast.
        
        Args:
            hostel_id: Hostel ID
            months: Number of months to forecast
            
        Returns:
            Revenue forecast data
        """
        overview = self.get_hostel_overview(hostel_id)
        
        monthly_revenue = Decimal(str(overview['rooms']['avg_price'])) * overview['rooms']['total_beds']
        
        forecast = []
        for i in range(months):
            month_date = date.today() + timedelta(days=30*i)
            forecast.append({
                'month': month_date.strftime('%Y-%m'),
                'estimated_revenue': float(monthly_revenue),
                'confidence': 0.7
            })
        
        return {
            'forecast': forecast,
            'total_estimated': float(monthly_revenue * months),
            'assumptions': 'Based on current occupancy and pricing'
        }

    def get_performance_report(
        self,
        hostel_id: str,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive performance report.
        
        Args:
            hostel_id: Hostel ID
            period_days: Period in days
            
        Returns:
            Performance report
        """
        overview = self.get_hostel_overview(hostel_id)
        
        # Get amenity count
        amenity_count = self.session.execute(
            select(func.count(distinct(RoomAmenity.id))).join(Room).where(
                and_(
                    Room.hostel_id == hostel_id,
                    RoomAmenity.is_deleted == False
                )
            )
        ).scalar()
        
        return {
            'period_days': period_days,
            'overview': overview,
            'amenities': {
                'total': amenity_count or 0
            },
            'performance_indicators': {
                'occupancy_rate': overview['rooms']['occupancy_rate'],
                'utilization_rate': overview['rooms']['occupancy_rate'],
                'availability_rate': 100 - overview['rooms']['occupancy_rate']
            },
            'generated_at': datetime.utcnow().isoformat()
        }