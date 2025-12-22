# metrics_collection_service.py

from typing import Dict, List, Any, Optional, Callable, Union, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import logging
from enum import Enum
import json
import statistics
from collections import defaultdict

class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    TIMER = "timer"

class MetricUnit(Enum):
    COUNT = "count"
    BYTES = "bytes"
    SECONDS = "seconds"
    PERCENTAGE = "percentage"
    MILLISECONDS = "milliseconds"
    MICROSECONDS = "microseconds"

@dataclass
class MetricDefinition:
    """Metric definition"""
    name: str
    type: MetricType
    unit: MetricUnit
    description: str
    labels: Set[str]
    aggregation: str = "sum"
    retention_days: int = 30

@dataclass
class MetricValue:
    """Metric value with metadata"""
    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str]
    type: MetricType
    unit: MetricUnit

class MetricCollector:
    """Collects and processes metrics"""
    
    def __init__(self):
        self._metrics: Dict[str, MetricDefinition] = {}
        self._values: Dict[str, List[MetricValue]] = defaultdict(list)
        self._pre_processors: Dict[str, List[Callable]] = defaultdict(list)
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_metric(
        self,
        definition: MetricDefinition
    ) -> None:
        """Register metric definition"""
        self._metrics[definition.name] = definition
        self.logger.info(f"Registered metric: {definition.name}")

    def add_pre_processor(
        self,
        metric_name: str,
        processor: Callable
    ) -> None:
        """Add metric pre-processor"""
        self._pre_processors[metric_name].append(processor)
        self.logger.info(
            f"Added pre-processor for {metric_name}: {processor.__name__}"
        )

    async def collect_metric(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Collect metric value"""
        definition = self._metrics.get(name)
        if not definition:
            raise ValueError(f"Unknown metric: {name}")

        # Apply pre-processors
        processed_value = value
        for processor in self._pre_processors[name]:
            try:
                processed_value = await processor(processed_value, labels)
            except Exception as e:
                self.logger.error(
                    f"Pre-processor failed for {name}: {str(e)}"
                )

        metric_value = MetricValue(
            name=name,
            value=processed_value,
            timestamp=datetime.utcnow(),
            labels=labels or {},
            type=definition.type,
            unit=definition.unit
        )

        self._values[name].append(metric_value)

    def get_metric_values(
        self,
        name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[MetricValue]:
        """Get metric values"""
        values = self._values.get(name, [])
        
        if start_time:
            values = [v for v in values if v.timestamp >= start_time]
        if end_time:
            values = [v for v in values if v.timestamp <= end_time]
            
        return values

    async def cleanup_old_metrics(self) -> None:
        """Clean up old metric values"""
        for name, definition in self._metrics.items():
            cutoff = datetime.utcnow() - timedelta(days=definition.retention_days)
            self._values[name] = [
                v for v in self._values[name]
                if v.timestamp >= cutoff
            ]

class MetricAggregator:
    """Aggregates metric values"""
    
    def __init__(self):
        self._aggregators: Dict[str, Callable] = {
            'sum': sum,
            'avg': lambda x: statistics.mean(x),
            'min': min,
            'max': max,
            'count': len,
            'p95': lambda x: statistics.quantiles(x, n=20)[18],
            'p99': lambda x: statistics.quantiles(x, n=100)[98]
        }
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_aggregator(
        self,
        name: str,
        func: Callable
    ) -> None:
        """Add custom aggregator"""
        self._aggregators[name] = func
        self.logger.info(f"Added aggregator: {name}")

    async def aggregate_metrics(
        self,
        values: List[MetricValue],
        aggregation: str,
        group_by: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """Aggregate metric values"""
        if not values:
            return {}

        aggregator = self._aggregators.get(aggregation)
        if not aggregator:
            raise ValueError(f"Unknown aggregation: {aggregation}")

        if not group_by:
            # Simple aggregation
            raw_values = [v.value for v in values]
            return {'total': aggregator(raw_values)}

        # Group by labels
        groups = defaultdict(list)
        for value in values:
            key = tuple(value.labels.get(label) for label in group_by)
            groups[key].append(value.value)

        return {
            '.'.join(str(k) for k in key): aggregator(values)
            for key, values in groups.items()
        }

class PerformanceMonitor:
    """Monitors system performance metrics"""
    
    def __init__(self):
        self._monitors: Dict[str, Callable] = {}
        self._thresholds: Dict[str, Dict[str, float]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_monitor(
        self,
        name: str,
        monitor_func: Callable,
        thresholds: Optional[Dict[str, float]] = None
    ) -> None:
        """Add performance monitor"""
        self._monitors[name] = monitor_func
        self._thresholds[name] = thresholds or {}
        self.logger.info(f"Added monitor: {name}")

    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect performance metrics"""
        results = {}
        
        for name, monitor in self._monitors.items():
            try:
                metrics = await monitor()
                results[name] = {
                    'metrics': metrics,
                    'thresholds': self._check_thresholds(name, metrics)
                }
            except Exception as e:
                self.logger.error(f"Monitor failed for {name}: {str(e)}")

        return results

    def _check_thresholds(
        self,
        name: str,
        metrics: Dict[str, float]
    ) -> Dict[str, bool]:
        """Check metric thresholds"""
        thresholds = self._thresholds.get(name, {})
        return {
            metric: value > thresholds.get(metric, float('inf'))
            for metric, value in metrics.items()
            if metric in thresholds
        }

class UsageTracker:
    """Tracks system usage metrics"""
    
    def __init__(self):
        self._trackers: Dict[str, Callable] = {}
        self._usage_data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_tracker(
        self,
        name: str,
        tracker_func: Callable
    ) -> None:
        """Add usage tracker"""
        self._trackers[name] = tracker_func
        self.logger.info(f"Added tracker: {name}")

    async def track_usage(self) -> Dict[str, Any]:
        """Track system usage"""
        results = {}
        
        for name, tracker in self._trackers.items():
            try:
                usage = await tracker()
                self._usage_data[name].append({
                    'timestamp': datetime.utcnow(),
                    'data': usage
                })
                results[name] = usage
            except Exception as e:
                self.logger.error(f"Tracker failed for {name}: {str(e)}")

        return results

    def get_usage_history(
        self,
        name: str,
        timeframe: Optional[timedelta] = None
    ) -> List[Dict[str, Any]]:
        """Get usage history"""
        history = self._usage_data.get(name, [])
        
        if timeframe:
            cutoff = datetime.utcnow() - timeframe
            history = [
                h for h in history
                if h['timestamp'] >= cutoff
            ]
            
        return history

class ErrorRateCalculator:
    """Calculates error rates and patterns"""
    
    def __init__(self):
        self._error_data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._thresholds: Dict[str, float] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def set_threshold(
        self,
        error_type: str,
        rate_threshold: float
    ) -> None:
        """Set error rate threshold"""
        self._thresholds[error_type] = rate_threshold
        self.logger.info(
            f"Set {rate_threshold}% threshold for {error_type}"
        )

    async def record_error(
        self,
        error_type: str,
        error_data: Dict[str, Any]
    ) -> None:
        """Record error occurrence"""
        self._error_data[error_type].append({
            'timestamp': datetime.utcnow(),
            'data': error_data
        })

    def calculate_error_rates(
        self,
        timeframe: Optional[timedelta] = None
    ) -> Dict[str, Dict[str, float]]:
        """Calculate error rates"""
        rates = {}
        
        for error_type, errors in self._error_data.items():
            if timeframe:
                cutoff = datetime.utcnow() - timeframe
                relevant_errors = [
                    e for e in errors
                    if e['timestamp'] >= cutoff
                ]
            else:
                relevant_errors = errors

            total = len(relevant_errors)
            if total == 0:
                continue

            rate = (total / len(errors)) * 100 if errors else 0
            threshold = self._thresholds.get(error_type, float('inf'))
            
            rates[error_type] = {
                'rate': rate,
                'total': total,
                'exceeds_threshold': rate > threshold
            }

        return rates

class MetricPublisher:
    """Publishes metrics to external systems"""
    
    def __init__(self):
        self._publishers: Dict[str, Callable] = {}
        self._batch_size: int = 100
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_publisher(
        self,
        name: str,
        publisher_func: Callable,
        batch_size: Optional[int] = None
    ) -> None:
        """Add metric publisher"""
        self._publishers[name] = publisher_func
        if batch_size:
            self._batch_size = batch_size
        self.logger.info(f"Added publisher: {name}")

    async def publish_metrics(
        self,
        metrics: List[MetricValue]
    ) -> Dict[str, Any]:
        """Publish metrics"""
        results = {}
        
        # Split into batches
        batches = [
            metrics[i:i + self._batch_size]
            for i in range(0, len(metrics), self._batch_size)
        ]

        for name, publisher in self._publishers.items():
            try:
                batch_results = []
                for batch in batches:
                    result = await publisher(batch)
                    batch_results.append(result)
                results[name] = batch_results
            except Exception as e:
                self.logger.error(f"Publisher failed for {name}: {str(e)}")

        return results

class AnomalyDetector:
    """Detects metric anomalies"""
    
    def __init__(self):
        self._detectors: Dict[str, Callable] = {}
        self._baseline_data: Dict[str, List[float]] = defaultdict(list)
        self._window_size: int = 100
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_detector(
        self,
        name: str,
        detector_func: Callable
    ) -> None:
        """Add anomaly detector"""
        self._detectors[name] = detector_func
        self.logger.info(f"Added detector: {name}")

    def update_baseline(
        self,
        metric_name: str,
        value: float
    ) -> None:
        """Update baseline data"""
        baseline = self._baseline_data[metric_name]
        baseline.append(value)
        
        if len(baseline) > self._window_size:
            baseline.pop(0)

    async def detect_anomalies(
        self,
        metrics: Dict[str, List[MetricValue]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Detect anomalies in metrics"""
        results = {}
        
        for metric_name, values in metrics.items():
            detector = self._detectors.get(metric_name)
            if not detector:
                continue

            try:
                baseline = self._baseline_data[metric_name]
                anomalies = await detector(values, baseline)
                if anomalies:
                    results[metric_name] = anomalies
            except Exception as e:
                self.logger.error(
                    f"Anomaly detection failed for {metric_name}: {str(e)}"
                )

        return results

class MetricsCollectionService:
    """Main metrics collection service"""
    
    def __init__(self):
        self.collector = MetricCollector()
        self.aggregator = MetricAggregator()
        self.performance = PerformanceMonitor()
        self.usage = UsageTracker()
        self.error_calc = ErrorRateCalculator()
        self.publisher = MetricPublisher()
        self.anomaly = AnomalyDetector()
        self._running = False
        self._collection_task: Optional[asyncio.Task] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def start(self) -> None:
        """Start metrics collection"""
        self._running = True
        self._collection_task = asyncio.create_task(self._run_collection())
        self.logger.info("Metrics collection started")

    async def stop(self) -> None:
        """Stop metrics collection"""
        self._running = False
        if self._collection_task:
            await self._collection_task
        self.logger.info("Metrics collection stopped")

    async def _run_collection(self) -> None:
        """Main collection loop"""
        while self._running:
            try:
                # Collect performance metrics
                perf_metrics = await self.performance.collect_metrics()
                
                # Track usage
                usage_metrics = await self.usage.track_usage()
                
                # Calculate error rates
                error_rates = self.error_calc.calculate_error_rates(
                    timedelta(minutes=5)
                )
                
                # Detect anomalies
                anomalies = await self.anomaly.detect_anomalies({
                    'performance': perf_metrics,
                    'usage': usage_metrics,
                    'errors': error_rates
                })
            

                # Publish metrics
                if any([perf_metrics, usage_metrics, error_rates, anomalies]):
                    await self.publisher.publish_metrics([
                        MetricValue(
                            name='system.performance',
                            value=1.0,
                            timestamp=datetime.utcnow(),
                            labels={'metrics': json.dumps(perf_metrics)},
                            type=MetricType.GAUGE,
                            unit=MetricUnit.COUNT
                        ),
                        MetricValue(
                            name='system.usage',
                            value=1.0,
                            timestamp=datetime.utcnow(),
                            labels={'metrics': json.dumps(usage_metrics)},
                            type=MetricType.GAUGE,
                            unit=MetricUnit.COUNT
                        ),
                        MetricValue(
                            name='system.errors',
                            value=1.0,
                            timestamp=datetime.utcnow(),
                            labels={'metrics': json.dumps(error_rates)},
                            type=MetricType.GAUGE,
                            unit=MetricUnit.COUNT
                        ),
                        MetricValue(
                            name='system.anomalies',
                            value=len(anomalies),
                            timestamp=datetime.utcnow(),
                            labels={'anomalies': json.dumps(anomalies)},
                            type=MetricType.GAUGE,
                            unit=MetricUnit.COUNT
                        )
                    ])

                # Cleanup old metrics
                await self.collector.cleanup_old_metrics()
                
                # Wait before next collection
                await asyncio.sleep(60)  # 1 minute
            except Exception as e:
                self.logger.error(f"Metrics collection failed: {str(e)}")
                await asyncio.sleep(5)

    def register_metric(
        self,
        name: str,
        metric_type: MetricType,
        unit: MetricUnit,
        description: str,
        labels: Optional[Set[str]] = None,
        **kwargs: Any
    ) -> None:
        """Register new metric"""
        definition = MetricDefinition(
            name=name,
            type=metric_type,
            unit=unit,
            description=description,
            labels=labels or set(),
            **kwargs
        )
        self.collector.register_metric(definition)

    async def collect_metric(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Collect metric value"""
        await self.collector.collect_metric(name, value, labels)

    def add_performance_monitor(
        self,
        name: str,
        monitor_func: Callable,
        thresholds: Optional[Dict[str, float]] = None
    ) -> None:
        """Add performance monitor"""
        self.performance.add_monitor(name, monitor_func, thresholds)

    def add_usage_tracker(
        self,
        name: str,
        tracker_func: Callable
    ) -> None:
        """Add usage tracker"""
        self.usage.add_tracker(name, tracker_func)

    def set_error_threshold(
        self,
        error_type: str,
        threshold: float
    ) -> None:
        """Set error rate threshold"""
        self.error_calc.set_threshold(error_type, threshold)

    async def record_error(
        self,
        error_type: str,
        error_data: Dict[str, Any]
    ) -> None:
        """Record error occurrence"""
        await self.error_calc.record_error(error_type, error_data)

    def add_metric_publisher(
        self,
        name: str,
        publisher_func: Callable,
        batch_size: Optional[int] = None
    ) -> None:
        """Add metric publisher"""
        self.publisher.add_publisher(name, publisher_func, batch_size)

    def add_anomaly_detector(
        self,
        name: str,
        detector_func: Callable
    ) -> None:
        """Add anomaly detector"""
        self.anomaly.add_detector(name, detector_func)

    async def get_metric_values(
        self,
        name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[MetricValue]:
        """Get metric values"""
        return self.collector.get_metric_values(name, start_time, end_time)

    async def aggregate_metrics(
        self,
        name: str,
        aggregation: str,
        group_by: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, float]:
        """Aggregate metric values"""
        values = self.collector.get_metric_values(name, start_time, end_time)
        return await self.aggregator.aggregate_metrics(values, aggregation, group_by)

    def get_performance_metrics(
        self,
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get performance metrics"""
        metrics = self.performance._monitors
        if name:
            return {name: metrics.get(name)}
        return metrics

    def get_usage_history(
        self,
        name: str,
        timeframe: Optional[timedelta] = None
    ) -> List[Dict[str, Any]]:
        """Get usage history"""
        return self.usage.get_usage_history(name, timeframe)

    def get_error_rates(
        self,
        timeframe: Optional[timedelta] = None
    ) -> Dict[str, Dict[str, float]]:
        """Get error rates"""
        return self.error_calc.calculate_error_rates(timeframe)

    async def detect_anomalies(
        self,
        metrics: Dict[str, List[MetricValue]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Detect anomalies in metrics"""
        return await self.anomaly.detect_anomalies(metrics)

    def add_metric_preprocessor(
        self,
        metric_name: str,
        processor: Callable
    ) -> None:
        """Add metric preprocessor"""
        self.collector.add_pre_processor(metric_name, processor)

    def add_custom_aggregator(
        self,
        name: str,
        aggregator: Callable
    ) -> None:
        """Add custom metric aggregator"""
        self.aggregator.add_aggregator(name, aggregator)

    async def get_system_metrics(
        self,
        timeframe: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """Get comprehensive system metrics"""
        end_time = datetime.utcnow()
        start_time = end_time - (timeframe or timedelta(hours=1))

        return {
            'performance': await self.performance.collect_metrics(),
            'usage': self.usage.get_usage_history(
                'system',
                timeframe
            ),
            'errors': self.error_calc.calculate_error_rates(timeframe),
            'anomalies': await self.anomaly.detect_anomalies({
                'performance': await self.performance.collect_metrics(),
                'usage': await self.usage.track_usage(),
                'errors': self.error_calc.calculate_error_rates(timeframe)
            })
        }

    async def export_metrics(
        self,
        format: str = 'json',
        timeframe: Optional[timedelta] = None
    ) -> Union[str, bytes]:
        """Export metrics in specified format"""
        metrics = await self.get_system_metrics(timeframe)
        
        if format.lower() == 'json':
            return json.dumps(metrics, default=str)
        elif format.lower() == 'csv':
            # Implement CSV export
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write headers
            writer.writerow(['Category', 'Metric', 'Value', 'Timestamp'])
            
            # Write metrics
            for category, category_metrics in metrics.items():
                if isinstance(category_metrics, list):
                    for metric in category_metrics:
                        writer.writerow([
                            category,
                            metric.get('name', 'N/A'),
                            metric.get('value', 'N/A'),
                            metric.get('timestamp', 'N/A')
                        ])
                elif isinstance(category_metrics, dict):
                    for metric_name, metric_value in category_metrics.items():
                        writer.writerow([
                            category,
                            metric_name,
                            metric_value,
                            datetime.utcnow().isoformat()
                        ])
            
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format}")

    async def get_metric_summary(
        self,
        metric_name: str,
        timeframe: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """Get metric summary statistics"""
        values = self.collector.get_metric_values(
            metric_name,
            start_time=datetime.utcnow() - (timeframe or timedelta(hours=1))
        )
        
        if not values:
            return {}

        raw_values = [v.value for v in values]
        return {
            'count': len(raw_values),
            'min': min(raw_values),
            'max': max(raw_values),
            'avg': statistics.mean(raw_values),
            'median': statistics.median(raw_values),
            'stddev': statistics.stdev(raw_values) if len(raw_values) > 1 else 0,
            'last_value': raw_values[-1],
            'last_update': values[-1].timestamp
        }