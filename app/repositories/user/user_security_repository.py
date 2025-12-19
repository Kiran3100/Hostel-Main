"""
User Security Repository - Login history and password history management.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Session

from app.models.user import LoginHistory, PasswordHistory
from app.repositories.base.base_repository import BaseRepository


class UserSecurityRepository:
    """
    Repository for security-related entities (LoginHistory, PasswordHistory)
    with analytics and monitoring capabilities.
    """

    def __init__(self, db: Session):
        self.db = db

    # ==================== Login History ====================

    def create_login_attempt(
        self,
        user_id: Optional[str],
        email_attempted: str,
        is_successful: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_info: Optional[Dict] = None,
        geolocation: Optional[Dict] = None,
        failure_reason: Optional[str] = None,
        auth_method: str = "password",
        session_id: Optional[str] = None
    ) -> LoginHistory:
        """
        Create a login attempt record.
        
        Args:
            user_id: User ID (None for failed attempts with invalid user)
            email_attempted: Email used in attempt
            is_successful: Success status
            ip_address: IP address
            user_agent: User agent string
            device_info: Parsed device information
            geolocation: GeoIP location data
            failure_reason: Reason for failure
            auth_method: Authentication method
            session_id: Created session ID if successful
            
        Returns:
            Created LoginHistory
        """
        login_record = LoginHistory(
            user_id=user_id,
            email_attempted=email_attempted,
            is_successful=is_successful,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info,
            geolocation=geolocation,
            failure_reason=failure_reason,
            auth_method=auth_method,
            session_id=session_id,
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(login_record)
        self.db.commit()
        self.db.refresh(login_record)
        
        return login_record

    def find_user_login_history(
        self,
        user_id: str,
        successful_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[LoginHistory]:
        """
        Get login history for a user.
        
        Args:
            user_id: User ID
            successful_only: Only successful logins
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of login attempts
        """
        query = self.db.query(LoginHistory).filter(
            LoginHistory.user_id == user_id
        )
        
        if successful_only:
            query = query.filter(LoginHistory.is_successful == True)
        
        return query.order_by(
            desc(LoginHistory.created_at)
        ).limit(limit).offset(offset).all()

    def find_failed_login_attempts(
        self,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        hours: int = 24
    ) -> List[LoginHistory]:
        """
        Find failed login attempts with filters.
        
        Args:
            user_id: Optional user ID filter
            email: Optional email filter
            ip_address: Optional IP filter
            hours: Time window in hours
            
        Returns:
            List of failed attempts
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        query = self.db.query(LoginHistory).filter(
            LoginHistory.is_successful == False,
            LoginHistory.created_at >= cutoff
        )
        
        if user_id:
            query = query.filter(LoginHistory.user_id == user_id)
        
        if email:
            query = query.filter(LoginHistory.email_attempted == email)
        
        if ip_address:
            query = query.filter(LoginHistory.ip_address == ip_address)
        
        return query.order_by(desc(LoginHistory.created_at)).all()

    def find_suspicious_login_attempts(
        self,
        limit: int = 100
    ) -> List[LoginHistory]:
        """
        Find login attempts flagged as suspicious.
        
        Args:
            limit: Maximum results
            
        Returns:
            List of suspicious attempts
        """
        return self.db.query(LoginHistory).filter(
            LoginHistory.is_suspicious == True
        ).order_by(desc(LoginHistory.created_at)).limit(limit).all()

    def mark_login_suspicious(
        self,
        login_id: str,
        risk_score: int,
        security_flags: Optional[Dict] = None
    ) -> LoginHistory:
        """
        Mark a login attempt as suspicious.
        
        Args:
            login_id: Login history ID
            risk_score: Risk score (0-100)
            security_flags: Security flags and anomalies
            
        Returns:
            Updated LoginHistory
        """
        login_record = self.db.query(LoginHistory).filter(
            LoginHistory.id == login_id
        ).first()
        
        if login_record:
            login_record.is_suspicious = True
            login_record.risk_score = risk_score
            login_record.security_flags = security_flags
            
            self.db.commit()
            self.db.refresh(login_record)
        
        return login_record

    def get_login_statistics(
        self,
        user_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get login statistics.
        
        Args:
            user_id: Optional user ID filter
            days: Number of days to analyze
            
        Returns:
            Dictionary with login metrics
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        query_base = self.db.query(LoginHistory).filter(
            LoginHistory.created_at >= cutoff
        )
        
        if user_id:
            query_base = query_base.filter(LoginHistory.user_id == user_id)
        
        total_attempts = query_base.count()
        
        successful = query_base.filter(
            LoginHistory.is_successful == True
        ).count()
        
        failed = query_base.filter(
            LoginHistory.is_successful == False
        ).count()
        
        suspicious = query_base.filter(
            LoginHistory.is_suspicious == True
        ).count()
        
        # Authentication methods distribution
        auth_methods = self.db.query(
            LoginHistory.auth_method,
            func.count(LoginHistory.id).label('count')
        ).filter(
            LoginHistory.created_at >= cutoff,
            LoginHistory.user_id == user_id if user_id else True
        ).group_by(LoginHistory.auth_method).all()
        
        # Failure reasons
        failure_reasons = self.db.query(
            LoginHistory.failure_reason,
            func.count(LoginHistory.id).label('count')
        ).filter(
            LoginHistory.created_at >= cutoff,
            LoginHistory.is_successful == False,
            LoginHistory.user_id == user_id if user_id else True
        ).group_by(LoginHistory.failure_reason).all()
        
        return {
            "total_attempts": total_attempts,
            "successful_logins": successful,
            "failed_logins": failed,
            "suspicious_attempts": suspicious,
            "success_rate": (successful / total_attempts * 100) if total_attempts > 0 else 0,
            "by_auth_method": {method: count for method, count in auth_methods},
            "failure_reasons": {
                reason: count for reason, count in failure_reasons if reason
            }
        }

    def detect_brute_force_attempt(
        self,
        email: str,
        minutes: int = 15,
        threshold: int = 5
    ) -> bool:
        """
        Detect potential brute force attack.
        
        Args:
            email: Email address
            minutes: Time window in minutes
            threshold: Number of failed attempts threshold
            
        Returns:
            True if brute force detected
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        
        failed_count = self.db.query(func.count(LoginHistory.id)).filter(
            LoginHistory.email_attempted == email,
            LoginHistory.is_successful == False,
            LoginHistory.created_at >= cutoff
        ).scalar()
        
        return failed_count >= threshold

    # ==================== Password History ====================

    def create_password_history(
        self,
        user_id: str,
        password_hash: str,
        changed_by: Optional[str] = None,
        change_reason: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> PasswordHistory:
        """
        Create a password history record.
        
        Args:
            user_id: User ID
            password_hash: Password hash
            changed_by: User who initiated change
            change_reason: Reason for change
            ip_address: IP address of change
            
        Returns:
            Created PasswordHistory
        """
        password_record = PasswordHistory(
            user_id=user_id,
            password_hash=password_hash,
            changed_by=changed_by,
            change_reason=change_reason,
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(password_record)
        self.db.commit()
        self.db.refresh(password_record)
        
        return password_record

    def find_user_password_history(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[PasswordHistory]:
        """
        Get password change history for a user.
        
        Args:
            user_id: User ID
            limit: Maximum results
            
        Returns:
            List of password history records
        """
        return self.db.query(PasswordHistory).filter(
            PasswordHistory.user_id == user_id
        ).order_by(desc(PasswordHistory.created_at)).limit(limit).all()

    def check_password_reuse(
        self,
        user_id: str,
        new_password_hash: str,
        history_limit: int = 5
    ) -> bool:
        """
        Check if password has been used recently.
        
        Args:
            user_id: User ID
            new_password_hash: New password hash to check
            history_limit: Number of previous passwords to check
            
        Returns:
            True if password was used before
        """
        recent_passwords = self.db.query(PasswordHistory.password_hash).filter(
            PasswordHistory.user_id == user_id
        ).order_by(desc(PasswordHistory.created_at)).limit(history_limit).all()
        
        for (stored_hash,) in recent_passwords:
            if stored_hash == new_password_hash:
                return True
        
        return False

    def get_password_change_statistics(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get password change statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with password change metrics
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        total_changes = self.db.query(func.count(PasswordHistory.id)).filter(
            PasswordHistory.created_at >= cutoff
        ).scalar()
        
        # Changes by reason
        by_reason = self.db.query(
            PasswordHistory.change_reason,
            func.count(PasswordHistory.id).label('count')
        ).filter(
            PasswordHistory.created_at >= cutoff
        ).group_by(PasswordHistory.change_reason).all()
        
        # Admin-initiated changes
        admin_changes = self.db.query(func.count(PasswordHistory.id)).filter(
            PasswordHistory.created_at >= cutoff,
            PasswordHistory.changed_by.isnot(None),
            PasswordHistory.user_id != PasswordHistory.changed_by
        ).scalar()
        
        return {
            "total_password_changes": total_changes,
            "admin_initiated_changes": admin_changes,
            "user_initiated_changes": total_changes - admin_changes,
            "by_reason": {reason: count for reason, count in by_reason if reason}
        }

    def cleanup_old_password_history(
        self,
        months: int = 12,
        keep_minimum: int = 5
    ) -> int:
        """
        Clean up old password history records.
        
        Args:
            months: Keep records newer than X months
            keep_minimum: Minimum records to keep per user
            
        Returns:
            Count of deleted records
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
        
        # Get users with more than minimum records
        users_with_excess = self.db.query(
            PasswordHistory.user_id,
            func.count(PasswordHistory.id).label('count')
        ).group_by(PasswordHistory.user_id).having(
            func.count(PasswordHistory.id) > keep_minimum
        ).all()
        
        deleted_count = 0
        
        for user_id, count in users_with_excess:
            # Delete old records beyond the minimum
            records_to_delete = self.db.query(PasswordHistory).filter(
                PasswordHistory.user_id == user_id,
                PasswordHistory.created_at < cutoff
            ).order_by(PasswordHistory.created_at.asc()).limit(
                count - keep_minimum
            ).all()
            
            for record in records_to_delete:
                self.db.delete(record)
                deleted_count += 1
        
        self.db.commit()
        return deleted_count

    # ==================== Combined Security Analytics ====================

    def get_comprehensive_security_report(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive security report for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with complete security overview
        """
        # Login statistics
        login_stats = self.get_login_statistics(user_id=user_id, days=30)
        
        # Recent failed attempts
        recent_failures = self.find_failed_login_attempts(
            user_id=user_id,
            hours=24
        )
        
        # Password history
        password_history = self.find_user_password_history(user_id, limit=5)
        
        # Last successful login
        last_login = self.db.query(LoginHistory).filter(
            LoginHistory.user_id == user_id,
            LoginHistory.is_successful == True
        ).order_by(desc(LoginHistory.created_at)).first()
        
        # Suspicious activity count
        suspicious_count = self.db.query(func.count(LoginHistory.id)).filter(
            LoginHistory.user_id == user_id,
            LoginHistory.is_suspicious == True
        ).scalar()
        
        return {
            "user_id": user_id,
            "login_statistics": login_stats,
            "recent_failed_attempts_24h": len(recent_failures),
            "password_changes_count": len(password_history),
            "last_password_change": password_history[0].created_at if password_history else None,
            "last_successful_login": last_login.created_at if last_login else None,
            "last_login_ip": last_login.ip_address if last_login else None,
            "total_suspicious_attempts": suspicious_count
        }