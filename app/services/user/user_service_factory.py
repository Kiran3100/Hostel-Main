# --- File: C:\Hostel-Main\app\services\user\user_service_factory.py ---
"""
User Service Factory - Centralized service instantiation and dependency injection.
"""
from typing import Optional
from sqlalchemy.orm import Session

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


class UserServiceFactory:
    """
    Factory class for creating and managing user services.
    Provides singleton-like access to services within a request context.
    """

    def __init__(self, db: Session):
        """
        Initialize service factory with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._services = {}

    # ==================== Service Getters ====================

    @property
    def user_service(self) -> UserService:
        """Get UserService instance."""
        if 'user_service' not in self._services:
            self._services['user_service'] = UserService(self.db)
        return self._services['user_service']

    @property
    def profile_service(self) -> UserProfileService:
        """Get UserProfileService instance."""
        if 'profile_service' not in self._services:
            self._services['profile_service'] = UserProfileService(self.db)
        return self._services['profile_service']

    @property
    def address_service(self) -> UserAddressService:
        """Get UserAddressService instance."""
        if 'address_service' not in self._services:
            self._services['address_service'] = UserAddressService(self.db)
        return self._services['address_service']

    @property
    def contact_service(self) -> EmergencyContactService:
        """Get EmergencyContactService instance."""
        if 'contact_service' not in self._services:
            self._services['contact_service'] = EmergencyContactService(self.db)
        return self._services['contact_service']

    @property
    def session_service(self) -> UserSessionService:
        """Get UserSessionService instance."""
        if 'session_service' not in self._services:
            self._services['session_service'] = UserSessionService(self.db)
        return self._services['session_service']

    @property
    def verification_service(self) -> UserVerificationService:
        """Get UserVerificationService instance."""
        if 'verification_service' not in self._services:
            self._services['verification_service'] = UserVerificationService(self.db)
        return self._services['verification_service']

    @property
    def preference_service(self) -> UserPreferenceService:
        """Get UserPreferenceService instance."""
        if 'preference_service' not in self._services:
            self._services['preference_service'] = UserPreferenceService(self.db)
        return self._services['preference_service']

    @property
    def export_service(self) -> UserDataExportService:
        """Get UserDataExportService instance."""
        if 'export_service' not in self._services:
            self._services['export_service'] = UserDataExportService(self.db)
        return self._services['export_service']

    @property
    def analytics_service(self) -> UserAnalyticsService:
        """Get UserAnalyticsService instance."""
        if 'analytics_service' not in self._services:
            self._services['analytics_service'] = UserAnalyticsService(self.db)
        return self._services['analytics_service']

    @property
    def notification_service(self) -> UserNotificationService:
        """Get UserNotificationService instance."""
        if 'notification_service' not in self._services:
            self._services['notification_service'] = UserNotificationService(self.db)
        return self._services['notification_service']

    @property
    def security_service(self) -> UserSecurityService:
        """Get UserSecurityService instance."""
        if 'security_service' not in self._services:
            self._services['security_service'] = UserSecurityService(self.db)
        return self._services['security_service']

    # ==================== Convenience Methods ====================

    def get_all_services(self) -> dict:
        """
        Get all services as dictionary.
        
        Returns:
            Dictionary of all service instances
        """
        return {
            'user': self.user_service,
            'profile': self.profile_service,
            'address': self.address_service,
            'contact': self.contact_service,
            'session': self.session_service,
            'verification': self.verification_service,
            'preference': self.preference_service,
            'export': self.export_service,
            'analytics': self.analytics_service,
            'notification': self.notification_service,
            'security': self.security_service
        }

    def clear_cache(self):
        """Clear cached service instances."""
        self._services.clear()


# Dependency injection helper
def get_user_services(db: Session) -> UserServiceFactory:
    """
    Get user service factory instance.
    
    Usage in FastAPI:
        @app.get("/users")
        def get_users(services: UserServiceFactory = Depends(get_user_services)):
            return services.user_service.search_users()
    
    Args:
        db: Database session
        
    Returns:
        UserServiceFactory instance
    """
    return UserServiceFactory(db)


