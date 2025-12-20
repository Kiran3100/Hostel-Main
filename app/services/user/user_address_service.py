# --- File: C:\Hostel-Main\app\services\user\user_address_service.py ---
"""
User Address Service - Address management with geolocation support.
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from decimal import Decimal

from app.models.user import UserAddress
from app.repositories.user import UserAddressRepository, UserRepository
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError


class UserAddressService:
    """
    Service for user address operations including geolocation,
    verification, and spatial queries.
    """

    def __init__(self, db: Session):
        self.db = db
        self.address_repo = UserAddressRepository(db)
        self.user_repo = UserRepository(db)

    # ==================== Address Management ====================

    def create_address(
        self,
        user_id: str,
        address_data: Dict[str, Any],
        set_as_primary: bool = False
    ) -> UserAddress:
        """
        Create user address.
        
        Args:
            user_id: User ID
            address_data: Address data dictionary
            set_as_primary: Set as primary address
            
        Returns:
            Created UserAddress
            
        Raises:
            EntityNotFoundError: If user not found
        """
        # Validate user exists
        user = self.user_repo.get_by_id(user_id)
        
        # Add user_id to address data
        address_data['user_id'] = user_id
        
        # Set default values
        if 'is_primary' not in address_data:
            address_data['is_primary'] = set_as_primary
        
        if 'address_type' not in address_data:
            address_data['address_type'] = 'home'
        
        # Create address
        address = self.address_repo.create(address_data)
        
        # If set as primary, unset other primary addresses
        if set_as_primary:
            self.address_repo.set_primary_address(address.id, user_id)
        
        # Attempt to geocode address
        self._geocode_address(address.id)
        
        return address

    def update_address(
        self,
        address_id: str,
        address_data: Dict[str, Any]
    ) -> UserAddress:
        """
        Update user address.
        
        Args:
            address_id: Address ID
            address_data: Address data dictionary
            
        Returns:
            Updated UserAddress
        """
        address = self.address_repo.update(address_id, address_data)
        
        # Re-geocode if address components changed
        address_fields = ['address_line1', 'address_line2', 'city', 
                         'state', 'country', 'pincode']
        if any(field in address_data for field in address_fields):
            self._geocode_address(address_id)
        
        return address

    def delete_address(self, address_id: str) -> None:
        """
        Delete user address.
        
        Args:
            address_id: Address ID
        """
        address = self.address_repo.get_by_id(address_id)
        
        # Don't allow deleting primary address if other addresses exist
        if address.is_primary:
            user_addresses = self.address_repo.find_by_user_id(address.user_id)
            if len(user_addresses) > 1:
                raise BusinessRuleViolationError(
                    "Cannot delete primary address. Set another address as primary first."
                )
        
        self.address_repo.delete(address_id)

    def get_user_addresses(self, user_id: str) -> List[UserAddress]:
        """
        Get all addresses for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of addresses
        """
        return self.address_repo.find_by_user_id(user_id)

    def get_primary_address(self, user_id: str) -> Optional[UserAddress]:
        """
        Get primary address for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Primary UserAddress or None
        """
        return self.address_repo.find_primary_address(user_id)

    def set_primary_address(
        self,
        address_id: str,
        user_id: str
    ) -> UserAddress:
        """
        Set an address as primary.
        
        Args:
            address_id: Address ID
            user_id: User ID for validation
            
        Returns:
            Updated primary address
        """
        return self.address_repo.set_primary_address(address_id, user_id)

    # ==================== Address Types ====================

    def get_address_by_type(
        self,
        user_id: str,
        address_type: str
    ) -> Optional[UserAddress]:
        """
        Get address by type for a user.
        
        Args:
            user_id: User ID
            address_type: Address type (home, permanent, billing, work)
            
        Returns:
            UserAddress or None
        """
        return self.address_repo.find_by_type(user_id, address_type)

    def create_or_update_address_by_type(
        self,
        user_id: str,
        address_type: str,
        address_data: Dict[str, Any]
    ) -> UserAddress:
        """
        Create or update address for a specific type.
        
        Args:
            user_id: User ID
            address_type: Address type
            address_data: Address data
            
        Returns:
            UserAddress
        """
        existing = self.address_repo.find_by_type(user_id, address_type)
        
        if existing:
            return self.update_address(existing.id, address_data)
        else:
            address_data['address_type'] = address_type
            return self.create_address(user_id, address_data)

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
        return self.address_repo.verify_address(
            address_id,
            verification_method
        )

    def unverify_address(self, address_id: str) -> UserAddress:
        """
        Remove address verification.
        
        Args:
            address_id: Address ID
            
        Returns:
            Updated address
        """
        address = self.address_repo.get_by_id(address_id)
        return self.address_repo.update(address.id, {
            'is_verified': False,
            'verified_at': None,
            'verification_method': None
        })

    def get_unverified_addresses(
        self,
        user_id: Optional[str] = None
    ) -> List[UserAddress]:
        """
        Get unverified addresses.
        
        Args:
            user_id: Optional user ID filter
            
        Returns:
            List of unverified addresses
        """
        return self.address_repo.find_unverified_addresses(user_id)

    # ==================== Geolocation ====================

    def _geocode_address(self, address_id: str) -> Optional[UserAddress]:
        """
        Geocode address to get coordinates (placeholder for geocoding service).
        
        Args:
            address_id: Address ID
            
        Returns:
            Updated address with coordinates or None
        """
        # TODO: Implement actual geocoding service integration
        # This is a placeholder that would integrate with Google Maps, 
        # OpenStreetMap, or other geocoding service
        
        address = self.address_repo.get_by_id(address_id)
        
        # Placeholder logic - in production, call geocoding API
        # Example: geocoding_service.geocode(address.full_address)
        
        return address

    def update_coordinates(
        self,
        address_id: str,
        latitude: float,
        longitude: float
    ) -> UserAddress:
        """
        Update address coordinates manually.
        
        Args:
            address_id: Address ID
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Updated address
        """
        # Calculate geohash
        geohash = self._calculate_geohash(latitude, longitude)
        
        return self.address_repo.update_coordinates(
            address_id,
            latitude,
            longitude,
            geohash
        )

    def _calculate_geohash(
        self,
        latitude: float,
        longitude: float,
        precision: int = 9
    ) -> str:
        """
        Calculate geohash for coordinates.
        
        Args:
            latitude: Latitude
            longitude: Longitude
            precision: Geohash precision
            
        Returns:
            Geohash string
        """
        # TODO: Implement geohash algorithm or use library like python-geohash
        # This is a placeholder
        return f"geohash_{latitude}_{longitude}"

    # ==================== Spatial Queries ====================

    def find_addresses_within_radius(
        self,
        center_lat: float,
        center_lon: float,
        radius_km: float,
        limit: int = 100
    ) -> List[Tuple[UserAddress, float]]:
        """
        Find addresses within radius of a point.
        
        Args:
            center_lat: Center latitude
            center_lon: Center longitude
            radius_km: Radius in kilometers
            limit: Maximum results
            
        Returns:
            List of tuples (address, distance_km)
        """
        return self.address_repo.find_within_radius(
            center_lat,
            center_lon,
            radius_km,
            limit
        )

    def find_nearby_users(
        self,
        user_id: str,
        radius_km: float = 10,
        limit: int = 50
    ) -> List[Tuple[UserAddress, float]]:
        """
        Find users near a specific user's address.
        
        Args:
            user_id: User ID
            radius_km: Search radius in kilometers
            limit: Maximum results
            
        Returns:
            List of nearby addresses with distances
        """
        primary_address = self.get_primary_address(user_id)
        
        if not primary_address or not primary_address.coordinates:
            return []
        
        lat, lon = primary_address.coordinates
        
        results = self.find_addresses_within_radius(
            lat, lon, radius_km, limit
        )
        
        # Filter out the user's own address
        return [
            (addr, dist) for addr, dist in results 
            if addr.user_id != user_id
        ]

    # ==================== Geographic Queries ====================

    def find_addresses_by_city(
        self,
        city: str,
        limit: int = 100
    ) -> List[UserAddress]:
        """
        Find addresses in a specific city.
        
        Args:
            city: City name
            limit: Maximum results
            
        Returns:
            List of addresses
        """
        return self.address_repo.find_by_city(city, limit)

    def find_addresses_by_state(
        self,
        state: str,
        limit: int = 100
    ) -> List[UserAddress]:
        """
        Find addresses in a specific state.
        
        Args:
            state: State name
            limit: Maximum results
            
        Returns:
            List of addresses
        """
        return self.address_repo.find_by_state(state, limit)

    def find_addresses_by_pincode(self, pincode: str) -> List[UserAddress]:
        """
        Find addresses by pincode.
        
        Args:
            pincode: Postal/ZIP code
            
        Returns:
            List of addresses
        """
        return self.address_repo.find_by_pincode(pincode)

    # ==================== Validity Management ====================

    def set_address_validity(
        self,
        address_id: str,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None
    ) -> UserAddress:
        """
        Set address validity period.
        
        Args:
            address_id: Address ID
            valid_from: Validity start date
            valid_until: Validity end date
            
        Returns:
            Updated address
        """
        address = self.address_repo.get_by_id(address_id)
        
        return self.address_repo.update(address.id, {
            'valid_from': valid_from,
            'valid_until': valid_until
        })

    def get_expiring_addresses(self, days: int = 30) -> List[UserAddress]:
        """
        Get addresses expiring within specified days.
        
        Args:
            days: Number of days to look ahead
            
        Returns:
            List of expiring addresses
        """
        return self.address_repo.find_expiring_addresses(days)

    def cleanup_expired_addresses(self) -> int:
        """
        Deactivate addresses past their valid_until date.
        
        Returns:
            Count of deactivated addresses
        """
        return self.address_repo.deactivate_expired_addresses()

    # ==================== Privacy & Visibility ====================

    def set_address_visibility(
        self,
        address_id: str,
        is_public: bool
    ) -> UserAddress:
        """
        Set address public visibility.
        
        Args:
            address_id: Address ID
            is_public: Public visibility flag
            
        Returns:
            Updated address
        """
        address = self.address_repo.get_by_id(address_id)
        return self.address_repo.update(address.id, {
            'is_public': is_public
        })

    # ==================== Analytics ====================

    def get_geographic_distribution(self) -> Dict[str, Any]:
        """
        Get geographic distribution statistics.
        
        Returns:
            Dictionary with geographic breakdowns
        """
        return self.address_repo.get_geographic_distribution()

    def get_verification_statistics(self) -> Dict[str, Any]:
        """
        Get address verification statistics.
        
        Returns:
            Dictionary with verification metrics
        """
        return self.address_repo.get_verification_statistics()

    # ==================== Utility Methods ====================

    def format_address(self, address_id: str) -> str:
        """
        Get formatted full address string.
        
        Args:
            address_id: Address ID
            
        Returns:
            Formatted address string
        """
        address = self.address_repo.get_by_id(address_id)
        return address.full_address

    def validate_address_completeness(
        self,
        address_data: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate if address data is complete.
        
        Args:
            address_data: Address data dictionary
            
        Returns:
            Tuple of (is_complete, missing_fields)
        """
        required_fields = [
            'address_line1', 'city', 'state', 'country', 'pincode'
        ]
        
        missing = [
            field for field in required_fields 
            if field not in address_data or not address_data[field]
        ]
        
        return len(missing) == 0, missing


