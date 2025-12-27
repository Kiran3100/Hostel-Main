"""
Fee Calculation Service

Handles fee calculations for:
- Quote generation (prospective calculations)
- Booking-based calculations (actual fees)
- Recalculations after modifications
- Calculation persistence and retrieval

Author: Senior Prompt Engineer
Version: 2.0.0
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.fee_structure import (
    FeeCalculationRepository,
    FeeStructureRepository
)
from app.models.fee_structure.fee_calculation import FeeCalculation as FeeCalculationModel
from app.models.fee_structure.fee_structure import FeeStructure as FeeStructureModel
from app.schemas.fee_structure.fee_calculation import (
    FeeCalculationRequest,
    FeeCalculation as FeeCalculationSchema,
)
from app.core1.logging import get_logger


class FeeCalculationService(BaseService[FeeCalculationModel, FeeCalculationRepository]):
    """
    Service for computing and managing fee calculations.
    
    Features:
    - Real-time quote generation
    - Persistent calculation records
    - Recalculation for booking modifications
    - Component-level breakdowns
    - Discount application
    - Tax calculations
    """

    def __init__(
        self,
        repository: FeeCalculationRepository,
        structure_repo: FeeStructureRepository,
        db_session: Session,
    ):
        """
        Initialize fee calculation service.

        Args:
            repository: Fee calculation repository
            structure_repo: Fee structure repository for fetching applicable structures
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self.structure_repo = structure_repo
        self._logger = get_logger(self.__class__.__name__)

    def calculate_quote(
        self,
        request: FeeCalculationRequest,
    ) -> ServiceResult[FeeCalculationSchema]:
        """
        Calculate a fee quote without persisting to database.

        Args:
            request: Calculation request with all required parameters

        Returns:
            ServiceResult containing calculated quote or error
        """
        try:
            # Validate request data
            validation_result = self._validate_calculation_request(request)
            if not validation_result.success:
                return validation_result

            # Find applicable fee structure
            structure = self.structure_repo.find_applicable(
                request.hostel_id,
                request.room_type,
                request.check_in_date,
            )

            if not structure:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No applicable fee structure found for the given criteria",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "hostel_id": str(request.hostel_id),
                            "room_type": request.room_type,
                            "check_in_date": str(request.check_in_date),
                        }
                    )
                )

            # Validate structure is active
            if structure.status != "active":
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.INVALID_STATE,
                        message=f"Fee structure is not active (status: {structure.status})",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "structure_id": str(structure.id),
                            "status": structure.status
                        }
                    )
                )

            # Perform calculation
            calculation = self.repository.calculate_quote_from_request(
                request,
                structure=structure
            )

            self._logger.info(
                "Fee quote calculated",
                extra={
                    "hostel_id": str(request.hostel_id),
                    "room_type": request.room_type,
                    "total_amount": float(calculation.total_amount) if hasattr(calculation, 'total_amount') else None,
                }
            )

            return ServiceResult.success(
                calculation,
                message="Fee quote calculated successfully"
            )

        except ValueError as e:
            self._logger.error(
                "Validation error during quote calculation",
                exc_info=True,
                extra={"error": str(e)}
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid calculation parameters: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )

        except Exception as e:
            return self._handle_exception(e, "calculate fee quote", request.hostel_id)

    def calculate_and_save(
        self,
        request: FeeCalculationRequest,
        booking_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[FeeCalculationModel]:
        """
        Calculate fees and persist to database.

        Args:
            request: Calculation request
            booking_id: Optional associated booking ID
            student_id: Optional associated student ID
            created_by: UUID of user creating the calculation

        Returns:
            ServiceResult containing persisted calculation or error
        """
        try:
            # First calculate the quote
            quote_result = self.calculate_quote(request)
            if not quote_result.success:
                return quote_result

            # Convert schema to model and persist
            calculation_model = self._schema_to_model(
                quote_result.data,
                booking_id=booking_id,
                student_id=student_id,
                created_by=created_by,
            )

            saved_calculation = self.repository.save_calculation(calculation_model)
            self.db.commit()
            self.db.refresh(saved_calculation)

            self._logger.info(
                "Fee calculation saved",
                extra={
                    "calculation_id": str(saved_calculation.id),
                    "booking_id": str(booking_id) if booking_id else None,
                    "student_id": str(student_id) if student_id else None,
                }
            )

            return ServiceResult.success(
                saved_calculation,
                message="Fee calculation saved successfully"
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "save fee calculation")

    def recompute_for_booking(
        self,
        booking_id: UUID,
        reason: Optional[str] = None,
    ) -> ServiceResult[FeeCalculationModel]:
        """
        Recompute fee calculation for an existing booking.

        Args:
            booking_id: UUID of the booking to recalculate
            reason: Optional reason for recalculation

        Returns:
            ServiceResult containing new calculation or error
        """
        try:
            # Validate booking exists and get its details
            # This would typically fetch from a booking repository
            booking = self._get_booking_details(booking_id)
            if not booking:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Booking not found: {booking_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"booking_id": str(booking_id)}
                    )
                )

            # Perform recalculation
            new_calculation = self.repository.recompute_for_booking(booking_id)
            self.db.commit()
            self.db.refresh(new_calculation)

            self._logger.info(
                "Fee calculation recomputed for booking",
                extra={
                    "booking_id": str(booking_id),
                    "calculation_id": str(new_calculation.id),
                    "reason": reason,
                }
            )

            return ServiceResult.success(
                new_calculation,
                message="Fee calculation recomputed successfully"
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "recompute fee calculation", booking_id)

    def get_calculation_by_id(
        self,
        calculation_id: UUID,
    ) -> ServiceResult[FeeCalculationModel]:
        """
        Retrieve a specific fee calculation by ID.

        Args:
            calculation_id: UUID of the calculation

        Returns:
            ServiceResult containing the calculation or error
        """
        try:
            calculation = self.repository.get_by_id(calculation_id)
            
            if not calculation:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Fee calculation not found: {calculation_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"calculation_id": str(calculation_id)}
                    )
                )

            return ServiceResult.success(calculation)

        except Exception as e:
            return self._handle_exception(e, "get fee calculation", calculation_id)

    def get_calculations_for_booking(
        self,
        booking_id: UUID,
        include_superseded: bool = False,
    ) -> ServiceResult[List[FeeCalculationModel]]:
        """
        Get all fee calculations for a booking.

        Args:
            booking_id: UUID of the booking
            include_superseded: If True, include superseded calculations

        Returns:
            ServiceResult containing list of calculations
        """
        try:
            calculations = self.repository.get_calculations_for_booking(
                booking_id,
                include_superseded=include_superseded
            )

            return ServiceResult.success(
                calculations,
                metadata={
                    "count": len(calculations),
                    "booking_id": str(booking_id),
                }
            )

        except Exception as e:
            return self._handle_exception(e, "get calculations for booking", booking_id)

    def get_calculations_for_student(
        self,
        student_id: UUID,
        active_only: bool = True,
    ) -> ServiceResult[List[FeeCalculationModel]]:
        """
        Get all fee calculations for a student.

        Args:
            student_id: UUID of the student
            active_only: If True, return only active calculations

        Returns:
            ServiceResult containing list of calculations
        """
        try:
            calculations = self.repository.get_calculations_for_student(
                student_id,
                active_only=active_only
            )

            return ServiceResult.success(
                calculations,
                metadata={
                    "count": len(calculations),
                    "student_id": str(student_id),
                }
            )

        except Exception as e:
            return self._handle_exception(e, "get calculations for student", student_id)

    def compare_calculations(
        self,
        calculation_id_1: UUID,
        calculation_id_2: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Compare two fee calculations and return differences.

        Args:
            calculation_id_1: First calculation ID
            calculation_id_2: Second calculation ID

        Returns:
            ServiceResult containing comparison details
        """
        try:
            calc1 = self.repository.get_by_id(calculation_id_1)
            calc2 = self.repository.get_by_id(calculation_id_2)

            if not calc1:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"First calculation not found: {calculation_id_1}",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            if not calc2:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Second calculation not found: {calculation_id_2}",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            comparison = self._build_comparison(calc1, calc2)

            return ServiceResult.success(
                comparison,
                message="Calculations compared successfully"
            )

        except Exception as e:
            return self._handle_exception(e, "compare calculations")

    # ==================== Private Helper Methods ====================

    def _validate_calculation_request(
        self,
        request: FeeCalculationRequest,
    ) -> ServiceResult[None]:
        """Validate fee calculation request data."""
        # Validate required fields
        if not request.hostel_id:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Hostel ID is required",
                    severity=ErrorSeverity.ERROR,
                )
            )

        if not request.room_type or not request.room_type.strip():
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Room type is required",
                    severity=ErrorSeverity.ERROR,
                )
            )

        if not request.check_in_date:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Check-in date is required",
                    severity=ErrorSeverity.ERROR,
                )
            )

        # Validate date logic
        if hasattr(request, 'check_out_date') and request.check_out_date:
            if request.check_out_date <= request.check_in_date:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Check-out date must be after check-in date",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "check_in_date": str(request.check_in_date),
                            "check_out_date": str(request.check_out_date),
                        }
                    )
                )

        # Validate stay duration if provided
        if hasattr(request, 'duration_months') and request.duration_months is not None:
            if request.duration_months <= 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Duration must be positive",
                        severity=ErrorSeverity.ERROR,
                    )
                )

        return ServiceResult.success(None)

    def _schema_to_model(
        self,
        schema: FeeCalculationSchema,
        booking_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        created_by: Optional[UUID] = None,
    ) -> FeeCalculationModel:
        """Convert calculation schema to model for persistence."""
        # Implementation depends on your schema/model structure
        # This is a placeholder
        model = FeeCalculationModel()
        # Map fields from schema to model
        # ...
        return model

    def _get_booking_details(self, booking_id: UUID) -> Optional[Dict[str, Any]]:
        """Fetch booking details for recalculation."""
        # This would typically call a booking repository
        # Placeholder implementation
        return None

    def _build_comparison(
        self,
        calc1: FeeCalculationModel,
        calc2: FeeCalculationModel,
    ) -> Dict[str, Any]:
        """Build detailed comparison between two calculations."""
        comparison = {
            "calculation_1": {
                "id": str(calc1.id),
                "created_at": calc1.created_at.isoformat() if calc1.created_at else None,
            },
            "calculation_2": {
                "id": str(calc2.id),
                "created_at": calc2.created_at.isoformat() if calc2.created_at else None,
            },
            "differences": {},
            "component_changes": [],
        }

        # Compare amounts
        if hasattr(calc1, 'total_amount') and hasattr(calc2, 'total_amount'):
            amount_diff = calc2.total_amount - calc1.total_amount
            comparison["differences"]["total_amount"] = {
                "old": float(calc1.total_amount),
                "new": float(calc2.total_amount),
                "change": float(amount_diff),
                "percentage_change": float(amount_diff / calc1.total_amount * 100) if calc1.total_amount else 0,
            }

        # Additional comparison logic...

        return comparison