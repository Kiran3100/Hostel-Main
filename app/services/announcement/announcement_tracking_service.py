"""
Announcement engagement tracking service.

Enhanced with analytics, engagement scoring, and predictive insights.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.announcement import AnnouncementTrackingRepository
from app.models.announcement.announcement_tracking import (
    AnnouncementView as AnnouncementViewModel
)
from app.schemas.announcement.announcement_tracking import (
    ReadReceipt,
    ReadReceiptResponse,
    AcknowledgmentRequest,
    AcknowledgmentResponse,
    PendingAcknowledgment,
    AcknowledgmentTracking,
    EngagementMetrics,
    ReadingTime,
    StudentEngagement,
    EngagementTrend,
    AnnouncementAnalytics,
)


class AnnouncementTrackingService(
    BaseService[AnnouncementViewModel, AnnouncementTrackingRepository]
):
    """
    Service for recording and analyzing announcement engagement.
    
    Responsibilities:
    - Track views and read receipts
    - Manage acknowledgments and deadlines
    - Compute engagement metrics
    - Generate analytics and insights
    - Monitor reading patterns
    """

    # Valid device types
    VALID_DEVICE_TYPES = {"web", "mobile_ios", "mobile_android", "tablet", "other"}
    
    # Engagement thresholds (seconds)
    QUICK_READ_THRESHOLD = 10
    NORMAL_READ_THRESHOLD = 60
    DETAILED_READ_THRESHOLD = 180

    def __init__(
        self,
        repository: AnnouncementTrackingRepository,
        db_session: Session
    ):
        """
        Initialize tracking service.
        
        Args:
            repository: Tracking repository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)

    def record_view(
        self,
        announcement_id: UUID,
        student_id: UUID,
        device_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[bool]:
        """
        Record a view event for announcement.
        
        Args:
            announcement_id: Unique identifier of announcement
            student_id: Unique identifier of student
            device_type: Type of device used
            metadata: Additional view context
            
        Returns:
            ServiceResult containing success boolean or error
            
        Notes:
            - Records timestamp and device information
            - Supports duplicate views for analytics
            - Lightweight operation for high volume
        """
        try:
            # Validate device type if provided
            if device_type and device_type not in self.VALID_DEVICE_TYPES:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid device_type: {device_type}. "
                                f"Must be one of {self.VALID_DEVICE_TYPES}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Record view
            self.repository.record_view(
                announcement_id=announcement_id,
                student_id=student_id,
                device_type=device_type,
                metadata=metadata or {}
            )
            
            # Commit transaction
            self.db.commit()
            
            return ServiceResult.success(
                data=True,
                message="View recorded successfully",
                metadata={
                    "announcement_id": str(announcement_id),
                    "student_id": str(student_id),
                    "viewed_at": datetime.utcnow().isoformat(),
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(
                e, "record view", announcement_id
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "record view", announcement_id)

    def submit_read_receipt(
        self,
        receipt: ReadReceipt,
    ) -> ServiceResult[ReadReceiptResponse]:
        """
        Submit read receipt with reading time.
        
        Args:
            receipt: Read receipt data
            
        Returns:
            ServiceResult containing ReadReceiptResponse or error
            
        Notes:
            - Records reading duration
            - Categorizes reading pattern
            - Updates engagement metrics
            - One receipt per student per announcement
        """
        try:
            # Validate reading time is reasonable
            if receipt.reading_time_seconds < 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Reading time cannot be negative",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            if receipt.reading_time_seconds > 3600:  # 1 hour max
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Reading time exceeds maximum allowed (1 hour)",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Submit receipt
            response = self.repository.submit_read_receipt(receipt)
            
            # Commit transaction
            self.db.commit()
            
            # Categorize reading pattern
            reading_pattern = self._categorize_reading_time(
                receipt.reading_time_seconds
            )
            
            return ServiceResult.success(
                data=response,
                message="Read receipt submitted successfully",
                metadata={
                    "announcement_id": str(receipt.announcement_id),
                    "student_id": str(receipt.student_id),
                    "reading_time": receipt.reading_time_seconds,
                    "reading_pattern": reading_pattern,
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(
                e, "submit read receipt", receipt.announcement_id
            )
            
        except ValueError as e:
            self.db.rollback()
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid read receipt: {str(e)}",
                    severity=ErrorSeverity.WARNING,
                )
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(
                e, "submit read receipt", receipt.announcement_id
            )

    def acknowledge(
        self,
        request: AcknowledgmentRequest,
    ) -> ServiceResult[AcknowledgmentResponse]:
        """
        Submit acknowledgment for announcement.
        
        Args:
            request: Acknowledgment request data
            
        Returns:
            ServiceResult containing AcknowledgmentResponse or error
            
        Notes:
            - Required for certain announcement types
            - May include acknowledgment text/signature
            - Tracks on-time vs late acknowledgments
            - Sends confirmation to student
        """
        try:
            # Validate announcement requires acknowledgment
            requires_ack = self._check_requires_acknowledgment(
                request.announcement_id
            )
            if not requires_ack.success:
                return requires_ack
            
            # Submit acknowledgment
            response = self.repository.submit_acknowledgment(request)
            
            # Commit transaction
            self.db.commit()
            
            # Check if on-time
            is_on_time = self._is_acknowledgment_on_time(
                request.announcement_id,
                datetime.utcnow()
            )
            
            return ServiceResult.success(
                data=response,
                message="Acknowledgment submitted successfully",
                metadata={
                    "announcement_id": str(request.announcement_id),
                    "student_id": str(request.student_id),
                    "acknowledged_at": datetime.utcnow().isoformat(),
                    "on_time": is_on_time,
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(
                e, "submit acknowledgment", request.announcement_id
            )
            
        except ValueError as e:
            self.db.rollback()
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid acknowledgment: {str(e)}",
                    severity=ErrorSeverity.WARNING,
                )
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(
                e, "submit acknowledgment", request.announcement_id
            )

    def get_acknowledgment_tracking(
        self,
        announcement_id: UUID,
    ) -> ServiceResult[AcknowledgmentTracking]:
        """
        Get acknowledgment progress tracking.
        
        Args:
            announcement_id: Unique identifier of announcement
            
        Returns:
            ServiceResult containing AcknowledgmentTracking or error
            
        Notes:
            - Shows pending, on-time, and late acknowledgments
            - Includes student details for follow-up
            - Calculates completion percentage
            - Identifies at-risk students
        """
        try:
            tracking = self.repository.get_acknowledgment_tracking(
                announcement_id
            )
            
            if not tracking:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No acknowledgment tracking found for announcement {announcement_id}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            return ServiceResult.success(
                data=tracking,
                message="Acknowledgment tracking retrieved successfully",
                metadata={
                    "announcement_id": str(announcement_id),
                    "completion_rate": self._calculate_acknowledgment_rate(tracking),
                    "pending_count": tracking.pending_count if hasattr(tracking, 'pending_count') else 0,
                }
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(
                e, "get acknowledgment tracking", announcement_id
            )
            
        except Exception as e:
            return self._handle_exception(
                e, "get acknowledgment tracking", announcement_id
            )

    def compute_engagement(
        self,
        announcement_id: UUID,
    ) -> ServiceResult[AnnouncementAnalytics]:
        """
        Compute comprehensive engagement analytics.
        
        Args:
            announcement_id: Unique identifier of announcement
            
        Returns:
            ServiceResult containing AnnouncementAnalytics or error
            
        Notes:
            - View and read metrics
            - Reading time distribution
            - Device and source breakdown
            - Engagement scores per student
            - Temporal engagement patterns
        """
        try:
            analytics = self.repository.get_analytics(announcement_id)
            
            if not analytics:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No analytics data found for announcement {announcement_id}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Compute additional metrics
            engagement_score = self._calculate_engagement_score(analytics)
            
            return ServiceResult.success(
                data=analytics,
                message="Engagement analytics computed successfully",
                metadata={
                    "announcement_id": str(announcement_id),
                    "engagement_score": engagement_score,
                    "view_rate": analytics.view_rate if hasattr(analytics, 'view_rate') else 0,
                    "read_rate": analytics.read_rate if hasattr(analytics, 'read_rate') else 0,
                }
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(
                e, "compute engagement", announcement_id
            )
            
        except Exception as e:
            return self._handle_exception(
                e, "compute engagement", announcement_id
            )

    def get_student_engagement(
        self,
        student_id: UUID,
        hostel_id: Optional[UUID] = None,
        days: int = 30,
    ) -> ServiceResult[StudentEngagement]:
        """
        Get engagement metrics for a specific student.
        
        Args:
            student_id: Unique identifier of student
            hostel_id: Optional hostel filter
            days: Number of days to analyze
            
        Returns:
            ServiceResult containing StudentEngagement or error
            
        Notes:
            - Aggregated engagement across announcements
            - Reading patterns and preferences
            - Acknowledgment compliance rate
            - Engagement trends over time
        """
        try:
            # Validate days parameter
            if days < 1 or days > 365:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Days must be between 1 and 365",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Fetch student engagement
            engagement = self.repository.get_student_engagement(
                student_id=student_id,
                hostel_id=hostel_id,
                days=days
            )
            
            return ServiceResult.success(
                data=engagement,
                message="Student engagement retrieved successfully",
                metadata={
                    "student_id": str(student_id),
                    "period_days": days,
                    "total_announcements": engagement.total_announcements if hasattr(engagement, 'total_announcements') else 0,
                }
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(
                e, "get student engagement", student_id
            )
            
        except Exception as e:
            return self._handle_exception(
                e, "get student engagement", student_id
            )

    def get_engagement_trend(
        self,
        announcement_id: UUID,
        interval: str = "hourly",
    ) -> ServiceResult[List[EngagementTrend]]:
        """
        Get time-series engagement trends.
        
        Args:
            announcement_id: Unique identifier of announcement
            interval: Time interval (hourly/daily/weekly)
            
        Returns:
            ServiceResult containing engagement trends or error
            
        Notes:
            - Time-series view and read data
            - Identifies peak engagement periods
            - Useful for optimizing future publish times
        """
        try:
            # Validate interval
            valid_intervals = {"hourly", "daily", "weekly"}
            if interval not in valid_intervals:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid interval: {interval}. "
                                f"Must be one of {valid_intervals}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Fetch trends
            trends = self.repository.get_engagement_trend(
                announcement_id=announcement_id,
                interval=interval
            )
            
            return ServiceResult.success(
                data=trends,
                message="Engagement trends retrieved successfully",
                metadata={
                    "announcement_id": str(announcement_id),
                    "interval": interval,
                    "data_points": len(trends),
                }
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(
                e, "get engagement trend", announcement_id
            )
            
        except Exception as e:
            return self._handle_exception(
                e, "get engagement trend", announcement_id
            )

    def get_pending_acknowledgments(
        self,
        student_id: UUID,
        hostel_id: Optional[UUID] = None,
    ) -> ServiceResult[List[PendingAcknowledgment]]:
        """
        Get pending acknowledgments for a student.
        
        Args:
            student_id: Unique identifier of student
            hostel_id: Optional hostel filter
            
        Returns:
            ServiceResult containing pending acknowledgments or error
            
        Notes:
            - Lists announcements requiring acknowledgment
            - Shows deadlines and urgency
            - Ordered by deadline proximity
        """
        try:
            pending = self.repository.get_pending_acknowledgments(
                student_id=student_id,
                hostel_id=hostel_id
            )
            
            return ServiceResult.success(
                data=pending,
                message=f"Found {len(pending)} pending acknowledgments",
                metadata={
                    "student_id": str(student_id),
                    "count": len(pending),
                    "hostel_id": str(hostel_id) if hostel_id else None,
                }
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(
                e, "get pending acknowledgments", student_id
            )
            
        except Exception as e:
            return self._handle_exception(
                e, "get pending acknowledgments", student_id
            )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _categorize_reading_time(
        self,
        seconds: int
    ) -> str:
        """
        Categorize reading time into patterns.
        
        Args:
            seconds: Reading time in seconds
            
        Returns:
            Reading pattern category
        """
        if seconds < self.QUICK_READ_THRESHOLD:
            return "quick_skim"
        elif seconds < self.NORMAL_READ_THRESHOLD:
            return "normal_read"
        elif seconds < self.DETAILED_READ_THRESHOLD:
            return "detailed_read"
        else:
            return "thorough_study"

    def _check_requires_acknowledgment(
        self,
        announcement_id: UUID
    ) -> ServiceResult:
        """
        Check if announcement requires acknowledgment.
        
        Args:
            announcement_id: Announcement to check
            
        Returns:
            ServiceResult indicating if acknowledgment required
        """
        try:
            requires = self.repository.requires_acknowledgment(
                announcement_id
            )
            
            if not requires:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="This announcement does not require acknowledgment",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            return ServiceResult.success(True)
            
        except Exception:
            # If method doesn't exist, assume acknowledgment allowed
            return ServiceResult.success(True)

    def _is_acknowledgment_on_time(
        self,
        announcement_id: UUID,
        acknowledged_at: datetime
    ) -> bool:
        """
        Check if acknowledgment was submitted on time.
        
        Args:
            announcement_id: Announcement being acknowledged
            acknowledged_at: Acknowledgment timestamp
            
        Returns:
            True if on time, False if late
        """
        try:
            deadline = self.repository.get_acknowledgment_deadline(
                announcement_id
            )
            
            if not deadline:
                return True  # No deadline means always on time
            
            return acknowledged_at <= deadline
            
        except Exception:
            return True  # Default to on-time if can't determine

    def _calculate_acknowledgment_rate(
        self,
        tracking: AcknowledgmentTracking
    ) -> float:
        """
        Calculate acknowledgment completion rate.
        
        Args:
            tracking: Acknowledgment tracking data
            
        Returns:
            Completion rate as percentage (0-100)
        """
        total = getattr(tracking, 'total_required', 0)
        if total == 0:
            return 0.0
        
        acknowledged = getattr(tracking, 'acknowledged_count', 0)
        return round((acknowledged / total) * 100, 2)

    def _calculate_engagement_score(
        self,
        analytics: AnnouncementAnalytics
    ) -> float:
        """
        Calculate overall engagement score.
        
        Args:
            analytics: Announcement analytics data
            
        Returns:
            Engagement score (0-100)
        """
        # Weighted scoring based on multiple factors
        view_weight = 0.2
        read_weight = 0.3
        reading_time_weight = 0.3
        acknowledgment_weight = 0.2
        
        view_score = getattr(analytics, 'view_rate', 0) * view_weight
        read_score = getattr(analytics, 'read_rate', 0) * read_weight
        reading_time_score = self._score_reading_time(analytics) * reading_time_weight
        ack_score = getattr(analytics, 'acknowledgment_rate', 0) * acknowledgment_weight
        
        total_score = view_score + read_score + reading_time_score + ack_score
        return round(total_score, 2)

    def _score_reading_time(
        self,
        analytics: AnnouncementAnalytics
    ) -> float:
        """
        Score reading time quality.
        
        Args:
            analytics: Analytics with reading time data
            
        Returns:
            Reading time score (0-100)
        """
        avg_reading_time = getattr(analytics, 'avg_reading_time', 0)
        
        # Optimal reading time is between 30-120 seconds
        if 30 <= avg_reading_time <= 120:
            return 100.0
        elif avg_reading_time < 30:
            # Too quick, might not be reading thoroughly
            return (avg_reading_time / 30) * 80
        else:
            # Too long, diminishing returns
            return max(60, 100 - ((avg_reading_time - 120) / 10))

    def _handle_database_error(
        self,
        error: SQLAlchemyError,
        operation: str,
        entity_id: Optional[UUID] = None,
    ) -> ServiceResult:
        """Handle database-specific errors."""
        error_msg = f"Database error during {operation}"
        if entity_id:
            error_msg += f" for {entity_id}"
        
        return ServiceResult.failure(
            ServiceError(
                code=ErrorCode.DATABASE_ERROR,
                message=error_msg,
                severity=ErrorSeverity.ERROR,
                details={"original_error": str(error)},
            )
        )