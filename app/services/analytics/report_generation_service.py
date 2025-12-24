"""
Report generation service for custom reports.

Optimizations:
- Added report template system
- Implemented scheduled report execution
- Enhanced report caching and versioning
- Added report sharing and permissions
- Improved error handling and validation
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, datetime, timedelta
from enum import Enum
import logging
import json

from sqlalchemy.orm import Session

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.analytics import CustomReportsRepository
from app.models.analytics.custom_reports import CustomReportDefinition as CustomReportDefinitionModel
from app.schemas.analytics.custom_reports import (
    CustomReportRequest,
    CustomReportDefinition,
    CustomReportResult,
    ReportExportRequest,
    ReportSchedule,
)

logger = logging.getLogger(__name__)


class ReportType(str, Enum):
    """Report types."""
    TABULAR = "tabular"
    CHART = "chart"
    DASHBOARD = "dashboard"
    SUMMARY = "summary"
    DETAILED = "detailed"


class ReportFormat(str, Enum):
    """Report output formats."""
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"
    HTML = "html"


class ScheduleFrequency(str, Enum):
    """Report schedule frequencies."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class ReportGenerationService(BaseService[CustomReportDefinitionModel, CustomReportsRepository]):
    """
    Service that manages custom report definitions, execution, schedules, and exports.
    
    Features:
    - Custom report creation and management
    - Report execution and caching
    - Scheduled report generation
    - Multi-format export
    - Report sharing and permissions
    """

    # Cache TTL for report results
    RESULT_CACHE_TTL = 3600  # 1 hour
    
    # Maximum report execution time
    MAX_EXECUTION_TIME = 300  # 5 minutes
    
    # Maximum rows per report
    MAX_REPORT_ROWS = 100000

    def __init__(self, repository: CustomReportsRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._result_cache = {}
        self._cache_timestamps = {}

    def create_report_definition(
        self,
        user_id: UUID,
        request: CustomReportRequest,
        validate_query: bool = True,
    ) -> ServiceResult[CustomReportDefinition]:
        """
        Create a custom report definition.
        
        Args:
            user_id: Creator user UUID
            request: Report definition request
            validate_query: Whether to validate the report query
            
        Returns:
            ServiceResult containing created report definition
        """
        try:
            # Validate request
            validation_result = self._validate_report_request(request)
            if not validation_result.success:
                return validation_result
            
            # Validate query if requested
            if validate_query and hasattr(request, 'query'):
                query_validation = self._validate_report_query(request.query)
                if not query_validation.success:
                    return query_validation
            
            # Create definition
            definition = self.repository.create_definition(user_id, request)
            
            if not definition:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to create report definition",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            self.db.commit()
            
            logger.info(f"Created report definition {definition.id} by user {user_id}")
            
            return ServiceResult.success(
                definition,
                message="Report definition created successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating report definition: {str(e)}")
            return self._handle_exception(e, "create report definition")

    def update_report_definition(
        self,
        definition_id: UUID,
        user_id: UUID,
        updates: Dict[str, Any],
    ) -> ServiceResult[CustomReportDefinition]:
        """
        Update a report definition.
        
        Args:
            definition_id: Report definition UUID
            user_id: User making the update
            updates: Fields to update
            
        Returns:
            ServiceResult containing updated definition
        """
        try:
            # Get existing definition
            definition = self.repository.get_by_id(definition_id)
            
            if not definition:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Report definition {definition_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check permissions
            if not self._check_report_permissions(definition, user_id, "edit"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.PERMISSION_DENIED,
                        message="User does not have permission to edit this report",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Update definition
            updated_definition = self.repository.update_definition(definition_id, updates)
            
            if not updated_definition:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to update report definition",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            self.db.commit()
            
            # Invalidate cache
            self._invalidate_report_cache(definition_id)
            
            return ServiceResult.success(
                updated_definition,
                message="Report definition updated successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating report definition: {str(e)}")
            return self._handle_exception(e, "update report definition", definition_id)

    def execute_report(
        self,
        definition_id: UUID,
        user_id: Optional[UUID] = None,
        parameters: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> ServiceResult[CustomReportResult]:
        """
        Execute a report.
        
        Args:
            definition_id: Report definition UUID
            user_id: User executing the report
            parameters: Runtime parameters
            use_cache: Whether to use cached results
            
        Returns:
            ServiceResult containing report result
        """
        execution_start = datetime.utcnow()
        
        try:
            # Get definition
            definition = self.repository.get_by_id(definition_id)
            
            if not definition:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Report definition {definition_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check permissions
            if user_id and not self._check_report_permissions(definition, user_id, "execute"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.PERMISSION_DENIED,
                        message="User does not have permission to execute this report",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check cache
            cache_key = self._get_cache_key(definition_id, parameters)
            if use_cache and self._is_result_cache_valid(cache_key):
                logger.info(f"Returning cached result for report {definition_id}")
                return ServiceResult.success(self._result_cache[cache_key])
            
            # Execute report
            result = self.repository.execute_report(
                definition_id,
                parameters=parameters,
                max_rows=self.MAX_REPORT_ROWS,
                timeout=self.MAX_EXECUTION_TIME,
            )
            
            if not result:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Report execution failed",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Calculate execution time
            execution_time = (datetime.utcnow() - execution_start).total_seconds()
            
            # Enhance result
            result.execution_time_seconds = round(execution_time, 2)
            result.executed_at = datetime.utcnow()
            result.executed_by = user_id
            
            # Cache result
            if use_cache:
                self._cache_result(cache_key, result)
            
            # Log execution
            self._log_report_execution(definition_id, user_id, execution_time, len(result.data) if hasattr(result, 'data') else 0)
            
            return ServiceResult.success(
                result,
                metadata={
                    "execution_time": execution_time,
                    "rows_returned": len(result.data) if hasattr(result, 'data') else 0,
                },
                message="Report executed successfully"
            )
            
        except Exception as e:
            execution_time = (datetime.utcnow() - execution_start).total_seconds()
            logger.error(f"Error executing report {definition_id}: {str(e)} (after {execution_time}s)")
            return self._handle_exception(e, "execute report", definition_id)

    def schedule_report(
        self,
        schedule: ReportSchedule,
        user_id: UUID,
    ) -> ServiceResult[ReportSchedule]:
        """
        Schedule a report for automatic execution.
        
        Args:
            schedule: Report schedule configuration
            user_id: User creating the schedule
            
        Returns:
            ServiceResult containing created schedule
        """
        try:
            # Validate schedule
            validation_result = self._validate_schedule(schedule)
            if not validation_result.success:
                return validation_result
            
            # Check permissions
            if hasattr(schedule, 'report_definition_id'):
                definition = self.repository.get_by_id(schedule.report_definition_id)
                if definition and not self._check_report_permissions(definition, user_id, "schedule"):
                    return ServiceResult.error(
                        ServiceError(
                            code=ErrorCode.PERMISSION_DENIED,
                            message="User does not have permission to schedule this report",
                            severity=ErrorSeverity.ERROR,
                        )
                    )
            
            # Create schedule
            saved_schedule = self.repository.create_schedule(schedule, user_id)
            
            if not saved_schedule:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to create report schedule",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            self.db.commit()
            
            logger.info(f"Created report schedule {saved_schedule.id} for report {schedule.report_definition_id}")
            
            return ServiceResult.success(
                saved_schedule,
                message="Report scheduled successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error scheduling report: {str(e)}")
            return self._handle_exception(e, "schedule report")

    def get_scheduled_reports(
        self,
        user_id: UUID,
        include_inactive: bool = False,
    ) -> ServiceResult[List[ReportSchedule]]:
        """
        Get scheduled reports for a user.
        
        Args:
            user_id: User UUID
            include_inactive: Include inactive schedules
            
        Returns:
            ServiceResult containing list of schedules
        """
        try:
            schedules = self.repository.get_user_schedules(user_id, include_inactive)
            
            if not schedules:
                schedules = []
            
            return ServiceResult.success(
                schedules,
                metadata={"count": len(schedules)},
                message=f"Retrieved {len(schedules)} scheduled reports"
            )
            
        except Exception as e:
            logger.error(f"Error getting scheduled reports: {str(e)}")
            return self._handle_exception(e, "get scheduled reports")

    def cancel_schedule(
        self,
        schedule_id: UUID,
        user_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Cancel a scheduled report.
        
        Args:
            schedule_id: Schedule UUID
            user_id: User canceling the schedule
            
        Returns:
            ServiceResult indicating success
        """
        try:
            # Get schedule
            schedule = self.repository.get_schedule_by_id(schedule_id)
            
            if not schedule:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Schedule {schedule_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check permissions
            if hasattr(schedule, 'created_by') and schedule.created_by != user_id:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.PERMISSION_DENIED,
                        message="User does not have permission to cancel this schedule",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Cancel schedule
            success = self.repository.cancel_schedule(schedule_id)
            
            if not success:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to cancel schedule",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            self.db.commit()
            
            return ServiceResult.success(
                True,
                message="Schedule canceled successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error canceling schedule: {str(e)}")
            return self._handle_exception(e, "cancel schedule", schedule_id)

    def export_report_result(
        self,
        request: ReportExportRequest,
        user_id: Optional[UUID] = None,
    ) -> ServiceResult[str]:
        """
        Export a report result to file.
        
        Args:
            request: Export request
            user_id: User requesting export
            
        Returns:
            ServiceResult containing file path
        """
        try:
            # Validate request
            if not hasattr(request, 'result_id') or not request.result_id:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Result ID is required",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Validate format
            try:
                ReportFormat(request.format)
            except ValueError:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid export format: {request.format}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Export result
            file_path = self.repository.export_result(request)
            
            if not file_path:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to export report result",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            logger.info(f"Exported report result {request.result_id} to {file_path}")
            
            return ServiceResult.success(
                file_path,
                message=f"Report exported successfully to {request.format.upper()}"
            )
            
        except Exception as e:
            logger.error(f"Error exporting report result: {str(e)}")
            return self._handle_exception(e, "export report result")

    def get_report_history(
        self,
        definition_id: UUID,
        limit: int = 50,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get execution history for a report.
        
        Args:
            definition_id: Report definition UUID
            limit: Maximum number of records
            
        Returns:
            ServiceResult containing execution history
        """
        try:
            history = self.repository.get_execution_history(definition_id, limit)
            
            if not history:
                history = []
            
            return ServiceResult.success(
                history,
                metadata={"count": len(history)},
                message=f"Retrieved {len(history)} execution records"
            )
            
        except Exception as e:
            logger.error(f"Error getting report history: {str(e)}")
            return self._handle_exception(e, "get report history", definition_id)

    def share_report(
        self,
        definition_id: UUID,
        owner_id: UUID,
        share_with_user_ids: List[UUID],
        permissions: List[str],
    ) -> ServiceResult[bool]:
        """
        Share a report with other users.
        
        Args:
            definition_id: Report definition UUID
            owner_id: Report owner UUID
            share_with_user_ids: List of user UUIDs to share with
            permissions: List of permissions to grant
            
        Returns:
            ServiceResult indicating success
        """
        try:
            # Get definition
            definition = self.repository.get_by_id(definition_id)
            
            if not definition:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Report definition {definition_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check ownership
            if hasattr(definition, 'created_by') and definition.created_by != owner_id:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.PERMISSION_DENIED,
                        message="Only the report owner can share it",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Validate permissions
            valid_permissions = {"view", "execute", "edit", "schedule"}
            invalid_perms = set(permissions) - valid_permissions
            
            if invalid_perms:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid permissions: {', '.join(invalid_perms)}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Share report
            success = self.repository.share_report(
                definition_id, share_with_user_ids, permissions
            )
            
            if not success:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to share report",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            self.db.commit()
            
            return ServiceResult.success(
                True,
                message=f"Report shared with {len(share_with_user_ids)} users"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error sharing report: {str(e)}")
            return self._handle_exception(e, "share report", definition_id)

    def delete_report_definition(
        self,
        definition_id: UUID,
        user_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Delete a report definition.
        
        Args:
            definition_id: Report definition UUID
            user_id: User requesting deletion
            
        Returns:
            ServiceResult indicating success
        """
        try:
            # Get definition
            definition = self.repository.get_by_id(definition_id)
            
            if not definition:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Report definition {definition_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check permissions
            if not self._check_report_permissions(definition, user_id, "delete"):
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.PERMISSION_DENIED,
                        message="User does not have permission to delete this report",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Delete definition
            success = self.repository.delete_definition(definition_id)
            
            if not success:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to delete report definition",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            self.db.commit()
            
            # Invalidate cache
            self._invalidate_report_cache(definition_id)
            
            return ServiceResult.success(
                True,
                message="Report definition deleted successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting report definition: {str(e)}")
            return self._handle_exception(e, "delete report definition", definition_id)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _validate_report_request(self, request: CustomReportRequest) -> ServiceResult[bool]:
        """Validate report request."""
        if not hasattr(request, 'name') or not request.name:
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Report name is required",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        if not hasattr(request, 'report_type'):
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Report type is required",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        try:
            ReportType(request.report_type)
        except ValueError:
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid report type: {request.report_type}",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        return ServiceResult.success(True)

    def _validate_report_query(self, query: str) -> ServiceResult[bool]:
        """Validate report query for safety."""
        # Prevent dangerous SQL operations
        dangerous_keywords = [
            'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE',
            'GRANT', 'REVOKE', 'INSERT', 'UPDATE'
        ]
        
        query_upper = query.upper()
        
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                return ServiceResult.error(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Query contains forbidden keyword: {keyword}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
        
        return ServiceResult.success(True)

    def _validate_schedule(self, schedule: ReportSchedule) -> ServiceResult[bool]:
        """Validate report schedule."""
        if not hasattr(schedule, 'frequency'):
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Schedule frequency is required",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        try:
            ScheduleFrequency(schedule.frequency)
        except ValueError:
            return ServiceResult.error(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid schedule frequency: {schedule.frequency}",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        return ServiceResult.success(True)

    def _check_report_permissions(
        self,
        definition: CustomReportDefinition,
        user_id: UUID,
        action: str,
    ) -> bool:
        """Check if user has permission to perform action on report."""
        # Owner has all permissions
        if hasattr(definition, 'created_by') and definition.created_by == user_id:
            return True
        
        # Check shared permissions
        if hasattr(definition, 'shared_with'):
            for share in definition.shared_with:
                if share.get('user_id') == str(user_id):
                    permissions = share.get('permissions', [])
                    
                    # Map actions to required permissions
                    permission_map = {
                        'view': ['view'],
                        'execute': ['view', 'execute'],
                        'edit': ['view', 'edit'],
                        'schedule': ['view', 'execute', 'schedule'],
                        'delete': ['view', 'edit'],
                    }
                    
                    required_perms = permission_map.get(action, [])
                    return any(perm in permissions for perm in required_perms)
        
        return False

    def _get_cache_key(self, definition_id: UUID, parameters: Optional[Dict[str, Any]]) -> str:
        """Generate cache key for report result."""
        param_str = json.dumps(parameters, sort_keys=True) if parameters else ""
        return f"report_{definition_id}_{hash(param_str)}"

    def _is_result_cache_valid(self, cache_key: str) -> bool:
        """Check if cached result is still valid."""
        if cache_key not in self._result_cache:
            return False
        
        if cache_key not in self._cache_timestamps:
            return False
        
        age = (datetime.utcnow() - self._cache_timestamps[cache_key]).total_seconds()
        return age < self.RESULT_CACHE_TTL

    def _cache_result(self, cache_key: str, result: CustomReportResult) -> None:
        """Cache report result."""
        self._result_cache[cache_key] = result
        self._cache_timestamps[cache_key] = datetime.utcnow()
        
        # Limit cache size
        if len(self._result_cache) > 100:
            oldest_keys = sorted(
                self._cache_timestamps.keys(),
                key=lambda k: self._cache_timestamps[k]
            )[:20]
            for key in oldest_keys:
                del self._result_cache[key]
                del self._cache_timestamps[key]

    def _invalidate_report_cache(self, definition_id: UUID) -> None:
        """Invalidate all cached results for a report."""
        prefix = f"report_{definition_id}_"
        keys_to_remove = [k for k in self._result_cache.keys() if k.startswith(prefix)]
        
        for key in keys_to_remove:
            del self._result_cache[key]
            if key in self._cache_timestamps:
                del self._cache_timestamps[key]

    def _log_report_execution(
        self,
        definition_id: UUID,
        user_id: Optional[UUID],
        execution_time: float,
        rows_returned: int,
    ) -> None:
        """Log report execution."""
        try:
            self.repository.log_execution(
                definition_id=definition_id,
                user_id=user_id,
                execution_time=execution_time,
                rows_returned=rows_returned,
                status="success",
            )
        except Exception as e:
            logger.error(f"Error logging report execution: {str(e)}")