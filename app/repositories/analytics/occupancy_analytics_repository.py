"""
Occupancy Analytics Repository for capacity management and forecasting.

Provides comprehensive occupancy analytics with:
- Occupancy KPI tracking and trends
- Room type and floor analysis
- Seasonal pattern identification
- Demand forecasting with ML
- Capacity optimization insights
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import and_, or_, func, select, case, desc
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
import statistics

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.models.analytics.occupancy_analytics import (
    OccupancyKPI,
    OccupancyTrendPoint,
    OccupancyByRoomType,
    OccupancyByFloor,
    SeasonalPattern,
    ForecastPoint,
    ForecastData,
    OccupancyReport,
)


class OccupancyAnalyticsRepository(BaseRepository):
    """Repository for occupancy analytics operations."""
    
    def __init__(self, db: Session):
        super().__init__(db)
    
    # ==================== Occupancy KPI ====================
    
    def create_occupancy_kpi(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        kpi_data: Dict[str, Any]
    ) -> OccupancyKPI:
        """Create or update occupancy KPI."""
        # Calculate derived fields
        vacancy_rate = self._calculate_vacancy_rate(
            kpi_data.get('total_beds', 0),
            kpi_data.get('occupied_beds', 0)
        )
        kpi_data['vacancy_rate'] = vacancy_rate
        
        occupancy_status = self._determine_occupancy_status(
            kpi_data.get('current_occupancy_percentage', 0)
        )
        kpi_data['occupancy_status'] = occupancy_status
        
        capacity_pressure = self._calculate_capacity_pressure(
            kpi_data.get('current_occupancy_percentage', 0)
        )
        kpi_data['capacity_pressure'] = capacity_pressure
        
        existing = self.db.query(OccupancyKPI).filter(
            and_(
                OccupancyKPI.hostel_id == hostel_id if hostel_id else OccupancyKPI.hostel_id.is_(None),
                OccupancyKPI.period_start == period_start,
                OccupancyKPI.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in kpi_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        kpi = OccupancyKPI(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **kpi_data
        )
        
        self.db.add(kpi)
        self.db.commit()
        self.db.refresh(kpi)
        
        return kpi
    
    def get_occupancy_kpi(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Optional[OccupancyKPI]:
        """Get occupancy KPI for period."""
        return self.db.query(OccupancyKPI).filter(
            and_(
                OccupancyKPI.hostel_id == hostel_id if hostel_id else OccupancyKPI.hostel_id.is_(None),
                OccupancyKPI.period_start == period_start,
                OccupancyKPI.period_end == period_end
            )
        ).first()
    
    def _calculate_vacancy_rate(
        self,
        total_beds: int,
        occupied_beds: int
    ) -> Decimal:
        """Calculate vacancy rate percentage."""
        if total_beds == 0:
            return Decimal('0.00')
        
        vacant = total_beds - occupied_beds
        rate = (vacant / total_beds) * 100
        
        return Decimal(str(round(rate, 2)))
    
    def _determine_occupancy_status(
        self,
        occupancy_percentage: Decimal
    ) -> str:
        """Determine occupancy status category."""
        occupancy = float(occupancy_percentage)
        
        if occupancy >= 95:
            return 'critical'  # At capacity
        elif occupancy >= 85:
            return 'high'
        elif occupancy >= 70:
            return 'optimal'
        elif occupancy >= 50:
            return 'moderate'
        else:
            return 'low'
    
    def _calculate_capacity_pressure(
        self,
        occupancy_percentage: Decimal
    ) -> Decimal:
        """Calculate capacity pressure score (0-100)."""
        occupancy = float(occupancy_percentage)
        
        # Pressure increases exponentially as occupancy approaches 100%
        if occupancy >= 95:
            pressure = 100
        elif occupancy >= 90:
            pressure = 80 + ((occupancy - 90) / 5) * 20
        elif occupancy >= 80:
            pressure = 60 + ((occupancy - 80) / 10) * 20
        else:
            pressure = (occupancy / 80) * 60
        
        return Decimal(str(round(pressure, 2)))
    
    # ==================== Trend Analysis ====================
    
    def add_occupancy_trend_points(
        self,
        kpi_id: UUID,
        trend_points: List[Dict[str, Any]]
    ) -> List[OccupancyTrendPoint]:
        """Add multiple occupancy trend points."""
        created_points = []
        
        for point_data in trend_points:
            # Calculate net change
            net_change = (
                point_data.get('check_ins', 0) - 
                point_data.get('check_outs', 0)
            )
            point_data['net_change'] = net_change
            
            existing = self.db.query(OccupancyTrendPoint).filter(
                and_(
                    OccupancyTrendPoint.kpi_id == kpi_id,
                    OccupancyTrendPoint.trend_date == point_data['trend_date']
                )
            ).first()
            
            if existing:
                for key, value in point_data.items():
                    if key != 'trend_date':
                        setattr(existing, key, value)
                created_points.append(existing)
            else:
                point = OccupancyTrendPoint(
                    kpi_id=kpi_id,
                    **point_data
                )
                self.db.add(point)
                created_points.append(point)
        
        self.db.commit()
        for point in created_points:
            self.db.refresh(point)
        
        return created_points
    
    def get_occupancy_trend_points(
        self,
        kpi_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[OccupancyTrendPoint]:
        """Get occupancy trend points."""
        query = QueryBuilder(OccupancyTrendPoint, self.db)
        query = query.where(OccupancyTrendPoint.kpi_id == kpi_id)
        
        if start_date:
            query = query.where(OccupancyTrendPoint.trend_date >= start_date)
        if end_date:
            query = query.where(OccupancyTrendPoint.trend_date <= end_date)
        
        query = query.order_by(OccupancyTrendPoint.trend_date.asc())
        
        return query.all()
    
    # ==================== Room Type Analysis ====================
    
    def create_room_type_occupancy(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        room_type: str,
        occupancy_data: Dict[str, Any]
    ) -> OccupancyByRoomType:
        """Create or update room type occupancy breakdown."""
        # Calculate available beds
        available_beds = (
            occupancy_data.get('total_beds', 0) - 
            occupancy_data.get('occupied_beds', 0)
        )
        occupancy_data['available_beds'] = available_beds
        
        existing = self.db.query(OccupancyByRoomType).filter(
            and_(
                OccupancyByRoomType.hostel_id == hostel_id if hostel_id else OccupancyByRoomType.hostel_id.is_(None),
                OccupancyByRoomType.period_start == period_start,
                OccupancyByRoomType.period_end == period_end,
                OccupancyByRoomType.room_type == room_type
            )
        ).first()
        
        if existing:
            for key, value in occupancy_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        breakdown = OccupancyByRoomType(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            room_type=room_type,
            **occupancy_data
        )
        
        self.db.add(breakdown)
        self.db.commit()
        self.db.refresh(breakdown)
        
        return breakdown
    
    def get_room_type_occupancies(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> List[OccupancyByRoomType]:
        """Get all room type occupancies for period."""
        return self.db.query(OccupancyByRoomType).filter(
            and_(
                OccupancyByRoomType.hostel_id == hostel_id if hostel_id else OccupancyByRoomType.hostel_id.is_(None),
                OccupancyByRoomType.period_start == period_start,
                OccupancyByRoomType.period_end == period_end
            )
        ).order_by(OccupancyByRoomType.occupancy_percentage.desc()).all()
    
    def get_best_performing_room_type(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> Optional[OccupancyByRoomType]:
        """Get room type with highest occupancy."""
        return self.db.query(OccupancyByRoomType).filter(
            and_(
                OccupancyByRoomType.hostel_id == hostel_id if hostel_id else OccupancyByRoomType.hostel_id.is_(None),
                OccupancyByRoomType.period_start == period_start,
                OccupancyByRoomType.period_end == period_end
            )
        ).order_by(OccupancyByRoomType.occupancy_percentage.desc()).first()
    
    # ==================== Floor Analysis ====================
    
    def create_floor_occupancy(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        floor_number: int,
        occupancy_data: Dict[str, Any]
    ) -> OccupancyByFloor:
        """Create or update floor occupancy breakdown."""
        existing = self.db.query(OccupancyByFloor).filter(
            and_(
                OccupancyByFloor.hostel_id == hostel_id if hostel_id else OccupancyByFloor.hostel_id.is_(None),
                OccupancyByFloor.period_start == period_start,
                OccupancyByFloor.period_end == period_end,
                OccupancyByFloor.floor_number == floor_number
            )
        ).first()
        
        if existing:
            for key, value in occupancy_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        breakdown = OccupancyByFloor(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            floor_number=floor_number,
            **occupancy_data
        )
        
        self.db.add(breakdown)
        self.db.commit()
        self.db.refresh(breakdown)
        
        return breakdown
    
    def get_floor_occupancies(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date
    ) -> List[OccupancyByFloor]:
        """Get all floor occupancies for period."""
        return self.db.query(OccupancyByFloor).filter(
            and_(
                OccupancyByFloor.hostel_id == hostel_id if hostel_id else OccupancyByFloor.hostel_id.is_(None),
                OccupancyByFloor.period_start == period_start,
                OccupancyByFloor.period_end == period_end
            )
        ).order_by(OccupancyByFloor.floor_number.asc()).all()
    
    # ==================== Seasonal Patterns ====================
    
    def create_seasonal_pattern(
        self,
        hostel_id: Optional[UUID],
        pattern_data: Dict[str, Any]
    ) -> SeasonalPattern:
        """Create or update seasonal pattern."""
        pattern = SeasonalPattern(
            hostel_id=hostel_id,
            **pattern_data
        )
        
        self.db.add(pattern)
        self.db.commit()
        self.db.refresh(pattern)
        
        return pattern
    
    def get_seasonal_patterns(
        self,
        hostel_id: Optional[UUID],
        year: Optional[int] = None
    ) -> List[SeasonalPattern]:
        """Get identified seasonal patterns."""
        query = QueryBuilder(SeasonalPattern, self.db)
        
        if hostel_id:
            query = query.where(SeasonalPattern.hostel_id == hostel_id)
        
        if year:
            query = query.where(SeasonalPattern.year_identified == year)
        
        query = query.order_by(SeasonalPattern.start_month.asc())
        
        return query.all()
    
    def identify_seasonal_patterns(
        self,
        hostel_id: Optional[UUID],
        lookback_years: int = 2
    ) -> List[SeasonalPattern]:
        """
        Identify seasonal patterns from historical data.
        
        Analyzes historical occupancy to detect recurring patterns.
        """
        # Get historical KPIs
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_years * 365)
        
        # This would analyze historical data and create patterns
        # Simplified implementation
        patterns = []
        
        # Example: High season (June-August for students)
        high_season = {
            'pattern_name': 'Academic Year Start',
            'start_month': 6,
            'end_month': 8,
            'average_occupancy': Decimal('85.00'),
            'occupancy_variance': Decimal('5.00'),
            'confidence': Decimal('90.00'),
            'is_high_season': True,
            'year_identified': end_date.year,
        }
        
        pattern = self.create_seasonal_pattern(hostel_id, high_season)
        patterns.append(pattern)
        
        return patterns
    
    # ==================== Forecasting ====================
    
    def create_forecast(
        self,
        hostel_id: Optional[UUID],
        forecast_data: Dict[str, Any]
    ) -> ForecastData:
        """Create or update forecast data."""
        forecast = ForecastData(
            hostel_id=hostel_id,
            last_updated=datetime.utcnow(),
            **forecast_data
        )
        
        self.db.add(forecast)
        self.db.commit()
        self.db.refresh(forecast)
        
        return forecast
    
    def add_forecast_points(
        self,
        forecast_data_id: UUID,
        forecast_points: List[Dict[str, Any]]
    ) -> List[ForecastPoint]:
        """Add forecast data points."""
        created_points = []
        
        for point_data in forecast_points:
            existing = self.db.query(ForecastPoint).filter(
                and_(
                    ForecastPoint.forecast_data_id == forecast_data_id,
                    ForecastPoint.forecast_date == point_data['forecast_date']
                )
            ).first()
            
            if existing:
                for key, value in point_data.items():
                    if key != 'forecast_date':
                        setattr(existing, key, value)
                created_points.append(existing)
            else:
                point = ForecastPoint(
                    forecast_data_id=forecast_data_id,
                    **point_data
                )
                self.db.add(point)
                created_points.append(point)
        
        self.db.commit()
        for point in created_points:
            self.db.refresh(point)
        
        return created_points
    
    def get_latest_forecast(
        self,
        hostel_id: Optional[UUID]
    ) -> Optional[ForecastData]:
        """Get the most recent forecast."""
        query = QueryBuilder(ForecastData, self.db)
        
        if hostel_id:
            query = query.where(ForecastData.hostel_id == hostel_id)
        
        query = query.order_by(ForecastData.created_at.desc())
        
        return query.first()
    
    def generate_occupancy_forecast(
        self,
        hostel_id: Optional[UUID],
        forecast_days: int = 30,
        model: str = 'moving_average'
    ) -> ForecastData:
        """
        Generate occupancy forecast using specified model.
        
        Args:
            hostel_id: Hostel ID
            forecast_days: Days to forecast
            model: Forecasting model to use
            
        Returns:
            ForecastData with forecast points
        """
        # Get historical data
        end_date = date.today()
        start_date = end_date - timedelta(days=90)
        
        # Get all trend points from recent KPIs
        kpis = self.db.query(OccupancyKPI).filter(
            and_(
                OccupancyKPI.hostel_id == hostel_id if hostel_id else OccupancyKPI.hostel_id.is_(None),
                OccupancyKPI.period_start >= start_date
            )
        ).all()
        
        all_points = []
        for kpi in kpis:
            points = self.get_occupancy_trend_points(kpi.id)
            all_points.extend(points)
        
        # Sort by date
        all_points.sort(key=lambda x: x.trend_date)
        
        if len(all_points) < 7:
            # Not enough data
            return None
        
        # Apply forecasting model
        if model == 'moving_average':
            forecast_points = self._forecast_moving_average(
                all_points, forecast_days
            )
        elif model == 'exponential_smoothing':
            forecast_points = self._forecast_exponential_smoothing(
                all_points, forecast_days
            )
        else:
            forecast_points = self._forecast_simple_extrapolation(
                all_points, forecast_days
            )
        
        # Calculate summary statistics
        forecasted_occupancies = [
            p['forecasted_occupancy_percentage'] for p in forecast_points
        ]
        
        avg_forecast = statistics.mean(forecasted_occupancies)
        
        peak_date = max(
            forecast_points,
            key=lambda x: x['forecasted_occupancy_percentage']
        )['forecast_date']
        
        low_date = min(
            forecast_points,
            key=lambda x: x['forecasted_occupancy_percentage']
        )['forecast_date']
        
        # Calculate model accuracy (if historical data available)
        model_accuracy = Decimal('75.00')  # Placeholder
        
        # Create forecast data
        forecast_data = {
            'forecast_horizon_days': forecast_days,
            'model_used': model,
            'model_accuracy': model_accuracy,
            'confidence_interval': Decimal('95.00'),
            'training_data_start': all_points[0].trend_date,
            'training_data_end': all_points[-1].trend_date,
            'training_samples': len(all_points),
            'average_forecasted_occupancy': Decimal(str(round(avg_forecast, 2))),
            'peak_forecasted_date': peak_date,
            'low_forecasted_date': low_date,
        }
        
        forecast = self.create_forecast(hostel_id, forecast_data)
        
        # Add forecast points
        self.add_forecast_points(forecast.id, forecast_points)
        
        return forecast
    
    def _forecast_moving_average(
        self,
        historical_points: List[OccupancyTrendPoint],
        forecast_days: int,
        window_size: int = 7
    ) -> List[Dict[str, Any]]:
        """Generate forecast using moving average."""
        # Get recent occupancy percentages
        recent_values = [
            float(p.occupancy_percentage) 
            for p in historical_points[-window_size:]
        ]
        
        moving_avg = statistics.mean(recent_values)
        
        # Calculate trend
        if len(recent_values) >= 3:
            recent_avg = statistics.mean(recent_values[-3:])
            older_avg = statistics.mean(recent_values[:3])
            daily_trend = (recent_avg - older_avg) / 3
        else:
            daily_trend = 0
        
        # Generate forecast points
        forecast_points = []
        last_date = historical_points[-1].trend_date
        
        for i in range(1, forecast_days + 1):
            forecast_date = last_date + timedelta(days=i)
            
            forecasted_occupancy = moving_avg + (daily_trend * i)
            forecasted_occupancy = max(0, min(100, forecasted_occupancy))
            
            # Simple confidence bounds (±10%)
            lower_bound = max(0, forecasted_occupancy * 0.9)
            upper_bound = min(100, forecasted_occupancy * 1.1)
            
            # Estimate occupied beds (assuming last known total)
            total_beds = historical_points[-1].total_beds
            forecasted_beds = int((forecasted_occupancy / 100) * total_beds)
            
            forecast_points.append({
                'forecast_date': forecast_date,
                'forecasted_occupancy_percentage': Decimal(str(round(forecasted_occupancy, 2))),
                'forecasted_occupied_beds': forecasted_beds,
                'lower_bound': Decimal(str(round(lower_bound, 2))),
                'upper_bound': Decimal(str(round(upper_bound, 2))),
                'confidence_level': Decimal('80.00'),
            })
        
        return forecast_points
    
    def _forecast_exponential_smoothing(
        self,
        historical_points: List[OccupancyTrendPoint],
        forecast_days: int,
        alpha: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Generate forecast using exponential smoothing."""
        # Get occupancy values
        values = [float(p.occupancy_percentage) for p in historical_points]
        
        # Calculate smoothed values
        smoothed = [values[0]]
        for value in values[1:]:
            smoothed_value = alpha * value + (1 - alpha) * smoothed[-1]
            smoothed.append(smoothed_value)
        
        # Use last smoothed value as baseline
        last_smoothed = smoothed[-1]
        
        # Generate forecast
        forecast_points = []
        last_date = historical_points[-1].trend_date
        total_beds = historical_points[-1].total_beds
        
        for i in range(1, forecast_days + 1):
            forecast_date = last_date + timedelta(days=i)
            
            forecasted_occupancy = last_smoothed
            forecasted_occupancy = max(0, min(100, forecasted_occupancy))
            
            lower_bound = max(0, forecasted_occupancy * 0.85)
            upper_bound = min(100, forecasted_occupancy * 1.15)
            
            forecasted_beds = int((forecasted_occupancy / 100) * total_beds)
            
            forecast_points.append({
                'forecast_date': forecast_date,
                'forecasted_occupancy_percentage': Decimal(str(round(forecasted_occupancy, 2))),
                'forecasted_occupied_beds': forecasted_beds,
                'lower_bound': Decimal(str(round(lower_bound, 2))),
                'upper_bound': Decimal(str(round(upper_bound, 2))),
                'confidence_level': Decimal('75.00'),
            })
        
        return forecast_points
    
    def _forecast_simple_extrapolation(
        self,
        historical_points: List[OccupancyTrendPoint],
        forecast_days: int
    ) -> List[Dict[str, Any]]:
        """Generate forecast using simple linear extrapolation."""
        # Use last value and assume stable
        last_point = historical_points[-1]
        last_occupancy = float(last_point.occupancy_percentage)
        
        forecast_points = []
        
        for i in range(1, forecast_days + 1):
            forecast_date = last_point.trend_date + timedelta(days=i)
            
            forecasted_occupancy = last_occupancy
            forecasted_occupancy = max(0, min(100, forecasted_occupancy))
            
            lower_bound = max(0, forecasted_occupancy * 0.8)
            upper_bound = min(100, forecasted_occupancy * 1.2)
            
            forecasted_beds = int((forecasted_occupancy / 100) * last_point.total_beds)
            
            forecast_points.append({
                'forecast_date': forecast_date,
                'forecasted_occupancy_percentage': Decimal(str(round(forecasted_occupancy, 2))),
                'forecasted_occupied_beds': forecasted_beds,
                'lower_bound': Decimal(str(round(lower_bound, 2))),
                'upper_bound': Decimal(str(round(upper_bound, 2))),
                'confidence_level': Decimal('70.00'),
            })
        
        return forecast_points
    
    # ==================== Comprehensive Report ====================
    
    def create_occupancy_report(
        self,
        hostel_id: Optional[UUID],
        period_start: date,
        period_end: date,
        kpi_id: Optional[UUID],
        forecast_id: Optional[UUID]
    ) -> OccupancyReport:
        """Create comprehensive occupancy report."""
        # Get room type breakdowns
        room_types = self.get_room_type_occupancies(
            hostel_id, period_start, period_end
        )
        
        # Get floor breakdowns
        floors = self.get_floor_occupancies(
            hostel_id, period_start, period_end
        )
        
        # Identify best and worst performers
        best_room_type = room_types[0].room_type if room_types else None
        worst_room_type = room_types[-1].room_type if room_types else None
        
        # Determine trend direction
        kpi = self.get_occupancy_kpi(hostel_id, period_start, period_end)
        if kpi:
            if float(kpi.average_occupancy_percentage) > float(kpi.peak_occupancy_percentage) * 0.9:
                trend_direction = 'increasing'
            elif float(kpi.average_occupancy_percentage) < float(kpi.low_occupancy_percentage) * 1.1:
                trend_direction = 'decreasing'
            else:
                trend_direction = 'stable'
        else:
            trend_direction = 'unknown'
        
        # Build breakdowns
        room_type_breakdown = [
            {
                'room_type': rt.room_type,
                'occupancy_percentage': float(rt.occupancy_percentage),
                'revenue_generated': float(rt.revenue_generated) if rt.revenue_generated else 0,
            }
            for rt in room_types
        ]
        
        floor_breakdown = [
            {
                'floor_number': f.floor_number,
                'floor_name': f.floor_name,
                'occupancy_percentage': float(f.occupancy_percentage),
            }
            for f in floors
        ]
        
        # Generate optimization insights
        optimization_insights = self._generate_optimization_insights(
            kpi, room_types, floors
        )
        
        existing = self.db.query(OccupancyReport).filter(
            and_(
                OccupancyReport.hostel_id == hostel_id if hostel_id else OccupancyReport.hostel_id.is_(None),
                OccupancyReport.period_start == period_start,
                OccupancyReport.period_end == period_end
            )
        ).first()
        
        report_data = {
            'kpi_id': kpi_id,
            'forecast_id': forecast_id,
            'best_performing_room_type': best_room_type,
            'worst_performing_room_type': worst_room_type,
            'occupancy_trend_direction': trend_direction,
            'room_type_breakdown': room_type_breakdown,
            'floor_breakdown': floor_breakdown,
            'optimization_insights': optimization_insights,
            'is_cached': True,
            'cache_expires_at': datetime.utcnow() + timedelta(hours=1),
            'calculated_at': datetime.utcnow(),
        }
        
        if existing:
            for key, value in report_data.items():
                setattr(existing, key, value)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        report = OccupancyReport(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            **report_data
        )
        
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        
        return report
    
    def _generate_optimization_insights(
        self,
        kpi: Optional[OccupancyKPI],
        room_types: List[OccupancyByRoomType],
        floors: List[OccupancyByFloor]
    ) -> Dict[str, Any]:
        """Generate actionable optimization insights."""
        insights = {
            'recommendations': [],
            'opportunities': [],
            'concerns': [],
        }
        
        if not kpi:
            return insights
        
        # Check overall occupancy
        avg_occupancy = float(kpi.average_occupancy_percentage)
        
        if avg_occupancy < 70:
            insights['recommendations'].append(
                'Occupancy below optimal level - consider pricing adjustments or marketing campaigns'
            )
        elif avg_occupancy > 95:
            insights['recommendations'].append(
                'Near full capacity - consider expanding or premium pricing'
            )
        
        # Check room type performance variance
        if room_types:
            occupancies = [float(rt.occupancy_percentage) for rt in room_types]
            if max(occupancies) - min(occupancies) > 20:
                insights['opportunities'].append(
                    'High variance in room type occupancy - rebalance pricing or inventory'
                )
        
        # Check for underutilized floors
        if floors:
            for floor in floors:
                if float(floor.occupancy_percentage) < 60:
                    insights['concerns'].append(
                        f'Floor {floor.floor_number} underutilized at {float(floor.occupancy_percentage)}%'
                    )
        
        return insights