"""
Token blacklist and revocation service.

Manages revoked tokens to prevent reuse and enforce
security policies.
"""

from typing import Optional, List, Dict, Any
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
from app.repositories.auth import (
    BlacklistedTokenRepository,
    TokenRevocationRepository,
)
from app.models.auth.token_blacklist import BlacklistedToken

logger = logging.getLogger(__name__)


class TokenBlacklistService(BaseService[BlacklistedToken, BlacklistedTokenRepository]):
    """
    Manage JWT token blacklist and revocation tracking.
    
    Features:
    - Token blacklisting for logout and security events
    - Revocation tracking with reasons
    - Bulk revocation for users
    - Automatic cleanup of expired blacklist entries
    - Audit trail for compliance
    """

    # Configuration
    BLACKLIST_CLEANUP_DAYS = 30
    CLEANUP_BATCH_SIZE = 1000

    def __init__(
        self,
        blacklist_repo: BlacklistedTokenRepository,
        revocation_repo: TokenRevocationRepository,
        db_session: Session,
    ):
        super().__init__(blacklist_repo, db_session)
        self.blacklist_repo = blacklist_repo
        self.revocation_repo = revocation_repo

    # -------------------------------------------------------------------------
    # Token Blacklisting
    # -------------------------------------------------------------------------

    def blacklist_token(
        self,
        token: str,
        user_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> ServiceResult[bool]:
        """
        Add token to blacklist.
        
        Args:
            token: JWT token to blacklist
            user_id: User who owns the token
            reason: Revocation reason
            expires_at: Token expiration time
            
        Returns:
            ServiceResult with success status
        """
        try:
            # Check if already blacklisted
            if self.blacklist_repo.is_blacklisted(token):
                logger.info(f"Token already blacklisted")
                return ServiceResult.success(
                    True,
                    message="Token already blacklisted",
                )

            # Add to blacklist
            self.blacklist_repo.add(
                token=token,
                user_id=user_id,
                reason=reason or "Manual revocation",
                expires_at=expires_at,
            )

            # Record revocation
            self.revocation_repo.record(
                token=token,
                user_id=user_id,
                reason=reason,
            )

            self.db.commit()

            logger.info(
                f"Token blacklisted for user: {user_id} - Reason: {reason}"
            )
            
            return ServiceResult.success(
                True,
                message="Token blacklisted successfully",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error blacklisting token: {str(e)}")
            return self._handle_exception(e, "blacklist token")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error blacklisting token: {str(e)}")
            return self._handle_exception(e, "blacklist token")

    def is_blacklisted(
        self,
        token: str,
    ) -> ServiceResult[bool]:
        """
        Check if token is blacklisted.
        
        Args:
            token: JWT token to check
            
        Returns:
            ServiceResult with blacklist status
        """
        try:
            is_blacklisted = self.blacklist_repo.is_blacklisted(token)
            
            return ServiceResult.success(
                is_blacklisted,
                message="Blacklisted" if is_blacklisted else "Not blacklisted",
            )

        except Exception as e:
            logger.error(f"Error checking blacklist status: {str(e)}")
            return self._handle_exception(e, "check blacklist status")

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def revoke_all_for_user(
        self,
        user_id: UUID,
        reason: Optional[str] = None,
    ) -> ServiceResult[int]:
        """
        Revoke all tokens for a user.
        
        Args:
            user_id: User identifier
            reason: Revocation reason
            
        Returns:
            ServiceResult with count of revoked tokens
        """
        try:
            count = self.revocation_repo.revoke_all_for_user(
                user_id=user_id,
                reason=reason or "Bulk revocation",
            )

            self.db.commit()

            logger.info(
                f"Revoked {count} token(s) for user: {user_id} - Reason: {reason}"
            )
            
            return ServiceResult.success(
                count,
                message=f"Revoked {count} token(s) successfully",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error revoking tokens: {str(e)}")
            return self._handle_exception(e, "revoke all tokens", user_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error revoking tokens: {str(e)}")
            return self._handle_exception(e, "revoke all tokens", user_id)

    # -------------------------------------------------------------------------
    # Cleanup Operations
    # -------------------------------------------------------------------------

    def cleanup_expired(
        self,
        batch_size: Optional[int] = None,
    ) -> ServiceResult[Dict[str, int]]:
        """
        Remove expired entries from blacklist.
        
        Args:
            batch_size: Number of entries to process
            
        Returns:
            ServiceResult with cleanup statistics
        """
        try:
            batch_size = batch_size or self.CLEANUP_BATCH_SIZE
            
            # Calculate expiry threshold
            threshold = datetime.utcnow() - timedelta(
                days=self.BLACKLIST_CLEANUP_DAYS
            )

            # Cleanup expired blacklist entries
            deleted_count = self.blacklist_repo.cleanup_expired(
                before=threshold,
                batch_size=batch_size,
            )

            self.db.commit()

            logger.info(f"Cleaned up {deleted_count} expired blacklist entries")
            
            return ServiceResult.success(
                {
                    "deleted_count": deleted_count,
                    "threshold_date": threshold.isoformat(),
                },
                message=f"Cleaned up {deleted_count} expired entries",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during cleanup: {str(e)}")
            return self._handle_exception(e, "cleanup expired tokens")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during cleanup: {str(e)}")
            return self._handle_exception(e, "cleanup expired tokens")

    # -------------------------------------------------------------------------
    # Revocation History
    # -------------------------------------------------------------------------

    def get_revocation_history(
        self,
        user_id: UUID,
        limit: int = 50,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get token revocation history for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of records
            
        Returns:
            ServiceResult with revocation history
        """
        try:
            history = self.revocation_repo.get_user_revocations(
                user_id=user_id,
                limit=limit,
            )

            revocations = [
                {
                    "id": str(rev.id),
                    "token": rev.token[:20] + "...",  # Truncate for security
                    "reason": rev.reason,
                    "revoked_at": rev.revoked_at.isoformat(),
                }
                for rev in history
            ]

            return ServiceResult.success(
                revocations,
                metadata={"count": len(revocations)},
            )

        except Exception as e:
            logger.error(f"Error retrieving revocation history: {str(e)}")
            return self._handle_exception(e, "get revocation history", user_id)