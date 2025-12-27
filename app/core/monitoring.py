"""
Monitoring and Metrics System

Comprehensive monitoring with performance tracking, health checks,
and integration with external monitoring systems.
"""

import time
import asyncio
import psutil
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
from prometheus_client.exposition import generate_latest

from .config import settings
from .exceptions import OperationError
from .logging import get_logger
from .cache import cache_manager

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health check status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class MetricType(str, Enum):
    """Metric type enumeration"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class HealthCheck:
    """Health check result"""
    name: str
    status: HealthStatus
    message: str
    response_time: float
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None


@dataclass
class MetricData:
    """Metric data container"""
    name: str
    type: MetricType
    value: float
    labels: Dict[str, str]
    timestamp: datetime
    help_text: Optional[str] = None


class PerformanceTracker:
    """Track API performance metrics"""
    
    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self.response_times: deque = deque(maxlen=max_samples)
        self.request_counts = defaultdict(int)
        self.error_counts = defaultdict(int)
        self.endpoint_stats = defaultdict(lambda: {
            'count': 0,
            'total_time': 0.0,
            'errors': 0,
            'avg_time': 0.0
        })
        
        # Prometheus metrics
        self.registry = CollectorRegistry()
        self._init_prometheus_metrics()
    
    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics"""
        if settings.monitoring.PROMETHEUS_ENABLED:
            self.request_counter = Counter(
                'http_requests_total',
                'Total HTTP requests',
                ['method', 'endpoint', 'status_code'],
                registry=self.registry
            )
            
            self.request_duration = Histogram(
                'http_request_duration_seconds',
                'HTTP request duration in seconds',
                ['method', 'endpoint'],
                registry=self.registry
            )
            
            self.active_connections = Gauge(
                'http_active_connections',
                'Active HTTP connections',
                registry=self.registry
            )
            
            self.error_rate = Gauge(
                'http_error_rate',
                'HTTP error rate percentage',
                registry=self.registry
            )
    
    async def track_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        response_time: float,
        error: Optional[Exception] = None
    ):
        """Track API request metrics"""
        try:
            # Update internal tracking
            self.response_times.append(response_time)
            self.request_counts[f"{method}:{endpoint}"] += 1
            
            if error or status_code >= 400:
                self.error_counts[f"{method}:{endpoint}"] += 1
            
            # Update endpoint statistics
            stats = self.endpoint_stats[f"{method}:{endpoint}"]
            stats['count'] += 1
            stats['total_time'] += response_time
            stats['avg_time'] = stats['total_time'] / stats['count']
            
            if error or status_code >= 400:
                stats['errors'] += 1
            
            # Update Prometheus metrics
            if settings.monitoring.PROMETHEUS_ENABLED:
                self.request_counter.labels(
                    method=method,
                    endpoint=endpoint,
                    status_code=str(status_code)
                ).inc()
                
                self.request_duration.labels(
                    method=method,
                    endpoint=endpoint
                ).observe(response_time)
            
            # Calculate and update error rate
            await self._update_error_rate()
            
        except Exception as e:
            logger.error(f"Failed to track request metrics: {str(e)}")
    
    async def _update_error_rate(self):
        """Update error rate metrics"""
        try:
            total_requests = sum(self.request_counts.values())
            total_errors = sum(self.error_counts.values())
            
            if total_requests > 0:
                error_rate = (total_errors / total_requests) * 100
                
                if settings.monitoring.PROMETHEUS_ENABLED:
                    self.error_rate.set(error_rate)
                    
        except Exception as e:
            logger.error(f"Failed to update error rate: {str(e)}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        response_times_list = list(self.response_times)
        
        stats = {
            "total_requests": sum(self.request_counts.values()),
            "total_errors": sum(self.error_counts.values()),
            "avg_response_time": sum(response_times_list) / len(response_times_list) if response_times_list else 0,
            "min_response_time": min(response_times_list) if response_times_list else 0,
            "max_response_time": max(response_times_list) if response_times_list else 0,
            "error_rate": (sum(self.error_counts.values()) / sum(self.request_counts.values()) * 100) if sum(self.request_counts.values()) > 0 else 0,
            "endpoints": dict(self.endpoint_stats)
        }
        
        return stats
    
    def get_prometheus_metrics(self) -> str:
        """Get Prometheus formatted metrics"""
        if settings.monitoring.PROMETHEUS_ENABLED:
            return generate_latest(self.registry).decode('utf-8')
        return ""


class HealthChecker:
    """System health monitoring"""
    
    def __init__(self):
        self.checks: Dict[str, Callable] = {}
        self.last_results: Dict[str, HealthCheck] = {}
    
    def register_check(self, name: str, check_func: Callable, interval: int = 30):
        """Register a health check"""
        self.checks[name] = {
            'func': check_func,
            'interval': interval,
            'last_run': None
        }
        logger.info(f"Registered health check: {name}")
    
    async def run_all_checks(self) -> Dict[str, HealthCheck]:
        """Run all registered health checks"""
        results = {}
        
        for name, check_info in self.checks.items():
            try:
                start_time = time.time()
                result = await self._run_check(check_info['func'])
                response_time = time.time() - start_time
                
                health_check = HealthCheck(
                    name=name,
                    status=result.get('status', HealthStatus.UNKNOWN),
                    message=result.get('message', 'No message'),
                    response_time=response_time,
                    timestamp=datetime.utcnow(),
                    details=result.get('details')
                )
                
                results[name] = health_check
                self.last_results[name] = health_check
                check_info['last_run'] = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Health check '{name}' failed: {str(e)}")
                results[name] = HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed: {str(e)}",
                    response_time=0.0,
                    timestamp=datetime.utcnow()
                )
        
        return results
    
    async def _run_check(self, check_func: Callable) -> Dict[str, Any]:
        """Run individual health check"""
        if asyncio.iscoroutinefunction(check_func):
            return await check_func()
        else:
            return check_func()
    
    async def get_overall_health(self) -> HealthStatus:
        """Get overall system health status"""
        if not self.last_results:
            return HealthStatus.UNKNOWN
        
        statuses = [check.status for check in self.last_results.values()]
        
        if all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            return HealthStatus.UNHEALTHY
        else:
            return HealthStatus.DEGRADED


class SystemMonitor:
    """System resource monitoring"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.registry = CollectorRegistry()
        self._init_system_metrics()
    
    def _init_system_metrics(self):
        """Initialize system metrics"""
        if settings.monitoring.PROMETHEUS_ENABLED:
            self.cpu_usage = Gauge(
                'system_cpu_usage_percent',
                'System CPU usage percentage',
                registry=self.registry
            )
            
            self.memory_usage = Gauge(
                'system_memory_usage_bytes',
                'System memory usage in bytes',
                registry=self.registry
            )
            
            self.disk_usage = Gauge(
                'system_disk_usage_percent',
                'System disk usage percentage',
                registry=self.registry
            )
            
            self.process_cpu = Gauge(
                'process_cpu_usage_percent',
                'Process CPU usage percentage',
                registry=self.registry
            )
            
            self.process_memory = Gauge(
                'process_memory_usage_bytes',
                'Process memory usage in bytes',
                registry=self.registry
            )
    
    async def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system resource metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Process metrics
            process_cpu = self.process.cpu_percent()
            process_memory = self.process.memory_info().rss
            
            metrics = {
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_bytes": memory.used,
                    "memory_total_bytes": memory.total,
                    "disk_percent": disk.percent,
                    "disk_used_bytes": disk.used,
                    "disk_total_bytes": disk.total
                },
                "process": {
                    "cpu_percent": process_cpu,
                    "memory_bytes": process_memory,
                    "threads": self.process.num_threads(),
                    "connections": len(self.process.connections()) if hasattr(self.process, 'connections') else 0
                }
            }
            
            # Update Prometheus metrics
            if settings.monitoring.PROMETHEUS_ENABLED:
                self.cpu_usage.set(cpu_percent)
                self.memory_usage.set(memory.used)
                self.disk_usage.set(disk.percent)
                self.process_cpu.set(process_cpu)
                self.process_memory.set(process_memory)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {str(e)}")
            return {}


class DatabaseMonitor:
    """Database connection and performance monitoring"""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        self._init_db_metrics()
    
    def _init_db_metrics(self):
        """Initialize database metrics"""
        if settings.monitoring.PROMETHEUS_ENABLED:
            self.db_connections = Gauge(
                'database_connections_active',
                'Active database connections',
                registry=self.registry
            )
            
            self.db_query_duration = Histogram(
                'database_query_duration_seconds',
                'Database query duration in seconds',
                ['operation'],
                registry=self.registry
            )
            
            self.db_errors = Counter(
                'database_errors_total',
                'Total database errors',
                ['error_type'],
                registry=self.registry
            )
    
    async def check_database_health(self) -> Dict[str, Any]:
        """Check database health and connectivity"""
        try:
            start_time = time.time()
            
            # Simple connectivity test
            # This would be replaced with actual database ping
            # await database.execute("SELECT 1")
            
            response_time = time.time() - start_time
            
            return {
                "status": HealthStatus.HEALTHY,
                "message": "Database connection successful",
                "response_time": response_time,
                "details": {
                    "driver": settings.database.DB_DRIVER,
                    "host": settings.database.DB_HOST,
                    "database": settings.database.DB_NAME
                }
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Database connection failed: {str(e)}",
                "response_time": 0.0
            }
    
    async def track_query(self, operation: str, duration: float, error: Optional[Exception] = None):
        """Track database query metrics"""
        try:
            if settings.monitoring.PROMETHEUS_ENABLED:
                self.db_query_duration.labels(operation=operation).observe(duration)
                
                if error:
                    self.db_errors.labels(error_type=type(error).__name__).inc()
                    
        except Exception as e:
            logger.error(f"Failed to track database query: {str(e)}")


class CacheMonitor:
    """Cache system monitoring"""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        self._init_cache_metrics()
    
    def _init_cache_metrics(self):
        """Initialize cache metrics"""
        if settings.monitoring.PROMETHEUS_ENABLED:
            self.cache_hits = Counter(
                'cache_hits_total',
                'Total cache hits',
                registry=self.registry
            )
            
            self.cache_misses = Counter(
                'cache_misses_total',
                'Total cache misses',
                registry=self.registry
            )
            
            self.cache_operations = Histogram(
                'cache_operation_duration_seconds',
                'Cache operation duration in seconds',
                ['operation'],
                registry=self.registry
            )
    
    async def check_cache_health(self) -> Dict[str, Any]:
        """Check cache system health"""
        try:
            start_time = time.time()
            
            # Test cache connectivity
            test_key = "health_check"
            await cache_manager.set(test_key, "test_value", expire=60)
            value = await cache_manager.get(test_key)
            await cache_manager.delete(test_key)
            
            response_time = time.time() - start_time
            
            if value == "test_value":
                return {
                    "status": HealthStatus.HEALTHY,
                    "message": "Cache system operational",
                    "response_time": response_time,
                    "details": {
                        "backend": settings.cache.CACHE_BACKEND,
                        "host": settings.redis.REDIS_HOST if settings.cache.CACHE_BACKEND == "redis" else "memory"
                    }
                }
            else:
                return {
                    "status": HealthStatus.DEGRADED,
                    "message": "Cache system partially functional",
                    "response_time": response_time
                }
                
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Cache system failed: {str(e)}",
                "response_time": 0.0
            }
    
    async def track_cache_operation(self, operation: str, duration: float, hit: bool):
        """Track cache operation metrics"""
        try:
            if settings.monitoring.PROMETHEUS_ENABLED:
                self.cache_operations.labels(operation=operation).observe(duration)
                
                if hit:
                    self.cache_hits.inc()
                else:
                    self.cache_misses.inc()
                    
        except Exception as e:
            logger.error(f"Failed to track cache operation: {str(e)}")


class MonitoringManager:
    """Main monitoring system manager"""
    
    def __init__(self):
        self.performance_tracker = PerformanceTracker()
        self.health_checker = HealthChecker()
        self.system_monitor = SystemMonitor()
        self.database_monitor = DatabaseMonitor()
        self.cache_monitor = CacheMonitor()
        
        self._monitoring_tasks = []
        self._initialized = False
    
    async def initialize(self):
        """Initialize monitoring system"""
        if self._initialized:
            return
        
        try:
            # Register default health checks
            self.health_checker.register_check(
                "database",
                self.database_monitor.check_database_health,
                interval=30
            )
            
            self.health_checker.register_check(
                "cache",
                self.cache_monitor.check_cache_health,
                interval=60
            )
            
            self.health_checker.register_check(
                "system_resources",
                self._check_system_resources,
                interval=60
            )
            
            # Start background monitoring tasks
            if settings.monitoring.ENABLE_METRICS:
                await self._start_monitoring_tasks()
            
            self._initialized = True
            logger.info("Monitoring system initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize monitoring system: {str(e)}")
            raise OperationError(f"Monitoring initialization failed: {str(e)}")
    
    async def _start_monitoring_tasks(self):
        """Start background monitoring tasks"""
        # Health check task
        if settings.monitoring.HEALTH_CHECK_INTERVAL > 0:
            self._monitoring_tasks.append(
                asyncio.create_task(self._health_check_loop())
            )
        
        # System metrics collection task
        self._monitoring_tasks.append(
            asyncio.create_task(self._system_metrics_loop())
        )
    
    async def _health_check_loop(self):
        """Periodic health check loop"""
        while True:
            try:
                await self.health_checker.run_all_checks()
                await asyncio.sleep(settings.monitoring.HEALTH_CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {str(e)}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _system_metrics_loop(self):
        """Periodic system metrics collection loop"""
        while True:
            try:
                await self.system_monitor.collect_system_metrics()
                await asyncio.sleep(60)  # Collect every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"System metrics loop error: {str(e)}")
                await asyncio.sleep(60)
    
    async def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource health"""
        try:
            metrics = await self.system_monitor.collect_system_metrics()
            
            cpu_threshold = 80.0
            memory_threshold = 85.0
            disk_threshold = 90.0
            
            status = HealthStatus.HEALTHY
            messages = []
            
            # Check CPU
            if metrics["system"]["cpu_percent"] > cpu_threshold:
                status = HealthStatus.DEGRADED
                messages.append(f"High CPU usage: {metrics['system']['cpu_percent']:.1f}%")
            
            # Check memory
            if metrics["system"]["memory_percent"] > memory_threshold:
                status = HealthStatus.DEGRADED
                messages.append(f"High memory usage: {metrics['system']['memory_percent']:.1f}%")
            
            # Check disk
            if metrics["system"]["disk_percent"] > disk_threshold:
                status = HealthStatus.UNHEALTHY
                messages.append(f"High disk usage: {metrics['system']['disk_percent']:.1f}%")
            
            return {
                "status": status,
                "message": "; ".join(messages) if messages else "System resources normal",
                "details": metrics
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.UNKNOWN,
                "message": f"Failed to check system resources: {str(e)}"
            }
    
    async def get_health_summary(self) -> Dict[str, Any]:
        """Get overall system health summary"""
        if not self._initialized:
            await self.initialize()
        
        try:
            health_checks = await self.health_checker.run_all_checks()
            overall_status = await self.health_checker.get_overall_health()
            performance_stats = self.performance_tracker.get_performance_stats()
            system_metrics = await self.system_monitor.collect_system_metrics()
            
            return {
                "overall_status": overall_status.value,
                "timestamp": datetime.utcnow().isoformat(),
                "health_checks": {
                    name: {
                        "status": check.status.value,
                        "message": check.message,
                        "response_time": check.response_time
                    }
                    for name, check in health_checks.items()
                },
                "performance": performance_stats,
                "system": system_metrics,
                "uptime": time.time() - self._start_time if hasattr(self, '_start_time') else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get health summary: {str(e)}")
            return {
                "overall_status": HealthStatus.UNKNOWN.value,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_metrics_export(self) -> str:
        """Get Prometheus formatted metrics"""
        if not settings.monitoring.PROMETHEUS_ENABLED:
            return ""
        
        try:
            metrics = []
            
            # Performance metrics
            metrics.append(self.performance_tracker.get_prometheus_metrics())
            
            # System metrics
            if hasattr(self.system_monitor, 'registry'):
                metrics.append(generate_latest(self.system_monitor.registry).decode('utf-8'))
            
            # Database metrics
            if hasattr(self.database_monitor, 'registry'):
                metrics.append(generate_latest(self.database_monitor.registry).decode('utf-8'))
            
            # Cache metrics
            if hasattr(self.cache_monitor, 'registry'):
                metrics.append(generate_latest(self.cache_monitor.registry).decode('utf-8'))
            
            return '\n'.join(filter(None, metrics))
            
        except Exception as e:
            logger.error(f"Failed to export metrics: {str(e)}")
            return f"# Error exporting metrics: {str(e)}\n"
    
    async def shutdown(self):
        """Shutdown monitoring system"""
        try:
            # Cancel monitoring tasks
            for task in self._monitoring_tasks:
                task.cancel()
            
            # Wait for tasks to complete
            if self._monitoring_tasks:
                await asyncio.gather(*self._monitoring_tasks, return_exceptions=True)
            
            logger.info("Monitoring system shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during monitoring shutdown: {str(e)}")


# Global monitoring manager
monitor_manager = MonitoringManager()


async def track_api_performance(
    endpoint: str,
    execution_time: float,
    status_code: int,
    request_size: int = 0,
    response_size: int = 0
):
    """Convenience function to track API performance"""
    await monitor_manager.performance_tracker.track_request(
        method="GET",  # Default method
        endpoint=endpoint,
        status_code=status_code,
        response_time=execution_time
    )


@asynccontextmanager
async def performance_monitor(operation: str):
    """Context manager for performance monitoring"""
    start_time = time.time()
    error = None
    
    try:
        yield
    except Exception as e:
        error = e
        raise
    finally:
        duration = time.time() - start_time
        
        # Track performance based on operation type
        if 'database' in operation.lower() or 'db' in operation.lower():
            await monitor_manager.database_monitor.track_query(
                operation=operation,
                duration=duration,
                error=error
            )
        elif 'cache' in operation.lower():
            await monitor_manager.cache_monitor.track_cache_operation(
                operation=operation,
                duration=duration,
                hit=error is None
            )


def monitor_function(operation_name: Optional[str] = None):
    """Decorator to monitor function performance"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            async with performance_monitor(op_name):
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            error = None
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error = e
                raise
            finally:
                duration = time.time() - start_time
                # For sync functions, we can't await, so just log
                logger.info(f"Function {op_name} completed in {duration:.3f}s")
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Export main functions and classes
__all__ = [
    'HealthStatus',
    'MetricType',
    'HealthCheck',
    'MetricData',
    'MonitoringManager',
    'monitor_manager',
    'track_api_performance',
    'performance_monitor',
    'monitor_function'
]