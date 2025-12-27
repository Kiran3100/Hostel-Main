"""
Token management service: issuance, validation, refresh, and lifecycle.

Centralized token operations for authentication and authorization.
"""

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import timedelta, datetime
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
from app.models.user.user import User
from app.core1.security.jwt_handler import JWTManager
from app.schemas.auth.token import (
    Token,
    TokenPayload,
    RefreshTokenRequest,
    RefreshTokenResponse,
    TokenValidationRequest,
    TokenValidationResponse,
    RevokeTokenRequest,
)

logger = logging.getLogger(__name__)


class TokenService(BaseService[User, UserRepository]):
    """
    Comprehensive token lifecycle management.
    
    Features:
    - Access and refresh token issuance
    - Token validation and verification
    - Token refresh with rotation
    - Role-based claims encoding
    - Hostel-specific scoping
    - Expiration management
    """

    # Configuration
    ACCESS_TOKEN_EXPIRE_MINUTES = 60
    REFRESH_TOKEN_EXPIRE_DAYS = 30

    def __init__(self, user_repository: UserRepository, db_session: Session):
        super().__init__(user_repository, db_session)
        self.jwt = JWTManager()

    # -------------------------------------------------------------------------
    # Token Issuance
    # -------------------------------------------------------------------------

    def issue_tokens(
        self,
        user_id: UUID,
        role: str,
        hostel_id: Optional[UUID] = None,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[Token]:
        """
        Issue access and refresh tokens for authenticated user.
        
        Args:
            user_id: User identifier
            role: User role
            hostel_id: Optional hostel scope
            additional_claims: Additional JWT claims
            
        Returns:
            ServiceResult with token pair
        """
        try:
            # Verify user exists and is active
            user = self.repository.get_by_id(user_id)
            if not user:
                logger.warning(f"Token issuance for non-existent user: {user_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="User not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            if not user.is_active:
                logger.warning(f"Token issuance for inactive user: {user_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.FORBIDDEN,
                        message="User account is inactive",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Create access token
            access_token = self.jwt.create_access_token(
                subject=str(user_id),
                role=role,
                hostel_id=str(hostel_id) if hostel_id else None,
                additional_claims=additional_claims,
                expires_delta=timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES),
            )

            # Create refresh token
            refresh_token = self.jwt.create_refresh_token(
                subject=str(user_id),
                expires_delta=timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
            )

            token = Token(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="Bearer",
                expires_in=self.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            )

            logger.info(f"Tokens issued for user: {user_id}, role: {role}")
            
            return ServiceResult.success(
                token,
                message="Tokens issued successfully",
            )

        except Exception as e:
            logger.error(f"Error issuing tokens: {str(e)}")
            return self._handle_exception(e, "issue tokens", user_id)

    # -------------------------------------------------------------------------
    # Token Refresh
    # -------------------------------------------------------------------------

    def refresh(
        self,
        request: RefreshTokenRequest,
    ) -> ServiceResult[RefreshTokenResponse]:
        """
        Refresh access token using valid refresh token.
        
        Args:
            request: Refresh token request
            
        Returns:
            ServiceResult with new token pair
        """
        try:
            # Decode and validate refresh token
            payload = self.jwt.decode_token(request.refresh_token)
            
            if not payload:
                logger.warning("Invalid refresh token attempted")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid or expired refresh token",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Verify token type
            token_type = payload.get("type")
            if token_type != "refresh":
                logger.warning(f"Non-refresh token used for refresh: {token_type}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid token type",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Extract user ID
            user_id_str = payload.get("sub")
            if not user_id_str:
                logger.warning("Refresh token missing subject")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid token payload",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            try:
                user_id = UUID(user_id_str)
            except ValueError:
                logger.warning(f"Invalid UUID in refresh token: {user_id_str}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid token format",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Fetch user
            user = self.repository.get_by_id(user_id)
            if not user:
                logger.warning(f"Refresh token for non-existent user: {user_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="User not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            if not user.is_active:
                logger.warning(f"Refresh token for inactive user: {user_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.FORBIDDEN,
                        message="User account is inactive",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Generate new token pair (with rotation)
            access_token = self.jwt.create_access_token(
                subject=str(user.id),
                role=user.user_role.value,
                hostel_id=None,
                expires_delta=timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES),
            )

            # Optionally rotate refresh token
            new_refresh_token = self.jwt.create_refresh_token(
                subject=str(user.id),
                expires_delta=timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
            )

            response = RefreshTokenResponse(
                access_token=access_token,
                refresh_token=new_refresh_token,
                token_type="Bearer",
                expires_in=self.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            )

            logger.info(f"Tokens refreshed for user: {user_id}")
            
            return ServiceResult.success(
                response,
                message="Tokens refreshed successfully",
            )

        except Exception as e:
            logger.error(f"Error refreshing tokens: {str(e)}")
            return self._handle_exception(e, "refresh tokens")

    # -------------------------------------------------------------------------
    # Token Validation
    # -------------------------------------------------------------------------

    def validate(
        self,
        request: TokenValidationRequest,
    ) -> ServiceResult[TokenValidationResponse]:
        """
        Validate and decode token.
        
        Args:
            request: Token validation request
            
        Returns:
            ServiceResult with validation response
        """
        try:
            # Decode token
            payload = self.jwt.decode_token(request.token)

            if not payload:
                return ServiceResult.success(
                    TokenValidationResponse(
                        is_valid=False,
                        user_id=None,
                        role=None,
                        expires_at=None,
                        error="Invalid or expired token",
                    ),
                    message="Token validation failed",
                )

            # Extract claims
            user_id = payload.get("sub")
            role = payload.get("role")
            exp = payload.get("exp")
            hostel_id = payload.get("hostel_id")

            # Verify expiration
            if exp:
                exp_datetime = datetime.fromtimestamp(exp)
                if exp_datetime < datetime.utcnow():
                    return ServiceResult.success(
                        TokenValidationResponse(
                            is_valid=False,
                            user_id=user_id,
                            role=role,
                            expires_at=exp,
                            error="Token expired",
                        ),
                        message="Token expired",
                    )

            # Verify user still exists and is active (optional strict mode)
            if request.validate_user:
                try:
                    user = self.repository.get_by_id(UUID(user_id))
                    if not user or not user.is_active:
                        return ServiceResult.success(
                            TokenValidationResponse(
                                is_valid=False,
                                user_id=user_id,
                                role=role,
                                expires_at=exp,
                                error="User not found or inactive",
                            ),
                            message="User validation failed",
                        )
                except ValueError:
                    return ServiceResult.success(
                        TokenValidationResponse(
                            is_valid=False,
                            user_id=user_id,
                            role=role,
                            expires_at=exp,
                            error="Invalid user ID format",
                        ),
                        message="Invalid token format",
                    )

            response = TokenValidationResponse(
                is_valid=True,
                user_id=user_id,
                role=role,
                hostel_id=hostel_id,
                expires_at=exp,
                error=None,
            )

            return ServiceResult.success(
                response,
                message="Token is valid",
            )

        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return ServiceResult.success(
                TokenValidationResponse(
                    is_valid=False,
                    user_id=None,
                    role=None,
                    expires_at=None,
                    error=f"Validation error: {str(e)}",
                ),
                message="Token validation error",
            )

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def decode_token_payload(
        self,
        token: str,
    ) -> ServiceResult[TokenPayload]:
        """
        Decode token and return payload.
        
        Args:
            token: JWT token
            
        Returns:
            ServiceResult with token payload
        """
        try:
            payload = self.jwt.decode_token(token)
            
            if not payload:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid token",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            token_payload = TokenPayload(
                sub=payload.get("sub"),
                role=payload.get("role"),
                hostel_id=payload.get("hostel_id"),
                exp=payload.get("exp"),
                iat=payload.get("iat"),
                type=payload.get("type", "access"),
            )

            return ServiceResult.success(
                token_payload,
                message="Token decoded successfully",
            )

        except Exception as e:
            logger.error(f"Error decoding token: {str(e)}")
            return self._handle_exception(e, "decode token")