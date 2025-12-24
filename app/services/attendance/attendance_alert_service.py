"""
Attendance alert service for configuration, triggering, listing, and acknowledgment.

Handles:
- Alert configuration per hostel
- Manual and automatic alert triggering
- Alert acknowledgment and resolution
- Alert listing with filtering
- Summary statistics
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, date, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.attendance import AttendanceAlertRepository
from app.models.attendance.attendance_alert import AttendanceAlert as AttendanceAlertModel
from app.schemas.attendance.attendance_alert import (
    AlertConfig,
    AlertTrigger,
    AlertAcknowledgment,
    AlertList,
    AlertSummary,
)

logger = logging.getLogger(__name__)


class AttendanceAlertService(
    BaseService[AttendanceAlertModel, AttendanceAlertRepository]
):
    """
    Service for attendance alerts: configure triggers, generate alerts, list & acknowledge.
    
    Responsibilities:
    - Configure alert rules and thresholds
    - Trigger manual and automatic alerts
    - Manage alert lifecycle (open, acknowledged, resolved)
    - Provide alert analytics and summaries
    """

    def __init__(self, repository: AttendanceAlertRepository, db_session: Session):
        """
        Initialize alert service.
        
        Args:
            repository: AttendanceAlertRepository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._operation_context = "AttendanceAlertService"

    def save_configuration(
        self,
        hostel_id: UUID,
        config: AlertConfig,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[AlertConfig]:
        """
        Save per-hostel alert configuration.
        
        Configures when and how alerts should be triggered.
        
        Args:
            hostel_id: UUID of hostel
            config: AlertConfig with alert settings
            updated_by: UUID of user updating the configuration
            
        Returns:
            ServiceResult containing saved AlertConfig
        """
        operation = "save_configuration"
        logger.info(
            f"{operation}: hostel_id={hostel_id}, updated_by={updated_by}"
        )
        
        try:
            # Validate configuration
            validation_result = self._validate_alert_config(config)
            if not validation_result.success:
                return validation_result
            
            # Save configuration
            saved = self.repository.save_configuration(
                hostel_id=hostel_id,
                config=config,
                updated_by=updated_by
            )
            
            self.db.commit()
            
            logger.info(
                f"{operation} successful for hostel {hostel_id}"
            )
            
            return ServiceResult.success(
                saved,
                message="Alert configuration saved successfully",
                metadata={"hostel_id": str(hostel_id)}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while saving alert configuration: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(hostel_id)}
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, hostel_id)

    def get_configuration(
        self,
        hostel_id: UUID,
    ) -> ServiceResult[AlertConfig]:
        """
        Get current alert configuration for hostel.
        
        Args:
            hostel_id: UUID of hostel
            
        Returns:
            ServiceResult containing AlertConfig
        """
        operation = "get_configuration"
        logger.debug(f"{operation}: hostel_id={hostel_id}")
        
        try:
            config = self.repository.get_configuration(hostel_id)
            
            if not config:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Alert configuration not found for this hostel",
                        severity=ErrorSeverity.WARNING,
                        details={"hostel_id": str(hostel_id)}
                    )
                )
            
            return ServiceResult.success(
                config,
                metadata={"hostel_id": str(hostel_id)}
            )
            
        except Exception as e:
            logger.error(f"{operation} error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, hostel_id)

    def trigger_alert(
        self,
        trigger: AlertTrigger,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Trigger a manual alert based on provided info.
        
        Args:
            trigger: AlertTrigger with alert details
            
        Returns:
            ServiceResult with alert creation confirmation
        """
        operation = "trigger_alert"
        logger.info(
            f"{operation}: hostel_id={trigger.hostel_id}, "
            f"alert_type={trigger.alert_type}, "
            f"severity={trigger.severity}"
        )
        
        try:
            # Validate trigger data
            validation_result = self._validate_alert_trigger(trigger)
            if not validation_result.success:
                return validation_result
            
            # Create alert
            alert = self.repository.trigger_alert(trigger)
            
            self.db.commit()
            
            response_data = {
                "alert_id": str(alert.id) if hasattr(alert, 'id') else None,
                "hostel_id": str(trigger.hostel_id),
                "alert_type": trigger.alert_type,
                "severity": trigger.severity,
                "triggered_at": datetime.utcnow().isoformat(),
            }
            
            logger.info(
                f"{operation} successful: alert_id={response_data['alert_id']}"
            )
            
            return ServiceResult.success(
                response_data,
                message="Alert triggered successfully",
                metadata={"alert_type": trigger.alert_type}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while triggering alert: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(trigger.hostel_id)}
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, trigger.hostel_id)

    def acknowledge(
        self,
        alert_id: UUID,
        ack: AlertAcknowledgment,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Acknowledge (and optionally resolve) an alert.
        
        Args:
            alert_id: UUID of alert to acknowledge
            ack: AlertAcknowledgment with acknowledgment details
            
        Returns:
            ServiceResult with acknowledgment confirmation
        """
        operation = "acknowledge_alert"
        logger.info(
            f"{operation}: alert_id={alert_id}, "
            f"acknowledged_by={ack.acknowledged_by}"
        )
        
        try:
            # Acknowledge alert
            success = self.repository.acknowledge_alert(alert_id, ack)
            
            if not success:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Alert not found: {alert_id}",
                        severity=ErrorSeverity.WARNING,
                        details={"alert_id": str(alert_id)}
                    )
                )
            
            self.db.commit()
            
            response_data = {
                "alert_id": str(alert_id),
                "acknowledged": True,
                "acknowledged_by": str(ack.acknowledged_by),
                "acknowledged_at": datetime.utcnow().isoformat(),
                "resolved": getattr(ack, 'resolved', False),
            }
            
            logger.info(f"{operation} successful: alert_id={alert_id}")
            
            return ServiceResult.success(
                response_data,
                message="Alert acknowledged successfully",
                metadata={"alert_id": str(alert_id)}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while acknowledging alert: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"alert_id": str(alert_id)}
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, alert_id)

    def list_alerts(
        self,
        hostel_id: UUID,
        page: int = 1,
        page_size: int = 50,
        status_filter: Optional[str] = None,
        severity_filter: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ServiceResult[AlertList]:
        """
        List alerts with aggregate statistics and filtering.
        
        Args:
            hostel_id: UUID of hostel
            page: Page number (1-indexed)
            page_size: Number of alerts per page
            status_filter: Optional status filter (open, acknowledged, resolved)
            severity_filter: Optional severity filter (low, medium, high, critical)
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            
        Returns:
            ServiceResult containing AlertList with alerts and statistics
        """
        operation = "list_alerts"
        logger.debug(
            f"{operation}: hostel_id={hostel_id}, page={page}, "
            f"page_size={page_size}, status={status_filter}, "
            f"severity={severity_filter}"
        )
        
        try:
            # Validate pagination
            if page < 1:
                page = 1
            if page_size < 1:
                page_size = 50
            if page_size > 500:
                page_size = 500
            
            # List alerts
            listing = self.repository.list_alerts(
                hostel_id=hostel_id,
                page=page,
                page_size=page_size,
                status_filter=status_filter,
                severity_filter=severity_filter,
                start_date=start_date,
                end_date=end_date
            )
            
            logger.debug(
                f"{operation} returned {len(listing.alerts)} alerts"
            )
            
            return ServiceResult.success(
                listing,
                metadata={
                    "count": len(listing.alerts),
                    "page": page,
                    "page_size": page_size,
                    "hostel_id": str(hostel_id),
                    "has_more": len(listing.alerts) == page_size
                }
            )
            
        except SQLAlchemyError as e:
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while listing alerts: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(hostel_id)}
                )
            )
            
        except Exception as e:
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, hostel_id)

    def get_summary(
        self,
        hostel_id: UUID,
        days: int = 30,
    ) -> ServiceResult[AlertSummary]:
        """
        Return a hostel-level alert summary for dashboards.
        
        Includes counts by status, severity, and trend information.
        
        Args:
            hostel_id: UUID of hostel
            days: Number of days to include in summary (default 30)
            
        Returns:
            ServiceResult containing AlertSummary
        """
        operation = "get_alert_summary"
        logger.debug(f"{operation}: hostel_id={hostel_id}, days={days}")
        
        try:
            # Validate days parameter
            if days < 1:
                days = 1
            if days > 365:
                days = 365
            
            # Get summary
            summary = self.repository.get_summary(hostel_id=hostel_id, days=days)
            
            logger.debug(
                f"{operation} successful: hostel_id={hostel_id}, "
                f"total_alerts={summary.total_alerts if summary else 0}"
            )
            
            return ServiceResult.success(
                summary,
                metadata={
                    "hostel_id": str(hostel_id),
                    "days": days
                }
            )
            
        except SQLAlchemyError as e:
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while fetching alert summary: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(hostel_id)}
                )
            )
            
        except Exception as e:
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, hostel_id)

    def resolve_alert(
        self,
        alert_id: UUID,
        resolved_by: UUID,
        resolution_notes: Optional[str] = None,
    ) -> ServiceResult[bool]:
        """
        Mark an alert as resolved.
        
        Args:
            alert_id: UUID of alert to resolve
            resolved_by: UUID of user resolving the alert
            resolution_notes: Optional notes about the resolution
            
        Returns:
            ServiceResult indicating resolution success
        """
        operation = "resolve_alert"
        logger.info(
            f"{operation}: alert_id={alert_id}, resolved_by={resolved_by}"
        )
        
        try:
            success = self.repository.resolve_alert(
                alert_id=alert_id,
                resolved_by=resolved_by,
                resolution_notes=resolution_notes
            )
            
            if not success:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Alert not found: {alert_id}",
                        severity=ErrorSeverity.WARNING,
                        details={"alert_id": str(alert_id)}
                    )
                )
            
            self.db.commit()
            
            logger.info(f"{operation} successful: alert_id={alert_id}")
            
            return ServiceResult.success(
                True,
                message="Alert resolved successfully",
                metadata={"alert_id": str(alert_id)}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"{operation} database error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DATABASE_ERROR,
                    message=f"Database error while resolving alert: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                    details={"alert_id": str(alert_id)}
                )
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"{operation} unexpected error: {str(e)}", exc_info=True)
            return self._handle_exception(e, operation, alert_id)

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _validate_alert_config(self, config: AlertConfig) -> ServiceResult[None]:
        """
        Validate alert configuration.
        
        Args:
            config: AlertConfig to validate
            
        Returns:
            ServiceResult indicating validation success/failure
        """
        errors = []
        
        # Validate enabled status
        if not hasattr(config, 'enabled'):
            errors.append("Enabled status is required")
        
        # Validate thresholds if provided
        if hasattr(config, 'absence_threshold'):
            if config.absence_threshold < 1:
                errors.append("Absence threshold must be at least 1")
        
        if hasattr(config, 'late_threshold'):
            if config.late_threshold < 1:
                errors.append("Late threshold must be at least 1")
        
        # Validate notification channels
        if hasattr(config, 'notification_channels'):
            valid_channels = {'email', 'sms', 'push', 'in_app'}
            invalid = set(config.notification_channels) - valid_channels
            if invalid:
                errors.append(f"Invalid notification channels: {invalid}")
        
        if errors:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Alert configuration validation failed",
                    severity=ErrorSeverity.WARNING,
                    details={"errors": errors}
                )
            )
        
        return ServiceResult.success(None)

    def _validate_alert_trigger(self, trigger: AlertTrigger) -> ServiceResult[None]:
        """
        Validate alert trigger data.
        
        Args:
            trigger: AlertTrigger to validate
            
        Returns:
            ServiceResult indicating validation success/failure
        """
        errors = []
        
        # Validate alert type
        if not hasattr(trigger, 'alert_type') or not trigger.alert_type:
            errors.append("Alert type is required")
        
        # Validate severity
        if not hasattr(trigger, 'severity') or not trigger.severity:
            errors.append("Severity is required")
        else:
            valid_severities = {'low', 'medium', 'high', 'critical'}
            if trigger.severity.lower() not in valid_severities:
                errors.append(f"Invalid severity: {trigger.severity}")
        
        # Validate message
        if not hasattr(trigger, 'message') or not trigger.message:
            errors.append("Alert message is required")
        
        if errors:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Alert trigger validation failed",
                    severity=ErrorSeverity.WARNING,
                    details={"errors": errors}
                )
            )
        
        return ServiceResult.success(None)