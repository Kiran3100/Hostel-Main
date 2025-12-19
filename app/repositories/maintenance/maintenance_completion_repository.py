# app/repositories/maintenance/maintenance_completion_repository.py
"""
Maintenance Completion Repository.

Completion tracking with quality checks, material usage,
and certification management.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.maintenance import (
    MaintenanceCompletion,
    MaintenanceMaterial,
    MaintenanceQualityCheck,
    MaintenanceCertificate,
    MaintenanceRequest,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginatedResult


class MaintenanceCompletionRepository(BaseRepository[MaintenanceCompletion]):
    """
    Repository for maintenance completion operations.
    
    Manages completion records, quality checks, materials,
    and certification with comprehensive tracking.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with session."""
        super().__init__(MaintenanceCompletion, session)
    
    # ============================================================================
    # CREATE OPERATIONS
    # ============================================================================
    
    def create_completion(
        self,
        maintenance_request_id: UUID,
        completed_by: UUID,
        work_notes: str,
        labor_hours: Decimal,
        materials_cost: Decimal = Decimal("0.00"),
        labor_cost: Decimal = Decimal("0.00"),
        vendor_charges: Decimal = Decimal("0.00"),
        other_costs: Decimal = Decimal("0.00"),
        actual_start_date: Optional[datetime] = None,
        actual_completion_date: Optional[datetime] = None,
        work_summary: Optional[str] = None,
        labor_rate_per_hour: Optional[Decimal] = None,
        number_of_workers: int = 1,
        cost_breakdown: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> MaintenanceCompletion:
        """
        Create maintenance completion record.
        
        Args:
            maintenance_request_id: Request identifier
            completed_by: User who completed work
            work_notes: Detailed work notes
            labor_hours: Total labor hours
            materials_cost: Materials cost
            labor_cost: Labor cost
            vendor_charges: Vendor charges
            other_costs: Other costs
            actual_start_date: Actual start date
            actual_completion_date: Actual completion date
            work_summary: Brief work summary
            labor_rate_per_hour: Labor rate
            number_of_workers: Number of workers
            cost_breakdown: Detailed cost breakdown
            **kwargs: Additional completion attributes
            
        Returns:
            Created completion record
        """
        # Calculate total cost
        actual_cost = (
            materials_cost + labor_cost + vendor_charges + other_costs
        )
        
        completion_data = {
            "maintenance_request_id": maintenance_request_id,
            "completed_by": completed_by,
            "work_notes": work_notes,
            "work_summary": work_summary,
            "labor_hours": labor_hours,
            "labor_rate_per_hour": labor_rate_per_hour,
            "number_of_workers": number_of_workers,
            "materials_cost": materials_cost,
            "labor_cost": labor_cost,
            "vendor_charges": vendor_charges,
            "other_costs": other_costs,
            "actual_cost": actual_cost,
            "actual_start_date": actual_start_date,
            "actual_completion_date": actual_completion_date or datetime.utcnow().date(),
            "cost_breakdown": cost_breakdown or {},
            **kwargs
        }
        
        return self.create(completion_data)
    
    def add_material(
        self,
        completion_id: UUID,
        material_name: str,
        quantity: Decimal,
        unit: str,
        unit_cost: Decimal,
        material_code: Optional[str] = None,
        category: Optional[str] = None,
        supplier: Optional[str] = None,
        supplier_invoice: Optional[str] = None,
        warranty_months: Optional[int] = None,
        **kwargs
    ) -> MaintenanceMaterial:
        """
        Add material to completion record.
        
        Args:
            completion_id: Completion record identifier
            material_name: Material name
            quantity: Quantity used
            unit: Unit of measurement
            unit_cost: Cost per unit
            material_code: Material code/SKU
            category: Material category
            supplier: Supplier name
            supplier_invoice: Supplier invoice number
            warranty_months: Warranty period
            **kwargs: Additional material attributes
            
        Returns:
            Created material record
        """
        total_cost = quantity * unit_cost
        
        material_data = {
            "completion_id": completion_id,
            "material_name": material_name,
            "material_code": material_code,
            "category": category,
            "quantity": quantity,
            "unit": unit,
            "unit_cost": unit_cost,
            "total_cost": total_cost,
            "supplier": supplier,
            "supplier_invoice": supplier_invoice,
            "warranty_months": warranty_months,
            **kwargs
        }
        
        material = MaintenanceMaterial(**material_data)
        self.session.add(material)
        self.session.commit()
        self.session.refresh(material)
        
        # Update completion materials cost
        self._update_completion_costs(completion_id)
        
        return material
    
    def create_quality_check(
        self,
        completion_id: UUID,
        maintenance_request_id: UUID,
        checked_by: UUID,
        quality_check_passed: bool,
        inspection_date: datetime,
        overall_rating: Optional[int] = None,
        quality_check_notes: Optional[str] = None,
        defects_found: Optional[str] = None,
        rework_required: bool = False,
        rework_details: Optional[str] = None,
        customer_acceptance: Optional[bool] = None,
        customer_feedback: Optional[str] = None,
        checklist_results: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> MaintenanceQualityCheck:
        """
        Create quality check record.
        
        Args:
            completion_id: Completion record identifier
            maintenance_request_id: Request identifier
            checked_by: Inspector user ID
            quality_check_passed: Check result
            inspection_date: Inspection date
            overall_rating: Overall rating (1-5)
            quality_check_notes: Inspection notes
            defects_found: Defects description
            rework_required: Whether rework needed
            rework_details: Rework details
            customer_acceptance: Customer acceptance
            customer_feedback: Customer feedback
            checklist_results: Checklist results
            **kwargs: Additional quality check attributes
            
        Returns:
            Created quality check record
        """
        quality_check_data = {
            "completion_id": completion_id,
            "maintenance_request_id": maintenance_request_id,
            "checked_by": checked_by,
            "quality_check_passed": quality_check_passed,
            "inspection_date": inspection_date.date() if isinstance(inspection_date, datetime) else inspection_date,
            "inspection_time": inspection_date,
            "overall_rating": overall_rating,
            "quality_check_notes": quality_check_notes,
            "defects_found": defects_found,
            "rework_required": rework_required,
            "rework_details": rework_details,
            "customer_acceptance": customer_acceptance,
            "customer_feedback": customer_feedback,
            "checklist_results": checklist_results or [],
            **kwargs
        }
        
        quality_check = MaintenanceQualityCheck(**quality_check_data)
        self.session.add(quality_check)
        self.session.commit()
        self.session.refresh(quality_check)
        
        # Update completion quality verification
        completion = self.find_by_id(completion_id)
        if completion:
            completion.quality_verified = True
            completion.quality_verified_by = checked_by
            completion.quality_verified_at = datetime.utcnow()
            self.session.commit()
        
        return quality_check
    
    def generate_certificate(
        self,
        completion_id: UUID,
        maintenance_request_id: UUID,
        work_title: str,
        work_description: str,
        work_category: str,
        completed_by: str,
        verified_by: str,
        approved_by: str,
        work_start_date: datetime,
        completion_date: datetime,
        verification_date: datetime,
        labor_hours: Decimal,
        total_cost: Decimal,
        completed_by_designation: Optional[str] = None,
        verified_by_designation: Optional[str] = None,
        approved_by_designation: Optional[str] = None,
        warranty_applicable: bool = False,
        warranty_period_months: Optional[int] = None,
        warranty_terms: Optional[str] = None,
        quality_rating: Optional[int] = None,
        cost_breakdown: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> MaintenanceCertificate:
        """
        Generate completion certificate.
        
        Args:
            completion_id: Completion record identifier
            maintenance_request_id: Request identifier
            work_title: Work title
            work_description: Work description
            work_category: Work category
            completed_by: Completer name
            verified_by: Verifier name
            approved_by: Approver name
            work_start_date: Start date
            completion_date: Completion date
            verification_date: Verification date
            labor_hours: Total labor hours
            total_cost: Total cost
            completed_by_designation: Completer designation
            verified_by_designation: Verifier designation
            approved_by_designation: Approver designation
            warranty_applicable: Warranty applies
            warranty_period_months: Warranty period
            warranty_terms: Warranty terms
            quality_rating: Quality rating
            cost_breakdown: Cost breakdown
            **kwargs: Additional certificate attributes
            
        Returns:
            Created certificate
        """
        # Generate certificate number
        certificate_number = self._generate_certificate_number()
        
        # Calculate warranty expiry if applicable
        warranty_valid_until = None
        if warranty_applicable and warranty_period_months:
            warranty_valid_until = (
                completion_date.date() if isinstance(completion_date, datetime) 
                else completion_date
            ) + timedelta(days=warranty_period_months * 30)
        
        certificate_data = {
            "completion_id": completion_id,
            "maintenance_request_id": maintenance_request_id,
            "certificate_number": certificate_number,
            "work_title": work_title,
            "work_description": work_description,
            "work_category": work_category,
            "labor_hours": labor_hours,
            "total_cost": total_cost,
            "cost_breakdown": cost_breakdown or {},
            "completed_by": completed_by,
            "completed_by_designation": completed_by_designation,
            "verified_by": verified_by,
            "verified_by_designation": verified_by_designation,
            "approved_by": approved_by,
            "approved_by_designation": approved_by_designation,
            "work_start_date": work_start_date.date() if isinstance(work_start_date, datetime) else work_start_date,
            "completion_date": completion_date.date() if isinstance(completion_date, datetime) else completion_date,
            "verification_date": verification_date.date() if isinstance(verification_date, datetime) else verification_date,
            "certificate_issue_date": datetime.utcnow().date(),
            "warranty_applicable": warranty_applicable,
            "warranty_period_months": warranty_period_months,
            "warranty_terms": warranty_terms,
            "warranty_valid_until": warranty_valid_until,
            "quality_rating": quality_rating,
            **kwargs
        }
        
        certificate = MaintenanceCertificate(**certificate_data)
        self.session.add(certificate)
        self.session.commit()
        self.session.refresh(certificate)
        
        return certificate
    
    # ============================================================================
    # READ OPERATIONS
    # ============================================================================
    
    def find_by_request(
        self,
        request_id: UUID
    ) -> Optional[MaintenanceCompletion]:
        """
        Find completion record by request.
        
        Args:
            request_id: Maintenance request identifier
            
        Returns:
            Completion record if exists
        """
        query = select(MaintenanceCompletion).where(
            MaintenanceCompletion.maintenance_request_id == request_id,
            MaintenanceCompletion.deleted_at.is_(None)
        ).options(
            joinedload(MaintenanceCompletion.materials),
            joinedload(MaintenanceCompletion.quality_checks),
            joinedload(MaintenanceCompletion.certificate)
        )
        
        return self.session.execute(query).scalar_one_or_none()
    
    def find_by_completer(
        self,
        completer_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceCompletion]:
        """
        Find completions by completer.
        
        Args:
            completer_id: Completer user identifier
            start_date: Optional start date filter
            end_date: Optional end date filter
            pagination: Pagination parameters
            
        Returns:
            Paginated completion records
        """
        query = select(MaintenanceCompletion).where(
            MaintenanceCompletion.completed_by == completer_id,
            MaintenanceCompletion.deleted_at.is_(None)
        )
        
        if start_date:
            query = query.where(MaintenanceCompletion.completed_at >= start_date)
        if end_date:
            query = query.where(MaintenanceCompletion.completed_at <= end_date)
        
        query = query.order_by(MaintenanceCompletion.completed_at.desc())
        
        return self.paginate(query, pagination)
    
    def find_pending_quality_check(
        self,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceCompletion]:
        """
        Find completions pending quality check.
        
        Args:
            pagination: Pagination parameters
            
        Returns:
            Paginated completions pending quality check
        """
        query = select(MaintenanceCompletion).where(
            MaintenanceCompletion.quality_verified == False,
            MaintenanceCompletion.deleted_at.is_(None)
        ).order_by(MaintenanceCompletion.completed_at.asc())
        
        return self.paginate(query, pagination)
    
    def find_requiring_follow_up(
        self,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceCompletion]:
        """
        Find completions requiring follow-up.
        
        Args:
            pagination: Pagination parameters
            
        Returns:
            Paginated completions requiring follow-up
        """
        query = select(MaintenanceCompletion).where(
            MaintenanceCompletion.follow_up_required == True,
            MaintenanceCompletion.follow_up_date >= datetime.utcnow().date(),
            MaintenanceCompletion.deleted_at.is_(None)
        ).order_by(MaintenanceCompletion.follow_up_date.asc())
        
        return self.paginate(query, pagination)
    
    def find_materials_by_completion(
        self,
        completion_id: UUID
    ) -> List[MaintenanceMaterial]:
        """
        Find all materials for a completion.
        
        Args:
            completion_id: Completion identifier
            
        Returns:
            List of materials
        """
        query = select(MaintenanceMaterial).where(
            MaintenanceMaterial.completion_id == completion_id
        ).order_by(MaintenanceMaterial.created_at.asc())
        
        return list(self.session.execute(query).scalars().all())
    
    def find_quality_checks_by_request(
        self,
        request_id: UUID
    ) -> List[MaintenanceQualityCheck]:
        """
        Find quality checks for a request.
        
        Args:
            request_id: Request identifier
            
        Returns:
            List of quality checks
        """
        query = select(MaintenanceQualityCheck).where(
            MaintenanceQualityCheck.maintenance_request_id == request_id
        ).order_by(MaintenanceQualityCheck.inspection_date.desc())
        
        return list(self.session.execute(query).scalars().all())
    
    def find_certificate_by_number(
        self,
        certificate_number: str
    ) -> Optional[MaintenanceCertificate]:
        """
        Find certificate by certificate number.
        
        Args:
            certificate_number: Certificate number
            
        Returns:
            Certificate if found
        """
        query = select(MaintenanceCertificate).where(
            MaintenanceCertificate.certificate_number == certificate_number
        )
        
        return self.session.execute(query).scalar_one_or_none()
    
    # ============================================================================
    # UPDATE OPERATIONS
    # ============================================================================
    
    def update_completion_costs(
        self,
        completion_id: UUID,
        materials_cost: Optional[Decimal] = None,
        labor_cost: Optional[Decimal] = None,
        vendor_charges: Optional[Decimal] = None,
        other_costs: Optional[Decimal] = None
    ) -> MaintenanceCompletion:
        """
        Update completion costs.
        
        Args:
            completion_id: Completion identifier
            materials_cost: Materials cost
            labor_cost: Labor cost
            vendor_charges: Vendor charges
            other_costs: Other costs
            
        Returns:
            Updated completion record
        """
        completion = self.find_by_id(completion_id)
        if not completion:
            raise ValueError(f"Completion {completion_id} not found")
        
        if materials_cost is not None:
            completion.materials_cost = materials_cost
        if labor_cost is not None:
            completion.labor_cost = labor_cost
        if vendor_charges is not None:
            completion.vendor_charges = vendor_charges
        if other_costs is not None:
            completion.other_costs = other_costs
        
        # Recalculate total
        completion.actual_cost = (
            completion.materials_cost +
            completion.labor_cost +
            completion.vendor_charges +
            completion.other_costs
        )
        
        self.session.commit()
        self.session.refresh(completion)
        
        return completion
    
    def add_warranty(
        self,
        completion_id: UUID,
        warranty_period_months: int,
        warranty_terms: str
    ) -> MaintenanceCompletion:
        """
        Add warranty to completion.
        
        Args:
            completion_id: Completion identifier
            warranty_period_months: Warranty period
            warranty_terms: Warranty terms
            
        Returns:
            Updated completion record
        """
        completion = self.find_by_id(completion_id)
        if not completion:
            raise ValueError(f"Completion {completion_id} not found")
        
        completion.warranty_applicable = True
        completion.warranty_period_months = warranty_period_months
        completion.warranty_terms = warranty_terms
        
        # Calculate expiry
        completion.warranty_expiry_date = (
            completion.actual_completion_date + timedelta(days=warranty_period_months * 30)
        )
        
        self.session.commit()
        self.session.refresh(completion)
        
        return completion
    
    # ============================================================================
    # ANALYTICS AND REPORTING
    # ============================================================================
    
    def get_completion_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get completion statistics.
        
        Args:
            hostel_id: Optional hostel filter
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Completion statistics
        """
        # Build base query with join to request for hostel filter
        query = select(
            func.count(MaintenanceCompletion.id).label("total_completions"),
            func.avg(MaintenanceCompletion.labor_hours).label("avg_labor_hours"),
            func.avg(MaintenanceCompletion.actual_cost).label("avg_cost"),
            func.sum(MaintenanceCompletion.actual_cost).label("total_cost"),
            func.sum(
                func.case(
                    (MaintenanceCompletion.quality_verified == True, 1),
                    else_=0
                )
            ).label("quality_verified_count"),
            func.avg(
                func.extract(
                    'epoch',
                    func.cast(MaintenanceCompletion.actual_completion_date, DateTime) -
                    func.cast(MaintenanceCompletion.actual_start_date, DateTime)
                ) / 86400
            ).label("avg_days_to_complete")
        ).where(
            MaintenanceCompletion.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.join(
                MaintenanceRequest,
                MaintenanceCompletion.maintenance_request_id == MaintenanceRequest.id
            ).where(
                MaintenanceRequest.hostel_id == hostel_id
            )
        
        if start_date:
            query = query.where(MaintenanceCompletion.completed_at >= start_date)
        if end_date:
            query = query.where(MaintenanceCompletion.completed_at <= end_date)
        
        result = self.session.execute(query).first()
        
        quality_rate = Decimal("0.00")
        if result.total_completions and result.total_completions > 0:
            quality_rate = round(
                Decimal(result.quality_verified_count or 0) / 
                Decimal(result.total_completions) * 100,
                2
            )
        
        return {
            "total_completions": result.total_completions or 0,
            "average_labor_hours": float(result.avg_labor_hours or 0),
            "average_cost": float(result.avg_cost or 0),
            "total_cost": float(result.total_cost or 0),
            "quality_verification_rate": float(quality_rate),
            "average_days_to_complete": float(result.avg_days_to_complete or 0)
        }
    
    def get_material_usage_summary(
        self,
        start_date: datetime,
        end_date: datetime,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get material usage summary.
        
        Args:
            start_date: Period start date
            end_date: Period end date
            category: Optional category filter
            
        Returns:
            Material usage summary
        """
        query = select(
            MaintenanceMaterial.material_name,
            MaintenanceMaterial.category,
            func.sum(MaintenanceMaterial.quantity).label("total_quantity"),
            MaintenanceMaterial.unit,
            func.sum(MaintenanceMaterial.total_cost).label("total_cost"),
            func.count(MaintenanceMaterial.id).label("usage_count")
        ).join(
            MaintenanceCompletion,
            MaintenanceMaterial.completion_id == MaintenanceCompletion.id
        ).where(
            MaintenanceCompletion.completed_at >= start_date,
            MaintenanceCompletion.completed_at <= end_date
        )
        
        if category:
            query = query.where(MaintenanceMaterial.category == category)
        
        query = query.group_by(
            MaintenanceMaterial.material_name,
            MaintenanceMaterial.category,
            MaintenanceMaterial.unit
        ).order_by(
            desc("total_cost")
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "material_name": row.material_name,
                "category": row.category,
                "total_quantity": float(row.total_quantity),
                "unit": row.unit,
                "total_cost": float(row.total_cost),
                "usage_count": row.usage_count
            }
            for row in results
        ]
    
    def get_quality_check_summary(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get quality check summary.
        
        Args:
            start_date: Period start date
            end_date: Period end date
            
        Returns:
            Quality check summary
        """
        query = select(
            func.count(MaintenanceQualityCheck.id).label("total_checks"),
            func.sum(
                func.case(
                    (MaintenanceQualityCheck.quality_check_passed == True, 1),
                    else_=0
                )
            ).label("passed"),
            func.sum(
                func.case(
                    (MaintenanceQualityCheck.rework_required == True, 1),
                    else_=0
                )
            ).label("rework_required"),
            func.avg(MaintenanceQualityCheck.overall_rating).label("avg_rating")
        ).where(
            MaintenanceQualityCheck.inspection_date >= start_date.date(),
            MaintenanceQualityCheck.inspection_date <= end_date.date()
        )
        
        result = self.session.execute(query).first()
        
        pass_rate = Decimal("0.00")
        rework_rate = Decimal("0.00")
        
        if result.total_checks and result.total_checks > 0:
            pass_rate = round(
                Decimal(result.passed or 0) / Decimal(result.total_checks) * 100,
                2
            )
            rework_rate = round(
                Decimal(result.rework_required or 0) / Decimal(result.total_checks) * 100,
                2
            )
        
        return {
            "total_checks": result.total_checks or 0,
            "passed": result.passed or 0,
            "pass_rate": float(pass_rate),
            "rework_required": result.rework_required or 0,
            "rework_rate": float(rework_rate),
            "average_rating": float(result.avg_rating or 0)
        }
    
    def get_warranty_expiring_soon(
        self,
        days: int = 30,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceCompletion]:
        """
        Find completions with warranties expiring soon.
        
        Args:
            days: Number of days to look ahead
            pagination: Pagination parameters
            
        Returns:
            Paginated completions with expiring warranties
        """
        future_date = datetime.utcnow().date() + timedelta(days=days)
        
        query = select(MaintenanceCompletion).where(
            MaintenanceCompletion.warranty_applicable == True,
            MaintenanceCompletion.warranty_expiry_date.isnot(None),
            MaintenanceCompletion.warranty_expiry_date >= datetime.utcnow().date(),
            MaintenanceCompletion.warranty_expiry_date <= future_date,
            MaintenanceCompletion.deleted_at.is_(None)
        ).order_by(MaintenanceCompletion.warranty_expiry_date.asc())
        
        return self.paginate(query, pagination)
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _update_completion_costs(self, completion_id: UUID) -> None:
        """
        Update completion costs based on materials.
        
        Args:
            completion_id: Completion identifier
        """
        # Calculate total materials cost
        materials_query = select(
            func.sum(MaintenanceMaterial.total_cost).label("total")
        ).where(
            MaintenanceMaterial.completion_id == completion_id
        )
        
        materials_total = self.session.execute(materials_query).scalar_one_or_none()
        
        if materials_total:
            completion = self.find_by_id(completion_id)
            if completion:
                completion.materials_cost = Decimal(str(materials_total))
                completion.actual_cost = (
                    completion.materials_cost +
                    completion.labor_cost +
                    completion.vendor_charges +
                    completion.other_costs
                )
                self.session.commit()
    
    def _generate_certificate_number(self) -> str:
        """
        Generate unique certificate number.
        
        Returns:
            Unique certificate number
        """
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        
        # Count certificates this month
        count_query = select(
            func.count(MaintenanceCertificate.id)
        ).where(
            func.extract('year', MaintenanceCertificate.certificate_issue_date) == now.year,
            func.extract('month', MaintenanceCertificate.certificate_issue_date) == now.month
        )
        
        count = self.session.execute(count_query).scalar_one() + 1
        
        # Format: CERT-YYYY-MM-0001
        return f"CERT-{year}-{month}-{count:04d}"