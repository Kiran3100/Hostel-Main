# --- File: C:\Hostel-Main\app\services\hostel\hostel_service.py ---
"""
Hostel service with comprehensive business logic and orchestration.
"""

from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hostel.hostel import Hostel
from app.models.base.enums import HostelStatus, HostelType
from app.repositories.hostel.hostel_repository import HostelRepository
from app.repositories.hostel.hostel_aggregate_repository import HostelAggregateRepository
from app.repositories.hostel.hostel_settings_repository import HostelSettingsRepository
from app.repositories.base.pagination import PaginationRequest, PaginationResult
from app.repositories.base.filtering import FilterCriteria
from app.core.exceptions import (
    HostelNotFoundError,
    ValidationError,
    BusinessRuleViolationError,
    DuplicateResourceError
)
from app.services.base.base_service import BaseService
from app.utils.slug_generator import generate_slug
from app.utils.validators import validate_coordinates, validate_price_range


class HostelService(BaseService):
    """
    Hostel service with comprehensive business logic.
    
    Handles all hostel-related operations including CRUD,
    search, recommendations, capacity management, and analytics.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.hostel_repo = HostelRepository(session)
        self.aggregate_repo = HostelAggregateRepository(session)
        self.settings_repo = HostelSettingsRepository(session)

    # ===== CRUD Operations =====

    async def create_hostel(
        self,
        hostel_data: Dict[str, Any],
        created_by: Optional[UUID] = None
    ) -> Hostel:
        """
        Create a new hostel with validation and default settings.
        
        Args:
            hostel_data: Hostel information
            created_by: User ID creating the hostel
            
        Returns:
            Created Hostel instance
            
        Raises:
            ValidationError: If data validation fails
            DuplicateResourceError: If hostel with slug already exists
        """
        # Validate required fields
        self._validate_hostel_data(hostel_data)
        
        # Generate slug if not provided
        if not hostel_data.get('slug'):
            hostel_data['slug'] = generate_slug(hostel_data['name'])
        
        # Validate slug uniqueness
        existing = await self.hostel_repo.find_by_slug(hostel_data['slug'])
        if existing:
            raise DuplicateResourceError(
                f"Hostel with slug '{hostel_data['slug']}' already exists"
            )
        
        # Validate coordinates if provided
        if hostel_data.get('latitude') and hostel_data.get('longitude'):
            if not validate_coordinates(
                hostel_data['latitude'], 
                hostel_data['longitude']
            ):
                raise ValidationError("Invalid geographic coordinates")
        
        # Set default values
        hostel_data.setdefault('is_active', True)
        hostel_data.setdefault('is_public', False)  # Needs approval
        hostel_data.setdefault('is_featured', False)
        hostel_data.setdefault('is_verified', False)
        hostel_data.setdefault('status', HostelStatus.ACTIVE)
        hostel_data.setdefault('currency', 'INR')
        hostel_data.setdefault('average_rating', Decimal('0.00'))
        hostel_data.setdefault('total_reviews', 0)
        hostel_data.setdefault('occupancy_percentage', Decimal('0.00'))
        
        # Create hostel
        hostel = await self.hostel_repo.create_hostel(
            hostel_data,
            audit_context={'created_by': created_by}
        )
        
        # Create default settings
        await self.settings_repo.create_default_settings(hostel.id)
        
        # Log event
        await self._log_event('hostel_created', {
            'hostel_id': hostel.id,
            'name': hostel.name,
            'created_by': created_by
        })
        
        return hostel

    async def get_hostel_by_id(
        self,
        hostel_id: UUID,
        include_details: bool = False
    ) -> Hostel:
        """
        Get hostel by ID with optional detailed information.
        
        Args:
            hostel_id: Hostel UUID
            include_details: Whether to include all related data
            
        Returns:
            Hostel instance
            
        Raises:
            HostelNotFoundError: If hostel not found
        """
        if include_details:
            hostel = await self.aggregate_repo.get_hostel_with_complete_details(
                hostel_id
            )
        else:
            hostel = await self.hostel_repo.get_by_id(hostel_id)
        
        if not hostel:
            raise HostelNotFoundError(f"Hostel {hostel_id} not found")
        
        return hostel

    async def get_hostel_by_slug(self, slug: str) -> Hostel:
        """
        Get hostel by URL slug.
        
        Args:
            slug: Hostel slug
            
        Returns:
            Hostel instance
            
        Raises:
            HostelNotFoundError: If hostel not found
        """
        hostel = await self.hostel_repo.find_by_slug(slug)
        if not hostel:
            raise HostelNotFoundError(f"Hostel with slug '{slug}' not found")
        
        return hostel

    async def update_hostel(
        self,
        hostel_id: UUID,
        update_data: Dict[str, Any],
        updated_by: Optional[UUID] = None
    ) -> Hostel:
        """
        Update hostel information.
        
        Args:
            hostel_id: Hostel UUID
            update_data: Fields to update
            updated_by: User ID performing update
            
        Returns:
            Updated Hostel instance
            
        Raises:
            HostelNotFoundError: If hostel not found
            ValidationError: If validation fails
        """
        hostel = await self.get_hostel_by_id(hostel_id)
        
        # Validate update data
        if 'slug' in update_data and update_data['slug'] != hostel.slug:
            existing = await self.hostel_repo.find_by_slug(update_data['slug'])
            if existing:
                raise DuplicateResourceError(
                    f"Slug '{update_data['slug']}' already in use"
                )
        
        if 'starting_price_monthly' in update_data:
            if not validate_price_range(update_data['starting_price_monthly']):
                raise ValidationError("Invalid price value")
        
        # Perform update
        updated_hostel = await self.hostel_repo.update(
            hostel_id,
            update_data,
            audit_context={'updated_by': updated_by}
        )
        
        # Invalidate cache
        await self.hostel_repo.invalidate_hostel_cache(hostel_id)
        
        # Log event
        await self._log_event('hostel_updated', {
            'hostel_id': hostel_id,
            'updated_fields': list(update_data.keys()),
            'updated_by': updated_by
        })
        
        return updated_hostel

    async def delete_hostel(
        self,
        hostel_id: UUID,
        deleted_by: Optional[UUID] = None,
        soft_delete: bool = True
    ) -> bool:
        """
        Delete or deactivate a hostel.
        
        Args:
            hostel_id: Hostel UUID
            deleted_by: User ID performing deletion
            soft_delete: Whether to soft delete (deactivate) or hard delete
            
        Returns:
            True if successful
            
        Raises:
            HostelNotFoundError: If hostel not found
            BusinessRuleViolationError: If hostel has active students
        """
        hostel = await self.get_hostel_by_id(hostel_id)
        
        # Check for active students
        if hostel.active_students > 0:
            raise BusinessRuleViolationError(
                f"Cannot delete hostel with {hostel.active_students} active students"
            )
        
        if soft_delete:
            # Soft delete - deactivate
            await self.hostel_repo.update(hostel_id, {
                'is_active': False,
                'status': HostelStatus.INACTIVE
            })
        else:
            # Hard delete
            await self.hostel_repo.delete(hostel_id)
        
        # Invalidate cache
        await self.hostel_repo.invalidate_hostel_cache(hostel_id)
        
        # Log event
        await self._log_event('hostel_deleted', {
            'hostel_id': hostel_id,
            'soft_delete': soft_delete,
            'deleted_by': deleted_by
        })
        
        return True

    # ===== Search and Discovery =====

    async def search_hostels(
        self,
        filters: FilterCriteria,
        pagination: PaginationRequest,
        user_id: Optional[UUID] = None
    ) -> PaginationResult[Hostel]:
        """
        Search hostels with comprehensive filtering and pagination.
        
        Args:
            filters: Search filters
            pagination: Pagination parameters
            user_id: Optional user ID for personalization
            
        Returns:
            Paginated hostel results
        """
        # Add default filters
        filters.setdefault('is_active', True)
        filters.setdefault('is_public', True)
        
        # Perform search
        results = await self.hostel_repo.search_hostels(
            filters,
            pagination,
            include_stats=True
        )
        
        # Log search for analytics
        await self._log_event('hostel_search', {
            'filters': filters,
            'results_count': results.total,
            'user_id': user_id
        })
        
        return results

    async def find_nearby_hostels(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        hostel_type: Optional[HostelType] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Find hostels near a geographic location.
        
        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_km: Search radius in kilometers
            hostel_type: Optional hostel type filter
            limit: Maximum results
            
        Returns:
            List of hostels with distance information
        """
        if not validate_coordinates(latitude, longitude):
            raise ValidationError("Invalid geographic coordinates")
        
        results = await self.hostel_repo.find_nearby_hostels(
            latitude,
            longitude,
            radius_km,
            hostel_type,
            limit
        )
        
        return [
            {
                'hostel': hostel,
                'distance_km': distance,
                'distance_formatted': f"{distance:.1f} km"
            }
            for hostel, distance in results
        ]

    async def get_recommended_hostels(
        self,
        user_preferences: Dict[str, Any],
        limit: int = 10
    ) -> List[Hostel]:
        """
        Get personalized hostel recommendations.
        
        Args:
            user_preferences: User preferences and requirements
            limit: Maximum recommendations
            
        Returns:
            List of recommended hostels
        """
        return await self.hostel_repo.get_recommended_hostels(
            user_preferences,
            limit
        )

    async def get_featured_hostels(self, limit: int = 6) -> List[Hostel]:
        """Get featured hostels for homepage display."""
        return await self.hostel_repo.get_featured_hostels(limit)

    # ===== Capacity Management =====

    async def update_capacity(
        self,
        hostel_id: UUID,
        total_rooms: Optional[int] = None,
        total_beds: Optional[int] = None,
        occupied_beds: Optional[int] = None
    ) -> Hostel:
        """
        Update hostel capacity information.
        
        Args:
            hostel_id: Hostel UUID
            total_rooms: Total number of rooms
            total_beds: Total number of beds
            occupied_beds: Currently occupied beds
            
        Returns:
            Updated Hostel instance
        """
        hostel = await self.get_hostel_by_id(hostel_id)
        
        update_data = {}
        if total_rooms is not None:
            if total_rooms < 0:
                raise ValidationError("Total rooms cannot be negative")
            update_data['total_rooms'] = total_rooms
        
        if total_beds is not None:
            if total_beds < 0:
                raise ValidationError("Total beds cannot be negative")
            update_data['total_beds'] = total_beds
        
        if occupied_beds is not None:
            if occupied_beds < 0:
                raise ValidationError("Occupied beds cannot be negative")
            if occupied_beds > (total_beds or hostel.total_beds):
                raise ValidationError(
                    "Occupied beds cannot exceed total beds"
                )
            update_data['occupied_beds'] = occupied_beds
        
        # Update hostel
        updated_hostel = await self.hostel_repo.update(hostel_id, update_data)
        
        # Recalculate occupancy
        await self.hostel_repo.update_capacity_stats(hostel_id)
        
        return updated_hostel

    async def check_availability(
        self,
        hostel_id: UUID,
        required_beds: int = 1
    ) -> Dict[str, Any]:
        """
        Check bed availability in a hostel.
        
        Args:
            hostel_id: Hostel UUID
            required_beds: Number of beds required
            
        Returns:
            Availability information
        """
        hostel = await self.get_hostel_by_id(hostel_id)
        
        available = hostel.can_accommodate(required_beds)
        
        return {
            'hostel_id': hostel_id,
            'available': available,
            'required_beds': required_beds,
            'available_beds': hostel.available_beds,
            'total_beds': hostel.total_beds,
            'occupied_beds': hostel.occupied_beds,
            'occupancy_percentage': float(hostel.occupancy_percentage)
        }

    # ===== Status Management =====

    async def activate_hostel(
        self,
        hostel_id: UUID,
        activated_by: Optional[UUID] = None
    ) -> Hostel:
        """Activate a hostel."""
        return await self.hostel_repo.update(
            hostel_id,
            {
                'is_active': True,
                'status': HostelStatus.ACTIVE
            },
            audit_context={'activated_by': activated_by}
        )

    async def deactivate_hostel(
        self,
        hostel_id: UUID,
        reason: Optional[str] = None,
        deactivated_by: Optional[UUID] = None
    ) -> Hostel:
        """Deactivate a hostel."""
        return await self.hostel_repo.update(
            hostel_id,
            {
                'is_active': False,
                'status': HostelStatus.INACTIVE
            },
            audit_context={
                'deactivated_by': deactivated_by,
                'reason': reason
            }
        )

    async def verify_hostel(
        self,
        hostel_id: UUID,
        verified_by: UUID
    ) -> Hostel:
        """Mark hostel as verified."""
        return await self.hostel_repo.update(
            hostel_id,
            {'is_verified': True},
            audit_context={'verified_by': verified_by}
        )

    async def feature_hostel(
        self,
        hostel_id: UUID,
        featured: bool = True
    ) -> Hostel:
        """Set hostel featured status."""
        return await self.hostel_repo.update(
            hostel_id,
            {'is_featured': featured}
        )

    # ===== Analytics and Reporting =====

    async def get_hostel_dashboard(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """Get comprehensive dashboard data for a hostel."""
        return await self.aggregate_repo.get_hostel_dashboard_data(hostel_id)

    async def get_performance_metrics(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """Get performance metrics for a hostel."""
        return await self.hostel_repo.get_performance_metrics(hostel_id)

    async def get_occupancy_statistics(
        self,
        date_range: Optional[Tuple[date, date]] = None
    ) -> Dict[str, Any]:
        """Get system-wide occupancy statistics."""
        return await self.hostel_repo.get_occupancy_statistics(date_range)

    async def get_pricing_analysis(self) -> Dict[str, Any]:
        """Get pricing analysis across all hostels."""
        return await self.hostel_repo.get_pricing_analysis()

    # ===== Bulk Operations =====

    async def bulk_update_metrics(
        self,
        hostel_ids: Optional[List[UUID]] = None
    ) -> Dict[str, Any]:
        """Bulk update metrics for multiple hostels."""
        return await self.aggregate_repo.bulk_update_metrics(hostel_ids)

    async def find_hostels_needing_attention(self) -> List[Hostel]:
        """Find hostels requiring immediate attention."""
        return await self.hostel_repo.find_hostels_needing_attention()

    # ===== Helper Methods =====

    def _validate_hostel_data(self, data: Dict[str, Any]) -> None:
        """Validate hostel data."""
        required_fields = ['name', 'hostel_type', 'city', 'state', 'country']
        
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError(f"'{field}' is required")
        
        # Validate hostel type
        if data['hostel_type'] not in [t.value for t in HostelType]:
            raise ValidationError(f"Invalid hostel type: {data['hostel_type']}")
        
        # Validate pricing if provided
        if 'starting_price_monthly' in data:
            if not validate_price_range(data['starting_price_monthly']):
                raise ValidationError("Invalid price value")

    async def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log service events for audit and analytics."""
        # Implementation depends on your logging/event system
        pass