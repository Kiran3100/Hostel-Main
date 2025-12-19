# app/repositories/maintenance/maintenance_vendor_repository.py
"""
Maintenance Vendor Repository.

Vendor management with performance tracking, contract management,
and comprehensive analytics.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.maintenance import (
    MaintenanceVendor,
    VendorContract,
    VendorPerformanceReview,
    VendorAssignment,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginatedResult


class MaintenanceVendorRepository(BaseRepository[MaintenanceVendor]):
    """
    Repository for maintenance vendor operations.
    
    Manages vendor records, contracts, performance reviews,
    and comprehensive vendor analytics.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with session."""
        super().__init__(MaintenanceVendor, session)
    
    # ============================================================================
    # CREATE OPERATIONS
    # ============================================================================
    
    def create_vendor(
        self,
        company_name: str,
        contact_person: str,
        phone: str,
        email: str,
        service_categories: List[str],
        vendor_code: Optional[str] = None,
        trade_name: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        postal_code: Optional[str] = None,
        business_type: Optional[str] = None,
        tax_id: Optional[str] = None,
        specializations: Optional[List[str]] = None,
        is_insured: bool = False,
        insurance_expiry_date: Optional[date] = None,
        **kwargs
    ) -> MaintenanceVendor:
        """
        Create new vendor record.
        
        Args:
            company_name: Vendor company name
            contact_person: Primary contact person
            phone: Contact phone
            email: Contact email
            service_categories: Service categories
            vendor_code: Unique vendor code
            trade_name: Trade/DBA name
            address: Street address
            city: City
            state: State
            postal_code: Postal code
            business_type: Business type
            tax_id: Tax ID/GST number
            specializations: Specializations
            is_insured: Whether insured
            insurance_expiry_date: Insurance expiry
            **kwargs: Additional vendor attributes
            
        Returns:
            Created vendor
        """
        vendor_data = {
            "vendor_code": vendor_code or self._generate_vendor_code(),
            "company_name": company_name,
            "trade_name": trade_name,
            "contact_person": contact_person,
            "phone": phone,
            "email": email,
            "address": address,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "business_type": business_type,
            "tax_id": tax_id,
            "service_categories": service_categories,
            "specializations": specializations or [],
            "is_insured": is_insured,
            "insurance_expiry_date": insurance_expiry_date,
            "vendor_status": "active",
            "is_approved": False,
            "performance_tier": "bronze",
            "is_recommended": True,
            **kwargs
        }
        
        return self.create(vendor_data)
    
    def create_contract(
        self,
        vendor_id: UUID,
        contract_number: str,
        contract_title: str,
        contract_type: str,
        start_date: date,
        end_date: date,
        service_categories: List[str],
        payment_terms: str,
        contract_value: Optional[Decimal] = None,
        scope_of_work: Optional[str] = None,
        sla_terms: Optional[Dict[str, Any]] = None,
        response_time_hours: Optional[int] = None,
        **kwargs
    ) -> VendorContract:
        """
        Create vendor contract.
        
        Args:
            vendor_id: Vendor identifier
            contract_number: Contract number
            contract_title: Contract title
            contract_type: Contract type
            start_date: Contract start date
            end_date: Contract end date
            service_categories: Covered services
            payment_terms: Payment terms
            contract_value: Total contract value
            scope_of_work: Scope of work
            sla_terms: SLA terms
            response_time_hours: Response time SLA
            **kwargs: Additional contract attributes
            
        Returns:
            Created contract
        """
        contract_data = {
            "vendor_id": vendor_id,
            "contract_number": contract_number,
            "contract_title": contract_title,
            "contract_type": contract_type,
            "start_date": start_date,
            "end_date": end_date,
            "contract_value": contract_value,
            "service_categories": service_categories,
            "scope_of_work": scope_of_work,
            "payment_terms": payment_terms,
            "sla_terms": sla_terms or {},
            "response_time_hours": response_time_hours,
            "contract_status": "active",
            **kwargs
        }
        
        contract = VendorContract(**contract_data)
        self.session.add(contract)
        self.session.commit()
        self.session.refresh(contract)
        
        return contract
    
    def create_performance_review(
        self,
        vendor_id: UUID,
        review_period_start: date,
        review_period_end: date,
        review_date: date,
        reviewed_by: UUID,
        jobs_completed: int,
        on_time_completion_rate: Decimal,
        total_spent: Decimal,
        quality_rating: Decimal,
        recommendation: str,
        average_cost_per_job: Optional[Decimal] = None,
        workmanship_rating: Optional[Decimal] = None,
        professionalism_rating: Optional[Decimal] = None,
        communication_rating: Optional[Decimal] = None,
        strengths: Optional[str] = None,
        areas_for_improvement: Optional[str] = None,
        **kwargs
    ) -> VendorPerformanceReview:
        """
        Create vendor performance review.
        
        Args:
            vendor_id: Vendor identifier
            review_period_start: Review period start
            review_period_end: Review period end
            review_date: Review date
            reviewed_by: Reviewer user ID
            jobs_completed: Jobs completed
            on_time_completion_rate: On-time rate
            total_spent: Total spent
            quality_rating: Quality rating
            recommendation: Recommendation
            average_cost_per_job: Average cost
            workmanship_rating: Workmanship rating
            professionalism_rating: Professionalism rating
            communication_rating: Communication rating
            strengths: Identified strengths
            areas_for_improvement: Improvement areas
            **kwargs: Additional review attributes
            
        Returns:
            Created performance review
        """
        review_data = {
            "vendor_id": vendor_id,
            "review_period_start": review_period_start,
            "review_period_end": review_period_end,
            "review_date": review_date,
            "reviewed_by": reviewed_by,
            "jobs_completed": jobs_completed,
            "on_time_completion_rate": on_time_completion_rate,
            "total_spent": total_spent,
            "average_cost_per_job": average_cost_per_job or (total_spent / jobs_completed if jobs_completed > 0 else Decimal("0.00")),
            "quality_rating": quality_rating,
            "workmanship_rating": workmanship_rating,
            "professionalism_rating": professionalism_rating,
            "communication_rating": communication_rating,
            "recommendation": recommendation,
            "strengths": strengths,
            "areas_for_improvement": areas_for_improvement,
            **kwargs
        }
        
        review = VendorPerformanceReview(**review_data)
        self.session.add(review)
        self.session.commit()
        self.session.refresh(review)
        
        return review
    
    # ============================================================================
    # READ OPERATIONS - VENDORS
    # ============================================================================
    
    def find_by_vendor_code(
        self,
        vendor_code: str
    ) -> Optional[MaintenanceVendor]:
        """
        Find vendor by vendor code.
        
        Args:
            vendor_code: Vendor code
            
        Returns:
            Vendor if found
        """
        query = select(MaintenanceVendor).where(
            MaintenanceVendor.vendor_code == vendor_code,
            MaintenanceVendor.deleted_at.is_(None)
        )
        
        return self.session.execute(query).scalar_one_or_none()
    
    def find_by_service_category(
        self,
        category: str,
        is_approved: bool = True,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceVendor]:
        """
        Find vendors by service category.
        
        Args:
            category: Service category
            is_approved: Filter approved vendors
            pagination: Pagination parameters
            
        Returns:
            Paginated vendors
        """
        query = select(MaintenanceVendor).where(
            MaintenanceVendor.service_categories.contains([category]),
            MaintenanceVendor.vendor_status == "active",
            MaintenanceVendor.deleted_at.is_(None)
        )
        
        if is_approved:
            query = query.where(MaintenanceVendor.is_approved == True)
        
        query = query.order_by(
            MaintenanceVendor.performance_tier.asc(),
            MaintenanceVendor.overall_rating.desc().nullslast()
        )
        
        return self.paginate(query, pagination)
    
    def find_active_vendors(
        self,
        is_approved: Optional[bool] = True,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceVendor]:
        """
        Find active vendors.
        
        Args:
            is_approved: Filter by approval status
            pagination: Pagination parameters
            
        Returns:
            Paginated active vendors
        """
        query = select(MaintenanceVendor).where(
            MaintenanceVendor.vendor_status == "active",
            MaintenanceVendor.deleted_at.is_(None)
        )
        
        if is_approved is not None:
            query = query.where(MaintenanceVendor.is_approved == is_approved)
        
        query = query.order_by(MaintenanceVendor.company_name.asc())
        
        return self.paginate(query, pagination)
    
    def find_recommended_vendors(
        self,
        service_category: Optional[str] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceVendor]:
        """
        Find recommended vendors.
        
        Args:
            service_category: Optional service category filter
            pagination: Pagination parameters
            
        Returns:
            Paginated recommended vendors
        """
        query = select(MaintenanceVendor).where(
            MaintenanceVendor.is_recommended == True,
            MaintenanceVendor.is_approved == True,
            MaintenanceVendor.vendor_status == "active",
            MaintenanceVendor.deleted_at.is_(None)
        )
        
        if service_category:
            query = query.where(
                MaintenanceVendor.service_categories.contains([service_category])
            )
        
        query = query.order_by(
            MaintenanceVendor.overall_rating.desc().nullslast(),
            MaintenanceVendor.performance_tier.asc()
        )
        
        return self.paginate(query, pagination)
    
    def find_by_performance_tier(
        self,
        tier: str,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceVendor]:
        """
        Find vendors by performance tier.
        
        Args:
            tier: Performance tier
            pagination: Pagination parameters
            
        Returns:
            Paginated vendors
        """
        query = select(MaintenanceVendor).where(
            MaintenanceVendor.performance_tier == tier,
            MaintenanceVendor.vendor_status == "active",
            MaintenanceVendor.deleted_at.is_(None)
        ).order_by(MaintenanceVendor.overall_rating.desc().nullslast())
        
        return self.paginate(query, pagination)
    
    def find_vendors_with_expiring_insurance(
        self,
        days: int = 30,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceVendor]:
        """
        Find vendors with insurance expiring soon.
        
        Args:
            days: Days to look ahead
            pagination: Pagination parameters
            
        Returns:
            Paginated vendors with expiring insurance
        """
        today = date.today()
        future_date = today + timedelta(days=days)
        
        query = select(MaintenanceVendor).where(
            MaintenanceVendor.is_insured == True,
            MaintenanceVendor.insurance_expiry_date.isnot(None),
            MaintenanceVendor.insurance_expiry_date >= today,
            MaintenanceVendor.insurance_expiry_date <= future_date,
            MaintenanceVendor.deleted_at.is_(None)
        ).order_by(MaintenanceVendor.insurance_expiry_date.asc())
        
        return self.paginate(query, pagination)
    
    # ============================================================================
    # READ OPERATIONS - CONTRACTS
    # ============================================================================
    
    def find_contracts_by_vendor(
        self,
        vendor_id: UUID,
        contract_status: Optional[str] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[VendorContract]:
        """
        Find contracts for vendor.
        
        Args:
            vendor_id: Vendor identifier
            contract_status: Optional status filter
            pagination: Pagination parameters
            
        Returns:
            Paginated vendor contracts
        """
        query = select(VendorContract).where(
            VendorContract.vendor_id == vendor_id,
            VendorContract.deleted_at.is_(None)
        )
        
        if contract_status:
            query = query.where(VendorContract.contract_status == contract_status)
        
        query = query.order_by(VendorContract.end_date.desc())
        
        return self.paginate(query, pagination)
    
    def find_active_contracts(
        self,
        vendor_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[VendorContract]:
        """
        Find active contracts.
        
        Args:
            vendor_id: Optional vendor filter
            pagination: Pagination parameters
            
        Returns:
            Paginated active contracts
        """
        today = date.today()
        
        query = select(VendorContract).where(
            VendorContract.contract_status == "active",
            VendorContract.start_date <= today,
            VendorContract.end_date >= today,
            VendorContract.deleted_at.is_(None)
        )
        
        if vendor_id:
            query = query.where(VendorContract.vendor_id == vendor_id)
        
        query = query.order_by(VendorContract.end_date.asc())
        
        return self.paginate(query, pagination)
    
    def find_expiring_contracts(
        self,
        days: int = 30,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[VendorContract]:
        """
        Find contracts expiring soon.
        
        Args:
            days: Days to look ahead
            pagination: Pagination parameters
            
        Returns:
            Paginated expiring contracts
        """
        today = date.today()
        future_date = today + timedelta(days=days)
        
        query = select(VendorContract).where(
            VendorContract.contract_status == "active",
            VendorContract.end_date >= today,
            VendorContract.end_date <= future_date,
            VendorContract.deleted_at.is_(None)
        ).order_by(VendorContract.end_date.asc())
        
        return self.paginate(query, pagination)
    
    def find_contract_by_number(
        self,
        contract_number: str
    ) -> Optional[VendorContract]:
        """
        Find contract by contract number.
        
        Args:
            contract_number: Contract number
            
        Returns:
            Contract if found
        """
        query = select(VendorContract).where(
            VendorContract.contract_number == contract_number,
            VendorContract.deleted_at.is_(None)
        )
        
        return self.session.execute(query).scalar_one_or_none()
    
    # ============================================================================
    # READ OPERATIONS - PERFORMANCE REVIEWS
    # ============================================================================
    
    def find_reviews_by_vendor(
        self,
        vendor_id: UUID,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[VendorPerformanceReview]:
        """
        Find performance reviews for vendor.
        
        Args:
            vendor_id: Vendor identifier
            pagination: Pagination parameters
            
        Returns:
            Paginated performance reviews
        """
        query = select(VendorPerformanceReview).where(
            VendorPerformanceReview.vendor_id == vendor_id
        ).order_by(VendorPerformanceReview.review_date.desc())
        
        return self.paginate(query, pagination)
    
    def get_latest_review(
        self,
        vendor_id: UUID
    ) -> Optional[VendorPerformanceReview]:
        """
        Get latest performance review for vendor.
        
        Args:
            vendor_id: Vendor identifier
            
        Returns:
            Latest review if exists
        """
        query = select(VendorPerformanceReview).where(
            VendorPerformanceReview.vendor_id == vendor_id
        ).order_by(
            VendorPerformanceReview.review_date.desc()
        )
        
        return self.session.execute(query).scalars().first()
    
    # ============================================================================
    # UPDATE OPERATIONS
    # ============================================================================
    
    def approve_vendor(
        self,
        vendor_id: UUID,
        approved_by: UUID
    ) -> MaintenanceVendor:
        """
        Approve vendor for work.
        
        Args:
            vendor_id: Vendor identifier
            approved_by: User approving vendor
            
        Returns:
            Approved vendor
        """
        vendor = self.find_by_id(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")
        
        vendor.is_approved = True
        vendor.approved_by = approved_by
        vendor.approved_at = datetime.utcnow()
        vendor.vendor_status = "active"
        
        self.session.commit()
        self.session.refresh(vendor)
        
        return vendor
    
    def update_performance_metrics(
        self,
        vendor_id: UUID
    ) -> MaintenanceVendor:
        """
        Update vendor performance metrics.
        
        Args:
            vendor_id: Vendor identifier
            
        Returns:
            Updated vendor
        """
        vendor = self.find_by_id(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")
        
        vendor.update_performance_metrics()
        
        self.session.commit()
        self.session.refresh(vendor)
        
        return vendor
    
    def blacklist_vendor(
        self,
        vendor_id: UUID,
        reason: str
    ) -> MaintenanceVendor:
        """
        Blacklist vendor.
        
        Args:
            vendor_id: Vendor identifier
            reason: Reason for blacklisting
            
        Returns:
            Blacklisted vendor
        """
        vendor = self.find_by_id(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")
        
        vendor.vendor_status = "blacklisted"
        vendor.is_approved = False
        vendor.is_recommended = False
        
        if not vendor.metadata:
            vendor.metadata = {}
        vendor.metadata["blacklist_reason"] = reason
        vendor.metadata["blacklisted_at"] = datetime.utcnow().isoformat()
        
        self.session.commit()
        self.session.refresh(vendor)
        
        return vendor
    
    # ============================================================================
    # ANALYTICS AND REPORTING
    # ============================================================================
    
    def get_vendor_summary(
        self,
        vendor_id: UUID
    ) -> Dict[str, Any]:
        """
        Get comprehensive vendor summary.
        
        Args:
            vendor_id: Vendor identifier
            
        Returns:
            Vendor summary with all metrics
        """
        vendor = self.find_by_id(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {vendor_id} not found")
        
        # Get assignment statistics
        assignment_query = select(
            func.count(VendorAssignment.id).label("total_assignments"),
            func.sum(
                func.case(
                    (VendorAssignment.is_completed == True, 1),
                    else_=0
                )
            ).label("completed"),
            func.sum(VendorAssignment.quoted_amount).label("total_quoted"),
            func.sum(VendorAssignment.payment_amount).label("total_paid")
        ).where(
            VendorAssignment.vendor_id == vendor_id,
            VendorAssignment.deleted_at.is_(None)
        )
        
        assignment_result = self.session.execute(assignment_query).first()
        
        # Get latest review
        latest_review = self.get_latest_review(vendor_id)
        
        return {
            "vendor_id": str(vendor_id),
            "vendor_code": vendor.vendor_code,
            "company_name": vendor.company_name,
            "vendor_status": vendor.vendor_status,
            "is_approved": vendor.is_approved,
            "performance_tier": vendor.performance_tier,
            "overall_rating": float(vendor.overall_rating) if vendor.overall_rating else None,
            "total_jobs": vendor.total_jobs,
            "completed_jobs": vendor.completed_jobs,
            "in_progress_jobs": vendor.in_progress_jobs,
            "completion_rate": float(vendor.completion_rate),
            "on_time_completion_rate": float(vendor.on_time_completion_rate),
            "total_spent": float(vendor.total_spent),
            "average_job_cost": float(vendor.average_job_cost),
            "outstanding_amount": float(vendor.outstanding_amount),
            "quality_score": float(vendor.quality_score) if vendor.quality_score else None,
            "is_insured": vendor.is_insured,
            "insurance_valid": vendor.is_insurance_valid,
            "latest_review": {
                "review_date": latest_review.review_date.isoformat() if latest_review else None,
                "quality_rating": float(latest_review.quality_rating) if latest_review else None,
                "recommendation": latest_review.recommendation if latest_review else None
            } if latest_review else None
        }
    
    def get_vendor_rankings(
        self,
        service_category: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top-ranked vendors.
        
        Args:
            service_category: Optional service category filter
            limit: Number of vendors to return
            
        Returns:
            List of top vendors
        """
        query = select(
            MaintenanceVendor.id,
            MaintenanceVendor.vendor_code,
            MaintenanceVendor.company_name,
            MaintenanceVendor.performance_tier,
            MaintenanceVendor.overall_rating,
            MaintenanceVendor.on_time_completion_rate,
            MaintenanceVendor.quality_score,
            MaintenanceVendor.total_jobs,
            MaintenanceVendor.completed_jobs
        ).where(
            MaintenanceVendor.is_approved == True,
            MaintenanceVendor.vendor_status == "active",
            MaintenanceVendor.deleted_at.is_(None)
        )
        
        if service_category:
            query = query.where(
                MaintenanceVendor.service_categories.contains([service_category])
            )
        
        query = query.order_by(
            MaintenanceVendor.overall_rating.desc().nullslast(),
            MaintenanceVendor.on_time_completion_rate.desc()
        ).limit(limit)
        
        results = self.session.execute(query).all()
        
        return [
            {
                "vendor_id": str(row.id),
                "vendor_code": row.vendor_code,
                "company_name": row.company_name,
                "performance_tier": row.performance_tier,
                "overall_rating": float(row.overall_rating) if row.overall_rating else 0.0,
                "on_time_rate": float(row.on_time_completion_rate),
                "quality_score": float(row.quality_score) if row.quality_score else 0.0,
                "total_jobs": row.total_jobs,
                "completed_jobs": row.completed_jobs
            }
            for row in results
        ]
    
    def calculate_performance_trends(
        self,
        vendor_id: UUID,
        months: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Calculate performance trends for vendor.
        
        Args:
            vendor_id: Vendor identifier
            months: Number of months to analyze
            
        Returns:
            Monthly performance trends
        """
        cutoff_date = date.today() - timedelta(days=months * 30)
        
        query = select(
            VendorPerformanceReview.review_period_start,
            VendorPerformanceReview.review_period_end,
            VendorPerformanceReview.quality_rating,
            VendorPerformanceReview.on_time_completion_rate,
            VendorPerformanceReview.jobs_completed,
            VendorPerformanceReview.total_spent
        ).where(
            VendorPerformanceReview.vendor_id == vendor_id,
            VendorPerformanceReview.review_date >= cutoff_date
        ).order_by(
            VendorPerformanceReview.review_date.asc()
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "period_start": row.review_period_start.isoformat(),
                "period_end": row.review_period_end.isoformat(),
                "quality_rating": float(row.quality_rating),
                "on_time_rate": float(row.on_time_completion_rate),
                "jobs_completed": row.jobs_completed,
                "total_spent": float(row.total_spent)
            }
            for row in results
        ]
    
    def get_category_performance(
        self,
        service_category: str
    ) -> List[Dict[str, Any]]:
        """
        Get vendor performance comparison by category.
        
        Args:
            service_category: Service category
            
        Returns:
            Vendor performance data for category
        """
        query = select(
            MaintenanceVendor.id,
            MaintenanceVendor.company_name,
            MaintenanceVendor.overall_rating,
            MaintenanceVendor.on_time_completion_rate,
            MaintenanceVendor.quality_score,
            MaintenanceVendor.average_job_cost,
            MaintenanceVendor.total_jobs
        ).where(
            MaintenanceVendor.service_categories.contains([service_category]),
            MaintenanceVendor.is_approved == True,
            MaintenanceVendor.vendor_status == "active",
            MaintenanceVendor.deleted_at.is_(None)
        ).order_by(
            MaintenanceVendor.overall_rating.desc().nullslast()
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "vendor_id": str(row.id),
                "company_name": row.company_name,
                "overall_rating": float(row.overall_rating) if row.overall_rating else 0.0,
                "on_time_rate": float(row.on_time_completion_rate),
                "quality_score": float(row.quality_score) if row.quality_score else 0.0,
                "average_cost": float(row.average_job_cost),
                "total_jobs": row.total_jobs
            }
            for row in results
        ]
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _generate_vendor_code(self) -> str:
        """
        Generate unique vendor code.
        
        Returns:
            Unique vendor code
        """
        # Count total vendors
        count_query = select(func.count(MaintenanceVendor.id))
        count = self.session.execute(count_query).scalar_one() + 1
        
        # Format: VND-0001
        return f"VND-{count:04d}"