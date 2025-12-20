# --- File: C:\Hostel-Main\app\services\analytics\report_generation_service.py ---
"""
Report Generation Service - Custom report execution and management.

Provides comprehensive reporting with:
- Custom report execution
- Scheduled report management
- Report caching and optimization
- Multi-format export
- Report history tracking
"""

from typing import List, Dict, Optional, Any
from datetime import date, datetime, timedelta, time
from decimal import Decimal
from sqlalchemy.orm import Session
from uuid import UUID
import logging
import hashlib
import json

from app.repositories.analytics.custom_reports_repository import (
    CustomReportsRepository
)


logger = logging.getLogger(__name__)


class ReportGenerationService:
    """Service for custom report generation and management."""
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.repo = CustomReportsRepository(db)
    
    # ==================== Report Definition Management ====================
    
    def create_report_definition(
        self,
        owner_id: UUID,
        report_name: str,
        module: str,
        fields: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None,
        group_by: Optional[List[str]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = 'asc',
        description: Optional[str] = None
    ) -> Any:
        """
        Create a new custom report definition.
        
        Args:
            owner_id: User creating the report
            report_name: Report name
            module: Module to report on (bookings, payments, etc.)
            fields: List of field definitions
            filters: Optional filter conditions
            group_by: Optional grouping fields
            sort_by: Optional sort field
            sort_order: Sort order (asc/desc)
            description: Optional description
            
        Returns:
            Created CustomReportDefinition
        """
        logger.info(f"Creating report definition: {report_name}")
        
        report_data = {
            'report_name': report_name,
            'description': description,
            'module': module,
            'fields': fields,
            'filters': filters,
            'group_by': group_by,
            'sort_by': sort_by,
            'sort_order': sort_order,
        }
        
        report = self.repo.create_report_definition(
            owner_id=owner_id,
            report_data=report_data
        )
        
        return report
    
    def get_user_reports(
        self,
        user_id: UUID,
        include_shared: bool = True,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Get all reports accessible to a user.
        
        Returns paginated list of report definitions.
        """
        reports, total = self.repo.get_user_reports(
            user_id=user_id,
            include_shared=include_shared,
            page=page,
            page_size=page_size
        )
        
        return {
            'reports': [self._format_report_definition(r) for r in reports],
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        }
    
    def get_public_templates(
        self,
        module: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Get public report templates."""
        templates, total = self.repo.get_public_templates(
            module=module,
            page=page,
            page_size=page_size
        )
        
        return {
            'templates': [self._format_report_definition(t) for t in templates],
            'total': total,
            'page': page,
            'page_size': page_size,
        }
    
    def share_report(
        self,
        report_id: UUID,
        user_ids: Optional[List[UUID]] = None,
        role: Optional[str] = None,
        is_public: bool = False
    ) -> Any:
        """Share a report with users or roles."""
        report = self.repo.share_report(
            report_id=report_id,
            user_ids=user_ids,
            role=role,
            is_public=is_public
        )
        
        return report
    
    def _format_report_definition(self, report: Any) -> Dict[str, Any]:
        """Format report definition for API response."""
        return {
            'id': str(report.id),
            'report_name': report.report_name,
            'description': report.description,
            'module': report.module,
            'fields': report.fields,
            'filters': report.filters,
            'group_by': report.group_by,
            'sort_by': report.sort_by,
            'sort_order': report.sort_order,
            'is_public': report.is_public,
            'is_template': report.is_template,
            'run_count': report.run_count,
            'last_run_at': report.last_run_at.isoformat() if report.last_run_at else None,
            'complexity_score': report.complexity_score,
            'created_at': report.created_at.isoformat(),
        }
    
    # ==================== Report Execution ====================
    
    def execute_report(
        self,
        report_id: UUID,
        executed_by: UUID,
        parameters: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a custom report.
        
        Args:
            report_id: Report definition ID
            executed_by: User executing the report
            parameters: Execution parameters (date ranges, filters, etc.)
            use_cache: Whether to use cached results if available
            
        Returns:
            Report execution results
        """
        logger.info(f"Executing report {report_id}")
        
        # Get report definition
        report_def = self.repo.get_report_definition(report_id)
        
        if not report_def:
            raise ValueError(f"Report definition {report_id} not found")
        
        # Check cache if enabled
        if use_cache and parameters:
            cached_result = self.repo.get_cached_result(report_id, parameters)
            if cached_result:
                logger.info(f"Using cached result for report {report_id}")
                
                # Create execution history record
                self._create_execution_history(
                    report_id, executed_by, 'completed',
                    cached_result.row_count, parameters
                )
                
                return {
                    'success': True,
                    'cached': True,
                    'data': cached_result.result_data,
                    'row_count': cached_result.row_count,
                    'column_definitions': cached_result.column_definitions,
                    'summary_stats': cached_result.summary_stats,
                }
        
        # Create execution history
        execution = self.repo.create_execution_history(
            report_definition_id=report_id,
            execution_data={
                'executed_by': executed_by,
                'execution_type': 'manual',
                'parameters_used': parameters,
            }
        )
        
        try:
            # Execute the report query
            result_data = self._execute_report_query(
                report_def, parameters or {}
            )
            
            # Update execution history
            self.repo.update_execution_history(
                execution_id=execution.id,
                update_data={
                    'completed_at': datetime.utcnow(),
                    'status': 'completed',
                    'rows_returned': len(result_data) if isinstance(result_data, list) else 0,
                }
            )
            
            # Cache the result
            if use_cache:
                self.repo.cache_report_result(
                    report_definition_id=report_id,
                    execution_history_id=execution.id,
                    result_data=result_data,
                    parameters=parameters or {},
                    cache_ttl_seconds=3600  # 1 hour
                )
            
            # Increment run count
            self.repo.increment_run_count(report_id)
            
            return {
                'success': True,
                'cached': False,
                'data': result_data,
                'row_count': len(result_data) if isinstance(result_data, list) else 0,
                'execution_id': str(execution.id),
            }
            
        except Exception as e:
            logger.error(f"Report execution failed: {str(e)}")
            
            # Update execution history with error
            self.repo.update_execution_history(
                execution_id=execution.id,
                update_data={
                    'completed_at': datetime.utcnow(),
                    'status': 'failed',
                    'error_message': str(e),
                }
            )
            
            return {
                'success': False,
                'error': str(e),
                'execution_id': str(execution.id),
            }
    
    def _execute_report_query(
        self,
        report_def: Any,
        parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Execute the actual report query.
        
        Builds and executes query based on report definition.
        """
        # This is a simplified implementation
        # In production, would build dynamic query based on report definition
        
        # Placeholder implementation
        logger.info(f"Executing query for module: {report_def.module}")
        
        # Would query the appropriate tables based on module and fields
        # Apply filters, grouping, sorting as defined
        
        # Return sample data
        return [
            {'id': 1, 'name': 'Sample 1', 'value': 100},
            {'id': 2, 'name': 'Sample 2', 'value': 200},
        ]
    
    def _create_execution_history(
        self,
        report_id: UUID,
        executed_by: UUID,
        status: str,
        rows_returned: int,
        parameters: Optional[Dict[str, Any]]
    ) -> None:
        """Create execution history record."""
        self.repo.create_execution_history(
            report_definition_id=report_id,
            execution_data={
                'executed_by': executed_by,
                'execution_type': 'manual',
                'status': status,
                'rows_returned': rows_returned,
                'parameters_used': parameters,
                'completed_at': datetime.utcnow(),
            }
        )
    
    # ==================== Report Scheduling ====================
    
    def create_schedule(
        self,
        report_id: UUID,
        schedule_name: str,
        frequency: str,
        time_of_day: time,
        recipients: List[str],
        format: str = 'pdf',
        day_of_week: Optional[int] = None,
        day_of_month: Optional[int] = None,
        timezone: str = 'UTC'
    ) -> Any:
        """
        Create a scheduled report execution.
        
        Args:
            report_id: Report definition ID
            schedule_name: Schedule name
            frequency: Frequency (daily, weekly, monthly, quarterly)
            time_of_day: Time to execute
            recipients: Email recipients
            format: Report format (csv, excel, json, pdf)
            day_of_week: Day for weekly schedules
            day_of_month: Day for monthly schedules
            timezone: Timezone for scheduling
            
        Returns:
            Created ReportSchedule
        """
        logger.info(f"Creating schedule for report {report_id}")
        
        schedule_data = {
            'schedule_name': schedule_name,
            'frequency': frequency,
            'time_of_day': time_of_day,
            'day_of_week': day_of_week,
            'day_of_month': day_of_month,
            'timezone': timezone,
            'recipients': recipients,
            'format': format,
        }
        
        schedule = self.repo.create_schedule(
            report_definition_id=report_id,
            schedule_data=schedule_data
        )
        
        return schedule
    
    def get_due_schedules(self) -> List[Any]:
        """Get schedules that are due for execution."""
        schedules = self.repo.get_due_schedules()
        return schedules
    
    def execute_scheduled_report(
        self,
        schedule_id: UUID
    ) -> Dict[str, Any]:
        """
        Execute a scheduled report.
        
        Called by scheduler (e.g., Celery task).
        """
        logger.info(f"Executing scheduled report {schedule_id}")
        
        schedule = self.repo.get_schedule(schedule_id)
        
        if not schedule:
            return {
                'success': False,
                'error': 'Schedule not found'
            }
        
        try:
            # Execute the report
            result = self.execute_report(
                report_id=schedule.report_definition_id,
                executed_by=None,  # System execution
                parameters={},
                use_cache=False  # Don't use cache for scheduled reports
            )
            
            if result['success']:
                # Send report to recipients
                self._send_report_to_recipients(
                    schedule.recipients,
                    schedule.format,
                    result['data']
                )
                
                # Update schedule
                self.repo.update_schedule_after_execution(
                    schedule_id=schedule_id,
                    status='completed'
                )
                
                return {
                    'success': True,
                    'schedule_id': str(schedule_id),
                    'rows_returned': result.get('row_count', 0)
                }
            else:
                # Update schedule with error
                self.repo.update_schedule_after_execution(
                    schedule_id=schedule_id,
                    status='failed',
                    error_message=result.get('error', 'Unknown error')
                )
                
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown error')
                }
                
        except Exception as e:
            logger.error(f"Scheduled report execution failed: {str(e)}")
            
            self.repo.update_schedule_after_execution(
                schedule_id=schedule_id,
                status='failed',
                error_message=str(e)
            )
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_report_to_recipients(
        self,
        recipients: List[str],
        format: str,
        data: Any
    ) -> None:
        """
        Send report to recipients via email.
        
        Would integrate with email service in production.
        """
        logger.info(f"Sending report to {len(recipients)} recipients in {format} format")
        
        # Placeholder for email sending logic
        # Would format data according to format and send via email service
        pass
    
    # ==================== Report History ====================
    
    def get_execution_history(
        self,
        report_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get execution history for a report."""
        history = self.repo.get_execution_history(report_id, limit)
        
        return [
            {
                'id': str(h.id),
                'executed_by': str(h.executed_by) if h.executed_by else 'System',
                'execution_type': h.execution_type,
                'started_at': h.started_at.isoformat(),
                'completed_at': h.completed_at.isoformat() if h.completed_at else None,
                'status': h.status,
                'rows_returned': h.rows_returned,
                'execution_time_ms': h.execution_time_ms,
                'error_message': h.error_message,
            }
            for h in history
        ]
    
    def get_execution_statistics(
        self,
        report_id: UUID
    ) -> Dict[str, Any]:
        """Get execution statistics for a report."""
        stats = self.repo.get_execution_statistics(report_id)
        return stats


