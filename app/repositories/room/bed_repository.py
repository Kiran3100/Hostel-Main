# app/repositories/room/bed_repository.py
"""
Bed repository with comprehensive bed management operations.
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, case
from sqlalchemy.orm import Session, joinedload

from app.models.room import (
    Bed,
    BedCondition,
    BedConfiguration,
    BedAccessibility,
    BedPreference,
    BedUtilization,
)
from app.models.base.enums import BedStatus
from .base_repository import BaseRepository


class BedRepository(BaseRepository[Bed]):
    """
    Repository for Bed entity and related models.
    
    Handles:
    - Bed CRUD operations
    - Bed conditions
    - Bed configurations
    - Accessibility features
    - Bed preferences
    - Utilization tracking
    """

    def __init__(self, session: Session):
        super().__init__(Bed, session)

    # ============================================================================
    # BED BASIC OPERATIONS
    # ============================================================================

    def create_bed_with_details(
        self,
        bed_data: Dict[str, Any],
        condition_data: Optional[Dict[str, Any]] = None,
        configuration_data: Optional[Dict[str, Any]] = None,
        accessibility_data: Optional[Dict[str, Any]] = None,
        commit: bool = True
    ) -> Bed:
        """
        Create bed with all related details.
        
        Args:
            bed_data: Bed data
            condition_data: Bed condition data
            configuration_data: Bed configuration data
            accessibility_data: Accessibility features data
            commit: Whether to commit transaction
            
        Returns:
            Created bed with related data
        """
        try:
            # Create bed
            bed = self.create(bed_data, commit=False)
            
            # Create condition record
            if condition_data:
                condition = BedCondition(
                    bed_id=bed.id,
                    **condition_data
                )
            else:
                # Create default condition
                condition = BedCondition(
                    bed_id=bed.id,
                    condition_score=10,
                    condition_grade='A',
                    wear_level='MINIMAL',
                    is_fully_functional=True,
                    cleanliness_rating=10
                )
            self.session.add(condition)
            
            # Create configuration record
            if configuration_data:
                config = BedConfiguration(
                    bed_id=bed.id,
                    **configuration_data
                )
            else:
                # Create default configuration
                config = BedConfiguration(
                    bed_id=bed.id,
                    configuration_type='STANDARD',
                    frame_type='PLATFORM',
                    mattress_type='FOAM',
                    mattress_firmness='MEDIUM',
                    pillow_count=1,
                    has_ceiling_fan=True,
                    configuration_date=date.today()
                )
            self.session.add(config)
            
            # Create accessibility record if provided
            if accessibility_data:
                accessibility = BedAccessibility(
                    bed_id=bed.id,
                    **accessibility_data
                )
                self.session.add(accessibility)
            
            # Create utilization tracking
            utilization = BedUtilization(
                bed_id=bed.id,
                current_month=datetime.utcnow().strftime('%Y-%m'),
                current_year=datetime.utcnow().year,
                last_calculated=datetime.utcnow(),
                next_calculation_due=datetime.utcnow()
            )
            self.session.add(utilization)
            
            if commit:
                self.session.commit()
                self.session.refresh(bed)
            
            return bed
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create bed with details: {str(e)}")

    def find_beds_by_room(
        self,
        room_id: str,
        include_deleted: bool = False
    ) -> List[Bed]:
        """
        Find all beds in a room.
        
        Args:
            room_id: Room ID
            include_deleted: Whether to include soft-deleted beds
            
        Returns:
            List of beds
        """
        return self.find_by_criteria(
            {'room_id': room_id},
            include_deleted=include_deleted,
            order_by='bed_number'
        )

    def find_by_bed_number(
        self,
        room_id: str,
        bed_number: str
    ) -> Optional[Bed]:
        """
        Find bed by room and bed number.
        
        Args:
            room_id: Room ID
            bed_number: Bed number
            
        Returns:
            Bed or None if not found
        """
        beds = self.find_by_criteria({
            'room_id': room_id,
            'bed_number': bed_number
        })
        return beds[0] if beds else None

    def find_by_bed_code(self, bed_code: str) -> Optional[Bed]:
        """
        Find bed by unique bed code.
        
        Args:
            bed_code: Bed code
            
        Returns:
            Bed or None if not found
        """
        beds = self.find_by_criteria({'bed_code': bed_code})
        return beds[0] if beds else None

    # ============================================================================
    # BED AVAILABILITY AND STATUS
    # ============================================================================

    def find_available_beds(
        self,
        room_id: Optional[str] = None,
        hostel_id: Optional[str] = None,
        bed_type: Optional[str] = None,
        is_upper_bunk: Optional[bool] = None,
        is_lower_bunk: Optional[bool] = None
    ) -> List[Bed]:
        """
        Find available beds with filters.
        
        Args:
            room_id: Room ID filter
            hostel_id: Hostel ID filter (requires join with Room)
            bed_type: Bed type filter
            is_upper_bunk: Upper bunk filter
            is_lower_bunk: Lower bunk filter
            
        Returns:
            List of available beds
        """
        query = select(Bed).where(
            and_(
                Bed.is_available == True,
                Bed.is_occupied == False,
                Bed.is_functional == True,
                Bed.status == BedStatus.AVAILABLE,
                Bed.is_deleted == False
            )
        )
        
        if room_id:
            query = query.where(Bed.room_id == room_id)
        
        if bed_type:
            query = query.where(Bed.bed_type == bed_type)
        
        if is_upper_bunk is not None:
            query = query.where(Bed.is_upper_bunk == is_upper_bunk)
        
        if is_lower_bunk is not None:
            query = query.where(Bed.is_lower_bunk == is_lower_bunk)
        
        if hostel_id:
            from app.models.room import Room
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        query = query.order_by(Bed.bed_number)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_occupied_beds(
        self,
        room_id: Optional[str] = None,
        include_student_info: bool = False
    ) -> List[Bed]:
        """
        Find occupied beds.
        
        Args:
            room_id: Room ID filter
            include_student_info: Whether to load student relationship
            
        Returns:
            List of occupied beds
        """
        query = select(Bed).where(
            and_(
                Bed.is_occupied == True,
                Bed.is_deleted == False
            )
        )
        
        if room_id:
            query = query.where(Bed.room_id == room_id)
        
        if include_student_info:
            query = query.options(joinedload(Bed.current_student))
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_beds_by_status(
        self,
        status: BedStatus,
        room_id: Optional[str] = None
    ) -> List[Bed]:
        """
        Find beds by status.
        
        Args:
            status: Bed status
            room_id: Room ID filter
            
        Returns:
            List of beds with specified status
        """
        filters = {'status': status}
        if room_id:
            filters['room_id'] = room_id
        
        return self.find_by_criteria(filters)

    def update_bed_status(
        self,
        bed_id: str,
        status: BedStatus,
        reason: Optional[str] = None,
        commit: bool = True
    ) -> Optional[Bed]:
        """
        Update bed status.
        
        Args:
            bed_id: Bed ID
            status: New status
            reason: Reason for status change
            commit: Whether to commit transaction
            
        Returns:
            Updated bed
        """
        bed = self.find_by_id(bed_id)
        if not bed:
            return None
        
        bed.status = status
        bed.last_status_change = datetime.utcnow()
        
        # Update availability flags based on status
        if status == BedStatus.AVAILABLE:
            bed.is_available = True
            bed.is_occupied = False
        elif status == BedStatus.OCCUPIED:
            bed.is_available = False
            bed.is_occupied = True
        elif status in [BedStatus.MAINTENANCE, BedStatus.BLOCKED]:
            bed.is_available = False
            bed.is_occupied = False
        
        if reason:
            bed.notes = f"{bed.notes}\n{datetime.utcnow()}: {reason}" if bed.notes else reason
        
        if commit:
            self.session.commit()
            self.session.refresh(bed)
        
        return bed

    # ============================================================================
    # BED ASSIGNMENT OPERATIONS
    # ============================================================================

    def assign_bed_to_student(
        self,
        bed_id: str,
        student_id: str,
        occupied_from: date,
        expected_vacate_date: Optional[date] = None,
        commit: bool = True
    ) -> Optional[Bed]:
        """
        Assign bed to student.
        
        Args:
            bed_id: Bed ID
            student_id: Student ID
            occupied_from: Occupation start date
            expected_vacate_date: Expected vacate date
            commit: Whether to commit transaction
            
        Returns:
            Updated bed
        """
        try:
            bed = self.find_by_id(bed_id)
            if not bed:
                return None
            
            if bed.is_occupied:
                raise ValueError(f"Bed {bed_id} is already occupied")
            
            if not bed.is_available or not bed.is_functional:
                raise ValueError(f"Bed {bed_id} is not available for assignment")
            
            # Update bed
            bed.current_student_id = student_id
            bed.occupied_from = occupied_from
            bed.expected_vacate_date = expected_vacate_date
            bed.is_occupied = True
            bed.is_available = False
            bed.status = BedStatus.OCCUPIED
            bed.last_assignment_date = date.today()
            bed.total_assignments += 1
            bed.last_status_change = datetime.utcnow()
            
            if commit:
                self.session.commit()
                self.session.refresh(bed)
            
            return bed
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to assign bed: {str(e)}")

    def release_bed(
        self,
        bed_id: str,
        actual_vacate_date: Optional[date] = None,
        commit: bool = True
    ) -> Optional[Bed]:
        """
        Release bed from current student.
        
        Args:
            bed_id: Bed ID
            actual_vacate_date: Actual vacate date
            commit: Whether to commit transaction
            
        Returns:
            Updated bed
        """
        try:
            bed = self.find_by_id(bed_id)
            if not bed:
                return None
            
            if not bed.is_occupied:
                raise ValueError(f"Bed {bed_id} is not currently occupied")
            
            # Calculate occupancy days
            if bed.occupied_from:
                vacate_date = actual_vacate_date or date.today()
                days_occupied = (vacate_date - bed.occupied_from).days
                bed.total_occupancy_days += days_occupied
            
            # Update bed
            bed.current_student_id = None
            bed.occupied_from = None
            bed.expected_vacate_date = None
            bed.is_occupied = False
            bed.is_available = True
            bed.status = BedStatus.AVAILABLE
            bed.last_release_date = date.today()
            bed.last_status_change = datetime.utcnow()
            
            if commit:
                self.session.commit()
                self.session.refresh(bed)
            
            return bed
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to release bed: {str(e)}")

    # ============================================================================
    # BED CONDITION MANAGEMENT
    # ============================================================================

    def update_bed_condition(
        self,
        bed_id: str,
        condition_data: Dict[str, Any],
        commit: bool = True
    ) -> Optional[BedCondition]:
        """
        Update bed condition.
        
        Args:
            bed_id: Bed ID
            condition_data: Condition update data
            commit: Whether to commit transaction
            
        Returns:
            Updated bed condition
        """
        try:
            condition = self.session.execute(
                select(BedCondition).where(BedCondition.bed_id == bed_id)
            ).scalar_one_or_none()
            
            if not condition:
                # Create new condition record if doesn't exist
                condition = BedCondition(bed_id=bed_id, **condition_data)
                self.session.add(condition)
            else:
                # Update existing condition
                for key, value in condition_data.items():
                    if hasattr(condition, key):
                        setattr(condition, key, value)
            
            # Update bed's condition rating
            bed = self.find_by_id(bed_id)
            if bed and 'condition_score' in condition_data:
                bed.condition_rating = condition_data['condition_score']
            
            if commit:
                self.session.commit()
                self.session.refresh(condition)
            
            return condition
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to update bed condition: {str(e)}")

    def get_bed_condition(self, bed_id: str) -> Optional[BedCondition]:
        """
        Get bed condition details.
        
        Args:
            bed_id: Bed ID
            
        Returns:
            Bed condition or None
        """
        return self.session.execute(
            select(BedCondition).where(BedCondition.bed_id == bed_id)
        ).scalar_one_or_none()

    def find_beds_requiring_maintenance(
        self,
        hostel_id: Optional[str] = None,
        min_priority: str = 'MEDIUM'
    ) -> List[Dict[str, Any]]:
        """
        Find beds requiring maintenance.
        
        Args:
            hostel_id: Hostel ID filter
            min_priority: Minimum priority level
            
        Returns:
            List of beds with condition details
        """
        from app.models.room import Room
        
        priority_levels = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'URGENT': 4}
        min_priority_level = priority_levels.get(min_priority, 2)
        
        query = select(Bed, BedCondition).join(
            BedCondition, Bed.id == BedCondition.bed_id
        ).where(
            and_(
                BedCondition.requires_maintenance == True,
                Bed.is_deleted == False
            )
        )
        
        if hostel_id:
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        
        beds_maintenance = []
        for bed, condition in result:
            condition_priority = priority_levels.get(
                condition.maintenance_priority, 1
            )
            if condition_priority >= min_priority_level:
                beds_maintenance.append({
                    'bed': bed,
                    'condition': condition,
                    'priority': condition.maintenance_priority,
                    'issues': condition.functional_issues or []
                })
        
        return beds_maintenance

    # ============================================================================
    # BED CONFIGURATION
    # ============================================================================

    def update_bed_configuration(
        self,
        bed_id: str,
        configuration_data: Dict[str, Any],
        commit: bool = True
    ) -> Optional[BedConfiguration]:
        """
        Update bed configuration.
        
        Args:
            bed_id: Bed ID
            configuration_data: Configuration update data
            commit: Whether to commit transaction
            
        Returns:
            Updated bed configuration
        """
        try:
            config = self.session.execute(
                select(BedConfiguration).where(
                    BedConfiguration.bed_id == bed_id
                )
            ).scalar_one_or_none()
            
            if not config:
                config = BedConfiguration(bed_id=bed_id, **configuration_data)
                self.session.add(config)
            else:
                for key, value in configuration_data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                config.last_modified_date = date.today()
            
            if commit:
                self.session.commit()
                self.session.refresh(config)
            
            return config
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to update bed configuration: {str(e)}")

    def get_bed_configuration(self, bed_id: str) -> Optional[BedConfiguration]:
        """
        Get bed configuration details.
        
        Args:
            bed_id: Bed ID
            
        Returns:
            Bed configuration or None
        """
        return self.session.execute(
            select(BedConfiguration).where(
                BedConfiguration.bed_id == bed_id
            )
        ).scalar_one_or_none()

    # ============================================================================
    # BED ACCESSIBILITY
    # ============================================================================

    def find_accessible_beds(
        self,
        room_id: Optional[str] = None,
        accessibility_level: Optional[str] = None,
        wheelchair_accessible: bool = False
    ) -> List[Bed]:
        """
        Find beds with accessibility features.
        
        Args:
            room_id: Room ID filter
            accessibility_level: Accessibility level filter
            wheelchair_accessible: Wheelchair accessible filter
            
        Returns:
            List of accessible beds
        """
        query = select(Bed).join(
            BedAccessibility, Bed.id == BedAccessibility.bed_id
        ).where(Bed.is_deleted == False)
        
        if room_id:
            query = query.where(Bed.room_id == room_id)
        
        if accessibility_level:
            query = query.where(
                BedAccessibility.accessibility_level == accessibility_level
            )
        
        if wheelchair_accessible:
            query = query.where(
                BedAccessibility.is_wheelchair_accessible == True
            )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def update_bed_accessibility(
        self,
        bed_id: str,
        accessibility_data: Dict[str, Any],
        commit: bool = True
    ) -> Optional[BedAccessibility]:
        """
        Update bed accessibility features.
        
        Args:
            bed_id: Bed ID
            accessibility_data: Accessibility update data
            commit: Whether to commit transaction
            
        Returns:
            Updated bed accessibility
        """
        try:
            accessibility = self.session.execute(
                select(BedAccessibility).where(
                    BedAccessibility.bed_id == bed_id
                )
            ).scalar_one_or_none()
            
            if not accessibility:
                accessibility = BedAccessibility(
                    bed_id=bed_id,
                    **accessibility_data
                )
                self.session.add(accessibility)
            else:
                for key, value in accessibility_data.items():
                    if hasattr(accessibility, key):
                        setattr(accessibility, key, value)
            
            if commit:
                self.session.commit()
                self.session.refresh(accessibility)
            
            return accessibility
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to update bed accessibility: {str(e)}")

    # ============================================================================
    # BED PREFERENCES
    # ============================================================================

    def create_bed_preference(
        self,
        bed_id: str,
        student_id: str,
        preference_data: Dict[str, Any],
        commit: bool = True
    ) -> BedPreference:
        """
        Create bed preference for a student.
        
        Args:
            bed_id: Bed ID
            student_id: Student ID
            preference_data: Preference data
            commit: Whether to commit transaction
            
        Returns:
            Created bed preference
        """
        try:
            preference = BedPreference(
                bed_id=bed_id,
                student_id=student_id,
                preference_date=date.today(),
                **preference_data
            )
            self.session.add(preference)
            
            if commit:
                self.session.commit()
                self.session.refresh(preference)
            
            return preference
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create bed preference: {str(e)}")

    def find_student_bed_preferences(
        self,
        student_id: str,
        status: Optional[str] = 'ACTIVE'
    ) -> List[BedPreference]:
        """
        Find bed preferences for a student.
        
        Args:
            student_id: Student ID
            status: Preference status filter
            
        Returns:
            List of bed preferences
        """
        query = select(BedPreference).where(
            BedPreference.student_id == student_id
        )
        
        if status:
            query = query.where(BedPreference.preference_status == status)
        
        query = query.order_by(BedPreference.preference_priority)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def match_bed_preferences(
        self,
        student_id: str,
        available_beds: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Match student preferences with available beds.
        
        Args:
            student_id: Student ID
            available_beds: List of available bed IDs
            
        Returns:
            List of matched beds with compatibility scores
        """
        preferences = self.find_student_bed_preferences(student_id, 'ACTIVE')
        
        matches = []
        for pref in preferences:
            if pref.bed_id in available_beds:
                matches.append({
                    'bed_id': pref.bed_id,
                    'preference_id': pref.id,
                    'priority': pref.preference_priority,
                    'compatibility_score': pref.compatibility_score,
                    'is_primary': pref.is_primary_preference
                })
        
        # Sort by priority and compatibility score
        matches.sort(
            key=lambda x: (x['priority'], -(x['compatibility_score'] or 0))
        )
        
        return matches

    # ============================================================================
    # BED UTILIZATION
    # ============================================================================

    def update_bed_utilization(
        self,
        bed_id: str,
        utilization_data: Dict[str, Any],
        commit: bool = True
    ) -> Optional[BedUtilization]:
        """
        Update bed utilization metrics.
        
        Args:
            bed_id: Bed ID
            utilization_data: Utilization update data
            commit: Whether to commit transaction
            
        Returns:
            Updated bed utilization
        """
        try:
            utilization = self.session.execute(
                select(BedUtilization).where(
                    BedUtilization.bed_id == bed_id
                )
            ).scalar_one_or_none()
            
            if not utilization:
                utilization = BedUtilization(
                    bed_id=bed_id,
                    current_month=datetime.utcnow().strftime('%Y-%m'),
                    current_year=datetime.utcnow().year,
                    **utilization_data
                )
                self.session.add(utilization)
            else:
                for key, value in utilization_data.items():
                    if hasattr(utilization, key):
                        setattr(utilization, key, value)
            
            utilization.last_calculated = datetime.utcnow()
            
            if commit:
                self.session.commit()
                self.session.refresh(utilization)
            
            return utilization
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to update bed utilization: {str(e)}")

    def get_bed_utilization_stats(
        self,
        bed_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive bed utilization statistics.
        
        Args:
            bed_id: Bed ID
            
        Returns:
            Dictionary with utilization statistics
        """
        utilization = self.session.execute(
            select(BedUtilization).where(BedUtilization.bed_id == bed_id)
        ).scalar_one_or_none()
        
        if not utilization:
            return None
        
        return {
            'bed_id': bed_id,
            'occupancy_rate_month': float(utilization.occupancy_rate_current_month),
            'occupancy_rate_year': float(utilization.occupancy_rate_current_year),
            'occupancy_rate_lifetime': float(utilization.occupancy_rate_lifetime),
            'revenue_month': float(utilization.revenue_current_month),
            'revenue_year': float(utilization.revenue_current_year),
            'revenue_lifetime': float(utilization.revenue_lifetime),
            'total_assignments': utilization.total_assignments,
            'avg_assignment_duration': float(utilization.average_assignment_duration_days or 0),
            'performance_score': float(utilization.performance_score or 0),
            'roi_percentage': float(utilization.roi_percentage),
            'is_top_performer': utilization.is_top_performer,
            'is_underperformer': utilization.is_underperformer
        }

    def find_top_performing_beds(
        self,
        hostel_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find top performing beds by utilization.
        
        Args:
            hostel_id: Hostel ID filter
            limit: Maximum number of results
            
        Returns:
            List of top performing beds with stats
        """
        from app.models.room import Room
        
        query = select(Bed, BedUtilization).join(
            BedUtilization, Bed.id == BedUtilization.bed_id
        ).where(
            and_(
                Bed.is_deleted == False,
                BedUtilization.is_top_performer == True
            )
        )
        
        if hostel_id:
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        query = query.order_by(
            BedUtilization.performance_score.desc()
        ).limit(limit)
        
        result = self.session.execute(query)
        
        top_beds = []
        for bed, util in result:
            top_beds.append({
                'bed': bed,
                'performance_score': float(util.performance_score or 0),
                'occupancy_rate': float(util.occupancy_rate_current_year),
                'revenue_year': float(util.revenue_current_year),
                'roi_percentage': float(util.roi_percentage)
            })
        
        return top_beds

    # ============================================================================
    # BED STATISTICS AND ANALYTICS
    # ============================================================================

    def get_room_bed_statistics(self, room_id: str) -> Dict[str, Any]:
        """
        Get comprehensive bed statistics for a room.
        
        Args:
            room_id: Room ID
            
        Returns:
            Dictionary with bed statistics
        """
        query = select(
            func.count(Bed.id).label('total_beds'),
            func.sum(case((Bed.is_occupied == True, 1), else_=0)).label('occupied_beds'),
            func.sum(case((Bed.is_available == True, 1), else_=0)).label('available_beds'),
            func.sum(case((Bed.status == BedStatus.MAINTENANCE, 1), else_=0)).label('maintenance_beds'),
            func.sum(case((Bed.is_upper_bunk == True, 1), else_=0)).label('upper_bunks'),
            func.sum(case((Bed.is_lower_bunk == True, 1), else_=0)).label('lower_bunks'),
            func.avg(Bed.condition_rating).label('avg_condition'),
            func.sum(Bed.total_assignments).label('total_assignments'),
            func.sum(Bed.total_occupancy_days).label('total_occupancy_days')
        ).where(
            and_(
                Bed.room_id == room_id,
                Bed.is_deleted == False
            )
        )
        
        result = self.session.execute(query).one()
        
        total_beds = result.total_beds or 0
        occupied_beds = result.occupied_beds or 0
        occupancy_rate = (occupied_beds / total_beds * 100) if total_beds > 0 else 0
        
        return {
            'total_beds': total_beds,
            'occupied_beds': occupied_beds,
            'available_beds': result.available_beds or 0,
            'occupancy_rate': round(occupancy_rate, 2),
            'maintenance_beds': result.maintenance_beds or 0,
            'upper_bunks': result.upper_bunks or 0,
            'lower_bunks': result.lower_bunks or 0,
            'avg_condition_rating': round(float(result.avg_condition or 0), 2),
            'total_assignments': result.total_assignments or 0,
            'total_occupancy_days': result.total_occupancy_days or 0
        }

    def get_bed_type_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Get bed type distribution.
        
        Args:
            hostel_id: Hostel ID filter
            
        Returns:
            Dictionary with bed type counts
        """
        from app.models.room import Room
        
        query = select(
            Bed.bed_type,
            func.count(Bed.id).label('count')
        ).where(Bed.is_deleted == False)
        
        if hostel_id:
            query = query.join(Room).where(Room.hostel_id == hostel_id)
        
        query = query.group_by(Bed.bed_type)
        
        result = self.session.execute(query)
        
        return {row.bed_type: row.count for row in result}

    def calculate_bed_occupancy_trends(
        self,
        bed_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Calculate bed occupancy trends.
        
        Args:
            bed_id: Bed ID
            days: Number of days to analyze
            
        Returns:
            List of daily occupancy data
        """
        # This would typically query assignment history
        # For now, return utilization summary
        utilization = self.get_bed_utilization_stats(bed_id)
        
        if not utilization:
            return []
        
        return [{
            'period': 'current_month',
            'occupancy_rate': utilization['occupancy_rate_month'],
            'revenue': utilization['revenue_month']
        }]