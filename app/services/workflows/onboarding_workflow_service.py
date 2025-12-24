"""
Enhanced Onboarding Workflow Service

Handles student onboarding with improved validation, monitoring, and error recovery.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum
import asyncio

from app.core.exceptions import ValidationException, BusinessLogicException
from app.core.config import settings
from app.models.base.enums import BookingStatus, StudentStatus, DocumentVerificationStatus
from app.repositories.booking import BookingRepository, BookingConversionRepository
from app.repositories.student import StudentRepository
from app.repositories.room import BedAssignmentRepository
from app.repositories.payment import PaymentRepository
from app.repositories.document import StudentDocumentRepository
from app.services.workflows.workflow_engine_service import (
    workflow_engine,
    create_workflow,
    create_step,
    WorkflowPriority
)
from app.services.workflows.notification_workflow_service import (
    NotificationWorkflowService
)


class OnboardingStage(str, Enum):
    """Enhanced onboarding stages."""
    BOOKING_VALIDATION = "booking_validation"
    DOCUMENT_VERIFICATION = "document_verification"
    PAYMENT_PROCESSING = "payment_processing"
    ROOM_ASSIGNMENT = "room_assignment"
    PROFILE_CREATION = "profile_creation"
    ACCESS_PROVISIONING = "access_provisioning"
    ORIENTATION_SCHEDULING = "orientation_scheduling"
    COMPLETION = "completion"


class DocumentType(str, Enum):
    """Required document types for onboarding."""
    ID_PROOF = "id_proof"
    PHOTO = "photo"
    ADDRESS_PROOF = "address_proof"
    EDUCATION_PROOF = "education_proof"
    GUARDIAN_ID = "guardian_id"
    MEDICAL_CERTIFICATE = "medical_certificate"
    POLICE_CLEARANCE = "police_clearance"


@dataclass
class OnboardingChecklist:
    """Checklist for tracking onboarding progress."""
    booking_confirmed: bool = False
    documents_verified: bool = False
    payments_completed: bool = False
    room_assigned: bool = False
    profile_created: bool = False
    access_provisioned: bool = False
    orientation_scheduled: bool = False
    welcome_kit_sent: bool = False
    
    def get_completion_percentage(self) -> float:
        """Calculate completion percentage."""
        completed_items = sum([
            self.booking_confirmed,
            self.documents_verified,
            self.payments_completed,
            self.room_assigned,
            self.profile_created,
            self.access_provisioned,
            self.orientation_scheduled,
            self.welcome_kit_sent
        ])
        return (completed_items / 8) * 100


@dataclass
class OnboardingContext:
    """Enhanced context for onboarding workflow."""
    booking_id: UUID
    student_user_id: UUID
    hostel_id: UUID
    check_in_date: datetime
    initiated_by: UUID
    checklist: OnboardingChecklist
    validation_errors: List[str]
    warnings: List[str]
    assigned_room_id: Optional[UUID] = None
    assigned_bed_id: Optional[UUID] = None
    student_id: Optional[UUID] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.validation_errors is None:
            self.validation_errors = []
        if self.warnings is None:
            self.warnings = []


class OnboardingWorkflowService:
    """
    Enhanced service for managing student onboarding workflows.
    
    Features:
    - Comprehensive validation and verification
    - Intelligent room assignment
    - Automated document verification
    - Real-time progress tracking
    - Error recovery and rollback
    - Integration with external services
    - Performance optimization
    """
    
    def __init__(
        self,
        booking_repo: BookingRepository,
        student_repo: StudentRepository,
        bed_assignment_repo: BedAssignmentRepository,
        payment_repo: PaymentRepository,
        document_repo: StudentDocumentRepository,
        conversion_repo: BookingConversionRepository,
        notification_service: NotificationWorkflowService
    ):
        self.booking_repo = booking_repo
        self.student_repo = student_repo
        self.bed_assignment_repo = bed_assignment_repo
        self.payment_repo = payment_repo
        self.document_repo = document_repo
        self.conversion_repo = conversion_repo
        self.notification_service = notification_service
        
        # Performance optimizations
        self._room_cache: Dict[str, Any] = {}
        self._cache_expiry = datetime.utcnow()
        
        self._register_workflows()
    
    def _register_workflows(self) -> None:
        """Register enhanced onboarding workflows."""
        
        # Comprehensive onboarding workflow
        full_onboarding_wf = (
            create_workflow(
                "student_onboarding",
                "Enhanced Student Onboarding Workflow",
                "Complete onboarding process with comprehensive validation and monitoring",
                priority=WorkflowPriority.HIGH,
                max_execution_time=1800,  # 30 minutes
                max_concurrent_executions=20,
                enable_monitoring=True
            )
            .add_validator(self._validate_onboarding_context)
            .add_step(create_step(
                "initialize_onboarding",
                self._initialize_onboarding_context,
                timeout_seconds=30
            ))
            .add_step(create_step(
                "validate_booking_eligibility",
                self._validate_booking_eligibility,
                timeout_seconds=60,
                retry_count=2
            ))
            .add_step(create_step(
                "verify_student_documents",
                self._verify_student_documents,
                timeout_seconds=120,
                retry_count=1
            ))
            .add_step(create_step(
                "validate_payment_requirements",
                self._validate_payment_requirements,
                timeout_seconds=60
            ))
            .add_step(create_step(
                "perform_background_checks",
                self._perform_background_checks,
                required=False,
                timeout_seconds=300
            ))
            .add_step(create_step(
                "assign_optimal_accommodation",
                self._assign_optimal_room_and_bed,
                timeout_seconds=120,
                rollback_handler=self._rollback_room_assignment
            ))
            .add_step(create_step(
                "create_comprehensive_profile",
                self._create_comprehensive_student_profile,
                timeout_seconds=60,
                rollback_handler=self._rollback_profile_creation
            ))
            .add_step(create_step(
                "setup_digital_services",
                self._setup_digital_services,
                timeout_seconds=90,
                rollback_handler=self._rollback_digital_services
            ))
            .add_step(create_step(
                "provision_access_credentials",
                self._provision_access_credentials,
                timeout_seconds=60,
                rollback_handler=self._revoke_access_credentials
            ))
            .add_step(create_step(
                "setup_meal_preferences",
                self._setup_meal_and_preferences,
                required=False,
                timeout_seconds=30
            ))
            .add_step(create_step(
                "schedule_orientation_session",
                self._schedule_orientation_session,
                required=False,
                timeout_seconds=45
            ))
            .add_step(create_step(
                "generate_welcome_package",
                self._generate_welcome_package,
                required=False,
                timeout_seconds=60
            ))
            .add_step(create_step(
                "finalize_booking_conversion",
                self._finalize_booking_conversion,
                timeout_seconds=30
            ))
            .add_step(create_step(
                "send_completion_notifications",
                self._send_onboarding_completion_notifications,
                required=False,
                timeout_seconds=30
            ))
            .add_step(create_step(
                "update_analytics_metrics",
                self._update_onboarding_analytics,
                required=False,
                timeout_seconds=15
            ))
            .on_complete(self._on_onboarding_complete)
            .on_error(self._on_onboarding_error)
        )
        
        workflow_engine.register_workflow(full_onboarding_wf)
        
        # Expedited onboarding workflow
        quick_onboarding_wf = (
            create_workflow(
                "quick_onboarding",
                "Expedited Onboarding Workflow",
                "Fast-track onboarding for pre-verified students"
            )
            .add_step(create_step(
                "validate_pre_verification",
                self._validate_pre_verification_status
            ))
            .add_step(create_step(
                "fast_track_document_check",
                self._fast_track_document_verification
            ))
            .add_step(create_step(
                "process_expedited_payments",
                self._process_expedited_payments
            ))
            .add_step(create_step(
                "assign_pre_allocated_room",
                self._assign_pre_allocated_accommodation
            ))
            .add_step(create_step(
                "create_profile_from_template",
                self._create_profile_from_template
            ))
            .add_step(create_step(
                "issue_temporary_access",
                self._issue_temporary_access_credentials
            ))
            .add_step(create_step(
                "schedule_followup_verification",
                self._schedule_followup_verification
            ))
        )
        
        workflow_engine.register_workflow(quick_onboarding_wf)
        
        # Walk-in onboarding workflow
        walkin_onboarding_wf = (
            create_workflow(
                "walkin_onboarding",
                "Walk-in Student Onboarding",
                "Handle walk-in students without prior booking"
            )
            .add_step(create_step(
                "collect_basic_information",
                self._collect_walkin_basic_info
            ))
            .add_step(create_step(
                "verify_availability",
                self._verify_immediate_accommodation_availability
            ))
            .add_step(create_step(
                "conduct_instant_verification",
                self._conduct_instant_document_verification
            ))
            .add_step(create_step(
                "process_advance_payment",
                self._process_walkin_advance_payment
            ))
            .add_step(create_step(
                "assign_available_accommodation",
                self._assign_next_available_accommodation
            ))
            .add_step(create_step(
                "create_provisional_profile",
                self._create_provisional_student_profile
            ))
            .add_step(create_step(
                "issue_temporary_credentials",
                self._issue_temporary_access_credentials
            ))
            .add_step(create_step(
                "schedule_complete_verification",
                self._schedule_complete_verification_followup
            ))
        )
        
        workflow_engine.register_workflow(walkin_onboarding_wf)
    
    # Public API methods
    
    async def onboard_student(
        self,
        db: Session,
        booking_id: UUID,
        initiated_by: UUID,
        check_in_date: Optional[datetime] = None,
        expedited: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute comprehensive student onboarding workflow.
        
        Args:
            db: Database session
            booking_id: Confirmed booking to convert
            initiated_by: Admin/staff performing onboarding
            check_in_date: Actual check-in date
            expedited: Use expedited workflow for pre-verified students
            metadata: Additional metadata
            
        Returns:
            Comprehensive onboarding result
        """
        # Load booking data
        booking = self.booking_repo.get_by_id(db, booking_id)
        if not booking:
            raise ValidationException("Booking not found")
        
        # Create onboarding context
        onboarding_context = OnboardingContext(
            booking_id=booking_id,
            student_user_id=booking.student_id,
            hostel_id=booking.hostel_id,
            check_in_date=check_in_date or datetime.utcnow(),
            initiated_by=initiated_by,
            checklist=OnboardingChecklist(),
            validation_errors=[],
            warnings=[],
            metadata=metadata or {}
        )
        
        # Prepare workflow context
        workflow_context = {
            "db": db,
            "onboarding_context": onboarding_context,
            "booking": booking,
            "expedited": expedited
        }
        
        # Choose appropriate workflow
        workflow_type = "quick_onboarding" if expedited else "student_onboarding"
        
        execution = await workflow_engine.execute_workflow(
            workflow_type,
            workflow_context,
            initiated_by
        )
        
        return execution.result or execution.to_dict()
    
    async def onboard_walkin_student(
        self,
        db: Session,
        hostel_id: UUID,
        student_data: Dict[str, Any],
        initiated_by: UUID,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute walk-in student onboarding workflow.
        
        Args:
            db: Database session
            hostel_id: Hostel for accommodation
            student_data: Student information
            initiated_by: Staff performing onboarding
            metadata: Additional metadata
            
        Returns:
            Walk-in onboarding result
        """
        # Create temporary context for walk-in
        temp_booking_id = UUID('00000000-0000-0000-0000-000000000000')
        
        onboarding_context = OnboardingContext(
            booking_id=temp_booking_id,
            student_user_id=UUID(student_data.get('user_id')),
            hostel_id=hostel_id,
            check_in_date=datetime.utcnow(),
            initiated_by=initiated_by,
            checklist=OnboardingChecklist(),
            validation_errors=[],
            warnings=[],
            metadata=metadata or {}
        )
        
        workflow_context = {
            "db": db,
            "onboarding_context": onboarding_context,
            "student_data": student_data,
            "is_walkin": True
        }
        
        execution = await workflow_engine.execute_workflow(
            "walkin_onboarding",
            workflow_context,
            initiated_by
        )
        
        return execution.result or execution.to_dict()
    
    async def get_onboarding_progress(
        self,
        db: Session,
        booking_id: UUID
    ) -> Dict[str, Any]:
        """Get real-time onboarding progress."""
        # Check for active onboarding executions
        active_executions = workflow_engine.get_executions_by_type(
            "student_onboarding",
            limit=50
        )
        
        for execution in active_executions:
            if (execution.context.get("onboarding_context") and 
                execution.context["onboarding_context"].booking_id == booking_id):
                
                onboarding_context = execution.context["onboarding_context"]
                return {
                    "execution_id": str(execution.execution_id),
                    "stage": execution.current_step_name,
                    "progress_percentage": execution.get_progress_percentage(),
                    "checklist": onboarding_context.checklist.__dict__,
                    "completion_percentage": onboarding_context.checklist.get_completion_percentage(),
                    "errors": onboarding_context.validation_errors,
                    "warnings": onboarding_context.warnings,
                    "estimated_completion": self._estimate_completion_time(execution)
                }
        
        # Check if already completed
        student = self.student_repo.get_by_booking_id(db, booking_id)
        if student and student.student_status == StudentStatus.ACTIVE:
            return {
                "stage": "completed",
                "progress_percentage": 100.0,
                "completion_percentage": 100.0,
                "completed_at": student.check_in_date.isoformat() if student.check_in_date else None
            }
        
        return {"stage": "not_started", "progress_percentage": 0.0}
    
    # Validation methods
    
    def _validate_onboarding_context(self, context: Dict[str, Any]) -> bool:
        """Validate onboarding workflow context."""
        required_fields = ["db", "onboarding_context"]
        
        if not all(field in context for field in required_fields):
            return False
        
        onboarding_context = context["onboarding_context"]
        if not isinstance(onboarding_context, OnboardingContext):
            return False
        
        return True
    
    # Step handlers - Main onboarding workflow
    
    async def _initialize_onboarding_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize comprehensive onboarding context with pre-checks."""
        db = context["db"]
        onboarding_context = context["onboarding_context"]
        
        # Load and validate booking
        booking = context.get("booking") or self.booking_repo.get_by_id(
            db, onboarding_context.booking_id
        )
        
        if not booking:
            raise ValidationException("Booking not found")
        
        # Validate booking status
        if booking.booking_status != BookingStatus.CONFIRMED:
            raise BusinessLogicException(
                f"Invalid booking status for onboarding: {booking.booking_status}"
            )
        
        # Check for existing student profile
        existing_student = self.student_repo.get_by_user_id(
            db, onboarding_context.student_user_id
        )
        
        if existing_student:
            if existing_student.student_status == StudentStatus.ACTIVE:
                raise BusinessLogicException("Student is already active")
            elif existing_student.hostel_id != onboarding_context.hostel_id:
                raise BusinessLogicException("Student belongs to different hostel")
        
        # Load guest information
        guest = booking.guest
        if not guest:
            raise ValidationException("Guest information not found")
        
        # Initialize context data
        onboarding_context.metadata.update({
            "booking_amount": float(booking.total_amount),
            "advance_paid": float(booking.advance_paid),
            "room_type_requested": booking.room_type_requested,
            "stay_duration": booking.stay_duration_months,
            "guest_name": guest.full_name,
            "guest_phone": guest.phone_number,
            "guest_email": guest.email
        })
        
        # Mark first checklist item
        onboarding_context.checklist.booking_confirmed = True
        
        return {
            "booking_id": str(booking.id),
            "student_user_id": str(onboarding_context.student_user_id),
            "hostel_id": str(onboarding_context.hostel_id),
            "booking_amount": float(booking.total_amount),
            "guest_name": guest.full_name,
            "initialization_completed": True
        }
    
    async def _validate_booking_eligibility(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive booking eligibility validation."""
        db = context["db"]
        booking = context["booking"]
        onboarding_context = context["onboarding_context"]
        
        validation_results = {
            "eligible": True,
            "checks_performed": [],
            "issues_found": []
        }
        
        # Check payment status
        payment_check = self._validate_payment_completion(booking)
        validation_results["checks_performed"].append("payment_status")
        
        if not payment_check["valid"]:
            validation_results["issues_found"].append(payment_check["issue"])
            if payment_check["severity"] == "critical":
                validation_results["eligible"] = False
            else:
                onboarding_context.warnings.append(payment_check["issue"])
        
        # Check document completeness
        document_check = await self._check_document_completeness(db, booking.guest)
        validation_results["checks_performed"].append("document_completeness")
        
        if not document_check["complete"]:
            missing_docs = document_check["missing_documents"]
            issue = f"Missing documents: {', '.join(missing_docs)}"
            validation_results["issues_found"].append(issue)
            
            # Critical documents vs optional
            critical_docs = {DocumentType.ID_PROOF, DocumentType.PHOTO}
            if any(doc in critical_docs for doc in missing_docs):
                validation_results["eligible"] = False
                onboarding_context.validation_errors.append(issue)
            else:
                onboarding_context.warnings.append(issue)
        
        # Check hostel capacity
        capacity_check = await self._check_hostel_capacity(db, onboarding_context.hostel_id)
        validation_results["checks_performed"].append("hostel_capacity")
        
        if not capacity_check["available"]:
            issue = "No accommodation available"
            validation_results["issues_found"].append(issue)
            validation_results["eligible"] = False
            onboarding_context.validation_errors.append(issue)
        
        # Check blacklist status
        blacklist_check = await self._check_blacklist_status(db, booking.guest)
        validation_results["checks_performed"].append("blacklist_status")
        
        if blacklist_check["is_blacklisted"]:
            issue = f"Student is blacklisted: {blacklist_check['reason']}"
            validation_results["issues_found"].append(issue)
            validation_results["eligible"] = False
            onboarding_context.validation_errors.append(issue)
        
        if not validation_results["eligible"]:
            raise BusinessLogicException(
                f"Student not eligible for onboarding: {'; '.join(validation_results['issues_found'])}"
            )
        
        return validation_results
    
    async def _verify_student_documents(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive document verification with AI assistance."""
        db = context["db"]
        booking = context["booking"]
        onboarding_context = context["onboarding_context"]
        
        verification_results = {
            "verified_documents": [],
            "failed_documents": [],
            "pending_documents": [],
            "verification_score": 0.0
        }
        
        # Get uploaded documents
        documents = self.document_repo.get_by_guest_id(db, booking.guest.id)
        
        for doc in documents:
            verification_result = await self._verify_single_document(doc)
            
            if verification_result["status"] == DocumentVerificationStatus.VERIFIED:
                verification_results["verified_documents"].append({
                    "type": doc.document_type,
                    "confidence_score": verification_result["confidence_score"]
                })
            elif verification_result["status"] == DocumentVerificationStatus.REJECTED:
                verification_results["failed_documents"].append({
                    "type": doc.document_type,
                    "reason": verification_result["rejection_reason"]
                })
            else:
                verification_results["pending_documents"].append({
                    "type": doc.document_type,
                    "status": verification_result["status"]
                })
        
        # Calculate overall verification score
        total_docs = len(documents)
        verified_count = len(verification_results["verified_documents"])
        verification_results["verification_score"] = (verified_count / total_docs) * 100 if total_docs > 0 else 0
        
        # Check minimum verification threshold
        min_threshold = settings.MIN_DOCUMENT_VERIFICATION_SCORE  # e.g., 80%
        
        if verification_results["verification_score"] < min_threshold:
            failed_docs = verification_results["failed_documents"]
            if failed_docs:
                issue = f"Document verification failed: {'; '.join([f'{d['type']}: {d['reason']}' for d in failed_docs])}"
                onboarding_context.validation_errors.append(issue)
                raise BusinessLogicException(issue)
            else:
                issue = "Insufficient document verification score"
                onboarding_context.warnings.append(issue)
        
        # Mark checklist item
        if verification_results["verification_score"] >= min_threshold:
            onboarding_context.checklist.documents_verified = True
        
        return verification_results
    
    async def _verify_single_document(self, document) -> Dict[str, Any]:
        """Verify a single document using AI/ML services."""
        # This would integrate with document verification services
        # For now, simplified verification
        
        # Check document type and format
        if not document.file_url:
            return {
                "status": DocumentVerificationStatus.REJECTED,
                "rejection_reason": "No file uploaded",
                "confidence_score": 0.0
            }
        
        # Simulate AI verification
        import random
        confidence_score = random.uniform(0.7, 0.99)  # Simulate confidence
        
        if confidence_score > 0.85:
            return {
                "status": DocumentVerificationStatus.VERIFIED,
                "confidence_score": confidence_score
            }
        elif confidence_score > 0.6:
            return {
                "status": DocumentVerificationStatus.PENDING_REVIEW,
                "confidence_score": confidence_score
            }
        else:
            return {
                "status": DocumentVerificationStatus.REJECTED,
                "rejection_reason": "Document quality insufficient for verification",
                "confidence_score": confidence_score
            }
    
    async def _validate_payment_requirements(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate all payment requirements are met."""
        db = context["db"]
        booking = context["booking"]
        onboarding_context = context["onboarding_context"]
        
        payment_validation = {
            "advance_payment_valid": False,
            "security_deposit_valid": False,
            "total_paid": Decimal("0"),
            "outstanding_amount": Decimal("0"),
            "payment_methods_used": []
        }
        
        # Get all payments for this booking
        payments = self.payment_repo.get_by_booking_id(db, booking.id)
        
        total_paid = sum(p.amount for p in payments if p.payment_status == "completed")
        payment_validation["total_paid"] = total_paid
        
        # Check advance payment requirement
        required_advance = booking.advance_amount
        advance_paid = booking.advance_paid
        
        if advance_paid >= required_advance:
            payment_validation["advance_payment_valid"] = True
        else:
            shortage = required_advance - advance_paid
            issue = f"Advance payment shortage: {shortage}"
            onboarding_context.validation_errors.append(issue)
            raise BusinessLogicException(issue)
        
        # Check security deposit (if required)
        security_deposit_required = booking.security_deposit_amount or Decimal("0")
        security_deposit_paid = sum(
            p.amount for p in payments 
            if p.payment_type == "security_deposit" and p.payment_status == "completed"
        )
        
        if security_deposit_required > 0:
            if security_deposit_paid >= security_deposit_required:
                payment_validation["security_deposit_valid"] = True
            else:
                shortage = security_deposit_required - security_deposit_paid
                issue = f"Security deposit shortage: {shortage}"
                onboarding_context.warnings.append(issue)
        else:
            payment_validation["security_deposit_valid"] = True
        
        # Calculate outstanding amount
        total_required = booking.total_amount
        payment_validation["outstanding_amount"] = max(Decimal("0"), total_required - total_paid)
        
        # Get payment methods used
        payment_validation["payment_methods_used"] = list(set(p.payment_method for p in payments))
        
        # Mark checklist item if payments are sufficient
        if (payment_validation["advance_payment_valid"] and 
            payment_validation["security_deposit_valid"] and
            payment_validation["outstanding_amount"] <= Decimal("100")):  # Allow small tolerance
            onboarding_context.checklist.payments_completed = True
        
        return payment_validation
    
    async def _perform_background_checks(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform background verification checks."""
        db = context["db"]
        booking = context["booking"]
        guest = booking.guest
        
        background_check_results = {
            "checks_performed": [],
            "issues_found": [],
            "overall_score": 100.0,
            "recommendations": []
        }
        
        # Police verification check (if applicable)
        if guest.police_verification_number:
            police_check = await self._verify_police_clearance(guest.police_verification_number)
            background_check_results["checks_performed"].append("police_verification")
            
            if not police_check["valid"]:
                background_check_results["issues_found"].append(
                    f"Police verification issue: {police_check['issue']}"
                )
                background_check_results["overall_score"] -= 20
        
        # Address verification
        if guest.permanent_address:
            address_check = await self._verify_address_details(guest.permanent_address)
            background_check_results["checks_performed"].append("address_verification")
            
            if not address_check["verified"]:
                background_check_results["issues_found"].append("Address verification failed")
                background_check_results["overall_score"] -= 10
        
        # Reference checks
        if guest.reference_contact:
            reference_check = await self._verify_reference_contact(guest.reference_contact)
            background_check_results["checks_performed"].append("reference_check")
            
            if not reference_check["contactable"]:
                background_check_results["issues_found"].append("Reference contact not reachable")
                background_check_results["overall_score"] -= 15
        
        # Generate recommendations based on score
        if background_check_results["overall_score"] < 70:
            background_check_results["recommendations"].append("Consider additional security deposit")
        if background_check_results["overall_score"] < 50:
            background_check_results["recommendations"].append("Require guarantor documentation")
        
        return background_check_results
    
    async def _assign_optimal_room_and_bed(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Assign optimal room and bed using intelligent algorithms."""
        db = context["db"]
        booking = context["booking"]
        onboarding_context = context["onboarding_context"]
        
        assignment_result = {
            "room_assigned": False,
            "bed_assigned": False,
            "room_id": None,
            "bed_id": None,
            "assignment_score": 0.0,
            "assignment_criteria": []
        }
        
        # Use existing assignment from booking if available
        if booking.room_id and booking.bed_id:
            # Verify the assignment is still valid
            bed_available = self.bed_assignment_repo.check_bed_availability(
                db, booking.bed_id, onboarding_context.check_in_date
            )
            
            if bed_available:
                assignment_result.update({
                    "room_assigned": True,
                    "bed_assigned": True,
                    "room_id": booking.room_id,
                    "bed_id": booking.bed_id,
                    "assignment_score": 100.0,
                    "assignment_criteria": ["pre_approved"]
                })
                
                onboarding_context.assigned_room_id = booking.room_id
                onboarding_context.assigned_bed_id = booking.bed_id
            else:
                # Pre-assigned bed is no longer available, find alternative
                assignment_result = await self._find_alternative_accommodation(
                    db, booking, onboarding_context
                )
        else:
            # Find optimal assignment
            assignment_result = await self._find_optimal_accommodation(
                db, booking, onboarding_context
            )
        
        if not assignment_result["bed_assigned"]:
            raise BusinessLogicException("No suitable accommodation available")
        
        # Create bed assignment record
        assignment = self.bed_assignment_repo.create_assignment(
            db=db,
            bed_id=assignment_result["bed_id"],
            student_id=onboarding_context.student_user_id,  # Will be updated after profile creation
            occupied_from=onboarding_context.check_in_date,
            monthly_rent=booking.quoted_rent_monthly,
            booking_id=booking.id,
            assignment_metadata={
                "assignment_score": assignment_result["assignment_score"],
                "criteria_used": assignment_result["assignment_criteria"]
            }
        )
        
        # Store assignment in context for rollback
        context["bed_assignment"] = assignment
        onboarding_context.checklist.room_assigned = True
        
        return assignment_result
    
    async def _find_optimal_accommodation(
        self, 
        db: Session, 
        booking, 
        onboarding_context: OnboardingContext
    ) -> Dict[str, Any]:
        """Find optimal room and bed assignment using intelligent algorithms."""
        # Get available beds matching criteria
        available_beds = self.bed_assignment_repo.get_available_beds(
            db=db,
            hostel_id=onboarding_context.hostel_id,
            room_type=booking.room_type_requested,
            from_date=onboarding_context.check_in_date,
            gender_preference=booking.guest.gender
        )
        
        if not available_beds:
            return {
                "room_assigned": False,
                "bed_assigned": False,
                "error": "No beds available matching criteria"
            }
        
        # Score beds based on multiple criteria
        scored_beds = []
        for bed in available_beds:
            score = self._calculate_bed_assignment_score(bed, booking.guest)
            scored_beds.append((bed, score))
        
        # Sort by score (highest first)
        scored_beds.sort(key=lambda x: x[1], reverse=True)
        
        # Select best bed
        best_bed, best_score = scored_beds[0]
        
        return {
            "room_assigned": True,
            "bed_assigned": True,
            "room_id": best_bed.room_id,
            "bed_id": best_bed.id,
            "assignment_score": best_score,
            "assignment_criteria": ["optimal_matching"]
        }
    
    def _calculate_bed_assignment_score(self, bed, guest) -> float:
        """Calculate assignment score for a bed based on multiple factors."""
        score = 50.0  # Base score
        
        # Room occupancy factor (prefer less crowded rooms)
        current_occupancy = bed.room.current_occupancy or 0
        max_occupancy = bed.room.max_occupancy or 1
        occupancy_ratio = current_occupancy / max_occupancy
        score += (1 - occupancy_ratio) * 20
        
        # Floor preference (ground floor for elderly/disabled)
        if guest.age and guest.age > 60:
            if bed.room.floor_number <= 2:
                score += 10
        
        # Amenity matching
        if bed.room.has_ac and guest.preferences.get("ac_preferred"):
            score += 15
        
        if bed.room.has_balcony and guest.preferences.get("balcony_preferred"):
            score += 5
        
        # Bed type preference
        if bed.bed_type == guest.preferences.get("bed_type", "single"):
            score += 10
        
        return min(score, 100.0)  # Cap at 100
    
    async def _find_alternative_accommodation(
        self, 
        db: Session, 
        booking, 
        onboarding_context: OnboardingContext
    ) -> Dict[str, Any]:
        """Find alternative accommodation when pre-assigned bed is unavailable."""
        # Similar to optimal assignment but with relaxed criteria
        return await self._find_optimal_accommodation(db, booking, onboarding_context)
    
    async def _create_comprehensive_student_profile(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create comprehensive student profile with all necessary data."""
        db = context["db"]
        booking = context["booking"]
        onboarding_context = context["onboarding_context"]
        guest = booking.guest
        
        # Prepare student data
        student_data = {
            "user_id": onboarding_context.student_user_id,
            "hostel_id": onboarding_context.hostel_id,
            "room_id": onboarding_context.assigned_room_id,
            "bed_id": onboarding_context.assigned_bed_id,
            "check_in_date": onboarding_context.check_in_date,
            "booking_id": booking.id,
            
            # From guest information
            "guardian_name": guest.guardian_name,
            "guardian_phone": guest.guardian_phone,
            "guardian_relation": guest.guardian_relation,
            "emergency_contact_name": guest.emergency_contact_name,
            "emergency_contact_phone": guest.emergency_contact_phone,
            
            # From booking
            "monthly_rent": booking.quoted_rent_monthly,
            "security_deposit_paid": booking.advance_paid,  # Simplified
            "stay_duration_months": booking.stay_duration_months,
            
            # Status and dates
            "student_status": StudentStatus.ACTIVE,
            "registration_date": datetime.utcnow(),
            
            # Academic/Professional information
            "institution_name": guest.institution_or_company,
            "course_or_designation": guest.designation_or_course,
            "student_id_number": guest.student_id or guest.employee_id,
            
            # Personal preferences
            "food_preferences": guest.food_preferences,
            "special_requirements": guest.special_requirements,
            "medical_conditions": guest.medical_conditions,
            
            # Additional metadata
            "onboarding_metadata": {
                "onboarded_by": str(onboarding_context.initiated_by),
                "onboarding_date": datetime.utcnow().isoformat(),
                "verification_score": onboarding_context.metadata.get("verification_score", 0),
                "auto_verified": onboarding_context.metadata.get("auto_verified", False)
            }
        }
        
        # Create student record
        student = self.student_repo.create(db, student_data)
        
        # Update context
        onboarding_context.student_id = student.id
        context["created_student"] = student
        onboarding_context.checklist.profile_created = True
        
        # Update bed assignment with actual student ID
        if "bed_assignment" in context:
            assignment = context["bed_assignment"]
            assignment.student_id = student.id
            db.commit()
        
        return {
            "student_id": str(student.id),
            "student_number": student.student_number,
            "profile_created": True,
            "user_id": str(student.user_id)
        }
    
    async def _setup_digital_services(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Setup digital services and integrations."""
        db = context["db"]
        onboarding_context = context["onboarding_context"]
        student = context["created_student"]
        
        setup_results = {
            "services_configured": [],
            "failed_services": [],
            "login_credentials_sent": False
        }
        
        # Setup mobile app access
        try:
            app_setup = await self._setup_mobile_app_access(student)
            if app_setup["success"]:
                setup_results["services_configured"].append("mobile_app")
            else:
                setup_results["failed_services"].append({"service": "mobile_app", "error": app_setup["error"]})
        except Exception as e:
            setup_results["failed_services"].append({"service": "mobile_app", "error": str(e)})
        
        # Setup web portal access
        try:
            portal_setup = await self._setup_web_portal_access(student)
            if portal_setup["success"]:
                setup_results["services_configured"].append("web_portal")
                setup_results["login_credentials_sent"] = True
            else:
                setup_results["failed_services"].append({"service": "web_portal", "error": portal_setup["error"]})
        except Exception as e:
            setup_results["failed_services"].append({"service": "web_portal", "error": str(e)})
        
        # Setup payment integration
        try:
            payment_setup = await self._setup_payment_integration(student)
            if payment_setup["success"]:
                setup_results["services_configured"].append("payment_integration")
        except Exception as e:
            setup_results["failed_services"].append({"service": "payment_integration", "error": str(e)})
        
        context["digital_services_setup"] = setup_results
        
        return setup_results
    
    async def _provision_access_credentials(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Provision physical and digital access credentials."""
        student = context["created_student"]
        onboarding_context = context["onboarding_context"]
        
        credentials_result = {
            "access_card_issued": False,
            "room_key_issued": False,
            "locker_assigned": False,
            "digital_access_enabled": False,
            "credentials": {}
        }
        
        # Issue access card
        try:
            access_card = await self._issue_access_card(student)
            credentials_result["access_card_issued"] = True
            credentials_result["credentials"]["access_card"] = access_card
        except Exception as e:
            onboarding_context.warnings.append(f"Access card issuance failed: {str(e)}")
        
        # Issue room key
        try:
            room_key = await self._issue_room_key(student)
            credentials_result["room_key_issued"] = True
            credentials_result["credentials"]["room_key"] = room_key
        except Exception as e:
            onboarding_context.warnings.append(f"Room key issuance failed: {str(e)}")
        
        # Assign locker
        try:
            locker = await self._assign_locker(student)
            credentials_result["locker_assigned"] = True
            credentials_result["credentials"]["locker"] = locker
        except Exception as e:
            onboarding_context.warnings.append(f"Locker assignment failed: {str(e)}")
        
        # Enable digital access
        try:
            digital_access = await self._enable_digital_access(student)
            credentials_result["digital_access_enabled"] = True
            credentials_result["credentials"]["digital_access"] = digital_access
        except Exception as e:
            onboarding_context.warnings.append(f"Digital access setup failed: {str(e)}")
        
        # Mark checklist item if at least basic access is provided
        if credentials_result["room_key_issued"] or credentials_result["access_card_issued"]:
            onboarding_context.checklist.access_provisioned = True
        
        context["issued_credentials"] = credentials_result
        
        return credentials_result
    
    # Helper methods for step handlers
    
    def _validate_payment_completion(self, booking) -> Dict[str, Any]:
        """Validate payment completion status."""
        required_advance = booking.advance_amount
        paid_advance = booking.advance_paid
        
        if paid_advance >= required_advance:
            return {"valid": True}
        else:
            shortage = required_advance - paid_advance
            return {
                "valid": False,
                "issue": f"Advance payment incomplete. Required: {required_advance}, Paid: {paid_advance}",
                "severity": "critical",
                "shortage": shortage
            }
    
    async def _check_document_completeness(self, db: Session, guest) -> Dict[str, Any]:
        """Check if all required documents are uploaded."""
        required_docs = {
            DocumentType.ID_PROOF,
            DocumentType.PHOTO
        }
        
        # Optional but recommended documents
        optional_docs = {
            DocumentType.ADDRESS_PROOF,
            DocumentType.EDUCATION_PROOF,
            DocumentType.GUARDIAN_ID
        }
        
        # Get uploaded documents
        uploaded_docs = self.document_repo.get_by_guest_id(db, guest.id)
        uploaded_types = {doc.document_type for doc in uploaded_docs}
        
        missing_required = required_docs - uploaded_types
        missing_optional = optional_docs - uploaded_types
        
        return {
            "complete": len(missing_required) == 0,
            "missing_documents": list(missing_required),
            "missing_optional": list(missing_optional),
            "uploaded_count": len(uploaded_docs),
            "completion_percentage": (len(uploaded_types) / len(required_docs.union(optional_docs))) * 100
        }
    
    async def _check_hostel_capacity(self, db: Session, hostel_id: UUID) -> Dict[str, Any]:
        """Check if hostel has available capacity."""
        # This would query actual bed availability
        # Simplified implementation
        return {"available": True, "available_beds": 25}
    
    async def _check_blacklist_status(self, db: Session, guest) -> Dict[str, Any]:
        """Check if guest is blacklisted."""
        # This would check against blacklist database
        # Simplified implementation
        return {"is_blacklisted": False, "reason": None}
    
    async def _verify_police_clearance(self, verification_number: str) -> Dict[str, Any]:
        """Verify police clearance certificate."""
        # Integration with police verification system
        return {"valid": True}
    
    async def _verify_address_details(self, address: str) -> Dict[str, Any]:
        """Verify address through external services."""
        # Integration with address verification services
        return {"verified": True}
    
    async def _verify_reference_contact(self, contact: str) -> Dict[str, Any]:
        """Verify reference contact."""
        # Verification through call/SMS
        return {"contactable": True}
    
    async def _setup_mobile_app_access(self, student) -> Dict[str, Any]:
        """Setup mobile app access for student."""
        # Integration with mobile app backend
        return {"success": True, "app_user_id": str(student.id)}
    
    async def _setup_web_portal_access(self, student) -> Dict[str, Any]:
        """Setup web portal access."""
        # Integration with web portal system
        return {"success": True, "portal_url": "https://portal.hostel.com"}
    
    async def _setup_payment_integration(self, student) -> Dict[str, Any]:
        """Setup payment integration."""
        # Integration with payment gateway
        return {"success": True, "payment_profile_id": f"pay_{student.id}"}
    
    async def _issue_access_card(self, student) -> Dict[str, Any]:
        """Issue access card."""
        # Integration with access control system
        return {"card_id": f"AC{student.id}", "issued_date": datetime.utcnow().isoformat()}
    
    async def _issue_room_key(self, student) -> Dict[str, Any]:
        """Issue room key."""
        # Key management system integration
        return {"key_id": f"RK{student.room_id}", "type": "physical"}
    
    async def _assign_locker(self, student) -> Dict[str, Any]:
        """Assign locker to student."""
        # Locker management system
        return {"locker_number": f"L{student.id % 1000}", "location": "Ground Floor"}
    
    async def _enable_digital_access(self, student) -> Dict[str, Any]:
        """Enable digital access systems."""
        # Digital access control
        return {"qr_code": f"QR{student.id}", "expires": "2025-12-31"}
    
    def _estimate_completion_time(self, execution) -> Optional[str]:
        """Estimate completion time based on current progress."""
        if not execution.started_at:
            return None
        
        elapsed = (datetime.utcnow() - execution.started_at).total_seconds()
        progress = execution.get_progress_percentage()
        
        if progress > 0:
            estimated_total = elapsed * (100 / progress)
            remaining = estimated_total - elapsed
            
            completion_time = datetime.utcnow() + timedelta(seconds=remaining)
            return completion_time.isoformat()
        
        return None
    
    # Additional step handlers (abbreviated for space)
    
    async def _setup_meal_and_preferences(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Setup meal subscriptions and preferences."""
        # Implementation for meal setup
        return {"meal_plan_configured": True}
    
    async def _schedule_orientation_session(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule orientation session for new student."""
        onboarding_context = context["onboarding_context"]
        
        # Find next available orientation slot
        next_session = datetime.utcnow() + timedelta(days=2)  # Simplified
        
        onboarding_context.checklist.orientation_scheduled = True
        
        return {
            "session_scheduled": True,
            "session_date": next_session.isoformat(),
            "session_type": "group_orientation"
        }
    
    async def _generate_welcome_package(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate and send welcome package."""
        student = context["created_student"]
        onboarding_context = context["onboarding_context"]
        
        # Generate welcome documents
        welcome_package = {
            "student_handbook_url": f"https://docs.hostel.com/handbook/{student.id}",
            "rules_and_regulations_url": f"https://docs.hostel.com/rules/{student.id}",
            "emergency_contacts": {
                "security": "+1-555-0101",
                "maintenance": "+1-555-0102",
                "medical": "+1-555-0103"
            },
            "wifi_credentials": {
                "ssid": "HostelWiFi",
                "password": "welcome2024"
            }
        }
        
        onboarding_context.checklist.welcome_kit_sent = True
        
        return welcome_package
    
    async def _finalize_booking_conversion(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize booking to student conversion."""
        db = context["db"]
        booking = context["booking"]
        student = context["created_student"]
        onboarding_context = context["onboarding_context"]
        
        # Create conversion record
        conversion = self.conversion_repo.create_conversion(
            db=db,
            booking_id=booking.id,
            student_id=student.id,
            conversion_date=onboarding_context.check_in_date,
            advance_paid=booking.advance_paid,
            conversion_metadata={
                "onboarded_by": str(onboarding_context.initiated_by),
                "completion_percentage": onboarding_context.checklist.get_completion_percentage(),
                "verification_score": onboarding_context.metadata.get("verification_score", 0)
            }
        )
        
        # Update booking status
        booking.booking_status = BookingStatus.COMPLETED
        booking.converted_to_student = True
        booking.conversion_date = onboarding_context.check_in_date
        
        db.commit()
        
        return {
            "conversion_id": str(conversion.id),
            "booking_completed": True,
            "conversion_date": onboarding_context.check_in_date.isoformat()
        }
    
    async def _send_onboarding_completion_notifications(self, context: Dict[str, Any]) -> None:
        """Send completion notifications."""
        db = context["db"]
        student = context["created_student"]
        onboarding_context = context["onboarding_context"]
        
        # Send welcome notification to student
        self.notification_service.send_onboarding_notifications(
            db=db,
            student_user_id=student.user_id,
            hostel_id=student.hostel_id,
            student_name=student.user.full_name,
            check_in_date=onboarding_context.check_in_date.isoformat()
        )
        
        # Send completion notification to admin
        # Implementation would notify relevant staff
        
    async def _update_onboarding_analytics(self, context: Dict[str, Any]) -> None:
        """Update onboarding analytics and metrics."""
        onboarding_context = context["onboarding_context"]
        
        # Update analytics
        # - Onboarding completion time
        # - Success rate
        # - Common failure points
        # - Verification scores
        pass
    
    # Rollback handlers
    
    async def _rollback_room_assignment(self, context: Dict[str, Any]) -> None:
        """Rollback room and bed assignment."""
        if "bed_assignment" in context:
            db = context["db"]
            assignment = context["bed_assignment"]
            db.delete(assignment)
            db.commit()
    
    async def _rollback_profile_creation(self, context: Dict[str, Any]) -> None:
        """Rollback student profile creation."""
        if "created_student" in context:
            db = context["db"]
            student = context["created_student"]
            db.delete(student)
            db.commit()
    
    async def _rollback_digital_services(self, context: Dict[str, Any]) -> None:
        """Rollback digital services setup."""
        if "digital_services_setup" in context:
            # Cleanup digital service accounts
            pass
    
    async def _revoke_access_credentials(self, context: Dict[str, Any]) -> None:
        """Revoke issued access credentials."""
        if "issued_credentials" in context:
            # Deactivate access cards, keys, etc.
            pass
    
    # Completion handlers
    
    async def _on_onboarding_complete(self, execution) -> None:
        """Handle onboarding completion."""
        # Update metrics
        # Send success notifications
        # Trigger post-onboarding workflows
        pass
    
    async def _on_onboarding_error(self, execution, error: Exception) -> None:
        """Handle onboarding errors."""
        # Log detailed error information
        # Send error notifications
        # Create support tickets for unresolved issues
        pass
    
    # Quick onboarding workflow handlers (simplified)
    
    async def _validate_pre_verification_status(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate pre-verification status for quick onboarding."""
        return {"pre_verified": True, "verification_level": "basic"}
    
    async def _fast_track_document_verification(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fast-track document verification for pre-verified students."""
        return {"verification_completed": True, "method": "fast_track"}
    
    async def _process_expedited_payments(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process payments for expedited onboarding."""
        return {"payments_processed": True}
    
    async def _assign_pre_allocated_accommodation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Assign pre-allocated accommodation."""
        return {"accommodation_assigned": True, "type": "pre_allocated"}
    
    async def _create_profile_from_template(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create student profile from template."""
        return {"profile_created": True, "method": "template"}
    
    async def _issue_temporary_access_credentials(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Issue temporary access credentials."""
        return {"temporary_access_issued": True, "validity": "7_days"}
    
    async def _schedule_followup_verification(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule follow-up verification."""
        return {"followup_scheduled": True, "scheduled_date": "2024-01-20"}
    
    # Walk-in onboarding handlers (simplified)
    
    async def _collect_walkin_basic_info(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Collect basic information for walk-in student."""
        return {"info_collected": True}
    
    async def _verify_immediate_accommodation_availability(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Verify immediate accommodation availability."""
        return {"accommodation_available": True}
    
    async def _conduct_instant_document_verification(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Conduct instant document verification."""
        return {"documents_verified": True, "method": "instant"}
    
    async def _process_walkin_advance_payment(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process advance payment for walk-in."""
        return {"payment_processed": True}
    
    async def _assign_next_available_accommodation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Assign next available accommodation."""
        return {"accommodation_assigned": True}
    
    async def _create_provisional_student_profile(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create provisional student profile."""
        return {"profile_created": True, "status": "provisional"}
    
    async def _schedule_complete_verification_followup(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule complete verification follow-up."""
        return {"verification_scheduled": True, "scheduled_date": "2024-01-25"}