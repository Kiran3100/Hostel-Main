# --- File: C:\Hostel-Main\app\services\hostel\hostel_onboarding_service.py ---
"""
Hostel onboarding service.

Orchestrates the complete onboarding process for new hostels including
initial setup, default configuration, seed data, and validation workflows.
"""

from typing import Optional, Dict, Any, List, Callable
from uuid import UUID
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.services.base import (
    ServiceResult,
    BaseService,
    ServiceError,
    ErrorCode,
    ErrorSeverity
)
from app.repositories.hostel import (
    HostelAggregateRepository,
    HostelRepository,
    HostelSettingsRepository,
    HostelPolicyRepository,
    HostelAmenityRepository,
)
from app.models.hostel.hostel import Hostel as HostelModel
from app.schemas.hostel.hostel_base import HostelCreate
from app.schemas.hostel.hostel_admin import HostelSettings as HostelSettingsSchema
from app.schemas.hostel.hostel_policy import PolicyCreate
from app.schemas.hostel.hostel_amenity import AmenityCreate
from app.services.hostel.constants import SUCCESS_ONBOARDING_COMPLETED

logger = logging.getLogger(__name__)


class OnboardingStep:
    """Represents a single step in the onboarding process."""
    
    def __init__(
        self,
        name: str,
        handler: Callable,
        required: bool = True,
        rollback_handler: Optional[Callable] = None
    ):
        """
        Initialize onboarding step.
        
        Args:
            name: Step name/identifier
            handler: Function to execute for this step
            required: Whether step is required for successful onboarding
            rollback_handler: Optional cleanup function if step fails
        """
        self.name = name
        self.handler = handler
        self.required = required
        self.rollback_handler = rollback_handler
        self.status = 'pending'
        self.error = None
        self.result = None


class HostelOnboardingService(BaseService[HostelModel, HostelAggregateRepository]):
    """
    Orchestrate initial setup of a hostel with sensible defaults.
    
    Provides functionality for:
    - Multi-step onboarding workflow
    - Default configuration seeding
    - Validation at each step
    - Rollback capability
    - Progress tracking
    - Post-onboarding verification
    """

    # Default amenity categories and items
    DEFAULT_AMENITIES = {
        'basic': [
            {'name': 'WiFi', 'description': 'Free high-speed internet', 'is_free': True},
            {'name': 'Bed Linens', 'description': 'Clean bed sheets and pillows', 'is_free': True},
            {'name': 'Lockers', 'description': 'Personal storage lockers', 'is_free': True},
        ],
        'common_areas': [
            {'name': 'Common Kitchen', 'description': 'Shared cooking facilities', 'is_free': True},
            {'name': 'Lounge Area', 'description': 'Common relaxation space', 'is_free': True},
        ],
        'services': [
            {'name': 'Laundry', 'description': 'Washing machines available', 'is_free': False},
            {'name': 'Breakfast', 'description': 'Daily breakfast service', 'is_free': False},
        ]
    }

    # Default policy templates
    DEFAULT_POLICIES = [
        {
            'title': 'House Rules',
            'policy_type': 'house_rules',
            'content': 'Standard house rules for guest conduct and facility usage.',
            'is_mandatory': True,
        },
        {
            'title': 'Cancellation Policy',
            'policy_type': 'cancellation_policy',
            'content': 'Standard cancellation and refund policy.',
            'is_mandatory': True,
        },
        {
            'title': 'Privacy Policy',
            'policy_type': 'privacy_policy',
            'content': 'How we collect, use, and protect guest information.',
            'is_mandatory': True,
        },
    ]

    def __init__(
        self,
        aggregate_repo: HostelAggregateRepository,
        hostel_repo: HostelRepository,
        settings_repo: HostelSettingsRepository,
        policy_repo: HostelPolicyRepository,
        amenity_repo: HostelAmenityRepository,
        db_session: Session,
    ):
        """
        Initialize hostel onboarding service.
        
        Args:
            aggregate_repo: Aggregate repository for hostel data
            hostel_repo: Hostel repository
            settings_repo: Settings repository
            policy_repo: Policy repository
            amenity_repo: Amenity repository
            db_session: Database session
        """
        super().__init__(aggregate_repo, db_session)
        self.hostel_repo = hostel_repo
        self.settings_repo = settings_repo
        self.policy_repo = policy_repo
        self.amenity_repo = amenity_repo
        self._onboarding_steps: List[OnboardingStep] = []
        self._current_hostel_id: Optional[UUID] = None

    # =========================================================================
    # Main Onboarding Operations
    # =========================================================================

    def onboard(
        self,
        hostel_request: HostelCreate,
        settings: Optional[HostelSettingsSchema] = None,
        default_policies: Optional[List[PolicyCreate]] = None,
        default_amenities: Optional[List[AmenityCreate]] = None,
        created_by: Optional[UUID] = None,
        skip_defaults: bool = False,
        validate_each_step: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Create hostel and seed defaults in a comprehensive onboarding flow.
        
        Args:
            hostel_request: Hostel creation request
            settings: Optional custom settings (uses defaults if not provided)
            default_policies: Optional custom policies (uses defaults if not provided)
            default_amenities: Optional custom amenities (uses defaults if not provided)
            created_by: UUID of the user creating the hostel
            skip_defaults: Skip seeding default data
            validate_each_step: Validate after each onboarding step
            
        Returns:
            ServiceResult containing onboarding summary or error
        """
        try:
            logger.info(f"Starting hostel onboarding: {hostel_request.name}")
            
            # Initialize onboarding workflow
            self._initialize_workflow(
                hostel_request,
                settings,
                default_policies,
                default_amenities,
                created_by,
                skip_defaults
            )
            
            # Execute onboarding steps
            onboarding_result = self._execute_onboarding_workflow(
                validate_each_step
            )
            
            if not onboarding_result['success']:
                # Rollback on failure
                self._rollback_onboarding()
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Onboarding failed",
                        severity=ErrorSeverity.ERROR,
                        details=onboarding_result
                    )
                )
            
            # Commit all changes
            self.db.commit()
            
            # Post-onboarding verification
            verification_result = self._verify_onboarding()
            
            # Prepare response
            response = {
                "hostel_id": str(self._current_hostel_id),
                "onboarding_steps": onboarding_result['steps'],
                "verification": verification_result,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            logger.info(f"Hostel onboarded successfully: {self._current_hostel_id}")
            return ServiceResult.success(
                response,
                message=SUCCESS_ONBOARDING_COMPLETED
            )
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error during onboarding: {str(e)}")
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Hostel with this identifier already exists",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)}
                )
            )
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "onboard hostel")

    def onboard_with_progress(
        self,
        hostel_request: HostelCreate,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        **kwargs
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Onboard hostel with progress tracking callback.
        
        Args:
            hostel_request: Hostel creation request
            progress_callback: Callback function(step_name, current, total)
            **kwargs: Additional arguments passed to onboard()
            
        Returns:
            ServiceResult containing onboarding summary
        """
        try:
            # Set up progress tracking
            self._progress_callback = progress_callback
            
            # Execute standard onboarding
            result = self.onboard(hostel_request, **kwargs)
            
            # Clear callback
            self._progress_callback = None
            
            return result
            
        except Exception as e:
            self._progress_callback = None
            return self._handle_exception(e, "onboard with progress")

    def quick_onboard(
        self,
        hostel_request: HostelCreate,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Quick onboarding with minimal default setup.
        
        Args:
            hostel_request: Hostel creation request
            created_by: UUID of the user creating the hostel
            
        Returns:
            ServiceResult containing onboarding summary
        """
        try:
            logger.info(f"Quick onboarding hostel: {hostel_request.name}")
            
            # Create hostel only
            hostel = self.hostel_repo.create_hostel(hostel_request, created_by=created_by)
            self.db.flush()
            
            # Create minimal default settings
            default_settings = self._get_minimal_settings()
            self.settings_repo.update_settings(
                hostel.id,
                default_settings,
                updated_by=created_by
            )
            self.db.flush()
            
            self.db.commit()
            
            response = {
                "hostel_id": str(hostel.id),
                "mode": "quick",
                "settings_seeded": True,
                "policies_seeded": 0,
                "amenities_seeded": 0,
            }
            
            return ServiceResult.success(
                response,
                message="Quick onboarding completed"
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "quick onboard hostel")

    # =========================================================================
    # Onboarding Workflow Management
    # =========================================================================

    def _initialize_workflow(
        self,
        hostel_request: HostelCreate,
        settings: Optional[HostelSettingsSchema],
        policies: Optional[List[PolicyCreate]],
        amenities: Optional[List[AmenityCreate]],
        created_by: Optional[UUID],
        skip_defaults: bool
    ) -> None:
        """Initialize the onboarding workflow with steps."""
        self._onboarding_steps = []
        
        # Step 1: Create hostel
        self._onboarding_steps.append(
            OnboardingStep(
                name='create_hostel',
                handler=lambda: self._step_create_hostel(hostel_request, created_by),
                required=True,
                rollback_handler=lambda: self._rollback_hostel_creation()
            )
        )
        
        # Step 2: Seed settings
        if not skip_defaults or settings:
            self._onboarding_steps.append(
                OnboardingStep(
                    name='seed_settings',
                    handler=lambda: self._step_seed_settings(settings, created_by),
                    required=False,
                    rollback_handler=lambda: self._rollback_settings()
                )
            )
        
        # Step 3: Seed policies
        if not skip_defaults or policies:
            policies_to_create = policies or self._get_default_policies(hostel_request)
            self._onboarding_steps.append(
                OnboardingStep(
                    name='seed_policies',
                    handler=lambda: self._step_seed_policies(policies_to_create, created_by),
                    required=False,
                    rollback_handler=lambda: self._rollback_policies()
                )
            )
        
        # Step 4: Seed amenities
        if not skip_defaults or amenities:
            amenities_to_create = amenities or self._get_default_amenities(hostel_request)
            self._onboarding_steps.append(
                OnboardingStep(
                    name='seed_amenities',
                    handler=lambda: self._step_seed_amenities(amenities_to_create, created_by),
                    required=False,
                    rollback_handler=lambda: self._rollback_amenities()
                )
            )
        
        # Step 5: Initialize analytics
        self._onboarding_steps.append(
            OnboardingStep(
                name='initialize_analytics',
                handler=lambda: self._step_initialize_analytics(),
                required=False
            )
        )
        
        # Step 6: Set initial status
        self._onboarding_steps.append(
            OnboardingStep(
                name='set_initial_status',
                handler=lambda: self._step_set_initial_status(),
                required=True
            )
        )

    def _execute_onboarding_workflow(
        self,
        validate_each_step: bool
    ) -> Dict[str, Any]:
        """Execute all onboarding steps in sequence."""
        total_steps = len(self._onboarding_steps)
        completed_steps = []
        failed_steps = []
        
        for idx, step in enumerate(self._onboarding_steps, 1):
            try:
                logger.info(f"Executing onboarding step {idx}/{total_steps}: {step.name}")
                
                # Report progress
                if hasattr(self, '_progress_callback') and self._progress_callback:
                    self._progress_callback(step.name, idx, total_steps)
                
                # Execute step
                step.result = step.handler()
                step.status = 'completed'
                
                # Validate if required
                if validate_each_step:
                    validation_result = self._validate_step(step)
                    if not validation_result['valid']:
                        raise Exception(f"Step validation failed: {validation_result['error']}")
                
                completed_steps.append({
                    'name': step.name,
                    'status': 'completed',
                    'result': step.result
                })
                
                logger.info(f"Step {step.name} completed successfully")
                
            except Exception as e:
                step.status = 'failed'
                step.error = str(e)
                
                failed_steps.append({
                    'name': step.name,
                    'status': 'failed',
                    'error': str(e)
                })
                
                logger.error(f"Step {step.name} failed: {str(e)}")
                
                # If required step fails, abort
                if step.required:
                    return {
                        'success': False,
                        'steps': completed_steps + failed_steps,
                        'failed_at': step.name,
                        'error': str(e)
                    }
        
        # Check if all required steps completed
        all_required_completed = all(
            step.status == 'completed'
            for step in self._onboarding_steps
            if step.required
        )
        
        return {
            'success': all_required_completed,
            'steps': completed_steps + failed_steps,
            'completed': len(completed_steps),
            'failed': len(failed_steps),
            'total': total_steps
        }

    def _rollback_onboarding(self) -> None:
        """Rollback onboarding steps in reverse order."""
        logger.warning("Rolling back onboarding steps")
        
        for step in reversed(self._onboarding_steps):
            if step.status == 'completed' and step.rollback_handler:
                try:
                    logger.info(f"Rolling back step: {step.name}")
                    step.rollback_handler()
                except Exception as e:
                    logger.error(f"Rollback failed for step {step.name}: {str(e)}")
        
        self.db.rollback()

    # =========================================================================
    # Individual Onboarding Steps
    # =========================================================================

    def _step_create_hostel(
        self,
        request: HostelCreate,
        created_by: Optional[UUID]
    ) -> Dict[str, Any]:
        """Step: Create the hostel record."""
        hostel = self.hostel_repo.create_hostel(request, created_by=created_by)
        self.db.flush()
        
        # Store hostel ID for subsequent steps
        self._current_hostel_id = hostel.id
        
        return {
            'hostel_id': str(hostel.id),
            'name': hostel.name,
            'created_at': hostel.created_at.isoformat() if hasattr(hostel, 'created_at') else None
        }

    def _step_seed_settings(
        self,
        settings: Optional[HostelSettingsSchema],
        created_by: Optional[UUID]
    ) -> Dict[str, Any]:
        """Step: Seed hostel settings."""
        if not self._current_hostel_id:
            raise Exception("Hostel ID not set")
        
        settings_to_apply = settings or self._get_default_settings()
        
        self.settings_repo.update_settings(
            self._current_hostel_id,
            settings_to_apply,
            updated_by=created_by
        )
        self.db.flush()
        
        return {
            'settings_applied': True,
            'custom_settings': settings is not None
        }

    def _step_seed_policies(
        self,
        policies: List[PolicyCreate],
        created_by: Optional[UUID]
    ) -> Dict[str, Any]:
        """Step: Seed hostel policies."""
        if not self._current_hostel_id:
            raise Exception("Hostel ID not set")
        
        created_policies = []
        
        for policy in policies:
            # Set hostel_id if not already set
            if not hasattr(policy, 'hostel_id') or not policy.hostel_id:
                policy.hostel_id = self._current_hostel_id
            
            created = self.policy_repo.create_policy(policy, created_by=created_by)
            created_policies.append(str(created.id))
            self.db.flush()
        
        return {
            'policies_created': len(created_policies),
            'policy_ids': created_policies
        }

    def _step_seed_amenities(
        self,
        amenities: List[AmenityCreate],
        created_by: Optional[UUID]
    ) -> Dict[str, Any]:
        """Step: Seed hostel amenities."""
        if not self._current_hostel_id:
            raise Exception("Hostel ID not set")
        
        created_amenities = []
        
        for amenity in amenities:
            # Set hostel_id if not already set
            if not hasattr(amenity, 'hostel_id') or not amenity.hostel_id:
                amenity.hostel_id = self._current_hostel_id
            
            created = self.amenity_repo.create_amenity(amenity, created_by=created_by)
            created_amenities.append(str(created.id))
            self.db.flush()
        
        return {
            'amenities_created': len(created_amenities),
            'amenity_ids': created_amenities
        }

    def _step_initialize_analytics(self) -> Dict[str, Any]:
        """Step: Initialize analytics tracking."""
        if not self._current_hostel_id:
            raise Exception("Hostel ID not set")
        
        # This is a placeholder for analytics initialization
        # Implement actual analytics setup as needed
        
        return {
            'analytics_initialized': True
        }

    def _step_set_initial_status(self) -> Dict[str, Any]:
        """Step: Set initial hostel status."""
        if not self._current_hostel_id:
            raise Exception("Hostel ID not set")
        
        hostel = self.hostel_repo.get_by_id(self._current_hostel_id)
        if hostel:
            # Set to 'pending_review' or 'draft' status
            hostel.status = 'pending_review'
            hostel.is_active = False  # Not active until reviewed
            self.db.flush()
        
        return {
            'status_set': True,
            'initial_status': 'pending_review'
        }

    # =========================================================================
    # Rollback Handlers
    # =========================================================================

    def _rollback_hostel_creation(self) -> None:
        """Rollback hostel creation."""
        if self._current_hostel_id:
            try:
                self.hostel_repo.delete(self._current_hostel_id)
                self.db.flush()
            except Exception as e:
                logger.error(f"Failed to rollback hostel creation: {str(e)}")

    def _rollback_settings(self) -> None:
        """Rollback settings creation."""
        # Settings are typically part of hostel, so cascade delete handles this
        pass

    def _rollback_policies(self) -> None:
        """Rollback policy creation."""
        if self._current_hostel_id:
            try:
                # Delete all policies for this hostel
                policies = self.policy_repo.list_policies(self._current_hostel_id, active_only=False)
                for policy in policies:
                    self.policy_repo.delete(policy.id)
                self.db.flush()
            except Exception as e:
                logger.error(f"Failed to rollback policies: {str(e)}")

    def _rollback_amenities(self) -> None:
        """Rollback amenity creation."""
        if self._current_hostel_id:
            try:
                # Delete all amenities for this hostel
                amenities = self.amenity_repo.list_amenities(self._current_hostel_id, active_only=False)
                for amenity in amenities:
                    self.amenity_repo.delete(amenity.id)
                self.db.flush()
            except Exception as e:
                logger.error(f"Failed to rollback amenities: {str(e)}")

    # =========================================================================
    # Validation & Verification
    # =========================================================================

    def _validate_step(self, step: OnboardingStep) -> Dict[str, Any]:
        """Validate a completed onboarding step."""
        validation_map = {
            'create_hostel': self._validate_hostel_creation,
            'seed_settings': self._validate_settings,
            'seed_policies': self._validate_policies,
            'seed_amenities': self._validate_amenities,
        }
        
        validator = validation_map.get(step.name)
        if validator:
            return validator(step.result)
        
        return {'valid': True}

    def _validate_hostel_creation(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate hostel was created correctly."""
        if not result.get('hostel_id'):
            return {'valid': False, 'error': 'Hostel ID not found'}
        
        # Verify hostel exists in database
        hostel = self.hostel_repo.get_by_id(UUID(result['hostel_id']))
        if not hostel:
            return {'valid': False, 'error': 'Hostel not found in database'}
        
        return {'valid': True}

    def _validate_settings(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings were applied."""
        if not result.get('settings_applied'):
            return {'valid': False, 'error': 'Settings not applied'}
        
        return {'valid': True}

    def _validate_policies(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate policies were created."""
        if result.get('policies_created', 0) == 0:
            return {'valid': False, 'error': 'No policies created'}
        
        return {'valid': True}

    def _validate_amenities(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate amenities were created."""
        # Amenities are optional, so this is just informational
        return {'valid': True}

    def _verify_onboarding(self) -> Dict[str, Any]:
        """Perform post-onboarding verification."""
        if not self._current_hostel_id:
            return {'verified': False, 'error': 'No hostel ID'}
        
        verification = {
            'verified': True,
            'checks': {}
        }
        
        # Check hostel exists
        hostel = self.hostel_repo.get_by_id(self._current_hostel_id)
        verification['checks']['hostel_exists'] = hostel is not None
        
        # Check settings exist
        try:
            settings = self.settings_repo.get_settings(self._current_hostel_id)
            verification['checks']['settings_exist'] = settings is not None
        except:
            verification['checks']['settings_exist'] = False
        
        # Check policies
        try:
            policies = self.policy_repo.list_policies(self._current_hostel_id)
            verification['checks']['policies_count'] = len(policies)
        except:
            verification['checks']['policies_count'] = 0
        
        # Check amenities
        try:
            amenities = self.amenity_repo.list_amenities(self._current_hostel_id)
            verification['checks']['amenities_count'] = len(amenities)
        except:
            verification['checks']['amenities_count'] = 0
        
        # Overall verification status
        verification['verified'] = all([
            verification['checks']['hostel_exists'],
            verification['checks']['settings_exist'],
        ])
        
        return verification

    # =========================================================================
    # Default Data Generators
    # =========================================================================

    def _get_default_settings(self) -> HostelSettingsSchema:
        """Get default hostel settings."""
        # Return comprehensive default settings
        return HostelSettingsSchema()

    def _get_minimal_settings(self) -> HostelSettingsSchema:
        """Get minimal hostel settings for quick onboarding."""
        # Return minimal required settings
        return HostelSettingsSchema()

    def _get_default_policies(
        self,
        hostel_request: HostelCreate
    ) -> List[PolicyCreate]:
        """Get default policies based on hostel type."""
        policies = []
        
        for template in self.DEFAULT_POLICIES:
            policy = PolicyCreate(
                hostel_id=self._current_hostel_id,
                title=template['title'],
                policy_type=template['policy_type'],
                content=template['content'],
                is_mandatory=template.get('is_mandatory', False),
                is_active=True,
            )
            policies.append(policy)
        
        return policies

    def _get_default_amenities(
        self,
        hostel_request: HostelCreate
    ) -> List[AmenityCreate]:
        """Get default amenities based on hostel type."""
        amenities = []
        
        for category, items in self.DEFAULT_AMENITIES.items():
            for item in items:
                amenity = AmenityCreate(
                    hostel_id=self._current_hostel_id,
                    name=item['name'],
                    description=item.get('description'),
                    category=category,
                    is_free=item.get('is_free', True),
                    is_available=True,
                )
                amenities.append(amenity)
        
        return amenities

    # =========================================================================
    # Batch Onboarding
    # =========================================================================

    def batch_onboard(
        self,
        hostel_requests: List[HostelCreate],
        created_by: Optional[UUID] = None,
        stop_on_error: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Onboard multiple hostels in a batch operation.
        
        Args:
            hostel_requests: List of hostel creation requests
            created_by: UUID of the user creating the hostels
            stop_on_error: Whether to stop on first error
            
        Returns:
            ServiceResult containing batch onboarding summary
        """
        try:
            logger.info(f"Batch onboarding {len(hostel_requests)} hostels")
            
            results = {
                'total': len(hostel_requests),
                'successful': 0,
                'failed': 0,
                'hostels': []
            }
            
            for idx, request in enumerate(hostel_requests, 1):
                try:
                    logger.info(f"Onboarding hostel {idx}/{len(hostel_requests)}: {request.name}")
                    
                    # Use quick onboarding for batch operations
                    result = self.quick_onboard(request, created_by=created_by)
                    
                    if result.success:
                        results['successful'] += 1
                        results['hostels'].append({
                            'name': request.name,
                            'status': 'success',
                            'hostel_id': result.data.get('hostel_id')
                        })
                    else:
                        results['failed'] += 1
                        results['hostels'].append({
                            'name': request.name,
                            'status': 'failed',
                            'error': str(result.error)
                        })
                        
                        if stop_on_error:
                            break
                    
                except Exception as e:
                    results['failed'] += 1
                    results['hostels'].append({
                        'name': request.name,
                        'status': 'failed',
                        'error': str(e)
                    })
                    
                    if stop_on_error:
                        break
            
            success = results['failed'] == 0
            message = f"Batch onboarding completed: {results['successful']}/{results['total']} successful"
            
            if success:
                return ServiceResult.success(results, message=message)
            else:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=message,
                        severity=ErrorSeverity.WARNING,
                        details=results
                    )
                )
            
        except Exception as e:
            return self._handle_exception(e, "batch onboard hostels")