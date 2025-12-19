"""
User Aggregate Repository - Complex user queries with related data aggregation.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import func, and_, or_, desc, case
from sqlalchemy.orm import Session, joinedload, contains_eager

from app.models.user import (
    User, UserProfile, UserAddress, EmergencyContact, 
    UserSession, LoginHistory, PasswordHistory
)
from app.schemas.common.enums import UserRole
from app.repositories.base.base_repository import BaseRepository


class UserAggregateRepository:
    """
    Repository for complex user queries that aggregate data
    from multiple related entities. Provides comprehensive
    user insights and analytics.
    """

    def __init__(self, db: Session):
        self.db = db

    # ==================== Complete User Data ====================

    def get_complete_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete user data with all relationships.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with complete user information
        """
        user = self.db.query(User).options(
            joinedload(User.profile),
            joinedload(User.address),
            joinedload(User.emergency_contact)
        ).filter(User.id == user_id).first()
        
        if not user:
            return None
        
        # Get active sessions
        active_sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_revoked == False,
            UserSession.expires_at > datetime.now(timezone.utc)
        ).count()
        
        # Get recent login history
        recent_logins = self.db.query(LoginHistory).filter(
            LoginHistory.user_id == user_id
        ).order_by(desc(LoginHistory.created_at)).limit(5).all()
        
        return {
            "user": user,
            "profile": user.profile,
            "address": user.address,
            "emergency_contact": user.emergency_contact,
            "active_sessions_count": active_sessions,
            "recent_logins": recent_logins
        }

    def get_user_summary(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user summary with key metrics.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with user summary
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return None
        
        profile_completion = 0
        if user.profile:
            profile_completion = user.profile.profile_completion_percentage
        
        has_emergency_contact = user.emergency_contact is not None
        has_verified_address = (
            user.address is not None and 
            user.address.is_verified if user.address else False
        )
        
        total_sessions = self.db.query(func.count(UserSession.id)).filter(
            UserSession.user_id == user_id
        ).scalar()
        
        total_logins = self.db.query(func.count(LoginHistory.id)).filter(
            LoginHistory.user_id == user_id,
            LoginHistory.is_successful == True
        ).scalar()
        
        return {
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.user_role.value,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "profile_completion": profile_completion,
            "has_emergency_contact": has_emergency_contact,
            "has_verified_address": has_verified_address,
            "total_sessions": total_sessions,
            "total_logins": total_logins,
            "last_login": user.last_login_at,
            "member_since": user.created_at
        }

    # ==================== User Discovery & Search ====================

    def advanced_user_search(
        self,
        search_term: Optional[str] = None,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        has_profile: Optional[bool] = None,
        has_address: Optional[bool] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        registered_after: Optional[datetime] = None,
        registered_before: Optional[datetime] = None,
        min_profile_completion: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[User], int]:
        """
        Advanced user search with multiple filters.
        
        Args:
            search_term: Search in name, email, phone
            role: User role filter
            is_active: Active status filter
            is_verified: Verification status filter
            has_profile: Profile existence filter
            has_address: Address existence filter
            city: City filter
            state: State filter
            registered_after: Registration date lower bound
            registered_before: Registration date upper bound
            min_profile_completion: Minimum profile completion percentage
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            Tuple of (users list, total count)
        """
        query = self.db.query(User).outerjoin(User.profile).outerjoin(User.address)
        
        # Text search
        if search_term:
            search_pattern = f"%{search_term}%"
            query = query.filter(
                or_(
                    User.full_name.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                    User.phone.like(search_pattern)
                )
            )
        
        # Role filter
        if role:
            query = query.filter(User.user_role == role)
        
        # Status filters
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        if is_verified is not None:
            query = query.filter(
                User.is_email_verified == is_verified,
                User.is_phone_verified == is_verified
            )
        
        # Relationship existence filters
        if has_profile is not None:
            if has_profile:
                query = query.filter(UserProfile.id.isnot(None))
            else:
                query = query.filter(UserProfile.id.is_(None))
        
        if has_address is not None:
            if has_address:
                query = query.filter(UserAddress.id.isnot(None))
            else:
                query = query.filter(UserAddress.id.is_(None))
        
        # Geographic filters
        if city:
            query = query.filter(UserAddress.city.ilike(f"%{city}%"))
        
        if state:
            query = query.filter(UserAddress.state.ilike(f"%{state}%"))
        
        # Date filters
        if registered_after:
            query = query.filter(User.created_at >= registered_after)
        
        if registered_before:
            query = query.filter(User.created_at <= registered_before)
        
        # Profile completion filter
        if min_profile_completion is not None:
            query = query.filter(
                UserProfile.profile_completion_percentage >= min_profile_completion
            )
        
        # Soft delete filter
        query = query.filter(User.deleted_at.is_(None))
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        users = query.order_by(
            desc(User.created_at)
        ).limit(limit).offset(offset).all()
        
        return users, total

    # ==================== User Analytics ====================

    def get_platform_overview(self) -> Dict[str, Any]:
        """
        Get comprehensive platform-wide user analytics.
        
        Returns:
            Dictionary with platform metrics
        """
        # Basic counts
        total_users = self.db.query(func.count(User.id)).filter(
            User.deleted_at.is_(None)
        ).scalar()
        
        active_users = self.db.query(func.count(User.id)).filter(
            User.is_active == True,
            User.deleted_at.is_(None)
        ).scalar()
        
        verified_users = self.db.query(func.count(User.id)).filter(
            User.is_email_verified == True,
            User.is_phone_verified == True,
            User.deleted_at.is_(None)
        ).scalar()
        
        # Role distribution
        role_dist = self.db.query(
            User.user_role,
            func.count(User.id).label('count')
        ).filter(
            User.deleted_at.is_(None)
        ).group_by(User.user_role).all()
        
        # Recent activity
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)
        
        new_users_24h = self.db.query(func.count(User.id)).filter(
            User.created_at >= last_24h,
            User.deleted_at.is_(None)
        ).scalar()
        
        new_users_7d = self.db.query(func.count(User.id)).filter(
            User.created_at >= last_7d,
            User.deleted_at.is_(None)
        ).scalar()
        
        new_users_30d = self.db.query(func.count(User.id)).filter(
            User.created_at >= last_30d,
            User.deleted_at.is_(None)
        ).scalar()
        
        active_sessions = self.db.query(func.count(UserSession.id)).filter(
            UserSession.is_revoked == False,
            UserSession.expires_at > now
        ).scalar()
        
        # Profile completion stats
        avg_completion = self.db.query(
            func.avg(UserProfile.profile_completion_percentage)
        ).scalar()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "verified_users": verified_users,
            "verification_rate": (verified_users / total_users * 100) if total_users > 0 else 0,
            "role_distribution": {role.value: count for role, count in role_dist},
            "new_users": {
                "last_24_hours": new_users_24h,
                "last_7_days": new_users_7d,
                "last_30_days": new_users_30d
            },
            "active_sessions": active_sessions,
            "average_profile_completion": float(avg_completion) if avg_completion else 0
        }

    def get_user_growth_metrics(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get daily user growth metrics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            List of daily metrics
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Daily registrations
        daily_registrations = self.db.query(
            func.date(User.created_at).label('date'),
            func.count(User.id).label('registrations'),
            User.user_role
        ).filter(
            User.created_at >= cutoff,
            User.deleted_at.is_(None)
        ).group_by(
            func.date(User.created_at),
            User.user_role
        ).order_by(func.date(User.created_at)).all()
        
        # Aggregate by date
        daily_data = {}
        for date, count, role in daily_registrations:
            date_str = str(date)
            if date_str not in daily_data:
                daily_data[date_str] = {
                    "date": date_str,
                    "total": 0,
                    "by_role": {}
                }
            daily_data[date_str]["total"] += count
            daily_data[date_str]["by_role"][role.value] = count
        
        return list(daily_data.values())

    def get_engagement_metrics(self) -> Dict[str, Any]:
        """
        Get user engagement metrics.
        
        Returns:
            Dictionary with engagement statistics
        """
        now = datetime.now(timezone.utc)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)
        
        # Users who logged in recently
        active_7d = self.db.query(func.count(func.distinct(User.id))).filter(
            User.last_login_at >= last_7d,
            User.deleted_at.is_(None)
        ).scalar()
        
        active_30d = self.db.query(func.count(func.distinct(User.id))).filter(
            User.last_login_at >= last_30d,
            User.deleted_at.is_(None)
        ).scalar()
        
        total_active = self.db.query(func.count(User.id)).filter(
            User.is_active == True,
            User.deleted_at.is_(None)
        ).scalar()
        
        # Average session duration
        avg_session_duration = self.db.query(
            func.avg(
                func.extract('epoch', UserSession.last_activity - UserSession.created_at)
            )
        ).scalar()
        
        # Users with multiple sessions
        users_multiple_sessions = self.db.query(
            func.count(func.distinct(UserSession.user_id))
        ).filter(
            UserSession.is_revoked == False,
            UserSession.expires_at > now
        ).having(func.count(UserSession.id) > 1).scalar()
        
        return {
            "daily_active_users_7d": active_7d,
            "monthly_active_users_30d": active_30d,
            "dau_to_mau_ratio": (active_7d / active_30d * 100) if active_30d > 0 else 0,
            "engagement_rate_7d": (active_7d / total_active * 100) if total_active > 0 else 0,
            "average_session_duration_minutes": float(avg_session_duration / 60) if avg_session_duration else 0,
            "users_with_multiple_sessions": users_multiple_sessions or 0
        }

    # ==================== Security Analytics ====================

    def get_security_overview(self) -> Dict[str, Any]:
        """
        Get security-related metrics and statistics.
        
        Returns:
            Dictionary with security metrics
        """
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        
        # Account security
        locked_accounts = self.db.query(func.count(User.id)).filter(
            User.account_locked_until.isnot(None),
            User.account_locked_until > now,
            User.deleted_at.is_(None)
        ).scalar()
        
        unverified_users = self.db.query(func.count(User.id)).filter(
            or_(
                User.is_email_verified == False,
                User.is_phone_verified == False
            ),
            User.deleted_at.is_(None)
        ).scalar()
        
        password_reset_required = self.db.query(func.count(User.id)).filter(
            User.password_reset_required == True,
            User.deleted_at.is_(None)
        ).scalar()
        
        # Login activity
        failed_logins_24h = self.db.query(func.count(LoginHistory.id)).filter(
            LoginHistory.is_successful == False,
            LoginHistory.created_at >= last_24h
        ).scalar()
        
        suspicious_sessions = self.db.query(func.count(UserSession.id)).filter(
            UserSession.is_suspicious == True,
            UserSession.is_revoked == False
        ).scalar()
        
        # Recent password changes
        password_changes_24h = self.db.query(func.count(PasswordHistory.id)).filter(
            PasswordHistory.created_at >= last_24h
        ).scalar()
        
        return {
            "locked_accounts": locked_accounts,
            "unverified_users": unverified_users,
            "password_reset_required": password_reset_required,
            "failed_logins_last_24h": failed_logins_24h,
            "suspicious_active_sessions": suspicious_sessions,
            "password_changes_last_24h": password_changes_24h
        }

    # ==================== Completeness Analysis ====================

    def get_incomplete_profiles_report(self) -> Dict[str, Any]:
        """
        Get detailed report on profile completeness.
        
        Returns:
            Dictionary with completeness metrics
        """
        total_users = self.db.query(func.count(User.id)).filter(
            User.deleted_at.is_(None)
        ).scalar()
        
        without_profile = self.db.query(func.count(User.id)).outerjoin(
            UserProfile
        ).filter(
            User.deleted_at.is_(None),
            UserProfile.id.is_(None)
        ).scalar()
        
        without_address = self.db.query(func.count(User.id)).outerjoin(
            UserAddress
        ).filter(
            User.deleted_at.is_(None),
            UserAddress.id.is_(None)
        ).scalar()
        
        without_emergency_contact = self.db.query(func.count(User.id)).outerjoin(
            EmergencyContact
        ).filter(
            User.deleted_at.is_(None),
            EmergencyContact.id.is_(None)
        ).scalar()
        
        # Profile completion distribution
        completion_ranges = [
            (0, 25, "0-25%"),
            (26, 50, "26-50%"),
            (51, 75, "51-75%"),
            (76, 100, "76-100%")
        ]
        
        completion_dist = {}
        for min_val, max_val, label in completion_ranges:
            count = self.db.query(func.count(UserProfile.id)).filter(
                UserProfile.profile_completion_percentage.between(min_val, max_val)
            ).scalar()
            completion_dist[label] = count
        
        return {
            "total_users": total_users,
            "without_profile": without_profile,
            "without_address": without_address,
            "without_emergency_contact": without_emergency_contact,
            "profile_completion_distribution": completion_dist
        }

    # ==================== Bulk Operations ====================

    def bulk_verify_emails(self, user_ids: List[str]) -> int:
        """
        Bulk verify user emails.
        
        Args:
            user_ids: List of user IDs
            
        Returns:
            Count of updated users
        """
        now = datetime.now(timezone.utc)
        
        count = self.db.query(User).filter(
            User.id.in_(user_ids)
        ).update({
            "is_email_verified": True,
            "email_verified_at": now
        }, synchronize_session=False)
        
        self.db.commit()
        return count

    def bulk_deactivate_users(
        self, 
        user_ids: List[str],
        reason: Optional[str] = None
    ) -> int:
        """
        Bulk deactivate users.
        
        Args:
            user_ids: List of user IDs
            reason: Deactivation reason
            
        Returns:
            Count of deactivated users
        """
        now = datetime.now(timezone.utc)
        
        count = self.db.query(User).filter(
            User.id.in_(user_ids)
        ).update({
            "is_active": False,
            "deactivated_at": now,
            "deactivation_reason": reason
        }, synchronize_session=False)
        
        self.db.commit()
        return count

    # ==================== Cleanup Operations ====================

    def find_stale_unverified_users(self, days: int = 30) -> List[User]:
        """
        Find unverified users registered more than X days ago.
        
        Args:
            days: Days threshold
            
        Returns:
            List of stale unverified users
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        return self.db.query(User).filter(
            User.created_at < cutoff,
            or_(
                User.is_email_verified == False,
                User.is_phone_verified == False
            ),
            User.deleted_at.is_(None)
        ).all()

    def find_inactive_verified_users(self, days: int = 90) -> List[User]:
        """
        Find verified but inactive users.
        
        Args:
            days: Inactivity threshold in days
            
        Returns:
            List of inactive users
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        return self.db.query(User).filter(
            User.is_email_verified == True,
            User.is_phone_verified == True,
            User.is_active == True,
            or_(
                User.last_login_at.is_(None),
                User.last_login_at < cutoff
            ),
            User.deleted_at.is_(None)
        ).all()