# --- File: C:\Hostel-Main\app\services\user\__init__.py (UPDATED) ---
"""
User services package initialization.

This package provides comprehensive business logic layer for user management,
including authentication, profiles, addresses, emergency contacts, sessions,
verification, preferences, data export, analytics, notifications, and security.
"""

from app.services.user.user_service import UserService
from app.services.user.user_profile_service import UserProfileService
from app.services.user.user_address_service import UserAddressService
from app.services.user.emergency_contact_service import EmergencyContactService
from app.services.user.user_session_service import UserSessionService
from app.services.user.user_verification_service import UserVerificationService
from app.services.user.user_preference_service import UserPreferenceService
from app.services.user.user_data_export_service import UserDataExportService
from app.services.user.user_analytics_service import UserAnalyticsService
from app.services.user.user_notification_service import UserNotificationService
from app.services.user.user_security_service import UserSecurityService
from app.services.user.user_service_factory import UserServiceFactory, get_user_services

__all__ = [
    # Core user management
    "UserService",
    "UserProfileService",
    "UserAddressService",
    "EmergencyContactService",
    
    # Session management
    "UserSessionService",
    
    # Verification
    "UserVerificationService",
    
    # Preferences
    "UserPreferenceService",
    
    # Data export & GDPR
    "UserDataExportService",
    
    # Analytics & reporting
    "UserAnalyticsService",
    
    # Notifications
    "UserNotificationService",
    
    # Security
    "UserSecurityService",
    
    # Service Factory
    "UserServiceFactory",
    "get_user_services",
]


