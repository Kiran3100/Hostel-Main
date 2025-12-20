"""
Student communication service.

Notification orchestration, bulk messaging, and communication tracking
for students, guardians, and related parties.
"""

from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.student.student_repository import StudentRepository
from app.repositories.student.student_preferences_repository import StudentPreferencesRepository
from app.repositories.student.guardian_contact_repository import GuardianContactRepository
from app.models.student.student import Student
from app.models.student.student_preferences import StudentPreferences
from app.models.student.guardian_contact import GuardianContact
from app.core.exceptions import ValidationError


class StudentCommunicationService:
    """
    Student communication service for notification management.
    
    Handles:
        - Individual notifications
        - Bulk messaging
        - Multi-channel delivery
        - Guardian communications
        - Communication tracking
        - Preference-based filtering
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.student_repo = StudentRepository(db)
        self.preferences_repo = StudentPreferencesRepository(db)
        self.guardian_repo = GuardianContactRepository(db)

    # ============================================================================
    # SINGLE STUDENT NOTIFICATIONS
    # ============================================================================

    def send_notification(
        self,
        student_id: str,
        notification_type: str,
        subject: str,
        message: str,
        channels: Optional[list[str]] = None,
        priority: str = 'normal'
    ) -> dict[str, Any]:
        """
        Send notification to a student.
        
        Args:
            student_id: Student UUID
            notification_type: Type of notification
            subject: Notification subject
            message: Notification message
            channels: Specific channels to use (overrides preferences)
            priority: Priority level (low, normal, high, urgent)
            
        Returns:
            Notification delivery status
        """
        try:
            student = self.student_repo.find_by_id(student_id)
            if not student:
                raise ValidationError(f"Student {student_id} not found")
            
            # Get student preferences
            preferences = self.preferences_repo.find_by_student_id(student_id)
            
            # Determine delivery channels
            delivery_channels = self._determine_channels(
                notification_type,
                preferences,
                channels
            )
            
            # Check if notification should be sent (quiet hours, digest mode)
            if not self._should_send_now(preferences, priority):
                return {
                    'student_id': student_id,
                    'queued': True,
                    'reason': 'quiet_hours_or_digest_mode',
                    'channels': delivery_channels
                }
            
            # Send notifications (in real implementation, this would call actual services)
            results = {
                'student_id': student_id,
                'notification_type': notification_type,
                'subject': subject,
                'priority': priority,
                'sent': True,
                'channels': {}
            }
            
            for channel in delivery_channels:
                # Simulate sending
                results['channels'][channel] = {
                    'sent': True,
                    'timestamp': 'now',
                    'status': 'delivered'
                }
            
            return results
            
        except Exception as e:
            raise ValidationError(f"Notification failed: {str(e)}")

    def _determine_channels(
        self,
        notification_type: str,
        preferences: Optional[StudentPreferences],
        override_channels: Optional[list[str]] = None
    ) -> list[str]:
        """
        Determine which channels to use for notification.
        
        Args:
            notification_type: Type of notification
            preferences: Student preferences
            override_channels: Override channels
            
        Returns:
            List of channels to use
        """
        if override_channels:
            return override_channels
        
        if not preferences:
            return ['email']  # Default channel
        
        channels = []
        
        # Check notification type preferences
        type_enabled = self._is_notification_type_enabled(
            notification_type,
            preferences
        )
        
        if not type_enabled:
            return []  # Student has disabled this notification type
        
        # Check channel preferences
        if preferences.email_notifications:
            channels.append('email')
        
        if preferences.sms_notifications:
            channels.append('sms')
        
        if preferences.push_notifications:
            channels.append('push')
        
        if preferences.whatsapp_notifications:
            channels.append('whatsapp')
        
        return channels if channels else ['email']  # Fallback to email

    def _is_notification_type_enabled(
        self,
        notification_type: str,
        preferences: StudentPreferences
    ) -> bool:
        """Check if notification type is enabled."""
        type_mapping = {
            'payment': preferences.payment_reminders,
            'attendance': preferences.attendance_alerts,
            'announcement': preferences.announcement_notifications,
            'complaint': preferences.complaint_updates,
            'event': preferences.event_notifications,
            'maintenance': preferences.maintenance_notifications,
            'mess': preferences.mess_menu_updates,
            'promotional': preferences.promotional_notifications
        }
        
        return type_mapping.get(notification_type, True)

    def _should_send_now(
        self,
        preferences: Optional[StudentPreferences],
        priority: str
    ) -> bool:
        """
        Check if notification should be sent immediately.
        
        Args:
            preferences: Student preferences
            priority: Notification priority
            
        Returns:
            True if should send now
        """
        if not preferences:
            return True
        
        # Always send urgent notifications
        if priority == 'urgent':
            return True
        
        # Check digest mode
        if preferences.digest_mode:
            return False
        
        # Check quiet hours
        if preferences.quiet_hours_enabled:
            # In real implementation, check current time against quiet hours
            # For now, return True
            pass
        
        return True

    # ============================================================================
    # GUARDIAN NOTIFICATIONS
    # ============================================================================

    def notify_guardian(
        self,
        guardian_id: str,
        notification_type: str,
        subject: str,
        message: str,
        channels: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """
        Send notification to a guardian.
        
        Args:
            guardian_id: Guardian contact UUID
            notification_type: Type of notification
            subject: Notification subject
            message: Notification message
            channels: Specific channels to use
            
        Returns:
            Notification delivery status
        """
        try:
            guardian = self.guardian_repo.find_by_id(guardian_id)
            if not guardian:
                raise ValidationError(f"Guardian {guardian_id} not found")
            
            # Check if guardian should receive this type of notification
            if not self._should_notify_guardian(guardian, notification_type):
                return {
                    'guardian_id': guardian_id,
                    'sent': False,
                    'reason': 'notification_type_disabled'
                }
            
            # Determine channels
            delivery_channels = channels or self._get_guardian_channels(guardian)
            
            results = {
                'guardian_id': guardian_id,
                'notification_type': notification_type,
                'subject': subject,
                'sent': True,
                'channels': {}
            }
            
            for channel in delivery_channels:
                results['channels'][channel] = {
                    'sent': True,
                    'timestamp': 'now',
                    'status': 'delivered'
                }
            
            return results
            
        except Exception as e:
            raise ValidationError(f"Guardian notification failed: {str(e)}")

    def notify_all_guardians(
        self,
        student_id: str,
        notification_type: str,
        subject: str,
        message: str
    ) -> list[dict[str, Any]]:
        """
        Send notification to all guardians of a student.
        
        Args:
            student_id: Student UUID
            notification_type: Type of notification
            subject: Notification subject
            message: Notification message
            
        Returns:
            List of notification results
        """
        guardians = self.guardian_repo.find_by_student_id(student_id)
        
        results = []
        for guardian in guardians:
            result = self.notify_guardian(
                guardian.id,
                notification_type,
                subject,
                message
            )
            results.append(result)
        
        return results

    def _should_notify_guardian(
        self,
        guardian: GuardianContact,
        notification_type: str
    ) -> bool:
        """Check if guardian should receive notification type."""
        if not guardian.authorized_to_receive_updates:
            return False
        
        type_mapping = {
            'payment': guardian.send_payment_reminders,
            'attendance': guardian.send_attendance_alerts,
            'monthly_report': guardian.send_monthly_reports
        }
        
        return type_mapping.get(notification_type, True)

    def _get_guardian_channels(
        self,
        guardian: GuardianContact
    ) -> list[str]:
        """Get notification channels for guardian."""
        channels = []
        
        if guardian.email and guardian.email_verified:
            channels.append('email')
        
        if guardian.phone and guardian.phone_verified:
            channels.append('sms')
        
        if guardian.whatsapp_number:
            channels.append('whatsapp')
        
        return channels if channels else ['email']

    # ============================================================================
    # BULK NOTIFICATIONS
    # ============================================================================

    def send_bulk_notification(
        self,
        student_ids: list[str],
        notification_type: str,
        subject: str,
        message: str,
        channels: Optional[list[str]] = None,
        include_guardians: bool = False
    ) -> dict[str, Any]:
        """
        Send notification to multiple students.
        
        Args:
            student_ids: List of student UUIDs
            notification_type: Type of notification
            subject: Notification subject
            message: Notification message
            channels: Specific channels to use
            include_guardians: Also notify guardians
            
        Returns:
            Bulk notification results
        """
        results = {
            'total': len(student_ids),
            'successful': 0,
            'failed': 0,
            'guardian_notified': 0,
            'details': []
        }
        
        for student_id in student_ids:
            try:
                # Notify student
                student_result = self.send_notification(
                    student_id,
                    notification_type,
                    subject,
                    message,
                    channels
                )
                
                if student_result.get('sent') or student_result.get('queued'):
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                
                # Notify guardians if requested
                if include_guardians:
                    guardian_results = self.notify_all_guardians(
                        student_id,
                        notification_type,
                        subject,
                        message
                    )
                    results['guardian_notified'] += len(guardian_results)
                
                results['details'].append({
                    'student_id': student_id,
                    'status': 'success',
                    'result': student_result
                })
                
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'student_id': student_id,
                    'status': 'failed',
                    'error': str(e)
                })
        
        return results

    def send_hostel_announcement(
        self,
        hostel_id: str,
        subject: str,
        message: str,
        channels: Optional[list[str]] = None,
        include_guardians: bool = False,
        student_status_filter: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """
        Send announcement to all students in a hostel.
        
        Args:
            hostel_id: Hostel UUID
            subject: Announcement subject
            message: Announcement message
            channels: Specific channels to use
            include_guardians: Also notify guardians
            student_status_filter: Filter by student status
            
        Returns:
            Announcement delivery results
        """
        # Get all students in hostel
        students = self.student_repo.find_by_hostel(hostel_id)
        
        # Filter by status if specified
        if student_status_filter:
            students = [
                s for s in students
                if s.student_status.value in student_status_filter
            ]
        
        student_ids = [s.id for s in students]
        
        return self.send_bulk_notification(
            student_ids,
            'announcement',
            subject,
            message,
            channels,
            include_guardians
        )

    # ============================================================================
    # EMERGENCY NOTIFICATIONS
    # ============================================================================

    def send_emergency_notification(
        self,
        student_id: str,
        subject: str,
        message: str,
        notify_guardians: bool = True,
        notify_emergency_contacts: bool = True
    ) -> dict[str, Any]:
        """
        Send emergency notification with highest priority.
        
        Args:
            student_id: Student UUID
            subject: Notification subject
            message: Notification message
            notify_guardians: Notify all guardians
            notify_emergency_contacts: Notify emergency contacts
            
        Returns:
            Emergency notification results
        """
        results = {
            'student_id': student_id,
            'student_notified': False,
            'guardians_notified': [],
            'emergency_contacts_notified': []
        }
        
        # Notify student (all available channels)
        student_result = self.send_notification(
            student_id,
            'emergency',
            subject,
            message,
            channels=['email', 'sms', 'push', 'whatsapp'],
            priority='urgent'
        )
        results['student_notified'] = student_result.get('sent', False)
        
        # Notify all guardians
        if notify_guardians:
            guardian_results = self.notify_all_guardians(
                student_id,
                'emergency',
                subject,
                message
            )
            results['guardians_notified'] = guardian_results
        
        # Notify emergency contacts
        if notify_emergency_contacts:
            emergency_contacts = self.guardian_repo.get_emergency_contacts(student_id)
            
            for contact in emergency_contacts:
                contact_result = self.notify_guardian(
                    contact.id,
                    'emergency',
                    subject,
                    message,
                    channels=['sms', 'phone', 'whatsapp']  # Prefer direct channels
                )
                results['emergency_contacts_notified'].append(contact_result)
        
        return results

    # ============================================================================
    # SCHEDULED NOTIFICATIONS
    # ============================================================================

    def get_digest_recipients(
        self,
        digest_time: str,
        hostel_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        Get students subscribed to digest at specific time.
        
        Args:
            digest_time: Digest time (HH:MM format)
            hostel_id: Optional hostel filter
            
        Returns:
            List of digest recipients
        """
        preferences_list = self.preferences_repo.find_digest_subscribers(
            digest_time,
            hostel_id
        )
        
        return [
            {
                'student_id': prefs.student_id,
                'preferences': prefs
            }
            for prefs in preferences_list
        ]