# app/models/maintenance/maintenance_vendor.py
"""
Maintenance vendor management models.

Vendor/contractor management with performance tracking,
contracts, and service history.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import (
    SoftDeleteMixin,
    UUIDMixin,
    ContactMixin,
    AddressMixin,
    AuditMixin,
)


class MaintenanceVendor(UUIDMixin, TimestampModel, SoftDeleteMixin, ContactMixin, AddressMixin, AuditMixin, BaseModel):
    """
    Maintenance vendor/contractor master record.
    
    Manages vendor information, certifications, and service capabilities
    with comprehensive performance tracking.
    """
    
    __tablename__ = "maintenance_vendors"
    
    # Company information
    vendor_code = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique vendor code",
    )
    
    company_name = Column(
        String(255),
        nullable=False,
        comment="Vendor company name",
    )
    
    trade_name = Column(
        String(255),
        nullable=True,
        comment="Trade/DBA name",
    )
    
    # Contact information (extends ContactMixin)
    contact_person = Column(
        String(255),
        nullable=True,
        comment="Primary contact person",
    )
    
    alternate_phone = Column(
        String(20),
        nullable=True,
        comment="Alternate contact number",
    )
    
    alternate_email = Column(
        String(255),
        nullable=True,
        comment="Alternate email address",
    )
    
    website = Column(
        String(500),
        nullable=True,
        comment="Company website",
    )
    
    # Business details
    business_type = Column(
        String(50),
        nullable=True,
        comment="Business type (individual, partnership, company)",
    )
    
    tax_id = Column(
        String(50),
        nullable=True,
        comment="Tax ID/GST number",
    )
    
    pan_number = Column(
        String(20),
        nullable=True,
        comment="PAN number",
    )
    
    registration_number = Column(
        String(100),
        nullable=True,
        comment="Business registration number",
    )
    
    # Service capabilities
    service_categories = Column(
        ARRAY(String),
        nullable=False,
        default=[],
        comment="Service categories vendor can handle",
    )
    
    specializations = Column(
        ARRAY(String),
        nullable=True,
        default=[],
        comment="Specific specializations",
    )
    
    service_areas = Column(
        ARRAY(String),
        nullable=True,
        default=[],
        comment="Geographic service areas",
    )
    
    # Certifications and compliance
    certifications = Column(
        JSONB,
        nullable=True,
        default=[],
        comment="Professional certifications",
    )
    
    licenses = Column(
        JSONB,
        nullable=True,
        default=[],
        comment="Business licenses",
    )
    
    insurance_details = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Insurance coverage details",
    )
    
    is_insured = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether vendor has liability insurance",
    )
    
    insurance_expiry_date = Column(
        Date,
        nullable=True,
        comment="Insurance expiry date",
    )
    
    # Vendor status
    vendor_status = Column(
        String(20),
        nullable=False,
        default="active",
        index=True,
        comment="Vendor status (active, inactive, blacklisted, suspended)",
    )
    
    is_approved = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether vendor is approved for work",
    )
    
    approved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who approved vendor",
    )
    
    approved_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Approval timestamp",
    )
    
    # Performance metrics
    total_jobs = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total jobs assigned",
    )
    
    completed_jobs = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Jobs completed",
    )
    
    in_progress_jobs = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Jobs currently in progress",
    )
    
    cancelled_jobs = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Jobs cancelled",
    )
    
    # Financial metrics
    total_spent = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total amount paid to vendor",
    )
    
    average_job_cost = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Average cost per job",
    )
    
    outstanding_amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Outstanding payment amount",
    )
    
    # Quality metrics
    overall_rating = Column(
        Numeric(3, 2),
        nullable=True,
        comment="Overall quality rating (1-5)",
    )
    
    on_time_completion_rate = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Percentage of jobs completed on time",
    )
    
    quality_score = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Quality score (0-100)",
    )
    
    customer_satisfaction_score = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Customer satisfaction score (0-100)",
    )
    
    # Response and availability
    average_response_time_hours = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Average response time in hours",
    )
    
    availability_score = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Vendor availability score (0-100)",
    )
    
    # Engagement period
    first_job_date = Column(
        Date,
        nullable=True,
        comment="Date of first job",
    )
    
    last_job_date = Column(
        Date,
        nullable=True,
        comment="Date of most recent job",
    )
    
    # Performance tier
    performance_tier = Column(
        String(20),
        nullable=False,
        default="bronze",
        comment="Performance tier (platinum, gold, silver, bronze, needs_improvement)",
    )
    
    is_recommended = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether vendor is recommended",
    )
    
    # Payment terms
    default_payment_terms = Column(
        String(200),
        nullable=True,
        comment="Default payment terms",
    )
    
    payment_method_preference = Column(
        String(50),
        nullable=True,
        comment="Preferred payment method",
    )
    
    # Bank details
    bank_details = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Bank account details for payments",
    )
    
    # Notes and remarks
    notes = Column(
        Text,
        nullable=True,
        comment="Internal notes about vendor",
    )
    
    special_instructions = Column(
        Text,
        nullable=True,
        comment="Special instructions for working with vendor",
    )
    
    # Metadata - renamed from 'metadata' to avoid conflict
    additional_data = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional vendor metadata",
    )
    
    # Relationships
    assignments = relationship(
        "VendorAssignment",
        back_populates="vendor",
        cascade="all, delete-orphan"
    )
    invoices = relationship(
        "VendorInvoice",
        back_populates="vendor",
        cascade="all, delete-orphan"
    )
    contracts = relationship(
        "VendorContract",
        back_populates="vendor",
        cascade="all, delete-orphan"
    )
    performance_reviews = relationship(
        "VendorPerformanceReview",
        back_populates="vendor",
        cascade="all, delete-orphan",
        order_by="VendorPerformanceReview.review_date.desc()"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "total_jobs >= 0",
            name="ck_vendor_total_jobs_positive"
        ),
        CheckConstraint(
            "completed_jobs >= 0",
            name="ck_vendor_completed_jobs_positive"
        ),
        CheckConstraint(
            "in_progress_jobs >= 0",
            name="ck_vendor_in_progress_jobs_positive"
        ),
        CheckConstraint(
            "cancelled_jobs >= 0",
            name="ck_vendor_cancelled_jobs_positive"
        ),
        CheckConstraint(
            "total_spent >= 0",
            name="ck_vendor_total_spent_positive"
        ),
        CheckConstraint(
            "average_job_cost >= 0",
            name="ck_vendor_average_cost_positive"
        ),
        CheckConstraint(
            "outstanding_amount >= 0",
            name="ck_vendor_outstanding_positive"
        ),
        CheckConstraint(
            "overall_rating >= 1 AND overall_rating <= 5",
            name="ck_vendor_overall_rating_range"
        ),
        CheckConstraint(
            "on_time_completion_rate >= 0 AND on_time_completion_rate <= 100",
            name="ck_vendor_on_time_rate_range"
        ),
        Index("idx_vendor_code", "vendor_code"),
        Index("idx_vendor_status", "vendor_status", "is_approved"),
        Index("idx_vendor_performance_tier", "performance_tier"),
        {"comment": "Maintenance vendor/contractor master records"}
    )
    
    def __repr__(self) -> str:
        return f"<MaintenanceVendor {self.vendor_code} - {self.company_name}>"
    
    @validates("overall_rating")
    def validate_overall_rating(self, key: str, value: Optional[Decimal]) -> Optional[Decimal]:
        """Validate overall rating is in valid range."""
        if value is not None and (value < 1 or value > 5):
            raise ValueError("Overall rating must be between 1 and 5")
        return value
    
    @hybrid_property
    def completion_rate(self) -> Decimal:
        """Calculate job completion rate."""
        if self.total_jobs == 0:
            return Decimal("0.00")
        return round(
            Decimal(self.completed_jobs) / Decimal(self.total_jobs) * 100,
            2
        )
    
    @hybrid_property
    def is_insurance_valid(self) -> bool:
        """Check if insurance is currently valid."""
        if not self.is_insured or not self.insurance_expiry_date:
            return False
        return self.insurance_expiry_date >= date.today()
    
    @hybrid_property
    def overall_performance_score(self) -> Decimal:
        """
        Calculate overall performance score.
        
        Weighted average of various performance metrics.
        """
        weights = {
            "completion": 0.3,
            "quality": 0.3,
            "timeliness": 0.4,
        }
        
        completion_score = float(self.completion_rate)
        quality_score = float(self.overall_rating or 3.0) * 20 if self.overall_rating else 60.0
        timeliness_score = float(self.on_time_completion_rate)
        
        overall = (
            completion_score * weights["completion"]
            + quality_score * weights["quality"]
            + timeliness_score * weights["timeliness"]
        )
        
        return round(Decimal(str(overall)), 2)
    
    def update_performance_metrics(self) -> None:
        """Update calculated performance metrics."""
        if self.completed_jobs > 0:
            self.average_job_cost = self.total_spent / self.completed_jobs
        else:
            self.average_job_cost = Decimal("0.00")
        
        # Update performance tier based on overall score
        score = float(self.overall_performance_score)
        if score >= 90:
            self.performance_tier = "platinum"
        elif score >= 80:
            self.performance_tier = "gold"
        elif score >= 70:
            self.performance_tier = "silver"
        elif score >= 60:
            self.performance_tier = "bronze"
        else:
            self.performance_tier = "needs_improvement"


class VendorContract(UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin, BaseModel):
    """
    Vendor contract management.
    
    Tracks contracts and agreements with vendors including
    terms, rates, and validity periods.
    """
    
    __tablename__ = "vendor_contracts"
    
    vendor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related vendor",
    )
    
    # Contract identification
    contract_number = Column(
        String(100),
        unique=True,
        nullable=False,
        comment="Unique contract number",
    )
    
    contract_title = Column(
        String(255),
        nullable=False,
        comment="Contract title/description",
    )
    
    contract_type = Column(
        String(50),
        nullable=False,
        comment="Contract type (annual, project, retainer)",
    )
    
    # Validity period
    start_date = Column(
        Date,
        nullable=False,
        comment="Contract start date",
    )
    
    end_date = Column(
        Date,
        nullable=False,
        comment="Contract end date",
    )
    
    # Contract value
    contract_value = Column(
        Numeric(12, 2),
        nullable=True,
        comment="Total contract value",
    )
    
    # Service scope
    service_categories = Column(
        ARRAY(String),
        nullable=False,
        default=[],
        comment="Services covered under contract",
    )
    
    scope_of_work = Column(
        Text,
        nullable=True,
        comment="Detailed scope of work",
    )
    
    # Rates and pricing
    rate_card = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Service rates and pricing",
    )
    
    # Payment terms
    payment_terms = Column(
        Text,
        nullable=False,
        comment="Payment terms and conditions",
    )
    
    payment_schedule = Column(
        JSONB,
        nullable=True,
        default=[],
        comment="Payment milestone schedule",
    )
    
    # SLA and performance
    sla_terms = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Service level agreement terms",
    )
    
    response_time_hours = Column(
        Integer,
        nullable=True,
        comment="Guaranteed response time in hours",
    )
    
    completion_time_days = Column(
        Integer,
        nullable=True,
        comment="Standard completion time in days",
    )
    
    # Contract status
    contract_status = Column(
        String(20),
        nullable=False,
        default="active",
        index=True,
        comment="Contract status (draft, active, expired, terminated)",
    )
    
    is_renewable = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether contract is renewable",
    )
    
    auto_renew = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether contract auto-renews",
    )
    
    # Termination
    termination_notice_days = Column(
        Integer,
        nullable=True,
        comment="Notice period for termination in days",
    )
    
    early_termination_penalty = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Penalty for early termination",
    )
    
    # Documents
    contract_document_url = Column(
        String(500),
        nullable=True,
        comment="URL to contract document",
    )
    
    attachments = Column(
        JSONB,
        nullable=True,
        default=[],
        comment="Contract attachments",
    )
    
    # Signatory details
    vendor_signatory = Column(
        String(255),
        nullable=True,
        comment="Vendor authorized signatory",
    )
    
    client_signatory = Column(
        String(255),
        nullable=True,
        comment="Client authorized signatory",
    )
    
    signed_date = Column(
        Date,
        nullable=True,
        comment="Contract signing date",
    )
    
    # Performance tracking
    total_work_orders = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total work orders under this contract",
    )
    
    total_billed = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total amount billed under contract",
    )
    
    # Notes
    notes = Column(
        Text,
        nullable=True,
        comment="Contract notes and remarks",
    )
    
    # Metadata - renamed from 'metadata' to avoid conflict
    additional_data = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional contract metadata",
    )
    
    # Relationships
    vendor = relationship(
        "MaintenanceVendor",
        back_populates="contracts"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "contract_value >= 0",
            name="ck_contract_value_positive"
        ),
        CheckConstraint(
            "response_time_hours > 0",
            name="ck_contract_response_time_positive"
        ),
        CheckConstraint(
            "completion_time_days > 0",
            name="ck_contract_completion_time_positive"
        ),
        CheckConstraint(
            "termination_notice_days >= 0",
            name="ck_contract_notice_days_positive"
        ),
        CheckConstraint(
            "early_termination_penalty >= 0",
            name="ck_contract_penalty_positive"
        ),
        CheckConstraint(
            "total_work_orders >= 0",
            name="ck_contract_work_orders_positive"
        ),
        CheckConstraint(
            "total_billed >= 0",
            name="ck_contract_total_billed_positive"
        ),
        Index("idx_contract_vendor_status", "vendor_id", "contract_status"),
        Index("idx_contract_end_date", "end_date"),
        {"comment": "Vendor contract management"}
    )
    
    def __repr__(self) -> str:
        return f"<VendorContract {self.contract_number} - {self.contract_status}>"
    
    @hybrid_property
    def is_active(self) -> bool:
        """Check if contract is currently active."""
        if self.contract_status != "active":
            return False
        today = date.today()
        return self.start_date <= today <= self.end_date
    
    @hybrid_property
    def is_expiring_soon(self) -> bool:
        """Check if contract is expiring within 30 days."""
        if not self.is_active:
            return False
        days_remaining = (self.end_date - date.today()).days
        return 0 < days_remaining <= 30
    
    @hybrid_property
    def days_remaining(self) -> int:
        """Calculate days remaining in contract."""
        if self.end_date < date.today():
            return 0
        return (self.end_date - date.today()).days


class VendorPerformanceReview(UUIDMixin, TimestampModel, BaseModel):
    """
    Vendor performance review records.
    
    Periodic performance reviews and evaluations of vendor work quality,
    timeliness, and overall service delivery.
    """
    
    __tablename__ = "vendor_performance_reviews"
    
    vendor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related vendor",
    )
    
    # Review period
    review_period_start = Column(
        Date,
        nullable=False,
        comment="Review period start date",
    )
    
    review_period_end = Column(
        Date,
        nullable=False,
        comment="Review period end date",
    )
    
    review_date = Column(
        Date,
        nullable=False,
        comment="Review conducted date",
    )
    
    # Reviewer
    reviewed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        comment="User who conducted review",
    )
    
    # Performance metrics
    jobs_completed = Column(
        Integer,
        nullable=False,
        comment="Jobs completed in review period",
    )
    
    on_time_completion_rate = Column(
        Numeric(5, 2),
        nullable=False,
        comment="On-time completion percentage",
    )
    
    average_delay_days = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Average delay in days for delayed jobs",
    )
    
    # Cost metrics
    total_spent = Column(
        Numeric(12, 2),
        nullable=False,
        comment="Total amount spent in period",
    )
    
    average_cost_per_job = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Average cost per job",
    )
    
    cost_variance_percentage = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Average cost variance from estimates",
    )
    
    # Quality ratings
    quality_rating = Column(
        Numeric(3, 2),
        nullable=False,
        comment="Overall quality rating (1-5)",
    )
    
    workmanship_rating = Column(
        Numeric(3, 2),
        nullable=True,
        comment="Workmanship quality rating (1-5)",
    )
    
    professionalism_rating = Column(
        Numeric(3, 2),
        nullable=True,
        comment="Professionalism rating (1-5)",
    )
    
    communication_rating = Column(
        Numeric(3, 2),
        nullable=True,
        comment="Communication rating (1-5)",
    )
    
    # Customer satisfaction
    customer_satisfaction_score = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Customer satisfaction score (0-100)",
    )
    
    complaint_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of complaints received",
    )
    
    # Strengths and weaknesses
    strengths = Column(
        Text,
        nullable=True,
        comment="Identified strengths",
    )
    
    areas_for_improvement = Column(
        Text,
        nullable=True,
        comment="Areas needing improvement",
    )
    
    # Recommendations
    recommendation = Column(
        String(50),
        nullable=False,
        comment="Recommendation (continue, warning, probation, terminate)",
    )
    
    recommended_for_renewal = Column(
        Boolean,
        nullable=True,
        comment="Whether recommended for contract renewal",
    )
    
    # Action items
    action_items = Column(
        JSONB,
        nullable=True,
        default=[],
        comment="Action items for vendor",
    )
    
    follow_up_required = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether follow-up review is required",
    )
    
    follow_up_date = Column(
        Date,
        nullable=True,
        comment="Scheduled follow-up date",
    )
    
    # Review notes
    review_notes = Column(
        Text,
        nullable=True,
        comment="Detailed review notes",
    )
    
    # Metadata - renamed from 'metadata' to avoid conflict
    additional_data = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional review metadata",
    )
    
    # Relationships
    vendor = relationship(
        "MaintenanceVendor",
        back_populates="performance_reviews"
    )
    reviewer = relationship("User")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "jobs_completed >= 0",
            name="ck_review_jobs_completed_positive"
        ),
        CheckConstraint(
            "on_time_completion_rate >= 0 AND on_time_completion_rate <= 100",
            name="ck_review_on_time_rate_range"
        ),
        CheckConstraint(
            "total_spent >= 0",
            name="ck_review_total_spent_positive"
        ),
        CheckConstraint(
            "average_cost_per_job >= 0",
            name="ck_review_average_cost_positive"
        ),
        CheckConstraint(
            "quality_rating >= 1 AND quality_rating <= 5",
            name="ck_review_quality_rating_range"
        ),
        CheckConstraint(
            "workmanship_rating >= 1 AND workmanship_rating <= 5",
            name="ck_review_workmanship_rating_range"
        ),
        CheckConstraint(
            "professionalism_rating >= 1 AND professionalism_rating <= 5",
            name="ck_review_professionalism_rating_range"
        ),
        CheckConstraint(
            "communication_rating >= 1 AND communication_rating <= 5",
            name="ck_review_communication_rating_range"
        ),
        CheckConstraint(
            "complaint_count >= 0",
            name="ck_review_complaint_count_positive"
        ),
        Index("idx_review_vendor_date", "vendor_id", "review_date"),
        Index("idx_review_recommendation", "recommendation"),
        {"comment": "Vendor performance review records"}
    )
    
    def __repr__(self) -> str:
        return f"<VendorPerformanceReview vendor={self.vendor_id} date={self.review_date}>"
    
    @validates("quality_rating", "workmanship_rating", "professionalism_rating", "communication_rating")
    def validate_ratings(self, key: str, value: Optional[Decimal]) -> Optional[Decimal]:
        """Validate ratings are in valid range."""
        if value is not None and (value < 1 or value > 5):
            raise ValueError(f"{key} must be between 1 and 5")
        return value
    
    @hybrid_property
    def overall_score(self) -> Decimal:
        """Calculate overall performance score."""
        ratings = [
            float(self.quality_rating),
            float(self.workmanship_rating or self.quality_rating),
            float(self.professionalism_rating or self.quality_rating),
            float(self.communication_rating or self.quality_rating),
        ]
        return round(Decimal(str(sum(ratings) / len(ratings))), 2)