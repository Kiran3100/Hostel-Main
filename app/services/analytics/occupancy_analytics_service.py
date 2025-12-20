# --- File: C:\Hostel-Main\app\services\analytics\occupancy_analytics_service.py ---
"""
Occupancy Analytics Service - Capacity management and forecasting.

Provides comprehensive occupancy analytics with:
- Occupancy rate tracking
- Room type and floor analysis
- Seasonal pattern detection
- Demand forecasting
- Capacity optimization
"""

from typing import List, Dict, Optional, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from uuid import UUID
import logging

from app.repositories.analytics.occupancy_analytics_repository import (
    OccupancyAnalyticsRepository
)
from app.models.rooms import Room  # Assuming you have this model
from app.models.bookings import Booking


logger = logging.getLogger(__name__)


class OccupancyAnalyticsService:
    """Service for occupancy analytics operations."""
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.repo = OccupancyAnalyticsRepository(db)
    
    # ==================== KPI Generation ====================
    
    def generate_occupancy_kpis(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Any:
        """
        Generate comprehensive occupancy KPIs for period.
        
        Calculates occupancy rates, utilization, and capacity metrics.
        """
        logger.info(f"Generating occupancy KPIs for hostel {hostel_id}")
        
        # Get total bed capacity
        rooms_query = self.db.query(Room)
        if hostel_id:
            rooms_query = rooms_query.filter(Room.hostel_id == hostel_id)
        
        rooms = rooms_query.all()
        total_beds = sum(r.capacity for r in rooms)
        
        # Calculate current occupancy
        current_date = date.today()
        occupied_beds = self.db.query(Booking).filter(
            and_(
                Booking.check_in_date <= current_date,
                Booking.check_out_date >= current_date,
                Booking.status == 'confirmed',
                Booking.hostel_id == hostel_id if hostel_id else True
            )
        ).count()
        
        current_occupancy = (
            Decimal(str((occupied_beds / total_beds) * 100))
            if total_beds > 0 else Decimal('0.00')
        )
        
        # Calculate period averages
        period_days = (period_end - period_start).days + 1
        daily_occupancies = []
        
        current = period_start
        while current <= period_end:
            daily_occupied = self.db.query(Booking).filter(
                and_(
                    Booking.check_in_date <= current,
                    Booking.check_out_date >= current,
                    Booking.status == 'confirmed',
                    Booking.hostel_id == hostel_id if hostel_id else True
                )
            ).count()
            
            daily_occ = (daily_occupied / total_beds * 100) if total_beds > 0 else 0
            daily_occupancies.append(daily_occ)
            
            current += timedelta(days=1)
        
        average_occupancy = (
            Decimal(str(sum(daily_occupancies) / len(daily_occupancies)))
            if daily_occupancies else Decimal('0.00')
        )
        
        peak_occupancy = Decimal(str(max(daily_occupancies))) if daily_occupancies else Decimal('0.00')
        low_occupancy = Decimal(str(min(daily_occupancies))) if daily_occupancies else Decimal('0.00')
        
        # Available and reserved beds
        available_beds = total_beds - occupied_beds
        reserved_beds = 0  # Would calculate from pending bookings
        maintenance_beds = len([r for r in rooms if r.status == 'maintenance'])
        
        # Utilization rate
        usable_beds = total_beds - maintenance_beds
        utilization_rate = (
            Decimal(str((occupied_beds / usable_beds) * 100))
            if usable_beds > 0 else Decimal('0.00')
        )
        
        # Turnover rate (simplified)
        turnover_rate = Decimal('0.00')  # Would calculate from check-ins/check-outs
        
        kpi_data = {
            'current_occupancy_percentage': current_occupancy,
            'average_occupancy_percentage': average_occupancy,
            'peak_occupancy_percentage': peak_occupancy,
            'low_occupancy_percentage': low_occupancy,
            'total_beds': total_beds,
            'occupied_beds': occupied_beds,
            'available_beds': available_beds,
            'reserved_beds': reserved_beds,
            'maintenance_beds': maintenance_beds,
            'utilization_rate': utilization_rate,
            'turnover_rate': turnover_rate,
        }
        
        kpi = self.repo.create_occupancy_kpi(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            kpi_data=kpi_data
        )
        
        # Generate trend points
        self._generate_occupancy_trend_points(
            kpi.id, period_start, period_end, hostel_id, total_beds
        )
        
        return kpi
    
    def _generate_occupancy_trend_points(
        self,
        kpi_id: UUID,
        period_start: date,
        period_end: date,
        hostel_id: Optional[UUID],
        total_beds: int
    ) -> None:
        """Generate daily occupancy trend points."""
        current_date = period_start
        trend_points = []
        
        while current_date <= period_end:
            # Get occupancy for this date
            occupied = self.db.query(Booking).filter(
                and_(
                    Booking.check_in_date <= current_date,
                    Booking.check_out_date >= current_date,
                    Booking.status == 'confirmed',
                    Booking.hostel_id == hostel_id if hostel_id else True
                )
            ).count()
            
            occupancy_percentage = (
                Decimal(str((occupied / total_beds) * 100))
                if total_beds > 0 else Decimal('0.00')
            )
            
            # Check-ins and check-outs
            check_ins = self.db.query(Booking).filter(
                and_(
                    Booking.check_in_date == current_date,
                    Booking.status == 'confirmed',
                    Booking.hostel_id == hostel_id if hostel_id else True
                )
            ).count()
            
            check_outs = self.db.query(Booking).filter(
                and_(
                    Booking.check_out_date == current_date,
                    Booking.status == 'confirmed',
                    Booking.hostel_id == hostel_id if hostel_id else True
                )
            ).count()
            
            trend_points.append({
                'trend_date': current_date,
                'occupancy_percentage': occupancy_percentage,
                'occupied_beds': occupied,
                'total_beds': total_beds,
                'check_ins': check_ins,
                'check_outs': check_outs,
                'net_change': check_ins - check_outs,
            })
            
            current_date += timedelta(days=1)
        
        if trend_points:
            self.repo.add_occupancy_trend_points(kpi_id, trend_points)
    
    # ==================== Room Type Analysis ====================
    
    def generate_room_type_occupancies(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> List[Any]:
        """
        Generate occupancy breakdown by room type.
        
        Analyzes performance of different room types.
        """
        logger.info(f"Generating room type occupancies for hostel {hostel_id}")
        
        # Get rooms grouped by type
        rooms_query = self.db.query(Room)
        if hostel_id:
            rooms_query = rooms_query.filter(Room.hostel_id == hostel_id)
        
        rooms = rooms_query.all()
        
        # Group by room type
        room_types = {}
        for room in rooms:
            room_type = room.room_type or 'Standard'
            if room_type not in room_types:
                room_types[room_type] = []
            room_types[room_type].append(room)
        
        occupancies = []
        
        for room_type, type_rooms in room_types.items():
            total_rooms = len(type_rooms)
            total_beds = sum(r.capacity for r in type_rooms)
            
            # Calculate average occupancy for period
            room_ids = [r.id for r in type_rooms]
            
            occupied_count = 0
            for current_date in self._date_range(period_start, period_end):
                daily_occupied = self.db.query(Booking).filter(
                    and_(
                        Booking.room_id.in_(room_ids),
                        Booking.check_in_date <= current_date,
                        Booking.check_out_date >= current_date,
                        Booking.status == 'confirmed'
                    )
                ).count()
                occupied_count += daily_occupied
            
            period_days = (period_end - period_start).days + 1
            avg_occupied = occupied_count / period_days if period_days > 0 else 0
            
            occupancy_percentage = (
                Decimal(str((avg_occupied / total_beds) * 100))
                if total_beds > 0 else Decimal('0.00')
            )
            
            # Revenue metrics (would calculate from bookings)
            average_rate = Decimal('0.00')
            revenue_generated = Decimal('0.00')
            revenue_per_bed = Decimal('0.00')
            
            occupancy_data = {
                'room_type_name': room_type,
                'total_rooms': total_rooms,
                'total_beds': total_beds,
                'occupied_beds': int(avg_occupied),
                'occupancy_percentage': occupancy_percentage,
                'average_rate': average_rate,
                'revenue_generated': revenue_generated,
                'revenue_per_bed': revenue_per_bed,
            }
            
            occupancy = self.repo.create_room_type_occupancy(
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
                room_type=room_type,
                occupancy_data=occupancy_data
            )
            
            occupancies.append(occupancy)
        
        return occupancies
    
    # ==================== Floor Analysis ====================
    
    def generate_floor_occupancies(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> List[Any]:
        """Generate occupancy breakdown by floor."""
        logger.info(f"Generating floor occupancies for hostel {hostel_id}")
        
        # Get rooms grouped by floor
        rooms_query = self.db.query(Room)
        if hostel_id:
            rooms_query = rooms_query.filter(Room.hostel_id == hostel_id)
        
        rooms = rooms_query.all()
        
        # Group by floor
        floors = {}
        for room in rooms:
            floor_number = room.floor_number or 0
            if floor_number not in floors:
                floors[floor_number] = []
            floors[floor_number].append(room)
        
        occupancies = []
        
        for floor_number, floor_rooms in floors.items():
            total_rooms = len(floor_rooms)
            total_beds = sum(r.capacity for r in floor_rooms)
            
            # Calculate average occupancy
            room_ids = [r.id for r in floor_rooms]
            
            occupied_count = 0
            for current_date in self._date_range(period_start, period_end):
                daily_occupied = self.db.query(Booking).filter(
                    and_(
                        Booking.room_id.in_(room_ids),
                        Booking.check_in_date <= current_date,
                        Booking.check_out_date >= current_date,
                        Booking.status == 'confirmed'
                    )
                ).count()
                occupied_count += daily_occupied
            
            period_days = (period_end - period_start).days + 1
            avg_occupied = occupied_count / period_days if period_days > 0 else 0
            
            occupancy_percentage = (
                Decimal(str((avg_occupied / total_beds) * 100))
                if total_beds > 0 else Decimal('0.00')
            )
            
            occupancy_data = {
                'floor_name': f'Floor {floor_number}',
                'total_rooms': total_rooms,
                'total_beds': total_beds,
                'occupied_beds': int(avg_occupied),
                'occupancy_percentage': occupancy_percentage,
            }
            
            occupancy = self.repo.create_floor_occupancy(
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
                floor_number=floor_number,
                occupancy_data=occupancy_data
            )
            
            occupancies.append(occupancy)
        
        return occupancies
    
    # ==================== Forecasting ====================
    
    def generate_occupancy_forecast(
        self,
        hostel_id: Optional[UUID],
        forecast_days: int = 30,
        model: str = 'moving_average'
    ) -> Any:
        """
        Generate occupancy forecast for upcoming period.
        
        Uses historical data and selected forecasting model.
        """
        logger.info(f"Generating occupancy forecast for hostel {hostel_id}")
        
        forecast = self.repo.generate_occupancy_forecast(
            hostel_id=hostel_id,
            forecast_days=forecast_days,
            model=model
        )
        
        return forecast
    
    # ==================== Seasonal Patterns ====================
    
    def identify_seasonal_patterns(
        self,
        hostel_id: Optional[UUID]
    ) -> List[Any]:
        """
        Identify seasonal occupancy patterns.
        
        Analyzes historical data to detect recurring patterns.
        """
        logger.info(f"Identifying seasonal patterns for hostel {hostel_id}")
        
        patterns = self.repo.identify_seasonal_patterns(
            hostel_id=hostel_id,
            lookback_years=2
        )
        
        return patterns
    
    # ==================== Comprehensive Report ====================
    
    def generate_occupancy_report(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Generate comprehensive occupancy report.
        
        Combines KPIs, breakdowns, and forecasts.
        """
        logger.info(f"Generating occupancy report for hostel {hostel_id}")
        
        # Generate all components
        kpi = self.generate_occupancy_kpis(hostel_id, period_start, period_end)
        room_types = self.generate_room_type_occupancies(hostel_id, period_start, period_end)
        floors = self.generate_floor_occupancies(hostel_id, period_start, period_end)
        forecast = self.generate_occupancy_forecast(hostel_id)
        
        # Create report
        report = self.repo.create_occupancy_report(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            kpi_id=kpi.id,
            forecast_id=forecast.id if forecast else None
        )
        
        return {
            'report': report,
            'kpi': kpi,
            'room_types': room_types,
            'floors': floors,
            'forecast': forecast,
        }
    
    # ==================== Helper Methods ====================
    
    def _date_range(self, start_date: date, end_date: date):
        """Generate date range."""
        current = start_date
        while current <= end_date:
            yield current
            current += timedelta(days=1)
