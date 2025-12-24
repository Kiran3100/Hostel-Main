"""
Background Services Module

This module provides background task execution services for the hostel management system.
Services include cleanup operations, data synchronization, health monitoring, metrics collection,
queue processing, and task scheduling.

Services:
    - CleanupService: Periodic cleanup of expired/obsolete data
    - DataSyncService: Third-party data synchronization
    - HealthCheckService: System health monitoring and aggregation
    - MetricsCollectionService: Operational metrics collection and analytics
    - QueueProcessorService: Multi-queue batch processing
    - TaskSchedulerService: Scheduled task execution across domains

Usage:
    from app.services.background import (
        CleanupService,
        DataSyncService,
        HealthCheckService,
        MetricsCollectionService,
        QueueProcessorService,
        TaskSchedulerService,
    )

Configuration:
    Each service accepts an optional configuration dataclass for customization:
    - CleanupConfig
    - SyncConfig
    - HealthCheckConfig
    - MetricsConfig
    - QueueProcessingConfig
    - SchedulerConfig

Example:
    # Initialize cleanup service with custom config
    from app.services.background import CleanupService, CleanupConfig
    
    config = CleanupConfig(
        blacklist_retention_days=60,
        enable_parallel=True
    )
    
    cleanup_service = CleanupService(
        otp_repo=otp_repo,
        session_repo=session_repo,
        blacklist_repo=blacklist_repo,
        file_upload_repo=file_upload_repo,
        ann_sched_repo=ann_sched_repo,
        ann_delivery_repo=ann_delivery_repo,
        audit_repo=audit_repo,
        db_session=db,
        config=config
    )
    
    # Execute daily cleanup
    result = cleanup_service.run_daily_cleanup()
    if result.success:
        print(f"Cleaned {result.data['total_cleaned']} items")
"""

from typing import List

# Import services
from .cleanup_service import CleanupService, CleanupConfig, CleanupTask, CleanupResult
from .data_sync_service import (
    DataSyncService,
    SyncConfig,
    SyncDirection,
    SyncStatus,
    SyncMetrics,
)
from .health_check_service import (
    HealthCheckService,
    HealthCheckConfig,
    HealthStatus,
    ComponentType,
    ComponentHealth,
    SystemHealth,
)
from .metrics_collection_service import (
    MetricsCollectionService,
    MetricsConfig,
    MetricCategory,
    MetricSnapshot,
    MetricsReport,
)
from .queue_processor_service import (
    QueueProcessorService,
    QueueProcessingConfig,
    QueueType,
    ProcessingStatus,
    ProcessingMetrics,
)
from .task_scheduler_service import (
    TaskSchedulerService,
    SchedulerConfig,
    TaskType,
    TaskStatus,
    TaskPriority,
    TaskExecution,
    SchedulerReport,
)

# Version info
__version__ = "1.0.0"
__author__ = "Hostel Management System Team"

# Public API
__all__: List[str] = [
    # Services
    "CleanupService",
    "DataSyncService",
    "HealthCheckService",
    "MetricsCollectionService",
    "QueueProcessorService",
    "TaskSchedulerService",
    # Cleanup exports
    "CleanupConfig",
    "CleanupTask",
    "CleanupResult",
    # Sync exports
    "SyncConfig",
    "SyncDirection",
    "SyncStatus",
    "SyncMetrics",
    # Health check exports
    "HealthCheckConfig",
    "HealthStatus",
    "ComponentType",
    "ComponentHealth",
    "SystemHealth",
    # Metrics exports
    "MetricsConfig",
    "MetricCategory",
    "MetricSnapshot",
    "MetricsReport",
    # Queue processor exports
    "QueueProcessingConfig",
    "QueueType",
    "ProcessingStatus",
    "ProcessingMetrics",
    # Scheduler exports
    "SchedulerConfig",
    "TaskType",
    "TaskStatus",
    "TaskPriority",
    "TaskExecution",
    "SchedulerReport",
]


def get_all_services() -> List[str]:
    """
    Get list of all available background services.
    
    Returns:
        List of service class names
    """
    return [
        "CleanupService",
        "DataSyncService",
        "HealthCheckService",
        "MetricsCollectionService",
        "QueueProcessorService",
        "TaskSchedulerService",
    ]


def get_service_info(service_name: str) -> dict:
    """
    Get information about a specific service.
    
    Args:
        service_name: Name of the service class
        
    Returns:
        Dictionary with service information
        
    Raises:
        ValueError: If service name is not recognized
    """
    service_map = {
        "CleanupService": {
            "name": "Cleanup Service",
            "description": "Periodic cleanup of expired/obsolete data",
            "config_class": "CleanupConfig",
            "tasks": [
                "OTP tokens cleanup",
                "User sessions cleanup",
                "Blacklisted tokens cleanup",
                "Temporary uploads cleanup",
                "Stale queues cleanup",
                "Audit logs cleanup",
            ],
        },
        "DataSyncService": {
            "name": "Data Sync Service",
            "description": "Third-party data synchronization",
            "config_class": "SyncConfig",
            "tasks": [
                "Pull webhooks",
                "Pull updates from providers",
                "Push updates to providers",
                "Data reconciliation",
            ],
        },
        "HealthCheckService": {
            "name": "Health Check Service",
            "description": "System health monitoring and aggregation",
            "config_class": "HealthCheckConfig",
            "tasks": [
                "Database health check",
                "Redis health check",
                "External services health check",
                "System health aggregation",
            ],
        },
        "MetricsCollectionService": {
            "name": "Metrics Collection Service",
            "description": "Operational metrics collection and analytics",
            "config_class": "MetricsConfig",
            "tasks": [
                "Performance metrics collection",
                "Capacity metrics collection",
                "Availability metrics collection",
                "Usage metrics collection",
                "Error metrics collection",
                "Trend analysis",
            ],
        },
        "QueueProcessorService": {
            "name": "Queue Processor Service",
            "description": "Multi-queue batch processing",
            "config_class": "QueueProcessingConfig",
            "tasks": [
                "Notification queue processing",
                "Announcement delivery processing",
                "Webhook processing",
                "Dead letter queue management",
            ],
        },
        "TaskSchedulerService": {
            "name": "Task Scheduler Service",
            "description": "Scheduled task execution across domains",
            "config_class": "SchedulerConfig",
            "tasks": [
                "Announcement publishing",
                "Report generation",
                "Billing cycle generation",
                "Task prioritization and timeout handling",
            ],
        },
    }
    
    if service_name not in service_map:
        raise ValueError(
            f"Unknown service: {service_name}. "
            f"Available services: {', '.join(service_map.keys())}"
        )
    
    return service_map[service_name]


# Module-level documentation
BACKGROUND_SERVICES_DOCS = """
Background Services Module
===========================

This module provides comprehensive background task execution capabilities for the
hostel management system. All services follow consistent patterns:

1. Configuration via dataclasses with sensible defaults
2. ServiceResult return pattern for consistent error handling
3. Comprehensive logging and metrics
4. Transaction management with proper rollback
5. Optional parallel execution where applicable

Service Initialization Pattern:
--------------------------------
All services require their specific repositories and a database session.
Optional configuration can be provided for customization.

    service = ServiceClass(
        required_repo_1=repo1,
        required_repo_2=repo2,
        db_session=db,
        config=CustomConfig()  # Optional
    )

Execution Pattern:
------------------
All services return ServiceResult objects:

    result = service.execute_operation()
    if result.success:
        # Handle success
        data = result.data
        print(result.message)
    else:
        # Handle failure
        error = result.error
        print(f"Error: {error.message}")

Best Practices:
---------------
1. Always check result.success before accessing result.data
2. Use configuration objects to customize behavior
3. Monitor service metrics and logs
4. Handle database sessions appropriately (commit/rollback)
5. Set appropriate timeouts for long-running operations
6. Use parallel execution judiciously based on workload

Performance Considerations:
---------------------------
- Batch sizes should be tuned based on database performance
- Parallel execution adds overhead; test before enabling
- Monitor database connection pool usage
- Set appropriate retention periods for cleanup operations
- Cache health check results when appropriate
- Use metrics collection to identify bottlenecks

Error Handling:
---------------
All services use the ServiceResult pattern with detailed error information:
- Error codes (ErrorCode enum)
- Severity levels (ErrorSeverity enum)
- Contextual error messages
- Optional error details dictionary

For more information on specific services, use get_service_info(service_name).
"""


def print_module_info():
    """Print comprehensive module information."""
    print(BACKGROUND_SERVICES_DOCS)
    print("\nAvailable Services:")
    print("=" * 80)
    
    for service_name in get_all_services():
        info = get_service_info(service_name)
        print(f"\n{info['name']}")
        print("-" * len(info['name']))
        print(f"Class: {service_name}")
        print(f"Config: {info['config_class']}")
        print(f"Description: {info['description']}")
        print("\nCapabilities:")
        for task in info['tasks']:
            print(f"  • {task}")
    
    print("\n" + "=" * 80)


# Validation function for imports
def validate_imports():
    """
    Validate that all services and configurations are properly imported.
    
    Raises:
        ImportError: If any required component is missing
    """
    required_services = [
        CleanupService,
        DataSyncService,
        HealthCheckService,
        MetricsCollectionService,
        QueueProcessorService,
        TaskSchedulerService,
    ]
    
    required_configs = [
        CleanupConfig,
        SyncConfig,
        HealthCheckConfig,
        MetricsConfig,
        QueueProcessingConfig,
        SchedulerConfig,
    ]
    
    required_enums = [
        CleanupTask,
        SyncDirection,
        SyncStatus,
        HealthStatus,
        ComponentType,
        MetricCategory,
        QueueType,
        ProcessingStatus,
        TaskType,
        TaskStatus,
        TaskPriority,
    ]
    
    for service in required_services:
        if not service:
            raise ImportError(f"Failed to import service: {service.__name__}")
    
    for config in required_configs:
        if not config:
            raise ImportError(f"Failed to import config: {config.__name__}")
    
    for enum in required_enums:
        if not enum:
            raise ImportError(f"Failed to import enum: {enum.__name__}")


# Run validation on import
try:
    validate_imports()
except ImportError as e:
    import warnings
    warnings.warn(f"Background services import validation failed: {str(e)}")


# Convenience function for getting default configurations
def get_default_configs() -> dict:
    """
    Get default configurations for all services.
    
    Returns:
        Dictionary mapping service names to default config instances
    """
    return {
        "cleanup": CleanupConfig(),
        "sync": SyncConfig(),
        "health_check": HealthCheckConfig(),
        "metrics": MetricsConfig(),
        "queue_processor": QueueProcessingConfig(),
        "scheduler": SchedulerConfig(),
    }


# Convenience function for creating service documentation
def generate_service_docs(service_name: str) -> str:
    """
    Generate detailed documentation for a specific service.
    
    Args:
        service_name: Name of the service class
        
    Returns:
        Formatted documentation string
    """
    try:
        info = get_service_info(service_name)
        
        docs = f"""
{info['name']}
{'=' * len(info['name'])}

Description: {info['description']}
Configuration: {info['config_class']}

Capabilities:
{chr(10).join(f'  • {task}' for task in info['tasks'])}

Usage Example:
--------------
from app.services.background import {service_name}, {info['config_class']}

# Create custom configuration (optional)
config = {info['config_class']}(
    # Add configuration parameters here
)

# Initialize service
service = {service_name}(
    # Add required repositories
    db_session=db,
    config=config  # Optional
)

# Execute service operation
result = service.main_operation()
if result.success:
    print(f"Success: {{result.message}}")
    print(f"Data: {{result.data}}")
else:
    print(f"Error: {{result.error.message}}")
"""
        return docs
        
    except ValueError as e:
        return f"Error: {str(e)}"


# Quick reference guide
QUICK_REFERENCE = """
Background Services Quick Reference
====================================

Import Pattern:
    from app.services.background import ServiceName, ConfigName

Service Creation:
    service = ServiceName(
        required_repos...,
        db_session=db,
        config=ConfigName()  # Optional
    )

Execution Pattern:
    result = service.operation()
    if result.success:
        data = result.data
    else:
        error = result.error

Common Configurations:
    • batch_size: Number of items per batch
    • enable_parallel: Enable parallel processing
    • max_workers: Thread pool size
    • timeout_seconds: Operation timeout
    • retention_days: Data retention period

For detailed docs: generate_service_docs('ServiceName')
For module info: print_module_info()
For service list: get_all_services()
"""


def show_quick_reference():
    """Display quick reference guide."""
    print(QUICK_REFERENCE)