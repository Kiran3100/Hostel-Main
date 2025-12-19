"""
Password Reset Repository
Manages password reset tokens, password history, policies, and attempts.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import Session

from app.models.auth import (
    PasswordReset,
    PasswordHistory,
    PasswordPolicy,
    PasswordAttempt,
)
from app.repositories.base.base_repository import BaseRepository


class PasswordResetRepository(BaseRepository[PasswordReset]):
    """
    Repository for password reset token management.
    """

    def __init__(self, db: Session):
        super().__init__(PasswordReset, db)

    def create_reset_token(
        self,
        user_id: UUID,
        token: str,
        token_hash: str,
        expires_in_hours: int = 1,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PasswordReset:
        """
        Create password reset token.
        
        Args:
            user_id: User identifier
            token: Reset token (plain text, will be hashed)
            token_hash: SHA256 hash of token
            expires_in_hours: Token validity period
            ip_address: Request IP address
            user_agent: Request user agent
            metadata: Additional metadata
            
        Returns:
            Created PasswordReset instance
        """
        # Invalidate any existing tokens for this user
        self.invalidate_user_tokens(user_id)
        
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        reset = PasswordReset(
            user_id=user_id,
            token=token,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata,
        )
        
        self.db.add(reset)
        self.db.commit()
        self.db.refresh(reset)
        return reset

    def find_by_token(self, token: str) -> Optional[PasswordReset]:
        """
        Find password reset by token.
        
        Args:
            token: Reset token
            
        Returns:
            PasswordReset or None
        """
        return self.db.query(PasswordReset).filter(
            PasswordReset.token == token
        ).first()

    def find_valid_token(
        self,
        user_id: UUID,
        token_hash: str
    ) -> Optional[PasswordReset]:
        """
        Find valid reset token for user.
        
        Args:
            user_id: User identifier
            token_hash: Token hash to verify
            
        Returns:
            Valid PasswordReset or None
        """
        reset = self.db.query(PasswordReset).filter(
            and_(
                PasswordReset.user_id == user_id,
                PasswordReset.token_hash == token_hash,
                PasswordReset.is_used == False,
                PasswordReset.is_expired == False,
                PasswordReset.expires_at > datetime.utcnow()
            )
        ).first()
        
        # Check expiration
        if reset:
            reset.check_expiration()
            self.db.commit()
            
            if not reset.is_valid():
                return None
        
        return reset

    def verify_and_use_token(
        self,
        token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, Optional[PasswordReset], Optional[str]]:
        """
        Verify and mark reset token as used.
        
        Args:
            token: Reset token to verify
            ip_address: IP address of reset request
            user_agent: User agent of reset request
            
        Returns:
            Tuple of (success, reset_object, error_message)
        """
        reset = self.find_by_token(token)
        
        if not reset:
            return False, None, "Invalid reset token"
        
        if not reset.is_valid():
            return False, None, "Reset token has expired or already been used"
        
        # Mark as used
        reset.mark_as_used(ip_address, user_agent)
        self.db.commit()
        
        return True, reset, None

    def invalidate_user_tokens(self, user_id: UUID) -> int:
        """
        Invalidate all active reset tokens for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Number of tokens invalidated
        """
        count = self.db.query(PasswordReset).filter(
            and_(
                PasswordReset.user_id == user_id,
                PasswordReset.is_used == False,
                PasswordReset.is_expired == False
            )
        ).update({
            "is_expired": True
        })
        
        self.db.commit()
        return count

    def get_reset_statistics(
        self,
        user_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get password reset statistics for a user.
        
        Args:
            user_id: User identifier
            days: Number of days to analyze
            
        Returns:
            Dictionary with reset statistics
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        total_requests = self.db.query(func.count(PasswordReset.id)).filter(
            and_(
                PasswordReset.user_id == user_id,
                PasswordReset.created_at >= cutoff_time
            )
        ).scalar()
        
        successful_resets = self.db.query(func.count(PasswordReset.id)).filter(
            and_(
                PasswordReset.user_id == user_id,
                PasswordReset.is_used == True,
                PasswordReset.created_at >= cutoff_time
            )
        ).scalar()
        
        expired_tokens = self.db.query(func.count(PasswordReset.id)).filter(
            and_(
                PasswordReset.user_id == user_id,
                PasswordReset.is_expired == True,
                PasswordReset.is_used == False,
                PasswordReset.created_at >= cutoff_time
            )
        ).scalar()
        
        return {
            "total_requests": total_requests,
            "successful_resets": successful_resets,
            "expired_tokens": expired_tokens,
            "completion_rate": (successful_resets / total_requests * 100) if total_requests > 0 else 0
        }

    def cleanup_expired_tokens(self, days_old: int = 7) -> int:
        """Clean up old expired tokens."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        count = self.db.query(PasswordReset).filter(
            PasswordReset.expires_at < cutoff_date
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return count


class PasswordHistoryRepository(BaseRepository[PasswordHistory]):
    """
    Repository for password history management.
    """

    def __init__(self, db: Session):
        super().__init__(PasswordHistory, db)

    def add_to_history(
        self,
        user_id: UUID,
        password_hash: str,
        changed_by_user_id: Optional[UUID] = None,
        change_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PasswordHistory:
        """
        Add password to history.
        
        Args:
            user_id: User identifier
            password_hash: Hashed password
            changed_by_user_id: Who changed the password (for admin overrides)
            change_reason: Reason for change
            ip_address: IP address
            user_agent: User agent
            metadata: Additional metadata
            
        Returns:
            Created PasswordHistory instance
        """
        history = PasswordHistory(
            user_id=user_id,
            password_hash=password_hash,
            changed_by_user_id=changed_by_user_id,
            change_reason=change_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata,
        )
        
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        return history

    def get_user_history(
        self,
        user_id: UUID,
        limit: int = 10
    ) -> List[PasswordHistory]:
        """
        Get password change history for user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of records to return
            
        Returns:
            List of PasswordHistory records
        """
        return self.db.query(PasswordHistory).filter(
            PasswordHistory.user_id == user_id
        ).order_by(desc(PasswordHistory.created_at)).limit(limit).all()

    def check_password_reuse(
        self,
        user_id: UUID,
        new_password_hash: str,
        check_last_n: int = 5
    ) -> bool:
        """
        Check if password has been used recently.
        
        Args:
            user_id: User identifier
            new_password_hash: New password hash to check
            check_last_n: Number of previous passwords to check
            
        Returns:
            True if password was used before
        """
        recent_passwords = self.db.query(PasswordHistory.password_hash).filter(
            PasswordHistory.user_id == user_id
        ).order_by(desc(PasswordHistory.created_at)).limit(check_last_n).all()
        
        # Compare hashes
        for (password_hash,) in recent_passwords:
            if password_hash == new_password_hash:
                return True
        
        return False

    def get_password_age(self, user_id: UUID) -> Optional[int]:
        """
        Get age of current password in days.
        
        Args:
            user_id: User identifier
            
        Returns:
            Number of days since last password change, or None
        """
        last_change = self.db.query(PasswordHistory).filter(
            PasswordHistory.user_id == user_id
        ).order_by(desc(PasswordHistory.created_at)).first()
        
        if last_change:
            age = datetime.utcnow() - last_change.created_at
            return age.days
        
        return None

    def cleanup_old_history(self, user_id: UUID, keep_last_n: int = 10) -> int:
        """
        Clean up old password history, keeping only the most recent entries.
        
        Args:
            user_id: User identifier
            keep_last_n: Number of recent passwords to keep
            
        Returns:
            Number of records deleted
        """
        # Get IDs of passwords to keep
        keep_ids = self.db.query(PasswordHistory.id).filter(
            PasswordHistory.user_id == user_id
        ).order_by(desc(PasswordHistory.created_at)).limit(keep_last_n).all()
        
        keep_ids = [id_tuple[0] for id_tuple in keep_ids]
        
        # Delete old records
        count = self.db.query(PasswordHistory).filter(
            and_(
                PasswordHistory.user_id == user_id,
                ~PasswordHistory.id.in_(keep_ids)
            )
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return count


class PasswordPolicyRepository(BaseRepository[PasswordPolicy]):
    """
    Repository for password policy management.
    """

    def __init__(self, db: Session):
        super().__init__(PasswordPolicy, db)

    def create_policy(
        self,
        name: str,
        description: Optional[str] = None,
        tenant_id: Optional[UUID] = None,
        min_length: int = 8,
        max_length: int = 128,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digit: bool = True,
        require_special_char: bool = True,
        special_chars: str = "!@#$%^&*()_+-=[]{}|;:,.<>?",
        prevent_reuse_count: int = 5,
        max_age_days: Optional[int] = None,
        expire_warning_days: int = 7,
        lockout_threshold: int = 5,
        lockout_duration_minutes: int = 30,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PasswordPolicy:
        """
        Create password policy.
        
        Args:
            name: Policy name
            description: Policy description
            tenant_id: Tenant ID (None for system-wide)
            min_length: Minimum password length
            max_length: Maximum password length
            require_uppercase: Require uppercase letters
            require_lowercase: Require lowercase letters
            require_digit: Require digits
            require_special_char: Require special characters
            special_chars: Allowed special characters
            prevent_reuse_count: Number of previous passwords to prevent reuse
            max_age_days: Maximum password age
            expire_warning_days: Days before expiration to warn
            lockout_threshold: Failed attempts before lockout
            lockout_duration_minutes: Lockout duration
            metadata: Additional metadata
            
        Returns:
            Created PasswordPolicy instance
        """
        policy = PasswordPolicy(
            name=name,
            description=description,
            tenant_id=tenant_id,
            min_length=min_length,
            max_length=max_length,
            require_uppercase=require_uppercase,
            require_lowercase=require_lowercase,
            require_digit=require_digit,
            require_special_char=require_special_char,
            special_chars=special_chars,
            prevent_reuse_count=prevent_reuse_count,
            max_age_days=max_age_days,
            expire_warning_days=expire_warning_days,
            lockout_threshold=lockout_threshold,
            lockout_duration_minutes=lockout_duration_minutes,
            metadata=metadata,
        )
        
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def get_active_policy(
        self,
        tenant_id: Optional[UUID] = None
    ) -> Optional[PasswordPolicy]:
        """
        Get active password policy for tenant or system-wide.
        
        Args:
            tenant_id: Tenant ID (None for system-wide)
            
        Returns:
            Active PasswordPolicy or None
        """
        # First try to get tenant-specific policy
        if tenant_id:
            policy = self.db.query(PasswordPolicy).filter(
                and_(
                    PasswordPolicy.tenant_id == tenant_id,
                    PasswordPolicy.is_active == True
                )
            ).first()
            
            if policy:
                return policy
        
        # Fall back to system-wide policy
        return self.db.query(PasswordPolicy).filter(
            and_(
                PasswordPolicy.tenant_id.is_(None),
                PasswordPolicy.is_active == True
            )
        ).first()

    def validate_password(
        self,
        password: str,
        tenant_id: Optional[UUID] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate password against policy.
        
        Args:
            password: Password to validate
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        policy = self.get_active_policy(tenant_id)
        
        if not policy:
            # No policy, use basic validation
            if len(password) < 8:
                return False, ["Password must be at least 8 characters long"]
            return True, []
        
        errors = []
        
        # Check length
        if len(password) < policy.min_length:
            errors.append(f"Password must be at least {policy.min_length} characters long")
        
        if len(password) > policy.max_length:
            errors.append(f"Password must not exceed {policy.max_length} characters")
        
        # Check character requirements
        if policy.require_uppercase and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if policy.require_lowercase and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if policy.require_digit and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        
        if policy.require_special_char:
            if not any(c in policy.special_chars for c in password):
                errors.append(f"Password must contain at least one special character: {policy.special_chars}")
        
        return len(errors) == 0, errors

    def get_all_policies(
        self,
        tenant_id: Optional[UUID] = None,
        active_only: bool = True
    ) -> List[PasswordPolicy]:
        """Get all password policies."""
        query = self.db.query(PasswordPolicy)
        
        if tenant_id is not None:
            query = query.filter(PasswordPolicy.tenant_id == tenant_id)
        
        if active_only:
            query = query.filter(PasswordPolicy.is_active == True)
        
        return query.all()


class PasswordAttemptRepository(BaseRepository[PasswordAttempt]):
    """
    Repository for password attempt tracking.
    """

    def __init__(self, db: Session):
        super().__init__(PasswordAttempt, db)

    def record_attempt(
        self,
        user_id: UUID,
        attempt_type: str,
        is_successful: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PasswordAttempt:
        """
        Record password attempt.
        
        Args:
            user_id: User identifier
            attempt_type: Type of attempt (login, password_change, etc.)
            is_successful: Whether attempt was successful
            ip_address: IP address
            user_agent: User agent
            metadata: Additional metadata
            
        Returns:
            Created PasswordAttempt instance
        """
        attempt = PasswordAttempt(
            user_id=user_id,
            attempt_type=attempt_type,
            is_successful=is_successful,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata,
        )
        
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)
        return attempt

    def count_recent_failures(
        self,
        user_id: UUID,
        attempt_type: str = "login",
        minutes: int = 30
    ) -> int:
        """
        Count recent failed password attempts.
        
        Args:
            user_id: User identifier
            attempt_type: Type of attempt to count
            minutes: Time window in minutes
            
        Returns:
            Count of failed attempts
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        return self.db.query(func.count(PasswordAttempt.id)).filter(
            and_(
                PasswordAttempt.user_id == user_id,
                PasswordAttempt.attempt_type == attempt_type,
                PasswordAttempt.is_successful == False,
                PasswordAttempt.created_at >= cutoff_time,
            )
        ).scalar() or 0

    def should_lockout(
        self,
        user_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> Tuple[bool, Optional[datetime]]:
        """
        Check if account should be locked based on failed attempts.
        
        Args:
            user_id: User identifier
            tenant_id: Tenant ID for policy lookup
            
        Returns:
            Tuple of (should_lock, lockout_until)
        """
        # Get password policy
        policy_repo = PasswordPolicyRepository(self.db)
        policy = policy_repo.get_active_policy(tenant_id)
        
        if not policy:
            # Default policy
            threshold = 5
            duration_minutes = 30
        else:
            threshold = policy.lockout_threshold
            duration_minutes = policy.lockout_duration_minutes
        
        # Count recent failures
        failure_count = self.count_recent_failures(
            user_id,
            minutes=duration_minutes
        )
        
        if failure_count >= threshold:
            lockout_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
            return True, lockout_until
        
        return False, None

    def reset_attempts(self, user_id: UUID) -> int:
        """
        Reset failed attempts for user (after successful login).
        
        Args:
            user_id: User identifier
            
        Returns:
            Number of attempts cleared
        """
        # We don't actually delete, just record successful attempt
        # The time-based window will naturally exclude old attempts
        return 0

    def get_attempt_statistics(
        self,
        user_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get password attempt statistics.
        
        Args:
            user_id: User identifier
            days: Number of days to analyze
            
        Returns:
            Dictionary with attempt statistics
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        total_attempts = self.db.query(func.count(PasswordAttempt.id)).filter(
            and_(
                PasswordAttempt.user_id == user_id,
                PasswordAttempt.created_at >= cutoff_time
            )
        ).scalar()
        
        successful_attempts = self.db.query(func.count(PasswordAttempt.id)).filter(
            and_(
                PasswordAttempt.user_id == user_id,
                PasswordAttempt.is_successful == True,
                PasswordAttempt.created_at >= cutoff_time
            )
        ).scalar()
        
        failed_attempts = total_attempts - successful_attempts
        
        # Get attempt type breakdown
        type_breakdown = self.db.query(
            PasswordAttempt.attempt_type,
            func.count(PasswordAttempt.id)
        ).filter(
            and_(
                PasswordAttempt.user_id == user_id,
                PasswordAttempt.created_at >= cutoff_time
            )
        ).group_by(PasswordAttempt.attempt_type).all()
        
        return {
            "total_attempts": total_attempts,
            "successful_attempts": successful_attempts,
            "failed_attempts": failed_attempts,
            "success_rate": (successful_attempts / total_attempts * 100) if total_attempts > 0 else 0,
            "type_breakdown": {
                attempt_type: count for attempt_type, count in type_breakdown
            }
        }

    def cleanup_old_attempts(self, days_old: int = 90) -> int:
        """Clean up old password attempts."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        count = self.db.query(PasswordAttempt).filter(
            PasswordAttempt.created_at < cutoff_date
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return count