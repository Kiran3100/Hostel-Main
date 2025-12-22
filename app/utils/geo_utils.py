"""
Geolocation utilities for hostel management system
"""

import math
import requests
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
import json
import time
from datetime import datetime
import hashlib

@dataclass
class GeoPoint:
    """Geographic point with latitude and longitude"""
    latitude: float
    longitude: float
    
    def __post_init__(self):
        if not (-90 <= self.latitude <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        if not (-180 <= self.longitude <= 180):
            raise ValueError("Longitude must be between -180 and 180")

@dataclass
class Address:
    """Structured address information"""
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    formatted_address: Optional[str] = None

@dataclass
class GeocodeResult:
    """Geocoding result with coordinate and address info"""
    point: GeoPoint
    address: Address
    accuracy: str = None
    place_id: str = None

class GeoLocationHelper:
    """Main geolocation utilities"""
    
    # Earth's radius in kilometers
    EARTH_RADIUS_KM = 6371.0
    EARTH_RADIUS_MILES = 3959.0
    
    @staticmethod
    def calculate_distance(point1: GeoPoint, point2: GeoPoint, 
                          unit: str = 'km') -> float:
        """Calculate distance between two points using Haversine formula"""
        lat1, lon1 = math.radians(point1.latitude), math.radians(point1.longitude)
        lat2, lon2 = math.radians(point2.latitude), math.radians(point2.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        if unit.lower() == 'miles':
            return c * GeoLocationHelper.EARTH_RADIUS_MILES
        else:
            return c * GeoLocationHelper.EARTH_RADIUS_KM
    
    @staticmethod
    def get_bounding_box(center: GeoPoint, radius_km: float) -> Dict[str, GeoPoint]:
        """Get bounding box coordinates around a center point"""
        # Approximate degrees per kilometer
        lat_deg_per_km = 1 / 111.0
        lon_deg_per_km = 1 / (111.0 * math.cos(math.radians(center.latitude)))
        
        lat_offset = radius_km * lat_deg_per_km
        lon_offset = radius_km * lon_deg_per_km
        
        return {
            'northeast': GeoPoint(
                center.latitude + lat_offset,
                center.longitude + lon_offset
            ),
            'southwest': GeoPoint(
                center.latitude - lat_offset,
                center.longitude - lon_offset
            )
        }
    
    @staticmethod
    def is_point_in_bounds(point: GeoPoint, bounds: Dict[str, GeoPoint]) -> bool:
        """Check if a point is within bounding box"""
        return (bounds['southwest'].latitude <= point.latitude <= bounds['northeast'].latitude and
                bounds['southwest'].longitude <= point.longitude <= bounds['northeast'].longitude)
    
    @staticmethod
    def get_center_point(points: List[GeoPoint]) -> GeoPoint:
        """Calculate center point of multiple coordinates"""
        if not points:
            raise ValueError("Points list cannot be empty")
        
        if len(points) == 1:
            return points[0]
        
        # Convert to Cartesian coordinates
        x = y = z = 0.0
        
        for point in points:
            lat_rad = math.radians(point.latitude)
            lon_rad = math.radians(point.longitude)
            
            x += math.cos(lat_rad) * math.cos(lon_rad)
            y += math.cos(lat_rad) * math.sin(lon_rad)
            z += math.sin(lat_rad)
        
        # Average the coordinates
        x /= len(points)
        y /= len(points)
        z /= len(points)
        
        # Convert back to latitude/longitude
        center_lat = math.atan2(z, math.sqrt(x*x + y*y))
        center_lon = math.atan2(y, x)
        
        return GeoPoint(
            math.degrees(center_lat),
            math.degrees(center_lon)
        )
    
    @staticmethod
    def get_bearing(start_point: GeoPoint, end_point: GeoPoint) -> float:
        """Calculate bearing from start point to end point"""
        lat1, lon1 = math.radians(start_point.latitude), math.radians(start_point.longitude)
        lat2, lon2 = math.radians(end_point.latitude), math.radians(end_point.longitude)
        
        dlon = lon2 - lon1
        
        y = math.sin(dlon) * math.cos(lat2)
        x = (math.cos(lat1) * math.sin(lat2) - 
             math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
        
        bearing = math.atan2(y, x)
        bearing = math.degrees(bearing)
        
        return (bearing + 360) % 360
    
    @staticmethod
    def get_destination_point(start_point: GeoPoint, bearing_degrees: float, 
                            distance_km: float) -> GeoPoint:
        """Calculate destination point given start point, bearing, and distance"""
        lat1 = math.radians(start_point.latitude)
        lon1 = math.radians(start_point.longitude)
        bearing = math.radians(bearing_degrees)
        
        angular_distance = distance_km / GeoLocationHelper.EARTH_RADIUS_KM
        
        lat2 = math.asin(
            math.sin(lat1) * math.cos(angular_distance) +
            math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing)
        )
        
        lon2 = lon1 + math.atan2(
            math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
            math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2)
        )
        
        return GeoPoint(math.degrees(lat2), math.degrees(lon2))

class DistanceCalculator:
    """Advanced distance calculation utilities"""
    
    @staticmethod
    def vincenty_distance(point1: GeoPoint, point2: GeoPoint) -> float:
        """Calculate distance using Vincenty's formula (more accurate)"""
        # WGS84 ellipsoid parameters
        a = 6378137.0  # Semi-major axis
        f = 1/298.257223563  # Flattening
        b = (1 - f) * a  # Semi-minor axis
        
        lat1, lon1 = math.radians(point1.latitude), math.radians(point1.longitude)
        lat2, lon2 = math.radians(point2.latitude), math.radians(point2.longitude)
        
        U1 = math.atan((1 - f) * math.tan(lat1))
        U2 = math.atan((1 - f) * math.tan(lat2))
        L = lon2 - lon1
        
        sin_U1 = math.sin(U1)
        cos_U1 = math.cos(U1)
        sin_U2 = math.sin(U2)
        cos_U2 = math.cos(U2)
        
        lambda_val = L
        lambda_prev = 2 * math.pi
        iteration_limit = 100
        
        while abs(lambda_val - lambda_prev) > 1e-12 and iteration_limit > 0:
            sin_lambda = math.sin(lambda_val)
            cos_lambda = math.cos(lambda_val)
            
            sin_sigma = math.sqrt(
                (cos_U2 * sin_lambda)**2 +
                (cos_U1 * sin_U2 - sin_U1 * cos_U2 * cos_lambda)**2
            )
            
            if sin_sigma == 0:
                return 0.0  # Coincident points
            
            cos_sigma = sin_U1 * sin_U2 + cos_U1 * cos_U2 * cos_lambda
            sigma = math.atan2(sin_sigma, cos_sigma)
            
            sin_alpha = cos_U1 * cos_U2 * sin_lambda / sin_sigma
            cos2_alpha = 1 - sin_alpha**2
            
            if cos2_alpha == 0:
                cos_2sigma_m = 0
            else:
                cos_2sigma_m = cos_sigma - 2 * sin_U1 * sin_U2 / cos2_alpha
            
            C = f / 16 * cos2_alpha * (4 + f * (4 - 3 * cos2_alpha))
            
            lambda_prev = lambda_val
            lambda_val = (L + (1 - C) * f * sin_alpha *
                         (sigma + C * sin_sigma *
                          (cos_2sigma_m + C * cos_sigma *
                           (-1 + 2 * cos_2sigma_m**2))))
            iteration_limit -= 1
        
        if iteration_limit == 0:
            return float('nan')  # Formula failed to converge
        
        u2 = cos2_alpha * (a**2 - b**2) / b**2
        A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
        B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
        
        delta_sigma = (B * sin_sigma *
                      (cos_2sigma_m + B / 4 *
                       (cos_sigma * (-1 + 2 * cos_2sigma_m**2) -
                        B / 6 * cos_2sigma_m * (-3 + 4 * sin_sigma**2) *
                        (-3 + 4 * cos_2sigma_m**2))))
        
        distance = b * A * (sigma - delta_sigma) / 1000  # Convert to km
        
        return distance
    
    @staticmethod
    def manhattan_distance(point1: GeoPoint, point2: GeoPoint) -> float:
        """Calculate Manhattan distance (city block distance)"""
        lat_diff = abs(point1.latitude - point2.latitude)
        lon_diff = abs(point1.longitude - point2.longitude)
        
        # Convert degrees to kilometers
        lat_km = lat_diff * 111.0
        lon_km = lon_diff * 111.0 * math.cos(math.radians((point1.latitude + point2.latitude) / 2))
        
        return lat_km + lon_km
    
    @staticmethod
    def find_nearest_points(target: GeoPoint, points: List[Tuple[GeoPoint, Any]], 
                          count: int = 5) -> List[Tuple[GeoPoint, Any, float]]:
        """Find nearest points to target location"""
        distances = []
        
        for point, data in points:
            distance = GeoLocationHelper.calculate_distance(target, point)
            distances.append((point, data, distance))
        
        # Sort by distance and return top N
        distances.sort(key=lambda x: x[2])
        return distances[:count]

class AddressGeocoder:
    """Address geocoding utilities"""
    
    def __init__(self, api_key: str = None, service: str = 'nominatim'):
        self.api_key = api_key
        self.service = service
        self.cache = {}  # Simple in-memory cache
    
    def geocode_address(self, address: str) -> Optional[GeocodeResult]:
        """Convert address to coordinates"""
        # Check cache first
        cache_key = hashlib.md5(address.encode()).hexdigest()
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        result = None
        
        if self.service == 'nominatim':
            result = self._geocode_nominatim(address)
        elif self.service == 'google' and self.api_key:
            result = self._geocode_google(address)
        elif self.service == 'mapbox' and self.api_key:
            result = self._geocode_mapbox(address)
        
        # Cache the result
        if result:
            self.cache[cache_key] = result
        
        return result
    
    def reverse_geocode(self, point: GeoPoint) -> Optional[Address]:
        """Convert coordinates to address"""
        cache_key = f"{point.latitude},{point.longitude}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        result = None
        
        if self.service == 'nominatim':
            result = self._reverse_geocode_nominatim(point)
        elif self.service == 'google' and self.api_key:
            result = self._reverse_geocode_google(point)
        elif self.service == 'mapbox' and self.api_key:
            result = self._reverse_geocode_mapbox(point)
        
        # Cache the result
        if result:
            self.cache[cache_key] = result
        
        return result
    
    def _geocode_nominatim(self, address: str) -> Optional[GeocodeResult]:
        """Geocode using OpenStreetMap Nominatim"""
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': address,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            }
            
            headers = {
                'User-Agent': 'HostelManagementSystem/1.0'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if not data:
                return None
            
            result = data[0]
            
            point = GeoPoint(
                float(result['lat']),
                float(result['lon'])
            )
            
            addr_data = result.get('address', {})
            address_obj = Address(
                street=addr_data.get('road'),
                city=addr_data.get('city') or addr_data.get('town') or addr_data.get('village'),
                state=addr_data.get('state'),
                country=addr_data.get('country'),
                postal_code=addr_data.get('postcode'),
                formatted_address=result.get('display_name')
            )
            
            return GeocodeResult(
                point=point,
                address=address_obj,
                accuracy='street',
                place_id=result.get('place_id')
            )
            
        except Exception as e:
            print(f"Nominatim geocoding error: {e}")
            return None
    
    def _geocode_google(self, address: str) -> Optional[GeocodeResult]:
        """Geocode using Google Maps API"""
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                'address': address,
                'key': self.api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data['status'] != 'OK' or not data['results']:
                return None
            
            result = data['results'][0]
            location = result['geometry']['location']
            
            point = GeoPoint(
                location['lat'],
                location['lng']
            )
            
            # Parse address components
            components = result.get('address_components', [])
            addr_data = {}
            
            for component in components:
                types = component['types']
                if 'street_number' in types:
                    addr_data['street_number'] = component['long_name']
                elif 'route' in types:
                    addr_data['street'] = component['long_name']
                elif 'locality' in types:
                    addr_data['city'] = component['long_name']
                elif 'administrative_area_level_1' in types:
                    addr_data['state'] = component['long_name']
                elif 'country' in types:
                    addr_data['country'] = component['long_name']
                elif 'postal_code' in types:
                    addr_data['postal_code'] = component['long_name']
            
            # Combine street number and route
            street = addr_data.get('street', '')
            if addr_data.get('street_number'):
                street = f"{addr_data['street_number']} {street}".strip()
            
            address_obj = Address(
                street=street or None,
                city=addr_data.get('city'),
                state=addr_data.get('state'),
                country=addr_data.get('country'),
                postal_code=addr_data.get('postal_code'),
                formatted_address=result.get('formatted_address')
            )
            
            return GeocodeResult(
                point=point,
                address=address_obj,
                accuracy=result['geometry']['location_type'].lower(),
                place_id=result.get('place_id')
            )
            
        except Exception as e:
            print(f"Google geocoding error: {e}")
            return None
    
    def _geocode_mapbox(self, address: str) -> Optional[GeocodeResult]:
        """Geocode using Mapbox API"""
        try:
            url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{address}.json"
            params = {
                'access_token': self.api_key,
                'limit': 1
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if not data['features']:
                return None
            
            feature = data['features'][0]
            coords = feature['geometry']['coordinates']
            
            point = GeoPoint(coords[1], coords[0])  # Mapbox uses [lon, lat]
            
            # Parse address from context
            context = feature.get('context', [])
            addr_data = {}
            
            for item in context:
                if item['id'].startswith('postcode'):
                    addr_data['postal_code'] = item['text']
                elif item['id'].startswith('place'):
                    addr_data['city'] = item['text']
                elif item['id'].startswith('region'):
                    addr_data['state'] = item['text']
                elif item['id'].startswith('country'):
                    addr_data['country'] = item['text']
            
            address_obj = Address(
                street=feature.get('properties', {}).get('address'),
                city=addr_data.get('city'),
                state=addr_data.get('state'),
                country=addr_data.get('country'),
                postal_code=addr_data.get('postal_code'),
                formatted_address=feature.get('place_name')
            )
            
            return GeocodeResult(
                point=point,
                address=address_obj,
                accuracy='street',
                place_id=feature.get('id')
            )
            
        except Exception as e:
            print(f"Mapbox geocoding error: {e}")
            return None
    
    def _reverse_geocode_nominatim(self, point: GeoPoint) -> Optional[Address]:
        """Reverse geocode using Nominatim"""
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'lat': point.latitude,
                'lon': point.longitude,
                'format': 'json',
                'addressdetails': 1
            }
            
            headers = {
                'User-Agent': 'HostelManagementSystem/1.0'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if 'error' in data:
                return None
            
            addr_data = data.get('address', {})
            return Address(
                street=addr_data.get('road'),
                city=addr_data.get('city') or addr_data.get('town') or addr_data.get('village'),
                state=addr_data.get('state'),
                country=addr_data.get('country'),
                postal_code=addr_data.get('postcode'),
                formatted_address=data.get('display_name')
            )
            
        except Exception as e:
            print(f"Nominatim reverse geocoding error: {e}")
            return None
    
    def _reverse_geocode_google(self, point: GeoPoint) -> Optional[Address]:
        """Reverse geocode using Google Maps API"""
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                'latlng': f"{point.latitude},{point.longitude}",
                'key': self.api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data['status'] != 'OK' or not data['results']:
                return None
            
            result = data['results'][0]
            
            # Parse address components
            components = result.get('address_components', [])
            addr_data = {}
            
            for component in components:
                types = component['types']
                if 'street_number' in types:
                    addr_data['street_number'] = component['long_name']
                elif 'route' in types:
                    addr_data['street'] = component['long_name']
                elif 'locality' in types:
                    addr_data['city'] = component['long_name']
                elif 'administrative_area_level_1' in types:
                    addr_data['state'] = component['long_name']
                elif 'country' in types:
                    addr_data['country'] = component['long_name']
                elif 'postal_code' in types:
                    addr_data['postal_code'] = component['long_name']
            
            # Combine street number and route
            street = addr_data.get('street', '')
            if addr_data.get('street_number'):
                street = f"{addr_data['street_number']} {street}".strip()
            
            return Address(
                street=street or None,
                city=addr_data.get('city'),
                state=addr_data.get('state'),
                country=addr_data.get('country'),
                postal_code=addr_data.get('postal_code'),
                formatted_address=result.get('formatted_address')
            )
            
        except Exception as e:
            print(f"Google reverse geocoding error: {e}")
            return None
    
    def _reverse_geocode_mapbox(self, point: GeoPoint) -> Optional[Address]:
        """Reverse geocode using Mapbox API"""
        try:
            url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{point.longitude},{point.latitude}.json"
            params = {
                'access_token': self.api_key,
                'limit': 1
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if not data['features']:
                return None
            
            feature = data['features'][0]
            
            # Parse address from context
            context = feature.get('context', [])
            addr_data = {}
            
            for item in context:
                if item['id'].startswith('postcode'):
                    addr_data['postal_code'] = item['text']
                elif item['id'].startswith('place'):
                    addr_data['city'] = item['text']
                elif item['id'].startswith('region'):
                    addr_data['state'] = item['text']
                elif item['id'].startswith('country'):
                    addr_data['country'] = item['text']
            
            return Address(
                street=feature.get('properties', {}).get('address'),
                city=addr_data.get('city'),
                state=addr_data.get('state'),
                country=addr_data.get('country'),
                postal_code=addr_data.get('postal_code'),
                formatted_address=feature.get('place_name')
            )
            
        except Exception as e:
            print(f"Mapbox reverse geocoding error: {e}")
            return None

class RegionDetector:
    """Region and timezone detection utilities"""
    
    # Major Indian cities and their coordinates
    INDIAN_CITIES = {
        'Mumbai': GeoPoint(19.0760, 72.8777),
        'Delhi': GeoPoint(28.7041, 77.1025),
        'Bangalore': GeoPoint(12.9716, 77.5946),
        'Hyderabad': GeoPoint(17.3850, 78.4867),
        'Chennai': GeoPoint(13.0827, 80.2707),
        'Kolkata': GeoPoint(22.5726, 88.3639),
        'Pune': GeoPoint(18.5204, 73.8567),
        'Ahmedabad': GeoPoint(23.0225, 72.5714),
        'Surat': GeoPoint(21.1702, 72.8311),
        'Jaipur': GeoPoint(26.9124, 75.7873)
    }
    
    @classmethod
    def detect_nearest_city(cls, point: GeoPoint) -> Dict[str, Any]:
        """Detect nearest major city"""
        nearest_city = None
        min_distance = float('inf')
        
        for city_name, city_point in cls.INDIAN_CITIES.items():
            distance = GeoLocationHelper.calculate_distance(point, city_point)
            if distance < min_distance:
                min_distance = distance
                nearest_city = city_name
        
        return {
            'city': nearest_city,
            'distance_km': round(min_distance, 2),
            'coordinates': cls.INDIAN_CITIES[nearest_city] if nearest_city else None
        }
    
    @classmethod
    def detect_region(cls, point: GeoPoint) -> str:
        """Detect geographical region within India"""
        lat, lon = point.latitude, point.longitude
        
        # Basic region detection for India
        if lat >= 28:
            if lon <= 77:
                return 'North West'
            else:
                return 'North East'
        elif lat >= 23:
            if lon <= 77:
                return 'West'
            else:
                return 'Central'
        elif lat >= 15:
            if lon <= 75:
                return 'South West'
            else:
                return 'South Central'
        else:
            if lon <= 77:
                return 'South'
            else:
                return 'South East'
    
    @classmethod
    def get_timezone(cls, point: GeoPoint) -> str:
        """Get timezone for coordinates (simplified for India)"""
        # India uses a single timezone
        return 'Asia/Kolkata'
    
    @classmethod
    def is_in_country(cls, point: GeoPoint, country: str = 'India') -> bool:
        """Check if point is within country boundaries"""
        if country.lower() == 'india':
            # Approximate bounding box for India
            return (6.0 <= point.latitude <= 37.0 and 
                   68.0 <= point.longitude <= 97.0)
        
        # Add other countries as needed
        return False

class GeoFencing:
    """Geofencing utilities for location-based features"""
    
    def __init__(self):
        self.fences = {}
    
    def add_circular_fence(self, fence_id: str, center: GeoPoint, 
                          radius_km: float, name: str = None):
        """Add circular geofence"""
        self.fences[fence_id] = {
            'type': 'circular',
            'center': center,
            'radius_km': radius_km,
            'name': name or fence_id,
            'created_at': datetime.now()
        }
    
    def add_polygon_fence(self, fence_id: str, vertices: List[GeoPoint], 
                         name: str = None):
        """Add polygon geofence"""
        self.fences[fence_id] = {
            'type': 'polygon',
            'vertices': vertices,
            'name': name or fence_id,
            'created_at': datetime.now()
        }
    
    def is_point_in_fence(self, point: GeoPoint, fence_id: str) -> bool:
        """Check if point is within geofence"""
        if fence_id not in self.fences:
            return False
        
        fence = self.fences[fence_id]
        
        if fence['type'] == 'circular':
            distance = GeoLocationHelper.calculate_distance(
                point, fence['center']
            )
            return distance <= fence['radius_km']
        
        elif fence['type'] == 'polygon':
            return self._point_in_polygon(point, fence['vertices'])
        
        return False
    
    def _point_in_polygon(self, point: GeoPoint, vertices: List[GeoPoint]) -> bool:
        """Check if point is inside polygon using ray casting algorithm"""
        x, y = point.longitude, point.latitude
        n = len(vertices)
        inside = False
        
        p1x, p1y = vertices[0].longitude, vertices[0].latitude
        
        for i in range(1, n + 1):
            p2x, p2y = vertices[i % n].longitude, vertices[i % n].latitude
            
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            
            p1x, p1y = p2x, p2y
        
        return inside
    
    def get_fence_status(self, point: GeoPoint) -> List[Dict[str, Any]]:
        """Get status of point relative to all geofences"""
        statuses = []
        
        for fence_id, fence in self.fences.items():
            is_inside = self.is_point_in_fence(point, fence_id)
            
            status = {
                'fence_id': fence_id,
                'fence_name': fence['name'],
                'is_inside': is_inside,
                'fence_type': fence['type']
            }
            
            if fence['type'] == 'circular':
                distance = GeoLocationHelper.calculate_distance(
                    point, fence['center']
                )
                status['distance_from_center'] = round(distance, 3)
                status['distance_from_boundary'] = round(
                    abs(distance - fence['radius_km']), 3
                )
            
            statuses.append(status)
        
        return statuses

class LocationAnalytics:
    """Location analytics and insights utilities"""
    
    def __init__(self):
        self.location_history = []
    
    def add_location_point(self, user_id: str, point: GeoPoint, 
                          timestamp: datetime = None):
        """Add location point to history"""
        self.location_history.append({
            'user_id': user_id,
            'point': point,
            'timestamp': timestamp or datetime.now()
        })
    
    def get_user_travel_distance(self, user_id: str, 
                                start_time: datetime = None,
                                end_time: datetime = None) -> float:
        """Calculate total travel distance for user"""
        user_points = [
            entry for entry in self.location_history
            if entry['user_id'] == user_id
        ]
        
        if start_time or end_time:
            user_points = [
                entry for entry in user_points
                if (not start_time or entry['timestamp'] >= start_time) and
                   (not end_time or entry['timestamp'] <= end_time)
            ]
        
        if len(user_points) < 2:
            return 0.0
        
        total_distance = 0.0
        user_points.sort(key=lambda x: x['timestamp'])
        
        for i in range(1, len(user_points)):
            prev_point = user_points[i-1]['point']
            curr_point = user_points[i]['point']
            
            distance = GeoLocationHelper.calculate_distance(prev_point, curr_point)
            total_distance += distance
        
        return round(total_distance, 2)
    
    def get_user_locations_summary(self, user_id: str) -> Dict[str, Any]:
        """Get summary of user's location data"""
        user_points = [
            entry for entry in self.location_history
            if entry['user_id'] == user_id
        ]
        
        if not user_points:
            return {'message': 'No location data available'}
        
        points = [entry['point'] for entry in user_points]
        
        # Calculate bounding box
        min_lat = min(p.latitude for p in points)
        max_lat = max(p.latitude for p in points)
        min_lon = min(p.longitude for p in points)
        max_lon = max(p.longitude for p in points)
        
        # Calculate center
        center = GeoLocationHelper.get_center_point(points)
        
        # Calculate total distance traveled
        total_distance = self.get_user_travel_distance(user_id)
        
        return {
            'total_points': len(user_points),
            'date_range': {
                'start': min(entry['timestamp'] for entry in user_points),
                'end': max(entry['timestamp'] for entry in user_points)
            },
            'bounding_box': {
                'northeast': GeoPoint(max_lat, max_lon),
                'southwest': GeoPoint(min_lat, min_lon)
            },
            'center_point': center,
            'total_distance_km': total_distance,
            'nearest_city': RegionDetector.detect_nearest_city(center)
        }