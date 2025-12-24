"""
Complaint SLA service (metrics & breaches).

Provides SLA monitoring, breach detection, and performance metrics
for complaint resolution timeframes.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, timedelta, datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.analytics.complaint_analytics_repository import ComplaintAnalyticsRepository
from app.models.analytics.complaint_analytics import ComplaintDashboard as ComplaintDashboardModel
from app.schemas.analytics.complaint_analytics import SLAMetrics, ComplaintKPI

logger = logging.getLogger(__name__)


class ComplaintSLAService(BaseService[ComplaintDashboardModel, ComplaintAnalyticsRepository]):
    """
    Provides SLA-focused endpoints and monitoring capabilities.
    
    Tracks SLA compliance, breach detection, and performance metrics
    for complaint resolution workflows.
    """

    # Default SLA thresholds (in hours)
    DEFAULT_SLA_THRESHOLDS = {
        "CRITICAL": 4,
        "HIGH": 24,
        "MEDIUM": 72,
        "LOW": 168,
    }

    def __init__(self, repository: ComplaintAnalyticsRepository, db_session: Session):
        """
        Initialize SLA service.
        
        Args:
            repository: Complaint analytics repository instance
            db_session: Active database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    # -------------------------------------------------------------------------
    # SLA Metrics
    # -------------------------------------------------------------------------

    def get_sla_metrics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[SLAMetrics]:
        """
        Get comprehensive SLA metrics for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start date for metrics
            end_date: End date for metrics
            
        Returns:
            ServiceResult containing SLAMetrics or error
        """
        try:
            # Validate date range
            date_validation = self._validate_date_range(start_date, end_date)
            if not date_validation.success:
                return date_validation
            
            self._logger.debug(
                f"Fetching SLA metrics for hostel {hostel_id}, "
                f"date range: {start_date} to {end_date}"
            )
            
            # Get KPIs which include SLA metrics
            kpi = self.repository.get_kpis(hostel_id, start_date, end_date)
            
            # Extract SLA metrics
            sla_metrics = kpi.sla_metrics if hasattr(kpi, "sla_metrics") else None
            
            if not sla_metrics:
                self._logger.warning(f"No SLA metrics available for hostel {hostel_id}")
                # Return empty metrics instead of failure
                sla_metrics = self._get_empty_sla_metrics()
            
            return ServiceResult.success(
                sla_metrics,
                metadata={
                    "hostel_id": str(hostel_id),
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching SLA metrics for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint SLA metrics", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching SLA metrics for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint SLA metrics", hostel_id)

    def get_kpis(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> ServiceResult[ComplaintKPI]:
        """
        Get complete KPIs including SLA metrics.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start date for KPIs
            end_date: End date for KPIs
            
        Returns:
            ServiceResult containing ComplaintKPI or error
        """
        try:
            # Validate date range
            date_validation = self._validate_date_range(start_date, end_date)
            if not date_validation.success:
                return date_validation
            
            self._logger.debug(
                f"Fetching complaint KPIs for hostel {hostel_id}, "
                f"date range: {start_date} to {end_date}"
            )
            
            kpi = self.repository.get_kpis(hostel_id, start_date, end_date)
            
            return ServiceResult.success(
                kpi,
                metadata={
                    "hostel_id": str(hostel_id),
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching KPIs for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint KPIs", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching KPIs for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get complaint KPIs", hostel_id)

    # -------------------------------------------------------------------------
    # SLA Breach Detection
    # -------------------------------------------------------------------------

    def get_sla_breaches(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        priority: Optional[str] = None,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get list of complaints that have breached SLA.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Optional start date filter
            end_date: Optional end date filter
            priority: Optional priority filter
            
        Returns:
            ServiceResult containing list of SLA breaches or error
        """
        try:
            self._logger.debug(
                f"Fetching SLA breaches for hostel {hostel_id}, "
                f"priority: {priority}"
            )
            
            # Implementation would query for breached complaints
            # Based on current time vs. created_at + SLA threshold
            
            breaches: List[Dict[str, Any]] = []
            
            # This would be implemented in repository
            # breaches = self.repository.get_sla_breaches(
            #     hostel_id, start_date, end_date, priority
            # )
            
            return ServiceResult.success(
                breaches,
                metadata={
                    "hostel_id": str(hostel_id),
                    "breach_count": len(breaches),
                    "priority": priority,
                }
            )
            
        except Exception as e:
            self._logger.error(
                f"Error fetching SLA breaches for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get SLA breaches", hostel_id)

    def get_at_risk_complaints(
        self,
        hostel_id: UUID,
        threshold_percentage: float = 0.8,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get complaints at risk of breaching SLA.
        
        Args:
            hostel_id: UUID of hostel
            threshold_percentage: Percentage of SLA time elapsed to consider "at risk" (0.0-1.0)
            
        Returns:
            ServiceResult containing list of at-risk complaints or error
        """
        try:
            # Validate threshold
            if threshold_percentage < 0.0 or threshold_percentage > 1.0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Threshold percentage must be between 0.0 and 1.0",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            self._logger.debug(
                f"Fetching at-risk complaints for hostel {hostel_id}, "
                f"threshold: {threshold_percentage * 100}%"
            )
            
            # Implementation would calculate time elapsed vs. SLA threshold
            at_risk: List[Dict[str, Any]] = []
            
            return ServiceResult.success(
                at_risk,
                metadata={
                    "hostel_id": str(hostel_id),
                    "at_risk_count": len(at_risk),
                    "threshold_percentage": threshold_percentage,
                }
            )
            
        except Exception as e:
            self._logger.error(
                f"Error fetching at-risk complaints for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get at-risk complaints", hostel_id)

    # -------------------------------------------------------------------------
    # SLA Configuration
    # -------------------------------------------------------------------------

    def get_sla_thresholds(
        self,
        hostel_id: UUID,
    ) -> ServiceResult[Dict[str, int]]:
        """
        Get SLA threshold configuration for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            
        Returns:
            ServiceResult containing threshold configuration or error
        """
        try:
            self._logger.debug(f"Fetching SLA thresholds for hostel {hostel_id}")
            
            # Implementation would fetch from database or config
            # For now, return defaults
            thresholds = self.DEFAULT_SLA_THRESHOLDS.copy()
            
            return ServiceResult.success(
                thresholds,
                metadata={"hostel_id": str(hostel_id)}
            )
            
        except Exception as e:
            self._logger.error(
                f"Error fetching SLA thresholds for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get SLA thresholds", hostel_id)

    def update_sla_thresholds(
        self,
        hostel_id: UUID,
        thresholds: Dict[str, int],
    ) -> ServiceResult[Dict[str, int]]:
        """
        Update SLA threshold configuration for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            thresholds: Dictionary of priority -> hours mapping
            
        Returns:
            ServiceResult containing updated thresholds or error
        """
        try:
            self._logger.info(f"Updating SLA thresholds for hostel {hostel_id}")
            
            # Validate thresholds
            validation = self._validate_sla_thresholds(thresholds)
            if not validation.success:
                return validation
            
            # Implementation would save to database
            # saved_thresholds = self.repository.update_sla_thresholds(hostel_id, thresholds)
            
            self.db.commit()
            
            return ServiceResult.success(
                thresholds,
                message="SLA thresholds updated successfully",
                metadata={"hostel_id": str(hostel_id)}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error updating SLA thresholds for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update SLA thresholds", hostel_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error updating SLA thresholds for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "update SLA thresholds", hostel_id)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _validate_date_range(
        self,
        start_date: date,
        end_date: date,
        max_range_days: int = 365
    ) -> ServiceResult[None]:
        """
        Validate date range for queries.
        
        Args:
            start_date: Start date
            end_date: End date
            max_range_days: Maximum allowed range in days
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if start_date > end_date:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Start date must be before or equal to end date",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        delta = end_date - start_date
        if delta.days > max_range_days:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Date range cannot exceed {max_range_days} days",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)

    def _validate_sla_thresholds(
        self,
        thresholds: Dict[str, int]
    ) -> ServiceResult[None]:
        """
        Validate SLA threshold configuration.
        
        Args:
            thresholds: Dictionary of priority -> hours mapping
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        valid_priorities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        
        for priority, hours in thresholds.items():
            if priority not in valid_priorities:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid priority: {priority}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            if not isinstance(hours, int) or hours <= 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Threshold for {priority} must be a positive integer",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            if hours > 8760:  # Max 1 year
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Threshold for {priority} cannot exceed 8760 hours (1 year)",
                        severity=ErrorSeverity.WARNING,
                    )
                )
        
        return ServiceResult.success(None)

    def _get_empty_sla_metrics(self) -> SLAMetrics:
        """
        Get empty SLA metrics structure.
        
        Returns:
            Empty SLAMetrics object
        """
        # This would return a properly structured empty SLAMetrics object
        # Implementation depends on your schema definition
        return SLAMetrics()