# --- File: C:\Hostel-Main\app\services\user\user_service.py ---
"""
User Service - Core user authentication and management business logic.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
import secrets
import hashlib

from app.models.user import User
from app.repositories.user import UserRepository, UserAggregateRepository
from app.schemas.common.enums import UserRole
from app.core.exceptions import (
    EntityNotFoundError, 
    BusinessRuleViolationError,
    AuthenticationError
)


class SecurityUtils:
    """Security utility class for password hashing and verification."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using bcrypt or similar.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        import bcrypt
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password
            
        Returns:
            True if password matches
        """
        import bcrypt
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate secure random token."""
        return secrets.token_urlsafe(length)


class UserService:
    """
    Service for core user operations including registration,
    authentication, account management, and security.
    """

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.aggregate_repo = UserAggregateRepository(db)
        self.security_utils = SecurityUtils()

    # ==================== Registration ====================

    def register_user(
        self,
        email: str,
        phone: str,
        full_name: str,
        password: str,
        user_role: UserRole = UserRole.STUDENT,
        registration_ip: Optional[str] = None,
        registration_source: str = "web",
        referral_code: Optional[str] = None,
        auto_verify: bool = False
    ) -> User:
        """
        Register a new user with complete validation and security checks.
        
        Args:
            email: User email (will be normalized)
            phone: Phone number (E.164 format)
            full_name: Full name
            password: Plain text password (will be hashed)
            user_role: User role
            registration_ip: Registration IP address
            registration_source: Registration source (web, mobile, admin)
            referral_code: Optional referral code
            auto_verify: Auto-verify email and phone (for admin creation)
            
        Returns:
            Created User entity
            
        Raises:
            BusinessRuleViolationError: If validation fails or user exists
        """
        # Normalize and validate email
        email = self._normalize_email(email)
        self._validate_email(email)
        
        # Validate phone
        phone = self._normalize_phone(phone)
        self._validate_phone(phone)
        
        # Check uniqueness
        if self.user_repo.exists_by_email(email):
            raise BusinessRuleViolationError(
                f"User with email {email} already exists"
            )
        
        if self.user_repo.exists_by_phone(phone):
            raise BusinessRuleViolationError(
                f"User with phone {phone} already exists"
            )
        
        # Validate password strength
        self._validate_password_strength(password)
        
        # Validate full name
        self._validate_full_name(full_name)
        
        # Hash password
        password_hash = self.security_utils.hash_password(password)
        
        # Prepare user data
        now = datetime.now(timezone.utc)
        user_data = {
            "email": email,
            "phone": phone,
            "full_name": full_name.strip(),
            "password_hash": password_hash,
            "user_role": user_role,
            "is_active": True,
            "is_email_verified": auto_verify,
            "is_phone_verified": auto_verify,
            "email_verified_at": now if auto_verify else None,
            "phone_verified_at": now if auto_verify else None,
            "registration_ip": registration_ip,
            "registration_source": registration_source,
            "referral_code": referral_code,
            "last_password_change_at": now,
            "failed_login_attempts": 0
        }
        
        # Create user
        user = self.user_repo.create(user_data)
        
        # Log registration event
        self._log_user_event(user.id, "user_registered", {
            "role": user_role.value,
            "source": registration_source,
            "ip": registration_ip
        })
        
        return user

    def _normalize_email(self, email: str) -> str:
        """Normalize email address."""
        return email.lower().strip()

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number."""
        # Remove all non-digit characters except '+'
        phone = ''.join(c for c in phone if c.isdigit() or c == '+')
        
        # Ensure E.164 format
        if not phone.startswith('+'):
            # Assume it's an Indian number if no country code
            phone = '+91' + phone
        
        return phone

    def _validate_email(self, email: str) -> None:
        """Validate email format."""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(email_pattern, email):
            raise BusinessRuleViolationError("Invalid email format")
        
        if len(email) > 255:
            raise BusinessRuleViolationError("Email is too long")

    def _validate_phone(self, phone: str) -> None:
        """Validate phone number format."""
        # Basic E.164 validation
        if not phone.startswith('+'):
            raise BusinessRuleViolationError("Phone must be in E.164 format (+country_code)")
        
        if len(phone) < 10 or len(phone) > 15:
            raise BusinessRuleViolationError("Invalid phone number length")

    def _validate_full_name(self, full_name: str) -> None:
        """Validate full name."""
        full_name = full_name.strip()
        
        if not full_name:
            raise BusinessRuleViolationError("Full name is required")
        
        if len(full_name) < 2:
            raise BusinessRuleViolationError("Full name must be at least 2 characters")
        
        if len(full_name) > 255:
            raise BusinessRuleViolationError("Full name is too long")
        
        # Check for at least one letter
        if not any(c.isalpha() for c in full_name):
            raise BusinessRuleViolationError("Full name must contain letters")

    def _validate_password_strength(self, password: str) -> None:
        """
        Validate password meets security requirements.
        
        Requirements:
        - Minimum 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character
        """
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            errors.append("Password must contain at least one special character")
        
        # Check for common passwords
        common_passwords = [
            'password', '12345678', 'qwerty', 'abc123', 'password123'
        ]
        if password.lower() in common_passwords:
            errors.append("Password is too common")
        
        if errors:
            raise BusinessRuleViolationError(
                "Password validation failed: " + "; ".join(errors)
            )

    # ==================== Authentication ====================

    def authenticate_user(
        self,
        identifier: str,  # email or phone
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None
    ) -> Tuple[User, Dict[str, Any]]:
        """
        Authenticate user with comprehensive security checks.
        
        Args:
            identifier: Email or phone number
            password: Plain text password
            ip_address: Login IP address
            user_agent: User agent string
            device_info: Device information
            
        Returns:
            Tuple of (User, authentication_info)
            
        Raises:
            AuthenticationError: If authentication fails
        """
        # Find user
        user = self.user_repo.find_by_email_or_phone(identifier)
        
        auth_info = {
            "identifier": identifier,
            "ip_address": ip_address,
            "success": False,
            "failure_reason": None
        }
        
        if not user:
            auth_info["failure_reason"] = "invalid_credentials"
            self._log_failed_login(identifier, ip_address, "user_not_found")
            raise AuthenticationError("Invalid credentials")
        
        # Check if account is locked
        if user.is_locked:
            auth_info["failure_reason"] = "account_locked"
            lock_duration = user.account_locked_until - datetime.now(timezone.utc)
            minutes_remaining = int(lock_duration.total_seconds() / 60)
            raise AuthenticationError(
                f"Account is locked. Try again in {minutes_remaining} minutes."
            )
        
        # Check if account is active
        if not user.is_active:
            auth_info["failure_reason"] = "account_inactive"
            raise AuthenticationError("Account is deactivated. Contact support.")
        
        # Check if account is deleted
        if user.deleted_at:
            auth_info["failure_reason"] = "account_deleted"
            raise AuthenticationError("Account not found")
        
        # Verify password
        if not self.security_utils.verify_password(password, user.password_hash):
            # Increment failed attempts
            self.user_repo.increment_failed_login(user.id)
            self._log_failed_login(user.email, ip_address, "invalid_password")
            
            auth_info["failure_reason"] = "invalid_credentials"
            
            # Check if account should be locked
            user = self.user_repo.get_by_id(user.id)  # Refresh
            if user.is_locked:
                raise AuthenticationError(
                    "Too many failed attempts. Account is now locked."
                )
            
            raise AuthenticationError("Invalid credentials")
        
        # Check if password reset is required
        if user.password_reset_required:
            auth_info["failure_reason"] = "password_reset_required"
            auth_info["password_reset_required"] = True
            raise AuthenticationError(
                "Password reset required. Please reset your password."
            )
        
        # Check password age (optional policy)
        if self._should_rotate_password(user):
            auth_info["password_rotation_suggested"] = True
        
        # Authentication successful
        user = self.user_repo.update_login_success(user.id, ip_address)
        
        auth_info["success"] = True
        auth_info["user_id"] = user.id
        auth_info["requires_2fa"] = False  # TODO: Implement 2FA
        
        # Log successful login
        self._log_user_event(user.id, "user_login", {
            "ip": ip_address,
            "user_agent": user_agent
        })
        
        return user, auth_info

    def _should_rotate_password(self, user: User) -> bool:
        """Check if password should be rotated based on age."""
        if not user.last_password_change_at:
            return True
        
        password_age = datetime.now(timezone.utc) - user.last_password_change_at
        return password_age.days > 90  # 90 days policy

    def validate_session(self, user_id: str) -> User:
        """
        Validate user session and retrieve user.
        
        Args:
            user_id: User ID from session
            
        Returns:
            User entity
            
        Raises:
            AuthenticationError: If user not found or inactive
        """
        try:
            user = self.user_repo.get_by_id(user_id)
        except EntityNotFoundError:
            raise AuthenticationError("Invalid session")
        
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")
        
        if user.is_locked:
            raise AuthenticationError("Account is locked")
        
        if user.deleted_at:
            raise AuthenticationError("Account not found")
        
        return user

    # ==================== Password Management ====================

    def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        ip_address: Optional[str] = None
    ) -> User:
        """
        Change user password with comprehensive validation.
        
        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password
            ip_address: IP address of change request
            
        Returns:
            Updated User entity
            
        Raises:
            AuthenticationError: If current password is invalid
            BusinessRuleViolationError: If new password is invalid
        """
        user = self.user_repo.get_by_id(user_id)
        
        # Verify current password
        if not self.security_utils.verify_password(
            current_password, 
            user.password_hash
        ):
            self._log_user_event(user_id, "password_change_failed", {
                "reason": "invalid_current_password",
                "ip": ip_address
            })
            raise AuthenticationError("Current password is incorrect")
        
        # Validate new password strength
        self._validate_password_strength(new_password)
        
        # Check if new password is same as current
        if self.security_utils.verify_password(new_password, user.password_hash):
            raise BusinessRuleViolationError(
                "New password must be different from current password"
            )
        
        # TODO: Check password history to prevent reuse
        # This requires password_history integration
        
        # Hash new password
        new_password_hash = self.security_utils.hash_password(new_password)
        
        # Update password
        user = self.user_repo.update_password(
            user_id, 
            new_password_hash,
            require_change=False
        )
        
        # Log password change
        self._log_user_event(user_id, "password_changed", {
            "ip": ip_address,
            "reason": "user_request"
        })
        
        # TODO: Invalidate all existing sessions except current
        # TODO: Send email notification
        
        return user

    def reset_password(
        self,
        user_id: str,
        new_password: str,
        require_change: bool = False,
        changed_by: Optional[str] = None
    ) -> User:
        """
        Reset user password (admin operation).
        
        Args:
            user_id: User ID
            new_password: New password
            require_change: Force password change on next login
            changed_by: Admin user ID who performed the reset
            
        Returns:
            Updated User entity
        """
        self._validate_password_strength(new_password)
        
        password_hash = self.security_utils.hash_password(new_password)
        
        user = self.user_repo.update_password(
            user_id,
            password_hash,
            require_change
        )
        
        # Log password reset
        self._log_user_event(user_id, "password_reset", {
            "changed_by": changed_by,
            "require_change": require_change,
            "reason": "admin_reset"
        })
        
        return user

    def request_password_reset(self, email: str) -> Dict[str, Any]:
        """
        Initiate password reset process.
        
        Args:
            email: User email
            
        Returns:
            Dictionary with reset token info
        """
        user = self.user_repo.find_by_email(email)
        
        if not user:
            # Don't reveal that user doesn't exist
            # Return success but don't actually send anything
            return {
                "status": "success",
                "message": "If the email exists, a reset link has been sent"
            }
        
        # Generate reset token
        reset_token = self.security_utils.generate_token()
        token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
        
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # TODO: Store reset token in cache/database with expiry
        # cache.set(f"password_reset:{token_hash}", user.id, expiry)
        
        # Log reset request
        self._log_user_event(user.id, "password_reset_requested", {})
        
        # TODO: Send reset email
        
        return {
            "status": "success",
            "user_id": user.id,
            "reset_token": reset_token,  # Remove in production
            "expires_at": expiry,
            "message": "Password reset link has been sent to your email"
        }

    def confirm_password_reset(
        self,
        token: str,
        new_password: str
    ) -> User:
        """
        Confirm password reset with token.
        
        Args:
            token: Reset token
            new_password: New password
            
        Returns:
            Updated User
            
        Raises:
            AuthenticationError: If token is invalid
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # TODO: Get user_id from cache
        # user_id = cache.get(f"password_reset:{token_hash}")
        # if not user_id:
        #     raise AuthenticationError("Invalid or expired reset token")
        
        # For now, raise error
        raise AuthenticationError("Password reset not fully implemented")
        
        # Validate and set new password
        # self._validate_password_strength(new_password)
        # password_hash = self.security_utils.hash_password(new_password)
        # user = self.user_repo.update_password(user_id, password_hash)
        # 
        # # Delete token
        # cache.delete(f"password_reset:{token_hash}")
        # 
        # # Log password reset
        # self._log_user_event(user_id, "password_reset_completed", {})
        # 
        # return user

    # ==================== Account Management ====================

    def update_user_info(
        self,
        user_id: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        full_name: Optional[str] = None
    ) -> User:
        """
        Update basic user information.
        
        Args:
            user_id: User ID
            email: New email (requires reverification)
            phone: New phone (requires reverification)
            full_name: New full name
            
        Returns:
            Updated User
            
        Raises:
            BusinessRuleViolationError: If validation fails
        """
        user = self.user_repo.get_by_id(user_id)
        update_data = {}
        
        if email and email != user.email:
            email = self._normalize_email(email)
            self._validate_email(email)
            
            if self.user_repo.exists_by_email(email, exclude_user_id=user_id):
                raise BusinessRuleViolationError(f"Email {email} is already in use")
            
            update_data['email'] = email
            update_data['is_email_verified'] = False
            update_data['email_verified_at'] = None
        
        if phone and phone != user.phone:
            phone = self._normalize_phone(phone)
            self._validate_phone(phone)
            
            if self.user_repo.exists_by_phone(phone, exclude_user_id=user_id):
                raise BusinessRuleViolationError(f"Phone {phone} is already in use")
            
            update_data['phone'] = phone
            update_data['is_phone_verified'] = False
            update_data['phone_verified_at'] = None
        
        if full_name and full_name != user.full_name:
            self._validate_full_name(full_name)
            update_data['full_name'] = full_name.strip()
        
        if update_data:
            user = self.user_repo.update(user_id, update_data)
            self._log_user_event(user_id, "user_info_updated", {
                "fields": list(update_data.keys())
            })
        
        return user

    def activate_account(self, user_id: str, activated_by: Optional[str] = None) -> User:
        """
        Activate user account.
        
        Args:
            user_id: User ID
            activated_by: Admin user ID who activated the account
            
        Returns:
            Activated User
        """
        user = self.user_repo.activate_account(user_id)
        
        self._log_user_event(user_id, "account_activated", {
            "activated_by": activated_by
        })
        
        return user

    def deactivate_account(
        self,
        user_id: str,
        reason: Optional[str] = None,
        deactivated_by: Optional[str] = None
    ) -> User:
        """
        Deactivate user account.
        
        Args:
            user_id: User ID
            reason: Deactivation reason
            deactivated_by: Admin user ID who deactivated the account
            
        Returns:
            Deactivated User
        """
        # TODO: Perform cleanup operations
        # - Revoke all sessions
        # - Cancel active bookings
        # - Suspend subscriptions
        
        user = self.user_repo.deactivate_account(user_id, reason)
        
        self._log_user_event(user_id, "account_deactivated", {
            "reason": reason,
            "deactivated_by": deactivated_by
        })
        
        return user

    def delete_account(
        self,
        user_id: str,
        reason: Optional[str] = None,
        deleted_by: Optional[str] = None
    ) -> User:
        """
        Soft delete user account (GDPR compliance).
        
        Args:
            user_id: User ID
            reason: Deletion reason
            deleted_by: Admin user ID who deleted the account
            
        Returns:
            Soft-deleted User
        """
        # TODO: Perform cleanup operations
        # - Anonymize personal data
        # - Revoke all sessions
        # - Cancel bookings
        # - Archive data for compliance
        
        user = self.user_repo.soft_delete(user_id)
        
        self._log_user_event(user_id, "account_deleted", {
            "reason": reason,
            "deleted_by": deleted_by
        })
        
        return user

    def unlock_account(
        self,
        user_id: str,
        unlocked_by: Optional[str] = None
    ) -> User:
        """
        Manually unlock user account.
        
        Args:
            user_id: User ID
            unlocked_by: Admin user ID who unlocked the account
            
        Returns:
            Unlocked User
        """
        user = self.user_repo.unlock_account(user_id)
        
        self._log_user_event(user_id, "account_unlocked", {
            "unlocked_by": unlocked_by
        })
        
        return user

    # ==================== Verification ====================

    def verify_email(self, user_id: str) -> User:
        """Mark user email as verified."""
        user = self.user_repo.verify_email(user_id)
        
        self._log_user_event(user_id, "email_verified", {})
        
        return user

    def verify_phone(self, user_id: str) -> User:
        """Mark user phone as verified."""
        user = self.user_repo.verify_phone(user_id)
        
        self._log_user_event(user_id, "phone_verified", {})
        
        return user

    def accept_terms(
        self,
        user_id: str,
        accept_privacy: bool = True,
        ip_address: Optional[str] = None
    ) -> User:
        """
        Record terms and privacy policy acceptance.
        
        Args:
            user_id: User ID
            accept_privacy: Also accept privacy policy
            ip_address: IP address of acceptance
            
        Returns:
            Updated User
        """
        user = self.user_repo.accept_terms(user_id, accept_privacy)
        
        self._log_user_event(user_id, "terms_accepted", {
            "privacy_policy": accept_privacy,
            "ip": ip_address
        })
        
        return user

    # ==================== User Retrieval ====================

    def get_user_by_id(
        self,
        user_id: str,
        eager_load: bool = True,
        include_deleted: bool = False
    ) -> User:
        """
        Get user by ID with optional eager loading.
        
        Args:
            user_id: User ID
            eager_load: Load related entities
            include_deleted: Include soft-deleted users
            
        Returns:
            User entity
        """
        user = self.user_repo.get_by_id(user_id)
        
        if user.deleted_at and not include_deleted:
            raise EntityNotFoundError(f"User {user_id} not found")
        
        if eager_load:
            # Reload with relationships
            user = self.user_repo.find_by_email(user.email, eager_load=True)
        
        return user

    def get_user_by_email(
        self,
        email: str,
        include_deleted: bool = False
    ) -> Optional[User]:
        """Get user by email."""
        email = self._normalize_email(email)
        return self.user_repo.find_by_email(email, include_deleted)

    def get_user_by_phone(
        self,
        phone: str,
        include_deleted: bool = False
    ) -> Optional[User]:
        """Get user by phone."""
        phone = self._normalize_phone(phone)
        return self.user_repo.find_by_phone(phone, include_deleted)

    def get_complete_user_data(self, user_id: str) -> Dict[str, Any]:
        """Get complete user data with all relationships."""
        return self.aggregate_repo.get_complete_user(user_id)

    def get_user_summary(self, user_id: str) -> Dict[str, Any]:
        """Get user summary with key metrics."""
        return self.aggregate_repo.get_user_summary(user_id)

    # ==================== Search & Listing ====================

    def search_users(
        self,
        search_term: Optional[str] = None,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[User], int]:
        """
        Search users with filters and pagination.
        
        Returns:
            Tuple of (users list, total count)
        """
        users = self.user_repo.search_users(
            search_term, role, is_active, is_verified, limit, offset
        )
        
        # Get total count for pagination
        # In production, implement a more efficient count query
        total = len(self.user_repo.search_users(
            search_term, role, is_active, is_verified, limit=10000, offset=0
        ))
        
        return users, total

    def list_users_by_role(
        self,
        role: UserRole,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[User]:
        """List users by role."""
        return self.user_repo.find_by_role(role, is_active, limit, offset)

    def get_unverified_users(
        self,
        verification_type: Optional[str] = None,
        older_than_days: Optional[int] = None
    ) -> List[User]:
        """Get users with pending verification."""
        return self.user_repo.find_unverified_users(
            verification_type,
            older_than_days
        )

    def get_inactive_users(self, inactive_days: int = 30) -> List[User]:
        """Get users inactive for specified period."""
        return self.user_repo.find_inactive_users(inactive_days)

    def get_locked_accounts(self) -> List[User]:
        """Get currently locked accounts."""
        return self.user_repo.find_locked_accounts(include_expired=False)

    # ==================== Statistics & Analytics ====================

    def get_user_statistics(self) -> Dict[str, Any]:
        """Get comprehensive user statistics."""
        return self.user_repo.get_user_statistics()

    def get_platform_overview(self) -> Dict[str, Any]:
        """Get platform-wide user analytics."""
        return self.aggregate_repo.get_platform_overview()

    def get_registration_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get user registration trends."""
        return self.user_repo.get_registration_trends(days)

    def get_user_growth_metrics(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily user growth metrics."""
        return self.aggregate_repo.get_user_growth_metrics(days)

    def get_engagement_metrics(self) -> Dict[str, Any]:
        """Get user engagement metrics."""
        return self.aggregate_repo.get_engagement_metrics()

    def get_role_distribution(self) -> Dict[str, int]:
        """Get user count distribution by role."""
        return self.user_repo.get_role_distribution()

    def get_verification_statistics(self) -> Dict[str, Any]:
        """Get verification statistics."""
        total = self.user_repo.count_all()
        
        email_verified = self.db.query(func.count(User.id)).filter(
            User.is_email_verified == True,
            User.deleted_at.is_(None)
        ).scalar()
        
        phone_verified = self.db.query(func.count(User.id)).filter(
            User.is_phone_verified == True,
            User.deleted_at.is_(None)
        ).scalar()
        
        fully_verified = self.db.query(func.count(User.id)).filter(
            User.is_email_verified == True,
            User.is_phone_verified == True,
            User.deleted_at.is_(None)
        ).scalar()
        
        return {
            "total_users": total,
            "email_verified": email_verified,
            "phone_verified": phone_verified,
            "fully_verified": fully_verified,
            "email_verification_rate": round(email_verified / total * 100, 2) if total > 0 else 0,
            "phone_verification_rate": round(phone_verified / total * 100, 2) if total > 0 else 0,
            "full_verification_rate": round(fully_verified / total * 100, 2) if total > 0 else 0
        }

    # ==================== Bulk Operations ====================

    def bulk_verify_emails(self, user_ids: List[str]) -> int:
        """Bulk verify user emails."""
        return self.aggregate_repo.bulk_verify_emails(user_ids)

    def bulk_deactivate_users(
        self,
        user_ids: List[str],
        reason: Optional[str] = None
    ) -> int:
        """Bulk deactivate users."""
        return self.aggregate_repo.bulk_deactivate_users(user_ids, reason)

    def bulk_send_notification(
        self,
        user_ids: List[str],
        notification_type: str,
        message: str
    ) -> Dict[str, int]:
        """
        Send notification to multiple users.
        
        Returns:
            Dictionary with success/failure counts
        """
        # TODO: Implement with notification service
        return {
            "total": len(user_ids),
            "success": 0,
            "failed": 0
        }

    # ==================== Cleanup Operations ====================

    def cleanup_stale_accounts(
        self,
        days: int = 30,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Clean up stale unverified accounts.
        
        Args:
            days: Days threshold
            dry_run: If True, don't actually delete
            
        Returns:
            Cleanup summary
        """
        stale_users = self.aggregate_repo.find_stale_unverified_users(days)
        
        summary = {
            "total_found": len(stale_users),
            "deleted": 0,
            "dry_run": dry_run,
            "user_ids": [user.id for user in stale_users]
        }
        
        if not dry_run:
            for user in stale_users:
                try:
                    self.user_repo.soft_delete(user.id)
                    summary["deleted"] += 1
                except Exception:
                    continue
        
        return summary

    def cleanup_expired_locks(self) -> int:
        """
        Clear expired account locks.
        
        Returns:
            Count of unlocked accounts
        """
        now = datetime.now(timezone.utc)
        
        count = self.db.query(User).filter(
            User.account_locked_until.isnot(None),
            User.account_locked_until < now
        ).update({
            "account_locked_until": None,
            "failed_login_attempts": 0
        })
        
        self.db.commit()
        return count

    # ==================== Helper Methods ====================

    def _log_user_event(
        self,
        user_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> None:
        """
        Log user event for auditing.
        
        Args:
            user_id: User ID
            event_type: Event type
            event_data: Event data
        """
        # TODO: Implement proper event logging system
        # This could use a separate audit log table or external logging service
        pass

    def _log_failed_login(
        self,
        identifier: str,
        ip_address: Optional[str],
        reason: str
    ) -> None:
        """Log failed login attempt."""
        # TODO: Implement with security monitoring system
        pass

    def check_user_exists(self, email: Optional[str] = None, phone: Optional[str] = None) -> bool:
        """
        Check if user exists by email or phone.
        
        Args:
            email: Email to check
            phone: Phone to check
            
        Returns:
            True if user exists
        """
        if email:
            email = self._normalize_email(email)
            if self.user_repo.exists_by_email(email):
                return True
        
        if phone:
            phone = self._normalize_phone(phone)
            if self.user_repo.exists_by_phone(phone):
                return True
        
        return False

    def validate_user_access(
        self,
        user_id: str,
        required_role: Optional[UserRole] = None,
        require_verified: bool = False
    ) -> User:
        """
        Validate user access with role and verification checks.
        
        Args:
            user_id: User ID
            required_role: Required user role
            require_verified: Require email and phone verification
            
        Returns:
            User if validation passes
            
        Raises:
            AuthenticationError: If validation fails
        """
        user = self.validate_session(user_id)
        
        if required_role and user.user_role != required_role:
            raise AuthenticationError(f"Access denied. Required role: {required_role.value}")
        
        if require_verified and not user.is_verified:
            raise AuthenticationError("Account verification required")
        
        return user