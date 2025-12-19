# app/repositories/room/room_type_repository.py
"""
Room type repository with type definitions and comparisons.
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, case, desc
from sqlalchemy.orm import Session, joinedload

from app.models.room import (
    RoomTypeDefinition,
    RoomTypeFeature,
    RoomTypePricing,
    RoomTypeAvailability,
    RoomTypeComparison,
    RoomTypeUpgrade,
    Room,
)
from app.models.base.enums import RoomType
from .base_repository import BaseRepository


class RoomTypeRepository(BaseRepository[RoomTypeDefinition]):
    """
    Repository for RoomTypeDefinition entity and related models.
    
    Handles:
    - Room type definitions
    - Type features and amenities
    - Pricing structures
    - Availability tracking
    - Type comparisons
    - Upgrade paths
    """

    def __init__(self, session: Session):
        super().__init__(RoomTypeDefinition, session)

    # ============================================================================
    # ROOM TYPE BASIC OPERATIONS
    # ============================================================================

    def create_room_type_with_details(
        self,
        type_data: Dict[str, Any],
        features: Optional[List[Dict[str, Any]]] = None,
        pricing_data: Optional[Dict[str, Any]] = None,
        commit: bool = True
    ) -> RoomTypeDefinition:
        """
        Create room type with features and pricing.
        
        Args:
            type_data: Room type data
            features: List of feature data
            pricing_data: Pricing data
            commit: Whether to commit transaction
            
        Returns:
            Created room type definition
        """
        try:
            # Create room type
            room_type = self.create(type_data, commit=False)
            
            # Create features
            if features:
                for feature_data in features:
                    feature = RoomTypeFeature(
                        room_type_id=room_type.id,
                        **feature_data
                    )
                    self.session.add(feature)
            
            # Create pricing
            if pricing_data:
                pricing = RoomTypePricing(
                    room_type_id=room_type.id,
                    effective_from=pricing_data.get('effective_from', date.today()),
                    is_current=True,
                    **pricing_data
                )
                self.session.add(pricing)
            
            # Create availability tracking
            availability = RoomTypeAvailability(
                room_type_id=room_type.id,
                total_rooms=0,
                available_rooms=0,
                occupied_rooms=0
            )
            self.session.add(availability)
            
            if commit:
                self.session.commit()
                self.session.refresh(room_type)
            
            return room_type
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create room type: {str(e)}")

    def find_by_type(
        self,
        hostel_id: str,
        room_type: RoomType
    ) -> Optional[RoomTypeDefinition]:
        """
        Find room type definition by type.
        
        Args:
            hostel_id: Hostel ID
            room_type: Room type enum
            
        Returns:
            Room type definition or None
        """
        types = self.find_by_criteria({
            'hostel_id': hostel_id,
            'room_type': room_type
        })
        return types[0] if types else None

    def find_by_type_code(
        self,
        hostel_id: str,
        type_code: str
    ) -> Optional[RoomTypeDefinition]:
        """
        Find room type by code.
        
        Args:
            hostel_id: Hostel ID
            type_code: Type code
            
        Returns:
            Room type definition or None
        """
        types = self.find_by_criteria({
            'hostel_id': hostel_id,
            'type_code': type_code
        })
        return types[0] if types else None

    def find_active_types(
        self,
        hostel_id: str,
        available_for_booking: bool = True
    ) -> List[RoomTypeDefinition]:
        """
        Find active room types.
        
        Args:
            hostel_id: Hostel ID
            available_for_booking: Filter by availability
            
        Returns:
            List of active room types
        """
        filters = {
            'hostel_id': hostel_id,
            'is_active': True
        }
        
        if available_for_booking:
            filters['is_available_for_booking'] = True
        
        return self.find_by_criteria(
            filters,
            order_by='display_order'
        )

    def find_featured_types(
        self,
        hostel_id: str
    ) -> List[RoomTypeDefinition]:
        """
        Find featured room types.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            List of featured room types
        """
        return self.find_by_criteria({
            'hostel_id': hostel_id,
            'is_featured': True,
            'is_active': True
        }, order_by='display_order')

    def find_popular_types(
        self,
        hostel_id: str,
        limit: int = 5
    ) -> List[RoomTypeDefinition]:
        """
        Find popular room types.
        
        Args:
            hostel_id: Hostel ID
            limit: Maximum number of results
            
        Returns:
            List of popular room types
        """
        query = select(RoomTypeDefinition).where(
            and_(
                RoomTypeDefinition.hostel_id == hostel_id,
                RoomTypeDefinition.is_popular == True,
                RoomTypeDefinition.is_active == True
            )
        ).order_by(
            desc(RoomTypeDefinition.average_occupancy_rate),
            RoomTypeDefinition.display_order
        ).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ============================================================================
    # ROOM TYPE FEATURES
    # ============================================================================

    def add_feature_to_type(
        self,
        room_type_id: str,
        feature_data: Dict[str, Any],
        commit: bool = True
    ) -> RoomTypeFeature:
        """
        Add feature to room type.
        
        Args:
            room_type_id: Room type ID
            feature_data: Feature data
            commit: Whether to commit transaction
            
        Returns:
            Created feature
        """
        try:
            feature = RoomTypeFeature(
                room_type_id=room_type_id,
                **feature_data
            )
            self.session.add(feature)
            
            if commit:
                self.session.commit()
                self.session.refresh(feature)
            
            return feature
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to add feature: {str(e)}")

    def get_type_features(
        self,
        room_type_id: str,
        category: Optional[str] = None,
        is_standard: Optional[bool] = None
    ) -> List[RoomTypeFeature]:
        """
        Get features for room type.
        
        Args:
            room_type_id: Room type ID
            category: Feature category filter
            is_standard: Standard feature filter
            
        Returns:
            List of features
        """
        query = select(RoomTypeFeature).where(
            RoomTypeFeature.room_type_id == room_type_id
        )
        
        if category:
            query = query.where(RoomTypeFeature.feature_category == category)
        
        if is_standard is not None:
            query = query.where(RoomTypeFeature.is_standard == is_standard)
        
        query = query.order_by(
            RoomTypeFeature.display_order,
            RoomTypeFeature.feature_name
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_features_by_category(
        self,
        room_type_id: str
    ) -> Dict[str, List[RoomTypeFeature]]:
        """
        Get features grouped by category.
        
        Args:
            room_type_id: Room type ID
            
        Returns:
            Dictionary of features by category
        """
        features = self.get_type_features(room_type_id)
        
        categorized = {}
        for feature in features:
            category = feature.feature_category
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(feature)
        
        return categorized

    def compare_type_features(
        self,
        type_id_1: str,
        type_id_2: str
    ) -> Dict[str, Any]:
        """
        Compare features between two room types.
        
        Args:
            type_id_1: First room type ID
            type_id_2: Second room type ID
            
        Returns:
            Dictionary with feature comparison
        """
        features_1 = {f.feature_name: f for f in self.get_type_features(type_id_1)}
        features_2 = {f.feature_name: f for f in self.get_type_features(type_id_2)}
        
        common_features = []
        unique_to_1 = []
        unique_to_2 = []
        
        for name, feature in features_1.items():
            if name in features_2:
                common_features.append(name)
            else:
                unique_to_1.append(name)
        
        for name in features_2.keys():
            if name not in features_1:
                unique_to_2.append(name)
        
        return {
            'common_features': common_features,
            'unique_to_type_1': unique_to_1,
            'unique_to_type_2': unique_to_2,
            'total_features_type_1': len(features_1),
            'total_features_type_2': len(features_2)
        }

    # ============================================================================
    # ROOM TYPE PRICING
    # ============================================================================

    def add_pricing_tier(
        self,
        room_type_id: str,
        pricing_data: Dict[str, Any],
        commit: bool = True
    ) -> RoomTypePricing:
        """
        Add pricing tier to room type.
        
        Args:
            room_type_id: Room type ID
            pricing_data: Pricing data
            commit: Whether to commit transaction
            
        Returns:
            Created pricing record
        """
        try:
            # Mark existing current pricing as historical if needed
            if pricing_data.get('is_current', False):
                self.session.execute(
                    select(RoomTypePricing).where(
                        and_(
                            RoomTypePricing.room_type_id == room_type_id,
                            RoomTypePricing.is_current == True
                        )
                    )
                ).scalars().all()
                
                for existing in self.session.execute(
                    select(RoomTypePricing).where(
                        and_(
                            RoomTypePricing.room_type_id == room_type_id,
                            RoomTypePricing.is_current == True
                        )
                    )
                ).scalars():
                    existing.is_current = False
                    existing.effective_to = pricing_data.get('effective_from', date.today())
            
            pricing = RoomTypePricing(
                room_type_id=room_type_id,
                **pricing_data
            )
            self.session.add(pricing)
            
            if commit:
                self.session.commit()
                self.session.refresh(pricing)
            
            return pricing
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to add pricing: {str(e)}")

    def get_current_pricing(
        self,
        room_type_id: str
    ) -> Optional[RoomTypePricing]:
        """
        Get current pricing for room type.
        
        Args:
            room_type_id: Room type ID
            
        Returns:
            Current pricing or None
        """
        return self.session.execute(
            select(RoomTypePricing).where(
                and_(
                    RoomTypePricing.room_type_id == room_type_id,
                    RoomTypePricing.is_current == True
                )
            )
        ).scalar_one_or_none()

    def get_pricing_history(
        self,
        room_type_id: str,
        limit: int = 10
    ) -> List[RoomTypePricing]:
        """
        Get pricing history for room type.
        
        Args:
            room_type_id: Room type ID
            limit: Maximum number of records
            
        Returns:
            List of pricing records
        """
        query = select(RoomTypePricing).where(
            RoomTypePricing.room_type_id == room_type_id
        ).order_by(desc(RoomTypePricing.effective_from)).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_pricing_for_date(
        self,
        room_type_id: str,
        check_date: date
    ) -> Optional[RoomTypePricing]:
        """
        Get pricing applicable for specific date.
        
        Args:
            room_type_id: Room type ID
            check_date: Date to check
            
        Returns:
            Applicable pricing or None
        """
        query = select(RoomTypePricing).where(
            and_(
                RoomTypePricing.room_type_id == room_type_id,
                RoomTypePricing.effective_from <= check_date,
                or_(
                    RoomTypePricing.effective_to.is_(None),
                    RoomTypePricing.effective_to >= check_date
                )
            )
        ).order_by(desc(RoomTypePricing.effective_from)).limit(1)
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def calculate_discounted_price(
        self,
        room_type_id: str,
        duration_months: int
    ) -> Optional[Decimal]:
        """
        Calculate discounted price based on duration.
        
        Args:
            room_type_id: Room type ID
            duration_months: Duration in months
            
        Returns:
            Discounted price or None
        """
        pricing = self.get_current_pricing(room_type_id)
        if not pricing:
            return None
        
        base_price = pricing.base_price_monthly
        
        if duration_months >= 12 and pricing.base_price_yearly:
            return pricing.base_price_yearly
        elif duration_months >= 6 and pricing.base_price_half_yearly:
            return pricing.base_price_half_yearly
        elif duration_months >= 3 and pricing.base_price_quarterly:
            return pricing.base_price_quarterly
        
        return base_price

    # ============================================================================
    # ROOM TYPE AVAILABILITY
    # ============================================================================

    def update_type_availability(
        self,
        room_type_id: str,
        availability_data: Dict[str, Any],
        commit: bool = True
    ) -> Optional[RoomTypeAvailability]:
        """
        Update room type availability.
        
        Args:
            room_type_id: Room type ID
            availability_data: Availability data
            commit: Whether to commit transaction
            
        Returns:
            Updated availability
        """
        try:
            availability = self.session.execute(
                select(RoomTypeAvailability).where(
                    RoomTypeAvailability.room_type_id == room_type_id
                )
            ).scalar_one_or_none()
            
            if not availability:
                availability = RoomTypeAvailability(
                    room_type_id=room_type_id,
                    **availability_data
                )
                self.session.add(availability)
            else:
                for key, value in availability_data.items():
                    if hasattr(availability, key):
                        setattr(availability, key, value)
                availability.last_availability_check = datetime.utcnow()
            
            if commit:
                self.session.commit()
                self.session.refresh(availability)
            
            return availability
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to update availability: {str(e)}")

    def sync_type_availability_from_rooms(
        self,
        room_type_id: str,
        commit: bool = True
    ) -> Optional[RoomTypeAvailability]:
        """
        Synchronize type availability from actual rooms.
        
        Args:
            room_type_id: Room type ID
            commit: Whether to commit transaction
            
        Returns:
            Updated availability
        """
        # Get room type to know which rooms to query
        room_type_def = self.find_by_id(room_type_id)
        if not room_type_def:
            return None
        
        # Aggregate room data
        query = select(
            func.count(Room.id).label('total_rooms'),
            func.sum(Room.total_beds).label('total_beds'),
            func.sum(Room.available_beds).label('available_beds'),
            func.sum(Room.occupied_beds).label('occupied_beds'),
            func.sum(
                case((Room.is_under_maintenance == True, 1), else_=0)
            ).label('maintenance_rooms')
        ).where(
            and_(
                Room.hostel_id == room_type_def.hostel_id,
                Room.room_type == room_type_def.room_type,
                Room.is_deleted == False
            )
        )
        
        result = self.session.execute(query).one()
        
        total_rooms = result.total_rooms or 0
        available_rooms = total_rooms - (result.maintenance_rooms or 0)
        total_beds = result.total_beds or 0
        occupied_beds = result.occupied_beds or 0
        
        occupancy_rate = (occupied_beds / total_beds * 100) if total_beds > 0 else Decimal('0.00')
        
        availability_data = {
            'total_rooms': total_rooms,
            'available_rooms': available_rooms,
            'occupied_rooms': result.occupied_beds or 0,
            'maintenance_rooms': result.maintenance_rooms or 0,
            'total_beds': total_beds,
            'available_beds': result.available_beds or 0,
            'occupancy_rate': Decimal(str(occupancy_rate)).quantize(Decimal('0.01'))
        }
        
        return self.update_type_availability(
            room_type_id,
            availability_data,
            commit=commit
        )

    def get_type_availability(
        self,
        room_type_id: str
    ) -> Optional[RoomTypeAvailability]:
        """
        Get room type availability.
        
        Args:
            room_type_id: Room type ID
            
        Returns:
            Type availability or None
        """
        return self.session.execute(
            select(RoomTypeAvailability).where(
                RoomTypeAvailability.room_type_id == room_type_id
            )
        ).scalar_one_or_none()

    def find_available_types(
        self,
        hostel_id: str,
        min_rooms: int = 1
    ) -> List[RoomTypeDefinition]:
        """
        Find room types with availability.
        
        Args:
            hostel_id: Hostel ID
            min_rooms: Minimum available rooms
            
        Returns:
            List of available room types
        """
        query = select(RoomTypeDefinition).join(
            RoomTypeAvailability,
            RoomTypeDefinition.id == RoomTypeAvailability.room_type_id
        ).where(
            and_(
                RoomTypeDefinition.hostel_id == hostel_id,
                RoomTypeDefinition.is_active == True,
                RoomTypeAvailability.available_rooms >= min_rooms
            )
        ).order_by(RoomTypeDefinition.display_order)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ============================================================================
    # ROOM TYPE COMPARISONS
    # ============================================================================

    def create_type_comparison(
        self,
        room_type_id: str,
        compared_with_type_id: str,
        commit: bool = True
    ) -> RoomTypeComparison:
        """
        Create comparison between two room types.
        
        Args:
            room_type_id: First room type ID
            compared_with_type_id: Second room type ID
            commit: Whether to commit transaction
            
        Returns:
            Created comparison
        """
        try:
            # Get both room types
            type_1 = self.find_by_id(room_type_id)
            type_2 = self.find_by_id(compared_with_type_id)
            
            if not type_1 or not type_2:
                raise ValueError("One or both room types not found")
            
            # Get current pricing
            pricing_1 = self.get_current_pricing(room_type_id)
            pricing_2 = self.get_current_pricing(compared_with_type_id)
            
            price_1 = pricing_1.base_price_monthly if pricing_1 else Decimal('0.00')
            price_2 = pricing_2.base_price_monthly if pricing_2 else Decimal('0.00')
            
            price_diff = price_1 - price_2
            price_diff_pct = (price_diff / price_2 * 100) if price_2 > 0 else Decimal('0.00')
            
            # Compare features
            feature_comparison = self.compare_type_features(room_type_id, compared_with_type_id)
            
            comparison = RoomTypeComparison(
                room_type_id=room_type_id,
                compared_with_type_id=compared_with_type_id,
                price_difference=price_diff,
                price_difference_percentage=price_diff_pct,
                additional_features=feature_comparison['unique_to_type_1'],
                missing_features=feature_comparison['unique_to_type_2'],
                size_difference_sqft=(type_1.standard_size_sqft or 0) - (type_2.standard_size_sqft or 0),
                capacity_difference=type_1.standard_capacity - type_2.standard_capacity
            )
            self.session.add(comparison)
            
            if commit:
                self.session.commit()
                self.session.refresh(comparison)
            
            return comparison
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create comparison: {str(e)}")

    def get_type_comparisons(
        self,
        room_type_id: str
    ) -> List[RoomTypeComparison]:
        """
        Get all comparisons for a room type.
        
        Args:
            room_type_id: Room type ID
            
        Returns:
            List of comparisons
        """
        query = select(RoomTypeComparison).where(
            RoomTypeComparison.room_type_id == room_type_id
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def compare_all_types(
        self,
        hostel_id: str,
        commit: bool = True
    ) -> List[RoomTypeComparison]:
        """
        Create comparisons between all room types in hostel.
        
        Args:
            hostel_id: Hostel ID
            commit: Whether to commit transaction
            
        Returns:
            List of created comparisons
        """
        types = self.find_active_types(hostel_id)
        comparisons = []
        
        for i, type_1 in enumerate(types):
            for type_2 in types[i+1:]:
                # Check if comparison already exists
                existing = self.session.execute(
                    select(RoomTypeComparison).where(
                        and_(
                            RoomTypeComparison.room_type_id == type_1.id,
                            RoomTypeComparison.compared_with_type_id == type_2.id
                        )
                    )
                ).scalar_one_or_none()
                
                if not existing:
                    comparison = self.create_type_comparison(
                        type_1.id,
                        type_2.id,
                        commit=False
                    )
                    comparisons.append(comparison)
        
        if commit and comparisons:
            self.session.commit()
            for comp in comparisons:
                self.session.refresh(comp)
        
        return comparisons

    # ============================================================================
    # ROOM TYPE UPGRADES
    # ============================================================================

    def create_upgrade_path(
        self,
        from_type_id: str,
        to_type_id: str,
        upgrade_data: Dict[str, Any],
        commit: bool = True
    ) -> RoomTypeUpgrade:
        """
        Create upgrade path between room types.
        
        Args:
            from_type_id: Source room type ID
            to_type_id: Target room type ID
            upgrade_data: Upgrade data
            commit: Whether to commit transaction
            
        Returns:
            Created upgrade path
        """
        try:
            # Calculate price difference
            pricing_from = self.get_current_pricing(from_type_id)
            pricing_to = self.get_current_pricing(to_type_id)
            
            if pricing_from and pricing_to:
                price_diff = pricing_to.base_price_monthly - pricing_from.base_price_monthly
                price_diff_pct = (price_diff / pricing_from.base_price_monthly * 100)
                
                upgrade_data['price_difference_monthly'] = price_diff
                upgrade_data['price_difference_percentage'] = price_diff_pct
            
            upgrade = RoomTypeUpgrade(
                from_room_type_id=from_type_id,
                to_room_type_id=to_type_id,
                **upgrade_data
            )
            self.session.add(upgrade)
            
            if commit:
                self.session.commit()
                self.session.refresh(upgrade)
            
            return upgrade
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create upgrade path: {str(e)}")

    def get_upgrade_options(
        self,
        from_type_id: str,
        is_available: bool = True
    ) -> List[RoomTypeUpgrade]:
        """
        Get available upgrade options from a room type.
        
        Args:
            from_type_id: Source room type ID
            is_available: Filter by availability
            
        Returns:
            List of upgrade options
        """
        query = select(RoomTypeUpgrade).where(
            RoomTypeUpgrade.from_room_type_id == from_type_id
        )
        
        if is_available:
            query = query.where(RoomTypeUpgrade.is_available == True)
        
        # Check validity period
        today = date.today()
        query = query.where(
            or_(
                RoomTypeUpgrade.valid_from.is_(None),
                RoomTypeUpgrade.valid_from <= today
            )
        ).where(
            or_(
                RoomTypeUpgrade.valid_to.is_(None),
                RoomTypeUpgrade.valid_to >= today
            )
        )
        
        query = query.order_by(RoomTypeUpgrade.price_difference_monthly)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_downgrade_options(
        self,
        from_type_id: str,
        is_available: bool = True
    ) -> List[RoomTypeUpgrade]:
        """
        Get available downgrade options (upgrades TO this type).
        
        Args:
            from_type_id: Source room type ID
            is_available: Filter by availability
            
        Returns:
            List of downgrade options
        """
        query = select(RoomTypeUpgrade).where(
            RoomTypeUpgrade.to_room_type_id == from_type_id
        )
        
        if is_available:
            query = query.where(RoomTypeUpgrade.is_available == True)
        
        today = date.today()
        query = query.where(
            or_(
                RoomTypeUpgrade.valid_from.is_(None),
                RoomTypeUpgrade.valid_from <= today
            )
        ).where(
            or_(
                RoomTypeUpgrade.valid_to.is_(None),
                RoomTypeUpgrade.valid_to >= today
            )
        )
        
        query = query.order_by(desc(RoomTypeUpgrade.price_difference_monthly))
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ============================================================================
    # STATISTICS AND ANALYTICS
    # ============================================================================

    def get_type_statistics(
        self,
        hostel_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get statistics for all room types.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            List of type statistics
        """
        types = self.find_active_types(hostel_id, available_for_booking=False)
        
        statistics = []
        for room_type in types:
            availability = self.get_type_availability(room_type.id)
            pricing = self.get_current_pricing(room_type.id)
            
            stats = {
                'room_type': room_type.room_type,
                'type_name': room_type.type_name,
                'total_rooms': availability.total_rooms if availability else 0,
                'available_rooms': availability.available_rooms if availability else 0,
                'occupancy_rate': float(availability.occupancy_rate) if availability else 0,
                'base_price': float(pricing.base_price_monthly) if pricing else 0,
                'is_featured': room_type.is_featured,
                'is_popular': room_type.is_popular,
                'average_occupancy': float(room_type.average_occupancy_rate or 0)
            }
            statistics.append(stats)
        
        return statistics

    def get_pricing_comparison(
        self,
        hostel_id: str
    ) -> Dict[str, Any]:
        """
        Get pricing comparison across all room types.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Pricing comparison data
        """
        types = self.find_active_types(hostel_id, available_for_booking=False)
        
        pricing_data = []
        for room_type in types:
            pricing = self.get_current_pricing(room_type.id)
            if pricing:
                pricing_data.append({
                    'type_name': room_type.type_name,
                    'monthly': float(pricing.base_price_monthly),
                    'quarterly': float(pricing.base_price_quarterly or 0),
                    'half_yearly': float(pricing.base_price_half_yearly or 0),
                    'yearly': float(pricing.base_price_yearly or 0)
                })
        
        # Calculate min/max
        monthly_prices = [p['monthly'] for p in pricing_data if p['monthly'] > 0]
        
        return {
            'types': pricing_data,
            'min_price': min(monthly_prices) if monthly_prices else 0,
            'max_price': max(monthly_prices) if monthly_prices else 0,
            'avg_price': sum(monthly_prices) / len(monthly_prices) if monthly_prices else 0
        }

    def get_capacity_summary(
        self,
        hostel_id: str
    ) -> Dict[str, Any]:
        """
        Get capacity summary across room types.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Capacity summary
        """
        query = select(
            RoomTypeDefinition.room_type,
            RoomTypeDefinition.type_name,
            func.count(Room.id).label('room_count'),
            func.sum(Room.total_beds).label('total_beds'),
            func.sum(Room.available_beds).label('available_beds'),
            func.avg(Room.price_monthly).label('avg_price')
        ).outerjoin(
            Room,
            and_(
                Room.room_type == RoomTypeDefinition.room_type,
                Room.hostel_id == RoomTypeDefinition.hostel_id,
                Room.is_deleted == False
            )
        ).where(
            RoomTypeDefinition.hostel_id == hostel_id
        ).group_by(
            RoomTypeDefinition.room_type,
            RoomTypeDefinition.type_name
        )
        
        result = self.session.execute(query)
        
        capacity_data = []
        total_rooms = 0
        total_beds = 0
        total_available = 0
        
        for row in result:
            room_count = row.room_count or 0
            beds = row.total_beds or 0
            available = row.available_beds or 0
            
            capacity_data.append({
                'type': row.room_type,
                'type_name': row.type_name,
                'rooms': room_count,
                'total_beds': beds,
                'available_beds': available,
                'occupancy_rate': ((beds - available) / beds * 100) if beds > 0 else 0,
                'avg_price': float(row.avg_price or 0)
            })
            
            total_rooms += room_count
            total_beds += beds
            total_available += available
        
        return {
            'by_type': capacity_data,
            'summary': {
                'total_rooms': total_rooms,
                'total_beds': total_beds,
                'available_beds': total_available,
                'overall_occupancy': ((total_beds - total_available) / total_beds * 100) if total_beds > 0 else 0
            }
        }

    def get_popular_types_ranking(
        self,
        hostel_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get ranking of popular room types.
        
        Args:
            hostel_id: Hostel ID
            limit: Maximum number of results
            
        Returns:
            List of ranked room types
        """
        query = select(
            RoomTypeDefinition,
            RoomTypeAvailability.occupancy_rate,
            func.count(Room.id).label('room_count')
        ).outerjoin(
            RoomTypeAvailability,
            RoomTypeDefinition.id == RoomTypeAvailability.room_type_id
        ).outerjoin(
            Room,
            and_(
                Room.room_type == RoomTypeDefinition.room_type,
                Room.hostel_id == RoomTypeDefinition.hostel_id,
                Room.is_deleted == False
            )
        ).where(
            RoomTypeDefinition.hostel_id == hostel_id
        ).group_by(
            RoomTypeDefinition.id,
            RoomTypeAvailability.occupancy_rate
        ).order_by(
            desc(RoomTypeAvailability.occupancy_rate)
        ).limit(limit)
        
        result = self.session.execute(query)
        
        ranking = []
        rank = 1
        for room_type, occupancy, room_count in result:
            ranking.append({
                'rank': rank,
                'type_name': room_type.type_name,
                'occupancy_rate': float(occupancy or 0),
                'room_count': room_count,
                'is_featured': room_type.is_featured,
                'is_popular': room_type.is_popular
            })
            rank += 1
        
        return ranking

    def recommend_type_for_student(
        self,
        hostel_id: str,
        student_preferences: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Recommend room types based on student preferences.
        
        Args:
            hostel_id: Hostel ID
            student_preferences: Student preference data
            
        Returns:
            List of recommended types with scores
        """
        types = self.find_available_types(hostel_id, min_rooms=1)
        
        recommendations = []
        for room_type in types:
            score = Decimal('50.00')  # Base score
            
            # Match capacity preference
            if student_preferences.get('preferred_capacity'):
                if room_type.standard_capacity == student_preferences['preferred_capacity']:
                    score += Decimal('20.00')
            
            # Match budget
            pricing = self.get_current_pricing(room_type.id)
            if pricing and student_preferences.get('max_budget'):
                max_budget = Decimal(str(student_preferences['max_budget']))
                if pricing.base_price_monthly <= max_budget:
                    score += Decimal('15.00')
                    # Higher score for better value
                    value_ratio = (max_budget - pricing.base_price_monthly) / max_budget
                    score += value_ratio * Decimal('10.00')
            
            # Match features
            if student_preferences.get('required_features'):
                type_features = self.get_type_features(room_type.id)
                feature_names = {f.feature_name for f in type_features}
                required = set(student_preferences['required_features'])
                matched = required.intersection(feature_names)
                score += Decimal(str(len(matched) * 5))
            
            recommendations.append({
                'room_type': room_type,
                'score': float(score),
                'pricing': pricing,
                'availability': self.get_type_availability(room_type.id)
            })
        
        # Sort by score
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        
        return recommendations
