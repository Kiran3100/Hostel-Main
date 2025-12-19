"""
User Address Repository - Address management with geolocation support.
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session
from decimal import Decimal
import math

from app.models.user import UserAddress
from app.repositories.base.base_repository import BaseRepository


class UserAddressRepository(BaseRepository[UserAddress]):
    """
    Repository for UserAddress entity with geolocation,
    verification, and spatial query support.
    """

    def __init__(self, db: Session):
        super().__init__(UserAddress, db)

    # ==================== Basic Address Operations ====================

    def find_by_user_id(self, user_id: str) -> List[UserAddress]:
        """
        Find all addresses for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of addresses
        """
        return self.db.query(UserAddress).filter(
            UserAddress.user_id == user_id,
            UserAddress.is_active == True
        ).order_by(UserAddress.is_primary.desc(), UserAddress.created_at).all()

    def find_primary_address(self, user_id: str) -> Optional[UserAddress]:
        """
        Find primary address for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Primary UserAddress or None
        """
        return self.db.query(UserAddress).filter(
            UserAddress.user_id == user_id,
            UserAddress.is_primary == True,
            UserAddress.is_active == True
        ).first()

    def find_by_type(
        self, 
        user_id: str, 
        address_type: str
    ) -> Optional[UserAddress]:
        """
        Find address by type for a user.
        
        Args:
            user_id: User ID
            address_type: Address type (home, permanent, billing, work)
            
        Returns:
            UserAddress or None
        """
        return self.db.query(UserAddress).filter(
            UserAddress.user_id == user_id,
            UserAddress.address_type == address_type,
            UserAddress.is_active == True
        ).first()

    def set_primary_address(self, address_id: str, user_id: str) -> UserAddress:
        """
        Set an address as primary (unset others).
        
        Args:
            address_id: Address ID to set as primary
            user_id: User ID for validation
            
        Returns:
            Updated primary address
        """
        # Unset all other primary addresses for this user
        self.db.query(UserAddress).filter(
            UserAddress.user_id == user_id,
            UserAddress.id != address_id
        ).update({"is_primary": False})
        
        # Set the new primary
        address = self.get_by_id(address_id)
        address.is_primary = True
        
        self.db.commit()
        self.db.refresh(address)
        
        return address

    # ==================== Verification ====================

    def verify_address(
        self, 
        address_id: str, 
        verification_method: str = "manual"
    ) -> UserAddress:
        """
        Mark address as verified.
        
        Args:
            address_id: Address ID
            verification_method: Verification method (document, postal, manual)
            
        Returns:
            Verified address
        """
        address = self.get_by_id(address_id)
        
        address.is_verified = True
        address.verified_at = datetime.now(timezone.utc)
        address.verification_method = verification_method
        
        self.db.commit()
        self.db.refresh(address)
        
        return address

    def find_unverified_addresses(
        self, 
        user_id: Optional[str] = None
    ) -> List[UserAddress]:
        """
        Find unverified addresses.
        
        Args:
            user_id: Optional user ID filter
            
        Returns:
            List of unverified addresses
        """
        query = self.db.query(UserAddress).filter(
            UserAddress.is_verified == False,
            UserAddress.is_active == True
        )
        
        if user_id:
            query = query.filter(UserAddress.user_id == user_id)
        
        return query.all()

    # ==================== Geolocation ====================

    def update_coordinates(
        self, 
        address_id: str, 
        latitude: float, 
        longitude: float,
        geohash: Optional[str] = None
    ) -> UserAddress:
        """
        Update address coordinates and geohash.
        
        Args:
            address_id: Address ID
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            geohash: Geohash string (optional)
            
        Returns:
            Updated address
        """
        address = self.get_by_id(address_id)
        
        address.latitude = Decimal(str(latitude))
        address.longitude = Decimal(str(longitude))
        
        if geohash:
            address.geohash = geohash
        
        self.db.commit()
        self.db.refresh(address)
        
        return address

    def find_by_geohash_prefix(
        self, 
        geohash_prefix: str, 
        limit: int = 100
    ) -> List[UserAddress]:
        """
        Find addresses by geohash prefix (proximity search).
        
        Args:
            geohash_prefix: Geohash prefix for area
            limit: Maximum results
            
        Returns:
            List of addresses in area
        """
        return self.db.query(UserAddress).filter(
            UserAddress.geohash.like(f"{geohash_prefix}%"),
            UserAddress.is_active == True
        ).limit(limit).all()

    def find_within_radius(
        self,
        center_lat: float,
        center_lon: float,
        radius_km: float,
        limit: int = 100
    ) -> List[Tuple[UserAddress, float]]:
        """
        Find addresses within radius using Haversine formula.
        
        Args:
            center_lat: Center latitude
            center_lon: Center longitude
            radius_km: Radius in kilometers
            limit: Maximum results
            
        Returns:
            List of tuples (address, distance_km)
        """
        addresses = self.db.query(UserAddress).filter(
            UserAddress.latitude.isnot(None),
            UserAddress.longitude.isnot(None),
            UserAddress.is_active == True
        ).all()
        
        results = []
        for address in addresses:
            distance = self._calculate_distance(
                center_lat, center_lon,
                float(address.latitude), float(address.longitude)
            )
            if distance <= radius_km:
                results.append((address, distance))
        
        # Sort by distance and limit
        results.sort(key=lambda x: x[1])
        return results[:limit]

    @staticmethod
    def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two coordinates using Haversine formula.
        
        Args:
            lat1, lon1: First coordinate
            lat2, lon2: Second coordinate
            
        Returns:
            Distance in kilometers
        """
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

    # ==================== Geographic Queries ====================

    def find_by_city(self, city: str, limit: int = 100) -> List[UserAddress]:
        """
        Find addresses by city.
        
        Args:
            city: City name
            limit: Maximum results
            
        Returns:
            List of addresses
        """
        return self.db.query(UserAddress).filter(
            UserAddress.city.ilike(f"%{city}%"),
            UserAddress.is_active == True
        ).limit(limit).all()

    def find_by_state(self, state: str, limit: int = 100) -> List[UserAddress]:
        """
        Find addresses by state.
        
        Args:
            state: State name
            limit: Maximum results
            
        Returns:
            List of addresses
        """
        return self.db.query(UserAddress).filter(
            UserAddress.state.ilike(f"%{state}%"),
            UserAddress.is_active == True
        ).limit(limit).all()

    def find_by_pincode(self, pincode: str) -> List[UserAddress]:
        """
        Find addresses by pincode.
        
        Args:
            pincode: Postal/ZIP code
            
        Returns:
            List of addresses
        """
        return self.db.query(UserAddress).filter(
            UserAddress.pincode == pincode,
            UserAddress.is_active == True
        ).all()

    def find_by_country(self, country: str = "India") -> List[UserAddress]:
        """
        Find addresses by country.
        
        Args:
            country: Country name
            
        Returns:
            List of addresses
        """
        return self.db.query(UserAddress).filter(
            UserAddress.country == country,
            UserAddress.is_active == True
        ).all()

    # ==================== Statistics ====================

    def get_geographic_distribution(self) -> Dict[str, Any]:
        """
        Get geographic distribution statistics.
        
        Returns:
            Dictionary with geographic breakdowns
        """
        # City distribution
        city_dist = self.db.query(
            UserAddress.city,
            func.count(UserAddress.id).label('count')
        ).filter(
            UserAddress.is_active == True
        ).group_by(UserAddress.city).order_by(
            func.count(UserAddress.id).desc()
        ).limit(10).all()
        
        # State distribution
        state_dist = self.db.query(
            UserAddress.state,
            func.count(UserAddress.id).label('count')
        ).filter(
            UserAddress.is_active == True
        ).group_by(UserAddress.state).order_by(
            func.count(UserAddress.id).desc()
        ).all()
        
        # Country distribution
        country_dist = self.db.query(
            UserAddress.country,
            func.count(UserAddress.id).label('count')
        ).filter(
            UserAddress.is_active == True
        ).group_by(UserAddress.country).all()
        
        return {
            "top_cities": [{"city": city, "count": count} for city, count in city_dist],
            "states": [{"state": state, "count": count} for state, count in state_dist],
            "countries": [{"country": country, "count": count} for country, count in country_dist]
        }

    def get_verification_statistics(self) -> Dict[str, Any]:
        """
        Get address verification statistics.
        
        Returns:
            Dictionary with verification metrics
        """
        total = self.db.query(func.count(UserAddress.id)).filter(
            UserAddress.is_active == True
        ).scalar()
        
        verified = self.db.query(func.count(UserAddress.id)).filter(
            UserAddress.is_verified == True,
            UserAddress.is_active == True
        ).scalar()
        
        by_method = self.db.query(
            UserAddress.verification_method,
            func.count(UserAddress.id).label('count')
        ).filter(
            UserAddress.is_verified == True,
            UserAddress.is_active == True
        ).group_by(UserAddress.verification_method).all()
        
        return {
            "total_addresses": total,
            "verified_addresses": verified,
            "unverified_addresses": total - verified,
            "verification_rate": (verified / total * 100) if total > 0 else 0,
            "by_method": {method: count for method, count in by_method if method}
        }

    # ==================== Validity Management ====================

    def find_expiring_addresses(self, days: int = 30) -> List[UserAddress]:
        """
        Find addresses expiring within specified days.
        
        Args:
            days: Number of days to look ahead
            
        Returns:
            List of expiring addresses
        """
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) + timedelta(days=days)
        
        return self.db.query(UserAddress).filter(
            UserAddress.valid_until.isnot(None),
            UserAddress.valid_until <= cutoff,
            UserAddress.is_active == True
        ).all()

    def deactivate_expired_addresses(self) -> int:
        """
        Deactivate addresses past their valid_until date.
        
        Returns:
            Count of deactivated addresses
        """
        now = datetime.now(timezone.utc)
        
        count = self.db.query(UserAddress).filter(
            UserAddress.valid_until.isnot(None),
            UserAddress.valid_until < now,
            UserAddress.is_active == True
        ).update({"is_active": False})
        
        self.db.commit()
        return count