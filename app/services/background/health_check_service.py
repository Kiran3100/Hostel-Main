"""
System health check service.

Aggregates health checks for:
- Database (connections, latency)
- Redis (availability, latency)
- External services (payments, email/SMS providers)

Performance improvements:
- Parallel health checks
- Timeout handling
- Detailed component metrics
- Health status caching
- Graceful degradation
"""

from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
import time

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult
from app.services.base.service_result import ServiceError, ErrorCode, ErrorSeverity
from app.core.logging import get_logger

# Config health checks
from app.config.database import DatabaseHealthCheck
from app.config.redis import RedisHealthCheck
from app.repositories.analytics import PlatformAnalyticsRepository
from app.models.analytics.platform_analytics import PlatformMetrics


class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(str, Enum):
    """System component types."""
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    STORAGE = "storage"
    EXTERNAL_API = "external_api"
    EMAIL = "email"
    SMS = "sms"
    PAYMENT = "payment"


@dataclass
class HealthCheckConfig:
    """Configuration for health checks."""
    enable_external_checks: bool = True
    check_timeout_seconds: int = 5
    parallel_checks: bool = True
    max_workers: int = 5
    cache_duration_seconds: int = 30
    
    # Thresholds
    db_latency_warning_ms: float = 100.0
    db_latency_critical_ms: float = 500.0
    redis_latency_warning_ms: float = 50.0
    redis_latency_critical_ms: float = 200.0
    external_latency_warning_ms: float = 1000.0
    external_latency_critical_ms: float = 3000.0


@dataclass
class ComponentHealth:
    """Health status of a system component."""
    component: str
    component_type: ComponentType
    status: HealthStatus
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SystemHealth:
    """Overall system health status."""
    status: HealthStatus
    components: List[ComponentHealth]
    timestamp: datetime
    healthy_count: int = 0
    degraded_count: int = 0
    unhealthy_count: int = 0
    unknown_count: int = 0
    total_check_duration_ms: float = 0.0


class HealthCheckService(BaseService[PlatformMetrics, PlatformAnalyticsRepository]):
    """
    Performs and aggregates health checks across system components.
    
    Features:
    - Parallel health check execution
    - Configurable timeouts and thresholds
    - Health status caching
    - Detailed component metrics
    - Graceful failure handling
    """

    def __init__(
        self,
        platform_repo: PlatformAnalyticsRepository,
        db_session: Session,
        config: Optional[HealthCheckConfig] = None,
    ):
        super().__init__(platform_repo, db_session)
        self.config = config or HealthCheckConfig()
        self.db_health = DatabaseHealthCheck()
        self.redis_health = RedisHealthCheck()
        self._logger = get_logger(self.__class__.__name__)
        self._health_cache: Optional[SystemHealth] = None
        self._cache_timestamp: Optional[datetime] = None

    def get_system_health(
        self,
        force_refresh: bool = False,
        include_external: Optional[bool] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Return consolidated health status and sub-component info.
        
        Args:
            force_refresh: Bypass cache and perform fresh checks
            include_external: Override config for external service checks
            
        Returns:
            ServiceResult with system health data
        """
        try:
            # Check cache
            if not force_refresh and self._is_cache_valid():
                self._logger.debug("Returning cached health status")
                return ServiceResult.success(
                    self._serialize_health(self._health_cache),
                    message="Health retrieved from cache"
                )
            
            start_time = time.time()
            
            # Determine which checks to run
            check_external = (
                include_external
                if include_external is not None
                else self.config.enable_external_checks
            )
            
            # Execute health checks
            if self.config.parallel_checks:
                components = self._run_parallel_checks(check_external)
            else:
                components = self._run_sequential_checks(check_external)
            
            # Calculate overall status
            overall_status = self._calculate_overall_status(components)
            
            # Build system health object
            duration_ms = (time.time() - start_time) * 1000
            system_health = SystemHealth(
                status=overall_status,
                components=components,
                timestamp=datetime.utcnow(),
                healthy_count=sum(1 for c in components if c.status == HealthStatus.HEALTHY),
                degraded_count=sum(1 for c in components if c.status == HealthStatus.DEGRADED),
                unhealthy_count=sum(1 for c in components if c.status == HealthStatus.UNHEALTHY),
                unknown_count=sum(1 for c in components if c.status == HealthStatus.UNKNOWN),
                total_check_duration_ms=round(duration_ms, 2),
            )
            
            # Update cache
            self._health_cache = system_health
            self._cache_timestamp = datetime.utcnow()
            
            # Log health status
            self._logger.info(
                f"System health: {overall_status.value} "
                f"({system_health.healthy_count} healthy, "
                f"{system_health.degraded_count} degraded, "
                f"{system_health.unhealthy_count} unhealthy) "
                f"in {duration_ms:.2f}ms"
            )
            
            return ServiceResult.success(
                self._serialize_health(system_health),
                message=f"Health check completed: {overall_status.value}"
            )
            
        except Exception as e:
            self._logger.error(f"Error getting system health: {str(e)}", exc_info=True)
            return self._handle_exception(e, "system health")

    def check_component(
        self,
        component: str,
        component_type: ComponentType,
    ) -> ServiceResult[ComponentHealth]:
        """
        Check health of a specific component.
        
        Args:
            component: Component name
            component_type: Type of component
            
        Returns:
            ServiceResult with component health
        """
        try:
            check_func = self._get_check_function(component, component_type)
            
            if not check_func:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No health check available for {component}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            component_health = self._execute_check(component, component_type, check_func)
            
            return ServiceResult.success(
                component_health,
                message=f"Component health: {component_health.status.value}"
            )
            
        except Exception as e:
            return self._handle_exception(e, f"check {component}")

    def _run_parallel_checks(self, include_external: bool) -> List[ComponentHealth]:
        """Execute health checks in parallel."""
        components = []
        check_tasks = self._get_check_tasks(include_external)
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_check = {
                executor.submit(
                    self._execute_check_with_timeout,
                    name,
                    comp_type,
                    func
                ): name
                for name, comp_type, func in check_tasks
            }
            
            for future in as_completed(future_to_check):
                check_name = future_to_check[future]
                try:
                    component_health = future.result()
                    components.append(component_health)
                except Exception as e:
                    self._logger.error(
                        f"Exception in parallel health check {check_name}: {str(e)}"
                    )
                    # Add failed check result
                    components.append(ComponentHealth(
                        component=check_name,
                        component_type=ComponentType.EXTERNAL_API,
                        status=HealthStatus.UNKNOWN,
                        error=str(e),
                    ))
        
        return components

    def _run_sequential_checks(self, include_external: bool) -> List[ComponentHealth]:
        """Execute health checks sequentially."""
        components = []
        check_tasks = self._get_check_tasks(include_external)
        
        for name, comp_type, func in check_tasks:
            try:
                component_health = self._execute_check_with_timeout(name, comp_type, func)
                components.append(component_health)
            except Exception as e:
                self._logger.error(f"Error in health check {name}: {str(e)}")
                components.append(ComponentHealth(
                    component=name,
                    component_type=comp_type,
                    status=HealthStatus.UNKNOWN,
                    error=str(e),
                ))
        
        return components

    def _get_check_tasks(
        self,
        include_external: bool
    ) -> List[tuple[str, ComponentType, Callable]]:
        """Get list of health check tasks to execute."""
        tasks = [
            ("database", ComponentType.DATABASE, self._check_database),
            ("redis", ComponentType.CACHE, self._check_redis),
        ]
        
        if include_external:
            tasks.extend([
                ("payments", ComponentType.PAYMENT, self._check_payments),
                ("email", ComponentType.EMAIL, self._check_email),
                ("sms", ComponentType.SMS, self._check_sms),
            ])
        
        return tasks

    def _execute_check_with_timeout(
        self,
        name: str,
        comp_type: ComponentType,
        check_func: Callable,
    ) -> ComponentHealth:
        """Execute a health check with timeout."""
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(check_func)
                return future.result(timeout=self.config.check_timeout_seconds)
        except TimeoutError:
            self._logger.warning(f"Health check timeout for {name}")
            return ComponentHealth(
                component=name,
                component_type=comp_type,
                status=HealthStatus.UNKNOWN,
                error=f"Check timeout after {self.config.check_timeout_seconds}s",
            )
        except Exception as e:
            return ComponentHealth(
                component=name,
                component_type=comp_type,
                status=HealthStatus.UNKNOWN,
                error=str(e),
            )

    def _execute_check(
        self,
        name: str,
        comp_type: ComponentType,
        check_func: Callable,
    ) -> ComponentHealth:
        """Execute a single health check."""
        start_time = time.time()
        
        try:
            result = check_func()
            latency_ms = (time.time() - start_time) * 1000
            
            # Determine status based on latency thresholds
            status = self._determine_status_from_latency(
                comp_type,
                latency_ms,
                result.get("is_healthy", False)
            )
            
            return ComponentHealth(
                component=name,
                component_type=comp_type,
                status=status,
                latency_ms=round(latency_ms, 2),
                details=result,
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._logger.error(f"Health check failed for {name}: {str(e)}")
            
            return ComponentHealth(
                component=name,
                component_type=comp_type,
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency_ms, 2),
                error=str(e),
            )

    def _check_database(self) -> Dict[str, Any]:
        """Check database health."""
        return self.db_health.check()

    def _check_redis(self) -> Dict[str, Any]:
        """Check Redis health."""
        return self.redis_health.check()

    def _check_payments(self) -> Dict[str, Any]:
        """Check payment provider health."""
        # Placeholder - implement actual payment provider health check
        return {
            "is_healthy": True,
            "provider": "unknown",
            "response_time_ms": None,
        }

    def _check_email(self) -> Dict[str, Any]:
        """Check email service health."""
        # Placeholder - implement actual email service health check
        return {
            "is_healthy": True,
            "provider": "unknown",
            "queue_size": 0,
        }

    def _check_sms(self) -> Dict[str, Any]:
        """Check SMS service health."""
        # Placeholder - implement actual SMS service health check
        return {
            "is_healthy": True,
            "provider": "unknown",
            "credits_remaining": None,
        }

    def _get_check_function(
        self,
        component: str,
        component_type: ComponentType
    ) -> Optional[Callable]:
        """Get health check function for a component."""
        check_map = {
            "database": self._check_database,
            "redis": self._check_redis,
            "payments": self._check_payments,
            "email": self._check_email,
            "sms": self._check_sms,
        }
        return check_map.get(component)

    def _determine_status_from_latency(
        self,
        comp_type: ComponentType,
        latency_ms: float,
        is_healthy: bool,
    ) -> HealthStatus:
        """Determine health status based on component type and latency."""
        if not is_healthy:
            return HealthStatus.UNHEALTHY
        
        # Get thresholds based on component type
        if comp_type == ComponentType.DATABASE:
            warning_threshold = self.config.db_latency_warning_ms
            critical_threshold = self.config.db_latency_critical_ms
        elif comp_type == ComponentType.CACHE:
            warning_threshold = self.config.redis_latency_warning_ms
            critical_threshold = self.config.redis_latency_critical_ms
        else:
            warning_threshold = self.config.external_latency_warning_ms
            critical_threshold = self.config.external_latency_critical_ms
        
        # Determine status
        if latency_ms >= critical_threshold:
            return HealthStatus.UNHEALTHY
        elif latency_ms >= warning_threshold:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def _calculate_overall_status(self, components: List[ComponentHealth]) -> HealthStatus:
        """Calculate overall system health from component statuses."""
        if not components:
            return HealthStatus.UNKNOWN
        
        # Count status types
        statuses = [c.status for c in components]
        unhealthy_count = statuses.count(HealthStatus.UNHEALTHY)
        degraded_count = statuses.count(HealthStatus.DEGRADED)
        
        # Determine overall status
        if unhealthy_count > 0:
            # Any unhealthy component makes system unhealthy
            return HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            # Any degraded component makes system degraded
            return HealthStatus.DEGRADED
        elif statuses.count(HealthStatus.HEALTHY) == len(components):
            # All components healthy
            return HealthStatus.HEALTHY
        else:
            # Mixed or unknown states
            return HealthStatus.DEGRADED

    def _is_cache_valid(self) -> bool:
        """Check if cached health data is still valid."""
        if self._health_cache is None or self._cache_timestamp is None:
            return False
        
        cache_age = datetime.utcnow() - self._cache_timestamp
        return cache_age.total_seconds() < self.config.cache_duration_seconds

    def _serialize_health(self, health: SystemHealth) -> Dict[str, Any]:
        """Convert SystemHealth object to dictionary."""
        return {
            "timestamp": health.timestamp.isoformat(),
            "status": health.status.value,
            "is_healthy": health.status == HealthStatus.HEALTHY,
            "summary": {
                "total_components": len(health.components),
                "healthy": health.healthy_count,
                "degraded": health.degraded_count,
                "unhealthy": health.unhealthy_count,
                "unknown": health.unknown_count,
            },
            "check_duration_ms": health.total_check_duration_ms,
            "components": [
                {
                    "name": c.component,
                    "type": c.component_type.value,
                    "status": c.status.value,
                    "latency_ms": c.latency_ms,
                    "error": c.error,
                    "details": c.details,
                    "checked_at": c.checked_at.isoformat(),
                }
                for c in health.components
            ],
        }

    def invalidate_cache(self) -> None:
        """Manually invalidate health check cache."""
        self._health_cache = None
        self._cache_timestamp = None
        self._logger.debug("Health check cache invalidated")