"""
OTP service: generate, verify, resend with comprehensive throttling.

Handles One-Time Password delivery via email and SMS with
rate limiting and security controls.
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
from app.repositories.auth import (
    OTPTokenRepository,
    OTPTemplateRepository,
    OTPDeliveryRepository,
    OTPThrottlingRepository,
)
from app.models.auth.otp_token import OTPToken
from app.schemas.auth.otp import (
    OTPGenerateRequest,
    OTPVerifyRequest,
    OTPResponse,
    OTPVerifyResponse,
    ResendOTPRequest,
)
from app.schemas.common.enums import OTPType

logger = logging.getLogger(__name__)


class OTPService(BaseService[OTPToken, OTPTokenRepository]):
    """
    OTP generation and verification service with comprehensive security.
    
    Features:
    - Multi-channel delivery (email, SMS)
    - Rate limiting and throttling
    - Template-based messaging
    - Delivery tracking and retry logic
    - Security event logging
    """

    # Configuration
    MAX_VERIFICATION_ATTEMPTS = 5
    OTP_VALIDITY_MINUTES = 10
    RESEND_COOLDOWN_SECONDS = 60

    def __init__(
        self,
        token_repo: OTPTokenRepository,
        template_repo: OTPTemplateRepository,
        delivery_repo: OTPDeliveryRepository,
        throttling_repo: OTPThrottlingRepository,
        db_session: Session,
    ):
        super().__init__(token_repo, db_session)
        self.token_repo = token_repo
        self.template_repo = template_repo
        self.delivery_repo = delivery_repo
        self.throttling_repo = throttling_repo

    # -------------------------------------------------------------------------
    # OTP Generation
    # -------------------------------------------------------------------------

    def generate(
        self,
        request: OTPGenerateRequest,
    ) -> ServiceResult[OTPResponse]:
        """
        Generate and send OTP to user.
        
        Args:
            request: OTP generation request with delivery details
            
        Returns:
            ServiceResult with OTP response including masked destination
        """
        try:
            # Validate request
            validation_result = self._validate_generate_request(request)
            if not validation_result.success:
                return validation_result

            # Check rate limits
            try:
                self.throttling_repo.check_rate_limit(request)
            except Exception as e:
                logger.warning(f"Rate limit exceeded: {str(e)}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Too many OTP requests. Please try again later.",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Invalidate any existing OTPs for this identifier
            self._invalidate_existing_otps(request)

            # Generate OTP token
            token = self.token_repo.generate(request)
            
            # Send OTP via appropriate channel
            delivery_result = self.delivery_repo.send(token, request)
            
            if not delivery_result.success:
                logger.error(
                    f"Failed to deliver OTP: {delivery_result.error_message}"
                )
                # Rollback token creation
                self.db.rollback()
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        message="Failed to send OTP. Please try again.",
                        severity=ErrorSeverity.ERROR,
                        details={"reason": delivery_result.error_message},
                    )
                )

            self.db.commit()

            # Calculate time until expiry
            expires_in = int(
                (token.expires_at - datetime.utcnow()).total_seconds()
            )

            response = OTPResponse(
                message="OTP sent successfully",
                expires_in=expires_in,
                sent_to=self._mask_destination(request),
                otp_type=request.otp_type,
                max_attempts=token.max_attempts,
                delivery_channel=delivery_result.channel,
            )

            logger.info(
                f"OTP generated for {request.otp_type}: "
                f"{self._mask_destination(request)}"
            )
            
            return ServiceResult.success(
                response,
                message="OTP sent successfully",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during OTP generation: {str(e)}")
            return self._handle_exception(e, "generate otp")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during OTP generation: {str(e)}")
            return self._handle_exception(e, "generate otp")

    # -------------------------------------------------------------------------
    # OTP Verification
    # -------------------------------------------------------------------------

    def verify(
        self,
        request: OTPVerifyRequest,
    ) -> ServiceResult[OTPVerifyResponse]:
        """
        Verify OTP code.
        
        Args:
            request: OTP verification request with code
            
        Returns:
            ServiceResult with verification result
        """
        try:
            # Validate request
            if not request.code or len(request.code.strip()) == 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="OTP code is required",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Verify OTP
            result = self.token_repo.verify(request)
            
            if result.is_valid:
                logger.info(
                    f"OTP verified successfully for: "
                    f"{self._mask_destination(request)}"
                )
                self.db.commit()
                return ServiceResult.success(
                    result,
                    message="OTP verified successfully",
                )
            else:
                logger.warning(
                    f"Invalid OTP attempt for: {self._mask_destination(request)}"
                )
                self.db.commit()
                
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message=result.error_message or "Invalid or expired OTP",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "attempts_remaining": result.attempts_remaining,
                        },
                    )
                )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during OTP verification: {str(e)}")
            return self._handle_exception(e, "verify otp")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during OTP verification: {str(e)}")
            return self._handle_exception(e, "verify otp")

    # -------------------------------------------------------------------------
    # OTP Resend
    # -------------------------------------------------------------------------

    def resend(
        self,
        request: ResendOTPRequest,
    ) -> ServiceResult[OTPResponse]:
        """
        Resend OTP to user.
        
        Args:
            request: Resend request with delivery details
            
        Returns:
            ServiceResult with new OTP response
        """
        try:
            # Check resend rate limits
            try:
                self.throttling_repo.check_rate_limit(request, is_resend=True)
            except Exception as e:
                logger.warning(f"Resend rate limit exceeded: {str(e)}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=(
                            "Too many resend requests. "
                            f"Please wait {self.RESEND_COOLDOWN_SECONDS} seconds."
                        ),
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Check if there's a recent OTP that can be resent
            existing_token = self.token_repo.get_latest_active_token(request)
            
            if existing_token:
                # Check cooldown period
                time_since_last = (
                    datetime.utcnow() - existing_token.created_at
                ).total_seconds()
                
                if time_since_last < self.RESEND_COOLDOWN_SECONDS:
                    wait_time = int(self.RESEND_COOLDOWN_SECONDS - time_since_last)
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Please wait {wait_time} seconds before resending",
                            severity=ErrorSeverity.WARNING,
                        )
                    )

            # Generate new OTP
            token = self.token_repo.resend(request)
            
            # Send via delivery channel
            delivery_result = self.delivery_repo.send(token, request)
            
            if not delivery_result.success:
                logger.error(f"Failed to resend OTP: {delivery_result.error_message}")
                self.db.rollback()
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        message="Failed to resend OTP. Please try again.",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            self.db.commit()

            expires_in = int(
                (token.expires_at - datetime.utcnow()).total_seconds()
            )

            response = OTPResponse(
                message="OTP resent successfully",
                expires_in=expires_in,
                sent_to=self._mask_destination(request),
                otp_type=token.otp_type,
                max_attempts=token.max_attempts,
                delivery_channel=delivery_result.channel,
            )

            logger.info(
                f"OTP resent for {request.otp_type}: "
                f"{self._mask_destination(request)}"
            )
            
            return ServiceResult.success(
                response,
                message="OTP resent successfully",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during OTP resend: {str(e)}")
            return self._handle_exception(e, "resend otp")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during OTP resend: {str(e)}")
            return self._handle_exception(e, "resend otp")

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _validate_generate_request(
        self,
        request: OTPGenerateRequest,
    ) -> ServiceResult:
        """Validate OTP generation request."""
        if request.otp_type == OTPType.EMAIL_VERIFICATION:
            if not request.email or "@" not in request.email:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Valid email address is required",
                        severity=ErrorSeverity.WARNING,
                    )
                )
        elif request.otp_type == OTPType.PHONE_VERIFICATION:
            if not request.phone:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Phone number is required",
                        severity=ErrorSeverity.WARNING,
                    )
                )

        return ServiceResult.success(True)

    def _invalidate_existing_otps(self, request: OTPGenerateRequest) -> None:
        """Invalidate any existing active OTPs for the identifier."""
        try:
            identifier = request.email or request.phone
            if identifier:
                self.token_repo.invalidate_existing(
                    identifier=identifier,
                    otp_type=request.otp_type,
                )
                self.db.flush()
        except Exception as e:
            logger.warning(f"Failed to invalidate existing OTPs: {str(e)}")
            # Non-critical, continue

    def _mask_destination(self, request: Any) -> str:
        """
        Mask email or phone for privacy.
        
        Args:
            request: Request object containing email or phone
            
        Returns:
            Masked destination string
        """
        if hasattr(request, "email") and request.email:
            email = request.email
            if "@" not in email:
                return "***@***.***"
            
            local, domain = email.split("@", 1)
            if len(local) <= 2:
                masked_local = "*" * len(local)
            else:
                masked_local = f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}"
            
            domain_parts = domain.split(".")
            if len(domain_parts) >= 2:
                masked_domain = f"***{domain_parts[-1]}"
            else:
                masked_domain = "***"
            
            return f"{masked_local}@{masked_domain}"
        
        if hasattr(request, "phone") and request.phone:
            phone = "".join(c for c in request.phone if c.isdigit() or c == "+")
            if len(phone) < 4:
                return "+***"
            
            return f"{phone[:2]}***{phone[-2:]}"
        
        return "***"