# app/repositories/supervisor/__init__.py
"""
Supervisor repositories package.

Provides data access layer for all supervisor-related entities
with comprehensive queries, analytics, and reporting capabilities.
"""

from app.repositories.supervisor.supervisor_repository import SupervisorRepository
from app.repositories.supervisor.supervisor_permissions_repository import (
    SupervisorPermissionsRepository
)
from app.repositories.supervisor.supervisor_assignment_repository import (
    SupervisorAssignmentRepository
)
from app.repositories.supervisor.supervisor_activity_repository import (
    SupervisorActivityRepository
)
from app.repositories.supervisor.supervisor_dashboard_repository import (
    SupervisorDashboardRepository
)
from app.repositories.supervisor.supervisor_performance_repository import (
    SupervisorPerformanceRepository
)
from app.repositories.supervisor.supervisor_aggregate_repository import (
    SupervisorAggregateRepository
)

__all__ = [
    # Core repository
    "SupervisorRepository",
    
    # Permission management
    "SupervisorPermissionsRepository",
    
    # Assignment management
    "SupervisorAssignmentRepository",
    
    # Activity tracking
    "SupervisorActivityRepository",
    
    # Dashboard data
    "SupervisorDashboardRepository",
    
    # Performance tracking
    "SupervisorPerformanceRepository",
    
    # Aggregate queries
    "SupervisorAggregateRepository",
]