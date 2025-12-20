# app/services/room/room_pricing_service.py
"""
Room pricing service with dynamic pricing and history.
"""

from typing import Dict, Any, List, Optional
from datetime import date
from decimal import Decimal

from app.services.room.base_service import BaseService
from app.repositories.room import (
    RoomRepository,
    RoomTypeRepository,
    RoomAvailabilityRepository
)


class RoomPricingService(BaseService):
    """
    Room pricing service handling pricing operations.
    
    Features:
    - Price updates with history
    - Dynamic pricing
    - Seasonal pricing
    - Discount calculations
    """
    
    def __init__(self, session):
        super().__init__(session)
        self.room_repo = RoomRepository(session)
        self.type_repo = RoomTypeRepository(session)
        self.availability_repo = RoomAvailabilityRepository(session)
    
    def update_room_pricing(
        self,
        room_id: str,
        new_pricing: Dict[str, Any],
        effective_from: date,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update room pricing with history tracking.
        
        Args:
            room_id: Room ID
            new_pricing: New pricing data
            effective_from: Effective date
            reason: Reason for price change
            
        Returns:
            Response with pricing history
        """
        try:
            pricing_history = self.room_repo.update_room_pricing(
                room_id,
                new_pricing,
                effective_from,
                reason,
                commit=True
            )
            
            return self.success_response(
                {
                    'pricing_history': pricing_history,
                    'new_monthly_price': float(pricing_history.price_monthly),
                    'price_change_percentage': float(
                        pricing_history.price_change_percentage or 0
                    )
                },
                "Pricing updated successfully"
            )
            
        except Exception as e:
            return self.handle_exception(e, "update room pricing")
    
    def calculate_dynamic_price(
        self,
        room_id: str,
        check_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Calculate dynamic price based on demand and availability.
        
        Business Rules:
        1. Get base price
        2. Apply occupancy multiplier
        3. Apply demand multiplier
        4. Apply seasonal adjustments
        5. Apply availability windows
        
        Args:
            room_id: Room ID
            check_date: Date for price calculation
            
        Returns:
            Response with calculated price
        """
        try:
            check_date = check_date or date.today()
            
            room = self.room_repo.find_by_id(room_id)
            if not room:
                return self.error_response("Room not found")
            
            base_price = room.price_monthly
            
            # Get availability
            availability = self.availability_repo.get_room_availability(room_id)
            
            multiplier = Decimal('1.00')
            adjustments = []
            
            if availability:
                # Occupancy-based adjustment
                occupancy_rate = availability.occupancy_rate
                if occupancy_rate >= Decimal('90.00'):
                    multiplier += Decimal('0.15')
                    adjustments.append("High occupancy (+15%)")
                elif occupancy_rate >= Decimal('75.00'):
                    multiplier += Decimal('0.10')
                    adjustments.append("Good occupancy (+10%)")
                elif occupancy_rate <= Decimal('40.00'):
                    multiplier -= Decimal('0.10')
                    adjustments.append("Low occupancy (-10%)")
                
                # Demand-based adjustment
                if availability.current_demand_level == 'VERY_HIGH':
                    multiplier += Decimal('0.20')
                    adjustments.append("Very high demand (+20%)")
                elif availability.current_demand_level == 'HIGH':
                    multiplier += Decimal('0.10')
                    adjustments.append("High demand (+10%)")
                elif availability.current_demand_level == 'LOW':
                    multiplier -= Decimal('0.05')
                    adjustments.append("Low demand (-5%)")
                
                # Check for applicable window
                window = self.availability_repo.get_applicable_window(
                    availability.id,
                    check_date
                )
                
                if window and window.has_price_adjustment:
                    multiplier = window.price_multiplier
                    adjustments.append(f"Window: {window.window_name}")
            
            # Calculate final price
            final_price = (base_price * multiplier).quantize(Decimal('0.01'))
            
            return self.success_response(
                {
                    'base_price': float(base_price),
                    'final_price': float(final_price),
                    'multiplier': float(multiplier),
                    'price_difference': float(final_price - base_price),
                    'adjustments': adjustments,
                    'calculation_date': check_date
                },
                "Dynamic price calculated"
            )
            
        except Exception as e:
            return self.handle_exception(e, "calculate dynamic price")
    
    def bulk_update_pricing(
        self,
        hostel_id: str,
        price_adjustment: Decimal,
        adjustment_type: str = 'PERCENTAGE',  # or 'FIXED'
        filters: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Bulk update pricing for multiple rooms.
        
        Args:
            hostel_id: Hostel ID
            price_adjustment: Adjustment amount
            adjustment_type: Type of adjustment
            filters: Room filters
            reason: Reason for adjustment
            
        Returns:
            Response with updated rooms
        """
        try:
            filters = filters or {}
            filters['hostel_id'] = hostel_id
            
            # Get matching rooms
            rooms = self.room_repo.find_by_criteria(filters)
            
            updated_count = 0
            effective_from = date.today()
            
            for room in rooms:
                if adjustment_type == 'PERCENTAGE':
                    new_price = room.price_monthly * (
                        Decimal('1.00') + (price_adjustment / Decimal('100.00'))
                    )
                else:  # FIXED
                    new_price = room.price_monthly + price_adjustment
                
                new_price = new_price.quantize(Decimal('0.01'))
                
                self.room_repo.update_room_pricing(
                    room.id,
                    {'price_monthly': new_price},
                    effective_from,
                    reason,
                    commit=False
                )
                updated_count += 1
            
            if not self.commit_or_rollback():
                return self.error_response("Failed to update pricing")
            
            return self.success_response(
                {
                    'rooms_updated': updated_count,
                    'adjustment': float(price_adjustment),
                    'adjustment_type': adjustment_type
                },
                f"Updated pricing for {updated_count} rooms"
            )
            
        except Exception as e:
            return self.handle_exception(e, "bulk update pricing")
    
    def get_pricing_comparison(
        self,
        hostel_id: str
    ) -> Dict[str, Any]:
        """
        Get pricing comparison across rooms.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Response with pricing analysis
        """
        try:
            comparison = self.type_repo.get_pricing_comparison(hostel_id)
            
            stats = self.room_repo.get_hostel_room_statistics(hostel_id)
            
            return self.success_response(
                {
                    'pricing_by_type': comparison,
                    'overall_stats': {
                        'avg_price': stats['avg_price'],
                        'min_price': stats['min_price'],
                        'max_price': stats['max_price']
                    }
                },
                "Pricing comparison generated"
            )
            
        except Exception as e:
            return self.handle_exception(e, "get pricing comparison")
    
    def calculate_discounted_price(
        self,
        room_id: str,
        duration_months: int
    ) -> Dict[str, Any]:
        """
        Calculate discounted price for long-term stay.
        
        Args:
            room_id: Room ID
            duration_months: Duration in months
            
        Returns:
            Response with discounted price
        """
        try:
            room = self.room_repo.find_by_id(room_id)
            if not room:
                return self.error_response("Room not found")
            
            monthly_price = room.price_monthly
            discount_percentage = Decimal('0.00')
            
            # Standard discount tiers
            if duration_months >= 12:
                discount_percentage = Decimal('15.00')
                if room.price_yearly:
                    total_price = room.price_yearly
                else:
                    total_price = monthly_price * 12 * (
                        Decimal('1.00') - discount_percentage / Decimal('100.00')
                    )
            elif duration_months >= 6:
                discount_percentage = Decimal('10.00')
                if room.price_half_yearly:
                    total_price = room.price_half_yearly
                else:
                    total_price = monthly_price * 6 * (
                        Decimal('1.00') - discount_percentage / Decimal('100.00')
                    )
            elif duration_months >= 3:
                discount_percentage = Decimal('5.00')
                if room.price_quarterly:
                    total_price = room.price_quarterly
                else:
                    total_price = monthly_price * 3 * (
                        Decimal('1.00') - discount_percentage / Decimal('100.00')
                    )
            else:
                total_price = monthly_price * duration_months
            
            total_price = total_price.quantize(Decimal('0.01'))
            monthly_effective = (total_price / duration_months).quantize(Decimal('0.01'))
            
            return self.success_response(
                {
                    'duration_months': duration_months,
                    'base_monthly_price': float(monthly_price),
                    'discount_percentage': float(discount_percentage),
                    'total_price': float(total_price),
                    'effective_monthly_price': float(monthly_effective),
                    'total_savings': float(
                        (monthly_price * duration_months) - total_price
                    )
                },
                "Discounted price calculated"
            )
            
        except Exception as e:
            return self.handle_exception(e, "calculate discounted price")