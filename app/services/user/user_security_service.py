# --- File: C:\Hostel-Main\app\services\user\user_security_service.py ---
"""
User Security Service - Advanced security operations and monitoring.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.repositories.user import UserRepository, UserSessionRepository
from app.repositories.user.user_security_repository import UserSecurityRepository
from app.core.exceptions import BusinessRuleViolationError, AuthenticationError


class UserSecurityService:
    """
    Service for advanced security operations including
    threat detection, account protection, and security auditing.
    """

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.session_repo = UserSessionRepository(db)
        self.security_repo = UserSecurityRepository(db)

    # ==================== Threat Detection ====================

    def detect_suspicious_activity(
        self,
        user_id: str,
        activity_window_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Detect suspicious activity for a user.
        
        Args:
            user_id: User ID
            activity_window_hours: Time window to analyze
            
        Returns:
            Suspicious activity report
        """
        threats = []
        risk_score = 0
        
        # Check for brute force attempts
        user = self.user_repo.get_by_id(user_id)
        
        brute_force_detected = self.security_repo.detect_brute_force_attempt(
            email=user.email,
            minutes=15,
            threshold=5
        )
        
        if brute_force_detected:
            threats.append({
                'type': 'brute_force_attempt',
                'severity': 'high',
                'description': 'Multiple failed login attempts detected'
            })
            risk_score += 30
        
        # Check for concurrent sessions from different locations
        sessions = self.session_repo.find_by_user_id(user_id, active_only=True)
        
        if len(sessions) > 5:
            threats.append({
                'type': 'excessive_concurrent_sessions',
                'severity': 'medium',
                'description': f'{len(sessions)} concurrent sessions detected'
            })
            risk_score += 20
        
        # Check for logins from different IPs in short time
        multiple_ips = self.session_repo.find_multiple_ip_sessions(
            user_id,
            time_window_minutes=5
        )
        
        if len(multiple_ips) > 1:
            threats.append({
                'type': 'multiple_ip_logins',
                'severity': 'high',
                'description': f'Logins from {len(multiple_ips)} different IPs'
            })
            risk_score += 40
        
        # Check for suspicious sessions
        suspicious_sessions = self.session_repo.find_suspicious_sessions(user_id)
        
        if suspicious_sessions:
            threats.append({
                'type': 'suspicious_sessions',
                'severity': 'medium',
                'description': f'{len(suspicious_sessions)} suspicious sessions found'
            })
            risk_score += 25
        
        return {
            'user_id': user_id,
            'risk_score': min(risk_score, 100),
            'risk_level': self._get_risk_level(risk_score),
            'threats_detected': threats,
            'threat_count': len(threats),
            'requires_action': risk_score >= 50
        }

    def _get_risk_level(self, score: int) -> str:
        """Convert risk score to level."""
        if score >= 70:
            return 'critical'
        elif score >= 50:
            return 'high'
        elif score >= 30:
            return 'medium'
        return 'low'

    # ==================== Account Protection ====================

    def enable_account_protection(
        self,
        user_id: str,
        protection_level: str = 'standard'
    ) -> Dict[str, Any]:
        """
        Enable enhanced account protection.
        
        Args:
            user_id: User ID
            protection_level: Protection level (basic, standard, maximum)
            
        Returns:
            Protection status
        """
        user = self.user_repo.get_by_id(user_id)
        
        protection_settings = {
            'basic': {
                'max_concurrent_sessions': 5,
                'max_failed_attempts': 5,
                'lockout_duration_minutes': 30,
                'require_2fa': False
            },
            'standard': {
                'max_concurrent_sessions': 3,
                'max_failed_attempts': 3,
                'lockout_duration_minutes': 60,
                'require_2fa': True
            },
            'maximum': {
                'max_concurrent_sessions': 1,
                'max_failed_attempts': 2,
                'lockout_duration_minutes': 120,
                'require_2fa': True
            }
        }
        
        settings = protection_settings.get(protection_level, protection_settings['standard'])
        
        # TODO: Store protection settings in user profile or separate table
        
        return {
            'user_id': user_id,
            'protection_level': protection_level,
            'settings': settings,
            'enabled_at': datetime.now(timezone.utc).isoformat()
        }

    def force_password_reset(
        self,
        user_id: str,
        reason: str = 'security_concern'
    ) -> Dict[str, Any]:
        """
        Force user to reset password on next login.
        
        Args:
            user_id: User ID
            reason: Reason for forced reset
            
        Returns:
            Reset status
        """
        user = self.user_repo.get_by_id(user_id)
        
        # Set password reset required flag
        self.user_repo.update(user.id, {
            'password_reset_required': True
        })
        
        # Revoke all sessions
        self.session_repo.revoke_all_user_sessions(
            user_id,
            reason='forced_password_reset'
        )
        
        # TODO: Send notification to user
        
        return {
            'user_id': user_id,
            'password_reset_required': True,
            'reason': reason,
            'sessions_revoked': True
        }

    def lock_account_temporarily(
        self,
        user_id: str,
        duration_minutes: int = 60,
        reason: str = 'suspicious_activity'
    ) -> Dict[str, Any]:
        """
        Temporarily lock user account.
        
        Args:
            user_id: User ID
            duration_minutes: Lock duration
            reason: Lock reason
            
        Returns:
            Lock status
        """
        locked_until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        
        self.user_repo.update(user_id, {
            'account_locked_until': locked_until
        })
        
        # Revoke all sessions
        self.session_repo.revoke_all_user_sessions(
            user_id,
            reason=f'account_locked_{reason}'
        )
        
        return {
            'user_id': user_id,
            'locked': True,
            'locked_until': locked_until.isoformat(),
            'duration_minutes': duration_minutes,
            'reason': reason
        }

    # ==================== Security Auditing ====================

    def generate_security_report(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate comprehensive security report for user.
        
        Args:
            user_id: User ID
            days: Number of days to analyze
            
        Returns:
            Security report
        """
        return self.security_repo.get_comprehensive_security_report(user_id)

    def get_login_history(
        self,
        user_id: str,
        limit: int = 50,
        successful_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get user login history.
        
        Args:
            user_id: User ID
            limit: Maximum results
            successful_only: Only successful logins
            
        Returns:
            Login history
        """
        history = self.security_repo.find_user_login_history(
            user_id,
            successful_only,
            limit
        )
        
        return [
            {
                'timestamp': record.created_at.isoformat(),
                'success': record.is_successful,
                'ip_address': record.ip_address,
                'device_info': record.device_info,
                'failure_reason': record.failure_reason,
                'is_suspicious': record.is_suspicious
            }
            for record in history
        ]

    def get_password_change_history(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get password change history.
        
        Args:
            user_id: User ID
            limit: Maximum results
            
        Returns:
            Password change history
        """
        history = self.security_repo.find_user_password_history(user_id, limit)
        
        return [
            {
                'changed_at': record.created_at.isoformat(),
                'change_reason': record.change_reason,
                'changed_by_self': record.changed_by == user_id if record.changed_by else True,
                'ip_address': record.ip_address
            }
            for record in history
        ]

    # ==================== Device Management ====================

    def get_trusted_devices(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get list of user's trusted devices.
        
        Args:
            user_id: User ID
            
        Returns:
            List of trusted devices
        """
        devices = self.session_repo.get_unique_devices(user_id)
        
        # Filter for devices with multiple successful sessions
        trusted = [
            device for device in devices
            if device['session_count'] >= 3
        ]
        
        return trusted

    def revoke_device_access(
        self,
        user_id: str,
        device_fingerprint: str
    ) -> Dict[str, Any]:
        """
        Revoke access for a specific device.
        
        Args:
            user_id: User ID
            device_fingerprint: Device fingerprint
            
        Returns:
            Revocation status
        """
        sessions = self.session_repo.find_by_device_fingerprint(
            user_id,
            device_fingerprint
        )
        
        revoked_count = 0
        for session in sessions:
            if session.is_active:
                self.session_repo.revoke_session(
                    session.id,
                    reason='device_access_revoked'
                )
                revoked_count += 1
        
        return {
            'user_id': user_id,
            'device_fingerprint': device_fingerprint,
            'sessions_revoked': revoked_count
        }

    # ==================== Security Recommendations ====================

    def get_security_recommendations(self, user_id: str) -> List[Dict[str, str]]:
        """
        Get personalized security recommendations.
        
        Args:
            user_id: User ID
            
        Returns:
            List of recommendations
        """
        user = self.user_repo.get_by_id(user_id)
        recommendations = []
        
        # Check verification status
        if not user.is_email_verified:
            recommendations.append({
                'priority': 'high',
                'category': 'verification',
                'title': 'Verify Your Email',
                'description': 'Verify your email address to secure account recovery options.'
            })
        
        if not user.is_phone_verified:
            recommendations.append({
                'priority': 'high',
                'category': 'verification',
                'title': 'Verify Your Phone',
                'description': 'Verify your phone number for two-factor authentication.'
            })
        
        # Check password age
        if user.last_password_change_at:
            days_since_change = (datetime.now(timezone.utc) - user.last_password_change_at).days
            if days_since_change > 90:
                recommendations.append({
                    'priority': 'medium',
                    'category': 'password',
                    'title': 'Update Your Password',
                    'description': f'Your password is {days_since_change} days old. Consider changing it.'
                })
        
        # Check for multiple sessions
        active_sessions = len(self.session_repo.find_by_user_id(user_id, active_only=True))
        if active_sessions > 3:
            recommendations.append({
                'priority': 'medium',
                'category': 'sessions',
                'title': 'Review Active Sessions',
                'description': f'You have {active_sessions} active sessions. Review and revoke unknown devices.'
            })
        
        # Check for recent suspicious activity
        threat_report = self.detect_suspicious_activity(user_id)
        if threat_report['risk_score'] > 30:
            recommendations.append({
                'priority': 'high',
                'category': 'security',
                'title': 'Review Security Alerts',
                'description': 'Suspicious activity detected. Review your account security.'
            })
        
        return recommendations


