# --- File: C:\Hostel-Main\app\services\hostel\constants.py ---
"""
Hostel service constants and configuration.
"""

from typing import Final

# Pagination defaults
DEFAULT_PAGE: Final[int] = 1
DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 100

# Comparison limits
MIN_COMPARISON_HOSTELS: Final[int] = 2
MAX_COMPARISON_HOSTELS: Final[int] = 10

# Cache TTL (seconds)
HOSTEL_DETAIL_CACHE_TTL: Final[int] = 300
HOSTEL_STATS_CACHE_TTL: Final[int] = 600
ANALYTICS_CACHE_TTL: Final[int] = 900

# Error messages
ERROR_HOSTEL_NOT_FOUND: Final[str] = "Hostel not found"
ERROR_INSUFFICIENT_HOSTELS: Final[str] = "Provide at least two unique hostel IDs for comparison"
ERROR_TOO_MANY_HOSTELS: Final[str] = f"Maximum {MAX_COMPARISON_HOSTELS} hostels allowed for comparison"
ERROR_MEDIA_NOT_FOUND: Final[str] = "Media not found"
ERROR_POLICY_NOT_FOUND: Final[str] = "Policy not found"
ERROR_AMENITY_NOT_FOUND: Final[str] = "Amenity not found"
ERROR_BOOKING_NOT_FOUND: Final[str] = "Booking not found"

# Success messages
SUCCESS_HOSTEL_CREATED: Final[str] = "Hostel created successfully"
SUCCESS_HOSTEL_UPDATED: Final[str] = "Hostel updated successfully"
SUCCESS_HOSTEL_DELETED: Final[str] = "Hostel deleted successfully"
SUCCESS_MEDIA_ADDED: Final[str] = "Media added successfully"
SUCCESS_MEDIA_UPDATED: Final[str] = "Media updated successfully"
SUCCESS_MEDIA_DELETED: Final[str] = "Media deleted successfully"
SUCCESS_POLICY_CREATED: Final[str] = "Policy created successfully"
SUCCESS_POLICY_UPDATED: Final[str] = "Policy updated successfully"
SUCCESS_POLICY_ACKNOWLEDGED: Final[str] = "Policy acknowledged successfully"
SUCCESS_VIOLATION_RECORDED: Final[str] = "Policy violation recorded successfully"
SUCCESS_AMENITY_CREATED: Final[str] = "Amenity created successfully"
SUCCESS_AMENITY_UPDATED: Final[str] = "Amenity updated successfully"
SUCCESS_AMENITY_DELETED: Final[str] = "Amenity deleted successfully"
SUCCESS_AMENITY_BOOKED: Final[str] = "Amenity booked successfully"
SUCCESS_BOOKING_CANCELLED: Final[str] = "Amenity booking cancelled successfully"
SUCCESS_SETTINGS_UPDATED: Final[str] = "Settings updated successfully"
SUCCESS_VISIBILITY_UPDATED: Final[str] = "Visibility updated successfully"
SUCCESS_STATUS_UPDATED: Final[str] = "Status updated successfully"
SUCCESS_CAPACITY_UPDATED: Final[str] = "Capacity updated successfully"
SUCCESS_SEO_UPDATED: Final[str] = "SEO metadata updated successfully"
SUCCESS_COMPARISON_GENERATED: Final[str] = "Comparison generated successfully"
SUCCESS_ONBOARDING_COMPLETED: Final[str] = "Hostel onboarded successfully"