# app/services/auth/social_auth_service.py
from __future__ import annotations

from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import UserRepository
from app.repositories.visitor import VisitorRepository
from app.schemas.auth.social_auth import (
    GoogleAuthRequest,
    FacebookAuthRequest,
    SocialAuthResponse,
    SocialUserInfo,
)
from app.schemas.common.enums import UserRole
from app.services.common import UnitOfWork, security, errors


class SocialAuthService:
    """
    Social authentication (Google/Facebook).

    This is a high-level skeleton. In a real implementation, you would:
    - Verify tokens with Google/Facebook APIs;
    - Extract profile info;
    - Create or update User + Visitor profile;
    - Issue JWT tokens (similar to AuthService).
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        jwt_settings: security.JWTSettings,
    ) -> None:
        self._session_factory = session_factory
        self._jwt_settings = jwt_settings

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _get_visitor_repo(self, uow: UnitOfWork) -> VisitorRepository:
        return uow.get_repo(VisitorRepository)

    # For brevity, Google/Facebook verification is omitted and should be added
    # using their respective SDKs or REST APIs.

    def authenticate_with_google(self, data: GoogleAuthRequest) -> SocialAuthResponse:
        """
        Verify Google ID token, then create or fetch user.

        This implementation is a stub and should be extended with actual
        Google token verification logic.
        """
        raise NotImplementedError("Google OAuth integration not implemented")

    def authenticate_with_facebook(self, data: FacebookAuthRequest) -> SocialAuthResponse:
        """
        Verify Facebook access token, then create or fetch user.

        This implementation is a stub and should be extended with actual
        Facebook token verification logic.
        """
        raise NotImplementedError("Facebook OAuth integration not implemented")