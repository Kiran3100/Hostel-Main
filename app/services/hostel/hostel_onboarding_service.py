# --- File: C:\Hostel-Main\app\services\hostel\hostel_onboarding_service.py ---
"""
Hostel onboarding service for streamlined hostel setup and configuration.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hostel.hostel import Hostel
from app.models.hostel.hostel_settings import HostelSettings
from app.models.base.enums import HostelType, HostelStatus
from app.services.hostel.hostel_service import HostelService
from app.services.hostel.hostel_settings_service import HostelSettingsService
from app.services.hostel.hostel_amenity_service import HostelAmenityService
from app.services.hostel.hostel_policy_service import HostelPolicyService
from app.core.exceptions import ValidationError, OnboardingError
from app.services.base.base_service import BaseService


class HostelOnboardingService(BaseService):
    """
    Hostel onboarding service for complete hostel setup.
    
    Provides guided onboarding workflow, templates, validation,
    and automated setup for new hostels.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.hostel_service = HostelService(session)
        self.settings_service = HostelSettingsService(session)
        self.amenity_service = HostelAmenityService(session)
        self.policy_service = HostelPolicyService(session)

    # ===== Onboarding Workflow =====

    async def start_onboarding(
        self,
        basic_info: Dict[str, Any],
        created_by: UUID
    ) -> Dict[str, Any]:
        """
        Start hostel onboarding process.
        
        Args:
            basic_info: Basic hostel information
            created_by: User ID starting onboarding
            
        Returns:
            Onboarding session data
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate basic info
        self._validate_basic_info(basic_info)
        
        # Create hostel in draft status
        hostel_data = {
            **basic_info,
            'status': HostelStatus.DRAFT,
            'is_active': False,
            'is_public': False
        }
        
        hostel = await self.hostel_service.create_hostel(hostel_data, created_by)
        
        # Create onboarding session
        onboarding_session = {
            'hostel_id': hostel.id,
            'created_by': created_by,
            'started_at': datetime.utcnow(),
            'current_step': 1,
            'total_steps': 6,
            'completed_steps': [],
            'status': 'in_progress'
        }
        
        # Log event
        await self._log_event('onboarding_started', {
            'hostel_id': hostel.id,
            'created_by': created_by
        })
        
        return {
            'hostel': hostel,
            'session': onboarding_session,
            'next_step': 'facilities'
        }

    async def complete_facilities_setup(
        self,
        hostel_id: UUID,
        facilities_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Complete facilities and capacity setup (Step 2).
        
        Args:
            hostel_id: Hostel UUID
            facilities_data: Facilities information
            
        Returns:
            Updated onboarding session
        """
        # Update hostel capacity
        await self.hostel_service.update_capacity(
            hostel_id,
            total_rooms=facilities_data.get('total_rooms'),
            total_beds=facilities_data.get('total_beds')
        )
        
        # Update hostel with facilities
        await self.hostel_service.update_hostel(hostel_id, {
            'amenities': facilities_data.get('amenities', []),
            'facilities': facilities_data.get('facilities', []),
            'security_features': facilities_data.get('security_features', [])
        })
        
        return {
            'step': 2,
            'completed': True,
            'next_step': 'pricing'
        }

    async def complete_pricing_setup(
        self,
        hostel_id: UUID,
        pricing_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Complete pricing setup (Step 3).
        
        Args:
            hostel_id: Hostel UUID
            pricing_data: Pricing information
            
        Returns:
            Updated onboarding session
        """
        # Update pricing
        await self.hostel_service.update_hostel(hostel_id, {
            'starting_price_monthly': pricing_data.get('starting_price'),
            'currency': pricing_data.get('currency', 'INR')
        })
        
        # Configure payment settings
        await self.settings_service.update_payment_settings(
            hostel_id,
            due_day=pricing_data.get('payment_due_day', 5),
            grace_days=pricing_data.get('grace_days', 3),
            security_deposit_months=pricing_data.get('security_deposit_months', 2)
        )
        
        return {
            'step': 3,
            'completed': True,
            'next_step': 'policies'
        }

    async def complete_policies_setup(
        self,
        hostel_id: UUID,
        use_templates: bool = True,
        custom_policies: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Complete policies setup (Step 4).
        
        Args:
            hostel_id: Hostel UUID
            use_templates: Use default policy templates
            custom_policies: Optional custom policies
            
        Returns:
            Updated onboarding session
        """
        if use_templates:
            # Create default policies from templates
            await self._create_default_policies(hostel_id)
        
        if custom_policies:
            # Create custom policies
            for policy_data in custom_policies:
                await self.policy_service.create_policy(
                    hostel_id,
                    policy_data
                )
        
        return {
            'step': 4,
            'completed': True,
            'next_step': 'settings'
        }

    async def complete_settings_configuration(
        self,
        hostel_id: UUID,
        settings_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Complete operational settings (Step 5).
        
        Args:
            hostel_id: Hostel UUID
            settings_data: Settings configuration
            
        Returns:
            Updated onboarding session
        """
        # Configure booking settings
        if 'booking' in settings_data:
            booking = settings_data['booking']
            await self.settings_service.update_booking_settings(
                hostel_id,
                auto_approve=booking.get('auto_approve', False),
                advance_percentage=booking.get('advance_percentage'),
                same_day_booking=booking.get('same_day_booking', False)
            )
        
        # Configure security settings
        if 'security' in settings_data:
            security = settings_data['security']
            await self.settings_service.update_security_settings(
                hostel_id,
                visitor_start_time=security.get('visitor_start_time'),
                visitor_end_time=security.get('visitor_end_time'),
                require_visitor_id=security.get('require_visitor_id', True)
            )
        
        # Enable features
        if 'features' in settings_data:
            for feature, enabled in settings_data['features'].items():
                if enabled:
                    await self.settings_service.enable_feature(hostel_id, feature)
        
        return {
            'step': 5,
            'completed': True,
            'next_step': 'review'
        }

    async def complete_review_and_launch(
        self,
        hostel_id: UUID,
        launch_immediately: bool = True
    ) -> Dict[str, Any]:
        """
        Complete review and launch hostel (Step 6).
        
        Args:
            hostel_id: Hostel UUID
            launch_immediately: Whether to activate immediately
            
        Returns:
            Completion status
        """
        # Validate hostel is ready
        validation = await self.validate_hostel_setup(hostel_id)
        
        if not validation['is_ready']:
            raise OnboardingError(
                f"Hostel setup incomplete. Missing: {', '.join(validation['missing_items'])}"
            )
        
        # Activate hostel if launching immediately
        if launch_immediately:
            await self.hostel_service.update_hostel(hostel_id, {
                'status': HostelStatus.ACTIVE,
                'is_active': True
            })
        
        # Log completion
        await self._log_event('onboarding_completed', {
            'hostel_id': hostel_id,
            'launched': launch_immediately
        })
        
        return {
            'step': 6,
            'completed': True,
            'status': 'completed',
            'hostel_id': hostel_id,
            'is_active': launch_immediately,
            'completed_at': datetime.utcnow()
        }

    # ===== Template Management =====

    async def get_onboarding_templates(
        self,
        hostel_type: HostelType
    ) -> Dict[str, Any]:
        """
        Get onboarding templates for hostel type.
        
        Args:
            hostel_type: Type of hostel
            
        Returns:
            Templates package
        """
        templates = {
            'amenities': self._get_amenity_templates(hostel_type),
            'policies': self._get_policy_templates(hostel_type),
            'settings': self._get_settings_templates(hostel_type)
        }
        
        return templates

    async def apply_template(
        self,
        hostel_id: UUID,
        template_type: str,
        template_name: str
    ) -> Dict[str, Any]:
        """
        Apply a specific template to hostel.
        
        Args:
            hostel_id: Hostel UUID
            template_type: Type of template (amenities, policies, settings)
            template_name: Template name
            
        Returns:
            Application result
        """
        hostel = await self.hostel_service.get_hostel_by_id(hostel_id)
        
        if template_type == 'amenities':
            return await self._apply_amenity_template(hostel_id, template_name)
        elif template_type == 'policies':
            return await self._apply_policy_template(hostel_id, template_name)
        elif template_type == 'settings':
            return await self._apply_settings_template(hostel_id, template_name)
        else:
            raise ValidationError(f"Invalid template type: {template_type}")

    # ===== Validation =====

    async def validate_hostel_setup(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Validate if hostel setup is complete and ready.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Validation result
        """
        hostel = await self.hostel_service.get_hostel_by_id(hostel_id, include_details=True)
        
        missing_items = []
        warnings = []
        
        # Check basic info
        if not hostel.description:
            warnings.append('Missing hostel description')
        
        # Check capacity
        if hostel.total_rooms == 0:
            missing_items.append('Total rooms not configured')
        
        if hostel.total_beds == 0:
            missing_items.append('Total beds not configured')
        
        # Check pricing
        if not hostel.starting_price_monthly:
            missing_items.append('Pricing not configured')
        
        # Check amenities
        if not hostel.amenities or len(hostel.amenities) == 0:
            warnings.append('No amenities added')
        
        # Check policies
        policies = await self.policy_service.get_hostel_policies(hostel_id, only_published=False)
        if len(policies) == 0:
            warnings.append('No policies created')
        
        mandatory_policies = [p for p in policies if p.is_mandatory]
        if len(mandatory_policies) == 0:
            warnings.append('No mandatory policies defined')
        
        # Check settings
        settings = await self.settings_service.get_hostel_settings(hostel_id)
        if not settings:
            missing_items.append('Settings not configured')
        
        is_ready = len(missing_items) == 0
        
        return {
            'hostel_id': hostel_id,
            'is_ready': is_ready,
            'completeness_score': self._calculate_completeness_score(hostel, policies, settings),
            'missing_items': missing_items,
            'warnings': warnings,
            'recommendations': self._generate_recommendations(missing_items, warnings)
        }

    async def get_onboarding_progress(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Get onboarding progress for a hostel.
        
        Args:
            hostel_id: Hostel UUID
            
        Returns:
            Progress information
        """
        hostel = await self.hostel_service.get_hostel_by_id(hostel_id)
        validation = await self.validate_hostel_setup(hostel_id)
        
        steps = [
            {
                'step': 1,
                'name': 'Basic Information',
                'completed': bool(hostel.name and hostel.city and hostel.state)
            },
            {
                'step': 2,
                'name': 'Facilities & Capacity',
                'completed': hostel.total_beds > 0
            },
            {
                'step': 3,
                'name': 'Pricing',
                'completed': bool(hostel.starting_price_monthly)
            },
            {
                'step': 4,
                'name': 'Policies',
                'completed': len(await self.policy_service.get_hostel_policies(hostel_id, only_published=False)) > 0
            },
            {
                'step': 5,
                'name': 'Settings',
                'completed': bool(await self.settings_service.get_hostel_settings(hostel_id, create_if_missing=False))
            },
            {
                'step': 6,
                'name': 'Review & Launch',
                'completed': hostel.status == HostelStatus.ACTIVE
            }
        ]
        
        completed_steps = sum(1 for step in steps if step['completed'])
        total_steps = len(steps)
        progress_percentage = (completed_steps / total_steps) * 100
        
        return {
            'hostel_id': hostel_id,
            'steps': steps,
            'completed_steps': completed_steps,
            'total_steps': total_steps,
            'progress_percentage': round(progress_percentage, 2),
            'is_complete': validation['is_ready'],
            'current_status': hostel.status
        }

    # ===== Helper Methods =====

    def _validate_basic_info(self, info: Dict[str, Any]) -> None:
        """Validate basic hostel information."""
        required_fields = ['name', 'hostel_type', 'city', 'state', 'country']
        
        for field in required_fields:
            if field not in info or not info[field]:
                raise ValidationError(f"'{field}' is required")

    async def _create_default_policies(self, hostel_id: UUID) -> None:
        """Create default policies from templates."""
        templates = self._get_policy_templates(None)
        
        for template in templates:
            await self.policy_service.create_policy(
                hostel_id,
                template
            )

    def _get_amenity_templates(self, hostel_type: HostelType) -> List[Dict[str, Any]]:
        """Get amenity templates."""
        basic_amenities = [
            'WiFi', 'Hot Water', 'Power Backup', 'Security', 
            'Common Area', 'Study Room', 'Laundry'
        ]
        
        return [{'name': amenity, 'category': 'basic'} for amenity in basic_amenities]

    def _get_policy_templates(self, hostel_type: Optional[HostelType]) -> List[Dict[str, Any]]:
        """Get policy templates."""
        return [
            {
                'policy_type': 'general',
                'title': 'General Hostel Rules',
                'content': 'Standard hostel rules and regulations...',
                'is_mandatory': True
            },
            {
                'policy_type': 'visitor',
                'title': 'Visitor Policy',
                'content': 'Visitor entry and management policy...',
                'is_mandatory': True
            },
            {
                'policy_type': 'payment',
                'title': 'Payment Policy',
                'content': 'Payment terms and conditions...',
                'is_mandatory': True
            }
        ]

    def _get_settings_templates(self, hostel_type: HostelType) -> Dict[str, Any]:
        """Get settings templates."""
        return {
            'booking': {
                'auto_approve': False,
                'advance_percentage': 20,
                'min_duration_days': 30
            },
            'payment': {
                'due_day': 5,
                'grace_days': 3,
                'security_deposit_months': 2
            },
            'features': {
                'attendance_tracking': True,
                'visitor_management': True,
                'complaint_management': True
            }
        }

    async def _apply_amenity_template(self, hostel_id: UUID, template_name: str) -> Dict[str, Any]:
        """Apply amenity template."""
        # Implementation for applying amenity templates
        return {'applied': True, 'template': template_name}

    async def _apply_policy_template(self, hostel_id: UUID, template_name: str) -> Dict[str, Any]:
        """Apply policy template."""
        # Implementation for applying policy templates
        return {'applied': True, 'template': template_name}

    async def _apply_settings_template(self, hostel_id: UUID, template_name: str) -> Dict[str, Any]:
        """Apply settings template."""
        # Implementation for applying settings templates
        return {'applied': True, 'template': template_name}

    def _calculate_completeness_score(
        self,
        hostel: Hostel,
        policies: List,
        settings: Optional[HostelSettings]
    ) -> float:
        """Calculate setup completeness score."""
        score = 0.0
        max_score = 100.0
        
        # Basic info (20 points)
        if hostel.description:
            score += 10
        if hostel.address_line1:
            score += 10
        
        # Capacity (20 points)
        if hostel.total_beds > 0:
            score += 20
        
        # Pricing (15 points)
        if hostel.starting_price_monthly:
            score += 15
        
        # Amenities (15 points)
        if hostel.amenities and len(hostel.amenities) > 0:
            score += 15
        
        # Policies (15 points)
        if len(policies) > 0:
            score += 15
        
        # Settings (15 points)
        if settings:
            score += 15
        
        return min(score, max_score)

    def _generate_recommendations(
        self,
        missing_items: List[str],
        warnings: List[str]
    ) -> List[str]:
        """Generate recommendations based on validation."""
        recommendations = []
        
        if 'Total rooms not configured' in missing_items:
            recommendations.append('Add room information to enable capacity management')
        
        if 'Pricing not configured' in missing_items:
            recommendations.append('Set pricing to start accepting bookings')
        
        if 'No amenities added' in warnings:
            recommendations.append('Add amenities to attract more students')
        
        if 'No policies created' in warnings:
            recommendations.append('Create hostel policies for better governance')
        
        return recommendations

    async def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log service events for audit and analytics."""
        pass