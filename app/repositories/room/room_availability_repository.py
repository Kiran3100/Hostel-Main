# app/repositories/room/room_availability_repository.py
"""
Room availability repository with real-time tracking and forecasting.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, case, desc
from sqlalchemy.orm import Session, joinedload

from app.models.room import (
    RoomAvailability,
    AvailabilityWindow,
    AvailabilityRule,
    AvailabilityForecast,
    AvailabilityAlert,
    AvailabilityOptimization,
    Room,
)
from .base_repository import BaseRepository


class RoomAvailabilityRepository(BaseRepository[RoomAvailability]):
    """
    Repository for RoomAvailability entity and related models.
    
    Handles:
    - Real-time availability tracking
    - Availability windows and rules
    - Demand forecasting
    - Alert management
    - Optimization strategies
    """

    def __init__(self, session: Session):
        super().__init__(RoomAvailability, session)

    # ============================================================================
    # AVAILABILITY BASIC OPERATIONS
    # ============================================================================

    def create_or_update_availability(
        self,
        room_id: str,
        availability_data: Dict[str, Any],
        commit: bool = True
    ) -> RoomAvailability:
        """
        Create or update room availability.
        
        Args:
            room_id: Room ID
            availability_data: Availability data
            commit: Whether to commit transaction
            
        Returns:
            Room availability record
        """
        try:
            availability = self.session.execute(
                select(RoomAvailability).where(
                    RoomAvailability.room_id == room_id
                )
            ).scalar_one_or_none()
            
            if not availability:
                availability = RoomAvailability(
                    room_id=room_id,
                    last_checked=datetime.utcnow(),
                    **availability_data
                )
                self.session.add(availability)
            else:
                for key, value in availability_data.items():
                    if hasattr(availability, key):
                        setattr(availability, key, value)
                availability.last_checked = datetime.utcnow()
            
            # Update availability status
            availability.update_availability()
            
            if commit:
                self.session.commit()
                self.session.refresh(availability)
            
            return availability
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to update availability: {str(e)}")

    def get_room_availability(
        self,
        room_id: str,
        create_if_missing: bool = True
    ) -> Optional[RoomAvailability]:
        """
        Get room availability.
        
        Args:
            room_id: Room ID
            create_if_missing: Create if doesn't exist
            
        Returns:
            Room availability or None
        """
        availability = self.session.execute(
            select(RoomAvailability).where(
                RoomAvailability.room_id == room_id
            )
        ).scalar_one_or_none()
        
        if not availability and create_if_missing:
            # Create default availability record
            room = self.session.execute(
                select(Room).where(Room.id == room_id)
            ).scalar_one_or_none()
            
            if room:
                availability = self.create_or_update_availability(
                    room_id,
                    {
                        'total_beds': room.total_beds,
                        'available_beds': room.available_beds,
                        'occupied_beds': room.occupied_beds,
                        'is_available': room.is_available_for_booking
                    }
                )
        
        return availability

    def sync_availability_with_room(
        self,
        room_id: str,
        commit: bool = True
    ) -> Optional[RoomAvailability]:
        """
        Synchronize availability with room data.
        
        Args:
            room_id: Room ID
            commit: Whether to commit transaction
            
        Returns:
            Updated availability
        """
        room = self.session.execute(
            select(Room).where(Room.id == room_id)
        ).scalar_one_or_none()
        
        if not room:
            return None
        
        return self.create_or_update_availability(
            room_id,
            {
                'total_beds': room.total_beds,
                'available_beds': room.available_beds,
                'occupied_beds': room.occupied_beds,
                'is_available': room.is_available_for_booking and not room.is_under_maintenance
            },
            commit=commit
        )

    def bulk_sync_availability(
        self,
        hostel_id: str,
        commit: bool = True
    ) -> int:
        """
        Bulk synchronize availability for all rooms in hostel.
        
        Args:
            hostel_id: Hostel ID
            commit: Whether to commit transaction
            
        Returns:
            Number of rooms updated
        """
        rooms = self.session.execute(
            select(Room).where(
                and_(
                    Room.hostel_id == hostel_id,
                    Room.is_deleted == False
                )
            )
        ).scalars().all()
        
        count = 0
        for room in rooms:
            self.sync_availability_with_room(room.id, commit=False)
            count += 1
        
        if commit:
            self.session.commit()
        
        return count

    # ============================================================================
    # AVAILABILITY SEARCH AND FILTERING
    # ============================================================================

    def find_available_rooms(
        self,
        hostel_id: str,
        min_beds: int = 1,
        check_date: Optional[date] = None
    ) -> List[RoomAvailability]:
        """
        Find available rooms.
        
        Args:
            hostel_id: Hostel ID
            min_beds: Minimum available beds
            check_date: Date to check availability
            
        Returns:
            List of available room availability records
        """
        query = select(RoomAvailability).join(Room).where(
            and_(
                Room.hostel_id == hostel_id,
                RoomAvailability.is_available == True,
                RoomAvailability.available_beds >= min_beds,
                Room.is_deleted == False
            )
        )
        
        # Check blackout dates if date provided
        if check_date:
            query = query.where(
                or_(
                    RoomAvailability.has_blackout_dates == False,
                    ~RoomAvailability.blackout_dates.contains([check_date.isoformat()])
                )
            )
        
        query = query.order_by(
            desc(RoomAvailability.available_beds)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_low_availability_rooms(
        self,
        hostel_id: str,
        threshold: Optional[int] = None
    ) -> List[RoomAvailability]:
        """
        Find rooms with low availability.
        
        Args:
            hostel_id: Hostel ID
            threshold: Availability threshold (uses room's own if not provided)
            
        Returns:
            List of low availability rooms
        """
        if threshold is not None:
            condition = RoomAvailability.available_beds <= threshold
        else:
            condition = RoomAvailability.available_beds <= RoomAvailability.low_availability_threshold
        
        query = select(RoomAvailability).join(Room).where(
            and_(
                Room.hostel_id == hostel_id,
                condition,
                RoomAvailability.is_available == True,
                Room.is_deleted == False
            )
        ).order_by(RoomAvailability.available_beds)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_full_rooms(self, hostel_id: str) -> List[RoomAvailability]:
        """
        Find fully occupied rooms.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            List of full rooms
        """
        query = select(RoomAvailability).join(Room).where(
            and_(
                Room.hostel_id == hostel_id,
                RoomAvailability.available_beds == 0,
                Room.is_deleted == False
            )
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_availability_summary(
        self,
        hostel_id: str
    ) -> Dict[str, Any]:
        """
        Get availability summary for hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Dictionary with availability statistics
        """
        query = select(
            func.count(RoomAvailability.id).label('total_rooms'),
            func.sum(RoomAvailability.total_beds).label('total_beds'),
            func.sum(RoomAvailability.available_beds).label('available_beds'),
            func.sum(RoomAvailability.occupied_beds).label('occupied_beds'),
            func.sum(RoomAvailability.reserved_beds).label('reserved_beds'),
            func.sum(RoomAvailability.blocked_beds).label('blocked_beds'),
            func.sum(
                case((RoomAvailability.is_available == True, 1), else_=0)
            ).label('available_rooms'),
            func.sum(
                case((RoomAvailability.availability_status == 'FULL', 1), else_=0)
            ).label('full_rooms'),
            func.avg(RoomAvailability.occupancy_rate).label('avg_occupancy')
        ).join(Room).where(
            and_(
                Room.hostel_id == hostel_id,
                Room.is_deleted == False
            )
        )
        
        result = self.session.execute(query).one()
        
        total_beds = result.total_beds or 0
        available_beds = result.available_beds or 0
        availability_rate = (available_beds / total_beds * 100) if total_beds > 0 else 0
        
        return {
            'total_rooms': result.total_rooms or 0,
            'total_beds': total_beds,
            'available_beds': available_beds,
            'occupied_beds': result.occupied_beds or 0,
            'reserved_beds': result.reserved_beds or 0,
            'blocked_beds': result.blocked_beds or 0,
            'available_rooms': result.available_rooms or 0,
            'full_rooms': result.full_rooms or 0,
            'availability_rate': round(availability_rate, 2),
            'avg_occupancy': round(float(result.avg_occupancy or 0), 2)
        }

    # ============================================================================
    # AVAILABILITY WINDOWS
    # ============================================================================

    def create_availability_window(
        self,
        room_availability_id: str,
        window_data: Dict[str, Any],
        commit: bool = True
    ) -> AvailabilityWindow:
        """
        Create availability window.
        
        Args:
            room_availability_id: Room availability ID
            window_data: Window data
            commit: Whether to commit transaction
            
        Returns:
            Created availability window
        """
        try:
            window = AvailabilityWindow(
                room_availability_id=room_availability_id,
                **window_data
            )
            self.session.add(window)
            
            if commit:
                self.session.commit()
                self.session.refresh(window)
            
            return window
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create availability window: {str(e)}")

    def find_active_windows(
        self,
        room_availability_id: str,
        check_date: Optional[date] = None
    ) -> List[AvailabilityWindow]:
        """
        Find active availability windows.
        
        Args:
            room_availability_id: Room availability ID
            check_date: Date to check (defaults to today)
            
        Returns:
            List of active windows
        """
        check_date = check_date or date.today()
        
        query = select(AvailabilityWindow).where(
            and_(
                AvailabilityWindow.room_availability_id == room_availability_id,
                AvailabilityWindow.is_active == True,
                AvailabilityWindow.start_date <= check_date,
                AvailabilityWindow.end_date >= check_date
            )
        ).order_by(desc(AvailabilityWindow.priority))
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_applicable_window(
        self,
        room_availability_id: str,
        check_date: date
    ) -> Optional[AvailabilityWindow]:
        """
        Get highest priority applicable window for date.
        
        Args:
            room_availability_id: Room availability ID
            check_date: Date to check
            
        Returns:
            Applicable window or None
        """
        windows = self.find_active_windows(room_availability_id, check_date)
        return windows[0] if windows else None

    # ============================================================================
    # AVAILABILITY RULES
    # ============================================================================

    def create_availability_rule(
        self,
        room_availability_id: str,
        rule_data: Dict[str, Any],
        commit: bool = True
    ) -> AvailabilityRule:
        """
        Create availability rule.
        
        Args:
            room_availability_id: Room availability ID
            rule_data: Rule data
            commit: Whether to commit transaction
            
        Returns:
            Created rule
        """
        try:
            rule = AvailabilityRule(
                room_availability_id=room_availability_id,
                **rule_data
            )
            self.session.add(rule)
            
            if commit:
                self.session.commit()
                self.session.refresh(rule)
            
            return rule
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create availability rule: {str(e)}")

    def find_active_rules(
        self,
        room_availability_id: str,
        rule_type: Optional[str] = None
    ) -> List[AvailabilityRule]:
        """
        Find active availability rules.
        
        Args:
            room_availability_id: Room availability ID
            rule_type: Rule type filter
            
        Returns:
            List of active rules ordered by priority
        """
        query = select(AvailabilityRule).where(
            and_(
                AvailabilityRule.room_availability_id == room_availability_id,
                AvailabilityRule.is_active == True
            )
        )
        
        if rule_type:
            query = query.where(AvailabilityRule.rule_type == rule_type)
        
        query = query.order_by(
            AvailabilityRule.priority,
            AvailabilityRule.execution_order
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def execute_availability_rules(
        self,
        room_availability_id: str,
        check_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute availability rules.
        
        Args:
            room_availability_id: Room availability ID
            check_context: Context for rule execution
            
        Returns:
            Rule execution results
        """
        rules = self.find_active_rules(room_availability_id)
        
        results = {
            'is_available': True,
            'rules_applied': [],
            'restrictions': [],
            'modifications': {}
        }
        
        for rule in rules:
            # Execute rule logic
            if self._evaluate_availability_rule(rule, check_context):
                results['rules_applied'].append(rule.rule_name)
                
                # Update execution stats
                rule.execution_count += 1
                rule.success_count += 1
                rule.last_executed = datetime.utcnow()
                
                # Apply rule actions
                if rule.actions:
                    results['modifications'].update(rule.actions)
        
        return results

    def _evaluate_availability_rule(
        self,
        rule: AvailabilityRule,
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate if rule conditions are met."""
        if not rule.conditions:
            return True
        
        for key, value in rule.conditions.items():
            if key in context and context[key] != value:
                return False
        
        return True

    # ============================================================================
    # AVAILABILITY FORECASTING
    # ============================================================================

    def create_or_update_forecast(
        self,
        room_availability_id: str,
        forecast_data: Dict[str, Any],
        commit: bool = True
    ) -> AvailabilityForecast:
        """
        Create or update availability forecast.
        
        Args:
            room_availability_id: Room availability ID
            forecast_data: Forecast data
            commit: Whether to commit transaction
            
        Returns:
            Forecast record
        """
        try:
            forecast = self.session.execute(
                select(AvailabilityForecast).where(
                    AvailabilityForecast.room_availability_id == room_availability_id
                )
            ).scalar_one_or_none()
            
            if not forecast:
                forecast = AvailabilityForecast(
                    room_availability_id=room_availability_id,
                    forecast_generated_at=datetime.utcnow(),
                    forecast_valid_until=datetime.utcnow() + timedelta(days=90),
                    **forecast_data
                )
                self.session.add(forecast)
            else:
                for key, value in forecast_data.items():
                    if hasattr(forecast, key):
                        setattr(forecast, key, value)
                forecast.forecast_generated_at = datetime.utcnow()
            
            if commit:
                self.session.commit()
                self.session.refresh(forecast)
            
            return forecast
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create forecast: {str(e)}")

    def get_forecast(
        self,
        room_availability_id: str
    ) -> Optional[AvailabilityForecast]:
        """
        Get current forecast.
        
        Args:
            room_availability_id: Room availability ID
            
        Returns:
            Forecast or None
        """
        return self.session.execute(
            select(AvailabilityForecast).where(
                and_(
                    AvailabilityForecast.room_availability_id == room_availability_id,
                    AvailabilityForecast.forecast_valid_until >= datetime.utcnow()
                )
            )
        ).scalar_one_or_none()

    def generate_simple_forecast(
        self,
        room_availability_id: str,
        days_ahead: int = 90,
        commit: bool = True
    ) -> AvailabilityForecast:
        """
        Generate simple forecast based on current trends.
        
        Args:
            room_availability_id: Room availability ID
            days_ahead: Number of days to forecast
            commit: Whether to commit transaction
            
        Returns:
            Generated forecast
        """
        availability = self.session.execute(
            select(RoomAvailability).where(
                RoomAvailability.id == room_availability_id
            )
        ).scalar_one_or_none()
        
        if not availability:
            raise ValueError("Room availability not found")
        
        # Simple forecast based on current occupancy
        daily_forecasts = {}
        current_occupancy = availability.occupancy_rate
        
        for i in range(days_ahead):
            forecast_date = date.today() + timedelta(days=i)
            # Simple linear projection (would be more sophisticated in production)
            forecasted_occupancy = min(Decimal('100.00'), current_occupancy + Decimal(str(i * 0.1)))
            
            daily_forecasts[forecast_date.isoformat()] = {
                'available_beds': int(availability.total_beds * (100 - forecasted_occupancy) / 100),
                'occupancy_rate': float(forecasted_occupancy),
                'confidence': 0.7  # Confidence level
            }
        
        forecast_data = {
            'model_version': '1.0',
            'model_type': 'LINEAR',
            'algorithm_used': 'SIMPLE_PROJECTION',
            'training_data_start_date': date.today() - timedelta(days=30),
            'training_data_end_date': date.today(),
            'data_points_used': 30,
            'forecast_horizon_days': days_ahead,
            'daily_forecasts': daily_forecasts,
            'avg_availability_next_30d': float(current_occupancy)
        }
        
        return self.create_or_update_forecast(
            room_availability_id,
            forecast_data,
            commit=commit
        )

    # ============================================================================
    # AVAILABILITY ALERTS
    # ============================================================================

    def create_availability_alert(
        self,
        room_availability_id: str,
        alert_data: Dict[str, Any],
        commit: bool = True
    ) -> AvailabilityAlert:
        """
        Create availability alert.
        
        Args:
            room_availability_id: Room availability ID
            alert_data: Alert data
            commit: Whether to commit transaction
            
        Returns:
            Created alert
        """
        try:
            alert = AvailabilityAlert(
                room_availability_id=room_availability_id,
                triggered_at=datetime.utcnow(),
                **alert_data
            )
            self.session.add(alert)
            
            if commit:
                self.session.commit()
                self.session.refresh(alert)
            
            return alert
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create alert: {str(e)}")

    def check_and_create_alerts(
        self,
        room_availability_id: str,
        commit: bool = True
    ) -> List[AvailabilityAlert]:
        """
        Check conditions and create alerts if needed.
        
        Args:
            room_availability_id: Room availability ID
            commit: Whether to commit transaction
            
        Returns:
            List of created alerts
        """
        availability = self.session.execute(
            select(RoomAvailability).where(
                RoomAvailability.id == room_availability_id
            )
        ).scalar_one_or_none()
        
        if not availability:
            return []
        
        alerts = []
        
        # Check low availability
        if availability.available_beds <= availability.low_availability_threshold:
            alert = self.create_availability_alert(
                room_availability_id,
                {
                    'alert_type': 'LOW_AVAILABILITY',
                    'alert_severity': 'HIGH' if availability.available_beds == 0 else 'MEDIUM',
                    'alert_title': 'Low Availability Alert',
                    'alert_message': f'Only {availability.available_beds} beds available',
                    'trigger_condition': f'available_beds <= {availability.low_availability_threshold}',
                    'trigger_threshold': Decimal(str(availability.low_availability_threshold)),
                    'trigger_value': Decimal(str(availability.available_beds)),
                    'available_beds_at_trigger': availability.available_beds,
                    'total_beds_at_trigger': availability.total_beds,
                    'occupancy_rate_at_trigger': availability.occupancy_rate
                },
                commit=False
            )
            alerts.append(alert)
        
        # Check full capacity
        if availability.available_beds == 0:
            alert = self.create_availability_alert(
                room_availability_id,
                {
                    'alert_type': 'FULL',
                    'alert_severity': 'CRITICAL',
                    'alert_title': 'Room Full',
                    'alert_message': 'Room has reached full capacity',
                    'trigger_condition': 'available_beds == 0',
                    'trigger_threshold': Decimal('0'),
                    'trigger_value': Decimal('0'),
                    'available_beds_at_trigger': 0,
                    'total_beds_at_trigger': availability.total_beds,
                    'occupancy_rate_at_trigger': Decimal('100.00')
                },
                commit=False
            )
            alerts.append(alert)
        
        # Check high demand
        if availability.demand_score and availability.demand_score >= Decimal('80.00'):
            alert = self.create_availability_alert(
                room_availability_id,
                {
                    'alert_type': 'HIGH_DEMAND',
                    'alert_severity': 'MEDIUM',
                    'alert_title': 'High Demand Detected',
                    'alert_message': f'Demand score: {availability.demand_score}',
                    'trigger_condition': 'demand_score >= 80',
                    'trigger_threshold': Decimal('80.00'),
                    'trigger_value': availability.demand_score,
                    'available_beds_at_trigger': availability.available_beds,
                    'total_beds_at_trigger': availability.total_beds,
                    'occupancy_rate_at_trigger': availability.occupancy_rate
                },
                commit=False
            )
            alerts.append(alert)
        
        if commit and alerts:
            self.session.commit()
            for alert in alerts:
                self.session.refresh(alert)
        
        return alerts

    def find_active_alerts(
        self,
        hostel_id: Optional[str] = None,
        alert_type: Optional[str] = None,
        min_severity: str = 'LOW'
    ) -> List[AvailabilityAlert]:
        """
        Find active availability alerts.
        
        Args:
            hostel_id: Hostel ID filter
            alert_type: Alert type filter
            min_severity: Minimum severity
            
        Returns:
            List of active alerts
        """
        severity_levels = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}
        min_level = severity_levels.get(min_severity, 1)
        
        query = select(AvailabilityAlert).join(
            RoomAvailability,
            AvailabilityAlert.room_availability_id == RoomAvailability.id
        ).where(
            AvailabilityAlert.is_active == True
        )
        
        if alert_type:
            query = query.where(AvailabilityAlert.alert_type == alert_type)
        
        if hostel_id:
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        
        # Filter by severity
        alerts = []
        for alert in result.scalars():
            alert_level = severity_levels.get(alert.alert_severity, 0)
            if alert_level >= min_level:
                alerts.append(alert)
        
        return alerts

    def acknowledge_alert(
        self,
        alert_id: str,
        user_id: str,
        notes: Optional[str] = None,
        commit: bool = True
    ) -> Optional[AvailabilityAlert]:
        """
        Acknowledge alert.
        
        Args:
            alert_id: Alert ID
            user_id: User ID acknowledging
            notes: Acknowledgment notes
            commit: Whether to commit transaction
            
        Returns:
            Acknowledged alert
        """
        alert = self.session.execute(
            select(AvailabilityAlert).where(AvailabilityAlert.id == alert_id)
        ).scalar_one_or_none()
        
        if not alert:
            return None
        
        alert.acknowledge(user_id, notes)
        
        if commit:
            self.session.commit()
            self.session.refresh(alert)
        
        return alert

    def resolve_alert(
        self,
        alert_id: str,
        user_id: str,
        resolution_method: str,
        notes: Optional[str] = None,
        commit: bool = True
    ) -> Optional[AvailabilityAlert]:
        """
        Resolve alert.
        
        Args:
            alert_id: Alert ID
            user_id: User ID resolving
            resolution_method: Resolution method
            notes: Resolution notes
            commit: Whether to commit transaction
            
        Returns:
            Resolved alert
        """
        alert = self.session.execute(
            select(AvailabilityAlert).where(AvailabilityAlert.id == alert_id)
        ).scalar_one_or_none()
        
        if not alert:
            return None
        
        alert.resolve(user_id, resolution_method, notes)
        
        if commit:
            self.session.commit()
            self.session.refresh(alert)
        
        return alert

    # ============================================================================
    # AVAILABILITY OPTIMIZATION
    # ============================================================================

    def create_optimization(
        self,
        room_availability_id: str,
        optimization_data: Dict[str, Any],
        commit: bool = True
    ) -> AvailabilityOptimization:
        """
        Create availability optimization.
        
        Args:
            room_availability_id: Room availability ID
            optimization_data: Optimization data
            commit: Whether to commit transaction
            
        Returns:
            Created optimization
        """
        try:
            optimization = AvailabilityOptimization(
                room_availability_id=room_availability_id,
                optimization_date=datetime.utcnow(),
                **optimization_data
            )
            self.session.add(optimization)
            
            if commit:
                self.session.commit()
                self.session.refresh(optimization)
            
            return optimization
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create optimization: {str(e)}")

    def run_optimization_analysis(
        self,
        room_availability_id: str,
        optimization_type: str = 'REVENUE',
        commit: bool = True
    ) -> AvailabilityOptimization:
        """
        Run optimization analysis.
        
        Args:
            room_availability_id: Room availability ID
            optimization_type: Type of optimization
            commit: Whether to commit transaction
            
        Returns:
            Optimization results
        """
        availability = self.session.execute(
            select(RoomAvailability).where(
                RoomAvailability.id == room_availability_id
            )
        ).scalar_one_or_none()
        
        if not availability:
            raise ValueError("Room availability not found")
        
        # Analyze current performance
        current_metrics = {
            'occupancy_rate': float(availability.occupancy_rate),
            'utilization_rate': float(availability.occupancy_rate),  # Simplified
            'revenue_per_day': 0.0,  # Would calculate from actual data
            'turnover_rate': 0.0
        }
        
        # Generate recommendations based on optimization type
        recommendations = {}
        priority_actions = []
        
        if optimization_type == 'OCCUPANCY':
            target_occupancy = Decimal('90.00')
            if availability.occupancy_rate < target_occupancy:
                recommendations['increase_marketing'] = True
                recommendations['adjust_pricing'] = 'DECREASE'
                priority_actions.append('Increase marketing efforts')
                priority_actions.append('Consider promotional pricing')
        
        elif optimization_type == 'REVENUE':
            if availability.occupancy_rate > Decimal('85.00'):
                recommendations['adjust_pricing'] = 'INCREASE'
                priority_actions.append('Increase pricing due to high demand')
            recommendations['dynamic_pricing'] = True
        
        optimization_data = {
            'optimization_type': optimization_type,
            'optimization_algorithm': 'RULE_BASED',
            'analysis_start_date': date.today() - timedelta(days=30),
            'analysis_end_date': date.today(),
            'data_points_analyzed': 30,
            'current_occupancy_rate': Decimal(str(current_metrics['occupancy_rate'])),
            'current_utilization_rate': Decimal(str(current_metrics['utilization_rate'])),
            'current_revenue_per_day': Decimal(str(current_metrics['revenue_per_day'])),
            'current_turnover_rate': Decimal(str(current_metrics['turnover_rate'])),
            'target_occupancy_rate': Decimal('90.00'),
            'target_revenue_increase': Decimal('10.00'),
            'recommendations': recommendations,
            'priority_actions': priority_actions,
            'risk_level': 'LOW'
        }
        
        return self.create_optimization(
            room_availability_id,
            optimization_data,
            commit=commit
        )

    def get_latest_optimization(
        self,
        room_availability_id: str
    ) -> Optional[AvailabilityOptimization]:
        """
        Get latest optimization.
        
        Args:
            room_availability_id: Room availability ID
            
        Returns:
            Latest optimization or None
        """
        return self.session.execute(
            select(AvailabilityOptimization).where(
                AvailabilityOptimization.room_availability_id == room_availability_id
            ).order_by(desc(AvailabilityOptimization.optimization_date)).limit(1)
        ).scalar_one_or_none()

    # ============================================================================
    # DEMAND TRACKING
    # ============================================================================

    def update_demand_metrics(
        self,
        room_availability_id: str,
        inquiry_count: int = 0,
        booking_count: int = 0,
        commit: bool = True
    ) -> Optional[RoomAvailability]:
        """
        Update demand tracking metrics.
        
        Args:
            room_availability_id: Room availability ID
            inquiry_count: Number of inquiries
            booking_count: Number of bookings
            commit: Whether to commit transaction
            
        Returns:
            Updated availability
        """
        availability = self.session.execute(
            select(RoomAvailability).where(
                RoomAvailability.id == room_availability_id
            )
        ).scalar_one_or_none()
        
        if not availability:
            return None
        
        availability.inquiry_count_24h += inquiry_count
        availability.booking_count_7d += booking_count
        
        # Update demand level based on metrics
        total_activity = availability.inquiry_count_24h + availability.booking_count_7d
        
        if total_activity >= 20:
            availability.current_demand_level = 'VERY_HIGH'
            availability.demand_score = Decimal('90.00')
        elif total_activity >= 10:
            availability.current_demand_level = 'HIGH'
            availability.demand_score = Decimal('70.00')
        elif total_activity >= 5:
            availability.current_demand_level = 'NORMAL'
            availability.demand_score = Decimal('50.00')
        else:
            availability.current_demand_level = 'LOW'
            availability.demand_score = Decimal('30.00')
        
        if commit:
            self.session.commit()
            self.session.refresh(availability)
        
        return availability

    def reset_daily_metrics(
        self,
        hostel_id: Optional[str] = None,
        commit: bool = True
    ) -> int:
        """
        Reset daily demand metrics (to be run daily).
        
        Args:
            hostel_id: Hostel ID filter
            commit: Whether to commit transaction
            
        Returns:
            Number of records updated
        """
        query = select(RoomAvailability).join(Room)
        
        if hostel_id:
            query = query.where(Room.hostel_id == hostel_id)
        
        availabilities = self.session.execute(query).scalars().all()
        
        count = 0
        for availability in availabilities:
            availability.inquiry_count_24h = 0
            count += 1
        
        if commit:
            self.session.commit()
        
        return count