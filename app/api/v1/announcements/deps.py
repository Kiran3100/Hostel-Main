"""
Enhanced dependency injection for announcement services.
"""
from functools import lru_cache
from typing import Type, TypeVar
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger
from app.services.announcement.announcement_service import AnnouncementService
from app.services.announcement.announcement_approval_service import AnnouncementApprovalService
from app.services.announcement.announcement_scheduling_service import AnnouncementSchedulingService
from app.services.announcement.announcement_targeting_service import AnnouncementTargetingService
from app.services.announcement.announcement_tracking_service import AnnouncementTrackingService

logger = get_logger(__name__)

ServiceType = TypeVar('ServiceType')


class ServiceFactory:
    """Centralized service factory with caching and error handling."""
    
    @staticmethod
    @lru_cache(maxsize=128)
    def _get_service_instance(service_class: Type[ServiceType], db_session_id: int) -> ServiceType:
        """Cache service instances per session to improve performance."""
        # Note: In real implementation, you'd need a proper session management strategy
        # This is a simplified approach for demonstration
        pass
    
    @staticmethod
    def create_service(service_class: Type[ServiceType], db: Session) -> ServiceType:
        """Create service instance with proper error handling."""
        try:
            return service_class(db=db)
        except Exception as e:
            logger.error(f"Failed to create service {service_class.__name__}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Service initialization failed"
            )


# Enhanced service dependency functions
def get_announcement_service(
    db: Session = Depends(deps.get_db)
) -> AnnouncementService:
    """Get announcement service with enhanced error handling."""
    return ServiceFactory.create_service(AnnouncementService, db)


def get_approval_service(
    db: Session = Depends(deps.get_db)
) -> AnnouncementApprovalService:
    """Get approval service with enhanced error handling."""
    return ServiceFactory.create_service(AnnouncementApprovalService, db)


def get_scheduling_service(
    db: Session = Depends(deps.get_db)
) -> AnnouncementSchedulingService:
    """Get scheduling service with enhanced error handling."""
    return ServiceFactory.create_service(AnnouncementSchedulingService, db)


def get_targeting_service(
    db: Session = Depends(deps.get_db)
) -> AnnouncementTargetingService:
    """Get targeting service with enhanced error handling."""
    return ServiceFactory.create_service(AnnouncementTargetingService, db)


def get_tracking_service(
    db: Session = Depends(deps.get_db)
) -> AnnouncementTrackingService:
    """Get tracking service with enhanced error handling."""
    return ServiceFactory.create_service(AnnouncementTrackingService, db)