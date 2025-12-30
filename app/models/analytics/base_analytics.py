"""
Base analytics models with common patterns and mixins.

Provides foundational classes for all analytics models including:
- Time-series data handling
- Metric aggregation
- Caching support
- Materialized view patterns
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Column, String, Integer, Numeric, DateTime, Date, Boolean,
    ForeignKey, JSON, Text, Index, CheckConstraint, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, declared_attr
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin
from app.core.database import Base


class AnalyticsMixin:
    """
    Mixin for analytics models with common patterns.
    
    Provides standard fields for analytics data including:
    - Time period tracking
    - Calculation metadata
    - Cache control
    """
    
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    
    calculated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True
    )
    
    is_cached = Column(Boolean, default=False, nullable=False)
    cache_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    calculation_metadata = Column(
        JSONB,
        nullable=True,
        comment="Metadata about calculation process"
    )
    
    @declared_attr
    def __table_args__(cls):
        return (
            Index(
                f'ix_{cls.__tablename__}_period',
                'period_start',
                'period_end'
            ),
            CheckConstraint(
                'period_end >= period_start',
                name=f'ck_{cls.__tablename__}_valid_period'
            ),
        )


class MetricMixin:
    """
    Mixin for metric storage with validation.
    
    Provides fields for storing numeric metrics with
    targets and variance tracking.
    """
    
    metric_value = Column(
        Numeric(precision=20, scale=4),
        nullable=False,
        comment="Primary metric value"
    )
    
    target_value = Column(
        Numeric(precision=20, scale=4),
        nullable=True,
        comment="Target/goal value for metric"
    )
    
    previous_value = Column(
        Numeric(precision=20, scale=4),
        nullable=True,
        comment="Previous period value for comparison"
    )
    
    variance = Column(
        Numeric(precision=20, scale=4),
        nullable=True,
        comment="Variance from target or previous"
    )
    
    unit = Column(String(20), nullable=True, comment="Unit of measurement")


class TrendMixin:
    """
    Mixin for trend data tracking.
    
    Provides fields for time-series trend analysis
    with direction indicators.
    """
    
    trend_direction = Column(
        SQLEnum('up', 'down', 'stable', name='trend_direction_enum'),
        nullable=True,
        comment="Trend direction indicator"
    )
    
    trend_percentage = Column(
        Numeric(precision=10, scale=4),
        nullable=True,
        comment="Percentage change in trend"
    )
    
    trend_confidence = Column(
        Numeric(precision=5, scale=4),
        nullable=True,
        comment="Statistical confidence in trend (0-1)"
    )


class AggregationMixin:
    """
    Mixin for aggregated analytics data.
    
    Tracks aggregation details and data sources.
    """
    
    aggregation_level = Column(
        SQLEnum(
            'daily', 'weekly', 'monthly', 'quarterly', 'yearly',
            name='aggregation_level_enum'
        ),
        nullable=False,
        default='daily',
        comment="Granularity of aggregation"
    )
    
    data_source_count = Column(
        Integer,
        nullable=True,
        comment="Number of data points aggregated"
    )
    
    aggregation_method = Column(
        String(50),
        nullable=True,
        comment="Method used for aggregation (sum, avg, etc.)"
    )


class BaseAnalyticsModel(Base, TimestampMixin):
    """
    Abstract base for all analytics models.
    
    Provides common functionality for analytics data storage
    with performance optimization features.
    """
    
    __abstract__ = True
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    
    notes = Column(Text, nullable=True, comment="Additional notes or context")
    
    metadata_json = Column(
        JSONB,
        nullable=True,
        comment="Flexible metadata storage"
    )
    
    def to_dict(self):
        """Convert model to dictionary representation."""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            
            # Handle special types
            if isinstance(value, (datetime, date)):
                result[column.name] = value.isoformat()
            elif isinstance(value, Decimal):
                result[column.name] = float(value)
            elif isinstance(value, uuid.UUID):
                result[column.name] = str(value)
            else:
                result[column.name] = value
        
        return result


class CachedAnalyticsMixin:
    """
    Mixin for cached analytics results.
    
    Manages cache lifecycle and invalidation.
    """
    
    is_cached = Column(Boolean, default=True, nullable=False)
    
    cache_key = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Cache key for invalidation"
    )
    
    cache_created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    
    cache_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    cache_hit_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of times cache was accessed"
    )
    
    @property
    def is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if not self.is_cached:
            return False
        
        if self.cache_expires_at is None:
            return True
        
        return datetime.utcnow() < self.cache_expires_at
    
    def invalidate_cache(self):
        """Invalidate the cached data."""
        self.is_cached = False
        self.cache_expires_at = datetime.utcnow()


class HostelScopedMixin:
    """
    Mixin for hostel-scoped analytics.
    
    Links analytics to specific hostel or platform-wide.
    """
    
    @declared_attr
    def hostel_id(cls):
        return Column(
            UUID(as_uuid=True),
            ForeignKey('hostels.id', ondelete='CASCADE'),
            nullable=True,
            index=True,
            comment="Hostel ID. NULL for platform-wide metrics"
        )
    
    scope_type = Column(
        SQLEnum('hostel', 'platform', name='analytics_scope_enum'),
        nullable=False,
        default='hostel',
        comment="Scope of analytics data"
    )


class ComparisonMixin:
    """
    Mixin for comparative analytics.
    
    Enables comparison with benchmarks and peers.
    """
    
    benchmark_value = Column(
        Numeric(precision=20, scale=4),
        nullable=True,
        comment="Industry or platform benchmark value"
    )
    
    peer_average = Column(
        Numeric(precision=20, scale=4),
        nullable=True,
        comment="Peer group average value"
    )
    
    percentile_rank = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Percentile ranking (0-100)"
    )
    
    comparison_group = Column(
        String(100),
        nullable=True,
        comment="Comparison group identifier"
    )

    