"""
Inquiry service layer.

Provides comprehensive business logic for inquiry management:
- Core CRUD operations and status lifecycle
- Assignment and ownership management
- Follow-up tracking and timeline
- Conversion to bookings
- Analytics and reporting

Version: 2.0.0 (Enhanced)
"""

from app.services.inquiry.inquiry_service import InquiryService
from app.services.inquiry.inquiry_assignment_service import InquiryAssignmentService
from app.services.inquiry.inquiry_follow_up_service import InquiryFollowUpService
from app.services.inquiry.inquiry_conversion_service import InquiryConversionService
from app.services.inquiry.inquiry_analytics_service import InquiryAnalyticsService

__all__ = [
    "InquiryService",
    "InquiryAssignmentService",
    "InquiryFollowUpService",
    "InquiryConversionService",
    "InquiryAnalyticsService",
]

__version__ = "2.0.0"
__author__ = "Hostel Management System"
__description__ = "Enhanced inquiry management services with comprehensive business logic"

# Service initialization helpers
def get_inquiry_service(db_session, repository=None):
    """
    Factory function to get InquiryService instance.
    
    Args:
        db_session: SQLAlchemy database session
        repository: Optional InquiryRepository instance
        
    Returns:
        Configured InquiryService instance
    """
    if repository is None:
        from app.repositories.inquiry.inquiry_repository import InquiryRepository
        repository = InquiryRepository(db_session)
    
    return InquiryService(repository, db_session)


def get_inquiry_assignment_service(db_session, repository=None):
    """
    Factory function to get InquiryAssignmentService instance.
    
    Args:
        db_session: SQLAlchemy database session
        repository: Optional InquiryRepository instance
        
    Returns:
        Configured InquiryAssignmentService instance
    """
    if repository is None:
        from app.repositories.inquiry.inquiry_repository import InquiryRepository
        repository = InquiryRepository(db_session)
    
    return InquiryAssignmentService(repository, db_session)


def get_inquiry_follow_up_service(db_session, repository=None):
    """
    Factory function to get InquiryFollowUpService instance.
    
    Args:
        db_session: SQLAlchemy database session
        repository: Optional InquiryFollowUpRepository instance
        
    Returns:
        Configured InquiryFollowUpService instance
    """
    if repository is None:
        from app.repositories.inquiry.inquiry_follow_up_repository import InquiryFollowUpRepository
        repository = InquiryFollowUpRepository(db_session)
    
    return InquiryFollowUpService(repository, db_session)


def get_inquiry_conversion_service(db_session, repository=None):
    """
    Factory function to get InquiryConversionService instance.
    
    Args:
        db_session: SQLAlchemy database session
        repository: Optional InquiryRepository instance
        
    Returns:
        Configured InquiryConversionService instance
    """
    if repository is None:
        from app.repositories.inquiry.inquiry_repository import InquiryRepository
        repository = InquiryRepository(db_session)
    
    return InquiryConversionService(repository, db_session)


def get_inquiry_analytics_service(db_session, repository=None):
    """
    Factory function to get InquiryAnalyticsService instance.
    
    Args:
        db_session: SQLAlchemy database session
        repository: Optional InquiryAggregateRepository instance
        
    Returns:
        Configured InquiryAnalyticsService instance
    """
    if repository is None:
        from app.repositories.inquiry.inquiry_aggregate_repository import InquiryAggregateRepository
        repository = InquiryAggregateRepository(db_session)
    
    return InquiryAnalyticsService(repository, db_session)