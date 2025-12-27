"""
Social authentication service: OAuth integration for Google, Facebook, etc.

Handles OAuth 2.0 flows, token validation, and user provisioning
for social login providers.
"""

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.user import UserRepository
from app.repositories.auth import (
    SocialAuthProviderRepository,
    SocialAuthTokenRepository,
    SocialAuthProfileRepository,
    SocialAuthLinkRepository,
    UserSessionRepository,
)
from app.schemas.auth.social_auth import (
    SocialAuthRequest,
    GoogleAuthRequest,
    FacebookAuthRequest,
    SocialAuthResponse,
    SocialUserInfo,
    SocialProfileData,
    SocialProvider,
)
from app.models.user.user import User
from app.core1.security.jwt_handler import JWTManager

logger = logging.getLogger(__name__)


class SocialAuthService(BaseService[User, UserRepository]):
    """
    Handle OAuth-based social authentication flows.
    
    Features:
    - Google OAuth 2.0 integration
    - Facebook OAuth 2.0 integration
    - User account linking
    - Profile synchronization
    - Token management
    - Auto-provisioning for new users
    """

    # Configuration
    ACCESS_TOKEN_EXPIRE_MINUTES = 60
    REFRESH_TOKEN_EXPIRE_DAYS = 30
    DEFAULT_NEW_USER_ROLE = "VISITOR"

    def __init__(
        self,
        user_repository: UserRepository,
        provider_repo: SocialAuthProviderRepository,
        token_repo: SocialAuthTokenRepository,
        profile_repo: SocialAuthProfileRepository,
        link_repo: SocialAuthLinkRepository,
        session_repo: UserSessionRepository,
        db_session: Session,
    ):
        super().__init__(user_repository, db_session)
        self.provider_repo = provider_repo
        self.token_repo = token_repo
        self.profile_repo = profile_repo
        self.link_repo = link_repo
        self.session_repo = session_repo
        self.jwt = JWTManager()

    # -------------------------------------------------------------------------
    # Google Authentication
    # -------------------------------------------------------------------------

    def google_login(
        self,
        request: GoogleAuthRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ServiceResult[SocialAuthResponse]:
        """
        Authenticate user via Google OAuth.
        
        Args:
            request: Google auth request with ID token
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            ServiceResult with authentication response
        """
        try:
            # Verify Google ID token
            verified_data = self.provider_repo.verify_google_token(request)
            
            if not verified_data or not verified_data.email:
                logger.warning(f"Invalid Google token verification")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid Google authentication token",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Get or create user
            user, is_new_user = self._get_or_create_social_user(
                provider=SocialProvider.GOOGLE,
                provider_user_id=verified_data.provider_user_id,
                email=verified_data.email,
                full_name=verified_data.full_name,
                profile_picture_url=verified_data.profile_picture_url,
            )

            # Store/update social auth profile
            self._update_social_profile(
                user_id=user.id,
                provider=SocialProvider.GOOGLE,
                profile_data=verified_data,
            )

            # Generate authentication tokens
            response = self._create_social_auth_response(
                user=user,
                is_new_user=is_new_user,
                provider=SocialProvider.GOOGLE,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            self.db.commit()

            logger.info(
                f"Google login successful for user: {user.id} "
                f"({'new user' if is_new_user else 'existing user'})"
            )
            
            return ServiceResult.success(
                response,
                message="Google authentication successful",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during Google login: {str(e)}")
            return self._handle_exception(e, "google login")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during Google login: {str(e)}")
            return self._handle_exception(e, "google login")

    # -------------------------------------------------------------------------
    # Facebook Authentication
    # -------------------------------------------------------------------------

    def facebook_login(
        self,
        request: FacebookAuthRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ServiceResult[SocialAuthResponse]:
        """
        Authenticate user via Facebook OAuth.
        
        Args:
            request: Facebook auth request with access token
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            ServiceResult with authentication response
        """
        try:
            # Verify Facebook access token
            verified_data = self.provider_repo.verify_facebook_token(request)
            
            if not verified_data or not verified_data.email:
                logger.warning(f"Invalid Facebook token verification")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid Facebook authentication token",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Get or create user
            user, is_new_user = self._get_or_create_social_user(
                provider=SocialProvider.FACEBOOK,
                provider_user_id=verified_data.provider_user_id,
                email=verified_data.email,
                full_name=verified_data.full_name,
                profile_picture_url=verified_data.profile_picture_url,
            )

            # Store/update social auth profile
            self._update_social_profile(
                user_id=user.id,
                provider=SocialProvider.FACEBOOK,
                profile_data=verified_data,
            )

            # Generate authentication tokens
            response = self._create_social_auth_response(
                user=user,
                is_new_user=is_new_user,
                provider=SocialProvider.FACEBOOK,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            self.db.commit()

            logger.info(
                f"Facebook login successful for user: {user.id} "
                f"({'new user' if is_new_user else 'existing user'})"
            )
            
            return ServiceResult.success(
                response,
                message="Facebook authentication successful",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during Facebook login: {str(e)}")
            return self._handle_exception(e, "facebook login")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during Facebook login: {str(e)}")
            return self._handle_exception(e, "facebook login")

    # -------------------------------------------------------------------------
    # Account Linking
    # -------------------------------------------------------------------------

    def link_social_account(
        self,
        user_id: UUID,
        provider: str,
        request: SocialAuthRequest,
    ) -> ServiceResult[bool]:
        """
        Link social account to existing user.
        
        Args:
            user_id: Existing user ID
            provider: Social provider name
            request: Social auth request
            
        Returns:
            ServiceResult with success status
        """
        try:
            # Verify user exists
            user = self.repository.get_by_id(user_id)
            if not user:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="User not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Verify social provider token based on provider type
            if provider == SocialProvider.GOOGLE:
                verified_data = self.provider_repo.verify_google_token(request)
            elif provider == SocialProvider.FACEBOOK:
                verified_data = self.provider_repo.verify_facebook_token(request)
            else:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Unsupported provider: {provider}",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            if not verified_data:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid authentication token",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Check if already linked
            existing_link = self.link_repo.get_by_provider_user_id(
                provider=provider,
                provider_user_id=verified_data.provider_user_id,
            )

            if existing_link:
                if existing_link.user_id == user_id:
                    logger.info(
                        f"Social account already linked: {provider} for user: {user_id}"
                    )
                    return ServiceResult.success(
                        True,
                        message="Social account already linked",
                    )
                else:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message="This social account is linked to another user",
                            severity=ErrorSeverity.WARNING,
                        )
                    )

            # Create link
            self.link_repo.create({
                "user_id": user_id,
                "provider": provider,
                "provider_user_id": verified_data.provider_user_id,
                "linked_at": datetime.utcnow(),
            })

            # Update social profile
            self._update_social_profile(
                user_id=user_id,
                provider=provider,
                profile_data=verified_data,
            )

            self.db.commit()

            logger.info(f"Social account linked: {provider} for user: {user_id}")
            return ServiceResult.success(
                True,
                message=f"{provider} account linked successfully",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error linking social account: {str(e)}")
            return self._handle_exception(e, "link social account", user_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error linking social account: {str(e)}")
            return self._handle_exception(e, "link social account", user_id)

    def unlink_social_account(
        self,
        user_id: UUID,
        provider: str,
    ) -> ServiceResult[bool]:
        """
        Unlink social account from user.
        
        Args:
            user_id: User identifier
            provider: Social provider name
            
        Returns:
            ServiceResult with success status
        """
        try:
            # Check if link exists
            link = self.link_repo.get_by_user_and_provider(
                user_id=user_id,
                provider=provider,
            )

            if not link:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No {provider} account linked",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Ensure user has other authentication methods
            user = self.repository.get_by_id(user_id)
            if not user.password_hash:
                # Check if other social accounts are linked
                other_links = self.link_repo.get_by_user(user_id)
                if len(other_links) <= 1:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=(
                                "Cannot unlink last authentication method. "
                                "Set a password first."
                            ),
                            severity=ErrorSeverity.WARNING,
                        )
                    )

            # Delete link
            self.link_repo.delete(link.id)
            self.db.commit()

            logger.info(f"Social account unlinked: {provider} for user: {user_id}")
            return ServiceResult.success(
                True,
                message=f"{provider} account unlinked successfully",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error unlinking social account: {str(e)}")
            return self._handle_exception(e, "unlink social account", user_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error unlinking social account: {str(e)}")
            return self._handle_exception(e, "unlink social account", user_id)

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _get_or_create_social_user(
        self,
        provider: str,
        provider_user_id: str,
        email: str,
        full_name: Optional[str],
        profile_picture_url: Optional[str],
    ) -> tuple[User, bool]:
        """
        Get existing user or create new one for social login.
        
        Args:
            provider: Social provider name
            provider_user_id: Provider's user ID
            email: User email
            full_name: User's full name
            profile_picture_url: Profile picture URL
            
        Returns:
            Tuple of (User, is_new_user)
        """
        # Check if user has previously linked this social account
        existing_link = self.link_repo.get_by_provider_user_id(
            provider=provider,
            provider_user_id=provider_user_id,
        )

        if existing_link:
            user = self.repository.get_by_id(existing_link.user_id)
            if user:
                # Update profile picture if not set
                if profile_picture_url and not user.profile_image_url:
                    self.repository.update(user.id, {
                        "profile_image_url": profile_picture_url,
                    })
                    self.db.flush()
                return user, False

        # Check if user exists by email
        user = self.repository.find_by_email(email)
        
        if user:
            # Link social account to existing user
            self.link_repo.create({
                "user_id": user.id,
                "provider": provider,
                "provider_user_id": provider_user_id,
                "linked_at": datetime.utcnow(),
            })
            
            # Update profile picture if not set
            if profile_picture_url and not user.profile_image_url:
                self.repository.update(user.id, {
                    "profile_image_url": profile_picture_url,
                })
            
            self.db.flush()
            return user, False

        # Create new user
        user_data = {
            "email": email,
            "full_name": full_name or email.split("@")[0],
            "user_role": self.DEFAULT_NEW_USER_ROLE,
            "is_active": True,
            "email_verified_at": datetime.utcnow(),  # Social accounts are pre-verified
            "profile_image_url": profile_picture_url,
        }

        user = self.repository.create(user_data)
        self.db.flush()

        # Create social link
        self.link_repo.create({
            "user_id": user.id,
            "provider": provider,
            "provider_user_id": provider_user_id,
            "linked_at": datetime.utcnow(),
        })
        self.db.flush()

        logger.info(f"New user created via {provider} social login: {user.id}")
        return user, True

    def _update_social_profile(
        self,
        user_id: UUID,
        provider: str,
        profile_data: SocialProfileData,
    ) -> None:
        """Update or create social profile data."""
        try:
            profile = self.profile_repo.get_by_user_and_provider(
                user_id=user_id,
                provider=provider,
            )

            profile_dict = {
                "user_id": user_id,
                "provider": provider,
                "provider_user_id": profile_data.provider_user_id,
                "email": profile_data.email,
                "full_name": profile_data.full_name,
                "profile_picture_url": profile_data.profile_picture_url,
                "raw_data": profile_data.raw_data,
                "updated_at": datetime.utcnow(),
            }

            if profile:
                self.profile_repo.update(profile.id, profile_dict)
            else:
                profile_dict["created_at"] = datetime.utcnow()
                self.profile_repo.create(profile_dict)

            self.db.flush()

        except Exception as e:
            logger.error(f"Error updating social profile: {str(e)}")
            # Non-critical, continue

    def _create_social_auth_response(
        self,
        user: User,
        is_new_user: bool,
        provider: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> SocialAuthResponse:
        """Create social authentication response with tokens."""
        # Generate JWT tokens
        access_token = self.jwt.create_access_token(
            subject=str(user.id),
            role=user.user_role.value,
            hostel_id=None,
            expires_delta=timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        
        refresh_token = self.jwt.create_refresh_token(
            subject=str(user.id),
            expires_delta=timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
        )

        # Create session
        session_expires_at = datetime.utcnow() + timedelta(
            days=self.REFRESH_TOKEN_EXPIRE_DAYS
        )
        
        self.session_repo.create({
            "user_id": user.id,
            "device_info": user_agent or f"{provider} Login",
            "ip_address": ip_address or "Unknown",
            "is_revoked": False,
            "expires_at": session_expires_at,
            "last_activity": datetime.utcnow(),
        })
        self.db.flush()

        # Build response
        return SocialAuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=self.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=SocialUserInfo(
                id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                role=user.user_role.value,
                profile_image_url=user.profile_image_url,
                is_email_verified=bool(user.email_verified_at),
            ),
            is_new_user=is_new_user,
            provider=provider,
        )