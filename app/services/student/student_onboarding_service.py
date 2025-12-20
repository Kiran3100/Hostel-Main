"""
Student onboarding service.

Comprehensive onboarding workflow for new students including registration,
document collection, verification, and initial setup.
"""

from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.student.student_service import StudentService
from app.services.student.student_profile_service import StudentProfileService
from app.services.student.student_preference_service import StudentPreferenceService
from app.services.student.guardian_contact_service import GuardianContactService
from app.services.student.student_document_service import StudentDocumentService
from app.models.student.student import Student
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    BusinessRuleViolationError
)


class StudentOnboardingService:
    """
    Student onboarding service for complete registration workflow.
    
    Handles:
        - Complete student registration
        - Profile setup
        - Guardian registration
        - Document collection
        - Preference configuration
        - Onboarding progress tracking
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.student_service = StudentService(db)
        self.profile_service = StudentProfileService(db)
        self.preference_service = StudentPreferenceService(db)
        self.guardian_service = GuardianContactService(db)
        self.document_service = StudentDocumentService(db)

    # ============================================================================
    # COMPLETE ONBOARDING
    # ============================================================================

    def onboard_student(
        self,
        user_id: str,
        hostel_id: str,
        student_data: dict[str, Any],
        profile_data: Optional[dict[str, Any]] = None,
        guardian_data: Optional[list[dict[str, Any]]] = None,
        preferences_data: Optional[dict[str, Any]] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Complete student onboarding process.
        
        Args:
            user_id: User UUID
            hostel_id: Hostel UUID
            student_data: Core student information
            profile_data: Extended profile information
            guardian_data: List of guardian contacts
            preferences_data: Student preferences
            audit_context: Audit context
            
        Returns:
            Dictionary with created entities
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Step 1: Create core student record
            student = self.student_service.create_student(
                user_id,
                hostel_id,
                student_data,
                audit_context
            )
            
            result = {
                'student': student,
                'profile': None,
                'guardians': [],
                'preferences': None,
                'onboarding_complete': False,
                'pending_steps': []
            }
            
            # Step 2: Update profile if data provided
            if profile_data:
                try:
                    profile = self.profile_service.update_profile(
                        student.id,
                        profile_data,
                        audit_context
                    )
                    result['profile'] = profile
                except Exception as e:
                    result['pending_steps'].append(f"Profile update failed: {str(e)}")
            
            # Step 3: Add guardians if data provided
            if guardian_data:
                for guardian_info in guardian_data:
                    try:
                        guardian = self.guardian_service.create_guardian_contact(
                            student.id,
                            guardian_info,
                            audit_context
                        )
                        result['guardians'].append(guardian)
                    except Exception as e:
                        result['pending_steps'].append(
                            f"Guardian creation failed: {str(e)}"
                        )
            
            # Step 4: Update preferences if data provided
            if preferences_data:
                try:
                    preferences = self.preference_service.update_preferences(
                        student.id,
                        preferences_data,
                        audit_context
                    )
                    result['preferences'] = preferences
                except Exception as e:
                    result['pending_steps'].append(
                        f"Preferences update failed: {str(e)}"
                    )
            
            # Check if onboarding is complete
            result['onboarding_complete'] = self._check_onboarding_complete(student.id)
            
            self.db.commit()
            
            return result
            
        except Exception as e:
            self.db.rollback()
            raise ValidationError(f"Onboarding failed: {str(e)}")

    def _check_onboarding_complete(self, student_id: str) -> bool:
        """
        Check if student onboarding is complete.
        
        Args:
            student_id: Student UUID
            
        Returns:
            True if onboarding complete
        """
        try:
            # Check student exists
            student = self.student_service.get_student_by_id(student_id)
            
            # Check profile exists and has minimum completeness
            try:
                profile = self.profile_service.get_profile_by_student_id(student_id)
                if profile.profile_completeness < 30:
                    return False
            except NotFoundError:
                return False
            
            # Check at least one guardian exists
            guardians = self.guardian_service.get_student_guardians(student_id)
            if not guardians:
                return False
            
            # Check preferences exist
            try:
                self.preference_service.get_preferences_by_student_id(student_id)
            except NotFoundError:
                return False
            
            return True
            
        except Exception:
            return False

    # ============================================================================
    # STEP-BY-STEP ONBOARDING
    # ============================================================================

    def register_basic_info(
        self,
        user_id: str,
        hostel_id: str,
        student_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Student:
        """
        Step 1: Register basic student information.
        
        Args:
            user_id: User UUID
            hostel_id: Hostel UUID
            student_data: Basic student information
            audit_context: Audit context
            
        Returns:
            Created student instance
        """
        return self.student_service.create_student(
            user_id,
            hostel_id,
            student_data,
            audit_context
        )

    def complete_profile(
        self,
        student_id: str,
        profile_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Step 2: Complete extended profile.
        
        Args:
            student_id: Student UUID
            profile_data: Profile information
            audit_context: Audit context
            
        Returns:
            Dictionary with profile and completeness
        """
        profile = self.profile_service.update_profile(
            student_id,
            profile_data,
            audit_context
        )
        
        completeness = self.profile_service.get_profile_completeness(student_id)
        
        return {
            'profile': profile,
            'completeness': completeness,
            'complete': completeness >= 70
        }

    def add_guardians(
        self,
        student_id: str,
        guardians_data: list[dict[str, Any]],
        audit_context: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """
        Step 3: Add guardian contacts.
        
        Args:
            student_id: Student UUID
            guardians_data: List of guardian information
            audit_context: Audit context
            
        Returns:
            List of results for each guardian
        """
        results = []
        
        for idx, guardian_data in enumerate(guardians_data):
            try:
                # Set first guardian as primary
                if idx == 0:
                    guardian_data['is_primary'] = True
                
                guardian = self.guardian_service.create_guardian_contact(
                    student_id,
                    guardian_data,
                    audit_context
                )
                
                results.append({
                    'success': True,
                    'guardian': guardian,
                    'error': None
                })
                
            except Exception as e:
                results.append({
                    'success': False,
                    'guardian': None,
                    'error': str(e)
                })
        
        return results

    def upload_documents(
        self,
        student_id: str,
        documents_data: list[dict[str, Any]],
        audit_context: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """
        Step 4: Upload required documents.
        
        Args:
            student_id: Student UUID
            documents_data: List of document information
            audit_context: Audit context
            
        Returns:
            List of results for each document
        """
        results = []
        
        for document_data in documents_data:
            try:
                document = self.document_service.upload_document(
                    student_id,
                    document_data,
                    audit_context
                )
                
                results.append({
                    'success': True,
                    'document': document,
                    'error': None
                })
                
            except Exception as e:
                results.append({
                    'success': False,
                    'document': None,
                    'error': str(e)
                })
        
        return results

    def configure_preferences(
        self,
        student_id: str,
        preferences_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Step 5: Configure student preferences.
        
        Args:
            student_id: Student UUID
            preferences_data: Preferences information
            audit_context: Audit context
            
        Returns:
            Configured preferences
        """
        preferences = self.preference_service.update_preferences(
            student_id,
            preferences_data,
            audit_context
        )
        
        return {
            'preferences': preferences,
            'configured': True
        }

    # ============================================================================
    # ONBOARDING PROGRESS
    # ============================================================================

    def get_onboarding_progress(
        self,
        student_id: str
    ) -> dict[str, Any]:
        """
        Get student onboarding progress.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Dictionary with progress details
        """
        progress = {
            'student_id': student_id,
            'steps': {},
            'overall_complete': False,
            'completion_percentage': 0
        }
        
        completed_steps = 0
        total_steps = 5
        
        # Check basic info (always complete if student exists)
        try:
            student = self.student_service.get_student_by_id(student_id)
            progress['steps']['basic_info'] = {
                'complete': True,
                'data': student
            }
            completed_steps += 1
        except NotFoundError:
            progress['steps']['basic_info'] = {
                'complete': False,
                'data': None
            }
        
        # Check profile
        try:
            profile = self.profile_service.get_profile_by_student_id(student_id)
            completeness = profile.profile_completeness
            progress['steps']['profile'] = {
                'complete': completeness >= 30,
                'completeness': completeness,
                'data': profile
            }
            if completeness >= 30:
                completed_steps += 1
        except NotFoundError:
            progress['steps']['profile'] = {
                'complete': False,
                'completeness': 0,
                'data': None
            }
        
        # Check guardians
        guardians = self.guardian_service.get_student_guardians(student_id)
        progress['steps']['guardians'] = {
            'complete': len(guardians) > 0,
            'count': len(guardians),
            'data': guardians
        }
        if len(guardians) > 0:
            completed_steps += 1
        
        # Check documents
        documents = self.document_service.get_student_documents(student_id)
        required_docs = ['id_proof', 'photo']
        uploaded_required = [
            doc.document_type for doc in documents
            if doc.document_type in required_docs
        ]
        progress['steps']['documents'] = {
            'complete': len(uploaded_required) >= len(required_docs),
            'required': required_docs,
            'uploaded': uploaded_required,
            'count': len(documents)
        }
        if len(uploaded_required) >= len(required_docs):
            completed_steps += 1
        
        # Check preferences
        try:
            preferences = self.preference_service.get_preferences_by_student_id(student_id)
            progress['steps']['preferences'] = {
                'complete': True,
                'data': preferences
            }
            completed_steps += 1
        except NotFoundError:
            progress['steps']['preferences'] = {
                'complete': False,
                'data': None
            }
        
        # Calculate overall progress
        progress['completion_percentage'] = int((completed_steps / total_steps) * 100)
        progress['overall_complete'] = completed_steps == total_steps
        
        return progress

    def get_pending_onboarding_steps(
        self,
        student_id: str
    ) -> list[dict[str, Any]]:
        """
        Get list of pending onboarding steps.
        
        Args:
            student_id: Student UUID
            
        Returns:
            List of pending steps with instructions
        """
        progress = self.get_onboarding_progress(student_id)
        pending_steps = []
        
        if not progress['steps']['basic_info']['complete']:
            pending_steps.append({
                'step': 'basic_info',
                'title': 'Complete Basic Information',
                'description': 'Provide basic student details',
                'priority': 1
            })
        
        if not progress['steps']['profile']['complete']:
            completeness = progress['steps']['profile'].get('completeness', 0)
            pending_steps.append({
                'step': 'profile',
                'title': 'Complete Profile',
                'description': f'Profile is {completeness}% complete. Minimum 30% required.',
                'priority': 2
            })
        
        if not progress['steps']['guardians']['complete']:
            pending_steps.append({
                'step': 'guardians',
                'title': 'Add Guardian Contact',
                'description': 'Add at least one guardian/parent contact',
                'priority': 3
            })
        
        if not progress['steps']['documents']['complete']:
            required = progress['steps']['documents']['required']
            uploaded = progress['steps']['documents']['uploaded']
            missing = [doc for doc in required if doc not in uploaded]
            pending_steps.append({
                'step': 'documents',
                'title': 'Upload Required Documents',
                'description': f'Missing documents: {", ".join(missing)}',
                'priority': 4
            })
        
        if not progress['steps']['preferences']['complete']:
            pending_steps.append({
                'step': 'preferences',
                'title': 'Configure Preferences',
                'description': 'Set your notification and privacy preferences',
                'priority': 5
            })
        
        return pending_steps

    # ============================================================================
    # VERIFICATION WORKFLOW
    # ============================================================================

    def verify_student_documents(
        self,
        student_id: str,
        verified_by: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Verify all pending student documents.
        
        Args:
            student_id: Student UUID
            verified_by: Admin user ID
            audit_context: Audit context
            
        Returns:
            Verification results
        """
        documents = self.document_service.get_student_documents(student_id)
        
        results = {
            'total': len(documents),
            'verified': 0,
            'failed': 0,
            'details': []
        }
        
        for document in documents:
            if document.verified:
                results['verified'] += 1
                continue
            
            try:
                verified_doc = self.document_service.verify_document(
                    document.id,
                    verified_by,
                    audit_context=audit_context
                )
                results['verified'] += 1
                results['details'].append({
                    'document_id': document.id,
                    'type': document.document_type,
                    'success': True
                })
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'document_id': document.id,
                    'type': document.document_type,
                    'success': False,
                    'error': str(e)
                })
        
        return results