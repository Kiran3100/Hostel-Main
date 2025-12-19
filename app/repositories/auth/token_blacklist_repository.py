"""
Token Blacklist Repository
Manages token revocation, blacklisting, and security events.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import Session

from app.models.auth import (
    BlacklistedToken,
    TokenRevocation,
    SecurityEvent,
)
from app.repositories.base.base_repository import BaseRepository


class BlacklistedTokenRepository(BaseRepository[BlacklistedToken]):
    """
    Repository for token blacklist management.
    """

    def __init__(self, db: Session):
        super().__init__(BlacklistedToken, db)

    def blacklist_token(
        self,
        jti: str,
        token_type: str,
        token_hash: str,
        user_id: Optional[UUID],
        expires_at: datetime,
        revocation_reason: str,
        revoked_by_user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> BlacklistedToken:
        """
        Add token to blacklist.
        
        Args:
            jti: JWT ID
            token_type: Token type (access, refresh)
            token_hash: SHA256 hash of token
            user_id: User identifier
            expires_at: Token expiration timestamp
            revocation_reason: Reason for revocation
            revoked_by_user_id: Who revoked the token
            ip_address: IP address of revocation request
            user_agent: User agent of revocation request
            metadata: Additional metadata
            
        Returns:
            Created BlacklistedToken instance
        """
        blacklisted = BlacklistedToken(
            jti=jti,
            token_type=token_type,
            token_hash=token_hash,
            user_id=user_id,
            expires_at=expires_at,
            revocation_reason=revocation_reason,
            revoked_by_user_id=revoked_by_user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata,
        )
        
        self.db.add(blacklisted)
        self.db.commit()
        self.db.refresh(blacklisted)
        return blacklisted

    def is_blacklisted(self, jti: str) -> bool:
        """
        Check if token is blacklisted.
        
        Args:
            jti: JWT ID to check
            
        Returns:
            True if token is blacklisted
        """
        exists = self.db.query(
            self.db.query(BlacklistedToken).filter(
                BlacklistedToken.jti == jti
            ).exists()
        ).scalar()
        
        return exists

    def find_by_jti(self, jti: str) -> Optional[BlacklistedToken]:
        """Find blacklisted token by JTI."""
        return self.db.query(BlacklistedToken).filter(
            BlacklistedToken.jti == jti
        ).first()

    def find_user_blacklisted_tokens(
        self,
        user_id: UUID,
        token_type: Optional[str] = None
    ) -> List[BlacklistedToken]:
        """Get all blacklisted tokens for user."""
        query = self.db.query(BlacklistedToken).filter(
            BlacklistedToken.user_id == user_id
        )
        
        if token_type:
            query = query.filter(BlacklistedToken.token_type == token_type)
        
        return query.order_by(desc(BlacklistedToken.revoked_at)).all()

    def bulk_blacklist_tokens(
        self,
        jtis: List[str],
        token_type: str,
        user_id: UUID,
        revocation_reason: str,
        expires_at: datetime,
        revoked_by_user_id: Optional[UUID] = None
    ) -> int:
        """
        Blacklist multiple tokens at once.
        
        Args:
            jtis: List of JWT IDs to blacklist
            token_type: Token type
            user_id: User identifier
            revocation_reason: Reason for revocation
            expires_at: Token expiration
            revoked_by_user_id: Who revoked the tokens
            
        Returns:
            Number of tokens blacklisted
        """
        blacklisted_tokens = [
            BlacklistedToken(
                jti=jti,
                token_type=token_type,
                token_hash="",  # Hash not needed for bulk operations
                user_id=user_id,
                expires_at=expires_at,
                revocation_reason=revocation_reason,
                revoked_by_user_id=revoked_by_user_id,
            )
            for jti in jtis
        ]
        
        self.db.bulk_save_objects(blacklisted_tokens)
        self.db.commit()
        
        return len(blacklisted_tokens)

    def cleanup_expired_tokens(self, days_old: int = 7) -> int:
        """
        Clean up expired blacklisted tokens.
        
        Args:
            days_old: Remove tokens expired more than this many days ago
            
        Returns:
            Number of tokens removed
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        count = self.db.query(BlacklistedToken).filter(
            BlacklistedToken.expires_at < cutoff_date
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return count

    def get_blacklist_statistics(
        self,
        user_id: Optional[UUID] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get blacklist statistics.
        
        Args:
            user_id: Filter by user (optional)
            days: Number of days to analyze
            
        Returns:
            Dictionary with blacklist statistics
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        query = self.db.query(BlacklistedToken).filter(
            BlacklistedToken.revoked_at >= cutoff_time
        )
        
        if user_id:
            query = query.filter(BlacklistedToken.user_id == user_id)
        
        total_blacklisted = query.count()
        
        # Token type breakdown
        type_breakdown = self.db.query(
            BlacklistedToken.token_type,
            func.count(BlacklistedToken.id)
        ).filter(
            BlacklistedToken.revoked_at >= cutoff_time
        )
        
        if user_id:
            type_breakdown = type_breakdown.filter(BlacklistedToken.user_id == user_id)
        
        type_breakdown = type_breakdown.group_by(BlacklistedToken.token_type).all()
        
        # Reason breakdown
        reason_breakdown = self.db.query(
            BlacklistedToken.revocation_reason,
            func.count(BlacklistedToken.id)
        ).filter(
            BlacklistedToken.revoked_at >= cutoff_time
        )
        
        if user_id:
            reason_breakdown = reason_breakdown.filter(BlacklistedToken.user_id == user_id)
        
        reason_breakdown = reason_breakdown.group_by(
            BlacklistedToken.revocation_reason
        ).all()
        
        return {
            "total_blacklisted": total_blacklisted,
            "type_breakdown": {
                token_type: count for token_type, count in type_breakdown
            },
            "reason_breakdown": {
                reason: count for reason, count in reason_breakdown
            }
        }


class TokenRevocationRepository(BaseRepository[TokenRevocation]):
    """
    Repository for token revocation audit trail.
    """

    def __init__(self, db: Session):
        super().__init__(TokenRevocation, db)

    def record_revocation(
        self,
        user_id: UUID,
        revocation_type: str,
        revocation_reason: str,
        tokens_revoked_count: int,
        initiated_by_user_id: Optional[UUID] = None,
        is_forced: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        affected_token_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TokenRevocation:
        """
        Record token revocation event.
        
        Args:
            user_id: User whose tokens were revoked
            revocation_type: Type (single, session, all_tokens)
            revocation_reason: Reason for revocation
            tokens_revoked_count: Number of tokens revoked
            initiated_by_user_id: Who initiated revocation
            is_forced: Whether forced by admin
            ip_address: IP address
            user_agent: User agent
            affected_token_ids: List of affected JTIs
            metadata: Additional metadata
            
        Returns:
            Created TokenRevocation instance
        """
        revocation = TokenRevocation(
            user_id=user_id,
            revocation_type=revocation_type,
            revocation_reason=revocation_reason,
            tokens_revoked_count=tokens_revoked_count,
            initiated_by_user_id=initiated_by_user_id,
            is_forced=is_forced,
            ip_address=ip_address,
            user_agent=user_agent,
            affected_token_ids=affected_token_ids,
            metadata=metadata,
        )
        
        self.db.add(revocation)
        self.db.commit()
        self.db.refresh(revocation)
        return revocation

    def find_user_revocations(
        self,
        user_id: UUID,
        revocation_type: Optional[str] = None,
        limit: int = 50
    ) -> List[TokenRevocation]:
        """Get revocation history for user."""
        query = self.db.query(TokenRevocation).filter(
            TokenRevocation.user_id == user_id
        )
        
        if revocation_type:
            query = query.filter(TokenRevocation.revocation_type == revocation_type)
        
        return query.order_by(desc(TokenRevocation.created_at)).limit(limit).all()

    def find_forced_revocations(
        self,
        days: int = 30
    ) -> List[TokenRevocation]:
        """Get all forced revocations (admin actions)."""
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        return self.db.query(TokenRevocation).filter(
            and_(
                TokenRevocation.is_forced == True,
                TokenRevocation.created_at >= cutoff_time
            )
        ).order_by(desc(TokenRevocation.created_at)).all()

    def get_revocation_statistics(
        self,
        user_id: Optional[UUID] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get revocation statistics.
        
        Args:
            user_id: Filter by user (optional)
            days: Number of days to analyze
            
        Returns:
            Dictionary with revocation statistics
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        query = self.db.query(TokenRevocation).filter(
            TokenRevocation.created_at >= cutoff_time
        )
        
        if user_id:
            query = query.filter(TokenRevocation.user_id == user_id)
        
        total_revocations = query.count()
        
        forced_revocations = self.db.query(
            func.count(TokenRevocation.id)
        ).filter(
            and_(
                TokenRevocation.is_forced == True,
                TokenRevocation.created_at >= cutoff_time
            )
        )
        
        if user_id:
            forced_revocations = forced_revocations.filter(
                TokenRevocation.user_id == user_id
            )
        
        forced_revocations = forced_revocations.scalar() or 0
        
        # Type breakdown
        type_breakdown = self.db.query(
            TokenRevocation.revocation_type,
            func.count(TokenRevocation.id)
        ).filter(
            TokenRevocation.created_at >= cutoff_time
        )
        
        if user_id:
            type_breakdown = type_breakdown.filter(TokenRevocation.user_id == user_id)
        
        type_breakdown = type_breakdown.group_by(
            TokenRevocation.revocation_type
        ).all()
        
        # Total tokens revoked
        total_tokens_revoked = self.db.query(
            func.sum(TokenRevocation.tokens_revoked_count)
        ).filter(
            TokenRevocation.created_at >= cutoff_time
        )
        
        if user_id:
            total_tokens_revoked = total_tokens_revoked.filter(
                TokenRevocation.user_id == user_id
            )
        
        total_tokens_revoked = total_tokens_revoked.scalar() or 0
        
        return {
            "total_revocations": total_revocations,
            "forced_revocations": forced_revocations,
            "total_tokens_revoked": total_tokens_revoked,
            "type_breakdown": {
                rev_type: count for rev_type, count in type_breakdown
            },
            "average_tokens_per_revocation": (
                total_tokens_revoked / total_revocations
            ) if total_revocations > 0 else 0
        }


class SecurityEventRepository(BaseRepository[SecurityEvent]):
    """
    Repository for security event tracking and monitoring.
    """

    def __init__(self, db: Session):
        super().__init__(SecurityEvent, db)

    def record_event(
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
        risk_score: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SecurityEvent:
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
            metadata: Additional metadata
            
        Returns:
            Created SecurityEvent instance
        """
        event = SecurityEvent(
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            country=country,
            city=city,
            event_data=event_data,
            risk_score=risk_score,
            metadata=metadata,
        )
        
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def find_user_events(
        self,
        user_id: UUID,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[SecurityEvent]:
        """Get security events for user."""
        query = self.db.query(SecurityEvent).filter(
            SecurityEvent.user_id == user_id
        )
        
        if event_type:
            query = query.filter(SecurityEvent.event_type == event_type)
        
        if severity:
            query = query.filter(SecurityEvent.severity == severity)
        
        return query.order_by(desc(SecurityEvent.created_at)).limit(limit).all()

    def find_high_risk_events(
        self,
        min_risk_score: int = 70,
        hours: int = 24,
        unresolved_only: bool = True
    ) -> List[SecurityEvent]:
        """Find high-risk security events."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = self.db.query(SecurityEvent).filter(
            and_(
                SecurityEvent.risk_score >= min_risk_score,
                SecurityEvent.created_at >= cutoff_time
            )
        )
        
        if unresolved_only:
            query = query.filter(SecurityEvent.is_resolved == False)
        
        return query.order_by(desc(SecurityEvent.risk_score)).all()

    def find_critical_events(
        self,
        hours: int = 24,
        unresolved_only: bool = True
    ) -> List[SecurityEvent]:
        """Find critical security events."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = self.db.query(SecurityEvent).filter(
            and_(
                SecurityEvent.severity == "critical",
                SecurityEvent.created_at >= cutoff_time
            )
        )
        
        if unresolved_only:
            query = query.filter(SecurityEvent.is_resolved == False)
        
        return query.order_by(desc(SecurityEvent.created_at)).all()

    def find_events_by_ip(
        self,
        ip_address: str,
        hours: int = 24
    ) -> List[SecurityEvent]:
        """Find all events from an IP address."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        return self.db.query(SecurityEvent).filter(
            and_(
                SecurityEvent.ip_address == ip_address,
                SecurityEvent.created_at >= cutoff_time
            )
        ).order_by(desc(SecurityEvent.created_at)).all()

    def resolve_event(
        self,
        event_id: UUID,
        resolved_by_user_id: UUID,
        resolution_note: Optional[str] = None
    ) -> bool:
        """Mark security event as resolved."""
        event = self.find_by_id(event_id)
        if event and not event.is_resolved:
            event.resolve(resolved_by_user_id, resolution_note)
            self.db.commit()
            return True
        return False

    def bulk_resolve_events(
        self,
        event_ids: List[UUID],
        resolved_by_user_id: UUID,
        resolution_note: Optional[str] = None
    ) -> int:
        """Resolve multiple security events."""
        count = self.db.query(SecurityEvent).filter(
            and_(
                SecurityEvent.id.in_(event_ids),
                SecurityEvent.is_resolved == False
            )
        ).update({
            "is_resolved": True,
            "resolved_at": datetime.utcnow(),
            "resolved_by_user_id": resolved_by_user_id,
            "resolution_note": resolution_note
        }, synchronize_session=False)
        
        self.db.commit()
        return count

    def get_event_statistics(
        self,
        user_id: Optional[UUID] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get security event statistics.
        
        Args:
            user_id: Filter by user (optional)
            days: Number of days to analyze
            
        Returns:
            Dictionary with event statistics
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        query = self.db.query(SecurityEvent).filter(
            SecurityEvent.created_at >= cutoff_time
        )
        
        if user_id:
            query = query.filter(SecurityEvent.user_id == user_id)
        
        total_events = query.count()
        
        # Severity breakdown
        severity_breakdown = self.db.query(
            SecurityEvent.severity,
            func.count(SecurityEvent.id)
        ).filter(
            SecurityEvent.created_at >= cutoff_time
        )
        
        if user_id:
            severity_breakdown = severity_breakdown.filter(
                SecurityEvent.user_id == user_id
            )
        
        severity_breakdown = severity_breakdown.group_by(
            SecurityEvent.severity
        ).all()
        
        # Event type breakdown
        type_breakdown = self.db.query(
            SecurityEvent.event_type,
            func.count(SecurityEvent.id)
        ).filter(
            SecurityEvent.created_at >= cutoff_time
        )
        
        if user_id:
            type_breakdown = type_breakdown.filter(SecurityEvent.user_id == user_id)
        
        type_breakdown = type_breakdown.group_by(SecurityEvent.event_type).all()
        
        # Unresolved events
        unresolved_count = self.db.query(
            func.count(SecurityEvent.id)
        ).filter(
            and_(
                SecurityEvent.is_resolved == False,
                SecurityEvent.created_at >= cutoff_time
            )
        )
        
        if user_id:
            unresolved_count = unresolved_count.filter(SecurityEvent.user_id == user_id)
        
        unresolved_count = unresolved_count.scalar() or 0
        
        # Average risk score
        avg_risk_score = self.db.query(
            func.avg(SecurityEvent.risk_score)
        ).filter(
            and_(
                SecurityEvent.risk_score.isnot(None),
                SecurityEvent.created_at >= cutoff_time
            )
        )
        
        if user_id:
            avg_risk_score = avg_risk_score.filter(SecurityEvent.user_id == user_id)
        
        avg_risk_score = avg_risk_score.scalar() or 0
        
        return {
            "total_events": total_events,
            "unresolved_events": unresolved_count,
            "resolution_rate": (
                (total_events - unresolved_count) / total_events * 100
            ) if total_events > 0 else 0,
            "average_risk_score": round(avg_risk_score, 2),
            "severity_breakdown": {
                severity: count for severity, count in severity_breakdown
            },
            "type_breakdown": {
                event_type: count for event_type, count in type_breakdown
            }
        }

    def get_threat_intelligence(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get threat intelligence summary.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with threat intelligence
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        # Top threatening IPs
        top_ips = self.db.query(
            SecurityEvent.ip_address,
            func.count(SecurityEvent.id).label("event_count"),
            func.avg(SecurityEvent.risk_score).label("avg_risk")
        ).filter(
            and_(
                SecurityEvent.ip_address.isnot(None),
                SecurityEvent.created_at >= cutoff_time
            )
        ).group_by(
            SecurityEvent.ip_address
        ).order_by(
            desc("event_count")
        ).limit(10).all()
        
        # Top threat types
        top_threats = self.db.query(
            SecurityEvent.event_type,
            func.count(SecurityEvent.id).label("count"),
            func.avg(SecurityEvent.risk_score).label("avg_risk")
        ).filter(
            SecurityEvent.created_at >= cutoff_time
        ).group_by(
            SecurityEvent.event_type
        ).order_by(
            desc("count")
        ).limit(10).all()
        
        # Geographic distribution
        geo_distribution = self.db.query(
            SecurityEvent.country,
            func.count(SecurityEvent.id).label("count")
        ).filter(
            and_(
                SecurityEvent.country.isnot(None),
                SecurityEvent.created_at >= cutoff_time
            )
        ).group_by(
            SecurityEvent.country
        ).order_by(
            desc("count")
        ).all()
        
        return {
            "top_threatening_ips": [
                {
                    "ip_address": ip,
                    "event_count": count,
                    "average_risk_score": round(avg_risk, 2)
                }
                for ip, count, avg_risk in top_ips
            ],
            "top_threat_types": [
                {
                    "event_type": event_type,
                    "count": count,
                    "average_risk_score": round(avg_risk, 2)
                }
                for event_type, count, avg_risk in top_threats
            ],
            "geographic_distribution": [
                {
                    "country": country,
                    "event_count": count
                }
                for country, count in geo_distribution
            ]
        }

    def cleanup_old_events(
        self,
        days_old: int = 90,
        keep_critical: bool = True
    ) -> int:
        """
        Clean up old security events.
        
        Args:
            days_old: Remove events older than this many days
            keep_critical: Keep critical events regardless of age
            
        Returns:
            Number of events deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        query = self.db.query(SecurityEvent).filter(
            SecurityEvent.created_at < cutoff_date
        )
        
        if keep_critical:
            query = query.filter(SecurityEvent.severity != "critical")
        
        count = query.delete(synchronize_session=False)
        self.db.commit()
        return count