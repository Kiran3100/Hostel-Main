"""
Social Authentication Service
OAuth integration and social login management.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
import requests

from sqlalchemy.orm import Session

from app.repositories.auth import (
    SocialAuthProviderRepository,
    SocialAuthTokenRepository,
    SocialAuthProfileRepository,
    SocialAuthLinkRepository,
)
from app.repositories.auth import SecurityEventRepository
from app.services.auth.session_service import SessionService
from app.services.auth.token_service import TokenService
from app.core.exceptions import (
    SocialAuthError,
    ProviderNotFoundError,
    AccountLinkingError,
)


class SocialAuthService:
    """
    Service for social authentication and OAuth operations.
    """

    def __init__(self, db: Session):
        self.db = db
        self.provider_repo = SocialAuthProviderRepository(db)
        self.token_repo = SocialAuthTokenRepository(db)
        self.profile_repo = SocialAuthProfileRepository(db)
        self.link_repo = SocialAuthLinkRepository(db)
        self.security_event_repo = SecurityEventRepository(db)
        self.session_service = SessionService(db)
        self.token_service = TokenService(db)

    # ==================== OAuth Flow ====================

    def get_authorization_url(
        self,
        provider_name: str,
        redirect_uri: str,
        state: str,
        scopes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get OAuth authorization URL.
        
        Args:
            provider_name: OAuth provider name
            redirect_uri: Callback URL
            state: CSRF state token
            scopes: OAuth scopes to request
            
        Returns:
            Dictionary with authorization URL and state
            
        Raises:
            ProviderNotFoundError: If provider doesn't exist or is disabled
        """
        provider = self.provider_repo.find_by_name(provider_name)
        
        if not provider or not provider.is_enabled:
            raise ProviderNotFoundError(f"Provider {provider_name} not available")
        
        # Use provider's default scopes if none specified
        request_scopes = scopes or provider.default_scopes or []
        
        # Build authorization URL
        scope_string = " ".join(request_scopes)
        
        auth_url = (
            f"{provider.authorization_url}"
            f"?client_id={provider.client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&scope={scope_string}"
            f"&state={state}"
            f"&response_type=code"
        )
        
        return {
            "authorization_url": auth_url,
            "state": state,
            "provider": provider_name
        }

    def exchange_code_for_token(
        self,
        provider_name: str,
        code: str,
        redirect_uri: str
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            provider_name: OAuth provider name
            code: Authorization code
            redirect_uri: Callback URL
            
        Returns:
            Dictionary with OAuth tokens
            
        Raises:
            SocialAuthError: If token exchange fails
        """
        provider = self.provider_repo.find_by_name(provider_name)
        
        if not provider:
            raise ProviderNotFoundError(f"Provider {provider_name} not found")
        
        # Prepare token request
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": provider.client_id,
            "client_secret": provider.client_secret
        }
        
        try:
            # Exchange code for token
            response = requests.post(
                provider.token_url,
                data=token_data,
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            
            token_response = response.json()
            
            return {
                "access_token": token_response.get("access_token"),
                "refresh_token": token_response.get("refresh_token"),
                "token_type": token_response.get("token_type", "Bearer"),
                "expires_in": token_response.get("expires_in"),
                "scope": token_response.get("scope")
            }
            
        except requests.RequestException as e:
            raise SocialAuthError(f"Failed to exchange code for token: {str(e)}")

    def get_user_profile(
        self,
        provider_name: str,
        access_token: str
    ) -> Dict[str, Any]:
        """
        Get user profile from OAuth provider.
        
        Args:
            provider_name: OAuth provider name
            access_token: OAuth access token
            
        Returns:
            User profile data
            
        Raises:
            SocialAuthError: If profile fetch fails
        """
        provider = self.provider_repo.find_by_name(provider_name)
        
        if not provider:
            raise ProviderNotFoundError(f"Provider {provider_name} not found")
        
        try:
            # Fetch user profile
            response = requests.get(
                provider.user_info_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                }
            )
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            raise SocialAuthError(f"Failed to fetch user profile: {str(e)}")

    # ==================== Social Login ====================

    def social_login(
        self,
        provider_name: str,
        code: str,
        redirect_uri: str,
        ip_address: str,
        user_agent: str,
        device_fingerprint: Optional[str] = None,
        country: Optional[str] = None,
        city: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete social login flow.
        
        Args:
            provider_name: OAuth provider name
            code: Authorization code
            redirect_uri: Callback URL
            ip_address: Request IP address
            user_agent: Request user agent
            device_fingerprint: Device fingerprint
            country: Country from geolocation
            city: City from geolocation
            
        Returns:
            Dictionary with authentication result
            
        Raises:
            SocialAuthError: If login fails
        """
        # Exchange code for token
        oauth_tokens = self.exchange_code_for_token(
            provider_name=provider_name,
            code=code,
            redirect_uri=redirect_uri
        )
        
        # Get user profile
        profile_data = self.get_user_profile(
            provider_name=provider_name,
            access_token=oauth_tokens["access_token"]
        )
        
        # Get provider
        provider = self.provider_repo.find_by_name(provider_name)
        
        # Extract provider user ID
        provider_user_id = self._extract_provider_user_id(
            provider_name=provider_name,
            profile_data=profile_data
        )
        
        # Check if social account is already linked
        existing_profile = self.profile_repo.find_by_provider_user_id(
            provider_id=provider.id,
            provider_user_id=provider_user_id
        )
        
        if existing_profile:
            # Existing user - login
            user_id = existing_profile.user_id
            
            # Update tokens
            self.token_repo.create_token(
                user_id=user_id,
                provider_id=provider.id,
                access_token=oauth_tokens["access_token"],
                refresh_token=oauth_tokens.get("refresh_token"),
                expires_in=oauth_tokens.get("expires_in")
            )
            
            # Update profile
            self.profile_repo.sync_profile(
                profile_id=existing_profile.id,
                profile_data=profile_data
            )
            
            # Create session
            session_data = self.session_service.create_session(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=device_fingerprint,
                country=country,
                city=city
            )
            
            # Record security event
            self.security_event_repo.record_event(
                event_type="social_login",
                severity="low",
                description=f"User logged in via {provider_name}",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            return {
                "user_id": user_id,
                "is_new_user": False,
                "session_id": session_data["session_id"],
                "access_token": session_data["tokens"]["access_token"],
                "refresh_token": session_data["tokens"]["refresh_token"],
                "token_type": session_data["tokens"]["token_type"],
                "expires_in": session_data["tokens"]["expires_in"]
            }
        else:
            # New user - needs registration
            return {
                "is_new_user": True,
                "requires_registration": True,
                "provider": provider_name,
                "provider_user_id": provider_user_id,
                "profile_data": profile_data,
                "oauth_tokens": oauth_tokens
            }

    def complete_social_registration(
        self,
        provider_name: str,
        provider_user_id: str,
        profile_data: Dict[str, Any],
        oauth_tokens: Dict[str, Any],
        additional_user_data: Optional[Dict[str, Any]],
        ip_address: str,
        user_agent: str,
        device_fingerprint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete social registration for new user.
        
        Args:
            provider_name: OAuth provider name
            provider_user_id: User ID from provider
            profile_data: Profile data from provider
            oauth_tokens: OAuth tokens
            additional_user_data: Additional user data for registration
            ip_address: Request IP address
            user_agent: Request user agent
            device_fingerprint: Device fingerprint
            
        Returns:
            Dictionary with registration result
        """
        # Get provider
        provider = self.provider_repo.find_by_name(provider_name)
        
        # Create user account
        user = self._create_user_from_social_profile(
            profile_data=profile_data,
            additional_data=additional_user_data
        )
        
        # Create social profile
        self.profile_repo.create_or_update_profile(
            user_id=user.id,
            provider_id=provider.id,
            provider_user_id=provider_user_id,
            profile_data=profile_data
        )
        
        # Store OAuth tokens
        self.token_repo.create_token(
            user_id=user.id,
            provider_id=provider.id,
            access_token=oauth_tokens["access_token"],
            refresh_token=oauth_tokens.get("refresh_token"),
            expires_in=oauth_tokens.get("expires_in")
        )
        
        # Create account link
        self.link_repo.create_link(
            user_id=user.id,
            provider_id=provider.id,
            link_method="social_signup",
            is_primary=True
        )
        
        # Create session
        session_data = self.session_service.create_session(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint
        )
        
        # Record security event
        self.security_event_repo.record_event(
            event_type="social_registration",
            severity="low",
            description=f"New user registered via {provider_name}",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return {
            "user_id": user.id,
            "is_new_user": True,
            "session_id": session_data["session_id"],
            "access_token": session_data["tokens"]["access_token"],
            "refresh_token": session_data["tokens"]["refresh_token"],
            "token_type": session_data["tokens"]["token_type"],
            "expires_in": session_data["tokens"]["expires_in"]
        }

    # ==================== Account Linking ====================

    def link_social_account(
        self,
        user_id: UUID,
        provider_name: str,
        code: str,
        redirect_uri: str,
        ip_address: str,
        user_agent: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Link social account to existing user.
        
        Args:
            user_id: User identifier
            provider_name: OAuth provider name
            code: Authorization code
            redirect_uri: Callback URL
            ip_address: Request IP address
            user_agent: Request user agent
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Exchange code for token
            oauth_tokens = self.exchange_code_for_token(
                provider_name=provider_name,
                code=code,
                redirect_uri=redirect_uri
            )
            
            # Get user profile
            profile_data = self.get_user_profile(
                provider_name=provider_name,
                access_token=oauth_tokens["access_token"]
            )
            
            # Get provider
            provider = self.provider_repo.find_by_name(provider_name)
            
            # Extract provider user ID
            provider_user_id = self._extract_provider_user_id(
                provider_name=provider_name,
                profile_data=profile_data
            )
            
            # Check if this social account is already linked to another user
            existing_profile = self.profile_repo.find_by_provider_user_id(
                provider_id=provider.id,
                provider_user_id=provider_user_id
            )
            
            if existing_profile and existing_profile.user_id != user_id:
                raise AccountLinkingError(
                    "This social account is already linked to another user"
                )
            
            # Create or update profile
            self.profile_repo.create_or_update_profile(
                user_id=user_id,
                provider_id=provider.id,
                provider_user_id=provider_user_id,
                profile_data=profile_data
            )
            
            # Store OAuth tokens
            self.token_repo.create_token(
                user_id=user_id,
                provider_id=provider.id,
                access_token=oauth_tokens["access_token"],
                refresh_token=oauth_tokens.get("refresh_token"),
                expires_in=oauth_tokens.get("expires_in")
            )
            
            # Create or update link
            existing_link = self.link_repo.find_by_user_and_provider(
                user_id=user_id,
                provider_id=provider.id
            )
            
            if existing_link:
                self.link_repo.relink_account(existing_link.id)
            else:
                self.link_repo.create_link(
                    user_id=user_id,
                    provider_id=provider.id,
                    link_method="manual_link"
                )
            
            # Record security event
            self.security_event_repo.record_event(
                event_type="social_account_linked",
                severity="medium",
                description=f"Social account linked: {provider_name}",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            return True, None
            
        except Exception as e:
            return False, str(e)

    def unlink_social_account(
        self,
        user_id: UUID,
        provider_name: str,
        ip_address: str,
        user_agent: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Unlink social account from user.
        
        Args:
            user_id: User identifier
            provider_name: OAuth provider name
            ip_address: Request IP address
            user_agent: Request user agent
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            provider = self.provider_repo.find_by_name(provider_name)
            
            if not provider:
                return False, f"Provider {provider_name} not found"
            
            # Find link
            link = self.link_repo.find_by_user_and_provider(
                user_id=user_id,
                provider_id=provider.id
            )
            
            if not link or not link.is_linked:
                return False, "Social account is not linked"
            
            # Check if this is the only authentication method
            active_links_count = self.link_repo.count_active_links(user_id)
            
            # Get user to check if they have a password
            user = self._get_user(user_id)
            has_password = user.password_hash is not None if user else False
            
            if active_links_count == 1 and not has_password:
                return False, (
                    "Cannot unlink the only authentication method. "
                    "Please set a password first."
                )
            
            # Unlink account
            self.link_repo.unlink_account(
                link_id=link.id,
                reason="User requested unlinking"
            )
            
            # Revoke OAuth token
            token = self.token_repo.find_by_user_and_provider(
                user_id=user_id,
                provider_id=provider.id
            )
            if token:
                self.token_repo.revoke_token(token.id)
            
            # Record security event
            self.security_event_repo.record_event(
                event_type="social_account_unlinked",
                severity="medium",
                description=f"Social account unlinked: {provider_name}",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            return True, None
            
        except Exception as e:
            return False, str(e)

    # ==================== Token Management ====================

    def refresh_social_token(
        self,
        user_id: UUID,
        provider_name: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Refresh OAuth access token.
        
        Args:
            user_id: User identifier
            provider_name: OAuth provider name
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            provider = self.provider_repo.find_by_name(provider_name)
            
            if not provider:
                return False, f"Provider {provider_name} not found"
            
            # Get current token
            token = self.token_repo.find_by_user_and_provider(
                user_id=user_id,
                provider_id=provider.id
            )
            
            if not token or not token.refresh_token:
                return False, "No refresh token available"
            
            # Prepare refresh request
            refresh_data = {
                "grant_type": "refresh_token",
                "refresh_token": token.refresh_token,
                "client_id": provider.client_id,
                "client_secret": provider.client_secret
            }
            
            # Request new token
            response = requests.post(
                provider.token_url,
                data=refresh_data,
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            
            token_response = response.json()
            
            # Update token
            self.token_repo.refresh_token(
                token_id=token.id,
                new_access_token=token_response.get("access_token"),
                new_refresh_token=token_response.get("refresh_token"),
                expires_in=token_response.get("expires_in")
            )
            
            return True, None
            
        except Exception as e:
            return False, f"Failed to refresh token: {str(e)}"

    def sync_social_profile(
        self,
        user_id: UUID,
        provider_name: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Sync user profile from social provider.
        
        Args:
            user_id: User identifier
            provider_name: OAuth provider name
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            provider = self.provider_repo.find_by_name(provider_name)
            
            if not provider:
                return False, f"Provider {provider_name} not found"
            
            # Get token
            token = self.token_repo.find_by_user_and_provider(
                user_id=user_id,
                provider_id=provider.id
            )
            
            if not token:
                return False, "Social account not linked"
            
            # Check if token is expired
            if token.is_expired():
                # Try to refresh
                refresh_success, refresh_error = self.refresh_social_token(
                    user_id=user_id,
                    provider_name=provider_name
                )
                if not refresh_success:
                    return False, "Token expired and refresh failed"
            
            # Fetch updated profile
            profile_data = self.get_user_profile(
                provider_name=provider_name,
                access_token=token.access_token
            )
            
            # Update profile
            profile = self.profile_repo.find_by_user_and_provider(
                user_id=user_id,
                provider_id=provider.id
            )
            
            if profile:
                self.profile_repo.sync_profile(
                    profile_id=profile.id,
                    profile_data=profile_data
                )
            
            return True, None
            
        except Exception as e:
            return False, f"Failed to sync profile: {str(e)}"

    # ==================== Provider Management ====================

    def get_enabled_providers(self) -> List[Dict[str, Any]]:
        """
        Get list of enabled OAuth providers.
        
        Returns:
            List of provider information
        """
        providers = self.provider_repo.get_enabled_providers()
        
        return [
            {
                "name": provider.provider_name,
                "display_name": provider.display_name,
                "icon_url": provider.icon_url
            }
            for provider in providers
        ]

    def get_user_linked_accounts(self, user_id: UUID) -> List[Dict[str, Any]]:
        """
        Get user's linked social accounts.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of linked accounts
        """
        links = self.link_repo.find_user_links(user_id, active_only=True)
        
        return [
            {
                "provider": link.provider.provider_name,
                "display_name": link.provider.display_name,
                "linked_at": link.linked_at,
                "is_primary": link.is_primary
            }
            for link in links
        ]

    def set_primary_social_account(
        self,
        user_id: UUID,
        provider_name: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Set a social account as primary authentication method.
        
        Args:
            user_id: User identifier
            provider_name: OAuth provider name
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            provider = self.provider_repo.find_by_name(provider_name)
            
            if not provider:
                return False, f"Provider {provider_name} not found"
            
            success = self.link_repo.set_primary_link(
                user_id=user_id,
                provider_id=provider.id
            )
            
            if success:
                return True, None
            else:
                return False, "Social account is not linked"
                
        except Exception as e:
            return False, str(e)

    # ==================== Helper Methods ====================

    def _extract_provider_user_id(
        self,
        provider_name: str,
        profile_data: Dict[str, Any]
    ) -> str:
        """Extract user ID from provider profile data."""
        # Different providers use different field names
        id_fields = {
            "google": "sub",
            "facebook": "id",
            "github": "id",
            "apple": "sub",
            "microsoft": "id",
            "linkedin": "id"
        }
        
        field_name = id_fields.get(provider_name.lower(), "id")
        return str(profile_data.get(field_name))

    def _create_user_from_social_profile(
        self,
        profile_data: Dict[str, Any],
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Create user account from social profile.
        This is a placeholder - implement based on your User model.
        """
        from app.models.user import User
        
        email = profile_data.get("email")
        name = profile_data.get("name", "")
        
        user = User(
            email=email,
            full_name=name,
            email_verified=profile_data.get("email_verified", False),
            is_active=True,
            **(additional_data or {})
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        return user

    def _get_user(self, user_id: UUID) -> Optional[Any]:
        """Get user by ID."""
        from app.models.user import User
        
        return self.db.query(User).filter(User.id == user_id).first()

    # ==================== Statistics ====================

    def get_social_auth_statistics(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get social authentication statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with statistics
        """
        return self.link_repo.get_link_statistics(days=days)