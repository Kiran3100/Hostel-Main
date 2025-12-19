"""
User Repository - Core user authentication and identity management.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import and_, or_, func, case
from sqlalchemy.orm import Session, joinedload

from app.models.user import User
from app.schemas.common.enums import UserRole
from app.repositories.base.base_repository import BaseRepository
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError


class UserRepository(BaseRepository[User]):
    """
    Repository for User entity with advanced authentication,
    security monitoring, and role-based access management.
    """

    def __init__(self, db: Session):
        super().__init__(User, db)

    # ==================== Authentication Operations ====================

    def find_by_email(
        self, 
        email: str, 
        include_deleted: bool = False,
        eager_load: bool = True
    ) -> Optional[User]:
        """
        Find user by email address (normalized to lowercase).
        
        Args:
            email: Email address to search
            include_deleted: Include soft-deleted users
            eager_load: Load related profile and address
            
        Returns:
            User entity or None
        """
        query = self.db.query(User)
        
        if eager_load:
            query = query.options(
                joinedload(User.profile),
                joinedload(User.address),
                joinedload(User.emergency_contact)
            )
        
        query = query.filter(func.lower(User.email) == email.lower())
        
        if not include_deleted:
            query = query.filter(User.deleted_at.is_(None))
        
        return query.first()

    def find_by_phone(
        self, 
        phone: str, 
        include_deleted: bool = False
    ) -> Optional[User]:
        """
        Find user by phone number.
        
        Args:
            phone: Phone number (E.164 format)
            include_deleted: Include soft-deleted users
            
        Returns:
            User entity or None
        """
        query = self.db.query(User).filter(User.phone == phone)
        
        if not include_deleted:
            query = query.filter(User.deleted_at.is_(None))
        
        return query.first()

    def find_by_email_or_phone(
        self, 
        identifier: str,
        include_deleted: bool = False
    ) -> Optional[User]:
        """
        Find user by email or phone number.
        
        Args:
            identifier: Email or phone number
            include_deleted: Include soft-deleted users
            
        Returns:
            User entity or None
        """
        query = self.db.query(User).filter(
            or_(
                func.lower(User.email) == identifier.lower(),
                User.phone == identifier
            )
        )
        
        if not include_deleted:
            query = query.filter(User.deleted_at.is_(None))
        
        return query.first()

    def exists_by_email(self, email: str, exclude_user_id: Optional[str] = None) -> bool:
        """
        Check if email already exists.
        
        Args:
            email: Email to check
            exclude_user_id: User ID to exclude from check (for updates)
            
        Returns:
            True if email exists
        """
        query = self.db.query(User.id).filter(
            func.lower(User.email) == email.lower(),
            User.deleted_at.is_(None)
        )
        
        if exclude_user_id:
            query = query.filter(User.id != exclude_user_id)
        
        return query.first() is not None

    def exists_by_phone(self, phone: str, exclude_user_id: Optional[str] = None) -> bool:
        """
        Check if phone number already exists.
        
        Args:
            phone: Phone to check
            exclude_user_id: User ID to exclude from check
            
        Returns:
            True if phone exists
        """
        query = self.db.query(User.id).filter(
            User.phone == phone,
            User.deleted_at.is_(None)
        )
        
        if exclude_user_id:
            query = query.filter(User.id != exclude_user_id)
        
        return query.first() is not None

    # ==================== Role-Based Queries ====================

    def find_by_role(
        self, 
        role: UserRole, 
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[User]:
        """
        Find users by role with optional active status filter.
        
        Args:
            role: User role to filter
            is_active: Filter by active status
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of users
        """
        query = self.db.query(User).filter(
            User.user_role == role,
            User.deleted_at.is_(None)
        )
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        return query.order_by(User.created_at.desc()).limit(limit).offset(offset).all()

    def count_by_role(self, role: UserRole, is_active: Optional[bool] = None) -> int:
        """
        Count users by role.
        
        Args:
            role: User role to count
            is_active: Filter by active status
            
        Returns:
            Count of users
        """
        query = self.db.query(func.count(User.id)).filter(
            User.user_role == role,
            User.deleted_at.is_(None)
        )
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        return query.scalar()

    def get_role_distribution(self) -> Dict[str, int]:
        """
        Get user count distribution by role.
        
        Returns:
            Dictionary mapping role to count
        """
        results = self.db.query(
            User.user_role,
            func.count(User.id).label('count')
        ).filter(
            User.deleted_at.is_(None)
        ).group_by(User.user_role).all()
        
        return {role.value: count for role, count in results}

    # ==================== Account Status Management ====================

    def find_active_users(
        self, 
        verified_only: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[User]:
        """
        Find active users with optional verification filter.
        
        Args:
            verified_only: Only return verified users
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of active users
        """
        query = self.db.query(User).filter(
            User.is_active == True,
            User.deleted_at.is_(None)
        )
        
        if verified_only:
            query = query.filter(
                User.is_email_verified == True,
                User.is_phone_verified == True
            )
        
        return query.order_by(User.created_at.desc()).limit(limit).offset(offset).all()

    def find_unverified_users(
        self, 
        verification_type: Optional[str] = None,
        older_than_days: Optional[int] = None
    ) -> List[User]:
        """
        Find users with pending verification.
        
        Args:
            verification_type: 'email', 'phone', or None for both
            older_than_days: Users registered more than X days ago
            
        Returns:
            List of unverified users
        """
        query = self.db.query(User).filter(User.deleted_at.is_(None))
        
        if verification_type == 'email':
            query = query.filter(User.is_email_verified == False)
        elif verification_type == 'phone':
            query = query.filter(User.is_phone_verified == False)
        else:
            query = query.filter(
                or_(
                    User.is_email_verified == False,
                    User.is_phone_verified == False
                )
            )
        
        if older_than_days:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
            query = query.filter(User.created_at < cutoff_date)
        
        return query.order_by(User.created_at).all()

    def find_inactive_users(self, inactive_days: int = 30) -> List[User]:
        """
        Find users inactive for specified period.
        
        Args:
            inactive_days: Days of inactivity threshold
            
        Returns:
            List of inactive users
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=inactive_days)
        
        return self.db.query(User).filter(
            User.is_active == True,
            User.deleted_at.is_(None),
            or_(
                User.last_login_at.is_(None),
                User.last_login_at < cutoff_date
            )
        ).order_by(User.last_login_at.asc()).all()

    def find_locked_accounts(self, include_expired: bool = False) -> List[User]:
        """
        Find currently locked accounts.
        
        Args:
            include_expired: Include accounts with expired locks
            
        Returns:
            List of locked users
        """
        query = self.db.query(User).filter(
            User.account_locked_until.isnot(None),
            User.deleted_at.is_(None)
        )
        
        if not include_expired:
            query = query.filter(
                User.account_locked_until > datetime.now(timezone.utc)
            )
        
        return query.order_by(User.account_locked_until.desc()).all()

    # ==================== Security Operations ====================

    def update_login_success(self, user_id: str, ip_address: Optional[str] = None) -> User:
        """
        Update user after successful login.
        
        Args:
            user_id: User ID
            ip_address: Login IP address
            
        Returns:
            Updated user
        """
        user = self.get_by_id(user_id)
        
        user.last_login_at = datetime.now(timezone.utc)
        user.failed_login_attempts = 0
        user.account_locked_until = None
        
        self.db.commit()
        self.db.refresh(user)
        
        return user

    def increment_failed_login(
        self, 
        user_id: str, 
        max_attempts: int = 5,
        lockout_duration_minutes: int = 30
    ) -> User:
        """
        Increment failed login attempts and lock if threshold exceeded.
        
        Args:
            user_id: User ID
            max_attempts: Maximum allowed attempts before lock
            lockout_duration_minutes: Lockout duration in minutes
            
        Returns:
            Updated user
        """
        user = self.get_by_id(user_id)
        
        user.failed_login_attempts += 1
        
        if user.failed_login_attempts >= max_attempts:
            user.account_locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=lockout_duration_minutes
            )
        
        self.db.commit()
        self.db.refresh(user)
        
        return user

    def unlock_account(self, user_id: str) -> User:
        """
        Manually unlock user account.
        
        Args:
            user_id: User ID
            
        Returns:
            Unlocked user
        """
        user = self.get_by_id(user_id)
        
        user.failed_login_attempts = 0
        user.account_locked_until = None
        
        self.db.commit()
        self.db.refresh(user)
        
        return user

    def update_password(
        self, 
        user_id: str, 
        password_hash: str,
        require_change: bool = False
    ) -> User:
        """
        Update user password and track change time.
        
        Args:
            user_id: User ID
            password_hash: New password hash
            require_change: Force password change on next login
            
        Returns:
            Updated user
        """
        user = self.get_by_id(user_id)
        
        user.password_hash = password_hash
        user.last_password_change_at = datetime.now(timezone.utc)
        user.password_reset_required = require_change
        
        self.db.commit()
        self.db.refresh(user)
        
        return user

    def find_password_reset_required(self) -> List[User]:
        """
        Find users requiring password reset.
        
        Returns:
            List of users with password_reset_required flag
        """
        return self.db.query(User).filter(
            User.password_reset_required == True,
            User.is_active == True,
            User.deleted_at.is_(None)
        ).all()

    def find_passwords_expiring_soon(self, days: int = 7, max_age_days: int = 90) -> List[User]:
        """
        Find users with passwords expiring soon.
        
        Args:
            days: Days before expiration to include
            max_age_days: Maximum password age before expiration
            
        Returns:
            List of users with expiring passwords
        """
        expiry_threshold = datetime.now(timezone.utc) - timedelta(days=max_age_days - days)
        expiry_cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        
        return self.db.query(User).filter(
            User.is_active == True,
            User.deleted_at.is_(None),
            User.last_password_change_at.isnot(None),
            User.last_password_change_at.between(expiry_cutoff, expiry_threshold)
        ).all()

    # ==================== Verification Operations ====================

    def verify_email(self, user_id: str) -> User:
        """
        Mark user email as verified.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated user
        """
        user = self.get_by_id(user_id)
        
        user.is_email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(user)
        
        return user

    def verify_phone(self, user_id: str) -> User:
        """
        Mark user phone as verified.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated user
        """
        user = self.get_by_id(user_id)
        
        user.is_phone_verified = True
        user.phone_verified_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(user)
        
        return user

    # ==================== Account Management ====================

    def activate_account(self, user_id: str) -> User:
        """
        Activate user account.
        
        Args:
            user_id: User ID
            
        Returns:
            Activated user
        """
        user = self.get_by_id(user_id)
        
        user.is_active = True
        user.deactivated_at = None
        user.deactivation_reason = None
        
        self.db.commit()
        self.db.refresh(user)
        
        return user

    def deactivate_account(self, user_id: str, reason: Optional[str] = None) -> User:
        """
        Deactivate user account.
        
        Args:
            user_id: User ID
            reason: Deactivation reason
            
        Returns:
            Deactivated user
        """
        user = self.get_by_id(user_id)
        
        user.is_active = False
        user.deactivated_at = datetime.now(timezone.utc)
        user.deactivation_reason = reason
        
        self.db.commit()
        self.db.refresh(user)
        
        return user

    def accept_terms(self, user_id: str, accept_privacy: bool = False) -> User:
        """
        Record terms and privacy policy acceptance.
        
        Args:
            user_id: User ID
            accept_privacy: Also accept privacy policy
            
        Returns:
            Updated user
        """
        user = self.get_by_id(user_id)
        
        now = datetime.now(timezone.utc)
        user.terms_accepted_at = now
        
        if accept_privacy:
            user.privacy_policy_accepted_at = now
        
        self.db.commit()
        self.db.refresh(user)
        
        return user

    # ==================== Analytics & Reporting ====================

    def get_user_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive user statistics.
        
        Returns:
            Dictionary with user metrics
        """
        total = self.db.query(func.count(User.id)).filter(
            User.deleted_at.is_(None)
        ).scalar()
        
        active = self.db.query(func.count(User.id)).filter(
            User.is_active == True,
            User.deleted_at.is_(None)
        ).scalar()
        
        verified = self.db.query(func.count(User.id)).filter(
            User.is_email_verified == True,
            User.is_phone_verified == True,
            User.deleted_at.is_(None)
        ).scalar()
        
        locked = self.db.query(func.count(User.id)).filter(
            User.account_locked_until.isnot(None),
            User.account_locked_until > datetime.now(timezone.utc),
            User.deleted_at.is_(None)
        ).scalar()
        
        return {
            "total_users": total,
            "active_users": active,
            "verified_users": verified,
            "locked_accounts": locked,
            "inactive_users": total - active,
            "verification_rate": (verified / total * 100) if total > 0 else 0
        }

    def get_registration_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get user registration trends.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            List of daily registration counts
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        results = self.db.query(
            func.date(User.created_at).label('date'),
            func.count(User.id).label('count'),
            User.user_role
        ).filter(
            User.created_at >= cutoff_date,
            User.deleted_at.is_(None)
        ).group_by(
            func.date(User.created_at),
            User.user_role
        ).order_by(func.date(User.created_at)).all()
        
        return [
            {
                "date": str(date),
                "count": count,
                "role": role.value
            }
            for date, count, role in results
        ]

    def search_users(
        self,
        search_term: Optional[str] = None,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[User]:
        """
        Advanced user search with multiple filters.
        
        Args:
            search_term: Search in name, email, phone
            role: Filter by role
            is_active: Filter by active status
            is_verified: Filter by verification status
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of matching users
        """
        query = self.db.query(User).filter(User.deleted_at.is_(None))
        
        if search_term:
            search_pattern = f"%{search_term}%"
            query = query.filter(
                or_(
                    User.full_name.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                    User.phone.like(search_pattern)
                )
            )
        
        if role:
            query = query.filter(User.user_role == role)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        if is_verified is not None:
            query = query.filter(
                User.is_email_verified == is_verified,
                User.is_phone_verified == is_verified
            )
        
        return query.order_by(User.created_at.desc()).limit(limit).offset(offset).all()