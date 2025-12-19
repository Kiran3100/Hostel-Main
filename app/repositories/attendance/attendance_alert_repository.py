# --- File: app/repositories/attendance/attendance_alert_repository.py ---
"""
Attendance alert repository with comprehensive alert management.

Provides alert creation, tracking, escalation, and notification
management for attendance monitoring.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, case
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.attendance.attendance_alert import (
    AttendanceAlert,
    AlertConfiguration,
    AlertNotification,
)
from app.repositories.base.base_repository import BaseRepository
from app.core.exceptions import ValidationError, NotFoundError, ConflictError


class AttendanceAlertRepository(BaseRepository[AttendanceAlert]):
    """
    Repository for attendance alert operations with comprehensive tracking.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy database session
        """
        super().__init__(AttendanceAlert, session)

    # ==================== Core Alert CRUD Operations ====================

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
    ) -> AttendanceAlert:
        """
        Create new attendance alert.

        Args:
            hostel_id: Hostel identifier
            student_id: Student identifier
            alert_type: Type of alert
            severity: Severity level (low, medium, high, critical)
            message: Alert message
            details: Alert details as JSON
            category: Alert category
            recommendation: Recommended action
            triggered_by_rule: Rule that triggered alert
            auto_generated: Auto-generated flag
            manual_trigger_by: Manual trigger user ID

        Returns:
            Created alert

        Raises:
            ValidationError: If validation fails
        """
        # Validate severity
        valid_severities = ["low", "medium", "high", "critical"]
        if severity not in valid_severities:
            raise ValidationError(f"Invalid severity. Must be one of: {valid_severities}")

        alert = AttendanceAlert(
            hostel_id=hostel_id,
            student_id=student_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            details=details,
            category=category,
            recommendation=recommendation,
            triggered_at=datetime.utcnow(),
            triggered_by_rule=triggered_by_rule,
            auto_generated=auto_generated,
            manual_trigger_by=manual_trigger_by,
        )

        self.session.add(alert)
        self.session.flush()
        return alert

    def get_by_id(
        self,
        alert_id: UUID,
        load_relationships: bool = False,
    ) -> Optional[AttendanceAlert]:
        """
        Get alert by ID.

        Args:
            alert_id: Alert identifier
            load_relationships: Whether to load relationships

        Returns:
            Alert if found
        """
        query = self.session.query(AttendanceAlert).filter(
            AttendanceAlert.id == alert_id
        )

        if load_relationships:
            query = query.options(
                joinedload(AttendanceAlert.hostel),
                joinedload(AttendanceAlert.student),
                selectinload(AttendanceAlert.alert_notifications),
            )

        return query.first()

    def update_alert(
        self,
        alert_id: UUID,
        **update_data: Any,
    ) -> AttendanceAlert:
        """
        Update alert.

        Args:
            alert_id: Alert identifier
            **update_data: Fields to update

        Returns:
            Updated alert

        Raises:
            NotFoundError: If alert not found
        """
        alert = self.get_by_id(alert_id)
        if not alert:
            raise NotFoundError(f"Attendance alert {alert_id} not found")

        for key, value in update_data.items():
            if hasattr(alert, key):
                setattr(alert, key, value)

        self.session.flush()
        return alert

    # ==================== Query Operations ====================

    def get_student_alerts(
        self,
        student_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        alert_type: Optional[str] = None,
        severity: Optional[str] = None,
        acknowledged_only: bool = False,
        unacknowledged_only: bool = False,
        resolved_only: bool = False,
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
            acknowledged_only: Only acknowledged alerts
            unacknowledged_only: Only unacknowledged alerts
            resolved_only: Only resolved alerts
            unresolved_only: Only unresolved alerts

        Returns:
            List of alerts
        """
        query = self.session.query(AttendanceAlert).filter(
            AttendanceAlert.student_id == student_id
        )

        if start_date:
            query = query.filter(AttendanceAlert.triggered_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(AttendanceAlert.triggered_at <= datetime.combine(end_date, datetime.max.time()))
        if alert_type:
            query = query.filter(AttendanceAlert.alert_type == alert_type)
        if severity:
            query = query.filter(AttendanceAlert.severity == severity)
        if acknowledged_only:
            query = query.filter(AttendanceAlert.acknowledged == True)
        if unacknowledged_only:
            query = query.filter(AttendanceAlert.acknowledged == False)
        if resolved_only:
            query = query.filter(AttendanceAlert.resolved == True)
        if unresolved_only:
            query = query.filter(AttendanceAlert.resolved == False)

        return query.order_by(AttendanceAlert.triggered_at.desc()).all()

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
        query = self.session.query(AttendanceAlert).filter(
            AttendanceAlert.hostel_id == hostel_id
        )

        if start_date:
            query = query.filter(AttendanceAlert.triggered_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(AttendanceAlert.triggered_at <= datetime.combine(end_date, datetime.max.time()))
        if severity:
            query = query.filter(AttendanceAlert.severity == severity)
        if unresolved_only:
            query = query.filter(AttendanceAlert.resolved == False)

        total_count = query.count()

        alerts = query.order_by(
            AttendanceAlert.triggered_at.desc()
        ).limit(page_size).offset((page - 1) * page_size).all()

        return alerts, total_count

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
        query = self.session.query(AttendanceAlert).filter(
            AttendanceAlert.severity == "critical"
        )

        if hostel_id:
            query = query.filter(AttendanceAlert.hostel_id == hostel_id)
        if unresolved_only:
            query = query.filter(AttendanceAlert.resolved == False)

        return query.order_by(AttendanceAlert.triggered_at.desc()).all()

    def get_escalated_alerts(
        self,
        hostel_id: Optional[UUID] = None,
        min_escalation_level: int = 1,
    ) -> List[AttendanceAlert]:
        """
        Get escalated alerts.

        Args:
            hostel_id: Optional hostel filter
            min_escalation_level: Minimum escalation level

        Returns:
            List of escalated alerts
        """
        query = self.session.query(AttendanceAlert).filter(
            and_(
                AttendanceAlert.escalated == True,
                AttendanceAlert.escalation_level >= min_escalation_level,
            )
        )

        if hostel_id:
            query = query.filter(AttendanceAlert.hostel_id == hostel_id)

        return query.order_by(
            AttendanceAlert.escalation_level.desc(),
            AttendanceAlert.escalated_at.desc(),
        ).all()

    def get_unacknowledged_alerts(
        self,
        hostel_id: UUID,
        severity: Optional[str] = None,
        older_than_hours: Optional[int] = None,
    ) -> List[AttendanceAlert]:
        """
        Get unacknowledged alerts.

        Args:
            hostel_id: Hostel identifier
            severity: Optional severity filter
            older_than_hours: Optional age filter in hours

        Returns:
            List of unacknowledged alerts
        """
        query = self.session.query(AttendanceAlert).filter(
            and_(
                AttendanceAlert.hostel_id == hostel_id,
                AttendanceAlert.acknowledged == False,
            )
        )

        if severity:
            query = query.filter(AttendanceAlert.severity == severity)

        if older_than_hours:
            cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
            query = query.filter(AttendanceAlert.triggered_at <= cutoff_time)

        return query.order_by(AttendanceAlert.triggered_at.asc()).all()

    def find_duplicate_alerts(
        self,
        student_id: UUID,
        alert_type: str,
        hours_window: int = 24,
    ) -> List[AttendanceAlert]:
        """
        Find duplicate alerts within time window.

        Args:
            student_id: Student identifier
            alert_type: Alert type
            hours_window: Time window in hours

        Returns:
            List of duplicate alerts
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_window)

        return self.session.query(AttendanceAlert).filter(
            and_(
                AttendanceAlert.student_id == student_id,
                AttendanceAlert.alert_type == alert_type,
                AttendanceAlert.triggered_at >= cutoff_time,
            )
        ).order_by(AttendanceAlert.triggered_at.desc()).all()

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

        Raises:
            NotFoundError: If alert not found
        """
        alert = self.get_by_id(alert_id)
        if not alert:
            raise NotFoundError(f"Attendance alert {alert_id} not found")

        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledgment_notes = acknowledgment_notes

        self.session.flush()
        return alert

    def assign_alert(
        self,
        alert_id: UUID,
        assigned_to: UUID,
    ) -> AttendanceAlert:
        """
        Assign alert to user.

        Args:
            alert_id: Alert identifier
            assigned_to: User to assign to

        Returns:
            Updated alert

        Raises:
            NotFoundError: If alert not found
        """
        alert = self.get_by_id(alert_id)
        if not alert:
            raise NotFoundError(f"Attendance alert {alert_id} not found")

        alert.assigned_to = assigned_to

        self.session.flush()
        return alert

    def add_action_taken(
        self,
        alert_id: UUID,
        action: Dict[str, Any],
    ) -> AttendanceAlert:
        """
        Add action taken to alert.

        Args:
            alert_id: Alert identifier
            action: Action details (timestamp, user, action, notes)

        Returns:
            Updated alert

        Raises:
            NotFoundError: If alert not found
        """
        alert = self.get_by_id(alert_id)
        if not alert:
            raise NotFoundError(f"Attendance alert {alert_id} not found")

        # Add timestamp if not present
        if 'timestamp' not in action:
            action['timestamp'] = datetime.utcnow().isoformat()

        alert.actions_taken.append(action)
        self.session.flush()
        return alert

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

        Raises:
            NotFoundError: If alert not found
        """
        alert = self.get_by_id(alert_id)
        if not alert:
            raise NotFoundError(f"Attendance alert {alert_id} not found")

        alert.resolved = True
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = resolved_by
        alert.resolution_notes = resolution_notes

        self.session.flush()
        return alert

    def escalate_alert(
        self,
        alert_id: UUID,
        escalation_level: Optional[int] = None,
    ) -> AttendanceAlert:
        """
        Escalate alert to higher level.

        Args:
            alert_id: Alert identifier
            escalation_level: Optional specific level (increments by 1 if not provided)

        Returns:
            Escalated alert

        Raises:
            NotFoundError: If alert not found
            ValidationError: If max escalation reached
        """
        alert = self.get_by_id(alert_id)
        if not alert:
            raise NotFoundError(f"Attendance alert {alert_id} not found")

        if escalation_level is not None:
            if escalation_level > 5:
                raise ValidationError("Maximum escalation level is 5")
            alert.escalation_level = escalation_level
        else:
            if alert.escalation_level >= 5:
                raise ValidationError("Alert already at maximum escalation level")
            alert.escalation_level += 1

        alert.escalated = True
        alert.escalated_at = datetime.utcnow()

        self.session.flush()
        return alert

    # ==================== Alert Configuration ====================

    def create_configuration(
        self,
        hostel_id: UUID,
        enable_low_attendance_alerts: bool = True,
        low_attendance_threshold: int = 75,
        low_attendance_check_period: str = "monthly",
        enable_consecutive_absence_alerts: bool = True,
        consecutive_absence_threshold: int = 3,
        enable_late_entry_alerts: bool = True,
        late_entry_count_threshold: int = 5,
        late_entry_evaluation_period: str = "monthly",
        enable_pattern_detection: bool = False,
        pattern_sensitivity: str = "medium",
        enable_absence_spike_alerts: bool = True,
        absence_spike_threshold: int = 3,
        notify_supervisor: bool = True,
        notify_admin: bool = True,
        notify_guardian: bool = True,
        notify_student: bool = True,
        notification_channels: Optional[List[str]] = None,
        auto_escalate_enabled: bool = True,
        auto_escalate_after_days: int = 7,
        max_escalation_level: int = 3,
        suppress_duplicate_alerts: bool = True,
        duplicate_suppression_hours: int = 24,
    ) -> AlertConfiguration:
        """
        Create alert configuration for hostel.

        Args:
            hostel_id: Hostel identifier
            (other parameters match model fields)

        Returns:
            Created configuration

        Raises:
            ConflictError: If configuration already exists
        """
        # Check for existing configuration
        existing = self.get_configuration_by_hostel(hostel_id)
        if existing:
            raise ConflictError(
                f"Alert configuration already exists for hostel {hostel_id}"
            )

        if notification_channels is None:
            notification_channels = ["email", "push"]

        config = AlertConfiguration(
            hostel_id=hostel_id,
            enable_low_attendance_alerts=enable_low_attendance_alerts,
            low_attendance_threshold=low_attendance_threshold,
            low_attendance_check_period=low_attendance_check_period,
            enable_consecutive_absence_alerts=enable_consecutive_absence_alerts,
            consecutive_absence_threshold=consecutive_absence_threshold,
            enable_late_entry_alerts=enable_late_entry_alerts,
            late_entry_count_threshold=late_entry_count_threshold,
            late_entry_evaluation_period=late_entry_evaluation_period,
            enable_pattern_detection=enable_pattern_detection,
            pattern_sensitivity=pattern_sensitivity,
            enable_absence_spike_alerts=enable_absence_spike_alerts,
            absence_spike_threshold=absence_spike_threshold,
            notify_supervisor=notify_supervisor,
            notify_admin=notify_admin,
            notify_guardian=notify_guardian,
            notify_student=notify_student,
            notification_channels=notification_channels,
            auto_escalate_enabled=auto_escalate_enabled,
            auto_escalate_after_days=auto_escalate_after_days,
            max_escalation_level=max_escalation_level,
            suppress_duplicate_alerts=suppress_duplicate_alerts,
            duplicate_suppression_hours=duplicate_suppression_hours,
        )

        self.session.add(config)
        self.session.flush()
        return config

    def get_configuration_by_hostel(
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
        return self.session.query(AlertConfiguration).filter(
            AlertConfiguration.hostel_id == hostel_id
        ).first()

    def update_configuration(
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

        Raises:
            NotFoundError: If configuration not found
        """
        config = self.session.query(AlertConfiguration).filter(
            AlertConfiguration.id == config_id
        ).first()

        if not config:
            raise NotFoundError(f"Alert configuration {config_id} not found")

        for key, value in update_data.items():
            if hasattr(config, key):
                setattr(config, key, value)

        self.session.flush()
        return config

    # ==================== Notification Management ====================

    def create_notification(
        self,
        alert_id: UUID,
        recipient_id: UUID,
        channel: str,
        recipient_type: str,
    ) -> AlertNotification:
        """
        Create notification record.

        Args:
            alert_id: Alert identifier
            recipient_id: Recipient user ID
            channel: Notification channel (email, sms, push, etc.)
            recipient_type: Type of recipient (student, guardian, admin, supervisor)

        Returns:
            Created notification

        Raises:
            ValidationError: If validation fails
        """
        valid_channels = ["email", "sms", "push", "in_app"]
        if channel not in valid_channels:
            raise ValidationError(f"Invalid channel. Must be one of: {valid_channels}")

        valid_types = ["student", "guardian", "admin", "supervisor"]
        if recipient_type not in valid_types:
            raise ValidationError(f"Invalid recipient type. Must be one of: {valid_types}")

        notification = AlertNotification(
            alert_id=alert_id,
            recipient_id=recipient_id,
            channel=channel,
            recipient_type=recipient_type,
            sent_at=datetime.utcnow(),
        )

        self.session.add(notification)
        self.session.flush()
        return notification

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

        Raises:
            NotFoundError: If notification not found
        """
        notification = self.session.query(AlertNotification).filter(
            AlertNotification.id == notification_id
        ).first()

        if not notification:
            raise NotFoundError(f"Alert notification {notification_id} not found")

        notification.delivered = True
        notification.delivered_at = datetime.utcnow()

        self.session.flush()
        return notification

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

        Raises:
            NotFoundError: If notification not found
        """
        notification = self.session.query(AlertNotification).filter(
            AlertNotification.id == notification_id
        ).first()

        if not notification:
            raise NotFoundError(f"Alert notification {notification_id} not found")

        notification.read = True
        notification.read_at = datetime.utcnow()

        self.session.flush()
        return notification

    def mark_notification_failed(
        self,
        notification_id: UUID,
        failure_reason: str,
    ) -> AlertNotification:
        """
        Mark notification as failed.

        Args:
            notification_id: Notification identifier
            failure_reason: Reason for failure

        Returns:
            Updated notification

        Raises:
            NotFoundError: If notification not found
        """
        notification = self.session.query(AlertNotification).filter(
            AlertNotification.id == notification_id
        ).first()

        if not notification:
            raise NotFoundError(f"Alert notification {notification_id} not found")

        notification.failed = True
        notification.failure_reason = failure_reason
        notification.retry_count += 1

        self.session.flush()
        return notification

    def get_alert_notifications(
        self,
        alert_id: UUID,
    ) -> List[AlertNotification]:
        """
        Get all notifications for alert.

        Args:
            alert_id: Alert identifier

        Returns:
            List of notifications
        """
        return self.session.query(AlertNotification).filter(
            AlertNotification.alert_id == alert_id
        ).order_by(AlertNotification.sent_at.desc()).all()

    def get_failed_notifications(
        self,
        max_retry_count: int = 3,
    ) -> List[AlertNotification]:
        """
        Get failed notifications eligible for retry.

        Args:
            max_retry_count: Maximum retry attempts

        Returns:
            List of failed notifications
        """
        return self.session.query(AlertNotification).filter(
            and_(
                AlertNotification.failed == True,
                AlertNotification.retry_count < max_retry_count,
            )
        ).order_by(AlertNotification.sent_at.asc()).all()

    # ==================== Statistics and Analytics ====================

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
            Dictionary with statistics
        """
        query = self.session.query(AttendanceAlert).filter(
            AttendanceAlert.hostel_id == hostel_id
        )

        if start_date:
            query = query.filter(AttendanceAlert.triggered_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(AttendanceAlert.triggered_at <= datetime.combine(end_date, datetime.max.time()))

        total_alerts = query.count()
        acknowledged_alerts = query.filter(AttendanceAlert.acknowledged == True).count()
        resolved_alerts = query.filter(AttendanceAlert.resolved == True).count()
        escalated_alerts = query.filter(AttendanceAlert.escalated == True).count()

        # Count by severity
        severity_counts = dict(
            self.session.query(
                AttendanceAlert.severity,
                func.count(AttendanceAlert.id),
            ).filter(
                AttendanceAlert.hostel_id == hostel_id
            ).group_by(AttendanceAlert.severity).all()
        )

        # Count by type
        type_counts = dict(
            self.session.query(
                AttendanceAlert.alert_type,
                func.count(AttendanceAlert.id),
            ).filter(
                AttendanceAlert.hostel_id == hostel_id
            ).group_by(AttendanceAlert.alert_type).all()
        )

        # Calculate average resolution time
        resolved_with_times = query.filter(
            and_(
                AttendanceAlert.resolved == True,
                AttendanceAlert.resolved_at.isnot(None),
            )
        ).all()

        avg_resolution_hours = 0
        if resolved_with_times:
            total_seconds = sum(
                (alert.resolved_at - alert.triggered_at).total_seconds()
                for alert in resolved_with_times
            )
            avg_resolution_hours = round(total_seconds / len(resolved_with_times) / 3600, 2)

        return {
            "total_alerts": total_alerts,
            "acknowledged_alerts": acknowledged_alerts,
            "resolved_alerts": resolved_alerts,
            "escalated_alerts": escalated_alerts,
            "unresolved_alerts": total_alerts - resolved_alerts,
            "acknowledgment_rate": round(
                (acknowledged_alerts / total_alerts * 100) if total_alerts > 0 else 0,
                2,
            ),
            "resolution_rate": round(
                (resolved_alerts / total_alerts * 100) if total_alerts > 0 else 0,
                2,
            ),
            "average_resolution_hours": avg_resolution_hours,
            "by_severity": severity_counts,
            "by_type": type_counts,
        }

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
            Dictionary with statistics
        """
        query = self.session.query(AlertNotification)

        if hostel_id:
            query = query.join(AttendanceAlert).filter(
                AttendanceAlert.hostel_id == hostel_id
            )

        if start_date:
            query = query.filter(AlertNotification.sent_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(AlertNotification.sent_at <= datetime.combine(end_date, datetime.max.time()))

        total_notifications = query.count()
        delivered_notifications = query.filter(AlertNotification.delivered == True).count()
        read_notifications = query.filter(AlertNotification.read == True).count()
        failed_notifications = query.filter(AlertNotification.failed == True).count()

        # Count by channel
        channel_counts = dict(
            query.with_entities(
                AlertNotification.channel,
                func.count(AlertNotification.id),
            ).group_by(AlertNotification.channel).all()
        )

        return {
            "total_notifications": total_notifications,
            "delivered_notifications": delivered_notifications,
            "read_notifications": read_notifications,
            "failed_notifications": failed_notifications,
            "delivery_rate": round(
                (delivered_notifications / total_notifications * 100) if total_notifications > 0 else 0,
                2,
            ),
            "read_rate": round(
                (read_notifications / delivered_notifications * 100) if delivered_notifications > 0 else 0,
                2,
            ),
            "failure_rate": round(
                (failed_notifications / total_notifications * 100) if total_notifications > 0 else 0,
                2,
            ),
            "by_channel": channel_counts,
        }