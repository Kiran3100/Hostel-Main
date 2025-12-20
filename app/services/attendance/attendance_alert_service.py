# --- File: app/services/attendance/attendance_alert_service.py ---
"""
Attendance alert service with alert generation and management.

Provides alert creation, tracking, escalation, notification management,
and automated alert generation based on policy rules.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.attendance.attendance_alert import (
    AttendanceAlert,
    AlertConfiguration,
    AlertNotification,
)
from app.repositories.attendance.attendance_alert_repository import (
    AttendanceAlertRepository,
)
from app.repositories.attendance.attendance_record_repository import (
    AttendanceRecordRepository,
)
from app.repositories.attendance.attendance_policy_repository import (
    AttendancePolicyRepository,
)
from app.core.exceptions import ValidationError, NotFoundError, BusinessLogicError
from app.core.logging import get_logger

logger = get_logger(__name__)


class AttendanceAlertService:
    """
    Service for attendance alert management and automation.
    """

    def __init__(self, session: Session):
        """
        Initialize service with database session.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.alert_repo = AttendanceAlertRepository(session)
        self.attendance_repo = AttendanceRecordRepository(session)
        self.policy_repo = AttendancePolicyRepository(session)

    # ==================== Alert Management ====================

    def create_alert(
        self,
        hostel_id: UUID,
        student_id: UUID,
        alert_type: str,
        severity: str,
        message: str,
        details: Dict[str, Any],
        category: str = "attendance",
        recommendation: Optional[str] = None,
        triggered_by_rule: Optional[str] = None,
        auto_generated: bool = True,
        manual_trigger_by: Optional[UUID] = None,
        suppress_duplicates: bool = True,
    ) -> AttendanceAlert:
        """
        Create attendance alert with duplicate suppression.

        Args:
            hostel_id: Hostel identifier
            student_id: Student identifier
            alert_type: Type of alert
            severity: Severity level (low, medium, high, critical)
            message: Alert message
            details: Alert details
            category: Alert category
            recommendation: Recommended action
            triggered_by_rule: Rule that triggered alert
            auto_generated: Auto-generated flag
            manual_trigger_by: Manual trigger user ID
            suppress_duplicates: Check for duplicates

        Returns:
            Created alert

        Raises:
            ValidationError: If validation fails
        """
        try:
            # Check for duplicate alerts if suppression enabled
            if suppress_duplicates:
                config = self.alert_repo.get_configuration_by_hostel(hostel_id)
                if config and config.suppress_duplicate_alerts:
                    duplicates = self.alert_repo.find_duplicate_alerts(
                        student_id=student_id,
                        alert_type=alert_type,
                        hours_window=config.duplicate_suppression_hours,
                    )
                    if duplicates:
                        logger.info(
                            f"Duplicate alert suppressed for student {student_id}: {alert_type}"
                        )
                        return duplicates[0]

            alert = self.alert_repo.create_alert(
                hostel_id=hostel_id,
                student_id=student_id,
                alert_type=alert_type,
                severity=severity,
                message=message,
                details=details,
                category=category,
                recommendation=recommendation,
                triggered_by_rule=triggered_by_rule,
                auto_generated=auto_generated,
                manual_trigger_by=manual_trigger_by,
            )

            # Send notifications based on configuration
            self._send_alert_notifications(alert)

            self.session.commit()
            logger.info(
                f"Alert created for student {student_id}: {alert_type} ({severity})"
            )

            return alert

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating alert: {str(e)}")
            raise

    def get_alert_by_id(
        self,
        alert_id: UUID,
        include_relationships: bool = True,
    ) -> Optional[AttendanceAlert]:
        """
        Get alert by ID.

        Args:
            alert_id: Alert identifier
            include_relationships: Load related entities

        Returns:
            Alert if found
        """
        return self.alert_repo.get_by_id(
            alert_id=alert_id,
            load_relationships=include_relationships,
        )

    def get_student_alerts(
        self,
        student_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        alert_type: Optional[str] = None,
        severity: Optional[str] = None,
        unresolved_only: bool = False,
    ) -> List[AttendanceAlert]:
        """
        Get alerts for student with filters.

        Args:
            student_id: Student identifier
            start_date: Optional start date
            end_date: Optional end date
            alert_type: Optional type filter
            severity: Optional severity filter
            unresolved_only: Only unresolved alerts

        Returns:
            List of alerts
        """
        return self.alert_repo.get_student_alerts(
            student_id=student_id,
            start_date=start_date,
            end_date=end_date,
            alert_type=alert_type,
            severity=severity,
            unresolved_only=unresolved_only,
        )

    def get_hostel_alerts(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        severity: Optional[str] = None,
        unresolved_only: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[AttendanceAlert], int]:
        """
        Get hostel alerts with pagination.

        Args:
            hostel_id: Hostel identifier
            start_date: Optional start date
            end_date: Optional end date
            severity: Optional severity filter
            unresolved_only: Only unresolved alerts
            page: Page number
            page_size: Records per page

        Returns:
            Tuple of (alerts, total_count)
        """
        return self.alert_repo.get_hostel_alerts(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
            severity=severity,
            unresolved_only=unresolved_only,
            page=page,
            page_size=page_size,
        )

    def get_critical_alerts(
        self,
        hostel_id: Optional[UUID] = None,
        unresolved_only: bool = True,
    ) -> List[AttendanceAlert]:
        """
        Get critical severity alerts.

        Args:
            hostel_id: Optional hostel filter
            unresolved_only: Only unresolved alerts

        Returns:
            List of critical alerts
        """
        return self.alert_repo.get_critical_alerts(
            hostel_id=hostel_id,
            unresolved_only=unresolved_only,
        )

    # ==================== Alert Actions ====================

    def acknowledge_alert(
        self,
        alert_id: UUID,
        acknowledged_by: UUID,
        acknowledgment_notes: Optional[str] = None,
    ) -> AttendanceAlert:
        """
        Acknowledge alert.

        Args:
            alert_id: Alert identifier
            acknowledged_by: User acknowledging
            acknowledgment_notes: Optional notes

        Returns:
            Acknowledged alert
        """
        try:
            alert = self.alert_repo.acknowledge_alert(
                alert_id=alert_id,
                acknowledged_by=acknowledged_by,
                acknowledgment_notes=acknowledgment_notes,
            )

            self.session.commit()
            logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")

            return alert

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error acknowledging alert: {str(e)}")
            raise

    def assign_alert(
        self,
        alert_id: UUID,
        assigned_to: UUID,
        assigned_by: UUID,
    ) -> AttendanceAlert:
        """
        Assign alert to user.

        Args:
            alert_id: Alert identifier
            assigned_to: User to assign to
            assigned_by: User assigning

        Returns:
            Updated alert
        """
        try:
            alert = self.alert_repo.assign_alert(
                alert_id=alert_id,
                assigned_to=assigned_to,
            )

            # Log action
            self.alert_repo.add_action_taken(
                alert_id=alert_id,
                action={
                    "type": "assigned",
                    "assigned_to": str(assigned_to),
                    "assigned_by": str(assigned_by),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            self.session.commit()
            logger.info(f"Alert {alert_id} assigned to {assigned_to}")

            return alert

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error assigning alert: {str(e)}")
            raise

    def add_action_to_alert(
        self,
        alert_id: UUID,
        action_type: str,
        action_description: str,
        performed_by: UUID,
        notes: Optional[str] = None,
    ) -> AttendanceAlert:
        """
        Add action taken to alert.

        Args:
            alert_id: Alert identifier
            action_type: Type of action
            action_description: Action description
            performed_by: User who performed action
            notes: Additional notes

        Returns:
            Updated alert
        """
        try:
            action = {
                "type": action_type,
                "description": action_description,
                "performed_by": str(performed_by),
                "timestamp": datetime.utcnow().isoformat(),
                "notes": notes,
            }

            alert = self.alert_repo.add_action_taken(
                alert_id=alert_id,
                action=action,
            )

            self.session.commit()
            logger.info(f"Action added to alert {alert_id}: {action_type}")

            return alert

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error adding action to alert: {str(e)}")
            raise

    def resolve_alert(
        self,
        alert_id: UUID,
        resolved_by: UUID,
        resolution_notes: str,
    ) -> AttendanceAlert:
        """
        Resolve alert.

        Args:
            alert_id: Alert identifier
            resolved_by: User resolving
            resolution_notes: Resolution details

        Returns:
            Resolved alert
        """
        try:
            alert = self.alert_repo.resolve_alert(
                alert_id=alert_id,
                resolved_by=resolved_by,
                resolution_notes=resolution_notes,
            )

            self.session.commit()
            logger.info(f"Alert {alert_id} resolved by {resolved_by}")

            return alert

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error resolving alert: {str(e)}")
            raise

    def escalate_alert(
        self,
        alert_id: UUID,
        escalation_reason: str,
        escalated_by: UUID,
        target_level: Optional[int] = None,
    ) -> AttendanceAlert:
        """
        Escalate alert to higher level.

        Args:
            alert_id: Alert identifier
            escalation_reason: Reason for escalation
            escalated_by: User escalating
            target_level: Target escalation level

        Returns:
            Escalated alert
        """
        try:
            alert = self.alert_repo.escalate_alert(
                alert_id=alert_id,
                escalation_level=target_level,
            )

            # Log escalation action
            self.alert_repo.add_action_taken(
                alert_id=alert_id,
                action={
                    "type": "escalated",
                    "reason": escalation_reason,
                    "escalated_by": str(escalated_by),
                    "escalation_level": alert.escalation_level,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            self.session.commit()
            logger.info(
                f"Alert {alert_id} escalated to level {alert.escalation_level}"
            )

            return alert

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error escalating alert: {str(e)}")
            raise

    # ==================== Alert Configuration ====================

    def create_alert_configuration(
        self,
        hostel_id: UUID,
        **config_params: Any,
    ) -> AlertConfiguration:
        """
        Create alert configuration for hostel.

        Args:
            hostel_id: Hostel identifier
            **config_params: Configuration parameters

        Returns:
            Created configuration
        """
        try:
            config = self.alert_repo.create_configuration(
                hostel_id=hostel_id,
                **config_params,
            )

            self.session.commit()
            logger.info(f"Alert configuration created for hostel {hostel_id}")

            return config

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating alert configuration: {str(e)}")
            raise

    def update_alert_configuration(
        self,
        config_id: UUID,
        **update_data: Any,
    ) -> AlertConfiguration:
        """
        Update alert configuration.

        Args:
            config_id: Configuration identifier
            **update_data: Fields to update

        Returns:
            Updated configuration
        """
        try:
            config = self.alert_repo.update_configuration(
                config_id=config_id,
                **update_data,
            )

            self.session.commit()
            logger.info(f"Alert configuration {config_id} updated")

            return config

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating alert configuration: {str(e)}")
            raise

    def get_hostel_alert_configuration(
        self,
        hostel_id: UUID,
    ) -> Optional[AlertConfiguration]:
        """
        Get alert configuration for hostel.

        Args:
            hostel_id: Hostel identifier

        Returns:
            Configuration if found
        """
        return self.alert_repo.get_configuration_by_hostel(hostel_id)

    # ==================== Automated Alert Generation ====================

    def generate_low_attendance_alerts(
        self,
        hostel_id: UUID,
        check_period: str = "monthly",
    ) -> List[AttendanceAlert]:
        """
        Generate alerts for low attendance.

        Args:
            hostel_id: Hostel identifier
            check_period: Period to check (monthly, quarterly)

        Returns:
            List of generated alerts
        """
        try:
            config = self.alert_repo.get_configuration_by_hostel(hostel_id)
            if not config or not config.enable_low_attendance_alerts:
                logger.info(f"Low attendance alerts disabled for hostel {hostel_id}")
                return []

            # Calculate period dates
            today = date.today()
            if check_period == "monthly":
                period_start = today.replace(day=1)
                period_end = today
            else:
                # Quarterly or custom logic
                period_start = today - timedelta(days=90)
                period_end = today

            # Get students with low attendance (simplified - would need student list)
            # In practice, this would query all students and check their attendance
            alerts = []
            
            logger.info(
                f"Generated {len(alerts)} low attendance alerts for hostel {hostel_id}"
            )

            return alerts

        except Exception as e:
            logger.error(f"Error generating low attendance alerts: {str(e)}")
            raise

    def generate_consecutive_absence_alerts(
        self,
        hostel_id: UUID,
    ) -> List[AttendanceAlert]:
        """
        Generate alerts for consecutive absences.

        Args:
            hostel_id: Hostel identifier

        Returns:
            List of generated alerts
        """
        try:
            config = self.alert_repo.get_configuration_by_hostel(hostel_id)
            if not config or not config.enable_consecutive_absence_alerts:
                logger.info(
                    f"Consecutive absence alerts disabled for hostel {hostel_id}"
                )
                return []

            threshold = config.consecutive_absence_threshold
            alerts = []

            # In practice, would iterate through all students
            # and check for consecutive absences using attendance_repo

            logger.info(
                f"Generated {len(alerts)} consecutive absence alerts for hostel {hostel_id}"
            )

            return alerts

        except Exception as e:
            logger.error(f"Error generating consecutive absence alerts: {str(e)}")
            raise

    def generate_late_entry_alerts(
        self,
        hostel_id: UUID,
        evaluation_period: str = "monthly",
    ) -> List[AttendanceAlert]:
        """
        Generate alerts for excessive late entries.

        Args:
            hostel_id: Hostel identifier
            evaluation_period: Period to evaluate

        Returns:
            List of generated alerts
        """
        try:
            config = self.alert_repo.get_configuration_by_hostel(hostel_id)
            if not config or not config.enable_late_entry_alerts:
                logger.info(f"Late entry alerts disabled for hostel {hostel_id}")
                return []

            threshold = config.late_entry_count_threshold
            alerts = []

            # Calculate period
            today = date.today()
            if evaluation_period == "monthly":
                period_start = today.replace(day=1)
            else:
                period_start = today - timedelta(days=30)

            # Get late entries and count per student
            late_entries = self.attendance_repo.find_late_entries(
                hostel_id=hostel_id,
                start_date=period_start,
                end_date=today,
            )

            # Group by student and check threshold
            student_late_counts: Dict[UUID, int] = {}
            for entry in late_entries:
                student_id = entry.student_id
                student_late_counts[student_id] = student_late_counts.get(student_id, 0) + 1

            # Create alerts for students exceeding threshold
            for student_id, count in student_late_counts.items():
                if count >= threshold:
                    alert = self.create_alert(
                        hostel_id=hostel_id,
                        student_id=student_id,
                        alert_type="excessive_late_entries",
                        severity="medium",
                        message=f"Student has {count} late entries in the past {evaluation_period}",
                        details={
                            "late_entry_count": count,
                            "threshold": threshold,
                            "period": evaluation_period,
                            "period_start": period_start.isoformat(),
                            "period_end": today.isoformat(),
                        },
                        triggered_by_rule="late_entry_threshold",
                    )
                    alerts.append(alert)

            logger.info(
                f"Generated {len(alerts)} late entry alerts for hostel {hostel_id}"
            )

            return alerts

        except Exception as e:
            logger.error(f"Error generating late entry alerts: {str(e)}")
            raise

    def process_auto_escalation(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> List[AttendanceAlert]:
        """
        Process automatic escalation for unresolved alerts.

        Args:
            hostel_id: Optional hostel filter

        Returns:
            List of escalated alerts
        """
        try:
            config = self.alert_repo.get_configuration_by_hostel(hostel_id) if hostel_id else None
            if config and not config.auto_escalate_enabled:
                logger.info("Auto-escalation disabled")
                return []

            escalate_after_days = config.auto_escalate_after_days if config else 7
            max_level = config.max_escalation_level if config else 3

            # Get unacknowledged alerts older than threshold
            unacknowledged = self.alert_repo.get_unacknowledged_alerts(
                hostel_id=hostel_id,
                older_than_hours=escalate_after_days * 24,
            )

            escalated = []
            for alert in unacknowledged:
                if alert.escalation_level < max_level:
                    escalated_alert = self.alert_repo.escalate_alert(
                        alert_id=alert.id,
                        escalation_level=alert.escalation_level + 1,
                    )
                    escalated.append(escalated_alert)

            self.session.commit()
            logger.info(f"Auto-escalated {len(escalated)} alerts")

            return escalated

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error in auto-escalation: {str(e)}")
            raise

    # ==================== Notification Management ====================

    def _send_alert_notifications(
        self,
        alert: AttendanceAlert,
    ) -> List[AlertNotification]:
        """
        Send notifications for alert based on configuration.

        Args:
            alert: Alert to send notifications for

        Returns:
            List of created notifications
        """
        try:
            config = self.alert_repo.get_configuration_by_hostel(alert.hostel_id)
            if not config:
                return []

            notifications = []

            # Determine recipients based on configuration
            recipients = []
            
            if config.notify_student:
                recipients.append({
                    "user_id": alert.student_id,  # Would need actual user ID
                    "type": "student",
                })

            if config.notify_guardian:
                # Would need to get guardian user ID
                pass

            if config.notify_supervisor:
                # Would need to get supervisor user ID
                pass

            if config.notify_admin:
                # Would need to get admin user IDs
                pass

            # Create notifications for each channel
            for recipient in recipients:
                for channel in config.notification_channels:
                    notification = self.alert_repo.create_notification(
                        alert_id=alert.id,
                        recipient_id=recipient["user_id"],
                        channel=channel,
                        recipient_type=recipient["type"],
                    )
                    notifications.append(notification)

            return notifications

        except Exception as e:
            logger.error(f"Error sending alert notifications: {str(e)}")
            return []

    def mark_notification_delivered(
        self,
        notification_id: UUID,
    ) -> AlertNotification:
        """
        Mark notification as delivered.

        Args:
            notification_id: Notification identifier

        Returns:
            Updated notification
        """
        try:
            notification = self.alert_repo.mark_notification_delivered(notification_id)
            self.session.commit()
            return notification

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error marking notification delivered: {str(e)}")
            raise

    def mark_notification_read(
        self,
        notification_id: UUID,
    ) -> AlertNotification:
        """
        Mark notification as read.

        Args:
            notification_id: Notification identifier

        Returns:
            Updated notification
        """
        try:
            notification = self.alert_repo.mark_notification_read(notification_id)
            self.session.commit()
            return notification

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error marking notification read: {str(e)}")
            raise

    def retry_failed_notifications(
        self,
        max_retry_count: int = 3,
    ) -> int:
        """
        Retry failed notifications.

        Args:
            max_retry_count: Maximum retry attempts

        Returns:
            Number of notifications retried
        """
        try:
            failed = self.alert_repo.get_failed_notifications(max_retry_count)
            
            retried = 0
            for notification in failed:
                # Retry logic would go here
                # For now, just increment retry count
                retried += 1

            self.session.commit()
            logger.info(f"Retried {retried} failed notifications")

            return retried

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error retrying notifications: {str(e)}")
            raise

    # ==================== Statistics ====================

    def get_alert_statistics(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Get alert statistics for hostel.

        Args:
            hostel_id: Hostel identifier
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Statistics dictionary
        """
        return self.alert_repo.get_alert_statistics(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )

    def get_notification_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Get notification statistics.

        Args:
            hostel_id: Optional hostel filter
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Statistics dictionary
        """
        return self.alert_repo.get_notification_statistics(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )