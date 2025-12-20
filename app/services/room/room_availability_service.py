# app/services/room/room_availability_service.py
"""
Room availability service with real-time tracking and forecasting.
"""

from typing import Dict, Any, List, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.services.room.base_service import BaseService
from app.repositories.room import (
    RoomAvailabilityRepository,
    RoomRepository
)


class RoomAvailabilityService(BaseService):
    """
    Room availability service handling availability operations.
    
    Features:
    - Real-time availability tracking
    - Demand forecasting
    - Alert management
    - Availability optimization
    """
    
    def __init__(self, session):
        super().__init__(session)
        self.availability_repo = RoomAvailabilityRepository(session)
        self.room_repo = RoomRepository(session)
    
    def sync_availability(
        self,
        room_id: Optional[str] = None,
        hostel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synchronize availability with actual room data.
        
        Args:
            room_id: Specific room ID (optional)
            hostel_id: Hostel ID for bulk sync (optional)
            
        Returns:
            Response with sync results
        """
        try:
            if room_id:
                # Sync single room
                availability = self.availability_repo.sync_availability_with_room(
                    room_id,
                    commit=True
                )
                
                if not availability:
                    return self.error_response("Room not found")
                
                return self.success_response(
                    {'availability': availability},
                    "Availability synchronized"
                )
            
            elif hostel_id:
                # Bulk sync
                count = self.availability_repo.bulk_sync_availability(
                    hostel_id,
                    commit=True
                )
                
                return self.success_response(
                    {'rooms_synced': count},
                    f"Synchronized {count} rooms"
                )
            
            else:
                return self.error_response("Either room_id or hostel_id required")
                
        except Exception as e:
            return self.handle_exception(e, "sync availability")
    
    def check_availability(
        self,
        room_id: str,
        check_date: Optional[date] = None,
        required_beds: int = 1
    ) -> Dict[str, Any]:
        """
        Check room availability for specific date.
        
        Args:
            room_id: Room ID
            check_date: Date to check (defaults to today)
            required_beds: Number of beds required
            
        Returns:
            Response with availability status
        """
        try:
            check_date = check_date or date.today()
            
            availability = self.availability_repo.get_room_availability(room_id)
            if not availability:
                return self.error_response("Availability data not found")
            
            # Check if date is in blackout period
            is_blackout = False
            if availability.has_blackout_dates and availability.blackout_dates:
                is_blackout = check_date.isoformat() in availability.blackout_dates
            
            # Get applicable window
            window = self.availability_repo.get_applicable_window(
                availability.id,
                check_date
            )
            
            # Check rules
            rules_result = self.availability_repo.execute_availability_rules(
                availability.id,
                {'check_date': check_date, 'required_beds': required_beds}
            )
            
            is_available = (
                availability.is_available and
                availability.available_beds >= required_beds and
                not is_blackout and
                rules_result.get('is_available', True)
            )
            
            return self.success_response(
                {
                    'is_available': is_available,
                    'available_beds': availability.available_beds,
                    'total_beds': availability.total_beds,
                    'occupancy_rate': float(availability.occupancy_rate),
                    'is_blackout_date': is_blackout,
                    'applicable_window': window,
                    'rules_applied': rules_result.get('rules_applied', []),
                    'restrictions': rules_result.get('restrictions', [])
                },
                "Availability checked"
            )
            
        except Exception as e:
            return self.handle_exception(e, "check availability")
    
    def find_available_rooms(
        self,
        hostel_id: str,
        check_date: Optional[date] = None,
        min_beds: int = 1
    ) -> Dict[str, Any]:
        """
        Find all available rooms in hostel.
        
        Args:
            hostel_id: Hostel ID
            check_date: Date to check
            min_beds: Minimum available beds
            
        Returns:
            Response with available rooms
        """
        try:
            availabilities = self.availability_repo.find_available_rooms(
                hostel_id,
                min_beds,
                check_date
            )
            
            # Get detailed info for each
            available_rooms = []
            for avail in availabilities:
                room = self.room_repo.find_by_id(avail.room_id)
                if room:
                    available_rooms.append({
                        'room': room,
                        'availability': avail,
                        'available_beds': avail.available_beds,
                        'occupancy_rate': float(avail.occupancy_rate)
                    })
            
            return self.success_response(
                {
                    'rooms': available_rooms,
                    'count': len(available_rooms)
                },
                f"Found {len(available_rooms)} available rooms"
            )
            
        except Exception as e:
            return self.handle_exception(e, "find available rooms")
    
    def create_availability_window(
        self,
        room_id: str,
        window_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create availability window with custom rules.
        
        Args:
            room_id: Room ID
            window_data: Window configuration
            
        Returns:
            Response with created window
        """
        try:
            availability = self.availability_repo.get_room_availability(room_id)
            if not availability:
                return self.error_response("Room availability not found")
            
            # Validate dates
            start_date = window_data.get('start_date')
            end_date = window_data.get('end_date')
            
            if start_date >= end_date:
                return self.error_response("End date must be after start date")
            
            window = self.availability_repo.create_availability_window(
                availability.id,
                window_data,
                commit=True
            )
            
            return self.success_response(
                {'window': window},
                "Availability window created"
            )
            
        except Exception as e:
            return self.handle_exception(e, "create availability window")
    
    def generate_forecast(
        self,
        room_id: str,
        days_ahead: int = 90
    ) -> Dict[str, Any]:
        """
        Generate availability forecast.
        
        Args:
            room_id: Room ID
            days_ahead: Number of days to forecast
            
        Returns:
            Response with forecast
        """
        try:
            availability = self.availability_repo.get_room_availability(room_id)
            if not availability:
                return self.error_response("Room availability not found")
            
            forecast = self.availability_repo.generate_simple_forecast(
                availability.id,
                days_ahead,
                commit=True
            )
            
            return self.success_response(
                {
                    'forecast': forecast,
                    'forecast_horizon_days': days_ahead,
                    'confidence_level': 0.7
                },
                f"Forecast generated for next {days_ahead} days"
            )
            
        except Exception as e:
            return self.handle_exception(e, "generate forecast")
    
    def get_availability_alerts(
        self,
        hostel_id: str,
        alert_type: Optional[str] = None,
        min_severity: str = 'MEDIUM'
    ) -> Dict[str, Any]:
        """
        Get active availability alerts.
        
        Args:
            hostel_id: Hostel ID
            alert_type: Alert type filter
            min_severity: Minimum severity level
            
        Returns:
            Response with alerts
        """
        try:
            alerts = self.availability_repo.find_active_alerts(
                hostel_id,
                alert_type,
                min_severity
            )
            
            # Group by severity
            by_severity = {
                'CRITICAL': [],
                'HIGH': [],
                'MEDIUM': [],
                'LOW': []
            }
            
            for alert in alerts:
                by_severity[alert.alert_severity].append(alert)
            
            return self.success_response(
                {
                    'alerts': alerts,
                    'total_count': len(alerts),
                    'by_severity': {
                        k: len(v) for k, v in by_severity.items()
                    }
                },
                f"Found {len(alerts)} active alerts"
            )
            
        except Exception as e:
            return self.handle_exception(e, "get alerts")
    
    def update_demand_metrics(
        self,
        room_id: str,
        inquiries: int = 0,
        bookings: int = 0
    ) -> Dict[str, Any]:
        """
        Update demand tracking metrics.
        
        Args:
            room_id: Room ID
            inquiries: Number of inquiries
            bookings: Number of bookings
            
        Returns:
            Response with updated metrics
        """
        try:
            availability = self.availability_repo.get_room_availability(room_id)
            if not availability:
                return self.error_response("Room availability not found")
            
            updated = self.availability_repo.update_demand_metrics(
                availability.id,
                inquiries,
                bookings,
                commit=True
            )
            
            return self.success_response(
                {
                    'availability': updated,
                    'demand_level': updated.current_demand_level,
                    'demand_score': float(updated.demand_score or 0)
                },
                "Demand metrics updated"
            )
            
        except Exception as e:
            return self.handle_exception(e, "update demand metrics")
    
    def run_optimization(
        self,
        room_id: str,
        optimization_type: str = 'REVENUE'
    ) -> Dict[str, Any]:
        """
        Run availability optimization analysis.
        
        Args:
            room_id: Room ID
            optimization_type: Type of optimization
            
        Returns:
            Response with optimization results
        """
        try:
            availability = self.availability_repo.get_room_availability(room_id)
            if not availability:
                return self.error_response("Room availability not found")
            
            optimization = self.availability_repo.run_optimization_analysis(
                availability.id,
                optimization_type,
                commit=True
            )
            
            return self.success_response(
                {
                    'optimization': optimization,
                    'recommendations': optimization.recommendations,
                    'priority_actions': optimization.priority_actions
                },
                "Optimization analysis completed"
            )
            
        except Exception as e:
            return self.handle_exception(e, "run optimization")
    
    def get_availability_summary(
        self,
        hostel_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive availability summary for hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Response with summary data
        """
        try:
            summary = self.availability_repo.get_availability_summary(hostel_id)
            
            # Get low availability rooms
            low_availability = self.availability_repo.find_low_availability_rooms(
                hostel_id
            )
            
            # Get full rooms
            full_rooms = self.availability_repo.find_full_rooms(hostel_id)
            
            return self.success_response(
                {
                    'summary': summary,
                    'low_availability_count': len(low_availability),
                    'full_rooms_count': len(full_rooms),
                    'low_availability_rooms': low_availability,
                    'full_rooms': full_rooms
                },
                "Availability summary generated"
            )
            
        except Exception as e:
            return self.handle_exception(e, "get availability summary")