# app/services/notification/__init__.py
"""
Enhanced Notification Services Package

Provides comprehensive services for all notification channels with improved:
- Performance through optimizations and caching
- Error handling with comprehensive validation
- Analytics and monitoring capabilities
- Real-time delivery coordination
- Advanced routing and escalation
- Template management and rendering

Services:

Device Management:
  - DeviceTokenService: Enhanced device token management with validation and cleanup

In-App Notifications:
  - InAppNotificationService: Enhanced in-app notifications with real-time delivery and filtering

Email:
  - EmailNotificationService: Enhanced email notifications with template rendering and analytics

SMS:
  - SMSNotificationService: Enhanced SMS with cost optimization and multi-provider support

Push:
  - PushNotificationService: Enhanced push notifications with platform optimization

Preferences:
  - NotificationPreferenceService: Enhanced preference management with audit logging

Queue Management:
  - NotificationQueueService: Enhanced queue processing with worker management and health monitoring

Routing:
  - NotificationRoutingService: Enhanced routing with context-aware rules and escalation

Templates:
  - NotificationTemplateService: Enhanced template management with versioning and testing

Main Facade:
  - NotificationService: Enhanced unified API with intelligent routing and analytics

Version: 2.0.0 (Enhanced)
"""

from .device_token_service import DeviceTokenService
from .email_notification_service import EmailNotificationService
from .in_app_notification_service import InAppNotificationService
from .notification_preference_service import NotificationPreferenceService
from .notification_queue_service import NotificationQueueService
from .notification_routing_service import NotificationRoutingService
from .notification_service import NotificationService
from .notification_template_service import NotificationTemplateService
from .push_notification_service import PushNotificationService
from .sms_notification_service import SMSNotificationService

# Service registry for dependency injection and factory patterns
SERVICE_REGISTRY = {
    "device_token": DeviceTokenService,
    "email": EmailNotificationService,
    "in_app": InAppNotificationService,
    "preferences": NotificationPreferenceService,
    "queue": NotificationQueueService,
    "routing": NotificationRoutingService,
    "main": NotificationService,
    "template": NotificationTemplateService,
    "push": PushNotificationService,
    "sms": SMSNotificationService,
}

# Service dependencies mapping for proper initialization order
SERVICE_DEPENDENCIES = {
    "device_token": [],
    "template": [],
    "preferences": [],
    "routing": [],
    "queue": [],
    "email": ["template"],
    "sms": ["template"],
    "push": ["device_token"],
    "in_app": [],
    "main": [
        "in_app",
        "email", 
        "sms",
        "push",
        "routing",
        "queue"
    ],
}

# Service configuration defaults
SERVICE_CONFIG = {
    "device_token": {
        "cache_timeout": 300,
        "max_bulk_size": 1000,
        "cleanup_days": 90,
    },
    "email": {
        "max_bulk_size": 1000,
        "chunk_size": 100,
        "template_cache_ttl": 300,
    },
    "sms": {
        "max_batch_size": 1000,
        "max_message_length": 1600,
        "chunk_size": 100,
        "optimize_messages": True,
    },
    "push": {
        "max_batch_size": 1000,
        "max_payload_size": 4096,
        "platform_optimizations": True,
    },
    "in_app": {
        "default_page_size": 20,
        "max_page_size": 100,
        "max_bulk_mark_size": 500,
        "auto_cleanup_days": 30,
    },
    "preferences": {
        "default_preferences": {
            "email_notifications": True,
            "sms_notifications": True,
            "push_notifications": True,
            "in_app_notifications": True,
            "marketing_emails": False,
        }
    },
    "queue": {
        "max_retry_count": 3,
        "default_priority": "normal",
        "max_dequeue_size": 100,
        "health_check_interval": 300,
    },
    "routing": {
        "rule_cache_ttl": 300,
        "max_escalation_levels": 5,
        "default_channels": ["in_app", "email"],
    },
    "template": {
        "cache_ttl": 300,
        "max_template_size": 50000,
        "version_retention": 10,
    },
}

__all__ = [
    # Core services
    "DeviceTokenService",
    "EmailNotificationService", 
    "InAppNotificationService",
    "NotificationPreferenceService",
    "NotificationQueueService",
    "NotificationRoutingService",
    "NotificationService",
    "NotificationTemplateService",
    "PushNotificationService",
    "SMSNotificationService",
    
    # Utility exports
    "SERVICE_REGISTRY",
    "SERVICE_DEPENDENCIES", 
    "SERVICE_CONFIG",
]


def create_service_factory(config_override: dict = None):
    """
    Create a service factory with optional configuration override.
    
    Args:
        config_override: Optional configuration overrides
        
    Returns:
        Callable: Service factory function
    """
    def factory(service_name: str, **kwargs):
        """
        Create a service instance by name.
        
        Args:
            service_name: Name of service to create
            **kwargs: Additional initialization parameters
            
        Returns:
            Service instance
            
        Raises:
            ValueError: For unknown service names
        """
        if service_name not in SERVICE_REGISTRY:
            raise ValueError(
                f"Unknown service '{service_name}'. "
                f"Available services: {list(SERVICE_REGISTRY.keys())}"
            )
        
        service_class = SERVICE_REGISTRY[service_name]
        
        # Merge default config with overrides
        config = SERVICE_CONFIG.get(service_name, {}).copy()
        if config_override and service_name in config_override:
            config.update(config_override[service_name])
        
        # Add config to kwargs
        if config:
            kwargs.setdefault("config", config)
        
        return service_class(**kwargs)
    
    return factory


def validate_service_dependencies(services: dict):
    """
    Validate that all service dependencies are satisfied.
    
    Args:
        services: Dict of service_name -> service_instance
        
    Raises:
        ValueError: If dependencies are not satisfied
    """
    for service_name, dependencies in SERVICE_DEPENDENCIES.items():
        if service_name in services:
            for dependency in dependencies:
                if dependency not in services:
                    raise ValueError(
                        f"Service '{service_name}' requires dependency '{dependency}' "
                        f"which is not available in provided services"
                    )


def get_initialization_order():
    """
    Get the correct initialization order based on dependencies.
    
    Returns:
        List[str]: Service names in initialization order
    """
    # Topological sort of dependencies
    order = []
    visited = set()
    temp_visited = set()
    
    def visit(service):
        if service in temp_visited:
            raise ValueError(f"Circular dependency detected involving '{service}'")
        if service in visited:
            return
            
        temp_visited.add(service)
        
        for dependency in SERVICE_DEPENDENCIES.get(service, []):
            visit(dependency)
        
        temp_visited.remove(service)
        visited.add(service)
        order.append(service)
    
    for service in SERVICE_REGISTRY.keys():
        visit(service)
    
    return order


def create_all_services(repositories: dict, config_override: dict = None):
    """
    Create all notification services in the correct dependency order.
    
    Args:
        repositories: Dict of repository instances
        config_override: Optional configuration overrides
        
    Returns:
        Dict of service_name -> service_instance
        
    Raises:
        ValueError: If required repositories are missing
    """
    factory = create_service_factory(config_override)
    services = {}
    
    # Get initialization order
    init_order = get_initialization_order()
    
    for service_name in init_order:
        try:
            # Map service name to repository parameter name
            repo_mappings = {
                "device_token": "device_repo",
                "email": "email_repo", 
                "in_app": "notification_repo",
                "preferences": "pref_repo",
                "queue": "queue_repo",
                "routing": "routing_repo",
                "template": "template_repo",
                "push": ["push_repo", "device_repo"],
                "sms": "sms_repo",
                "main": [
                    "in_app_service",
                    "email_service",
                    "sms_service", 
                    "push_service",
                    "routing_service",
                    "queue_service"
                ],
            }
            
            kwargs = {}
            
            if service_name == "main":
                # Main service needs other service instances
                kwargs.update({
                    "in_app_service": services["in_app"],
                    "email_service": services["email"],
                    "sms_service": services["sms"],
                    "push_service": services["push"],
                    "routing_service": services["routing"],
                    "queue_service": services["queue"],
                })
            elif service_name == "push":
                # Push service needs two repositories
                kwargs.update({
                    "push_repo": repositories["push_notification"],
                    "device_repo": repositories["device_token"],
                })
            else:
                # Single repository services
                repo_name = repo_mappings[service_name]
                if isinstance(repo_name, str):
                    if repo_name.endswith("_repo"):
                        # Map to repository
                        actual_repo_name = repo_name.replace("_repo", "")
                        if service_name == "in_app":
                            actual_repo_name = "notification"  # Special case
                        elif service_name == "preferences":
                            actual_repo_name = "notification_preference"  # Special case
                        
                        if actual_repo_name in repositories:
                            kwargs[repo_name] = repositories[actual_repo_name]
                        else:
                            raise ValueError(f"Repository '{actual_repo_name}' not found")
            
            services[service_name] = factory(service_name, **kwargs)
            
        except Exception as e:
            raise ValueError(f"Failed to create service '{service_name}': {str(e)}")
    
    return services


# Version information
__enhanced_features__ = [
    "Comprehensive validation and error handling",
    "Performance optimizations with caching",
    "Advanced analytics and monitoring",
    "Real-time delivery coordination", 
    "Context-aware routing and escalation",
    "Template versioning and testing",
    "Multi-provider support with failover",
    "Cost optimization for SMS",
    "Platform-specific push optimizations",
    "Batch processing capabilities",
    "Health monitoring and diagnostics",
    "Audit logging and compliance features",
]