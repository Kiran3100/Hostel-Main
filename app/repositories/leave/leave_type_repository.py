"""
Leave Type Repository

Comprehensive leave type configuration and policy management with
blackout dates, validation, and policy versioning.
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from app.models.leave.leave_type import (
    LeaveTypeConfig,
    LeavePolicy,
    LeaveBlackoutDate,
)
from app.models.common.enums import LeaveType
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginatedResult


class LeaveTypeRepository(BaseRepository[LeaveTypeConfig]):
    """
    Leave type configuration repository.
    
    Features:
    - Leave type configuration management
    - Policy document management
    - Blackout date management
    - Validation and rules
    - Configuration versioning
    """

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        super().__init__(session, LeaveTypeConfig)

    # ============================================================================
    # CONFIGURATION MANAGEMENT
    # ============================================================================

    def get_leave_type_config(
        self,
        leave_type: LeaveType,
        hostel_id: Optional[UUID] = None
    ) -> Optional[LeaveTypeConfig]:
        """
        Get leave type configuration.
        
        Args:
            leave_type: Leave type
            hostel_id: Optional hostel ID (None for global)
            
        Returns:
            Leave type configuration or None
        """
        now = datetime.utcnow()
        
        query = self.session.query(LeaveTypeConfig).filter(
            LeaveTypeConfig.leave_type == leave_type,
            LeaveTypeConfig.is_active == True,
            LeaveTypeConfig.deleted_at.is_(None)
        )
        
        # First try to get hostel-specific config
        if hostel_id:
            hostel_config = query.filter(
                LeaveTypeConfig.hostel_id == hostel_id,
                or_(
                    LeaveTypeConfig.effective_from.is_(None),
                    LeaveTypeConfig.effective_from <= now
                ),
                or_(
                    LeaveTypeConfig.effective_to.is_(None),
                    LeaveTypeConfig.effective_to >= now
                )
            ).first()
            
            if hostel_config:
                return hostel_config
        
        # Fall back to global config
        return query.filter(
            LeaveTypeConfig.hostel_id.is_(None),
            or_(
                LeaveTypeConfig.effective_from.is_(None),
                LeaveTypeConfig.effective_from <= now
            ),
            or_(
                LeaveTypeConfig.effective_to.is_(None),
                LeaveTypeConfig.effective_to >= now
            )
        ).first()

    def get_all_active_configs(
        self,
        hostel_id: Optional[UUID] = None,
        visible_to_students_only: bool = False
    ) -> List[LeaveTypeConfig]:
        """
        Get all active leave type configurations.
        
        Args:
            hostel_id: Optional hostel filter
            visible_to_students_only: Only student-visible types
            
        Returns:
            List of configurations
        """
        now = datetime.utcnow()
        
        query = self.session.query(LeaveTypeConfig).filter(
            LeaveTypeConfig.is_active == True,
            LeaveTypeConfig.deleted_at.is_(None),
            or_(
                LeaveTypeConfig.effective_from.is_(None),
                LeaveTypeConfig.effective_from <= now
            ),
            or_(
                LeaveTypeConfig.effective_to.is_(None),
                LeaveTypeConfig.effective_to >= now
            )
        )
        
        if hostel_id:
            query = query.filter(
                or_(
                    LeaveTypeConfig.hostel_id == hostel_id,
                    LeaveTypeConfig.hostel_id.is_(None)
                )
            )
        
        if visible_to_students_only:
            query = query.filter(LeaveTypeConfig.is_visible_to_students == True)
        
        return query.order_by(LeaveTypeConfig.display_order).all()

    def create_leave_type_config(
        self,
        leave_type: LeaveType,
        config_data: Dict[str, Any],
        hostel_id: Optional[UUID] = None
    ) -> LeaveTypeConfig:
        """
        Create leave type configuration.
        
        Args:
            leave_type: Leave type
            config_data: Configuration details
            hostel_id: Optional hostel ID
            
        Returns:
            Created configuration
        """
        config = LeaveTypeConfig(
            leave_type=leave_type,
            hostel_id=hostel_id,
            **config_data
        )
        
        self.session.add(config)
        self.session.flush()
        
        return config

    def update_leave_type_config(
        self,
        config_id: UUID,
        update_data: Dict[str, Any]
    ) -> Optional[LeaveTypeConfig]:
        """
        Update leave type configuration.
        
        Args:
            config_id: Configuration ID
            update_data: Fields to update
            
        Returns:
            Updated configuration or None
        """
        config = self.find_by_id(config_id)
        if not config:
            return None
        
        for key, value in update_data.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        self.session.flush()
        return config

    def deactivate_config(
        self,
        config_id: UUID
    ) -> Optional[LeaveTypeConfig]:
        """
        Deactivate leave type configuration.
        
        Args:
            config_id: Configuration ID
            
        Returns:
            Updated configuration or None
        """
        config = self.find_by_id(config_id)
        if not config:
            return None
        
        config.is_active = False
        config.effective_to = datetime.utcnow()
        
        self.session.flush()
        return config

    # ============================================================================
    # VALIDATION AND RULES
    # ============================================================================

    def validate_leave_application(
        self,
        leave_type: LeaveType,
        hostel_id: UUID,
        application_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate leave application against configuration rules.
        
        Args:
            leave_type: Leave type
            hostel_id: Hostel ID
            application_data: Application details
            
        Returns:
            Validation result
        """
        config = self.get_leave_type_config(leave_type, hostel_id)
        
        if not config:
            return {
                'is_valid': False,
                'errors': ['Leave type not configured for this hostel']
            }
        
        errors = []
        warnings = []
        
        # Check if visible to students
        if not config.is_visible_to_students:
            errors.append('This leave type is not available for student applications')
        
        # Validate total days
        total_days = application_data.get('total_days', 0)
        
        if total_days < config.min_days_per_application:
            errors.append(f'Minimum {config.min_days_per_application} days required')
        
        if config.max_consecutive_days and total_days > config.max_consecutive_days:
            errors.append(f'Maximum {config.max_consecutive_days} consecutive days allowed')
        
        # Validate advance notice
        from_date = application_data.get('from_date')
        if from_date and isinstance(from_date, date):
            days_notice = (from_date - date.today()).days
            
            if days_notice < 0:  # Backdated
                if not config.allow_backdated_application:
                    errors.append('Backdated applications not allowed for this leave type')
                elif abs(days_notice) > config.max_backdated_days:
                    errors.append(f'Cannot apply for leaves more than {config.max_backdated_days} days in the past')
            elif days_notice < config.min_notice_days:
                errors.append(f'Minimum {config.min_notice_days} days advance notice required')
            elif days_notice > config.max_advance_days:
                errors.append(f'Cannot apply more than {config.max_advance_days} days in advance')
        
        # Check document requirements
        has_document = application_data.get('supporting_document_url') is not None
        
        if config.requires_document and not has_document:
            errors.append('Supporting document is mandatory for this leave type')
        elif config.requires_document_after_days and total_days > config.requires_document_after_days:
            if not has_document:
                errors.append(f'Document required for leaves longer than {config.requires_document_after_days} days')
        
        # Check contact requirements
        if config.requires_contact_info and not application_data.get('contact_during_leave'):
            errors.append('Contact information during leave is required')
        
        if config.requires_emergency_contact and not application_data.get('emergency_contact'):
            errors.append('Emergency contact is required')
        
        if config.requires_destination and not application_data.get('destination_address'):
            errors.append('Destination address is required')
        
        # Check blackout dates
        if from_date and application_data.get('to_date'):
            blackout_conflicts = self.check_blackout_dates(
                config.id,
                from_date,
                application_data['to_date']
            )
            
            for blackout in blackout_conflicts:
                if blackout.is_complete_blackout:
                    errors.append(
                        f'Leave not allowed during {blackout.blackout_name} '
                        f'({blackout.blackout_start_date.date()} to {blackout.blackout_end_date.date()})'
                    )
                elif blackout.allow_with_special_approval:
                    warnings.append(
                        f'Special approval required for {blackout.blackout_name} period'
                    )
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'requires_approval': config.requires_approval,
            'can_auto_approve': self._check_auto_approval(config, application_data),
            'config': {
                'display_name': config.display_name,
                'description': config.description,
                'help_text': config.application_help_text
            }
        }

    def _check_auto_approval(
        self,
        config: LeaveTypeConfig,
        application_data: Dict[str, Any]
    ) -> bool:
        """
        Check if application can be auto-approved.
        
        Args:
            config: Leave type configuration
            application_data: Application details
            
        Returns:
            True if can auto-approve
        """
        if not config.auto_approve_enabled:
            return False
        
        total_days = application_data.get('total_days', 0)
        
        if config.auto_approve_upto_days and total_days <= config.auto_approve_upto_days:
            return True
        
        # Could check custom conditions here
        # if config.auto_approve_conditions:
        #     # Parse and evaluate JSON conditions
        #     pass
        
        return False

    def check_blackout_dates(
        self,
        config_id: UUID,
        from_date: date,
        to_date: date
    ) -> List[LeaveBlackoutDate]:
        """
        Check for blackout date conflicts.
        
        Args:
            config_id: Configuration ID
            from_date: Leave start date
            to_date: Leave end date
            
        Returns:
            List of conflicting blackout dates
        """
        now = datetime.utcnow()
        
        # Convert dates to datetime for comparison
        from_datetime = datetime.combine(from_date, datetime.min.time())
        to_datetime = datetime.combine(to_date, datetime.max.time())
        
        return self.session.query(LeaveBlackoutDate).filter(
            LeaveBlackoutDate.leave_type_config_id == config_id,
            LeaveBlackoutDate.is_active == True,
            or_(
                and_(
                    LeaveBlackoutDate.blackout_start_date <= to_datetime,
                    LeaveBlackoutDate.blackout_end_date >= from_datetime
                )
            )
        ).all()

    # ============================================================================
    # BLACKOUT DATE MANAGEMENT
    # ============================================================================

    def create_blackout_date(
        self,
        config_id: UUID,
        blackout_data: Dict[str, Any]
    ) -> LeaveBlackoutDate:
        """
        Create blackout date period.
        
        Args:
            config_id: Configuration ID
            blackout_data: Blackout details
            
        Returns:
            Created blackout date
        """
        blackout = LeaveBlackoutDate(
            leave_type_config_id=config_id,
            **blackout_data
        )
        
        self.session.add(blackout)
        self.session.flush()
        
        return blackout

    def update_blackout_date(
        self,
        blackout_id: UUID,
        update_data: Dict[str, Any]
    ) -> Optional[LeaveBlackoutDate]:
        """
        Update blackout date.
        
        Args:
            blackout_id: Blackout ID
            update_data: Fields to update
            
        Returns:
            Updated blackout or None
        """
        blackout = self.session.query(LeaveBlackoutDate).filter(
            LeaveBlackoutDate.id == blackout_id
        ).first()
        
        if not blackout:
            return None
        
        for key, value in update_data.items():
            if hasattr(blackout, key):
                setattr(blackout, key, value)
        
        self.session.flush()
        return blackout

    def get_blackout_dates(
        self,
        config_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        active_only: bool = True
    ) -> List[LeaveBlackoutDate]:
        """
        Get blackout dates for configuration.
        
        Args:
            config_id: Configuration ID
            from_date: Optional start date filter
            to_date: Optional end date filter
            active_only: Return only active blackouts
            
        Returns:
            List of blackout dates
        """
        query = self.session.query(LeaveBlackoutDate).filter(
            LeaveBlackoutDate.leave_type_config_id == config_id
        )
        
        if active_only:
            query = query.filter(LeaveBlackoutDate.is_active == True)
        
        if from_date:
            query = query.filter(LeaveBlackoutDate.blackout_end_date >= from_date)
        
        if to_date:
            query = query.filter(LeaveBlackoutDate.blackout_start_date <= to_date)
        
        return query.order_by(LeaveBlackoutDate.blackout_start_date).all()

    def get_upcoming_blackout_dates(
        self,
        config_id: UUID,
        days_ahead: int = 30
    ) -> List[LeaveBlackoutDate]:
        """
        Get upcoming blackout dates.
        
        Args:
            config_id: Configuration ID
            days_ahead: Number of days to look ahead
            
        Returns:
            List of upcoming blackout dates
        """
        now = datetime.utcnow()
        future_date = now + timedelta(days=days_ahead)
        
        return self.session.query(LeaveBlackoutDate).filter(
            LeaveBlackoutDate.leave_type_config_id == config_id,
            LeaveBlackoutDate.is_active == True,
            LeaveBlackoutDate.blackout_start_date >= now,
            LeaveBlackoutDate.blackout_start_date <= future_date
        ).order_by(LeaveBlackoutDate.blackout_start_date).all()

    def deactivate_blackout_date(
        self,
        blackout_id: UUID
    ) -> Optional[LeaveBlackoutDate]:
        """
        Deactivate blackout date.
        
        Args:
            blackout_id: Blackout ID
            
        Returns:
            Updated blackout or None
        """
        blackout = self.session.query(LeaveBlackoutDate).filter(
            LeaveBlackoutDate.id == blackout_id
        ).first()
        
        if not blackout:
            return None
        
        blackout.is_active = False
        
        self.session.flush()
        return blackout

    # ============================================================================
    # POLICY MANAGEMENT
    # ============================================================================

    def create_policy(
        self,
        policy_data: Dict[str, Any],
        hostel_id: Optional[UUID] = None
    ) -> LeavePolicy:
        """
        Create leave policy document.
        
        Args:
            policy_data: Policy details
            hostel_id: Optional hostel ID
            
        Returns:
            Created policy
        """
        policy = LeavePolicy(
            hostel_id=hostel_id,
            **policy_data
        )
        
        self.session.add(policy)
        self.session.flush()
        
        return policy

    def update_policy(
        self,
        policy_id: UUID,
        update_data: Dict[str, Any]
    ) -> Optional[LeavePolicy]:
        """
        Update leave policy.
        
        Args:
            policy_id: Policy ID
            update_data: Fields to update
            
        Returns:
            Updated policy or None
        """
        policy = self.session.query(LeavePolicy).filter(
            LeavePolicy.id == policy_id
        ).first()
        
        if not policy:
            return None
        
        for key, value in update_data.items():
            if hasattr(policy, key):
                setattr(policy, key, value)
        
        self.session.flush()
        return policy

    def get_policy(
        self,
        policy_code: str,
        hostel_id: Optional[UUID] = None
    ) -> Optional[LeavePolicy]:
        """
        Get policy by code.
        
        Args:
            policy_code: Policy code
            hostel_id: Optional hostel filter
            
        Returns:
            Policy or None
        """
        query = self.session.query(LeavePolicy).filter(
            LeavePolicy.policy_code == policy_code,
            LeavePolicy.is_active == True
        )
        
        if hostel_id:
            query = query.filter(
                or_(
                    LeavePolicy.hostel_id == hostel_id,
                    LeavePolicy.hostel_id.is_(None)
                )
            )
        
        now = datetime.utcnow()
        return query.filter(
            LeavePolicy.effective_from <= now,
            or_(
                LeavePolicy.effective_to.is_(None),
                LeavePolicy.effective_to >= now
            )
        ).first()

    def get_active_policies(
        self,
        hostel_id: Optional[UUID] = None,
        leave_types: Optional[List[str]] = None
    ) -> List[LeavePolicy]:
        """
        Get all active policies.
        
        Args:
            hostel_id: Optional hostel filter
            leave_types: Optional leave type filter
            
        Returns:
            List of active policies
        """
        now = datetime.utcnow()
        
        query = self.session.query(LeavePolicy).filter(
            LeavePolicy.is_active == True,
            LeavePolicy.effective_from <= now,
            or_(
                LeavePolicy.effective_to.is_(None),
                LeavePolicy.effective_to >= now
            )
        )
        
        if hostel_id:
            query = query.filter(
                or_(
                    LeavePolicy.hostel_id == hostel_id,
                    LeavePolicy.hostel_id.is_(None)
                )
            )
        
        if leave_types:
            # Check if policy applies to any of the specified leave types
            query = query.filter(
                or_(
                    LeavePolicy.applies_to_leave_types.is_(None),
                    LeavePolicy.applies_to_leave_types.op('?|')(leave_types)
                )
            )
        
        return query.all()

    def create_policy_version(
        self,
        previous_policy_id: UUID,
        new_version_data: Dict[str, Any]
    ) -> LeavePolicy:
        """
        Create new version of policy.
        
        Args:
            previous_policy_id: ID of previous version
            new_version_data: New version details
            
        Returns:
            Created policy version
        """
        previous_policy = self.session.query(LeavePolicy).filter(
            LeavePolicy.id == previous_policy_id
        ).first()
        
        if not previous_policy:
            raise ValueError("Previous policy not found")
        
        # Deactivate previous version
        previous_policy.is_active = False
        previous_policy.effective_to = datetime.utcnow()
        
        # Create new version
        new_policy = LeavePolicy(
            policy_code=previous_policy.policy_code,
            hostel_id=previous_policy.hostel_id,
            previous_version_id=previous_policy_id,
            **new_version_data
        )
        
        self.session.add(new_policy)
        self.session.flush()
        
        return new_policy

    def get_policy_versions(
        self,
        policy_code: str
    ) -> List[LeavePolicy]:
        """
        Get all versions of a policy.
        
        Args:
            policy_code: Policy code
            
        Returns:
            List of policy versions ordered by version
        """
        return self.session.query(LeavePolicy).filter(
            LeavePolicy.policy_code == policy_code
        ).order_by(LeavePolicy.version.desc()).all()

    def publish_policy(
        self,
        policy_id: UUID,
        published_by: UUID
    ) -> Optional[LeavePolicy]:
        """
        Publish policy.
        
        Args:
            policy_id: Policy ID
            published_by: User publishing
            
        Returns:
            Published policy or None
        """
        policy = self.session.query(LeavePolicy).filter(
            LeavePolicy.id == policy_id
        ).first()
        
        if not policy:
            return None
        
        policy.published_at = datetime.utcnow()
        policy.published_by = published_by
        
        self.session.flush()
        return policy

    def approve_policy(
        self,
        policy_id: UUID,
        approved_by: UUID
    ) -> Optional[LeavePolicy]:
        """
        Approve policy.
        
        Args:
            policy_id: Policy ID
            approved_by: User approving
            
        Returns:
            Approved policy or None
        """
        policy = self.session.query(LeavePolicy).filter(
            LeavePolicy.id == policy_id
        ).first()
        
        if not policy:
            return None
        
        policy.approved_at = datetime.utcnow()
        policy.approved_by = approved_by
        
        self.session.flush()
        return policy

    # ============================================================================
    # REPORTING AND ANALYTICS
    # ============================================================================

    def get_config_usage_statistics(
        self,
        config_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get usage statistics for configuration.
        
        Args:
            config_id: Configuration ID
            from_date: Optional start date
            to_date: Optional end date
            
        Returns:
            Usage statistics
        """
        from app.models.leave.leave_application import LeaveApplication
        from app.models.common.enums import LeaveStatus
        
        config = self.find_by_id(config_id)
        if not config:
            return {}
        
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.leave_type == config.leave_type,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if config.hostel_id:
            query = query.filter(LeaveApplication.hostel_id == config.hostel_id)
        
        if from_date:
            query = query.filter(LeaveApplication.applied_at >= from_date)
        
        if to_date:
            query = query.filter(LeaveApplication.applied_at <= to_date)
        
        total_applications = query.count()
        approved = query.filter(LeaveApplication.status == LeaveStatus.APPROVED).count()
        rejected = query.filter(LeaveApplication.status == LeaveStatus.REJECTED).count()
        pending = query.filter(LeaveApplication.status == LeaveStatus.PENDING).count()
        
        # Average days requested
        avg_days = query.with_entities(
            func.avg(LeaveApplication.total_days)
        ).scalar() or 0
        
        # Document compliance
        with_document = query.filter(
            LeaveApplication.supporting_document_url.isnot(None)
        ).count()
        
        return {
            'leave_type': config.leave_type.value,
            'display_name': config.display_name,
            'total_applications': total_applications,
            'approved': approved,
            'rejected': rejected,
            'pending': pending,
            'approval_rate': round((approved / total_applications * 100) if total_applications else 0, 2),
            'average_days_requested': round(float(avg_days), 2),
            'document_compliance_rate': round((with_document / total_applications * 100) if total_applications else 0, 2),
            'requires_document': config.requires_document
        }

    def get_hostel_leave_type_summary(
        self,
        hostel_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get summary of all leave types for hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            List of leave type summaries
        """
        configs = self.get_all_active_configs(hostel_id, visible_to_students_only=False)
        
        summaries = []
        for config in configs:
            stats = self.get_config_usage_statistics(config.id)
            summaries.append({
                'config_id': str(config.id),
                'leave_type': config.leave_type.value,
                'display_name': config.display_name,
                'max_days_per_year': config.max_days_per_year,
                'max_consecutive_days': config.max_consecutive_days,
                'requires_approval': config.requires_approval,
                'auto_approve_enabled': config.auto_approve_enabled,
                'is_visible_to_students': config.is_visible_to_students,
                **stats
            })
        
        return summaries


class LeavePolicyRepository(BaseRepository[LeavePolicy]):
    """
    Leave policy document repository.
    
    Simplified repository for direct policy operations.
    """

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        super().__init__(session, LeavePolicy)

    def find_by_code(
        self,
        policy_code: str,
        version: Optional[str] = None
    ) -> Optional[LeavePolicy]:
        """
        Find policy by code and optional version.
        
        Args:
            policy_code: Policy code
            version: Optional version
            
        Returns:
            Policy or None
        """
        query = self.session.query(LeavePolicy).filter(
            LeavePolicy.policy_code == policy_code
        )
        
        if version:
            query = query.filter(LeavePolicy.version == version)
        else:
            query = query.filter(LeavePolicy.is_active == True)
        
        return query.first()


class LeaveBlackoutDateRepository(BaseRepository[LeaveBlackoutDate]):
    """
    Leave blackout date repository.
    
    Simplified repository for direct blackout operations.
    """

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        super().__init__(session, LeaveBlackoutDate)

    def find_active_blackouts(
        self,
        config_id: UUID,
        check_date: Optional[date] = None
    ) -> List[LeaveBlackoutDate]:
        """
        Find active blackouts for a date.
        
        Args:
            config_id: Configuration ID
            check_date: Date to check (default: today)
            
        Returns:
            List of active blackouts
        """
        if check_date is None:
            check_date = date.today()
        
        check_datetime = datetime.combine(check_date, datetime.min.time())
        
        return self.session.query(LeaveBlackoutDate).filter(
            LeaveBlackoutDate.leave_type_config_id == config_id,
            LeaveBlackoutDate.is_active == True,
            LeaveBlackoutDate.blackout_start_date <= check_datetime,
            LeaveBlackoutDate.blackout_end_date >= check_datetime
        ).all()