"""
Guest information & documents service for bookings.

Enhanced with:
- Document validation and verification
- Guest data privacy handling
- Document type validation
- Audit trail for document changes
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.booking import BookingGuestRepository
from app.models.booking.booking_guest import BookingGuest as BookingGuestModel
from app.schemas.booking.booking_request import GuestInformation
from app.schemas.booking.booking_response import BookingDetail

logger = logging.getLogger(__name__)


class BookingGuestService(BaseService[BookingGuestModel, BookingGuestRepository]):
    """
    Manage guest info and documents tied to a booking.
    
    Features:
    - Guest information management
    - Document upload and verification
    - Privacy-compliant data handling
    - Document type validation
    """

    # Allowed document types
    ALLOWED_DOCUMENT_TYPES = [
        'passport',
        'national_id',
        'driver_license',
        'student_id',
        'visa',
        'birth_certificate',
        'other'
    ]

    def __init__(self, repository: BookingGuestRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_guest_information(self, guest_info: GuestInformation) -> Optional[ServiceError]:
        """Validate guest information."""
        # Validate required fields
        if hasattr(guest_info, 'full_name'):
            if not guest_info.full_name or len(guest_info.full_name.strip()) < 2:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Guest full name must be at least 2 characters",
                    severity=ErrorSeverity.ERROR,
                    details={"full_name": guest_info.full_name}
                )

        # Validate email format
        if hasattr(guest_info, 'email') and guest_info.email:
            if '@' not in guest_info.email or '.' not in guest_info.email.split('@')[1]:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Invalid email format",
                    severity=ErrorSeverity.ERROR,
                    details={"email": guest_info.email}
                )

        # Validate phone number
        if hasattr(guest_info, 'phone') and guest_info.phone:
            # Remove common formatting characters
            phone_digits = ''.join(c for c in guest_info.phone if c.isdigit())
            if len(phone_digits) < 10 or len(phone_digits) > 15:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Phone number must be between 10 and 15 digits",
                    severity=ErrorSeverity.ERROR,
                    details={"phone": guest_info.phone}
                )

        # Validate date of birth
        if hasattr(guest_info, 'date_of_birth') and guest_info.date_of_birth:
            from datetime import date
            today = date.today()
            age = today.year - guest_info.date_of_birth.year - (
                (today.month, today.day) < (guest_info.date_of_birth.month, guest_info.date_of_birth.day)
            )
            
            if age < 16:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Guest must be at least 16 years old",
                    severity=ErrorSeverity.ERROR,
                    details={"age": age}
                )
            
            if age > 120:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Invalid date of birth",
                    severity=ErrorSeverity.ERROR,
                    details={"date_of_birth": str(guest_info.date_of_birth)}
                )

        return None

    def _validate_document_type(self, document_type: str) -> Optional[ServiceError]:
        """Validate document type."""
        if not document_type or document_type.lower() not in self.ALLOWED_DOCUMENT_TYPES:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Invalid document type",
                severity=ErrorSeverity.ERROR,
                details={
                    "document_type": document_type,
                    "allowed_types": self.ALLOWED_DOCUMENT_TYPES
                }
            )
        return None

    # -------------------------------------------------------------------------
    # Guest Information Management
    # -------------------------------------------------------------------------

    def update_guest_information(
        self,
        booking_id: UUID,
        guest_info: GuestInformation,
    ) -> ServiceResult[BookingDetail]:
        """
        Update guest information for a booking.
        
        Args:
            booking_id: UUID of booking
            guest_info: Guest information data
            
        Returns:
            ServiceResult containing updated BookingDetail or error
        """
        try:
            # Validate guest information
            validation_error = self._validate_guest_information(guest_info)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Updating guest information for booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "has_email": hasattr(guest_info, 'email') and bool(guest_info.email),
                    "has_phone": hasattr(guest_info, 'phone') and bool(guest_info.phone)
                }
            )

            # Update guest information
            detail = self.repository.update_guest_information(booking_id, guest_info)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Successfully updated guest information for booking {booking_id}",
                extra={"booking_id": str(booking_id)}
            )

            return ServiceResult.success(
                detail,
                message="Guest information updated successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(f"Integrity error updating guest information: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.CONFLICT,
                    message="Guest information conflicts with existing data",
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(booking_id), "error": str(e)}
                )
            )
        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Validation error updating guest information: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.BUSINESS_RULE_VIOLATION,
                    message=str(e),
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(booking_id)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error updating guest information: {str(e)}", exc_info=True)
            return self._handle_exception(e, "update guest information", booking_id)

    def get_guest_information(
        self,
        booking_id: UUID,
    ) -> ServiceResult[GuestInformation]:
        """
        Get guest information for a booking.
        
        Args:
            booking_id: UUID of booking
            
        Returns:
            ServiceResult containing GuestInformation or error
        """
        try:
            self._logger.debug(f"Fetching guest information for booking {booking_id}")

            guest_info = self.repository.get_guest_information(booking_id)

            if not guest_info:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Guest information not found",
                        severity=ErrorSeverity.ERROR,
                        details={"booking_id": str(booking_id)}
                    )
                )

            return ServiceResult.success(guest_info)

        except Exception as e:
            self._logger.error(f"Error fetching guest information: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get guest information", booking_id)

    # -------------------------------------------------------------------------
    # Document Management
    # -------------------------------------------------------------------------

    def add_guest_document(
        self,
        booking_id: UUID,
        document_type: str,
        file_id: UUID,
        notes: Optional[str] = None,
    ) -> ServiceResult[BookingDetail]:
        """
        Add a guest document to a booking.
        
        Args:
            booking_id: UUID of booking
            document_type: Type of document
            file_id: UUID of uploaded file
            notes: Optional notes about the document
            
        Returns:
            ServiceResult containing updated BookingDetail or error
        """
        try:
            # Validate document type
            validation_error = self._validate_document_type(document_type)
            if validation_error:
                return ServiceResult.failure(validation_error)

            # Validate notes length if provided
            if notes and len(notes) > 1000:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Notes cannot exceed 1000 characters",
                        severity=ErrorSeverity.ERROR,
                        details={"notes_length": len(notes)}
                    )
                )

            self._logger.info(
                f"Adding guest document to booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "document_type": document_type,
                    "file_id": str(file_id)
                }
            )

            # Add document
            detail = self.repository.add_guest_document(
                booking_id,
                document_type,
                file_id,
                notes=notes
            )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Successfully added guest document to booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "document_type": document_type
                }
            )

            return ServiceResult.success(
                detail,
                message="Guest document added successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(f"Integrity error adding guest document: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.CONFLICT,
                    message="Document already exists or file not found",
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(booking_id), "file_id": str(file_id)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error adding guest document: {str(e)}", exc_info=True)
            return self._handle_exception(e, "add guest document", booking_id)

    def remove_guest_document(
        self,
        booking_id: UUID,
        document_id: UUID,
    ) -> ServiceResult[BookingDetail]:
        """
        Remove a guest document from a booking.
        
        Args:
            booking_id: UUID of booking
            document_id: UUID of document to remove
            
        Returns:
            ServiceResult containing updated BookingDetail or error
        """
        try:
            self._logger.info(
                f"Removing guest document from booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "document_id": str(document_id)
                }
            )

            detail = self.repository.remove_guest_document(booking_id, document_id)

            self.db.commit()

            self._logger.info(
                f"Successfully removed guest document from booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "document_id": str(document_id)
                }
            )

            return ServiceResult.success(
                detail,
                message="Guest document removed successfully"
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error removing guest document: {str(e)}", exc_info=True)
            return self._handle_exception(e, "remove guest document", booking_id)

    def get_guest_documents(
        self,
        booking_id: UUID,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get all guest documents for a booking.
        
        Args:
            booking_id: UUID of booking
            
        Returns:
            ServiceResult containing list of documents or error
        """
        try:
            self._logger.debug(f"Fetching guest documents for booking {booking_id}")

            documents = self.repository.get_guest_documents(booking_id)

            return ServiceResult.success(
                documents,
                metadata={"count": len(documents)}
            )

        except Exception as e:
            self._logger.error(f"Error fetching guest documents: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get guest documents", booking_id)

    def verify_guest_document(
        self,
        booking_id: UUID,
        document_id: UUID,
        verified: bool,
        verified_by: Optional[UUID] = None,
        verification_notes: Optional[str] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Verify or reject a guest document.
        
        Args:
            booking_id: UUID of booking
            document_id: UUID of document
            verified: Verification status
            verified_by: UUID of user performing verification
            verification_notes: Optional verification notes
            
        Returns:
            ServiceResult containing updated document info or error
        """
        try:
            self._logger.info(
                f"{'Verifying' if verified else 'Rejecting'} guest document for booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "document_id": str(document_id),
                    "verified": verified,
                    "verified_by": str(verified_by) if verified_by else None
                }
            )

            document = self.repository.verify_guest_document(
                booking_id,
                document_id,
                verified,
                verified_by=verified_by,
                verification_notes=verification_notes
            )

            self.db.commit()

            return ServiceResult.success(
                document,
                message=f"Document {'verified' if verified else 'rejected'} successfully"
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error verifying guest document: {str(e)}", exc_info=True)
            return self._handle_exception(e, "verify guest document", booking_id)

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def bulk_update_guest_information(
        self,
        updates: List[Dict[str, Any]],
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Update guest information for multiple bookings.
        
        Args:
            updates: List of update dictionaries with booking_id and guest_info
            
        Returns:
            ServiceResult containing summary or error
        """
        try:
            if not updates or len(updates) == 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="At least one update is required",
                        severity=ErrorSeverity.ERROR
                    )
                )

            if len(updates) > 100:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Cannot update more than 100 bookings at once",
                        severity=ErrorSeverity.ERROR,
                        details={"count": len(updates)}
                    )
                )

            self._logger.info(
                f"Bulk updating guest information for {len(updates)} bookings",
                extra={"update_count": len(updates)}
            )

            start_time = datetime.utcnow()

            summary = self.repository.bulk_update_guest_information(updates)

            self.db.commit()

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._logger.info(
                f"Bulk update completed: {summary.get('updated', 0)} updated, "
                f"{summary.get('failed', 0)} failed in {duration_ms:.2f}ms",
                extra={
                    "updated": summary.get('updated', 0),
                    "failed": summary.get('failed', 0),
                    "duration_ms": duration_ms
                }
            )

            return ServiceResult.success(
                summary,
                message=f"Bulk update completed: {summary.get('updated', 0)} updated, "
                        f"{summary.get('failed', 0)} failed",
                metadata={"duration_ms": duration_ms}
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error during bulk update: {str(e)}", exc_info=True)
            return self._handle_exception(e, "bulk update guest information")

    # -------------------------------------------------------------------------
    # Privacy & Compliance
    # -------------------------------------------------------------------------

    def anonymize_guest_data(
        self,
        booking_id: UUID,
        reason: str,
    ) -> ServiceResult[bool]:
        """
        Anonymize guest data for privacy compliance (e.g., GDPR).
        
        Args:
            booking_id: UUID of booking
            reason: Reason for anonymization
            
        Returns:
            ServiceResult containing success boolean or error
        """
        try:
            if not reason or len(reason.strip()) < 10:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Anonymization reason must be at least 10 characters",
                        severity=ErrorSeverity.ERROR
                    )
                )

            self._logger.warning(
                f"Anonymizing guest data for booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "reason": reason
                }
            )

            success = self.repository.anonymize_guest_data(booking_id, reason)

            self.db.commit()

            self._logger.info(
                f"Guest data anonymized for booking {booking_id}",
                extra={"booking_id": str(booking_id)}
            )

            return ServiceResult.success(
                success,
                message="Guest data anonymized successfully"
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error anonymizing guest data: {str(e)}", exc_info=True)
            return self._handle_exception(e, "anonymize guest data", booking_id)