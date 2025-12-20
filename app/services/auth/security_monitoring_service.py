"""
Security Monitoring Service
Security event tracking, threat detection, and risk analysis.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.auth import (
    SecurityEventRepository,
    LoginAttemptRepository,
    BlacklistedTokenRepository,
)


class SecurityMonitoringService:
    """
    Service for security monitoring and threat detection.
    """

    def __init__(self, db: Session):
        self.db = db
        self.security_event_repo = SecurityEventRepository(db)
        self.login_attempt_repo = LoginAttemptRepository(db)
        self.blacklist_repo = BlacklistedTokenRepository(db)

    # ==================== Security Event Recording ====================

    def record_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
        country: Optional[str] = None,
        city: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        risk_score: Optional[int] = None
    ) -> Any:
        """
        Record security event.
        
        Args:
            event_type: Type of security event
            severity: Event severity (low, medium, high, critical)
            description: Event description
            user_id: Associated user (if applicable)
            ip_address: IP address
            user_agent: User agent
            device_fingerprint: Device fingerprint
            country: Country from geolocation
            city: City from geolocation
            event_data: Event-specific data
            risk_score: Calculated risk score (0-100)
            
        Returns:
            Created SecurityEvent instance
        """
        # Auto-calculate risk score if not provided
        if risk_score is None and user_id:
            risk_score = self.calculate_event_risk(
                event_type=event_type,
                user_id=user_id,
                ip_address=ip_address,
                device_fingerprint=device_fingerprint
            )
        
        return self.security_event_repo.record_event(
            event_type=event_type,
            severity=severity,
            description=description,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            country=country,
            city=city,
            event_data=event_data,
            risk_score=risk_score
        )

    # ==================== Risk Calculation ====================

    def calculate_login_risk(
        self,
        user_id: Optional[UUID],
        ip_address: str,
        device_fingerprint: Optional[str] = None
    ) -> int:
        """
        Calculate risk score for login attempt.
        
        Args:
            user_id: User identifier
            ip_address: IP address
            device_fingerprint: Device fingerprint
            
        Returns:
            Risk score (0-100)
        """
        risk_score = 0
        
        if not user_id:
            # Unknown user increases risk
            risk_score += 20
        else:
            # Check failed login attempts
            recent_failures = self.login_attempt_repo.count_recent_failures(
                identifier=str(user_id),
                identifier_type="user_id",
                minutes=60
            )
            
            if recent_failures > 0:
                risk_score += min(recent_failures * 10, 30)
            
            # Check if device is known
            if device_fingerprint:
                is_known_device = self._is_known_device(user_id, device_fingerprint)
                if not is_known_device:
                    risk_score += 20
        
        # Check IP reputation
        ip_risk = self._check_ip_reputation(ip_address)
        risk_score += ip_risk
        
        # Check for rapid login attempts from different locations
        if user_id:
            location_risk = self._check_location_anomaly(user_id, ip_address)
            risk_score += location_risk
        
        return min(risk_score, 100)

    def calculate_event_risk(
        self,
        event_type: str,
        user_id: UUID,
        ip_address: Optional[str] = None,
        device_fingerprint: Optional[str] = None
    ) -> int:
        """
        Calculate risk score for security event.
        
        Args:
            event_type: Type of event
            user_id: User identifier
            ip_address: IP address
            device_fingerprint: Device fingerprint
            
        Returns:
            Risk score (0-100)
        """
        # Base risk scores for different event types
        base_risks = {
            "password_reset_requested": 30,
            "password_changed": 40,
            "email_changed": 50,
            "mfa_disabled": 70,
            "suspicious_login": 80,
            "token_reuse_detected": 90,
            "account_takeover_attempt": 100
        }
        
        risk_score = base_risks.get(event_type, 20)
        
        # Add risk factors
        if ip_address:
            ip_risk = self._check_ip_reputation(ip_address)
            risk_score += ip_risk * 0.5
        
        if device_fingerprint:
            is_known = self._is_known_device(user_id, device_fingerprint)
            if not is_known:
                risk_score += 15
        
        # Check recent security events
        recent_events = self.get_recent_security_events(user_id, hours=24)
        if len(recent_events) > 5:
            risk_score += 20
        
        return min(int(risk_score), 100)

    def _is_known_device(self, user_id: UUID, device_fingerprint: str) -> bool:
        """Check if device is known for user."""
        from app.models.auth import UserSession
        
        # Check if user has previous sessions from this device
        session_count = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.device_fingerprint == device_fingerprint
        ).count()
        
        return session_count > 0

    def _check_ip_reputation(self, ip_address: str) -> int:
        """
        Check IP address reputation.
        Returns risk score (0-50).
        """
        # Check recent events from this IP
        recent_events = self.security_event_repo.find_events_by_ip(
            ip_address=ip_address,
            hours=24
        )
        
        risk_score = 0
        
        # Multiple failed attempts
        if len(recent_events) > 10:
            risk_score += 30
        
        # High-risk events from this IP
        high_risk_count = sum(
            1 for event in recent_events
            if event.risk_score and event.risk_score >= 70
        )
        
        if high_risk_count > 0:
            risk_score += 20
        
        return min(risk_score, 50)

    def _check_location_anomaly(self, user_id: UUID, ip_address: str) -> int:
        """
        Check for location anomalies.
        Returns risk score (0-30).
        """
        from app.models.auth import UserSession
        
        # Get recent sessions
        recent_sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.created_at >= datetime.utcnow() - timedelta(hours=1)
        ).all()
        
        if len(recent_sessions) < 2:
            return 0
        
        # Check if sessions are from different countries
        countries = set(s.country for s in recent_sessions if s.country)
        
        if len(countries) > 1:
            return 30
        
        return 0

    # ==================== Threat Detection ====================

    def detect_account_takeover(self, user_id: UUID) -> Dict[str, Any]:
        """
        Detect potential account takeover.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with detection results
        """
        indicators = []
        risk_score = 0
        
        # Check for password changes
        recent_password_changes = self._check_recent_password_changes(user_id)
        if recent_password_changes > 0:
            indicators.append("Recent password change")
            risk_score += 30
        
        # Check for email changes
        recent_email_changes = self._check_recent_email_changes(user_id)
        if recent_email_changes > 0:
            indicators.append("Recent email change")
            risk_score += 40
        
        # Check for MFA disabled
        if self._check_mfa_disabled(user_id):
            indicators.append("MFA recently disabled")
            risk_score += 50
        
        # Check for unusual login locations
        unusual_locations = self._check_unusual_locations(user_id)
        if unusual_locations:
            indicators.append(f"Login from unusual location: {unusual_locations}")
            risk_score += 30
        
        # Check for rapid session creation
        rapid_sessions = self._check_rapid_sessions(user_id)
        if rapid_sessions:
            indicators.append("Rapid session creation detected")
            risk_score += 20
        
        is_suspicious = risk_score >= 70
        
        if is_suspicious:
            # Record security event
            self.record_security_event(
                event_type="account_takeover_suspected",
                severity="critical",
                description="Potential account takeover detected",
                user_id=user_id,
                event_data={"indicators": indicators},
                risk_score=risk_score
            )
        
        return {
            "is_suspicious": is_suspicious,
            "risk_score": risk_score,
            "indicators": indicators,
            "recommendation": self._get_takeover_recommendation(risk_score)
        }

    def detect_brute_force(
        self,
        identifier: str,
        identifier_type: str = "email"
    ) -> Dict[str, Any]:
        """
        Detect brute force attacks.
        
        Args:
            identifier: Email or phone
            identifier_type: Type of identifier
            
        Returns:
            Dictionary with detection results
        """
        # Count recent failed attempts
        failures_15min = self.login_attempt_repo.count_recent_failures(
            identifier=identifier,
            identifier_type=identifier_type,
            minutes=15
        )
        
        failures_1hour = self.login_attempt_repo.count_recent_failures(
            identifier=identifier,
            identifier_type=identifier_type,
            minutes=60
        )
        
        is_brute_force = failures_15min >= 5 or failures_1hour >= 10
        
        if is_brute_force:
            self.record_security_event(
                event_type="brute_force_detected",
                severity="high",
                description=f"Brute force attack detected on {identifier}",
                event_data={
                    "identifier": identifier,
                    "failures_15min": failures_15min,
                    "failures_1hour": failures_1hour
                },
                risk_score=80
            )
        
        return {
            "is_brute_force": is_brute_force,
            "failures_15min": failures_15min,
            "failures_1hour": failures_1hour,
            "recommendation": "Account should be temporarily locked" if is_brute_force else None
        }

    def _check_recent_password_changes(self, user_id: UUID) -> int:
        """Check for recent password changes."""
        from app.models.auth import PasswordHistory
        
        recent_changes = self.db.query(PasswordHistory).filter(
            PasswordHistory.user_id == user_id,
            PasswordHistory.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        return recent_changes

    def _check_recent_email_changes(self, user_id: UUID) -> int:
        """Check for recent email changes."""
        # This would check your user audit log
        # Placeholder implementation
        return 0

    def _check_mfa_disabled(self, user_id: UUID) -> bool:
        """Check if MFA was recently disabled."""
        recent_events = self.security_event_repo.find_user_events(
            user_id=user_id,
            event_type="mfa_disabled"
        )
        
        if not recent_events:
            return False
        
        # Check if disabled in last 24 hours
        latest_event = recent_events[0]
        return (datetime.utcnow() - latest_event.created_at) < timedelta(hours=24)

    def _check_unusual_locations(self, user_id: UUID) -> Optional[str]:
        """Check for logins from unusual locations."""
        from app.models.auth import UserSession
        
        # Get recent sessions
        recent_sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).all()
        
        if len(recent_sessions) < 2:
            return None
        
        # Get historical locations
        historical_sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.created_at < datetime.utcnow() - timedelta(days=7)
        ).all()
        
        known_countries = set(s.country for s in historical_sessions if s.country)
        recent_countries = set(s.country for s in recent_sessions if s.country)
        
        unusual = recent_countries - known_countries
        
        return ", ".join(unusual) if unusual else None

    def _check_rapid_sessions(self, user_id: UUID) -> bool:
        """Check for rapid session creation."""
        from app.models.auth import UserSession
        
        session_count = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.created_at >= datetime.utcnow() - timedelta(minutes=15)
        ).count()
        
        return session_count >= 5

    def _get_takeover_recommendation(self, risk_score: int) -> str:
        """Get recommendation based on risk score."""
        if risk_score >= 90:
            return "Immediately lock account and require password reset"
        elif risk_score >= 70:
            return "Require MFA verification and notify user"
        elif risk_score >= 50:
            return "Send security alert to user"
        else:
            return "Continue monitoring"

    # ==================== Security Event Management ====================

    def get_recent_security_events(
        self,
        user_id: UUID,
        hours: int = 24,
        severity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent security events for user.
        
        Args:
            user_id: User identifier
            hours: Time window in hours
            severity: Filter by severity
            
        Returns:
            List of security events
        """
        events = self.security_event_repo.find_user_events(
            user_id=user_id,
            severity=severity,
            limit=100
        )
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_events = [e for e in events if e.created_at >= cutoff_time]
        
        return [
            {
                "event_type": event.event_type,
                "severity": event.severity,
                "description": event.description,
                "risk_score": event.risk_score,
                "created_at": event.created_at,
                "ip_address": event.ip_address,
                "location": f"{event.city}, {event.country}" if event.city and event.country else None
            }
            for event in recent_events
        ]

    def get_high_risk_events(
        self,
        hours: int = 24,
        min_risk_score: int = 70
    ) -> List[Dict[str, Any]]:
        """
        Get high-risk security events.
        
        Args:
            hours: Time window in hours
            min_risk_score: Minimum risk score
            
        Returns:
            List of high-risk events
        """
        events = self.security_event_repo.find_high_risk_events(
            min_risk_score=min_risk_score,
            hours=hours,
            unresolved_only=True
        )
        
        return [
            {
                "event_type": event.event_type,
                "severity": event.severity,
                "description": event.description,
                "risk_score": event.risk_score,
                "user_id": event.user_id,
                "created_at": event.created_at,
                "ip_address": event.ip_address
            }
            for event in events
        ]

    def resolve_security_event(
        self,
        event_id: UUID,
        resolved_by_user_id: UUID,
        resolution_note: Optional[str] = None
    ) -> bool:
        """
        Mark security event as resolved.
        
        Args:
            event_id: Event identifier
            resolved_by_user_id: User who resolved the event
            resolution_note: Resolution notes
            
        Returns:
            Success status
        """
        return self.security_event_repo.resolve_event(
            event_id=event_id,
            resolved_by_user_id=resolved_by_user_id,
            resolution_note=resolution_note
        )

    # ==================== Threat Intelligence ====================

    def get_threat_intelligence(self, days: int = 7) -> Dict[str, Any]:
        """
        Get threat intelligence summary.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with threat intelligence
        """
        return self.security_event_repo.get_threat_intelligence(days=days)

    def get_ip_threat_score(self, ip_address: str) -> Dict[str, Any]:
        """
        Get threat score for IP address.
        
        Args:
            ip_address: IP address to analyze
            
        Returns:
            Dictionary with IP threat information
        """
        events = self.security_event_repo.find_events_by_ip(
            ip_address=ip_address,
            hours=168  # 1 week
        )
        
        if not events:
            return {
                "ip_address": ip_address,
                "threat_score": 0,
                "is_suspicious": False,
                "event_count": 0
            }
        
        # Calculate threat score
        threat_score = 0
        high_risk_count = 0
        
        for event in events:
            if event.risk_score:
                threat_score += event.risk_score
                if event.risk_score >= 70:
                    high_risk_count += 1
        
        avg_threat_score = threat_score / len(events) if events else 0
        
        return {
            "ip_address": ip_address,
            "threat_score": int(avg_threat_score),
            "is_suspicious": avg_threat_score >= 50 or high_risk_count >= 3,
            "event_count": len(events),
            "high_risk_events": high_risk_count,
            "recent_events": [
                {
                    "type": e.event_type,
                    "severity": e.severity,
                    "created_at": e.created_at
                }
                for e in events[:5]
            ]
        }

    # ==================== User Security Summary ====================

    def get_user_security_summary(
        self,
        user_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive security summary for user.
        
        Args:
            user_id: User identifier
            days: Number of days to analyze
            
        Returns:
            Dictionary with security summary
        """
        # Get statistics
        event_stats = self.security_event_repo.get_event_statistics(
            user_id=user_id,
            days=days
        )
        
        # Check for account takeover indicators
        takeover_check = self.detect_account_takeover(user_id)
        
        # Get recent high-risk events
        recent_events = self.get_recent_security_events(
            user_id=user_id,
            hours=24
        )
        high_risk_events = [e for e in recent_events if e.get('risk_score', 0) >= 70]
        
        return {
            "user_id": user_id,
            "summary_period_days": days,
            "event_statistics": event_stats,
            "account_takeover_risk": takeover_check,
            "recent_high_risk_events": high_risk_events,
            "security_recommendations": self._get_security_recommendations(
                user_id=user_id,
                takeover_risk=takeover_check
            )
        }

    def _get_security_recommendations(
        self,
        user_id: UUID,
        takeover_risk: Dict[str, Any]
    ) -> List[str]:
        """Generate security recommendations for user."""
        recommendations = []
        
        if takeover_risk.get('is_suspicious'):
            recommendations.append("Review recent account activity immediately")
            recommendations.append("Change your password")
            recommendations.append("Enable MFA if not already enabled")
        
        # Check MFA status
        from app.models.user import User
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if user and not getattr(user, 'mfa_enabled', False):
            recommendations.append("Enable Multi-Factor Authentication for better security")
        
        # Check password age
        from app.repositories.auth import PasswordHistoryRepository
        password_history_repo = PasswordHistoryRepository(self.db)
        password_age = password_history_repo.get_password_age(user_id)
        
        if password_age and password_age > 90:
            recommendations.append("Consider changing your password (current password is over 90 days old)")
        
        return recommendations