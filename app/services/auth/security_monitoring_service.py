"""
Security monitoring service: login attempts, security events, and threat detection.

Comprehensive security monitoring with anomaly detection,
suspicious activity tracking, and alerting capabilities.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta
import logging
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.auth import (
    LoginAttemptRepository,
    SecurityEventRepository,
)
from app.models.auth.user_session import LoginAttempt
from app.schemas.auth.security import (
    SecurityEventType,
    SecurityEventSeverity,
    LoginAttemptSummary,
    SecurityEventSummary,
    ThreatAnalysis,
)

logger = logging.getLogger(__name__)


class SecurityMonitoringService(BaseService[LoginAttempt, LoginAttemptRepository]):
    """
    Monitor and analyze security events and login patterns.
    
    Features:
    - Login attempt tracking and analysis
    - Security event logging and categorization
    - Anomaly detection (unusual locations, devices, timing)
    - Threat scoring and risk assessment
    - Automated alerting for suspicious activity
    - Compliance reporting
    """

    # Configuration
    SUSPICIOUS_FAILURE_THRESHOLD = 5
    SUSPICIOUS_TIME_WINDOW_MINUTES = 15
    MAX_FAILED_ATTEMPTS_PER_IP = 10
    GEOGRAPHIC_ANOMALY_DISTANCE_KM = 500
    DEVICE_FINGERPRINT_CHANGE_THRESHOLD = 3

    def __init__(
        self,
        login_attempt_repo: LoginAttemptRepository,
        security_event_repo: SecurityEventRepository,
        db_session: Session,
    ):
        super().__init__(login_attempt_repo, db_session)
        self.login_attempt_repo = login_attempt_repo
        self.security_event_repo = security_event_repo

    # -------------------------------------------------------------------------
    # Login Attempt Analysis
    # -------------------------------------------------------------------------

    def get_recent_attempts(
        self,
        user_id: UUID,
        days: int = 7,
        limit: int = 50,
        include_successful: bool = True,
    ) -> ServiceResult[List[LoginAttemptSummary]]:
        """
        Retrieve recent login attempts for a user.
        
        Args:
            user_id: User identifier
            days: Number of days to look back
            limit: Maximum number of attempts to return
            include_successful: Include successful attempts
            
        Returns:
            ServiceResult with list of login attempt summaries
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            attempts = self.login_attempt_repo.get_recent(
                user_id=user_id,
                since=since,
                limit=limit,
            )

            # Filter and transform
            summaries = []
            for attempt in attempts:
                if not include_successful and attempt.success:
                    continue
                
                summary = LoginAttemptSummary(
                    id=str(attempt.id),
                    user_id=str(attempt.user_id) if attempt.user_id else None,
                    identifier=attempt.identifier,
                    ip_address=attempt.ip_address,
                    user_agent=attempt.user_agent,
                    success=attempt.success,
                    attempted_at=attempt.attempted_at,
                    location=self._extract_location(attempt),
                    device_info=self._parse_device_info(attempt.user_agent),
                )
                summaries.append(summary)

            logger.info(
                f"Retrieved {len(summaries)} login attempts for user: {user_id}"
            )
            
            return ServiceResult.success(
                summaries,
                metadata={
                    "count": len(summaries),
                    "period_days": days,
                    "includes_successful": include_successful,
                },
            )

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving login attempts: {str(e)}")
            return self._handle_exception(e, "get login attempts", user_id)
        except Exception as e:
            logger.error(f"Error retrieving login attempts: {str(e)}")
            return self._handle_exception(e, "get login attempts", user_id)

    def analyze_login_pattern(
        self,
        user_id: UUID,
        days: int = 30,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Analyze login patterns for anomaly detection.
        
        Args:
            user_id: User identifier
            days: Analysis period in days
            
        Returns:
            ServiceResult with pattern analysis
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            attempts = self.login_attempt_repo.get_recent(
                user_id=user_id,
                since=since,
                limit=1000,
            )

            if not attempts:
                return ServiceResult.success(
                    {
                        "total_attempts": 0,
                        "message": "No login activity in the specified period",
                    }
                )

            # Analyze patterns
            analysis = {
                "total_attempts": len(attempts),
                "successful_attempts": sum(1 for a in attempts if a.success),
                "failed_attempts": sum(1 for a in attempts if not a.success),
                "unique_ips": len(set(a.ip_address for a in attempts if a.ip_address)),
                "unique_devices": len(
                    set(a.user_agent for a in attempts if a.user_agent)
                ),
                "time_distribution": self._analyze_time_distribution(attempts),
                "geographic_distribution": self._analyze_geographic_distribution(
                    attempts
                ),
                "device_distribution": self._analyze_device_distribution(attempts),
                "anomalies": self._detect_anomalies(attempts),
            }

            # Calculate risk score
            analysis["risk_score"] = self._calculate_risk_score(analysis)
            analysis["risk_level"] = self._get_risk_level(analysis["risk_score"])

            logger.info(f"Login pattern analyzed for user: {user_id}")
            return ServiceResult.success(
                analysis,
                metadata={"analysis_period_days": days},
            )

        except Exception as e:
            logger.error(f"Error analyzing login pattern: {str(e)}")
            return self._handle_exception(e, "analyze login pattern", user_id)

    def get_failed_attempts_by_ip(
        self,
        ip_address: str,
        hours: int = 24,
    ) -> ServiceResult[List[LoginAttemptSummary]]:
        """
        Get failed login attempts from specific IP address.
        
        Args:
            ip_address: IP address to analyze
            hours: Time window in hours
            
        Returns:
            ServiceResult with failed attempts from IP
        """
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            
            attempts = self.login_attempt_repo.get_by_ip(
                ip_address=ip_address,
                since=since,
                success=False,
            )

            summaries = [
                LoginAttemptSummary(
                    id=str(attempt.id),
                    user_id=str(attempt.user_id) if attempt.user_id else None,
                    identifier=attempt.identifier,
                    ip_address=attempt.ip_address,
                    user_agent=attempt.user_agent,
                    success=attempt.success,
                    attempted_at=attempt.attempted_at,
                )
                for attempt in attempts
            ]

            # Check if IP should be blocked
            should_block = len(summaries) >= self.MAX_FAILED_ATTEMPTS_PER_IP

            logger.info(
                f"Retrieved {len(summaries)} failed attempts from IP: {ip_address}"
            )
            
            return ServiceResult.success(
                summaries,
                metadata={
                    "count": len(summaries),
                    "should_block": should_block,
                    "threshold": self.MAX_FAILED_ATTEMPTS_PER_IP,
                },
            )

        except Exception as e:
            logger.error(f"Error retrieving attempts by IP: {str(e)}")
            return self._handle_exception(e, "get attempts by IP", ip_address)

    # -------------------------------------------------------------------------
    # Security Event Management
    # -------------------------------------------------------------------------

    def record_event(
        self,
        user_id: UUID,
        event_type: str,
        reason: str,
        severity: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ServiceResult[bool]:
        """
        Record a security event.
        
        Args:
            user_id: User identifier
            event_type: Type of security event
            reason: Event reason/description
            severity: Event severity level
            details: Additional event details
            ip_address: Source IP address
            user_agent: User agent string
            
        Returns:
            ServiceResult with success status
        """
        try:
            event_data = {
                "user_id": user_id,
                "event_type": event_type,
                "reason": reason,
                "severity": severity or SecurityEventSeverity.MEDIUM,
                "details": details or {},
                "ip_address": ip_address,
                "user_agent": user_agent,
                "created_at": datetime.utcnow(),
                "resolved": False,
            }

            event = self.security_event_repo.create_event(event_data)
            self.db.commit()

            logger.info(
                f"Security event recorded: {event_type} for user: {user_id}"
            )

            # Check if event requires immediate action
            if severity in [SecurityEventSeverity.HIGH, SecurityEventSeverity.CRITICAL]:
                self._trigger_security_alert(event)

            return ServiceResult.success(
                True,
                message="Security event recorded",
                metadata={"event_id": str(event.id)},
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error recording security event: {str(e)}")
            return self._handle_exception(e, "record security event", user_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error recording security event: {str(e)}")
            return self._handle_exception(e, "record security event", user_id)

    def get_events(
        self,
        user_id: UUID,
        days: int = 30,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        resolved: Optional[bool] = None,
    ) -> ServiceResult[List[SecurityEventSummary]]:
        """
        Retrieve security events for a user.
        
        Args:
            user_id: User identifier
            days: Number of days to look back
            event_type: Filter by event type
            severity: Filter by severity
            resolved: Filter by resolution status
            
        Returns:
            ServiceResult with list of security events
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            events = self.security_event_repo.get_events_for_user(
                user_id=user_id,
                since=since,
                event_type=event_type,
                severity=severity,
                resolved=resolved,
            )

            summaries = [
                SecurityEventSummary(
                    id=str(event.id),
                    user_id=str(event.user_id),
                    event_type=event.event_type,
                    reason=event.reason,
                    severity=event.severity,
                    details=event.details,
                    ip_address=event.ip_address,
                    created_at=event.created_at,
                    resolved=event.resolved,
                    resolved_at=event.resolved_at,
                )
                for event in events
            ]

            logger.info(f"Retrieved {len(summaries)} security events for user: {user_id}")
            
            return ServiceResult.success(
                summaries,
                metadata={
                    "count": len(summaries),
                    "period_days": days,
                },
            )

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving security events: {str(e)}")
            return self._handle_exception(e, "get security events", user_id)
        except Exception as e:
            logger.error(f"Error retrieving security events: {str(e)}")
            return self._handle_exception(e, "get security events", user_id)

    def resolve_event(
        self,
        event_id: UUID,
        resolution_notes: Optional[str] = None,
    ) -> ServiceResult[bool]:
        """
        Mark security event as resolved.
        
        Args:
            event_id: Event identifier
            resolution_notes: Notes about resolution
            
        Returns:
            ServiceResult with success status
        """
        try:
            self.security_event_repo.resolve_event(
                event_id=event_id,
                resolution_notes=resolution_notes,
            )
            self.db.commit()

            logger.info(f"Security event resolved: {event_id}")
            return ServiceResult.success(
                True,
                message="Security event resolved",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error resolving event: {str(e)}")
            return self._handle_exception(e, "resolve event", event_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error resolving event: {str(e)}")
            return self._handle_exception(e, "resolve event", event_id)

    # -------------------------------------------------------------------------
    # Threat Analysis
    # -------------------------------------------------------------------------

    def analyze_threat_level(
        self,
        user_id: UUID,
    ) -> ServiceResult[ThreatAnalysis]:
        """
        Analyze overall threat level for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            ServiceResult with threat analysis
        """
        try:
            # Gather data from multiple sources
            recent_attempts = self.login_attempt_repo.get_recent(
                user_id=user_id,
                since=datetime.utcnow() - timedelta(days=7),
            )
            
            recent_events = self.security_event_repo.get_events_for_user(
                user_id=user_id,
                since=datetime.utcnow() - timedelta(days=7),
            )

            # Calculate threat indicators
            failed_login_rate = self._calculate_failed_login_rate(recent_attempts)
            unusual_activity_score = self._calculate_unusual_activity_score(
                recent_attempts
            )
            security_event_score = self._calculate_security_event_score(
                recent_events
            )

            # Aggregate threat score (0-100)
            threat_score = (
                failed_login_rate * 0.4 +
                unusual_activity_score * 0.3 +
                security_event_score * 0.3
            )

            # Determine threat level
            if threat_score >= 80:
                threat_level = "CRITICAL"
                recommendations = [
                    "Immediate account review required",
                    "Consider temporary account suspension",
                    "Force password reset",
                    "Enable MFA if not already active",
                ]
            elif threat_score >= 60:
                threat_level = "HIGH"
                recommendations = [
                    "Review recent account activity",
                    "Notify user of suspicious activity",
                    "Recommend password change",
                ]
            elif threat_score >= 40:
                threat_level = "MEDIUM"
                recommendations = [
                    "Monitor account activity",
                    "Suggest security review",
                ]
            elif threat_score >= 20:
                threat_level = "LOW"
                recommendations = [
                    "Continue routine monitoring",
                ]
            else:
                threat_level = "MINIMAL"
                recommendations = []

            analysis = ThreatAnalysis(
                user_id=str(user_id),
                threat_score=threat_score,
                threat_level=threat_level,
                failed_login_rate=failed_login_rate,
                unusual_activity_score=unusual_activity_score,
                security_event_score=security_event_score,
                recommendations=recommendations,
                analyzed_at=datetime.utcnow(),
            )

            logger.info(
                f"Threat analysis completed for user {user_id}: "
                f"Level={threat_level}, Score={threat_score:.2f}"
            )
            
            return ServiceResult.success(
                analysis,
                message=f"Threat level: {threat_level}",
            )

        except Exception as e:
            logger.error(f"Error analyzing threat level: {str(e)}")
            return self._handle_exception(e, "analyze threat level", user_id)

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _analyze_time_distribution(
        self,
        attempts: List[LoginAttempt],
    ) -> Dict[str, int]:
        """Analyze login attempts by time of day."""
        distribution = defaultdict(int)
        
        for attempt in attempts:
            hour = attempt.attempted_at.hour
            if 0 <= hour < 6:
                distribution["night"] += 1
            elif 6 <= hour < 12:
                distribution["morning"] += 1
            elif 12 <= hour < 18:
                distribution["afternoon"] += 1
            else:
                distribution["evening"] += 1
        
        return dict(distribution)

    def _analyze_geographic_distribution(
        self,
        attempts: List[LoginAttempt],
    ) -> Dict[str, int]:
        """Analyze login attempts by geographic location."""
        distribution = defaultdict(int)
        
        for attempt in attempts:
            location = self._extract_location(attempt)
            if location:
                distribution[location] += 1
        
        return dict(distribution)

    def _analyze_device_distribution(
        self,
        attempts: List[LoginAttempt],
    ) -> Dict[str, int]:
        """Analyze login attempts by device type."""
        distribution = defaultdict(int)
        
        for attempt in attempts:
            device_info = self._parse_device_info(attempt.user_agent)
            device_type = device_info.get("device_type", "unknown")
            distribution[device_type] += 1
        
        return dict(distribution)

    def _detect_anomalies(
        self,
        attempts: List[LoginAttempt],
    ) -> List[Dict[str, Any]]:
        """Detect anomalous login patterns."""
        anomalies = []

        # Check for rapid failed attempts
        failed_attempts = [a for a in attempts if not a.success]
        if len(failed_attempts) >= self.SUSPICIOUS_FAILURE_THRESHOLD:
            recent_failures = [
                a for a in failed_attempts
                if (datetime.utcnow() - a.attempted_at).total_seconds() < 
                   self.SUSPICIOUS_TIME_WINDOW_MINUTES * 60
            ]
            
            if len(recent_failures) >= self.SUSPICIOUS_FAILURE_THRESHOLD:
                anomalies.append({
                    "type": "rapid_failed_attempts",
                    "severity": "HIGH",
                    "description": (
                        f"{len(recent_failures)} failed attempts in "
                        f"{self.SUSPICIOUS_TIME_WINDOW_MINUTES} minutes"
                    ),
                    "count": len(recent_failures),
                })

        # Check for multiple IPs
        unique_ips = set(a.ip_address for a in attempts if a.ip_address)
        if len(unique_ips) > 5:
            anomalies.append({
                "type": "multiple_ip_addresses",
                "severity": "MEDIUM",
                "description": f"Login attempts from {len(unique_ips)} different IPs",
                "count": len(unique_ips),
            })

        # Check for unusual times
        night_attempts = [
            a for a in attempts
            if 0 <= a.attempted_at.hour < 6
        ]
        if len(night_attempts) > len(attempts) * 0.3:
            anomalies.append({
                "type": "unusual_time_pattern",
                "severity": "LOW",
                "description": f"{len(night_attempts)} attempts during night hours",
                "count": len(night_attempts),
            })

        return anomalies

    def _calculate_risk_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall risk score from analysis data."""
        score = 0.0

        # Factor in failed attempts
        if analysis["total_attempts"] > 0:
            failure_rate = (
                analysis["failed_attempts"] / analysis["total_attempts"]
            )
            score += failure_rate * 30

        # Factor in unique IPs
        if analysis["unique_ips"] > 5:
            score += min(analysis["unique_ips"] * 2, 20)

        # Factor in anomalies
        anomaly_count = len(analysis.get("anomalies", []))
        score += min(anomaly_count * 10, 30)

        # Factor in high-severity anomalies
        high_severity_anomalies = [
            a for a in analysis.get("anomalies", [])
            if a.get("severity") == "HIGH"
        ]
        score += len(high_severity_anomalies) * 20

        return min(score, 100.0)

    def _get_risk_level(self, risk_score: float) -> str:
        """Determine risk level from score."""
        if risk_score >= 80:
            return "CRITICAL"
        elif risk_score >= 60:
            return "HIGH"
        elif risk_score >= 40:
            return "MEDIUM"
        elif risk_score >= 20:
            return "LOW"
        else:
            return "MINIMAL"

    def _calculate_failed_login_rate(
        self,
        attempts: List[LoginAttempt],
    ) -> float:
        """Calculate failed login rate (0-100)."""
        if not attempts:
            return 0.0
        
        failed_count = sum(1 for a in attempts if not a.success)
        return (failed_count / len(attempts)) * 100

    def _calculate_unusual_activity_score(
        self,
        attempts: List[LoginAttempt],
    ) -> float:
        """Calculate unusual activity score (0-100)."""
        if not attempts:
            return 0.0

        score = 0.0

        # Check IP diversity
        unique_ips = len(set(a.ip_address for a in attempts if a.ip_address))
        if unique_ips > 5:
            score += min(unique_ips * 5, 40)

        # Check unusual timing
        night_attempts = sum(
            1 for a in attempts if 0 <= a.attempted_at.hour < 6
        )
        if night_attempts > len(attempts) * 0.3:
            score += 30

        # Check device diversity
        unique_devices = len(
            set(a.user_agent for a in attempts if a.user_agent)
        )
        if unique_devices > 3:
            score += 30

        return min(score, 100.0)

    def _calculate_security_event_score(
        self,
        events: List,
    ) -> float:
        """Calculate security event severity score (0-100)."""
        if not events:
            return 0.0

        score = 0.0
        
        for event in events:
            severity = event.severity
            if severity == SecurityEventSeverity.CRITICAL:
                score += 25
            elif severity == SecurityEventSeverity.HIGH:
                score += 15
            elif severity == SecurityEventSeverity.MEDIUM:
                score += 10
            elif severity == SecurityEventSeverity.LOW:
                score += 5

        return min(score, 100.0)

    def _extract_location(self, attempt: LoginAttempt) -> Optional[str]:
        """Extract location from login attempt (placeholder)."""
        # In production, integrate with GeoIP service
        if not attempt.ip_address:
            return None
        
        # Placeholder - would use actual GeoIP lookup
        return "Unknown"

    def _parse_device_info(self, user_agent: Optional[str]) -> Dict[str, str]:
        """Parse user agent string for device information."""
        if not user_agent:
            return {"device_type": "unknown", "browser": "unknown", "os": "unknown"}

        # Simplified parsing - use user-agents library in production
        device_type = "desktop"
        if "Mobile" in user_agent or "Android" in user_agent:
            device_type = "mobile"
        elif "Tablet" in user_agent or "iPad" in user_agent:
            device_type = "tablet"

        browser = "unknown"
        if "Chrome" in user_agent:
            browser = "Chrome"
        elif "Firefox" in user_agent:
            browser = "Firefox"
        elif "Safari" in user_agent:
            browser = "Safari"
        elif "Edge" in user_agent:
            browser = "Edge"

        os = "unknown"
        if "Windows" in user_agent:
            os = "Windows"
        elif "Mac" in user_agent:
            os = "macOS"
        elif "Linux" in user_agent:
            os = "Linux"
        elif "Android" in user_agent:
            os = "Android"
        elif "iOS" in user_agent:
            os = "iOS"

        return {
            "device_type": device_type,
            "browser": browser,
            "os": os,
        }

    def _trigger_security_alert(self, event) -> None:
        """Trigger security alert for high-severity events."""
        # In production, integrate with alerting system
        logger.warning(
            f"SECURITY ALERT: {event.event_type} for user {event.user_id} - "
            f"Severity: {event.severity}"
        )
        # Could send email, SMS, push notification, etc.