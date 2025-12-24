"""
Enhanced Workflow Services Package

Comprehensive workflow orchestration system with advanced features:
- Intelligent workflow execution engine
- Multi-level approval workflows  
- Comprehensive onboarding and checkout processes
- Advanced escalation management
- Multi-channel notification orchestration
- Intelligent scheduled task management

This package provides enterprise-grade workflow management capabilities
for hostel management systems with performance optimization, monitoring,
and reliability features.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

# Core workflow engine
from .workflow_engine_service import (
    WorkflowEngineService,
    workflow_engine,
    WorkflowDefinition,
    WorkflowState,
    WorkflowPriority,
    WorkflowExecution,
    WorkflowStep,
    create_workflow,
    create_step,
    workflow_step,
    workflow_validator,
    StepMetrics,
    WorkflowMetrics
)

# Business workflow services
from .approval_workflow_service import (
    ApprovalWorkflowService,
    ApprovalDecision,
    ApprovalRule,
    ApprovalContext
)

from .onboarding_workflow_service import (
    OnboardingWorkflowService,
    OnboardingStage,
    DocumentType,
    OnboardingChecklist,
    OnboardingContext
)

from .checkout_workflow_service import (
    CheckoutWorkflowService,
    CheckoutStage,
    ClearanceStatus,
    ClearanceCertificate,
    FinancialSettlement,
    CheckoutContext
)

from .escalation_workflow_service import (
    EscalationWorkflowService,
    EscalationType,
    EscalationLevel,
    EscalationTrigger,
    EscalationRule,
    SLAConfiguration,
    EscalationMetrics
)

from .notification_workflow_service import (
    NotificationWorkflowService,
    DeliveryStrategy,
    NotificationStatus,
    NotificationTemplate,
    DeliveryMetrics,
    UserNotificationPreference
)

from .scheduled_task_service import (
    ScheduledTaskService,
    TaskPriority,
    TaskStatus,
    TaskFrequency,
    TaskConfiguration,
    TaskExecution,
    TaskMetrics
)

# Package metadata
__version__ = "2.0.0"
__author__ = "Hostel Management System Team"
__description__ = "Enhanced workflow orchestration services for hostel management"

# Configure logging for the workflow package
logger = logging.getLogger(__name__)


# Workflow registry for dynamic service discovery
class WorkflowRegistry:
    """
    Central registry for workflow services and configurations.
    
    Provides service discovery, health monitoring, and configuration management
    for all workflow services in the system.
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._health_status: Dict[str, str] = {}
        self._configurations: Dict[str, Dict[str, Any]] = {}
        self._metrics: Dict[str, Dict[str, Any]] = {}
        
    def register_service(
        self, 
        service_name: str, 
        service_instance: Any,
        configuration: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register a workflow service with the registry."""
        self._services[service_name] = service_instance
        self._health_status[service_name] = "healthy"
        self._configurations[service_name] = configuration or {}
        self._metrics[service_name] = {}
        
        logger.info(f"Registered workflow service: {service_name}")
    
    def get_service(self, service_name: str) -> Optional[Any]:
        """Get a registered workflow service."""
        return self._services.get(service_name)
    
    def get_all_services(self) -> Dict[str, Any]:
        """Get all registered workflow services."""
        return self._services.copy()
    
    def get_service_health(self, service_name: str) -> Optional[str]:
        """Get health status of a workflow service."""
        return self._health_status.get(service_name)
    
    def update_service_health(self, service_name: str, status: str) -> None:
        """Update health status of a workflow service."""
        if service_name in self._services:
            self._health_status[service_name] = status
            logger.debug(f"Updated health status for {service_name}: {status}")
    
    def get_service_metrics(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a workflow service."""
        return self._metrics.get(service_name)
    
    def update_service_metrics(
        self, 
        service_name: str, 
        metrics: Dict[str, Any]
    ) -> None:
        """Update metrics for a workflow service."""
        if service_name in self._services:
            self._metrics[service_name].update(metrics)
    
    def get_system_overview(self) -> Dict[str, Any]:
        """Get comprehensive system overview."""
        return {
            "total_services": len(self._services),
            "healthy_services": sum(1 for status in self._health_status.values() if status == "healthy"),
            "service_status": dict(self._health_status),
            "last_updated": datetime.utcnow().isoformat()
        }


# Global workflow registry instance
workflow_registry = WorkflowRegistry()


# Workflow service factory
class WorkflowServiceFactory:
    """
    Factory for creating and configuring workflow services with proper dependencies.
    
    Handles dependency injection, configuration management, and service lifecycle.
    """
    
    @staticmethod
    def create_approval_workflow_service(
        booking_approval_repo,
        maintenance_approval_repo,
        leave_approval_repo,
        notification_service,
        escalation_service,
        **kwargs
    ) -> ApprovalWorkflowService:
        """Create and configure approval workflow service."""
        service = ApprovalWorkflowService(
            booking_approval_repo=booking_approval_repo,
            maintenance_approval_repo=maintenance_approval_repo,
            leave_approval_repo=leave_approval_repo,
            notification_service=notification_service,
            escalation_service=escalation_service
        )
        
        # Register with registry
        workflow_registry.register_service("approval_workflow", service, kwargs)
        
        return service
    
    @staticmethod
    def create_onboarding_workflow_service(
        booking_repo,
        student_repo,
        bed_assignment_repo,
        payment_repo,
        document_repo,
        conversion_repo,
        notification_service,
        **kwargs
    ) -> OnboardingWorkflowService:
        """Create and configure onboarding workflow service."""
        service = OnboardingWorkflowService(
            booking_repo=booking_repo,
            student_repo=student_repo,
            bed_assignment_repo=bed_assignment_repo,
            payment_repo=payment_repo,
            document_repo=document_repo,
            conversion_repo=conversion_repo,
            notification_service=notification_service
        )
        
        # Register with registry
        workflow_registry.register_service("onboarding_workflow", service, kwargs)
        
        return service
    
    @staticmethod
    def create_checkout_workflow_service(
        student_repo,
        bed_assignment_repo,
        payment_repo,
        ledger_repo,
        complaint_repo,
        maintenance_repo,
        inventory_repo,
        notification_service,
        **kwargs
    ) -> CheckoutWorkflowService:
        """Create and configure checkout workflow service."""
        service = CheckoutWorkflowService(
            student_repo=student_repo,
            bed_assignment_repo=bed_assignment_repo,
            payment_repo=payment_repo,
            ledger_repo=ledger_repo,
            complaint_repo=complaint_repo,
            maintenance_repo=maintenance_repo,
            inventory_repo=inventory_repo,
            notification_service=notification_service
        )
        
        # Register with registry
        workflow_registry.register_service("checkout_workflow", service, kwargs)
        
        return service
    
    @staticmethod
    def create_escalation_workflow_service(
        complaint_repo,
        complaint_escalation_repo,
        auto_escalation_rule_repo,
        admin_repo,
        supervisor_repo,
        notification_service,
        **kwargs
    ) -> EscalationWorkflowService:
        """Create and configure escalation workflow service."""
        service = EscalationWorkflowService(
            complaint_repo=complaint_repo,
            complaint_escalation_repo=complaint_escalation_repo,
            auto_escalation_rule_repo=auto_escalation_rule_repo,
            admin_repo=admin_repo,
            supervisor_repo=supervisor_repo,
            notification_service=notification_service
        )
        
        # Register with registry
        workflow_registry.register_service("escalation_workflow", service, kwargs)
        
        return service
    
    @staticmethod
    def create_notification_workflow_service(
        notification_repo,
        template_repo,
        queue_repo,
        preference_repo,
        analytics_repo,
        email_service,
        sms_service,
        push_service,
        **kwargs
    ) -> NotificationWorkflowService:
        """Create and configure notification workflow service."""
        service = NotificationWorkflowService(
            notification_repo=notification_repo,
            template_repo=template_repo,
            queue_repo=queue_repo,
            preference_repo=preference_repo,
            analytics_repo=analytics_repo,
            email_service=email_service,
            sms_service=sms_service,
            push_service=push_service
        )
        
        # Register with registry
        workflow_registry.register_service("notification_workflow", service, kwargs)
        
        return service
    
    @staticmethod
    def create_scheduled_task_service(
        escalation_service,
        announcement_schedule_repo,
        payment_reminder_repo,
        booking_analytics_repo,
        complaint_analytics_repo,
        financial_analytics_repo,
        occupancy_analytics_repo,
        maintenance_schedule_repo,
        audit_aggregate_repo,
        hostel_repo,
        redis_client=None,
        celery_app=None,
        **kwargs
    ) -> ScheduledTaskService:
        """Create and configure scheduled task service."""
        service = ScheduledTaskService(
            escalation_service=escalation_service,
            announcement_schedule_repo=announcement_schedule_repo,
            payment_reminder_repo=payment_reminder_repo,
            booking_analytics_repo=booking_analytics_repo,
            complaint_analytics_repo=complaint_analytics_repo,
            financial_analytics_repo=financial_analytics_repo,
            occupancy_analytics_repo=occupancy_analytics_repo,
            maintenance_schedule_repo=maintenance_schedule_repo,
            audit_aggregate_repo=audit_aggregate_repo,
            hostel_repo=hostel_repo,
            redis_client=redis_client,
            celery_app=celery_app
        )
        
        # Register with registry
        workflow_registry.register_service("scheduled_task", service, kwargs)
        
        return service


# Health monitoring utilities
async def check_workflow_health() -> Dict[str, Any]:
    """Check health of all workflow services."""
    health_report = {
        "overall_status": "healthy",
        "services": {},
        "issues": [],
        "timestamp": datetime.utcnow().isoformat()
    }
    
    services = workflow_registry.get_all_services()
    
    for service_name, service_instance in services.items():
        try:
            # Check service health if method exists
            if hasattr(service_instance, 'health_check'):
                service_health = await service_instance.health_check()
                health_report["services"][service_name] = service_health
            else:
                # Default health check
                health_report["services"][service_name] = {
                    "status": "healthy",
                    "message": "Service operational"
                }
                
            # Update registry
            status = health_report["services"][service_name]["status"]
            workflow_registry.update_service_health(service_name, status)
            
        except Exception as e:
            health_report["services"][service_name] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_report["issues"].append(f"{service_name}: {str(e)}")
            workflow_registry.update_service_health(service_name, "unhealthy")
    
    # Determine overall status
    unhealthy_services = [
        name for name, health in health_report["services"].items()
        if health["status"] != "healthy"
    ]
    
    if unhealthy_services:
        health_report["overall_status"] = "degraded" if len(unhealthy_services) < len(services) / 2 else "unhealthy"
    
    return health_report


# Performance monitoring
async def get_workflow_metrics() -> Dict[str, Any]:
    """Get comprehensive workflow performance metrics."""
    metrics_report = {
        "engine_metrics": workflow_engine.get_statistics(),
        "service_metrics": {},
        "system_overview": workflow_registry.get_system_overview(),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Get metrics from each service
    services = workflow_registry.get_all_services()
    
    for service_name, service_instance in services.items():
        try:
            if hasattr(service_instance, 'get_metrics'):
                service_metrics = await service_instance.get_metrics()
                metrics_report["service_metrics"][service_name] = service_metrics
                
                # Update registry
                workflow_registry.update_service_metrics(service_name, service_metrics)
                
        except Exception as e:
            logger.error(f"Failed to get metrics for {service_name}: {str(e)}")
            metrics_report["service_metrics"][service_name] = {"error": str(e)}
    
    return metrics_report


# Configuration management
def configure_workflow_services(config: Dict[str, Any]) -> None:
    """Configure all workflow services with provided configuration."""
    
    # Configure workflow engine
    if "workflow_engine" in config:
        engine_config = config["workflow_engine"]
        
        # Apply engine configuration
        if "max_execution_history" in engine_config:
            workflow_engine.max_execution_history = engine_config["max_execution_history"]
        
        if "enable_persistence" in engine_config:
            workflow_engine.enable_persistence = engine_config["enable_persistence"]
        
        if "enable_monitoring" in engine_config:
            workflow_engine.enable_monitoring = engine_config["enable_monitoring"]
    
    # Configure individual services
    services = workflow_registry.get_all_services()
    
    for service_name, service_instance in services.items():
        if service_name in config and hasattr(service_instance, 'configure'):
            try:
                service_instance.configure(config[service_name])
                logger.info(f"Configured service: {service_name}")
            except Exception as e:
                logger.error(f"Failed to configure {service_name}: {str(e)}")
    
    logger.info("Workflow services configuration completed")


# Package initialization
def initialize_workflow_services(
    repositories: Dict[str, Any],
    external_services: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Initialize all workflow services with proper dependencies.
    
    Args:
        repositories: Dictionary of repository instances
        external_services: Dictionary of external service instances
        config: Optional configuration dictionary
        
    Returns:
        Dictionary of initialized workflow services
    """
    logger.info("Initializing workflow services...")
    
    # Create notification service first (dependency for others)
    notification_service = WorkflowServiceFactory.create_notification_workflow_service(
        notification_repo=repositories.get("notification"),
        template_repo=repositories.get("notification_template"),
        queue_repo=repositories.get("notification_queue"),
        preference_repo=repositories.get("notification_preference"),
        analytics_repo=repositories.get("notification_analytics"),
        email_service=external_services.get("email"),
        sms_service=external_services.get("sms"),
        push_service=external_services.get("push")
    )
    
    # Create escalation service (dependency for others)
    escalation_service = WorkflowServiceFactory.create_escalation_workflow_service(
        complaint_repo=repositories.get("complaint"),
        complaint_escalation_repo=repositories.get("complaint_escalation"),
        auto_escalation_rule_repo=repositories.get("auto_escalation_rule"),
        admin_repo=repositories.get("admin"),
        supervisor_repo=repositories.get("supervisor"),
        notification_service=notification_service
    )
    
    # Create approval workflow service
    approval_service = WorkflowServiceFactory.create_approval_workflow_service(
        booking_approval_repo=repositories.get("booking_approval"),
        maintenance_approval_repo=repositories.get("maintenance_approval"),
        leave_approval_repo=repositories.get("leave_approval"),
        notification_service=notification_service,
        escalation_service=escalation_service
    )
    
    # Create onboarding workflow service
    onboarding_service = WorkflowServiceFactory.create_onboarding_workflow_service(
        booking_repo=repositories.get("booking"),
        student_repo=repositories.get("student"),
        bed_assignment_repo=repositories.get("bed_assignment"),
        payment_repo=repositories.get("payment"),
        document_repo=repositories.get("student_document"),
        conversion_repo=repositories.get("booking_conversion"),
        notification_service=notification_service
    )
    
    # Create checkout workflow service
    checkout_service = WorkflowServiceFactory.create_checkout_workflow_service(
        student_repo=repositories.get("student"),
        bed_assignment_repo=repositories.get("bed_assignment"),
        payment_repo=repositories.get("payment"),
        ledger_repo=repositories.get("payment_ledger"),
        complaint_repo=repositories.get("complaint"),
        maintenance_repo=repositories.get("maintenance"),
        inventory_repo=repositories.get("inventory_item"),
        notification_service=notification_service
    )
    
    # Create scheduled task service
    scheduled_task_service = WorkflowServiceFactory.create_scheduled_task_service(
        escalation_service=escalation_service,
        announcement_schedule_repo=repositories.get("announcement_scheduling"),
        payment_reminder_repo=repositories.get("payment_reminder"),
        booking_analytics_repo=repositories.get("booking_analytics"),
        complaint_analytics_repo=repositories.get("complaint_analytics"),
        financial_analytics_repo=repositories.get("financial_analytics"),
        occupancy_analytics_repo=repositories.get("occupancy_analytics"),
        maintenance_schedule_repo=repositories.get("maintenance_schedule"),
        audit_aggregate_repo=repositories.get("audit_aggregate"),
        hostel_repo=repositories.get("hostel"),
        redis_client=external_services.get("redis"),
        celery_app=external_services.get("celery")
    )
    
    # Apply configuration if provided
    if config:
        configure_workflow_services(config)
    
    # Collect all services
    services = {
        "approval_workflow": approval_service,
        "onboarding_workflow": onboarding_service,
        "checkout_workflow": checkout_service,
        "escalation_workflow": escalation_service,
        "notification_workflow": notification_service,
        "scheduled_task": scheduled_task_service,
        "workflow_engine": workflow_engine,
        "workflow_registry": workflow_registry
    }
    
    logger.info(f"Workflow services initialized successfully: {len(services)} services")
    
    return services


# Export all public components
__all__ = [
    # Core Engine
    "WorkflowEngineService",
    "workflow_engine",
    "WorkflowDefinition",
    "WorkflowState",
    "WorkflowPriority",
    "WorkflowExecution",
    "WorkflowStep",
    "create_workflow",
    "create_step",
    "workflow_step",
    "workflow_validator",
    "StepMetrics",
    "WorkflowMetrics",
    
    # Business Services
    "ApprovalWorkflowService",
    "OnboardingWorkflowService",
    "CheckoutWorkflowService",
    "EscalationWorkflowService",
    "NotificationWorkflowService",
    "ScheduledTaskService",
    
    # Enums and Data Classes
    "ApprovalDecision",
    "ApprovalRule",
    "ApprovalContext",
    "OnboardingStage",
    "DocumentType",
    "OnboardingChecklist",
    "OnboardingContext",
    "CheckoutStage",
    "ClearanceStatus",
    "ClearanceCertificate",
    "FinancialSettlement",
    "CheckoutContext",
    "EscalationType",
    "EscalationLevel",
    "EscalationTrigger",
    "EscalationRule",
    "SLAConfiguration",
    "EscalationMetrics",
    "DeliveryStrategy",
    "NotificationStatus",
    "NotificationTemplate",
    "DeliveryMetrics",
    "UserNotificationPreference",
    "TaskPriority",
    "TaskStatus",
    "TaskFrequency",
    "TaskConfiguration",
    "TaskExecution",
    "TaskMetrics",
    
    # Management and Utilities
    "workflow_registry",
    "WorkflowRegistry",
    "WorkflowServiceFactory",
    "check_workflow_health",
    "get_workflow_metrics",
    "configure_workflow_services",
    "initialize_workflow_services",
]