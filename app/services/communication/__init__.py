"""
Communication service layer.

Provides comprehensive business logic for multi-channel communication:
- Unified communication orchestration (email, SMS, push, in-app)
- Channel-specific services (email, SMS)
- Broadcast messaging with routing and preferences
- Chat and chatbot interactions
- Communication analytics and reporting

Version: 1.1.0
"""

from typing import List

# Core communication services
from app.services.communication.communication_service import CommunicationService
from app.services.communication.email_service import EmailService
from app.services.communication.sms_service import SMSService

# Specialized services
from app.services.communication.broadcast_service import BroadcastService
from app.services.communication.chat_service import ChatService
from app.services.communication.chatbot_service import ChatbotService
from app.services.communication.communication_analytics_service import (
    CommunicationAnalyticsService,
    AnalyticsPeriod,
)


__all__: List[str] = [
    # Primary services
    "CommunicationService",
    "EmailService",
    "SMSService",
    
    # Specialized services
    "BroadcastService",
    "ChatService",
    "ChatbotService",
    "CommunicationAnalyticsService",
    
    # Enums and utilities
    "AnalyticsPeriod",
]

__version__ = "1.1.0"
__author__ = "Hostel Management System"
__description__ = "Multi-channel communication service layer"


# Service registry for dynamic loading (optional)
SERVICE_REGISTRY = {
    "communication": CommunicationService,
    "email": EmailService,
    "sms": SMSService,
    "broadcast": BroadcastService,
    "chat": ChatService,
    "chatbot": ChatbotService,
    "analytics": CommunicationAnalyticsService,
}


def get_service(service_name: str):
    """
    Get service class by name.
    
    Args:
        service_name: Name of the service
        
    Returns:
        Service class or None if not found
    """
    return SERVICE_REGISTRY.get(service_name.lower())


def list_services() -> List[str]:
    """
    List all available service names.
    
    Returns:
        List of service names
    """
    return list(SERVICE_REGISTRY.keys())