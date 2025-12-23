"""
Booking waitlist service.

Enhanced with:
- Priority queue management
- Automated notifications
- Conversion tracking
- Waitlist analytics
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.booking import BookingWaitlistRepository
from app.models.booking.booking_waitlist import BookingWaitlist as BookingWaitlistModel
from app.schemas.booking.booking_waitlist import (
    WaitlistRequest,
    WaitlistResponse,
    WaitlistStatusInfo,
    WaitlistNotification,
    WaitlistConversion,
    WaitlistCancellation,
    WaitlistEntry,
    WaitlistManagement,
)

logger = logging.getLogger(__name__)


class BookingWaitlistService(BaseService[BookingWaitlistModel, BookingWaitlistRepository]):
    """
    Manage waitlist: join, notify, conversion response, cancellation, and admin views.
    
    Features:
    - Waitlist queue management
    - Priority handling
    - Availability notifications
    - Conversion tracking
    - Analytics and reporting
    """

    def __init__(self, repository: BookingWaitlistRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_waitlist_request(self, request: WaitlistRequest) -> Optional[ServiceError]:
        """Validate waitlist join request."""
        if not request.hostel_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Hostel ID is required",
                severity=ErrorSeverity.ERROR
            )

        if not hasattr(request, 'room_type') or not request.room_type:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Room type is required",
                severity=ErrorSeverity.ERROR
            )

        if hasattr(request, 'desired_check_in_date') and request.desired_check_in_date:
            if request.desired_check_in_date < datetime.now().date():
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Desired check-in date cannot be in the past",
                    severity=ErrorSeverity.ERROR,
                    details={"desired_check_in_date": str(request.desired_check_in_date)}
                )

        if hasattr(request, 'contact_email') and request.contact_email:
            if '@' not in request.contact_email:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Valid email is required",
                    severity=ErrorSeverity.ERROR,
                    details={"contact_email": request.contact_email}
                )

        return None

    def _validate_waitlist_notification(self, notification: WaitlistNotification) -> Optional[ServiceError]:
        """Validate waitlist notification request."""
        if not notification.waitlist_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Waitlist ID is required",
                severity=ErrorSeverity.ERROR
            )

        if hasattr(notification, 'available_from') and hasattr(notification, 'available_until'):
            if notification.available_from and notification.available_until:
                if notification.available_from >= notification.available_until:
                    return ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Available from date must be before available until date",
                        severity=ErrorSeverity.ERROR
                    )

        return None

    def _validate_waitlist_conversion(self, request: WaitlistConversion) -> Optional[ServiceError]:
        """Validate waitlist conversion request."""
        if not request.waitlist_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Waitlist ID is required",
                severity=ErrorSeverity.ERROR
            )

        if hasattr(request, 'accepted') and request.accepted is None:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Acceptance decision is required",
                severity=ErrorSeverity.ERROR
            )

        return None

    def _validate_waitlist_cancellation(self, request: WaitlistCancellation) -> Optional[ServiceError]:
        """Validate waitlist cancellation request."""
        if not request.waitlist_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Waitlist ID is required",
                severity=ErrorSeverity.ERROR
            )

        if hasattr(request, 'reason') and request.reason:
            if len(request.reason.strip()) < 5:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Cancellation reason must be at least 5 characters",
                    severity=ErrorSeverity.ERROR,
                    details={"reason_length": len(request.reason.strip())}
                )

        return None

    # -------------------------------------------------------------------------
    # Waitlist Operations
    # -------------------------------------------------------------------------

    def join(
        self,
        request: WaitlistRequest,
    ) -> ServiceResult[WaitlistResponse]:
        """
        Add user to waitlist.
        
        Args:
            request: Waitlist join request data
            
        Returns:
            ServiceResult containing WaitlistResponse or error
        """
        try:
            # Validate request
            validation_error = self._validate_waitlist_request(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Adding to waitlist for hostel {request.hostel_id}",
                extra={
                    "hostel_id": str(request.hostel_id),
                    "room_type": request.room_type if hasattr(request, 'room_type') else None,
                    "user_id": str(request.user_id) if hasattr(request, 'user_id') else None
                }
            )

            # Join waitlist
            resp = self.repository.join(request)

            # Commit transaction
            self.db.commit()

            self._logger.info(
                f"Successfully added to waitlist: {resp.id if hasattr(resp, 'id') else 'unknown'}",
                extra={
                    "waitlist_id": str(resp.id) if hasattr(resp, 'id') else None,
                    "position": resp.position if hasattr(resp, 'position') else None
                }
            )

            return ServiceResult.success(
                resp,
                message=f"Added to waitlist at position {resp.position if hasattr(resp, 'position') else 'unknown'}"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(f"Integrity error joining waitlist: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.CONFLICT,
                    message="Already on waitlist for this room type",
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(request.hostel_id)}
                )
            )
        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Validation error joining waitlist: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.BUSINESS_RULE_VIOLATION,
                    message=str(e),
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(request.hostel_id)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error joining waitlist: {str(e)}", exc_info=True)
            return self._handle_exception(e, "join waitlist", request.hostel_id)

    def cancel(
        self,
        request: WaitlistCancellation,
    ) -> ServiceResult[bool]:
        """
        Remove user from waitlist.
        
        Args:
            request: Waitlist cancellation request data
            
        Returns:
            ServiceResult containing success boolean or error
        """
        try:
            # Validate request
            validation_error = self._validate_waitlist_cancellation(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Cancelling waitlist entry {request.waitlist_id}",
                extra={
                    "waitlist_id": str(request.waitlist_id),
                    "reason": request.reason if hasattr(request, 'reason') else None
                }
            )

            # Cancel waitlist entry
            ok = self.repository.cancel(request)

            # Commit transaction
            self.db.commit()

            if ok:
                self._logger.info(
                    f"Successfully cancelled waitlist entry {request.waitlist_id}",
                    extra={"waitlist_id": str(request.waitlist_id)}
                )
            else:
                self._logger.warning(
                    f"Waitlist cancellation returned false for {request.waitlist_id}",
                    extra={"waitlist_id": str(request.waitlist_id)}
                )

            return ServiceResult.success(
                ok,
                message="Removed from waitlist successfully" if ok else "Failed to remove from waitlist"
            )

        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Validation error cancelling waitlist: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.BUSINESS_RULE_VIOLATION,
                    message=str(e),
                    severity=ErrorSeverity.ERROR,
                    details={"waitlist_id": str(request.waitlist_id)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error cancelling waitlist: {str(e)}", exc_info=True)
            return self._handle_exception(e, "cancel waitlist", request.waitlist_id)

    # -------------------------------------------------------------------------
    # Notification Operations
    # -------------------------------------------------------------------------

    def notify_availability(
        self,
        notification: WaitlistNotification,
    ) -> ServiceResult[bool]:
        """
        Send availability notification to waitlist entry.
        
        Args:
            notification: Notification data
            
        Returns:
            ServiceResult containing success boolean or error
        """
        try:
            # Validate notification
            validation_error = self._validate_waitlist_notification(notification)
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.info(
                f"Sending availability notification to waitlist entry {notification.waitlist_id}",
                extra={
                    "waitlist_id": str(notification.waitlist_id),
                    "available_from": str(notification.available_from) if hasattr(notification, 'available_from') else None
                }
            )

            # Send notification
            ok = self.repository.send_availability_notification(notification)

            # Commit transaction
            self.db.commit()

            if ok:
                self._logger.info(
                    f"Successfully sent availability notification to {notification.waitlist_id}",
                    extra={"waitlist_id": str(notification.waitlist_id)}
                )
            else:
                self._logger.warning(
                    f"Notification sending returned false for {notification.waitlist_id}",
                    extra={"waitlist_id": str(notification.waitlist_id)}
                )

            return ServiceResult.success(
                ok,
                message="Availability notification sent" if ok else "Failed to send notification"
            )

        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Validation error sending notification: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.BUSINESS_RULE_VIOLATION,
                    message=str(e),
                    severity=ErrorSeverity.ERROR,
                    details={"waitlist_id": str(notification.waitlist_id)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error sending availability notification: {str(e)}", exc_info=True)
            return self._handle_exception(e, "notify availability", notification.waitlist_id)

    def notify_next_in_queue(
        self,
        hostel_id: UUID,
        room_type: str,
        count: int = 1,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Notify next person(s) in waitlist queue.
        
        Args:
            hostel_id: UUID of hostel
            room_type: Room type
            count: Number of people to notify
            
        Returns:
            ServiceResult containing summary or error
        """
        try:
            if count < 1 or count > 10:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Count must be between 1 and 10",
                        severity=ErrorSeverity.ERROR,
                        details={"count": count}
                    )
                )

            self._logger.info(
                f"Notifying next {count} in waitlist queue for hostel {hostel_id}, room type {room_type}",
                extra={
                    "hostel_id": str(hostel_id),
                    "room_type": room_type,
                    "count": count
                }
            )

            summary = self.repository.notify_next_in_queue(hostel_id, room_type, count=count)

            self.db.commit()

            self._logger.info(
                f"Notified {summary.get('notified', 0)} waitlist entries",
                extra={
                    "hostel_id": str(hostel_id),
                    "notified": summary.get('notified', 0)
                }
            )

            return ServiceResult.success(
                summary,
                message=f"Notified {summary.get('notified', 0)} waitlist entries"
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error notifying next in queue: {str(e)}", exc_info=True)
            return self._handle_exception(e, "notify next in queue", hostel_id)

    # -------------------------------------------------------------------------
    # Conversion Operations
    # -------------------------------------------------------------------------

    def conversion_response(
        self,
        request: WaitlistConversion,
    ) -> ServiceResult[bool]:
        """
        Handle user response to availability notification.
        
        Args:
            request: Conversion response data
            
        Returns:
            ServiceResult containing success boolean or error
        """
        try:
            # Validate request
            validation_error = self._validate_waitlist_conversion(request)
            if validation_error:
                return ServiceResult.failure(validation_error)

            action = "Accepting" if request.accepted else "Declining"
            self._logger.info(
                f"{action} waitlist conversion for {request.waitlist_id}",
                extra={
                    "waitlist_id": str(request.waitlist_id),
                    "accepted": request.accepted
                }
            )

            # Handle conversion response
            ok = self.repository.handle_conversion_response(request)

            # Commit transaction
            self.db.commit()

            if ok:
                self._logger.info(
                    f"Successfully processed conversion response for {request.waitlist_id}",
                    extra={
                        "waitlist_id": str(request.waitlist_id),
                        "accepted": request.accepted
                    }
                )
            else:
                self._logger.warning(
                    f"Conversion response processing returned false for {request.waitlist_id}",
                    extra={"waitlist_id": str(request.waitlist_id)}
                )

            message = (
                "Conversion accepted successfully" if request.accepted
                else "Conversion declined"
            ) if ok else "Failed to process conversion response"

            return ServiceResult.success(ok, message=message)

        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Validation error processing conversion response: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.BUSINESS_RULE_VIOLATION,
                    message=str(e),
                    severity=ErrorSeverity.ERROR,
                    details={"waitlist_id": str(request.waitlist_id)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error processing conversion response: {str(e)}", exc_info=True)
            return self._handle_exception(e, "conversion response", request.waitlist_id)

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def get_status(
        self,
        waitlist_id: UUID,
    ) -> ServiceResult[WaitlistStatusInfo]:
        """
        Get status of waitlist entry.
        
        Args:
            waitlist_id: UUID of waitlist entry
            
        Returns:
            ServiceResult containing WaitlistStatusInfo or error
        """
        try:
            self._logger.debug(f"Fetching waitlist status for {waitlist_id}")

            info = self.repository.get_status(waitlist_id)

            if not info:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Waitlist entry not found",
                        severity=ErrorSeverity.ERROR,
                        details={"waitlist_id": str(waitlist_id)}
                    )
                )

            return ServiceResult.success(info)

        except Exception as e:
            self._logger.error(f"Error fetching waitlist status: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get waitlist status", waitlist_id)

    def management_view(
        self,
        hostel_id: UUID,
        room_type: str,
    ) -> ServiceResult[WaitlistManagement]:
        """
        Get management view of waitlist for a room type.
        
        Args:
            hostel_id: UUID of hostel
            room_type: Room type
            
        Returns:
            ServiceResult containing WaitlistManagement or error
        """
        try:
            if not room_type or len(room_type.strip()) == 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Room type is required",
                        severity=ErrorSeverity.ERROR
                    )
                )

            self._logger.debug(
                f"Fetching waitlist management view for hostel {hostel_id}, room type {room_type}",
                extra={
                    "hostel_id": str(hostel_id),
                    "room_type": room_type
                }
            )

            mgmt = self.repository.get_management_view(hostel_id, room_type)

            return ServiceResult.success(
                mgmt,
                metadata={
                    "total_entries": len(mgmt.entries) if hasattr(mgmt, 'entries') else 0
                }
            )

        except Exception as e:
            self._logger.error(f"Error fetching waitlist management view: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get waitlist management view", hostel_id)

    def get_user_waitlist_entries(
        self,
        user_id: UUID,
        active_only: bool = True,
    ) -> ServiceResult[List[WaitlistEntry]]:
        """
        Get all waitlist entries for a user.
        
        Args:
            user_id: UUID of user
            active_only: Whether to return only active entries
            
        Returns:
            ServiceResult containing list of WaitlistEntry or error
        """
        try:
            self._logger.debug(
                f"Fetching waitlist entries for user {user_id}",
                extra={
                    "user_id": str(user_id),
                    "active_only": active_only
                }
            )

            entries = self.repository.get_user_waitlist_entries(user_id, active_only=active_only)

            return ServiceResult.success(
                entries,
                metadata={
                    "count": len(entries),
                    "active_only": active_only
                }
            )

        except Exception as e:
            self._logger.error(f"Error fetching user waitlist entries: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get user waitlist entries", user_id)

    # -------------------------------------------------------------------------
    # Analytics & Reporting
    # -------------------------------------------------------------------------

    def get_waitlist_statistics(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get waitlist statistics for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            ServiceResult containing statistics or error
        """
        try:
            # Validate date range
            if start_date and end_date:
                if start_date >= end_date:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message="Start date must be before end date",
                            severity=ErrorSeverity.ERROR
                        )
                    )

            self._logger.debug(
                f"Fetching waitlist statistics for hostel {hostel_id}",
                extra={
                    "hostel_id": str(hostel_id),
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
            )

            stats = self.repository.get_waitlist_statistics(
                hostel_id,
                start_date=start_date,
                end_date=end_date
            )

            return ServiceResult.success(stats)

        except Exception as e:
            self._logger.error(f"Error fetching waitlist statistics: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get waitlist statistics", hostel_id)

    def get_conversion_rate(
        self,
        hostel_id: UUID,
        room_type: Optional[str] = None,
        days: int = 30,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get waitlist to booking conversion rate.
        
        Args:
            hostel_id: UUID of hostel
            room_type: Optional room type filter
            days: Number of days to analyze
            
        Returns:
            ServiceResult containing conversion rate data or error
        """
        try:
            if days < 1 or days > 365:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Days must be between 1 and 365",
                        severity=ErrorSeverity.ERROR,
                        details={"days": days}
                    )
                )

            self._logger.debug(
                f"Calculating conversion rate for hostel {hostel_id}",
                extra={
                    "hostel_id": str(hostel_id),
                    "room_type": room_type,
                    "days": days
                }
            )

            conversion_data = self.repository.get_conversion_rate(
                hostel_id,
                room_type=room_type,
                days=days
            )

            return ServiceResult.success(
                conversion_data,
                metadata={
                    "analysis_period_days": days
                }
            )

        except Exception as e:
            self._logger.error(f"Error calculating conversion rate: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get conversion rate", hostel_id)

    def get_average_wait_time(
        self,
        hostel_id: UUID,
        room_type: Optional[str] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get average wait time for waitlist entries.
        
        Args:
            hostel_id: UUID of hostel
            room_type: Optional room type filter
            
        Returns:
            ServiceResult containing wait time data or error
        """
        try:
            self._logger.debug(
                f"Calculating average wait time for hostel {hostel_id}",
                extra={
                    "hostel_id": str(hostel_id),
                    "room_type": room_type
                }
            )

            wait_time_data = self.repository.get_average_wait_time(
                hostel_id,
                room_type=room_type
            )

            return ServiceResult.success(wait_time_data)

        except Exception as e:
            self._logger.error(f"Error calculating average wait time: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get average wait time", hostel_id)

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def bulk_notify(
        self,
        waitlist_ids: List[UUID],
        notification_message: str,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Send notifications to multiple waitlist entries.
        
        Args:
            waitlist_ids: List of waitlist entry UUIDs
            notification_message: Message to send
            
        Returns:
            ServiceResult containing summary or error
        """
        try:
            if not waitlist_ids or len(waitlist_ids) == 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="At least one waitlist ID is required",
                        severity=ErrorSeverity.ERROR
                    )
                )

            if len(waitlist_ids) > 100:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Cannot notify more than 100 entries at once",
                        severity=ErrorSeverity.ERROR,
                        details={"count": len(waitlist_ids)}
                    )
                )

            if not notification_message or len(notification_message.strip()) < 10:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Notification message must be at least 10 characters",
                        severity=ErrorSeverity.ERROR
                    )
                )

            self._logger.info(
                f"Sending bulk notifications to {len(waitlist_ids)} waitlist entries",
                extra={"entry_count": len(waitlist_ids)}
            )

            start_time = datetime.utcnow()

            summary = self.repository.bulk_notify(waitlist_ids, notification_message)

            self.db.commit()

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._logger.info(
                f"Bulk notification completed: {summary.get('notified', 0)} notified, "
                f"{summary.get('failed', 0)} failed in {duration_ms:.2f}ms",
                extra={
                    "notified": summary.get('notified', 0),
                    "failed": summary.get('failed', 0),
                    "duration_ms": duration_ms
                }
            )

            return ServiceResult.success(
                summary,
                message=f"Bulk notification completed: {summary.get('notified', 0)} notified, "
                        f"{summary.get('failed', 0)} failed",
                metadata={"duration_ms": duration_ms}
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error during bulk notification: {str(e)}", exc_info=True)
            return self._handle_exception(e, "bulk notify waitlist entries")

    def expire_old_entries(
        self,
        hostel_id: UUID,
        days_old: int = 90,
        dry_run: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Expire old waitlist entries.
        
        Args:
            hostel_id: UUID of hostel
            days_old: Age threshold in days
            dry_run: If True, only return count without expiring
            
        Returns:
            ServiceResult containing summary or error
        """
        try:
            if days_old < 30 or days_old > 365:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Days old must be between 30 and 365",
                        severity=ErrorSeverity.ERROR,
                        details={"days_old": days_old}
                    )
                )

            self._logger.info(
                f"{'Dry run: ' if dry_run else ''}Expiring waitlist entries older than {days_old} days for hostel {hostel_id}",
                extra={
                    "hostel_id": str(hostel_id),
                    "days_old": days_old,
                    "dry_run": dry_run
                }
            )

            summary = self.repository.expire_old_entries(hostel_id, days_old=days_old, dry_run=dry_run)

            if not dry_run:
                self.db.commit()

            self._logger.info(
                f"Expired {summary.get('expired', 0)} waitlist entries",
                extra={
                    "hostel_id": str(hostel_id),
                    "expired": summary.get('expired', 0),
                    "dry_run": dry_run
                }
            )

            return ServiceResult.success(
                summary,
                message=f"{'Would expire' if dry_run else 'Expired'} {summary.get('expired', 0)} entries"
            )

        except Exception as e:
            if not dry_run:
                self.db.rollback()
            self._logger.error(f"Error expiring old entries: {str(e)}", exc_info=True)
            return self._handle_exception(e, "expire old waitlist entries", hostel_id)