"""
Announcement Targeting Repository

Advanced audience targeting with segmentation, personalization, and delivery optimization.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Set, Tuple
from uuid import UUID
from collections import defaultdict

from sqlalchemy import and_, or_, func, select, exists
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.dialects.postgresql import array

from app.models.announcement import (
    AnnouncementTarget,
    TargetingRule,
    TargetAudienceCache,
    BulkTargetingRule,
    Announcement,
)
from app.models.base.enums import TargetAudience, RoomType
from app.models.user.user import User
from app.models.room.room import Room
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.core1.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    BusinessLogicError,
)


class AnnouncementTargetingRepository(BaseRepository[AnnouncementTarget]):
    """
    Repository for announcement audience targeting.
    
    Provides sophisticated targeting capabilities including:
    - Dynamic audience segmentation
    - Target reach calculation
    - Delivery timing optimization
    - Content personalization
    - Targeting effectiveness tracking
    - Audience preference management
    - Over-messaging prevention
    """
    
    def __init__(self, session: Session):
        super().__init__(AnnouncementTarget, session)
    
    # ==================== Audience Segmentation ====================
    
    def build_audience_segment(
        self,
        announcement_id: UUID,
        target_type: TargetAudience,
        created_by_id: UUID,
        **targeting_params
    ) -> AnnouncementTarget:
        """
        Build audience segment for announcement.
        
        Args:
            announcement_id: Announcement UUID
            target_type: Target audience type
            created_by_id: User creating target
            **targeting_params: Additional targeting parameters
            
        Returns:
            Created targeting configuration
        """
        target = AnnouncementTarget(
            announcement_id=announcement_id,
            created_by_id=created_by_id,
            target_type=target_type,
            **targeting_params
        )
        
        self.session.add(target)
        self.session.flush()
        
        # Calculate recipients
        student_ids = self._calculate_target_audience(target)
        target.estimated_recipients = len(student_ids)
        
        # Validate targeting
        self._validate_targeting(target)
        
        self.session.flush()
        return target
    
    def build_multi_criteria_segment(
        self,
        announcement_id: UUID,
        created_by_id: UUID,
        criteria: List[Dict[str, Any]]
    ) -> AnnouncementTarget:
        """
        Build segment with multiple targeting criteria.
        
        Args:
            announcement_id: Announcement UUID
            created_by_id: User creating target
            criteria: List of targeting criteria
            
        Returns:
            Created targeting configuration with rules
        """
        target = AnnouncementTarget(
            announcement_id=announcement_id,
            created_by_id=created_by_id,
            target_type=TargetAudience.CUSTOM,
        )
        
        self.session.add(target)
        self.session.flush()
        
        # Create targeting rules
        for priority, criterion in enumerate(criteria):
            rule = TargetingRule(
                target_id=target.id,
                rule_type=criterion['type'],
                rule_field=criterion['field'],
                rule_operator=criterion['operator'],
                rule_value=criterion['value'],
                priority=priority,
                is_inclusion=criterion.get('is_inclusion', True),
                description=criterion.get('description'),
            )
            self.session.add(rule)
        
        self.session.flush()
        
        # Calculate recipients
        student_ids = self._calculate_target_audience(target)
        target.estimated_recipients = len(student_ids)
        target.is_validated = True
        target.validated_at = datetime.utcnow()
        
        self.session.flush()
        return target
    
    def calculate_target_reach(
        self,
        announcement_id: UUID,
        update_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Calculate and analyze target audience reach.
        
        Args:
            announcement_id: Announcement UUID
            update_cache: Whether to update audience cache
            
        Returns:
            Reach analysis dictionary
        """
        target = self._get_target_by_announcement(announcement_id)
        if not target:
            raise ResourceNotFoundError(
                f"No targeting found for announcement {announcement_id}"
            )
        
        # Calculate audience
        student_ids = self._calculate_target_audience(target)
        
        # Get detailed breakdown
        breakdown = self._get_audience_breakdown(student_ids)
        
        # Update target
        target.actual_recipients = len(student_ids)
        
        # Cache results if requested
        if update_cache:
            self._update_audience_cache(target, student_ids, breakdown)
        
        self.session.flush()
        
        return {
            'announcement_id': str(announcement_id),
            'target_type': target.target_type.value,
            'estimated_recipients': target.estimated_recipients,
            'actual_recipients': len(student_ids),
            'student_ids': [str(sid) for sid in student_ids],
            'breakdown_by_room': breakdown['by_room'],
            'breakdown_by_floor': breakdown['by_floor'],
            'breakdown_by_status': breakdown['by_status'],
        }
    
    def optimize_delivery_timing(
        self,
        announcement_id: UUID,
        student_ids: Optional[List[UUID]] = None
    ) -> Dict[str, Any]:
        """
        Calculate optimal delivery time for target audience.
        
        Args:
            announcement_id: Announcement UUID
            student_ids: Optional specific student list
            
        Returns:
            Optimal timing recommendations
        """
        if not student_ids:
            target = self._get_target_by_announcement(announcement_id)
            student_ids = self._calculate_target_audience(target)
        
        # Analyze historical engagement patterns
        from app.models.announcement import AnnouncementView
        
        # Get hour-of-day engagement distribution
        hourly_engagement = (
            self.session.query(
                func.extract('hour', AnnouncementView.viewed_at).label('hour'),
                func.count(AnnouncementView.id).label('views')
            )
            .filter(AnnouncementView.student_id.in_(student_ids))
            .group_by('hour')
            .all()
        )
        
        # Get day-of-week engagement
        daily_engagement = (
            self.session.query(
                func.extract('dow', AnnouncementView.viewed_at).label('day'),
                func.count(AnnouncementView.id).label('views')
            )
            .filter(AnnouncementView.student_id.in_(student_ids))
            .group_by('day')
            .all()
        )
        
        # Find peak engagement times
        peak_hour = max(hourly_engagement, key=lambda x: x.views) if hourly_engagement else None
        peak_day = max(daily_engagement, key=lambda x: x.views) if daily_engagement else None
        
        return {
            'optimal_hour': int(peak_hour.hour) if peak_hour else 9,  # Default to 9 AM
            'optimal_day': int(peak_day.day) if peak_day else 1,  # Default to Monday
            'hourly_distribution': {
                int(h.hour): h.views for h in hourly_engagement
            },
            'daily_distribution': {
                int(d.day): d.views for d in daily_engagement
            },
            'total_students_analyzed': len(student_ids),
        }
    
    def personalize_content(
        self,
        announcement_id: UUID,
        student_id: UUID
    ) -> Dict[str, Any]:
        """
        Generate personalized content based on recipient profile.
        
        Args:
            announcement_id: Announcement UUID
            student_id: Student UUID
            
        Returns:
            Personalization data
        """
        # Get student profile
        student = self.session.get(User, student_id)
        if not student:
            raise ResourceNotFoundError(f"Student {student_id} not found")
        
        # Get announcement
        announcement = self.session.get(Announcement, announcement_id)
        if not announcement:
            raise ResourceNotFoundError(
                f"Announcement {announcement_id} not found"
            )
        
        # Build personalization context
        personalization = {
            'student_name': student.full_name,
            'student_first_name': student.first_name,
            'room_number': student.room.room_number if student.room else None,
            'floor_number': student.room.floor_number if student.room else None,
            'preferred_language': student.preferred_language or 'en',
            'notification_preferences': self._get_notification_preferences(student_id),
            'past_engagement': self._get_engagement_history(student_id),
        }
        
        return personalization
    
    def track_targeting_effectiveness(
        self,
        announcement_id: UUID
    ) -> Dict[str, Any]:
        """
        Track and analyze targeting strategy effectiveness.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            Effectiveness metrics
        """
        target = self._get_target_by_announcement(announcement_id)
        if not target:
            raise ResourceNotFoundError(
                f"No targeting found for announcement {announcement_id}"
            )
        
        announcement = self.session.get(Announcement, announcement_id)
        
        # Calculate effectiveness metrics
        from app.models.announcement import ReadReceipt, Acknowledgment
        
        actual_reads = (
            self.session.query(func.count(ReadReceipt.id))
            .filter(ReadReceipt.announcement_id == announcement_id)
            .scalar()
        ) or 0
        
        actual_acknowledgments = 0
        if announcement.requires_acknowledgment:
            actual_acknowledgments = (
                self.session.query(func.count(Acknowledgment.id))
                .filter(Acknowledgment.announcement_id == announcement_id)
                .scalar()
            ) or 0
        
        # Calculate rates
        total_recipients = target.actual_recipients or target.estimated_recipients
        read_rate = (actual_reads / total_recipients * 100) if total_recipients > 0 else 0
        ack_rate = (actual_acknowledgments / total_recipients * 100) if total_recipients > 0 else 0
        
        return {
            'target_type': target.target_type.value,
            'estimated_recipients': target.estimated_recipients,
            'actual_recipients': target.actual_recipients,
            'accuracy': self._calculate_estimation_accuracy(target),
            'read_rate': round(read_rate, 2),
            'acknowledgment_rate': round(ack_rate, 2),
            'effectiveness_score': self._calculate_effectiveness_score(
                read_rate, ack_rate, announcement.requires_acknowledgment
            ),
        }
    
    def manage_audience_preferences(
        self,
        student_id: UUID,
        preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Manage student notification and targeting preferences.
        
        Args:
            student_id: Student UUID
            preferences: Preference settings
            
        Returns:
            Updated preferences
        """
        student = self.session.get(User, student_id)
        if not student:
            raise ResourceNotFoundError(f"Student {student_id} not found")
        
        # Update preferences in student metadata
        if not student.metadata:
            student.metadata = {}
        
        student.metadata['notification_preferences'] = preferences
        student.metadata['preferences_updated_at'] = datetime.utcnow().isoformat()
        
        self.session.flush()
        
        return preferences
    
    def prevent_over_messaging(
        self,
        student_ids: List[UUID],
        timeframe_hours: int = 24,
        max_announcements: int = 5
    ) -> Tuple[List[UUID], List[UUID]]:
        """
        Filter students to prevent announcement fatigue.
        
        Args:
            student_ids: List of student UUIDs
            timeframe_hours: Time window to check
            max_announcements: Maximum announcements allowed
            
        Returns:
            Tuple of (eligible_students, filtered_out_students)
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=timeframe_hours)
        
        # Count announcements received by each student
        from app.models.announcement import AnnouncementRecipient
        
        announcement_counts = (
            self.session.query(
                AnnouncementRecipient.student_id,
                func.count(AnnouncementRecipient.id).label('count')
            )
            .filter(
                AnnouncementRecipient.student_id.in_(student_ids),
                AnnouncementRecipient.created_at >= cutoff_time
            )
            .group_by(AnnouncementRecipient.student_id)
            .all()
        )
        
        # Build count dictionary
        student_counts = {str(sid): count for sid, count in announcement_counts}
        
        # Filter students
        eligible = []
        filtered_out = []
        
        for student_id in student_ids:
            count = student_counts.get(str(student_id), 0)
            if count < max_announcements:
                eligible.append(student_id)
            else:
                filtered_out.append(student_id)
        
        return eligible, filtered_out
    
    # ==================== Bulk Targeting ====================
    
    def create_bulk_targeting_rule(
        self,
        announcement_id: UUID,
        created_by_id: UUID,
        rule_name: str,
        target_ids: List[UUID],
        combine_mode: str = 'union',
        global_exclusions: Optional[List[UUID]] = None
    ) -> BulkTargetingRule:
        """
        Create bulk targeting rule with multiple segments.
        
        Args:
            announcement_id: Announcement UUID
            created_by_id: User creating rule
            rule_name: Descriptive name
            target_ids: List of targeting configuration IDs
            combine_mode: How to combine (union/intersection)
            global_exclusions: Students to exclude
            
        Returns:
            Created bulk targeting rule
        """
        bulk_rule = BulkTargetingRule(
            announcement_id=announcement_id,
            created_by_id=created_by_id,
            rule_name=rule_name,
            target_ids=target_ids,
            combine_mode=combine_mode,
            global_exclude_student_ids=global_exclusions or [],
        )
        
        self.session.add(bulk_rule)
        self.session.flush()
        
        return bulk_rule
    
    def process_bulk_targeting(
        self,
        bulk_rule_id: UUID
    ) -> BulkTargetingRule:
        """
        Process bulk targeting rule to calculate final audience.
        
        Args:
            bulk_rule_id: Bulk rule UUID
            
        Returns:
            Processed bulk rule with final audience
        """
        bulk_rule = self.session.get(BulkTargetingRule, bulk_rule_id)
        if not bulk_rule:
            raise ResourceNotFoundError(f"Bulk rule {bulk_rule_id} not found")
        
        # Get all target configurations
        targets = (
            self.session.query(AnnouncementTarget)
            .filter(AnnouncementTarget.id.in_(bulk_rule.target_ids))
            .all()
        )
        
        # Calculate audiences for each target
        audience_sets = []
        for target in targets:
            student_ids = self._calculate_target_audience(target)
            audience_sets.append(set(student_ids))
        
        # Combine based on mode
        if bulk_rule.combine_mode == 'union':
            final_audience = set.union(*audience_sets) if audience_sets else set()
        elif bulk_rule.combine_mode == 'intersection':
            final_audience = set.intersection(*audience_sets) if audience_sets else set()
        else:
            raise ValidationError(f"Invalid combine mode: {bulk_rule.combine_mode}")
        
        # Apply global exclusions
        if bulk_rule.global_exclude_student_ids:
            exclusions = set(bulk_rule.global_exclude_student_ids)
            final_audience = final_audience - exclusions
        
        # Update bulk rule
        bulk_rule.final_student_ids = list(final_audience)
        bulk_rule.final_count = len(final_audience)
        bulk_rule.is_processed = True
        bulk_rule.processed_at = datetime.utcnow()
        
        self.session.flush()
        return bulk_rule
    
    # ==================== Audience Cache Management ====================
    
    def get_cached_audience(
        self,
        announcement_id: UUID,
        refresh_if_stale: bool = True
    ) -> Optional[TargetAudienceCache]:
        """
        Get cached audience data.
        
        Args:
            announcement_id: Announcement UUID
            refresh_if_stale: Refresh cache if stale
            
        Returns:
            Cached audience or None
        """
        cache = (
            self.session.query(TargetAudienceCache)
            .filter(TargetAudienceCache.announcement_id == announcement_id)
            .first()
        )
        
        if not cache:
            return None
        
        # Check if stale
        if cache.is_stale and refresh_if_stale:
            target = self._get_target_by_announcement(announcement_id)
            if target:
                student_ids = self._calculate_target_audience(target)
                breakdown = self._get_audience_breakdown(student_ids)
                cache = self._update_audience_cache(target, student_ids, breakdown)
        
        return cache
    
    def invalidate_audience_cache(
        self,
        announcement_id: UUID
    ) -> None:
        """
        Mark audience cache as stale.
        
        Args:
            announcement_id: Announcement UUID
        """
        cache = (
            self.session.query(TargetAudienceCache)
            .filter(TargetAudienceCache.announcement_id == announcement_id)
            .first()
        )
        
        if cache:
            cache.is_stale = True
            self.session.flush()
    
    # ==================== Query Operations ====================
    
    def find_by_announcement(
        self,
        announcement_id: UUID
    ) -> Optional[AnnouncementTarget]:
        """
        Find targeting configuration for announcement.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            Targeting configuration or None
        """
        return self._get_target_by_announcement(announcement_id)
    
    def get_targeting_rules(
        self,
        target_id: UUID,
        active_only: bool = True
    ) -> List[TargetingRule]:
        """
        Get targeting rules for a target configuration.
        
        Args:
            target_id: Target configuration UUID
            active_only: Only active rules
            
        Returns:
            List of targeting rules
        """
        query = (
            select(TargetingRule)
            .where(TargetingRule.target_id == target_id)
            .order_by(TargetingRule.priority.asc())
        )
        
        if active_only:
            query = query.where(TargetingRule.is_active == True)
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    # ==================== Helper Methods ====================
    
    def _calculate_target_audience(
        self,
        target: AnnouncementTarget
    ) -> List[UUID]:
        """
        Calculate actual student IDs based on targeting configuration.
        
        Args:
            target: Targeting configuration
            
        Returns:
            List of student UUIDs
        """
        announcement = self.session.get(Announcement, target.announcement_id)
        hostel_id = announcement.hostel_id
        
        # Base query for students in hostel
        query = (
            select(User.id)
            .join(Room, User.room_id == Room.id)
            .where(Room.hostel_id == hostel_id)
        )
        
        # Apply target type filters
        if target.target_type == TargetAudience.ALL:
            # All students in hostel
            pass
        
        elif target.target_type == TargetAudience.SPECIFIC_ROOMS:
            if target.room_ids:
                query = query.where(User.room_id.in_(target.room_ids))
        
        elif target.target_type == TargetAudience.SPECIFIC_FLOORS:
            if target.floor_numbers:
                query = query.where(Room.floor_number.in_(target.floor_numbers))
        
        elif target.target_type == TargetAudience.SPECIFIC_STUDENTS:
            if target.student_ids:
                query = select(User.id).where(User.id.in_(target.student_ids))
        
        elif target.target_type == TargetAudience.CUSTOM:
            # Apply custom targeting rules
            rules = self.get_targeting_rules(target.id)
            for rule in rules:
                rule_filter = self._build_rule_filter(rule)
                if rule.is_inclusion:
                    query = query.where(rule_filter)
                else:
                    query = query.where(~rule_filter)
        
        # Apply status filters
        if target.include_active_students:
            query = query.where(User.status == 'ACTIVE')
        
        if target.include_inactive_students:
            query = query.where(User.status == 'INACTIVE')
        
        if target.include_notice_period_students:
            query = query.where(User.status == 'NOTICE_PERIOD')
        
        # Apply exclusions
        if target.exclude_student_ids:
            query = query.where(~User.id.in_(target.exclude_student_ids))
        
        if target.exclude_room_ids:
            query = query.where(~User.room_id.in_(target.exclude_room_ids))
        
        # Execute query
        result = self.session.execute(query)
        return [row[0] for row in result]
    
    def _build_rule_filter(self, rule: TargetingRule):
        """Build SQLAlchemy filter from targeting rule."""
        field = getattr(User, rule.rule_field, None)
        if not field:
            # Try Room model
            field = getattr(Room, rule.rule_field, None)
        
        if not field:
            raise ValidationError(f"Invalid rule field: {rule.rule_field}")
        
        operator = rule.rule_operator
        value = rule.rule_value.get('value')
        
        if operator == 'equals':
            return field == value
        elif operator == 'in':
            return field.in_(value)
        elif operator == 'contains':
            return field.contains(value)
        elif operator == 'greater_than':
            return field > value
        elif operator == 'less_than':
            return field < value
        elif operator == 'between':
            return and_(field >= value[0], field <= value[1])
        else:
            raise ValidationError(f"Invalid operator: {operator}")
    
    def _get_audience_breakdown(
        self,
        student_ids: List[UUID]
    ) -> Dict[str, Dict]:
        """Get detailed breakdown of audience by various dimensions."""
        if not student_ids:
            return {
                'by_room': {},
                'by_floor': {},
                'by_status': {},
            }
        
        # Breakdown by room
        room_breakdown = (
            self.session.query(
                Room.room_number,
                func.count(User.id)
            )
            .join(User, User.room_id == Room.id)
            .filter(User.id.in_(student_ids))
            .group_by(Room.room_number)
            .all()
        )
        
        # Breakdown by floor
        floor_breakdown = (
            self.session.query(
                Room.floor_number,
                func.count(User.id)
            )
            .join(User, User.room_id == Room.id)
            .filter(User.id.in_(student_ids))
            .group_by(Room.floor_number)
            .all()
        )
        
        # Breakdown by status
        status_breakdown = (
            self.session.query(
                User.status,
                func.count(User.id)
            )
            .filter(User.id.in_(student_ids))
            .group_by(User.status)
            .all()
        )
        
        return {
            'by_room': {room: count for room, count in room_breakdown},
            'by_floor': {floor: count for floor, count in floor_breakdown},
            'by_status': {status: count for status, count in status_breakdown},
        }
    
    def _update_audience_cache(
        self,
        target: AnnouncementTarget,
        student_ids: List[UUID],
        breakdown: Dict[str, Dict]
    ) -> TargetAudienceCache:
        """Update or create audience cache."""
        cache = (
            self.session.query(TargetAudienceCache)
            .filter(
                TargetAudienceCache.announcement_id == target.announcement_id,
                TargetAudienceCache.target_id == target.id
            )
            .first()
        )
        
        now = datetime.utcnow()
        
        if cache:
            cache.student_ids = student_ids
            cache.total_count = len(student_ids)
            cache.breakdown_by_room = breakdown['by_room']
            cache.breakdown_by_floor = breakdown['by_floor']
            cache.calculated_at = now
            cache.is_stale = False
            cache.expires_at = now + timedelta(hours=24)
            cache.cache_version = f"v{int(now.timestamp())}"
        else:
            cache = TargetAudienceCache(
                announcement_id=target.announcement_id,
                target_id=target.id,
                student_ids=student_ids,
                total_count=len(student_ids),
                breakdown_by_room=breakdown['by_room'],
                breakdown_by_floor=breakdown['by_floor'],
                calculated_at=now,
                expires_at=now + timedelta(hours=24),
                is_stale=False,
                cache_version=f"v{int(now.timestamp())}"
            )
            self.session.add(cache)
        
        self.session.flush()
        return cache
    
    def _validate_targeting(self, target: AnnouncementTarget) -> None:
        """Validate targeting configuration."""
        errors = []
        
        # Check estimated recipients
        if target.estimated_recipients == 0:
            errors.append("No recipients match targeting criteria")
        
        # Validate specific targets
        if target.target_type == TargetAudience.SPECIFIC_ROOMS:
            if not target.room_ids:
                errors.append("Room IDs required for SPECIFIC_ROOMS targeting")
        
        if target.target_type == TargetAudience.SPECIFIC_FLOORS:
            if not target.floor_numbers:
                errors.append("Floor numbers required for SPECIFIC_FLOORS targeting")
        
        if target.target_type == TargetAudience.SPECIFIC_STUDENTS:
            if not target.student_ids:
                errors.append("Student IDs required for SPECIFIC_STUDENTS targeting")
        
        target.validation_errors = errors if errors else None
        target.is_validated = len(errors) == 0
        target.validated_at = datetime.utcnow()
    
    def _get_target_by_announcement(
        self,
        announcement_id: UUID
    ) -> Optional[AnnouncementTarget]:
        """Get targeting configuration for announcement."""
        return (
            self.session.query(AnnouncementTarget)
            .filter(AnnouncementTarget.announcement_id == announcement_id)
            .first()
        )
    
    def _get_notification_preferences(
        self,
        student_id: UUID
    ) -> Dict[str, Any]:
        """Get student notification preferences."""
        student = self.session.get(User, student_id)
        if not student or not student.metadata:
            return {
                'email': True,
                'sms': False,
                'push': True,
            }
        
        return student.metadata.get('notification_preferences', {
            'email': True,
            'sms': False,
            'push': True,
        })
    
    def _get_engagement_history(
        self,
        student_id: UUID,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get student's engagement history."""
        from app.models.announcement import ReadReceipt
        
        recent_reads = (
            self.session.query(
                ReadReceipt.announcement_id,
                ReadReceipt.read_at,
                ReadReceipt.reading_time_seconds
            )
            .filter(ReadReceipt.student_id == student_id)
            .order_by(ReadReceipt.read_at.desc())
            .limit(limit)
            .all()
        )
        
        total_reads = (
            self.session.query(func.count(ReadReceipt.id))
            .filter(ReadReceipt.student_id == student_id)
            .scalar()
        ) or 0
        
        avg_reading_time = (
            self.session.query(func.avg(ReadReceipt.reading_time_seconds))
            .filter(ReadReceipt.student_id == student_id)
            .scalar()
        ) or 0
        
        return {
            'total_reads': total_reads,
            'average_reading_time_seconds': float(avg_reading_time),
            'recent_reads': [
                {
                    'announcement_id': str(r.announcement_id),
                    'read_at': r.read_at.isoformat(),
                    'reading_time': r.reading_time_seconds
                }
                for r in recent_reads
            ]
        }
    
    def _calculate_estimation_accuracy(
        self,
        target: AnnouncementTarget
    ) -> float:
        """Calculate accuracy of recipient estimation."""
        if target.estimated_recipients == 0:
            return 0.0
        
        actual = target.actual_recipients or target.estimated_recipients
        estimated = target.estimated_recipients
        
        # Calculate percentage accuracy
        difference = abs(actual - estimated)
        accuracy = (1 - (difference / estimated)) * 100
        
        return max(0.0, min(100.0, accuracy))
    
    def _calculate_effectiveness_score(
        self,
        read_rate: float,
        ack_rate: float,
        requires_ack: bool
    ) -> float:
        """Calculate overall targeting effectiveness score."""
        if requires_ack:
            # Weight acknowledgment more heavily
            score = (read_rate * 0.3) + (ack_rate * 0.7)
        else:
            # Only consider read rate
            score = read_rate
        
        return round(score, 2)


from datetime import timedelta