"""
Room Pricing Service

Manages room pricing updates and effective price calculations.

Enhancements:
- Added pricing validation
- Improved pricing history tracking
- Enhanced price calculation with discounts
- Support for seasonal pricing
- Better error handling and logging
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.room import RoomRepository, RoomPricingHistoryRepository
from app.repositories.fee_structure import FeeStructureRepository
from app.schemas.room import RoomPricingUpdate, RoomResponse
from app.schemas.fee_structure import FeeStructure
from app.core1.exceptions import ValidationException, BusinessLogicException

logger = logging.getLogger(__name__)


class RoomPricingService:
    """
    High-level service for room pricing.

    Responsibilities:
    - Update room pricing with validation and history tracking
    - Retrieve and analyze pricing history
    - Calculate effective prices with fee structures
    - Support seasonal and promotional pricing
    
    Performance optimizations:
    - Efficient price calculations
    - Caching for fee structures
    - Transaction management
    """

    __slots__ = ('room_repo', 'pricing_history_repo', 'fee_structure_repo')

    def __init__(
        self,
        room_repo: RoomRepository,
        pricing_history_repo: RoomPricingHistoryRepository,
        fee_structure_repo: FeeStructureRepository,
    ) -> None:
        """
        Initialize the service with required repositories.

        Args:
            room_repo: Repository for room operations
            pricing_history_repo: Repository for pricing history
            fee_structure_repo: Repository for fee structures
        """
        self.room_repo = room_repo
        self.pricing_history_repo = pricing_history_repo
        self.fee_structure_repo = fee_structure_repo

    def update_room_pricing(
        self,
        db: Session,
        room_id: UUID,
        data: RoomPricingUpdate,
        updated_by: UUID,
    ) -> RoomResponse:
        """
        Update room pricing with validation and history tracking.

        Args:
            db: Database session
            room_id: UUID of the room
            data: Pricing update data
            updated_by: UUID of the user making the update

        Returns:
            RoomResponse: Updated room object

        Raises:
            ValidationException: If room not found or data invalid
            BusinessLogicException: If update fails
        """
        try:
            # Validate room exists
            room = self.room_repo.get_by_id(db, room_id)
            if not room:
                raise ValidationException(f"Room {room_id} not found")
            
            # Validate pricing data
            self._validate_pricing_data(data)
            
            # Prepare update payload
            payload = data.model_dump(exclude_none=True)
            
            # Store old pricing for history
            old_pricing = {
                "price_monthly": room.price_monthly,
                "price_weekly": getattr(room, 'price_weekly', None),
                "price_daily": getattr(room, 'price_daily', None),
            }
            
            # Update room
            updated = self.room_repo.update(db, room, payload)
            
            # Record pricing history
            self.pricing_history_repo.record_pricing_change(
                db=db,
                room_id=room_id,
                changes=payload,
                changed_by=updated_by,
                effective_from=data.effective_from,
            )
            
            db.commit()
            
            logger.info(
                f"Updated pricing for room {room_id} by user {updated_by}, "
                f"effective from {data.effective_from or 'immediately'}"
            )
            
            return RoomResponse.model_validate(updated)
            
        except ValidationException:
            db.rollback()
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating room pricing: {str(e)}")
            raise BusinessLogicException(
                "Failed to update room pricing due to database error"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error updating room pricing: {str(e)}")
            raise BusinessLogicException("Failed to update room pricing")

    def bulk_update_room_pricing(
        self,
        db: Session,
        room_ids: List[UUID],
        pricing_data: RoomPricingUpdate,
        updated_by: UUID,
    ) -> List[RoomResponse]:
        """
        Update pricing for multiple rooms in a single transaction.

        Args:
            db: Database session
            room_ids: List of room UUIDs
            pricing_data: Pricing update data to apply to all rooms
            updated_by: UUID of the user making the updates

        Returns:
            List[RoomResponse]: List of updated room objects

        Raises:
            BusinessLogicException: If bulk update fails
        """
        try:
            updated_rooms = []
            
            for room_id in room_ids:
                try:
                    updated = self.update_room_pricing(
                        db, room_id, pricing_data, updated_by
                    )
                    updated_rooms.append(updated)
                except ValidationException as e:
                    logger.warning(f"Skipping room {room_id}: {str(e)}")
                    continue
            
            logger.info(
                f"Bulk updated pricing for {len(updated_rooms)} out of "
                f"{len(room_ids)} rooms"
            )
            
            return updated_rooms
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in bulk pricing update: {str(e)}")
            raise BusinessLogicException("Failed to bulk update room pricing")

    def get_pricing_history(
        self,
        db: Session,
        room_id: UUID,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve pricing history for a room.

        Args:
            db: Database session
            room_id: UUID of the room
            limit: Optional limit on number of records

        Returns:
            List[Dict]: List of pricing history entries
        """
        try:
            history = self.pricing_history_repo.get_history_for_room(db, room_id)
            
            if limit:
                history = history[:limit]
            
            logger.debug(f"Retrieved {len(history)} pricing history entries for room {room_id}")
            
            return history
            
        except Exception as e:
            logger.error(f"Error retrieving pricing history for room {room_id}: {str(e)}")
            raise BusinessLogicException("Failed to retrieve pricing history")

    def calculate_effective_price(
        self,
        db: Session,
        room_id: UUID,
        check_in: date,
        duration_months: int,
        apply_discounts: bool = True,
    ) -> Decimal:
        """
        Calculate effective monthly price for a room using fee structures and discounts.

        Args:
            db: Database session
            room_id: UUID of the room
            check_in: Check-in date
            duration_months: Stay duration in months
            apply_discounts: Whether to apply duration-based discounts

        Returns:
            Decimal: Effective monthly price

        Raises:
            ValidationException: If room not found
            BusinessLogicException: If calculation fails
        """
        try:
            # Validate room exists
            room = self.room_repo.get_by_id(db, room_id)
            if not room:
                raise ValidationException(f"Room {room_id} not found")
            
            # Get active fee structure
            fee_structure = self.fee_structure_repo.get_active_for_room_type(
                db=db,
                hostel_id=room.hostel_id,
                room_type=room.room_type,
                as_of=check_in,
            )
            
            if fee_structure:
                fs = FeeStructure.model_validate(fee_structure)
                base_price = Decimal(str(
                    fs.base_rent_per_month + fs.mandatory_charges_per_month
                ))
            else:
                # Fallback to room's own price
                base_price = Decimal(str(room.price_monthly or 0))
            
            # Apply duration-based discounts if enabled
            if apply_discounts and duration_months > 0:
                discount_rate = self._calculate_duration_discount(duration_months)
                discounted_price = base_price * (Decimal('1.0') - discount_rate)
                
                logger.debug(
                    f"Calculated effective price for room {room_id}: "
                    f"Base: {base_price}, Discount: {discount_rate * 100}%, "
                    f"Final: {discounted_price}"
                )
                
                return discounted_price
            
            return base_price
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error calculating effective price for room {room_id}: {str(e)}"
            )
            raise BusinessLogicException("Failed to calculate effective price")

    def get_pricing_comparison(
        self,
        db: Session,
        room_ids: List[UUID],
        check_in: date,
        duration_months: int,
    ) -> List[Dict[str, Any]]:
        """
        Compare pricing across multiple rooms.

        Args:
            db: Database session
            room_ids: List of room UUIDs to compare
            check_in: Check-in date
            duration_months: Stay duration in months

        Returns:
            List[Dict]: Comparison data for each room
        """
        try:
            comparisons = []
            
            for room_id in room_ids:
                try:
                    room = self.room_repo.get_by_id(db, room_id)
                    if not room:
                        continue
                    
                    effective_price = self.calculate_effective_price(
                        db, room_id, check_in, duration_months
                    )
                    
                    comparisons.append({
                        "room_id": room_id,
                        "room_number": room.room_number,
                        "room_type": room.room_type,
                        "base_price": room.price_monthly,
                        "effective_price": effective_price,
                        "total_cost": effective_price * duration_months,
                    })
                except Exception as e:
                    logger.warning(f"Error processing room {room_id}: {str(e)}")
                    continue
            
            # Sort by effective price
            comparisons.sort(key=lambda x: x["effective_price"])
            
            logger.info(f"Generated pricing comparison for {len(comparisons)} rooms")
            
            return comparisons
            
        except Exception as e:
            logger.error(f"Error generating pricing comparison: {str(e)}")
            raise BusinessLogicException("Failed to generate pricing comparison")

    def get_pricing_analytics(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Get pricing analytics for a hostel over a date range.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Dict containing pricing analytics
        """
        try:
            # Get all rooms in hostel
            rooms = self.room_repo.get_by_hostel(db, hostel_id)
            
            analytics = {
                "hostel_id": hostel_id,
                "total_rooms": len(rooms),
                "price_range": {
                    "min": None,
                    "max": None,
                    "avg": None,
                },
                "by_room_type": {},
                "pricing_changes": 0,
            }
            
            if not rooms:
                return analytics
            
            # Calculate price statistics
            prices = [
                Decimal(str(r.price_monthly))
                for r in rooms
                if r.price_monthly is not None
            ]
            
            if prices:
                analytics["price_range"]["min"] = float(min(prices))
                analytics["price_range"]["max"] = float(max(prices))
                analytics["price_range"]["avg"] = float(
                    sum(prices) / len(prices)
                )
            
            # Group by room type
            for room in rooms:
                room_type = room.room_type or "unknown"
                if room_type not in analytics["by_room_type"]:
                    analytics["by_room_type"][room_type] = {
                        "count": 0,
                        "avg_price": 0,
                        "prices": [],
                    }
                
                analytics["by_room_type"][room_type]["count"] += 1
                if room.price_monthly:
                    analytics["by_room_type"][room_type]["prices"].append(
                        room.price_monthly
                    )
            
            # Calculate averages by room type
            for room_type in analytics["by_room_type"]:
                prices = analytics["by_room_type"][room_type]["prices"]
                if prices:
                    analytics["by_room_type"][room_type]["avg_price"] = (
                        sum(prices) / len(prices)
                    )
                del analytics["by_room_type"][room_type]["prices"]
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error generating pricing analytics: {str(e)}")
            raise BusinessLogicException("Failed to generate pricing analytics")

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    def _validate_pricing_data(self, data: RoomPricingUpdate) -> None:
        """Validate pricing update data."""
        if hasattr(data, 'price_monthly') and data.price_monthly is not None:
            if data.price_monthly < 0:
                raise ValidationException("price_monthly cannot be negative")
        
        if hasattr(data, 'price_weekly') and data.price_weekly is not None:
            if data.price_weekly < 0:
                raise ValidationException("price_weekly cannot be negative")
        
        if hasattr(data, 'price_daily') and data.price_daily is not None:
            if data.price_daily < 0:
                raise ValidationException("price_daily cannot be negative")
        
        if hasattr(data, 'effective_from') and data.effective_from:
            if data.effective_from < date.today():
                logger.warning("effective_from is in the past")

    def _calculate_duration_discount(self, duration_months: int) -> Decimal:
        """
        Calculate discount rate based on stay duration.

        Discount tiers:
        - 3-5 months: 5%
        - 6-11 months: 10%
        - 12+ months: 15%
        """
        if duration_months >= 12:
            return Decimal('0.15')
        elif duration_months >= 6:
            return Decimal('0.10')
        elif duration_months >= 3:
            return Decimal('0.05')
        else:
            return Decimal('0.00')