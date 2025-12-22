# health_check_service.py

from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import logging
from enum import Enum
import json
import aiohttp

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class HealthCheckResult:
    """Health check result"""
    component: str
    status: HealthStatus
    details: Dict[str, Any]
    timestamp: datetime
    latency_ms: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'component': self.component,
            'status': self.status.value,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'latency_ms': self.latency_ms,
            'error': self.error,
            'metadata': self.metadata or {}
        }

class SystemHealthMonitor:
    """Monitors overall system health"""
    
    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._thresholds: Dict[str, Dict[str, Any]] = {}
        self._results: Dict[str, HealthCheckResult] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_check(
        self,
        component: str,
        check_func: Callable,
        thresholds: Dict[str, Any] = None
    ) -> None:
        """Add health check"""
        self._checks[component] = check_func
        self._thresholds[component] = thresholds or {}
        self.logger.info(f"Added health check for {component}")

    async def run_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks"""
        results = {}
        
        for component, check_func in self._checks.items():
            try:
                start_time = datetime.utcnow()
                details = await check_func()
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000

                status = self._evaluate_status(component, details)
                
                results[component] = HealthCheckResult(
                    component=component,
                    status=status,
                    details=details,
                    timestamp=datetime.utcnow(),
                    latency_ms=latency
                )
            except Exception as e:
                self.logger.error(f"Health check failed for {component}: {str(e)}")
                results[component] = HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNHEALTHY,
                    details={},
                    timestamp=datetime.utcnow(),
                    latency_ms=0,
                    error=str(e)
                )

        self._results = results
        return results

    def _evaluate_status(
        self,
        component: str,
        details: Dict[str, Any]
    ) -> HealthStatus:
        """Evaluate component status"""
        thresholds = self._thresholds.get(component, {})
        
        for metric, threshold in thresholds.items():
            value = details.get(metric)
            if value is None:
                continue

            if isinstance(threshold, dict):
                if value > threshold.get('critical', float('inf')):
                    return HealthStatus.UNHEALTHY
                if value > threshold.get('warning', float('inf')):
                    return HealthStatus.DEGRADED
            else:
                if value > threshold:
                    return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def get_system_status(self) -> HealthStatus:
        """Get overall system status"""
        if not self._results:
            return HealthStatus.UNKNOWN

        statuses = [result.status for result in self._results.values()]
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

class DependencyChecker:
    """Checks external dependencies"""
    
    def __init__(self):
        self._dependencies: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_dependency(
        self,
        name: str,
        check_url: str,
        timeout: float = 5.0,
        headers: Optional[Dict[str, str]] = None
    ) -> None:
        """Add dependency check"""
        self._dependencies[name] = {
            'url': check_url,
            'timeout': timeout,
            'headers': headers or {}
        }
        self.logger.info(f"Added dependency check for {name}")

    async def check_dependencies(self) -> Dict[str, HealthCheckResult]:
        """Check all dependencies"""
        results = {}
        
        async with aiohttp.ClientSession() as session:
            for name, config in self._dependencies.items():
                try:
                    start_time = datetime.utcnow()
                    
                    async with session.get(
                        config['url'],
                        timeout=config['timeout'],
                        headers=config['headers']
                    ) as response:
                        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                        
                        status = (
                            HealthStatus.HEALTHY
                            if response.status < 400
                            else HealthStatus.UNHEALTHY
                        )
                        
                        results[name] = HealthCheckResult(
                            component=name,
                            status=status,
                            details={'status_code': response.status},
                            timestamp=datetime.utcnow(),
                            latency_ms=latency
                        )
                except Exception as e:
                    self.logger.error(f"Dependency check failed for {name}: {str(e)}")
                    results[name] = HealthCheckResult(
                        component=name,
                        status=HealthStatus.UNHEALTHY,
                        details={},
                        timestamp=datetime.utcnow(),
                        latency_ms=0,
                        error=str(e)
                    )

        return results

class DatabaseHealthChecker:
    """Checks database health"""
    
    def __init__(self):
        self._databases: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_database(
        self,
        name: str,
        check_func: Callable,
        thresholds: Dict[str, Any] = None
    ) -> None:
        """Add database check"""
        self._databases[name] = {
            'check_func': check_func,
            'thresholds': thresholds or {}
        }
        self.logger.info(f"Added database check for {name}")

    async def check_databases(self) -> Dict[str, HealthCheckResult]:
        """Check all databases"""
        results = {}
        
        for name, config in self._databases.items():
            try:
                start_time = datetime.utcnow()
                details = await config['check_func']()
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000

                status = self._evaluate_status(details, config['thresholds'])
                
                results[name] = HealthCheckResult(
                    component=name,
                    status=status,
                    details=details,
                    timestamp=datetime.utcnow(),
                    latency_ms=latency
                )
            except Exception as e:
                self.logger.error(f"Database check failed for {name}: {str(e)}")
                results[name] = HealthCheckResult(
                    component=name,
                    status=HealthStatus.UNHEALTHY,
                    details={},
                    timestamp=datetime.utcnow(),
                    latency_ms=0,
                    error=str(e)
                )

        return results

    def _evaluate_status(
        self,
        details: Dict[str, Any],
        thresholds: Dict[str, Any]
    ) -> HealthStatus:
        """Evaluate database status"""
        for metric, threshold in thresholds.items():
            value = details.get(metric)
            if value is None:
                continue

            if isinstance(threshold, dict):
                if value > threshold.get('critical', float('inf')):
                    return HealthStatus.UNHEALTHY
                if value > threshold.get('warning', float('inf')):
                    return HealthStatus.DEGRADED
            else:
                if value > threshold:
                    return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

class CacheHealthChecker:
    """Checks cache health"""
    
    def __init__(self):
        self._caches: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_cache(
        self,
        name: str,
        check_func: Callable,
        thresholds: Dict[str, Any] = None
    ) -> None:
        """Add cache check"""
        self._caches[name] = {
            'check_func': check_func,
            'thresholds': thresholds or {}
        }
        self.logger.info(f"Added cache check for {name}")

    async def check_caches(self) -> Dict[str, HealthCheckResult]:
        """Check all caches"""
        results = {}
        
        for name, config in self._caches.items():
            try:
                start_time = datetime.utcnow()
                details = await config['check_func']()
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000

                status = self._evaluate_status(details, config['thresholds'])
                
                results[name] = HealthCheckResult(
                    component=name,
                    status=status,
                    details=details,
                    timestamp=datetime.utcnow(),
                    latency_ms=latency
                )
            except Exception as e:
                self.logger.error(f"Cache check failed for {name}: {str(e)}")
                results[name] = HealthCheckResult(
                    component=name,
                    status=HealthStatus.UNHEALTHY,
                    details={},
                    timestamp=datetime.utcnow(),
                    latency_ms=0,
                    error=str(e)
                )

        return results

    def _evaluate_status(
        self,
        details: Dict[str, Any],
        thresholds: Dict[str, Any]
    ) -> HealthStatus:
        """Evaluate cache status"""
        for metric, threshold in thresholds.items():
            value = details.get(metric)
            if value is None:
                continue

            if isinstance(threshold, dict):
                if value > threshold.get('critical', float('inf')):
                    return HealthStatus.UNHEALTHY
                if value > threshold.get('warning', float('inf')):
                    return HealthStatus.DEGRADED
            else:
                if value > threshold:
                    return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

class QueueHealthChecker:
    """Checks queue health"""
    
    def __init__(self):
        self._queues: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_queue(
        self,
        name: str,
        check_func: Callable,
        thresholds: Dict[str, Any] = None
    ) -> None:
        """Add queue check"""
        self._queues[name] = {
            'check_func': check_func,
            'thresholds': thresholds or {}
        }
        self.logger.info(f"Added queue check for {name}")

    async def check_queues(self) -> Dict[str, HealthCheckResult]:
        """Check all queues"""
        results = {}
        
        for name, config in self._queues.items():
            try:
                start_time = datetime.utcnow()
                details = await config['check_func']()
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000

                status = self._evaluate_status(details, config['thresholds'])
                
                results[name] = HealthCheckResult(
                    component=name,
                    status=status,
                    details=details,
                    timestamp=datetime.utcnow(),
                    latency_ms=latency
                )
            except Exception as e:
                self.logger.error(f"Queue check failed for {name}: {str(e)}")
                results[name] = HealthCheckResult(
                    component=name,
                    status=HealthStatus.UNHEALTHY,
                    details={},
                    timestamp=datetime.utcnow(),
                    latency_ms=0,
                    error=str(e)
                )

        return results

    def _evaluate_status(
        self,
        details: Dict[str, Any],
        thresholds: Dict[str, Any]
    ) -> HealthStatus:
        """Evaluate queue status"""
        for metric, threshold in thresholds.items():
            value = details.get(metric)
            if value is None:
                continue

            if isinstance(threshold, dict):
                if value > threshold.get('critical', float('inf')):
                    return HealthStatus.UNHEALTHY
                if value > threshold.get('warning', float('inf')):
                    return HealthStatus.DEGRADED
            else:
                if value > threshold:
                    return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

class ExternalServiceChecker:
    """Checks external service health"""
    
    def __init__(self):
        self._services: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_service(
        self,
        name: str,
        check_func: Callable,
        timeout: float = 5.0
    ) -> None:
        """Add service check"""
        self._services[name] = {
            'check_func': check_func,
            'timeout': timeout
        }
        self.logger.info(f"Added service check for {name}")

    async def check_services(self) -> Dict[str, HealthCheckResult]:
        """Check all external services"""
        results = {}
        
        for name, config in self._services.items():
            try:
                start_time = datetime.utcnow()
                
                # Run check with timeout
                details = await asyncio.wait_for(
                    config['check_func'](),
                    timeout=config['timeout']
                )
                
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                results[name] = HealthCheckResult(
                    component=name,
                    status=HealthStatus.HEALTHY,
                    details=details,
                    timestamp=datetime.utcnow(),
                    latency_ms=latency
                )
            except asyncio.TimeoutError:
                self.logger.error(f"Service check timed out for {name}")
                results[name] = HealthCheckResult(
                    component=name,
                    status=HealthStatus.UNHEALTHY,
                    details={},
                    timestamp=datetime.utcnow(),
                    latency_ms=config['timeout'] * 1000,
                    error="Timeout"
                )
            except Exception as e:
                self.logger.error(f"Service check failed for {name}: {str(e)}")
                results[name] = HealthCheckResult(
                    component=name,
                    status=HealthStatus.UNHEALTHY,
                    details={},
                    timestamp=datetime.utcnow(),
                    latency_ms=0,
                    error=str(e)
                )

        return results

class HealthReporter:
    """Generates health reports"""
    
    def __init__(self):
        self._history: Dict[str, List[HealthCheckResult]] = {}
        self._max_history = 100
        self.logger = logging.getLogger(self.__class__.__name__)

    def record_results(
        self,
        results: Dict[str, HealthCheckResult]
    ) -> None:
        """Record health check results"""
        for component, result in results.items():
            if component not in self._history:
                self._history[component] = []
            
            history = self._history[component]
            history.append(result)
            
            # Maintain history size
            if len(history) > self._max_history:
                history.pop(0)

    def generate_report(
        self,
        timeframe: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """Generate health report"""
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'components': {}
        }

        for component, history in self._history.items():
            if not history:
                continue

            # Filter by timeframe if specified
            if timeframe:
                cutoff = datetime.utcnow() - timeframe
                relevant_history = [
                    result for result in history
                    if result.timestamp >= cutoff
                ]
            else:
                relevant_history = history

            if not relevant_history:
                continue

            # Calculate statistics
            total_checks = len(relevant_history)
            status_counts = {}
            avg_latency = sum(r.latency_ms for r in relevant_history) / total_checks
            error_count = sum(1 for r in relevant_history if r.error)

            for status in HealthStatus:
                count = sum(1 for r in relevant_history if r.status == status)
                status_counts[status.value] = count

            report['components'][component] = {
                'current_status': relevant_history[-1].status.value,
                'status_counts': status_counts,
                'total_checks': total_checks,
                'average_latency_ms': avg_latency,
                'error_count': error_count,
                'last_check': relevant_history[-1].to_dict()
            }

        return report

class HealthCheckService:
    """Main health check service"""
    
    def __init__(self):
        self.system_monitor = SystemHealthMonitor()
        self.dependency_checker = DependencyChecker()
        self.database_checker = DatabaseHealthChecker()
        self.cache_checker = CacheHealthChecker()
        self.queue_checker = QueueHealthChecker()
        self.service_checker = ExternalServiceChecker()
        self.reporter = HealthReporter()
        self._running = False
        self._check_task: Optional[asyncio.Task] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def start(self) -> None:
        """Start health check service"""
        self._running = True
        self._check_task = asyncio.create_task(self._run_checks())
        self.logger.info("Health check service started")

    async def stop(self) -> None:
        """Stop health check service"""
        self._running = False
        if self._check_task:
            await self._check_task
        self.logger.info("Health check service stopped")

    async def _run_checks(self) -> None:
        """Main health check loop"""
        while self._running:
            try:
                # Run all health checks
                results = {}
                results.update(await self.system_monitor.run_checks())
                results.update(await self.dependency_checker.check_dependencies())
                results.update(await self.database_checker.check_databases())
                results.update(await self.cache_checker.check_caches())
                results.update(await self.queue_checker.check_queues())
                results.update(await self.service_checker.check_services())

                # Record results
                self.reporter.record_results(results)
                
                # Log overall status
                status = self.system_monitor.get_system_status()
                self.logger.info(f"System health status: {status.value}")

                # Wait before next check
                await asyncio.sleep(60)  # 1 minute
            except Exception as e:
                self.logger.error(f"Health check cycle failed: {str(e)}")
                await asyncio.sleep(5)

    def add_system_check(
        self,
        component: str,
        check_func: Callable,
        thresholds: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add system health check"""
        self.system_monitor.add_check(component, check_func, thresholds)

    def add_dependency(
        self,
        name: str,
        check_url: str,
        **kwargs: Any
    ) -> None:
        """Add dependency check"""
        self.dependency_checker.add_dependency(name, check_url, **kwargs)

    def add_database(
        self,
        name: str,
        check_func: Callable,
        thresholds: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add database check"""
        self.database_checker.add_database(name, check_func, thresholds)

    def add_cache(
        self,
        name: str,
        check_func: Callable,
        thresholds: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add cache check"""
        self.cache_checker.add_cache(name, check_func, thresholds)

    def add_queue(
        self,
        name: str,
        check_func: Callable,
        thresholds: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add queue check"""
        self.queue_checker.add_queue(name, check_func, thresholds)

    def add_service(
        self,
        name: str,
        check_func: Callable,
        timeout: float = 5.0
    ) -> None:
        """Add external service check"""
        self.service_checker.add_service(name, check_func, timeout)

    def get_health_report(
        self,
        timeframe: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """Get health report"""
        return self.reporter.generate_report(timeframe)

    def get_component_status(
        self,
        component: str
    ) -> Optional[HealthStatus]:
        """Get specific component status"""
        results = self.reporter._history.get(component, [])
        if results:
            return results[-1].status
        return None

    async def run_specific_check(
        self,
        component: str
    ) -> Optional[HealthCheckResult]:
        """Run specific health check"""
        try:
            if component in self.system_monitor._checks:
                results = await self.system_monitor.run_checks()
                return results.get(component)
            elif component in self.dependency_checker._dependencies:
                results = await self.dependency_checker.check_dependencies()
                return results.get(component)
            elif component in self.database_checker._databases:
                results = await self.database_checker.check_databases()
                return results.get(component)
            elif component in self.cache_checker._caches:
                results = await self.cache_checker.check_caches()
                return results.get(component)
            elif component in self.queue_checker._queues:
                results = await self.queue_checker.check_queues()
                return results.get(component)
            elif component in self.service_checker._services:
                results = await self.service_checker.check_services()
                return results.get(component)
            return None
        except Exception as e:
            self.logger.error(f"Specific check failed for {component}: {str(e)}")
            return None