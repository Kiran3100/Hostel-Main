# --- File: C:\Hostel-Main\app\services\user\user_analytics_service.py ---
"""
User Analytics Service - Comprehensive user analytics and insights.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.repositories.user import (
    UserRepository,
    UserProfileRepository,
    UserAddressRepository,
    EmergencyContactRepository,
    UserSessionRepository,
    UserAggregateRepository
)
from app.repositories.user.user_security_repository import UserSecurityRepository


class UserAnalyticsService:
    """
    Service for user analytics, metrics, and insights.
    Provides comprehensive reporting for admin dashboards.
    """

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.profile_repo = UserProfileRepository(db)
        self.address_repo = UserAddressRepository(db)
        self.contact_repo = EmergencyContactRepository(db)
        self.session_repo = UserSessionRepository(db)
        self.aggregate_repo = UserAggregateRepository(db)
        self.security_repo = UserSecurityRepository(db)

    # ==================== Dashboard Metrics ====================

    def get_dashboard_overview(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard overview.
        
        Returns:
            Dashboard metrics
        """
        # Platform overview
        platform_overview = self.aggregate_repo.get_platform_overview()
        
        # User statistics
        user_stats = self.user_repo.get_user_statistics()
        
        # Profile statistics
        profile_stats = self.profile_repo.get_profile_statistics()
        
        # Security overview
        security_overview = self.aggregate_repo.get_security_overview()
        
        # Recent activity
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        
        recent_registrations = self.db.query(func.count(User.id)).filter(
            User.created_at >= last_24h,
            User.deleted_at.is_(None)
        ).scalar()
        
        recent_logins = self.security_repo.get_login_statistics(days=1)
        
        return {
            'overview': platform_overview,
            'user_stats': user_stats,
            'profile_stats': profile_stats,
            'security': security_overview,
            'recent_activity': {
                'registrations_24h': recent_registrations,
                'successful_logins_24h': recent_logins.get('successful_logins', 0),
                'failed_logins_24h': recent_logins.get('failed_logins', 0)
            },
            'generated_at': now.isoformat()
        }

    # ==================== User Growth Analytics ====================

    def get_growth_metrics(
        self,
        days: int = 30,
        granularity: str = 'day'
    ) -> Dict[str, Any]:
        """
        Get detailed user growth metrics.
        
        Args:
            days: Number of days to analyze
            granularity: Time granularity (day, week, month)
            
        Returns:
            Growth metrics
        """
        # Daily growth
        daily_growth = self.aggregate_repo.get_user_growth_metrics(days)
        
        # Registration trends
        registration_trends = self.user_repo.get_registration_trends(days)
        
        # Role distribution over time
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Calculate growth rate
        total_users = self.user_repo.count_all()
        users_at_start = self.db.query(func.count(User.id)).filter(
            User.created_at < cutoff,
            User.deleted_at.is_(None)
        ).scalar()
        
        growth_count = total_users - users_at_start
        growth_rate = (growth_count / users_at_start * 100) if users_at_start > 0 else 0
        
        return {
            'period_days': days,
            'total_users_now': total_users,
            'users_at_period_start': users_at_start,
            'new_users_in_period': growth_count,
            'growth_rate_percentage': round(growth_rate, 2),
            'average_daily_registrations': round(growth_count / days, 2),
            'daily_breakdown': daily_growth,
            'registration_trends': registration_trends
        }

    def get_retention_metrics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get user retention metrics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Retention metrics
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Users registered in period
        users_in_period = self.db.query(User).filter(
            User.created_at >= cutoff,
            User.deleted_at.is_(None)
        ).all()
        
        # Active users in period
        active_users = [
            u for u in users_in_period
            if u.last_login_at and u.last_login_at >= cutoff
        ]
        
        # Verified users
        verified_users = [
            u for u in users_in_period
            if u.is_verified
        ]
        
        retention_rate = (len(active_users) / len(users_in_period) * 100) if users_in_period else 0
        verification_rate = (len(verified_users) / len(users_in_period) * 100) if users_in_period else 0
        
        return {
            'period_days': days,
            'users_registered': len(users_in_period),
            'users_active': len(active_users),
            'users_verified': len(verified_users),
            'retention_rate': round(retention_rate, 2),
            'verification_rate': round(verification_rate, 2)
        }

    # ==================== Engagement Analytics ====================

    def get_engagement_metrics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get detailed user engagement metrics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Engagement metrics
        """
        engagement = self.aggregate_repo.get_engagement_metrics()
        
        # Session statistics
        session_stats = self.session_repo.get_session_statistics()
        session_duration = self.session_repo.get_session_duration_stats()
        
        # Login frequency
        login_stats = self.security_repo.get_login_statistics(days=days)
        
        return {
            'period_days': days,
            'engagement_overview': engagement,
            'session_metrics': session_stats,
            'session_duration': session_duration,
            'login_metrics': login_stats
        }

    def get_user_activity_heatmap(self, days: int = 7) -> Dict[str, Any]:
        """
        Get user activity heatmap data (hourly distribution).
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Heatmap data
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        from app.models.user import LoginHistory
        
        # Get login attempts by hour
        login_by_hour = self.db.query(
            func.extract('hour', LoginHistory.created_at).label('hour'),
            func.count(LoginHistory.id).label('count')
        ).filter(
            LoginHistory.created_at >= cutoff,
            LoginHistory.is_successful == True
        ).group_by('hour').all()
        
        # Format for heatmap
        hourly_activity = {int(hour): count for hour, count in login_by_hour}
        
        # Fill missing hours with 0
        for hour in range(24):
            if hour not in hourly_activity:
                hourly_activity[hour] = 0
        
        return {
            'period_days': days,
            'hourly_activity': hourly_activity,
            'peak_hour': max(hourly_activity, key=hourly_activity.get),
            'peak_hour_count': max(hourly_activity.values())
        }

    # ==================== Demographic Analytics ====================

    def get_demographic_insights(self) -> Dict[str, Any]:
        """
        Get comprehensive demographic insights.
        
        Returns:
            Demographic data
        """
        # Demographics from profiles
        demographics = self.profile_repo.get_demographics_statistics()
        
        # Geographic distribution
        geographic = self.address_repo.get_geographic_distribution()
        
        # Language distribution
        languages = self.profile_repo.get_language_distribution()
        
        # Role distribution
        roles = self.user_repo.get_role_distribution()
        
        return {
            'demographics': demographics,
            'geographic_distribution': geographic,
            'language_distribution': languages,
            'role_distribution': roles
        }

    # ==================== Security Analytics ====================

    def get_security_insights(self, days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive security insights.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Security insights
        """
        # Platform security overview
        security_overview = self.aggregate_repo.get_security_overview()
        
        # Login statistics
        login_stats = self.security_repo.get_login_statistics(days=days)
        
        # Password change statistics
        password_stats = self.security_repo.get_password_change_statistics(days=days)
        
        # Suspicious sessions
        suspicious_sessions = self.session_repo.find_suspicious_sessions(limit=50)
        
        # Failed login attempts by IP
        from app.models.user import LoginHistory
        
        failed_by_ip = self.db.query(
            LoginHistory.ip_address,
            func.count(LoginHistory.id).label('count')
        ).filter(
            LoginHistory.is_successful == False,
            LoginHistory.created_at >= datetime.now(timezone.utc) - timedelta(days=days)
        ).group_by(LoginHistory.ip_address).order_by(
            func.count(LoginHistory.id).desc()
        ).limit(10).all()
        
        return {
            'period_days': days,
            'overview': security_overview,
            'login_statistics': login_stats,
            'password_statistics': password_stats,
            'suspicious_sessions_count': len(suspicious_sessions),
            'top_failed_login_ips': [
                {'ip': ip, 'failed_attempts': count}
                for ip, count in failed_by_ip
            ]
        }

    # ==================== Profile Completion Analytics ====================

    def get_profile_completion_insights(self) -> Dict[str, Any]:
        """
        Get profile completion insights.
        
        Returns:
            Profile completion data
        """
        # Profile statistics
        profile_stats = self.profile_repo.get_profile_statistics()
        
        # Incomplete profiles report
        incomplete = self.aggregate_repo.get_incomplete_profiles_report()
        
        # Address statistics
        address_stats = self.address_repo.get_verification_statistics()
        
        # Emergency contact statistics
        contact_stats = self.contact_repo.get_contact_statistics()
        
        return {
            'profile_stats': profile_stats,
            'incomplete_profiles': incomplete,
            'address_completion': address_stats,
            'emergency_contact_completion': contact_stats
        }

    # ==================== Verification Analytics ====================

    def get_verification_insights(self) -> Dict[str, Any]:
        """
        Get verification insights.
        
        Returns:
            Verification data
        """
        total_users = self.user_repo.count_all()
        
        # Email verification
        email_verified = self.db.query(func.count(User.id)).filter(
            User.is_email_verified == True,
            User.deleted_at.is_(None)
        ).scalar()
        
        # Phone verification
        phone_verified = self.db.query(func.count(User.id)).filter(
            User.is_phone_verified == True,
            User.deleted_at.is_(None)
        ).scalar()
        
        # Fully verified
        fully_verified = self.db.query(func.count(User.id)).filter(
            User.is_email_verified == True,
            User.is_phone_verified == True,
            User.deleted_at.is_(None)
        ).scalar()
        
        # Unverified users by age
        unverified_by_age = {
            'less_than_7_days': len(self.user_repo.find_unverified_users(older_than_days=None)),
            '7_to_30_days': len(self.user_repo.find_unverified_users(older_than_days=7)),
            'more_than_30_days': len(self.user_repo.find_unverified_users(older_than_days=30))
        }
        
        return {
            'total_users': total_users,
            'email_verified_count': email_verified,
            'email_verification_rate': round(email_verified / total_users * 100, 2) if total_users > 0 else 0,
            'phone_verified_count': phone_verified,
            'phone_verification_rate': round(phone_verified / total_users * 100, 2) if total_users > 0 else 0,
            'fully_verified_count': fully_verified,
            'full_verification_rate': round(fully_verified / total_users * 100, 2) if total_users > 0 else 0,
            'unverified_by_registration_age': unverified_by_age
        }

    # ==================== Cohort Analysis ====================

    def get_cohort_analysis(
        self,
        start_date: datetime,
        end_date: datetime,
        cohort_by: str = 'month'
    ) -> Dict[str, Any]:
        """
        Get cohort analysis for user retention.
        
        Args:
            start_date: Analysis start date
            end_date: Analysis end date
            cohort_by: Cohort grouping (day, week, month)
            
        Returns:
            Cohort analysis data
        """
        # This is a simplified version
        # In production, implement proper cohort retention analysis
        
        users = self.db.query(User).filter(
            User.created_at.between(start_date, end_date),
            User.deleted_at.is_(None)
        ).all()
        
        cohorts = {}
        
        for user in users:
            if cohort_by == 'month':
                cohort_key = user.created_at.strftime('%Y-%m')
            elif cohort_by == 'week':
                cohort_key = user.created_at.strftime('%Y-W%W')
            else:
                cohort_key = user.created_at.strftime('%Y-%m-%d')
            
            if cohort_key not in cohorts:
                cohorts[cohort_key] = {
                    'total_users': 0,
                    'active_users': 0,
                    'retention_rate': 0
                }
            
            cohorts[cohort_key]['total_users'] += 1
            
            if user.last_login_at and user.last_login_at >= end_date - timedelta(days=30):
                cohorts[cohort_key]['active_users'] += 1
        
        # Calculate retention rates
        for cohort in cohorts.values():
            if cohort['total_users'] > 0:
                cohort['retention_rate'] = round(
                    cohort['active_users'] / cohort['total_users'] * 100, 2
                )
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'cohort_by': cohort_by,
            'cohorts': cohorts
        }

    # ==================== Comparison Reports ====================

    def get_period_comparison(
        self,
        current_days: int = 30,
        compare_to_previous: bool = True
    ) -> Dict[str, Any]:
        """
        Compare current period with previous period.
        
        Args:
            current_days: Current period in days
            compare_to_previous: Compare to previous equal period
            
        Returns:
            Comparison data
        """
        now = datetime.now(timezone.utc)
        current_start = now - timedelta(days=current_days)
        
        # Current period metrics
        current_users = self.db.query(func.count(User.id)).filter(
            User.created_at >= current_start,
            User.deleted_at.is_(None)
        ).scalar()
        
        current_logins = self.security_repo.get_login_statistics(days=current_days)
        
        # Previous period metrics
        if compare_to_previous:
            previous_start = current_start - timedelta(days=current_days)
            previous_end = current_start
            
            previous_users = self.db.query(func.count(User.id)).filter(
                User.created_at.between(previous_start, previous_end),
                User.deleted_at.is_(None)
            ).scalar()
            
            # Calculate changes
            user_change = current_users - previous_users
            user_change_percent = (user_change / previous_users * 100) if previous_users > 0 else 0
            
            return {
                'current_period': {
                    'days': current_days,
                    'start': current_start.isoformat(),
                    'end': now.isoformat(),
                    'new_users': current_users,
                    'login_stats': current_logins
                },
                'previous_period': {
                    'days': current_days,
                    'start': previous_start.isoformat(),
                    'end': previous_end.isoformat(),
                    'new_users': previous_users
                },
                'comparison': {
                    'user_growth': user_change,
                    'user_growth_percent': round(user_change_percent, 2),
                    'trend': 'up' if user_change > 0 else 'down' if user_change < 0 else 'stable'
                }
            }
        
        return {
            'current_period': {
                'days': current_days,
                'start': current_start.isoformat(),
                'end': now.isoformat(),
                'new_users': current_users,
                'login_stats': current_logins
            }
        }

    # ==================== Export Reports ====================

    def generate_comprehensive_report(
        self,
        include_demographics: bool = True,
        include_security: bool = True,
        include_engagement: bool = True,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate comprehensive analytics report.
        
        Args:
            include_demographics: Include demographic data
            include_security: Include security data
            include_engagement: Include engagement data
            days: Analysis period
            
        Returns:
            Comprehensive report
        """
        report = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'period_days': days,
            'dashboard_overview': self.get_dashboard_overview()
        }
        
        if include_demographics:
            report['demographics'] = self.get_demographic_insights()
            report['profile_completion'] = self.get_profile_completion_insights()
            report['verification'] = self.get_verification_insights()
        
        if include_security:
            report['security'] = self.get_security_insights(days)
        
        if include_engagement:
            report['engagement'] = self.get_engagement_metrics(days)
            report['growth'] = self.get_growth_metrics(days)
            report['retention'] = self.get_retention_metrics(days)
        
        return report


