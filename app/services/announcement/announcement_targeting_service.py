"""
Targeting & audience selection service for announcements.

Enhanced with validation, caching optimization, and preview capabilities.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.announcement import AnnouncementTargetingRepository
from app.models.announcement.announcement_targeting import (
    AnnouncementTarget as AnnouncementTargetModel
)
from app.schemas.announcement.announcement_targeting import (
    TargetingConfig,
    AudienceSelection,
    TargetRooms,
    TargetFloors,
    IndividualTargeting,
    TargetingSummary,
    BulkTargeting,
    TargetingPreview,
)


class AnnouncementTargetingService(
    BaseService[AnnouncementTargetModel, AnnouncementTargetingRepository]
):
    """
    Business logic for audience targeting with advanced selection capabilities.
    
    Responsibilities:
    - Apply and combine targeting rules
    - Preview audience before commitment
    - Manage exclusions and overrides
    - Compute targeting summaries and statistics
    """

    # Valid combine modes
    VALID_COMBINE_MODES = {"union", "intersection", "difference"}
    
    # Maximum preview size
    MAX_PREVIEW_SIZE = 500

    def __init__(
        self,
        repository: AnnouncementTargetingRepository,
        db_session: Session
    ):
        """
        Initialize targeting service.
        
        Args:
            repository: Targeting repository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)

    def apply_targeting(
        self,
        announcement_id: UUID,
        rules: List[TargetingConfig],
        combine_mode: str = "union",
        global_exclusions: Optional[List[UUID]] = None,
    ) -> ServiceResult[TargetingSummary]:
        """
        Apply multiple targeting rules and update audience cache.
        
        Args:
            announcement_id: Unique identifier of announcement
            rules: List of targeting configurations to apply
            combine_mode: How to combine multiple rules (union/intersection/difference)
            global_exclusions: List of student IDs to exclude globally
            
        Returns:
            ServiceResult containing TargetingSummary or error
            
        Notes:
            - Validates all rules before applying
            - Updates audience cache atomically
            - Computes final recipient count
        """
        try:
            # Validate combine mode
            if combine_mode not in self.VALID_COMBINE_MODES:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid combine_mode: {combine_mode}. "
                                f"Must be one of {self.VALID_COMBINE_MODES}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Validate rules list
            if not rules:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="At least one targeting rule is required",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Validate each rule configuration
            validation_result = self._validate_targeting_rules(rules)
            if not validation_result.success:
                return validation_result
            
            # Apply targeting rules
            summary = self.repository.apply_rules(
                announcement_id=announcement_id,
                rules=rules,
                combine_mode=combine_mode,
                global_exclusions=global_exclusions or [],
            )
            
            # Commit transaction
            self.db.commit()
            
            return ServiceResult.success(
                data=summary,
                message=f"Targeting applied successfully to {summary.total_recipients} recipients",
                metadata={
                    "total_recipients": summary.total_recipients,
                    "rules_count": len(rules),
                    "combine_mode": combine_mode,
                    "exclusions_count": len(global_exclusions or []),
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(
                e, "apply targeting", announcement_id
            )
            
        except ValueError as e:
            self.db.rollback()
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid targeting configuration: {str(e)}",
                    severity=ErrorSeverity.WARNING,
                )
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "apply targeting", announcement_id)

    def preview_targeting(
        self,
        preview: TargetingPreview,
        max_preview: int = 50,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Preview targeting configuration before applying to announcement.
        
        Args:
            preview: Targeting preview configuration
            max_preview: Maximum number of recipients to return in preview
            
        Returns:
            ServiceResult containing preview data or error
            
        Notes:
            - Does not modify database state
            - Useful for validating rules before commitment
            - Returns sample of matching recipients
        """
        try:
            # Validate max preview size
            if max_preview < 1:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="max_preview must be at least 1",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            if max_preview > self.MAX_PREVIEW_SIZE:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"max_preview cannot exceed {self.MAX_PREVIEW_SIZE}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Validate preview configuration
            if not preview.rules:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="At least one targeting rule is required for preview",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Generate preview
            payload = self.repository.preview(
                preview=preview,
                max_preview=max_preview
            )
            
            return ServiceResult.success(
                data=payload,
                message="Targeting preview generated successfully",
                metadata={
                    "total_matched": payload.get("total_matched", 0),
                    "preview_size": len(payload.get("preview_recipients", [])),
                    "rules_count": len(preview.rules),
                }
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(
                e, "preview targeting", preview.hostel_id
            )
            
        except ValueError as e:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid preview configuration: {str(e)}",
                    severity=ErrorSeverity.WARNING,
                )
            )
            
        except Exception as e:
            return self._handle_exception(e, "preview targeting", preview.hostel_id)

    def compute_summary(
        self,
        announcement_id: UUID,
    ) -> ServiceResult[TargetingSummary]:
        """
        Compute targeting summary from current audience cache and rules.
        
        Args:
            announcement_id: Unique identifier of announcement
            
        Returns:
            ServiceResult containing TargetingSummary or error
            
        Notes:
            - Reads from cached audience data
            - Includes breakdown by targeting type
            - Reflects current state without recomputation
        """
        try:
            summary = self.repository.get_targeting_summary(announcement_id)
            
            if not summary:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No targeting configuration found for announcement {announcement_id}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            return ServiceResult.success(
                data=summary,
                message="Targeting summary computed successfully",
                metadata={
                    "total_recipients": summary.total_recipients,
                    "targeting_types": summary.breakdown_by_type if hasattr(summary, 'breakdown_by_type') else {},
                }
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(
                e, "compute targeting summary", announcement_id
            )
            
        except Exception as e:
            return self._handle_exception(
                e, "compute targeting summary", announcement_id
            )

    def update_targeting(
        self,
        announcement_id: UUID,
        rules: List[TargetingConfig],
        combine_mode: str = "union",
        global_exclusions: Optional[List[UUID]] = None,
    ) -> ServiceResult[TargetingSummary]:
        """
        Update existing targeting configuration.
        
        Args:
            announcement_id: Unique identifier of announcement
            rules: Updated targeting rules
            combine_mode: How to combine rules
            global_exclusions: Updated exclusion list
            
        Returns:
            ServiceResult containing updated TargetingSummary or error
            
        Notes:
            - Replaces existing targeting completely
            - Use for modifying audience after initial setup
        """
        try:
            # Verify announcement exists
            announcement_exists = self.repository.announcement_exists(announcement_id)
            if not announcement_exists:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Announcement {announcement_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Apply updated targeting (reuses apply_targeting logic)
            return self.apply_targeting(
                announcement_id=announcement_id,
                rules=rules,
                combine_mode=combine_mode,
                global_exclusions=global_exclusions,
            )
            
        except Exception as e:
            return self._handle_exception(e, "update targeting", announcement_id)

    def clear_targeting(
        self,
        announcement_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Remove all targeting rules and clear audience cache.
        
        Args:
            announcement_id: Unique identifier of announcement
            
        Returns:
            ServiceResult containing success boolean or error
            
        Notes:
            - Removes all targeting configurations
            - Clears cached audience
            - Useful for resetting announcement audience
        """
        try:
            self.repository.clear_targeting(announcement_id)
            self.db.commit()
            
            return ServiceResult.success(
                data=True,
                message="Targeting cleared successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(
                e, "clear targeting", announcement_id
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "clear targeting", announcement_id)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _validate_targeting_rules(
        self,
        rules: List[TargetingConfig]
    ) -> ServiceResult:
        """
        Validate targeting rule configurations.
        
        Args:
            rules: List of targeting configurations
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        for idx, rule in enumerate(rules):
            # Validate rule has required fields
            if not hasattr(rule, 'target_type'):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Rule {idx + 1}: target_type is required",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Additional rule-specific validations can be added here
            
        return ServiceResult.success(True)

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