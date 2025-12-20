"""
Password Service
Handles password validation, hashing, reset, and policy enforcement.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from uuid import UUID

from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.repositories.auth import (
    PasswordResetRepository,
    PasswordHistoryRepository,
    PasswordPolicyRepository,
    PasswordAttemptRepository,
)
from app.repositories.auth import SecurityEventRepository
from app.core.exceptions import (
    PasswordPolicyViolationError,
    PasswordResetError,
    PasswordReuseError,
)


class PasswordService:
    """
    Service for password operations including hashing, validation, and reset.
    """

    def __init__(self, db: Session):
        self.db = db
        self.password_reset_repo = PasswordResetRepository(db)
        self.password_history_repo = PasswordHistoryRepository(db)
        self.password_policy_repo = PasswordPolicyRepository(db)
        self.password_attempt_repo = PasswordAttemptRepository(db)
        self.security_event_repo = SecurityEventRepository(db)
        
        # Password hashing context
        self.pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=12
        )

    # ==================== Password Hashing ====================

    def hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        return self.pwd_context.hash(password)

    def verify_password(
        self,
        plain_password: str,
        hashed_password: str
    ) -> bool:
        """
        Verify password against hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password
            
        Returns:
            True if password matches
        """
        return self.pwd_context.verify(plain_password, hashed_password)

    def needs_rehash(self, hashed_password: str) -> bool:
        """
        Check if password hash needs updating.
        
        Args:
            hashed_password: Current password hash
            
        Returns:
            True if rehashing is needed
        """
        return self.pwd_context.needs_update(hashed_password)

    # ==================== Password Validation ====================

    def validate_password(
        self,
        password: str,
        tenant_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate password against policy.
        
        Args:
            password: Password to validate
            tenant_id: Tenant ID for policy lookup
            user_id: User ID for history check
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        # Get password policy
        is_valid, errors = self.password_policy_repo.validate_password(
            password=password,
            tenant_id=tenant_id
        )
        
        if not is_valid:
            return False, errors
        
        # Check password reuse if user_id provided
        if user_id:
            policy = self.password_policy_repo.get_active_policy(tenant_id)
            check_count = policy.prevent_reuse_count if policy else 5
            
            password_hash = self.hash_password(password)
            is_reused = self.password_history_repo.check_password_reuse(
                user_id=user_id,
                new_password_hash=password_hash,
                check_last_n=check_count
            )
            
            if is_reused:
                errors.append(
                    f"Password has been used in your last {check_count} passwords. "
                    "Please choose a different password."
                )
                return False, errors
        
        return True, []

    def check_password_strength(self, password: str) -> Dict[str, Any]:
        """
        Analyze password strength.
        
        Args:
            password: Password to analyze
            
        Returns:
            Dictionary with strength analysis
        """
        strength = {
            "length": len(password),
            "has_uppercase": any(c.isupper() for c in password),
            "has_lowercase": any(c.islower() for c in password),
            "has_digit": any(c.isdigit() for c in password),
            "has_special": any(not c.isalnum() for c in password),
            "score": 0,
            "strength_label": ""
        }
        
        # Calculate strength score (0-100)
        score = 0
        
        # Length score (max 30 points)
        if strength["length"] >= 8:
            score += 10
        if strength["length"] >= 12:
            score += 10
        if strength["length"] >= 16:
            score += 10
        
        # Character variety (max 40 points)
        if strength["has_uppercase"]:
            score += 10
        if strength["has_lowercase"]:
            score += 10
        if strength["has_digit"]:
            score += 10
        if strength["has_special"]:
            score += 10
        
        # Complexity bonus (max 30 points)
        unique_chars = len(set(password))
        if unique_chars >= 8:
            score += 15
        if unique_chars >= 12:
            score += 15
        
        strength["score"] = score
        
        # Assign strength label
        if score >= 80:
            strength["strength_label"] = "Very Strong"
        elif score >= 60:
            strength["strength_label"] = "Strong"
        elif score >= 40:
            strength["strength_label"] = "Medium"
        elif score >= 20:
            strength["strength_label"] = "Weak"
        else:
            strength["strength_label"] = "Very Weak"
        
        return strength

    # ==================== Password Reset ====================

    def initiate_password_reset(
        self,
        user_id: UUID,
        ip_address: str,
        user_agent: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Initiate password reset process.
        
        Args:
            user_id: User identifier
            ip_address: Request IP address
            user_agent: Request user agent
            
        Returns:
            Tuple of (success, reset_token, error_message)
        """
        try:
            # Generate secure reset token
            reset_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
            
            # Create reset record
            self.password_reset_repo.create_reset_token(
                user_id=user_id,
                token=reset_token,
                token_hash=token_hash,
                expires_in_hours=1,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            # Record security event
            self.security_event_repo.record_event(
                event_type="password_reset_requested",
                severity="medium",
                description="Password reset requested",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            return True, reset_token, None
            
        except Exception as e:
            return False, None, f"Failed to initiate password reset: {str(e)}"

    def verify_reset_token(
        self,
        token: str
    ) -> Tuple[bool, Optional[Any], Optional[str]]:
        """
        Verify password reset token.
        
        Args:
            token: Reset token
            
        Returns:
            Tuple of (success, reset_object, error_message)
        """
        reset = self.password_reset_repo.find_by_token(token)
        
        if not reset:
            return False, None, "Invalid reset token"
        
        if not reset.is_valid():
            return False, None, "Reset token has expired or already been used"
        
        return True, reset, None

    def complete_password_reset(
        self,
        reset_token: str,
        new_password: str,
        ip_address: str,
        user_agent: str,
        tenant_id: Optional[UUID] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Complete password reset process.
        
        Args:
            reset_token: Reset token
            new_password: New password
            ip_address: Request IP address
            user_agent: Request user agent
            tenant_id: Tenant ID for policy lookup
            
        Returns:
            Tuple of (success, error_message)
        """
        # Verify reset token
        success, reset, error = self.password_reset_repo.verify_and_use_token(
            token=reset_token,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if not success or not reset:
            raise PasswordResetError(error)
        
        # Validate new password
        is_valid, errors = self.validate_password(
            password=new_password,
            tenant_id=tenant_id,
            user_id=reset.user_id
        )
        
        if not is_valid:
            raise PasswordPolicyViolationError("; ".join(errors))
        
        # Hash new password
        new_password_hash = self.hash_password(new_password)
        
        # Add to password history
        self.password_history_repo.add_to_history(
            user_id=reset.user_id,
            password_hash=new_password_hash,
            change_reason="Password reset",
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Record security event
        self.security_event_repo.record_event(
            event_type="password_reset_completed",
            severity="medium",
            description="Password successfully reset",
            user_id=reset.user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return True, None

    # ==================== Password Change ====================

    def change_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
        current_password_hash: str,
        ip_address: str,
        user_agent: str,
        tenant_id: Optional[UUID] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Change user password (authenticated).
        
        Args:
            user_id: User identifier
            current_password: Current password
            new_password: New password
            current_password_hash: Current password hash for verification
            ip_address: Request IP address
            user_agent: Request user agent
            tenant_id: Tenant ID for policy lookup
            
        Returns:
            Tuple of (success, error_message)
        """
        # Verify current password
        if not self.verify_password(current_password, current_password_hash):
            # Record failed attempt
            self.password_attempt_repo.record_attempt(
                user_id=user_id,
                attempt_type="password_change",
                is_successful=False,
                ip_address=ip_address,
                user_agent=user_agent
            )
            return False, "Current password is incorrect"
        
        # Validate new password
        is_valid, errors = self.validate_password(
            password=new_password,
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        if not is_valid:
            return False, "; ".join(errors)
        
        # Hash new password
        new_password_hash = self.hash_password(new_password)
        
        # Add to password history
        self.password_history_repo.add_to_history(
            user_id=user_id,
            password_hash=new_password_hash,
            change_reason="User changed password",
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Record successful attempt
        self.password_attempt_repo.record_attempt(
            user_id=user_id,
            attempt_type="password_change",
            is_successful=True,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Record security event
        self.security_event_repo.record_event(
            event_type="password_changed",
            severity="low",
            description="User changed password",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return True, None

    # ==================== Password Expiration ====================

    def check_password_expiration(
        self,
        user_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Check if password needs to be changed.
        
        Args:
            user_id: User identifier
            tenant_id: Tenant ID for policy lookup
            
        Returns:
            Dictionary with expiration information
        """
        # Get password policy
        policy = self.password_policy_repo.get_active_policy(tenant_id)
        
        if not policy or not policy.max_age_days:
            return {
                "requires_change": False,
                "days_until_expiration": None,
                "is_expired": False
            }
        
        # Get password age
        password_age = self.password_history_repo.get_password_age(user_id)
        
        if password_age is None:
            return {
                "requires_change": False,
                "days_until_expiration": None,
                "is_expired": False
            }
        
        days_until_expiration = policy.max_age_days - password_age
        is_expired = days_until_expiration <= 0
        should_warn = days_until_expiration <= policy.expire_warning_days
        
        return {
            "requires_change": is_expired,
            "days_until_expiration": days_until_expiration,
            "is_expired": is_expired,
            "should_warn": should_warn,
            "password_age_days": password_age
        }

    # ==================== Account Lockout ====================

    def check_account_lockout(
        self,
        user_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> Tuple[bool, Optional[datetime]]:
        """
        Check if account should be locked due to failed attempts.
        
        Args:
            user_id: User identifier
            tenant_id: Tenant ID for policy lookup
            
        Returns:
            Tuple of (should_lock, lockout_until)
        """
        return self.password_attempt_repo.should_lockout(
            user_id=user_id,
            tenant_id=tenant_id
        )

    def record_password_attempt(
        self,
        user_id: UUID,
        is_successful: bool,
        ip_address: str,
        user_agent: str,
        attempt_type: str = "login"
    ) -> None:
        """
        Record password verification attempt.
        
        Args:
            user_id: User identifier
            is_successful: Whether attempt was successful
            ip_address: Request IP address
            user_agent: Request user agent
            attempt_type: Type of attempt
        """
        self.password_attempt_repo.record_attempt(
            user_id=user_id,
            attempt_type=attempt_type,
            is_successful=is_successful,
            ip_address=ip_address,
            user_agent=user_agent
        )

    # ==================== Password History ====================

    def get_password_history(
        self,
        user_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get password change history.
        
        Args:
            user_id: User identifier
            limit: Maximum records to return
            
        Returns:
            List of password change records
        """
        history = self.password_history_repo.get_user_history(user_id, limit)
        
        return [
            {
                "changed_at": record.created_at,
                "change_reason": record.change_reason,
                "ip_address": record.ip_address,
                "changed_by": record.changed_by_user_id
            }
            for record in history
        ]

    # ==================== Password Policy ====================

    def get_password_policy(
        self,
        tenant_id: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get active password policy.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Password policy dictionary or None
        """
        policy = self.password_policy_repo.get_active_policy(tenant_id)
        
        if not policy:
            return None
        
        return {
            "min_length": policy.min_length,
            "max_length": policy.max_length,
            "require_uppercase": policy.require_uppercase,
            "require_lowercase": policy.require_lowercase,
            "require_digit": policy.require_digit,
            "require_special_char": policy.require_special_char,
            "special_chars": policy.special_chars,
            "prevent_reuse_count": policy.prevent_reuse_count,
            "max_age_days": policy.max_age_days,
            "expire_warning_days": policy.expire_warning_days,
            "lockout_threshold": policy.lockout_threshold,
            "lockout_duration_minutes": policy.lockout_duration_minutes
        }

    def create_password_policy(
        self,
        name: str,
        tenant_id: Optional[UUID] = None,
        **policy_settings
    ) -> Any:
        """
        Create password policy.
        
        Args:
            name: Policy name
            tenant_id: Tenant ID
            **policy_settings: Policy configuration
            
        Returns:
            Created policy
        """
        return self.password_policy_repo.create_policy(
            name=name,
            tenant_id=tenant_id,
            **policy_settings
        )

    # ==================== Statistics ====================

    def get_password_statistics(
        self,
        user_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get password-related statistics.
        
        Args:
            user_id: User identifier
            days: Number of days to analyze
            
        Returns:
            Dictionary with statistics
        """
        reset_stats = self.password_reset_repo.get_reset_statistics(user_id, days)
        attempt_stats = self.password_attempt_repo.get_attempt_statistics(user_id, days)
        password_age = self.password_history_repo.get_password_age(user_id)
        
        return {
            "reset_statistics": reset_stats,
            "attempt_statistics": attempt_stats,
            "password_age_days": password_age
        }

    # ==================== Cleanup ====================

    def cleanup_password_data(self, days_old: int = 90) -> Dict[str, int]:
        """
        Clean up old password-related data.
        
        Args:
            days_old: Remove data older than this many days
            
        Returns:
            Dictionary with cleanup counts
        """
        return {
            "password_resets_cleaned": self.password_reset_repo.cleanup_expired_tokens(days_old),
            "password_attempts_cleaned": self.password_attempt_repo.cleanup_old_attempts(days_old)
        }