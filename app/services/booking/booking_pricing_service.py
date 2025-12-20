# app/services/booking/booking_pricing_service.py
"""
Booking pricing service for dynamic pricing calculations.

Handles rent calculation, discounts, seasonal pricing, promotional offers,
and pricing optimization.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError
from app.models.base.enums import RoomType


class BookingPricingService:
    """
    Service for booking pricing calculations.
    
    Responsibilities:
    - Calculate booking prices with all components
    - Apply discounts and promotions
    - Handle seasonal pricing
    - Calculate security deposits
    - Process referral discounts
    - Generate pricing breakdowns
    """
    
    def __init__(self, session: Session):
        """Initialize pricing service."""
        self.session = session
    
    # ==================== PRICE CALCULATION ====================
    
    def calculate_booking_price(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        duration_months: int,
        check_in_date: date,
        referral_code: Optional[str] = None,
        promotional_code: Optional[str] = None,
    ) -> Dict:
        """
        Calculate complete booking price with all components.
        
        Args:
            hostel_id: Hostel UUID
            room_type: Room type
            duration_months: Stay duration
            check_in_date: Check-in date
            referral_code: Referral code
            promotional_code: Promotional code
            
        Returns:
            Complete pricing breakdown dictionary
        """
        # Get base monthly rent (from hostel/room configuration)
        base_monthly_rent = self._get_base_monthly_rent(hostel_id, room_type)
        
        # Apply seasonal pricing adjustments
        adjusted_rent = self._apply_seasonal_pricing(
            base_monthly_rent, check_in_date
        )
        
        # Apply duration-based discounts
        rent_with_duration_discount = self._apply_duration_discount(
            adjusted_rent, duration_months
        )
        
        # Calculate total rent
        total_rent = rent_with_duration_discount * duration_months
        
        # Calculate security deposit
        security_deposit = self._calculate_security_deposit(
            rent_with_duration_discount
        )
        
        # Apply referral discount
        referral_discount = Decimal("0.00")
        if referral_code:
            referral_discount = self._apply_referral_discount(
                total_rent, referral_code
            )
        
        # Apply promotional discount
        promotional_discount = Decimal("0.00")
        if promotional_code:
            promotional_discount = self._apply_promotional_discount(
                total_rent, promotional_code
            )
        
        # Calculate final amounts
        total_discount = referral_discount + promotional_discount
        total_amount = total_rent - total_discount
        
        # Calculate advance payment (20% of total)
        advance_percentage = Decimal("20.00")
        advance_amount = (total_amount * advance_percentage / 100).quantize(
            Decimal("0.01")
        )
        
        return {
            "monthly_rent": float(rent_with_duration_discount),
            "base_monthly_rent": float(base_monthly_rent),
            "seasonal_adjustment": float(adjusted_rent - base_monthly_rent),
            "duration_discount_percentage": float(
                self._get_duration_discount_percentage(duration_months)
            ),
            "duration_months": duration_months,
            "total_rent": float(total_rent),
            "security_deposit": float(security_deposit),
            "referral_discount": float(referral_discount),
            "promotional_discount": float(promotional_discount),
            "total_discount": float(total_discount),
            "total_amount": float(total_amount),
            "advance_percentage": float(advance_percentage),
            "advance_amount": float(advance_amount),
            "breakdown": self._generate_price_breakdown(
                base_monthly_rent,
                adjusted_rent,
                rent_with_duration_discount,
                duration_months,
                total_rent,
                security_deposit,
                referral_discount,
                promotional_discount,
                total_amount,
                advance_amount,
            ),
        }
    
    def _get_base_monthly_rent(
        self,
        hostel_id: UUID,
        room_type: RoomType,
    ) -> Decimal:
        """
        Get base monthly rent for room type.
        
        In production, fetch from hostel/room configuration.
        This is a simplified placeholder.
        """
        # Placeholder pricing
        base_prices = {
            RoomType.SINGLE: Decimal("8000.00"),
            RoomType.DOUBLE: Decimal("6000.00"),
            RoomType.TRIPLE: Decimal("5000.00"),
            RoomType.QUAD: Decimal("4500.00"),
            RoomType.DORMITORY: Decimal("3500.00"),
        }
        
        return base_prices.get(room_type, Decimal("5000.00"))
    
    def _apply_seasonal_pricing(
        self,
        base_rent: Decimal,
        check_in_date: date,
    ) -> Decimal:
        """
        Apply seasonal pricing adjustments.
        
        Args:
            base_rent: Base monthly rent
            check_in_date: Check-in date
            
        Returns:
            Adjusted rent
        """
        # Peak season (June-August): +10%
        # Off-season (December-February): -5%
        # Regular season: no change
        
        month = check_in_date.month
        
        if month in [6, 7, 8]:  # Peak season
            return (base_rent * Decimal("1.10")).quantize(Decimal("0.01"))
        elif month in [12, 1, 2]:  # Off-season
            return (base_rent * Decimal("0.95")).quantize(Decimal("0.01"))
        else:
            return base_rent
    
    def _apply_duration_discount(
        self,
        monthly_rent: Decimal,
        duration_months: int,
    ) -> Decimal:
        """
        Apply duration-based discount.
        
        Args:
            monthly_rent: Monthly rent amount
            duration_months: Duration in months
            
        Returns:
            Discounted monthly rent
        """
        discount_percentage = self._get_duration_discount_percentage(duration_months)
        
        if discount_percentage > 0:
            discount_multiplier = Decimal("1.00") - (
                discount_percentage / Decimal("100.00")
            )
            return (monthly_rent * discount_multiplier).quantize(Decimal("0.01"))
        
        return monthly_rent
    
    def _get_duration_discount_percentage(
        self,
        duration_months: int,
    ) -> Decimal:
        """Get discount percentage based on duration."""
        if duration_months >= 12:
            return Decimal("10.00")  # 10% for 12+ months
        elif duration_months >= 6:
            return Decimal("5.00")  # 5% for 6-11 months
        elif duration_months >= 3:
            return Decimal("2.00")  # 2% for 3-5 months
        else:
            return Decimal("0.00")  # No discount for < 3 months
    
    def _calculate_security_deposit(
        self,
        monthly_rent: Decimal,
    ) -> Decimal:
        """
        Calculate security deposit.
        
        Typically 1 month's rent or a fixed amount.
        
        Args:
            monthly_rent: Monthly rent amount
            
        Returns:
            Security deposit amount
        """
        return monthly_rent  # 1 month's rent as security
    
    def _apply_referral_discount(
        self,
        total_rent: Decimal,
        referral_code: str,
    ) -> Decimal:
        """
        Apply referral code discount.
        
        Args:
            total_rent: Total rent amount
            referral_code: Referral code
            
        Returns:
            Discount amount
        """
        # In production, validate referral code and get discount percentage
        # Placeholder: 5% discount for valid referral
        referral_discount_percentage = Decimal("5.00")
        
        return (total_rent * referral_discount_percentage / 100).quantize(
            Decimal("0.01")
        )
    
    def _apply_promotional_discount(
        self,
        total_rent: Decimal,
        promotional_code: str,
    ) -> Decimal:
        """
        Apply promotional code discount.
        
        Args:
            total_rent: Total rent amount
            promotional_code: Promotional code
            
        Returns:
            Discount amount
        """
        # In production, validate promotional code and get discount
        # Placeholder: ₹500 flat discount or 10% (whichever is less)
        percentage_discount = (total_rent * Decimal("10.00") / 100).quantize(
            Decimal("0.01")
        )
        flat_discount = Decimal("500.00")
        
        return min(percentage_discount, flat_discount)
    
    def _generate_price_breakdown(
        self,
        base_rent: Decimal,
        seasonal_rent: Decimal,
        final_monthly_rent: Decimal,
        duration: int,
        total_rent: Decimal,
        security_deposit: Decimal,
        referral_discount: Decimal,
        promo_discount: Decimal,
        total_amount: Decimal,
        advance_amount: Decimal,
    ) -> Dict:
        """Generate detailed price breakdown."""
        return {
            "base_monthly_rent": float(base_rent),
            "seasonal_adjusted_rent": float(seasonal_rent),
            "duration_discounted_rent": float(final_monthly_rent),
            "duration_months": duration,
            "subtotal_rent": float(total_rent),
            "security_deposit": float(security_deposit),
            "discounts": {
                "referral": float(referral_discount),
                "promotional": float(promo_discount),
                "total": float(referral_discount + promo_discount),
            },
            "grand_total": float(total_amount),
            "advance_required": float(advance_amount),
            "balance_on_checkin": float(total_amount - advance_amount),
        }
    
    # ==================== PRICING UTILITIES ====================
    
    def calculate_refund_amount(
        self,
        booking_total: Decimal,
        advance_paid: Decimal,
        days_before_checkin: int,
    ) -> Dict:
        """
        Calculate refund amount based on cancellation policy.
        
        Args:
            booking_total: Total booking amount
            advance_paid: Advance amount paid
            days_before_checkin: Days before check-in
            
        Returns:
            Refund calculation breakdown
        """
        # Standard cancellation policy
        if days_before_checkin >= 30:
            refund_percentage = Decimal("90.00")  # 90% refund
        elif days_before_checkin >= 15:
            refund_percentage = Decimal("50.00")  # 50% refund
        elif days_before_checkin >= 7:
            refund_percentage = Decimal("25.00")  # 25% refund
        else:
            refund_percentage = Decimal("0.00")  # No refund
        
        refund_amount = (advance_paid * refund_percentage / 100).quantize(
            Decimal("0.01")
        )
        cancellation_charge = advance_paid - refund_amount
        
        return {
            "advance_paid": float(advance_paid),
            "days_before_checkin": days_before_checkin,
            "refund_percentage": float(refund_percentage),
            "refund_amount": float(refund_amount),
            "cancellation_charge": float(cancellation_charge),
        }
    
    def estimate_monthly_revenue(
        self,
        hostel_id: UUID,
        occupancy_rate: float = 80.0,
    ) -> Dict:
        """
        Estimate monthly revenue for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            occupancy_rate: Expected occupancy rate (0-100)
            
        Returns:
            Revenue estimate
        """
        # Placeholder implementation
        # In production, calculate based on actual room inventory and pricing
        
        total_beds = 100  # Fetch from hostel configuration
        avg_rent_per_bed = Decimal("5000.00")
        
        occupied_beds = int(total_beds * occupancy_rate / 100)
        monthly_revenue = occupied_beds * avg_rent_per_bed
        
        return {
            "total_beds": total_beds,
            "occupancy_rate": occupancy_rate,
            "occupied_beds": occupied_beds,
            "average_rent_per_bed": float(avg_rent_per_bed),
            "estimated_monthly_revenue": float(monthly_revenue),
        }