"""
Custom Reports Repository for flexible report generation.

Provides comprehensive report management with:
- Report definition and template management
- Scheduled report execution
- Report result caching
- Execution history tracking
- Multi-format export capabilities
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta, time
from decimal import Decimal
from sqlalchemy import and_, or_, func, select, case, desc
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
import hashlib
import json

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.pagination import PaginationManager
from app.models.analytics.custom_reports import (
    CustomReportDefinition,
    ReportSchedule,
    ReportExecutionHistory,
    CachedReportResult,
)


class CustomReportsRepository(BaseRepository):
    """Repository for custom report operations."""
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.pagination = PaginationManager()
    
    # ==================== Report Definition Operations ====================
    
    def create_report_definition(
        self,
        owner_id: UUID,
        report_data: Dict[str, Any]
    ) -> CustomReportDefinition:
        """
        Create a new custom report definition.
        
        Args:
            owner_id: User ID creating the report
            report_data: Report configuration data
            
        Returns:
            Created CustomReportDefinition instance
        """
        # Calculate complexity score
        complexity = self._calculate_report_complexity(report_data)
        
        report = CustomReportDefinition(
            owner_id=owner_id,
            complexity_score=complexity,
            **report_data
        )
        
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        
        return report
    
    def update_report_definition(
        self,
        report_id: UUID,
        update_data: Dict[str, Any]
    ) -> Optional[CustomReportDefinition]:
        """Update an existing report definition."""
        report = self.db.query(CustomReportDefinition).filter(
            CustomReportDefinition.id == report_id
        ).first()
        
        if not report:
            return None
        
        # Recalculate complexity if fields/filters changed
        if 'fields' in update_data or 'filters' in update_data:
            complexity = self._calculate_report_complexity(update_data)
            update_data['complexity_score'] = complexity
        
        for key, value in update_data.items():
            setattr(report, key, value)
        
        self.db.commit()
        self.db.refresh(report)
        
        return report
    
    def get_report_definition(
        self,
        report_id: UUID
    ) -> Optional[CustomReportDefinition]:
        """Get a report definition by ID."""
        return self.db.query(CustomReportDefinition).filter(
            CustomReportDefinition.id == report_id
        ).first()
    
    def get_user_reports(
        self,
        user_id: UUID,
        include_shared: bool = True,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[CustomReportDefinition], int]:
        """
        Get all reports accessible to a user.
        
        Args:
            user_id: User ID
            include_shared: Whether to include reports shared with user
            page: Page number
            page_size: Items per page
            
        Returns:
            Tuple of (reports list, total count)
        """
        query = QueryBuilder(CustomReportDefinition, self.db)
        
        if include_shared:
            # Include owned reports and reports shared with user
            query = query.where(
                or_(
                    CustomReportDefinition.owner_id == user_id,
                    CustomReportDefinition.shared_with_user_ids.contains([user_id]),
                    CustomReportDefinition.is_public == True
                )
            )
        else:
            query = query.where(CustomReportDefinition.owner_id == user_id)
        
        query = query.order_by(CustomReportDefinition.created_at.desc())
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.limit(page_size).offset(offset)
        
        reports = query.all()
        
        return reports, total
    
    def get_public_templates(
        self,
        module: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[CustomReportDefinition], int]:
        """Get public report templates."""
        query = QueryBuilder(CustomReportDefinition, self.db)
        
        query = query.where(CustomReportDefinition.is_template == True)
        query = query.where(CustomReportDefinition.is_public == True)
        
        if module:
            query = query.where(CustomReportDefinition.module == module)
        
        query = query.order_by(CustomReportDefinition.run_count.desc())
        
        total = query.count()
        
        offset = (page - 1) * page_size
        query = query.limit(page_size).offset(offset)
        
        templates = query.all()
        
        return templates, total
    
    def search_reports(
        self,
        user_id: UUID,
        search_term: str,
        module: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[CustomReportDefinition], int]:
        """Search reports by name or description."""
        query = QueryBuilder(CustomReportDefinition, self.db)
        
        # Access filter
        query = query.where(
            or_(
                CustomReportDefinition.owner_id == user_id,
                CustomReportDefinition.shared_with_user_ids.contains([user_id]),
                CustomReportDefinition.is_public == True
            )
        )
        
        # Search filter
        search_filter = or_(
            CustomReportDefinition.report_name.ilike(f'%{search_term}%'),
            CustomReportDefinition.description.ilike(f'%{search_term}%')
        )
        query = query.where(search_filter)
        
        # Module filter
        if module:
            query = query.where(CustomReportDefinition.module == module)
        
        total = query.count()
        
        offset = (page - 1) * page_size
        query = query.limit(page_size).offset(offset)
        
        reports = query.all()
        
        return reports, total
    
    def share_report(
        self,
        report_id: UUID,
        user_ids: Optional[List[UUID]] = None,
        role: Optional[str] = None,
        is_public: bool = False
    ) -> Optional[CustomReportDefinition]:
        """Share a report with users or roles."""
        report = self.get_report_definition(report_id)
        
        if not report:
            return None
        
        if user_ids:
            # Add to existing shared users
            existing_users = report.shared_with_user_ids or []
            new_users = list(set(existing_users + user_ids))
            report.shared_with_user_ids = new_users
        
        if role:
            report.shared_with_role = role
        
        if is_public:
            report.is_public = True
        
        report.is_shared = True
        
        self.db.commit()
        self.db.refresh(report)
        
        return report
    
    def unshare_report(
        self,
        report_id: UUID,
        user_ids: Optional[List[UUID]] = None
    ) -> Optional[CustomReportDefinition]:
        """Remove sharing for specific users."""
        report = self.get_report_definition(report_id)
        
        if not report:
            return None
        
        if user_ids and report.shared_with_user_ids:
            remaining_users = [
                uid for uid in report.shared_with_user_ids
                if uid not in user_ids
            ]
            report.shared_with_user_ids = remaining_users if remaining_users else None
        
        # Update is_shared flag
        report.is_shared = bool(
            report.shared_with_user_ids or 
            report.shared_with_role or 
            report.is_public
        )
        
        self.db.commit()
        self.db.refresh(report)
        
        return report
    
    def delete_report_definition(
        self,
        report_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Delete a report definition (only owner can delete).
        
        Args:
            report_id: Report ID
            user_id: User requesting deletion
            
        Returns:
            True if deleted, False if not found or unauthorized
        """
        report = self.db.query(CustomReportDefinition).filter(
            and_(
                CustomReportDefinition.id == report_id,
                CustomReportDefinition.owner_id == user_id
            )
        ).first()
        
        if not report:
            return False
        
        self.db.delete(report)
        self.db.commit()
        
        return True
    
    def _calculate_report_complexity(
        self,
        report_data: Dict[str, Any]
    ) -> int:
        """
        Calculate report complexity score (0-100).
        
        Based on:
        - Number of fields
        - Number of filters
        - Presence of grouping
        - Join complexity
        """
        score = 0
        
        # Field count (max 30 points)
        fields = report_data.get('fields', [])
        field_count = len(fields) if isinstance(fields, list) else 0
        score += min(field_count * 3, 30)
        
        # Filter count (max 30 points)
        filters = report_data.get('filters', {})
        filter_count = len(filters) if isinstance(filters, dict) else 0
        score += min(filter_count * 5, 30)
        
        # Grouping (20 points)
        if report_data.get('group_by'):
            score += 20
        
        # Sorting (10 points)
        if report_data.get('sort_by'):
            score += 10
        
        # Complex filters (10 points)
        if filters and any(
            isinstance(v, dict) for v in filters.values()
        ):
            score += 10
        
        return min(score, 100)
    
    # ==================== Report Scheduling ====================
    
    def create_schedule(
        self,
        report_definition_id: UUID,
        schedule_data: Dict[str, Any]
    ) -> ReportSchedule:
        """Create a new report schedule."""
        # Calculate next run time
        next_run = self._calculate_next_run_time(
            schedule_data.get('frequency'),
            schedule_data.get('time_of_day'),
            schedule_data.get('day_of_week'),
            schedule_data.get('day_of_month'),
            schedule_data.get('timezone', 'UTC')
        )
        
        schedule = ReportSchedule(
            report_definition_id=report_definition_id,
            next_run_at=next_run,
            **schedule_data
        )
        
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        
        return schedule
    
    def update_schedule(
        self,
        schedule_id: UUID,
        update_data: Dict[str, Any]
    ) -> Optional[ReportSchedule]:
        """Update a report schedule."""
        schedule = self.db.query(ReportSchedule).filter(
            ReportSchedule.id == schedule_id
        ).first()
        
        if not schedule:
            return None
        
        # Recalculate next run if schedule changed
        if any(key in update_data for key in ['frequency', 'time_of_day', 'day_of_week', 'day_of_month']):
            next_run = self._calculate_next_run_time(
                update_data.get('frequency', schedule.frequency),
                update_data.get('time_of_day', schedule.time_of_day),
                update_data.get('day_of_week', schedule.day_of_week),
                update_data.get('day_of_month', schedule.day_of_month),
                update_data.get('timezone', schedule.timezone)
            )
            update_data['next_run_at'] = next_run
        
        for key, value in update_data.items():
            setattr(schedule, key, value)
        
        self.db.commit()
        self.db.refresh(schedule)
        
        return schedule
    
    def get_schedule(
        self,
        schedule_id: UUID
    ) -> Optional[ReportSchedule]:
        """Get a report schedule by ID."""
        return self.db.query(ReportSchedule).filter(
            ReportSchedule.id == schedule_id
        ).first()
    
    def get_schedules_for_report(
        self,
        report_definition_id: UUID
    ) -> List[ReportSchedule]:
        """Get all schedules for a report."""
        return self.db.query(ReportSchedule).filter(
            ReportSchedule.report_definition_id == report_definition_id
        ).all()
    
    def get_due_schedules(
        self,
        current_time: Optional[datetime] = None
    ) -> List[ReportSchedule]:
        """Get schedules that are due for execution."""
        if not current_time:
            current_time = datetime.utcnow()
        
        return self.db.query(ReportSchedule).filter(
            and_(
                ReportSchedule.is_active == True,
                ReportSchedule.next_run_at <= current_time
            )
        ).all()
    
    def update_schedule_after_execution(
        self,
        schedule_id: UUID,
        status: str,
        error_message: Optional[str] = None
    ) -> Optional[ReportSchedule]:
        """Update schedule after execution."""
        schedule = self.get_schedule(schedule_id)
        
        if not schedule:
            return None
        
        schedule.last_run_at = datetime.utcnow()
        schedule.last_run_status = status
        schedule.execution_count += 1
        
        if status == 'failed':
            schedule.failure_count += 1
            
            # Disable after 5 consecutive failures
            if schedule.failure_count >= 5:
                schedule.is_active = False
        else:
            schedule.failure_count = 0  # Reset on success
        
        # Calculate next run
        schedule.next_run_at = self._calculate_next_run_time(
            schedule.frequency,
            schedule.time_of_day,
            schedule.day_of_week,
            schedule.day_of_month,
            schedule.timezone
        )
        
        self.db.commit()
        self.db.refresh(schedule)
        
        return schedule
    
    def delete_schedule(
        self,
        schedule_id: UUID
    ) -> bool:
        """Delete a report schedule."""
        schedule = self.db.query(ReportSchedule).filter(
            ReportSchedule.id == schedule_id
        ).first()
        
        if not schedule:
            return False
        
        self.db.delete(schedule)
        self.db.commit()
        
        return True
    
    def _calculate_next_run_time(
        self,
        frequency: str,
        time_of_day: time,
        day_of_week: Optional[int],
        day_of_month: Optional[int],
        timezone: str
    ) -> datetime:
        """Calculate next scheduled run time."""
        # Simplified calculation (assumes UTC)
        now = datetime.utcnow()
        
        # Combine today's date with scheduled time
        next_run = datetime.combine(now.date(), time_of_day)
        
        if frequency == 'daily':
            # If time has passed today, schedule for tomorrow
            if next_run <= now:
                next_run += timedelta(days=1)
        
        elif frequency == 'weekly':
            # Find next occurrence of day_of_week
            current_weekday = now.weekday()
            days_ahead = (day_of_week - current_weekday) % 7
            
            if days_ahead == 0 and next_run <= now:
                days_ahead = 7
            
            next_run += timedelta(days=days_ahead)
        
        elif frequency == 'monthly':
            # Find next occurrence of day_of_month
            if day_of_month <= now.day and next_run <= now:
                # Next month
                if now.month == 12:
                    next_month = datetime(now.year + 1, 1, day_of_month)
                else:
                    next_month = datetime(now.year, now.month + 1, day_of_month)
                next_run = datetime.combine(next_month.date(), time_of_day)
            else:
                next_run = datetime.combine(
                    datetime(now.year, now.month, day_of_month).date(),
                    time_of_day
                )
        
        elif frequency == 'quarterly':
            # Next quarter
            quarter_months = [1, 4, 7, 10]
            current_quarter_month = min(
                [m for m in quarter_months if m >= now.month],
                default=1
            )
            
            if current_quarter_month == 1:
                next_year = now.year + 1
            else:
                next_year = now.year
            
            next_run = datetime.combine(
                datetime(next_year, current_quarter_month, day_of_month or 1).date(),
                time_of_day
            )
        
        return next_run
    
    # ==================== Execution History ====================
    
    def create_execution_history(
        self,
        report_definition_id: UUID,
        execution_data: Dict[str, Any]
    ) -> ReportExecutionHistory:
        """Create a new execution history record."""
        history = ReportExecutionHistory(
            report_definition_id=report_definition_id,
            started_at=datetime.utcnow(),
            **execution_data
        )
        
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        
        return history
    
    def update_execution_history(
        self,
        execution_id: UUID,
        update_data: Dict[str, Any]
    ) -> Optional[ReportExecutionHistory]:
        """Update execution history record."""
        history = self.db.query(ReportExecutionHistory).filter(
            ReportExecutionHistory.id == execution_id
        ).first()
        
        if not history:
            return None
        
        # Calculate execution time if completed
        if 'completed_at' in update_data and not history.completed_at:
            completed_at = update_data['completed_at']
            execution_time = int(
                (completed_at - history.started_at).total_seconds() * 1000
            )
            update_data['execution_time_ms'] = execution_time
        
        for key, value in update_data.items():
            setattr(history, key, value)
        
        self.db.commit()
        self.db.refresh(history)
        
        return history
    
    def get_execution_history(
        self,
        report_definition_id: UUID,
        limit: int = 10
    ) -> List[ReportExecutionHistory]:
        """Get execution history for a report."""
        return self.db.query(ReportExecutionHistory).filter(
            ReportExecutionHistory.report_definition_id == report_definition_id
        ).order_by(
            ReportExecutionHistory.started_at.desc()
        ).limit(limit).all()
    
    def get_execution_statistics(
        self,
        report_definition_id: UUID
    ) -> Dict[str, Any]:
        """Get execution statistics for a report."""
        history = self.db.query(ReportExecutionHistory).filter(
            ReportExecutionHistory.report_definition_id == report_definition_id
        ).all()
        
        if not history:
            return {
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
                'success_rate': 0,
                'average_execution_time_ms': 0,
            }
        
        successful = [h for h in history if h.status == 'completed']
        failed = [h for h in history if h.status == 'failed']
        
        execution_times = [
            h.execution_time_ms for h in successful
            if h.execution_time_ms is not None
        ]
        
        avg_time = (
            sum(execution_times) / len(execution_times)
            if execution_times else 0
        )
        
        return {
            'total_executions': len(history),
            'successful_executions': len(successful),
            'failed_executions': len(failed),
            'success_rate': (len(successful) / len(history) * 100) if history else 0,
            'average_execution_time_ms': round(avg_time),
            'last_execution': history[0].started_at if history else None,
        }
    
    # ==================== Result Caching ====================
    
    def cache_report_result(
        self,
        report_definition_id: UUID,
        execution_history_id: Optional[UUID],
        result_data: Any,
        parameters: Dict[str, Any],
        cache_ttl_seconds: int = 3600
    ) -> CachedReportResult:
        """Cache report execution result."""
        # Generate parameter hash for cache key
        params_hash = self._generate_parameters_hash(parameters)
        
        # Calculate column definitions from result
        column_definitions = self._extract_column_definitions(result_data)
        
        # Calculate summary stats
        summary_stats = self._calculate_summary_statistics(result_data)
        
        # Count rows
        row_count = len(result_data) if isinstance(result_data, list) else 0
        
        # Calculate data size
        data_json = json.dumps(result_data)
        data_size = len(data_json.encode('utf-8'))
        
        # Set expiration
        cache_expires_at = datetime.utcnow() + timedelta(seconds=cache_ttl_seconds)
        
        # Check for existing cache
        existing = self.db.query(CachedReportResult).filter(
            and_(
                CachedReportResult.report_definition_id == report_definition_id,
                CachedReportResult.parameters_hash == params_hash
            )
        ).first()
        
        if existing:
            # Update existing cache
            existing.result_data = result_data
            existing.row_count = row_count
            existing.column_definitions = column_definitions
            existing.summary_stats = summary_stats
            existing.data_size_bytes = data_size
            existing.generated_at = datetime.utcnow()
            existing.cache_expires_at = cache_expires_at
            existing.execution_history_id = execution_history_id
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        # Create new cache
        cached_result = CachedReportResult(
            report_definition_id=report_definition_id,
            execution_history_id=execution_history_id,
            result_data=result_data,
            row_count=row_count,
            column_definitions=column_definitions,
            summary_stats=summary_stats,
            parameters_hash=params_hash,
            data_size_bytes=data_size,
            cache_expires_at=cache_expires_at,
            is_cached=True
        )
        
        self.db.add(cached_result)
        self.db.commit()
        self.db.refresh(cached_result)
        
        return cached_result
    
    def get_cached_result(
        self,
        report_definition_id: UUID,
        parameters: Dict[str, Any]
    ) -> Optional[CachedReportResult]:
        """Get cached result if available and valid."""
        params_hash = self._generate_parameters_hash(parameters)
        
        cached = self.db.query(CachedReportResult).filter(
            and_(
                CachedReportResult.report_definition_id == report_definition_id,
                CachedReportResult.parameters_hash == params_hash,
                CachedReportResult.cache_expires_at > datetime.utcnow()
            )
        ).first()
        
        if cached:
            # Increment hit count
            cached.cache_hit_count += 1
            self.db.commit()
        
        return cached
    
    def invalidate_report_cache(
        self,
        report_definition_id: UUID
    ) -> int:
        """Invalidate all cached results for a report."""
        count = self.db.query(CachedReportResult).filter(
            CachedReportResult.report_definition_id == report_definition_id
        ).update({
            'cache_expires_at': datetime.utcnow()
        })
        
        self.db.commit()
        
        return count
    
    def cleanup_expired_cache(
        self,
        before_date: Optional[datetime] = None
    ) -> int:
        """Delete expired cache entries."""
        if not before_date:
            before_date = datetime.utcnow()
        
        count = self.db.query(CachedReportResult).filter(
            CachedReportResult.cache_expires_at < before_date
        ).delete()
        
        self.db.commit()
        
        return count
    
    def _generate_parameters_hash(
        self,
        parameters: Dict[str, Any]
    ) -> str:
        """Generate hash from parameters for caching."""
        # Sort parameters for consistent hashing
        sorted_params = json.dumps(parameters, sort_keys=True)
        
        # Generate SHA256 hash
        hash_object = hashlib.sha256(sorted_params.encode())
        
        return hash_object.hexdigest()
    
    def _extract_column_definitions(
        self,
        result_data: Any
    ) -> Dict[str, Any]:
        """Extract column definitions from result data."""
        if not result_data or not isinstance(result_data, list):
            return {}
        
        if not result_data[0]:
            return {}
        
        first_row = result_data[0]
        
        columns = {}
        for key, value in first_row.items():
            columns[key] = {
                'type': type(value).__name__,
                'nullable': value is None,
            }
        
        return columns
    
    def _calculate_summary_statistics(
        self,
        result_data: Any
    ) -> Dict[str, Any]:
        """Calculate summary statistics for numeric columns."""
        if not result_data or not isinstance(result_data, list):
            return {}
        
        summary = {
            'row_count': len(result_data),
        }
        
        # Find numeric columns
        if result_data:
            first_row = result_data[0]
            numeric_columns = [
                key for key, value in first_row.items()
                if isinstance(value, (int, float, Decimal))
            ]
            
            # Calculate stats for each numeric column
            for col in numeric_columns:
                values = [
                    row[col] for row in result_data
                    if row.get(col) is not None
                ]
                
                if values:
                    summary[col] = {
                        'min': min(values),
                        'max': max(values),
                        'sum': sum(values),
                        'avg': sum(values) / len(values),
                        'count': len(values),
                    }
        
        return summary
    
    # ==================== Report Execution ====================
    
    def increment_run_count(
        self,
        report_definition_id: UUID
    ) -> Optional[CustomReportDefinition]:
        """Increment run count for a report."""
        report = self.get_report_definition(report_definition_id)
        
        if not report:
            return None
        
        report.run_count += 1
        report.last_run_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(report)
        
        return report