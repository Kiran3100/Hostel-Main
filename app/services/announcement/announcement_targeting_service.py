"""
Announcement Targeting Service

Audience targeting and segmentation service providing sophisticated
targeting capabilities, reach calculation, and delivery optimization.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Set, Tuple
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.orm import Session
from pydantic import BaseModel, validator, Field

from app.repositories.announcement import (
    AnnouncementTargetingRepository,
    AnnouncementRepository,
)
from app.models.base.enums import TargetAudience, RoomType
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    BusinessLogicError,
) 
from app.core.events import EventPublisher
from app.core.cache import CacheManager


# ==================== DTOs ====================

class TargetingCriteriaDTO(BaseModel):
    """DTO for targeting criteria."""
    type: str = Field(..., regex='^(room_type|floor|status|custom)$')
    field: str
    operator: str = Field(..., regex='^(equals|in|contains|greater_than|less_than|between)$')
    value: Any
    is_inclusion: bool = True
    description: Optional[str] = None


class BuildAudienceSegmentDTO(BaseModel):
    """DTO for building audience segment."""
    target_type: TargetAudience
    room_ids: Optional[List[UUID]] = None
    student_ids: Optional[List[UUID]] = None
    floor_numbers: Optional[List[int]] = None
    exclude_student_ids: Optional[List[UUID]] = None
    exclude_room_ids: Optional[List[UUID]] = None
    include_active_students: bool = True
    include_inactive_students: bool = False
    include_notice_period_students: bool = True
    room_types: Optional[List[str]] = None
    
    @validator('room_ids')
    def validate_room_targeting(cls, v, values):
        if values.get('target_type') == TargetAudience.SPECIFIC_ROOMS and not v:
            raise ValueError('Room IDs required for SPECIFIC_ROOMS targeting')
        return v
    
    @validator('student_ids')
    def validate_student_targeting(cls, v, values):
        if values.get('target_type') == TargetAudience.SPECIFIC_STUDENTS and not v:
            raise ValueError('Student IDs required for SPECIFIC_STUDENTS targeting')
        return v
    
    @validator('floor_numbers')
    def validate_floor_targeting(cls, v, values):
        if values.get('target_type') == TargetAudience.SPECIFIC_FLOORS and not v:
            raise ValueError('Floor numbers required for SPECIFIC_FLOORS targeting')
        return v


class MultiCriteriaSegmentDTO(BaseModel):
    """DTO for multi-criteria segment."""
    criteria: List[TargetingCriteriaDTO] = Field(..., min_items=1)
    exclude_student_ids: Optional[List[UUID]] = None
    
    @validator('criteria')
    def validate_criteria(cls, v):
        if len(v) > 10:
            raise ValueError('Maximum 10 criteria allowed')
        return v


class BulkTargetingDTO(BaseModel):
    """DTO for bulk targeting."""
    rule_name: str = Field(..., min_length=3, max_length=100)
    segment_ids: List[UUID] = Field(..., min_items=1, max_items=10)
    combine_mode: str = Field(..., regex='^(union|intersection)$')
    global_exclusions: Optional[List[UUID]] = None


class PersonalizationContextDTO(BaseModel):
    """DTO for personalization context."""
    student_id: UUID
    include_history: bool = True
    include_preferences: bool = True


class NotificationPreferencesDTO(BaseModel):
    """DTO for notification preferences."""
    email: bool = True
    sms: bool = False
    push: bool = True
    quiet_hours_start: Optional[str] = Field(None, regex='^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
    quiet_hours_end: Optional[str] = Field(None, regex='^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
    max_daily_announcements: Optional[int] = Field(None, ge=1, le=20)


@dataclass
class ServiceResult:
    """Standard service result wrapper."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @classmethod
    def ok(cls, data: Any = None, **metadata) -> 'ServiceResult':
        return cls(success=True, data=data, metadata=metadata)
    
    @classmethod
    def fail(cls, error: str, error_code: str = None, **metadata) -> 'ServiceResult':
        return cls(success=False, error=error, error_code=error_code, metadata=metadata)


# ==================== Service ====================

class AnnouncementTargetingService:
    """
    Audience targeting and segmentation service.
    
    Provides sophisticated targeting capabilities including:
    - Dynamic audience segmentation
    - Multi-criteria targeting rules
    - Target reach calculation and validation
    - Delivery timing optimization
    - Content personalization
    - Over-messaging prevention
    - Audience preference management
    - Bulk targeting operations
    """
    
    def __init__(
        self,
        session: Session,
        event_publisher: Optional[EventPublisher] = None,
        cache_manager: Optional[CacheManager] = None
    ):
        self.session = session
        self.repository = AnnouncementTargetingRepository(session)
        self.announcement_repository = AnnouncementRepository(session)
        self.event_publisher = event_publisher or EventPublisher()
        self.cache = cache_manager or CacheManager()
    
    # ==================== Audience Segmentation ====================
    
    def build_audience_segment(
        self,
        announcement_id: UUID,
        dto: BuildAudienceSegmentDTO,
        user_id: UUID
    ) -> ServiceResult:
        """
        Build audience segment for announcement.
        
        Args:
            announcement_id: Announcement UUID
            dto: Targeting configuration
            user_id: User creating segment
            
        Returns:
            ServiceResult with segment data
        """
        try:
            # Validate announcement exists
            announcement = self.announcement_repository.find_by_id(announcement_id)
            if not announcement:
                return ServiceResult.fail(
                    f"Announcement {announcement_id} not found",
                    error_code="NOT_FOUND"
                )
            
            # Build segment
            target = self.repository.build_audience_segment(
                announcement_id=announcement_id,
                target_type=dto.target_type,
                created_by_id=user_id,
                room_ids=dto.room_ids,
                student_ids=dto.student_ids,
                floor_numbers=dto.floor_numbers,
                exclude_student_ids=dto.exclude_student_ids,
                exclude_room_ids=dto.exclude_room_ids,
                include_active_students=dto.include_active_students,
                include_inactive_students=dto.include_inactive_students,
                include_notice_period_students=dto.include_notice_period_students,
                room_types=dto.room_types
            )
            
            # Calculate reach
            reach = self.repository.calculate_target_reach(
                announcement_id=announcement_id,
                update_cache=True
            )
            
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('targeting.segment_created', {
                'announcement_id': str(announcement_id),
                'target_type': dto.target_type.value,
                'estimated_recipients': target.estimated_recipients,
                'actual_recipients': reach['actual_recipients'],
            })
            
            return ServiceResult.ok(
                data={
                    'target': self._serialize_target(target),
                    'reach': reach,
                    'validation': {
                        'is_valid': target.is_validated,
                        'errors': target.validation_errors,
                    }
                },
                target_id=str(target.id)
            )
            
        except ValidationError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="VALIDATION_ERROR")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(
                f"Failed to build segment: {str(e)}",
                error_code="SEGMENT_BUILD_FAILED"
            )
    
    def build_multi_criteria_segment(
        self,
        announcement_id: UUID,
        dto: MultiCriteriaSegmentDTO,
        user_id: UUID
    ) -> ServiceResult:
        """
        Build segment with multiple targeting criteria.
        
        Args:
            announcement_id: Announcement UUID
            dto: Multi-criteria configuration
            user_id: User creating segment
            
        Returns:
            ServiceResult with segment data
        """
        try:
            # Convert DTO criteria to dict format
            criteria_dicts = [
                {
                    'type': c.type,
                    'field': c.field,
                    'operator': c.operator,
                    'value': c.value,
                    'is_inclusion': c.is_inclusion,
                    'description': c.description,
                }
                for c in dto.criteria
            ]
            
            # Build segment
            target = self.repository.build_multi_criteria_segment(
                announcement_id=announcement_id,
                created_by_id=user_id,
                criteria=criteria_dicts
            )
            
            # Calculate reach
            reach = self.repository.calculate_target_reach(
                announcement_id=announcement_id,
                update_cache=True
            )
            
            self.session.commit()
            
            self.event_publisher.publish('targeting.multi_criteria_created', {
                'announcement_id': str(announcement_id),
                'criteria_count': len(dto.criteria),
                'actual_recipients': reach['actual_recipients'],
            })
            
            return ServiceResult.ok(
                data={
                    'target': self._serialize_target(target),
                    'reach': reach,
                    'criteria_count': len(dto.criteria),
                },
                target_id=str(target.id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="MULTI_CRITERIA_FAILED")
    
    def calculate_target_reach(
        self,
        announcement_id: UUID,
        refresh_cache: bool = False
    ) -> ServiceResult:
        """
        Calculate target audience reach with detailed breakdown.
        
        Args:
            announcement_id: Announcement UUID
            refresh_cache: Force cache refresh
            
        Returns:
            ServiceResult with reach analysis
        """
        try:
            # Check cache if not refreshing
            if not refresh_cache:
                cache_key = f"reach:{announcement_id}"
                cached = self.cache.get(cache_key)
                if cached:
                    return ServiceResult.ok(data=cached, from_cache=True)
            
            # Calculate fresh reach
            reach = self.repository.calculate_target_reach(
                announcement_id=announcement_id,
                update_cache=True
            )
            
            # Cache for 5 minutes
            cache_key = f"reach:{announcement_id}"
            self.cache.set(cache_key, reach, ttl=300)
            
            return ServiceResult.ok(data=reach, from_cache=False)
            
        except ResourceNotFoundError as e:
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="REACH_CALCULATION_FAILED")
    
    def validate_targeting(
        self,
        announcement_id: UUID
    ) -> ServiceResult:
        """
        Validate targeting configuration.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            ServiceResult with validation results
        """
        try:
            target = self.repository.find_by_announcement(announcement_id)
            if not target:
                return ServiceResult.fail(
                    f"No targeting found for announcement {announcement_id}",
                    error_code="NOT_FOUND"
                )
            
            # Recalculate to validate
            reach = self.repository.calculate_target_reach(
                announcement_id=announcement_id,
                update_cache=False
            )
            
            is_valid = (
                target.is_validated and
                not target.validation_errors and
                reach['actual_recipients'] > 0
            )
            
            return ServiceResult.ok(data={
                'is_valid': is_valid,
                'validation_errors': target.validation_errors,
                'actual_recipients': reach['actual_recipients'],
                'warnings': self._get_targeting_warnings(target, reach),
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="VALIDATION_FAILED")
    
    # ==================== Delivery Optimization ====================
    
    def optimize_delivery_timing(
        self,
        announcement_id: UUID
    ) -> ServiceResult:
        """
        Calculate optimal delivery time based on audience engagement patterns.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            ServiceResult with timing recommendations
        """
        try:
            timing = self.repository.optimize_delivery_timing(
                announcement_id=announcement_id
            )
            
            # Add recommendations
            recommendations = self._generate_timing_recommendations(timing)
            
            return ServiceResult.ok(data={
                'optimal_timing': timing,
                'recommendations': recommendations,
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="TIMING_OPTIMIZATION_FAILED")
    
    def get_optimal_channels(
        self,
        announcement_id: UUID,
        student_id: UUID
    ) -> ServiceResult:
        """
        Get optimal delivery channels for specific student.
        
        Args:
            announcement_id: Announcement UUID
            student_id: Student UUID
            
        Returns:
            ServiceResult with channel recommendations
        """
        try:
            # Get student preferences
            prefs_result = self.get_notification_preferences(student_id)
            if not prefs_result.success:
                return prefs_result
            
            preferences = prefs_result.data
            
            # Get optimal channel
            optimal_channel = self.repository.get_optimal_channel(
                announcement_id=announcement_id,
                recipient_id=student_id
            )
            
            # Build channel list with priorities
            channels = []
            
            if preferences.get('push', True):
                channels.append({
                    'channel': 'push',
                    'priority': 1,
                    'recommended': optimal_channel == 'push'
                })
            
            if preferences.get('email', True):
                channels.append({
                    'channel': 'email',
                    'priority': 2,
                    'recommended': optimal_channel == 'email'
                })
            
            if preferences.get('sms', False):
                channels.append({
                    'channel': 'sms',
                    'priority': 3,
                    'recommended': optimal_channel == 'sms'
                })
            
            channels.append({
                'channel': 'in_app',
                'priority': 4,
                'recommended': optimal_channel == 'in_app'
            })
            
            return ServiceResult.ok(data={
                'optimal_channel': optimal_channel,
                'available_channels': channels,
                'preferences': preferences,
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="CHANNEL_OPTIMIZATION_FAILED")
    
    # ==================== Personalization ====================
    
    def get_personalization_context(
        self,
        announcement_id: UUID,
        dto: PersonalizationContextDTO
    ) -> ServiceResult:
        """
        Get personalization context for recipient.
        
        Args:
            announcement_id: Announcement UUID
            dto: Personalization request
            
        Returns:
            ServiceResult with personalization data
        """
        try:
            context = self.repository.personalize_content(
                announcement_id=announcement_id,
                student_id=dto.student_id
            )
            
            # Optionally exclude history/preferences
            if not dto.include_history:
                context.pop('past_engagement', None)
            
            if not dto.include_preferences:
                context.pop('notification_preferences', None)
            
            return ServiceResult.ok(data=context)
            
        except ResourceNotFoundError as e:
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="PERSONALIZATION_FAILED")
    
    def render_personalized_content(
        self,
        announcement_id: UUID,
        student_id: UUID,
        content_template: str
    ) -> ServiceResult:
        """
        Render content with personalization variables.
        
        Args:
            announcement_id: Announcement UUID
            student_id: Student UUID
            content_template: Content template with variables
            
        Returns:
            ServiceResult with rendered content
        """
        try:
            # Get personalization context
            context_result = self.get_personalization_context(
                announcement_id,
                PersonalizationContextDTO(student_id=student_id)
            )
            
            if not context_result.success:
                return context_result
            
            context = context_result.data
            
            # Simple variable substitution
            rendered = content_template
            for key, value in context.items():
                if isinstance(value, (str, int, float)):
                    rendered = rendered.replace(f'{{{key}}}', str(value))
            
            return ServiceResult.ok(data={
                'rendered_content': rendered,
                'variables_used': list(context.keys()),
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="RENDERING_FAILED")
    
    # ==================== Over-messaging Prevention ====================
    
    def check_messaging_limits(
        self,
        student_ids: List[UUID],
        timeframe_hours: int = 24,
        max_announcements: int = 5
    ) -> ServiceResult:
        """
        Check if students are within messaging limits.
        
        Args:
            student_ids: List of student UUIDs
            timeframe_hours: Time window
            max_announcements: Maximum allowed
            
        Returns:
            ServiceResult with eligible and filtered students
        """
        try:
            eligible, filtered_out = self.repository.prevent_over_messaging(
                student_ids=student_ids,
                timeframe_hours=timeframe_hours,
                max_announcements=max_announcements
            )
            
            return ServiceResult.ok(data={
                'eligible_students': [str(sid) for sid in eligible],
                'filtered_out_students': [str(sid) for sid in filtered_out],
                'eligible_count': len(eligible),
                'filtered_count': len(filtered_out),
                'timeframe_hours': timeframe_hours,
                'max_announcements': max_announcements,
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="LIMIT_CHECK_FAILED")
    
    def apply_smart_filtering(
        self,
        announcement_id: UUID,
        rules: Optional[Dict[str, Any]] = None
    ) -> ServiceResult:
        """
        Apply intelligent filtering to prevent over-messaging.
        
        Args:
            announcement_id: Announcement UUID
            rules: Optional filtering rules
            
        Returns:
            ServiceResult with filtered audience
        """
        try:
            # Get current target audience
            reach = self.repository.calculate_target_reach(
                announcement_id=announcement_id,
                update_cache=False
            )
            
            student_ids = [UUID(sid) for sid in reach['student_ids']]
            
            # Apply default or custom rules
            if not rules:
                rules = {
                    'timeframe_hours': 24,
                    'max_announcements': 5,
                }
            
            # Check limits
            limit_result = self.check_messaging_limits(
                student_ids=student_ids,
                timeframe_hours=rules.get('timeframe_hours', 24),
                max_announcements=rules.get('max_announcements', 5)
            )
            
            if not limit_result.success:
                return limit_result
            
            eligible_ids = [UUID(sid) for sid in limit_result.data['eligible_students']]
            
            # Update targeting with filtered list
            target = self.repository.find_by_announcement(announcement_id)
            if target:
                # Add filtered-out students to exclusion list
                filtered_ids = [UUID(sid) for sid in limit_result.data['filtered_out_students']]
                if not target.exclude_student_ids:
                    target.exclude_student_ids = []
                target.exclude_student_ids.extend(filtered_ids)
                
                self.session.commit()
            
            return ServiceResult.ok(data={
                'original_count': len(student_ids),
                'filtered_count': len(eligible_ids),
                'removed_count': len(student_ids) - len(eligible_ids),
                'eligible_students': [str(sid) for sid in eligible_ids],
            })
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="FILTERING_FAILED")
    
    # ==================== Preference Management ====================
    
    def get_notification_preferences(
        self,
        student_id: UUID
    ) -> ServiceResult:
        """
        Get student notification preferences.
        
        Args:
            student_id: Student UUID
            
        Returns:
            ServiceResult with preferences
        """
        try:
            from app.models.user.user import User
            
            student = self.session.get(User, student_id)
            if not student:
                return ServiceResult.fail(
                    f"Student {student_id} not found",
                    error_code="NOT_FOUND"
                )
            
            preferences = student.metadata.get('notification_preferences', {
                'email': True,
                'sms': False,
                'push': True,
            }) if student.metadata else {
                'email': True,
                'sms': False,
                'push': True,
            }
            
            return ServiceResult.ok(data=preferences)
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="FETCH_PREFERENCES_FAILED")
    
    def update_notification_preferences(
        self,
        student_id: UUID,
        dto: NotificationPreferencesDTO
    ) -> ServiceResult:
        """
        Update student notification preferences.
        
        Args:
            student_id: Student UUID
            dto: Preferences data
            
        Returns:
            ServiceResult with updated preferences
        """
        try:
            preferences = dto.dict()
            
            updated = self.repository.manage_audience_preferences(
                student_id=student_id,
                preferences=preferences
            )
            
            self.session.commit()
            
            self.event_publisher.publish('preferences.updated', {
                'student_id': str(student_id),
                'preferences': updated,
            })
            
            return ServiceResult.ok(data=updated)
            
        except ResourceNotFoundError as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="UPDATE_FAILED")
    
    # ==================== Bulk Targeting ====================
    
    def create_bulk_targeting(
        self,
        announcement_id: UUID,
        dto: BulkTargetingDTO,
        user_id: UUID
    ) -> ServiceResult:
        """
        Create bulk targeting rule combining multiple segments.
        
        Args:
            announcement_id: Announcement UUID
            dto: Bulk targeting configuration
            user_id: User creating rule
            
        Returns:
            ServiceResult with bulk targeting data
        """
        try:
            bulk_rule = self.repository.create_bulk_targeting_rule(
                announcement_id=announcement_id,
                created_by_id=user_id,
                rule_name=dto.rule_name,
                target_ids=dto.segment_ids,
                combine_mode=dto.combine_mode,
                global_exclusions=dto.global_exclusions
            )
            
            # Process immediately
            bulk_rule = self.repository.process_bulk_targeting(bulk_rule.id)
            
            self.session.commit()
            
            self.event_publisher.publish('targeting.bulk_created', {
                'announcement_id': str(announcement_id),
                'rule_name': dto.rule_name,
                'segments_combined': len(dto.segment_ids),
                'final_count': bulk_rule.final_count,
            })
            
            return ServiceResult.ok(
                data={
                    'rule_id': str(bulk_rule.id),
                    'rule_name': bulk_rule.rule_name,
                    'combine_mode': bulk_rule.combine_mode,
                    'segments_combined': len(dto.segment_ids),
                    'final_count': bulk_rule.final_count,
                    'final_students': [str(sid) for sid in bulk_rule.final_student_ids],
                },
                rule_id=str(bulk_rule.id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="BULK_TARGETING_FAILED")
    
    # ==================== Analytics ====================
    
    def get_targeting_effectiveness(
        self,
        announcement_id: UUID
    ) -> ServiceResult:
        """
        Analyze targeting strategy effectiveness.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            ServiceResult with effectiveness metrics
        """
        try:
            effectiveness = self.repository.track_targeting_effectiveness(
                announcement_id=announcement_id
            )
            
            return ServiceResult.ok(data=effectiveness)
            
        except ResourceNotFoundError as e:
            return ServiceResult.fail(str(e), error_code="NOT_FOUND")
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="EFFECTIVENESS_ANALYSIS_FAILED")
    
    def get_audience_insights(
        self,
        announcement_id: UUID
    ) -> ServiceResult:
        """
        Get detailed audience insights and breakdown.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            ServiceResult with audience insights
        """
        try:
            reach = self.repository.calculate_target_reach(
                announcement_id=announcement_id,
                update_cache=False
            )
            
            # Add additional insights
            insights = {
                'reach_summary': {
                    'total_recipients': reach['actual_recipients'],
                    'breakdown_by_room': reach['breakdown_by_room'],
                    'breakdown_by_floor': reach['breakdown_by_floor'],
                },
                'targeting_strategy': reach['target_type'],
                'coverage_analysis': self._analyze_coverage(reach),
            }
            
            return ServiceResult.ok(data=insights)
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="INSIGHTS_FAILED")
    
    # ==================== Cache Management ====================
    
    def invalidate_audience_cache(
        self,
        announcement_id: UUID
    ) -> ServiceResult:
        """
        Invalidate cached audience data.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            ServiceResult
        """
        try:
            self.repository.invalidate_audience_cache(announcement_id)
            self.cache.delete(f"reach:{announcement_id}")
            
            return ServiceResult.ok(data={'cache_invalidated': True})
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="CACHE_INVALIDATION_FAILED")
    
    def refresh_audience_cache(
        self,
        announcement_id: UUID
    ) -> ServiceResult:
        """
        Refresh audience cache with latest data.
        
        Args:
            announcement_id: Announcement UUID
            
        Returns:
            ServiceResult with refreshed data
        """
        try:
            # Invalidate first
            self.invalidate_audience_cache(announcement_id)
            
            # Recalculate
            reach = self.repository.calculate_target_reach(
                announcement_id=announcement_id,
                update_cache=True
            )
            
            return ServiceResult.ok(data=reach, cache_refreshed=True)
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="CACHE_REFRESH_FAILED")
    
    # ==================== Helper Methods ====================
    
    def _serialize_target(self, target) -> Dict[str, Any]:
        """Serialize targeting configuration."""
        return {
            'id': str(target.id),
            'announcement_id': str(target.announcement_id),
            'target_type': target.target_type.value,
            'estimated_recipients': target.estimated_recipients,
            'actual_recipients': target.actual_recipients,
            'is_validated': target.is_validated,
            'validation_errors': target.validation_errors,
            'created_at': target.created_at.isoformat(),
        }
    
    def _get_targeting_warnings(
        self,
        target,
        reach: Dict[str, Any]
    ) -> List[str]:
        """Generate targeting warnings."""
        warnings = []
        
        # Low reach warning
        if reach['actual_recipients'] < 5:
            warnings.append("Very small audience - consider broadening targeting criteria")
        
        # Estimation accuracy warning
        if target.estimated_recipients > 0:
            accuracy = abs(target.estimated_recipients - reach['actual_recipients']) / target.estimated_recipients
            if accuracy > 0.2:  # More than 20% difference
                warnings.append("Significant difference between estimated and actual reach")
        
        return warnings
    
    def _generate_timing_recommendations(
        self,
        timing: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate timing recommendations."""
        recommendations = []
        
        optimal_hour = timing.get('optimal_hour', 9)
        optimal_day = timing.get('optimal_day', 1)
        
        # Map day of week
        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        
        recommendations.append({
            'type': 'optimal_time',
            'recommendation': f"Best time to send: {days[optimal_day]} at {optimal_hour}:00",
            'confidence': 'high' if timing.get('total_students_analyzed', 0) > 50 else 'medium',
        })
        
        # Avoid late night
        if optimal_hour < 7 or optimal_hour > 21:
            recommendations.append({
                'type': 'timing_warning',
                'recommendation': "Consider sending during waking hours (7 AM - 9 PM)",
                'confidence': 'high',
            })
        
        return recommendations
    
    def _analyze_coverage(self, reach: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze audience coverage."""
        total = reach['actual_recipients']
        breakdown = reach.get('breakdown_by_floor', {})
        
        return {
            'total_coverage': total,
            'floor_distribution': breakdown,
            'floor_count': len(breakdown),
            'average_per_floor': total / len(breakdown) if breakdown else 0,
        }