# app/repositories/room/room_amenity_repository.py
"""
Room amenity repository with comprehensive amenity management.
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, case, desc
from sqlalchemy.orm import Session, joinedload

from app.models.room import (
    RoomAmenity,
    AmenityCondition,
    AmenityMaintenance,
    AmenityUsage,
    AmenityFeedback,
    AmenityInventory,
    Room,
)
from .base_repository import BaseRepository


class RoomAmenityRepository(BaseRepository[RoomAmenity]):
    """
    Repository for RoomAmenity entity and related models.
    
    Handles:
    - Amenity CRUD operations
    - Amenity conditions and tracking
    - Maintenance scheduling
    - Usage analytics
    - Feedback management
    - Inventory tracking
    """

    def __init__(self, session: Session):
        super().__init__(RoomAmenity, session)

    # ============================================================================
    # AMENITY BASIC OPERATIONS
    # ============================================================================

    def create_amenity_with_details(
        self,
        amenity_data: Dict[str, Any],
        condition_data: Optional[Dict[str, Any]] = None,
        inventory_data: Optional[Dict[str, Any]] = None,
        commit: bool = True
    ) -> RoomAmenity:
        """
        Create amenity with condition and inventory tracking.
        
        Args:
            amenity_data: Amenity data
            condition_data: Condition data
            inventory_data: Inventory data
            commit: Whether to commit transaction
            
        Returns:
            Created amenity
        """
        try:
            # Create amenity
            amenity = self.create(amenity_data, commit=False)
            
            # Create condition record
            if condition_data:
                condition = AmenityCondition(
                    amenity_id=amenity.id,
                    **condition_data
                )
            else:
                # Create default condition
                condition = AmenityCondition(
                    amenity_id=amenity.id,
                    condition_score=10,
                    condition_grade='A',
                    wear_level='MINIMAL',
                    is_fully_functional=True,
                    cleanliness_rating=10
                )
            self.session.add(condition)
            
            # Create inventory record if provided
            if inventory_data:
                # Generate inventory code if not provided
                if 'inventory_code' not in inventory_data:
                    inventory_data['inventory_code'] = self._generate_inventory_code(
                        amenity.room_id,
                        amenity.amenity_name
                    )
                
                inventory = AmenityInventory(
                    amenity_id=amenity.id,
                    acquisition_date=inventory_data.get('acquisition_date', date.today()),
                    current_value=inventory_data.get('unit_cost', Decimal('0.00')),
                    **inventory_data
                )
                self.session.add(inventory)
            
            if commit:
                self.session.commit()
                self.session.refresh(amenity)
            
            return amenity
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create amenity: {str(e)}")

    def _generate_inventory_code(self, room_id: str, amenity_name: str) -> str:
        """Generate unique inventory code."""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        name_prefix = ''.join(amenity_name.split()[:2]).upper()[:4]
        return f"INV-{name_prefix}-{timestamp}"

    def find_amenities_by_room(
        self,
        room_id: str,
        include_deleted: bool = False,
        load_condition: bool = False
    ) -> List[RoomAmenity]:
        """
        Find all amenities in a room.
        
        Args:
            room_id: Room ID
            include_deleted: Whether to include soft-deleted amenities
            load_condition: Whether to load condition relationship
            
        Returns:
            List of amenities
        """
        query = select(RoomAmenity).where(RoomAmenity.room_id == room_id)
        
        if not include_deleted:
            query = query.where(RoomAmenity.is_deleted == False)
        
        if load_condition:
            query = query.options(joinedload(RoomAmenity.condition))
        
        query = query.order_by(RoomAmenity.amenity_type, RoomAmenity.amenity_name)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_amenities_by_type(
        self,
        amenity_type: str,
        hostel_id: Optional[str] = None,
        is_functional: bool = True
    ) -> List[RoomAmenity]:
        """
        Find amenities by type.
        
        Args:
            amenity_type: Amenity type
            hostel_id: Hostel ID filter
            is_functional: Functional status filter
            
        Returns:
            List of amenities
        """
        query = select(RoomAmenity).where(
            and_(
                RoomAmenity.amenity_type == amenity_type,
                RoomAmenity.is_deleted == False
            )
        )
        
        if is_functional:
            query = query.where(RoomAmenity.is_functional == True)
        
        if hostel_id:
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_amenities_by_category(
        self,
        category: str,
        room_id: Optional[str] = None
    ) -> List[RoomAmenity]:
        """
        Find amenities by category.
        
        Args:
            category: Amenity category
            room_id: Room ID filter
            
        Returns:
            List of amenities
        """
        filters = {'category': category}
        if room_id:
            filters['room_id'] = room_id
        
        return self.find_by_criteria(filters, order_by='amenity_name')

    def search_amenities(
        self,
        search_term: str,
        hostel_id: Optional[str] = None,
        limit: int = 50
    ) -> List[RoomAmenity]:
        """
        Search amenities by name, brand, or model.
        
        Args:
            search_term: Search term
            hostel_id: Hostel ID filter
            limit: Maximum results
            
        Returns:
            List of matching amenities
        """
        search_pattern = f"%{search_term}%"
        
        query = select(RoomAmenity).where(
            and_(
                or_(
                    RoomAmenity.amenity_name.ilike(search_pattern),
                    RoomAmenity.brand.ilike(search_pattern),
                    RoomAmenity.model_number.ilike(search_pattern)
                ),
                RoomAmenity.is_deleted == False
            )
        )
        
        if hostel_id:
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        query = query.limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ============================================================================
    # AMENITY STATUS AND AVAILABILITY
    # ============================================================================

    def update_amenity_status(
        self,
        amenity_id: str,
        status: str,
        is_functional: Optional[bool] = None,
        reason: Optional[str] = None,
        commit: bool = True
    ) -> Optional[RoomAmenity]:
        """
        Update amenity status.
        
        Args:
            amenity_id: Amenity ID
            status: New status
            is_functional: Functional status
            reason: Reason for status change
            commit: Whether to commit transaction
            
        Returns:
            Updated amenity
        """
        amenity = self.find_by_id(amenity_id)
        if not amenity:
            return None
        
        amenity.current_status = status
        
        if is_functional is not None:
            amenity.is_functional = is_functional
            amenity.is_available = is_functional
        
        if reason:
            amenity.notes = f"{amenity.notes}\n{datetime.utcnow()}: {reason}" if amenity.notes else reason
        
        if commit:
            self.session.commit()
            self.session.refresh(amenity)
        
        return amenity

    def find_defective_amenities(
        self,
        hostel_id: Optional[str] = None,
        amenity_type: Optional[str] = None
    ) -> List[RoomAmenity]:
        """
        Find defective or non-functional amenities.
        
        Args:
            hostel_id: Hostel ID filter
            amenity_type: Amenity type filter
            
        Returns:
            List of defective amenities
        """
        query = select(RoomAmenity).where(
            and_(
                RoomAmenity.is_functional == False,
                RoomAmenity.is_deleted == False
            )
        )
        
        if amenity_type:
            query = query.where(RoomAmenity.amenity_type == amenity_type)
        
        if hostel_id:
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_amenities_under_warranty(
        self,
        hostel_id: Optional[str] = None
    ) -> List[RoomAmenity]:
        """
        Find amenities currently under warranty.
        
        Args:
            hostel_id: Hostel ID filter
            
        Returns:
            List of amenities under warranty
        """
        query = select(RoomAmenity).where(
            and_(
                RoomAmenity.is_under_warranty == True,
                RoomAmenity.warranty_expiry_date >= date.today(),
                RoomAmenity.is_deleted == False
            )
        )
        
        if hostel_id:
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        query = query.order_by(RoomAmenity.warranty_expiry_date)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_expiring_warranties(
        self,
        days_ahead: int = 30,
        hostel_id: Optional[str] = None
    ) -> List[RoomAmenity]:
        """
        Find amenities with warranties expiring soon.
        
        Args:
            days_ahead: Number of days to look ahead
            hostel_id: Hostel ID filter
            
        Returns:
            List of amenities with expiring warranties
        """
        expiry_date = date.today() + timedelta(days=days_ahead)
        
        query = select(RoomAmenity).where(
            and_(
                RoomAmenity.is_under_warranty == True,
                RoomAmenity.warranty_expiry_date.isnot(None),
                RoomAmenity.warranty_expiry_date <= expiry_date,
                RoomAmenity.warranty_expiry_date >= date.today(),
                RoomAmenity.is_deleted == False
            )
        ).order_by(RoomAmenity.warranty_expiry_date)
        
        if hostel_id:
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ============================================================================
    # AMENITY CONDITION MANAGEMENT
    # ============================================================================

    def update_amenity_condition(
        self,
        amenity_id: str,
        condition_data: Dict[str, Any],
        commit: bool = True
    ) -> Optional[AmenityCondition]:
        """
        Update amenity condition.
        
        Args:
            amenity_id: Amenity ID
            condition_data: Condition update data
            commit: Whether to commit transaction
            
        Returns:
            Updated condition
        """
        try:
            condition = self.session.execute(
                select(AmenityCondition).where(
                    AmenityCondition.amenity_id == amenity_id
                )
            ).scalar_one_or_none()
            
            if not condition:
                condition = AmenityCondition(amenity_id=amenity_id, **condition_data)
                self.session.add(condition)
            else:
                for key, value in condition_data.items():
                    if hasattr(condition, key):
                        setattr(condition, key, value)
            
            # Update amenity's functional status if needed
            amenity = self.find_by_id(amenity_id)
            if amenity and 'is_fully_functional' in condition_data:
                amenity.is_functional = condition_data['is_fully_functional']
            
            if commit:
                self.session.commit()
                self.session.refresh(condition)
            
            return condition
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to update condition: {str(e)}")

    def get_amenity_condition(self, amenity_id: str) -> Optional[AmenityCondition]:
        """
        Get amenity condition details.
        
        Args:
            amenity_id: Amenity ID
            
        Returns:
            Amenity condition or None
        """
        return self.session.execute(
            select(AmenityCondition).where(
                AmenityCondition.amenity_id == amenity_id
            )
        ).scalar_one_or_none()

    def find_amenities_requiring_maintenance(
        self,
        hostel_id: Optional[str] = None,
        min_priority: str = 'MEDIUM'
    ) -> List[Dict[str, Any]]:
        """
        Find amenities requiring maintenance.
        
        Args:
            hostel_id: Hostel ID filter
            min_priority: Minimum priority level
            
        Returns:
            List of amenities with condition details
        """
        priority_levels = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'URGENT': 4}
        min_priority_level = priority_levels.get(min_priority, 2)
        
        query = select(RoomAmenity, AmenityCondition).join(
            AmenityCondition,
            RoomAmenity.id == AmenityCondition.amenity_id
        ).where(
            and_(
                AmenityCondition.requires_maintenance == True,
                RoomAmenity.is_deleted == False
            )
        )
        
        if hostel_id:
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        
        amenities_maintenance = []
        for amenity, condition in result:
            condition_priority = priority_levels.get(
                condition.maintenance_priority, 1
            )
            if condition_priority >= min_priority_level:
                amenities_maintenance.append({
                    'amenity': amenity,
                    'condition': condition,
                    'priority': condition.maintenance_priority,
                    'recommended_actions': condition.recommended_actions or []
                })
        
        # Sort by priority
        amenities_maintenance.sort(
            key=lambda x: priority_levels.get(x['priority'], 0),
            reverse=True
        )
        
        return amenities_maintenance

    def find_amenities_requiring_replacement(
        self,
        hostel_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find amenities requiring replacement.
        
        Args:
            hostel_id: Hostel ID filter
            
        Returns:
            List of amenities needing replacement
        """
        query = select(RoomAmenity, AmenityCondition).join(
            AmenityCondition,
            RoomAmenity.id == AmenityCondition.amenity_id
        ).where(
            and_(
                AmenityCondition.requires_replacement == True,
                RoomAmenity.is_deleted == False
            )
        )
        
        if hostel_id:
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        
        replacements = []
        for amenity, condition in result:
            replacements.append({
                'amenity': amenity,
                'condition': condition,
                'replacement_priority': condition.replacement_priority,
                'estimated_cost': float(condition.replacement_cost_estimate or 0)
            })
        
        return replacements

    # ============================================================================
    # MAINTENANCE OPERATIONS
    # ============================================================================

    def schedule_amenity_maintenance(
        self,
        amenity_id: str,
        maintenance_data: Dict[str, Any],
        commit: bool = True
    ) -> AmenityMaintenance:
        """
        Schedule maintenance for amenity.
        
        Args:
            amenity_id: Amenity ID
            maintenance_data: Maintenance data
            commit: Whether to commit transaction
            
        Returns:
            Created maintenance record
        """
        try:
            maintenance = AmenityMaintenance(
                amenity_id=amenity_id,
                maintenance_status='SCHEDULED',
                **maintenance_data
            )
            self.session.add(maintenance)
            
            if commit:
                self.session.commit()
                self.session.refresh(maintenance)
            
            return maintenance
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to schedule maintenance: {str(e)}")

    def complete_amenity_maintenance(
        self,
        maintenance_id: str,
        completion_data: Dict[str, Any],
        commit: bool = True
    ) -> Optional[AmenityMaintenance]:
        """
        Complete amenity maintenance.
        
        Args:
            maintenance_id: Maintenance ID
            completion_data: Completion data
            commit: Whether to commit transaction
            
        Returns:
            Updated maintenance record
        """
        try:
            maintenance = self.session.execute(
                select(AmenityMaintenance).where(
                    AmenityMaintenance.id == maintenance_id
                )
            ).scalar_one_or_none()
            
            if not maintenance:
                return None
            
            maintenance.maintenance_status = 'COMPLETED'
            maintenance.completion_date = datetime.utcnow()
            
            for key, value in completion_data.items():
                if hasattr(maintenance, key):
                    setattr(maintenance, key, value)
            
            # Update amenity condition if maintenance was successful
            if completion_data.get('quality_rating', 0) >= 7:
                condition = self.get_amenity_condition(maintenance.amenity_id)
                if condition:
                    condition.requires_maintenance = False
                    condition.last_inspection_date = date.today()
            
            if commit:
                self.session.commit()
                self.session.refresh(maintenance)
            
            return maintenance
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to complete maintenance: {str(e)}")

    def get_maintenance_history(
        self,
        amenity_id: str,
        limit: int = 50
    ) -> List[AmenityMaintenance]:
        """
        Get maintenance history for amenity.
        
        Args:
            amenity_id: Amenity ID
            limit: Maximum number of records
            
        Returns:
            List of maintenance records
        """
        query = select(AmenityMaintenance).where(
            AmenityMaintenance.amenity_id == amenity_id
        ).order_by(desc(AmenityMaintenance.maintenance_date)).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_scheduled_maintenance(
        self,
        hostel_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[AmenityMaintenance]:
        """
        Get scheduled maintenance activities.
        
        Args:
            hostel_id: Hostel ID filter
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            List of scheduled maintenance
        """
        query = select(AmenityMaintenance).join(
            RoomAmenity,
            AmenityMaintenance.amenity_id == RoomAmenity.id
        ).where(
            AmenityMaintenance.maintenance_status.in_(['SCHEDULED', 'IN_PROGRESS'])
        )
        
        if hostel_id:
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        if start_date:
            query = query.where(AmenityMaintenance.maintenance_date >= start_date)
        
        if end_date:
            query = query.where(AmenityMaintenance.maintenance_date <= end_date)
        
        query = query.order_by(AmenityMaintenance.maintenance_date)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ============================================================================
    # USAGE TRACKING
    # ============================================================================

    def track_amenity_usage(
        self,
        amenity_id: str,
        usage_data: Dict[str, Any],
        commit: bool = True
    ) -> AmenityUsage:
        """
        Track amenity usage.
        
        Args:
            amenity_id: Amenity ID
            usage_data: Usage data
            commit: Whether to commit transaction
            
        Returns:
            Created usage record
        """
        try:
            usage = AmenityUsage(
                amenity_id=amenity_id,
                usage_date=usage_data.get('usage_date', date.today()),
                usage_month=datetime.utcnow().strftime('%Y-%m'),
                **usage_data
            )
            self.session.add(usage)
            
            if commit:
                self.session.commit()
                self.session.refresh(usage)
            
            return usage
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to track usage: {str(e)}")

    def get_usage_statistics(
        self,
        amenity_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get usage statistics for amenity.
        
        Args:
            amenity_id: Amenity ID
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Dictionary with usage statistics
        """
        query = select(
            func.sum(AmenityUsage.usage_count).label('total_usage'),
            func.avg(AmenityUsage.usage_count).label('avg_daily_usage'),
            func.sum(AmenityUsage.usage_duration_minutes).label('total_duration'),
            func.sum(AmenityUsage.performance_issues_reported).label('total_issues'),
            func.sum(AmenityUsage.operational_cost).label('total_cost')
        ).where(AmenityUsage.amenity_id == amenity_id)
        
        if start_date:
            query = query.where(AmenityUsage.usage_date >= start_date)
        if end_date:
            query = query.where(AmenityUsage.usage_date <= end_date)
        
        result = self.session.execute(query).one()
        
        return {
            'total_usage': result.total_usage or 0,
            'avg_daily_usage': round(float(result.avg_daily_usage or 0), 2),
            'total_duration_minutes': result.total_duration or 0,
            'total_issues': result.total_issues or 0,
            'total_cost': float(result.total_cost or 0)
        }

    # ============================================================================
    # FEEDBACK MANAGEMENT
    # ============================================================================

    def submit_amenity_feedback(
        self,
        amenity_id: str,
        student_id: str,
        feedback_data: Dict[str, Any],
        commit: bool = True
    ) -> AmenityFeedback:
        """
        Submit feedback for amenity.
        
        Args:
            amenity_id: Amenity ID
            student_id: Student ID
            feedback_data: Feedback data
            commit: Whether to commit transaction
            
        Returns:
            Created feedback record
        """
        try:
            feedback = AmenityFeedback(
                amenity_id=amenity_id,
                student_id=student_id,
                **feedback_data
            )
            self.session.add(feedback)
            
            # Update amenity if issues reported
            if feedback_data.get('has_issues'):
                amenity = self.find_by_id(amenity_id)
                if amenity:
                    # Mark amenity for inspection
                    condition = self.get_amenity_condition(amenity_id)
                    if condition:
                        condition.requires_maintenance = True
            
            if commit:
                self.session.commit()
                self.session.refresh(feedback)
            
            return feedback
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to submit feedback: {str(e)}")

    def get_amenity_feedback(
        self,
        amenity_id: str,
        min_rating: Optional[int] = None,
        has_issues: Optional[bool] = None,
        limit: int = 50
    ) -> List[AmenityFeedback]:
        """
        Get feedback for amenity.
        
        Args:
            amenity_id: Amenity ID
            min_rating: Minimum rating filter
            has_issues: Issues filter
            limit: Maximum records
            
        Returns:
            List of feedback records
        """
        query = select(AmenityFeedback).where(
            AmenityFeedback.amenity_id == amenity_id
        )
        
        if min_rating is not None:
            query = query.where(AmenityFeedback.overall_rating >= min_rating)
        
        if has_issues is not None:
            query = query.where(AmenityFeedback.has_issues == has_issues)
        
        query = query.order_by(desc(AmenityFeedback.created_at)).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_average_rating(self, amenity_id: str) -> Optional[Decimal]:
        """
        Get average rating for amenity.
        
        Args:
            amenity_id: Amenity ID
            
        Returns:
            Average rating or None
        """
        result = self.session.execute(
            select(func.avg(AmenityFeedback.overall_rating)).where(
                AmenityFeedback.amenity_id == amenity_id
            )
        ).scalar()
        
        return Decimal(str(result)).quantize(Decimal('0.01')) if result else None

    def find_low_rated_amenities(
        self,
        hostel_id: Optional[str] = None,
        max_rating: Decimal = Decimal('3.0'),
        min_feedback_count: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find amenities with low ratings.
        
        Args:
            hostel_id: Hostel ID filter
            max_rating: Maximum average rating
            min_feedback_count: Minimum number of feedbacks required
            
        Returns:
            List of low-rated amenities with statistics
        """
        query = select(
            RoomAmenity.id,
            RoomAmenity.amenity_name,
            RoomAmenity.room_id,
            func.avg(AmenityFeedback.overall_rating).label('avg_rating'),
            func.count(AmenityFeedback.id).label('feedback_count')
        ).join(
            AmenityFeedback,
            RoomAmenity.id == AmenityFeedback.amenity_id
        ).where(
            RoomAmenity.is_deleted == False
        ).group_by(
            RoomAmenity.id,
            RoomAmenity.amenity_name,
            RoomAmenity.room_id
        ).having(
            and_(
                func.avg(AmenityFeedback.overall_rating) <= max_rating,
                func.count(AmenityFeedback.id) >= min_feedback_count
            )
        )
        
        if hostel_id:
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        query = query.order_by(func.avg(AmenityFeedback.overall_rating))
        
        result = self.session.execute(query)
        
        return [
            {
                'amenity_id': row.id,
                'amenity_name': row.amenity_name,
                'room_id': row.room_id,
                'avg_rating': float(row.avg_rating),
                'feedback_count': row.feedback_count
            }
            for row in result
        ]

    # ============================================================================
    # INVENTORY MANAGEMENT
    # ============================================================================

    def update_amenity_inventory(
        self,
        amenity_id: str,
        inventory_data: Dict[str, Any],
        commit: bool = True
    ) -> Optional[AmenityInventory]:
        """
        Update amenity inventory.
        
        Args:
            amenity_id: Amenity ID
            inventory_data: Inventory update data
            commit: Whether to commit transaction
            
        Returns:
            Updated inventory record
        """
        try:
            inventory = self.session.execute(
                select(AmenityInventory).where(
                    AmenityInventory.amenity_id == amenity_id
                )
            ).scalar_one_or_none()
            
            if not inventory:
                inventory = AmenityInventory(
                    amenity_id=amenity_id,
                    **inventory_data
                )
                self.session.add(inventory)
            else:
                for key, value in inventory_data.items():
                    if hasattr(inventory, key):
                        setattr(inventory, key, value)
            
            if commit:
                self.session.commit()
                self.session.refresh(inventory)
            
            return inventory
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to update inventory: {str(e)}")

    def get_amenity_inventory(self, amenity_id: str) -> Optional[AmenityInventory]:
        """
        Get amenity inventory details.
        
        Args:
            amenity_id: Amenity ID
            
        Returns:
            Inventory record or None
        """
        return self.session.execute(
            select(AmenityInventory).where(
                AmenityInventory.amenity_id == amenity_id
            )
        ).scalar_one_or_none()

    def find_amenities_for_verification(
        self,
        hostel_id: Optional[str] = None,
        overdue_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find amenities requiring physical verification.
        
        Args:
            hostel_id: Hostel ID filter
            overdue_only: Only include overdue verifications
            
        Returns:
            List of amenities needing verification
        """
        query = select(RoomAmenity, AmenityInventory).join(
            AmenityInventory,
            RoomAmenity.id == AmenityInventory.amenity_id
        ).where(
            RoomAmenity.is_deleted == False
        )
        
        if overdue_only:
            # Calculate verification due date
            query = query.where(
                or_(
                    AmenityInventory.next_verification_due.is_(None),
                    AmenityInventory.next_verification_due <= date.today()
                )
            )
        
        if hostel_id:
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        
        verifications = []
        for amenity, inventory in result:
            days_overdue = 0
            if inventory.next_verification_due:
                days_overdue = (date.today() - inventory.next_verification_due).days
            
            verifications.append({
                'amenity': amenity,
                'inventory': inventory,
                'days_overdue': max(0, days_overdue),
                'last_verified': inventory.last_physical_verification
            })
        
        return verifications

    # ============================================================================
    # STATISTICS AND ANALYTICS
    # ============================================================================

    def get_amenity_statistics(
        self,
        hostel_id: str,
        amenity_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive amenity statistics.
        
        Args:
            hostel_id: Hostel ID
            amenity_type: Amenity type filter
            
        Returns:
            Dictionary with amenity statistics
        """
        query = select(
            func.count(RoomAmenity.id).label('total_amenities'),
            func.sum(
                case((RoomAmenity.is_functional == True, 1), else_=0)
            ).label('functional'),
            func.sum(
                case((RoomAmenity.is_functional == False, 1), else_=0)
            ).label('defective'),
            func.sum(
                case((RoomAmenity.is_under_warranty == True, 1), else_=0)
            ).label('under_warranty'),
            func.avg(
                case(
                    (AmenityCondition.condition_score.isnot(None), 
                     AmenityCondition.condition_score),
                    else_=0
                )
            ).label('avg_condition_score')
        ).select_from(RoomAmenity).outerjoin(
            AmenityCondition,
            RoomAmenity.id == AmenityCondition.amenity_id
        ).join(Room).where(
            and_(
                Room.hostel_id == hostel_id,
                RoomAmenity.is_deleted == False
            )
        )
        
        if amenity_type:
            query = query.where(RoomAmenity.amenity_type == amenity_type)
        
        result = self.session.execute(query).one()
        
        return {
            'total_amenities': result.total_amenities or 0,
            'functional': result.functional or 0,
            'defective': result.defective or 0,
            'under_warranty': result.under_warranty or 0,
            'avg_condition_score': round(float(result.avg_condition_score or 0), 2)
        }

    def get_amenity_value_summary(
        self,
        hostel_id: str
    ) -> Dict[str, Any]:
        """
        Get total value of amenities.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Dictionary with value statistics
        """
        query = select(
            func.sum(AmenityInventory.current_value).label('total_value'),
            func.sum(AmenityInventory.accumulated_depreciation).label('total_depreciation'),
            func.count(AmenityInventory.id).label('tracked_items')
        ).join(
            RoomAmenity,
            AmenityInventory.amenity_id == RoomAmenity.id
        ).join(Room).where(
            and_(
                Room.hostel_id == hostel_id,
                RoomAmenity.is_deleted == False
            )
        )
        
        result = self.session.execute(query).one()
        
        total_value = result.total_value or Decimal('0.00')
        total_depreciation = result.total_depreciation or Decimal('0.00')
        net_value = total_value - total_depreciation
        
        return {
            'total_value': float(total_value),
            'total_depreciation': float(total_depreciation),
            'net_value': float(net_value),
            'tracked_items': result.tracked_items or 0
        }

    def get_maintenance_cost_summary(
        self,
        hostel_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get maintenance cost summary.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Dictionary with cost summary
        """
        query = select(
            func.count(AmenityMaintenance.id).label('total_activities'),
            func.sum(AmenityMaintenance.total_cost).label('total_cost'),
            func.avg(AmenityMaintenance.total_cost).label('avg_cost'),
            func.sum(AmenityMaintenance.labor_cost).label('labor_cost'),
            func.sum(AmenityMaintenance.parts_cost).label('parts_cost')
        ).join(
            RoomAmenity,
            AmenityMaintenance.amenity_id == RoomAmenity.id
        ).join(Room).where(
            Room.hostel_id == hostel_id
        )
        
        if start_date:
            query = query.where(AmenityMaintenance.maintenance_date >= start_date)
        if end_date:
            query = query.where(AmenityMaintenance.maintenance_date <= end_date)
        
        result = self.session.execute(query).one()
        
        return {
            'total_activities': result.total_activities or 0,
            'total_cost': float(result.total_cost or 0),
            'avg_cost': float(result.avg_cost or 0),
            'labor_cost': float(result.labor_cost or 0),
            'parts_cost': float(result.parts_cost or 0)
        }