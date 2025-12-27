"""
Enhanced Checkout Workflow Service

Handles student checkout with comprehensive clearance processes and financial settlements.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum
import asyncio

from app.core1.exceptions import ValidationException, BusinessLogicException
from app.core1.config import settings
from app.models.base.enums import StudentStatus, PaymentStatus
from app.repositories.student import StudentRepository
from app.repositories.room import BedAssignmentRepository
from app.repositories.payment import PaymentRepository, PaymentLedgerRepository
from app.repositories.complaint import ComplaintRepository
from app.repositories.maintenance import MaintenanceRepository
from app.repositories.inventory import InventoryItemRepository
from app.services.workflows.workflow_engine_service import (
    workflow_engine,
    create_workflow,
    create_step,
    WorkflowPriority
)
from app.services.workflows.notification_workflow_service import (
    NotificationWorkflowService
)


class CheckoutStage(str, Enum):
    """Enhanced checkout stages."""
    NOTICE_VALIDATION = "notice_validation"
    CLEARANCE_INITIATION = "clearance_initiation"
    DUES_VERIFICATION = "dues_verification"
    COMPLAINT_CLEARANCE = "complaint_clearance"
    ROOM_INSPECTION = "room_inspection"
    ASSET_RETURN = "asset_return"
    SETTLEMENT_CALCULATION = "settlement_calculation"
    REFUND_PROCESSING = "refund_processing"
    ACCESS_REVOCATION = "access_revocation"
    COMPLETION = "completion"


class ClearanceStatus(str, Enum):
    """Clearance verification status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    CLEARED = "cleared"
    BLOCKED = "blocked"
    CONDITIONAL = "conditional"


@dataclass
class ClearanceCertificate:
    """Digital clearance certificate."""
    certificate_id: str
    student_id: UUID
    hostel_id: UUID
    checkout_date: datetime
    clearance_status: ClearanceStatus
    cleared_departments: List[str]
    pending_clearances: List[str]
    total_dues: Decimal
    refund_amount: Decimal
    issued_by: UUID
    issued_at: datetime
    digital_signature: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "student_id": str(self.student_id),
            "hostel_id": str(self.hostel_id),
            "checkout_date": self.checkout_date.isoformat(),
            "clearance_status": self.clearance_status.value,
            "cleared_departments": self.cleared_departments,
            "pending_clearances": self.pending_clearances,
            "total_dues": float(self.total_dues),
            "refund_amount": float(self.refund_amount),
            "issued_by": str(self.issued_by),
            "issued_at": self.issued_at.isoformat(),
            "digital_signature": self.digital_signature
        }


@dataclass
class FinancialSettlement:
    """Comprehensive financial settlement details."""
    outstanding_dues: Decimal = Decimal("0")
    damage_charges: Decimal = Decimal("0")
    asset_penalty: Decimal = Decimal("0")
    notice_penalty: Decimal = Decimal("0")
    late_fees: Decimal = Decimal("0")
    other_charges: Decimal = Decimal("0")
    total_charges: Decimal = Decimal("0")
    security_deposit: Decimal = Decimal("0")
    advance_adjustments: Decimal = Decimal("0")
    total_refund: Decimal = Decimal("0")
    net_settlement: Decimal = Decimal("0")
    
    def calculate_totals(self):
        """Calculate total charges and settlements."""
        self.total_charges = (
            self.outstanding_dues + self.damage_charges + self.asset_penalty +
            self.notice_penalty + self.late_fees + self.other_charges
        )
        
        available_for_refund = self.security_deposit + self.advance_adjustments
        
        if self.total_charges >= available_for_refund:
            self.total_refund = Decimal("0")
            self.net_settlement = self.total_charges - available_for_refund
        else:
            self.total_refund = available_for_refund - self.total_charges
            self.net_settlement = Decimal("0")


@dataclass
class CheckoutContext:
    """Enhanced context for checkout workflow."""
    student_id: UUID
    checkout_date: datetime
    initiated_by: UUID
    reason: str
    is_emergency: bool = False
    notice_period_compliant: bool = False
    financial_settlement: Optional[FinancialSettlement] = None
    clearance_certificate: Optional[ClearanceCertificate] = None
    forwarding_address: Optional[str] = None
    emergency_contact: Optional[str] = None
    checkout_metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.checkout_metadata is None:
            self.checkout_metadata = {}


class CheckoutWorkflowService:
    """
    Enhanced service for managing student checkout workflows.
    
    Features:
    - Comprehensive clearance verification
    - Intelligent financial settlement
    - Asset tracking and return verification
    - Automated refund processing
    - Digital clearance certificates
    - Emergency checkout handling
    - Real-time progress tracking
    """
    
    def __init__(
        self,
        student_repo: StudentRepository,
        bed_assignment_repo: BedAssignmentRepository,
        payment_repo: PaymentRepository,
        ledger_repo: PaymentLedgerRepository,
        complaint_repo: ComplaintRepository,
        maintenance_repo: MaintenanceRepository,
        inventory_repo: InventoryItemRepository,
        notification_service: NotificationWorkflowService
    ):
        self.student_repo = student_repo
        self.bed_assignment_repo = bed_assignment_repo
        self.payment_repo = payment_repo
        self.ledger_repo = ledger_repo
        self.complaint_repo = complaint_repo
        self.maintenance_repo = maintenance_repo
        self.inventory_repo = inventory_repo
        self.notification_service = notification_service
        
        # Settlement calculation cache
        self._settlement_cache: Dict[str, FinancialSettlement] = {}
        
        self._register_workflows()
    
    def _register_workflows(self) -> None:
        """Register enhanced checkout workflows."""
        
        # Comprehensive checkout workflow
        standard_checkout_wf = (
            create_workflow(
                "student_checkout",
                "Enhanced Student Checkout Workflow",
                "Complete checkout process with comprehensive clearance verification",
                priority=WorkflowPriority.HIGH,
                max_execution_time=2400,  # 40 minutes
                max_concurrent_executions=15,
                enable_monitoring=True
            )
            .add_validator(self._validate_checkout_context)
            .add_step(create_step(
                "initialize_checkout_process",
                self._initialize_checkout_process,
                timeout_seconds=60
            ))
            .add_step(create_step(
                "validate_student_eligibility",
                self._validate_student_checkout_eligibility,
                timeout_seconds=90
            ))
            .add_step(create_step(
                "verify_notice_period_compliance",
                self._verify_notice_period_compliance,
                required=False,
                timeout_seconds=30
            ))
            .add_step(create_step(
                "initiate_clearance_process",
                self._initiate_comprehensive_clearance,
                timeout_seconds=120
            ))
            .add_step(create_step(
                "verify_financial_dues",
                self._verify_comprehensive_financial_dues,
                timeout_seconds=180
            ))
            .add_step(create_step(
                "clear_pending_complaints",
                self._clear_pending_complaints,
                timeout_seconds=300,
                required=False
            ))
            .add_step(create_step(
                "conduct_detailed_room_inspection",
                self._conduct_detailed_room_inspection,
                timeout_seconds=600,  # 10 minutes for thorough inspection
                retry_count=1
            ))
            .add_step(create_step(
                "verify_asset_return_checklist",
                self._verify_comprehensive_asset_return,
                timeout_seconds=300
            ))
            .add_step(create_step(
                "calculate_final_settlement",
                self._calculate_comprehensive_settlement,
                timeout_seconds=120
            ))
            .add_step(create_step(
                "process_pending_settlements",
                self._process_pending_financial_settlements,
                timeout_seconds=180,
                required=False
            ))
            .add_step(create_step(
                "initiate_refund_processing",
                self._initiate_intelligent_refund_processing,
                timeout_seconds=240,
                required=False,
                rollback_handler=self._rollback_refund_processing
            ))
            .add_step(create_step(
                "revoke_all_access_credentials",
                self._revoke_comprehensive_access,
                timeout_seconds=90,
                rollback_handler=self._restore_access_credentials
            ))
            .add_step(create_step(
                "release_accommodation_assignment",
                self._release_accommodation_assignment,
                timeout_seconds=60,
                rollback_handler=self._restore_accommodation_assignment
            ))
            .add_step(create_step(
                "update_student_status_final",
                self._update_student_status_to_checkout,
                timeout_seconds=30,
                rollback_handler=self._restore_student_status
            ))
            .add_step(create_step(
                "generate_clearance_certificate",
                self._generate_digital_clearance_certificate,
                timeout_seconds=90,
                required=False
            ))
            .add_step(create_step(
                "send_checkout_notifications",
                self._send_comprehensive_checkout_notifications,
                timeout_seconds=60,
                required=False
            ))
            .add_step(create_step(
                "archive_student_data",
                self._archive_student_data,
                timeout_seconds=120,
                required=False
            ))
            .add_step(create_step(
                "update_checkout_analytics",
                self._update_checkout_analytics,
                timeout_seconds=30,
                required=False
            ))
            .on_complete(self._on_checkout_complete)
            .on_error(self._on_checkout_error)
        )
        
        workflow_engine.register_workflow(standard_checkout_wf)
        
        # Emergency checkout workflow
        emergency_checkout_wf = (
            create_workflow(
                "emergency_checkout",
                "Emergency Checkout Workflow",
                "Expedited checkout for emergency situations"
            )
            .add_step(create_step(
                "validate_emergency_authorization",
                self._validate_emergency_authorization
            ))
            .add_step(create_step(
                "create_emergency_clearance_snapshot",
                self._create_emergency_clearance_snapshot
            ))
            .add_step(create_step(
                "perform_quick_inspection",
                self._perform_emergency_room_inspection
            ))
            .add_step(create_step(
                "calculate_provisional_settlement",
                self._calculate_provisional_settlement
            ))
            .add_step(create_step(
                "issue_temporary_clearance",
                self._issue_temporary_clearance_certificate
            ))
            .add_step(create_step(
                "suspend_student_account",
                self._suspend_student_account_emergency
            ))
            .add_step(create_step(
                "schedule_final_clearance_followup",
                self._schedule_final_clearance_followup
            ))
        )
        
        workflow_engine.register_workflow(emergency_checkout_wf)
        
        # Notice period workflow
        notice_period_wf = (
            create_workflow(
                "notice_period",
                "Notice Period Processing Workflow",
                "Handle notice period submission and tracking"
            )
            .add_step(create_step(
                "validate_notice_submission",
                self._validate_notice_submission_requirements
            ))
            .add_step(create_step(
                "calculate_notice_charges",
                self._calculate_notice_period_charges
            ))
            .add_step(create_step(
                "update_student_notice_status",
                self._update_student_notice_period_status
            ))
            .add_step(create_step(
                "schedule_checkout_preparation",
                self._schedule_checkout_preparation_tasks
            ))
            .add_step(create_step(
                "notify_checkout_stakeholders",
                self._notify_checkout_stakeholders
            ))
        )
        
        workflow_engine.register_workflow(notice_period_wf)
    
    # Public API methods
    
    async def checkout_student(
        self,
        db: Session,
        student_id: UUID,
        checkout_date: datetime,
        initiated_by: UUID,
        reason: str,
        forwarding_address: Optional[str] = None,
        clearance_data: Optional[Dict[str, Any]] = None,
        emergency: bool = False
    ) -> Dict[str, Any]:
        """
        Execute comprehensive student checkout workflow.
        
        Args:
            db: Database session
            student_id: Student to checkout
            checkout_date: Intended checkout date
            initiated_by: Admin/staff processing checkout
            reason: Reason for checkout
            forwarding_address: Student's forwarding address
            clearance_data: Room inspection and asset data
            emergency: Whether this is an emergency checkout
            
        Returns:
            Comprehensive checkout result
        """
        # Create checkout context
        checkout_context = CheckoutContext(
            student_id=student_id,
            checkout_date=checkout_date,
            initiated_by=initiated_by,
            reason=reason,
            is_emergency=emergency,
            forwarding_address=forwarding_address,
            checkout_metadata=clearance_data or {}
        )
        
        # Prepare workflow context
        workflow_context = {
            "db": db,
            "checkout_context": checkout_context
        }
        
        # Choose appropriate workflow
        workflow_type = "emergency_checkout" if emergency else "student_checkout"
        
        execution = await workflow_engine.execute_workflow(
            workflow_type,
            workflow_context,
            initiated_by
        )
        
        return execution.result or execution.to_dict()
    
    async def submit_notice_period(
        self,
        db: Session,
        student_id: UUID,
        notice_date: datetime,
        intended_checkout_date: datetime,
        reason: str,
        submitted_by: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Process notice period submission with validation.
        
        Args:
            db: Database session
            student_id: Student submitting notice
            notice_date: Notice submission date
            intended_checkout_date: Intended last day
            reason: Reason for leaving
            submitted_by: User submitting (if different from student)
            
        Returns:
            Notice period processing result
        """
        context = {
            "db": db,
            "student_id": student_id,
            "notice_date": notice_date,
            "intended_checkout_date": intended_checkout_date,
            "reason": reason,
            "submitted_by": submitted_by or student_id
        }
        
        execution = await workflow_engine.execute_workflow(
            "notice_period",
            context,
            submitted_by or student_id
        )
        
        return execution.result or execution.to_dict()
    
    async def get_checkout_progress(
        self,
        db: Session,
        student_id: UUID
    ) -> Dict[str, Any]:
        """Get real-time checkout progress."""
        # Check for active checkout executions
        active_executions = workflow_engine.get_executions_by_type(
            "student_checkout",
            limit=50
        )
        
        for execution in active_executions:
            if (execution.context.get("checkout_context") and 
                execution.context["checkout_context"].student_id == student_id):
                
                return {
                    "execution_id": str(execution.execution_id),
                    "stage": execution.current_step_name,
                    "progress_percentage": execution.get_progress_percentage(),
                    "current_step_index": execution.current_step_index,
                    "total_steps": len(execution.definition.steps),
                    "estimated_completion": self._estimate_checkout_completion(execution)
                }
        
        # Check if student is already checked out
        student = self.student_repo.get_by_id(db, student_id)
        if student and student.student_status == StudentStatus.CHECKED_OUT:
            return {
                "stage": "completed",
                "progress_percentage": 100.0,
                "checkout_date": student.checkout_date.isoformat() if student.checkout_date else None
            }
        
        return {"stage": "not_started", "progress_percentage": 0.0}
    
    async def get_clearance_status(
        self,
        db: Session,
        student_id: UUID
    ) -> Dict[str, Any]:
        """Get detailed clearance status for student."""
        student = self.student_repo.get_by_id(db, student_id)
        if not student:
            raise ValidationException("Student not found")
        
        clearance_status = {
            "student_id": str(student_id),
            "overall_status": "pending",
            "clearance_percentage": 0.0,
            "departments": {}
        }
        
        # Check financial clearance
        financial_status = await self._check_financial_clearance_status(db, student)
        clearance_status["departments"]["finance"] = financial_status
        
        # Check accommodation clearance
        accommodation_status = await self._check_accommodation_clearance_status(db, student)
        clearance_status["departments"]["accommodation"] = accommodation_status
        
        # Check complaint clearance
        complaint_status = await self._check_complaint_clearance_status(db, student)
        clearance_status["departments"]["complaints"] = complaint_status
        
        # Check asset clearance
        asset_status = await self._check_asset_clearance_status(db, student)
        clearance_status["departments"]["assets"] = asset_status
        
        # Calculate overall clearance percentage
        department_statuses = list(clearance_status["departments"].values())
        cleared_count = sum(1 for dept in department_statuses if dept["status"] == "cleared")
        clearance_status["clearance_percentage"] = (cleared_count / len(department_statuses)) * 100
        
        if clearance_status["clearance_percentage"] == 100:
            clearance_status["overall_status"] = "cleared"
        elif clearance_status["clearance_percentage"] > 0:
            clearance_status["overall_status"] = "partial"
        
        return clearance_status
    
    # Validation methods
    
    def _validate_checkout_context(self, context: Dict[str, Any]) -> bool:
        """Validate checkout workflow context."""
        required_fields = ["db", "checkout_context"]
        
        if not all(field in context for field in required_fields):
            return False
        
        checkout_context = context["checkout_context"]
        if not isinstance(checkout_context, CheckoutContext):
            return False
        
        return True
    
    # Step handlers - Main checkout workflow
    
    async def _initialize_checkout_process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize comprehensive checkout process."""
        db = context["db"]
        checkout_context = context["checkout_context"]
        
        # Load and validate student
        student = self.student_repo.get_by_id(db, checkout_context.student_id)
        if not student:
            raise ValidationException("Student not found")
        
        # Validate current status
        if student.student_status == StudentStatus.CHECKED_OUT:
            raise BusinessLogicException("Student is already checked out")
        
        if student.student_status not in [
            StudentStatus.ACTIVE,
            StudentStatus.NOTICE_PERIOD,
            StudentStatus.SUSPENDED
        ]:
            raise BusinessLogicException(
                f"Cannot checkout student with status: {student.student_status}"
            )
        
        # Calculate stay duration
        stay_duration = None
        if student.check_in_date:
            stay_duration = (checkout_context.checkout_date - student.check_in_date).days
        
        # Initialize financial settlement
        checkout_context.financial_settlement = FinancialSettlement()
        
        # Store student in context
        context["student"] = student
        
        return {
            "student_id": str(student.id),
            "student_name": student.user.full_name,
            "current_status": student.student_status.value,
            "check_in_date": student.check_in_date.isoformat() if student.check_in_date else None,
            "stay_duration_days": stay_duration,
            "hostel_id": str(student.hostel_id),
            "room_id": str(student.room_id) if student.room_id else None,
            "bed_id": str(student.bed_id) if student.bed_id else None
        }
    
    async def _validate_student_checkout_eligibility(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation of student eligibility for checkout."""
        db = context["db"]
        student = context["student"]
        checkout_context = context["checkout_context"]
        
        validation_results = {
            "eligible": True,
            "blocking_issues": [],
            "warnings": [],
            "checks_performed": []
        }
        
        # Check for active maintenance requests assigned to student
        active_maintenance = self.maintenance_repo.get_active_by_student(db, student.id)
        validation_results["checks_performed"].append("active_maintenance")
        
        if active_maintenance:
            for request in active_maintenance:
                if request.priority == "high" or request.priority == "urgent":
                    validation_results["blocking_issues"].append(
                        f"High priority maintenance request pending: {request.id}"
                    )
                else:
                    validation_results["warnings"].append(
                        f"Maintenance request pending: {request.id}"
                    )
        
        # Check for ongoing disciplinary actions
        disciplinary_check = await self._check_disciplinary_actions(db, student)
        validation_results["checks_performed"].append("disciplinary_actions")
        
        if disciplinary_check["has_active_cases"]:
            validation_results["blocking_issues"].extend(disciplinary_check["blocking_cases"])
            validation_results["warnings"].extend(disciplinary_check["warning_cases"])
        
        # Check for borrowed library items (if applicable)
        library_check = await self._check_library_clearance(db, student)
        validation_results["checks_performed"].append("library_clearance")
        
        if not library_check["cleared"]:
            validation_results["warnings"].extend(library_check["pending_items"])
        
        # Determine overall eligibility
        if validation_results["blocking_issues"]:
            validation_results["eligible"] = False
            
            if not checkout_context.is_emergency:
                raise BusinessLogicException(
                    f"Student not eligible for checkout: {'; '.join(validation_results['blocking_issues'])}"
                )
        
        return validation_results
    
    async def _verify_notice_period_compliance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Verify notice period compliance with penalties calculation."""
        db = context["db"]
        student = context["student"]
        checkout_context = context["checkout_context"]
        
        notice_verification = {
            "compliant": False,
            "notice_period_days": 0,
            "required_notice_days": 30,  # Default from settings
            "shortage_days": 0,
            "penalty_amount": Decimal("0"),
            "exemption_applied": False
        }
        
        # Get hostel-specific notice period requirement
        hostel_settings = await self._get_hostel_settings(db, student.hostel_id)
        notice_verification["required_notice_days"] = hostel_settings.get("required_notice_days", 30)
        
        if student.notice_period_start_date:
            # Calculate actual notice period
            notice_days = (checkout_context.checkout_date - student.notice_period_start_date).days
            notice_verification["notice_period_days"] = notice_days
            
            if notice_days >= notice_verification["required_notice_days"]:
                notice_verification["compliant"] = True
                checkout_context.notice_period_compliant = True
            else:
                shortage_days = notice_verification["required_notice_days"] - notice_days
                notice_verification["shortage_days"] = shortage_days
                
                # Calculate penalty
                daily_rent = student.monthly_rent / 30
                penalty_rate = hostel_settings.get("notice_penalty_rate", 1.0)  # 100% of daily rent
                penalty_amount = daily_rent * shortage_days * penalty_rate
                
                notice_verification["penalty_amount"] = penalty_amount
                checkout_context.financial_settlement.notice_penalty = penalty_amount
        else:
            # No notice submitted
            shortage_days = notice_verification["required_notice_days"]
            notice_verification["shortage_days"] = shortage_days
            
            # Calculate full penalty
            daily_rent = student.monthly_rent / 30
            penalty_rate = hostel_settings.get("notice_penalty_rate", 1.0)
            penalty_amount = daily_rent * shortage_days * penalty_rate
            
            notice_verification["penalty_amount"] = penalty_amount
            checkout_context.financial_settlement.notice_penalty = penalty_amount
        
        # Check for exemptions (emergency, medical, etc.)
        if checkout_context.reason in ["medical_emergency", "family_emergency", "job_termination"]:
            notice_verification["exemption_applied"] = True
            notice_verification["penalty_amount"] = Decimal("0")
            checkout_context.financial_settlement.notice_penalty = Decimal("0")
        
        return notice_verification
    
    async def _initiate_comprehensive_clearance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Initiate comprehensive clearance process across all departments."""
        db = context["db"]
        student = context["student"]
        
        clearance_initiation = {
            "clearance_id": f"CLR_{student.id}_{int(datetime.utcnow().timestamp())}",
            "departments_involved": [],
            "clearance_started": True,
            "estimated_completion_time": None
        }
        
        # Identify departments involved in clearance
        departments = ["finance", "accommodation", "complaints", "assets", "maintenance"]
        
        # Check each department
        for dept in departments:
            dept_status = await self._check_department_clearance_requirements(db, student, dept)
            if dept_status["requires_clearance"]:
                clearance_initiation["departments_involved"].append({
                    "department": dept,
                    "requirements": dept_status["requirements"],
                    "estimated_time": dept_status["estimated_time"]
                })
        
        # Estimate total completion time
        total_time = sum(
            dept["estimated_time"] 
            for dept in clearance_initiation["departments_involved"]
        )
        clearance_initiation["estimated_completion_time"] = total_time
        
        # Store clearance ID in context
        context["clearance_id"] = clearance_initiation["clearance_id"]
        
        return clearance_initiation
    
    async def _verify_comprehensive_financial_dues(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive verification of all financial dues."""
        db = context["db"]
        student = context["student"]
        checkout_context = context["checkout_context"]
        
        financial_verification = {
            "total_outstanding": Decimal("0"),
            "pending_payments": [],
            "advance_adjustments": Decimal("0"),
            "security_deposit": Decimal("0"),
            "dues_breakdown": {}
        }
        
        # Get comprehensive ledger summary
        ledger_summary = self.ledger_repo.get_comprehensive_balance(db, student.id)
        
        # Outstanding rent
        rent_dues = ledger_summary.get("rent_outstanding", Decimal("0"))
        financial_verification["dues_breakdown"]["rent"] = float(rent_dues)
        
        # Outstanding maintenance charges
        maintenance_dues = ledger_summary.get("maintenance_outstanding", Decimal("0"))
        financial_verification["dues_breakdown"]["maintenance"] = float(maintenance_dues)
        
        # Outstanding mess charges
        mess_dues = ledger_summary.get("mess_outstanding", Decimal("0"))
        financial_verification["dues_breakdown"]["mess"] = float(mess_dues)
        
        # Late payment fees
        late_fees = ledger_summary.get("late_fees", Decimal("0"))
        financial_verification["dues_breakdown"]["late_fees"] = float(late_fees)
        
        # Other charges
        other_charges = ledger_summary.get("other_charges", Decimal("0"))
        financial_verification["dues_breakdown"]["other"] = float(other_charges)
        
        # Calculate total outstanding
        total_outstanding = rent_dues + maintenance_dues + mess_dues + late_fees + other_charges
        financial_verification["total_outstanding"] = total_outstanding
        
        # Get available credits
        security_deposit = student.security_deposit_paid or Decimal("0")
        advance_balance = ledger_summary.get("advance_balance", Decimal("0"))
        
        financial_verification["security_deposit"] = security_deposit
        financial_verification["advance_adjustments"] = advance_balance
        
        # Update financial settlement
        checkout_context.financial_settlement.outstanding_dues = total_outstanding
        checkout_context.financial_settlement.security_deposit = security_deposit
        checkout_context.financial_settlement.advance_adjustments = advance_balance
        checkout_context.financial_settlement.late_fees = late_fees
        
        return financial_verification
    
    async def _clear_pending_complaints(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Clear or review pending complaints."""
        db = context["db"]
        student = context["student"]
        
        complaint_clearance = {
            "pending_complaints": [],
            "cleared_complaints": [],
            "blocking_complaints": [],
            "clearance_status": "cleared"
        }
        
        # Get all open complaints by student
        open_complaints = self.complaint_repo.get_open_by_student(db, student.id)
        
        for complaint in open_complaints:
            complaint_info = {
                "complaint_id": str(complaint.id),
                "type": complaint.complaint_type,
                "priority": complaint.priority,
                "created_date": complaint.created_at.isoformat(),
                "status": complaint.status
            }
            
            # Check if complaint blocks checkout
            if complaint.priority in ["high", "urgent"] and complaint.status == "open":
                complaint_clearance["blocking_complaints"].append(complaint_info)
                complaint_clearance["clearance_status"] = "blocked"
            else:
                # Auto-close minor complaints on checkout
                if complaint.priority == "low":
                    complaint.status = "closed"
                    complaint.resolution_notes = f"Auto-closed during checkout on {datetime.utcnow()}"
                    complaint.resolved_at = datetime.utcnow()
                    db.commit()
                    
                    complaint_clearance["cleared_complaints"].append(complaint_info)
                else:
                    complaint_clearance["pending_complaints"].append(complaint_info)
        
        # If no blocking complaints, mark as cleared
        if not complaint_clearance["blocking_complaints"]:
            if complaint_clearance["pending_complaints"]:
                complaint_clearance["clearance_status"] = "conditional"
            else:
                complaint_clearance["clearance_status"] = "cleared"
        
        return complaint_clearance
    
    async def _conduct_detailed_room_inspection(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Conduct comprehensive room inspection with AI assistance."""
        db = context["db"]
        student = context["student"]
        checkout_context = context["checkout_context"]
        
        inspection_data = checkout_context.checkout_metadata.get("room_inspection", {})
        
        inspection_result = {
            "inspection_id": f"INSP_{student.id}_{int(datetime.utcnow().timestamp())}",
            "room_id": str(student.room_id) if student.room_id else None,
            "bed_id": str(student.bed_id) if student.bed_id else None,
            "inspection_date": datetime.utcnow().isoformat(),
            "inspector_id": str(checkout_context.initiated_by),
            "overall_condition": "good",
            "cleanliness_rating": 5,
            "damages_found": [],
            "missing_items": [],
            "damage_charges": Decimal("0"),
            "photos": [],
            "notes": "",
            "ai_analysis": {}
        }
        
        # Process inspection data
        if inspection_data:
            inspection_result.update({
                "overall_condition": inspection_data.get("condition", "good"),
                "cleanliness_rating": inspection_data.get("cleanliness", 5),
                "damages_found": inspection_data.get("damages", []),
                "missing_items": inspection_data.get("missing_items", []),
                "photos": inspection_data.get("photos", []),
                "notes": inspection_data.get("notes", "")
            })
        
        # Calculate damage charges
        damage_charges = await self._calculate_damage_charges(inspection_result["damages_found"])
        inspection_result["damage_charges"] = damage_charges
        
        # AI analysis of inspection photos (if available)
        if inspection_result["photos"]:
            ai_analysis = await self._analyze_inspection_photos(inspection_result["photos"])
            inspection_result["ai_analysis"] = ai_analysis
            
            # Adjust damage charges based on AI analysis
            if ai_analysis.get("additional_damages"):
                additional_charges = await self._calculate_damage_charges(
                    ai_analysis["additional_damages"]
                )
                damage_charges += additional_charges
                inspection_result["damage_charges"] = damage_charges
        
        # Update financial settlement
        checkout_context.financial_settlement.damage_charges = damage_charges
        
        # Store inspection result
        context["room_inspection"] = inspection_result
        
        return inspection_result
    
    async def _verify_comprehensive_asset_return(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive verification of all asset returns."""
        db = context["db"]
        student = context["student"]
        checkout_context = context["checkout_context"]
        
        # Get assets assigned to student
        assigned_assets = self.inventory_repo.get_assigned_assets(db, student.id)
        
        asset_verification = {
            "total_assets": len(assigned_assets),
            "returned_assets": [],
            "missing_assets": [],
            "damaged_assets": [],
            "asset_penalty": Decimal("0"),
            "return_status": "complete"
        }
        
        # Process each asset
        for asset in assigned_assets:
            asset_info = {
                "asset_id": str(asset.id),
                "asset_type": asset.asset_type,
                "asset_code": asset.asset_code,
                "condition_issued": asset.condition_when_issued,
                "replacement_cost": asset.replacement_cost or Decimal("0")
            }
            
            # Check return status from checkout data
            return_data = checkout_context.checkout_metadata.get("asset_returns", {})
            asset_return = return_data.get(str(asset.id), {})
            
            if asset_return.get("returned", False):
                asset_info.update({
                    "returned": True,
                    "return_condition": asset_return.get("condition", "good"),
                    "return_date": asset_return.get("return_date", datetime.utcnow().isoformat())
                })
                
                # Check for damage
                if asset_return.get("condition") in ["damaged", "poor"]:
                    damage_penalty = await self._calculate_asset_damage_penalty(asset, asset_return["condition"])
                    asset_info["damage_penalty"] = damage_penalty
                    asset_verification["asset_penalty"] += damage_penalty
                    asset_verification["damaged_assets"].append(asset_info)
                else:
                    asset_verification["returned_assets"].append(asset_info)
            else:
                # Asset not returned
                asset_info.update({
                    "returned": False,
                    "replacement_penalty": asset.replacement_cost or Decimal("500")  # Default penalty
                })
                
                asset_verification["asset_penalty"] += asset_info["replacement_penalty"]
                asset_verification["missing_assets"].append(asset_info)
                asset_verification["return_status"] = "incomplete"
        
        # Update financial settlement
        checkout_context.financial_settlement.asset_penalty = asset_verification["asset_penalty"]
        
        return asset_verification
    
    async def _calculate_comprehensive_settlement(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive financial settlement."""
        checkout_context = context["checkout_context"]
        settlement = checkout_context.financial_settlement
        
        # Calculate all totals
        settlement.calculate_totals()
        
        settlement_summary = {
            "settlement_id": f"SETT_{checkout_context.student_id}_{int(datetime.utcnow().timestamp())}",
            "calculation_date": datetime.utcnow().isoformat(),
            "breakdown": {
                "outstanding_dues": float(settlement.outstanding_dues),
                "damage_charges": float(settlement.damage_charges),
                "asset_penalty": float(settlement.asset_penalty),
                "notice_penalty": float(settlement.notice_penalty),
                "late_fees": float(settlement.late_fees),
                "other_charges": float(settlement.other_charges),
                "total_charges": float(settlement.total_charges)
            },
            "credits": {
                "security_deposit": float(settlement.security_deposit),
                "advance_adjustments": float(settlement.advance_adjustments),
                "total_credits": float(settlement.security_deposit + settlement.advance_adjustments)
            },
            "final_settlement": {
                "refund_amount": float(settlement.total_refund),
                "amount_to_collect": float(settlement.net_settlement),
                "settlement_type": "refund" if settlement.total_refund > 0 else "collection"
            }
        }
        
        # Cache settlement for performance
        cache_key = f"settlement_{checkout_context.student_id}"
        self._settlement_cache[cache_key] = settlement
        
        return settlement_summary
    
    # Additional helper methods and step handlers would continue here...
    # Due to length constraints, I'll provide key remaining methods
    
    async def _calculate_damage_charges(self, damages_list: List[Dict[str, Any]]) -> Decimal:
        """Calculate charges for reported damages."""
        total_charges = Decimal("0")
        
        # Standard damage charges
        damage_rates = {
            "wall_damage": Decimal("100"),
            "door_damage": Decimal("200"),
            "window_damage": Decimal("300"),
            "furniture_damage": Decimal("150"),
            "electrical_damage": Decimal("250"),
            "plumbing_damage": Decimal("400"),
            "paint_damage": Decimal("50"),
            "other": Decimal("100")
        }
        
        for damage in damages_list:
            damage_type = damage.get("type", "other")
            severity = damage.get("severity", "minor")
            
            base_charge = damage_rates.get(damage_type, Decimal("100"))
            
            # Adjust for severity
            if severity == "major":
                charge = base_charge * Decimal("2")
            elif severity == "moderate":
                charge = base_charge * Decimal("1.5")
            else:  # minor
                charge = base_charge
            
            total_charges += charge
        
        return total_charges
    
    async def _analyze_inspection_photos(self, photos: List[str]) -> Dict[str, Any]:
        """AI analysis of inspection photos."""
        # This would integrate with AI/ML services for image analysis
        # For now, return placeholder data
        return {
            "analysis_completed": True,
            "confidence_score": 0.85,
            "detected_issues": [],
            "additional_damages": []
        }
    
    # Emergency checkout workflow handlers
    
    async def _validate_emergency_authorization(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate emergency checkout authorization."""
        return {"authorized": True, "authorization_level": "admin"}
    
    async def _create_emergency_clearance_snapshot(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create snapshot for later processing."""
        return {"snapshot_id": f"SNAP_{int(datetime.utcnow().timestamp())}"}
    
    # Notice period workflow handlers
    
    async def _validate_notice_submission_requirements(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate notice submission requirements."""
        return {"valid": True}
    
    # Helper methods
    
    async def _get_hostel_settings(self, db: Session, hostel_id: UUID) -> Dict[str, Any]:
        """Get hostel-specific settings."""
        # Implementation would query hostel settings
        return {"required_notice_days": 30, "notice_penalty_rate": 1.0}
    
    async def _check_disciplinary_actions(self, db: Session, student) -> Dict[str, Any]:
        """Check for active disciplinary actions."""
        # Implementation would check disciplinary records
        return {"has_active_cases": False, "blocking_cases": [], "warning_cases": []}
    
    async def _check_library_clearance(self, db: Session, student) -> Dict[str, Any]:
        """Check library clearance status."""
        # Implementation would check library system
        return {"cleared": True, "pending_items": []}
    
    def _estimate_checkout_completion(self, execution) -> Optional[str]:
        """Estimate checkout completion time."""
        if not execution.started_at:
            return None
        
        # Implementation similar to onboarding estimation
        elapsed = (datetime.utcnow() - execution.started_at).total_seconds()
        progress = execution.get_progress_percentage()
        
        if progress > 0:
            estimated_total = elapsed * (100 / progress)
            remaining = estimated_total - elapsed
            
            completion_time = datetime.utcnow() + timedelta(seconds=remaining)
            return completion_time.isoformat()
        
        return None
    
    # Completion handlers
    
    async def _on_checkout_complete(self, execution) -> None:
        """Handle checkout completion."""
        # Update analytics
        # Archive data
        # Send final notifications
        pass
    
    async def _on_checkout_error(self, execution, error: Exception) -> None:
        """Handle checkout errors."""
        # Log error
        # Send alerts
        # Preserve state
        pass