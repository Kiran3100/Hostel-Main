"""
Social Authentication Repository
Manages OAuth providers, tokens, profiles, and account linking.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import Session

from app.models.auth import (
    SocialAuthProvider,
    SocialAuthToken,
    SocialAuthProfile,
    SocialAuthLink,
)
from app.repositories.base.base_repository import BaseRepository


class SocialAuthProviderRepository(BaseRepository[SocialAuthProvider]):
    """
    Repository for OAuth provider configuration management.
    """

    def __init__(self, db: Session):
        super().__init__(SocialAuthProvider, db)

    def create_provider(
        self,
        provider_name: str,
        display_name: str,
        client_id: str,
        client_secret: str,
        authorization_url: str,
        token_url: str,
        user_info_url: str,
        default_scopes: Optional[List[str]] = None,
        icon_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SocialAuthProvider:
        """
        Create OAuth provider configuration.
        
        Args:
            provider_name: Provider identifier (google, facebook, etc.)
            display_name: Display name for UI
            client_id: OAuth client ID
            client_secret: OAuth client secret (should be encrypted)
            authorization_url: Authorization endpoint
            token_url: Token endpoint
            user_info_url: User info endpoint
            default_scopes: Default OAuth scopes
            icon_url: Provider icon URL
            metadata: Additional configuration
            
        Returns:
            Created SocialAuthProvider instance
        """
        provider = SocialAuthProvider(
            provider_name=provider_name,
            display_name=display_name,
            client_id=client_id,
            client_secret=client_secret,
            authorization_url=authorization_url,
            token_url=token_url,
            user_info_url=user_info_url,
            default_scopes=default_scopes,
            icon_url=icon_url,
            metadata=metadata,
        )
        
        self.db.add(provider)
        self.db.commit()
        self.db.refresh(provider)
        return provider

    def find_by_name(self, provider_name: str) -> Optional[SocialAuthProvider]:
        """Find provider by name."""
        return self.db.query(SocialAuthProvider).filter(
            SocialAuthProvider.provider_name == provider_name
        ).first()

    def get_enabled_providers(self) -> List[SocialAuthProvider]:
        """Get all enabled OAuth providers."""
        return self.db.query(SocialAuthProvider).filter(
            SocialAuthProvider.is_enabled == True
        ).all()

    def enable_provider(self, provider_id: UUID) -> bool:
        """Enable OAuth provider."""
        provider = self.find_by_id(provider_id)
        if provider:
            provider.is_enabled = True
            self.db.commit()
            return True
        return False

    def disable_provider(self, provider_id: UUID) -> bool:
        """Disable OAuth provider."""
        provider = self.find_by_id(provider_id)
        if provider:
            provider.is_enabled = False
            self.db.commit()
            return True
        return False


class SocialAuthTokenRepository(BaseRepository[SocialAuthToken]):
    """
    Repository for OAuth token management.
    """

    def __init__(self, db: Session):
        super().__init__(SocialAuthToken, db)

    def create_token(
        self,
        user_id: UUID,
        provider_id: UUID,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_type: str = "Bearer",
        expires_in: Optional[int] = None,
        scopes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SocialAuthToken:
        """
        Create or update OAuth token.
        
        Args:
            user_id: User identifier
            provider_id: OAuth provider ID
            access_token: Access token (should be encrypted)
            refresh_token: Refresh token (should be encrypted)
            token_type: Token type
            expires_in: Token expiration in seconds
            scopes: Granted OAuth scopes
            metadata: Additional metadata
            
        Returns:
            Created/Updated SocialAuthToken instance
        """
        # Check if token already exists
        existing_token = self.find_by_user_and_provider(user_id, provider_id)
        
        if existing_token:
            # Update existing token
            existing_token.update_tokens(access_token, refresh_token, expires_in)
            if scopes:
                existing_token.scopes = scopes
            if metadata:
                existing_token.metadata = metadata
            self.db.commit()
            return existing_token
        
        # Create new token
        expires_at = None
        if expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        token = SocialAuthToken(
            user_id=user_id,
            provider_id=provider_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=token_type,
            expires_at=expires_at,
            scopes=scopes,
            metadata=metadata,
        )
        
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    def find_by_user_and_provider(
        self,
        user_id: UUID,
        provider_id: UUID
    ) -> Optional[SocialAuthToken]:
        """Find token for user and provider."""
        return self.db.query(SocialAuthToken).filter(
            and_(
                SocialAuthToken.user_id == user_id,
                SocialAuthToken.provider_id == provider_id
            )
        ).first()

    def find_user_tokens(self, user_id: UUID) -> List[SocialAuthToken]:
        """Get all social auth tokens for user."""
        return self.db.query(SocialAuthToken).filter(
            SocialAuthToken.user_id == user_id
        ).all()

    def refresh_token(
        self,
        token_id: UUID,
        new_access_token: str,
        new_refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None
    ) -> bool:
        """Refresh OAuth token."""
        token = self.find_by_id(token_id)
        if token:
            token.update_tokens(new_access_token, new_refresh_token, expires_in)
            self.db.commit()
            return True
        return False

    def revoke_token(self, token_id: UUID) -> bool:
        """Revoke OAuth token."""
        token = self.find_by_id(token_id)
        if token:
            self.db.delete(token)
            self.db.commit()
            return True
        return False

    def get_expired_tokens(self) -> List[SocialAuthToken]:
        """Get all expired tokens that need refresh."""
        return self.db.query(SocialAuthToken).filter(
            and_(
                SocialAuthToken.expires_at.isnot(None),
                SocialAuthToken.expires_at < datetime.utcnow(),
                SocialAuthToken.refresh_token.isnot(None)
            )
        ).all()


class SocialAuthProfileRepository(BaseRepository[SocialAuthProfile]):
    """
    Repository for social profile data management.
    """

    def __init__(self, db: Session):
        super().__init__(SocialAuthProfile, db)

    def create_or_update_profile(
        self,
        user_id: UUID,
        provider_id: UUID,
        provider_user_id: str,
        profile_data: Dict[str, Any]
    ) -> SocialAuthProfile:
        """
        Create or update social profile.
        
        Args:
            user_id: User identifier
            provider_id: OAuth provider ID
            provider_user_id: User ID from provider
            profile_data: Profile data from provider
            
        Returns:
            Created/Updated SocialAuthProfile instance
        """
        # Check if profile exists
        existing_profile = self.find_by_user_and_provider(user_id, provider_id)
        
        if existing_profile:
            # Update existing profile
            existing_profile.sync_profile(profile_data)
            self.db.commit()
            return existing_profile
        
        # Create new profile
        profile = SocialAuthProfile(
            user_id=user_id,
            provider_id=provider_id,
            provider_user_id=provider_user_id,
            email=profile_data.get("email"),
            full_name=profile_data.get("name"),
            first_name=profile_data.get("given_name"),
            last_name=profile_data.get("family_name"),
            profile_picture_url=profile_data.get("picture"),
            gender=profile_data.get("gender"),
            locale=profile_data.get("locale"),
            email_verified=profile_data.get("email_verified", False),
            raw_profile_data=profile_data,
        )
        
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def find_by_user_and_provider(
        self,
        user_id: UUID,
        provider_id: UUID
    ) -> Optional[SocialAuthProfile]:
        """Find profile for user and provider."""
        return self.db.query(SocialAuthProfile).filter(
            and_(
                SocialAuthProfile.user_id == user_id,
                SocialAuthProfile.provider_id == provider_id
            )
        ).first()

    def find_by_provider_user_id(
        self,
        provider_id: UUID,
        provider_user_id: str
    ) -> Optional[SocialAuthProfile]:
        """Find profile by provider user ID."""
        return self.db.query(SocialAuthProfile).filter(
            and_(
                SocialAuthProfile.provider_id == provider_id,
                SocialAuthProfile.provider_user_id == provider_user_id
            )
        ).first()

    def find_user_profiles(self, user_id: UUID) -> List[SocialAuthProfile]:
        """Get all social profiles for user."""
        return self.db.query(SocialAuthProfile).filter(
            SocialAuthProfile.user_id == user_id
        ).all()

    def sync_profile(
        self,
        profile_id: UUID,
        profile_data: Dict[str, Any]
    ) -> bool:
        """Sync profile data from provider."""
        profile = self.find_by_id(profile_id)
        if profile:
            profile.sync_profile(profile_data)
            self.db.commit()
            return True
        return False

    def get_profiles_needing_sync(
        self,
        hours_old: int = 24
    ) -> List[SocialAuthProfile]:
        """Get profiles that need syncing."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)
        
        return self.db.query(SocialAuthProfile).filter(
            SocialAuthProfile.last_synced_at < cutoff_time
        ).all()


class SocialAuthLinkRepository(BaseRepository[SocialAuthLink]):
    """
    Repository for social account linking management.
    """

    def __init__(self, db: Session):
        super().__init__(SocialAuthLink, db)

    def create_link(
        self,
        user_id: UUID,
        provider_id: UUID,
        link_method: str = "manual_link",
        is_primary: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SocialAuthLink:
        """
        Create social account link.
        
        Args:
            user_id: User identifier
            provider_id: OAuth provider ID
            link_method: How account was linked
            is_primary: Whether this is primary auth method
            metadata: Additional metadata
            
        Returns:
            Created SocialAuthLink instance
        """
        link = SocialAuthLink(
            user_id=user_id,
            provider_id=provider_id,
            link_method=link_method,
            is_primary=is_primary,
            metadata=metadata,
        )
        
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return link

    def find_by_user_and_provider(
        self,
        user_id: UUID,
        provider_id: UUID
    ) -> Optional[SocialAuthLink]:
        """Find link for user and provider."""
        return self.db.query(SocialAuthLink).filter(
            and_(
                SocialAuthLink.user_id == user_id,
                SocialAuthLink.provider_id == provider_id
            )
        ).first()

    def find_user_links(
        self,
        user_id: UUID,
        active_only: bool = True
    ) -> List[SocialAuthLink]:
        """Get all social account links for user."""
        query = self.db.query(SocialAuthLink).filter(
            SocialAuthLink.user_id == user_id
        )
        
        if active_only:
            query = query.filter(SocialAuthLink.is_linked == True)
        
        return query.all()

    def unlink_account(
        self,
        link_id: UUID,
        reason: Optional[str] = None
    ) -> bool:
        """Unlink social account."""
        link = self.find_by_id(link_id)
        if link and link.is_linked:
            link.unlink(reason)
            self.db.commit()
            return True
        return False

    def relink_account(self, link_id: UUID) -> bool:
        """Relink previously unlinked account."""
        link = self.find_by_id(link_id)
        if link and not link.is_linked:
            link.relink()
            self.db.commit()
            return True
        return False

    def set_primary_link(
        self,
        user_id: UUID,
        provider_id: UUID
    ) -> bool:
        """Set a social account as primary authentication method."""
        # First, remove primary status from all links
        self.db.query(SocialAuthLink).filter(
            SocialAuthLink.user_id == user_id
        ).update({"is_primary": False})
        
        # Set new primary
        link = self.find_by_user_and_provider(user_id, provider_id)
        if link and link.is_linked:
            link.is_primary = True
            self.db.commit()
            return True
        
        return False

    def get_primary_link(self, user_id: UUID) -> Optional[SocialAuthLink]:
        """Get primary social auth link for user."""
        return self.db.query(SocialAuthLink).filter(
            and_(
                SocialAuthLink.user_id == user_id,
                SocialAuthLink.is_linked == True,
                SocialAuthLink.is_primary == True
            )
        ).first()

    def count_active_links(self, user_id: UUID) -> int:
        """Count active social account links."""
        return self.db.query(func.count(SocialAuthLink.id)).filter(
            and_(
                SocialAuthLink.user_id == user_id,
                SocialAuthLink.is_linked == True
            )
        ).scalar() or 0

    def get_link_statistics(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get social auth link statistics."""
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        total_links = self.db.query(func.count(SocialAuthLink.id)).filter(
            SocialAuthLink.created_at >= cutoff_time
        ).scalar()
        
        active_links = self.db.query(func.count(SocialAuthLink.id)).filter(
            and_(
                SocialAuthLink.is_linked == True,
                SocialAuthLink.created_at >= cutoff_time
            )
        ).scalar()
        
        unlinked = total_links - active_links
        
        # Get provider breakdown
        provider_breakdown = self.db.query(
            SocialAuthLink.provider_id,
            func.count(SocialAuthLink.id)
        ).filter(
            and_(
                SocialAuthLink.is_linked == True,
                SocialAuthLink.created_at >= cutoff_time
            )
        ).group_by(SocialAuthLink.provider_id).all()
        
        return {
            "total_links": total_links,
            "active_links": active_links,
            "unlinked": unlinked,
            "retention_rate": (active_links / total_links * 100) if total_links > 0 else 0,
            "provider_breakdown": {
                str(provider_id): count for provider_id, count in provider_breakdown
            }
        }