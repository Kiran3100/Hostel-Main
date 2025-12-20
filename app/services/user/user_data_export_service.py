# --- File: C:\Hostel-Main\app\services\user\user_data_export_service.py ---
"""
User Data Export Service - GDPR compliance and data portability.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import json

from app.models.user import User
from app.repositories.user import (
    UserRepository,
    UserProfileRepository,
    UserAddressRepository,
    EmergencyContactRepository,
    UserSessionRepository,
    UserAggregateRepository
)
from app.core.exceptions import EntityNotFoundError


class UserDataExportService:
    """
    Service for exporting user data for GDPR compliance,
    data portability, and backup purposes.
    """

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.profile_repo = UserProfileRepository(db)
        self.address_repo = UserAddressRepository(db)
        self.contact_repo = EmergencyContactRepository(db)
        self.session_repo = UserSessionRepository(db)
        self.aggregate_repo = UserAggregateRepository(db)

    # ==================== Complete Data Export ====================

    def export_user_data(
        self,
        user_id: str,
        include_sensitive: bool = False
    ) -> Dict[str, Any]:
        """
        Export complete user data.
        
        Args:
            user_id: User ID
            include_sensitive: Include sensitive data (sessions, security logs)
            
        Returns:
            Dictionary with all user data
            
        Raises:
            EntityNotFoundError: If user not found
        """
        user = self.user_repo.get_by_id(user_id)
        
        export_data = {
            'export_metadata': {
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'user_id': user_id,
                'format_version': '1.0'
            },
            'user': self._export_user_basic(user, include_sensitive),
            'profile': self._export_profile(user_id),
            'addresses': self._export_addresses(user_id),
            'emergency_contacts': self._export_emergency_contacts(user_id)
        }
        
        if include_sensitive:
            export_data['sessions'] = self._export_sessions(user_id)
            export_data['security'] = self._export_security_data(user_id)
        
        return export_data

    def _export_user_basic(
        self,
        user: User,
        include_sensitive: bool
    ) -> Dict[str, Any]:
        """Export basic user information."""
        data = {
            'id': user.id,
            'email': user.email,
            'phone': user.phone,
            'full_name': user.full_name,
            'user_role': user.user_role.value,
            'is_active': user.is_active,
            'is_email_verified': user.is_email_verified,
            'is_phone_verified': user.is_phone_verified,
            'email_verified_at': user.email_verified_at.isoformat() if user.email_verified_at else None,
            'phone_verified_at': user.phone_verified_at.isoformat() if user.phone_verified_at else None,
            'registration_source': user.registration_source,
            'referral_code': user.referral_code,
            'created_at': user.created_at.isoformat(),
            'updated_at': user.updated_at.isoformat()
        }
        
        if include_sensitive:
            data.update({
                'registration_ip': user.registration_ip,
                'last_login_at': user.last_login_at.isoformat() if user.last_login_at else None,
                'last_password_change_at': user.last_password_change_at.isoformat() if user.last_password_change_at else None,
                'failed_login_attempts': user.failed_login_attempts,
                'account_locked_until': user.account_locked_until.isoformat() if user.account_locked_until else None,
                'terms_accepted_at': user.terms_accepted_at.isoformat() if user.terms_accepted_at else None,
                'privacy_policy_accepted_at': user.privacy_policy_accepted_at.isoformat() if user.privacy_policy_accepted_at else None
            })
        
        return data

    def _export_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Export user profile data."""
        profile = self.profile_repo.find_by_user_id(user_id)
        
        if not profile:
            return None
        
        return {
            'gender': profile.gender.value if profile.gender else None,
            'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else None,
            'nationality': profile.nationality,
            'bio': profile.bio,
            'occupation': profile.occupation,
            'organization': profile.organization,
            'profile_image_url': profile.profile_image_url,
            'cover_image_url': profile.cover_image_url,
            'profile_completion_percentage': profile.profile_completion_percentage,
            'preferred_language': profile.preferred_language,
            'timezone': profile.timezone,
            'notification_preferences': profile.notification_preferences,
            'privacy_settings': profile.privacy_settings,
            'communication_preferences': profile.communication_preferences,
            'social_links': profile.social_links,
            'custom_fields': profile.custom_fields,
            'profile_views': profile.profile_views,
            'last_profile_update': profile.last_profile_update.isoformat() if profile.last_profile_update else None,
            'created_at': profile.created_at.isoformat(),
            'updated_at': profile.updated_at.isoformat()
        }

    def _export_addresses(self, user_id: str) -> list:
        """Export user addresses."""
        addresses = self.address_repo.find_by_user_id(user_id)
        
        return [
            {
                'id': addr.id,
                'address_type': addr.address_type,
                'is_primary': addr.is_primary,
                'address_line1': addr.address_line1,
                'address_line2': addr.address_line2,
                'landmark': addr.landmark,
                'city': addr.city,
                'state': addr.state,
                'country': addr.country,
                'pincode': addr.pincode,
                'latitude': float(addr.latitude) if addr.latitude else None,
                'longitude': float(addr.longitude) if addr.longitude else None,
                'is_verified': addr.is_verified,
                'verified_at': addr.verified_at.isoformat() if addr.verified_at else None,
                'verification_method': addr.verification_method,
                'label': addr.label,
                'instructions': addr.instructions,
                'is_active': addr.is_active,
                'created_at': addr.created_at.isoformat(),
                'updated_at': addr.updated_at.isoformat()
            }
            for addr in addresses
        ]

    def _export_emergency_contacts(self, user_id: str) -> list:
        """Export emergency contacts."""
        contacts = self.contact_repo.find_by_user_id(user_id, active_only=False)
        
        return [
            {
                'id': contact.id,
                'name': contact.emergency_contact_name,
                'phone': contact.emergency_contact_phone,
                'alternate_phone': contact.emergency_contact_alternate_phone,
                'email': contact.emergency_contact_email,
                'relation': contact.emergency_contact_relation,
                'priority': contact.priority,
                'is_primary': contact.is_primary,
                'address': contact.contact_address,
                'is_verified': contact.is_verified,
                'verified_at': contact.verified_at.isoformat() if contact.verified_at else None,
                'consent_given': contact.consent_given,
                'consent_date': contact.consent_date.isoformat() if contact.consent_date else None,
                'can_make_decisions': contact.can_make_decisions,
                'can_access_medical_info': contact.can_access_medical_info,
                'notes': contact.notes,
                'is_active': contact.is_active,
                'created_at': contact.created_at.isoformat(),
                'updated_at': contact.updated_at.isoformat()
            }
            for contact in contacts
        ]

    def _export_sessions(self, user_id: str) -> list:
        """Export user sessions."""
        sessions = self.session_repo.find_by_user_id(
            user_id,
            active_only=False,
            limit=100
        )
        
        return [
            {
                'id': session.id,
                'device_info': session.device_info,
                'ip_address': session.ip_address,
                'ip_location': session.ip_location,
                'session_type': session.session_type,
                'is_remember_me': session.is_remember_me,
                'is_revoked': session.is_revoked,
                'revoked_at': session.revoked_at.isoformat() if session.revoked_at else None,
                'revocation_reason': session.revocation_reason,
                'created_at': session.created_at.isoformat(),
                'expires_at': session.expires_at.isoformat(),
                'last_activity': session.last_activity.isoformat(),
                'requests_count': session.requests_count
            }
            for session in sessions
        ]

    def _export_security_data(self, user_id: str) -> Dict[str, Any]:
        """Export security-related data."""
        # This would include login history, password changes, etc.
        # For now, return basic structure
        return {
            'login_history_available': True,
            'password_change_history_available': True,
            'note': 'Detailed security logs available on request'
        }

    # ==================== Export Formats ====================

    def export_as_json(
        self,
        user_id: str,
        include_sensitive: bool = False,
        pretty: bool = True
    ) -> str:
        """
        Export user data as JSON string.
        
        Args:
            user_id: User ID
            include_sensitive: Include sensitive data
            pretty: Pretty print JSON
            
        Returns:
            JSON string
        """
        data = self.export_user_data(user_id, include_sensitive)
        
        if pretty:
            return json.dumps(data, indent=2, default=str)
        return json.dumps(data, default=str)

    def export_to_file(
        self,
        user_id: str,
        filepath: str,
        include_sensitive: bool = False
    ) -> str:
        """
        Export user data to JSON file.
        
        Args:
            user_id: User ID
            filepath: Output file path
            include_sensitive: Include sensitive data
            
        Returns:
            File path
        """
        json_data = self.export_as_json(user_id, include_sensitive, pretty=True)
        
        with open(filepath, 'w') as f:
            f.write(json_data)
        
        return filepath

    # ==================== Data Anonymization ====================

    def anonymize_user_data(self, user_id: str) -> User:
        """
        Anonymize user data (GDPR right to be forgotten).
        
        Args:
            user_id: User ID
            
        Returns:
            Anonymized user
        """
        user = self.user_repo.get_by_id(user_id)
        
        # Anonymize user
        anonymized_email = f"deleted_{user.id}@anonymized.com"
        anonymized_phone = f"+00000{user.id[-6:]}"
        
        self.user_repo.update(user.id, {
            'email': anonymized_email,
            'phone': anonymized_phone,
            'full_name': 'Deleted User',
            'is_active': False
        })
        
        # Anonymize profile
        profile = self.profile_repo.find_by_user_id(user_id)
        if profile:
            self.profile_repo.update(profile.id, {
                'bio': None,
                'profile_image_url': None,
                'social_links': None,
                'custom_fields': None
            })
        
        # Delete addresses
        addresses = self.address_repo.find_by_user_id(user_id)
        for addr in addresses:
            self.address_repo.delete(addr.id)
        
        # Delete emergency contacts
        contacts = self.contact_repo.find_by_user_id(user_id)
        for contact in contacts:
            self.contact_repo.delete(contact.id)
        
        # Soft delete user
        return self.user_repo.soft_delete(user_id)

    # ==================== Data Summary ====================

    def get_data_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get summary of user data stored.
        
        Args:
            user_id: User ID
            
        Returns:
            Data summary
        """
        user = self.user_repo.get_by_id(user_id)
        profile = self.profile_repo.find_by_user_id(user_id)
        addresses = self.address_repo.find_by_user_id(user_id)
        contacts = self.contact_repo.find_by_user_id(user_id)
        sessions = self.session_repo.find_by_user_id(user_id, active_only=False)
        
        return {
            'user_id': user_id,
            'email': user.email,
            'full_name': user.full_name,
            'has_profile': profile is not None,
            'addresses_count': len(addresses),
            'emergency_contacts_count': len(contacts),
            'sessions_count': len(sessions),
            'account_created': user.created_at.isoformat(),
            'last_updated': user.updated_at.isoformat(),
            'data_categories': {
                'basic_info': True,
                'profile': profile is not None,
                'addresses': len(addresses) > 0,
                'emergency_contacts': len(contacts) > 0,
                'sessions': len(sessions) > 0
            }
        }


