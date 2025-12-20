"""
Token Blacklist Service
Token revocation, blacklisting, and audit trail management.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.auth import (
    BlacklistedTokenRepository,
    TokenRevocationRepository,
    SecurityEventRepository,
)
from app.core.exceptions import (
    TokenRevokedError,
    TokenBlacklistError,
)


class TokenBlacklistService:
    """
    Service for token blacklisting and revocation management.
    """

    def __init__(self, db: Session):
        self.db = db
        self.blacklist_repo = BlacklistedTokenRepository(db)
        self.revocation_repo = TokenRevocationRepository(db)
        self.security_event_repo = SecurityEventRepository(db)

    # ==================== Token Blacklisting ====================

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
    ) -> bool:
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
            Success status
        """
        try:
            # Check if already blacklisted
            if self.is_token_blacklisted(jti):
                return True
            
            # Add to blacklist
            self.blacklist_repo.blacklist_token(
                jti=jti,
                token_type=token_type,
                token_hash=token_hash,
                user_id=user_id,
                expires_at=expires_at,
                revocation_reason=revocation_reason,
                revoked_by_user_id=revoked_by_user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=metadata
            )
            
            # Record security event if user-related
            if user_id:
                self.security_event_repo.record_event(
                    event_type="token_blacklisted",
                    severity="low",
                    description=f"Token blacklisted: {revocation_reason}",
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    event_data={
                        "token_type": token_type,
                        "jti": jti,
                        "reason": revocation_reason
                    }
                )
            
            return True
            
        except Exception as e:
            raise TokenBlacklistError(f"Failed to blacklist token: {str(e)}")

    def bulk_blacklist_tokens(
        self,
        jtis: List[str],
        token_type: str,
        user_id: UUID,
        revocation_reason: str,
        expires_at: datetime,
        revoked_by_user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
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
            ip_address: IP address
            user_agent: User agent
            
        Returns:
            Number of tokens blacklisted
        """
        count = self.blacklist_repo.bulk_blacklist_tokens(
            jtis=jtis,
            token_type=token_type,
            user_id=user_id,
            revocation_reason=revocation_reason,
            expires_at=expires_at,
            revoked_by_user_id=revoked_by_user_id
        )
        
        # Record revocation event
        if count > 0:
            self.revocation_repo.record_revocation(
                user_id=user_id,
                revocation_type="bulk",
                revocation_reason=revocation_reason,
                tokens_revoked_count=count,
                initiated_by_user_id=revoked_by_user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                affected_token_ids=jtis
            )
            
            # Record security event
            self.security_event_repo.record_event(
                event_type="bulk_token_revocation",
                severity="medium",
                description=f"Bulk token revocation: {count} tokens",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                event_data={
                    "token_count": count,
                    "reason": revocation_reason
                }
            )
        
        return count

    def is_token_blacklisted(self, jti: str) -> bool:
        """
        Check if token is blacklisted.
        
        Args:
            jti: JWT ID to check
            
        Returns:
            True if token is blacklisted
        """
        return self.blacklist_repo.is_blacklisted(jti)

    def get_blacklisted_token(self, jti: str) -> Optional[Any]:
        """
        Get blacklisted token details.
        
        Args:
            jti: JWT ID
            
        Returns:
            BlacklistedToken or None
        """
        return self.blacklist_repo.find_by_jti(jti)

    # ==================== Token Revocation ====================

    def revoke_user_tokens(
        self,
        user_id: UUID,
        revocation_type: str,
        revocation_reason: str,
        initiated_by_user_id: Optional[UUID] = None,
        is_forced: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Revoke tokens for a user.
        
        Args:
            user_id: User identifier
            revocation_type: Type (single, session, all_tokens)
            revocation_reason: Reason for revocation
            initiated_by_user_id: Who initiated revocation
            is_forced: Whether forced by admin
            ip_address: IP address
            user_agent: User agent
            
        Returns:
            Dictionary with revocation results
        """
        from app.models.auth import SessionToken, RefreshToken
        
        # Get all user tokens
        access_tokens = self.db.query(SessionToken).join(
            SessionToken.session
        ).filter(
            SessionToken.session.has(user_id=user_id),
            SessionToken.is_revoked == False
        ).all()
        
        refresh_tokens = self.db.query(RefreshToken).join(
            RefreshToken.session
        ).filter(
            RefreshToken.session.has(user_id=user_id),
            RefreshToken.is_revoked == False
        ).all()
        
        total_tokens = len(access_tokens) + len(refresh_tokens)
        
        if total_tokens == 0:
            return {
                "tokens_revoked": 0,
                "message": "No active tokens found"
            }
        
        # Blacklist all tokens
        for token in access_tokens:
            self.blacklist_token(
                jti=token.jti,
                token_type="access",
                token_hash=token.token_hash,
                user_id=user_id,
                expires_at=token.expires_at,
                revocation_reason=revocation_reason,
                revoked_by_user_id=initiated_by_user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
        
        for token in refresh_tokens:
            self.blacklist_token(
                jti=token.jti,
                token_type="refresh",
                token_hash=token.token_hash,
                user_id=user_id,
                expires_at=token.expires_at,
                revocation_reason=revocation_reason,
                revoked_by_user_id=initiated_by_user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
        
        # Record revocation
        self.revocation_repo.record_revocation(
            user_id=user_id,
            revocation_type=revocation_type,
            revocation_reason=revocation_reason,
            tokens_revoked_count=total_tokens,
            initiated_by_user_id=initiated_by_user_id,
            is_forced=is_forced,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Record security event
        severity = "high" if is_forced else "medium"
        self.security_event_repo.record_event(
            event_type="user_tokens_revoked",
            severity=severity,
            description=f"All user tokens revoked: {revocation_reason}",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "revocation_type": revocation_type,
                "tokens_revoked": total_tokens,
                "is_forced": is_forced
            }
        )
        
        return {
            "tokens_revoked": total_tokens,
            "access_tokens_revoked": len(access_tokens),
            "refresh_tokens_revoked": len(refresh_tokens),
            "revocation_type": revocation_type,
            "is_forced": is_forced
        }

    def revoke_session_tokens(
        self,
        session_id: UUID,
        revocation_reason: str,
        initiated_by_user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None
    ) -> int:
        """
        Revoke all tokens for a specific session.
        
        Args:
            session_id: Session identifier
            revocation_reason: Reason for revocation
            initiated_by_user_id: Who initiated revocation
            ip_address: IP address
            
        Returns:
            Number of tokens revoked
        """
        from app.models.auth import SessionToken, RefreshToken, UserSession
        
        # Get session
        session = self.db.query(UserSession).filter(
            UserSession.id == session_id
        ).first()
        
        if not session:
            return 0
        
        # Get session tokens
        access_tokens = self.db.query(SessionToken).filter(
            SessionToken.session_id == session_id,
            SessionToken.is_revoked == False
        ).all()
        
        refresh_tokens = self.db.query(RefreshToken).filter(
            RefreshToken.session_id == session_id,
            RefreshToken.is_revoked == False
        ).all()
        
        total_tokens = len(access_tokens) + len(refresh_tokens)
        
        if total_tokens == 0:
            return 0
        
        # Blacklist all tokens
        for token in access_tokens:
            self.blacklist_token(
                jti=token.jti,
                token_type="access",
                token_hash=token.token_hash,
                user_id=session.user_id,
                expires_at=token.expires_at,
                revocation_reason=revocation_reason,
                revoked_by_user_id=initiated_by_user_id,
                ip_address=ip_address
            )
        
        for token in refresh_tokens:
            self.blacklist_token(
                jti=token.jti,
                token_type="refresh",
                token_hash=token.token_hash,
                user_id=session.user_id,
                expires_at=token.expires_at,
                revocation_reason=revocation_reason,
                revoked_by_user_id=initiated_by_user_id,
                ip_address=ip_address
            )
        
        # Record revocation
        self.revocation_repo.record_revocation(
            user_id=session.user_id,
            revocation_type="session",
            revocation_reason=revocation_reason,
            tokens_revoked_count=total_tokens,
            initiated_by_user_id=initiated_by_user_id,
            ip_address=ip_address
        )
        
        return total_tokens

    # ==================== Revocation History ====================

    def get_user_revocations(
        self,
        user_id: UUID,
        revocation_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get revocation history for user.
        
        Args:
            user_id: User identifier
            revocation_type: Filter by type
            limit: Maximum records to return
            
        Returns:
            List of revocation records
        """
        revocations = self.revocation_repo.find_user_revocations(
            user_id=user_id,
            revocation_type=revocation_type,
            limit=limit
        )
        
        return [
            {
                "revocation_type": rev.revocation_type,
                "revocation_reason": rev.revocation_reason,
                "tokens_revoked_count": rev.tokens_revoked_count,
                "is_forced": rev.is_forced,
                "created_at": rev.created_at,
                "initiated_by": rev.initiated_by_user_id,
                "ip_address": rev.ip_address
            }
            for rev in revocations
        ]

    def get_forced_revocations(
        self,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get all forced revocations (admin actions).
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of forced revocation records
        """
        revocations = self.revocation_repo.find_forced_revocations(days=days)
        
        return [
            {
                "user_id": rev.user_id,
                "revocation_type": rev.revocation_type,
                "revocation_reason": rev.revocation_reason,
                "tokens_revoked_count": rev.tokens_revoked_count,
                "created_at": rev.created_at,
                "initiated_by": rev.initiated_by_user_id,
                "ip_address": rev.ip_address
            }
            for rev in revocations
        ]

    # ==================== Blacklist Management ====================

    def get_user_blacklisted_tokens(
        self,
        user_id: UUID,
        token_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get blacklisted tokens for user.
        
        Args:
            user_id: User identifier
            token_type: Filter by token type
            
        Returns:
            List of blacklisted tokens
        """
        tokens = self.blacklist_repo.find_user_blacklisted_tokens(
            user_id=user_id,
            token_type=token_type
        )
        
        return [
            {
                "jti": token.jti,
                "token_type": token.token_type,
                "revoked_at": token.revoked_at,
                "revocation_reason": token.revocation_reason,
                "expires_at": token.expires_at,
                "revoked_by": token.revoked_by_user_id,
                "ip_address": token.ip_address
            }
            for token in tokens
        ]

    def get_active_blacklist_count(self) -> Dict[str, int]:
        """
        Get count of currently active blacklisted tokens.
        
        Returns:
            Dictionary with blacklist counts
        """
        from app.models.auth import BlacklistedToken
        
        now = datetime.utcnow()
        
        total = self.db.query(BlacklistedToken).filter(
            BlacklistedToken.expires_at > now
        ).count()
        
        access_tokens = self.db.query(BlacklistedToken).filter(
            BlacklistedToken.token_type == "access",
            BlacklistedToken.expires_at > now
        ).count()
        
        refresh_tokens = self.db.query(BlacklistedToken).filter(
            BlacklistedToken.token_type == "refresh",
            BlacklistedToken.expires_at > now
        ).count()
        
        return {
            "total_active": total,
            "access_tokens": access_tokens,
            "refresh_tokens": refresh_tokens
        }

    # ==================== Statistics ====================

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
        return self.blacklist_repo.get_blacklist_statistics(
            user_id=user_id,
            days=days
        )

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
        return self.revocation_repo.get_revocation_statistics(
            user_id=user_id,
            days=days
        )

    def get_comprehensive_statistics(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive blacklist and revocation statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with comprehensive statistics
        """
        blacklist_stats = self.get_blacklist_statistics(days=days)
        revocation_stats = self.get_revocation_statistics(days=days)
        active_counts = self.get_active_blacklist_count()
        
        return {
            "period_days": days,
            "blacklist_statistics": blacklist_stats,
            "revocation_statistics": revocation_stats,
            "active_blacklist": active_counts,
            "summary": {
                "total_tokens_revoked": revocation_stats.get("total_tokens_revoked", 0),
                "total_revocation_events": revocation_stats.get("total_revocations", 0),
                "forced_revocations": revocation_stats.get("forced_revocations", 0),
                "currently_blacklisted": active_counts.get("total_active", 0)
            }
        }

    # ==================== Cleanup ====================

    def cleanup_expired_blacklist(self, days_old: int = 7) -> int:
        """
        Clean up expired blacklisted tokens.
        
        Args:
            days_old: Remove tokens expired more than this many days ago
            
        Returns:
            Number of tokens removed
        """
        count = self.blacklist_repo.cleanup_expired_tokens(days_old)
        
        if count > 0:
            self.security_event_repo.record_event(
                event_type="blacklist_cleanup",
                severity="low",
                description=f"Cleaned up {count} expired blacklisted tokens",
                event_data={"tokens_cleaned": count, "days_old": days_old}
            )
        
        return count

    def cleanup_old_revocation_records(self, days_old: int = 90) -> int:
        """
        Clean up old revocation audit records.
        
        Args:
            days_old: Remove records older than this many days
            
        Returns:
            Number of records removed
        """
        from app.models.auth import TokenRevocation
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        count = self.db.query(TokenRevocation).filter(
            TokenRevocation.created_at < cutoff_date
        ).delete(synchronize_session=False)
        
        self.db.commit()
        
        return count

    # ==================== Emergency Functions ====================

    def emergency_revoke_all_tokens(
        self,
        reason: str,
        admin_user_id: UUID,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Emergency function to revoke ALL tokens in the system.
        Use with extreme caution!
        
        Args:
            reason: Reason for emergency revocation
            admin_user_id: Admin who initiated
            ip_address: IP address
            
        Returns:
            Dictionary with revocation results
        """
        from app.models.auth import SessionToken, RefreshToken
        
        # Get all active tokens
        access_tokens = self.db.query(SessionToken).filter(
            SessionToken.is_revoked == False
        ).all()
        
        refresh_tokens = self.db.query(RefreshToken).filter(
            RefreshToken.is_revoked == False
        ).all()
        
        total_tokens = len(access_tokens) + len(refresh_tokens)
        
        # Revoke all tokens
        for token in access_tokens:
            token.is_revoked = True
            token.revoked_at = datetime.utcnow()
            token.revocation_reason = f"EMERGENCY: {reason}"
        
        for token in refresh_tokens:
            token.is_revoked = True
            token.revoked_at = datetime.utcnow()
            token.revocation_reason = f"EMERGENCY: {reason}"
        
        self.db.commit()
        
        # Record critical security event
        self.security_event_repo.record_event(
            event_type="emergency_token_revocation",
            severity="critical",
            description=f"EMERGENCY: All system tokens revoked - {reason}",
            user_id=admin_user_id,
            ip_address=ip_address,
            event_data={
                "tokens_revoked": total_tokens,
                "reason": reason,
                "admin_user_id": str(admin_user_id)
            },
            risk_score=100
        )
        
        return {
            "emergency_revocation": True,
            "tokens_revoked": total_tokens,
            "access_tokens_revoked": len(access_tokens),
            "refresh_tokens_revoked": len(refresh_tokens),
            "reason": reason,
            "initiated_by": admin_user_id,
            "timestamp": datetime.utcnow()
        }

    def revoke_tokens_by_ip(
        self,
        ip_address: str,
        reason: str,
        admin_user_id: UUID
    ) -> Dict[str, Any]:
        """
        Revoke all tokens from a specific IP address.
        
        Args:
            ip_address: IP address to block
            reason: Reason for revocation
            admin_user_id: Admin who initiated
            
        Returns:
            Dictionary with revocation results
        """
        from app.models.auth import UserSession, SessionToken, RefreshToken
        
        # Find all sessions from this IP
        sessions = self.db.query(UserSession).filter(
            UserSession.ip_address == ip_address,
            UserSession.is_active == True
        ).all()
        
        total_tokens = 0
        affected_users = set()
        
        for session in sessions:
            # Revoke session tokens
            count = self.revoke_session_tokens(
                session_id=session.id,
                revocation_reason=f"IP blocked: {reason}",
                initiated_by_user_id=admin_user_id,
                ip_address=ip_address
            )
            total_tokens += count
            affected_users.add(session.user_id)
        
        # Record security event
        self.security_event_repo.record_event(
            event_type="ip_address_blocked",
            severity="high",
            description=f"All tokens from IP {ip_address} revoked: {reason}",
            ip_address=ip_address,
            event_data={
                "tokens_revoked": total_tokens,
                "sessions_affected": len(sessions),
                "users_affected": len(affected_users),
                "reason": reason
            },
            risk_score=90
        )
        
        return {
            "ip_address": ip_address,
            "tokens_revoked": total_tokens,
            "sessions_affected": len(sessions),
            "users_affected": len(affected_users),
            "reason": reason
        }