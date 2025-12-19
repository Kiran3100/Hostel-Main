"""
Hostel repository with comprehensive hostel management capabilities.
"""

from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, date
from sqlalchemy import and_, or_, func, desc, asc, text
from sqlalchemy.orm import selectinload, joinedload

from app.models.hostel.hostel import Hostel
from app.models.base.enums import HostelStatus, HostelType
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.specifications import Specification
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.pagination import PaginationRequest, PaginationResult
from app.repositories.base.filtering import FilterCriteria


class ActiveHostelsSpecification(Specification[Hostel]):
    """Specification for active hostels."""
    
    def __init__(self, include_featured_only: bool = False):
        self.include_featured_only = include_featured_only
    
    def is_satisfied_by(self, entity: Hostel) -> bool:
        base_condition = entity.is_active and entity.status == HostelStatus.ACTIVE
        if self.include_featured_only:
            return base_condition and entity.is_featured
        return base_condition
    
    def to_sql_condition(self):
        base_condition = and_(
            Hostel.is_active == True,
            Hostel.status == HostelStatus.ACTIVE
        )
        if self.include_featured_only:
            return and_(base_condition, Hostel.is_featured == True)
        return base_condition


class AvailableHostelsSpecification(Specification[Hostel]):
    """Specification for hostels with available beds."""
    
    def __init__(self, required_beds: int = 1):
        self.required_beds = required_beds
    
    def is_satisfied_by(self, entity: Hostel) -> bool:
        return entity.available_beds >= self.required_beds
    
    def to_sql_condition(self):
        return Hostel.available_beds >= self.required_beds


class LocationBasedSpecification(Specification[Hostel]):
    """Specification for location-based hostel search."""
    
    def __init__(self, city: Optional[str] = None, state: Optional[str] = None, 
                 lat: Optional[float] = None, lng: Optional[float] = None, 
                 radius_km: Optional[float] = None):
        self.city = city
        self.state = state
        self.lat = lat
        self.lng = lng
        self.radius_km = radius_km
    
    def to_sql_condition(self):
        conditions = []
        
        if self.city:
            conditions.append(Hostel.city.ilike(f"%{self.city}%"))
        if self.state:
            conditions.append(Hostel.state.ilike(f"%{self.state}%"))
        
        if self.lat and self.lng and self.radius_km:
            # Haversine formula for distance calculation
            distance_formula = func.acos(
                func.cos(func.radians(self.lat)) *
                func.cos(func.radians(Hostel.latitude)) *
                func.cos(func.radians(Hostel.longitude) - func.radians(self.lng)) +
                func.sin(func.radians(self.lat)) *
                func.sin(func.radians(Hostel.latitude))
            ) * 6371  # Earth's radius in km
            
            conditions.append(distance_formula <= self.radius_km)
        
        return and_(*conditions) if conditions else text("1=1")


class PriceRangeSpecification(Specification[Hostel]):
    """Specification for price range filtering."""
    
    def __init__(self, min_price: Optional[Decimal] = None, max_price: Optional[Decimal] = None):
        self.min_price = min_price
        self.max_price = max_price
    
    def to_sql_condition(self):
        conditions = []
        if self.min_price:
            conditions.append(Hostel.starting_price_monthly >= self.min_price)
        if self.max_price:
            conditions.append(Hostel.starting_price_monthly <= self.max_price)
        return and_(*conditions) if conditions else text("1=1")


class HostelRepository(BaseRepository[Hostel]):
    """
    Comprehensive hostel repository with advanced search, analytics, and management capabilities.
    """
    
    def __init__(self, session):
        super().__init__(session, Hostel)
    
    # ===== Core Operations =====
    
    async def create_hostel(self, hostel_data: Dict[str, Any], audit_context: Optional[Dict] = None) -> Hostel:
        """Create a new hostel with validation and audit logging."""
        # Validate slug uniqueness
        existing = await self.find_by_slug(hostel_data.get("slug"))
        if existing:
            raise ValueError(f"Hostel with slug '{hostel_data['slug']}' already exists")
        
        hostel = await self.create(hostel_data, audit_context)
        await self.session.flush()  # Ensure ID is generated
        
        # Initialize capacity stats
        hostel.update_capacity_stats()
        return hostel
    
    async def find_by_slug(self, slug: str) -> Optional[Hostel]:
        """Find hostel by URL slug."""
        return await self.find_one_by_criteria({"slug": slug})
    
    async def update_capacity_stats(self, hostel_id: UUID) -> Hostel:
        """Update capacity statistics for a hostel."""
        hostel = await self.get_by_id(hostel_id)
        if not hostel:
            raise ValueError(f"Hostel {hostel_id} not found")
        
        hostel.update_capacity_stats()
        await self.session.commit()
        return hostel
    
    # ===== Advanced Search =====
    
    async def search_hostels(
        self,
        filters: FilterCriteria,
        pagination: PaginationRequest,
        include_stats: bool = True
    ) -> PaginationResult[Hostel]:
        """
        Advanced hostel search with comprehensive filtering and sorting.
        """
        query_builder = QueryBuilder(Hostel)
        
        # Apply specifications based on filters
        if filters.get("is_active", True):
            spec = ActiveHostelsSpecification(filters.get("featured_only", False))
            query_builder = query_builder.where(spec.to_sql_condition())
        
        if filters.get("has_availability"):
            required_beds = filters.get("required_beds", 1)
            spec = AvailableHostelsSpecification(required_beds)
            query_builder = query_builder.where(spec.to_sql_condition())
        
        # Location filtering
        if any(k in filters for k in ["city", "state", "lat", "lng", "radius"]):
            location_spec = LocationBasedSpecification(
                city=filters.get("city"),
                state=filters.get("state"),
                lat=filters.get("lat"),
                lng=filters.get("lng"),
                radius_km=filters.get("radius")
            )
            query_builder = query_builder.where(location_spec.to_sql_condition())
        
        # Price range filtering
        if filters.get("min_price") or filters.get("max_price"):
            price_spec = PriceRangeSpecification(
                min_price=filters.get("min_price"),
                max_price=filters.get("max_price")
            )
            query_builder = query_builder.where(price_spec.to_sql_condition())
        
        # Hostel type filtering
        if filters.get("hostel_type"):
            query_builder = query_builder.where(Hostel.hostel_type == filters["hostel_type"])
        
        # Amenities filtering
        if filters.get("amenities"):
            amenities = filters["amenities"]
            query_builder = query_builder.where(Hostel.amenities.contains(amenities))
        
        # Rating filtering
        if filters.get("min_rating"):
            query_builder = query_builder.where(Hostel.average_rating >= filters["min_rating"])
        
        # Sorting
        sort_by = filters.get("sort_by", "created_at")
        sort_order = filters.get("sort_order", "desc")
        
        if sort_by == "price":
            order_field = Hostel.starting_price_monthly
        elif sort_by == "rating":
            order_field = Hostel.average_rating
        elif sort_by == "occupancy":
            order_field = Hostel.occupancy_percentage
        elif sort_by == "name":
            order_field = Hostel.name
        else:
            order_field = Hostel.created_at
        
        if sort_order == "desc":
            query_builder = query_builder.order_by(desc(order_field))
        else:
            query_builder = query_builder.order_by(asc(order_field))
        
        # Include related data if needed
        if include_stats:
            query_builder = query_builder.options(
                selectinload(Hostel.rooms),
                selectinload(Hostel.amenity_details)
            )
        
        return await self.paginate(query_builder.build(), pagination)
    
    async def find_nearby_hostels(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        hostel_type: Optional[HostelType] = None,
        limit: int = 20
    ) -> List[Tuple[Hostel, float]]:
        """
        Find nearby hostels with distance calculation.
        Returns list of tuples (hostel, distance_km).
        """
        # Haversine distance formula
        distance_formula = func.acos(
            func.cos(func.radians(latitude)) *
            func.cos(func.radians(Hostel.latitude)) *
            func.cos(func.radians(Hostel.longitude) - func.radians(longitude)) +
            func.sin(func.radians(latitude)) *
            func.sin(func.radians(Hostel.latitude))
        ) * 6371  # Earth's radius in km
        
        query = (
            self.session.query(Hostel, distance_formula.label("distance"))
            .filter(
                and_(
                    Hostel.is_active == True,
                    Hostel.status == HostelStatus.ACTIVE,
                    distance_formula <= radius_km
                )
            )
            .order_by("distance")
            .limit(limit)
        )
        
        if hostel_type:
            query = query.filter(Hostel.hostel_type == hostel_type)
        
        results = await query.all()
        return [(hostel, float(distance)) for hostel, distance in results]
    
    # ===== Recommendations =====
    
    async def get_recommended_hostels(
        self,
        user_preferences: Dict[str, Any],
        limit: int = 10
    ) -> List[Hostel]:
        """
        Get recommended hostels based on user preferences and behavior.
        """
        query_builder = QueryBuilder(Hostel)
        
        # Base active hostels
        query_builder = query_builder.where(
            and_(
                Hostel.is_active == True,
                Hostel.status == HostelStatus.ACTIVE,
                Hostel.has_availability == True
            )
        )
        
        # Apply preference-based filtering
        if user_preferences.get("preferred_price_range"):
            min_price, max_price = user_preferences["preferred_price_range"]
            query_builder = query_builder.where(
                and_(
                    Hostel.starting_price_monthly >= min_price,
                    Hostel.starting_price_monthly <= max_price
                )
            )
        
        if user_preferences.get("preferred_hostel_type"):
            query_builder = query_builder.where(
                Hostel.hostel_type == user_preferences["preferred_hostel_type"]
            )
        
        if user_preferences.get("required_amenities"):
            amenities = user_preferences["required_amenities"]
            query_builder = query_builder.where(Hostel.amenities.contains(amenities))
        
        # Preference-based scoring (simplified)
        score_case = func.case(
            (Hostel.is_featured == True, 10),
            else_=0
        ) + func.case(
            (Hostel.average_rating >= 4.0, 8),
            (Hostel.average_rating >= 3.5, 5),
            else_=0
        ) + func.case(
            (Hostel.occupancy_percentage.between(70, 90), 5),
            else_=0
        )
        
        query_builder = query_builder.order_by(desc(score_case), desc(Hostel.average_rating))
        
        return await query_builder.limit(limit).all()
    
    async def get_featured_hostels(self, limit: int = 6) -> List[Hostel]:
        """Get featured hostels for homepage display."""
        return await self.find_by_criteria(
            {
                "is_featured": True,
                "is_active": True,
                "status": HostelStatus.ACTIVE
            },
            limit=limit,
            order_by=[desc(Hostel.average_rating), desc(Hostel.created_at)]
        )
    
    # ===== Analytics Queries =====
    
    async def get_occupancy_statistics(self, date_range: Optional[Tuple[date, date]] = None) -> Dict[str, Any]:
        """Get comprehensive occupancy statistics."""
        query = self.session.query(
            func.count(Hostel.id).label("total_hostels"),
            func.sum(Hostel.total_beds).label("total_beds"),
            func.sum(Hostel.occupied_beds).label("total_occupied"),
            func.avg(Hostel.occupancy_percentage).label("avg_occupancy"),
            func.max(Hostel.occupancy_percentage).label("max_occupancy"),
            func.min(Hostel.occupancy_percentage).label("min_occupancy")
        ).filter(
            and_(
                Hostel.is_active == True,
                Hostel.status == HostelStatus.ACTIVE
            )
        )
        
        result = await query.first()
        
        return {
            "total_hostels": result.total_hostels or 0,
            "total_beds": result.total_beds or 0,
            "total_occupied": result.total_occupied or 0,
            "total_available": (result.total_beds or 0) - (result.total_occupied or 0),
            "average_occupancy": float(result.avg_occupancy or 0),
            "max_occupancy": float(result.max_occupancy or 0),
            "min_occupancy": float(result.min_occupancy or 0),
            "overall_occupancy": float((result.total_occupied or 0) / max(result.total_beds or 1, 1) * 100)
        }
    
    async def get_pricing_analysis(self) -> Dict[str, Any]:
        """Get pricing analysis across all hostels."""
        query = self.session.query(
            func.avg(Hostel.starting_price_monthly).label("avg_price"),
            func.min(Hostel.starting_price_monthly).label("min_price"),
            func.max(Hostel.starting_price_monthly).label("max_price"),
            func.percentile_cont(0.25).within_group(Hostel.starting_price_monthly).label("q1_price"),
            func.percentile_cont(0.5).within_group(Hostel.starting_price_monthly).label("median_price"),
            func.percentile_cont(0.75).within_group(Hostel.starting_price_monthly).label("q3_price")
        ).filter(
            and_(
                Hostel.is_active == True,
                Hostel.starting_price_monthly.isnot(None)
            )
        )
        
        result = await query.first()
        
        return {
            "average_price": float(result.avg_price or 0),
            "min_price": float(result.min_price or 0),
            "max_price": float(result.max_price or 0),
            "q1_price": float(result.q1_price or 0),
            "median_price": float(result.median_price or 0),
            "q3_price": float(result.q3_price or 0)
        }
    
    async def get_performance_metrics(self, hostel_id: UUID) -> Dict[str, Any]:
        """Get comprehensive performance metrics for a hostel."""
        hostel = await self.get_by_id(hostel_id)
        if not hostel:
            raise ValueError(f"Hostel {hostel_id} not found")
        
        # Calculate performance score based on multiple factors
        occupancy_score = min(float(hostel.occupancy_percentage), 100) * 0.3
        rating_score = min(float(hostel.average_rating) * 20, 100) * 0.25  # Convert 5-star to 100-point
        availability_score = (hostel.available_beds / max(hostel.total_beds, 1)) * 100 * 0.2
        revenue_efficiency = min(float(hostel.total_revenue_this_month) / max(hostel.total_beds, 1), 10000) / 100 * 0.15
        complaint_score = max(100 - (hostel.pending_complaints * 10), 0) * 0.1
        
        overall_score = occupancy_score + rating_score + availability_score + revenue_efficiency + complaint_score
        
        return {
            "hostel_id": str(hostel_id),
            "hostel_name": hostel.name,
            "overall_score": round(overall_score, 2),
            "occupancy_score": round(occupancy_score, 2),
            "rating_score": round(rating_score, 2),
            "availability_score": round(availability_score, 2),
            "revenue_efficiency": round(revenue_efficiency, 2),
            "complaint_score": round(complaint_score, 2),
            "current_metrics": {
                "occupancy_percentage": float(hostel.occupancy_percentage),
                "average_rating": float(hostel.average_rating),
                "available_beds": hostel.available_beds,
                "total_beds": hostel.total_beds,
                "revenue_this_month": float(hostel.total_revenue_this_month),
                "pending_complaints": hostel.pending_complaints
            }
        }
    
    # ===== Bulk Operations =====
    
    async def bulk_update_occupancy(self, updates: List[Dict[str, Any]]) -> List[Hostel]:
        """Bulk update occupancy data for multiple hostels."""
        hostel_ids = [update["hostel_id"] for update in updates]
        hostels = await self.find_by_ids(hostel_ids)
        hostel_dict = {str(h.id): h for h in hostels}
        
        updated_hostels = []
        for update in updates:
            hostel_id = str(update["hostel_id"])
            if hostel_id in hostel_dict:
                hostel = hostel_dict[hostel_id]
                hostel.occupied_beds = update.get("occupied_beds", hostel.occupied_beds)
                hostel.total_beds = update.get("total_beds", hostel.total_beds)
                hostel.update_capacity_stats()
                updated_hostels.append(hostel)
        
        await self.session.commit()
        return updated_hostels
    
    async def bulk_update_pricing(self, price_updates: Dict[UUID, Decimal]) -> List[Hostel]:
        """Bulk update pricing for multiple hostels."""
        hostel_ids = list(price_updates.keys())
        hostels = await self.find_by_ids(hostel_ids)
        
        for hostel in hostels:
            if hostel.id in price_updates:
                hostel.starting_price_monthly = price_updates[hostel.id]
        
        await self.session.commit()
        return hostels
    
    # ===== Specialized Queries =====
    
    async def find_hostels_needing_attention(self) -> List[Hostel]:
        """Find hostels that need immediate attention."""
        return await self.find_by_criteria({
            "status": HostelStatus.ACTIVE,
            "is_active": True
        }, custom_filter=or_(
            Hostel.pending_complaints > 5,
            Hostel.pending_maintenance > 10,
            Hostel.occupancy_percentage < 30,
            Hostel.outstanding_payments > 50000
        ))
    
    async def find_high_performing_hostels(self, limit: int = 10) -> List[Hostel]:
        """Find top performing hostels based on multiple criteria."""
        return await self.find_by_criteria(
            {
                "status": HostelStatus.ACTIVE,
                "is_active": True
            },
            custom_filter=and_(
                Hostel.occupancy_percentage >= 80,
                Hostel.average_rating >= 4.0,
                Hostel.pending_complaints <= 2
            ),
            order_by=[
                desc(Hostel.occupancy_percentage),
                desc(Hostel.average_rating),
                asc(Hostel.pending_complaints)
            ],
            limit=limit
        )
    
    async def find_hostels_with_low_occupancy(self, threshold: float = 50.0) -> List[Hostel]:
        """Find hostels with occupancy below threshold."""
        return await self.find_by_criteria(
            {
                "status": HostelStatus.ACTIVE,
                "is_active": True
            },
            custom_filter=Hostel.occupancy_percentage < threshold,
            order_by=[asc(Hostel.occupancy_percentage)]
        )
    
    # ===== Cache Management =====
    
    async def get_cached_hostel_stats(self, hostel_id: UUID) -> Optional[Dict[str, Any]]:
        """Get cached hostel statistics."""
        cache_key = f"hostel_stats:{hostel_id}"
        return await self.get_from_cache(cache_key)
    
    async def cache_hostel_stats(self, hostel_id: UUID, stats: Dict[str, Any], ttl: int = 300):
        """Cache hostel statistics with TTL."""
        cache_key = f"hostel_stats:{hostel_id}"
        await self.set_cache(cache_key, stats, ttl)
    
    async def invalidate_hostel_cache(self, hostel_id: UUID):
        """Invalidate all cache entries for a hostel."""
        patterns = [
            f"hostel_stats:{hostel_id}",
            f"hostel_details:{hostel_id}",
            f"hostel_analytics:{hostel_id}*"
        ]
        await self.invalidate_cache_patterns(patterns)